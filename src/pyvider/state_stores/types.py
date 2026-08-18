#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Value types and errors shared by every state-store backend."""

from __future__ import annotations

import os
import socket
import time
from typing import Any

from attrs import define, field

from pyvider.exceptions import PyviderError


def _current_holder() -> str:
    """Identify the process holding a lease.

    The holder string is diagnostic only -- correctness comes from the lock id --
    but it is what turns "state is locked" into an actionable message when a
    stale lease has to be broken by hand.
    """
    try:
        host = socket.gethostname()
    except OSError:  # pragma: no cover - hostname lookup effectively never fails
        host = "unknown-host"
    return f"{host}/{os.getpid()}"


@define(frozen=True, slots=True)
class StateLock:
    """A lease-bearing lock over a single state object.

    ``expires_at`` is an absolute wall-clock timestamp rather than a duration
    because the lease has to be comparable across processes that never share
    memory; a monotonic clock is per-process and would make a lease written by
    one provider meaningless to another.
    """

    lock_id: str
    type_name: str
    state_id: str
    operation: str = ""
    holder: str = field(factory=_current_holder)
    acquired_at: float = field(factory=time.time)
    expires_at: float = 0.0

    def is_expired(self, now: float | None = None) -> bool:
        """Report whether the lease has lapsed.

        A non-positive ``expires_at`` means "no expiry", which is how a caller
        asks for a lock that is only released explicitly.
        """
        if self.expires_at <= 0:
            return False
        return (time.time() if now is None else now) >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON-compatible form written to durable storage."""
        return {
            "lock_id": self.lock_id,
            "type_name": self.type_name,
            "state_id": self.state_id,
            "operation": self.operation,
            "holder": self.holder,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StateLock:
        """Rebuild a lease from its stored representation."""
        return cls(
            lock_id=str(payload["lock_id"]),
            type_name=str(payload.get("type_name", "")),
            state_id=str(payload.get("state_id", "")),
            operation=str(payload.get("operation", "")),
            holder=str(payload.get("holder", "")),
            acquired_at=float(payload.get("acquired_at", 0.0)),
            expires_at=float(payload.get("expires_at", 0.0)),
        )


class StateStoreError(PyviderError):
    """Base class for state-store backend failures."""

    def _default_code(self) -> str:
        return "STATE_STORE_ERROR"


class StateLockConflictError(StateStoreError):
    """Raised when a state is already locked by a live lease."""

    def __init__(self, existing: StateLock) -> None:
        self.existing = existing
        super().__init__(
            f"State '{existing.type_name}/{existing.state_id}' is locked by {existing.holder} "
            f"for operation '{existing.operation}' (lock id {existing.lock_id}).",
            context={
                "state_store.type_name": existing.type_name,
                "state_store.state_id": existing.state_id,
                "state_store.lock_id": existing.lock_id,
                "state_store.holder": existing.holder,
            },
        )

    def _default_code(self) -> str:
        return "STATE_LOCK_CONFLICT"


class StateStoreConfigurationError(StateStoreError):
    """Raised when a backend cannot be resolved or configured."""

    def _default_code(self) -> str:
        return "STATE_STORE_CONFIG_ERROR"


# 🐍🏗️🔚
