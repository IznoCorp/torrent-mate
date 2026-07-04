# Implementation Progress — tm-shell

> For Claude: read this file at session start. Current feature tracker.

**Feature**: TorrentMate UI S1 — shell + auth + WebSocket foundation
**Type**: feat
**Version bump**: 0.39.0 → 0.40.0 (minor)
**Branch**: feat/tm-shell
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/tm-shell/DESIGN.md
**Master plan**: docs/features/tm-shell/plan/INDEX.md
**Ticket**: #158 (KanbanMate — claimed, heartbeat active)

## Phases

| #   | Phase                                                                 | File                              | Status |
| --- | --------------------------------------------------------------------- | --------------------------------- | ------ |
| 1   | Backend skeleton (web/ package, config, health/version, CLI, PM2)    | phase-01-backend-skeleton.md      | [ ]    |
| 2   | Auth (passwords, JWT, guard, routes, set-password)                   | phase-02-auth.md                  | [ ]    |
| 3   | Event relay (RedisEventPublisher, WS relay, replay, producer wiring) | phase-03-event-relay.md           | [ ]    |
| 4   | Frontend scaffold (Vite/TS/shadcn/DS tokens/OpenAPI client/CI job)   | phase-04-frontend-scaffold.md     | [ ]    |
| 5   | App shell + auth flow (login, layout, router, auth guard)            | phase-05-shell-auth-flow.md       | [ ]    |
| 6   | EventStream + dashboard (useEventStream hook, live feed, cards)      | phase-06-eventstream-dashboard.md | [ ]    |
| 7   | PWA (manifest, service worker, auto-update, install prompts)         | phase-07-pwa.md                   | [ ]    |
| 8   | Deploy rails (scripts, autodeploy, Caddy, staging branch, docs)      | phase-08-deploy-rails.md          | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 1.
