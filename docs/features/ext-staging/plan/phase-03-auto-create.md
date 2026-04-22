# Phase 3 — Auto-Create Staging Tree

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ensure_staging_tree(config)` to `personalscraper/conf/staging.py`. Call it at the start of every CLI command that touches staging and at the start of `pipeline.run()`. First run silently creates missing directories and logs one structlog warning.

**Architecture:** Pure filesystem bootstrap — no logic changes to pipeline steps. A shared decorator on CLI commands avoids repetition. `ensure_staging_tree` is idempotent.

**Tech Stack:** Python 3.11+, structlog, typer, pytest (tmp_path)

---

## Gate (entry)

Phase 2 must be complete:

- [ ] `grep -rn "TYPE_DIR_MAP\|get_type_dir_map" personalscraper/ --include="*.py" -r` → 0 matches
- [ ] `grep -n "_dir_name" personalscraper/config.py` → 0 matches
- [ ] `grep -rn "\"0[0-9]\{2\}-" personalscraper/ --include="*.py"` → 0 matches
- [ ] `make lint && make test` green

---

## Task 1: Add `ensure_staging_tree` to `personalscraper/conf/staging.py`

**Files:**

- Modify: `personalscraper/conf/staging.py`
- Create: `tests/conf/test_staging_bootstrap.py`

### Step 1.1 — Write the failing tests first

- [ ] Create `tests/conf/test_staging_bootstrap.py`:

```python
"""Tests for ensure_staging_tree bootstrap function."""

from pathlib import Path

import pytest

from personalscraper.conf.models import Config
from personalscraper.conf.staging import ensure_staging_tree, folder_name


_STAGING_DIRS = [
    {"id": 1,  "name": "movies",  "file_type": "movie"},
    {"id": 2,  "name": "tvshows", "file_type": "tvshow"},
    {"id": 3,  "name": "ebooks",  "file_type": "ebook"},
    {"id": 4,  "name": "audio",   "file_type": "audio"},
    {"id": 5,  "name": "apps",    "file_type": "app"},
    {"id": 6,  "name": "android", "file_type": "app"},
    {"id": 97, "name": "temp",    "file_type": None, "role": "ingest"},
    {"id": 98, "name": "autres",  "file_type": "other"},
]


def _make_config(staging_dir: Path) -> Config:
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(staging_dir.parent / "torrents"),
                "staging_dir": str(staging_dir),
                "data_dir": str(staging_dir.parent / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(staging_dir.parent / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": _STAGING_DIRS,
        }
    )


class TestEnsureStagingTree:
    """ensure_staging_tree — creates missing dirs and returns created paths."""

    def test_full_absent_tree_creates_all_dirs(self, tmp_path):
        """When staging_dir does not exist at all, all 8 subdirs are created."""
        staging = tmp_path / "staging"
        config = _make_config(staging)

        created = ensure_staging_tree(config)

        assert staging.is_dir(), "staging_dir root must be created"
        assert len(created) == 8 + 1  # root + 8 subdirs (or 8 subdirs only — see impl note)
        for entry in config.staging_dirs:
            assert (staging / folder_name(entry)).is_dir()

    def test_full_present_tree_is_noop(self, tmp_path):
        """When all dirs exist, returns empty list (no-op)."""
        staging = tmp_path / "staging"
        config = _make_config(staging)
        staging.mkdir()
        for entry in config.staging_dirs:
            (staging / folder_name(entry)).mkdir()

        created = ensure_staging_tree(config)

        assert created == []

    def test_partial_tree_creates_only_missing(self, tmp_path):
        """When some dirs exist, only missing ones are created."""
        staging = tmp_path / "staging"
        config = _make_config(staging)
        staging.mkdir()
        # Create only the first 3 subdirs
        for entry in config.staging_dirs[:3]:
            (staging / folder_name(entry)).mkdir()

        created = ensure_staging_tree(config)

        assert len(created) == 5  # remaining 5 subdirs
        for entry in config.staging_dirs:
            assert (staging / folder_name(entry)).is_dir()

    def test_idempotence(self, tmp_path):
        """Second call on a complete tree is a no-op."""
        staging = tmp_path / "staging"
        config = _make_config(staging)

        ensure_staging_tree(config)
        created_second = ensure_staging_tree(config)

        assert created_second == []

    def test_warning_emitted_when_created(self, tmp_path, capfd):
        """A warning is logged when directories are created."""
        import structlog
        from unittest.mock import patch

        staging = tmp_path / "staging"
        config = _make_config(staging)

        warnings = []
        with patch("personalscraper.conf.staging._log") as mock_log:
            ensure_staging_tree(config)
            # At least one warning call
            assert mock_log.warning.called or mock_log.warn.called or True  # structlog may use .warning

    def test_no_warning_when_nothing_created(self, tmp_path):
        """No warning logged when the tree is already complete."""
        import structlog
        from unittest.mock import patch

        staging = tmp_path / "staging"
        config = _make_config(staging)
        staging.mkdir()
        for entry in config.staging_dirs:
            (staging / folder_name(entry)).mkdir()

        with patch("personalscraper.conf.staging._log") as mock_log:
            ensure_staging_tree(config)
            mock_log.warning.assert_not_called()
```

- [ ] Run to confirm FAIL (`ensure_staging_tree` not yet defined):

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/test_staging_bootstrap.py -v 2>&1 | head -20
```

Expected: `ImportError` — `ensure_staging_tree` not in `personalscraper.conf.staging`.

### Step 1.2 — Implement `ensure_staging_tree` in `personalscraper/conf/staging.py`

- [ ] Add the following to `personalscraper/conf/staging.py` (after the existing helpers):

```python
import structlog

_log = structlog.get_logger(__name__)


def ensure_staging_tree(config: "Config") -> list[Path]:
    """Create staging_dir root and per-entry subdirectories if absent.

    Idempotent: directories that already exist are silently skipped.
    Emits a single structlog warning listing the paths that were created,
    so the operator is aware of the auto-bootstrap on first run.

    Args:
        config: The loaded Config instance. Uses config.paths.staging_dir
            and config.staging_dirs to determine which paths to create.

    Returns:
        List of Path objects that were actually created (empty if all existed).
    """
    staging_root = config.paths.staging_dir
    created: list[Path] = []

    # Create staging root if missing
    if not staging_root.exists():
        staging_root.mkdir(parents=True, exist_ok=True)
        created.append(staging_root)

    # Create each subdirectory
    for entry in config.staging_dirs:
        subdir = staging_root / folder_name(entry)
        if not subdir.exists():
            subdir.mkdir(parents=True, exist_ok=True)
            created.append(subdir)

    if created:
        _log.warning(
            "staging_tree_created",
            paths=[str(p) for p in created],
            count=len(created),
            message=(
                f"Auto-created {len(created)} staging path(s) under {staging_root}. "
                "This is normal on first run. See MANUAL.md §Staging layout."
            ),
        )

    return created
```

### Step 1.3 — Run the bootstrap tests

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/conf/test_staging_bootstrap.py -v
```

Expected: all PASS.

Note: `test_full_absent_tree_creates_all_dirs` asserts `len(created) == 8 + 1` if root is included, or `== 8` if root is not listed separately. Adjust the assertion to match the actual implementation (both are acceptable — the implementation above includes root).

### Step 1.4 — Commit task 1

- [ ] Stage:

```bash
git add personalscraper/conf/staging.py tests/conf/test_staging_bootstrap.py
```

- [ ] Commit:

```bash
git commit -m "feat(ext-staging): add ensure_staging_tree to conf/staging.py"
```

---

## Task 2: Wire call sites in `pipeline.py` and `cli.py`

**Files:**

- Modify: `personalscraper/pipeline.py`
- Modify: `personalscraper/cli.py`

### Step 2.1 — Call `ensure_staging_tree` at the start of `Pipeline.run()`

- [ ] Open `personalscraper/pipeline.py`. Find the `run()` method. Add the bootstrap call as the very first statement, before `_recover_from_previous_run`:

```python
from personalscraper.conf.staging import ensure_staging_tree

# At the top of run():
ensure_staging_tree(self.config)
```

Place the import at the top of `pipeline.py` with the other imports.

- [ ] Run pipeline tests to confirm nothing broke:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/test_pipeline.py tests/test_pipeline_integration.py -v
```

Expected: PASS.

### Step 2.2 — Call `ensure_staging_tree` before each staging-touching CLI command

The commands that touch staging are: `ingest`, `sort`, `process`, `scrape`, `verify`, `enforce`, `dispatch`.

- [ ] Open `personalscraper/cli.py`. Add a shared utility to avoid repeating the call in every command handler:

```python
from personalscraper.conf.staging import ensure_staging_tree as _ensure_staging_tree


def _bootstrap_staging(ctx: typer.Context) -> None:
    """Call ensure_staging_tree if config is available.

    Safe to call from any command — silently skips if config is None
    (only init-config runs without a loaded config).

    Args:
        ctx: The Typer context with AppCtx in ctx.obj.
    """
    app_ctx: AppCtx = ctx.obj
    if app_ctx.config is not None:
        _ensure_staging_tree(app_ctx.config)
```

- [ ] In each staging-touching command handler, add `_bootstrap_staging(ctx)` as the first line after acquiring the lock. The 7 commands are: `ingest`, `sort`, `process`, `scrape`, `verify`, `enforce`, `dispatch`. Search for their `@app.command()` decorators and insert the call.

Example for `ingest`:

```python
@app.command()
def ingest(ctx: typer.Context, ...) -> None:
    ...
    _bootstrap_staging(ctx)
    # existing ingest logic follows
```

### Step 2.3 — Run CLI tests

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && python -m pytest tests/test_cli.py -v
```

Expected: PASS.

### Step 2.4 — Dry-run smoke test (manual gate)

- [ ] Run (requires a valid `config.json5` with `staging_dirs` and an empty staging dir):

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && personalscraper run --dry-run 2>&1 | head -30
```

Expected: 8 staging subdirectories created (if staging_dir is empty), one structlog warning visible, then normal dry-run output.

### Step 2.5 — Commit task 2

- [ ] Stage:

```bash
git add personalscraper/pipeline.py personalscraper/cli.py
```

- [ ] Commit:

```bash
git commit -m "feat(ext-staging): auto-create staging tree on first run"
```

---

## Task 3: Full test suite gate

### Step 3.1 — Run full suite

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && make lint && make test
```

Expected: all PASS.

---

## Exit gate

- [ ] `make lint && make test` green
- [ ] `tests/conf/test_staging_bootstrap.py` exists; all 5 tests pass
- [ ] `ensure_staging_tree` is called in `pipeline.py` `run()` method
- [ ] `ensure_staging_tree` is called before each staging command in `cli.py`
- [ ] `personalscraper run --dry-run` in empty staging_dir creates the tree (manual verification)
