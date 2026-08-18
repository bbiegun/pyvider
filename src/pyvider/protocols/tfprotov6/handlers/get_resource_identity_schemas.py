#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from typing import Any

from provide.foundation import logger

from pyvider.conversion import pvs_identity_schema_to_proto
from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
from pyvider.protocols.tfprotov6.handlers.utils import (
    get_filtered_components,
    resolve_identity_schema,
)
import pyvider.protocols.tfprotov6.protobuf as pb


@rpc_handler("GetResourceIdentitySchemas")
async def GetResourceIdentitySchemasHandler(
    request: pb.GetResourceIdentitySchemas.Request, context: Any
) -> pb.GetResourceIdentitySchemas.Response:
    """Handle the GetResourceIdentitySchemas RPC."""
    return await _get_resource_identity_schemas_impl(request, context)


async def _get_resource_identity_schemas_impl(
    request: pb.GetResourceIdentitySchemas.Request, context: Any
) -> pb.GetResourceIdentitySchemas.Response:
    """Collect identity schemas for every resource that declares one.

    Identity is opt-in: a resource whose get_identity_schema() returns None is
    simply absent from the map, which is what Terraform expects. A resource
    registered without get_identity_schema() at all (duck-typed, predating
    identity) means the same thing -- resolve_identity_schema() treats the
    missing method as "no identity" rather than letting the try/except below
    turn it into a spurious warning.
    """
    identity_schemas: dict[str, pb.ResourceIdentitySchema] = {}
    diagnostics: list[pb.Diagnostic] = []

    for name, resource_class in get_filtered_components("resource").items():
        try:
            schema = resolve_identity_schema(resource_class)
            if schema is None:
                continue
            identity_schemas[name] = pvs_identity_schema_to_proto(schema)
        except Exception as e:
            logger.warning(
                "Identity schema collection failed for resource",
                operation="get_resource_identity_schemas",
                resource_type=name,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            diagnostics.append(
                pb.Diagnostic(
                    severity=pb.Diagnostic.WARNING,
                    summary=f"Identity schema collection error for resource '{name}'",
                    detail=str(e),
                )
            )

    logger.debug(
        "Collected resource identity schemas",
        operation="get_resource_identity_schemas",
        identity_count=len(identity_schemas),
        warning_count=len(diagnostics),
    )

    return pb.GetResourceIdentitySchemas.Response(identity_schemas=identity_schemas, diagnostics=diagnostics)


# 🐍🏗️🔚
