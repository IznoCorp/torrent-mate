# Phase 2 — Cross-process health projection + REST read route

> **Architecture correction (2026-07-10).** The web process is separate from the pipeline
> process; a web-side `registry.status()` is a fresh, meaningless registry. Live health crosses
> processes ONLY via the event stream. So this phase builds a **server-side projection** fed by
> the event stream (live + a boot warm-up replay) and a REST route that reads it. See DESIGN
> §3.1b/§3.2/§3.3/§3.4.

Two sub-phases (each ≤6 files, cohesive).

## Gate

```bash
make check              # lint + test + module-size + guardrails (zero errors)
make openapi            # regenerate frontend/openapi.json + frontend/src/api/schema.d.ts
git diff --stat frontend/src/api/schema.d.ts frontend/openapi.json   # commit if changed
pytest tests/unit/web/test_registry_projection.py tests/web/routes/test_registry_status.py -v
```

---

## 2.1 — `ProviderCallCompleted` event + `RegistryHealthProjection` + relay wiring + boot warm-up

### Objectives

1. Add a `ProviderCallCompleted` event (`provider: str`, `latency_ms: float`, `ok: bool`) —
   frozen `kw_only` dataclass — in `personalscraper/api/metadata/registry/_events.py` (or the
   nearest existing registry events module). It auto-publishes to the stream (base `Event`).
2. Emit it from the transport where Phase 1 records latency
   (`personalscraper/api/transport/_http.py`, the `_request_outer` method). The transport HOLDS an
   `event_bus` (`__init__(self, policy, *, event_bus)`, ~line 50) and `policy.provider_name` —
   emit via that bus (the same bus the circuit uses for `CircuitBreakerOpened`, so it reaches the
   web identically). After computing `elapsed_ms` on BOTH success and failure paths, emit
   `ProviderCallCompleted(provider=policy.provider_name, latency_ms=elapsed_ms, ok=…)`.
   **THROTTLE (mandatory — avoid event flooding):** provider calls are high-frequency; a per-call
   emit would flood the Redis stream (evicting the rare circuit events) and spam WS clients. Emit
   at most **once per ~10 s per transport instance**: keep `self._last_latency_emit: float` (init
   `0.0`), emit only when `time.monotonic() - self._last_latency_emit >= 10.0`, updating the stamp
   on emit. Latency is still recorded on the circuit every call (Phase 1, unthrottled — the CLI
   sees all); only the _event_ is throttled. Keep `self._event_bus = event_bus` in `__init__` if
   not already stored. The emit is fail-soft (wrap in try/except so a bus error never breaks the
   HTTP call; log once).
3. Create `personalscraper/web/registry_projection.py` — `RegistryHealthProjection`:
   - internal dict `{provider: dict}` with keys `circuit_state, failure_count_recent,
last_success_at, last_failure_at, last_latency_ms`.
   - `apply(event_type: str, data: dict) -> None` reducer:
     - `CircuitBreakerOpened` → `circuit_state="open"`, `failure_count_recent=data["failure_count"]`,
       `last_failure_at=<now epoch>`.
     - `CircuitBreakerClosed` → `circuit_state="closed"`, `last_success_at=<now epoch>`.
     - `CircuitBreakerHalfOpened` → `circuit_state="half_open"`.
     - `ProviderCallCompleted` → `last_latency_ms=data["latency_ms"]`; `data["ok"]` truthy →
       `last_success_at=<now epoch>`, else `last_failure_at=<now epoch>`.
     - the provider key for circuit events is `data["breaker"]`; for call events `data["provider"]`.
     - unknown event types are ignored.
   - `snapshot() -> dict[str, dict]` returns a deep copy.
   - Uses `time.time()` epoch floats for timestamps (web-ui epoch convention). Thread-unsafe is
     fine (single relay task + request-thread reads of an immutable-ish snapshot); guard the dict
     mutation minimally if trivial.
4. Wire into `personalscraper/web/ws/relay.py`: `read_stream_loop` calls
   `projection.apply(msg["type"], msg["data"])` for each relayed message (pass the projection in,
   or read it off a shared ref). Store the projection on `app.state.registry_projection` in
   `create_app` (default instance) so both the relay task and the REST route share it.
5. Boot warm-up: in `personalscraper/web/app.py` lifespan, after the redis pool is up, replay the
   Redis stream tail (reuse the existing `replay_events`/`XRANGE` helper the WS route uses; read
   the last N≈1000 entries) and feed each through `projection.apply(...)`, so the first REST hit
   reflects history. Fail-soft: Redis down → warm-up skipped, projection starts empty.

### Files

- modify `personalscraper/api/metadata/registry/_events.py` (add event)
- modify `personalscraper/api/transport/_http.py` (emit event)
- create `personalscraper/web/registry_projection.py`
- modify `personalscraper/web/ws/relay.py` (apply in read_stream_loop)
- modify `personalscraper/web/app.py` (store projection on app.state + boot warm-up in lifespan)
- create `tests/unit/web/test_registry_projection.py`

### Tests (2.1)

- `test_registry_projection.py`: the reducer — Opened→open+failure_count, Closed→closed,
  HalfOpened→half_open, ProviderCallCompleted ok/!ok sets latency + success/failure ts, unknown
  event ignored, snapshot is a copy (mutating it doesn't change the projection). Assert epoch
  floats. (These must be REAL assertions, not vacuous — verify actual state transitions.)
- a relay test (extend the existing relay test) asserting a `CircuitBreakerOpened` message run
  through `read_stream_loop`'s handling updates the projection to `open`.

---

## 2.2 — REST `GET /api/registry/status` (projection + roster) + models + mount + openapi

### Objectives

1. `personalscraper/web/models/registry.py` — Pydantic `ProviderStatusItem` (`provider_name: str`,
   `circuit_state: Literal["closed","open","half_open"]`, `failure_count_recent: int`,
   `last_success_at: float | None`, `last_failure_at: float | None`, `last_latency_ms: float | None`,
   `live: bool`) + `RegistryStatusResponse{providers: list[ProviderStatusItem]}`.
2. `personalscraper/web/routes/registry.py` — `GET /api/registry/status`:
   - read `app.state.registry_projection.snapshot()`.
   - read the configured provider **roster** from config (the registry-config provider names —
     find how config exposes providers, e.g. `config.providers` / the registry config section;
     if unclear, enumerate the projection's own keys as the roster fallback).
   - merge: every roster provider present → if in the projection, emit its observed state with
     `live=True`; else optimistic baseline (`closed`, 0, nulls, `live=False`). Providers seen in
     the projection but not in the roster are still included (`live=True`).
   - fail-soft: any error → `RegistryStatusResponse(providers=[])`, never 500.
   - mounted under `guarded_api`; NO per-route `Depends(require_session)`; NO
     `require_x_requested_with`; NO `require_not_staging` (read allowed on staging).
3. Mount in `personalscraper/web/app.py`: `guarded_api.include_router(registry_router)` next to
   the decisions router.
4. `make openapi` + commit the regenerated `frontend/openapi.json` + `frontend/src/api/schema.d.ts`.

### Files

- create `personalscraper/web/models/registry.py`
- create `personalscraper/web/routes/registry.py`
- modify `personalscraper/web/app.py` (mount)
- modify `frontend/openapi.json` + `frontend/src/api/schema.d.ts` (regen)
- create `tests/web/routes/test_registry_status.py`

### Tests (2.2)

Follow the existing web route test pattern (`tests/web/test_pipeline_routes.py` / decisions
routes — build a minimal guarded app + session cookie). Cover:

- unauth → 401; authed → 200 with a `providers` array.
- item shape == exactly `{provider_name, circuit_state, failure_count_recent, last_success_at,
last_failure_at, last_latency_ms, live}`; `circuit_state ∈ {closed,open,half_open}`.
- a projection pre-seeded with an `open` provider surfaces `circuit_state="open"`, `live=True`.
- a roster provider absent from the projection surfaces the optimistic baseline (`closed`,
  `live=False`).
- staging role (`PERSONALSCRAPER_WEB_ROLE=staging`) → still 200 (read allowed).

## Gotchas

- **Cross-process**: do NOT call `registry.status()` from the web route — it builds a meaningless
  fresh registry (DESIGN §3.1b). Read the projection instead.
- **Single auth perimeter**: NEVER add `Depends(require_session)` on the route — guarded_api owns it.
- **Epoch floats**: `time.time()` for all timestamps (web-ui invariant), consistent with the
  projection reducer.
- **openapi drift**: any new `response_model` route ⇒ `make openapi` + commit the two regen files,
  else CI's frontend diff-guard reds (project_openapi_drift_ci_guard).
- **Fail-soft everywhere**: the panel must degrade gracefully (empty list) rather than 500 when
  the projection or roster read fails.
- **Latency event bus reachability**: if the transport genuinely has no EventBus to emit on,
  report it — do not fabricate wiring. In that case latency stays visible only via the in-process
  circuit (CLI) and the projection latency field stays null from the web; flag for a follow-up.
