#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from typing import Any

from provide.foundation import logger

from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
import pyvider.protocols.tfprotov6.protobuf as pb


@rpc_handler("MoveResourceState")
async def MoveResourceStateHandler(
    request: pb.MoveResourceState.Request, context: Any
) -> pb.MoveResourceState.Response:
    """Handle move resource state request."""
    return await _move_resource_state_impl(request, context)


async def _move_resource_state_impl(
    request: pb.MoveResourceState.Request, context: Any
) -> pb.MoveResourceState.Response:
    """Implementation of MoveResourceState handler."""
    logger.debug(
        "MoveResourceState requested",
        operation="move_resource_state",
        source_type_name=request.source_type_name,
        target_type_name=request.target_type_name,
        source_state_has_json=bool(request.source_state.json),
    )

    target_state = pb.DynamicValue(json=request.source_state.json or b"{}")
    target_identity = pb.ResourceIdentityData(
        identity_data=pb.DynamicValue(json=request.source_identity.json or b"{}")
    )

    logger.info(
        "MoveResourceState completed",
        operation="move_resource_state",
        target_state_bytes=len(target_state.json),
    )

    return pb.MoveResourceState.Response(
        target_state=target_state,
        diagnostics=[],
        target_private=request.source_private,
        target_identity=target_identity,
    )


# 🐍🏗️🔚
