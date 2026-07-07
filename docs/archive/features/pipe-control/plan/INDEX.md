# pipe-control — Implementation Plan

> **Feature:** S2 Pipeline control (TorrentMate Web UI wave 2)
> **Ticket:** [#181](https://github.com/izno/PersonalScraper/issues/181)
> **DESIGN:** `docs/features/pipe-control/DESIGN.md`
> **Branch:** `feat/pipe-control`
> **SemVer:** 0.40.0 → 0.41.0 (minor bump, `feat`)

## Phases

| #   | Phase                                                               | File                                                         | Status |
| --- | ------------------------------------------------------------------- | ------------------------------------------------------------ | ------ |
| 1   | Engine — pause checkpoint + run-history                             | [phase-01-engine.md](phase-01-engine.md)                     | [ ]    |
| 2   | Web controls — run/pause/resume/kill/watcher/status                 | [phase-02-web-controls.md](phase-02-web-controls.md)         | [ ]    |
| 3   | Web history — history + detail routes                               | [phase-03-web-history.md](phase-03-web-history.md)           | [ ]    |
| 4   | Frontend control screen — Pipeline page + controls + stepper + logs | [phase-04-frontend-control.md](phase-04-frontend-control.md) | [ ]    |
| 5   | Frontend history — run-history table + detail                       | [phase-05-frontend-history.md](phase-05-frontend-history.md) | [ ]    |
| 6   | Deploy rails + docs + ACCEPTANCE                                    | [phase-06-deploy-docs.md](phase-06-deploy-docs.md)           | [ ]    |

## Global Constraints

- **Single trigger authority** — every write passes through `pipeline.lock`; EventBus is observe-only for the web.
- **Sync engine, async only at the WS relay** — route handlers are sync `def` on the threadpool.
- **Auth + CSRF** — all `/api/*` under `require_session`; mutating POSTs carry `X-Requested-With: TorrentMate`.
- **DS-strict frontend** — shadcn + TanStack + domain primitives; zero raw hex/px; FR-leading copy; EN machine tokens.
- **Pre-1.0 no back-compat** — schema + config evolve in place on the single instance.
- **Sub-phases = 1 commit** — scope `(pipe-control)`, conventional-commits format.
