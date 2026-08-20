#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tunable defaults for pluggable state-store backends.

Every configurable value used by the state-store subsystem lives here so that
backends, the manager, and the protocol handlers share one source of truth
instead of scattering literals across call sites.
"""

from __future__ import annotations

from typing import Final

# Wire chunking. Terraform negotiates a chunk size during ConfigureStateStore;
# this value is used when the client does not supply one.
DEFAULT_STATE_STORE_CHUNK_SIZE: Final[int] = 32_768

# Lease duration for a state lock, in seconds. A lock whose lease has expired is
# reclaimable by any other process, which is what keeps a crashed provider from
# wedging the state forever.
DEFAULT_LOCK_TTL_SECONDS: Final[float] = 300.0

# Backend identifiers understood by the manager.
BACKEND_MEMORY: Final[str] = "memory"
BACKEND_FILESYSTEM: Final[str] = "filesystem"
DEFAULT_BACKEND: Final[str] = BACKEND_MEMORY

# Environment overrides.
ENV_BACKEND: Final[str] = "PYVIDER_STATE_STORE_BACKEND"
ENV_PATH: Final[str] = "PYVIDER_STATE_STORE_PATH"
ENV_LOCK_TTL: Final[str] = "PYVIDER_STATE_STORE_LOCK_TTL"

# Filesystem backend layout, relative to the working directory when
# ``PYVIDER_STATE_STORE_PATH`` is unset.
DEFAULT_STATE_ROOT_DIRNAME: Final[str] = ".pyvider"
DEFAULT_STATE_SUBDIRNAME: Final[str] = "state"

STATE_FILE_SUFFIX: Final[str] = ".tfstate"
LOCK_FILE_SUFFIX: Final[str] = ".tflock"
TEMP_FILE_SUFFIX: Final[str] = ".tmp"

# Directory and file permissions. State payloads routinely contain credentials,
# so they are owner-only.
STATE_DIR_MODE: Final[int] = 0o700
STATE_FILE_MODE: Final[int] = 0o600

# 🐍🏗️🔚
