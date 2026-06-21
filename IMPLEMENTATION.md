# Implementation Progress — tiller

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Interactive agent terminal + operator control from KanbanMateUI (ticket #47) (minor)
**Version bump**: 0.14.0 → 0.15.0 (resync VERSION + pyproject + `__init__`; the stale `VERSION` file
was at 0.11.0)
**Branch**: feat/tiller
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/tiller/DESIGN.md
**Master plan**: docs/features/tiller/plan/INDEX.md

## Phases

| #   | Phase                              | File                             | Status |
| --- | ---------------------------------- | -------------------------------- | ------ |
| 1   | Backend terminal                   | phase-01-backend-terminal.md     | [x]    |
| 2   | Frontend terminal                  | phase-02-frontend-terminal.md    | [x]    |
| 3   | Editable description (marker-safe) | phase-03-editable-description.md | [x]    |
| 4   | UI finishes                        | phase-04-ui-finishes.md          | [x]    |
| 5   | Final gate + ACCEPTANCE            | phase-05-final-gate.md           | [x]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

All 5 phases complete + `make check` green. Push `feat/tiller` and open the PR; deploy via the #57
guardrails (staging for test verification, then `scripts/deploy.sh` from `main` on merge — never from
this dev worktree).
