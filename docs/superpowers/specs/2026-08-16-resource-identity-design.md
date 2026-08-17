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

- An `s_identity()` factory over the existing `PvsSchema` / `PvsAttribute` types
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

### Schema representation

**No new schema types.** An identity schema is a `PvsSchema`, and an identity
attribute is a `PvsAttribute`. The existing types already fit:

| Identity needs | Existing type provides |
| --- | --- |
| a version, separate from the resource schema's | `PvsSchema.version` |
| a set of named, typed attributes | `PvsObjectType.attributes` |
| `required_for_import` | `PvsAttribute.required` |
| `optional_for_import` | `PvsAttribute.optional` |
| description | `PvsAttribute.description` |
| an object type for marshalling identity data | `PvsObjectType.to_cty_type()` |

The two import flags map cleanly onto `required` / `optional` because they are
the same axis — who must supply the value — scoped to import. The proto defines
`required_for_import` as "must be defined for ImportResourceState to complete
successfully" and `optional_for_import` as "not required for
ImportResourceState, because it can be supplied by the provider".

Reuse also inherits validation instead of reimplementing it.
`PvsAttribute.__attrs_post_init__` already defaults an unflagged attribute to
`optional`, and already resolves required-and-optional in favour of required —
which is exactly the rule identity needs, and which a parallel
`PvsIdentityAttribute` would have had to restate.

The decisive point is `to_cty_type()`. Identity data marshals over the same
msgpack path as everything else, against the `CtyObject` implied by its
attributes. `PvsObjectType.to_cty_type()` already produces that. A separate
identity type would have to reimplement it.

What reuse gives up, and how each is handled:

- **`PvsSchema` can express nested blocks and collection types, which are
  invalid for identity.** Identity must be "wholly representative of all data
  necessary to compare two managed resource instances" and is compared by
  equality. Rejected at conversion time (see below) rather than made
  unrepresentable.
- **`computed`, `sensitive`, `default`, and `object_type` are meaningless on an
  identity attribute.** Rejected at conversion time alongside the shape checks.
  `computed` is the one that would otherwise do something: `to_cty_type()` folds
  it into the optional set, so a stray `computed=True` would silently alter the
  identity object type.
- **`PvsSchema.version` used to validate `> 0`, which was wrong for every
  schema, not just identity.** That floor is relaxed to `>= 0`. Terraform stores
  a resource's schema version in state as `SchemaVersion uint64`
  (`internal/states/instance_object_src.go:29`), with no floor reserving 0 as a
  sentinel, and `schema_version: 0` is a genuine persisted value throughout the
  state round-trip fixtures under `internal/states/statefile/testdata/roundtrip/`
  (e.g. `v4-modules`, `v4-simple`), alongside `schema_version: 1` in others
  (`v3-bigint.out.tfstate`, `v3-grabbag.out.tfstate`). Only negative versions
  are rejected.
- **Identity versions start at 0, and `s_identity()` defaults to 0.** The proto
  says so directly — identity "versioning implicitly starts at 0 and by
  convention should be incremented by 1 each change"
  (`docs/plugin-protocol/tfplugin6.proto`, `ResourceIdentitySchema.version`) —
  and the starting number is *not* merely a provider-internal convention.
  Terraform persists `IdentitySchemaVersion` in state
  (`internal/states/instance_object_src.go`), and it is 0 for every instance
  written before the resource declared identity. `upgradeResourceIdentity`
  returns early when the stored version equals the schema's; if the stored
  version is instead *greater* than the schema's current version, Terraform
  does not silently downgrade — it emits a hard `ERROR` diagnostic, "Resource
  instance managed by newer provider version"
  (`internal/terraform/upgrade_resource_state.go:158-170`). For every
  pre-existing instance (stored version 0, lower than the schema's), it calls
  `UpgradeResourceIdentity` with `Version: 0` and an empty `RawIdentityJSON`,
  on every state read (`internal/terraform/upgrade_resource_state.go`,
  `internal/terraform/node_resource_abstract.go`). Defaulting to 1 would fire
  that RPC with no data to upgrade for every pre-existing instance. Defaulting
  to 0 means adopting identity on a live resource is a no-op at the protocol
  level.

### Factory helpers

`src/pyvider/schema/factory.py` gains exactly one function, `s_identity()`,
exported from `pyvider.schema`. Identity attributes are built with the existing
`a_str` / `a_num` / `a_bool`:

```python
@classmethod
def get_identity_schema(cls) -> PvsSchema:
    return s_identity(
        attributes={"path": a_str(required=True)},
    )
```

`version` defaults to 0 and is normally omitted; pass it only when the identity
shape actually changes.

`required` here reads as `required_for_import`, and that is not a reinterpretation
pyvider invents — Terraform core performs the same collapse. `ProtoToIdentitySchema`
maps `RequiredForImport` onto `configschema.Attribute.Required` and
`OptionalForImport` onto `.Optional`, reusing the identical attribute struct it
uses for ordinary config attributes (`internal/plugin6/convert/schema.go:162`).
The two names exist only as wire fields; nothing downstream of decoding keeps
them apart.

No `i_*` wrapper builders. They would only move the flat-scalar constraint from
conversion time to authoring time, and conversion has to enforce it regardless
to catch hand-built `PvsAttribute`s — so the wrappers would buy error locality
on a handful of lines written once per resource, at the cost of a parallel
factory surface to keep in step with `a_*`.

### Resource API

`BaseResource` gains three members, all with working defaults, matching the
existing pattern of a small required surface (`get_schema`, `read`,
`_delete_apply`) plus optional hooks (`_create`, `_update_apply`, …):

```python
@classmethod
def get_identity_schema(cls) -> PvsSchema | None:
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
`_encode_cty_type_bytes()` for attribute types. Because identity reuses
`PvsSchema`, this is the single place the identity-specific constraints are
enforced. It raises when the schema declares `block_types`, when any attribute's
type is not a scalar (`CtyString` / `CtyNumber` / `CtyBool`), or when an
attribute sets `computed` or `sensitive`. Identity must be "wholly
representative of all data necessary to compare two managed resource instances"
and is compared by equality, so none of those shapes are valid.

The flag mapping happens here too: `required` becomes `required_for_import` and
`optional` becomes `optional_for_import`.

A new `src/pyvider/conversion/identity.py` provides the value codec:

```python
def marshal_identity(values, schema: PvsSchema) -> pb.ResourceIdentityData
def unmarshal_identity(data: pb.ResourceIdentityData, schema: PvsSchema) -> dict[str, Any] | None
```

Both delegate to the existing `marshal` / `unmarshal` against
`schema.block.to_cty_type()`, so identity uses the same msgpack path as
everything else. `unmarshal_identity` returns `None` for absent or null identity
so handlers do not have to distinguish "no identity sent" from "empty identity".

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
  the existing `UpgradeResourceState` passthrough shape. An **empty**
  `raw_identity` returns with `upgraded_identity` left unset rather than
  marshalling `{}`, which would fail on the first required attribute. Terraform
  reads a nil `UpgradedIdentity` as `cty.NullVal(ty)`
  (`internal/plugin6/grpc_provider.go:485`); that is wholly known, conforms to
  the identity type, and `CompleteIdentityUpgrade` stores it and stamps the
  current version.

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
  field. Not an error, and omission is *required* when the value is not wholly
  known, because Terraform rejects an identity containing unknowns
  (`validateIdentityKnown`, `internal/terraform/node_resource_abstract_instance.go`).

  But omission does **not** mean "unchanged". Terraform assigns identity from
  the response unconditionally — `ret.Identity = resp.Identity` after refresh,
  `Identity: resp.PlannedIdentity` on plan, and `Identity: resp.NewIdentity` on
  both apply branches (`node_resource_abstract_instance.go:810`, `:1407`,
  `:2931`, `:2949`) — so an omitted identity is written to state as nil.
  Omitting **clears** identity rather than preserving it.

  The consequence worth recording: a resource whose identity is legitimately
  `None` for some instances will have identity cleared from state on the next
  refresh. That is a known property of omission, not something this design
  fixes. It is also why identity should be derivable from state for every
  instance a resource manages, rather than only some.
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

- **Factory** — `s_identity` returns a `PvsSchema` wrapping a `PvsObjectType`,
  with the version applied; an unflagged identity attribute inherits the
  existing default of `optional`, and setting both flags resolves to required,
  both via `PvsAttribute.__attrs_post_init__` rather than new code.
- **Conversion** — `pvs_identity_schema_to_proto` maps `required` to
  `required_for_import` and `optional` to `optional_for_import`; rejects an
  identity schema carrying `block_types`, a non-scalar attribute type, or
  `computed` / `sensitive`; identity value round-trip through
  `marshal_identity` / `unmarshal_identity`, including null and absent.
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
