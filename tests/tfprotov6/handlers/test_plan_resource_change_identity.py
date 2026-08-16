#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for identity handling in the PlanResourceChange handler."""

from typing import Any

from attrs import define
from provide.testkit.mocking import MagicMock, patch
import pytest

from pyvider.conversion import marshal, marshal_identity, unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.plan_resource_change import (
    _handle_planned_state_dict,
    _plan_resource_change_impl,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_str, s_identity, s_resource

MODULE = "pyvider.protocols.tfprotov6.handlers.plan_resource_change"
IDENTITY_SCHEMA = s_identity(attributes={"path": a_str(required=True)})
RESOURCE_SCHEMA = s_resource({"path": a_str(required=True)})


def test_omits_identity_when_schema_is_none() -> None:
    response = pb.PlanResourceChange.Response()

    _handle_planned_state_dict(
        {"path": "/tmp/x"}, RESOURCE_SCHEMA, response, identity_schema=None, identity_values=None
    )

    assert not response.HasField("planned_identity")


def test_emits_identity_when_values_are_known() -> None:
    response = pb.PlanResourceChange.Response()

    _handle_planned_state_dict(
        {"path": "/tmp/x"},
        RESOURCE_SCHEMA,
        response,
        identity_schema=IDENTITY_SCHEMA,
        identity_values={"path": "/tmp/x"},
    )

    assert unmarshal_identity(response.planned_identity, IDENTITY_SCHEMA) == {"path": "/tmp/x"}


def test_omits_identity_when_values_are_not_yet_known() -> None:
    """During plan an identity attribute may still be unknown; omitting is valid."""
    response = pb.PlanResourceChange.Response()

    _handle_planned_state_dict(
        {"path": "/tmp/x"},
        RESOURCE_SCHEMA,
        response,
        identity_schema=IDENTITY_SCHEMA,
        identity_values=None,
    )

    assert not response.HasField("planned_identity")


# --- Integration-level coverage through _plan_resource_change_impl ---
# The helper-level tests above prove _handle_planned_state_dict's own contract, but not
# that the real derivation path (resource_class.get_identity_schema()/get_identity())
# actually reaches it. These exercise the full handler.


@define(frozen=True)
class DemoConfig:
    path: str | None = None


@define(frozen=True)
class DemoState:
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

    async def _create(
        self, ctx: ResourceContext, base_plan: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, None]:
        type(self).seen_identity = ctx.identity
        return base_plan, None

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


class IdentityResourceReturningNone(_Base):
    seen_identity: Any = None

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA

    @classmethod
    def get_identity(cls, state: Any) -> dict[str, Any] | None:
        return None


class IdentityResourceRaisingOnDerive(_Base):
    """A resource whose get_identity() override is buggy -- this is the actual case the
    handler's broad except guards against, distinct from the (non-raising) unknown-value case."""

    seen_identity: Any = None

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA

    @classmethod
    def get_identity(cls, state: Any) -> dict[str, Any] | None:
        raise RuntimeError("boom: buggy get_identity() override")


def _request(prior_identity: pb.ResourceIdentityData | None = None) -> pb.PlanResourceChange.Request:
    config = marshal({"path": "/tmp/x"}, schema=RESOURCE_SCHEMA.block)
    proposed_new_state = marshal({"path": "/tmp/x"}, schema=RESOURCE_SCHEMA.block)
    request = pb.PlanResourceChange.Request(
        type_name="demo",
        config=config,
        proposed_new_state=proposed_new_state,
        prior_private=b"",
    )
    if prior_identity is not None:
        request.prior_identity.CopyFrom(prior_identity)
    return request


def _patched(resource_class: Any) -> Any:
    provider = MagicMock()
    provider.metadata.capabilities = {}
    return patch(
        f"{MODULE}.hub.get_component",
        side_effect=lambda kind, name: resource_class if kind == "resource" else provider,
    )


@pytest.mark.asyncio
async def test_impl_omits_planned_identity_when_resource_declares_none() -> None:
    with _patched(NoIdentityResource):
        response = await _plan_resource_change_impl(_request(), context=None)

    assert not response.diagnostics
    assert not response.HasField("planned_identity")


@pytest.mark.asyncio
async def test_impl_emits_planned_identity_when_derivable() -> None:
    with _patched(IdentityResource):
        response = await _plan_resource_change_impl(_request(), context=None)

    assert not response.diagnostics
    assert unmarshal_identity(response.planned_identity, IDENTITY_SCHEMA) == {"path": "/tmp/x"}


@pytest.mark.asyncio
async def test_impl_omits_planned_identity_when_derivation_returns_none() -> None:
    """A resource may declare an identity schema yet be unable to derive identity during
    plan (e.g. it depends on an unknown). Terraform only decodes planned_identity when the
    field is present, so omitting it -- not erroring -- is the correct behaviour."""
    with _patched(IdentityResourceReturningNone):
        response = await _plan_resource_change_impl(_request(), context=None)

    assert not response.diagnostics
    assert not response.HasField("planned_identity")


@pytest.mark.asyncio
async def test_impl_inbound_prior_identity_reaches_the_resource_context() -> None:
    inbound = marshal_identity({"path": "/prior"}, IDENTITY_SCHEMA)

    with _patched(IdentityResource):
        await _plan_resource_change_impl(_request(prior_identity=inbound), context=None)

    assert IdentityResource.seen_identity == {"path": "/prior"}


@pytest.mark.asyncio
async def test_impl_omits_planned_identity_when_derivation_raises() -> None:
    """A buggy get_identity() override (or malformed planned-state data) must not fail the
    plan or surface as a diagnostic -- it is swallowed and identity is simply omitted, the
    same as the not-yet-knowable case, but logged loudly since this one is a real defect."""
    with _patched(IdentityResourceRaisingOnDerive):
        response = await _plan_resource_change_impl(_request(), context=None)

    assert not any(d.severity == pb.Diagnostic.ERROR for d in response.diagnostics)
    assert not response.HasField("planned_identity")


# 🐍🏗️🔚
