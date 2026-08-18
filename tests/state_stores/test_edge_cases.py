#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Failure and boundary paths of the state-store subsystem.

These are the branches the happy-path suites never reach: storage errors,
corrupt lease records, non-expiring leases, and contention on the cross-process
mutex itself.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path
import time

import pytest

from pyvider.state_stores import FileSystemStateStore, StateLock, StateStoreError
from pyvider.state_stores._filelock import FileMutexTimeoutError, exclusive_file_mutex
from pyvider.state_stores.defaults import LOCK_FILE_SUFFIX
from tests.state_stores import _lock_workers as workers

TYPE_NAME = "edge_store"


@pytest.fixture
def store(tmp_path: Path) -> FileSystemStateStore:
    return FileSystemStateStore(root=tmp_path / "state")


# --- StateLock -------------------------------------------------------------


def test_a_lease_without_an_expiry_never_expires() -> None:
    lock = StateLock(lock_id="x", type_name=TYPE_NAME, state_id="main", expires_at=0.0)

    assert lock.is_expired() is False
    # Even far in the future: no expiry means released explicitly or not at all.
    assert lock.is_expired(now=time.time() + 10_000) is False


def test_a_lease_expires_at_its_stated_time() -> None:
    now = time.time()
    lock = StateLock(lock_id="x", type_name=TYPE_NAME, state_id="main", expires_at=now + 5)

    assert lock.is_expired(now=now) is False
    assert lock.is_expired(now=now + 6) is True


def test_a_lease_round_trips_through_its_serialized_form() -> None:
    original = StateLock(
        lock_id="abc",
        type_name=TYPE_NAME,
        state_id="main",
        operation="apply",
        holder="host/1",
        acquired_at=1.0,
        expires_at=2.0,
    )

    assert StateLock.from_dict(original.to_dict()) == original


# --- lease records that cannot be trusted ----------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"[]", id="not-an-object"),
        pytest.param(b'{"no_lock_id": true}', id="object-without-lock-id"),
        pytest.param(b'"a string"', id="json-scalar"),
    ],
)
@pytest.mark.asyncio
async def test_a_structurally_wrong_lease_is_treated_as_unlocked(
    store: FileSystemStateStore, payload: bytes
) -> None:
    lock_path = store.root / TYPE_NAME / f"main{LOCK_FILE_SUFFIX}"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(payload)

    lock = await store.lock_state(TYPE_NAME, "main", "apply", ttl_seconds=60)

    assert lock.lock_id
    assert json.loads(lock_path.read_text(encoding="utf-8"))["lock_id"] == lock.lock_id


# --- storage failures ------------------------------------------------------


@pytest.mark.asyncio
async def test_a_write_failure_surfaces_as_a_state_store_error(
    store: FileSystemStateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(self: Path, target: Path) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(Path, "replace", explode)

    with pytest.raises(StateStoreError, match="Failed to write state"):
        await store.write_state(TYPE_NAME, "main", b"payload")


@pytest.mark.asyncio
async def test_a_failed_write_leaves_no_temporary_file_behind(
    store: FileSystemStateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(self: Path, target: Path) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(Path, "replace", explode)

    with pytest.raises(StateStoreError):
        await store.write_state(TYPE_NAME, "main", b"payload")

    # A half-finished write must not leave debris that a later listing or a
    # human would have to reason about.
    assert list((store.root / TYPE_NAME).glob("*.tmp")) == []


@pytest.mark.asyncio
async def test_a_delete_failure_surfaces_as_a_state_store_error(
    store: FileSystemStateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    await store.write_state(TYPE_NAME, "main", b"payload")

    def explode(self: Path, missing_ok: bool = False) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "unlink", explode)

    with pytest.raises(StateStoreError, match="Failed to delete state"):
        await store.delete_state(TYPE_NAME, "main")


# --- configuration validation ---------------------------------------------


@pytest.mark.asyncio
async def test_validate_accepts_a_root_that_is_an_existing_directory(
    store: FileSystemStateStore, tmp_path: Path
) -> None:
    existing = tmp_path / "already-here"
    existing.mkdir()

    assert await store.validate({"path": str(existing)}) == []


@pytest.mark.asyncio
async def test_validate_accepts_a_root_that_does_not_exist_yet(
    store: FileSystemStateStore, tmp_path: Path
) -> None:
    assert await store.validate({"path": str(tmp_path / "not-created-yet")}) == []


# --- the cross-process mutex itself ---------------------------------------


def test_the_mutex_times_out_when_another_process_holds_it(tmp_path: Path) -> None:
    """Contention on the mutex must fail loudly rather than hang forever."""
    lock_path = tmp_path / "contended.tflock"
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    context = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(max_workers=1, mp_context=context) as pool:
        future = pool.submit(workers.hold_mutex, str(lock_path), str(ready), str(release))

        deadline = time.monotonic() + 30.0
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert ready.exists(), "the holder process never acquired the mutex"

        try:
            with pytest.raises(FileMutexTimeoutError, match="Timed out"):
                with exclusive_file_mutex(lock_path, timeout=0.05):
                    pass  # pragma: no cover - the block must not be entered
        finally:
            release.write_text("go", encoding="utf-8")

        assert future.result(timeout=60) == "released"

    # Once the holder is gone the mutex is free again, which proves the timeout
    # did not leave the lock wedged.
    with exclusive_file_mutex(lock_path, timeout=5):
        pass


def test_a_mutex_error_that_is_not_contention_is_re_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only EACCES/EAGAIN mean "someone else holds it".

    Any other OSError is a real fault -- a bad descriptor, a filesystem that
    does not implement locking -- and retrying until the deadline would turn a
    clear failure into a slow, confusing one.
    """
    import errno as errno_module
    import fcntl

    def explode(fd: int, operation: int) -> None:
        raise OSError(errno_module.EBADF, "bad file descriptor")

    monkeypatch.setattr(fcntl, "lockf", explode)

    with pytest.raises(OSError, match="bad file descriptor"):
        with exclusive_file_mutex(tmp_path / "broken.tflock", timeout=5):
            pass  # pragma: no cover - the block must not be entered


# 🐍🏗️🔚
