# Phase 2 — date-refreshed population

**Covers**: AC-5, AC-6
**Risk**: low (changes one value in one column of the staged row dict; no schema
change — `date_metadata_refreshed` is already in the `upsert` column set)

## Gate

Phase 1 done: `_collect_rescrape_candidates` + `rescrape_library` have `item_id`
support; `library-rescrape --item-id` is wired in the CLI. `make check` is green.

---

### 2.1 — Populate `date_metadata_refreshed` from scan epoch (TDD, one commit)

**Commit**: `fix(rescrape-target): populate date_metadata_refreshed from scan epoch for valid NFO`

TDD red→green **within this single sub-phase** (write the failing tests, then the
fix, end green — do NOT commit a red state). Root cause (DESIGN §Origin):
`personalscraper/indexer/scanner/_modes/_item_stage.py` hardcodes
`"date_metadata_refreshed": None` (~L162), so the column is never populated.

**Tests first** (`tests/indexer/scanner/test_item_stage.py` — create if absent, or
the nearest existing `_item_stage` test module):

- `test_build_item_row_valid_nfo_sets_date_refreshed` — call `build_item_row(...
nfo_status="valid", scan_epoch=12345)`; assert `row["date_metadata_refreshed"]
== 12345`. (Fails before the fix — the bug.)
- `test_build_item_row_invalid_nfo_keeps_date_refreshed_none` — same with
  `nfo_status` not "valid" (e.g. `"missing"`); assert
  `row["date_metadata_refreshed"] is None`. (Stays green — that part is already
  correct.)
- `test_scan_and_stage_dir_valid_nfo_sets_date_refreshed` — minimal fixture dir
  with a valid NFO; call `scan_and_stage_dir(... )` with the run timestamp; query
  the resulting `media_item` row and assert `date_metadata_refreshed` equals that
  timestamp. (Integration: proves the epoch threads through to the DB.)

**Fix** (same commit, until `make check` is green):

- `_item_stage.py` `build_item_row`: add a keyword-only `scan_epoch: int | None =
None` parameter (after existing params). Replace L162
  `"date_metadata_refreshed": None` with:
  ```python
  "date_metadata_refreshed": scan_epoch if nfo_status == "valid" else None,
  ```
  Update the Google-style docstring (document `scan_epoch` + the conditional).
- `scan_and_stage_dir` (the call site of `build_item_row`, ~L679): pass
  `scan_epoch=stamp` (the run timestamp already threaded into the staging path —
  re-verify its variable name and thread it if not already in scope).
- No change to `upsert_item_with_attrs` / `item_repo.upsert` —
  `date_metadata_refreshed` is already in the written column set.
- **Backfill**: no migration script (pre-1.0). Existing NULLs are populated
  organically on the next full/quick scan (every staged valid item now gets the
  epoch). Documented in DESIGN §Part 2.

End state: all three tests pass, `make check` green.

---

## Phase gate

`make check` green (0 failures). AC-5 covered by
`test_scan_and_stage_dir_valid_nfo_sets_date_refreshed`. AC-6 (no-filter rescrape
returns only non-valid items once the column is populated) is a live-DB check
re-exercised in phase-03-gate after a real scan. No modules deleted → no residual
import grep.
