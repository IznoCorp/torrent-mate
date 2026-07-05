# Implementation Plan — tm-shell (TorrentMate UI S1)

**Design**: `docs/features/tm-shell/DESIGN.md`
**Branch**: `feat/tm-shell` · **Ticket**: #158
**Bump**: minor 0.39.0 → 0.40.0 (already applied at branch creation)

## Phases

| #   | Phase                                                                | File                              | Status |
| --- | -------------------------------------------------------------------- | --------------------------------- | ------ |
| 1   | Backend skeleton (web/ package, config, health/version, CLI, PM2)    | phase-01-backend-skeleton.md      | [ ]    |
| 2   | Auth (passwords, JWT, guard, routes, set-password)                   | phase-02-auth.md                  | [ ]    |
| 3   | Event relay (RedisEventPublisher, WS relay, replay, producer wiring) | phase-03-event-relay.md           | [ ]    |
| 4   | Frontend scaffold (Vite/TS/shadcn/DS tokens/OpenAPI client/CI job)   | phase-04-frontend-scaffold.md     | [ ]    |
| 5   | App shell + auth flow (login, layout, router, auth guard)            | phase-05-shell-auth-flow.md       | [ ]    |
| 6   | EventStream + dashboard (useEventStream hook, live feed, cards)      | phase-06-eventstream-dashboard.md | [ ]    |
| 7   | PWA (manifest, service worker, auto-update, install prompts)         | phase-07-pwa.md                   | [ ]    |
| 8   | Deploy rails (scripts, autodeploy, Caddy, staging branch, docs)      | phase-08-deploy-rails.md          | [ ]    |

## Dependency graph

```
1 ──> 2 ──> 3 ──> 4 ──> 5 ──> 6 ──> 7 ──> 8
```

Phases 2–3 can run in parallel if separate agents, but each depends on 1.
Phase 4 depends on 1–3 (backend API surface needed for OpenAPI export).
Phase 5 needs the typed API client from 4. Phase 6 needs the shell + auth
context from 5. Phase 7 needs the dashboard from 6. Phase 8 is last.

## Quality gates (every phase)

- `make lint` zero errors (ruff + mypy, plus `check_logging.py` on new modules)
- `make test` all tests pass; new coverage ≥ 90% on `personalscraper/web/`
- Module size ≤ 800 LOC soft (run `python scripts/check-module-size.py`)
- No AI attribution in commits; Conventional Commits format
- Phase gate commit format: `chore(tm-shell): phase N gate — <summary>`
