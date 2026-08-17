# Suite Dependency Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the ten core pyvider-suite packages to current dependencies with floor-only version constraints, every test suite green, and versions aligned for a co-release.

**Architecture:** Three enabling changes land first — a toolchain-tolerant `regen_protobuf.py --check`, the removal of the pin it was propping up, and `[tool.uv.sources]` path entries so sibling repos resolve from source. Then the ten repositories are upgraded in six dependency-ordered waves, each wave a barrier. Version alignment and a final cap audit close it out.

**Tech Stack:** Python 3.11+, uv (lock/sync/resolution), pytest, ruff, mypy, grpcio-tools/protoc, GitHub Actions via `provide-io/ci-tooling`.

**Spec:** `docs/superpowers/specs/2026-08-16-suite-dependency-refresh-design.md`

## Global Constraints

- **Floor-only version constraints.** No `<`, `<=`, `==`, or `~=` on any dependency in an in-scope repository. Express every requirement as a `>=` floor.
- **One documented exception path:** the `cryptography` cap in `terraform-provider-pyvider` may be restored *only* after an observed Windows-ARM CI failure, with a comment naming that failure.
- **No dependency is upgraded without running the dependent's test suite.**
- Python floor stays `>=3.11` across the suite.
- Locks are regenerated with uv, never hand-edited.
- Waves are barriers: every repository in wave *N* is green before wave *N+1* begins.
- Fallout from an upgrade is fixed **in the consumer**, never by capping the dependency.
- In-scope repositories (10): `provide-foundation`, `provide-testkit`, `pyvider-cty`, `pyvider-rpcplugin`, `pyvider-hcl`, `pyvider`, `plating`, `pyvider-components`, `tofusoup`, `terraform-provider-pyvider`.
- Repository root paths are `/Volumes/data/pyv/<repo-name>`.
- Commit messages must not mention Claude or AI assistance, and must not carry a `Co-Authored-By: Claude` trailer.
- Never bypass commit signing (`--no-gpg-sign`, `--no-verify`). If signing fails, stop and ask.

## File Structure

| File | Responsibility |
|---|---|
| `scripts/regen_protobuf.py` (pyvider) | Gains version masking + floor extraction; `--check` grows two independent comparisons |
| `scripts/__init__.py` (pyvider) | New, empty — makes `scripts.regen_protobuf` importable by tests |
| `tests/scripts/test_regen_protobuf.py` (pyvider) | New — unit tests for masking, extraction, and floor comparison |
| `pyproject.toml` (each of 10 repos) | Cap removals, `[tool.uv.sources]` entries, floor rewrites |
| `uv.lock` (each of 10 repos) | Regenerated |
| `VERSION` (each of 10 repos) | Bumped to `0.5.0` |
| `.github/workflows/ci.yml` (terraform-provider-pyvider) | Windows-ARM enablement so the cryptography ruling has a mechanism |

---

### Task 1: Toolchain-version masking for proto-drift comparison

`scripts/regen_protobuf.py --check` currently byte-compares generated stubs against committed ones with `filecmp.cmp` (line 182). The generated output embeds the generating toolchain's version in three places, so any `grpcio-tools` movement reports the stubs as stale over pure banner churn. This task makes the comparison ignore those tokens. Task 2 then checks them deliberately.

**Files:**
- Create: `/Volumes/data/pyv/pyvider/scripts/__init__.py`
- Create: `/Volumes/data/pyv/pyvider/tests/scripts/__init__.py`
- Create: `/Volumes/data/pyv/pyvider/tests/scripts/test_regen_protobuf.py`
- Modify: `/Volumes/data/pyv/pyvider/scripts/regen_protobuf.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `mask_toolchain_versions(text: str) -> str` in `scripts/regen_protobuf.py`.

The three version-bearing locations, verified against the committed stubs:

| File | Line | Content |
|---|---|---|
| `tfplugin6_pb2.py` | 10 | `# Protobuf Python Version: 7.35.1` |
| `tfplugin6_pb2.py` | 19–21 | `7,` `35,` `1,` — args to `ValidateProtobufRuntimeVersion` |
| `tfplugin6_pb2_grpc.py` | 13 | `GRPC_GENERATED_VERSION = '1.83.0'` |

- [ ] **Step 1: Create the empty package markers**

```bash
cd /Volumes/data/pyv/pyvider
touch scripts/__init__.py tests/scripts/__init__.py
```

`pyproject.toml` sets `pythonpath = ["src", "."]`, so `scripts/__init__.py` makes `scripts.regen_protobuf` importable in tests. `[tool.setuptools.packages.find]` uses `where = ["src"]`, so a root-level `scripts` package is never packaged into the distribution.

- [ ] **Step 2: Write the failing test**

Create `/Volumes/data/pyv/pyvider/tests/scripts/test_regen_protobuf.py`:

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Unit tests for the protobuf regeneration script's drift checks."""

from scripts.regen_protobuf import mask_toolchain_versions

PB2_SAMPLE = """# Protobuf Python Version: 7.35.1
\"\"\"Generated protocol buffer code.\"\"\"
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    7,
    35,
    1,
    '',
    'tfplugin6.proto'
)
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\\n\\x0ftfplugin6.proto')
"""

GRPC_SAMPLE = """GRPC_GENERATED_VERSION = '1.83.0'
GRPC_VERSION = grpc.__version__
"""


def test_masking_makes_differing_toolchain_versions_compare_equal():
    """A pure toolchain bump must not read as proto drift."""
    newer = (
        PB2_SAMPLE.replace("7.35.1", "7.36.0")
        .replace("    7,\n    35,\n    1,", "    7,\n    36,\n    0,")
    )
    assert newer != PB2_SAMPLE
    assert mask_toolchain_versions(newer) == mask_toolchain_versions(PB2_SAMPLE)


def test_masking_makes_differing_grpc_versions_compare_equal():
    """The grpc stub's generated-version constant is toolchain noise too."""
    newer = GRPC_SAMPLE.replace("1.83.0", "1.84.0")
    assert newer != GRPC_SAMPLE
    assert mask_toolchain_versions(newer) == mask_toolchain_versions(GRPC_SAMPLE)


def test_masking_preserves_real_proto_drift():
    """Masking must not blind the check to an actual change in the descriptor."""
    changed = PB2_SAMPLE.replace("tfplugin6.proto')", "tfplugin7.proto')")
    assert mask_toolchain_versions(changed) != mask_toolchain_versions(PB2_SAMPLE)


def test_masking_preserves_drift_in_unrelated_numbers():
    """Only the known version tokens are masked, not every integer."""
    changed = PB2_SAMPLE.replace("_descriptor_pool.Default()", "_descriptor_pool.Other()")
    assert mask_toolchain_versions(changed) != mask_toolchain_versions(PB2_SAMPLE)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd /Volumes/data/pyv/pyvider && uv run pytest tests/scripts/test_regen_protobuf.py -v`
Expected: FAIL — `ImportError: cannot import name 'mask_toolchain_versions'`

- [ ] **Step 4: Implement the masking**

In `scripts/regen_protobuf.py`, add `import re` to the imports (it is not currently imported), then add below the `GRPC_IMPORT_AFTER` constant (around line 87).

This repo sets `force-sort-within-sections = true` in `[tool.ruff.lint.isort]`, which sorts `import x` and `from x import y` together alphabetically — so `re` belongs between `from pathlib import Path` and `import shutil`. Rather than placing it by hand, run `uv run ruff check --fix .` after editing and let the formatter settle it.

```python
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd /Volumes/data/pyv/pyvider && uv run pytest tests/scripts/test_regen_protobuf.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Switch `--check` to the masked comparison**

In `main()`, replace the `filecmp.cmp` line (line 182):

```python
        if args.check:
            stale = [
                p.name
                for p in staged
                if mask_toolchain_versions(p.read_text())
                != mask_toolchain_versions((PROTO_DIR / p.name).read_text())
            ]
            if stale:
                perr("Committed stubs are out of date: " + ", ".join(stale))
                perr("Run: python scripts/regen_protobuf.py")
                return 1
```

Remove the now-unused `import filecmp` from the imports.

- [ ] **Step 7: Verify `--check` still passes against the committed stubs**

Run: `cd /Volumes/data/pyv/pyvider && uv run python scripts/regen_protobuf.py --check`
Expected: `Committed stubs are up to date.`

- [ ] **Step 8: Commit**

```bash
cd /Volumes/data/pyv/pyvider
git add scripts/__init__.py scripts/regen_protobuf.py tests/scripts/
git commit -m "refactor(scripts): compare stubs on proto content, not toolchain banners

--check byte-compared generated output whose banners embed the generating
grpcio-tools version, so any toolchain movement reported the stubs as stale
over churn that means nothing. The comparison now masks those tokens and
answers only the question it is asking: do the committed stubs match the
vendored proto. The masked values are checked separately against the
declared floors in the next commit."
```

---

### Task 2: Floor-drift check against declared dependency floors

Masking alone removes a real signal: the embedded versions *are* the floors `pyproject.toml` declares, and they are enforced at import. This task checks them deliberately, so a toolchain upgrade that genuinely moves a floor fails loudly instead of being silently frozen out.

**Files:**
- Modify: `/Volumes/data/pyv/pyvider/scripts/regen_protobuf.py`
- Modify: `/Volumes/data/pyv/pyvider/tests/scripts/test_regen_protobuf.py`

**Interfaces:**
- Consumes: `mask_toolchain_versions(text: str) -> str` from Task 1.
- Produces: `extract_generated_versions(out_dir: Path) -> tuple[str, str]` returning `(protobuf_version, grpc_version)`; `declared_floor(package: str) -> str | None`; `check_floor_drift(out_dir: Path) -> list[str]` returning human-readable mismatch messages.

- [ ] **Step 1: Write the failing tests**

Append to `/Volumes/data/pyv/pyvider/tests/scripts/test_regen_protobuf.py`:

```python
import pytest

from scripts.regen_protobuf import (
    declared_floor,
    extract_generated_versions,
)


def _write_stub_pair(tmp_path, protobuf_version: str, grpc_version: str):
    """Write a minimal generated-stub pair carrying the given versions."""
    pb2 = PB2_SAMPLE.replace("7.35.1", protobuf_version)
    grpc = GRPC_SAMPLE.replace("1.83.0", grpc_version)
    (tmp_path / "tfplugin6_pb2.py").write_text(pb2)
    (tmp_path / "tfplugin6_pb2_grpc.py").write_text(grpc)
    return tmp_path


def test_extract_generated_versions_reads_both_stamps(tmp_path):
    out = _write_stub_pair(tmp_path, "7.36.0", "1.84.0")
    assert extract_generated_versions(out) == ("7.36.0", "1.84.0")


def test_extract_generated_versions_rejects_missing_stamp(tmp_path):
    (tmp_path / "tfplugin6_pb2.py").write_text("no banner here\n")
    (tmp_path / "tfplugin6_pb2_grpc.py").write_text(GRPC_SAMPLE)
    with pytest.raises(SystemExit):
        extract_generated_versions(tmp_path)


def test_declared_floor_reads_pyproject():
    """The real pyproject must declare floors for both packages."""
    assert declared_floor("protobuf") is not None
    assert declared_floor("grpcio") is not None


def test_declared_floor_returns_none_for_absent_package():
    assert declared_floor("definitely-not-a-dependency") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Volumes/data/pyv/pyvider && uv run pytest tests/scripts/test_regen_protobuf.py -v`
Expected: FAIL — `ImportError: cannot import name 'declared_floor'`

- [ ] **Step 3: Implement extraction and floor lookup**

Add `import tomllib` to the imports of `scripts/regen_protobuf.py`, then add after `mask_toolchain_versions`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Volumes/data/pyv/pyvider && uv run pytest tests/scripts/test_regen_protobuf.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Wire floor drift into `--check`**

In `main()`, extend the `--check` branch so both comparisons run and both can fail:

```python
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
```

- [ ] **Step 6: Verify `--check` passes on the current tree**

Run: `cd /Volumes/data/pyv/pyvider && uv run python scripts/regen_protobuf.py --check`
Expected: `Committed stubs are up to date, and declared floors match.`

- [ ] **Step 7: Prove the floor-drift check can actually fail**

This step exists because a guard that never fires is worse than the pin it replaced — it looks like coverage while measuring nothing. Temporarily edit `pyproject.toml`, changing `"protobuf>=7.35.1"` to `"protobuf>=7.0.0"`, then run:

Run: `cd /Volumes/data/pyv/pyvider && uv run python scripts/regen_protobuf.py --check`
Expected: exit code 1, with a message reading `stubs were generated against protobuf 7.35.1, but pyproject declares protobuf>=7.0.0`

Then revert the edit:

```bash
cd /Volumes/data/pyv/pyvider && git checkout pyproject.toml
```

Confirm `--check` returns to passing before continuing. If the check passed with the mutated floor, the wiring is wrong — fix it before committing.

- [ ] **Step 8: Commit**

```bash
cd /Volumes/data/pyv/pyvider
git add scripts/regen_protobuf.py tests/scripts/test_regen_protobuf.py
git commit -m "feat(scripts): check generated stubs against declared dependency floors

Masking the toolchain banners removed a real signal: those stamps are the
floors pyproject declares, and the stubs enforce them at import --
tfplugin6_pb2.py through ValidateProtobufRuntimeVersion, the grpc stub by
raising below GRPC_GENERATED_VERSION. --check now extracts both stamps and
compares them to the declared floors, so a toolchain upgrade that moves a
floor fails with a message naming both versions instead of being frozen out
by a pin. Verified by mutating the declared floor and confirming the check
fails, so the guard is not passing vacuously."
```

---

### Task 3: Replace the `grpcio-tools` pin with a floor

**Files:**
- Modify: `/Volumes/data/pyv/pyvider/pyproject.toml:65-71`

**Interfaces:**
- Consumes: the toolchain-tolerant `--check` from Tasks 1 and 2.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Replace the pin and its rationale comment**

In `[dependency-groups] dev`, replace the pinned entry and the comment block above it (lines 65–71) with:

```toml
dev = [
    "provide-testkit[pyvider-dev]>=0.4.0",
    # Floor only. scripts/regen_protobuf.py --check compares stub content with
    # toolchain version stamps masked, and checks those stamps separately against
    # the grpcio/protobuf floors declared above, so a newer grpcio-tools no longer
    # reports the stubs as stale over banner churn.
    "grpcio-tools>=1.83.0",
]
```

- [ ] **Step 2: Re-resolve and sync**

```bash
cd /Volumes/data/pyv/pyvider
uv lock --upgrade-package grpcio-tools
uv sync --all-groups
```

- [ ] **Step 3: Verify the check passes against whatever grpcio-tools resolved**

```bash
cd /Volumes/data/pyv/pyvider
uv run python -c "import grpc_tools; print(grpc_tools.__file__)"
uv run python scripts/regen_protobuf.py --check
```

Expected: `--check` passes. If it reports floor drift, that is the check working correctly — the newer toolchain generates stubs declaring a higher floor. Regenerate and raise the floors together:

```bash
cd /Volumes/data/pyv/pyvider
uv run python scripts/regen_protobuf.py
# then raise grpcio>= / protobuf>= in pyproject.toml to the versions now stamped
uv run python scripts/regen_protobuf.py --check
```

- [ ] **Step 4: Run the full gate**

```bash
cd /Volumes/data/pyv/pyvider
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/data/pyv/pyvider
git add pyproject.toml uv.lock src/pyvider/protocols/tfprotov6/protobuf/
git commit -m "build: float grpcio-tools now that --check tolerates toolchain drift

The exact pin existed only to keep --check from reporting banner churn as
stale stubs. That comparison no longer depends on the toolchain version, so
the pin has nothing left to protect and becomes a floor."
```

---

### Task 4: Cross-repository source resolution via `[tool.uv.sources]`

No repository declares `[tool.uv.workspace]` or `[tool.uv.sources]` today; each resolves siblings from PyPI. That is why validating an unreleased pairing has required improvised `PYTHONPATH` overlays, and why cross-consumer test runs have historically proved nothing — they ran against published releases rather than the code under test.

**Files:**
- Modify: `pyproject.toml` in all 10 in-scope repositories

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: source resolution that every later wave task depends on.

The in-suite runtime edges each repository must declare:

| Repository | `[tool.uv.sources]` entries needed |
|---|---|
| `provide-foundation` | (none) |
| `provide-testkit` | provide-foundation |
| `pyvider-cty` | provide-foundation |
| `pyvider-rpcplugin` | provide-foundation |
| `pyvider` | provide-foundation, pyvider-cty, pyvider-rpcplugin |
| `pyvider-hcl` | provide-foundation, pyvider, pyvider-cty |
| `plating` | provide-foundation, pyvider, pyvider-cty |
| `pyvider-components` | plating, provide-foundation, pyvider, pyvider-cty, pyvider-rpcplugin |
| `tofusoup` | plating, provide-foundation, pyvider |
| `terraform-provider-pyvider` | provide-foundation, pyvider, pyvider-components |

Repositories also declaring `provide-testkit` in a dev/test group add a `provide-testkit` entry too.

- [ ] **Step 1: Add the sources block to each repository**

For each repository, append to its `pyproject.toml`. The full example for `pyvider`:

```toml
# Local development resolves sibling suite packages from source, so a change in
# one repo is exercised by its consumers immediately rather than at release. uv
# does not propagate a dependency's sources into published metadata, so this is
# invisible to consumers of the built wheel. CI passes --no-sources to verify the
# published story instead.
[tool.uv.sources]
provide-foundation = { path = "../provide-foundation", editable = true }
pyvider-cty = { path = "../pyvider-cty", editable = true }
pyvider-rpcplugin = { path = "../pyvider-rpcplugin", editable = true }
```

For `pyvider-components`, the block is:

```toml
[tool.uv.sources]
plating = { path = "../plating", editable = true }
provide-foundation = { path = "../provide-foundation", editable = true }
pyvider = { path = "../pyvider", editable = true }
pyvider-cty = { path = "../pyvider-cty", editable = true }
pyvider-rpcplugin = { path = "../pyvider-rpcplugin", editable = true }
```

Follow the same pattern for the remaining repositories using the table above. `provide-foundation` gets no block.

- [ ] **Step 2: Verify each repository still resolves**

```bash
for r in provide-testkit pyvider-cty pyvider-rpcplugin pyvider pyvider-hcl plating pyvider-components tofusoup terraform-provider-pyvider; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv lock 2>&1 | tail -3)
done
```

Expected: each locks without error. A failure here means a path is wrong or a sibling's version does not satisfy the declared floor — fix the path, or note the floor conflict for the wave that owns that repository.

- [ ] **Step 3: Verify sources are genuinely in effect**

```bash
cd /Volumes/data/pyv/pyvider-components
uv sync --all-groups
uv run python -c "import pyvider, pathlib; print(pathlib.Path(pyvider.__file__).resolve())"
```

Expected: a path under `/Volumes/data/pyv/pyvider/src/`, **not** under `.venv/lib/.../site-packages`. If it still points at site-packages, the sources block is not being applied and the rest of this plan will silently test the wrong code.

- [ ] **Step 4: Commit, one commit per repository**

```bash
cd /Volumes/data/pyv/<repo>
git add pyproject.toml uv.lock
git commit -m "build: resolve sibling suite packages from source in local development

Each repo resolved its siblings from PyPI, so testing an unreleased pairing
meant a PYTHONPATH overlay that only worked when someone remembered -- and
cross-consumer runs that nobody remembered to set up reported passes against
the last release rather than the code under test. uv does not propagate a
dependency's sources into published metadata, so this changes local
development only; CI uses --no-sources for the published story."
```

---

### Task 5: Wave 1 — provide-foundation

The base of the suite; everything else depends on it.

**Files:**
- Modify: `/Volumes/data/pyv/provide-foundation/pyproject.toml`, `uv.lock`

**Interfaces:**
- Consumes: source resolution from Task 4.
- Produces: a green `provide-foundation` that waves 2 onward build against.

- [ ] **Step 1: Upgrade all dependencies**

```bash
cd /Volumes/data/pyv/provide-foundation
uv lock --upgrade
uv sync --all-groups
```

- [ ] **Step 2: Run the full gate**

```bash
cd /Volumes/data/pyv/provide-foundation
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

- [ ] **Step 3: Fix fallout in the consumer**

If any check fails, fix `provide-foundation`'s own code to work with the new dependency versions. Do not add an upper bound to make a failure go away. If a dependency's new major has no viable migration, stop and record the specific incompatibility rather than capping.

- [ ] **Step 4: Re-run the gate until green**

Repeat Step 2 until all four commands pass.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/data/pyv/provide-foundation
git add -A
git commit -m "build: upgrade dependencies to current releases

Wave 1 of the suite dependency refresh. Upgrade and any fallout fixes land
together so the change is revertible as a unit."
```

---

### Task 6: Wave 2 — provide-testkit, pyvider-cty, pyvider-rpcplugin

Three independent repositories that each depend only on `provide-foundation`. Same-shape work, so they are handled as one batch, but each gets its own commit.

**Files:**
- Modify: `pyproject.toml` and `uv.lock` in `/Volumes/data/pyv/provide-testkit`, `/Volumes/data/pyv/pyvider-cty`, `/Volumes/data/pyv/pyvider-rpcplugin`

**Interfaces:**
- Consumes: green `provide-foundation` from Task 5; source resolution from Task 4.
- Produces: green wave-2 packages for `pyvider` in Task 7.

**Note on `pyvider-cty`:** its local `VERSION` reads `0.5.0` and it carries roughly 25 breaking changes relative to the published 0.4.0. It is actively developed in a parallel session. Before upgrading, confirm its working tree is clean and coordinate if it is not.

- [ ] **Step 1: Upgrade each repository**

```bash
for r in provide-testkit pyvider-cty pyvider-rpcplugin; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv lock --upgrade && uv sync --all-groups)
done
```

- [ ] **Step 2: Run each gate**

```bash
for r in provide-testkit pyvider-cty pyvider-rpcplugin; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src/)
done
```

- [ ] **Step 3: Fix fallout per repository**

Fix failures in the repository that owns them. No caps.

- [ ] **Step 4: Re-run until all three are green**

- [ ] **Step 5: Commit each repository separately**

```bash
cd /Volumes/data/pyv/<repo>
git add -A
git commit -m "build: upgrade dependencies to current releases

Wave 2 of the suite dependency refresh."
```

---

### Task 7: Wave 3 — pyvider

**Files:**
- Modify: `/Volumes/data/pyv/pyvider/pyproject.toml`, `uv.lock`

**Interfaces:**
- Consumes: green wave-2 packages from Task 6.
- Produces: a green `pyvider` for waves 4 and 5.

- [ ] **Step 1: Upgrade**

```bash
cd /Volumes/data/pyv/pyvider
uv lock --upgrade
uv sync --all-groups
```

- [ ] **Step 2: Run the full gate, including the protobuf check**

```bash
cd /Volumes/data/pyv/pyvider
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run python scripts/regen_protobuf.py --check
```

Expected: all green. `pytest -q` should report the same count as before the upgrade — currently 1497 passed.

- [ ] **Step 3: Handle floor drift if `--check` reports it**

A newer `grpcio-tools` may generate stubs declaring higher floors. That is the Task 2 check working. Regenerate and raise the floors together:

```bash
cd /Volumes/data/pyv/pyvider
uv run python scripts/regen_protobuf.py
# raise grpcio>= / protobuf>= in pyproject.toml to the newly stamped versions
uv run python scripts/regen_protobuf.py --check
uv run pytest -q
```

- [ ] **Step 4: Fix fallout**

`pyvider-cty` 0.5.0's breaking changes surface here if anywhere. Fix them in `pyvider`.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/data/pyv/pyvider
git add -A
git commit -m "build: upgrade dependencies to current releases

Wave 3 of the suite dependency refresh."
```

---

### Task 8: Wave 4 — plating, pyvider-hcl

**Files:**
- Modify: `pyproject.toml` and `uv.lock` in `/Volumes/data/pyv/plating`, `/Volumes/data/pyv/pyvider-hcl`

**Interfaces:**
- Consumes: green `pyvider` from Task 7.
- Produces: green `plating` for wave 5.

- [ ] **Step 1: Upgrade both**

```bash
for r in plating pyvider-hcl; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv lock --upgrade && uv sync --all-groups)
done
```

- [ ] **Step 2: Run each gate**

```bash
for r in plating pyvider-hcl; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src/)
done
```

- [ ] **Step 3: Fix fallout, re-run until green**

- [ ] **Step 4: Commit each separately**

```bash
cd /Volumes/data/pyv/<repo>
git add -A
git commit -m "build: upgrade dependencies to current releases

Wave 4 of the suite dependency refresh."
```

---

### Task 9: Wave 5 — pyvider-components (with jq cap removal), tofusoup

`pyvider-components` is where the refresh pays off: it currently runs grpcio 1.80.0 and protobuf 6.33.6 against pyvider floors of 1.83.0 and 7.35.1, so it cannot import pyvider's regenerated stubs at all. This is the task that unblocks the identity e2e work.

**Files:**
- Modify: `/Volumes/data/pyv/pyvider-components/pyproject.toml` (jq cap), `uv.lock`
- Modify: `/Volumes/data/pyv/tofusoup/pyproject.toml`, `uv.lock`

**Interfaces:**
- Consumes: green `pyvider` and `plating` from Tasks 7 and 8.
- Produces: a `pyvider-components` that can load current pyvider — the prerequisite for the identity e2e plan.

- [ ] **Step 1: Remove the jq cap in pyvider-components**

In `/Volumes/data/pyv/pyvider-components/pyproject.toml`, change:

```toml
    "jq>=1.9.1,<1.11.0; sys_platform != 'win32' or platform_machine != 'ARM64'",
```

to:

```toml
    "jq>=1.9.1; sys_platform != 'win32' or platform_machine != 'ARM64'",
```

- [ ] **Step 2: Upgrade both repositories**

```bash
for r in pyvider-components tofusoup; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv lock --upgrade && uv sync --all-groups)
done
```

- [ ] **Step 3: Confirm the runtime skew is actually gone**

```bash
cd /Volumes/data/pyv/pyvider-components
uv run python -c "import grpc, google.protobuf as p; print('grpcio', grpc.__version__); print('protobuf', p.__version__)"
uv run python -c "from pyvider.protocols.tfprotov6.protobuf import tfplugin6_pb2; print('stubs import OK')"
```

Expected: grpcio >= 1.83.0, protobuf >= 7.35.1, and `stubs import OK`. Before this task, the second command raises at import. This is the concrete unblock.

- [ ] **Step 4: Run each gate**

```bash
for r in pyvider-components tofusoup; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src/)
done
```

- [ ] **Step 5: Fix fallout**

Two failures are already known here: `pyvider-components` fails two tests with `CtyMarksSerializationError` when paired with `pyvider-cty` 0.5.0, because the pyvider it currently resolves has no unmark handling. Once Task 4's source resolution and Task 7's `pyvider` are in place, those should resolve; if they persist, fix them in `pyvider-components`.

If `jq` usage breaks with the cap removed, fix the call sites rather than restoring the cap.

- [ ] **Step 6: Re-run until both are green**

- [ ] **Step 7: Commit each separately**

```bash
cd /Volumes/data/pyv/pyvider-components
git add -A
git commit -m "build: upgrade dependencies and uncap jq

Wave 5 of the suite dependency refresh. The grpcio and protobuf floors move
past 1.83.0 and 7.35.1, which is what lets this package import pyvider's
regenerated protobuf stubs at all -- below those versions they raise at
import. The jq cap carried no recorded rationale and current jq passes."
```

```bash
cd /Volumes/data/pyv/tofusoup
git add -A
git commit -m "build: upgrade dependencies to current releases

Wave 5 of the suite dependency refresh."
```

---

### Task 10: Wave 6 — terraform-provider-pyvider, cap removals, and Windows-ARM CI

Both remaining caps live here. The cryptography cap targets `win32` + `ARM64`, a platform **no CI job currently exercises**: this repo's `ci.yml` does not set `platform-preset`, so it defaults to `standard` (linux + macos only); `build-provider.yml` and `test-conformance.yml` run Windows with `continue-on-error: true`; and `test-conformance.yml:69` excludes windows_arm64 outright with the note "grpcio has no win_arm64 wheel". Dropping the cap and "letting Windows CI decide" therefore requires first giving that decision a mechanism.

**Files:**
- Modify: `/Volumes/data/pyv/terraform-provider-pyvider/pyproject.toml` (both caps)
- Modify: `/Volumes/data/pyv/terraform-provider-pyvider/.github/workflows/ci.yml`
- Modify: `/Volumes/data/pyv/terraform-provider-pyvider/uv.lock`

**Interfaces:**
- Consumes: green `pyvider` and `pyvider-components` from Tasks 7 and 9.
- Produces: a fully uncapped suite.

- [ ] **Step 1: Remove both caps**

In `/Volumes/data/pyv/terraform-provider-pyvider/pyproject.toml`, change:

```toml
    "jq>=1.9.1,<1.11.0; sys_platform != 'win32' or platform_machine != 'ARM64'",
    "cryptography>=46.0.0,<=46.0.3; sys_platform == 'win32' and platform_machine == 'ARM64'",
```

to:

```toml
    "jq>=1.9.1; sys_platform != 'win32' or platform_machine != 'ARM64'",
    # Floor only. The previous <=46.0.3 cap applied to win32/ARM64 and was never
    # exercised by CI, so it could not be justified or refuted. Windows-ARM tests
    # are enabled in ci.yml; if they fail on a newer cryptography, restore the cap
    # here with a comment naming the observed failure.
    "cryptography>=46.0.0; sys_platform == 'win32' and platform_machine == 'ARM64'",
```

- [ ] **Step 2: Give the ruling a mechanism — enable Windows tests in CI**

In `/Volumes/data/pyv/terraform-provider-pyvider/.github/workflows/ci.yml`, add to the `with:` block of the `ci` job:

```yaml
      # Windows-ARM is the only platform the cryptography constraint applies to.
      # Without this the constraint can be neither justified nor refuted, because
      # the standard preset runs linux and macos only.
      include-windows: true
```

`ci-tooling/.github/workflows/python-ci.yml` gates its `test-windows` and `test-windows-arm` jobs on `inputs.platform-preset == 'full' || inputs.include-windows`, so this enables both.

- [ ] **Step 3: Upgrade**

```bash
cd /Volumes/data/pyv/terraform-provider-pyvider
uv lock --upgrade
uv sync --all-groups
```

- [ ] **Step 4: Run the gate**

```bash
cd /Volumes/data/pyv/terraform-provider-pyvider
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy ci/
```

This repository's first-party Python lives in `ci/`, not `src/` — its wrknv `typecheck` task points there.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/data/pyv/terraform-provider-pyvider
git add -A
git commit -m "build: upgrade dependencies, uncap jq and cryptography, test Windows

Wave 6 of the suite dependency refresh, and the last capped pins in the core
suite.

The cryptography cap applied only to win32/ARM64, which no CI job ran: this
workflow used the default standard preset (linux and macos), the build and
conformance workflows mark Windows continue-on-error, and conformance
excludes windows_arm64 entirely. A constraint on a platform nothing exercises
can be neither justified nor refuted, so enabling Windows here is what makes
dropping it a decision rather than a guess. If those jobs fail on a newer
cryptography, the cap comes back with the failure recorded next to it."
```

- [ ] **Step 6: Record the Windows-ARM outcome**

After CI runs, check the `test-windows-arm` job. Note that `grpcio` may have no `win_arm64` wheel, which would fail that job for reasons unrelated to `cryptography` — read the failure before concluding anything. Three outcomes:

- **Job passes:** the cap is correctly gone. Nothing further.
- **Job fails on `cryptography`:** restore the cap in `pyproject.toml` with a comment quoting the failure.
- **Job fails on `grpcio` wheel availability:** the platform is unsupported for reasons larger than this plan. Leave the cryptography cap off, and record that windows_arm64 is unsupported.

---

### Task 11: Version alignment to 0.5.0

Versions are bumped after the waves are green, not before, so a failed wave never leaves the suite claiming a release it cannot make.

**Files:**
- Modify: `VERSION` in all 10 in-scope repositories
- Modify: `pyproject.toml` in all 10 (in-suite floors)

**Interfaces:**
- Consumes: all waves green (Tasks 5–10).
- Produces: a suite consistently at `0.5.0` with `>=0.5.0` in-suite floors.

Current versions: every core package is `0.4.x` except `pyvider-cty`, whose `VERSION` already reads `0.5.0`. `pyvider` reads `0.4.0` despite carrying resource identity and the tfprotov6 6.9 → 6.11 protocol bump.

- [ ] **Step 1: Bump every VERSION file**

```bash
for r in provide-foundation provide-testkit pyvider-cty pyvider-rpcplugin pyvider pyvider-hcl plating pyvider-components tofusoup terraform-provider-pyvider; do
  echo "0.5.0" > "/Volumes/data/pyv/$r/VERSION"
done
```

- [ ] **Step 2: Rewrite in-suite floors to `>=0.5.0`**

In each repository's `pyproject.toml`, every dependency naming an in-suite package becomes `>=0.5.0` — floor only, no upper bound. For example, `pyvider`'s dependencies become:

```toml
    "provide-foundation>=0.5.0",
    "pyvider-cty>=0.5.0",
    "pyvider-rpcplugin>=0.5.0",
```

Apply the same to `provide-testkit`, `pyvider-cty`, `pyvider-rpcplugin`, `pyvider-hcl`, `plating`, `pyvider-components`, `tofusoup`, and `terraform-provider-pyvider`, per the Task 4 dependency table. Third-party floors are untouched.

- [ ] **Step 3: Re-lock and re-test the whole suite in wave order**

```bash
for r in provide-foundation provide-testkit pyvider-cty pyvider-rpcplugin pyvider plating pyvider-hcl pyvider-components tofusoup terraform-provider-pyvider; do
  echo "=== $r ==="
  (cd "/Volumes/data/pyv/$r" && uv lock && uv sync --all-groups && uv run pytest -q 2>&1 | tail -3)
done
```

Expected: every repository locks and passes. A resolution failure means a floor references a version a sibling does not yet claim — check that repository's `VERSION`.

- [ ] **Step 4: Commit each repository**

```bash
cd /Volumes/data/pyv/<repo>
git add -A
git commit -m "chore: release 0.5.0 across the suite

The suite is co-released, so versions move together and in-suite floors read
>=0.5.0. Release order follows the runtime dependency waves, so no package is
published against an unpublished floor. This also fixes pyvider's version,
which still read 0.4.0 while carrying resource identity and the tfprotov6
6.9 to 6.11 protocol bump."
```

---

### Task 12: Final cap audit and verification

**Files:**
- Create: `/Volumes/data/pyv/pyvider/scripts/audit_pins.py`

**Interfaces:**
- Consumes: everything.
- Produces: a repeatable audit proving the floor-only constraint holds.

- [ ] **Step 1: Write the audit script**

Create `/Volumes/data/pyv/pyvider/scripts/audit_pins.py`:

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Report capped or exact dependency pins across the core pyvider suite.

The suite's policy is floor-only constraints: a cap turns a loud, fixable
failure into a silent refusal to upgrade, and outlives whatever it went up for.
Run this to confirm the policy still holds.
"""

from pathlib import Path
import sys
import tomllib

SUITE_ROOT = Path("/Volumes/data/pyv")
CORE = (
    "provide-foundation", "provide-testkit", "pyvider-cty", "pyvider-rpcplugin",
    "pyvider-hcl", "pyvider", "plating", "pyvider-components", "tofusoup",
    "terraform-provider-pyvider",
)
CAPPED = ("<", "==", "~=")


def requirements(repo: str) -> list[tuple[str, str]]:
    """Yield (section, requirement) for every dependency the repo declares."""
    data = tomllib.loads((SUITE_ROOT / repo / "pyproject.toml").read_text())
    project = data.get("project", {})
    found = [("dependencies", r) for r in project.get("dependencies", [])]
    for extra, reqs in project.get("optional-dependencies", {}).items():
        found += [(f"optional:{extra}", r) for r in reqs]
    for group, reqs in data.get("dependency-groups", {}).items():
        found += [(f"group:{group}", r) for r in reqs if isinstance(r, str)]
    return found


def main() -> int:
    offenders = []
    for repo in CORE:
        for section, requirement in requirements(repo):
            # Environment markers after ';' may legitimately contain '<'.
            if any(token in requirement.split(";")[0] for token in CAPPED):
                offenders.append(f"{repo} [{section}] {requirement}")

    if offenders:
        print("Capped or exact pins found:")
        for offender in offenders:
            print(f"  {offender}")
        return 1

    print(f"No capped pins across {len(CORE)} core repositories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the audit**

Run: `cd /Volumes/data/pyv/pyvider && uv run python scripts/audit_pins.py`
Expected: `No capped pins across 10 core repositories.`

If the cryptography cap was restored in Task 10 Step 6 after an observed Windows failure, that one line is the expected and documented exception — record it in the commit message rather than deleting the audit.

- [ ] **Step 3: Verify third-party floors resolve without source overrides**

The spec calls for a `--no-sources` re-resolution. Note that this **cannot fully pass before publication**: in-suite floors read `>=0.5.0`, and 0.5.0 does not exist on PyPI until released. Verify what is verifiable now:

```bash
cd /Volumes/data/pyv/provide-foundation
uv lock --no-sources
```

`provide-foundation` has no in-suite runtime dependencies, so it is the one repository whose `--no-sources` resolution is meaningful pre-release. For the other nine, the full `--no-sources` gate belongs to release time, after each wave is published. Record this in the handoff rather than treating it as done.

- [ ] **Step 4: Confirm every repository is green one final time**

```bash
for r in provide-foundation provide-testkit pyvider-cty pyvider-rpcplugin pyvider plating pyvider-hcl pyvider-components tofusoup terraform-provider-pyvider; do
  printf "%-30s " "$r"
  (cd "/Volumes/data/pyv/$r" && uv run pytest -q 2>&1 | tail -1)
done
```

- [ ] **Step 5: Commit**

```bash
cd /Volumes/data/pyv/pyvider
git add scripts/audit_pins.py
git commit -m "chore(scripts): add a floor-only pin audit for the core suite

The refresh removed every cap; this makes the policy checkable instead of
remembered. A cap turns a loud, fixable failure into a silent refusal to
upgrade, so the useful question is not whether one is justified today but
whether anyone will notice when it stops being."
```

---

## Post-plan handoff

Two items belong to release time rather than this plan:

1. **The full `--no-sources` gate.** It can only pass once each wave is published, because in-suite floors read `>=0.5.0`. Run it wave by wave during release.
2. **Publication order.** Publish in wave order — `provide-foundation`, then wave 2, and so on — so no package is published against an unpublished floor. This is what satisfies the requirement that `pyvider` release at or before `pyvider-cty`.

The identity e2e plan (`docs/superpowers/specs/2026-08-16-resource-identity-e2e-design.md`) becomes unblocked at Task 9, when `pyvider-components` can import current pyvider's protobuf stubs.
