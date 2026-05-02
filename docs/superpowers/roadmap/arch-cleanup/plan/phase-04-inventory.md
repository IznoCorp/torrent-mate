# Phase 4 Inventory — `indexer/scanner/_modes.py`

Generated before splitting `personalscraper/indexer/scanner/_modes.py` into a package.

## Current Entry Points

`_modes.py` defines these functions:

- `_scan_disk_full` — `full`
- `_run_paranoia_branch` — `quick` helper
- `_scan_disk_quick` — `quick`
- `_scan_disk_incremental` — `incremental`
- `_walk_dir_incremental` — `incremental` helper
- `_resolve_item_root_dir` — `enrich` helper
- `_inventory_artwork` — `enrich` helper, directly tested
- `_purge_non_video_stream_rows` — `enrich` helper
- `_check_nfo_status` — `enrich` helper
- `_enrich_one_file` — `enrich` helper, directly tested
- `_scan_disk_enrich` — `enrich`
- `_scan_disk_enrich_backfill` — `enrich`
- `_scan_disk_verify` — `verify`

## Module Constants

- `_TV_SEASON_DIR_RE` — `enrich` helper constant used by `_resolve_item_root_dir`.

## Shared Imports And Dependencies

Most mode functions share schema rows, logging, SQLite, and scanner DB-write helpers. The split should keep direct imports local to each module and avoid moving scanner business logic during extraction.

Shared scanner helpers used by multiple modes:

- `_compute_oshash`
- `_flush_insert_buffer`
- `_safe_mtime_ns`
- `_upsert_file_row`
- `_upsert_path_row`
- `_relpath`
- `_should_exclude`

Mode-specific helper clusters:

- `full.py`: `_scan_disk_full`
- `quick.py`: `_run_paranoia_branch`, `_scan_disk_quick`
- `incremental.py`: `_scan_disk_incremental`, `_walk_dir_incremental`
- `enrich.py`: `_TV_SEASON_DIR_RE`, `_resolve_item_root_dir`, `_inventory_artwork`, `_purge_non_video_stream_rows`, `_check_nfo_status`, `_enrich_one_file`, `_scan_disk_enrich`, `_scan_disk_enrich_backfill`
- `verify.py`: `_scan_disk_verify`

## External Consumers

Production imports:

- `personalscraper/indexer/scanner/__init__.py` imports `_scan_disk_enrich`, `_scan_disk_enrich_backfill`, `_scan_disk_full`, `_scan_disk_incremental`, `_scan_disk_quick`, `_scan_disk_verify`.

Tests importing from `personalscraper.indexer.scanner._modes`:

- `tests/indexer/test_enrich_optimizations.py` imports `_scan_disk_enrich`, `_scan_disk_enrich_backfill`, and patches `_enrich_one_file`, `_inventory_artwork`.
- `tests/indexer/scanner/test_modes.py` imports `_enrich_one_file`, `_inventory_artwork`.

Tests patching scanner package re-exports:

- `tests/indexer/test_scanner.py` patches `personalscraper.indexer.scanner._scan_disk_full`.

## Compatibility Requirements

- `from personalscraper.indexer.scanner._modes import <existing_name>` must keep working after the final package rename.
- Patches to `personalscraper.indexer.scanner._modes._enrich_one_file` and `_inventory_artwork` must continue to affect `_scan_disk_enrich`.
- `personalscraper.indexer.scanner.__init__` should keep its existing re-export surface.
- No logic changes during extraction; mode modules should be behaviour-preserving moves.
