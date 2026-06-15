# Implementation Progress — seed-pure

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Seed Safety O1: seed-pure tag + pipeline skip (+ manual tagger) (minor)
**Version bump**: 0.32.0 → 0.33.0
**Branch**: feat/seed-pure
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/seed-pure/DESIGN.md
**Master plan**: docs/features/seed-pure/plan/INDEX.md

## Phases

| #   | Phase                         | File                             | Status |
| --- | ----------------------------- | -------------------------------- | ------ |
| 1   | Tag vocab + tagger capability | phase-01-tag-vocab-tagger.md     | [x]    |
| 2   | `seed` CLI group              | phase-02-seed-cli.md             | [ ]    |
| 3   | Ingest skip (always-on)       | phase-03-ingest-skip.md          | [ ]    |
| 4   | Opt-in sort/process guard     | phase-04-optional-guard.md       | [ ]    |
| 5   | Docs + ACCEPTANCE + gate      | phase-05-docs-acceptance-gate.md | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

Run `/implement:phase` to start Phase 2 (`seed` CLI group).
