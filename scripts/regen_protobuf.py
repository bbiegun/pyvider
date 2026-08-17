#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Regenerate the tfprotov6 protobuf stubs from the vendored ``tfplugin6.proto``.

The generated ``*_pb2*`` files are committed to the repository, so this script is
the only supported way to refresh them -- do not hand-edit the output.

Three things here are deliberate and easy to get wrong when running ``protoc`` by
hand:

1.  ``protoc`` is invoked with ``--proto_path`` pointing at the *directory*
    holding the proto, not at ``src/``. That keeps the embedded descriptor name
    as ``tfplugin6.proto`` rather than the full package path. The descriptor pool
    keys off that name, and every other tfplugin6 implementation registers the
    short form.
2.  Because of (1), ``protoc`` emits a bare ``import tfplugin6_pb2`` into the gRPC
    stub, which is not importable from within the package. The import is
    rewritten to the package-absolute form afterwards.
3.  The output is generated code: ruff and mypy both exclude it, and nothing here
    reformats it. The ``.py`` pair gets the project's SPDX header and trailing
    marker so it matches the rest of the tree; the ``.pyi`` gets neither, as no
    ``.pyi`` in this repo carries them. protoc's own "DO NOT EDIT" banner is left
    in place -- it records which protobuf/grpcio gencode version produced the
    file, which matters when chasing wire-format differences.

``--check`` makes two independent comparisons. It compares regenerated output
against the committed stubs with the generator's version stamps masked, so a
newer ``grpcio-tools`` cannot report "stubs are out of date" over banner churn
alone; and it compares those masked stamps against the ``grpcio`` and
``protobuf`` floors declared in ``pyproject.toml``, because the generated code
enforces them at import. A toolchain upgrade that moves a floor therefore fails
with a named mismatch rather than being silently absorbed -- raise the floors and
regenerate in the same change.

Usage::

    # regenerate from the currently vendored proto
    python scripts/regen_protobuf.py

    # refresh the vendored proto from a Terraform checkout first, then regenerate
    python scripts/regen_protobuf.py --from-terraform ~/code/tf/terraform

    # check that the committed stubs match the vendored proto (CI-friendly)
    python scripts/regen_protobuf.py --check
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

from provide.foundation import perr, pout

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = REPO_ROOT / "src" / "pyvider" / "protocols" / "tfprotov6" / "protobuf"
PROTO_PATH = PROTO_DIR / "tfplugin6.proto"

# Path to the proto within a Terraform source checkout. Terraform publishes the
# authoritative copy under docs/plugin-protocol/; internal/tfplugin6/ is a symlink
# to it in some releases, so the docs path is the one to read.
TERRAFORM_PROTO_RELPATH = Path("docs") / "plugin-protocol" / "tfplugin6.proto"

# Generated artifacts. Only the .py pair carries the SPDX header.
GENERATED_PY = ("tfplugin6_pb2.py", "tfplugin6_pb2_grpc.py")
GENERATED_FILES = (*GENERATED_PY, "tfplugin6_pb2.pyi")

SPDX_HEADER = (
    "# \n"
    "# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.\n"
    "# SPDX-License-Identifier: Apache-2.0\n"
    "#\n"
    "\n"
)

# End-of-file marker used by essentially every .py in this repo.
FOOTER = "\n# 🐍🏗️🔚\n"

# protoc writes a bare module import into the gRPC stub; rewrite it so the stub is
# importable as part of the pyvider package.
GRPC_IMPORT_BEFORE = "import tfplugin6_pb2 as tfplugin6__pb2"
GRPC_IMPORT_AFTER = "from pyvider.protocols.tfprotov6.protobuf import tfplugin6_pb2 as tfplugin6__pb2"

# grpcio-tools stamps its own version into generated output in three places. Those
# values are the floors pyproject declares -- tfplugin6_pb2.py enforces its triple
# via ValidateProtobufRuntimeVersion, and tfplugin6_pb2_grpc.py raises below
# GRPC_GENERATED_VERSION -- so --check masks them for the proto-drift comparison
# and checks them separately against pyproject. Masking alone would let a
# toolchain upgrade silently move a floor.
PROTOBUF_BANNER_RE = re.compile(r"^# Protobuf Python Version: .*$", re.MULTILINE)
PROTOBUF_RUNTIME_RE = re.compile(
    r"(_runtime_version\.ValidateProtobufRuntimeVersion\(\s*"
    r"_runtime_version\.Domain\.\w+,\s*)\d+,\s*\d+,\s*\d+,",
)
GRPC_GENERATED_RE = re.compile(r"^GRPC_GENERATED_VERSION = '.*'$", re.MULTILINE)

MASK = "<toolchain-version>"


def mask_toolchain_versions(text: str) -> str:
    """Blank out generator-version tokens so only proto-derived drift compares."""
    text = PROTOBUF_BANNER_RE.sub(f"# Protobuf Python Version: {MASK}", text)
    text = PROTOBUF_RUNTIME_RE.sub(rf"\g<1>{MASK},", text)
    return GRPC_GENERATED_RE.sub(f"GRPC_GENERATED_VERSION = '{MASK}'", text)


PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

# Which generated stamp corresponds to which declared dependency.
FLOOR_SOURCES = (
    ("protobuf", "tfplugin6_pb2.py", PROTOBUF_BANNER_RE),
    ("grpcio", "tfplugin6_pb2_grpc.py", GRPC_GENERATED_RE),
)

_VERSION_IN_LINE_RE = re.compile(r"(\d+\.\d+\.\d+)")


def extract_generated_versions(out_dir: Path) -> tuple[str, str]:
    """Return (protobuf_version, grpc_version) as stamped into generated output."""
    found: list[str] = []
    for package, filename, pattern in FLOOR_SOURCES:
        match = pattern.search((out_dir / filename).read_text())
        version = _VERSION_IN_LINE_RE.search(match.group(0)) if match else None
        if version is None:
            raise SystemExit(
                f"No {package} version stamp found in {filename}; "
                "protoc output layout changed, update this script."
            )
        found.append(version.group(1))
    return found[0], found[1]


def declared_floor(package: str) -> str | None:
    """Return the >= floor pyproject declares for ``package``, if any."""
    data = tomllib.loads(PYPROJECT_PATH.read_text())
    for requirement in data["project"]["dependencies"]:
        name = re.split(r"[<>=!~\[; ]", requirement.strip())[0]
        if name == package:
            floor = re.search(r">=\s*([\d.]+)", requirement)
            return floor.group(1) if floor else None
    return None


def check_floor_drift(out_dir: Path) -> list[str]:
    """Return a message per generated stamp that disagrees with its declared floor."""
    protobuf_version, grpc_version = extract_generated_versions(out_dir)
    problems = []
    for package, generated in (("protobuf", protobuf_version), ("grpcio", grpc_version)):
        floor = declared_floor(package)
        if floor != generated:
            problems.append(
                f"stubs were generated against {package} {generated}, but pyproject "
                f"declares {package}>={floor}. The generated stubs enforce their "
                f"version at import, so raise the floor together with the stubs."
            )
    return problems


def describe_proto_version(proto_path: Path) -> str:
    """Return the protocol version recorded in the proto's header comment."""
    for line in proto_path.read_text().splitlines()[:30]:
        if "protocol version" in line:
            return line.lstrip("/ ").strip()
    return "unknown protocol version"


def sync_proto_from_terraform(terraform_root: Path) -> None:
    """Copy the tfplugin6 proto out of a Terraform checkout into the package."""
    source = terraform_root.expanduser().resolve() / TERRAFORM_PROTO_RELPATH
    if not source.is_file():
        raise SystemExit(f"No tfplugin6 proto at {source}")

    shutil.copyfile(source, PROTO_PATH)
    pout(f"Vendored {source} -> {PROTO_PATH.relative_to(REPO_ROOT)} ({describe_proto_version(PROTO_PATH)})")


def _run(argv: list[str], what: str) -> None:
    """Run a subprocess, surfacing its output and aborting on failure."""
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        perr(result.stdout.strip())
        perr(result.stderr.strip())
        raise SystemExit(f"{what} failed with exit code {result.returncode}")


def run_protoc(out_dir: Path) -> None:
    """Generate the message, gRPC, and stub-file outputs into ``out_dir``."""
    _run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"--proto_path={PROTO_DIR}",
            f"--python_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            f"--pyi_out={out_dir}",
            str(PROTO_PATH),
        ],
        "protoc",
    )


def rewrite_grpc_import(grpc_stub: Path) -> None:
    """Point the gRPC stub's message import at the package-absolute module."""
    content = grpc_stub.read_text()
    if GRPC_IMPORT_BEFORE not in content:
        raise SystemExit(
            f"Expected to find {GRPC_IMPORT_BEFORE!r} in {grpc_stub.name}; "
            "protoc output layout changed, update this script."
        )
    grpc_stub.write_text(content.replace(GRPC_IMPORT_BEFORE, GRPC_IMPORT_AFTER, 1))


def generate(out_dir: Path) -> list[Path]:
    """Produce the finished stub set in ``out_dir`` and return the written paths."""
    run_protoc(out_dir)
    rewrite_grpc_import(out_dir / "tfplugin6_pb2_grpc.py")

    for name in GENERATED_PY:
        path = out_dir / name
        path.write_text(SPDX_HEADER + path.read_text().rstrip("\n") + "\n" + FOOTER)

    return [out_dir / name for name in GENERATED_FILES]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--from-terraform",
        type=Path,
        metavar="TERRAFORM_ROOT",
        help="Copy the proto out of this Terraform checkout before regenerating.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed stubs differ from a fresh generation instead of rewriting them.",
    )
    args = parser.parse_args()

    if args.from_terraform:
        if args.check:
            parser.error("--check cannot be combined with --from-terraform")
        sync_proto_from_terraform(args.from_terraform)

    pout(f"Generating from {PROTO_PATH.relative_to(REPO_ROOT)} ({describe_proto_version(PROTO_PATH)})")

    with tempfile.TemporaryDirectory() as tmp:
        staged = generate(Path(tmp))

        if args.check:
            stale = [
                p.name
                for p in staged
                if mask_toolchain_versions(p.read_text())
                != mask_toolchain_versions((PROTO_DIR / p.name).read_text())
            ]
            drift = check_floor_drift(Path(tmp))
            if stale:
                perr("Committed stubs are out of date: " + ", ".join(stale))
                perr("Run: python scripts/regen_protobuf.py")
            for problem in drift:
                perr(problem)
            if stale or drift:
                return 1
            pout("Committed stubs are up to date, and declared floors match.")
            return 0

        for path in staged:
            shutil.copyfile(path, PROTO_DIR / path.name)
            pout(f"Wrote {(PROTO_DIR / path.name).relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())


# 🐍🏗️🔚
