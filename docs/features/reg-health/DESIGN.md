# DESIGN — S6 Web UI: Registry + Health (`reg-health`)

**Roadmap**: S6 (web-UI wave), KanbanMate ticket #185. Depends on S1 #158 (shell + auth + WS relay — done).
**Bump**: minor (`0.45.1 → 0.46.0`) — additive read surface + new page, no breaking change.
**Commit type**: `feat`.

## 1. Purpose

Expose the `ProviderRegistry`'s live health in the web UI: per-provider circuit-breaker
state, provider-chain attempt provenance, recent-failure counts, last success/failure
timestamps, and per-provider latency. Read-only surface — the registry stays observe-only
(no web-triggered mutation of provider/circuit state).

Includes **S6.0**: freeze the registry status _contract_ as **additive-only** BEFORE the
panel consumes it, so future changes can add fields but never remove/rename/retype the ones
the frontend binds to.

## 2. What already exists (from the code map)

- `ProviderStatus` frozen dataclass — `personalscraper/api/metadata/registry/__init__.py:146-166`:
  `provider_name: RegistryProviderName`, `circuit_state: CircuitState`,
  `failure_count_recent: int`, `last_success_at: datetime | None`,
  `last_failure_at: datetime | None`.
- `ProviderRegistry.status() -> dict[str, ProviderStatus]` — same file, ~line 605-626
  (reads each provider's `.circuit`; the read is fast + lock-guarded, safe in a request).
- `CircuitState` enum — `personalscraper/core/circuit.py:83-94`: `CLOSED/OPEN/HALF_OPEN`
  (values `"closed"/"open"/"half_open"`). **Gotcha**: reading `CircuitBreaker.state`
  auto-transitions `OPEN→HALF_OPEN` after cooldown (emits `CircuitBreakerHalfOpened`).
- Health/registry events (all frozen dataclasses, auto-published to the web stream because
  `RedisEventPublisher` subscribes to the base `Event`): `CircuitBreakerOpened/Closed/HalfOpened`
  (`core/circuit.py`), `ProviderFallbackTriggered`, `ProviderExhaustedEvent`,
  `RegistryFanOutCompleted`, `RegistryBootValidated`, `LockedCapabilityUnresolved`
  (`registry/_events.py`).
- EventBus → Redis stream (`subscribers/redis_stream.py`) → `web/ws/relay.py:read_stream_loop`
  → WS clients. WS envelope: `{"id", "type": "<EventClassName>", "data": {…}}`. **No per-event
  wiring needed** — the events already flow to the browser.
- Frontend: `/registry` is a `ComingSoon` stub (`frontend/src/router.tsx:63-65`), nav entry
  disabled (`frontend/src/components/layout/nav.ts:81`). `useEventStreamContext()` gives the
  live event ring; `StatPanel` (`components/ds/StatPanel.tsx`) is the panel primitive;
  `IndexHealthPanel` (`components/maintenance/`) is the mirror pattern.
- **Gap**: no `/api/registry/*` REST endpoint; `ProviderStatus` carries **no latency** field.

## 3. Design decisions

### 3.1 S6.0 — additive-only contract freeze (do FIRST)

Add a **characterization test** `tests/api/metadata/registry/test_status_contract_frozen.py`
that pins the _public_ contract the web binds to:

- `ProviderStatus` field set == exactly `{provider_name, circuit_state, failure_count_recent,
last_success_at, last_failure_at, last_latency_ms}` (see §3.2) — asserted via
  `dataclasses.fields`. A **removed/renamed** field fails the test (breaking); a **new**
  field is allowed only when the test is deliberately extended in the same commit
  (documents the additive change).
- `CircuitState` values == `{"closed","open","half_open"}` — a removed/renamed value fails.
- The serialized JSON shape (§3.3) round-trips every field with the documented type.

This is a _guard_, not runtime code: it makes "additive-only" a checkable invariant the way
the other web invariants are (staging-guard, typed-route, epoch-timestamp tests).

### 3.1b CROSS-PROCESS REALITY (architecture correction, 2026-07-10)

**The web process is separate from the pipeline process.** Circuit breakers live in-memory in
the _pipeline_ process's `ProviderRegistry`; the web process has **no live registry** (the
decisions route builds a throwaway `per_step_boundary` context per request — fresh circuits,
all `CLOSED`). Therefore a web-side `registry.status()` read does **not** reflect real health,
and `last_latency_ms` set on a pipeline-process circuit is **unreachable** from the web.

**The only cross-process channel is the event stream** (pipeline EventBus → Redis stream →
`web/ws/relay.py` → WS). So S6 is **event-driven**: live health reaches the browser only through
events, and the REST endpoint is a lightweight **roster + optimistic baseline**, not a live read.

### 3.2 Latency (additive field + latency event)

`ProviderStatus` gains `last_latency_ms: float | None` (additive — safe under the freeze;
still useful **in-process** for CLI `info providers`). The transport records it on the circuit
with a `time.monotonic()` delta (done in Phase 1). **To cross into the web**, the transport
also emits a lightweight `ProviderCallCompleted{provider, latency_ms, ok}` event (auto-published
to the stream like every other event); the frontend projects the latest latency per provider
from it. `None` until the first call.

### 3.3 REST — `GET /api/registry/status` (roster + optimistic baseline)

- Mounts inside `guarded_api` (session guard; **no** `X-Requested-With`, it's a read; **no**
  `require_not_staging` — read allowed on staging 8711).
- Reads the **server-side health projection** (§3.4) — the true last-known per-provider state
  derived from the event history — merged with the **configured provider roster** so a provider
  with no event yet still renders (optimistic baseline `circuit_state="closed"`, counts 0,
  timestamps `null`, `last_latency_ms` `null`, `live=false`). A provider the projection has
  observed carries its real state + `live=true`.
- Pydantic `response_model` (OpenAPI → `schema.d.ts`): `RegistryStatusResponse{providers:
list[ProviderStatusItem]}`; item = `provider_name`, `circuit_state:
Literal["closed","open","half_open"]`, `failure_count_recent`, `last_success_at: float|None`
  (epoch), `last_failure_at: float|None`, `last_latency_ms: float|None`, `live: bool`.
- Fail-soft: never 500 — an empty projection + empty roster yields `{providers: []}`.

### 3.4 Server-side health projection (the cross-process bridge)

A small in-memory `RegistryHealthProjection` (in the web process) holds `{provider →
{circuit_state, failure_count_recent, last_success_at, last_failure_at, last_latency_ms}}` and
an `apply(event_type, data)` reducer:

- `CircuitBreakerOpened` → state `open`, set `failure_count_recent`, `last_failure_at`.
- `CircuitBreakerClosed` → state `closed`. `CircuitBreakerHalfOpened` → state `half_open`.
- `ProviderCallCompleted{provider, latency_ms, ok}` → set `last_latency_ms`; `ok` refreshes
  `last_success_at`, else `last_failure_at`.

It is fed from **two sources that share the reducer**: (1) `read_stream_loop` calls
`projection.apply(...)` on every relevant event as it relays it live; (2) on web **boot**, the
lifespan **warms** the projection by `XRANGE`-replaying the Redis stream tail through the same
reducer (so the very first REST hit reflects history, not a cold cache). Stored on
`app.state.registry_projection`. The REST route reads it; the frontend ALSO patches its own view
from the same live WS events (so the panel updates without re-polling). This is the honest
cross-process bridge — no shared DB, reuses the existing event stream + relay.

### 3.5 Frontend — `/registry` page

- Replace the `ComingSoon` stub with a `RegistryPage`; enable the nav entry (drop `disabled`).
- Typed client `frontend/src/api/registry.ts` (`fetchRegistryStatus`) from the generated schema.
- `useRegistryStatus` TanStack Query hook (initial snapshot) + `useEventStreamContext` filter
  for live circuit/registry events → invalidate/patch.
- Layout: one `StatPanel`-style card per provider (name, circuit-state badge coloured by state,
  recent-failure count, last success/failure relative time, `last_latency_ms`), plus a
  chain/attempt strip driven by the latest `RegistryFanOutCompleted`/`ProviderExhaustedEvent`.
- Vitest coverage: typed client (URL/headers/error paths), the hook (snapshot + WS patch),
  the page (renders providers, badge colour per state, empty state).

## 4. Non-goals

- No web-triggered reset/trip of circuit breakers (observe-only; a future wave may add it).
- No historical latency charting (only the last value); no per-capability drill-down beyond
  the latest fan-out.
- No change to how events are published (the auto-publish path is reused as-is).

## 5. Phases

1. **S6.0 contract freeze + latency field** — add `last_latency_ms` (additive) + the
   characterization freeze test; instrument the attempt boundary to record latency.
2. **REST read route** — `GET /api/registry/status` + Pydantic models + `make openapi`
   regen + route tests (auth guard, shape, staging-allowed, fail-soft per-provider).
3. **Frontend typed client + hook** — `api/registry.ts` + `useRegistryStatus` + vitest.
4. **Frontend page + nav** — `RegistryPage` (panels + chain strip + live WS patch), enable
   nav, replace stub, vitest + a11y.
5. **Integration + ACC + docs** — e2e (snapshot + a live circuit-open event reflected in the
   panel), `docs/reference/web-ui.md` §registry section, ACCEPTANCE (executable), final gate.

## 6. ACCEPTANCE (executable — filled in ACCEPTANCE.md)

- `GET /api/registry/status` returns 200 with a `providers[]` of the frozen shape (authed).
- Unauthenticated → 401. Staging (8711) → 200 (read allowed).
- The freeze test fails if a `ProviderStatus` field or `CircuitState` value is removed/renamed.
- Frontend `/registry` renders one card per provider with the correct circuit badge; a live
  `CircuitBreakerOpened` event flips the badge without a reload.
- `make check` green; openapi drift clean; design-gaps + feature-map clean.
