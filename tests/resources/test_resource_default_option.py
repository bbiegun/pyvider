#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""`PvsAttribute.default` has to be resolved by the provider.

The plugin protocol schema carries no default-value field, so Terraform sends an
omitted optional attribute as null and never learns what the provider considers
the default. Unless the framework resolves it while decoding config and building
the plan, `a_str(default=...)` is inert and apply can return a value Terraform
never planned.
"""

from typing import Any

import attrs
import pytest

from pyvider.cty import CtyObject, CtyString, CtyValue
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_str, s_resource

DEFAULT_SIZE = "small"


@attrs.define
class WidgetConfig:
    name: str
    size: str | None = DEFAULT_SIZE


@attrs.define
class WidgetState:
    name: str
    size: str | None = DEFAULT_SIZE
    id: str | None = None


class Widget(BaseResource[Any, WidgetState, WidgetConfig]):
    config_class = WidgetConfig
    state_class = WidgetState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource(
            attributes={
                "name": a_str(required=True),
                "size": a_str(default=DEFAULT_SIZE),
                "id": a_str(computed=True),
            }
        )

    async def _validate_config(self, config: WidgetConfig) -> list[str]:
        return []

    async def read(self, ctx: ResourceContext) -> WidgetState | None:
        return ctx.state

    async def _delete_apply(self, ctx: ResourceContext) -> None:
        return None


CONFIG_TYPE = CtyObject({"name": CtyString(), "size": CtyString(), "id": CtyString()})


def _config_cty(size: CtyValue | str) -> CtyValue:
    return CONFIG_TYPE.validate({"name": "example", "size": size, "id": CtyValue.unknown(CtyString())})


class TestSchemaFlags:
    """An attribute with a default has to be Optional + Computed.

    Terraform rejects a planned value on an attribute that is not computed
    ("planned value ... for a non-computed attribute"), so a schema default is
    unusable unless the attribute is also computed.
    """

    def test_default_marks_the_attribute_optional_and_computed(self) -> None:
        attribute = a_str(default=DEFAULT_SIZE)

        assert attribute.optional is True
        assert attribute.computed is True
        assert attribute.required is False

    def test_attribute_without_a_default_is_not_computed(self) -> None:
        attribute = a_str()

        assert attribute.optional is True
        assert attribute.computed is False

    def test_required_attribute_is_not_made_computed(self) -> None:
        # Required and Computed is a contradiction the schema rejects outright,
        # so a default on a required attribute must not force the flag on.
        attribute = a_str(required=True, default=DEFAULT_SIZE)

        assert attribute.required is True
        assert attribute.computed is False

    def test_write_only_attribute_is_not_made_computed(self) -> None:
        # A write-only value is never stored, so it cannot be computed.
        attribute = a_str(optional=True, write_only=True, default=DEFAULT_SIZE)

        assert attribute.write_only is True
        assert attribute.computed is False


class TestConfigDecoding:
    def test_omitted_attribute_decodes_to_its_default(self) -> None:
        config = Widget.from_cty(_config_cty(CtyValue.null(CtyString())), WidgetConfig)

        assert config is not None
        assert config.size == DEFAULT_SIZE

    def test_configured_value_overrides_the_default(self) -> None:
        config = Widget.from_cty(_config_cty("large"), WidgetConfig)

        assert config is not None
        assert config.size == "large"

    def test_unknown_value_does_not_become_the_default(self) -> None:
        config = Widget.from_cty(_config_cty(CtyValue.unknown(CtyString())), WidgetConfig)

        assert config is not None
        assert config.size is None


class TestPlanning:
    @pytest.mark.asyncio
    async def test_create_plan_contains_the_default(self) -> None:
        config_cty = _config_cty(CtyValue.null(CtyString()))
        ctx = ResourceContext(
            config=Widget.from_cty(config_cty, WidgetConfig),
            state=None,
            config_cty=config_cty,
        )

        planned_state, _ = await Widget().plan(ctx)

        assert planned_state is not None
        assert planned_state["size"] == DEFAULT_SIZE

    @pytest.mark.asyncio
    async def test_update_plan_contains_the_default(self) -> None:
        config_cty = _config_cty(CtyValue.null(CtyString()))
        ctx = ResourceContext(
            config=Widget.from_cty(config_cty, WidgetConfig),
            state=WidgetState(name="example", size="large", id="w-1"),
            config_cty=config_cty,
        )

        planned_state, _ = await Widget().plan(ctx)

        assert planned_state is not None
        assert planned_state["size"] == DEFAULT_SIZE

    @pytest.mark.asyncio
    async def test_configured_value_wins_over_the_default_in_the_plan(self) -> None:
        config_cty = _config_cty("large")
        ctx = ResourceContext(
            config=Widget.from_cty(config_cty, WidgetConfig),
            state=None,
            config_cty=config_cty,
        )

        planned_state, _ = await Widget().plan(ctx)

        assert planned_state is not None
        assert planned_state["size"] == "large"

    @pytest.mark.asyncio
    async def test_unknown_value_stays_unknown_in_the_plan(self) -> None:
        config_cty = _config_cty(CtyValue.unknown(CtyString()))
        ctx = ResourceContext(
            config=Widget.from_cty(config_cty, WidgetConfig),
            state=None,
            config_cty=config_cty,
        )

        planned_state, _ = await Widget().plan(ctx)

        assert planned_state is not None
        planned_size = planned_state["size"]
        assert isinstance(planned_size, CtyValue)
        assert planned_size.is_unknown


# 🐍🏗️🔚
