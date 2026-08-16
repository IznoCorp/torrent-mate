# Phase 2 — Pipeline page UX

Trigger labels, interpreted logs (accordion), persisted last-run summary, run-history dedup.
Mostly frontend; one additive backend change (persist StepReport summary into `steps_json`).

## Gate

- `npm run lint && typecheck && vitest run` green; `make check` green (backend touched).
- `make openapi` re-run + committed if the run-detail response_model changes.
- Trigger labels + legend visible; raw logs collapsed by default with interpreted lines; no
  run-history table on Pipeline; last-run report visible when idle.

## 2.1 — Trigger labels + legend (frontend)

**Objective**: raw trigger strings become human labels with a legend.

**Current**: `RunHistoryTable.tsx:142` renders `trigger` verbatim (`web`/`cli`/`cron`/`completion`/
`safety_net`/`manual`); no label map.

**Approach**: add `frontend/src/components/pipeline/triggers.ts` (mirror
`components/decisions/triggers.ts`): `trigger → { label, tone, meaning }`. Render labels in the run
tables + a small legend/caption. Map: `completion`→"Fin de téléchargement", `safety_net`→"Filet de
sécurité", `manual`→"Manuel", `cli`→"Ligne de commande", `web`→"Interface web", `cron`→"Planifié".
**Files**: new `pipeline/triggers.ts`, `RunHistoryTable.tsx`, Pipeline page.
**Tests**: unit for the map (every known trigger → label; unknown → passthrough).

## 2.2 — Persist StepReport summary into steps_json (backend, additive)

**Objective**: the interpreted last-run report survives past the live WS stream.

**Current** (survey): `pipeline_history.update_step` (`pipeline_history.py:170`) writes only
`{name, started_at, ended_at, status}`; rich `StepReport` (`models.py:62`) lives only on the bus.

**Approach**: enrich each `steps_json` entry with the StepReport summary the engine already has:
`success_count`, `skip_count`, `error_count`, selected `counts`, `unmatched_count` (len of
`unmatched_paths`). Thread the summary from the pipeline engine's `StepCompleted` into
`update_step` (additive kwargs, all optional → back-compatible with existing rows). Expose via the
run-detail response_model. **No migration** (`steps_json` is JSON). `make openapi` if the model
changes.
**Files**: `personalscraper/pipeline_history.py`, the engine call-site emitting step completion,
`personalscraper/web/models/*` (run detail), `personalscraper/web/routes/pipeline.py`.
**Tests**: unit — `update_step` persists the summary; a run-detail read returns it; a legacy entry
without the summary still parses (fail-soft defaults).

## 2.3 — Interpreted-log reducer + accordion (frontend)

**Objective**: default Pipeline view = plain-language interpreted lines; raw WS logs collapse into
an accordion (hidden by default).

**Approach**:

- Add an `Accordion` primitive to `frontend/src/components/ui/accordion.tsx` (shadcn/radix; none
  exists yet). Unit-test open/close + a11y.
- Interpreted-log reducer: fold the live WS events for the active `run_uid`
  (`StepStarted`/`StepCompleted`/`ItemProgressed`/`StepErrored`) into ordered French lines
  (folder scan, collected items, move-to-staging what→where, cleaning before→after, scrape ok /
  ambiguous-awaiting-decision, trailers dl/unavailable, dispatch destination per media). Pure
  function over the event list → unit-testable with fixtures.
- Pipeline page: interpreted lines shown by default; the existing raw-log feed moves inside the
  Accordion (collapsed). Keep auto-follow behaviour when the accordion is open.
  **Files**: new `ui/accordion.tsx`, new `components/pipeline/interpretRun.ts` (+ test),
  `frontend/src/pages/Pipeline.tsx`, the raw-log component.
  **Tests**: reducer fixtures (event sequence → expected lines incl. ambiguous/dispatch cases);
  accordion unit test.

## 2.4 — Remove run-history dup + keep last report (frontend)

**Objective**: run-history only on Maintenance; Pipeline always shows the last run's interpreted
summary when idle.

**Approach**: drop `RunHistoryTable` from the Pipeline page (it stays on Maintenance with
`kind="pipeline"`… confirm Maintenance already shows pipeline history; if it only shows
`kind="maintenance"`, add a pipeline-history view there so nothing is lost). When no run is active,
Pipeline fetches `GET /api/pipeline/history?limit=1` and renders that run's interpreted summary
(from the persisted 2.2 summary) until a newer run supersedes it.
**Files**: `frontend/src/pages/Pipeline.tsx`, `frontend/src/pages/Maintenance.tsx` (if a pipeline
history view must be added), relevant hooks.
**Tests**: Pipeline vitest — no history table present; idle state shows the last-run summary;
active run shows live interpreted lines.
