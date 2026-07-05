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

| #   | Phase                                                                | File                              | Status |
| --- | -------------------------------------------------------------------- | --------------------------------- | ------ |
| 1   | Backend skeleton (web/ package, config, health/version, CLI, PM2)    | phase-01-backend-skeleton.md      | [x]    |
| 2   | Auth (passwords, JWT, guard, routes, set-password)                   | phase-02-auth.md                  | [x]    |
| 3   | Event relay (RedisEventPublisher, WS relay, replay, producer wiring) | phase-03-event-relay.md           | [x]    |
| 4   | Frontend scaffold (Vite/TS/shadcn/DS tokens/OpenAPI client/CI job)   | phase-04-frontend-scaffold.md     | [x]    |
| 5   | App shell + auth flow (login, layout, router, auth guard)            | phase-05-shell-auth-flow.md       | [x]    |
| 6   | EventStream + dashboard (useEventStream hook, live feed, cards)      | phase-06-eventstream-dashboard.md | [x]    |
| 7   | PWA (manifest, service worker, auto-update, install prompts)         | phase-07-pwa.md                   | [x]    |
| 8   | Deploy rails (scripts, autodeploy, Caddy, staging branch, docs)      | phase-08-deploy-rails.md          | [x]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

All phases complete — run `/implement:feature-pr` (push + PR + CI), then
`/implement:pr-review` (manual merge).

> **Post-audit note**: after phase 7, a comprehensive guarantor audit (57 agents,
> adversarial verify) confirmed 40 findings across backend, frontend, relay, PWA,
> tests, and deploy. ALL were fixed (fix-waves A–E + inline), each with a
> regression test; live `/chrome` desktop+mobile validation and full ACCEPTANCE
> re-exercise pass. Backend 7619 tests / frontend 74 tests / lint 0 issues.
