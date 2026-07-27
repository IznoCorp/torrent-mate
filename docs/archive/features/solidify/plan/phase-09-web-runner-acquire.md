# Phase 9 — Web runner engine + acquire hygiene (T6)

## Gate

```bash
make lint && make test && make check

# Route/model-touching phase: regenerate + commit the typed-API chain (ACC-13)
make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts && echo ACC-13-OK

# Reservation + steps_json single owner (zero divergent copies)
rg -n "BEGIN IMMEDIATE" -g '*.py' personalscraper/web/                     # reservation lives in the engine only
rg -n "def .*parse.*steps_json|steps_json" -g '*.py' personalscraper/web/models/  # one parser owner

# web followed-metadata routes through store methods (single-writer discipline)
rg -n "BEGIN IMMEDIATE|INSERT INTO|UPDATE " -g '*.py' personalscraper/web/acquisition/  # 0 raw writes — store methods only

python -c "import personalscraper" && echo IMPORT-OK
```

## Objective

Introduce `web/_runner_engine.py` — ONE engine owning run-row reservation, subprocess
spawn + stream capture, heartbeat, requeue-on-busy (202 + queue step), finalize + terminal
status, and `pipeline.lock` tenure for destructive actions (DESIGN §5 T6). The four
detached runners (maintenance / decisions / acquisition / pipeline-queue) become thin
configs (command builder + row table + event names). The resolve queue keeps its SERIAL
semantics — the engine parameterises concurrency=1 there; nothing about #287 is re-opened.
Consolidate the ×3 `steps_json` parsers, layer the web routes, and land acquire hygiene:
dispatch-time reconciliation moves out of `DeleteAuthority` into an explicit post-dispatch
acquire subscriber; DETECT logic moves from the CLI into the service layer (grab parity);
web followed-metadata raw SQL routes through store methods; `QualityProfile` dead fields
dropped; `CrossSeedService.check()` decomposed. Web-UI is ratified — realign, never raze
(product-intent constitution binds; pixels unchanged).

## Findings addressed

WEB-BACKEND-01/02 (four re-implemented runner lifecycles; atomic reservation ×3),
WEB-BACKEND-06 (steps_json parser ×3), ACQUIRE-02 (dispatch-time reconciliation in
DeleteAuthority), ACQUIRE-03 (DETECT in CLI, not service), ACQUIRE-04 (runner reservation),
ACQUIRE-05 (`CrossSeedService.check` monolith), ACQUIRE-07 (`QualityProfile` dead fields),
ACQUIRE-09 (web followed-metadata raw SQL), MECHANICAL-DUP-04.

## Code anchors (verified)

- `personalscraper/web/_runner_engine.py`: NEW module (verified absent).
- Four runners (verified): `personalscraper/web/acquisition/runner.py`, `web/decisions/runner.py`, `web/maintenance/runner.py`, `web/pipeline_queue.py`. Reservation today: `personalscraper/web/decisions/reserve.py` (`BEGIN IMMEDIATE` :163, `INSERT INTO pipeline_run` :166, docstring :111 "one connection under BEGIN IMMEDIATE so the concurrency check and insert are atomic") and `web/run_queue.py`.
- steps_json parsers (×3 divergent — WEB-BACKEND-06): `personalscraper/web/models/pipeline.py`, and route/read sites in `web/routes/{maintenance,decisions,pipeline,acquisition}.py`, `web/pipeline_queue.py`.
- Route module-size relief (DESIGN T10 via this phase): `web/routes/acquisition.py` 909 non-blank LOC (1081 raw), `web/routes/maintenance.py` 974 non-blank LOC (1180 raw).
- Acquire hygiene:
  - `personalscraper/acquire/delete_authority.py::DeleteAuthority` :49 — `record_dispatch` does dispatch-time reconciliation (:37/:58), injected into `dispatch/run.py` + `maintenance/disk_cleaner.py` (:52); `may_delete` :108, `has_active_obligation` :84. ACQUIRE-02: move the reconciliation half into a post-dispatch acquire subscriber (DeleteAuthority keeps only the delete-permit decision).
  - DETECT logic in the CLI: `personalscraper/commands/follow.py` (ACQUIRE-03 → move to service layer for grab parity).
  - `personalscraper/acquire/reconcile.py::reconcile_wanted` :56 (the pure reconciliation pass the subscriber calls).
  - `personalscraper/acquire/cross_seed.py::CrossSeedService.check` :109 (836 non-blank LOC module — decompose with one reject-bookkeeping helper; ACQUIRE-05 + size relief).
  - `personalscraper/acquire/desired.py::QualityProfile` :78 (drop dead fields — ACQUIRE-07).
  - `personalscraper/acquire/store.py` (811 non-blank LOC — size relief); web raw-SQL sites `personalscraper/web/acquisition/truth.py`, `web/acquisition/_helpers.py` (ACQUIRE-09 → route through store methods).

Invariant reminders (do not regress): every mutating web endpoint stays staging-guarded
(`require_not_staging`) and typed (`response_model` → OpenAPI → `schema.d.ts`); the web auth
perimeter stays the single `guarded_api` dependency (no per-route `Depends(require_session)`);
write/destructive maintenance actions hold `pipeline.lock` for the runner's whole lifetime;
`pipeline_run` timestamps stay Unix-epoch `time.time()`; the resolve queue stays SERIAL.

## Tasks

1. **P9.1 — `_runner_engine.py`.** Implement ONE engine owning: run-row reservation (BEGIN IMMEDIATE + pid-alive guard + INSERT, lifted from `reserve.py`), subprocess spawn + stream capture, heartbeat, requeue-on-busy (202 + queue step, generalised from the resolve queue), finalize + terminal status, and `pipeline.lock` tenure for destructive runs. Concurrency is a parameter (=1 for the SERIAL resolve queue). Verify: `pytest tests -k "runner_engine or reservation" -q`; a busy engine returns 202 + enqueues; a destructive run holds `pipeline.lock` for its lifetime.
2. **P9.2 — Runners become thin configs.** Rewrite `web/acquisition/runner.py`, `web/decisions/runner.py`, `web/maintenance/runner.py`, `web/pipeline_queue.py` as configs (command builder + row table + event names) over the engine; delete the duplicated reservation in `reserve.py`/`run_queue.py` (or make them thin shims to the engine). Verify: `rg -n "BEGIN IMMEDIATE" -g '*.py' personalscraper/web/` shows the engine as the only owner; each runner's observable lifecycle (events, terminal status) unchanged (`pytest tests -k "web and runner" -q`).
3. **P9.3 — One steps_json parser (WEB-BACKEND-06).** Extract ONE `steps_json` parser (in `web/models/pipeline.py`) consumed by all route/read sites; remove the two divergent copies. Verify: `pytest tests -k "steps_json or pipeline_history" -q`; the parser is imported, not re-implemented, at every site.
4. **P9.4 — Routes layering + size relief.** Split `web/routes/acquisition.py` and `web/routes/maintenance.py` into route + service/read-model layers so each module is ≤800 non-blank LOC; keep endpoint signatures + `response_model`s byte-identical (no OpenAPI drift beyond intended). Verify: `python3 scripts/check-module-size.py` resolves both; `make openapi` yields no unexpected diff.
5. **P9.5 — ACQUIRE-02: post-dispatch reconciliation subscriber.** Move the dispatch-time reconciliation out of `DeleteAuthority.record_dispatch` into an explicit post-dispatch acquire subscriber calling `reconcile.reconcile_wanted`. `DeleteAuthority` retains only the delete-permit decision (`may_delete`/`has_active_obligation`). The narrow `DeleteAuthority`/`DeletePermit` port must NOT carry an event_bus (narrow-port rule); the subscriber is wired at the composition root. Verify: `pytest tests -k "reconcile and (subscriber or post_dispatch)" -q`; delete-permit behaviour byte-identical; reconciliation still runs after dispatch.
6. **P9.6 — ACQUIRE-03: DETECT into the service layer.** Move the DETECT logic from `commands/follow.py` into the acquire service so grab and follow share one detect path (grab parity). Verify: `pytest tests -k "detect and (service or grab_parity)" -q`; CLI output unchanged.
7. **P9.7 — ACQUIRE-09: web followed-metadata via store methods.** Replace the raw SQL in `web/acquisition/truth.py` + `web/acquisition/_helpers.py` with acquire store methods (single-writer discipline; no raw writes from the web layer). Verify: `rg -n "BEGIN IMMEDIATE|INSERT INTO|UPDATE " -g '*.py' personalscraper/web/acquisition/` == 0; acquisition read/write endpoints return identical payloads.
8. **P9.8 — ACQUIRE-05/07: CrossSeed decomposition + QualityProfile cleanup.** Decompose `CrossSeedService.check` (:109) with one reject-bookkeeping helper (module ≤800 non-blank LOC); drop the dead `QualityProfile` fields (`desired.py:78`), updating any config/serialization touched (pre-1.0: no compat shim; config/DB shapes may change if a field is truly dead). Verify: `pytest tests -k "cross_seed or quality_profile" -q`; `check-module-size` resolves `cross_seed.py` + `store.py`.
9. **P9.9 — Green + openapi.** Full gate + `make openapi` + commit `frontend/openapi.json` + `frontend/src/api/schema.d.ts`. Verify: ACC-13 gate line green.

## Non-goals

- Do not re-open the resolve queue serialization (#287) — concurrency=1 is a parameter, not a
  redesign.
- Do not change the `guarded_api` single-auth-dependency perimeter or add per-route
  `Depends(require_session)`.
- Do not weaken `require_not_staging` on any mutating endpoint or the `pipeline.lock` tenure
  rule for destructive runs.
- Do not change any UI screen/pixel or endpoint contract semantics (product-intent
  constitution — realign, never raze); OpenAPI diffs must be intentional and committed.
- Do not pass AppContext into the acquire domain / narrow ports; the reconciliation subscriber
  is wired at the composition root only.

## Commit

```
refactor(solidify): web/_runner_engine.py — one reserve/spawn/stream/requeue/finalize engine
refactor(solidify): four web runners become thin configs; one steps_json parser; routes layered
refactor(solidify): acquire hygiene — post-dispatch reconcile subscriber, DETECT to service, store-method writes
chore(solidify): regenerate openapi.json + schema.d.ts
```

Phase-gate commit:

```
chore(solidify): phase 9 gate — web runner engine + steps_json + routes layering + acquire hygiene
```
