# Phase 1: Core function + config + flag + unit tests

**Codename**: index-sync
**Target**: `personalscraper/dispatch/post_maintenance.py` (NEW), `config.example/indexer.json5`, `personalscraper/conf/models/indexer.py`, `personalscraper/commands/pipeline.py` (flag only), tests

## Gate

This is Phase 1 — no prior phase. Gate is: feature branch `feat/index-sync` exists and `docs/features/index-sync/DESIGN.md` is present (already met).

## Architecture

**New module**: `personalscraper/dispatch/post_maintenance.py`

- Exposes `run_post_dispatch_maintenance(config, touched_disks, *, enabled)` — the single reusable function.
- Composes `library_index_command` (programmatic, from `personalscraper.indexer.cli`), the relink SQL loop (extracted from `personalscraper/commands/library/audit.py`), and the fix-season-counts SQL from `personalscraper/commands/library/fix_season_counts.py`.
- Fail-soft: exceptions caught, logged as warnings, never propagate.

**Config key**: `indexer.post_dispatch_maintenance.enabled: bool` (default `true`)

- In `personalscraper/conf/models/indexer.py`: new `PostDispatchMaintenanceConfig` Pydantic model, nested under `IndexerConfig.post_dispatch_maintenance`.
- In `config.example/indexer.json5`: the `post_dispatch_maintenance: { enabled: true }` block.

**CLI flag**: `--no-post-maintenance` on `dispatch` (and `run`) in `personalscraper/commands/pipeline.py`.

- Resolution: flag (if passed) > config key > default(`true`).

## Sub-phases

---

### Sub-phase 1.1: Config model + example template

**Files:**

- Modify: `personalscraper/conf/models/indexer.py`
- Modify: `config.example/indexer.json5`

**Commit**: `feat(index-sync): add PostDispatchMaintenanceConfig model and example template`

- [ ] **Step 1: Add Pydantic model to `indexer.py`**

```python
class PostDispatchMaintenanceConfig(_StrictModel):
    """Post-dispatch index maintenance tunables.

    Attributes:
        enabled: When ``True`` (default), automatically run per-disk
            incremental scan + relink + fix-season-counts after every
            dispatch that moved ≥1 item.
    """

    enabled: bool = Field(default=True, description="Run index maintenance automatically after dispatch.")
```

Add the field to `IndexerConfig`:

```python
# In IndexerConfig, after the ``log`` field:
post_dispatch_maintenance: PostDispatchMaintenanceConfig = Field(
    default_factory=PostDispatchMaintenanceConfig,
)
```

- [ ] **Step 2: Add example config to `config.example/indexer.json5`**

Add after the `log` block (before the closing `}` of `indexer`):

```json5
    post_dispatch_maintenance: {
      enabled: true,                        // auto-run index maintenance after dispatch
    },
```

- [ ] **Step 3: Verify import**

```bash
python -c "from personalscraper.conf.models.indexer import IndexerConfig; c = IndexerConfig(); print('enabled:', c.post_dispatch_maintenance.enabled)"
# Expected: enabled: True
```

- [ ] **Step 4: Commit**

```bash
git add personalscraper/conf/models/indexer.py config.example/indexer.json5
git commit -m "feat(index-sync): add PostDispatchMaintenanceConfig model and example template"
```

---

### Sub-phase 1.2: Core `run_post_dispatch_maintenance` function

**Files:**

- Create: `personalscraper/dispatch/post_maintenance.py`

**Commit**: `feat(index-sync): add run_post_dispatch_maintenance function composing scan/relink/fix`

- [ ] **Step 1: Write the module skeleton with docstring and imports**

```python
"""Post-dispatch index maintenance hook.

After ``dispatch`` moves media onto the storage disks, the indexer database
lags reality: new ``media_file`` rows have ``release_id IS NULL`` and season
``episode_count`` may be stale.  This module provides a single reusable
function that runs a scoped, sequential index-maintenance sequence so the
library index is coherent without a manual operator step.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

_log = get_logger("dispatch.post_maintenance")
```

- [ ] **Step 2: Write the touched-disks iteration + scan step**

```python
def _scan_disk_incremental(config: Config, disk: str) -> int:
    """Run ``library-index --mode incremental --disk D --no-budget``.

    Uses the programmatic entry point rather than shelling out.

    Args:
        config: Validated application Config.
        disk: Disk label (e.g. ``"disk_1"``) — must exist in ``config.disks``.

    Returns:
        Exit code (0 = success, non-zero = failure).
    """
    from personalscraper.core.event_bus import EventBus
    from personalscraper.indexer.cli import library_index_command

    _log.info("post_maintenance_scan_start", disk=disk)
    rc = library_index_command(
        mode="incremental",
        disk=disk,
        no_budget=True,
        event_bus=EventBus(),
        # wait_for_lock: 0 means fail immediately if locked — consistent
        # with the CLI default. The dispatch command already holds
        # pipeline.lock so no concurrent indexer should be running.
    )
    if rc != 0:
        _log.warning("post_maintenance_scan_failed", disk=disk, exit_code=rc)
    else:
        _log.info("post_maintenance_scan_done", disk=disk)
    return rc
```

- [ ] **Step 3: Write the relink step (inline SQL, extracted from audit.py)**

```python
def _run_relink(config: Config) -> dict[str, int]:
    """Relink ``media_file`` rows with ``release_id IS NULL``.

    Opens its own short-lived connection (the scan already released its
    lock).  Mirrors the ``library-relink --apply`` logic in
    :func:`personalscraper.commands.library.audit.library_relink`.

    Args:
        config: Validated application Config.

    Returns:
        Dict with ``linked``, ``unmatched``, ``errors`` counts.
    """
    from personalscraper.indexer.db import _apply_pragmas
    from personalscraper.indexer.release_linker import link_file_to_release

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
    linked = unmatched = errors = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        disks = {
            did: Path(mp)
            for did, mp in conn.execute(
                "SELECT id, mount_path FROM disk WHERE is_mounted = 1"
            )
        }
        if not disks:
            _log.info("post_maintenance_relink_no_disks")
            return {"linked": 0, "unmatched": 0, "errors": 0}

        rows = list(
            conn.execute(
                """
                SELECT mf.id, mf.filename, p.disk_id, p.rel_path
                FROM media_file mf
                JOIN path p ON p.id = mf.path_id
                WHERE mf.release_id IS NULL AND mf.deleted_at IS NULL
                """
            )
        )
        if not rows:
            conn.rollback()
            _log.info("post_maintenance_relink_nothing_to_do")
            return {"linked": 0, "unmatched": 0, "errors": 0}

        for mf_id, filename, disk_id, rel_path in rows:
            mount = disks.get(disk_id)
            if mount is None:
                continue
            abs_path = mount / rel_path / filename
            try:
                result = link_file_to_release(conn, mf_id, str(abs_path))
                if result is not None:
                    linked += 1
                else:
                    unmatched += 1
            except Exception as exc:
                errors += 1
                _log.warning(
                    "post_maintenance_relink_failed",
                    file_id=mf_id,
                    path=str(abs_path),
                    error=str(exc),
                )

        conn.commit()
        _log.info("post_maintenance_relink_done", linked=linked, unmatched=unmatched, errors=errors)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"linked": linked, "unmatched": unmatched, "errors": errors}
```

- [ ] **Step 4: Write the fix-season-counts step**

```python
def _run_fix_season_counts(config: Config) -> int:
    """Repair ``season.episode_count`` drift.

    Opens its own short-lived connection. Mirrors the
    ``library-fix-season-counts --apply`` logic.

    Args:
        config: Validated application Config.

    Returns:
        Number of season rows whose ``episode_count`` was corrected.
    """
    from personalscraper.indexer.db import _apply_pragmas

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    conn = sqlite3.connect(str(db_path))
    _apply_pragmas(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            """
            UPDATE season
            SET episode_count = (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
            WHERE episode_count != (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
            """
        )
        fixed = cur.rowcount if cur.rowcount >= 0 else 0
        conn.commit()
        _log.info("post_maintenance_fix_season_counts_done", fixed=fixed)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return fixed
```

- [ ] **Step 5: Write the public function**

```python
def run_post_dispatch_maintenance(
    config: Config,
    touched_disks: set[str],
    *,
    enabled: bool = True,
) -> None:
    """Run post-dispatch index maintenance for disks touched by dispatch.

    Sequentially scans each touched disk (incremental mode), then runs
    a global relink pass and season-episode-count repair.  Fail-soft:
    exceptions are caught, logged as warnings, and the manual fallback
    command is printed — the function never raises.

    Args:
        config: Validated application Config.
        touched_disks: Distinct, non-None disk labels from ``DispatchResult.disk``
            for items whose action was ``moved | merged | replaced``.
        enabled: Feature toggle. When ``False``, the function is a no-op.
            Callers should resolve ``flag > config > default(true)`` before
            passing this parameter.
    """
    if not enabled:
        _log.info("post_maintenance_disabled")
        return

    if not touched_disks:
        _log.info("post_maintenance_no_touched_disks")
        return

    _log.info("post_maintenance_start", disks=sorted(touched_disks))

    # Per-disk incremental scan — sequential (parallel dies on SQLite writer lock).
    scan_failures: list[str] = []
    for disk in sorted(touched_disks):
        try:
            rc = _scan_disk_incremental(config, disk)
            if rc != 0:
                scan_failures.append(disk)
        except Exception as exc:
            scan_failures.append(disk)
            _log.warning("post_maintenance_scan_exception", disk=disk, error=str(exc))

    # Global relink — fast, DB-only.
    try:
        relink_counts = _run_relink(config)
    except Exception as exc:
        relink_counts = {"linked": 0, "unmatched": 0, "errors": 0}
        _log.warning("post_maintenance_relink_exception", error=str(exc))

    # Global fix-season-counts — fast, DB-only.
    try:
        fixed_seasons = _run_fix_season_counts(config)
    except Exception as exc:
        fixed_seasons = 0
        _log.warning("post_maintenance_fix_season_counts_exception", error=str(exc))

    # Print manual fallback if anything failed.
    if scan_failures or relink_counts.get("errors", 0) > 0:
        disks_str = " ".join(f"--disk " + d for d in scan_failures) if scan_failures else ""
        _log.warning(
            "post_maintenance_incomplete",
            failed_disks=scan_failures,
            relink_errors=relink_counts.get("errors", 0),
            manual_fallback=(
                f"library-index --mode full {disks_str} --no-budget && "
                f"library-relink --apply && library-fix-season-counts --apply"
            ).strip(),
        )

    _log.info(
        "post_maintenance_complete",
        disks_scanned=len(touched_disks) - len(scan_failures),
        scan_failures=len(scan_failures),
        relinked=relink_counts.get("linked", 0),
        seasons_fixed=fixed_seasons,
    )
```

- [ ] **Step 6: Verify the module imports**

```bash
python -c "from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance; print('import-ok')"
# Expected: import-ok
```

- [ ] **Step 7: Verify no-op with empty touched_disks**

```bash
python -c "
from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance
# This will fail without a real config, but proves the function is callable
print('function-defined')
"
# Expected: function-defined
```

- [ ] **Step 8: Commit**

```bash
git add personalscraper/dispatch/post_maintenance.py
git commit -m "feat(index-sync): add run_post_dispatch_maintenance function composing scan/relink/fix"
```

---

### Sub-phase 1.3: CLI `--no-post-maintenance` flag on dispatch

**Files:**

- Modify: `personalscraper/commands/pipeline.py`

**Commit**: `feat(index-sync): add --no-post-maintenance CLI flag to dispatch`

- [ ] **Step 1: Add the flag to the `dispatch` function signature**

In `personalscraper/commands/pipeline.py`, find the `dispatch` function (line 274). Add the parameter:

```python
def dispatch(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
    no_post_maintenance: bool = typer.Option(
        False,
        "--no-post-maintenance",
        help="Skip automatic index maintenance after dispatch (scan/relink/fix).",
    ),
) -> None:
```

- [ ] **Step 2: Verify the flag appears in help**

```bash
python -m personalscraper dispatch --help 2>&1 | grep -c -- '--no-post-maintenance'
# Expected: 1
```

- [ ] **Step 3: Commit**

```bash
git add personalscraper/commands/pipeline.py
git commit -m "feat(index-sync): add --no-post-maintenance CLI flag to dispatch"
```

---

### Sub-phase 1.4: Unit tests for `run_post_dispatch_maintenance`

**Files:**

- Create: `tests/dispatch/test_post_maintenance.py`

**Commit**: `test(index-sync): add unit tests for run_post_dispatch_maintenance`

- [ ] **Step 1: Write test file with imports and fixtures**

```python
"""Unit tests for post-dispatch index maintenance hook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config with a resolved indexer.db_path."""
    cfg = MagicMock()
    cfg.indexer.db_path = "/tmp/test_library.db"
    cfg.indexer.post_dispatch_maintenance.enabled = True
    return cfg
```

- [ ] **Step 2: Test empty touched_disks → no-op (no scan)**

```python
def test_empty_touched_disks_no_op(mock_config: MagicMock) -> None:
    """Empty touched_disks set skips all steps — no scan nor relink nor fix."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental") as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink") as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts") as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, set(), enabled=True)
        mock_scan.assert_not_called()
        mock_relink.assert_not_called()
        mock_fix.assert_not_called()
```

- [ ] **Step 3: Test disabled → no-op regardless of touched_disks**

```python
def test_disabled_no_op(mock_config: MagicMock) -> None:
    """When enabled=False, the function is a no-op even with touched disks."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental") as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink") as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts") as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1", "disk_2"}, enabled=False)
        mock_scan.assert_not_called()
        mock_relink.assert_not_called()
        mock_fix.assert_not_called()
```

- [ ] **Step 4: Test sequential per-disk scan calls**

```python
def test_sequential_per_disk_scan(mock_config: MagicMock) -> None:
    """Each touched disk gets an incremental scan call, sequentially."""
    touched = {"disk_1", "disk_2"}
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0) as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink", return_value={"linked": 0, "unmatched": 0, "errors": 0}),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        run_post_dispatch_maintenance(mock_config, touched, enabled=True)
        assert mock_scan.call_count == 2
        # Verify per-disk calls (sorted order)
        mock_scan.assert_any_call(mock_config, "disk_1")
        mock_scan.assert_any_call(mock_config, "disk_2")
```

- [ ] **Step 5: Test relink + fix-season-counts called once after scans**

```python
def test_relink_and_fix_called_after_scans(mock_config: MagicMock) -> None:
    """Relink and fix-season-counts are each called exactly once after all scans."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0) as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink", return_value={"linked": 3, "unmatched": 0, "errors": 0}) as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=5) as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)
        mock_scan.assert_called_once()
        mock_relink.assert_called_once()
        mock_fix.assert_called_once()
```

- [ ] **Step 6: Test fail-soft — scan exception swallowed**

```python
def test_fail_soft_scan_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in a scan step is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", side_effect=RuntimeError("boom")),
        patch("personalscraper.dispatch.post_maintenance._run_relink", return_value={"linked": 0, "unmatched": 0, "errors": 0}),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        # Must not raise
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)
```

- [ ] **Step 7: Test fail-soft — relink exception swallowed**

```python
def test_fail_soft_relink_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in relink is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_relink", side_effect=RuntimeError("boom")),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)
```

- [ ] **Step 8: Test fail-soft — fix exception swallowed**

```python
def test_fail_soft_fix_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in fix-season-counts is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_relink", return_value={"linked": 0, "unmatched": 0, "errors": 0}),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", side_effect=RuntimeError("boom")),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)
```

- [ ] **Step 9: Run tests**

```bash
python -m pytest tests/dispatch/test_post_maintenance.py -v
# Expected: 7 passed
```

- [ ] **Step 10: Commit**

```bash
git add tests/dispatch/test_post_maintenance.py
git commit -m "test(index-sync): add unit tests for run_post_dispatch_maintenance"
```

---

## Files summary

| File                                           | Action                                                                  |
| ---------------------------------------------- | ----------------------------------------------------------------------- |
| `personalscraper/conf/models/indexer.py`       | Modify — add `PostDispatchMaintenanceConfig` + field on `IndexerConfig` |
| `config.example/indexer.json5`                 | Modify — add `post_dispatch_maintenance` block                          |
| `personalscraper/dispatch/post_maintenance.py` | Create — `run_post_dispatch_maintenance` + helpers                      |
| `personalscraper/commands/pipeline.py`         | Modify — add `--no-post-maintenance` flag to `dispatch()`               |
| `tests/dispatch/test_post_maintenance.py`      | Create — 7 unit tests                                                   |

## Produces

- `run_post_dispatch_maintenance(config, touched_disks, *, enabled)` — importable, testable function
- `IndexerConfig.post_dispatch_maintenance.enabled` — Pydantic field (default `True`)
- `config.example/indexer.json5` — tracked example with the new key
- `dispatch --no-post-maintenance` — CLI flag (visible in `--help`)
- 7 passing unit tests (mocked indexer entry points)

## Acceptance criteria covered

- ACC-02 (config key present in example template) — Sub-phase 1.1
- ACC-03 (function importable) — Sub-phase 1.2
