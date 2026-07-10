# acq-watch Implementation Plan — Phase Index

> **Branch**: `feat/acq-watch` | **Design**: `docs/features/acq-watch/DESIGN.md`
> **Bump**: minor (`0.46.0 → 0.47.0`) | **Commit type**: `feat`

## Phases

| N   | Phase                         | Plan                                                       | Status |
| --- | ----------------------------- | ---------------------------------------------------------- | ------ |
| 1   | Read routes + models          | [phase-01-read-routes.md](phase-01-read-routes.md)         | [ ]    |
| 2   | Write routes                  | [phase-02-write-routes.md](phase-02-write-routes.md)       | [ ]    |
| 3   | Frontend typed client + hooks | [phase-03-frontend-client.md](phase-03-frontend-client.md) | [ ]    |
| 4   | Frontend page                 | [phase-04-frontend-page.md](phase-04-frontend-page.md)     | [ ]    |
| 5   | Integration + ACC + docs      | [phase-05-integration-acc.md](phase-05-integration-acc.md) | [ ]    |

## Gate summary

| Phase | Gate                                                                                |
| ----- | ----------------------------------------------------------------------------------- |
| 1     | `make check` + `make openapi` + commit regen                                        |
| 2     | `make check` + `make openapi` + commit regen                                        |
| 3     | `cd frontend && npm run lint && npm run typecheck && npx vitest run`                |
| 4     | `make check` + `cd frontend && npm run lint && npm run typecheck && npx vitest run` |
| 5     | `make check` + frontend triple gate + design-gaps + feature-map + ACC re-exercise   |
