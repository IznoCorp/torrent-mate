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

| #   | Phase                                                    | File                         | Status |
| --- | -------------------------------------------------------- | ---------------------------- | ------ |
| 1   | Root-cause `_canonical_title` NFC fix + regression tests | phase-01-root-cause-fix.md   | [x]    |
| 2a  | Red tests for `library-dedup-titles`                     | phase-02a-dedup-tests.md     | [x]    |
| 2b  | Implement `library-dedup-titles` (green) + 2.3 guard fix | phase-02b-dedup-impl.md      | [x]    |
| 3   | Live remediation + ACC re-exercise + gate                | phase-03-gate.md             | [x]    |
| 4   | PR fixes cycle 1 — dispatch_path guard hardening + tests | phase-04-pr-fixes-cycle-1.md | [x]    |

## Review cycles

### Cycle 1

3 review agents (code-reviewer, silent-failure-hunter, pr-test-analyzer) converged on
one critical issue in `library-dedup-titles`: the `dispatch_path` safety guard
(`{p for p in paths.values() if p is not None}`) makes a missing/empty `dispatch_path`
invisible, so a group with one path-bearing + one path-less row passes the guard, and
`_select_survivor` (path-agnostic) can keep the path-less row and cascade-delete the
verifiable one — a silent data-loss path contradicting DESIGN's "missing dispatch_path
→ skip, never guess" contract. Retained findings (fixed in phase 4 / cycle 1):

- **critical** — guard must require every member to have a non-empty NFC-matching path, else skip.
- **medium** — empty-string path → None; `--db` existence guard; `_canonical_key` docstring (no real `lower()` indexer dedup).
- **critical coverage** — test skip-branch (divergent real paths) + partial-None (path-bearing row preserved) + CASCADE + idempotent `normalized==0`.
- **minor** — guard survivor normalize with `_is_nfd` (count inflation).

Ignored (non-blocking LOW): F4 skipped-not-surfaced-prominently, F5 rowcount-vs-pre-count.
Live run was already safe (all 12 survivors had matching paths; 0 suspect) — fix is for
future robustness + the merge gate.

### Cycle 2

Clean — all cycle-1 findings resolved and verified (commit `66b7ffcf`, phase 4 gate
`a5c858e4`, CI green). Guard now skips any group with a missing/empty or NFC-divergent
`dispatch_path` (`dispatch_path_unverifiable`); the critical data-loss path is locked by
`test_apply_skips_partial_none_dispatch_path` (red→green: the path-bearing row must NOT be
deleted), plus skip-divergent, CASCADE, and idempotent-`normalized` tests. F2/F3/docstring/
minor confirmed in the diff. make test 7127, lint clean, CI 8/8 green. No new
critical/major/medium findings → Case A, proceed to squash merge. (Cycle-2 re-review run
inline: the toolkit subagents hit their weekly limit; verification done by direct diff +
test inspection + the green CI gate.)

## Next action

Review clean (cycle 2). Auto-squash-merge PR #208 on CI green, then post-merge archive.

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
