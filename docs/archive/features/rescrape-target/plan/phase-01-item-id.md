# Phase 1 — item-id targeting

**Covers**: AC-1, AC-2, AC-3, AC-4
**Risk**: low (additive parameter, no existing behaviour changed)

## Gate

Previous: branch `feat/rescrape-target` created, IMPLEMENTATION.md initialised.

---

### 1.1 — `_collect_rescrape_candidates`: add `item_id` fast-path

**Commit**: `feat(rescrape-target): add item_id fast-path to _collect_rescrape_candidates`

**What**

- Add `item_id: int | None = None` to `_collect_rescrape_candidates` in
  `personalscraper/maintenance/rescraper.py`.
- When `item_id` is set:
  1. Call `item_repo.get_by_id(conn, item_id)` (already exists, L176 of
     `personalscraper/indexer/repos/item_repo.py`).
  2. If the row is `None` → log warning, return `[]`.
  3. Resolve `media_dir` by reading the `_ATTR_DISPATCH_PATH` flex attribute
     via `item_repo.get_attr(conn, item_id, item_repo._ATTR_DISPATCH_PATH)`
     (or the join already available in `find_items_needing_rescrape`). If path
     is missing or not a dir → log warning, return `[]`.
  4. Reconstruct `(media_dir, media_type, disk_id, category_id)` from the row
     and return it as a single-element list — **bypassing**
     `find_items_needing_rescrape` entirely (so `nfo_status='valid'` items are
     still force-re-scraped).
  5. Mutual exclusion: if `item_id` is set and either `disk_filter` or
     `category_filter` is also set → raise `ValueError` with a clear message
     (documented, not silent). Enforce before the DB lookup.
- Update the Google-style docstring to document `item_id` and mutual-exclusion
  behaviour.

**Tests** (`tests/maintenance/test_rescraper.py`)

Write the failing test first:

- `test_collect_candidates_item_id_returns_single_candidate` — mock
  `item_repo.get_by_id` returning a valid row with `nfo_status='valid'`;
  assert exactly 1 tuple returned and `find_items_needing_rescrape` is never
  called.
- `test_collect_candidates_item_id_missing_item` — `get_by_id` returns `None`;
  assert empty list returned.
- `test_collect_candidates_item_id_mutual_exclusion` — `item_id` + `disk_filter`
  → `ValueError`.

Then add the implementation until `make check` passes.

---

### 1.2 — Thread `item_id` through `rescrape_library`

**Commit**: `feat(rescrape-target): thread item_id through rescrape_library`

**What**

- Add `item_id: int | None = None` parameter to `rescrape_library` in
  `personalscraper/maintenance/rescraper.py` (after existing params, before
  keyword-only block).
- Pass it to `_collect_rescrape_candidates(... item_id=item_id)`.
- Update docstring.

**Tests** (`tests/maintenance/test_rescraper.py`)

- `test_rescrape_library_item_id_threads_through` — spy on
  `_collect_rescrape_candidates`; call `rescrape_library` with `item_id=42`;
  assert `_collect_rescrape_candidates` was called with `item_id=42`.

Then implement and verify `make check` is green.

---

### 1.3 — `library-rescrape --item-id` CLI option

**Commit**: `feat(rescrape-target): add --item-id option to library-rescrape CLI`

**What**

- In `personalscraper/commands/library/analyze.py`, add:
  ```python
  item_id: int = typer.Option(None, "--item-id", help="Re-scrape exactly this item by DB id, bypassing the needs-rescrape predicate.")
  ```
  to the `library-rescrape` command (after `max_items`).
- Plumb `item_id` to `rescrape_library(... item_id=item_id)`.
- Guard: if `item_id` is set and no `conn` (indexer DB not available), print a
  clear error and exit 1. The existing `per_step_boundary` already opens
  `conn` when the indexer config is present; verify the call site passes `conn`
  or document the fallback. If `conn` is currently not passed to
  `rescrape_library` in the CLI (it is not — see L298-308 of `analyze.py`),
  add the `conn` plumbing from `app_context` or the indexer DB path, matching
  how other library commands open the connection.
- Update the CLI docstring/`Examples:` block.

**Tests** (`tests/maintenance/test_rescraper.py` or a CLI test)

- `test_cli_library_rescrape_item_id_passed` — use `typer.testing.CliRunner`
  to invoke `library-rescrape --item-id 99 --dry-run`; mock `rescrape_library`
  and assert it was called with `item_id=99`.

Then implement and confirm `make check` is green.

---

## Phase gate

`make check` must pass with 0 failures. Residual import grep: none (additive
only). AC-1 and AC-2 covered by unit tests (single candidate returned for a
`valid` item). AC-3 and AC-4 covered by unit tests (mutual exclusion raises).
