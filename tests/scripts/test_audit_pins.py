#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Unit tests for the dependency-pin audit script.

These tests build synthetic ``pyproject.toml`` files under ``tmp_path`` rather
than reading the real sibling repos -- the real checkouts are optional (a
partial suite checkout is a supported case, see
``test_audit_skips_missing_sibling_repo``) and reading them would make this
test's outcome depend on whatever happens to be pinned in a developer's
machine at the moment the suite runs.
"""

from pathlib import Path

from scripts.audit_pins import audit, resolve_suite_root


def _write_pyproject(repo_root: Path, dependencies: list[str]) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    deps = ", ".join(f'"{d}"' for d in dependencies)
    (repo_root / "pyproject.toml").write_text(
        f"""[project]
name = "{repo_root.name}"
version = "0.0.0"
dependencies = [{deps}]
"""
    )


def test_audit_detects_a_capped_pin(tmp_path: Path) -> None:
    _write_pyproject(tmp_path / "repo-a", ["attrs>=23.0", "click<9.0"])

    offenders, skipped = audit(tmp_path, repos=("repo-a",))

    assert skipped == []
    assert len(offenders) == 1
    assert "repo-a" in offenders[0]
    assert "click<9.0" in offenders[0]


def test_audit_passes_a_floor_only_set(tmp_path: Path) -> None:
    _write_pyproject(tmp_path / "repo-a", ["attrs>=23.0", "click>=8.0"])

    offenders, skipped = audit(tmp_path, repos=("repo-a",))

    assert offenders == []
    assert skipped == []


def test_audit_skips_missing_sibling_repo(tmp_path: Path) -> None:
    # repo-a exists with a clean, floor-only dependency; repo-b is not
    # checked out at all -- a partial suite checkout must not raise.
    _write_pyproject(tmp_path / "repo-a", ["attrs>=23.0"])

    offenders, skipped = audit(tmp_path, repos=("repo-a", "repo-b"))

    assert offenders == []
    assert skipped == ["repo-b"]


def test_audit_flags_exact_and_compatible_pins_too(tmp_path: Path) -> None:
    _write_pyproject(tmp_path / "repo-a", ["attrs==23.0", "click~=8.0"])

    offenders, skipped = audit(tmp_path, repos=("repo-a",))

    assert skipped == []
    assert len(offenders) == 2


def test_audit_ignores_caps_inside_environment_markers(tmp_path: Path) -> None:
    # A '<' after ';' is a Python-version marker, not a version cap.
    _write_pyproject(tmp_path / "repo-a", ["attrs>=23.0; python_version < '3.12'"])

    offenders, skipped = audit(tmp_path, repos=("repo-a",))

    assert offenders == []
    assert skipped == []


def test_audit_reports_optional_and_group_dependencies(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-a"
    repo_root.mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text(
        """[project]
name = "repo-a"
version = "0.0.0"
dependencies = ["attrs>=23.0"]

[project.optional-dependencies]
extra = ["click<9.0"]

[dependency-groups]
dev = ["pytest==8.0"]
"""
    )

    offenders, skipped = audit(repo_root.parent, repos=("repo-a",))

    assert skipped == []
    sections = {o.split(" ", 2)[1] for o in offenders}
    assert sections == {"[optional:extra]", "[group:dev]"}


def test_resolve_suite_root_prefers_explicit_cli_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PYVIDER_SUITE_ROOT", str(tmp_path / "from-env"))

    resolved = resolve_suite_root(tmp_path / "from-cli")

    assert resolved == (tmp_path / "from-cli").resolve()


def test_resolve_suite_root_falls_back_to_env_var(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PYVIDER_SUITE_ROOT", str(tmp_path / "from-env"))

    resolved = resolve_suite_root(None)

    assert resolved == (tmp_path / "from-env").resolve()


def test_resolve_suite_root_defaults_to_parent_of_this_repo(monkeypatch) -> None:
    monkeypatch.delenv("PYVIDER_SUITE_ROOT", raising=False)

    from scripts.audit_pins import DEFAULT_SUITE_ROOT

    resolved = resolve_suite_root(None)

    assert resolved == DEFAULT_SUITE_ROOT
