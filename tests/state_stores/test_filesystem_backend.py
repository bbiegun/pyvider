#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Behavior specific to the durable filesystem backend."""

from __future__ import annotations

import json
from pathlib import Path
import stat
import sys

import pytest

from pyvider.state_stores import FileSystemStateStore, StateStoreError, default_state_root
from pyvider.state_stores.defaults import (
    ENV_PATH,
    LOCK_FILE_SUFFIX,
    STATE_FILE_SUFFIX,
    TEMP_FILE_SUFFIX,
)

TYPE_NAME = "fs_store"


@pytest.fixture
def store(tmp_path: Path) -> FileSystemStateStore:
    return FileSystemStateStore(root=tmp_path / "state")


@pytest.mark.asyncio
async def test_state_survives_a_new_backend_instance(tmp_path: Path) -> None:
    root = tmp_path / "state"
    await FileSystemStateStore(root=root).write_state(TYPE_NAME, "main", b"durable")

    # A fresh instance stands in for a restarted provider process.
    assert await FileSystemStateStore(root=root).read_state(TYPE_NAME, "main") == b"durable"


@pytest.mark.asyncio
@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "chmod only toggles the read-only bit on Windows; it cannot restrict other "
        "users, so the owner-only guarantee does not hold there. See the Windows "
        "caveats in the state-store docs."
    ),
)
async def test_payload_is_written_to_an_owner_only_file(store: FileSystemStateStore) -> None:
    await store.write_state(TYPE_NAME, "main", b"secret")

    files = list((store.root / TYPE_NAME).glob(f"*{STATE_FILE_SUFFIX}"))
    assert len(files) == 1
    mode = stat.S_IMODE(files[0].stat().st_mode)
    assert mode & (stat.S_IRWXG | stat.S_IRWXO) == 0


@pytest.mark.asyncio
async def test_write_leaves_no_temporary_files_behind(store: FileSystemStateStore) -> None:
    await store.write_state(TYPE_NAME, "main", b"one")
    await store.write_state(TYPE_NAME, "main", b"two")

    assert list((store.root / TYPE_NAME).glob(f"*{TEMP_FILE_SUFFIX}")) == []


@pytest.mark.asyncio
async def test_path_traversal_in_names_stays_inside_the_root(store: FileSystemStateStore) -> None:
    await store.write_state("../escape", "../../etc/passwd", b"contained")

    escaped = list(store.root.parent.glob("escape*"))
    assert escaped == []
    assert await store.read_state("../escape", "../../etc/passwd") == b"contained"
    assert await store.list_states("../escape") == ["../../etc/passwd"]


@pytest.mark.asyncio
async def test_names_with_separators_round_trip_through_listing(store: FileSystemStateStore) -> None:
    await store.write_state(TYPE_NAME, "env/prod/main", b"payload")

    assert await store.list_states(TYPE_NAME) == ["env/prod/main"]
    assert await store.read_state(TYPE_NAME, "env/prod/main") == b"payload"


@pytest.mark.asyncio
async def test_unreadable_lease_is_reclaimed_rather_than_wedging_the_state(
    store: FileSystemStateStore,
) -> None:
    lock_path = store.root / TYPE_NAME / f"main{LOCK_FILE_SUFFIX}"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(b"this is not json")

    lock = await store.lock_state(TYPE_NAME, "main", "apply", ttl_seconds=60)

    assert lock.lock_id
    assert json.loads(lock_path.read_text(encoding="utf-8"))["lock_id"] == lock.lock_id


@pytest.mark.asyncio
async def test_released_lease_leaves_an_empty_record(store: FileSystemStateStore) -> None:
    lock = await store.lock_state(TYPE_NAME, "main", "apply", ttl_seconds=60)
    await store.unlock_state(TYPE_NAME, "main", lock.lock_id)

    lock_path = store.root / TYPE_NAME / f"main{LOCK_FILE_SUFFIX}"
    assert lock_path.read_bytes() == b""
    assert await store.get_lock(TYPE_NAME, "main") is None


@pytest.mark.asyncio
async def test_get_lock_without_any_lock_file_is_none(store: FileSystemStateStore) -> None:
    assert await store.get_lock(TYPE_NAME, "never-locked") is None


@pytest.mark.asyncio
async def test_read_failure_surfaces_as_state_store_error(store: FileSystemStateStore) -> None:
    # A directory where the state file is expected makes the read fail with
    # something other than "missing", which must not be reported as absent.
    path = store.root / TYPE_NAME / f"main{STATE_FILE_SUFFIX}"
    path.mkdir(parents=True)

    with pytest.raises(StateStoreError):
        await store.read_state(TYPE_NAME, "main")


@pytest.mark.asyncio
async def test_configure_relocates_the_root(tmp_path: Path) -> None:
    store = FileSystemStateStore(root=tmp_path / "original")
    relocated = tmp_path / "relocated"

    await store.configure({"path": str(relocated)}, chunk_size=1024)
    await store.write_state(TYPE_NAME, "main", b"payload")

    assert store.root == relocated
    assert (relocated / TYPE_NAME / f"main{STATE_FILE_SUFFIX}").is_file()


@pytest.mark.asyncio
async def test_validate_rejects_a_root_that_is_a_file(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    store = FileSystemStateStore(root=tmp_path / "state")

    errors = await store.validate({"path": str(blocker)})

    assert len(errors) == 1
    assert "not a directory" in errors[0]


@pytest.mark.asyncio
async def test_validate_accepts_a_config_without_a_path(store: FileSystemStateStore) -> None:
    assert await store.validate(None) == []
    assert await store.validate({}) == []
    assert await store.validate({"path": "  "}) == []


def test_default_root_follows_the_path_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_PATH, str(tmp_path / "from-env"))

    assert default_state_root() == tmp_path / "from-env"


def test_default_root_falls_back_to_a_working_directory_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_PATH, raising=False)

    root = default_state_root()

    assert root.is_relative_to(Path.cwd())


def test_backend_declares_itself_durable() -> None:
    assert FileSystemStateStore.durable is True


# 🐍🏗️🔚
