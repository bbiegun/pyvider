#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


import asyncio
from typing import Any, cast

from provide.foundation import logger

from pyvider.hub import hub
from pyvider.observability import handler_errors
from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.rpcplugin.config import rpcplugin_config
from pyvider.rpcplugin.server import RPCPluginServer

#: Shutdown tasks, held so the event loop cannot collect one mid-flight and
#: abandon a half-stopped server. Tests await these to observe the shutdown.
_shutdown_tasks: set[asyncio.Task[None]] = set()


@rpc_handler("StopProvider")
async def StopProviderHandler(request: pb.StopProvider.Request, context: Any) -> pb.StopProvider.Response:
    """
    Handles the StopProvider RPC call from Terraform Core.
    This is the primary mechanism for Terraform to request a graceful plugin exit.
    """
    return await _stop_provider_impl(request, context)


async def _stop_after_response(server_instance: RPCPluginServer) -> None:
    """Stop the server once the StopProvider response has gone out.

    Stopping the gRPC server waits out its grace period and then cancels every
    call still in flight. Awaiting it from inside a handler therefore deadlocks
    on itself: the handler cannot return until the stop completes, and the stop
    will not complete until the handler returns -- so the caller that asked for
    the shutdown receives UNAVAILABLE and cannot tell an orderly stop from a
    provider that died mid-shutdown.
    """
    # Yield long enough for the response to be written before the transport
    # goes away. This is the server's own drain window, not a new constant.
    await asyncio.sleep(rpcplugin_config.plugin_grpc_grace_period)
    try:
        await server_instance.stop()
        logger.info("Provider server stop completed successfully", operation="stop_provider")
    except Exception as e:
        # The caller already has its response, so this can only be recorded,
        # not returned. Counted as well as logged so a provider that routinely
        # fails to shut down is visible in metrics rather than only in logs.
        handler_errors.inc(handler="StopProvider")
        logger.error(
            "Provider server stop failed after responding",
            operation="stop_provider",
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )


def _schedule_shutdown(server_instance: RPCPluginServer) -> asyncio.Task[None]:
    """Hand the shutdown to the event loop so this RPC can answer first."""
    task = asyncio.create_task(_stop_after_response(server_instance))
    _shutdown_tasks.add(task)
    task.add_done_callback(_shutdown_tasks.discard)
    return task


async def _stop_provider_impl(request: pb.StopProvider.Request, context: Any) -> pb.StopProvider.Response:
    """Implementation of StopProvider handler.

    StopProvider.Response carries an `Error` string, which is the protocol's
    channel for reporting a stop that could not be started -- so a failure is
    returned there rather than raised. Raising would surface to Terraform as a
    transport error, indistinguishable from the plugin having crashed.
    """
    logger.info("StopProvider RPC received, initiating graceful shutdown", operation="stop_provider")

    try:
        server_factory = hub.get_component("singleton", "rpc_plugin_server")
        server_instance = (
            cast(RPCPluginServer, server_factory() if callable(server_factory) else server_factory)
            if server_factory
            else None
        )
    except Exception as e:
        handler_errors.inc(handler="StopProvider")
        logger.error(
            "Unexpected error during provider stop",
            operation="stop_provider",
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        return pb.StopProvider.Response(Error=f"{type(e).__name__}: {e}")

    if server_instance is None:
        # Nothing to stop is not a failure: the plugin exits when its serving
        # coroutine finishes either way.
        logger.warning(
            "No active RPCPluginServer instance found during stop",
            operation="stop_provider",
        )
        return pb.StopProvider.Response()

    logger.debug("Scheduling server stop for graceful shutdown", operation="stop_provider")
    _schedule_shutdown(server_instance)

    logger.info("StopProvider handler completed successfully", operation="stop_provider")
    return pb.StopProvider.Response()


# 🐍🏗️🔚
