#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for identity handling in the ReadResource handler."""

from typing import Any

from attrs import define
from provide.testkit.mocking import MagicMock, patch
import pytest

from pyvider.conversion import marshal, marshal_identity, unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.read_resource import _read_resource_impl
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_str, s_identity, s_resource

MODULE = "pyvider.protocols.tfprotov6.handlers.read_resource"
IDENTITY_SCHEMA = s_identity(attributes={"path": a_str(required=True)})


@define(frozen=True)
class DemoState:
    path: str | None = None


class _Base(BaseResource[Any, DemoState, Any]):
    state_class = DemoState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource({"path": a_str(required=True)})

    async def _validate_config(self, config: Any) -> list[str]:
        return []

    async def read(self, ctx: ResourceContext) -> DemoState | None:
        type(self).seen_identity = ctx.identity
        return DemoState(path="/tmp/x")

    async def _delete_apply(self, ctx: ResourceContext) -> None:
        return None


class NoIdentityResource(_Base):
    seen_identity: Any = None


class IdentityResource(_Base):
    seen_identity: Any = None

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA


def _request(current_identity: pb.ResourceIdentityData | None = None) -> pb.ReadResource.Request:
    state = marshal({"path": "/tmp/x"}, schema=_Base.get_schema().block)
    request = pb.ReadResource.Request(type_name="demo", current_state=state)
    if current_identity is not None:
        request.current_identity.CopyFrom(current_identity)
    return request


def _patched(resource_class):
    provider = MagicMock()
    provider.metadata.capabilities = {}
    return patch(
        f"{MODULE}.hub.get_component",
        side_effect=lambda kind, name: resource_class if kind == "resource" else provider,
    )


@pytest.mark.asyncio
async def test_omits_identity_when_resource_declares_none() -> None:
    with _patched(NoIdentityResource):
        response = await _read_resource_impl(_request(), context=None)

    assert not response.diagnostics
    assert not response.HasField("new_identity")


@pytest.mark.asyncio
async def test_emits_derived_identity_when_declared() -> None:
    with _patched(IdentityResource):
        response = await _read_resource_impl(_request(), context=None)

    assert not response.diagnostics
    assert unmarshal_identity(response.new_identity, IDENTITY_SCHEMA) == {"path": "/tmp/x"}


@pytest.mark.asyncio
async def test_inbound_identity_reaches_the_resource_context() -> None:
    inbound = marshal_identity({"path": "/prior"}, IDENTITY_SCHEMA)

    with _patched(IdentityResource):
        await _read_resource_impl(_request(current_identity=inbound), context=None)

    assert IdentityResource.seen_identity == {"path": "/prior"}


# 🐍🏗️🔚
