# Implementation Progress — pipe-control

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Pipeline control (S2 web UI — start/pause/kill, live logs, run history)
**Type**: feat
**Version bump**: 0.40.0 → 0.41.0 (minor)
**Branch**: feat/pipe-control
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/pipe-control/DESIGN.md
**Master plan**: docs/features/pipe-control/plan/INDEX.md

## Phases

| #   | Phase                                                    | File                         | Status |
| --- | -------------------------------------------------------- | ---------------------------- | ------ |
| 1   | Engine — pause checkpoint + run-history                  | phase-01-engine.md           | [x]    |
| 2   | Web controls — run/pause/resume/kill/watcher/status      | phase-02-web-controls.md     | [x]    |
| 3   | Web history — history + detail routes                    | phase-03-web-history.md      | [ ]    |
| 4   | Frontend control screen — Pipeline page + stepper + logs | phase-04-frontend-control.md | [ ]    |
| 5   | Frontend history — run-history table + detail            | phase-05-frontend-history.md | [ ]    |
| 6   | Deploy rails + docs + ACCEPTANCE                         | phase-06-deploy-docs.md      | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to continue with Phase 3 (web history).
