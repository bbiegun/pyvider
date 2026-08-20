#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for ProviderHandler - Resource and data source operations."""

from collections.abc import Callable
from typing import Any

from provide.testkit.mocking import AsyncMock, MagicMock
import pytest

from pyvider.handler import ProviderHandler
import pyvider.protocols.tfprotov6.protobuf as pb


@pytest.fixture
def mock_provider() -> MagicMock:
    return MagicMock()


@pytest.mark.asyncio
async def test_validate_resource_config_delegates(mock_provider: MagicMock) -> None:
    """Test ValidateResourceConfig delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="validate_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.ValidateResourceConfig(request, context)

    mock_delegate.assert_awaited_once_with("ValidateResourceConfig", request, context)
    assert result == "validate_response"


@pytest.mark.asyncio
async def test_read_resource_delegates(mock_provider: MagicMock) -> None:
    """Test ReadResource delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="read_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.ReadResource(request, context)

    mock_delegate.assert_awaited_once_with("ReadResource", request, context)
    assert result == "read_response"


@pytest.mark.asyncio
async def test_plan_resource_change_delegates(mock_provider: MagicMock) -> None:
    """Test PlanResourceChange delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="plan_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.PlanResourceChange(request, context)

    mock_delegate.assert_awaited_once_with("PlanResourceChange", request, context)
    assert result == "plan_response"


@pytest.mark.asyncio
async def test_apply_resource_change_delegates(mock_provider: MagicMock) -> None:
    """Test ApplyResourceChange delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="apply_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.ApplyResourceChange(request, context)

    mock_delegate.assert_awaited_once_with("ApplyResourceChange", request, context)
    assert result == "apply_response"


@pytest.mark.asyncio
async def test_import_resource_state_delegates(mock_provider: MagicMock) -> None:
    """Test ImportResourceState delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="import_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.ImportResourceState(request, context)

    mock_delegate.assert_awaited_once_with("ImportResourceState", request, context)
    assert result == "import_response"


@pytest.mark.asyncio
async def test_upgrade_resource_state_delegates(mock_provider: MagicMock) -> None:
    """Test UpgradeResourceState delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="upgrade_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.UpgradeResourceState(request, context)

    mock_delegate.assert_awaited_once_with("UpgradeResourceState", request, context)
    assert result == "upgrade_response"


@pytest.mark.asyncio
async def test_move_resource_state_delegates(mock_provider: MagicMock) -> None:
    """Test MoveResourceState delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="move_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.MoveResourceState(request, context)

    mock_delegate.assert_awaited_once_with("MoveResourceState", request, context)
    assert result == "move_response"


@pytest.mark.asyncio
async def test_validate_data_resource_config_delegates(mock_provider: MagicMock) -> None:
    """Test ValidateDataResourceConfig delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="validate_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.ValidateDataResourceConfig(request, context)

    mock_delegate.assert_awaited_once_with("ValidateDataResourceConfig", request, context)
    assert result == "validate_response"


@pytest.mark.asyncio
async def test_read_data_source_delegates(mock_provider: MagicMock) -> None:
    """Test ReadDataSource delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="read_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.ReadDataSource(request, context)

    mock_delegate.assert_awaited_once_with("ReadDataSource", request, context)
    assert result == "read_response"


@pytest.mark.asyncio
async def test_validate_ephemeral_resource_config_delegates(mock_provider: MagicMock) -> None:
    """Test ValidateEphemeralResourceConfig delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="validate_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.ValidateEphemeralResourceConfig(request, context)

    mock_delegate.assert_awaited_once_with("ValidateEphemeralResourceConfig", request, context)
    assert result == "validate_response"


@pytest.mark.asyncio
async def test_open_ephemeral_resource_delegates(mock_provider: MagicMock) -> None:
    """Test OpenEphemeralResource delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="open_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.OpenEphemeralResource(request, context)

    mock_delegate.assert_awaited_once_with("OpenEphemeralResource", request, context)
    assert result == "open_response"


@pytest.mark.asyncio
async def test_renew_ephemeral_resource_delegates(mock_provider: MagicMock) -> None:
    """Test RenewEphemeralResource delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="renew_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.RenewEphemeralResource(request, context)

    mock_delegate.assert_awaited_once_with("RenewEphemeralResource", request, context)
    assert result == "renew_response"


@pytest.mark.parametrize(
    ("method_name", "request_factory"),
    [
        ("GenerateResourceConfig", lambda: pb.GenerateResourceConfig.Request(type_name="demo")),
        (
            "ValidateListResourceConfig",
            lambda: pb.ValidateListResourceConfig.Request(type_name="demo"),
        ),
        ("ValidateStateStoreConfig", lambda: pb.ValidateStateStore.Request(type_name="demo")),
        ("ConfigureStateStore", lambda: pb.ConfigureStateStore.Request(type_name="demo")),
        ("PlanAction", lambda: pb.PlanAction.Request(action_type="demo_action")),
        ("ValidateActionConfig", lambda: pb.ValidateActionConfig.Request(type_name="demo_action")),
        (
            "LockState",
            lambda: pb.LockState.Request(type_name="demo_state", state_id="state-id", operation="read"),
        ),
        (
            "UnlockState",
            lambda: pb.UnlockState.Request(type_name="demo_state", state_id="state-id", lock_id="lock-id"),
        ),
        ("GetStates", lambda: pb.GetStates.Request(type_name="demo_state")),
        ("DeleteState", lambda: pb.DeleteState.Request(type_name="demo_state", state_id="state-id")),
    ],
)
@pytest.mark.asyncio
async def test_6_11_placeholder_handlers_delegate(
    method_name: str, request_factory: Callable[[], Any], mock_provider: MagicMock
) -> None:
    """Test v6.11 placeholder methods delegate to _delegate."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="placeholder_response")
    handler._delegate = mock_delegate

    request = request_factory()
    context = MagicMock()

    method = getattr(handler, method_name)
    result = await method(request, context)

    mock_delegate.assert_awaited_once_with(method_name, request, context)
    assert result == "placeholder_response"


@pytest.mark.asyncio
async def test_close_ephemeral_resource_delegates(mock_provider: MagicMock) -> None:
    """Test CloseEphemeralResource delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="close_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.CloseEphemeralResource(request, context)

    mock_delegate.assert_awaited_once_with("CloseEphemeralResource", request, context)
    assert result == "close_response"


@pytest.mark.asyncio
async def test_get_functions_delegates(mock_provider: MagicMock) -> None:
    """Test GetFunctions delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="functions_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.GetFunctions(request, context)

    mock_delegate.assert_awaited_once_with("GetFunctions", request, context)
    assert result == "functions_response"


@pytest.mark.asyncio
async def test_call_function_delegates(mock_provider: MagicMock) -> None:
    """Test CallFunction delegates to handler."""
    handler = ProviderHandler(provider=mock_provider)

    mock_delegate = AsyncMock(return_value="call_response")
    handler._delegate = mock_delegate

    request = MagicMock()
    context = MagicMock()

    result = await handler.CallFunction(request, context)

    mock_delegate.assert_awaited_once_with("CallFunction", request, context)
    assert result == "call_response"


# 🐍🏗️🔚
