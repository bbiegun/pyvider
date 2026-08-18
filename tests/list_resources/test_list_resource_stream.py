#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""The ListResource RPC streams registered list resources."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

import pytest

from pyvider.conversion import marshal, unmarshal_identity
from pyvider.handler import ProviderHandler
from pyvider.hub import hub
from pyvider.list_resources import BaseListResource, ListResourceContext, ListResult
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema, a_str, s_resource

from .conftest import LIST_TYPE, RESOURCE_TYPE, DemoWidget, DemoWidgetList, widget_result


async def _collect(
    type_name: str = LIST_TYPE,
    *,
    config: pb.DynamicValue | None = None,
    include_resource_object: bool = False,
    limit: int = 0,
) -> list[pb.ListResource.Event]:
    request = pb.ListResource.Request(
        type_name=type_name,
        include_resource_object=include_resource_object,
        limit=limit,
    )
    if config is not None:
        request.config.CopyFrom(config)

    handler = ProviderHandler()
    return [event async for event in handler.ListResource(request, context=None)]


def _errors(events: list[pb.ListResource.Event]) -> list[pb.Diagnostic]:
    return [d for event in events for d in event.diagnostic if d.severity == pb.Diagnostic.ERROR]


@pytest.mark.asyncio
async def test_no_registered_list_resources_yields_an_empty_stream() -> None:
    assert await _collect("anything") == []


@pytest.mark.asyncio
async def test_registered_results_are_streamed(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result("a"), widget_result("b")]

    events = await _collect()

    assert len(events) == 2
    assert [event.display_name for event in events] == ["widget a", "widget b"]
    assert _errors(events) == []


@pytest.mark.asyncio
async def test_identity_is_encoded_with_the_resource_identity_schema(
    demo_list: type[DemoWidgetList],
) -> None:
    demo_list.results = [widget_result("abc123")]

    events = await _collect()

    decoded = unmarshal_identity(events[0].identity, DemoWidget.get_identity_schema())
    assert decoded == {"id": "abc123"}


@pytest.mark.asyncio
async def test_resource_object_is_omitted_unless_requested(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result("a")]

    events = await _collect(include_resource_object=False)

    assert not events[0].HasField("resource_object")


@pytest.mark.asyncio
async def test_resource_object_is_included_when_requested(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result("a")]

    events = await _collect(include_resource_object=True)

    assert events[0].HasField("resource_object")
    assert events[0].resource_object.msgpack


@pytest.mark.asyncio
async def test_a_result_without_a_resource_object_stays_absent(
    demo_list: type[DemoWidgetList],
) -> None:
    demo_list.results = [widget_result("a", resource_object=None)]

    events = await _collect(include_resource_object=True)

    assert not events[0].HasField("resource_object")


@pytest.mark.asyncio
async def test_limit_stops_the_stream(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result(str(index)) for index in range(5)]

    events = await _collect(limit=2)

    assert len(events) == 2


@pytest.mark.asyncio
async def test_a_zero_limit_means_no_limit(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result(str(index)) for index in range(5)]

    events = await _collect(limit=0)

    assert len(events) == 5


@pytest.mark.asyncio
async def test_result_warnings_travel_with_the_event(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result("a", warnings=("partially stale",))]

    events = await _collect()

    assert len(events[0].diagnostic) == 1
    assert events[0].diagnostic[0].severity == pb.Diagnostic.WARNING
    assert events[0].diagnostic[0].summary == "partially stale"


@pytest.mark.asyncio
async def test_unknown_type_is_reported_as_an_error(demo_list: type[DemoWidgetList]) -> None:
    events = await _collect("not_registered")

    errors = _errors(events)
    assert len(errors) == 1
    assert "not_registered" in errors[0].summary
    assert LIST_TYPE in errors[0].detail


@pytest.mark.asyncio
async def test_missing_identity_schema_is_reported(demo_list: type[DemoWidgetList]) -> None:
    # Dropping the managed resource leaves the list resource without the
    # identity schema it borrows.
    hub.unregister("resource", RESOURCE_TYPE)
    try:
        events = await _collect()
    finally:
        hub.register("resource", RESOURCE_TYPE, DemoWidget)

    errors = _errors(events)
    assert len(errors) == 1
    assert "identity schema" in errors[0].summary


@pytest.mark.asyncio
async def test_validation_errors_stop_the_stream(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result("a")]
    demo_list.validation_errors = ["region is required"]

    events = await _collect()

    errors = _errors(events)
    assert [d.summary for d in errors] == ["region is required"]
    assert demo_list.seen_contexts == []


@pytest.mark.asyncio
async def test_a_failing_implementation_is_reported_after_partial_results(
    demo_list: type[DemoWidgetList],
) -> None:
    class Exploding(DemoWidgetList):
        async def list(self, ctx: ListResourceContext[Any]) -> AsyncIterator[ListResult]:
            yield widget_result("a")
            raise RuntimeError("upstream API rejected the query")

    hub.register("list_resource", LIST_TYPE, Exploding)
    events = await _collect()

    assert len(events) == 2
    assert events[0].display_name == "widget a"
    errors = _errors(events)
    assert len(errors) == 1
    assert "upstream API rejected the query" in errors[0].detail


@pytest.mark.asyncio
async def test_config_is_decoded_into_the_declared_config_class(
    demo_list: type[DemoWidgetList],
) -> None:
    demo_list.results = [widget_result("a")]
    config = marshal(
        {"region": "us-east-1", "include_archived": True},
        schema=demo_list.get_schema().block,
    )

    await _collect(config=config)

    ctx = demo_list.seen_contexts[0]
    assert ctx.config is not None
    assert ctx.config.region == "us-east-1"
    assert ctx.config.include_archived is True


@pytest.mark.asyncio
async def test_context_carries_the_request_parameters(demo_list: type[DemoWidgetList]) -> None:
    demo_list.results = [widget_result("a")]

    await _collect(include_resource_object=True, limit=7)

    ctx = demo_list.seen_contexts[0]
    assert ctx.type_name == LIST_TYPE
    assert ctx.include_resource_object is True
    assert ctx.limit == 7
    assert ctx.config is None


@pytest.mark.asyncio
async def test_an_undecodable_config_is_reported(demo_list: type[DemoWidgetList]) -> None:
    request = pb.ListResource.Request(type_name=LIST_TYPE)
    request.config.msgpack = b"\xc1not-msgpack"

    handler = ProviderHandler()
    events = [event async for event in handler.ListResource(request, context=None)]

    errors = _errors(events)
    assert len(errors) == 1
    assert "Invalid configuration" in errors[0].summary


@pytest.mark.asyncio
async def test_a_list_resource_without_a_config_class_receives_the_cty_value(
    demo_widget: type[DemoWidget],
) -> None:
    class RawConfigList(BaseListResource[Any]):
        resource_type = RESOURCE_TYPE
        seen: ClassVar[list[Any]] = []

        @classmethod
        def get_schema(cls) -> PvsSchema:
            return s_resource(attributes={"region": a_str()})

        async def list(self, ctx: ListResourceContext[Any]) -> AsyncIterator[ListResult]:
            type(self).seen.append(ctx.config)
            yield widget_result("a")

    hub.register("list_resource", "raw_config_list", RawConfigList)
    try:
        config = marshal({"region": "eu-west-1"}, schema=RawConfigList.get_schema().block)
        events = await _collect("raw_config_list", config=config)
    finally:
        hub.unregister("list_resource", "raw_config_list")

    assert len(events) == 1
    assert RawConfigList.seen[0]["region"].value == "eu-west-1"


# 🐍🏗️🔚
