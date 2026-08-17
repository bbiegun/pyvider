#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from typing import Any

from provide.foundation import logger

from pyvider.conversion import marshal
from pyvider.exceptions import ResourceError
from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
from pyvider.protocols.tfprotov6.handlers.utils import (
    attrs_to_dict_for_cty,
    check_test_only_access,
    create_diagnostic_from_exception,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.context import ResourceContext


@rpc_handler("ImportResourceState")
async def ImportResourceStateHandler(
    request: pb.ImportResourceState.Request, context: Any
) -> pb.ImportResourceState.Response:
    """Handle import resource state request."""
    return await _import_resource_state_impl(request, context)


async def _import_resource_state_impl(
    request: pb.ImportResourceState.Request, context: Any
) -> pb.ImportResourceState.Response:
    """Adopt an object that already exists into Terraform state.

    A resource participates by implementing `import_state(ctx, id) -> state | None`;
    the framework marshals whatever it returns through the resource schema.

    `read()` is deliberately not used as a fallback: read is given prior state,
    while import is given an ID STRING and must locate the object from that alone.
    A resource whose identity is more than its id — a workspace plus a name, say —
    can only answer the second question deliberately.
    """
    response = pb.ImportResourceState.Response()

    logger.debug(
        "ImportResourceState handler called",
        operation="import_resource_state",
        resource_type=request.type_name,
        import_id=request.id,
    )

    try:
        resource_class = hub.get_component("resource", request.type_name)
        if not resource_class:
            err = ResourceError(
                f"Resource type '{request.type_name}' not registered.\n\n"
                f"Suggestion: Ensure the resource is registered with @register_resource "
                f"and that component discovery has completed.\n\n"
                f"Run 'pyvider components list' to see what was registered."
            )
            err.add_context("resource.type_name", request.type_name)
            raise err

        check_test_only_access(resource_class, request.type_name, "resource")

        resource_schema = resource_class.get_schema()
        resource_handler = resource_class()
        import_state = getattr(resource_handler, "import_state", None)
        if import_state is None:
            # A resource that cannot be imported is a normal thing to be, so this
            # reports the resource rather than the framework.
            logger.info(
                "Resource does not implement import_state",
                operation="import_resource_state",
                resource_type=request.type_name,
            )
            response.diagnostics.append(
                pb.Diagnostic(
                    severity=pb.Diagnostic.ERROR,
                    summary=f"{request.type_name} does not support import",
                    detail=(
                        f"The resource type '{request.type_name}' does not implement "
                        f"`import_state`, so an existing object cannot be adopted into state.\n\n"
                        f"Suggestion: implement `async def import_state(self, ctx, import_id)` on the "
                        f"resource, returning its state object — or declare the resource in "
                        f"configuration and apply it instead."
                    ),
                )
            )
            return response

        provider_instance = hub.get_component("singleton", "provider")
        provider_context = hub.get_component("singleton", "provider_context")
        test_mode_enabled = getattr(provider_context, "test_mode_enabled", False)
        resource_context: ResourceContext = ResourceContext(
            config=None,
            state=None,
            capabilities=provider_instance.metadata.capabilities if provider_instance else {},  # type: ignore[arg-type]
            test_mode_enabled=test_mode_enabled,
        )

        imported = await import_state(resource_context, request.id)

        if imported is None:
            # "Not found" and "cannot import" are different answers; Terraform has a
            # specific message for the first, and conflating them misdirects the reader.
            response.diagnostics.append(
                pb.Diagnostic(
                    severity=pb.Diagnostic.ERROR,
                    summary="Cannot import non-existent remote object",
                    detail=(
                        f"No {request.type_name} was found for id {request.id!r}. Only objects that "
                        f"already exist can be imported; check the id, or use `tofu apply` to create it."
                    ),
                )
            )
            return response

        raw_state_dict = attrs_to_dict_for_cty(imported)
        validator_type = resource_schema.block.to_cty_type()
        state_cty = validator_type.validate(raw_state_dict)
        marshalled = marshal(state_cty, schema=resource_schema.block)

        imported_resource = pb.ImportResourceState.ImportedResource(
            type_name=request.type_name,
        )
        imported_resource.state.msgpack = marshalled.msgpack
        imported_resource.private = b""
        response.imported_resources.append(imported_resource)

        logger.info(
            "Resource imported successfully",
            operation="import_resource_state",
            resource_type=request.type_name,
            import_id=request.id,
            state_fields=list(raw_state_dict.keys()),
        )
        return response

    except Exception as e:
        logger.error(
            "Resource import failed",
            operation="import_resource_state",
            resource_type=request.type_name,
            import_id=request.id,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        response.diagnostics.append(await create_diagnostic_from_exception(e))
        return response
