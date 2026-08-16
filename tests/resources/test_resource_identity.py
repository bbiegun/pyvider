#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for resource identity declaration and value derivation."""

from typing import Any

from attrs import define
import pytest

from pyvider.cty import CtyDynamic, CtyValue
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_str, s_identity, s_resource


@define(frozen=True)
class DemoState:
    path: str | None = None
    region: str | None = None
    size: int | None = None


class _DemoBase(BaseResource[Any, DemoState, Any]):
    state_class = DemoState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource({"path": a_str(required=True)})

    async def _validate_config(self, config: Any) -> list[str]:
        return []

    async def read(self, ctx: ResourceContext) -> DemoState | None:
        return None

    async def _delete_apply(self, ctx: ResourceContext) -> None:
        return None


class NoIdentityResource(_DemoBase):
    pass


class IdentityResource(_DemoBase):
    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return s_identity(attributes={"path": a_str(required=True), "region": a_str(optional=True)})


class OverriddenIdentityResource(IdentityResource):
    @classmethod
    def get_identity(cls, state: Any) -> dict[str, Any] | None:
        return {"path": "computed", "region": "elsewhere"}


def test_identity_is_opt_in() -> None:
    assert NoIdentityResource.get_identity_schema() is None


def test_no_identity_schema_derives_no_values() -> None:
    assert NoIdentityResource.get_identity(DemoState(path="/tmp", region="us")) is None


def test_derives_values_from_state_by_attribute_name() -> None:
    state = DemoState(path="/tmp/x", region="us-east-1", size=10)

    assert IdentityResource.get_identity(state) == {"path": "/tmp/x", "region": "us-east-1"}


def test_derivation_ignores_state_fields_outside_the_identity_schema() -> None:
    identity = IdentityResource.get_identity(DemoState(path="/tmp/x", region="us", size=99))

    assert "size" not in identity


def test_derives_none_from_none_state() -> None:
    assert IdentityResource.get_identity(None) is None


def test_derives_none_when_an_attribute_is_missing() -> None:
    assert IdentityResource.get_identity(DemoState(path="/tmp/x")) is None


def test_derives_none_when_an_attribute_is_unknown() -> None:
    """During plan an identity attribute may not be knowable yet."""
    state = DemoState(path="/tmp/x", region=CtyValue.unknown(CtyDynamic()))

    assert IdentityResource.get_identity(state) is None


def test_override_replaces_derivation() -> None:
    identity = OverriddenIdentityResource.get_identity(DemoState(path="/tmp/x", region="us"))

    assert identity == {"path": "computed", "region": "elsewhere"}


@pytest.mark.asyncio
async def test_upgrade_identity_passes_through_by_default() -> None:
    raw = {"path": "/tmp/x", "region": "us"}

    assert await IdentityResource.upgrade_identity(1, raw) == raw


def test_resource_context_carries_identity() -> None:
    ctx = ResourceContext(identity={"path": "/tmp/x"})

    assert ctx.identity == {"path": "/tmp/x"}


def test_resource_context_identity_defaults_to_none() -> None:
    assert ResourceContext().identity is None


# 🐍🏗️🔚
