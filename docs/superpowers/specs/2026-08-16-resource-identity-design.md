# Resource Identity

**Date:** 2026-08-16
**Status:** Approved, not yet implemented
**Protocol:** tfplugin6 (identity shipped in 6.9; pyvider is on 6.11)

## Problem

Pyvider implements none of the Terraform resource identity protocol. Identity
is not a 6.11 addition — it shipped in 6.9, and pyvider has never supported it.
The gap covers two dedicated RPCs and identity fields on three implemented
handlers:

| RPC | Identity surface | Pyvider today |
| --- | --- | --- |
| `GetResourceIdentitySchemas` | whole RPC | unimplemented |
| `UpgradeResourceIdentity` | whole RPC | unimplemented |
| `ReadResource` | `current_identity` req, `new_identity` resp | fields ignored |
| `PlanResourceChange` | `prior_identity` req, `planned_identity` resp | fields ignored |
| `ApplyResourceChange` | `planned_identity` req, `new_identity` resp | fields ignored |

Nothing breaks today because Terraform tolerates the absence. Its client treats
a failed `GetResourceIdentitySchemas` call as an empty map, and merges identity
onto a resource schema with `id := identResp.IdentitySchemas[name] // We're fine
if the id is not found` (`internal/plugin6/grpc_provider.go:177`).

### Why now

Identity is a hard prerequisite for list resources. Terraform's list client
rejects any list type whose matching managed resource has no identity schema:

```go
resourceSchema, ok := schema.ResourceTypes[r.TypeName]
if !ok || resourceSchema.Identity == nil {
    resp.Diagnostics = resp.Diagnostics.Append(fmt.Errorf(
        "Identity schema not found for resource type %s; this is a bug in the provider - please report it there", r.TypeName))
    return resp
}
```

and errors per-event on `missing identity data in ListResource event` (both in
`GRPCProvider.ListResource`, `internal/plugin6/grpc_provider.go:1325`). List
resources are therefore phase 2 of this work, not a separate feature.

## Scope

**In scope**

- `PvsIdentitySchema` / `PvsIdentityAttribute` schema types and factories
- Opt-in `get_identity_schema()` on `BaseResource`, with value derivation
- `GetResourceIdentitySchemas` and `UpgradeResourceIdentity` handlers
- Identity threaded through `ReadResource`, `PlanResourceChange`,
  `ApplyResourceChange`

**Out of scope**

- `ImportResourceState` — a stub today that returns a "not yet implemented"
  diagnostic. Wiring identity into import means implementing import, which is
  its own feature. The inbound plumbing this design adds
  (`ResourceContext.identity`) is what import will consume when it is built.
- List resources — phase 2, on top of this.
- State stores, actions, config generation — unrelated 6.11 subsystems.

`GetProviderSchema` needs **no change**. Terraform fetches identity over the
separate RPC and merges it client-side, so the existing schema handler and its
cache are untouched.

## Design

### Schema types

New module `src/pyvider/schema/types/identity.py`:

```python
@define(frozen=True, kw_only=True)
class PvsIdentityAttribute:
    name: str = field(default="")
    type: CtyType = field()
    required_for_import: bool = field(default=False)
    optional_for_import: bool = field(default=False)
    description: str = field(default="")

@define(frozen=True, kw_only=True)
class PvsIdentitySchema:
    version: int = field(default=1, validator=lambda i, a, v: v >= 0)
    attributes: dict[str, PvsIdentityAttribute] = field(factory=dict)

    def to_cty_type(self) -> CtyObject: ...
```

These are deliberately **not** flags on `PvsAttribute`:

- Identity carries a version independent of the resource schema version, and
  `PvsSchema.version` is already taken.
- `required_for_import` / `optional_for_import` are meaningless on the other
  ~99% of attributes, and adding them would put dead fields on every attribute
  in every schema in the ecosystem.
- Terraform transmits identity schemas as a distinct message
  (`ResourceIdentitySchema`, not `Schema`) over a distinct RPC. Mirroring that
  split keeps the conversion layer a straight field-for-field mapping rather
  than a filter-and-reinterpret pass over the resource schema.

`version` validates as non-negative, not positive: the proto states identity
versioning "implicitly starts at 0". This differs from `PvsSchema.version`,
which validates `> 0`.

**Validation rule** (pyvider's choice, not enforced by Terraform core, which
only decodes): `required_for_import` and `optional_for_import` may not both be
true. Both false is legal and means the attribute is provider-supplied and
cannot be used to address the resource on import.

### Factory helpers

`src/pyvider/schema/factory.py` gains `s_identity()` plus `i_str()`, `i_num()`,
and `i_bool()`, exported from `pyvider.schema`:

```python
@classmethod
def get_identity_schema(cls) -> PvsIdentitySchema:
    return s_identity(
        version=1,
        attributes={"path": i_str(required_for_import=True)},
    )
```

Only scalar builders are provided. Identity is required to be "wholly
representative of all data necessary to compare two managed resource instances"
and is compared by equality, so nested or collection-typed identity is a design
error. Offering no `i_list` / `i_obj` enforces flatness structurally instead of
by documentation.

### Resource API

`BaseResource` gains three members, all with working defaults, matching the
existing pattern of a small required surface (`get_schema`, `read`,
`_delete_apply`) plus optional hooks (`_create`, `_update_apply`, …):

```python
@classmethod
def get_identity_schema(cls) -> PvsIdentitySchema | None:
    """Opt in to resource identity. None means this resource has none."""
    return None

@classmethod
def get_identity(cls, state: StateType | None) -> dict[str, Any] | None:
    """Derive identity values from state. Override when identity is not a
    subset of state."""

@classmethod
async def upgrade_identity(cls, version: int, raw_identity: dict[str, Any]) -> dict[str, Any]:
    """Upgrade identity data written by an older identity version."""
    return raw_identity
```

`get_identity`'s default reads each identity attribute name off the state
object. This covers the overwhelmingly common case — `path`, `arn`, `id`,
`region` + `name` are already state fields — so **an existing resource gains
identity by adding one classmethod and nothing else**. It returns `None` when
state is `None` or when any required attribute is missing or unknown, which is
what callers need during plan.

There is deliberately **no `identity_class`**. Config and state earn attrs
classes because resources manipulate them richly across the lifecycle; identity
is a small flat key the framework marshals and the resource almost never
touches. A third attrs class would be a second source of truth beside the
identity schema, free to drift from it, buying nothing. Identity values move as
`dict[str, Any]` keyed by attribute name.

`ResourceContext` gains `identity: dict[str, Any] | None = None`, carrying the
inbound identity. Derivation cannot serve this direction: on import Terraform
supplies identity and no state, and locating a resource from it is inherently
resource-specific.

### Conversion

`src/pyvider/conversion/schema_adapter.py` gains
`pvs_identity_schema_to_proto()`, reusing the existing cached
`_encode_cty_type_bytes()` for attribute types. A new
`src/pyvider/conversion/identity.py` provides the value codec:

```python
def marshal_identity(values, schema: PvsIdentitySchema) -> pb.ResourceIdentityData
def unmarshal_identity(data: pb.ResourceIdentityData, schema: PvsIdentitySchema) -> dict[str, Any] | None
```

Both delegate to the existing `marshal` / `unmarshal` against
`schema.to_cty_type()`, so identity uses the same msgpack path as everything
else. `unmarshal_identity` returns `None` for absent or null identity so
handlers do not have to distinguish "no identity sent" from "empty identity".

### Handlers

Two new handlers, following the existing `@rpc_handler` +
`Handler` / `_impl` split:

- **`get_resource_identity_schemas.py`** — iterates registered resources via the
  existing `get_all_components("resource")`, keeps those whose
  `get_identity_schema()` is not `None`, converts each. A resource that raises
  during conversion produces a warning diagnostic and is omitted, matching how
  `_collect_schemas` already degrades.
- **`upgrade_resource_identity.py`** — decodes `raw_identity` (JSON, per the
  proto), passes through unchanged when `request.version` equals the resource's
  current identity version, and otherwise calls `upgrade_identity()`. Mirrors
  the existing `UpgradeResourceState` passthrough shape.

Three modified handlers. Each reads inbound identity into `ResourceContext` and
writes derived identity onto the response, guarded on the resource declaring an
identity schema:

| Handler | Insertion point | Response field |
| --- | --- | --- |
| `read_resource.py` | after `response.new_state.msgpack` is set (~L169) | `new_identity` |
| `plan_resource_change.py` | `_handle_planned_state_dict` (~L199) | `planned_identity` |
| `apply_resource_change.py` | `_apply_new_state` (~L224) | `new_identity` |

Identity is emitted only when the derived value is complete. During plan an
identity that depends on computed values may not be knowable yet; omitting it is
valid, and Terraform decodes identity only `if protoResp.PlannedIdentity != nil`.

Wiring all three matters even though Terraform tolerates a provider that never
sends identity — partial wiring is exactly how identity drifts silently between
read and apply.

`src/pyvider/handler.py` gains `GetResourceIdentitySchemas` and
`UpgradeResourceIdentity` methods plus their `_handlers` map entries, and
`handlers/__init__.py` exports the two new handlers.

## Data flow

```
GetResourceIdentitySchemas
  hub resources → get_identity_schema() → pvs_identity_schema_to_proto → map

ReadResource
  request.current_identity → unmarshal_identity → ResourceContext.identity
  resource.read(ctx) → state → get_identity(state) → marshal_identity
                                                   → response.new_identity

PlanResourceChange / ApplyResourceChange
  same shape, against prior_identity/planned_identity and
  planned_identity/new_identity respectively
```

## Error handling

Follows the established handler convention: `PyviderError` and unexpected
exceptions are both converted via `create_diagnostic_from_exception` and
appended to `response.diagnostics`, never raised across the RPC boundary.

Identity-specific cases:

- **Resource declares identity, derivation returns `None`** — omit the identity
  field. Not an error; Terraform treats absent identity as "unchanged".
- **Identity fails to marshal** (wrong type for the declared attribute) — error
  diagnostic naming the resource type and attribute. This is a provider bug and
  should be loud.
- **Inbound identity fails to unmarshal** — error diagnostic. Indicates an
  identity version mismatch that `UpgradeResourceIdentity` should have handled.
- **Unknown resource type** in either new handler — reuses the existing
  not-registered error text from `read_resource.py`.

## Testing

TDD, per project convention. Test files stay under the 500-line cap, so this
splits across several files rather than one per subsystem.

- **Schema types** — attribute flag validation (both import flags true is an
  error), version non-negative, `to_cty_type()` shape.
- **Factories** — `s_identity` / `i_*` produce the expected types; scalar-only
  surface.
- **Conversion** — `pvs_identity_schema_to_proto` field mapping; identity value
  round-trip through `marshal_identity` / `unmarshal_identity`, including null
  and absent.
- **Derivation** — default `get_identity` against a state object; missing
  attribute, unknown value, and `None` state all yield `None`; override is
  honoured.
- **New handlers** — schema collection includes only identity-declaring
  resources; conversion failure degrades to a warning; upgrade passthrough on
  matching version and hook invocation otherwise.
- **Modified handlers** — extend the existing
  `tests/tfprotov6/handlers/test_{read,plan,apply}_*` files: identity absent
  when the resource declares none, present and correct when it does, inbound
  identity reaches `ResourceContext`.
- **Integration** — a fixture resource with an identity schema exercised across
  read → plan → apply, asserting identity is stable across the three.

Existing behaviour must not shift: resources that declare no identity schema
produce byte-identical responses to today. This is the main regression risk and
is covered by the existing 1407-test suite passing unchanged.

## Phase 2 preview

With this in place, list resources add no new identity concepts:

- `ValidateListResourceConfig` (unary) and `ListResource` (server-streaming,
  pyvider's first)
- a list schema containing Terraform's required nested block literally named
  `config` (`listResourceSchema.Body.BlockTypes["config"]`)
- per-event emission of the already-derived identity

The streaming handler is the only genuinely new machinery.
