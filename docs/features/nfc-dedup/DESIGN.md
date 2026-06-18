# Design — nfc-dedup

**Type**: bugfix (0.36.1 → 0.36.2)
**Codename**: nfc-dedup
**Date**: 2026-06-18

## Problem

The media indexer accumulates **duplicate `media_item` rows** for titles
containing accented characters. In the current 1909-row production DB there are
**14 exact duplicate groups** (same title + kind + year) and 31 groups when the
year is ignored. Each duplicate pair is a **stale orphan**
(`date_metadata_refreshed IS NULL`) plus a **live twin** (`date_metadata_refreshed`
set), and **both rows point at the same physical folder**. The orphans are the
13 items a full re-scan could never backfill (the trigger for this work).

## Root cause (verified live)

`personalscraper/indexer/repos/item_repo.py::get_by_title_kind_year()` deduplicates
via a raw SQLite `title = ?` byte comparison, after `_canonical_title()` strips a
trailing ` (YYYY)` suffix. **`_canonical_title()` does not Unicode-normalize.**

macOS / macFUSE `iterdir()` returns folder names in **NFD** (decomposed:
`Fantômes` = `o` + combining circumflex), while the DB stores titles in
**NFC** (precomposed: `Fant\xf4mes`). When a full scan
(`stage_library_items` pass-1) walks an accented-title folder, the NFD lookup
misses the existing NFC row and the upsert falls through to **INSERT a new NFD
duplicate row**. Every subsequent scan refreshes the NFD twin and leaves the NFC
orphan untouched.

Hard evidence:

- `get_by_title_kind_year(NFD 'Fantômes contre fantômes', movie, 1996)` → `id=3232` (NFD dup)
- `get_by_title_kind_year(NFC 'Fant\xf4mes contre fant\xf4mes', movie, 1996)` → `id=3222` (orphan)
- `scan_run 68` (full `--no-budget`) backfilled **0/13** NULL-valid items.
- The `dispatch_normalized_title` attribute already stores an NFC-normalized
  title for the dispatch layer (`find_by_normalized_name`), but the indexer
  upsert dedup ignores it.

A second, smaller defect: **2 true orphans** (`id=504`
`insidious the last key 2018 light ()`, `id=1438` `L'Exoconference (2014)`) have
no duplicate — their on-disk NFO filename does not match the scanner's expected
`<folder-title>.nfo` (the real file carries the year or the folder name carries
trailing garbage `()`), so they evaluate `nfo_status='invalid'` at scan time.

## Goals

1. Stop new duplicate rows forming when an NFD-named folder is scanned.
2. Clean up the existing duplicate pairs without deleting legitimately-distinct
   year-variants / remakes.
3. Repair the 2 true orphans so the library reaches **0 NULL-valid** items.
4. Lock the fix with regression tests (one per bug).

## Non-goals

- No schema migration script (pre-1.0 — evolve data in place).
- No convergence/auto-heal pass inside the scanner (the `_canonical_title` fix
  prevents recurrence, so a recurring auto-delete is unnecessary and riskier).
- No change to the dispatch layer (already NFC-correct via
  `dispatch_normalized_title`).

## Approach

### 1. Root-cause code fix — NFC-normalize `_canonical_title`

`_canonical_title()` (`item_repo.py`) is the single choke point: it is called by
both `upsert()` (store path, L421) and `get_by_title_kind_year()` (lookup path,
L520). NFC-normalize there:

```python
canonical = unicodedata.normalize("NFC", stripped_title)
```

Effect: new rows are stored NFC-canonical, and NFD-from-disk lookups normalize to
NFC and match the existing NFC row → no new duplicate is inserted. Single-point
fix covering all callers.

### 2 + 3. One-shot maintenance command — `library-dedup-titles`

New CLI command mirroring `library-fix-orphan-files` (default **dry-run**;
`--apply` to mutate; `--db` to override path; a `DedupTitlesStats` dataclass via
`_fix_stats_base.py`).

Algorithm:

1. Load all `media_item` rows. Group by `(NFC(canonical_title).lower(), kind, year)`.
2. For each group with > 1 row → a **duplicate group**. Within it:
   - **Guard against false merges**: only treat rows as duplicates of each other
     when they resolve to the **same physical folder** (identical
     `dispatch_path` attribute, or both pointing at an existing identical path).
     Year-variants/remakes (e.g. The Killing 2010 vs 2011) differ by year already
     (separate groups) and additionally by `dispatch_path` — never merged.
   - **Survivor selection**: keep the **live** row (has `dispatch_path` + the
     most-recent `date_metadata_refreshed`, tie-break: highest `id`). NFC-normalize
     the survivor's `title` in place.
   - **Delete** the other rows in the group (`ON DELETE CASCADE` removes
     seasons / releases / files / attributes).
3. Separately, NFC-normalize the `title` of any **non-duplicated** row whose
   stored title is NFD (so the column is uniformly NFC even where no twin exists).
4. `--dry-run` prints the full plan (groups, survivor, deletions, normalizations,
   counts) and mutates nothing. `--apply` performs the writes inside one
   transaction, then `PRAGMA wal_checkpoint(TRUNCATE)`.

### 4. Regression tests (test-per-bug)

- `_canonical_title` NFC: an NFD input with a year suffix returns the NFC base.
- Upsert no-dup: staging an NFD-named folder when an NFC row already exists
  performs an UPDATE (no second row) — reproduces the bug, must pass after fix.
- `library-dedup-titles` dry-run: reports the pairs, mutates nothing.
- `library-dedup-titles --apply`: deletes orphans, keeps live, normalizes titles,
  preserves distinct year-variants.

### 5. Repair the 2 true orphans (504, 1438)

Case-by-case on-disk fix (not a general code change): rename the NFO to the
scanner-expected `<folder-title>.nfo` (and, for 504, the folder's trailing ` ()`
garbage), then re-stage. If a code touch is warranted, it is limited to making
`_nfo_metadata_for_dir` fall back to a single `*.nfo` when `<title>.nfo` is
absent — decided during implementation; the on-disk rename is the baseline.

## Components / interfaces

| Unit                                       | Responsibility                                                         |
| ------------------------------------------ | ---------------------------------------------------------------------- |
| `_canonical_title` (item_repo.py)          | NFC-normalize + strip year. Single dedup key source.                   |
| `library-dedup-titles` (commands/library/) | One-shot dry-run/apply title-NFC + orphan-dedup maintenance.           |
| `DedupTitlesStats`                         | Snapshot counters (groups, deleted, normalized) via `_fix_stats_base`. |

## Error handling

- Command is fail-soft per the `library-fix-*` convention: a row that can't be
  resolved (missing dispatch_path on all twins) is **reported and skipped**, never
  guessed.
- All writes in one transaction; abort → rollback, DB unchanged.
- macFUSE NFD noise / ghost-inodes: ignored (operator directive).
- Verify reads use a normal connection + `PRAGMA wal_checkpoint(TRUNCATE)` before
  asserting (WAL visibility).

## Risks

- **Over-deleting legit remakes** → guarded by year-separated groups + identical
  `dispatch_path` requirement; dry-run reviewed before `--apply`.
- **Survivor mis-selection** → deterministic rule (live + newest drefr + highest id).
- **WAL visibility** on verification → checkpoint before counting.

## ACCEPTANCE criteria

ACC-1 — `_canonical_title` NFC-normalizes:

```bash
python -c "import unicodedata as u; from personalscraper.indexer.repos.item_repo import _canonical_title; print(_canonical_title(u.normalize('NFD','Fantômes (1996)')) == u.normalize('NFC','Fantômes'))"
# Expected: True
```

ACC-2 — dry-run reports duplicate groups and mutates nothing:

```bash
B=$(sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item"); \
personalscraper library-dedup-titles --dry-run >/dev/null 2>&1; \
A=$(sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item"); \
echo "$B == $A"
# Expected: <N> == <N> (unchanged; e.g. 1909 == 1909)
```

ACC-3 — apply removes orphans (NULL-valid drops to only the 2 true orphans, which
ACC-6 then repairs to 0):

```bash
personalscraper library-dedup-titles --apply >/dev/null 2>&1; \
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE date_metadata_refreshed IS NULL AND nfo_status='valid'"
# Expected: 2 immediately after --apply (ids 504, 1438); 0 after ACC-6 repair
```

ACC-4 — no duplicate group remains:

```bash
python -c "
import sqlite3, unicodedata as u, re
c=sqlite3.connect('.data/library.db'); g={}
for i,t,k,y in c.execute('SELECT id,title,kind,year FROM media_item'):
    key=(u.normalize('NFC',re.sub(r'\s*\(\d{4}\)\s*$','',t)).lower(),k,y); g.setdefault(key,[]).append(i)
print(sum(1 for v in g.values() if len(v)>1))"
# Expected: 0
```

ACC-5 — regression suite green:

```bash
make test 2>&1 | tail -1
# Expected: a line reporting "NNNN passed" with 0 failed / 0 errors
```

ACC-6 — the 2 true orphans are valid + refreshed:

```bash
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE id IN (504,1438) AND nfo_status='valid' AND date_metadata_refreshed IS NOT NULL"
# Expected: 2
```
