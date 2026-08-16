# webui-ux — Implementation Plan

Post-S7 web-UI UX polish + full-interface overhaul. Code-grounded from a 3-agent survey of the
live frontend + backend (file:line refs in `../DESIGN.md`).

## Phases

| #   | Phase                                | File                      | Status |
| --- | ------------------------------------ | ------------------------- | ------ |
| 1   | Quick presentation fixes             | phase-01-quick-fixes.md   | [ ]    |
| 2   | Pipeline page UX                     | phase-02-pipeline-ux.md   | [ ]    |
| 3   | Config SchemaForm redesign           | phase-03-config-form.md   | [ ]    |
| 4   | Scraping refonte + parallel scraping | phase-04-scraping.md      | [ ]    |
| 5   | Dashboard reorg + scheduler overview | phase-05-dashboard.md     | [ ]    |
| 6   | Backend fold-in — follow dedup       | phase-06-follow-dedup.md  | [ ]    |
| 7   | Full-interface UX overhaul loop      | phase-07-overhaul-loop.md | [ ]    |

## Ordering rationale

1–2 are low-risk presentation/frontend wins (fast operator payoff). 3 is a self-contained frontend
redesign. 4 carries the only real safety design (scoped scrape-lock) — done after the easy wins so
the branch is already validated on staging. 5 adds one typed endpoint + relocation. 6 is an
isolated backend migration. 7 is the iterative Chrome-on-staging overhaul over every page, run last
so it audits the finished Part-A surfaces too.

## Cross-cutting constraints (every phase)

- Frontend gate before each commit: `npm run lint && npm run typecheck && npx vitest run`.
- Backend gate: `make check`; any route/response_model change ⇒ `make openapi` + commit
  `frontend/openapi.json` + `frontend/src/api/schema.d.ts`.
- No S1–S7 regressions: `require_not_staging` on mutations, single `guarded_api` perimeter,
  runners hold `pipeline.lock` lifetime, epoch step timestamps.
- Preview/test on staging only (never a local server on 8710/8711).
