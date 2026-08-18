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
from pyvider.protocols.tfprotov6.handlers.apply_resource_change import _apply_resource_change_impl
from pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas import (
    GetResourceIdentitySchemasHandler,
)
from pyvider.protocols.tfprotov6.handlers.plan_resource_change import _plan_resource_change_impl
from pyvider.protocols.tfprotov6.handlers.read_resource import _read_resource_impl
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_num, a_str, s_identity, s_resource

IDENTITY_SCHEMA = s_identity(attributes={"region": a_str(required=True), "name": a_str(required=True)})
EXPECTED_IDENTITY = {"region": "us-east-1", "name": "widget"}


@define(frozen=True)
class WidgetState:
    region: str | None = None
    name: str | None = None
    size: int | None = None


@define(frozen=True)
class WidgetConfig:
    region: str | None = None
    name: str | None = None
    size: int | None = None


class WidgetResource(BaseResource[Any, WidgetState, WidgetConfig]):
    config_class = WidgetConfig
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
        "pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas.get_filtered_components",
        return_value={"pyvider_widget": WidgetResource},
    ):
        response = await GetResourceIdentitySchemasHandler(
            pb.GetResourceIdentitySchemas.Request(), context=None
        )

    schema = response.identity_schemas["pyvider_widget"]
    assert [a.name for a in schema.identity_attributes] == ["region", "name"]
    assert all(a.required_for_import for a in schema.identity_attributes)


def _patched(module: str) -> Any:
    provider = MagicMock()
    provider.metadata.capabilities = {}
    return patch(
        f"pyvider.protocols.tfprotov6.handlers.{module}.hub.get_component",
        side_effect=lambda kind, name: WidgetResource if kind == "resource" else provider,
    )


def _widget_state() -> pb.DynamicValue:
    return marshal({"region": "us-east-1", "name": "widget"}, schema=WidgetResource.get_schema().block)


async def _read_identity() -> dict[str, Any] | None:
    request = pb.ReadResource.Request(type_name="pyvider_widget", current_state=_widget_state())
    with _patched("read_resource"):
        response = await _read_resource_impl(request, context=None)
    assert not response.diagnostics
    return unmarshal_identity(response.new_identity, IDENTITY_SCHEMA)


async def _plan_identity() -> dict[str, Any] | None:
    request = pb.PlanResourceChange.Request(
        type_name="pyvider_widget",
        config=_widget_state(),
        proposed_new_state=_widget_state(),
        prior_private=b"",
    )
    with _patched("plan_resource_change"):
        response = await _plan_resource_change_impl(request, context=None)
    assert not response.diagnostics
    return unmarshal_identity(response.planned_identity, IDENTITY_SCHEMA)


async def _apply_identity() -> dict[str, Any] | None:
    request = pb.ApplyResourceChange.Request(
        type_name="pyvider_widget",
        config=_widget_state(),
        planned_state=_widget_state(),
        planned_private=b"",
    )
    with _patched("apply_resource_change"):
        response = await _apply_resource_change_impl(request, context=None)
    assert not response.diagnostics
    return unmarshal_identity(response.new_identity, IDENTITY_SCHEMA)


@pytest.mark.asyncio
async def test_read_emits_identity_excluding_non_identity_state() -> None:
    identity = await _read_identity()

    assert identity == EXPECTED_IDENTITY
    assert identity is not None
    assert "size" not in identity


@pytest.mark.asyncio
async def test_identity_is_stable_across_read_plan_and_apply() -> None:
    """One resource driven through all three RPCs, asserting they agree.

    This is not redundant with the per-handler tests. Plan derives identity from an attrs
    instance rebuilt by re-validating the planned-state dict against the resource schema,
    while read and apply derive from the live attrs object the resource returned -- three
    call sites, two different derivation inputs, and nothing else proves they land on the
    same value. Terraform itself cross-checks plan-vs-apply identity and reports a mismatch
    as a provider bug (`node_resource_abstract_instance.go`), so drift here surfaces to
    users as a broken provider rather than as a wrong-but-quiet value. Partial wiring is
    exactly how identity drifts silently between read and apply.
    """
    read_identity = await _read_identity()
    plan_identity = await _plan_identity()
    apply_identity = await _apply_identity()

    assert read_identity == EXPECTED_IDENTITY
    assert plan_identity == read_identity
    assert apply_identity == read_identity


# 🐍🏗️🔚
