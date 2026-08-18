#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Worker entry points executed in separate processes by the concurrency tests.

These live outside the test module because ``spawn``-started children re-import
the module that defines the callable, and re-importing a pytest test module in a
child is fragile. A plain module has no such problem.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import time

from pyvider.state_stores import FileSystemStateStore, StateLockConflictError
from pyvider.state_stores._filelock import exclusive_file_mutex

TYPE_NAME = "concurrent_store"
STATE_ID = "shared"


def _wait_for_start(start_flag: str) -> None:
    """Block until the parent releases every worker at once.

    Without this the children serialize simply by starting at different times,
    and the test would pass whether or not the lock actually works.
    """
    flag = Path(start_flag)
    deadline = time.monotonic() + 30.0
    while not flag.exists():
        if time.monotonic() >= deadline:  # pragma: no cover - watchdog
            raise TimeoutError("Workers were never released by the parent process.")
        time.sleep(0.002)


def acquire_once(root: str, start_flag: str) -> str | None:
    """Try once to lock the shared state; return the lock id or None."""
    _wait_for_start(start_flag)
    store = FileSystemStateStore(root=Path(root))
    try:
        lock = asyncio.run(store.lock_state(TYPE_NAME, STATE_ID, "apply", ttl_seconds=120))
    except StateLockConflictError:
        return None
    return lock.lock_id


def locked_increment(root: str, start_flag: str, iterations: int) -> int:
    """Read-modify-write a shared counter under the lock, ``iterations`` times.

    Any gap in the locking primitive shows up as a final counter lower than the
    total number of increments performed across all processes.
    """
    _wait_for_start(start_flag)
    store = FileSystemStateStore(root=Path(root))

    async def run() -> int:
        applied = 0
        for _ in range(iterations):
            lock = None
            deadline = time.monotonic() + 30.0
            while lock is None:
                try:
                    lock = await store.lock_state(TYPE_NAME, STATE_ID, "apply", ttl_seconds=30)
                except StateLockConflictError:
                    if time.monotonic() >= deadline:  # pragma: no cover - watchdog
                        raise
                    await asyncio.sleep(0.002)

            raw = await store.read_state(TYPE_NAME, STATE_ID)
            value = int(raw.decode("utf-8")) if raw else 0
            await store.write_state(TYPE_NAME, STATE_ID, str(value + 1).encode("utf-8"))
            applied += 1
            await store.unlock_state(TYPE_NAME, STATE_ID, lock.lock_id)
        return applied

    return asyncio.run(run())


def write_own_state(root: str, start_flag: str, index: int) -> str:
    """Write a state named after this worker, proving writes do not collide."""
    _wait_for_start(start_flag)
    store = FileSystemStateStore(root=Path(root))
    state_id = f"worker-{index}"
    asyncio.run(store.write_state(TYPE_NAME, state_id, f"payload-{index}".encode()))
    return state_id


def hold_mutex(lock_path: str, ready_flag: str, release_flag: str) -> str:
    """Hold the cross-process file mutex until told to let go.

    POSIX record locks are owned by the *process*, so a second thread in the
    same process would acquire the mutex rather than block on it. Only a
    separate process can prove contention.
    """
    ready = Path(ready_flag)
    release = Path(release_flag)
    with exclusive_file_mutex(Path(lock_path)):
        ready.write_text("held", encoding="utf-8")
        deadline = time.monotonic() + 30.0
        while not release.exists():
            if time.monotonic() >= deadline:  # pragma: no cover - watchdog
                break
            time.sleep(0.002)
    return "released"


def read_state(root: str, state_id: str) -> bytes | None:
    """Read a state written by a different process."""
    store = FileSystemStateStore(root=Path(root))
    return asyncio.run(store.read_state(TYPE_NAME, state_id))


# 🐍🏗️🔚
