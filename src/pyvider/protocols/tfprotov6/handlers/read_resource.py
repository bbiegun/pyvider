#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from typing import Any

import msgpack  # type: ignore[import-untyped]
from provide.foundation import logger

from pyvider.common.encryption import decrypt
from pyvider.conversion import marshal, marshal_identity, unmarshal, unmarshal_identity
from pyvider.exceptions import PyviderError, ResourceError
from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
from pyvider.protocols.tfprotov6.handlers.utils import (
    attrs_to_dict_for_cty,
    check_test_only_access,
    create_diagnostic_from_exception,
    cty_to_attrs_instance,
    resolve_identity_schema,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema


@rpc_handler("ReadResource")
async def ReadResourceHandler(request: pb.ReadResource.Request, context: Any) -> pb.ReadResource.Response:
    """Handle read resource request."""
    return await _read_resource_impl(request, context)


def _derive_new_state_identity_values(
    resource_class: Any,
    new_state_attrs: Any,
    resource_type: str,
) -> dict[str, Any] | None:
    """Derive identity from the post-read state, which -- like apply and unlike plan -- is
    fully known.

    This is only reached when the read returned a state, so both failure modes here are
    genuine defects rather than "not yet knowable":

    - A raised exception almost certainly indicates a bug in this resource's get_identity()
      override -- there is no missing-state excuse left by this point.
    - An ordinary None return means the identity schema's attribute names did not resolve
      against the state object -- a schema/state mismatch.

    Neither is surfaced as a Terraform diagnostic -- the read itself succeeded, and failing
    it over an identity-derivation bug would report a live resource as unreadable, which is
    strictly worse than the same bug being tolerated during plan and apply -- but both are
    logged at WARNING so they are visible in provider logs instead of silently
    disappearing.
    """
    try:
        identity_values: dict[str, Any] | None = resource_class.get_identity(new_state_attrs)
    except Exception as e:
        logger.warning(
            "Omitting new identity: derivation raised an exception after a successful read, "
            "which likely indicates a bug in this resource's get_identity() override",
            operation="read_resource",
            resource_type=resource_type,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        return None

    if identity_values is None:
        logger.warning(
            "Omitting new identity: get_identity() returned None even though the new state "
            "is fully known, which likely means the identity schema's attributes do not "
            "resolve against this resource's state object",
            operation="read_resource",
            resource_type=resource_type,
        )

    return identity_values


def _set_new_identity(
    response: pb.ReadResource.Response,
    resource_class: Any,
    identity_schema: PvsSchema | None,
    new_state_attrs: Any,
    resource_type: str,
) -> None:
    """Attach derived identity to the response, only when fully determinable."""
    if identity_schema is None:
        return
    identity_values = _derive_new_state_identity_values(resource_class, new_state_attrs, resource_type)
    if identity_values is not None:
        response.new_identity.CopyFrom(marshal_identity(identity_values, identity_schema))


async def _read_resource_impl(request: pb.ReadResource.Request, context: Any) -> pb.ReadResource.Response:
    """Implementation of ReadResource handler."""
    response = pb.ReadResource.Response()
    resource_context: Any = None

    logger.debug(
        "ReadResource handler called",
        operation="read_resource",
        resource_type=request.type_name,
        has_current_state=bool(request.current_state.msgpack),
        has_private_state=bool(request.private),
    )

    try:
        resource_class = hub.get_component("resource", request.type_name)
        if not resource_class:
            logger.error(
                "Resource type not found during read operation",
                operation="read_resource",
                resource_type=request.type_name,
                registered_resources=list(hub.get_components("resource").keys())
                if hub.get_components("resource")
                else [],
            )

            err = ResourceError(
                f"Resource type '{request.type_name}' not registered.\n\n"
                f"Suggestion: Ensure the resource is registered using the @resource decorator "
                f"and that component discovery has completed successfully.\n\n"
                f"Troubleshooting:\n"
                f"  1. Check that the resource class has the @resource decorator\n"
                f"  2. Verify the resource module is imported by the provider\n"
                f"  3. Run 'pyvider components list' to see registered resources\n"
                f"  4. Review provider logs for component registration errors"
            )
            err.add_context("resource.type_name", request.type_name)
            raise err

        # Check if this is a test-only component accessed without test mode
        check_test_only_access(resource_class, request.type_name, "resource")

        provider_instance = hub.get_component("singleton", "provider")
        if not provider_instance:
            logger.error(
                "Provider instance not found in hub during read operation",
                operation="read_resource",
                resource_type=request.type_name,
            )
            raise RuntimeError(
                "Provider instance not found in hub.\n\n"
                "This is an internal framework error. The provider should be registered "
                "during server initialization.\n\n"
                "Suggestion: Report this issue - it indicates a provider initialization problem."
            )

        logger.debug(
            "Resource and provider instances retrieved for read",
            operation="read_resource",
            resource_type=request.type_name,
        )

        resource_schema = resource_class.get_schema()
        identity_schema = resolve_identity_schema(resource_class)
        prior_state_cty = unmarshal(request.current_state, schema=resource_schema.block)
        prior_state_instance = cty_to_attrs_instance(prior_state_cty, resource_class.state_class)

        private_state_instance = None
        if (
            hasattr(resource_class, "private_state_class")
            and resource_class.private_state_class
            and request.private
        ):
            try:
                logger.debug(
                    "Deserializing private state for read operation",
                    operation="read_resource",
                    resource_type=request.type_name,
                    private_state_size=len(request.private),
                )

                decrypted_bytes = decrypt(request.private)
                private_data = msgpack.unpackb(decrypted_bytes, raw=False)
                private_state_instance = resource_class.private_state_class(**private_data)

                logger.debug(
                    "Private state deserialized successfully",
                    operation="read_resource",
                    resource_type=request.type_name,
                )

            except Exception as e:
                logger.error(
                    "Failed to deserialize private state during read",
                    operation="read_resource",
                    resource_type=request.type_name,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    exc_info=True,
                )

                err = ResourceError(
                    f"Failed to deserialize private state for resource '{request.type_name}': {e}\n\n"
                    f"Suggestion: This usually indicates a mismatch between the state encryption key "
                    f"or corrupted private state data.\n\n"
                    f"Troubleshooting:\n"
                    f"  1. Verify PYVIDER_PRIVATE_STATE_SHARED_SECRET hasn't changed\n"
                    f"  2. Check if the private state schema has changed incompatibly\n"
                    f"  3. Review the original error: {type(e).__name__}: {e}\n"
                    f"  4. Consider destroying and recreating the resource if schema changed"
                )
                err.add_context("resource.type_name", request.type_name)
                err.add_context("private_state.error", str(e))
                raise err from e

        logger.debug(
            "Invoking resource read method",
            operation="read_resource",
            resource_type=request.type_name,
        )

        resource_handler = resource_class()
        provider_context = hub.get_component("singleton", "provider_context")
        test_mode_enabled = getattr(provider_context, "test_mode_enabled", False)
        resource_context = ResourceContext(
            config=None,
            state=prior_state_instance,
            private_state=private_state_instance,
            capabilities=provider_instance.metadata.capabilities,  # type: ignore[arg-type]
            test_mode_enabled=test_mode_enabled,
            identity=(
                unmarshal_identity(request.current_identity, identity_schema)
                if identity_schema is not None
                else None
            ),
        )
        new_state_attrs = await resource_handler.read(resource_context)

        if new_state_attrs is not None:
            raw_state_dict = attrs_to_dict_for_cty(new_state_attrs)
            validator_type = resource_schema.block.to_cty_type()
            new_state_cty = validator_type.validate(raw_state_dict)
            marshalled_new_state = marshal(new_state_cty, schema=resource_schema.block)
            response.new_state.msgpack = marshalled_new_state.msgpack
            _set_new_identity(response, resource_class, identity_schema, new_state_attrs, request.type_name)

            logger.info(
                "Resource read completed successfully with new state",
                operation="read_resource",
                resource_type=request.type_name,
                state_fields=list(raw_state_dict.keys()),
            )
        else:
            response.new_state.msgpack = b"\xc0"

            logger.info(
                "Resource read completed - resource no longer exists",
                operation="read_resource",
                resource_type=request.type_name,
            )

        response.private = request.private

    except PyviderError as e:
        logger.error(
            "ReadResource failed with framework error",
            operation="read_resource",
            resource_type=request.type_name,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        diag = await create_diagnostic_from_exception(e)
        response.diagnostics.append(diag)
    except Exception as e:
        logger.error(
            "ReadResource failed with unexpected error",
            operation="read_resource",
            resource_type=request.type_name,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        diag = await create_diagnostic_from_exception(e)
        response.diagnostics.append(diag)

    if resource_context and resource_context.diagnostics:
        response.diagnostics.extend(resource_context.diagnostics)

    return response


# 🐍🏗️🔚
