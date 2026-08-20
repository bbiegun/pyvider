#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Registration, schema resolution, and discovery of list resources."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from pyvider.hub import hub
from pyvider.list_resources import BaseListResource, ListResourceContext, ListResult, register_list_resource
from pyvider.protocols.tfprotov6.handlers.get_metadata import GetMetadataHandler
from pyvider.protocols.tfprotov6.handlers.get_provider_schema import _collect_list_resource_schemas
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema, a_str, s_resource

from .conftest import LIST_TYPE, RESOURCE_TYPE, DemoWidget, DemoWidgetList


class MinimalList(BaseListResource[Any]):
    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource(attributes={"filter": a_str()})

    async def list(self, ctx: ListResourceContext[Any]) -> AsyncIterator[ListResult]:
        yield ListResult(identity={"id": "only"})


@pytest.fixture
def registered(request: pytest.FixtureRequest) -> Iterator[str]:
    name = "registered_list"
    yield name
    if hub.get_component("list_resource", name) is not None:
        hub.unregister("list_resource", name)


def test_decorator_registers_in_the_hub(registered: str) -> None:
    decorated = register_list_resource(registered)(type("Decorated", (MinimalList,), {}))

    assert hub.get_component("list_resource", registered) is decorated
    assert decorated._registered_name == registered
    assert decorated._is_registered_list_resource is True
    assert decorated._is_test_only is False


def test_decorator_can_set_the_managed_resource_type(registered: str) -> None:
    decorated = register_list_resource(registered, resource_type=RESOURCE_TYPE)(
        type("Decorated", (MinimalList,), {})
    )

    assert decorated.resource_type == RESOURCE_TYPE


def test_decorator_can_mark_a_list_resource_test_only(registered: str) -> None:
    decorated = register_list_resource(registered, test_only=True)(type("Decorated", (MinimalList,), {}))

    assert decorated._is_test_only is True


def test_decorator_rejects_a_non_list_resource() -> None:
    with pytest.raises(TypeError, match="BaseListResource"):

        @register_list_resource("invalid_list")
        class NotAListResource:  # type: ignore[misc]
            pass


def test_identity_schema_defaults_to_the_managed_resource(demo_widget: type[DemoWidget]) -> None:
    schema = DemoWidgetList.get_identity_schema()

    assert schema is not None
    assert set(schema.block.attributes) == {"id"}


def test_resource_object_schema_defaults_to_the_managed_resource(demo_widget: type[DemoWidget]) -> None:
    schema = DemoWidgetList.get_resource_object_schema()

    assert schema is not None
    assert set(schema.block.attributes) == {"id", "name", "size"}


def test_schemas_are_none_without_a_managed_resource_type() -> None:
    assert MinimalList.resource_type is None
    assert MinimalList.get_identity_schema() is None
    assert MinimalList.get_resource_object_schema() is None


def test_schemas_are_none_when_the_managed_resource_is_absent() -> None:
    class DanglingList(MinimalList):
        resource_type = "never_registered_resource"

    assert DanglingList.get_identity_schema() is None
    assert DanglingList.get_resource_object_schema() is None


def test_schemas_are_none_when_the_resource_declares_none() -> None:
    class SchemalessResource:
        pass

    hub.register("resource", "schemaless_resource", SchemalessResource)

    class BorrowingList(MinimalList):
        resource_type = "schemaless_resource"

    try:
        assert BorrowingList.get_identity_schema() is None
        assert BorrowingList.get_resource_object_schema() is None
    finally:
        hub.unregister("resource", "schemaless_resource")


@pytest.mark.asyncio
async def test_validate_defaults_to_accepting_any_config() -> None:
    assert await MinimalList().validate(None) == []


@pytest.mark.asyncio
async def test_metadata_advertises_registered_list_resources(demo_list: type[DemoWidgetList]) -> None:
    response = await GetMetadataHandler(pb.GetMetadata.Request(), context=None)

    assert {entry.type_name for entry in response.list_resources} == {LIST_TYPE}


@pytest.mark.asyncio
async def test_metadata_reports_none_when_nothing_is_registered() -> None:
    response = await GetMetadataHandler(pb.GetMetadata.Request(), context=None)

    assert list(response.list_resources) == []


@pytest.mark.asyncio
async def test_schema_collection_includes_registered_list_resources(
    demo_list: type[DemoWidgetList],
) -> None:
    diagnostics: list[pb.Diagnostic] = []

    schemas = await _collect_list_resource_schemas(diagnostics)

    assert set(schemas) == {LIST_TYPE}
    assert {attr.name for attr in schemas[LIST_TYPE].block.attributes} == {"region", "include_archived"}
    assert diagnostics == []


@pytest.mark.asyncio
async def test_a_failing_list_resource_schema_becomes_a_warning(registered: str) -> None:
    class BrokenList(MinimalList):
        @classmethod
        def get_schema(cls) -> PvsSchema:
            raise RuntimeError("schema build failed")

    register_list_resource(registered)(BrokenList)
    diagnostics: list[pb.Diagnostic] = []

    schemas = await _collect_list_resource_schemas(diagnostics)

    assert registered not in schemas
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == pb.Diagnostic.WARNING
    assert registered in diagnostics[0].summary


# 🐍🏗️🔚
