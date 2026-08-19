#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Apply must create a resource whose plan contains unknown computed values.

Marking a computed attribute unknown during plan is the ordinary pattern -- the
provider fills it in during apply. A regression made that arrive at apply as
``planned_state=None``, which ``BaseResource.apply`` reads as a destroy, so a
create silently deleted instead and returned null state with no diagnostic.

The cause was a validation policy leaking out of ``cty_to_attrs_instance``:
returning None for any value that is not wholly known is right when handing a
config to a provider's custom validator (issue #5), and wrong everywhere None
already means something else.
"""

from __future__ import annotations

from typing import Any, ClassVar

import attrs
import pytest

from pyvider.conversion import marshal, unmarshal
from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.apply_resource_change import ApplyResourceChangeHandler
from pyvider.protocols.tfprotov6.handlers.plan_resource_change import PlanResourceChangeHandler
from pyvider.protocols.tfprotov6.handlers.utils import cty_to_attrs_instance
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.providers.base import BaseProvider, ProviderMetadata
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_str, a_unknown, s_resource

RESOURCE = "unknown_computed_widget"


@attrs.define(frozen=True)
class WidgetConfig:
    name: str | None = None


@attrs.define(frozen=True)
class WidgetState:
    name: str | None = None
    generated: str | None = None


class UnknownComputedWidget(BaseResource[WidgetState, WidgetState, WidgetConfig]):
    """Computes `generated` during apply, so it is unknown at plan time."""

    config_class = WidgetConfig
    state_class = WidgetState

    deleted: ClassVar[list[str]] = []

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource({"name": a_str(required=True), "generated": a_str(computed=True)})

    async def _validate_config(self, config: WidgetConfig) -> list[str]:
        return []

    async def _create(
        self, ctx: ResourceContext, base_plan: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, Any]:
        base_plan["generated"] = a_unknown(a_str())
        return base_plan, None

    async def _create_apply(self, ctx: ResourceContext) -> tuple[WidgetState | None, Any]:
        assert ctx.planned_state is not None, "apply was handed no planned state"
        return attrs.evolve(ctx.planned_state, generated=f"generated-for-{ctx.config.name}"), None

    async def read(self, ctx: ResourceContext) -> WidgetState | None:
        state: WidgetState | None = ctx.state
        return state

    async def _delete_apply(self, ctx: ResourceContext) -> None:
        type(self).deleted.append(getattr(ctx.state, "name", "?"))


@pytest.fixture
def widget() -> Any:
    UnknownComputedWidget.deleted = []
    previous = hub.get_component("singleton", "provider")
    hub.register("singleton", "provider", BaseProvider(metadata=ProviderMetadata(name="t", version="0")))
    hub.register("resource", RESOURCE, UnknownComputedWidget)

    yield UnknownComputedWidget

    hub.unregister("resource", RESOURCE)
    if previous is None:
        hub.unregister("singleton", "provider")
    else:
        hub.register("singleton", "provider", previous)
    UnknownComputedWidget.deleted = []


@pytest.mark.asyncio
async def test_a_plan_with_an_unknown_computed_value_creates_rather_than_deletes(
    widget: Any,
) -> None:
    config = marshal({"name": "alpha", "generated": None}, schema=widget.get_schema().block)

    plan = await PlanResourceChangeHandler(
        pb.PlanResourceChange.Request(type_name=RESOURCE, config=config, proposed_new_state=config),
        context=None,
    )
    assert not plan.diagnostics, f"plan failed: {plan.diagnostics}"

    applied = await ApplyResourceChangeHandler(
        pb.ApplyResourceChange.Request(
            type_name=RESOURCE,
            config=config,
            planned_state=plan.planned_state,
            planned_private=plan.planned_private,
        ),
        context=None,
    )

    assert not applied.diagnostics, f"apply failed: {applied.diagnostics}"
    state = unmarshal(applied.new_state, schema=widget.get_schema().block)
    # The regression produced a null state and ran _delete_apply instead.
    assert not state.is_null, "apply returned null state: the create was executed as a destroy"
    assert state["generated"].value == "generated-for-alpha"
    assert widget.deleted == [], "apply deleted the resource it was asked to create"


def test_the_converter_still_withholds_unknown_values_by_default() -> None:
    """Issue #5's policy is intact: validators are not handed half-known objects."""
    from pyvider.cty import CtyObject, CtyString, CtyValue

    cty_type = CtyObject(attribute_types={"name": CtyString()})
    partially_known = cty_type.validate({"name": CtyValue.unknown(CtyString())})

    assert cty_to_attrs_instance(partially_known, WidgetConfig) is None


def test_allow_unknown_converts_instead_of_collapsing() -> None:
    """With the opt-in, unknown attributes become None on a real instance."""
    from pyvider.cty import CtyObject, CtyString, CtyValue

    cty_type = CtyObject(attribute_types={"name": CtyString(), "generated": CtyString()})
    partially_known = cty_type.validate({"name": "alpha", "generated": CtyValue.unknown(CtyString())})

    instance = cty_to_attrs_instance(partially_known, WidgetState, allow_unknown=True)

    assert instance is not None
    assert instance.name == "alpha"
    assert instance.generated is None


# 🐍🏗️🔚
