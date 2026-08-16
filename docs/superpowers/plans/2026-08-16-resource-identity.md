# Resource Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Terraform resource identity protocol in pyvider — the two dedicated RPCs plus the identity fields on `ReadResource`, `PlanResourceChange`, and `ApplyResourceChange`.

**Architecture:** Identity reuses the existing `PvsSchema` / `PvsAttribute` types rather than introducing parallel ones; a single `s_identity()` factory builds the schema, and `required`/`optional` map onto the wire's `required_for_import`/`optional_for_import` exactly as Terraform core itself does. Identity is opt-in per resource via a `get_identity_schema()` classmethod, and identity *values* are derived from state by attribute name so an existing resource gains identity by adding one method.

**Tech Stack:** Python 3.11+, attrs, pyvider-cty, grpcio, protobuf (tfplugin6 6.11), pytest + pytest-asyncio, provide-testkit.

**Spec:** `docs/superpowers/specs/2026-08-16-resource-identity-design.md`

## Global Constraints

- Protocol is tfplugin6 **6.11**. Generated stubs are committed; never hand-edit `*_pb2*`. Regenerate with `python scripts/regen_protobuf.py`.
- Identity schema versions **start at 1 and increment**. Terraform compares identity versions only for equality, so the starting number is a provider-internal convention. Task 1 repairs `PvsSchema.version`'s validator to enforce this — see that task for why the repair is in scope.
- Identity attributes must be **flat scalars** — `CtyString`, `CtyNumber`, `CtyBool` only. No nested blocks, no collections.
- Identity attributes must not set `computed` or `sensitive`. `PvsObjectType.to_cty_type()` folds `computed` into the optional set, which would silently alter the identity object type.
- `ImportResourceState` is **out of scope** — it is a stub today. This plan adds the inbound plumbing (`ResourceContext.identity`) that import will later consume, but does not implement import.
- Resources that declare **no** identity schema must produce byte-identical responses to today. The existing suite passing unchanged is the regression gate.
- Run the full gate before declaring done: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`.
- Test files are capped at **500 lines**. Split rather than exceed.
- Commits: no `Co-Authored-By` trailer, no mention of AI assistance. Signing is configured (SSH); never bypass it.

---

### Task 1: `s_identity()` schema factory (and the version validator it depends on)

**Files:**
- Modify: `src/pyvider/schema/types/schema.py:29` (repair the `version` validator)
- Modify: `src/pyvider/schema/factory.py` (add after `s_provider`, ~line 171)
- Modify: `src/pyvider/schema/__init__.py` (import + `__all__`)
- Test: `tests/schema/test_identity_factory.py`

**Interfaces:**
- Consumes: existing `_create_schema(version, attributes, block_types)` and `PvsAttribute`.
- Produces: `s_identity(attributes: dict[str, PvsAttribute] | None = None, version: int = 1) -> PvsSchema`, exported from `pyvider.schema`.

**Why the validator repair is in scope:** `PvsSchema.version` currently reads
`field(validator=lambda i, a, v: v > 0)`. That lambda *returns* a bool, and attrs
discards validator return values — failure is signalled by raising. So the
validator has never enforced anything; `PvsSchema(version=0)` constructs fine.
`s_identity` is the **first** factory to accept a `version` argument at all — every
existing `s_*` hardcodes `_create_schema(1, ...)` and exposes no parameter — so this
task is the first code that can reach a bad version, and it depends on the check
working. Verified before scoping this in: no code in pyvider, pyvider-components,
tofusoup, terraform-provider-pyvider, or plating constructs `PvsSchema` directly, and
no caller anywhere passes a custom version. Repairing the validator therefore changes
no existing behaviour.

- [ ] **Step 1: Write the failing test**

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the s_identity schema factory."""

import pytest

from pyvider.cty import CtyString
from pyvider.schema import PvsSchema, a_str, s_identity
from pyvider.schema.exceptions import PvsSchemaDefinitionError
from pyvider.schema.types import PvsObjectType


def test_s_identity_builds_a_pvs_schema() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)})

    assert isinstance(schema, PvsSchema)
    assert schema.version == 1
    assert set(schema.block.attributes) == {"path"}
    assert isinstance(schema.block.attributes["path"].type, CtyString)


def test_s_identity_names_attributes_from_the_dict_key() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)})

    assert schema.block.attributes["path"].name == "path"


def test_s_identity_carries_an_explicit_version() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)}, version=3)

    assert schema.version == 3


def test_s_identity_has_no_nested_blocks() -> None:
    schema = s_identity(attributes={"path": a_str(required=True)})

    assert schema.block.block_types == ()


def test_s_identity_rejects_version_below_one() -> None:
    """Identity versions start at 1."""
    with pytest.raises(PvsSchemaDefinitionError, match="version"):
        s_identity(attributes={"path": a_str(required=True)}, version=0)


def test_s_identity_rejects_negative_version() -> None:
    with pytest.raises(PvsSchemaDefinitionError, match="version"):
        s_identity(attributes={"path": a_str(required=True)}, version=-1)


def test_pvs_schema_version_validator_actually_raises() -> None:
    """Regression: the validator used to return a bool, which attrs discards.

    s_identity is the first factory to accept a version argument, so it is the
    first code that can reach a bad value.
    """
    with pytest.raises(PvsSchemaDefinitionError, match="version"):
        PvsSchema(version=0, block=PvsObjectType(attributes={}))


def test_pvs_schema_accepts_version_one() -> None:
    assert PvsSchema(version=1, block=PvsObjectType(attributes={})).version == 1


def test_unflagged_identity_attribute_defaults_to_optional() -> None:
    """Inherited from PvsAttribute.__attrs_post_init__ -- optional_for_import."""
    schema = s_identity(attributes={"region": a_str()})

    assert schema.block.attributes["region"].optional is True
    assert schema.block.attributes["region"].required is False


def test_required_wins_when_both_flags_set() -> None:
    """Also inherited: required and optional together resolves to required."""
    schema = s_identity(attributes={"path": a_str(required=True, optional=True)})

    assert schema.block.attributes["path"].required is True
    assert schema.block.attributes["path"].optional is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/schema/test_identity_factory.py -v`
Expected: FAIL — `ImportError: cannot import name 's_identity' from 'pyvider.schema'`

- [ ] **Step 3a: Repair the version validator**

In `src/pyvider/schema/types/schema.py`, add the import and a real validator, then use it. The current line 29 is `version: int = field(validator=lambda i, a, v: v > 0)`.

```python
from pyvider.schema.exceptions import PvsSchemaDefinitionError


def _validate_version(instance: object, attribute: object, value: int) -> None:
    """Reject schema versions below 1.

    Replaces a lambda that returned a bool. attrs signals validation failure by
    raising and discards return values, so the original enforced nothing.
    """
    if value < 1:
        raise PvsSchemaDefinitionError(
            f"Schema version must be 1 or greater, got {value}."
        )
```

Then change the field to:

```python
    version: int = field(validator=_validate_version)
```

`pyvider/schema/exceptions.py` imports nothing, so this introduces no import cycle.

- [ ] **Step 3b: Write the factory**

In `src/pyvider/schema/factory.py`, after `s_provider`:

```python
def s_identity(
    attributes: dict[str, PvsAttribute] | None = None,
    version: int = 1,
) -> PvsSchema:
    """Create a resource identity schema.

    Identity reuses PvsSchema and PvsAttribute rather than parallel types.
    `required` on an attribute becomes `required_for_import` on the wire and
    `optional` becomes `optional_for_import` -- the same collapse Terraform
    core performs in ProtoToIdentitySchema.

    Identity versions start at 1 and increment by 1 on each change; the floor is
    enforced by PvsSchema.version.

    Identity attributes must be flat scalars and must not set computed or
    sensitive; both are enforced in pvs_identity_schema_to_proto.
    """
    return _create_schema(version, attributes=attributes)
```

No import change is needed in `factory.py` — the version check lives on `PvsSchema`.

In `src/pyvider/schema/__init__.py`, add `s_identity` to the `from pyvider.schema.factory import (...)` block and to `__all__`, keeping both alphabetically sorted (`s_function`, `s_identity`, `s_provider`, `s_resource`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/schema/test_identity_factory.py -v`
Expected: PASS — 10 passed

- [ ] **Step 5: Verify the validator repair broke nothing**

Run: `uv run pytest -q`
Expected: PASS, with no drop in the pre-existing count. Every existing `s_*` factory hardcodes version 1, so the now-live validator has nothing to reject. If any existing test fails here, report it as a concern rather than weakening the validator — it means something really was constructing an invalid schema.

- [ ] **Step 6: Commit**

```bash
git add src/pyvider/schema/types/schema.py src/pyvider/schema/factory.py src/pyvider/schema/__init__.py tests/schema/test_identity_factory.py
git commit -m "feat(schema): add s_identity factory and repair the version validator"
```

---

### Task 2: Identity schema → proto conversion

**Files:**
- Modify: `src/pyvider/conversion/schema_adapter.py`
- Modify: `src/pyvider/conversion/__init__.py`
- Test: `tests/conversion/test_identity_schema_adapter.py`

**Interfaces:**
- Consumes: `s_identity` (Task 1); existing `_encode_cty_type_bytes(cty_type) -> bytes`.
- Produces: `pvs_identity_schema_to_proto(schema: PvsSchema) -> pb.ResourceIdentitySchema`, exported from `pyvider.conversion`. Raises `PvsSchemaDefinitionError` on invalid identity shapes.

- [ ] **Step 1: Write the failing test**

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for identity schema to protobuf conversion."""

import pytest

from pyvider.conversion import pvs_identity_schema_to_proto
from pyvider.schema import PvsSchema, a_list, a_str, b_list, s_identity
from pyvider.schema.exceptions import PvsSchemaDefinitionError
from pyvider.schema.types import PvsAttribute, PvsObjectType


def test_maps_required_to_required_for_import() -> None:
    proto = pvs_identity_schema_to_proto(s_identity(attributes={"path": a_str(required=True)}))

    assert len(proto.identity_attributes) == 1
    attr = proto.identity_attributes[0]
    assert attr.name == "path"
    assert attr.required_for_import is True
    assert attr.optional_for_import is False


def test_maps_optional_to_optional_for_import() -> None:
    proto = pvs_identity_schema_to_proto(s_identity(attributes={"region": a_str(optional=True)}))

    attr = proto.identity_attributes[0]
    assert attr.required_for_import is False
    assert attr.optional_for_import is True


def test_carries_version_and_description() -> None:
    schema = s_identity(
        attributes={"path": a_str("The absolute path.", required=True)},
        version=2,
    )
    proto = pvs_identity_schema_to_proto(schema)

    assert proto.version == 2
    assert proto.identity_attributes[0].description == "The absolute path."


def test_encodes_attribute_type_as_wire_json() -> None:
    proto = pvs_identity_schema_to_proto(s_identity(attributes={"path": a_str(required=True)}))

    assert proto.identity_attributes[0].type == b'"string"'


def test_rejects_nested_blocks() -> None:
    schema = PvsSchema(
        version=1,
        block=PvsObjectType(
            attributes={"path": a_str(required=True)},
            block_types=(b_list("nested"),),
        ),
    )

    with pytest.raises(PvsSchemaDefinitionError, match="nested blocks"):
        pvs_identity_schema_to_proto(schema)


def test_rejects_non_scalar_attribute_type() -> None:
    schema = s_identity(attributes={"tags": a_list(a_str(), required=True)})

    with pytest.raises(PvsSchemaDefinitionError, match="scalar"):
        pvs_identity_schema_to_proto(schema)


def test_rejects_computed_attribute() -> None:
    """computed would be folded into to_cty_type()'s optional set."""
    schema = s_identity(attributes={"path": a_str(computed=True)})

    with pytest.raises(PvsSchemaDefinitionError, match="computed"):
        pvs_identity_schema_to_proto(schema)


def test_rejects_sensitive_attribute() -> None:
    schema = s_identity(attributes={"path": a_str(required=True, sensitive=True)})

    with pytest.raises(PvsSchemaDefinitionError, match="sensitive"):
        pvs_identity_schema_to_proto(schema)


def test_preserves_attribute_order() -> None:
    schema = s_identity(
        attributes={
            "region": a_str(required=True),
            "name": a_str(required=True),
        }
    )
    proto = pvs_identity_schema_to_proto(schema)

    assert [a.name for a in proto.identity_attributes] == ["region", "name"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/conversion/test_identity_schema_adapter.py -v`
Expected: FAIL — `ImportError: cannot import name 'pvs_identity_schema_to_proto'`

- [ ] **Step 3: Write minimal implementation**

In `src/pyvider/conversion/schema_adapter.py`, add the import `from pyvider.cty import CtyBool, CtyNumber, CtyString` alongside the existing `CtyType` import, add `from pyvider.schema.exceptions import PvsSchemaDefinitionError`, then append:

```python
# Identity is compared by equality and must be "wholly representative of all
# data necessary to compare two managed resource instances", so only flat
# scalars are valid.
_IDENTITY_SCALAR_TYPES = (CtyString, CtyNumber, CtyBool)


def pvs_identity_schema_to_proto(schema: PvsSchema) -> pb.ResourceIdentitySchema:
    """Convert an identity PvsSchema into a protobuf ResourceIdentitySchema.

    Identity reuses PvsSchema, so this is the single place the identity-specific
    constraints are enforced. `required` maps to `required_for_import` and
    `optional` to `optional_for_import`, matching the collapse Terraform core
    performs in ProtoToIdentitySchema.
    """
    block = schema.block

    if block.block_types:
        raise PvsSchemaDefinitionError(
            "Identity schemas cannot declare nested blocks. Identity must be a "
            "flat set of scalar attributes."
        )

    attributes = []
    for name, attr in block.attributes.items():
        if not isinstance(attr.type, _IDENTITY_SCALAR_TYPES):
            raise PvsSchemaDefinitionError(
                f"Identity attribute '{name}' has type {type(attr.type).__name__}; "
                "identity attributes must be scalar (string, number, or bool)."
            )
        if attr.computed:
            raise PvsSchemaDefinitionError(
                f"Identity attribute '{name}' is marked computed, which is not "
                "meaningful for identity and would alter the identity object type."
            )
        if attr.sensitive:
            raise PvsSchemaDefinitionError(
                f"Identity attribute '{name}' is marked sensitive, which is not "
                "meaningful for identity."
            )

        attributes.append(
            pb.ResourceIdentitySchema.IdentityAttribute(
                name=name,
                type=_encode_cty_type_bytes(attr.type),
                required_for_import=attr.required,
                optional_for_import=attr.optional,
                description=attr.description,
            )
        )

    return pb.ResourceIdentitySchema(version=schema.version, identity_attributes=attributes)
```

In `src/pyvider/conversion/__init__.py`, add `pvs_identity_schema_to_proto` to the `schema_adapter` import and to `__all__` (alphabetically, before `pvs_schema_to_proto`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/conversion/test_identity_schema_adapter.py -v`
Expected: PASS — 9 passed

If `test_encodes_attribute_type_as_wire_json` fails on the exact bytes, print the actual value and update the assertion to match `_encode_cty_type_bytes(CtyString())` — the wire encoding is owned by pyvider-cty, not by this task.

- [ ] **Step 5: Commit**

```bash
git add src/pyvider/conversion/schema_adapter.py src/pyvider/conversion/__init__.py tests/conversion/test_identity_schema_adapter.py
git commit -m "feat(conversion): convert identity schemas to protobuf"
```

---

### Task 3: Identity value codec

**Files:**
- Create: `src/pyvider/conversion/identity.py`
- Modify: `src/pyvider/conversion/__init__.py`
- Test: `tests/conversion/test_identity_codec.py`

**Interfaces:**
- Consumes: existing `marshal(value, *, schema)` / `unmarshal(dv, *, schema)`; `cty_to_native`.
- Produces:
  - `marshal_identity(values: dict[str, Any], schema: PvsSchema) -> pb.ResourceIdentityData`
  - `unmarshal_identity(data: pb.ResourceIdentityData | None, schema: PvsSchema) -> dict[str, Any] | None`

- [ ] **Step 1: Write the failing test**

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the identity value codec."""

from pyvider.conversion import marshal_identity, unmarshal_identity
from pyvider.schema import a_num, a_str, s_identity
import pyvider.protocols.tfprotov6.protobuf as pb

SCHEMA = s_identity(attributes={"region": a_str(required=True), "port": a_num(required=True)})


def test_round_trips_identity_values() -> None:
    data = marshal_identity({"region": "us-east-1", "port": 443}, SCHEMA)

    assert isinstance(data, pb.ResourceIdentityData)
    assert data.identity_data.msgpack

    assert unmarshal_identity(data, SCHEMA) == {"region": "us-east-1", "port": 443}


def test_unmarshal_returns_none_for_none_input() -> None:
    assert unmarshal_identity(None, SCHEMA) is None


def test_unmarshal_returns_none_for_empty_message() -> None:
    """Terraform sends no identity when it has none to send."""
    assert unmarshal_identity(pb.ResourceIdentityData(), SCHEMA) is None


def test_unmarshal_returns_none_for_null_identity() -> None:
    null_data = pb.ResourceIdentityData(identity_data=pb.DynamicValue(msgpack=b"\xc0"))

    assert unmarshal_identity(null_data, SCHEMA) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/conversion/test_identity_codec.py -v`
Expected: FAIL — `ImportError: cannot import name 'marshal_identity'`

- [ ] **Step 3: Write minimal implementation**

Create `src/pyvider/conversion/identity.py`:

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Codec for resource identity values.

Identity data travels over the same msgpack path as state and config, against
the object type implied by the identity schema's attributes.
"""

from typing import Any

from pyvider.conversion.adapter import cty_to_native
from pyvider.conversion.marshaler import marshal, unmarshal
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import PvsSchema


def marshal_identity(values: dict[str, Any], schema: PvsSchema) -> pb.ResourceIdentityData:
    """Encode identity values against the identity schema."""
    return pb.ResourceIdentityData(identity_data=marshal(values, schema=schema.block))


def unmarshal_identity(
    data: pb.ResourceIdentityData | None, schema: PvsSchema
) -> dict[str, Any] | None:
    """Decode inbound identity values.

    Returns None for absent, empty, or null identity so callers do not have to
    distinguish "no identity sent" from "empty identity".
    """
    if data is None or not data.identity_data.msgpack:
        return None

    cty_value = unmarshal(data.identity_data, schema=schema.block)
    if cty_value.is_null:
        return None

    return cty_to_native(cty_value)


# 🐍🏗️🔚
```

In `src/pyvider/conversion/__init__.py`, add `from pyvider.conversion.identity import marshal_identity, unmarshal_identity` and both names to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/conversion/test_identity_codec.py -v`
Expected: PASS — 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pyvider/conversion/identity.py src/pyvider/conversion/__init__.py tests/conversion/test_identity_codec.py
git commit -m "feat(conversion): add identity value codec"
```

---

### Task 4: Resource API — declaration, derivation, and context

**Files:**
- Modify: `src/pyvider/resources/base.py` (add classmethods near `get_schema`, ~line 61)
- Modify: `src/pyvider/resources/context.py` (add field)
- Test: `tests/resources/test_resource_identity.py`

**Interfaces:**
- Consumes: `s_identity` (Task 1).
- Produces, on `BaseResource`:
  - `get_identity_schema() -> PvsSchema | None` (classmethod, returns `None`)
  - `get_identity(state: Any) -> dict[str, Any] | None` (classmethod)
  - `upgrade_identity(version: int, raw_identity: dict[str, Any]) -> dict[str, Any]` (async classmethod)
  - `ResourceContext.identity: dict[str, Any] | None` (kw-only, defaults `None`)

- [ ] **Step 1: Write the failing test**

```python
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
        return s_identity(
            attributes={"path": a_str(required=True), "region": a_str(optional=True)}
        )


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/resources/test_resource_identity.py -v`
Expected: FAIL — `AttributeError: type object 'NoIdentityResource' has no attribute 'get_identity_schema'`

- [ ] **Step 3: Write minimal implementation**

In `src/pyvider/resources/base.py`, add `from pyvider.schema import PvsSchema` if not already imported (it is, line 25), then add directly after the abstract `get_schema` declaration:

```python
    @classmethod
    def get_identity_schema(cls) -> PvsSchema | None:
        """Opt in to resource identity.

        Returning None means this resource has no identity, which is the
        default. Terraform treats identity as optional for managed resources;
        it is only mandatory for list resources.
        """
        return None

    @classmethod
    def get_identity(cls, state: Any) -> dict[str, Any] | None:
        """Derive identity values from state by attribute name.

        Identity attributes are almost always a subset of state, so this
        default means a resource gains identity by declaring
        get_identity_schema() and nothing else. Override when identity is not
        derivable from state.

        Returns None when identity cannot be fully determined -- no schema, no
        state, or any attribute missing, null, or still unknown during plan.
        """
        schema = cls.get_identity_schema()
        if schema is None or state is None:
            return None

        values: dict[str, Any] = {}
        for name in schema.block.attributes:
            value = getattr(state, name, None)
            if value is None:
                return None
            if isinstance(value, CtyValue) and (value.is_unknown or value.is_null):
                return None
            values[name] = value

        return values

    @classmethod
    async def upgrade_identity(cls, version: int, raw_identity: dict[str, Any]) -> dict[str, Any]:
        """Upgrade identity data written under an older identity version.

        Only called when the stored version differs from the schema's current
        version. The default passes data through unchanged.
        """
        return raw_identity
```

In `src/pyvider/resources/context.py`, add to `ResourceContext` after `test_mode_enabled`:

```python
    identity: dict[str, Any] | None = field(default=None, kw_only=True)
```

Add `Any` to the `typing` import in `context.py` if absent. Keep the field **kw-only and last** so no existing positional construction shifts.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/resources/test_resource_identity.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Verify no regression in the existing suite**

Run: `uv run pytest -q`
Expected: PASS — the pre-existing tests all still pass. `BaseResource` gained only defaulted methods and `ResourceContext` a defaulted kw-only field.

- [ ] **Step 6: Commit**

```bash
git add src/pyvider/resources/base.py src/pyvider/resources/context.py tests/resources/test_resource_identity.py
git commit -m "feat(resources): add opt-in identity declaration and derivation"
```

---

### Task 5: `GetResourceIdentitySchemas` handler

**Files:**
- Create: `src/pyvider/protocols/tfprotov6/handlers/get_resource_identity_schemas.py`
- Modify: `src/pyvider/protocols/tfprotov6/handlers/__init__.py`
- Modify: `src/pyvider/handler.py`
- Test: `tests/tfprotov6/handlers/test_get_resource_identity_schemas.py`

**Interfaces:**
- Consumes: `pvs_identity_schema_to_proto` (Task 2); `get_identity_schema()` (Task 4); existing `get_all_components(component_type)`.
- Produces: `GetResourceIdentitySchemasHandler(request, context) -> pb.GetResourceIdentitySchemas.Response`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tfprotov6/handlers/test_get_resource_identity_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...get_resource_identity_schemas'`

- [ ] **Step 3: Write minimal implementation**

Create `src/pyvider/protocols/tfprotov6/handlers/get_resource_identity_schemas.py`:

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


from typing import Any

from provide.foundation import logger

from pyvider.conversion import pvs_identity_schema_to_proto
from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
from pyvider.protocols.tfprotov6.handlers.utils import get_all_components
import pyvider.protocols.tfprotov6.protobuf as pb


@rpc_handler("GetResourceIdentitySchemas")
async def GetResourceIdentitySchemasHandler(
    request: pb.GetResourceIdentitySchemas.Request, context: Any
) -> pb.GetResourceIdentitySchemas.Response:
    """Handle the GetResourceIdentitySchemas RPC."""
    return await _get_resource_identity_schemas_impl(request, context)


async def _get_resource_identity_schemas_impl(
    request: pb.GetResourceIdentitySchemas.Request, context: Any
) -> pb.GetResourceIdentitySchemas.Response:
    """Collect identity schemas for every resource that declares one.

    Identity is opt-in: a resource whose get_identity_schema() returns None is
    simply absent from the map, which is what Terraform expects.
    """
    identity_schemas: dict[str, pb.ResourceIdentitySchema] = {}
    diagnostics: list[pb.Diagnostic] = []

    for name, resource_class in get_all_components("resource").items():
        try:
            schema = resource_class.get_identity_schema()
            if schema is None:
                continue
            identity_schemas[name] = pvs_identity_schema_to_proto(schema)
        except Exception as e:
            logger.warning(
                "Identity schema collection failed for resource",
                operation="get_resource_identity_schemas",
                resource_type=name,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            diagnostics.append(
                pb.Diagnostic(
                    severity=pb.Diagnostic.WARNING,
                    summary=f"Identity schema collection error for resource '{name}'",
                    detail=str(e),
                )
            )

    logger.debug(
        "Collected resource identity schemas",
        operation="get_resource_identity_schemas",
        identity_count=len(identity_schemas),
        warning_count=len(diagnostics),
    )

    return pb.GetResourceIdentitySchemas.Response(
        identity_schemas=identity_schemas, diagnostics=diagnostics
    )


# 🐍🏗️🔚
```

In `handlers/__init__.py`, add the import and the `__all__` entry (alphabetical — after `GetProviderSchemaHandler`).

In `src/pyvider/handler.py`: add `GetResourceIdentitySchemasHandler` to the `__attrs_post_init__` import block, add `"GetResourceIdentitySchemas": GetResourceIdentitySchemasHandler,` to `self._handlers`, and add the servicer method after `GetProviderSchema`:

```python
    async def GetResourceIdentitySchemas(self, request: Any, context: Any) -> Any:
        return await self._delegate("GetResourceIdentitySchemas", request, context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tfprotov6/handlers/test_get_resource_identity_schemas.py -v`
Expected: PASS — 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pyvider/protocols/tfprotov6/handlers/get_resource_identity_schemas.py src/pyvider/protocols/tfprotov6/handlers/__init__.py src/pyvider/handler.py tests/tfprotov6/handlers/test_get_resource_identity_schemas.py
git commit -m "feat(tfprotov6): implement GetResourceIdentitySchemas"
```

---

### Task 6: `UpgradeResourceIdentity` handler

**Files:**
- Create: `src/pyvider/protocols/tfprotov6/handlers/upgrade_resource_identity.py`
- Modify: `src/pyvider/protocols/tfprotov6/handlers/__init__.py`
- Modify: `src/pyvider/handler.py`
- Test: `tests/tfprotov6/handlers/test_upgrade_resource_identity.py`

**Interfaces:**
- Consumes: `upgrade_identity()` and `get_identity_schema()` (Task 4); `marshal_identity` (Task 3).
- Produces: `UpgradeResourceIdentityHandler(request, context) -> pb.UpgradeResourceIdentity.Response`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tfprotov6/handlers/test_upgrade_resource_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...upgrade_resource_identity'`

- [ ] **Step 3: Write minimal implementation**

Create `src/pyvider/protocols/tfprotov6/handlers/upgrade_resource_identity.py`:

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


import json
from typing import Any

from provide.foundation import logger

from pyvider.conversion import marshal_identity
from pyvider.hub import hub
from pyvider.protocols.tfprotov6.handlers._metrics import rpc_handler
from pyvider.protocols.tfprotov6.handlers.utils import create_diagnostic_from_exception
import pyvider.protocols.tfprotov6.protobuf as pb


@rpc_handler("UpgradeResourceIdentity")
async def UpgradeResourceIdentityHandler(
    request: pb.UpgradeResourceIdentity.Request, context: Any
) -> pb.UpgradeResourceIdentity.Response:
    """Handle the UpgradeResourceIdentity RPC."""
    return await _upgrade_resource_identity_impl(request, context)


async def _upgrade_resource_identity_impl(
    request: pb.UpgradeResourceIdentity.Request, context: Any
) -> pb.UpgradeResourceIdentity.Response:
    """Upgrade stored identity data to the resource's current identity version.

    raw_identity is JSON-encoded per the proto. When the stored version already
    matches, the data passes through untouched -- the same shape as the
    existing UpgradeResourceState passthrough.
    """
    response = pb.UpgradeResourceIdentity.Response()

    try:
        resource_class = hub.get_component("resource", request.type_name)
        if not resource_class:
            return pb.UpgradeResourceIdentity.Response(
                diagnostics=[
                    pb.Diagnostic(
                        severity=pb.Diagnostic.ERROR,
                        summary=f"Unknown resource type '{request.type_name}'",
                        detail=(
                            f"Resource type '{request.type_name}' is not registered.\n\n"
                            "Suggestion: Ensure the resource is registered using the "
                            "@register_resource decorator and that component discovery "
                            "has completed successfully."
                        ),
                    )
                ]
            )

        schema = resource_class.get_identity_schema()
        if schema is None:
            return pb.UpgradeResourceIdentity.Response(
                diagnostics=[
                    pb.Diagnostic(
                        severity=pb.Diagnostic.ERROR,
                        summary=f"Resource '{request.type_name}' declares no identity schema",
                        detail=(
                            "Terraform asked to upgrade identity data for a resource that "
                            "does not declare an identity schema. This is a bug in the "
                            "provider: implement get_identity_schema() on the resource."
                        ),
                    )
                ]
            )

        raw_identity = json.loads(request.raw_identity.json) if request.raw_identity.json else {}

        if request.version == schema.version:
            logger.debug(
                "Identity version matches, passing through",
                operation="upgrade_resource_identity",
                resource_type=request.type_name,
                version=request.version,
            )
            upgraded = raw_identity
        else:
            logger.info(
                "Upgrading resource identity",
                operation="upgrade_resource_identity",
                resource_type=request.type_name,
                from_version=request.version,
                to_version=schema.version,
            )
            upgraded = await resource_class.upgrade_identity(request.version, raw_identity)

        response.upgraded_identity.CopyFrom(marshal_identity(upgraded, schema))

    except Exception as e:
        logger.error(
            "UpgradeResourceIdentity failed",
            operation="upgrade_resource_identity",
            resource_type=request.type_name,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        response.diagnostics.append(await create_diagnostic_from_exception(e))

    return response


# 🐍🏗️🔚
```

Wire into `handlers/__init__.py` (import + `__all__`, alphabetical after `UpgradeResourceStateHandler`) and `src/pyvider/handler.py` (import, `_handlers` entry, and a servicer method after `UpgradeResourceState`):

```python
    async def UpgradeResourceIdentity(self, request: Any, context: Any) -> Any:
        return await self._delegate("UpgradeResourceIdentity", request, context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tfprotov6/handlers/test_upgrade_resource_identity.py -v`
Expected: PASS — 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pyvider/protocols/tfprotov6/handlers/upgrade_resource_identity.py src/pyvider/protocols/tfprotov6/handlers/__init__.py src/pyvider/handler.py tests/tfprotov6/handlers/test_upgrade_resource_identity.py
git commit -m "feat(tfprotov6): implement UpgradeResourceIdentity"
```

---

### Task 7: Thread identity through `ReadResource`

**Files:**
- Modify: `src/pyvider/protocols/tfprotov6/handlers/read_resource.py`
- Test: `tests/tfprotov6/handlers/test_read_resource_identity.py`

**Interfaces:**
- Consumes: `marshal_identity` / `unmarshal_identity` (Task 3); `get_identity_schema` / `get_identity` (Task 4); `ResourceContext.identity` (Task 4).
- Produces: a shared helper other handlers reuse —
  `apply_identity_to_response(resource_class, state, response_field) -> None` is **not** introduced; each handler sets its own field inline, since the response field names differ (`new_identity` vs `planned_identity`).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tfprotov6/handlers/test_read_resource_identity.py -v`
Expected: FAIL — `test_emits_derived_identity_when_declared` fails because `response.new_identity` is empty, and `test_inbound_identity_reaches_the_resource_context` fails with `seen_identity is None`.

- [ ] **Step 3: Write minimal implementation**

In `src/pyvider/protocols/tfprotov6/handlers/read_resource.py`, add to the conversion import:

```python
from pyvider.conversion import marshal, marshal_identity, unmarshal, unmarshal_identity
```

Resolve the identity schema once, just after `resource_schema = resource_class.get_schema()`:

```python
        identity_schema = resource_class.get_identity_schema()
```

Pass inbound identity into the context by adding this keyword to the existing `ResourceContext(...)` construction:

```python
            identity=(
                unmarshal_identity(request.current_identity, identity_schema)
                if identity_schema is not None
                else None
            ),
```

Emit derived identity inside the `if new_state_attrs is not None:` branch, immediately after `response.new_state.msgpack = marshalled_new_state.msgpack`:

```python
            if identity_schema is not None:
                identity_values = resource_class.get_identity(new_state_attrs)
                if identity_values is not None:
                    response.new_identity.CopyFrom(
                        marshal_identity(identity_values, identity_schema)
                    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tfprotov6/handlers/test_read_resource_identity.py tests/tfprotov6/handlers/test_read_resource.py -v`
Expected: PASS — the three new tests plus the existing ReadResource tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/pyvider/protocols/tfprotov6/handlers/read_resource.py tests/tfprotov6/handlers/test_read_resource_identity.py
git commit -m "feat(tfprotov6): thread resource identity through ReadResource"
```

---

### Task 8: Thread identity through `PlanResourceChange`

**Files:**
- Modify: `src/pyvider/protocols/tfprotov6/handlers/plan_resource_change.py`
- Test: `tests/tfprotov6/handlers/test_plan_resource_change_identity.py`

**Interfaces:**
- Consumes: same as Task 7.
- Produces: `planned_identity` on `pb.PlanResourceChange.Response`; `prior_identity` decoded into `ResourceContext.identity`.

- [ ] **Step 1: Write the failing test**

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for identity handling in the PlanResourceChange handler."""

from pyvider.conversion import unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.plan_resource_change import _handle_planned_state_dict
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import a_str, s_identity, s_resource

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tfprotov6/handlers/test_plan_resource_change_identity.py -v`
Expected: FAIL — `TypeError: _handle_planned_state_dict() got an unexpected keyword argument 'identity_schema'`

- [ ] **Step 3: Write minimal implementation**

In `plan_resource_change.py`, extend `_handle_planned_state_dict`'s signature with two keyword-only parameters and emit at the end of the function, after `response.planned_state.msgpack` is assigned:

```python
def _handle_planned_state_dict(
    planned_state_dict: dict[str, Any],
    resource_schema: PvsSchema,
    response: pb.PlanResourceChange.Response,
    *,
    identity_schema: PvsSchema | None = None,
    identity_values: dict[str, Any] | None = None,
) -> None:
```

```python
    if identity_schema is not None and identity_values is not None:
        response.planned_identity.CopyFrom(marshal_identity(identity_values, identity_schema))
```

Add `marshal_identity, unmarshal_identity` to the module's `pyvider.conversion` import.

At the call site (`planned_state_dict` branch, ~line 272), resolve the schema and derive values from the planned state:

```python
        identity_schema = resource_class.get_identity_schema()
        if planned_state_dict:
            identity_values = (
                resource_class.get_identity(
                    cty_to_attrs_instance(
                        resource_schema.block.to_cty_type().validate(planned_state_dict),
                        resource_class.state_class,
                    )
                )
                if identity_schema is not None
                else None
            )
            _handle_planned_state_dict(
                planned_state_dict,
                resource_schema,
                response,
                identity_schema=identity_schema,
                identity_values=identity_values,
            )
```

If `cty_to_attrs_instance` is not already imported in this module, add it to the existing `handlers.utils` import block. Wrap the `identity_values` derivation in a `try/except Exception` that logs a debug message and falls back to `None` — during plan the planned state may contain unknowns that cannot be validated, and an unknowable identity is legitimately omitted rather than an error.

Pass inbound `prior_identity` into the `ResourceContext(...)` construction (~line 151) with the same keyword used in Task 7:

```python
        identity=(
            unmarshal_identity(request.prior_identity, identity_schema)
            if identity_schema is not None
            else None
        ),
```

resolving `identity_schema` before the context is built.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tfprotov6/handlers/test_plan_resource_change_identity.py tests/tfprotov6/handlers/test_plan_resource_change_basic.py tests/tfprotov6/handlers/test_plan_resource_change_implementation.py -v`
Expected: PASS — three new tests plus the existing plan tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/pyvider/protocols/tfprotov6/handlers/plan_resource_change.py tests/tfprotov6/handlers/test_plan_resource_change_identity.py
git commit -m "feat(tfprotov6): thread resource identity through PlanResourceChange"
```

---

### Task 9: Thread identity through `ApplyResourceChange`

**Files:**
- Modify: `src/pyvider/protocols/tfprotov6/handlers/apply_resource_change.py`
- Test: `tests/tfprotov6/handlers/test_apply_resource_change_identity.py`

**Interfaces:**
- Consumes: same as Task 7.
- Produces: `new_identity` on `pb.ApplyResourceChange.Response`; `planned_identity` decoded into `ResourceContext.identity`.

- [ ] **Step 1: Write the failing test**

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for identity handling in the ApplyResourceChange handler."""

from attrs import define

from pyvider.conversion import unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.apply_resource_change import _handle_apply_result
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.schema import a_str, s_identity, s_resource

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
```

The existing signature is `_handle_apply_result(new_state_attrs, new_private_state_attrs, resource_schema, planned_state_cty, response)` at `apply_resource_change.py:191`. Passing `None` for `planned_state_cty` skips the refinement check, which is not what these tests exercise.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tfprotov6/handlers/test_apply_resource_change_identity.py -v`
Expected: FAIL — `TypeError: _handle_apply_result() got an unexpected keyword argument 'identity_schema'`

- [ ] **Step 3: Write minimal implementation**

Mirror Task 8. Add two keyword-only parameters to `_handle_apply_result` (`apply_resource_change.py:191`):

```python
    *,
    identity_schema: PvsSchema | None = None,
    identity_values: dict[str, Any] | None = None,
```

and, inside the `if new_state_attrs is not None:` branch, immediately after `response.new_state.msgpack = marshalled_new_state.msgpack` (~line 224):

```python
        if identity_schema is not None and identity_values is not None:
            response.new_identity.CopyFrom(marshal_identity(identity_values, identity_schema))
```

Add `marshal_identity, unmarshal_identity` to the module's `pyvider.conversion` import, and `PvsSchema` to its `pyvider.schema` import.

At the `_handle_apply_result(...)` call site in `_apply_resource_change_impl` (~line 299), resolve the schema and derive from the post-apply state — which, unlike plan, is fully known:

```python
        identity_schema = resource_class.get_identity_schema()
        _handle_apply_result(
            new_state_attrs,
            new_private_state_attrs,
            resource_schema,
            planned_state_cty,
            response,
            identity_schema=identity_schema,
            identity_values=(
                resource_class.get_identity(new_state_attrs) if identity_schema is not None else None
            ),
        )
```

Match the existing positional arguments at that call site rather than copying the names above verbatim.

Inbound `planned_identity` is threaded in `_create_resource_context` (`apply_resource_change.py:165`), not at the impl level. Add an `identity_schema: PvsSchema | None = None` keyword-only parameter to it, pass `request.planned_identity` through as a new `planned_identity: pb.ResourceIdentityData | None = None` keyword-only parameter, and add to the `ResourceContext(...)` it returns:

```python
        identity=(
            unmarshal_identity(planned_identity, identity_schema)
            if identity_schema is not None
            else None
        ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tfprotov6/handlers/test_apply_resource_change_identity.py tests/tfprotov6/handlers/test_apply_resource_change_core.py tests/tfprotov6/handlers/test_apply_resource_change_advanced.py -v`
Expected: PASS — two new tests plus the existing apply tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/pyvider/protocols/tfprotov6/handlers/apply_resource_change.py tests/tfprotov6/handlers/test_apply_resource_change_identity.py
git commit -m "feat(tfprotov6): thread resource identity through ApplyResourceChange"
```

---

### Task 10: End-to-end identity stability

**Files:**
- Test: `tests/integration/test_resource_identity_lifecycle.py`

**Interfaces:**
- Consumes: everything from Tasks 1–9.
- Produces: nothing — this is the acceptance gate.

- [ ] **Step 1: Write the failing test**

```python
#
# SPDX-FileCopyrightText: Copyright (c) 2025-2026 provide.io llc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""Identity must stay stable across read, plan, and apply."""

from typing import Any

from attrs import define
from provide.testkit.mocking import MagicMock, patch
import pytest

from pyvider.conversion import marshal, unmarshal_identity
from pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas import (
    GetResourceIdentitySchemasHandler,
)
from pyvider.protocols.tfprotov6.handlers.read_resource import _read_resource_impl
import pyvider.protocols.tfprotov6.protobuf as pb
from pyvider.resources.base import BaseResource
from pyvider.resources.context import ResourceContext
from pyvider.schema import PvsSchema, a_str, s_identity, s_resource

IDENTITY_SCHEMA = s_identity(attributes={"region": a_str(required=True), "name": a_str(required=True)})


@define(frozen=True)
class WidgetState:
    region: str | None = None
    name: str | None = None
    size: int | None = None


class WidgetResource(BaseResource[Any, WidgetState, Any]):
    state_class = WidgetState

    @classmethod
    def get_schema(cls) -> PvsSchema:
        return s_resource({"region": a_str(required=True), "name": a_str(required=True)})

    @classmethod
    def get_identity_schema(cls) -> PvsSchema:
        return IDENTITY_SCHEMA

    async def _validate_config(self, config: Any) -> list[str]:
        return []

    async def read(self, ctx: ResourceContext) -> WidgetState | None:
        return WidgetState(region="us-east-1", name="widget", size=3)

    async def _delete_apply(self, ctx: ResourceContext) -> None:
        return None


@pytest.mark.asyncio
async def test_identity_schema_is_advertised() -> None:
    with patch(
        "pyvider.protocols.tfprotov6.handlers.get_resource_identity_schemas.get_all_components",
        return_value={"pyvider_widget": WidgetResource},
    ):
        response = await GetResourceIdentitySchemasHandler(
            pb.GetResourceIdentitySchemas.Request(), context=None
        )

    schema = response.identity_schemas["pyvider_widget"]
    assert [a.name for a in schema.identity_attributes] == ["region", "name"]
    assert all(a.required_for_import for a in schema.identity_attributes)


@pytest.mark.asyncio
async def test_read_emits_identity_excluding_non_identity_state() -> None:
    provider = MagicMock()
    provider.metadata.capabilities = {}
    state = marshal(
        {"region": "us-east-1", "name": "widget"}, schema=WidgetResource.get_schema().block
    )
    request = pb.ReadResource.Request(type_name="pyvider_widget", current_state=state)

    with patch(
        "pyvider.protocols.tfprotov6.handlers.read_resource.hub.get_component",
        side_effect=lambda kind, name: WidgetResource if kind == "resource" else provider,
    ):
        response = await _read_resource_impl(request, context=None)

    identity = unmarshal_identity(response.new_identity, IDENTITY_SCHEMA)
    assert identity == {"region": "us-east-1", "name": "widget"}
    assert "size" not in identity
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/integration/test_resource_identity_lifecycle.py -v`
Expected: PASS — both tests. If either fails, the defect is in Tasks 1–9, not here; fix it there.

- [ ] **Step 3: Run the full gate**

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run python scripts/regen_protobuf.py --check
```

Expected: all pass. The pre-existing test count must not drop — resources declaring no identity are unaffected.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_resource_identity_lifecycle.py
git commit -m "test(tfprotov6): cover identity stability across the resource lifecycle"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
| --- | --- |
| Schema representation (reuse `PvsSchema`/`PvsAttribute`) | 1 |
| `s_identity()` factory, no `i_*` builders | 1 |
| `pvs_identity_schema_to_proto` + flag mapping + shape rejection | 2 |
| Identity value codec | 3 |
| `get_identity_schema()` opt-in | 4 |
| `get_identity()` derivation + override | 4 |
| `upgrade_identity()` hook | 4, 6 |
| `ResourceContext.identity` | 4 |
| `GetResourceIdentitySchemas` handler | 5 |
| `UpgradeResourceIdentity` handler | 6 |
| Identity on Read / Plan / Apply | 7, 8, 9 |
| `handler.py` servicer wiring | 5, 6 |
| No change to `GetProviderSchema` | — (deliberately absent) |
| Error handling conventions | 5, 6 (diagnostics), 7–9 (omission is not an error) |
| Regression: no-identity resources unchanged | 4 step 5, 7–9 step 4, 10 step 3 |
| `ImportResourceState` out of scope | — (deliberately absent) |

**Type consistency:** `get_identity_schema() -> PvsSchema | None`, `get_identity(state) -> dict[str, Any] | None`, `marshal_identity(values, schema) -> pb.ResourceIdentityData`, `unmarshal_identity(data, schema) -> dict[str, Any] | None`, and `pvs_identity_schema_to_proto(schema) -> pb.ResourceIdentitySchema` are used with identical names and signatures in every task that references them. Handlers 7–9 each set their own response field inline rather than sharing a helper, because the field names differ (`new_identity` vs `planned_identity`).

**Verified against the current tree:** `_handle_planned_state_dict(planned_state_dict, resource_schema, response)` exists at `plan_resource_change.py:160`; `_handle_apply_result(new_state_attrs, new_private_state_attrs, resource_schema, planned_state_cty, response)` at `apply_resource_change.py:191`; `_create_resource_context(...)` at `apply_resource_change.py:165`. `HasField` works on all three identity response fields (they are message fields), and `_encode_cty_type_bytes(CtyString())` is `b'"string"'`, so Task 2's assertion is exact.

**Known imprecision:** Tasks 8 and 9 give call-site line numbers (`~line 272`, `~line 299`). Read the surrounding function before editing rather than trusting the offset — no preceding task modifies these files, but the offsets are approximate by nature.
