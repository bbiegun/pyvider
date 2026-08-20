#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for ValidateResourceConfig handler."""

from typing import Any

import attrs
import pytest

from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.validate_resource_config import (
    ValidateResourceConfigHandler,
    _validate_resource_config_impl,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.schema import a_num, a_str, s_resource


@attrs.define
class SampleConfig:
    name: str
    count: int = 0


class SampleValidateResource(BaseResource):
    """Sample resource for validation testing."""

    config_class = SampleConfig

    @classmethod
    def get_schema(cls) -> s_resource:
        return s_resource(
            attributes={
                "id": a_str(computed=True),
                "name": a_str(required=True),
                "count": a_num(optional=True),
            }
        )

    async def _validate_config(self, config: SampleConfig) -> list[str]:
        errors = []
        if config.name == "invalid":
            errors.append("Name 'invalid' is not allowed")
        if config.count < 0:
            errors.append("Count must be non-negative")
        return errors

    async def read(self, ctx: Any) -> Any:
        return ctx.state

    async def _delete_apply(self, ctx: Any) -> None:
        pass


class TestValidateResourceConfigHandler:
    """Tests for ValidateResourceConfigHandler function."""

    @pytest.mark.asyncio
    async def test_handler_returns_response_object(self, provider_in_hub: Any) -> None:
        """Test that handler returns proper response object."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            schema = SampleValidateResource.get_schema()
            cty_type = schema.block.to_cty_type()
            config_cty = cty_type.validate({"name": "valid-name", "count": 5})

            from pyvider.conversion import marshal

            config_dv = marshal(config_cty, schema=schema.block)

            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=config_dv,
            )

            response = await ValidateResourceConfigHandler(request, context=None)

            assert isinstance(response, pb.ValidateResourceConfig.Response)
        finally:
            hub.unregister("resource", "test_resource")

    @pytest.mark.asyncio
    async def test_handler_validates_valid_config(self, provider_in_hub: Any) -> None:
        """Test handler validates valid configuration."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            schema = SampleValidateResource.get_schema()
            cty_type = schema.block.to_cty_type()
            config_cty = cty_type.validate({"name": "valid-name", "count": 10})

            from pyvider.conversion import marshal

            config_dv = marshal(config_cty, schema=schema.block)

            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=config_dv,
            )

            response = await ValidateResourceConfigHandler(request, context=None)

            assert len(response.diagnostics) == 0
        finally:
            hub.unregister("resource", "test_resource")

    @pytest.mark.asyncio
    async def test_handler_detects_invalid_config(self, provider_in_hub: Any) -> None:
        """Test handler detects invalid configuration."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            schema = SampleValidateResource.get_schema()
            cty_type = schema.block.to_cty_type()
            config_cty = cty_type.validate({"name": "invalid", "count": 5})

            from pyvider.conversion import marshal

            config_dv = marshal(config_cty, schema=schema.block)

            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=config_dv,
            )

            response = await ValidateResourceConfigHandler(request, context=None)

            assert len(response.diagnostics) > 0
            assert any("invalid" in str(d.summary).lower() for d in response.diagnostics)
        finally:
            hub.unregister("resource", "test_resource")

    @pytest.mark.asyncio
    async def test_handler_handles_unknown_resource_type(self) -> None:
        """Test handler handles unknown resource type."""
        request = pb.ValidateResourceConfig.Request(
            type_name="nonexistent_resource",
            config=pb.DynamicValue(msgpack=b"\x80"),
        )

        response = await ValidateResourceConfigHandler(request, context=None)

        assert isinstance(response, pb.ValidateResourceConfig.Response)
        assert len(response.diagnostics) > 0

    @pytest.mark.asyncio
    async def test_handler_handles_negative_count(self, provider_in_hub: Any) -> None:
        """Test handler detects negative count value."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            schema = SampleValidateResource.get_schema()
            cty_type = schema.block.to_cty_type()
            config_cty = cty_type.validate({"name": "test", "count": -5})

            from pyvider.conversion import marshal

            config_dv = marshal(config_cty, schema=schema.block)

            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=config_dv,
            )

            response = await ValidateResourceConfigHandler(request, context=None)

            assert len(response.diagnostics) > 0
            assert any("non-negative" in str(d.summary).lower() for d in response.diagnostics)
        finally:
            hub.unregister("resource", "test_resource")


class TestValidateResourceConfigImpl:
    """Tests for _validate_resource_config_impl function."""

    @pytest.mark.asyncio
    async def test_impl_returns_empty_diagnostics_for_valid_config(self, provider_in_hub: Any) -> None:
        """Test implementation returns no diagnostics for valid config."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            schema = SampleValidateResource.get_schema()
            cty_type = schema.block.to_cty_type()
            config_cty = cty_type.validate({"name": "valid", "count": 1})

            from pyvider.conversion import marshal

            config_dv = marshal(config_cty, schema=schema.block)

            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=config_dv,
            )

            response = await _validate_resource_config_impl(request, context=None)

            assert len(response.diagnostics) == 0
        finally:
            hub.unregister("resource", "test_resource")

    @pytest.mark.asyncio
    async def test_impl_handles_unknown_values_gracefully(self, provider_in_hub: Any) -> None:
        """Test implementation handles unknown/computed values during planning."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            schema = SampleValidateResource.get_schema()
            cty_type = schema.block.to_cty_type()

            from pyvider.cty import CtyString, CtyValue

            # Create config with unknown value
            # Built with the unknown in place. A CtyValue's payload is
            # immutable: mutating it used to work and quietly invalidated the
            # deep-mark memo cached against that value.
            config_cty = cty_type.validate({"name": CtyValue.unknown(CtyString()), "count": 5})

            from pyvider.conversion import marshal

            config_dv = marshal(config_cty, schema=schema.block)

            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=config_dv,
            )

            response = await _validate_resource_config_impl(request, context=None)

            # Should not crash, must skip custom validation for unknown values (Issue #5)
            assert isinstance(response, pb.ValidateResourceConfig.Response)
            assert len(response.diagnostics) == 0
        finally:
            hub.unregister("resource", "test_resource")

    @pytest.mark.asyncio
    async def test_impl_issue_5_regression(self, provider_in_hub: Any) -> None:
        """Test issue 5: Ensure custom validation skips when unknown values are present."""

        class Issue5Resource(BaseResource):
            config_class = SampleConfig

            @classmethod
            def get_schema(cls) -> s_resource:
                return s_resource(
                    attributes={
                        "name": a_str(required=True),
                        "count": a_num(optional=True),
                    }
                )

            async def _validate_config(self, config: SampleConfig) -> list[str]:
                # If unknown values were incorrectly converted to None, this would fail:
                return ["`name` must not be empty."] if not config.name else []

            async def read(self, ctx: Any) -> Any:
                return ctx.state

            async def _delete_apply(self, ctx: Any) -> None:
                pass

        hub.register("resource", "issue5_resource", Issue5Resource)

        try:
            schema = Issue5Resource.get_schema()
            cty_type = schema.block.to_cty_type()
            from pyvider.conversion import marshal
            from pyvider.cty import CtyString, CtyValue

            config_cty = cty_type.validate({"name": CtyValue.unknown(CtyString()), "count": 5})
            config_dv = marshal(config_cty, schema=schema.block)
            request = pb.ValidateResourceConfig.Request(
                type_name="issue5_resource",
                config=config_dv,
            )
            response = await _validate_resource_config_impl(request, context=None)

            # The validation should be completely skipped, producing 0 diagnostics.
            # If issue 5 happens, this would have a validation error "`name` must not be empty."
            assert len(response.diagnostics) == 0
        finally:
            hub.unregister("resource", "issue5_resource")

    @pytest.mark.asyncio
    async def test_impl_creates_diagnostic_from_exception(self) -> None:
        """Test implementation creates diagnostic from exceptions."""
        request = pb.ValidateResourceConfig.Request(
            type_name="unknown_resource",
            config=pb.DynamicValue(msgpack=b"\x80"),
        )

        response = await _validate_resource_config_impl(request, context=None)

        assert len(response.diagnostics) > 0
        assert response.diagnostics[0].severity == pb.Diagnostic.ERROR


class TestValidateResourceConfigEdgeCases:
    """Edge case tests for ValidateResourceConfig."""

    @pytest.mark.asyncio
    async def test_handler_with_empty_config(self, provider_in_hub: Any) -> None:
        """Test handler with empty configuration."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=pb.DynamicValue(msgpack=b"\x80"),  # Empty map
            )

            response = await ValidateResourceConfigHandler(request, context=None)

            # Empty config should fail schema validation (missing required 'name')
            assert isinstance(response, pb.ValidateResourceConfig.Response)
        finally:
            hub.unregister("resource", "test_resource")

    @pytest.mark.asyncio
    async def test_handler_rejects_present_null_required_attribute(self, provider_in_hub: Any) -> None:
        """A present-but-null required attribute must be rejected, not silently accepted.

        Terraform marshals every unset argument as a present null via
        ImpliedType(), not an absent key, so this is the common case in
        practice -- not an edge case. cty 0.5's CtyObject.validate no longer
        refuses this on its own (see pyvider.schema.required); the schema
        layer's own check has to be wired into the handler. The wire bytes
        below are `{"name": null}` (map with one key "name" -> msgpack nil)
        built directly rather than through `marshal`/`validate`, since
        constructing it the "normal" way requires the exact call that used to
        reject it. SampleValidateResource's schema declares only `name` as
        required -- `id` is computed and `count` is optional, so both may be
        legitimately absent from the map without tripping cty's separate
        "missing required attribute" check for an absent key.
        """
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=pb.DynamicValue(msgpack=b"\x81\xa4name\xc0"),
            )

            response = await ValidateResourceConfigHandler(request, context=None)

            assert len(response.diagnostics) > 0
            assert any("null" in str(d.summary).lower() for d in response.diagnostics)
            assert any(
                d.attribute.steps and d.attribute.steps[0].attribute_name == "name"
                for d in response.diagnostics
            )
        finally:
            hub.unregister("resource", "test_resource")

    @pytest.mark.asyncio
    async def test_handler_metrics_recorded(self, provider_in_hub: Any) -> None:
        """Test that handler records metrics."""
        hub.register("resource", "test_resource", SampleValidateResource)

        try:
            schema = SampleValidateResource.get_schema()
            cty_type = schema.block.to_cty_type()
            config_cty = cty_type.validate({"name": "test", "count": 1})

            from pyvider.conversion import marshal

            config_dv = marshal(config_cty, schema=schema.block)

            request = pb.ValidateResourceConfig.Request(
                type_name="test_resource",
                config=config_dv,
            )

            # Just verify handler completes successfully (metrics are recorded internally)
            response = await ValidateResourceConfigHandler(request, context=None)

            assert isinstance(response, pb.ValidateResourceConfig.Response)
        finally:
            hub.unregister("resource", "test_resource")


# 🐍🏗️🔚
