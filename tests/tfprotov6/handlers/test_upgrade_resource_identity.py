#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the UpgradeResourceIdentity handler."""

import json

from provide.testkit.mocking import AsyncMock, MagicMock, patch
import pytest

from pyvider.conversion import unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.upgrade_resource_identity import (
    UpgradeResourceIdentityHandler,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import a_str, s_identity

MODULE = "pyvider.protocols.tfprotov6.handlers.upgrade_resource_identity"
SCHEMA = s_identity(attributes={"path": a_str(required=True)}, version=2)


def _resource(schema=SCHEMA, upgraded=None) -> MagicMock:
    cls = MagicMock()
    cls.get_identity_schema.return_value = schema
    cls.upgrade_identity = AsyncMock(return_value=upgraded or {"path": "/upgraded"})
    return cls


def _request(version: int) -> pb.UpgradeResourceIdentity.Request:
    return pb.UpgradeResourceIdentity.Request(
        type_name="demo",
        version=version,
        raw_identity=pb.RawState(json=json.dumps({"path": "/tmp/x"}).encode("utf-8")),
    )


@pytest.mark.asyncio
async def test_passes_through_when_version_matches() -> None:
    resource = _resource()

    with patch(f"{MODULE}.hub.get_component", return_value=resource):
        response = await UpgradeResourceIdentityHandler(_request(version=2), context=None)

    resource.upgrade_identity.assert_not_awaited()
    assert not response.diagnostics
    assert unmarshal_identity(response.upgraded_identity, SCHEMA) == {"path": "/tmp/x"}


@pytest.mark.asyncio
async def test_calls_the_hook_when_version_differs() -> None:
    resource = _resource(upgraded={"path": "/upgraded"})

    with patch(f"{MODULE}.hub.get_component", return_value=resource):
        response = await UpgradeResourceIdentityHandler(_request(version=1), context=None)

    resource.upgrade_identity.assert_awaited_once_with(1, {"path": "/tmp/x"})
    assert unmarshal_identity(response.upgraded_identity, SCHEMA) == {"path": "/upgraded"}


@pytest.mark.asyncio
async def test_errors_for_unknown_resource_type() -> None:
    with patch(f"{MODULE}.hub.get_component", return_value=None):
        response = await UpgradeResourceIdentityHandler(_request(version=2), context=None)

    assert len(response.diagnostics) == 1
    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR


@pytest.mark.asyncio
async def test_errors_when_resource_declares_no_identity() -> None:
    with patch(f"{MODULE}.hub.get_component", return_value=_resource(schema=None)):
        response = await UpgradeResourceIdentityHandler(_request(version=2), context=None)

    assert len(response.diagnostics) == 1
    assert response.diagnostics[0].severity == pb.Diagnostic.ERROR
    assert "identity" in response.diagnostics[0].summary.lower()


# 🐍🏗️🔚
