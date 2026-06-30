# Phase 2: Wiring + integration + regression + ACC gate

**Codename**: index-sync
**Target**: `personalscraper/dispatch/run.py`, `personalscraper/commands/pipeline.py`, `personalscraper/pipeline_steps.py`, tests

## Gate

Phase 1 MUST have produced:

- `run_post_dispatch_maintenance(config, touched_disks, *, enabled)` importable from `personalscraper.dispatch.post_maintenance`
- `IndexerConfig.post_dispatch_maintenance.enabled` field (default `True`)
- `--no-post-maintenance` CLI flag on `dispatch` (visible in `--help`)
- 7 passing unit tests in `tests/dispatch/test_post_maintenance.py`

Verify before starting:

```bash
python -c "from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance; print('ok')" && \
python -m pytest tests/dispatch/test_post_maintenance.py -q
```

## Sub-phases

---

### Sub-phase 2.1: Modify `run_dispatch` to expose raw results

**Files:**

- Modify: `personalscraper/dispatch/run.py`

**Commit**: `feat(index-sync): return raw DispatchResult list from run_dispatch`

- [ ] **Step 1: Change return type of `run_dispatch`**

In `personalscraper/dispatch/run.py`, change the return:

```python
# Current (line 206-209):
#   report = _to_step_report(results)
#   if cleaned:
#       report.details.insert(0, f"Cleaned {cleaned} staging orphan(s)")
#   return report

# New:
report = _to_step_report(results)
if cleaned:
    report.details.insert(0, f"Cleaned {cleaned} staging orphan(s)")
return report, results
```

Update the function signature's `Returns:` docstring:

```
Returns:
    ``(StepReport, list[DispatchResult])`` — the step report with
    counts/details for CLI output, and the raw per-item results for
    post-dispatch processing (touched-disk collection).
```

- [ ] **Step 2: Update `DispatchStep.__call__` in `pipeline_steps.py`**

```python
# Current (line 279):
#   return run_dispatch(
#       ctx.app.settings,
#       ...
#   )

# New:
report, _results = run_dispatch(
    ctx.app.settings,
    config=ctx.app.config,
    dry_run=ctx.dry_run,
    verified=ctx.extras.get("verified"),
    event_bus=ctx.app.event_bus,
    permit=kw.get("permit", AllowAllPermit()),
    recorder=kw.get("recorder", AllowAllPermit()),
)
return report
```

- [ ] **Step 3: Update `dispatch()` CLI function in `pipeline.py`**

```python
# Current (line 290):
#   report = run_dispatch(settings, config=config, dry_run=dry_run, event_bus=app_context.event_bus)

# New (sub-phase 2.3 will insert the post-maintenance call here):
report, results = run_dispatch(settings, config=config, dry_run=dry_run, event_bus=app_context.event_bus)
```

- [ ] **Step 4: Run existing dispatch tests to confirm no regression**

```bash
python -m pytest tests/dispatch/ -q
# Expected: all existing dispatch tests pass
```

- [ ] **Step 5: Commit**

```bash
git add personalscraper/dispatch/run.py personalscraper/commands/pipeline.py personalscraper/pipeline_steps.py
git commit -m "feat(index-sync): return raw DispatchResult list from run_dispatch"
```

---

### Sub-phase 2.2: Extract touched disks + wire the hook into `dispatch` CLI

**Files:**

- Modify: `personalscraper/commands/pipeline.py`

**Commit**: `feat(index-sync): wire post-maintenance hook into dispatch CLI`

- [ ] **Step 1: Add the touched-disks extraction and post-maintenance call**

In `personalscraper/commands/pipeline.py`, in the `dispatch()` function, after `run_dispatch` returns and before the `console.print`:

```python
# After: report, results = run_dispatch(settings, config=config, dry_run=dry_run, event_bus=app_context.event_bus)

# Collect touched disks from DispatchResult objects.
touched_disks: set[str] = {
    r.disk
    for r in results
    if r.disk is not None and r.action in ("moved", "merged", "replaced")
}

# Resolve post-maintenance enablement: flag > config > default(true).
maintenance_enabled = not no_post_maintenance
if maintenance_enabled:
    # If flag was not passed (stays False), check config.
    maintenance_enabled = config.indexer.post_dispatch_maintenance.enabled

if touched_disks:
    from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance

    run_post_dispatch_maintenance(config, touched_disks, enabled=maintenance_enabled)
```

- [ ] **Step 2: Verify importable and wired**

```bash
python -c "
# Simulate the wiring path (won't run because no real config)
import importlib
spec = importlib.util.find_spec('personalscraper.dispatch.post_maintenance')
print('post_maintenance module found:', spec is not None)
"
# Expected: post_maintenance module found: True
```

- [ ] **Step 3: Verify ACC-01 — flag in help**

```bash
python -m personalscraper dispatch --help 2>/dev/null | grep -c -- '--no-post-maintenance'
# Expected: 1
```

- [ ] **Step 4: Commit**

```bash
git add personalscraper/commands/pipeline.py
git commit -m "feat(index-sync): wire post-maintenance hook into dispatch CLI"
```

---

### Sub-phase 2.3: Wire the hook into `DispatchStep` for the `run` path

**Files:**

- Modify: `personalscraper/pipeline_steps.py`

**Commit**: `feat(index-sync): wire post-maintenance into pipeline DispatchStep for run command`

- [ ] **Step 1: Add post-maintenance call after `run_dispatch` in `DispatchStep.__call__`**

In `personalscraper/pipeline_steps.py`, in `DispatchStep.__call__`, after getting `report, results`:

```python
report, results = run_dispatch(
    ctx.app.settings,
    config=ctx.app.config,
    dry_run=ctx.dry_run,
    verified=ctx.extras.get("verified"),
    event_bus=ctx.app.event_bus,
    permit=kw.get("permit", AllowAllPermit()),
    recorder=kw.get("recorder", AllowAllPermit()),
)

# Post-dispatch index maintenance (DESIGN index-sync):
# triggered for run command too; flag resolution from StepContext extras.
no_maintenance = bool(ctx.extras.get("no_post_maintenance", False))
maintenance_enabled = not no_maintenance
if maintenance_enabled:
    maintenance_enabled = ctx.app.config.indexer.post_dispatch_maintenance.enabled

touched_disks: set[str] = {
    r.disk
    for r in results
    if r.disk is not None and r.action in ("moved", "merged", "replaced")
}
if touched_disks and maintenance_enabled:
    from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance

    run_post_dispatch_maintenance(
        ctx.app.config, touched_disks, enabled=maintenance_enabled
    )

return report
```

Need to also plumb `--no-post-maintenance` through the `run` CLI command and into `ctx.extras`. Add the flag to the `run()` function signature:

```python
def run(
    ...
    no_post_maintenance: bool = typer.Option(
        False,
        "--no-post-maintenance",
        help="Skip automatic index maintenance after dispatch.",
    ),
) -> None:
```

And pass it through to the Pipeline extras:

```python
# Find where extras dict is built for the Pipeline.run() call and add:
# "no_post_maintenance": no_post_maintenance,
```

- [ ] **Step 2: Verify `run --help` shows the flag**

```bash
python -m personalscraper run --help 2>/dev/null | grep -c -- '--no-post-maintenance'
# Expected: 1
```

- [ ] **Step 3: Commit**

```bash
git add personalscraper/pipeline_steps.py personalscraper/commands/pipeline.py
git commit -m "feat(index-sync): wire post-maintenance into pipeline DispatchStep for run command"
```

---

### Sub-phase 2.4: Integration + regression test

**Files:**

- Create: `tests/dispatch/test_post_maintenance_integration.py`

**Commit**: `test(index-sync): add integration + regression test for items_without_files`

- [ ] **Step 1: Write test file**

This test reproduces the 2026-06-29 `items_without_files=6` symptom and proves the hook fixes it.

```python
"""Integration/regression tests for post-dispatch index maintenance.

Reproduces the 2026-06-29 ``items_without_files=6`` symptom where freshly
dispatched items had releases but 0 linked media_file rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance


@pytest.fixture
def temp_library_db(tmp_path: Path) -> Path:
    """Create a minimal library.db with the schema needed for relinking.

    Creates the core tables (media_item, season, episode, media_release,
    media_file, path, disk, item_attribute) and inserts a freshly dispatched
    item that HAS releases but 0 linked media_file rows — the exact
    2026-06-29 symptom.
    """
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE disk (
            id INTEGER PRIMARY KEY,
            label TEXT NOT NULL,
            mount_path TEXT NOT NULL,
            is_mounted INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE media_item (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            kind TEXT NOT NULL,
            year INTEGER
        );
        CREATE TABLE season (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES media_item(id),
            number INTEGER NOT NULL,
            episode_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE episode (
            id INTEGER PRIMARY KEY,
            season_id INTEGER NOT NULL REFERENCES season(id),
            number INTEGER NOT NULL
        );
        CREATE TABLE media_release (
            id INTEGER PRIMARY KEY,
            item_id INTEGER REFERENCES media_item(id),
            episode_id INTEGER REFERENCES episode(id),
            quality TEXT,
            edition TEXT,
            primary_lang TEXT
        );
        CREATE TABLE path (
            id INTEGER PRIMARY KEY,
            disk_id INTEGER NOT NULL REFERENCES disk(id),
            rel_path TEXT NOT NULL
        );
        CREATE TABLE media_file (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            path_id INTEGER REFERENCES path(id),
            release_id INTEGER REFERENCES media_release(id),
            deleted_at TEXT
        );
        CREATE TABLE item_attribute (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES media_item(id),
            key TEXT NOT NULL,
            value TEXT NOT NULL
        );
    """)

    # Insert a disk.
    conn.execute(
        "INSERT INTO disk (id, label, mount_path, is_mounted) VALUES (1, 'disk_1', ?, 1)",
        (str(tmp_path / "disk_1"),),
    )

    # Create the disk mount dir.
    disk_dir = tmp_path / "disk_1"
    disk_dir.mkdir()

    # Insert a dispatched movie: has item + release but 0 linked files.
    conn.execute(
        "INSERT INTO media_item (id, title, kind, year) VALUES (1, 'Test Movie', 'movie', 2025)"
    )
    conn.execute(
        "INSERT INTO media_release (id, item_id, quality, edition, primary_lang) "
        "VALUES (1, 1, NULL, NULL, NULL)"
    )
    # Insert item_attribute with dispatch_path so the linker can find the item.
    movie_dir = disk_dir / "Test Movie (2025)"
    movie_dir.mkdir()
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (1, 'dispatch_path', ?)",
        (str(movie_dir),),
    )

    # Insert a path and a media_file with release_id=NULL (the regression symptom).
    conn.execute(
        "INSERT INTO path (id, disk_id, rel_path) VALUES (1, 1, 'Test Movie (2025)')"
    )
    # Create a dummy video file.
    video_file = movie_dir / "Test.Movie.2025.1080p.mkv"
    video_file.write_text("fake video")
    conn.execute(
        "INSERT INTO media_file (id, filename, path_id, release_id, deleted_at) "
        "VALUES (1, 'Test.Movie.2025.1080p.mkv', 1, NULL, NULL)"
    )

    conn.commit()
    conn.close()
    return db_path


def test_integration_media_file_linked_after_maintenance(
    tmp_path: Path, temp_library_db: Path
) -> None:
    """After post_maintenance, media_file rows gain linked release_id.

    This is the regression test for the 2026-06-29 symptom: freshly dispatched
    items had releases but 0 linked media_file rows (items_without_files=6).
    The hook must link those files.
    """
    disk_dir = tmp_path / "disk_1"
    touched_disks = {"disk_1"}

    # Build a mock Config that points to our temp DB.
    mock_config = MagicMock()
    mock_config.indexer.db_path = temp_library_db
    mock_config.indexer.post_dispatch_maintenance.enabled = True

    # The scan step uses library_index_command which needs full config.
    # We patch the scan to a no-op (the integration concern is relink + fix).
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        # Use the REAL _run_relink and _run_fix_season_counts (not mocked)
        # so we exercise the actual linker code against the temp DB.
    ):
        run_post_dispatch_maintenance(mock_config, touched_disks, enabled=True)

    # Verify: the media_file now has a non-NULL release_id.
    conn = sqlite3.connect(str(temp_library_db))
    row = conn.execute(
        "SELECT release_id FROM media_file WHERE id = 1"
    ).fetchone()
    conn.close()

    assert row is not None, "media_file row should exist"
    assert row[0] is not None, (
        f"REGRESSION: media_file.release_id is still NULL after post_maintenance — "
        f"the 2026-06-29 symptom (items_without_files=6) was NOT fixed"
    )


def test_integration_noop_when_all_files_linked(
    tmp_path: Path, temp_library_db: Path
) -> None:
    """Post-maintenance is a no-op when all files are already linked."""
    # Pre-link the file.
    conn = sqlite3.connect(str(temp_library_db))
    conn.execute("UPDATE media_file SET release_id = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    mock_config = MagicMock()
    mock_config.indexer.db_path = temp_library_db
    mock_config.indexer.post_dispatch_maintenance.enabled = True

    with patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    # Verify: no change — release_id still 1.
    conn = sqlite3.connect(str(temp_library_db))
    row = conn.execute("SELECT release_id FROM media_file WHERE id = 1").fetchone()
    conn.close()
    assert row is not None and row[0] == 1
```

- [ ] **Step 2: Run integration tests**

```bash
python -m pytest tests/dispatch/test_post_maintenance_integration.py -v
# Expected: 2 passed
```

- [ ] **Step 3: Commit**

```bash
git add tests/dispatch/test_post_maintenance_integration.py
git commit -m "test(index-sync): add integration + regression test for items_without_files"
```

---

### Sub-phase 2.5: Validation — incremental indexes new items (auto-fallback removed)

**Files:**

- No new files (manual validation — code guard removed per operator)

**Commit**: `chore(index-sync): validate incremental scan indexes dispatched items`

**Status**: ~~Done~~ — auto-fallback REMOVED per operator decision (2026-06-30).

This sub-phase was **validation**, not implementation. The DESIGN's Risk §1 originally read:
"Incremental scan might not re-stage brand-new dispatched dirs the way full does."

The plan called for a full-scan fallback when incremental left unlinked files —
`_count_unlinked_files_for_disk` + `library_index_command(mode="full", ...)`.
However, this fired on every dispatch (counted `release_id IS NULL` BEFORE relink

- standing orphans already exist → library-wide full scan every time, defeating
  the incremental design).

**Operator decision (2026-06-30):** REMOVE the auto full-scan fallback entirely.
New dispatched dirs have new mtimes → incremental walks them. If items remain
unlinked, the fail-soft warning + manual fallback command is logged for the
operator (no automatic full scan). The `_count_unlinked_files_for_disk` function
was deleted and the fallback block was stripped from the per-disk scan loop.

- [x] **Step 1: Manual check — scan mode understanding** (done, validated)
- [x] **Step 2: Code guard removed** — operator decision
- [x] **Step 3: Unit test deleted** — `test_full_scan_fallback_when_incremental_leaves_unlinked` removed
- [x] **Step 4: Tests pass without the fallback**
- [x] **Step 5: Committed** (see current commit)

---

### Sub-phase 2.6: ACCEPTANCE gate

**Files:**

- None (verification only)

**Commit**: `chore(index-sync): phase 2 gate — wiring + acceptance`

Run every ACCEPTANCE criterion and record results.

- [ ] **ACC-01 — `--no-post-maintenance` flag in `dispatch --help`**

```bash
personalscraper dispatch --help | grep -c -- '--no-post-maintenance'
# Expected: 1
```

- [ ] **ACC-02 — Config key in example template**

```bash
grep -rEc "post_dispatch_maintenance|post_maintenance" config.example/ | awk -F: '{s+=$2} END{print (s>0)?"OK":"MISSING"}'
# Expected: OK
```

- [ ] **ACC-03 — Function importable**

```bash
python3 -c "from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance; print('import-ok')"
# Expected: import-ok
```

- [ ] **ACC-04 — All post_maintenance tests pass**

```bash
python3 -m pytest tests/ -k "post_dispatch_maintenance or post_maintenance or index_sync" -q 2>&1 | tail -1
# Expected: line ending with "passed" and 0 failed
```

- [ ] **ACC-05 — Full quality gate**

```bash
make check 2>&1 | tail -3
# Expected: lint clean, NNNN passed with 0 failed/errors, module-size + typed-api OK
```

- [ ] **ACC-06 — (Documented) E2E proof**

After a real dispatch of ≥1 item with the hook enabled, run:

```bash
personalscraper library-reconcile --read-only 2>&1 | grep items_without_files
```

The `items_without_files` should not increase by the number of dispatched items (newly dispatched items have linked files). Document the before/after values in the phase report.

**Note**: ACC-06 is a manual observation, not an automated gate. Record the result in the phase gate commit message or an inline note.

- [ ] **Step: Commit the gate**

```bash
git add -A
git commit -m "chore(index-sync): phase 2 gate — wiring + acceptance

ACC-01: flag in dispatch --help ✓
ACC-02: config key in config.example/ ✓
ACC-03: function importable ✓
ACC-04: post_maintenance tests pass ✓
ACC-05: make check green ✓
ACC-06: E2E proof (manual — before/after items_without_files recorded)"
```

---

## Files summary

| File                                                  | Action                                                                                                    |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `personalscraper/dispatch/run.py`                     | Modify — return `(report, results)` tuple                                                                 |
| `personalscraper/commands/pipeline.py`                | Modify — extract touched disks + call hook in `dispatch()`; add `--no-post-maintenance` to `run()`        |
| `personalscraper/pipeline_steps.py`                   | Modify — extract touched disks + call hook in `DispatchStep.__call__`; plumb `no_post_maintenance` extras |
| `personalscraper/dispatch/post_maintenance.py`        | Modify — add fallback full-scan when incremental leaves unlinked files                                    |
| `tests/dispatch/test_post_maintenance.py`             | Modify — add fallback unit test                                                                           |
| `tests/dispatch/test_post_maintenance_integration.py` | Create — 2 integration/regression tests                                                                   |

## Acceptance criteria covered

| Criterion | Sub-phase                                        |
| --------- | ------------------------------------------------ |
| ACC-01    | 2.2 (flag in `--help`)                           |
| ACC-02    | Already covered by Phase 1.1; verified at gate   |
| ACC-03    | Already covered by Phase 1.2; verified at gate   |
| ACC-04    | Covered by 2.4/2.5 (all tests pass)              |
| ACC-05    | Covered by 2.6 (quality gate)                    |
| ACC-06    | Manual observation documented in 2.6 gate commit |

## Design coverage

| Design element                               | Sub-phase                          |
| -------------------------------------------- | ---------------------------------- |
| Touched-disks collection from DispatchResult | 2.2, 2.3                           |
| Per-disk incremental scan (sequential)       | Phase 1.2; fallback in 2.5         |
| Global relink --apply                        | Phase 1.2                          |
| Global fix-season-counts --apply             | Phase 1.2                          |
| Fail-soft                                    | Phase 1.2, 1.4                     |
| Flag > config > default resolution           | 2.2                                |
| Observatory: structured events               | Phase 1.2 (log.info/warning calls) |
| Idempotence (no-op on 0 touched disks)       | Phase 1.4                          |
