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


class IdentityResourceReturningNone(_Base):
    """Declares an identity schema, but get_identity() cannot derive a value (e.g. the
    identity depends on data this resource doesn't have). Identity is omitted, not an error."""

    seen_identity: Any = None

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA

    @classmethod
    def get_identity(cls, state: Any) -> dict[str, Any] | None:
        return None


class IdentityResourceRaisingOnDerive(_Base):
    """A resource whose get_identity() override is buggy. The read must still succeed with
    identity omitted -- the same outcome plan and apply produce for the identical bug."""

    seen_identity: Any = None

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA

    @classmethod
    def get_identity(cls, state: Any) -> dict[str, Any] | None:
        raise RuntimeError("boom: buggy get_identity() override")


class DuckTypedResource:
    """A resource registered by marker attribute alone, with no BaseResource in sight and
    therefore no get_identity_schema(). @register_resource stamps markers and discovery
    registers on the marker, so this shape is registrable and predates identity entirely --
    it must not start dying with an AttributeError."""

    state_class = DemoState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource({"path": a_str(required=True)})

    async def read(self, ctx: ResourceContext) -> DemoState | None:
        return DemoState(path="/tmp/x")


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
async def test_omits_identity_when_derivation_returns_none() -> None:
    """A resource may declare an identity schema yet get_identity() return None. Identity is
    never marshalled partially -- None means emit nothing, and this must not be an error."""
    with _patched(IdentityResourceReturningNone):
        response = await _read_resource_impl(_request(), context=None)

    assert not any(d.severity == pb.Diagnostic.ERROR for d in response.diagnostics)
    assert not response.HasField("new_identity")


@pytest.mark.asyncio
async def test_inbound_identity_reaches_the_resource_context() -> None:
    inbound = marshal_identity({"path": "/prior"}, IDENTITY_SCHEMA)

    with _patched(IdentityResource):
        await _read_resource_impl(_request(current_identity=inbound), context=None)

    assert IdentityResource.seen_identity == {"path": "/prior"}


@pytest.mark.asyncio
async def test_omits_identity_when_derivation_raises() -> None:
    """One buggy get_identity() override must not produce three different outcomes. Apply
    and plan both swallow the exception, log a WARNING and omit; read used to have no
    try/except at all, so the same bug turned the next refresh into an "Internal Provider
    Error" after apply had already written state."""
    with _patched(IdentityResourceRaisingOnDerive):
        response = await _read_resource_impl(_request(), context=None)

    assert not any(d.severity == pb.Diagnostic.ERROR for d in response.diagnostics)
    assert not response.HasField("new_identity")
    assert response.new_state.msgpack


@pytest.mark.asyncio
async def test_duck_typed_resource_without_get_identity_schema_still_reads() -> None:
    """A registered resource that never inherited BaseResource has no
    get_identity_schema(). A missing method means the same as one returning None."""
    with _patched(DuckTypedResource):
        response = await _read_resource_impl(_request(), context=None)

    assert not response.diagnostics
    assert not response.HasField("new_identity")
    assert response.new_state.msgpack


# 🐍🏗️🔚
