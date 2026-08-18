#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from __future__ import annotations

import threading
from typing import Any
import uuid

from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
import pyvider.protocols.tfprotov6.protobuf as pb

_STATE_STORE_LOCK = threading.Lock()
_STATE_STORE_DATA: dict[tuple[str, str], bytes] = {}
_STATE_LOCKS: dict[tuple[str, str], str] = {}
_STATE_STORE_CHUNK_SIZES: dict[str, int] = {}
_DEFAULT_STATE_STORE_CHUNK_SIZE = 32_768


def _state_store_key(type_name: str, state_id: str) -> tuple[str, str]:
    return (type_name, state_id)


def _normalize_chunk_size(chunk_size: int) -> int:
    return chunk_size if chunk_size > 0 else _DEFAULT_STATE_STORE_CHUNK_SIZE


def _set_state_store_chunk_size(type_name: str, chunk_size: int) -> int:
    chunk_size = _normalize_chunk_size(chunk_size)
    with _STATE_STORE_LOCK:
        _STATE_STORE_CHUNK_SIZES[type_name] = chunk_size
    return chunk_size


def _get_state_store_chunk_size(type_name: str) -> int:
    with _STATE_STORE_LOCK:
        return _STATE_STORE_CHUNK_SIZES.get(type_name, _DEFAULT_STATE_STORE_CHUNK_SIZE)


def _store_state_bytes(type_name: str, state_id: str, payload: bytes) -> None:
    with _STATE_STORE_LOCK:
        _STATE_STORE_DATA[_state_store_key(type_name, state_id)] = bytes(payload)


def _get_state_bytes(type_name: str, state_id: str) -> bytes | None:
    with _STATE_STORE_LOCK:
        return _STATE_STORE_DATA.get(_state_store_key(type_name, state_id))


def _delete_state_bytes(type_name: str, state_id: str) -> None:
    with _STATE_STORE_LOCK:
        _STATE_STORE_DATA.pop(_state_store_key(type_name, state_id), None)


def _list_state_ids(type_name: str) -> list[str]:
    with _STATE_STORE_LOCK:
        return [state_id for store_type, state_id in _STATE_STORE_DATA if store_type == type_name]


def _lock_state(type_name: str, state_id: str, operation: str) -> str:
    lock_id = str(uuid.uuid4())
    with _STATE_STORE_LOCK:
        _STATE_LOCKS[_state_store_key(type_name, state_id)] = lock_id
    return lock_id


def _unlock_state(type_name: str, state_id: str, lock_id: str) -> bool:
    with _STATE_STORE_LOCK:
        key = _state_store_key(type_name, state_id)
        existing_lock_id = _STATE_LOCKS.get(key)
        if existing_lock_id is None or existing_lock_id != lock_id:
            return False
        del _STATE_LOCKS[key]
        return True


def _reset_state_store_state_for_tests() -> None:
    """Reset in-memory state-store helper state (test only)."""
    with _STATE_STORE_LOCK:
        _STATE_STORE_DATA.clear()
        _STATE_LOCKS.clear()
        _STATE_STORE_CHUNK_SIZES.clear()


@rpc_handler("GenerateResourceConfig")
async def GenerateResourceConfigHandler(
    request: pb.GenerateResourceConfig.Request, context: Any
) -> pb.GenerateResourceConfig.Response:
    """Handle missing GenerateResourceConfig RPC."""
    return pb.GenerateResourceConfig.Response(config=request.state, diagnostics=[])


@rpc_handler("ValidateStateStoreConfig")
async def ValidateStateStoreConfigHandler(
    request: pb.ValidateStateStore.Request, context: Any
) -> pb.ValidateStateStore.Response:
    """Handle missing ValidateStateStoreConfig RPC."""
    return pb.ValidateStateStore.Response(diagnostics=[])


@rpc_handler("ConfigureStateStore")
async def ConfigureStateStoreHandler(
    request: pb.ConfigureStateStore.Request, context: Any
) -> pb.ConfigureStateStore.Response:
    """Handle missing ConfigureStateStore RPC."""
    chunk_size = _set_state_store_chunk_size(request.type_name, request.capabilities.chunk_size)
    return pb.ConfigureStateStore.Response(
        diagnostics=[],
        capabilities=pb.StateStoreServerCapabilities(chunk_size=chunk_size),
    )


@rpc_handler("ValidateListResourceConfig")
async def ValidateListResourceConfigHandler(
    request: pb.ValidateListResourceConfig.Request, context: Any
) -> pb.ValidateListResourceConfig.Response:
    """Handle missing ValidateListResourceConfig RPC."""
    return pb.ValidateListResourceConfig.Response(diagnostics=[])


@rpc_handler("PlanAction")
async def PlanActionHandler(request: pb.PlanAction.Request, context: Any) -> pb.PlanAction.Response:
    """Handle missing PlanAction RPC."""
    return pb.PlanAction.Response(diagnostics=[])


@rpc_handler("ValidateActionConfig")
async def ValidateActionConfigHandler(
    request: pb.ValidateActionConfig.Request, context: Any
) -> pb.ValidateActionConfig.Response:
    """Handle missing ValidateActionConfig RPC."""
    return pb.ValidateActionConfig.Response(diagnostics=[])


@rpc_handler("LockState")
async def LockStateHandler(request: pb.LockState.Request, context: Any) -> pb.LockState.Response:
    """Handle missing LockState RPC."""
    lock_id = _lock_state(request.type_name, request.state_id, request.operation)
    return pb.LockState.Response(lock_id=lock_id, diagnostics=[])


@rpc_handler("UnlockState")
async def UnlockStateHandler(request: pb.UnlockState.Request, context: Any) -> pb.UnlockState.Response:
    """Handle missing UnlockState RPC."""
    if _unlock_state(request.type_name, request.state_id, request.lock_id):
        return pb.UnlockState.Response(diagnostics=[])
    return pb.UnlockState.Response(
        diagnostics=[
            pb.Diagnostic(
                severity=pb.Diagnostic.WARNING,
                summary="UnlockState lock not held",
                detail="The provided lock ID does not match an active lock.",
            )
        ]
    )


@rpc_handler("GetStates")
async def GetStatesHandler(request: pb.GetStates.Request, context: Any) -> pb.GetStates.Response:
    """Handle missing GetStates RPC."""
    return pb.GetStates.Response(state_id=_list_state_ids(request.type_name), diagnostics=[])


@rpc_handler("DeleteState")
async def DeleteStateHandler(request: pb.DeleteState.Request, context: Any) -> pb.DeleteState.Response:
    """Handle missing DeleteState RPC."""
    _delete_state_bytes(request.type_name, request.state_id)
    return pb.DeleteState.Response(diagnostics=[])
