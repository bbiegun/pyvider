# Pyvider Cloudflare Adapter — Design

## Motivation

Running pyvider itself (grpcio, cryptography, the full gRPC server) inside a
Cloudflare Worker or Durable Object is not viable: Cloudflare's Python
Workers run on Pyodide (CPython-to-WASM), which has no functional raw
socket support and only supports pure-Python or Pyodide/PyEmscripten-wheel
packages. grpcio needs raw TCP/TLS and has no such build. Cloudflare
Containers (a real container runtime) can run pyvider unmodified, but at
meaningful always-on cost (~$77–82/month for a 24/7 "standard" instance)
that's disproportionate to what's actually needed.

Separately, Terraform Core's plugin protocol (HashiCorp's `go-plugin`)
requires a **local** process: Terraform spawns a binary, reads a handshake
line from its stdout, and dials a **local** Unix socket or TCP port
directly. Nothing running remotely — Worker, Durable Object, or Container —
can stand in for that role. This is a hard, unchangeable constraint of how
Terraform Core discovers and talks to providers.

The actual driver for this work is **wanting a cheap, pay-per-request
serverless backend for provider logic** — a Durable Object's strong
consistency is not the point; a plain Cloudflare Worker satisfies the goal
just as well, with DO being optional infrastructure a specific backend
author might choose, not something the adapter itself needs to know about.

## Goal

A **general-purpose, reusable adapter** — not tied to any specific provider
or resource — that lets any pyvider-based provider run its resource logic
behind an HTTP(S) backend (a Cloudflare Worker being the flagship target),
while satisfying Terraform's local-process requirement with a thin local
shim. Provider authors should keep writing resources with the same
`@register_resource` / `BaseResource` / `BaseProvider` model they already
use for local pyvider — no new authoring API to learn.

## Prior investigation (this session)

Confirmed empirically, not assumed:

- `pyvider.resources`, `pyvider.schema`, `pyvider.cty` import cleanly with
  zero `grpc`/`cryptography` pulled in transitively — pyvider's package
  boundaries already separate the resource/schema layer from the transport
  layer. This is what makes reusing the resource-authoring model on a
  Worker plausible at all.
- `pyvider.rpcplugin.server.RPCPluginServer` already implements the full
  go-plugin handshake generically (magic cookie env-var check, protocol
  version negotiation, transport negotiation, Unix-socket setup, stdout
  handshake line, gRPC server bootstrap) — reusable as-is, no
  reimplementation needed for the local leg.
- `pyvider.protocols.tfprotov6.protobuf` (the message types) currently
  pulls in `grpc.aio`, `grpc._cython.cygrpc`, and all of `cryptography`'s
  hazmat layer transitively, even for a bare message-only import. The real
  per-RPC handler functions (`_configure_provider_impl` et al.) are
  themselves decoupled from the grpc server machinery (proven by the PR #6
  audit's proof suite, which calls them directly with no grpc server
  running) — but they still import from the `protobuf` package as
  currently structured, so they cannot be imported grpc-free today. This
  is why the Worker-side dispatch layer is JSON-native rather than a
  direct reuse of the real protobuf-typed handlers (see "DRY" below).
- Active protobuf implementation in this environment is `upb` (compiled),
  confirming the C-extension path is the default, not merely available.

## Architecture

```
Terraform Core
   |  spawn subprocess + dial local socket (go-plugin protocol)
   v
pyvider-cloudflare-adapter   (new package, runs locally — dev machine / CI)
   |  - pyvider.rpcplugin.server.RPCPluginServer for handshake/transport/lifecycle
   |  - one generic tfplugin6 gRPC servicer (RemoteProviderServicer)
   |  - per RPC: protobuf -> JSON (pyvider.cty/conversion) -> HTTPS -> backend
   v  HTTPS POST /rpc  (bearer token auth, TLS-only)
Cloudflare Worker             (new companion package, runs on Cloudflare)
   |  - imports pyvider.resources / pyvider.schema / pyvider.cty directly
   |    (confirmed grpc/cryptography-free)
   |  - thin JSON entrypoint dispatches to the SAME @register_resource /
   |    BaseResource / BaseProvider classes a normal pyvider provider uses
   |  - optional Durable Object behind it — backend author's choice
   v
resource logic (unmodified pyvider authoring model)
```

## Components

### `pyvider-cloudflare-adapter` (local; full Python, no Pyodide constraint)

- **`RemoteProviderServicer`** — implements the full tfplugin6 `Provider`
  gRPC service interface. Every method has the same shape: decode
  protobuf request -> convert to JSON (shared conversion helper built on
  `pyvider.cty`/`pyvider.conversion`) -> HTTP POST -> decode JSON response
  -> convert back to protobuf -> return.
- **`BackendClient`** — thin HTTP client: base URL, auth header,
  timeout/retry policy (see Error Handling), one POST per RPC.
- **`AdapterServer`** — wraps `pyvider.rpcplugin.server.RPCPluginServer`,
  wiring `RemoteProviderServicer` in as the service implementation. No
  reimplementation of the handshake/transport layer.
- **CLI entrypoint** (`pyvider-cloudflare-adapter` binary) — reads backend
  URL + auth token from env/flags. This binary is what a Terraform
  provider registry/local mirror points at as "the provider."

Depends on: `pyvider-rpcplugin`, `grpcio`, an HTTP client. No Pyodide
constraint — this process never runs on Cloudflare.

### `pyvider-cloudflare-worker` (Cloudflare Python Worker)

- **`WorkerEntrypoint`** — the Worker's request handler: parses
  `{rpc_name, payload}`, dispatches via a lookup table.
- **Per-RPC dispatch functions** — JSON-native, working with plain dicts
  instead of protobuf, but calling into `pyvider.hub`, `pyvider.schema`,
  `pyvider.cty` the same way the real handlers do underneath.
- Reuses the exact same `@register_resource` / `@register_provider` /
  hub-discovery mechanism pyvider already has. A provider author writes
  resources exactly like they do for local pyvider, then imports those
  classes into the Worker's entrypoint file.

Depends on: `pyvider` core (resources/schema/cty only) — must stay
grpc/cryptography-free to remain Pyodide-installable. Kept as a *separate
distribution* from the adapter so that boundary is enforceable, not just a
convention someone can accidentally break.

**Schema is dynamic, not static.** `GetProviderSchema` is just another
forwarded RPC — the Worker computes it live off `hub`/`provider.schema`,
same as local pyvider does today. No codegen step, no schema drift to
manage between adapter and backend. The adapter caches the schema
in-process for the life of a single Terraform run (it can't change
mid-`apply`) to avoid a redundant round trip on every subsequent RPC.

## Data flow

Per-RPC round trip, same shape for every RPC:

```
Terraform -> gRPC request -> adapter's RemoteProviderServicer method
  -> decode protobuf -> convert to JSON (pyvider.cty/conversion)
  -> BackendClient.post(rpc_name, json_payload, auth_header, timeout)
  -> Worker WorkerEntrypoint receives {rpc_name, payload}
  -> dispatch table -> JSON-native wrapper (pyvider.hub / schema / cty /
     resource lifecycle hook)
  -> JSON response {diagnostics, result}
  -> adapter converts JSON -> protobuf response
  -> gRPC response -> Terraform
```

## Error handling

- **Network failure** (timeout, DNS, Cloudflare down): caught at
  `BackendClient` level, converted to a tfplugin6 `Diagnostic` (ERROR
  severity) via the existing `create_diagnostic_from_exception` pattern.
  Never an unhandled exception that kills the adapter process mid-`apply`.
- **Auth failure** (401/403 from Worker): a distinct diagnostic pointing
  at the token config, not a generic network-error message.
- **Retry policy**: idempotent RPCs only (`GetProviderSchema`,
  `ReadResource`, `ValidateProviderConfig`, `PlanResourceChange`) get
  transient-failure retry with backoff. `ApplyResourceChange` and
  `ImportResourceState` never auto-retry on the adapter's side — a network
  blip mid-apply must surface as an error, not risk a silent double-create.
- **Version mismatch**: the adapter sends its own protocol version on
  every request; the Worker validates and returns a clear "adapter vX
  incompatible with worker vY" diagnostic instead of a confusing
  downstream failure.
- **Worker-side exceptions**: caught and converted to diagnostics with
  schema-`sensitive=True` fields redacted before the message crosses back
  to the adapter — see Security.

## Security

- Adapter <-> Worker: HTTPS-only, bearer token from an env var (never
  hardcoded), treated as a credential like any other provider's API key.
- Terraform <-> adapter leg already gets ephemeral per-session mTLS from
  pyvider-rpcplugin's existing handshake certificate generation — nothing
  new needed there.
- **Sensitive-value redaction is a first-class requirement, not an
  afterthought.** The PR #6 audit in this same session found a real leak
  (Rich traceback locals exposing `sensitive=True` schema values in
  logs). The same class of risk applies here, arguably worse since
  payloads now cross a network boundary: never log a raw request/response
  body without redacting fields the schema marks `sensitive=True`, on both
  the adapter and the Worker.
- Backend authorization (who's allowed to call which resources) is the
  backend author's responsibility, same as any HTTP API — out of scope
  for the adapter itself.

## DRY — known duplication and how it's bounded

`pyvider.protocols.tfprotov6.protobuf` currently bundles protobuf message
types together with grpc service stubs in its import graph (confirmed
above), so the Worker's JSON-native dispatch functions cannot delegate
directly to pyvider's real protobuf-typed handler functions
(`_configure_provider_impl` et al.) today. This means the ~30–80 line
per-RPC orchestration wrapper (unmarshal -> call lifecycle hook -> build
diagnostics) is duplicated between pyvider's real handlers and this
project's JSON-native ones. Everything underneath that wrapper — `hub`,
`schema`, `cty`, resource lifecycle hooks — is shared and not duplicated.

Duplication is bounded by **contract tests**: a shared fixture set
(canonical request -> expected response, per RPC) run against both the
real protobuf handlers and the new JSON wrappers, asserting equivalent
behavior. Lives in `pyvider-cloudflare-worker`'s test suite. This is the
mechanism that catches drift over time rather than relying on manual
vigilance.

### Future work: eliminate the duplication upstream

Split `pyvider/protocols/tfprotov6/protobuf/__init__.py` so message-only
imports (`_pb2.py`) don't drag in the grpc service stubs (`_pb2_grpc.py`).
That's a separate, additive, low-risk change to the `pyvider` repo with
its own review cycle — not a blocker for this project. Once merged, the
Worker's JSON wrappers can migrate to delegate directly into the real
handlers, shrinking the duplicated surface to near zero. Tracked as
follow-up, not gating v1.

## Testing

- **Unit — conversion round-trip**: protobuf<->JSON tests per RPC type on
  the adapter side, reusing pyvider's existing `cty`/`conversion` test
  patterns. `BackendClient` tested with mocked HTTP responses (timeout,
  401, 5xx each map to the correct diagnostic).
- **Unit — Worker dispatch**: JSON-native wrapper tests mirroring
  pyvider's own handler test structure, exercised against the new
  wrappers.
- **Contract tests**: shared fixtures run against both the real protobuf
  handlers and the JSON wrappers — the DRY safety net described above.
- **Integration**: a real adapter subprocess plus a local mock HTTP
  backend (not live Cloudflare) exercising the full handshake -> gRPC ->
  HTTP -> back round trip. Check what TofuSoup (sibling testing project)
  already provides before building this from scratch.
- **Worker-under-Pyodide smoke test**: the dispatch logic itself is plain
  Python, testable in normal CI without Cloudflare. Package availability
  under `micropip` is a Pyodide-specific risk, not caught by plain-Python
  unit tests — add a smoke-test tier against `wrangler dev`/Miniflare
  before treating any release as shippable.
- **Security regression test**: automated check that `sensitive=True`
  schema fields never appear in logged payloads on either side, same
  style as the proof-suite tests used in the PR #6 audit.

## Open questions for the implementation plan

- Exact package names (`pyvider-cloudflare-adapter` /
  `pyvider-cloudflare-worker` are working names, not finalized).
- Where contract-test fixtures physically live and how they're kept in
  sync as pyvider's real handlers evolve.
- Whether the upstream `pyvider.protocols.tfprotov6.protobuf` packaging
  fix (Future Work) should be scoped as a companion PR now or deferred
  entirely until there's a second reason to want it.
