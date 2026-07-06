# Phase 6 — Deploy rails + docs + ACCEPTANCE

## Gate

Phase 5 must have produced:

- `RunHistoryTable` working with sortable columns and pagination
- `RunDetail` rendering the per-step timings via `PipelineStepper` (read-only)
- Frontend pipeline page complete: controls + stepper + log feed + history table + detail
- `make openapi` regenerated, `schema.d.ts` up-to-date, `npm run typecheck` 0, `npm run lint` 0

## Scope

Documentation updates, executable ACCEPTANCE criteria, staging validation. No new code — this phase
validates and documents what was built.

## Sub-phases

### 6.1 — Documentation + ACCEPTANCE

**Files:**

- Modify: `docs/reference/web-ui.md` (add pipeline control section)
- Modify: `docs/reference/commands.md` (add `--trigger-reason` flag + pause sentinel doc)
- Create: `docs/features/pipe-control/ACCEPTANCE.md`

**Commit:** `docs(pipe-control): add web-ui pipeline docs + executable ACCEPTANCE`

- `web-ui.md`: add section "Pipeline control (S2)" describing:
  - The 6 REST endpoints (table from DESIGN §4)
  - The pause/resume mechanic (sentinel file)
  - The watcher toggle (separate from run pause)
  - Run-history API
  - The `pipeline_run` table schema
- `commands.md`: document the new `--trigger-reason` flag on `personalscraper run`:
  - Values: `cli` (default), `web`, `watch`, `safety-net`
  - The `pipeline.pause` sentinel file and how to use it manually
  - The `watcher.paused` sentinel
- `ACCEPTANCE.md` with executable `ACC-NN` criteria:
  - **ACC-01**: `curl -X POST .../api/pipeline/run -H 'Cookie: ...' -H 'X-Requested-With: TorrentMate' -H 'Content-Type: application/json' -d '{"dry_run":true}'` → `202` + a `run_uid`; second immediate call → `409`
  - **ACC-02**: `curl -X POST .../api/pipeline/pause ...` then `.../status` → `state:"paused"`; `.../resume` → `state:"running"`
  - **ACC-03**: `curl -X POST .../api/pipeline/kill ...` → run pid gone, lock released, history row `outcome:"killed"`
  - **ACC-04**: `curl -X POST .../api/pipeline/watcher -d '{"enabled":false}'` → `watcher.paused` sentinel present; watch loop no-ops
  - **ACC-05**: `curl .../api/pipeline/history` → the run appears with per-step timings in `steps_json`
  - **ACC-06**: Frontend: `npm run typecheck` 0, `npm run lint` 0 (zero `no-explicit-any`), DS-adherence green
  - **ACC-07**: Frontend: visit `/pipeline`, click Démarrer → dialog with dry-run switch → confirm → status flips to `running`, stepper advances, logs appear live, pause/kill buttons become active
  - **ACC-08**: History table shows the run with correct outcome, click row → detail shows per-step timings

### 6.2 — OpenAPI regeneration + CI gate

**Files:**

- Modify: `frontend/openapi.json` (regenerated)
- Modify: `frontend/src/api/schema.d.ts` (regenerated)

**Commit:** `chore(pipe-control): regenerate OpenAPI + frontend schema.d.ts for pipeline routes`

- Run `make openapi` to regenerate `frontend/openapi.json` from the new pipeline routes + models.
- Run `npm run generate-types` (or equivalent) in the frontend to regenerate `schema.d.ts`.
- Verify CI: backend job's `diff` guard on `frontend/openapi.json` must pass.
- Verify CI: frontend job's `typecheck` must pass with the new types.
- Staging validation:
  - Deploy branch to staging (`git push origin feat/pipe-control:staging`).
  - Visit `https://tm-staging.iznogoudatall.xyz/pipeline` via Orca browser.
  - Run through ACC-01 → ACC-08 manually.
  - Verify WS events appear in the log feed.
  - Check PM2 logs for any errors: `pm2 logs torrentmate-web-staging --lines 50`.

## Files touched this phase

| Operation | File                                       |
| --------- | ------------------------------------------ |
| Modify    | `docs/reference/web-ui.md`                 |
| Modify    | `docs/reference/commands.md`               |
| Create    | `docs/features/pipe-control/ACCEPTANCE.md` |
| Modify    | `frontend/openapi.json`                    |
| Modify    | `frontend/src/api/schema.d.ts`             |
