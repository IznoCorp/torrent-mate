# nfc-dedup Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix NFD/NFC Unicode normalization mismatch in `_canonical_title` that causes
duplicate `media_item` rows for accented titles, and provide a one-shot maintenance
command to clean up the 14 existing duplicate groups.

**Architecture:** Single-point fix in `_canonical_title` (item_repo.py) covers both
the upsert store-path and the lookup-path. A `library-dedup-titles` maintenance
command (mirroring `library-fix-orphan-files`) handles the existing duplicates and
NFC-normalizes all NFD-titled rows. The 2 true orphans (ids 504, 1438) are repaired
by re-staging after an on-disk NFO rename.

**Tech Stack:** Python stdlib `unicodedata`, SQLite `ON DELETE CASCADE`,
Typer CLI, pytest, `personalscraper.logger.get_logger`.

**Branch:** `fix/nfc-dedup`  
**Type:** bugfix (0.36.1 → 0.36.2)

---

## Phase Overview

| Phase | File                                                     | Scope                                            | Gate dependency          |
| ----- | -------------------------------------------------------- | ------------------------------------------------ | ------------------------ |
| 1     | [phase-01-root-cause-fix.md](phase-01-root-cause-fix.md) | `_canonical_title` NFC fix + 2 regression tests  | none                     |
| 2a    | [phase-02a-dedup-tests.md](phase-02a-dedup-tests.md)     | Red tests for `library-dedup-titles`             | phase 1 merged-ready     |
| 2b    | [phase-02b-dedup-impl.md](phase-02b-dedup-impl.md)       | Implement `library-dedup-titles` (green)         | phase 2a committed       |
| 3     | [phase-03-gate.md](phase-03-gate.md)                     | Live remediation + ACC re-exercise + gate commit | phases 1+2b merged-ready |

## Sub-phase → commit mapping

| Sub-phase | Commit message                                                             |
| --------- | -------------------------------------------------------------------------- |
| 1.1       | `test(nfc-dedup): red tests — _canonical_title NFC + upsert no-dup`        |
| 1.2       | `fix(nfc-dedup): NFC-normalize _canonical_title — stop NFD duplicate rows` |
| 2.1       | `test(nfc-dedup): red tests — library-dedup-titles dry-run + apply`        |
| 2.2       | `feat(nfc-dedup): library-dedup-titles command`                            |
| 3.1       | `chore(nfc-dedup): phase 3 gate — live remediation + ACC-1..ACC-6 green`   |

## Key files

| File                                               | Action                                                          |
| -------------------------------------------------- | --------------------------------------------------------------- |
| `personalscraper/indexer/repos/item_repo.py`       | Modify `_canonical_title` (add `unicodedata` import + NFC call) |
| `personalscraper/commands/library/dedup_titles.py` | Create — `library-dedup-titles` command                         |
| `tests/indexer/test_canonical_title_nfc.py`        | Create — regression tests for phase 1                           |
| `tests/integration/test_dedup_titles.py`           | Create — command tests for phase 2                              |
