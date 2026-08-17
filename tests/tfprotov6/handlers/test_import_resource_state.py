#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for ImportResourceState handler.

The three answers the handler must keep DISTINCT — "this type cannot be imported",
"this object does not exist", and "here it is" — because collapsing any two of them
misdirects whoever reads the error.
"""

from attrs import define
from provide.testkit.mocking import patch
import pytest

from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.import_resource_state import (
    ImportResourceStateHandler,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema, a_str, s_resource


@define
class _ImportableState:
    id: str
    name: str


class _Importable:
    """Minimal resource that supports import."""

    state_class = _ImportableState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource(
            {
                "id": a_str(computed=True),
                "name": a_str(required=True),
            }
        )

    async def import_state(self, ctx, import_id: str):
        if import_id == "missing":
            return None
        return _ImportableState(id=f"things/{import_id}", name=import_id)


class _NotImportable:
    """A resource with no import_state: reported as unsupported for THIS resource,
    not as a framework limitation."""

    state_class = _ImportableState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource({"id": a_str(computed=True), "name": a_str(required=True)})


@pytest.fixture
def registered(request):
    """Register a resource class in the hub for the duration of one test."""
    cls = request.param
    hub.register("resource", "test_resource", cls)
    yield cls
    try:
        hub.unregister("resource", "test_resource")
    except Exception:
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [_Importable], indirect=True)
async def test_import_returns_the_object(registered) -> None:
    """An object that already exists is adopted into state."""
    request = pb.ImportResourceState.Request(type_name="test_resource", id="widget")

    response = await ImportResourceStateHandler(request, context=None)

    assert not [d for d in response.diagnostics if d.severity == pb.Diagnostic.ERROR]
    assert len(response.imported_resources) == 1
    assert response.imported_resources[0].type_name == "test_resource"
    # Empty msgpack would import a resource that shows every attribute as a change
    # on the next plan.
    assert response.imported_resources[0].state.msgpack


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [_Importable], indirect=True)
async def test_import_of_absent_object_is_not_found(registered) -> None:
    """ "Does not exist" is a different answer from "cannot be imported"."""
    request = pb.ImportResourceState.Request(type_name="test_resource", id="missing")

    response = await ImportResourceStateHandler(request, context=None)

    assert len(response.imported_resources) == 0
    assert len(response.diagnostics) == 1
    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "non-existent" in response.diagnostics[0].summary


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [_NotImportable], indirect=True)
async def test_resource_without_import_state_says_so(registered) -> None:
    """A resource with no import_state reports itself as unsupported."""
    request = pb.ImportResourceState.Request(type_name="test_resource", id="widget")

    response = await ImportResourceStateHandler(request, context=None)

    assert len(response.imported_resources) == 0
    assert len(response.diagnostics) == 1
    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "does not support import" in response.diagnostics[0].summary


@pytest.mark.asyncio
async def test_unregistered_type_is_an_error() -> None:
    """An unknown type name is a configuration mistake, and is reported as one."""
    request = pb.ImportResourceState.Request(type_name="no_such_resource", id="x")

    response = await ImportResourceStateHandler(request, context=None)

    assert len(response.imported_resources) == 0
    assert len(response.diagnostics) == 1
    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR


@pytest.mark.asyncio
async def test_import_resource_state_records_error_metric_on_exception() -> None:
    """Test that handler increments error counter on exception."""
    request = pb.ImportResourceState.Request(
        type_name="test_resource",
        id="test-id",
    )

    with (
        patch("pyvider.protocols.tfprotov6.handlers._metrics.handler_errors") as mock_errors,
        patch(
            "pyvider.protocols.tfprotov6.handlers.import_resource_state._import_resource_state_impl"
        ) as mock_impl,
    ):
        mock_impl.side_effect = RuntimeError("Test error")

        with pytest.raises(RuntimeError):
            await ImportResourceStateHandler(request, context=None)

        mock_errors.inc.assert_called_once_with(handler="ImportResourceState")


@pytest.mark.asyncio
async def test_import_resource_state_records_metrics() -> None:
    """Test that handler records request and duration metrics."""
    request = pb.ImportResourceState.Request(
        type_name="test_resource",
        id="test-id",
    )

    with (
        patch("pyvider.protocols.tfprotov6.handlers._metrics.handler_requests") as mock_requests,
        patch("pyvider.protocols.tfprotov6.handlers._metrics.handler_duration") as mock_duration,
    ):
        await ImportResourceStateHandler(request, context=None)

        mock_requests.inc.assert_called_once_with(handler="ImportResourceState")
        assert mock_duration.observe.call_count == 1


# 🐍🏗️🔚
