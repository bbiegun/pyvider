#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Cross-process guarantees for the durable state store.

These tests run real OS processes rather than threads or tasks. The in-memory
backend passes a threaded test trivially, so only separate processes can show
that the durable backend actually coordinates.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path

import pytest

from pyvider.state_stores import FileSystemStateStore
from tests.state_stores import _lock_workers as workers

pytestmark = pytest.mark.integration

WORKER_COUNT = 6
INCREMENTS_PER_WORKER = 5


@pytest.fixture
def spawn_pool() -> multiprocessing.context.SpawnContext:
    # "spawn" rather than "fork": a forked child inherits the parent's asyncio
    # loop and logging handlers, which produces failures unrelated to locking.
    return multiprocessing.get_context("spawn")


def _release(start_flag: Path) -> None:
    start_flag.write_text("go", encoding="utf-8")


def test_only_one_process_wins_a_contended_lock(tmp_path: Path, spawn_pool) -> None:
    root = tmp_path / "state"
    start_flag = tmp_path / "start"

    with ProcessPoolExecutor(max_workers=WORKER_COUNT, mp_context=spawn_pool) as pool:
        futures = [pool.submit(workers.acquire_once, str(root), str(start_flag)) for _ in range(WORKER_COUNT)]
        _release(start_flag)
        results = [future.result(timeout=120) for future in futures]

    winners = [lock_id for lock_id in results if lock_id is not None]
    assert len(winners) == 1, f"expected exactly one lock holder, got {winners}"


def test_locked_read_modify_write_loses_no_updates(tmp_path: Path, spawn_pool) -> None:
    root = tmp_path / "state"
    start_flag = tmp_path / "start"

    with ProcessPoolExecutor(max_workers=WORKER_COUNT, mp_context=spawn_pool) as pool:
        futures = [
            pool.submit(workers.locked_increment, str(root), str(start_flag), INCREMENTS_PER_WORKER)
            for _ in range(WORKER_COUNT)
        ]
        _release(start_flag)
        applied = [future.result(timeout=180) for future in futures]

    assert sum(applied) == WORKER_COUNT * INCREMENTS_PER_WORKER

    store = FileSystemStateStore(root=root)
    raw = asyncio.run(store.read_state(workers.TYPE_NAME, workers.STATE_ID))
    assert raw is not None
    assert int(raw.decode("utf-8")) == WORKER_COUNT * INCREMENTS_PER_WORKER


def test_concurrent_writes_to_distinct_states_all_survive(tmp_path: Path, spawn_pool) -> None:
    root = tmp_path / "state"
    start_flag = tmp_path / "start"

    with ProcessPoolExecutor(max_workers=WORKER_COUNT, mp_context=spawn_pool) as pool:
        futures = [
            pool.submit(workers.write_own_state, str(root), str(start_flag), index)
            for index in range(WORKER_COUNT)
        ]
        _release(start_flag)
        written = [future.result(timeout=120) for future in futures]

    store = FileSystemStateStore(root=root)
    listed = asyncio.run(store.list_states(workers.TYPE_NAME))
    assert sorted(listed) == sorted(written)
    for index in range(WORKER_COUNT):
        payload = asyncio.run(store.read_state(workers.TYPE_NAME, f"worker-{index}"))
        assert payload == f"payload-{index}".encode()


def test_state_written_in_one_process_is_visible_in_another(tmp_path: Path, spawn_pool) -> None:
    root = tmp_path / "state"
    store = FileSystemStateStore(root=root)
    asyncio.run(store.write_state(workers.TYPE_NAME, "durable", b"survives-restart"))

    with ProcessPoolExecutor(max_workers=1, mp_context=spawn_pool) as pool:
        payload = pool.submit(workers.read_state, str(root), "durable").result(timeout=120)

    assert payload == b"survives-restart"


# 🐍🏗️🔚
