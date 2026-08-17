# Suite Dependency Refresh — Design

**Date:** 2026-08-16
**Status:** Approved for planning
**Sequel:** [Resource Identity E2E](2026-08-16-resource-identity-e2e-design.md) depends on this landing first.

## Goal

Bring every core pyvider-suite package to current dependencies, remove every
hard high version pin, keep each package's test suite green, and align versions
so the suite can be co-released.

## Why now

Two independent forces converged:

1. The resource-identity work raised pyvider's floors to `grpcio>=1.83.0` and
   `protobuf>=7.35.1`. `pyvider-components` runs grpcio 1.80.0 / protobuf
   6.33.6, so it **cannot import** pyvider's regenerated stubs at all — they
   raise at module load. No end-to-end validation of identity is possible until
   this is fixed.
2. `pyvider-cty` 0.5.0 carries roughly 25 breaking changes. `pyvider` still
   declares `pyvider-cty>=0.4.0`, a floor that is now actively wrong:
   pyvider 0.4.0 paired with cty 0.5.0 fails, because pyvider 0.4.0's
   `conversion/marshaler.py` has no unmark handling.

## Scope

**In scope — 10 repositories:**

`provide-foundation`, `provide-testkit`, `pyvider-cty`, `pyvider-rpcplugin`,
`pyvider-hcl`, `pyvider`, `plating`, `pyvider-components`, `tofusoup`,
`terraform-provider-pyvider`.

**Out of scope, flagged deliberately:** `flavorpack` is the one remaining
repository in the wider suite holding capped pins — `setuptools==82.0.1` and
`wheel==0.46.3`, in both `[project.dependencies]` and the `build-backends`
dependency group. Their comment ties them to
`_ensure_no_isolation_build_backend`, meaning flavorpack performs
no-isolation builds where the runtime setuptools must match the build backend.
That is a different problem with a different failure mode and deserves its own
investigation. Also out of scope: `wrknv`, `supsrc`, `ci-tooling`,
`provide-workspace`, `provide-uterm`, `provide-foundry`,
`terraform-provider-tofusoup`.

## Global Constraints

- **Floor-only version constraints.** No `<`, no `<=`, no `==`, no `~=` on any
  dependency in an in-scope repository. Express requirements as `>=` floors.
- **One documented exception path:** `cryptography>=46.0.0,<=46.0.3` in
  `terraform-provider-pyvider` applies only to `sys_platform == 'win32' and
  platform_machine == 'ARM64'` and cannot be verified on darwin or linux. The
  cap is removed; if the Windows-ARM CI job then fails, the cap is restored
  with a comment recording the observed failure. Evidence, not prediction.
- **No dependency may be upgraded without running the dependent's test suite.**
- Python floor stays `>=3.11` across the suite.
- Every repository keeps its own `uv.lock`; locks are regenerated, not
  hand-edited.

## Release order

Runtime-only dependencies (dev/test groups excluded, which is what breaks the
`provide-foundation` ↔ `provide-testkit` cycle) form a clean 6-wave DAG:

```
wave 1   provide-foundation
wave 2   provide-testkit | pyvider-cty | pyvider-rpcplugin
wave 3   pyvider
wave 4   plating | pyvider-hcl
wave 5   pyvider-components | tofusoup
wave 6   terraform-provider-pyvider
```

Full runtime edges:

| Package | Depends on (in-suite, runtime) |
|---|---|
| provide-foundation | — |
| provide-testkit | provide-foundation |
| pyvider-cty | provide-foundation |
| pyvider-rpcplugin | provide-foundation |
| pyvider | provide-foundation, pyvider-cty, pyvider-rpcplugin |
| pyvider-hcl | provide-foundation, pyvider, pyvider-cty |
| plating | provide-foundation, pyvider, pyvider-cty |
| pyvider-components | plating, provide-foundation, pyvider, pyvider-cty, pyvider-rpcplugin |
| tofusoup | plating, provide-foundation, pyvider |
| terraform-provider-pyvider | provide-foundation, pyvider, pyvider-components |

**Waves are barriers.** Everything in wave *N* must be green before wave *N+1*
begins. Downstream failures are usually upstream breakage arriving late, and
processing out of order makes them impossible to attribute.

## Per-repository procedure

For each repository, in wave order:

1. `uv lock --upgrade` — move every transitive dependency to its newest
   compatible release.
2. `uv sync --all-groups`.
3. Run the repository's full gate: tests, `ruff check`, `ruff format --check`,
   `mypy`, plus any repo-specific checks.
4. Fix fallout **in the consumer**. A breaking change upstream is repaired by
   updating the code that consumes it, never by capping the dependency.
5. Rewrite the in-suite floors this repository declares to the versions being
   released (see *Version alignment*).
6. Commit as one change per repository, with the upgrade and its fallout fixes
   together so the commit is revertible as a unit.

## Cap removals

### `grpcio-tools==1.83.0` — pyvider, `dev` group

This is the only cap whose removal requires a code change rather than an edit
to `pyproject.toml`.

`scripts/regen_protobuf.py --check` byte-compares freshly generated stubs
against the committed ones. The generated output embeds the generating
toolchain's version in three places:

| File | Line | Content |
|---|---|---|
| `tfplugin6_pb2.py` | 10 | `# Protobuf Python Version: 7.35.1` |
| `tfplugin6_pb2.py` | 19–21 | `7,` `35,` `1,` — args to `ValidateProtobufRuntimeVersion` |
| `tfplugin6_pb2_grpc.py` | 13 | `GRPC_GENERATED_VERSION = '1.83.0'` |

Any `grpcio-tools` movement changes those bytes, so `--check` reports the
stubs as out of date over pure banner churn. The pin exists to prevent that.

Those embedded versions are not noise, though — they **are** the floors
`pyproject.toml` declares, and they are enforced at import: `tfplugin6_pb2.py`
calls `ValidateProtobufRuntimeVersion`, and `tfplugin6_pb2_grpc.py` raises a
`RuntimeError` below `GRPC_GENERATED_VERSION`. Simply masking them would
discard a real signal.

**Design — `--check` gains two independent comparisons:**

1. **Proto drift.** Compare generated against committed with the version tokens
   above masked out. This answers "do the stubs match the vendored proto?" and
   is immune to toolchain churn.
2. **Floor drift.** Extract the embedded protobuf triple and grpc version from
   the freshly generated output and compare them against the floors declared in
   `pyproject.toml` (`protobuf>=` and `grpcio>=`). A mismatch fails with its own
   message naming both values, e.g. *"stubs generated with grpcio-tools 1.84.0
   declare GRPC_GENERATED_VERSION 1.84.0, but pyproject declares grpcio>=1.83.0
   — raise the floor together with the stubs."*

The result is strictly better than the pin: toolchain upgrades no longer produce
false failures, and a toolchain upgrade that genuinely moves a floor is caught
as a distinct, actionable error instead of being silently frozen out.

With that in place, `grpcio-tools` becomes a floor: `grpcio-tools>=1.83.0`.

### `jq>=1.9.1,<1.11.0` — pyvider-components, terraform-provider-pyvider

Platform-conditional (`sys_platform != 'win32' or platform_machine != 'ARM64'`).
The cap carries no comment explaining it. Remove it, resolve against current
`jq`, and run each repository's suite. If `jq` usage breaks, fix the call sites.

### `cryptography>=46.0.0,<=46.0.3` — terraform-provider-pyvider

Applies only to `sys_platform == 'win32' and platform_machine == 'ARM64'`,
almost certainly a wheel-availability workaround. Cannot be reproduced on the
development platform. Remove the cap and let the Windows-ARM CI job decide; if
it fails, restore the cap with a comment recording the specific failure.

## Version alignment

Current state: every core package is at `0.4.x` except `pyvider-cty`, whose
local `VERSION` reads `0.5.0` but which has not been published or pushed.
`pyvider`'s `VERSION` still reads `0.4.0` despite carrying the resource-identity
feature and a protocol bump from tfprotov6 6.9 to 6.11.

**Decision:** the in-scope suite moves to `0.5.0` together, and in-suite floors
are rewritten to `>=0.5.0` — floor-only, no upper bound, per the global
constraint. Publication follows the wave order, so a package is never released
against an unpublished floor.

This satisfies the release gate the cty work recorded: pyvider must be released
at or before pyvider-cty, because `pyvider-cty>=0.5.0` is only satisfiable
alongside a pyvider that has the unmark handling.

## Cross-repository source resolution

No repository currently declares `[tool.uv.workspace]` or `[tool.uv.sources]`;
each resolves from PyPI independently. That is why validating an unreleased
cross-repo pairing has required improvised `PYTHONPATH` overlays, and why
"all consumers pass" reports have historically been made against published
versions rather than the code under test — a false signal.

**Design:** each in-scope repository declares `[tool.uv.sources]` path entries
for the in-suite packages it depends on, pointing at the sibling checkout.

- uv honours `tool.uv.sources` only for the project being developed; it is not
  propagated into published metadata, so consumers of a released wheel are
  unaffected. This is publish-safe.
- CI, and any resolution that must reflect real published artifacts, passes
  `--no-sources`.

This makes "test against the tree, not the last release" the default local
behaviour rather than something each session has to reinvent.

## Error handling and failure modes

| Failure | Response |
|---|---|
| Upgrade breaks a consumer's tests | Fix the consumer. Never cap the dependency. |
| A dependency's new major genuinely has no viable migration | Stop, record the specific incompatibility, and raise it as a decision rather than silently capping. |
| Windows-ARM CI fails after the cryptography cap is dropped | Restore the cap with a comment naming the observed failure. |
| `regen_protobuf.py --check` reports floor drift | Raise `grpcio`/`protobuf` floors in `pyproject.toml` together with the regenerated stubs, in one commit. |
| A wave-*N* repo cannot go green | Do not start wave *N+1*. Late-arriving upstream breakage is unattributable. |

## Testing strategy

- Every repository's existing full gate is the acceptance criterion; no new
  test framework is introduced.
- After the final wave, the whole suite is re-resolved with `--no-sources` and
  re-tested, confirming the declared floors are actually satisfiable from
  published artifacts and that the path sources were not masking a missing floor.
- `regen_protobuf.py --check`'s two new comparisons each get unit tests: one
  proving proto drift is still detected when version tokens differ, one proving
  floor drift is detected and named.

## Definition of done

- Zero `<`, `<=`, `==`, `~=` constraints across the 10 in-scope repositories,
  except a restored cryptography cap if and only if Windows CI demanded it.
- Every in-scope repository green on its full gate.
- All 10 at version `0.5.0` with in-suite floors reading `>=0.5.0`.
- `regen_protobuf.py --check` passes without a pinned `grpcio-tools`.
- Suite re-verified once with `--no-sources`.
