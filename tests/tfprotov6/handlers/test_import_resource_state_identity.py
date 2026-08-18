#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Resource identity across the import boundary.

`ImportResourceState.Request` carries both `id` and `identity`, and Terraform
sends whichever the practitioner wrote -- `import { id = ... }` or
`import { identity = {...} }`. So this is one operation with two input forms
rather than two operations, which is why there is no `import_by_identity` hook:
a resource implementing only one of a pair would silently return no identity
from the other.

The identity therefore arrives on `ctx.identity`, exactly as it does for read,
plan and apply, and the answer is derived from the returned state by the same
`get_identity()`. A resource gains all of it by declaring
`get_identity_schema()` and nothing else.

Import was the one lifecycle RPC with no identity wiring at all. Terraform reads
`ImportedResource.identity` and writes it to state, so a resource that declares
an identity schema and is then imported arrived in state with an empty identity
-- and every later plan saw a change it could not explain.
"""

from attrs import define
import pytest

from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers.import_resource_state import (
    ImportResourceStateHandler,
)
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.schema import PvsSchema, a_str, s_identity, s_resource


@define
class _State:
    id: str
    region: str
    name: str


class _Base(BaseResource):
    """The abstract methods stubbed, so these fixtures are instantiable.

    `BaseResource` is abstract; what is under test is the import path, so the
    rest of the lifecycle is inert.
    """

    state_class = _State
    seen_identity: object = None

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource(
            {
                "id": a_str(computed=True),
                "region": a_str(required=True),
                "name": a_str(required=True),
            }
        )

    async def _validate_config(self, config: object) -> list[str]:
        return []

    async def read(self, ctx: object) -> _State | None:
        return None

    async def _delete_apply(self, ctx: object) -> None:
        return None

    async def import_state(self, ctx, import_id: str):
        # Records what the framework handed in, so the inbound half is checkable.
        type(self).seen_identity = ctx.identity
        if ctx.identity:
            return _State(id="things/x", region=ctx.identity["region"], name=ctx.identity["name"])
        return _State(id=f"things/{import_id}", region="us-east-1", name=import_id)


class _WithIdentity(_Base):
    """Declares an identity schema and nothing else.

    No `get_identity()` override: `BaseResource`'s default derives identity from
    state by attribute name, which is the whole point -- declaring the schema is
    meant to be the only thing a resource has to do.
    """

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return s_identity({"region": a_str(required=True), "name": a_str(required=True)})


class _NoIdentity(_Base):
    """The pre-identity shape, which must keep working untouched."""


@pytest.fixture
def registered(request):
    cls = request.param
    hub.register("resource", "test_resource", cls)
    yield cls
    try:
        hub.unregister("resource", "test_resource")
    except Exception:
        pass


def _identity_request(values: dict[str, str]) -> pb.ImportResourceState.Request:
    """An `import { identity = {...} }`, where Terraform sends no id."""
    from pyvider.conversion.identity import marshal_identity

    request = pb.ImportResourceState.Request(type_name="test_resource", id="")
    request.identity.CopyFrom(marshal_identity(values, _WithIdentity.get_identity_schema()))
    return request


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [_WithIdentity], indirect=True)
async def test_the_answer_carries_identity(registered) -> None:
    """Terraform writes this to state; an empty one makes every later plan drift."""
    request = pb.ImportResourceState.Request(type_name="test_resource", id="widget")

    response = await ImportResourceStateHandler(request, context=None)

    assert not [d for d in response.diagnostics if d.severity == pb.Diagnostic.ERROR]
    imported = response.imported_resources[0]
    assert imported.HasField("identity"), "identity was not returned to Terraform"
    assert imported.identity.identity_data.msgpack


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [_WithIdentity], indirect=True)
async def test_an_identity_import_reaches_the_resource(registered) -> None:
    """`import { identity = {...} }`: the id is empty and the identity is not."""
    _WithIdentity.seen_identity = None
    request = _identity_request({"region": "eu-west-2", "name": "widget"})

    response = await ImportResourceStateHandler(request, context=None)

    assert not [d for d in response.diagnostics if d.severity == pb.Diagnostic.ERROR]
    assert _WithIdentity.seen_identity == {"region": "eu-west-2", "name": "widget"}


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [_WithIdentity], indirect=True)
async def test_an_id_import_still_works_and_gets_no_identity_in(registered) -> None:
    """The other input form. `ctx.identity` is empty rather than absent."""
    _WithIdentity.seen_identity = "unset"
    request = pb.ImportResourceState.Request(type_name="test_resource", id="widget")

    await ImportResourceStateHandler(request, context=None)

    assert not _WithIdentity.seen_identity


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [_NoIdentity], indirect=True)
async def test_a_resource_without_an_identity_schema_is_untouched(registered) -> None:
    """The default is no identity, and it must cost nothing."""
    request = pb.ImportResourceState.Request(type_name="test_resource", id="widget")

    response = await ImportResourceStateHandler(request, context=None)

    assert not [d for d in response.diagnostics if d.severity == pb.Diagnostic.ERROR]
    imported = response.imported_resources[0]
    assert imported.state.msgpack
    assert not imported.HasField("identity")


# 🐍🏗️🔚
