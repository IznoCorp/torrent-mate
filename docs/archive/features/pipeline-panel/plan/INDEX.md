# Implementation Plan — pipeline-panel

**Feature**: pipeline-panel (Design overhaul V3: Pipeline)
**Epic**: #304, **Ticket**: #307
**Binding spec**: `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §2.3 + §1.1
**Branch**: `feat/pipeline-panel`
**Merge mode**: auto
**Codename**: pipeline-panel

## Phase table

| #   | Phase                                        | File                                                                 | Status |
| --- | -------------------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Stepper compression + always-visible anomaly | [phase-01-stepper-compression.md](phase-01-stepper-compression.md)   | [ ]    |
| 2   | History repatriation + legend popover        | [phase-02-history-repatriation.md](phase-02-history-repatriation.md) | [ ]    |
| 3   | `/maintenance?run=` redirect wrapper         | [phase-03-redirect-wrapper.md](phase-03-redirect-wrapper.md)         | [ ]    |
| 4   | Final gate                                   | [phase-04-final-gate.md](phase-04-final-gate.md)                     | [ ]    |

## Hard guardrails

1. **ZERO backend change** — no Python, no OpenAPI regen, no endpoint signatures touched.
2. **Maintenance loses ONLY** the `RunHistoryTable kind="pipeline"` row — everything else stays.
3. **No route removals** — `/maintenance` stays live; `/pipeline` unchanged.
4. **REUSE, never rewrite** — FlowBoard drawer, RunHistoryTable, RunDetail, LegacyRedirect all kept as-is.
5. **Per-commit gate**: `cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run`
6. **Existing suites migrate** in the same phase as their surface.
