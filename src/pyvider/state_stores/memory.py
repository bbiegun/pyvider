#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Process-local state-store backend.

This is the explicitly-named non-durable backend referenced by the state-store
contract. It exists for unit tests and single-process local development, where
paying for real storage buys nothing. It is *not* suitable for production: the
data lives in this process's heap, so a restart drops every state and a second
provider process sees an entirely separate store.
"""

from __future__ import annotations

import threading
import time
from typing import Any
import uuid

from pyvider.state_stores.base import BaseStateStore
from pyvider.state_stores.defaults import DEFAULT_LOCK_TTL_SECONDS
from pyvider.state_stores.types import StateLock, StateLockConflictError


class InMemoryStateStore(BaseStateStore):
    """Non-durable backend backed by in-process dictionaries."""

    durable = False

    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self._data: dict[tuple[str, str], bytes] = {}
        self._locks: dict[tuple[str, str], StateLock] = {}

    @staticmethod
    def _key(type_name: str, state_id: str) -> tuple[str, str]:
        return (type_name, state_id)

    async def configure(self, config: Any, chunk_size: int) -> None:
        return None

    async def read_state(self, type_name: str, state_id: str) -> bytes | None:
        with self._mutex:
            return self._data.get(self._key(type_name, state_id))

    async def write_state(self, type_name: str, state_id: str, payload: bytes) -> None:
        with self._mutex:
            self._data[self._key(type_name, state_id)] = bytes(payload)

    async def delete_state(self, type_name: str, state_id: str) -> None:
        with self._mutex:
            self._data.pop(self._key(type_name, state_id), None)

    async def list_states(self, type_name: str) -> list[str]:
        with self._mutex:
            return [state_id for store_type, state_id in self._data if store_type == type_name]

    async def lock_state(
        self,
        type_name: str,
        state_id: str,
        operation: str = "",
        ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS,
    ) -> StateLock:
        now = time.time()
        with self._mutex:
            key = self._key(type_name, state_id)
            existing = self._locks.get(key)
            if existing is not None and not existing.is_expired(now):
                raise StateLockConflictError(existing)

            lock = StateLock(
                lock_id=str(uuid.uuid4()),
                type_name=type_name,
                state_id=state_id,
                operation=operation,
                acquired_at=now,
                expires_at=now + ttl_seconds if ttl_seconds > 0 else 0.0,
            )
            self._locks[key] = lock
            return lock

    async def unlock_state(self, type_name: str, state_id: str, lock_id: str) -> bool:
        with self._mutex:
            key = self._key(type_name, state_id)
            existing = self._locks.get(key)
            if existing is None or existing.lock_id != lock_id:
                return False
            del self._locks[key]
            return True

    async def get_lock(self, type_name: str, state_id: str) -> StateLock | None:
        now = time.time()
        with self._mutex:
            existing = self._locks.get(self._key(type_name, state_id))
            if existing is None or existing.is_expired(now):
                return None
            return existing

    def clear(self) -> None:
        """Drop all state and locks. Used to isolate tests."""
        with self._mutex:
            self._data.clear()
            self._locks.clear()


# 🐍🏗️🔚
