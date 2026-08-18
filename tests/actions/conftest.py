#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Shared components for action tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import ClassVar

import attrs
import pytest

from pyvider.actions import ActionContext, ActionPlan, ActionProgress, BaseAction
from pyvider.hub import hub
from pyvider.schema import PvsSchema, a_num, a_str, s_resource

ACTION_TYPE = "demo_reboot"


@attrs.define
class RebootConfig:
    """Configuration block for the demo action."""

    target: str | None = None
    attempts: int | None = None


class DemoRebootAction(BaseAction[RebootConfig]):
    """A configurable action whose behavior each test dictates."""

    config_class = RebootConfig

    #: Validation errors returned by validate(); empty means valid.
    validation_errors: ClassVar[list[str]] = []
    #: The plan returned by plan().
    planned: ClassVar[ActionPlan] = ActionPlan()
    #: Progress messages yielded by invoke().
    progress: ClassVar[list[str]] = []
    #: Contexts recorded by plan() and invoke() so tests can inspect them.
    plan_contexts: ClassVar[list[ActionContext[RebootConfig]]] = []
    invoke_contexts: ClassVar[list[ActionContext[RebootConfig]]] = []

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource(attributes={"target": a_str(), "attempts": a_num()})

    async def validate(self, config: RebootConfig | None) -> list[str]:
        return list(type(self).validation_errors)

    async def plan(self, ctx: ActionContext[RebootConfig]) -> ActionPlan:
        type(self).plan_contexts.append(ctx)
        return type(self).planned

    async def invoke(self, ctx: ActionContext[RebootConfig]) -> AsyncIterator[ActionProgress]:
        type(self).invoke_contexts.append(ctx)
        for message in type(self).progress:
            yield ActionProgress(message=message)


def _reset(cls: type[DemoRebootAction]) -> None:
    cls.validation_errors = []
    cls.planned = ActionPlan()
    cls.progress = []
    cls.plan_contexts = []
    cls.invoke_contexts = []


@pytest.fixture
def demo_action() -> Iterator[type[DemoRebootAction]]:
    _reset(DemoRebootAction)
    hub.register("action", ACTION_TYPE, DemoRebootAction)
    yield DemoRebootAction
    hub.unregister("action", ACTION_TYPE)
    _reset(DemoRebootAction)


# 🐍🏗️🔚
