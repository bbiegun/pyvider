#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Registration and discovery of actions."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest

from pyvider.actions import ActionContext, ActionPlan, ActionProgress, BaseAction, register_action
from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.get_metadata import GetMetadataHandler
from pyvider.protocols.tfprotov6.handlers.get_provider_schema import _collect_action_schemas
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema, a_str, s_resource

from .conftest import ACTION_TYPE, DemoRebootAction


class MinimalAction(BaseAction[None]):
    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource(attributes={"target": a_str()})

    async def invoke(self, ctx: ActionContext[None]) -> AsyncIterator[ActionProgress]:
        yield ActionProgress(message="done")


@pytest.fixture
def registered() -> Iterator[str]:
    name = "registered_action"
    yield name
    if hub.get_component("action", name) is not None:
        hub.unregister("action", name)


def test_decorator_registers_in_the_hub(registered: str) -> None:
    decorated = register_action(registered)(type("Decorated", (MinimalAction,), {}))

    assert hub.get_component("action", registered) is decorated
    assert decorated._registered_name == registered
    assert decorated._is_registered_action is True
    assert decorated._is_test_only is False


def test_decorator_can_mark_an_action_test_only(registered: str) -> None:
    decorated = register_action(registered, test_only=True)(type("Decorated", (MinimalAction,), {}))

    assert decorated._is_test_only is True


def test_decorator_rejects_a_non_action() -> None:
    with pytest.raises(TypeError, match="BaseAction"):

        @register_action("invalid_action")
        class NotAnAction:  # type: ignore[misc]
            pass


@pytest.mark.asyncio
async def test_default_hooks_accept_and_run_unconditionally() -> None:
    action = MinimalAction()

    assert await action.validate(None) == []
    assert await action.plan(ActionContext(action_type="minimal")) == ActionPlan()


def test_action_config_class_defaults_to_none() -> None:
    assert MinimalAction.config_class is None


@pytest.mark.asyncio
async def test_metadata_advertises_registered_actions(demo_action: type[DemoRebootAction]) -> None:
    response = await GetMetadataHandler(pb.GetMetadata.Request(), context=None)

    assert {entry.type_name for entry in response.actions} == {ACTION_TYPE}


@pytest.mark.asyncio
async def test_metadata_reports_none_when_nothing_is_registered() -> None:
    response = await GetMetadataHandler(pb.GetMetadata.Request(), context=None)

    assert list(response.actions) == []


@pytest.mark.asyncio
async def test_schema_collection_wraps_action_schemas(demo_action: type[DemoRebootAction]) -> None:
    diagnostics: list[pb.Diagnostic] = []

    schemas = await _collect_action_schemas(diagnostics)

    assert set(schemas) == {ACTION_TYPE}
    assert isinstance(schemas[ACTION_TYPE], pb.ActionSchema)
    assert {attr.name for attr in schemas[ACTION_TYPE].schema.block.attributes} == {"target", "attempts"}
    assert diagnostics == []


@pytest.mark.asyncio
async def test_a_failing_action_schema_becomes_a_warning(registered: str) -> None:
    class BrokenAction(MinimalAction):
        @classmethod
        def get_schema(cls) -> PvsSchema:
            raise RuntimeError("schema build failed")

    register_action(registered)(BrokenAction)
    diagnostics: list[pb.Diagnostic] = []

    schemas = await _collect_action_schemas(diagnostics)

    assert registered not in schemas
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == pb.Diagnostic.WARNING
    assert registered in diagnostics[0].summary


# 🐍🏗️🔚
