#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Identity must stay stable across read, plan, and apply."""

from typing import Any

from attrs import define
from provide.testkit.mocking import MagicMock, patch
import pytest

from pyvider.conversion import marshal, unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas import (
    GetResourceIdentitySchemasHandler,
)
from pyvider.protocols.tfprotov6.handlers.read_resource import _read_resource_impl
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_num, a_str, s_identity, s_resource

IDENTITY_SCHEMA = s_identity(attributes={"region": a_str(required=True), "name": a_str(required=True)})


@define(frozen=True)
class WidgetState:
    region: str | None = None
    name: str | None = None
    size: int | None = None


class WidgetResource(BaseResource[Any, WidgetState, Any]):
    state_class = WidgetState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource(
            {
                "region": a_str(required=True),
                "name": a_str(required=True),
                "size": a_num(computed=True),
            }
        )

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA

    async def _validate_config(self, config: Any) -> list[str]:
        return []

    async def read(self, ctx: ResourceContext) -> WidgetState | None:
        return WidgetState(region="us-east-1", name="widget", size=3)

    async def _delete_apply(self, ctx: ResourceContext) -> None:
        return None


@pytest.mark.asyncio
async def test_identity_schema_is_advertised() -> None:
    with patch(
        "pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas.get_all_components",
        return_value={"pyvider_widget": WidgetResource},
    ):
        response = await GetResourceIdentitySchemasHandler(
            pb.GetResourceIdentitySchemas.Request(), context=None
        )

    schema = response.identity_schemas["pyvider_widget"]
    assert [a.name for a in schema.identity_attributes] == ["region", "name"]
    assert all(a.required_for_import for a in schema.identity_attributes)


@pytest.mark.asyncio
async def test_read_emits_identity_excluding_non_identity_state() -> None:
    provider = MagicMock()
    provider.metadata.capabilities = {}
    state = marshal({"region": "us-east-1", "name": "widget"}, schema=WidgetResource.get_schema().block)
    request = pb.ReadResource.Request(type_name="pyvider_widget", current_state=state)

    with patch(
        "pyvider.protocols.tfprotov6.handlers.read_resource.hub.get_component",
        side_effect=lambda kind, name: WidgetResource if kind == "resource" else provider,
    ):
        response = await _read_resource_impl(request, context=None)

    identity = unmarshal_identity(response.new_identity, IDENTITY_SCHEMA)
    assert identity == {"region": "us-east-1", "name": "widget"}
    assert "size" not in identity


# 🐍🏗️🔚
