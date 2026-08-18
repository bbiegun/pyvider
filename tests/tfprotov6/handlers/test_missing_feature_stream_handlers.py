#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Functional tests for stream-style Terraform Plugin v6.11 handlers."""

from collections.abc import AsyncIterator

import pytest

from pyvider.handler import ProviderHandler
from pyvider.protocols.tfprotov6.handlers.missing_feature_handlers import _reset_state_store_state_for_tests
import pyvider.protocols.tfprotov6.protobuf as pb


@pytest.fixture(autouse=True)
def _reset_state_store() -> None:
    """Ensure state-store behavior tests are deterministic."""
    _reset_state_store_state_for_tests()


@pytest.mark.asyncio
async def test_list_resource_returns_no_events() -> None:
    handler = ProviderHandler()

    request = pb.ListResource.Request(type_name="demo")

    events = []
    async for event in handler.ListResource(request, context=None):
        events.append(event)

    assert events == []


@pytest.mark.asyncio
async def test_read_state_bytes_returns_empty_payload_when_state_missing() -> None:
    handler = ProviderHandler()

    request = pb.ReadStateBytes.Request(type_name="s3", state_id="state-id")

    responses = []
    async for response in handler.ReadStateBytes(request, context=None):
        responses.append(response)

    assert len(responses) == 1
    response = responses[0]
    assert response.total_length == 0
    assert len(response.diagnostics) == 0
    assert response.bytes == b""


async def _request_chunks() -> AsyncIterator[pb.WriteStateBytes.RequestChunk]:
    yield pb.WriteStateBytes.RequestChunk(
        meta=pb.RequestChunkMeta(type_name="s3", state_id="state-id"),
        bytes=b"abc",
        total_length=6,
        range=pb.StateRange(start=0, end=3),
    )
    yield pb.WriteStateBytes.RequestChunk(
        meta=pb.RequestChunkMeta(type_name="s3", state_id="state-id"),
        bytes=b"def",
        total_length=6,
        range=pb.StateRange(start=3, end=6),
    )


@pytest.mark.asyncio
async def test_write_state_bytes_persists_state_and_returns_success() -> None:
    handler = ProviderHandler()

    response = await handler.WriteStateBytes(_request_chunks(), context=None)

    assert isinstance(response, pb.WriteStateBytes.Response)
    assert len(response.diagnostics) == 0

    read_request = pb.ReadStateBytes.Request(type_name="s3", state_id="state-id")
    responses = []
    async for response in handler.ReadStateBytes(read_request, context=None):
        responses.append(response)

    assert responses
    assert b"".join(payload.bytes for payload in responses) == b"abcdef"
    assert responses[0].total_length == 6


@pytest.mark.asyncio
async def test_invoke_action_emits_completed_event() -> None:
    handler = ProviderHandler()

    request = pb.InvokeAction.Request(action_type="demo-action")

    events = []
    async for event in handler.InvokeAction(request, context=None):
        events.append(event)

    assert len(events) == 1
    event = events[0]
    assert event.WhichOneof("type") == "completed"
    completed = event.completed
    assert completed.diagnostics == []
