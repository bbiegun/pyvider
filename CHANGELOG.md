# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`requires_replace` no longer looks effective on a write-only attribute while doing nothing.** Terraform requires write-only values to be null in both prior and planned state, so the plan comparison always saw `null == null` and an attribute declared `write_only=True, requires_replace=True` never once produced a replacement path -- a silent no-op on exactly the attributes (secrets, credentials) whose rotation most needs one. The combination is now rejected at schema-definition time with a `ValueError` pointing at the alternatives, matching Terraform's own SDK, which errors with `WriteOnly cannot be set with ForceNew`. To rotate a write-only secret, pair it with a companion attribute the practitioner bumps -- conventionally `<name>_wo_version` -- and set `requires_replace=True` on that, or call `ctx.require_replace()` from the plan hook.
- **`requires_replace` no longer looks effective inside a nested block or an object-typed attribute.** Replacement is decided from a flat list of attribute paths, and an attribute inside a block has no stable path until Terraform matches the block's elements between prior and planned state, so the flag was read by nothing and the practitioner got an in-place update the remote API could not honour -- discovered at apply time. `PvsNestedBlock` and `PvsAttribute` now reject it at schema-definition time, naming the offending path and pointing at `ctx.require_replace()`, which runs where the changed element is known.
- **`PvsAttribute.default` is applied to configuration and to plans.** The plugin protocol schema has no default-value field, so Terraform sends an omitted optional attribute as null and never learns what the provider considers the default; the provider has to resolve it. It did not: the cty-to-attrs conversion passed `None` explicitly, overriding the attrs field default the config class declared, and `_merge_config_into_plan()` skipped nulls without consulting the schema. `a_str(default="small")` was inert, and a resource that fell back to its own default at apply time returned a value Terraform had not planned. A null attribute now leaves the keyword out so attrs applies its default, and the plan carries the schema default. Unknown values are untouched: unknown is a value not yet known, not an absent one.
- **The default reaches `ctx.config`, not just the plan.** Resolving it while planning is not enough: `ctx.config` is what a resource's own apply hook reads, and it reported an omitted attribute as None unless the config class happened to declare the same default itself. A resource that read the value there returned a state the plan did not contain, which pyvider rejects as `ResourceLifecycleContractError` ("the final state ... is not a valid refinement of the planned state") and Terraform as a provider-produced inconsistency. Every inbound *configuration* -- resource, data source, ephemeral resource, provider, list resource, action and state store alike -- is now decoded with `unmarshal(..., apply_defaults=True)`, which resolves declared defaults into the cty value itself, nested blocks included. State is decoded without it: a null in state is a recorded absence, not an omission.
- **Defaults inside nested blocks reach the plan.** Defaults were resolved recursively into the configuration but corrected on the plan only at the top level, so a block that already existed in prior state kept the prior value for an attribute the practitioner had since removed: Terraform's proposed new state carries it forward, and the whole configured block was skipped because the key was already present. `ctx.config` reported the default while the plan showed the stale value, and apply failed the refinement check. Every nesting mode is now merged (`b_single`, `b_group`, `b_list`, `b_map`, and `b_set` where the block is unambiguous), at any depth, and only for attributes that declare a default.
- **A computed-only attribute may no longer declare a default.** `a_str(computed=True, default="x")` was accepted and resolved `"x"` into a configuration the practitioner can never write, which the plan then treated as configured and let beat prior state -- so every plan showed a spurious diff back to `"x"`, discarding the value computed on the previous run. A default is the value used when the practitioner omits something they *could* have written, so the combination is a contradiction and `PvsAttribute` now rejects it with a message pointing at the two coherent alternatives: add `optional=True` if the value is settable, or set the fallback in the resource's own create/read logic. Nothing in-tree declared it; `default=` was inert before this change, so no working configuration relied on it.

### Added

- **Resources can force replacement instead of an in-place update.** `PlanResourceChange` never populated `requires_replace`, so an attribute the remote API cannot change (a region, an availability zone, an immutable name) was planned as an update, and the provider's `_update_apply()` was asked to perform something it could not do. Two ways to say so: `requires_replace=True` on a schema attribute -- the equivalent of the SDK's `ForceNew` and the plugin framework's `RequiresReplace()` -- which compares the planned value against prior state, and `ctx.require_replace(path)` for replacement that depends on the values themselves rather than on the mere fact of a change. Neither reports anything on create or destroy, where Terraform rejects replacement paths, and a planned value that is still unknown counts as a change because the plan has to be decided before the value resolves.

### Changed

- **An attribute with a `default` is now Optional *and* Computed.** Terraform rejects a provider-supplied value on an attribute that is not computed -- `planned value cty.StringVal("small") for a non-computed attribute` -- so a default was unusable without it, and Optional + Computed is how the protocol spells "the practitioner may set this, and the provider fills it in otherwise". Required and write-only attributes are untouched, since neither can be computed, and a computed-only attribute is rejected outright (see above).
- **Removing a defaulted attribute from configuration plans a change back to the default**, rather than retaining the value in state as bare Optional + Computed does. This matches terraform-plugin-framework with a `Default` declared, and by the same mechanism: Terraform Core builds the proposed new state before the provider sees it and, for Optional + Computed, falls back to prior state when the configuration is null -- that is where retention comes from. The framework then applies `Default` keyed on *configuration* nullness rather than plan nullness, overwriting the value Core just carried forward. Pyvider resolves the default into the configuration for the same reason: the effective configuration is what the resource reads at apply time, so a plan that kept a stale value while `ctx.config` reported the default would fail apply's refinement check. Prior-state preservation remains opt-in, exactly as `UseStateForUnknown` is in the framework.
- **`BaseResource.from_cty()` and `cty_to_attrs_instance()` take `apply_defaults`.** It decides what a null attribute means, and the answer differs by what is being decoded: in a configuration a null is an omission, so the target class's own field default applies; in state a null is a recorded absence that must survive the round trip. The flag defaults to False, and every inbound configuration passes True -- matching `unmarshal(..., apply_defaults=True)` one layer below, which resolves the *schema* default. The class default and the schema default are deliberately separate: the schema default is resolved into the cty value before it ever reaches the attrs layer.


## [0.5.3] - 2026-08-22

### Fixed

- **An absent state no longer panics Terraform.** `ReadStateBytes` sent no `range` on the empty-state path. `Range` is a message field, so unset is a nil `*StateRange` on the other side, and `grpc_provider.go:1610` dereferences it with no nil check. The result is not a diagnostic but a crashed process, on `terraform init` against a workspace that has no state yet -- which is the first thing anyone does.
- **`range.end` is the index of the last byte, not one past it.** Core writes `End: totalBytesProcessed + len(chunk) - 1` and decides which chunk is the last with `Range.End < TotalLength-1`, so an exclusive end moved that boundary by a byte and misclassified the second-to-last chunk whenever the payload ended exactly one byte past a chunk boundary.
- **Chunk sizes follow Core's.** It proposes `chunks.DefaultStateStoreChunkSize` (8 MB) and refuses to negotiate above `chunks.MaxStateStoreChunkSize` (128 MB). This defaulted to 32 KB and had no ceiling, so an oversized proposal was echoed back and became this provider's configuration failure rather than the client's.

### Changed

- **`pyvider-rpcplugin>=0.4.2`**, which raises the gRPC server's message limits from the 4 MB default to Terraform's 256 MB. A state store negotiates 8 MB chunks, so on anything older every chunk of a multi-chunk write is refused before it arrives.

Verified against Terraform built from source with the pluggable-state-storage experiment enabled: `init`, `apply`, `plan` and `destroy` all succeed with state served entirely by the provider, and an 18 MB state reads back in three chunks with no size warnings from Core.



## [0.5.2] - 2026-08-21

### Fixed
- **A list resource's identity schema is published under its own type name.**
  `GetResourceIdentitySchemas` iterated managed resources only, so a list
  resource -- for which identity is mandatory, since it is how Terraform ties a
  listed instance back to a managed one -- was absent from the map.

## [0.5.1] - 2026-08-21

### Fixed
- **A provider-defined function is no longer handed a half-known argument.**
  `call_function` guarded with `is_unknown`, which is top-level only: a list
  whose *elements* are unknown is itself known, so the guard never fired,
  `cty_to_native` rendered those elements as `None`, and the function ran on a
  partially known argument. At plan time
  `provider::x::join("\n", [resource.a.token, ...])` raised `TypeError` from
  inside `str.join` and Terraform reported "Invalid function argument" for a
  configuration that is valid. Both the required and variadic paths now test
  `is_wholly_known()` and defer the call instead.
- **`BaseEphemeralResource.validate` is annotated `ConfigType | None`.** The
  handler passes whatever `cty_to_attrs_instance` returns, which is `None` when
  the configuration is not wholly known -- an attribute referencing a
  not-yet-created resource, for instance. Every other component type already
  declared this; ephemeral resources did not, so an implementation written
  against the annotation raised `AttributeError` at plan time.

## [0.5.0] - 2026-08-20

### Added
- **Terraform plugin protocol 6.11.** Ninety-seven commits:
  - **State stores** -- a provider can serve Terraform's state backend, with
    locking that survives a crashed process on non-POSIX hosts.
  - **List resources** and **actions**, the two new 6.11 component types,
    discovered into a caller's registry.
  - **Deferred responses** in resource handlers, so a provider can answer "not
    yet" rather than guessing.
  - **Resource identity** carried across the import boundary.
  - **Server and client capability advertisement** in `GetProviderSchema`,
    including `provider_meta`.

### Fixed
- `StopProvider` is answered before the server stops.
- An unknown data source is reported as a diagnostic rather than a crash.
- The proposed new state may carry unknown values.
- `WriteStateBytes` accepts a multi-chunk stream.
- A create is no longer executed as a destroy.
- A crashed process no longer wedges state on non-POSIX hosts.

### Changed
- Requires **pyvider-cty >= 0.5.0**, which carries 61 breaking changes. Read its
  changelog before upgrading: arithmetic width, set ordering on the wire, mark
  propagation, `regex` argument order, and stricter `csvdecode`/`jsondecode` all
  moved.
- `[tool.uv.sources]` is gone from the manifest; sibling checkouts are installed
  with `uv pip install -e ../<repo>` for local development instead, so the
  published metadata describes what a real install resolves.

## [0.4.0] - 2026-04-24

Released without a changelog entry at the time; recorded here for continuity.
See the [GitHub release](https://github.com/provide-io/pyvider/releases/tag/v0.4.0).

## [0.3.33] - 2026-04-13

### Fixed
- **Ephemeral resources now surface to Terraform.** `GetMetadata` and
  `GetProviderSchema` handlers populate the `ephemeral_resources` and
  `ephemeral_resource_schemas` protobuf fields. Previously ephemerals
  were registered with the hub but invisible to Terraform, causing
  `ephemeral "<type>" "<name>" {}` blocks to fail with "Invalid
  ephemeral resource" regardless of registration.
- **Broad-exception swallowing in `apply_resource_change`.** Unexpected
  exceptions are now wrapped in `ResourceError` with `__cause__`
  preserved, `handler_errors` metric now bumps on the error path, and
  the catch-all produces a diagnostic that names the origin exception
  type instead of an opaque "unexpected error".
- **Race in `StreamStdio`.** Replaced the hand-rolled `_stream_active`
  boolean with `asyncio.Event`; removed the nested-generator layer and
  stale debugging comment. Stream lifetime is now signaled through a
  single source of truth that callers can `await`.
- **`BaseProvider.capabilities` no longer shared across instances.**
  Previously declared as `ClassVar[dict]`, which meant every provider
  instance in a process saw the same capability registrations.
  `capabilities` is now a per-instance attrs field populated inside
  `setup()` and published atomically. `setup()` is idempotent and
  guarded by an `asyncio.Lock` + `_setup_done` flag.
- **Bare `RuntimeError` in `apply_resource_change`.** Replaced with
  `FrameworkConfigurationError` carrying enriched context
  (`resource.type_name`, `terraform.summary`, `terraform.detail`) so
  the framework's diagnostic enrichment path applies.
- **Non-attrs classes silently round-tripped to empty objects.**
  `cty_to_attrs_instance` now rejects non-attrs classes up front with
  a `FrameworkConfigurationError` that names the offending class and
  suggests decorating with `@attrs.define` / `@attrs.frozen`.

### Changed
- **Refactor: all 20 tfprotov6 RPC handlers share an `@rpc_handler`
  decorator** (`src/pyvider/protocols/tfprotov6/handlers/_metrics.py`).
  Replaces ~12 lines of per-handler boilerplate that wrapped metric
  collection and `@resilient()` — a single-file change for any future
  cross-cutting concern at the handler boundary.
- `pyvider.hub.DISCOVERY_READY_EVENT` is now the canonical key for the
  discovery-ready singleton. Three files previously hardcoded the
  magic string; a typo at any one of them used to turn into a silent
  55-second startup hang. Now it's an ImportError at module load.
- Protocol timeouts in `protocols/service.py` lifted out of magic
  numbers into named module-level constants:
  `STREAM_STARTUP_TIMEOUT_SECONDS`,
  `STREAM_HEARTBEAT_INTERVAL_SECONDS`, `SHUTDOWN_DRAIN_SECONDS`.
  `StreamStdio`'s inbound iterator is now typed as
  `AsyncIterator[Any]` rather than plain `Any`.
- `BaseResource` and `BaseDataSource` class docstrings now document
  the attrs-class requirement for `config_class` / `state_class` /
  `private_state_class`.
- Test-mode access-check log promoted from debug to info so successful
  test-only access events are visible in audit logs.
- `common/launch_context.py` uses `Path.cwd()` instead of
  `os.getcwd()` (PTH109).
- Drop Python 3.14 classifier from `pyproject.toml`; `requires-python`
  remains `>=3.11` and CI targets 3.11.
- Copyright range extended through 2026 across SPDX headers, LICENSE,
  and site footer.

### Docs
- Replace stale `foundry.provide.io/pyvider/` URLs with
  `pyvider.com/docs/` in `README.md`, `docs/index.md`, `docs/faq.md`,
  `pyproject.toml`, and `mkdocs.yml`.
- Remove "Made with ❤️" footers and the
  "🛠️ with 💚 and 🦝 on 🌎" emoji flourish from project metadata.
- Add full ephemeral resource showcase (`DemoSessionToken`) to the
  demo provider in `examples/demo-provider/`.

### Added
- `tests/regression/test_high_severity_fixes.py`: 10 regression tests
  locking in the behavior of every fix above, including two new tests
  that cover the attrs-class validator.

### Infrastructure
- Full CI suite (ruff format, ruff check, mypy strict, pytest): 1,407
  passed / 3 skipped / 2 xfailed.

## [0.3.32] - 2026-04-11

### Added
- Initial development release of pyvider
- Python Terraform Provider Framework core functionality
- Integration with pyvider-cty for type system
- Integration with pyvider-rpcplugin for gRPC protocol
