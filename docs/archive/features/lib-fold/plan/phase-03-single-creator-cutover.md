# Phase 3 — Single creator cutover: redirect dispatch, alias `library-scan`, delete `scanner.py`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redirect `dispatch/media_index.rebuild()` to the shared `upsert_item_with_attrs` (rich rows, no `canonical_provider=None`). Make `library-scan` a visible re-pointed alias of `library-index --mode full` (kept in `--help`). Then delete `library/scanner.py` and migrate its unique tests.

**Architecture:** Phase 2 proved (via the golden test) that `library-index --mode full` produces the same DB end-state as `library-scan`. Phase 3 commits to that path: deletes the legacy creator, eliminates the third write pattern in dispatch, and re-homes scanner tests. The golden test remains in the suite as a regression guard.

> **POST-PHASE-2-CORRECTION STATE (read before executing — validated against HEAD `d7a210e9`):** The Phase-2 corrective sweep already advanced several Phase-3 preconditions, so this phase is _cleaner_ than the original narrative below:
>
> - `scan_library._upsert_media_item` **already delegates** to the shared `upsert_item_with_attrs` (commit `a01bc3a0`) → the single-writer is **already achieved for the `library-scan` leg**. The **only remaining second writer is `dispatch/media_index.py`** (Task 1/2 below).
> - `_normalize_canonical_provider` is **already deleted** from `scanner.py` (logic lives in `_canonical.derive_canonical_provider`); the NFO helpers in `scanner.py` are **already imports** from `nfo_utils`; `_ensure_disk_row` / `_detect_issues` / `_upsert_seasons_and_episodes` / `_read_episode_titles` / `_build_disk_row` / artwork+nfo-status helpers are **already ported** into `_item_stage.py`. So deleting `scanner.py` (Task 3) removes only the dir-scanning (`scan_movie_dir`/`scan_tvshow_dir`) + `scan_library` walk that the alias replaces — no unique logic is lost.
> - The dispatch redirect (Task 2) target is real: `media_index.py` rebuild/add still does its own `item_repo.upsert(MediaItemRow(..., canonical_provider=None, ...))` (line ~418). `scan_and_stage_dir(conn, media_dir, disk_cfg, category_id, kind, now_s=None)` and `_ensure_disk_row(conn, disk_cfg, now_s)` signatures **match** what `MediaIndex.rebuild()` has in scope (`DiskConfig`, category id, kind via `TV_CATEGORY_IDS`). ACC-04b (`no canonical_provider=None`) currently **fails** at `media_index.py:418` — Task 2 fixes it.
> - `library-scan` (Task 2/3 alias) currently calls the (now-delegating) `scan_library`; re-pointing it to `library-index --mode full` is the final CLI cut. Confirm `scan_library` has no other callers before deletion.
> - Importers to migrate before deleting `scanner.py`: `commands/library/scan.py` (`scan_library`), `tests/library/test_scanner.py` (`scan_movie_dir`/`scan_tvshow_dir`/`_ensure_disk_row`), `tests/library/test_integration.py` (`scan_library`), `tests/architecture/test_event_bus_required_signatures.py` (`scan_library`), `tests/indexer/scanner/_modes/test_item_stage_golden.py` (`scan_library` — the golden baseline; re-home or adapt). NFO-helper imports were already repointed to `nfo_utils` in Phase 2.

**Tech Stack:** Python 3.11, SQLite, Typer (CLI alias), pytest, ruff, mypy.

---

## Gate

Phase 2 must be complete AND the golden test green:

- `python -m pytest tests/indexer/scanner/_modes/test_item_stage_golden.py -m integration` PASS.
- `python -c "import personalscraper.indexer.scanner._modes._item_stage, personalscraper.indexer.scanner._modes._canonical; print('OK')"` prints `OK`.
- `make lint && make test && make check` green.

---

## Objective

1. Redirect `dispatch/media_index.py:MediaIndex.rebuild()` to call `upsert_item_with_attrs` from `_item_stage.py` instead of its own minimal-row upsert. Eliminate `canonical_provider=None` from this code path.
2. Re-point `library-scan` CLI command as a visible alias of `library-index --mode full`.
3. Delete `personalscraper/library/scanner.py`.
4. Migrate any tests from `tests/library/test_scanner.py` that cover logic not already covered elsewhere into `tests/indexer/scanner/_modes/test_item_stage.py`.
5. Add a dispatch rich-rows regression test (pins the prior `canonical_provider=None` degradation as a bug-reproducer).

---

## Files to create / modify

| Action         | File                                                                                                        |
| -------------- | ----------------------------------------------------------------------------------------------------------- |
| Modify         | `personalscraper/dispatch/media_index.py`                                                                   |
| Modify         | `personalscraper/commands/library/scan.py` (re-point alias)                                                 |
| Delete         | `personalscraper/library/scanner.py`                                                                        |
| Modify/migrate | `tests/library/test_scanner.py` → relevant tests moved to `tests/indexer/scanner/_modes/test_item_stage.py` |
| Create         | `tests/dispatch/test_media_index_rich_rows.py` (dispatch regression test)                                   |

---

## Sub-tasks

> **▶ RESUME POINT (fresh session): Tasks 1 + 2 are DONE — START AT TASK 3.**
> The dispatch single-writer cutover is already committed and the suite is green (5987 passed):
>
> - Task 1+2 → `media_index.py` `rebuild()`/`add()` delegate to the shared `scan_and_stage_dir`/`build_item_row`+`upsert_item_with_attrs`; `canonical_provider=None` eliminated (ACC-04b ✓); regression test `tests/dispatch/test_media_index_rich_rows.py` exists. Commit `3d54ba8c`.
> - Exposed-bug fixes: `run.py` post-enrich uses `ScanMode.enrich` (`b73a141c`); the unscoped prod `OSError` guard was reverted for the documented `guard_disk_mounted` test seam (`0784850d`).
>
> Do **NOT** re-run Tasks 1/2 (the redirect + regression test already exist — re-dispatch would be a no-op at best, a duplicate at worst). **Begin at Task 3** (library-scan alias) → Task 4 (delete `scanner.py` + migrate its importers/tests, per the POST-PHASE-2-CORRECTION note above) → Task 5 (gate + milestone commit). See `IMPLEMENTATION.md` "Next action" for the same resume state.

### Task 1: Write the dispatch rich-rows regression test FIRST

**Files:**

- Create: `tests/dispatch/test_media_index_rich_rows.py`

This test pins the prior bug (dispatch auto-rebuild produced `canonical_provider=None`, no seasons) as a regression guard.

- [ ] **Step 1.1: Write the failing regression test**

```python
# tests/dispatch/test_media_index_rich_rows.py
"""Regression test: dispatch auto-rebuild must produce rich rows.

Prior to lib-fold Phase 3, MediaIndex.rebuild() used its own minimal-row
upsert (dispatch/media_index.py:406) with canonical_provider=None and no
season data. This test pins that bug as a reproducer and guards against
regression after the fix.
"""
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.dispatch.media_index import MediaIndex


@pytest.fixture()
def minimal_config(tmp_path: Path) -> MagicMock:
    """Minimal config stub for MediaIndex construction."""
    cfg = MagicMock()
    cfg.indexer.db_path = str(tmp_path / "index.db")
    # Provide at least one disk and category so rebuild() iterates
    disk = MagicMock()
    disk.id = "disk1"
    disk.mount_point = str(tmp_path / "disk1")
    (tmp_path / "disk1").mkdir()
    cfg.disks = [disk]
    cat = MagicMock()
    cat.id = "movies"
    cat.kind = "movie"
    cat.path = str(tmp_path / "disk1" / "Movies")
    (tmp_path / "disk1" / "Movies").mkdir()
    cfg.categories = [cat]
    return cfg


def test_dispatch_rebuild_no_canonical_provider_none(minimal_config: MagicMock) -> None:
    """After Phase 3: rebuild() must not write canonical_provider=None for items with IDs."""
    # Create a movie dir with a minimal NFO so the stage can derive canonical_provider
    movie_dir = Path(minimal_config.categories[0].path) / "The Godfather (1972)"
    movie_dir.mkdir(parents=True)
    nfo = movie_dir / "The Godfather (1972).nfo"
    nfo.write_text(
        '<?xml version="1.0"?><movie>'
        '<uniqueid type="tmdb" default="true">238</uniqueid>'
        "<title>The Godfather</title><year>1972</year></movie>",
        encoding="utf-8",
    )

    idx = MediaIndex(config=minimal_config, auto_rebuild=True)
    conn = sqlite3.connect(minimal_config.indexer.db_path)
    rows = conn.execute(
        "SELECT title, canonical_provider FROM media_item"
    ).fetchall()
    conn.close()

    assert rows, "rebuild() must create at least one media_item row"
    for title, cp in rows:
        assert cp is not None, (
            f"canonical_provider=None found for {title!r} — "
            "dispatch auto-rebuild must produce rich rows (lib-fold regression)"
        )
```

Run to confirm current failure (the legacy code writes `canonical_provider=None`):

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/dispatch/test_media_index_rich_rows.py -v 2>&1 | tail -15
```

Expected: FAIL with `AssertionError: canonical_provider=None found for ...`.

---

### Task 2: Redirect `dispatch/media_index.py` to `upsert_item_with_attrs`

**Files:**

- Modify: `personalscraper/dispatch/media_index.py`

- [ ] **Step 2.1: Read the current `rebuild()` / `add()` implementation**

```bash
sed -n '395,440p' /Users/izno/dev/PersonnalScaper/personalscraper/dispatch/media_index.py
```

- [ ] **Step 2.2: Add import**

At the top of `dispatch/media_index.py`, add:

```python
from personalscraper.indexer.scanner._modes._item_stage import (
    scan_and_stage_dir,
    _ensure_disk_row,
)
```

- [ ] **Step 2.3: Replace the minimal-row upsert in `rebuild()` / `add()`**

Find the block that calls `item_repo.upsert(...)` with `canonical_provider=None` (around line 406). Replace the per-directory upsert call with a delegation to the shared stage. Use the **corrected** `scan_and_stage_dir` signature from Phase 2 (`scan_and_stage_dir(conn, media_dir, disk_cfg, category_id, kind, now_s=None)` — `disk_cfg` is a `DiskConfig`, not `disk.id`):

```python
# Delegate to the shared item stage — produces rich rows (canonical_provider
# derived from NFO, seasons, issues) identical to library-index --mode full.
# Prior to lib-fold, this path wrote canonical_provider=None (regression fixed).
scan_and_stage_dir(
    self._conn,
    Path(media_dir_path),
    disk_cfg=disk_cfg,          # DiskConfig from MediaIndex config — verify the real var
    category_id=category_id,    # the logical category id string
    kind=kind,                  # "movie" | "show" — derive via TV_CATEGORY_IDS
)
```

> Verify the actual objects available in `MediaIndex.rebuild()` / `add()` before wiring: the dispatch layer carries `config` (→ `DiskConfig`), a category id, and the media-dir path. Resolve `disk_cfg` / `category_id` / `kind` from those — do **not** assume a `disk.id` / `category.id` / `category.kind` attribute shape (those were from the stale draft). `_ensure_disk_row(conn, disk_cfg, now_s)` (imported above) needs the same `DiskConfig`.

Remove the old `item_repo.upsert(...)` call and the `canonical_provider=None` assignment. Keep the `find_by_normalized_name` dedup check if it is used for something other than the upsert (read the surrounding code first).

- [ ] **Step 2.4: Verify ACC-04b — no `canonical_provider=None` left in dispatch**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'canonical_provider=None' personalscraper/dispatch/media_index.py ; echo "rc=$?"
```

Expected: no output, then `rc=1`.

- [ ] **Step 2.5: Run the dispatch regression test — must now pass**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/dispatch/test_media_index_rich_rows.py -v 2>&1 | tail -15
```

Expected: PASS.

- [ ] **Step 2.6: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/dispatch/media_index.py tests/dispatch/test_media_index_rich_rows.py && git commit -m "fix(lib-fold): dispatch rebuild delegates to upsert_item_with_attrs — eliminates canonical_provider=None"
```

---

### Task 3: Re-point `library-scan` as an alias of `library-index --mode full`

**Files:**

- Modify: `personalscraper/commands/library/scan.py`

- [ ] **Step 3.1: Read the current `scan.py` command**

```bash
cat /Users/izno/dev/PersonnalScaper/personalscraper/commands/library/scan.py
```

- [ ] **Step 3.2: Replace the scan command body**

Keep the Typer command registration (`@app.command("library-scan")`) and its `--help` text so the command remains visible. Replace the body to delegate to the indexer:

```python
@app.command("library-scan")
def library_scan(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only; no DB writes."),
) -> None:
    """Index the media library (rich rows: title, canonical provider, seasons).

    This command is an alias for ``library-index --mode full``.
    It is kept for backwards compatibility and remains visible in --help.
    """
    from personalscraper.commands.library.index import library_index  # lazy import to avoid circulars
    # Delegate — all arguments forwarded; this alias is intentionally thin.
    library_index(ctx, mode="full", dry_run=dry_run)
```

Adjust the import path to match how `library-index` is registered in the codebase (read `commands/library/__init__.py` or `cli_app.py` to find the exact module).

- [ ] **Step 3.3: Verify the alias appears in help**

```bash
cd /Users/izno/dev/PersonnalScaper && personalscraper --help 2>&1 | grep 'library-scan'
```

Expected: `library-scan` line present.

- [ ] **Step 3.4: Run existing `library-scan` tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/commands/test_library_scan.py tests/commands/test_library_scan_e2e.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 3.5: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/commands/library/scan.py && git commit -m "feat(lib-fold): library-scan becomes visible alias of library-index --mode full"
```

---

### Task 4: Migrate unique scanner tests, then delete `library/scanner.py`

**Files:**

- Modify: `tests/indexer/scanner/_modes/test_item_stage.py` (absorb unique coverage)
- Delete: `personalscraper/library/scanner.py`

- [ ] **Step 4.1: Audit `tests/library/test_scanner.py` for unique coverage**

```bash
grep -n 'def test_' /Users/izno/dev/PersonnalScaper/tests/library/test_scanner.py
```

For each test function, determine whether the logic under test now lives in `_item_stage.py`, `nfo_utils.py`, or `_canonical.py`. Move tests that cover logic in those new homes; delete tests that were testing the now-deleted direct DB write path that is fully covered by the golden test.

- [ ] **Step 4.2: Run migrated tests to confirm they pass**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/_modes/test_item_stage.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4.3: Delete `library/scanner.py`**

```bash
cd /Users/izno/dev/PersonnalScaper && git rm personalscraper/library/scanner.py
```

- [ ] **Step 4.4: Verify ACC-04 — scanner.py deleted; no residual imports**

```bash
test ! -f /Users/izno/dev/PersonnalScaper/personalscraper/library/scanner.py && echo "deleted"
# RE-SCOPED ACC-04 (signed off) — live-import form, not the unsatisfiable bare-token form:
cd /Users/izno/dev/PersonnalScaper && rg -t py 'from personalscraper\.library\.scanner|import personalscraper\.library\.scanner' personalscraper/ tests/ ; echo "rc=$?"
```

Expected: `deleted`, then no output, then `rc=1`.

- [ ] **Step 4.5: Run full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test 2>&1 | tail -20
```

Expected: zero lint errors, all tests pass.

- [ ] **Step 4.6: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add tests/indexer/scanner/_modes/test_item_stage.py tests/library/test_scanner.py && git commit -m "refactor(lib-fold): migrate scanner tests; delete library/scanner.py"
```

---

### Task 5: Phase 3 gate

- [ ] **Step 5.1: Full gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test && make check ; echo "rc=$?"
```

Expected: ruff+mypy clean, `NNNN passed` 0 failed/errors, coverage ≥ 90 %, `rc=0`.

- [ ] **Step 5.2: Residual import grep**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'personalscraper\.library' personalscraper/ tests/ | grep -v 'analyzer\|rescraper\|disk_cleaner\|validator\|recommender\|reporter\|models'
```

Expected: only `library/analyzer.py`, `library/rescraper.py`, `library/disk_cleaner.py`, `library/validator.py`, `library/recommender.py`, `library/reporter.py`, `library/models.py` — scanner-related hits = zero.

- [ ] **Step 5.3: Gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "chore(lib-fold): phase 3 gate — single creator; scanner.py deleted; dispatch rich rows"
```

---

## Acceptance

```bash
# ACC-04  library/scanner.py deleted; NO LIVE import of the deleted module remains
# RE-SCOPED (operator sign-off — mirrors the ACC-02 incoherence-fix): the broad
# 'library.scanner|scan_library' grep is unsatisfiable (trailers has its own unrelated
# scan_library method; analyzer.py keeps :func: docstrings until Phase 4; '.' is a regex
# wildcard). Satisfiable form = file gone + no live import of the deleted module.
test ! -f personalscraper/library/scanner.py && echo "deleted"
rg -t py 'from personalscraper\.library\.scanner|import personalscraper\.library\.scanner' personalscraper/ tests/ ; echo "rc=$?"
# Expected: deleted   then no output, then rc=1

# ACC-04b  no canonical_provider=None in dispatch
rg -t py 'canonical_provider=None' personalscraper/dispatch/media_index.py ; echo "rc=$?"
# Expected: no output, then rc=1
```

---

## Risks & mitigations

| Risk                                                        | Mitigation                                                                                                                              |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Dispatch auto-rebuild diverges (third write pattern)        | Single shared `upsert_item_with_attrs`; ACC-04b grep forbids `canonical_provider=None` reappearing; regression test pins the prior bug. |
| Test coverage drop when `test_scanner.py` tests are removed | Each gate runs `make check` (coverage included); unique coverage migrated in Task 4 before deletion.                                    |
| `library-scan` alias breaks existing callers / tests        | Alias kept in `--help`; existing `test_library_scan.py` and `test_library_scan_e2e.py` must pass before gate commit.                    |
| Deletion before golden test is green                        | Gate prerequisite explicitly requires the golden test to pass; blocked if it fails.                                                     |
