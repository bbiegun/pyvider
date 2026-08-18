#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Registered state stores are advertised through metadata and schema RPCs."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.get_metadata import GetMetadataHandler
from pyvider.protocols.tfprotov6.handlers.get_provider_schema import _collect_state_store_schemas
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema, a_str, s_provider
from pyvider.state_stores import InMemoryStateStore, register_state_store


class ConfiguredStore(InMemoryStateStore):
    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_provider(attributes={"bucket": a_str(required=True)})


class SchemalessStore(InMemoryStateStore):
    pass


@pytest.fixture
def registered_stores() -> Iterator[None]:
    register_state_store("configured_store")(ConfiguredStore)
    register_state_store("schemaless_store")(SchemalessStore)
    yield
    hub.unregister("state_store", "configured_store")
    hub.unregister("state_store", "schemaless_store")


@pytest.mark.asyncio
async def test_metadata_advertises_registered_state_stores(registered_stores: None) -> None:
    response = await GetMetadataHandler(pb.GetMetadata.Request(), context=None)

    advertised = {entry.type_name for entry in response.state_stores}
    assert {"configured_store", "schemaless_store"} <= advertised


@pytest.mark.asyncio
async def test_metadata_reports_no_state_stores_when_none_are_registered() -> None:
    response = await GetMetadataHandler(pb.GetMetadata.Request(), context=None)

    assert list(response.state_stores) == []


@pytest.mark.asyncio
async def test_schema_collection_includes_only_stores_with_a_schema(registered_stores: None) -> None:
    diagnostics: list[pb.Diagnostic] = []

    schemas = await _collect_state_store_schemas(diagnostics)

    assert "configured_store" in schemas
    assert "schemaless_store" not in schemas
    assert diagnostics == []


@pytest.mark.asyncio
async def test_a_failing_store_schema_becomes_a_warning() -> None:
    class BrokenStore(InMemoryStateStore):
        @classmethod
        def get_schema(cls) -> PvsSchema:
            raise RuntimeError("schema build failed")

    register_state_store("broken_store")(BrokenStore)
    diagnostics: list[pb.Diagnostic] = []
    try:
        schemas = await _collect_state_store_schemas(diagnostics)
    finally:
        hub.unregister("state_store", "broken_store")

    assert "broken_store" not in schemas
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == pb.Diagnostic.WARNING
    assert "broken_store" in diagnostics[0].summary


# 🐍🏗️🔚
