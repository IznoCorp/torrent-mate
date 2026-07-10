# Scrape Arbiter — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Interactive scraping decision queue — batch runs enqueue ambiguous/low-confidence
items, the operator resolves them from the web UI, a detached runner re-scrapes with the
chosen provider ID.

**Architecture:** One new `scrape_decision` table in `library.db` (migration 013), a
`DecisionWriter` (short-lived DB connections, fail-soft), a `scrape-resolve` CLI
(self-locking, fetch-by-ID), a web runner (S3 pattern), a `/api/decisions/*` REST surface,
and a `/decisions` frontend page (mobile-first, shadcn/TanStack).

**Tech Stack:** Python 3.12+ (FastAPI, Pydantic, sqlite3, subprocess), TypeScript strict
(React 19, TanStack Query, shadcn/ui, Vitest), SQLite WAL, Redis pub/sub → WebSocket.

## Global Constraints

- Typed routes → `make openapi` → `schema.d.ts`; any route change ⇒ commit regenerated files.
- Auth perimeter: single `guarded_api` router; never add per-route `Depends(require_session)`.
- Write routes: `require_not_staging` + XRW (`require_x_requested_with`) on mutations.
- Pipeline-lock: `scrape-resolve` self-acquires (`_CLI_SELF_LOCKING`) — web runner does NOT
  double-acquire (R11).
- Timestamps: epoch `time.time()` on `created_at`, `updated_at`, `resolved_at`.
- NFC normalization: `staging_path` always NFC-normalized before DB insert (macFUSE NFD
  gotcha per `docs/reference/web-ui.md`).
- Frontend: lint + typecheck + vitest triple gate before every commit.
- Commit scope: `scrape-arbiter`; Conventional Commits format.
- All new modules use `personalscraper.logger.get_logger` (not `structlog.get_logger`).

---

## Phases

| #   | Phase                                                                               | File                                                           | Status |
| --- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------ |
| 1   | Migration 013 + DecisionWriter + confidence.py candidate surfacing + enqueue wiring | [phase-01-migration-enqueue.md](phase-01-migration-enqueue.md) | [ ]    |
| 2   | scrape-resolve CLI + web runner + journal wiring                                    | [phase-02-cli-runner.md](phase-02-cli-runner.md)               | [ ]    |
| 3   | REST routes + models + OpenAPI regen                                                | [phase-03-rest-routes.md](phase-03-rest-routes.md)             | [ ]    |
| 4   | Frontend /decisions page + badge + typed client                                     | [phase-04-frontend.md](phase-04-frontend.md)                   | [ ]    |
| 5   | Integration gates + ACC + docs                                                      | [phase-05-integration.md](phase-05-integration.md)             | [ ]    |
