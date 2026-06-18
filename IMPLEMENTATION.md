# Implementation Progress — nfc-dedup

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Fix NFD/NFC + year-in-title duplicate-row pollution in indexer upsert dedup (bugfix)
**Version bump**: 0.36.1 → 0.36.2
**Branch**: fix/nfc-dedup
**PR merge**: auto
**PR**: https://github.com/IznoCorp/personal-scraper/pull/208
**Design**: docs/features/nfc-dedup/DESIGN.md
**Master plan**: docs/features/nfc-dedup/plan/INDEX.md

## Phases

| #   | Phase                                                    | File                       | Status |
| --- | -------------------------------------------------------- | -------------------------- | ------ |
| 1   | Root-cause `_canonical_title` NFC fix + regression tests | phase-01-root-cause-fix.md | [x]    |
| 2a  | Red tests for `library-dedup-titles`                     | phase-02a-dedup-tests.md   | [x]    |
| 2b  | Implement `library-dedup-titles` (green) + 2.3 guard fix | phase-02b-dedup-impl.md    | [x]    |
| 3   | Live remediation + ACC re-exercise + gate                | phase-03-gate.md           | [x]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

All phases complete — `/implement:feature-pr` (push + PR + CI), then `/implement:pr-review` (auto-merge).

**Note (phase 2):** an extra bugfix sub-phase 2.3 was added — the
`library-dedup-titles` dispatch_path guard compared raw path strings, wrongly
skipping NFC/NFD twins whose `dispatch_path` differs only by Unicode
normalization (found via real-DB dry-run: 10/14 groups skipped → now NFC-normalized,
12 groups detected, 1 legitimately skipped). Commit `8039e458`.

**Note (phase 3 — live remediation, operator-authorized 2026-06-18):**

- `library-dedup-titles --apply` on `.data/library.db`: deleted 12 NFC/NFD orphan
  rows, normalized 438 NFD titles (1909→1897 rows, NULL-valid 13→4). Backup at
  `.data/library.db.bak-nfc-dedup-560239ef`.
- 2 same-folder dups outside NFC/NFD scope deleted manually with sign-off — id 1142
  (trailing non-breaking space) + id 1122 (year column 2011 vs live twin's 2010);
  kept live twins 3185/3187 (NULL-valid 4→2, rows 1897→1895).
- 2 true orphans repaired (504, 1438): on-disk NFO renamed to the scanner-expected
  `<folder-title>.nfo`, surgically re-staged → nfo=valid + drefr set (NULL-valid 2→0).
- **Goal reached: NULL-valid 13 → 0.** Sub-phase 3.2 added command docs + a
  solo-NFD-normalize regression test (commit `d7c3c132`).
- Documented residual (out of scope, no action): `Les Griffes de la nuit` (1984),
  ids 492/3234 — two physically-distinct on-disk folders (case-variant), both live;
  the command correctly skips it. ACC-4 expected value updated to 1.
