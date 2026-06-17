# Design — Targeted + incremental library re-scrape

**Date**: 2026-06-17
**Type**: minor (0.35.1 → 0.36.0)
**Origin**: GATE 7 row 9 (pipeline run 2026-06-16). Diagnosed live: `media_item.date_metadata_refreshed` is NULL for all 1909 rows because the scanner always writes `None`. Consequence: `find_items_needing_rescrape` (predicate `nfo_status != 'valid' OR date_metadata_refreshed IS NULL`) matches the whole library → `library-rescrape` is permanently non-incremental and cannot target a single item. This blocked the surgical fix of the 7 ID-less items (had to bypass via NFO write + `library-init-canonical`).

## Problem

1. **No targeted re-scrape.** `library-rescrape` only accepts `--disk`/`--category`. There is no way to re-scrape one specific library item (e.g. correct a single mis-identified show).
2. **Non-incremental default.** `date_metadata_refreshed` is never populated (scanner `_modes/_item_stage.py` hardcodes `None`), so the rescrape candidate predicate matches every item — a no-filter `library-rescrape` always targets the full library.

## Goal

- **Part 1**: targeted re-scrape of a single item via `library-rescrape --item-id <id>`, bypassing the needs-rescrape predicate (so a `nfo_status='valid'` item can be force-re-scraped).
- **Part 2**: populate `date_metadata_refreshed` so the default rescrape becomes incremental (only items with an invalid/incomplete NFO or never refreshed are candidates).

## Design

### Part 1 — `--item-id` targeting (low risk)

- `personalscraper/maintenance/rescraper.py`:
  - `_collect_rescrape_candidates(...)` gains `item_id: int | None`. When set, resolve exactly that item via `item_repo.get_by_id(conn, item_id)` (already exists), reconstruct its `media_dir` from `path`/`disk` rows, and return it as the **sole** candidate — **bypassing** the `find_items_needing_rescrape` predicate so a `valid` item is still re-scraped. `disk_filter`/`category_filter` are ignored when `item_id` is set (mutually exclusive; fail loud if combined).
  - `rescrape_library(...)` gains the `item_id` passthrough.
- `personalscraper/commands/library/analyze.py` (the `library-rescrape` command): add `--item-id INTEGER` option, plumb to `rescrape_library`. Requires the indexer DB (`conn`); error clearly if `--item-id` is given without a DB.
- Behaviour: `library-rescrape --item-id 1600` re-scrapes only item 1600, regardless of its NFO status.

### Part 2 — populate `date_metadata_refreshed` (core scanner)

- `personalscraper/indexer/scanner/_modes/_item_stage.py`: replace the hardcoded `"date_metadata_refreshed": None` with the **scan epoch** when the staged item's `nfo_status == "valid"`, else `None`. (The scan epoch is the scanner's run timestamp, already threaded through the staging path.) Rationale: a valid NFO means the item carries scraped metadata; recording the epoch removes it from the rescrape predicate's `IS NULL` arm. Items with an invalid/incomplete NFO keep `None` → remain rescrape candidates.
- **Backfill**: no migration script (pre-1.0). Existing NULLs are populated organically by the next full/quick scan (the scheduled `index-rotate`/`index-quick` jobs sweep all disks within a week), since every staged valid item now gets the epoch. The design accepts this gradual backfill; an operator may force it immediately with a full `library-index` run.
- Net effect: after a scan, `find_items_needing_rescrape` returns only items whose NFO is not valid (genuinely needing repair) → the no-filter `library-rescrape` is incremental.

### Why this split is safe

Part 1 is independent of Part 2 (targeting uses `get_by_id`, not the predicate). Part 2 changes only the value written to one column in the staging row dict; the upsert column list already includes `date_metadata_refreshed`, so no schema change. `is_locked = 0` guard in the predicate is preserved.

## Acceptance (executable)

- **AC-1** targeted select: `library-rescrape --item-id 1600 --dry-run` reports exactly 1 candidate (La Linea), not the full library.
  Expected: dry-run output lists 1 item, item 1600.
- **AC-2** bypass predicate: AC-1 holds even though item 1600 is `nfo_status='valid'` (force re-scrape).
- **AC-3** real targeted re-scrape: `library-rescrape --item-id 1600` re-scrapes La Linea (tvdb:80915) and corrects its title/year; no other item's NFO mtime changes.
- **AC-4** mutual exclusion: `library-rescrape --item-id 1600 --disk disk_2` errors clearly (or ignores the disk filter with a logged warning) — documented, not silent.
- **AC-5** scanner populates: after a `library-index` scan, a sampled valid-NFO item has `date_metadata_refreshed` non-NULL; an invalid-NFO item stays NULL.
- **AC-6** incremental: with `date_metadata_refreshed` populated for valid items, `library-rescrape --dry-run` (no filter) reports only items with `nfo_status != 'valid'`, not all 1909.
- **AC-7** `make check` green.

## Testing

- Unit: `_collect_rescrape_candidates(item_id=1600)` returns one candidate via `get_by_id`, bypassing the predicate; mutual-exclusion handling; `item_id` for a missing/None-path item → empty + clear log.
- Unit: `_item_stage` staging row sets `date_metadata_refreshed = scan_epoch` when `nfo_status == 'valid'`, `None` otherwise (test-per-bug: reproduces the always-None bug).
- Integration: targeted rescrape touches only the targeted item (assert other items untouched).

## Non-goals

- `--show <title>` fuzzy targeting (deferred — `--item-id` is precise and sufficient; `--show` risks mis-targeting).
- Changing the `find_items_needing_rescrape` predicate itself.
- Correcting historical wrong titles/years in bulk (only the targeted item, on demand).
- A standalone backfill command/migration (rely on the scheduled scans).
