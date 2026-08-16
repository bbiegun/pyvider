#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the GetResourceIdentitySchemas handler."""

from provide.testkit.mocking import MagicMock, patch
import pytest

from pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas import (
    GetResourceIdentitySchemasHandler,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import a_str, s_identity

MODULE = "pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas"


def _resource_with_identity() -> MagicMock:
    cls = MagicMock()
    cls.get_identity_schema.return_value = s_identity(attributes={"path": a_str(required=True)})
    return cls


def _resource_without_identity() -> MagicMock:
    cls = MagicMock()
    cls.get_identity_schema.return_value = None
    return cls


@pytest.mark.asyncio
async def test_includes_only_resources_declaring_identity() -> None:
    components = {
        "demo_with": _resource_with_identity(),
        "demo_without": _resource_without_identity(),
    }

    with patch(f"{MODULE}.get_all_components", return_value=components):
        response = await GetResourceIdentitySchemasHandler(
            pb.GetResourceIdentitySchemas.Request(), context=None
        )

    assert set(response.identity_schemas) == {"demo_with"}
    assert not response.diagnostics


@pytest.mark.asyncio
async def test_converts_the_identity_schema() -> None:
    with patch(f"{MODULE}.get_all_components", return_value={"demo": _resource_with_identity()}):
        response = await GetResourceIdentitySchemasHandler(
            pb.GetResourceIdentitySchemas.Request(), context=None
        )

    schema = response.identity_schemas["demo"]
    assert schema.version == 1
    assert [a.name for a in schema.identity_attributes] == ["path"]
    assert schema.identity_attributes[0].required_for_import is True


@pytest.mark.asyncio
async def test_returns_empty_map_when_no_resource_declares_identity() -> None:
    with patch(f"{MODULE}.get_all_components", return_value={"demo": _resource_without_identity()}):
        response = await GetResourceIdentitySchemasHandler(
            pb.GetResourceIdentitySchemas.Request(), context=None
        )

    assert len(response.identity_schemas) == 0
    assert not response.diagnostics


@pytest.mark.asyncio
async def test_conversion_failure_degrades_to_a_warning() -> None:
    """Matches how _collect_schemas already degrades: warn and omit."""
    broken = MagicMock()
    broken.get_identity_schema.side_effect = ValueError("bad identity schema")

    with patch(f"{MODULE}.get_all_components", return_value={"broken": broken}):
        response = await GetResourceIdentitySchemasHandler(
            pb.GetResourceIdentitySchemas.Request(), context=None
        )

    assert len(response.identity_schemas) == 0
    assert len(response.diagnostics) == 1
    assert response.diagnostics[0].severity == pb.Diagnostic.WARNING
    assert "broken" in response.diagnostics[0].summary


# 🐍🏗️🔚
