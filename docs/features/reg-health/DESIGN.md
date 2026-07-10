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

### 3.2 Latency (additive field)

`ProviderStatus` gains `last_latency_ms: float | None` (additive — safe under the freeze).
Source: instrument the registry attempt boundary (where `AttemptOutcome` is already produced
on each provider call) to record the last call's wall-clock ms on the provider's circuit/
status. Measured with `time.monotonic()` deltas around the provider call; `None` until the
first call. No new event needed — the value surfaces via `status()` + the REST snapshot;
the panel updates it on each `RegistryFanOutCompleted`/circuit event by re-querying, or shows
the REST snapshot value.

### 3.3 REST — `GET /api/registry/status`

- Mounts inside `guarded_api` (session guard; **no** `X-Requested-With`, it's a read).
- Pydantic `response_model` (so OpenAPI → `schema.d.ts`): `RegistryStatusResponse` with
  `providers: list[ProviderStatusItem]`, each item = the ProviderStatus fields with
  `circuit_state: Literal["closed","open","half_open"]`, timestamps as Unix-epoch floats
  (consistency with pipeline_run epoch convention) or ISO-8601 — **epoch floats** to match
  the rest of the web surface, `last_latency_ms: float | None`.
- Read-only, fast, fail-soft: a provider whose `.circuit` read raises is reported with a
  degraded marker rather than 500-ing the whole list.
- `require_not_staging` is **not** applied (read is allowed on staging).

### 3.4 WebSocket — consume existing events (no backend change)

The panel subscribes via `useEventStreamContext()` and filters the event ring for the
health/registry event types (§2). Circuit transitions flip a provider's badge live; fan-out/
exhausted events annotate the chain view. Initial state comes from the REST snapshot (TanStack
Query); WS events are the live delta. This mirrors how S2 pipeline + S5 decisions combine a
REST snapshot with the WS stream.

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
