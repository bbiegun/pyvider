#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Terraform protocol v6.11 configuration and action RPC handlers.

The state-store RPCs that used to live here now delegate to
:mod:`pyvider.protocols.tfprotov6.handlers.state_store_handlers`, which routes
every operation through a pluggable durable backend. They are re-exported below
so existing import sites keep working.
"""

from __future__ import annotations

from typing import Any

from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
from pyvider.protocols.tfprotov6.handlers.state_store_handlers import (
    ConfigureStateStoreHandler,
    DeleteStateHandler,
    GetStatesHandler,
    LockStateHandler,
    UnlockStateHandler,
    ValidateStateStoreConfigHandler,
    delete_state_bytes,
    list_state_ids,
    read_state_bytes,
    reset_state_stores,
    state_store_chunk_size,
    write_state_bytes,
)
import pyvider.protocols.tfprotov6.protobuf as pb

__all__ = [
    "ConfigureStateStoreHandler",
    "DeleteStateHandler",
    "GenerateResourceConfigHandler",
    "GetStatesHandler",
    "LockStateHandler",
    "PlanActionHandler",
    "UnlockStateHandler",
    "ValidateActionConfigHandler",
    "ValidateListResourceConfigHandler",
    "ValidateStateStoreConfigHandler",
    "delete_state_bytes",
    "list_state_ids",
    "read_state_bytes",
    "reset_state_stores",
    "state_store_chunk_size",
    "write_state_bytes",
]


@rpc_handler("GenerateResourceConfig")
async def GenerateResourceConfigHandler(
    request: pb.GenerateResourceConfig.Request, context: Any
) -> pb.GenerateResourceConfig.Response:
    """Handle missing GenerateResourceConfig RPC."""
    return pb.GenerateResourceConfig.Response(config=request.state, diagnostics=[])


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


# 🐍🏗️🔚
