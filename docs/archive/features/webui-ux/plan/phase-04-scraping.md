# Phase 4 — Scraping / decisions refonte + parallel scraping

Frontend refonte (flat list + optional filters + inline actions) + the riskiest backend change:
scoped, scrape-only locking for safe parallel resolves.

## Gate

- `npm run lint && typecheck && vitest run` green; `make check` green; `make openapi` if routes
  change.
- Flat list + optional filters render; states relabelled with tooltips; two decisions on distinct
  staging paths resolve concurrently; same-item double-resolve still 409; scrape-resolve refuses
  while the global `pipeline.lock` is held.

## 4.1 — Flat-list refonte + optional filters + relabel (frontend)

**Current** (survey): `Decisions.tsx` uses status filter chips (`pending`/`resolved`/`dismissed`/
`superseded`) + list/detail split; operator finds `dismissed`/`superseded` confusing.

**Approach**:

- One always-visible flat list of all decisions; filter chips become **optional** (default: show
  all, or pending-first) with a live count per status.
- Relabel + tooltip the confusing states: `dismissed` → "Ignorée (laissée telle quelle)",
  `superseded` → "Remplacée (re-scrapée depuis)". Presentation only — backend `status` values
  unchanged.
- Inline per-row primary action (resolve/dismiss/re-search) where possible; detail panel retained
  for candidate selection.
  **Files**: `frontend/src/pages/Decisions.tsx`, `components/decisions/DecisionList.tsx`,
  `components/decisions/triggers.ts` (labels), `components/decisions/DecisionDetail.tsx`.
  **Tests**: `Decisions.test.tsx` — all items visible without selecting a tab; filter is optional;
  relabelled states + tooltips present.

## 4.2 — Scoped scrape-only lock (backend, safety-critical)

**Objective**: disjoint staging items resolve in parallel; the global single-writer guarantee for
dispatch/move is preserved.

**Current** (survey): the decision runner holds no lock, but the child `scrape-resolve`
self-acquires the **global** `pipeline.lock` for its lifetime (`web/decisions/runner.py:14`), so
resolves serialize. `scrape-resolve` touches ONE staging path (metadata/NFO/artwork only — no
dispatch/move).

**Approach** (explicit safety design):

- Introduce a **per-staging-path lock** `<data_dir>/locks/scrape-<sha1(staging_path)>.lock` for the
  `scrape-resolve` code path, replacing its global `pipeline.lock` acquisition. Two resolves on
  distinct paths proceed concurrently; the SAME path still blocks (idempotent guard).
- `scrape-resolve` must still **read-check** the global `pipeline.lock` and refuse to start if a
  full pipeline run holds it (prevents a scrape racing a dispatch of the same tree). It does NOT
  acquire the global lock.
- Full-pipeline + maintenance runners keep acquiring the global `pipeline.lock` (unchanged).
- Update `web/maintenance/runner.py::_CLI_SELF_LOCKING` bookkeeping accordingly.
  **Files**: `personalscraper/web/decisions/runner.py`, the `scrape-resolve` command
  (`personalscraper/commands/*` scrape-resolve), the lock helper (`acquire_lock` module), possibly a
  new `scoped_lock` util.
  **Tests** (regression-per-bug): integration test with two temp staging dirs — two scrape-resolves
  run concurrently to completion; same-path second resolve blocks/409; a held global pipeline.lock
  makes scrape-resolve refuse. Assert no cross-item filesystem interference.

## 4.3 — Web layer: allow concurrent decision runners

**Objective**: the web POST no longer globally rejects a second concurrent resolve; it rejects only
a double-launch of the SAME decision.

**Current**: 409 "Un autre re-scraping est déjà en cours" on any concurrent resolve.

**Approach**: scope the 409 to the same `decision_id` (or same staging path); allow different
decisions to launch concurrently. Keep the per-decision idempotency (a decision already `resolved`/
in-flight → 409/410 as today).
**Files**: `personalscraper/web/routes/decisions.py`, `web/decisions/runner.py`.
**Tests**: route test — two different decisions → both 202; same decision twice → second 409;
resolve of an already-resolved decision → 410. `make openapi` if the response shape changes.
