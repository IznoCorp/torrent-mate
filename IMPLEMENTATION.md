# Implementation Progress — follow-list

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Follow D1 — followed-series list (store CRUD + `follow` CLI) (minor)
**Version bump**: 0.28.0 → 0.29.0
**Branch**: feat/follow-list
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/197
**Design**: docs/features/follow-list/DESIGN.md
**Master plan**: docs/features/follow-list/plan/INDEX.md

## Phases

| #   | Phase                                                       | File               | Status |
| --- | ----------------------------------------------------------- | ------------------ | ------ |
| 1   | Store CRUD (_FollowSubStore completion + Protocol)          | phase-01-store.md  | [x]    |
| 2   | Title resolution helper (fail-soft metadata lookup)         | phase-02-title.md  | [x]    |
| 3   | follow CLI command group (add/list/remove)                  | phase-03-cli.md    | [x]    |
| 4   | Docs + ACCEPTANCE + gate                                    | phase-04-gate.md   | [x]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

All phases complete — run `/implement:feature-pr`.
