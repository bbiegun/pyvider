#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


import json
from typing import Any

from provide.foundation import logger

from pyvider.conversion import marshal_identity
from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
from pyvider.protocols.tfprotov6.handlers.utils import create_diagnostic_from_exception
import pyvider.protocols.tfprotov6.protobuf as pb


@rpc_handler("UpgradeResourceIdentity")
async def UpgradeResourceIdentityHandler(
    request: pb.UpgradeResourceIdentity.Request, context: Any
) -> pb.UpgradeResourceIdentity.Response:
    """Handle the UpgradeResourceIdentity RPC."""
    return await _upgrade_resource_identity_impl(request, context)


async def _upgrade_resource_identity_impl(
    request: pb.UpgradeResourceIdentity.Request, context: Any
) -> pb.UpgradeResourceIdentity.Response:
    """Upgrade stored identity data to the resource's current identity version.

    raw_identity is JSON-encoded per the proto. When the stored version already
    matches, the data passes through untouched -- the same shape as the
    existing UpgradeResourceState passthrough.
    """
    response = pb.UpgradeResourceIdentity.Response()

    try:
        resource_class = hub.get_component("resource", request.type_name)
        if not resource_class:
            return pb.UpgradeResourceIdentity.Response(
                diagnostics=[
                    pb.Diagnostic(
                        severity=pb.Diagnostic.ERROR,
                        summary=f"Unknown resource type '{request.type_name}'",
                        detail=(
                            f"Resource type '{request.type_name}' is not registered.\n\n"
                            "Suggestion: Ensure the resource is registered using the "
                            "@register_resource decorator and that component discovery "
                            "has completed successfully."
                        ),
                    )
                ]
            )

        schema = resource_class.get_identity_schema()
        if schema is None:
            return pb.UpgradeResourceIdentity.Response(
                diagnostics=[
                    pb.Diagnostic(
                        severity=pb.Diagnostic.ERROR,
                        summary=f"Resource '{request.type_name}' declares no identity schema",
                        detail=(
                            "Terraform asked to upgrade identity data for a resource that "
                            "does not declare an identity schema. This is a bug in the "
                            "provider: implement get_identity_schema() on the resource."
                        ),
                    )
                ]
            )

        raw_identity = json.loads(request.raw_identity.json) if request.raw_identity.json else {}

        if request.version == schema.version:
            logger.debug(
                "Identity version matches, passing through",
                operation="upgrade_resource_identity",
                resource_type=request.type_name,
                version=request.version,
            )
            upgraded = raw_identity
        else:
            logger.info(
                "Upgrading resource identity",
                operation="upgrade_resource_identity",
                resource_type=request.type_name,
                from_version=request.version,
                to_version=schema.version,
            )
            upgraded = await resource_class.upgrade_identity(request.version, raw_identity)

        response.upgraded_identity.CopyFrom(marshal_identity(upgraded, schema))

    except Exception as e:
        logger.error(
            "UpgradeResourceIdentity failed",
            operation="upgrade_resource_identity",
            resource_type=request.type_name,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        response.diagnostics.append(await create_diagnostic_from_exception(e))

    return response


# 🐍🏗️🔚
