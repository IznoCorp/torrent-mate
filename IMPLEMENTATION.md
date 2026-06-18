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
| 2a  | Red tests for `library-dedup-titles`                     | phase-02a-dedup-tests.md   | [x]    |
| 2b  | Implement `library-dedup-titles` (green) + 2.3 guard fix | phase-02b-dedup-impl.md    | [x]    |
| 3   | Live remediation + ACC re-exercise + gate                | phase-03-gate.md           | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to execute phase 3 (live remediation + ACC re-exercise + gate).

**Note (phase 2):** an extra bugfix sub-phase 2.3 was added — the
`library-dedup-titles` dispatch_path guard compared raw path strings, wrongly
skipping NFC/NFD twins whose `dispatch_path` differs only by Unicode
normalization (found via real-DB dry-run: 10/14 groups skipped → now NFC-normalized,
12 groups detected, 1 legitimately skipped). Commit `8039e458`.
