# Implementation Progress — nfc-dedup

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Fix NFD/NFC + year-in-title duplicate-row pollution in indexer upsert dedup (bugfix)
**Version bump**: 0.36.1 → 0.36.2
**Branch**: fix/nfc-dedup
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/nfc-dedup/DESIGN.md
**Master plan**: docs/features/nfc-dedup/plan/INDEX.md

## Phases

| #   | Phase                                                    | File                       | Status |
| --- | -------------------------------------------------------- | -------------------------- | ------ |
| 1   | Root-cause `_canonical_title` NFC fix + regression tests | phase-01-root-cause-fix.md | [x]    |
| 2a  | Red tests for `library-dedup-titles`                     | phase-02a-dedup-tests.md   | [ ]    |
| 2b  | Implement `library-dedup-titles` (green)                 | phase-02b-dedup-impl.md    | [ ]    |
| 3   | Live remediation + ACC re-exercise + gate                | phase-03-gate.md           | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to execute phase 2a (red tests for `library-dedup-titles`).
