# Implementation Progress — acquire-events

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP4 — acquisition event catalog + muted Telegram subscriber (minor)
**Version bump**: 0.26.0 → 0.27.0
**Branch**: feat/acquire-events
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/acquire-events/DESIGN.md
**Master plan**: docs/features/acquire-events/plan/INDEX.md

## Phases

| #   | Phase                                                            | File                   | Status |
| --- | ---------------------------------------------------------------- | ---------------------- | ------ |
| 1   | Event catalog (acquire/events.py) + hub registration + factories | phase-01-events.md     | [x]    |
| 2   | Muted Telegram subscriber + config flag + CLI wiring             | phase-02-subscriber.md | [x]    |
| 3   | Docs update + ACCEPTANCE.md + make check gate                    | phase-03-docs-gate.md  | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 3 (docs + ACCEPTANCE + gate).
