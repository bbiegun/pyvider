#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Pluggable state-store backends for Terraform's remote-state RPCs.

``BaseStateStore`` is the contract; ``FileSystemStateStore`` is the durable
default for production, and ``InMemoryStateStore`` is the explicitly non-durable
backend kept for tests and single-process local development.
"""

from pyvider.state_stores.base import BaseStateStore
from pyvider.state_stores.decorators import register_state_store
from pyvider.state_stores.defaults import (
    BACKEND_FILESYSTEM,
    BACKEND_MEMORY,
    DEFAULT_LOCK_TTL_SECONDS,
    DEFAULT_STATE_STORE_CHUNK_SIZE,
)
from pyvider.state_stores.filesystem import FileSystemStateStore, default_state_root
from pyvider.state_stores.manager import (
    StateStoreManager,
    default_backend_name,
    default_lock_ttl_seconds,
    normalize_chunk_size,
    state_store_manager,
)
from pyvider.state_stores.memory import InMemoryStateStore
from pyvider.state_stores.types import (
    StateLock,
    StateLockConflictError,
    StateStoreConfigurationError,
    StateStoreError,
)

__all__ = [
    "BACKEND_FILESYSTEM",
    "BACKEND_MEMORY",
    "DEFAULT_LOCK_TTL_SECONDS",
    "DEFAULT_STATE_STORE_CHUNK_SIZE",
    "BaseStateStore",
    "FileSystemStateStore",
    "InMemoryStateStore",
    "StateLock",
    "StateLockConflictError",
    "StateStoreConfigurationError",
    "StateStoreError",
    "StateStoreManager",
    "default_backend_name",
    "default_lock_ttl_seconds",
    "default_state_root",
    "normalize_chunk_size",
    "register_state_store",
    "state_store_manager",
]

# 🐍🏗️🔚
