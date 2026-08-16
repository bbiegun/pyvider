#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for identity handling in the ApplyResourceChange handler."""

from typing import Any

from attrs import define
from provide.testkit.mocking import MagicMock, patch
import pytest

from pyvider.conversion import marshal, marshal_identity, unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.apply_resource_change import (
    _apply_resource_change_impl,
    _handle_apply_result,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_str, s_identity, s_resource

MODULE = "pyvider.protocols.tfprotov6.handlers.apply_resource_change"
IDENTITY_SCHEMA = s_identity(attributes={"path": a_str(required=True)})
RESOURCE_SCHEMA = s_resource({"path": a_str(required=True)})


@define(frozen=True)
class DemoState:
    path: str | None = None


def test_omits_identity_when_schema_is_none() -> None:
    response = pb.ApplyResourceChange.Response()

    _handle_apply_result(
        DemoState(path="/tmp/x"),
        None,
        RESOURCE_SCHEMA,
        None,
        response,
        identity_schema=None,
        identity_values=None,
    )

    assert not response.HasField("new_identity")


def test_emits_identity_after_apply() -> None:
    response = pb.ApplyResourceChange.Response()

    _handle_apply_result(
        DemoState(path="/tmp/x"),
        None,
        RESOURCE_SCHEMA,
        None,
        response,
        identity_schema=IDENTITY_SCHEMA,
        identity_values={"path": "/tmp/x"},
    )

    assert unmarshal_identity(response.new_identity, IDENTITY_SCHEMA) == {"path": "/tmp/x"}


def test_omits_identity_when_schema_present_but_values_are_none() -> None:
    """A resource may declare an identity schema yet get_identity() return None. Identity
    is never marshalled partially -- None means emit nothing, since Terraform errors on an
    identity that contains unknown values."""
    response = pb.ApplyResourceChange.Response()

    _handle_apply_result(
        DemoState(path="/tmp/x"),
        None,
        RESOURCE_SCHEMA,
        None,
        response,
        identity_schema=IDENTITY_SCHEMA,
        identity_values=None,
    )

    assert not response.HasField("new_identity")


# --- Integration-level coverage through _apply_resource_change_impl ---
# The helper-level tests above prove _handle_apply_result's own contract, but not that the
# real derivation path (resource_class.get_identity_schema()/get_identity()) actually
# reaches it, nor that inbound planned_identity reaches ResourceContext.identity. These
# exercise the full handler.


@define(frozen=True)
class DemoConfig:
    path: str | None = None


class _Base(BaseResource[Any, DemoState, DemoConfig]):
    config_class = DemoConfig
    state_class = DemoState
    seen_identity: Any = None

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return RESOURCE_SCHEMA

    async def _validate_config(self, config: Any) -> list[str]:
        return []

    async def _create_apply(self, ctx: ResourceContext) -> tuple[Any, None]:
        type(self).seen_identity = ctx.identity
        return ctx.planned_state, None

    async def read(self, ctx: ResourceContext) -> DemoState | None:
        return None

    async def _delete_apply(self, ctx: ResourceContext) -> None:
        return None


class NoIdentityResource(_Base):
    seen_identity: Any = None


class IdentityResource(_Base):
    seen_identity: Any = None

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA


class IdentityResourceRaisingOnDerive(_Base):
    """A resource whose get_identity() override is buggy -- the apply itself must still
    succeed, with identity simply omitted, distinct from the state-contract-violation path."""

    seen_identity: Any = None

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA

    @classmethod
    def get_identity(cls, state: Any) -> dict[str, Any] | None:
        raise RuntimeError("boom: buggy get_identity() override")


def _request(planned_identity: pb.ResourceIdentityData | None = None) -> pb.ApplyResourceChange.Request:
    config = marshal({"path": "/tmp/x"}, schema=RESOURCE_SCHEMA.block)
    planned_state = marshal({"path": "/tmp/x"}, schema=RESOURCE_SCHEMA.block)
    request = pb.ApplyResourceChange.Request(
        type_name="demo",
        config=config,
        planned_state=planned_state,
        planned_private=b"",
    )
    if planned_identity is not None:
        request.planned_identity.CopyFrom(planned_identity)
    return request


def _patched(resource_class: Any) -> Any:
    provider = MagicMock()
    provider.metadata.capabilities = {}
    return patch(
        f"{MODULE}.hub.get_component",
        side_effect=lambda kind, name: resource_class if kind == "resource" else provider,
    )


@pytest.mark.asyncio
async def test_impl_omits_new_identity_when_resource_declares_none() -> None:
    with _patched(NoIdentityResource):
        response = await _apply_resource_change_impl(_request(), context=None)

    assert not response.diagnostics
    assert not response.HasField("new_identity")


@pytest.mark.asyncio
async def test_impl_emits_new_identity_when_derivable() -> None:
    with _patched(IdentityResource):
        response = await _apply_resource_change_impl(_request(), context=None)

    assert not response.diagnostics
    assert unmarshal_identity(response.new_identity, IDENTITY_SCHEMA) == {"path": "/tmp/x"}


@pytest.mark.asyncio
async def test_impl_inbound_planned_identity_reaches_the_resource_context() -> None:
    inbound = marshal_identity({"path": "/planned"}, IDENTITY_SCHEMA)

    with _patched(IdentityResource):
        await _apply_resource_change_impl(_request(planned_identity=inbound), context=None)

    assert IdentityResource.seen_identity == {"path": "/planned"}


@pytest.mark.asyncio
async def test_impl_omits_new_identity_when_derivation_raises() -> None:
    """A buggy get_identity() override must not fail the apply or surface as a diagnostic --
    identity is simply omitted. Unlike plan, apply runs after state is fully known, so this
    is logged loudly (WARNING) as it is a genuine defect rather than a "not yet knowable"."""
    with _patched(IdentityResourceRaisingOnDerive):
        response = await _apply_resource_change_impl(_request(), context=None)

    assert not any(d.severity == pb.Diagnostic.ERROR for d in response.diagnostics)
    assert not response.HasField("new_identity")


# 🐍🏗️🔚
