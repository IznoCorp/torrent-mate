# Phase 5 — Dashboard reorg + scheduler overview

Relocate event panels to Maintenance; add a typed scheduler/cron/watcher overview.

## Gate

- `npm run lint && typecheck && vitest run` green; `make check` green; `make openapi` committed
  (new/extended endpoint).
- Dashboard no longer shows the event feed/table (now on Maintenance); Dashboard shows a scheduler
  overview (watcher + 3 crons, each with last-run); endpoint typed + in openapi.

## 5.1 — Move event panels to Maintenance (frontend)

**Current** (survey): `EventFeed` + `RecentEventsTable` (`components/dashboard/`) are self-contained,
both read one `useEventStreamContext()`. Dashboard also has `HealthCard` + `VersionCard`.

**Approach**: relocate both event components to the Maintenance page (keep a single shared
`useEventStreamContext()` — no duplicate WS). Dashboard keeps Health + Version + the new scheduler
panel.
**Files**: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Maintenance.tsx`,
`components/dashboard/EventFeed.tsx` + `RecentEventsTable.tsx` (move or re-import; consider a
`components/events/` home).
**Tests**: `Dashboard.test.tsx` — no EventFeed/RecentEventsTable; `Maintenance` renders both.

## 5.2 — Scheduler overview endpoint (backend, typed read)

**Objective**: one typed read surfacing each scheduled agent's state.

**Current** (survey): watcher state = ¬`data_dir/watcher.paused` + `acquire.db
watch_state.last_successful_run_at`; crons (`follow-detect` 03:00, `grab` 03:20&15:20,
`index-enrich` Sun 04:30) have no enabled flag — last-run derivable from `pipeline_run`. Existing
`GET /api/acquisition/status` already reads the watcher bits.

**Approach**: add `GET /api/maintenance/schedulers` (or extend acquisition status) → typed list of
`{ name, kind: "watcher"|"cron", schedule_or_enabled, last_run_at, last_outcome }`. Sources: the
watcher sentinel + `watch_state`; a **static schedule registry** mirroring `ecosystem.config.js`
crons; last-run/outcome from `pipeline_run` (by trigger/command). Read-only, lock-free
per-request sqlite. Typed `response_model` → `make openapi`.
**Files**: `personalscraper/web/routes/maintenance.py` (or acquisition), new
`personalscraper/web/models/*` schema, a small static scheduler registry module.
**Tests**: route test — watcher + crons present with last-run; fail-soft when a source db is absent.

## 5.3 — Dashboard scheduler panel (frontend)

**Approach**: a "Planificateurs" panel on the Dashboard consuming 5.2 — each agent as a row/card
with name, kind badge, schedule/enabled, last-run (relative time), last-outcome tone. Responsive.
**Files**: new `components/dashboard/SchedulersPanel.tsx` + hook `useSchedulers()`,
`frontend/src/pages/Dashboard.tsx`, `frontend/src/api/*` client.
**Tests**: panel vitest — rows render from a mocked payload; empty/loading/error states.
