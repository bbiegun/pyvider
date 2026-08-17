# Resource Identity End-to-End Validation — Design

**Date:** 2026-08-16
**Status:** Approved for planning
**Prerequisite:** [Suite Dependency Refresh](2026-08-16-suite-dependency-refresh-design.md) must land first.
**Implements validation for:** [Resource Identity](2026-08-16-resource-identity-design.md)

## Goal

Prove that pyvider's resource-identity implementation works against a real
Terraform binary, across the full chain from resource declaration to
import-by-identity.

## Why

Resource identity was implemented, unit-tested, and reviewed without a single
Terraform process ever executing it. The final review of that work found one
Critical and two Important defects; each would have surfaced immediately from
one real `terraform apply`. The most valuable missing test is the cheapest one
to describe and the most awkward one to build, which is why it did not exist.

## The chain under test

```
pyvider            framework: identity schema, marshalling, the two new RPCs
  └─ pyvider-components   resources that declare an identity
       └─ terraform-provider-pyvider   .tf fixtures + the installed provider binary
            └─ terraform / tofu        the real client driving the protocol
                 └─ tofusoup stir      lifecycle runner + assertions
```

## Prerequisites established

These were verified against the tree rather than assumed:

- **Identity entered the protocol in Terraform 1.12.0** — commit `857d188308`
  ("Add resource identity message to protocol (TF-23178)"), reachable from
  `v1.12.0-alpha20250213`. Both locally installed clients are past it:
  Terraform 1.14.0 and OpenTofu 1.12.5, each carrying the
  `GetResourceIdentitySchemas` and `UpgradeResourceIdentity` symbols and the
  `import`-block identity argument.
- **`terraform show -json` exposes identity.** `internal/command/jsonstate/state.go`
  emits `identity` (line 124) and `identity_schema_version` (line 120) per
  resource. It additionally hard-errors if state's identity schema version
  disagrees with the provider's, or if the provider reports no identity schema
  for a resource that has one in state — a free consistency check.
- **Identity is invisible to HCL.** `internal/lang/` contains no identity
  references; there is no `self.identity`. Terraform-native postconditions
  therefore *cannot* assert an identity value. A harness-side assertion is the
  only mechanism, which is what makes the stir work below load-bearing rather
  than convenient.
- **`import { identity = {...} }` is real** — `internal/configs/import.go:48`,
  mutually exclusive with `id` (lines 100, 109).
- **The provider binary already has an installer.** `pyvider install` places a
  development wrapper script (`_install_dev_provider`) or copies the packaged
  executable (`_install_binary_provider`), auto-selected by
  `is_running_as_binary()`, with `--reinstall` and `--uninstall`. Nothing new is
  needed here.

## Global Constraints

- Terraform client must be >= 1.12 (or OpenTofu >= 1.12). `soup.toml`'s
  `[workenv.tools]` currently pins `terraform = "1.8.5"` and `tofu = "1.10.5"`,
  and `[workenv.matrix.versions]` lists 1.5.7–1.8.0 — all predate identity and
  must be raised.
- No hardcoded absolute paths or ports in fixtures; paths are derived from
  `path.module`.
- Test files stay under 500 lines.
- The identity assertion surface is **identity-only** (see *Scope of the
  assertion layer*).

## Architecture

Three stages, each independently runnable and independently failing, so a
regression localizes to a layer rather than reporting "e2e broken".

| Stage | Question answered | Mechanism | Harness work |
|---|---|---|---|
| 1 | Does the provider *advertise* identity correctly? | pytest over `terraform providers schema -json` | none |
| 2 | Does the provider *emit* the right identity values? | stir `[[assert]]` against `terraform show -json` | the assertion layer |
| 3 | Can Terraform *consume* identity to import? | `import { identity = {...} }` fixture | none |

Stage 3 needs no assertion support because a failed import fails `apply`, and
stir already treats a non-zero terraform exit as a test failure.

## Component 1 — identity on a component resource

`pyvider_local_directory` is the natural first subject: its schema already has
`path` (required) and `id` (computed, the absolute path), so identity requires
no schema redesign.

```python
# src/pyvider/components/resources/local_directory.py

@classmethod
def get_identity_schema(cls) -> PvsSchema:
    return s_identity(
        {"path": a_str(required=True, description="Absolute path of the managed directory.")}
    )
```

`s_identity` defaults to `version=0`, which is what Terraform assumes for a
resource whose state carries no recorded identity version — adopting identity is
a protocol-level no-op for existing state.

`BaseResource.get_identity()` derives identity values from state by attribute
name, returning `None` rather than a partial mapping, so no override is needed
while the identity attribute names match state attribute names.

`pyvider_file_content` follows as a second subject once `local_directory` is
green, confirming the mechanism is not accidentally specific to one resource.

## Component 2 — the stir assertion layer

### Why it must exist

Stage 2 has no alternative implementation. Identity is not reachable from HCL,
so it cannot be asserted in the `.tf`; and stir currently has no assertion
concept at all — a test passes if the terraform commands exited zero.

### Scope

**Identity-only.** The block supports exactly `resource`, `identity`, and
`identity_schema_version`. A general matcher over `show -json` — arbitrary
attribute paths, regex and equality operators, counts — is a strictly larger
design that should be built when a second use case asks for it, as a superset
that keeps these files working.

### Configuration surface

Per-test `soup.toml` already exists and is already read by
`stir/discovery.py` for `[metadata]`/`[test]` tags. It gains an array of tables:

```toml
[[assert]]
resource = "pyvider_local_directory.test"
identity = { path = "out" }
identity_schema_version = 0
```

`resource` is the resource address as it appears in `show -json`.
`identity` is compared as a whole mapping — every declared key must match, and
no undeclared key may be present, so a spurious extra identity attribute fails.
`identity_schema_version` is optional and defaults to `0`.

### Evaluation

`stir/executor.py` already runs `terraform show -json` at the ANALYZING stage
and parses it into a `state` dict, using it only to count providers, resources
and outputs before discarding it. Assertions evaluate against that same
already-parsed structure: walk `values.root_module.resources`, match on
`address`, compare `identity` and `identity_schema_version`.

Because the state JSON is already in hand, this adds no terraform invocations.

### Reporting

A new `ASSERT` stage runs between ANALYZING and DESTROYING.
`StirTestResult` already carries `failed_stage` and `error_message`, so a
failed assertion populates the existing fields; `stir/config.py`'s status emoji
table gains one row. Destroy still runs after a failed assertion, so a failing
test does not leak state.

Failure messages name the resource address, the expected mapping and the actual
mapping, because "assertion failed" without values is useless in CI logs.

## Component 3 — fixtures

Fixtures live beside the existing examples in `terraform-provider-pyvider`,
which already has `examples/resource/local_directory/`. Each stage gets its own
directory so stir treats it as an independent test with its own lifecycle.

**Stage 2 — identity emitted into state:**

```hcl
resource "pyvider_local_directory" "test" {
  path = "${path.module}/out"
}
```

with the `[[assert]]` block above in the directory's `soup.toml`.

**Stage 3 — import by identity.** A first apply creates the directory; a second
configuration imports that same object by identity rather than by id:

```hcl
resource "pyvider_local_directory" "imported" {
  path = "${path.module}/out"
}

import {
  to       = pyvider_local_directory.imported
  identity = { path = "${path.module}/out" }
}
```

A wrong identity schema, a wrong marshalled value, or an unimplemented
`ImportResourceState` path each fail `apply` here.

## Component 4 — the schema-exposure test

A pytest in tofusoup runs `terraform providers schema -json` against a
minimal configuration and asserts the provider's entry contains a
`resource_identity_schemas` mapping for `pyvider_local_directory` whose
attribute set is exactly `{path}` and whose version is `0`.

This is the cheapest stage and the first to run: if the schema is wrong,
stages 2 and 3 fail in ways that are much harder to read.

## Provider binary supply

`pyvider install` handles both modes, so the design uses it rather than
introducing anything:

- **Inner loop:** run from the components virtualenv, which places the
  development wrapper script into the Terraform plugin directory. Source
  changes take effect without repacking.
- **Gate:** run once from the packaged PSP built by
  `terraform-provider-pyvider`'s `make build`, confirming the artifact that
  actually ships also passes. This is what catches a packaging-layer regression
  that the wrapper would hide.

Both write to the same
`~/.terraform.d/plugins/local/providers/pyvider/$VERSION/$PLATFORM/` path that
the existing `make install` and `.github/scripts/install-provider.sh` already
target, so no new discovery mechanism is introduced.

## Client matrix

Both installed clients support everything under test, so both are exercised:
Terraform >= 1.12 and OpenTofu >= 1.12. `stir`'s binary resolution already
prefers `tofu`, falling back to `terraform`, honouring `TOFU_CLI_PATH` first
(`stir/config.py`). The `soup.toml` workenv pins and version matrix are raised
to versions that support identity.

Running both matters here specifically: identity is a protocol feature with two
independent client implementations, and pyvider is the server for both.

## Error handling and failure modes

| Failure | Where it surfaces | Diagnosis |
|---|---|---|
| Identity schema malformed or absent | Stage 1 | Schema RPC or `pvs_identity_schema_to_proto` |
| Identity absent from state | Stage 2, missing `identity` key | `get_identity()` returned `None`, or the handler dropped it |
| Identity value wrong | Stage 2, mapping mismatch | Derivation or marshalling |
| Identity schema version mismatch | Terraform hard-errors during `show` | Provider's declared version disagrees with state |
| Import cannot resolve | Stage 3, `apply` fails | `ImportResourceState` identity path |
| Provider fails to start | init/apply, before any stage | Version skew — the prerequisite dependency refresh |

## Testing strategy

The stages *are* the tests. Additionally:

- The stir assertion layer gets unit tests of its own, against recorded
  `show -json` fixtures rather than a live terraform run, covering: match,
  value mismatch, missing resource address, extra undeclared identity key, and
  schema-version mismatch.
- Each stage must be demonstrated to fail when the implementation is broken —
  reverting the identity declaration must turn the stages red. A test that
  cannot fail is not evidence.

## Definition of done

- `pyvider_local_directory` and `pyvider_file_content` declare identity schemas.
- Stages 1–3 pass against both Terraform >= 1.12 and OpenTofu >= 1.12.
- Stir's identity assertion layer is implemented, unit-tested, and documented.
- `soup.toml` client pins raised past 1.12.
- The packaged PSP gate has been run at least once and passes.
- Each stage has been shown to fail when identity is deliberately broken.

## Explicitly not in scope

- A general-purpose state assertion language for stir (recorded as a deferred
  concept; build when a second use case appears).
- List resources (`ListResource`), which the protocol 6.11 work left as stubs.
- CI wiring for these stages; they run on demand until the suite is released
  and the dependency refresh has settled.
