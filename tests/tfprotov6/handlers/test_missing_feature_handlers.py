#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for Terraform protocol v6.11 placeholder handlers."""

import pytest

from pyvider.protocols.tfprotov6.handlers.missing_feature_handlers import (
    ConfigureStateStoreHandler,
    DeleteStateHandler,
    GenerateResourceConfigHandler,
    GetStatesHandler,
    LockStateHandler,
    PlanActionHandler,
    UnlockStateHandler,
    ValidateActionConfigHandler,
    ValidateListResourceConfigHandler,
    ValidateStateStoreConfigHandler,
    list_state_ids,
    reset_state_stores,
    write_state_bytes,
)
import pyvider.protocols.tfprotov6.protobuf as pb


@pytest.fixture(autouse=True)
def _reset_state_store() -> None:
    """Ensure tests that use shared in-memory state store state stay isolated."""
    reset_state_stores()


def _assert_no_diagnostics(response_diag: list[pb.Diagnostic]) -> None:
    """Assert successful responses expose no diagnostics."""
    assert len(response_diag) == 0


@pytest.mark.asyncio
async def test_generate_resource_config_returns_state_without_warning() -> None:
    request = pb.GenerateResourceConfig.Request(type_name="demo")
    request.state.msgpack = b'{"x": 1}'

    response = await GenerateResourceConfigHandler(request, context=None)

    assert isinstance(response, pb.GenerateResourceConfig.Response)
    assert response.config == request.state
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_validate_list_resource_config_returns_empty_diagnostics() -> None:
    request = pb.ValidateListResourceConfig.Request(type_name="demo")

    response = await ValidateListResourceConfigHandler(request, context=None)

    assert isinstance(response, pb.ValidateListResourceConfig.Response)
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_validate_state_store_config_returns_empty_diagnostics() -> None:
    request = pb.ValidateStateStore.Request(type_name="demo")

    response = await ValidateStateStoreConfigHandler(request, context=None)

    assert isinstance(response, pb.ValidateStateStore.Response)
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_configure_state_store_returns_server_capabilities() -> None:
    request = pb.ConfigureStateStore.Request(type_name="demo")
    request.capabilities.chunk_size = 4096

    response = await ConfigureStateStoreHandler(request, context=None)

    assert isinstance(response, pb.ConfigureStateStore.Response)
    assert response.capabilities.chunk_size == 4096
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_plan_action_returns_empty_diagnostics() -> None:
    request = pb.PlanAction.Request(action_type="my_action")

    response = await PlanActionHandler(request, context=None)

    assert isinstance(response, pb.PlanAction.Response)
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_validate_action_config_returns_empty_diagnostics() -> None:
    request = pb.ValidateActionConfig.Request(type_name="my_action")

    response = await ValidateActionConfigHandler(request, context=None)

    assert isinstance(response, pb.ValidateActionConfig.Response)
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_lock_state_returns_lock_and_no_diagnostics() -> None:
    request = pb.LockState.Request(type_name="s3", state_id="id", operation="read")

    response = await LockStateHandler(request, context=None)

    assert isinstance(response, pb.LockState.Response)
    assert isinstance(response.lock_id, str)
    assert response.lock_id
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_unlock_state_releases_lock_and_no_diagnostics() -> None:
    lock_request = pb.LockState.Request(type_name="s3", state_id="id", operation="read")
    lock_response = await LockStateHandler(lock_request, context=None)

    request = pb.UnlockState.Request(type_name="s3", state_id="id", lock_id=lock_response.lock_id)

    response = await UnlockStateHandler(request, context=None)

    assert isinstance(response, pb.UnlockState.Response)
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_get_states_returns_state_ids_by_type() -> None:
    await write_state_bytes("s3", "first", b"state")
    await write_state_bytes("s3", "second", b"state")

    request = pb.GetStates.Request(type_name="s3")
    response = await GetStatesHandler(request, context=None)

    assert isinstance(response, pb.GetStates.Response)
    assert set(response.state_id) == {"first", "second"}
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_get_states_returns_empty_list_when_unknown_store() -> None:
    request = pb.GetStates.Request(type_name="s3")

    response = await GetStatesHandler(request, context=None)

    assert isinstance(response, pb.GetStates.Response)
    assert response.state_id == []
    _assert_no_diagnostics(response.diagnostics)


@pytest.mark.asyncio
async def test_delete_state_removes_state_and_no_diagnostics() -> None:
    await write_state_bytes("s3", "state-id", b"state")

    request = pb.DeleteState.Request(type_name="s3", state_id="state-id")

    response = await DeleteStateHandler(request, context=None)

    assert isinstance(response, pb.DeleteState.Response)
    _assert_no_diagnostics(response.diagnostics)
    assert "state-id" not in await list_state_ids("s3")
