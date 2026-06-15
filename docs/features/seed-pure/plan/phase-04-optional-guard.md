# Phase 4 — Opt-in sort/process guard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add `verify_seed_pure` config flags (default `False`) to new `SortConfig` and `ProcessCleanConfig` models in `conf/models/scraper.py`; wire them onto `Config`; extend `run_sort` and `run_clean` to accept an optional `torrent_client`; extend `SortStep` and `CleanStep` in `pipeline_steps.py` to pass `ctx.app.torrent_client` when the flag is on; add per-item seed-pure skip logic inside both runners. Tests cover DESIGN criterion 7.

**Architecture:** The signal-loss reality (DESIGN §4.2) means the guard can only work when a torrent client is available AND the operator opts in. The flag default is `False` so pre-existing configs load unchanged (pre-1.0, no migration). When the flag is off, the `torrent_client` parameter is `None` and the sorter/cleaner behave exactly as today — zero added cost. When the flag is on and a client is available, each staging item is matched to a completed torrent by name (best-effort); if the torrent carries `SEED_PURE`, the item is skipped (log + `StepReport.skip_count++`).

**Tech Stack:** Python 3.11+, `pydantic`, `pytest`, `unittest.mock`

---

## Gate

**Previous phase produced:**

- Always-on `SEED_PURE` skip in `personalscraper/ingest/ingest.py`.
- `pytest tests/ingest/test_ingest_seed_pure.py` passes (0 failed).

Verify:

```bash
pytest tests/ingest/test_ingest_seed_pure.py --tb=short -q
```

Expected: all pass.

---

## Sub-phase 4.1 — Config models (`SortConfig`, `ProcessCleanConfig`)

**Files:**

- Modify: `personalscraper/conf/models/scraper.py`
- Modify: `personalscraper/conf/models/config.py`

### Task 1: Add `SortConfig` and `ProcessCleanConfig` to `conf/models/scraper.py`

The current `scraper.py` exports `ScraperConfig`, `IngestConfig`, and `ThresholdsConfig`. We add two new models.

- [ ] **Step 1: Read the end of `scraper.py` to find the `__all__` and insert point**

```bash
rg "__all__|class " --type py personalscraper/conf/models/scraper.py -n
```

- [ ] **Step 2: Append `SortConfig` and `ProcessCleanConfig` before or after `ThresholdsConfig`**

Add these two classes in `personalscraper/conf/models/scraper.py`:

```python
class SortConfig(_StrictModel):
    """Sort step runtime tunables.

    Attributes:
        verify_seed_pure: When True and a torrent client is available in the
            pipeline context, the sort step re-queries the client for each
            staging item and skips items whose source torrent carries the
            ``seed-pure`` tag. Default ``False`` (opt-in). Has no effect
            when ``False`` — no torrent client query is made.
    """

    verify_seed_pure: bool = Field(
        default=False,
        description=(
            "Re-query the torrent client to skip seed-pure items at sort time. "
            "Opt-in (default False). Requires a torrent client to be configured."
        ),
    )


class ProcessCleanConfig(_StrictModel):
    """Process / clean step runtime tunables.

    Attributes:
        verify_seed_pure: When True and a torrent client is available in the
            pipeline context, the clean step re-queries the client for each
            staging item and skips items whose source torrent carries the
            ``seed-pure`` tag. Default ``False`` (opt-in). Has no effect
            when ``False`` — no torrent client query is made.
    """

    verify_seed_pure: bool = Field(
        default=False,
        description=(
            "Re-query the torrent client to skip seed-pure items at clean time. "
            "Opt-in (default False). Requires a torrent client to be configured."
        ),
    )
```

Update `__all__` in `scraper.py` to include the two new names:

```python
__all__ = [
    "IngestConfig",
    "ProcessCleanConfig",
    "ScraperConfig",
    "SortConfig",
    "ThresholdsConfig",
]
```

- [ ] **Step 3: Wire the new models onto `Config` in `conf/models/config.py`**

In `personalscraper/conf/models/config.py`, update the import from `scraper`:

```python
from personalscraper.conf.models.scraper import IngestConfig, ProcessCleanConfig, ScraperConfig, SortConfig, ThresholdsConfig
```

Add two fields to `class Config` (after the `ingest` field, around line 87):

```python
    sort: SortConfig = Field(default_factory=SortConfig)
    process_clean: ProcessCleanConfig = Field(default_factory=ProcessCleanConfig)
```

Update the `Config` docstring `Attributes` section to document the two new fields.

- [ ] **Step 4: Smoke-test the config models**

```bash
python -c "
from personalscraper.conf.models.scraper import SortConfig, ProcessCleanConfig
s = SortConfig()
p = ProcessCleanConfig()
assert s.verify_seed_pure is False
assert p.verify_seed_pure is False
print('config models OK')
"
```

Expected: `config models OK`

- [ ] **Step 5: Commit**

```bash
git add personalscraper/conf/models/scraper.py personalscraper/conf/models/config.py
git commit -m "feat(seed-pure): add SortConfig + ProcessCleanConfig with verify_seed_pure flag (default off)"
```

---

## Sub-phase 4.2 — `run_sort` guard + `SortStep` wiring

**Files:**

- Modify: `personalscraper/sorter/run.py`
- Modify: `personalscraper/pipeline_steps.py`
- Create: `tests/sorter/test_sort_seed_pure_guard.py`

### Task 2: Write failing tests for the sort guard

- [ ] **Step 1: Create `tests/sorter/test_sort_seed_pure_guard.py`**

```python
"""Tests for the opt-in seed-pure guard in run_sort (criterion 7 — sort half).

When verify_seed_pure=False (default): zero torrent client queries.
When verify_seed_pure=True + stub client with a seed-pure torrent: item skipped.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_torrent_item(name: str, hash_: str, tags: list[str]):
    from personalscraper.api.torrent._base import TorrentItem

    return TorrentItem(
        hash=hash_,
        name=name,
        size_bytes=1024,
        progress=1.0,
        state="uploading",
        tags=tags,
    )


def _make_sort_config(verify_seed_pure: bool = False):
    mock = MagicMock()
    mock.sort.verify_seed_pure = verify_seed_pure
    mock.ingest.min_ratio = 0.0
    return mock


def test_sort_guard_off_no_client_query(tmp_path):
    """When verify_seed_pure=False, run_sort makes zero torrent client queries."""
    from personalscraper.sorter.run import run_sort
    from personalscraper.core.event_bus import EventBus

    mock_client = MagicMock()

    # Patch Sorter.process to return empty list (nothing to sort)
    with patch("personalscraper.sorter.run.Sorter") as mock_sorter_cls, \
         patch("personalscraper.sorter.run._has_unsorted_items", return_value=True), \
         patch("personalscraper.sorter.run.staging_path", return_value=tmp_path), \
         patch("personalscraper.sorter.run.find_ingest_dir", return_value="000-INGEST"):
        mock_sorter = MagicMock()
        mock_sorter.process.return_value = []
        mock_sorter_cls.return_value = mock_sorter

        config = _make_sort_config(verify_seed_pure=False)
        run_sort(
            MagicMock(),
            staging_dir=tmp_path,
            config=config,
            event_bus=EventBus(),
            torrent_client=mock_client,
        )

    # With guard off, the torrent client must never be queried
    mock_client.get_completed.assert_not_called()
    mock_client.get_all_hashes.assert_not_called()


def test_sort_guard_on_skips_seed_pure_item(tmp_path):
    """When verify_seed_pure=True and a completed torrent is seed-pure, the item is skipped."""
    from personalscraper.sorter.run import run_sort
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.tags import SEED_PURE

    seed_torrent = _make_torrent_item("Seed.Movie.2024", "aaa111", [SEED_PURE])
    mock_client = MagicMock()
    mock_client.get_completed.return_value = [seed_torrent]

    # Simulate one staging item named like the seed torrent
    staging_item = tmp_path / "Seed.Movie.2024"
    staging_item.mkdir()

    with patch("personalscraper.sorter.run.Sorter") as mock_sorter_cls, \
         patch("personalscraper.sorter.run._has_unsorted_items", return_value=True), \
         patch("personalscraper.sorter.run.staging_path", return_value=tmp_path), \
         patch("personalscraper.sorter.run.find_ingest_dir", return_value="000-INGEST"):
        mock_sorter = MagicMock()
        mock_sorter.process.return_value = []
        mock_sorter_cls.return_value = mock_sorter

        config = _make_sort_config(verify_seed_pure=True)
        report = run_sort(
            MagicMock(),
            staging_dir=tmp_path,
            config=config,
            event_bus=EventBus(),
            torrent_client=mock_client,
        )

    # With guard on, the client was queried
    mock_client.get_completed.assert_called_once()
    # The seed-pure item must be in the skip count
    assert report.skip_count >= 1, f"Expected skip_count >= 1 for seed-pure item, got {report.skip_count}"


def test_sort_guard_on_no_client_is_inert(tmp_path):
    """When verify_seed_pure=True but torrent_client=None, guard is inert (no crash)."""
    from personalscraper.sorter.run import run_sort
    from personalscraper.core.event_bus import EventBus

    with patch("personalscraper.sorter.run.Sorter") as mock_sorter_cls, \
         patch("personalscraper.sorter.run._has_unsorted_items", return_value=True), \
         patch("personalscraper.sorter.run.staging_path", return_value=tmp_path), \
         patch("personalscraper.sorter.run.find_ingest_dir", return_value="000-INGEST"):
        mock_sorter = MagicMock()
        mock_sorter.process.return_value = []
        mock_sorter_cls.return_value = mock_sorter

        config = _make_sort_config(verify_seed_pure=True)
        # Must not crash
        report = run_sort(
            MagicMock(),
            staging_dir=tmp_path,
            config=config,
            event_bus=EventBus(),
            torrent_client=None,
        )

    # No skip from seed-pure (client unavailable)
    assert report.error_count == 0
```

- [ ] **Step 2: Run tests to confirm they FAIL**

```bash
pytest tests/sorter/test_sort_seed_pure_guard.py --tb=short -q 2>&1 | head -20
```

Expected: `TypeError` — `run_sort` does not accept a `torrent_client` parameter yet.

### Task 3: Extend `run_sort` with the optional guard

The current `run_sort` signature (`sorter/run.py` line 28):

```python
def run_sort(
    settings: Settings,
    staging_dir: Path,
    config: Config,
    dry_run: bool = False,
    *,
    event_bus: EventBus,
) -> StepReport:
```

- [ ] **Step 1: Add `torrent_client` param and guard logic to `run_sort`**

Add `SEED_PURE` import at the top of `sorter/run.py`:

```python
from personalscraper.core.tags import SEED_PURE
```

Update the function signature:

```python
def run_sort(
    settings: Settings,
    staging_dir: Path,
    config: Config,
    dry_run: bool = False,
    *,
    event_bus: EventBus,
    torrent_client: object | None = None,
) -> StepReport:
```

Add the following docstring extension to the `Args:` section:

```
        torrent_client: Optional torrent client. When ``config.sort.verify_seed_pure``
            is True and this is not None, each staging item is matched to a completed
            torrent by name and skipped if that torrent carries ``SEED_PURE``. When
            ``config.sort.verify_seed_pure`` is False (default), this argument is
            ignored — no client query is made.
```

Add a seed-pure pre-filter block **after** the fast-skip check and **before** the `Sorter` construction. The pre-filter builds a set of names to skip, then passes it into the sorter or skips items manually:

```python
    # --- opt-in seed-pure guard -------------------------------------------
    # When enabled + a client is available: build a name-based skip-set from
    # completed torrents carrying SEED_PURE before the Sorter runs.
    seed_pure_names: set[str] = set()
    if getattr(config, "sort", None) is not None and config.sort.verify_seed_pure and torrent_client is not None:
        try:
            completed = torrent_client.get_completed()
            seed_pure_names = {t.name for t in completed if SEED_PURE in t.tags}
            if seed_pure_names:
                log.info("sort.seed_pure_guard_active", skipping=sorted(seed_pure_names))
        except Exception as exc:  # fail-soft: guard must not abort the sort
            log.warning("sort.seed_pure_guard_failed", error=str(exc))
    # -----------------------------------------------------------------------
```

After the sorter processes items, accumulate skips for seed-pure names. The simplest approach is to iterate `ingest_dir` contents before calling `sorter.process` and count/skip matched items:

```python
    # Apply seed-pure skip before passing to the Sorter.
    report = StepReport(name="sort")
    if seed_pure_names:
        ingest_items = list(ingest_dir.iterdir()) if ingest_dir.exists() else []
        skipped_items: list[str] = []
        for item in ingest_items:
            if item.name in seed_pure_names:
                log.info("sort.seed_pure_item_skipped", name=item.name)
                report.skip_count += 1
                skipped_items.append(item.name)
                event_bus.emit(
                    ItemProgressed(
                        step="sort",
                        item=item.name,
                        status="skipped",
                        details={"reason": "seed_pure"},
                    )
                )
        # Only pass non-seed-pure items to the Sorter (by temporarily hiding them
        # is complex; instead we rely on the Sorter skipping items not found in
        # ingest_dir — which it does naturally if we filter the list).
        # For simplicity: if ALL items are seed-pure, return early.
        remaining = [i for i in ingest_items if i.name not in seed_pure_names]
        if not remaining:
            return report
```

Then keep the existing `sorter.process(ingest_dir, dest_root=staging_dir)` call for non-seed-pure items and merge results into `report`:

```python
    cleaner = NameCleaner()
    sorter = Sorter(config=config, cleaner=cleaner, dry_run=dry_run)
    results = sorter.process(ingest_dir, dest_root=staging_dir)

    for r in results:
        # ... existing result handling ...
```

> **Note to implementer:** the exact integration point depends on how `Sorter.process` iterates `ingest_dir`. Read `sorter/sorter.py` lines 60-120 before implementing. If `Sorter.process` iterates directory contents internally, the cleanest approach is to pre-move seed-pure items aside (into a temp subdir) before calling `process`, then move them back. Alternatively, add a `skip_names: set[str]` parameter to `Sorter.process`. Choose the approach that requires the fewest changes to `sorter.py`; document the choice in a comment.

- [ ] **Step 2: Run the sort guard tests**

```bash
pytest tests/sorter/test_sort_seed_pure_guard.py -v
```

Expected: all tests pass, `0 failed`.

- [ ] **Step 3: Update `SortStep` in `pipeline_steps.py`**

The current `SortStep.__call__` (lines 43-65) calls `run_sort` without `torrent_client`. Add it:

```python
class SortStep:
    """Adapter for the sort step (``personalscraper.sorter.run.run_sort``)."""

    name = "sort"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the sort step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with per-item sort outcomes.
        """
        from personalscraper.sorter.run import run_sort

        return run_sort(
            ctx.app.settings,
            staging_dir=ctx.app.config.paths.staging_dir,
            dry_run=ctx.dry_run,
            config=ctx.app.config,
            event_bus=ctx.app.event_bus,
            torrent_client=ctx.app.torrent_client if getattr(ctx.app.config, "sort", None) is not None and ctx.app.config.sort.verify_seed_pure else None,
        )
```

- [ ] **Step 4: Commit**

```bash
git add personalscraper/sorter/run.py personalscraper/pipeline_steps.py tests/sorter/test_sort_seed_pure_guard.py
git commit -m "feat(seed-pure): opt-in seed-pure guard in run_sort + SortStep wiring + tests"
```

---

## Sub-phase 4.3 — `run_clean` guard + `CleanStep` wiring

**Files:**

- Modify: `personalscraper/process/run.py`
- Modify: `personalscraper/pipeline_steps.py`
- Create: `tests/process/test_clean_seed_pure_guard.py`

### Task 4: Write failing tests for the clean guard

- [ ] **Step 1: Create `tests/process/test_clean_seed_pure_guard.py`**

```python
"""Tests for the opt-in seed-pure guard in run_clean (criterion 7 — clean half).

When verify_seed_pure=False (default): zero torrent client queries.
When verify_seed_pure=True + stub client with a seed-pure torrent: item skipped.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_torrent_item(name: str, tags: list[str]):
    from personalscraper.api.torrent._base import TorrentItem

    return TorrentItem(
        hash="aaa111",
        name=name,
        size_bytes=1024,
        progress=1.0,
        state="uploading",
        tags=tags,
    )


def _make_config(verify_seed_pure: bool = False):
    mock = MagicMock()
    mock.process_clean.verify_seed_pure = verify_seed_pure
    return mock


def _make_clean_config(tmp_path, verify_seed_pure: bool = False):
    """Return a mock Config with staging_dir set to tmp_path and process_clean flag."""
    cfg = MagicMock()
    cfg.process_clean.verify_seed_pure = verify_seed_pure
    cfg.paths.staging_dir = tmp_path
    cfg.fuzzy_match = MagicMock()
    return cfg


def test_clean_guard_off_no_client_query(tmp_path):
    """When verify_seed_pure=False, run_clean makes zero torrent client queries."""
    from personalscraper.process.run import run_clean
    from personalscraper.core.event_bus import EventBus

    mock_client = MagicMock()

    # Patch the heavy internals so run_clean returns quickly with no I/O
    with patch("personalscraper.process.run.find_by_file_type", return_value=MagicMock()), \
         patch("personalscraper.process.run.folder_name", return_value="001-MOVIES"), \
         patch("personalscraper.process.reclean._has_polluted_folders", return_value=False), \
         patch("personalscraper.process.extract.extract_release_archives", return_value=MagicMock(success_count=0, error_count=0, details=[], warnings=[])), \
         patch("personalscraper.process.extract.strip_sample_artifacts", return_value=MagicMock(success_count=0, error_count=0, details=[], warnings=[])), \
         patch("personalscraper.process.run.dedup_folders", return_value=([], [])):
        config = _make_clean_config(tmp_path, verify_seed_pure=False)
        run_clean(
            MagicMock(),
            dry_run=True,
            config=config,
            event_bus=EventBus(),
            torrent_client=mock_client,
        )

    mock_client.get_completed.assert_not_called()


def test_clean_guard_on_skips_seed_pure_item(tmp_path):
    """When verify_seed_pure=True and a completed torrent is seed-pure, the item is skipped."""
    from personalscraper.process.run import run_clean
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.tags import SEED_PURE

    seed_torrent = _make_torrent_item("Seed.Movie.2024", [SEED_PURE])
    mock_client = MagicMock()
    mock_client.get_completed.return_value = [seed_torrent]

    with patch("personalscraper.process.run.find_by_file_type", return_value=MagicMock()), \
         patch("personalscraper.process.run.folder_name", return_value="001-MOVIES"), \
         patch("personalscraper.process.reclean._has_polluted_folders", return_value=False), \
         patch("personalscraper.process.extract.extract_release_archives", return_value=MagicMock(success_count=0, error_count=0, details=[], warnings=[])), \
         patch("personalscraper.process.extract.strip_sample_artifacts", return_value=MagicMock(success_count=0, error_count=0, details=[], warnings=[])), \
         patch("personalscraper.process.run.dedup_folders", return_value=([], [])):
        config = _make_clean_config(tmp_path, verify_seed_pure=True)
        report = run_clean(
            MagicMock(),
            dry_run=True,
            config=config,
            event_bus=EventBus(),
            torrent_client=mock_client,
        )

    mock_client.get_completed.assert_called_once()
    assert report.skip_count >= 1, f"Expected skip_count >= 1 for seed-pure item, got {report.skip_count}"


def test_clean_guard_on_no_client_is_inert(tmp_path):
    """When verify_seed_pure=True but torrent_client=None, guard is inert (no crash)."""
    from personalscraper.process.run import run_clean
    from personalscraper.core.event_bus import EventBus

    with patch("personalscraper.process.run.find_by_file_type", return_value=MagicMock()), \
         patch("personalscraper.process.run.folder_name", return_value="001-MOVIES"), \
         patch("personalscraper.process.reclean._has_polluted_folders", return_value=False), \
         patch("personalscraper.process.extract.extract_release_archives", return_value=MagicMock(success_count=0, error_count=0, details=[], warnings=[])), \
         patch("personalscraper.process.extract.strip_sample_artifacts", return_value=MagicMock(success_count=0, error_count=0, details=[], warnings=[])), \
         patch("personalscraper.process.run.dedup_folders", return_value=([], [])):
        config = _make_clean_config(tmp_path, verify_seed_pure=True)
        report = run_clean(
            MagicMock(),
            dry_run=True,
            config=config,
            event_bus=EventBus(),
            torrent_client=None,
        )

    assert report.error_count == 0
```

- [ ] **Step 2: Run tests to confirm they FAIL**

```bash
pytest tests/process/test_clean_seed_pure_guard.py --tb=short -q 2>&1 | head -20
```

Expected: `TypeError` — `run_clean` does not accept `torrent_client` yet.

### Task 5: Extend `run_clean` with the optional guard

Current `run_clean` signature (find it with `rg "def run_clean" --type py personalscraper/process/run.py -n`).

- [ ] **Step 1: Add `SEED_PURE` import at top of `process/run.py`**

```python
from personalscraper.core.tags import SEED_PURE
```

- [ ] **Step 2: Add `torrent_client` param and guard to `run_clean`**

Find the `run_clean` function in `personalscraper/process/run.py` and update its signature:

```python
def run_clean(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    *,
    event_bus: EventBus,
    torrent_client: object | None = None,
) -> StepReport:
```

Add to its docstring `Args:` section:

```
        torrent_client: Optional torrent client. When ``config.process_clean.verify_seed_pure``
            is True and this is not None, each staging item is matched to a completed
            torrent by name and skipped if that torrent carries ``SEED_PURE``. When
            ``config.process_clean.verify_seed_pure`` is False (default), this argument
            is ignored.
```

Add the seed-pure pre-filter block at the start of `run_clean`'s work body (after the fast-skip / category enumeration, before the reclean loop):

```python
    # --- opt-in seed-pure guard -------------------------------------------
    seed_pure_names: set[str] = set()
    if (
        getattr(config, "process_clean", None) is not None
        and config.process_clean.verify_seed_pure
        and torrent_client is not None
    ):
        try:
            completed = torrent_client.get_completed()
            seed_pure_names = {t.name for t in completed if SEED_PURE in t.tags}
            if seed_pure_names:
                log.info("process_clean.seed_pure_guard_active", skipping=sorted(seed_pure_names))
        except Exception as exc:
            log.warning("process_clean.seed_pure_guard_failed", error=str(exc))
    # -----------------------------------------------------------------------
```

Inside the per-item processing loop (wherever `run_clean` iterates staging items), add a skip check before the actual clean operation:

```python
            if item.name in seed_pure_names:
                log.info("process_clean.seed_pure_item_skipped", name=item.name)
                report.skip_count += 1
                event_bus.emit(
                    ItemProgressed(
                        step="clean",
                        item=item.name,
                        status="skipped",
                        details={"reason": "seed_pure"},
                    )
                )
                continue
```

> **Note to implementer:** `run_clean` in `process/run.py` calls `reclean_folders` and `dedup_folders`. Read the function body carefully to identify where per-item iteration happens and insert the skip at the earliest sensible point (before `reclean_folders` is called for that item). If `reclean_folders` processes all items at once (batch), insert a pre-filter that removes seed-pure items from the category dirs list passed to it.

- [ ] **Step 3: Update `CleanStep` in `pipeline_steps.py`**

Update `CleanStep.__call__` (lines 68-89):

```python
class CleanStep:
    """Adapter for the clean process sub-step (``personalscraper.process.run.run_clean``)."""

    name = "clean"

    def __call__(self, ctx: StepContext) -> StepReport:
        """Execute the clean sub-step.

        Args:
            ctx: Pipeline step context with config, settings, and flags.

        Returns:
            A ``StepReport`` with per-item cleaning outcomes.
        """
        from personalscraper.process.run import run_clean

        return run_clean(
            ctx.app.settings,
            dry_run=ctx.dry_run,
            config=ctx.app.config,
            event_bus=ctx.app.event_bus,
            torrent_client=(
                ctx.app.torrent_client
                if getattr(ctx.app.config, "process_clean", None) is not None
                and ctx.app.config.process_clean.verify_seed_pure
                else None
            ),
        )
```

- [ ] **Step 4: Run the clean guard tests**

```bash
pytest tests/process/test_clean_seed_pure_guard.py -v
```

Expected: all tests pass, `0 failed`.

- [ ] **Step 5: Run full test suite to catch regressions**

```bash
pytest tests/sorter/ tests/process/ tests/ingest/ -v --tb=short -q
```

Expected: `0 failed`, `0 errors`.

- [ ] **Step 6: Commit**

```bash
git add personalscraper/process/run.py personalscraper/pipeline_steps.py tests/process/test_clean_seed_pure_guard.py
git commit -m "feat(seed-pure): opt-in seed-pure guard in run_clean + CleanStep wiring + tests"
```

---

## Phase 4 Gate

- [ ] **Run `make lint`** — must exit 0.
- [ ] **Run `make test`** — must show `0 failed`, `0 errors`.
- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must exit 0.
- [ ] **Config smoke test:** `python -c "from personalscraper.conf.models.scraper import SortConfig, ProcessCleanConfig; s=SortConfig(); p=ProcessCleanConfig(); assert not s.verify_seed_pure; assert not p.verify_seed_pure; print('flags default off OK')"` — must print `flags default off OK`.
- [ ] **Residual literal check:** `rg '"seed-pure"' --type py personalscraper/sorter/ personalscraper/process/` — must return no matches (only `SEED_PURE` constant used, not raw strings).
