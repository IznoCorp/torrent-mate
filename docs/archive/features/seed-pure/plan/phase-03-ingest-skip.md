# Phase 3 — Ingest skip (always-on)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Insert the always-on `SEED_PURE` skip into the ingest completed-torrent loop in `ingest/ingest.py`, mirroring the existing ratio-skip pattern exactly. Tests cover DESIGN criteria 5 and 6.

**Architecture:** The ingest loop (`ingest.py` line 334) iterates `for torrent in torrents`. Each torrent already carries `torrent.tags: list[str]` (`TorrentItem._base.py:47`). The new check is inserted **after** the ratio-skip block (ending at line 404's `continue`) and **before** content resolution (line 407 `source = client.get_content_path(torrent)`). It mirrors the ratio-skip pattern: `report.skip_count += 1` + `event_bus.emit(ItemProgressed(..., status="skipped", details={"reason": "seed_pure"}))` + `continue`. No config gate — this skip is unconditional.

> **Deviation (3.1, implemented):** `tags` is read via `getattr(torrent, "tags", None) or []` rather than `torrent.tags` directly. The ratio guard already reads `getattr(torrent, "ratio", None)` for the same reason — a degenerate provider response may omit the attribute. The existing regression `tests/ingest/test_ingest.py::test_torrent_ratio_missing_emits_warning` feeds a hand-rolled stub with no `tags` attribute; a bare `torrent.tags` raised `AttributeError` and broke that test. Real `TorrentItem` always carries `tags` (default `[]`), so all seed-pure assertions are unaffected.

**Tech Stack:** Python 3.11+, `pytest`, `unittest.mock`

---

## Gate

**Previous phase produced:**

- `personalscraper/commands/seed.py` registered in `cli.py`.
- `pytest tests/commands/test_seed.py` passes (0 failed).
- `personalscraper seed --help` shows `mark`, `unmark`, `list`.

Verify:

```bash
pytest tests/commands/test_seed.py --tb=short -q
personalscraper seed --help 2>&1 | grep -E "mark|unmark|list"
```

Expected: tests pass; help output contains `mark`, `unmark`, `list`.

---

## Sub-phase 3.1 — Ingest skip + tests

**Files:**

- Modify: `personalscraper/ingest/ingest.py`
- Create: `tests/ingest/test_ingest_seed_pure.py`

### Task 1: Locate the exact insertion point

- [ ] **Step 1: Confirm the current ratio-skip ending line and content-resolution start**

```bash
rg "ratio_below_threshold|get_content_path" --type py personalscraper/ingest/ingest.py -n | head -10
```

Expected output: a line showing `ratio_below_threshold` around line 390-404, and `get_content_path` around line 407. This confirms the insertion window.

### Task 2: Write failing tests first (TDD)

- [ ] **Step 1: Create `tests/ingest/test_ingest_seed_pure.py`**

```python
"""Tests for the always-on SEED_PURE ingest skip (seed-pure feature, criteria 5-6).

Criterion 5 — golden: a completed torrent tagged seed-pure is skipped
(skip_count incremented, ItemProgressed emitted with reason='seed_pure',
no content resolution called).

Criterion 6 — ordering: a torrent that is both below-ratio AND seed-pure is
counted exactly once (the ratio check fires first; seed-pure never double-counts).
A non-tagged torrent is NOT skipped by the seed-pure check.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


def _make_torrent(name: str, hash_: str, tags: list[str], ratio: float = 2.0, progress: float = 1.0):
    """Build a minimal TorrentItem for ingest tests."""
    from personalscraper.api.torrent._base import TorrentItem

    return TorrentItem(
        hash=hash_,
        name=name,
        size_bytes=1024 * 1024 * 100,
        progress=progress,
        state="uploading",
        ratio=ratio,
        tags=tags,
    )


def _run_ingest(torrents, min_ratio=0.0, dry_run=True):
    """Run run_ingest with a stub torrent client returning the given list.

    Returns (report, emitted_events) where emitted_events is a list of all
    ItemProgressed events emitted during the run.
    """
    from personalscraper.ingest.ingest import run_ingest
    from personalscraper.core.event_bus import EventBus
    from personalscraper.pipeline_events import ItemProgressed

    emitted: list[ItemProgressed] = []

    event_bus = EventBus()
    event_bus.subscribe(ItemProgressed, lambda e: emitted.append(e))

    mock_client = MagicMock()
    mock_client.get_completed.return_value = torrents
    mock_client.get_all_hashes.return_value = {t.hash for t in torrents}
    # get_content_path should NOT be called for seed-pure torrents
    mock_client.get_content_path.side_effect = AssertionError(
        "get_content_path called on a seed-pure torrent — skip failed"
    )

    mock_config = MagicMock()
    mock_config.ingest.min_ratio = min_ratio
    mock_config.paths.data_dir = Path("/tmp/test-ingest-seed-pure")
    mock_config.paths.staging_dir = Path("/tmp/test-staging")
    mock_config.thresholds.min_free_space_staging_gb = 0

    mock_settings = MagicMock()

    with patch("personalscraper.ingest.ingest.staging_path", return_value=Path("/tmp/test-staging")), \
         patch("personalscraper.ingest.ingest.find_ingest_dir", return_value="000-INGEST"), \
         patch("personalscraper.ingest.ingest.IngestTracker") as mock_tracker_cls:
        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(
            mock_settings,
            config=mock_config,
            event_bus=event_bus,
            dry_run=dry_run,
            torrent_client=mock_client,
        )

    return report, emitted


# ---------------------------------------------------------------------------
# Criterion 5 — golden: seed-pure torrent is skipped
# ---------------------------------------------------------------------------


def test_seed_pure_torrent_is_skipped():
    """A completed torrent tagged seed-pure is skipped: skip_count += 1."""
    from personalscraper.core.tags import SEED_PURE

    torrent = _make_torrent("Ratio.Seed.2024", "aaa111", tags=[SEED_PURE])
    report, _ = _run_ingest([torrent])

    assert report.skip_count == 1, f"Expected skip_count=1, got {report.skip_count}"
    assert report.success_count == 0
    assert report.error_count == 0


def test_seed_pure_skip_emits_item_progressed_event():
    """Skipping a seed-pure torrent emits ItemProgressed(status='skipped', reason='seed_pure')."""
    from personalscraper.core.tags import SEED_PURE
    from personalscraper.pipeline_events import ItemProgressed

    torrent = _make_torrent("Ratio.Seed.2024", "aaa111", tags=[SEED_PURE])
    _, emitted = _run_ingest([torrent])

    skipped_events = [
        e for e in emitted
        if isinstance(e, ItemProgressed)
        and e.status == "skipped"
        and e.details.get("reason") == "seed_pure"
    ]
    assert len(skipped_events) == 1, (
        f"Expected exactly 1 ItemProgressed(status='skipped', reason='seed_pure'), "
        f"got {len(skipped_events)}. All events: {emitted}"
    )
    assert skipped_events[0].item == "Ratio.Seed.2024"
    assert skipped_events[0].step == "ingest"


def test_seed_pure_skip_does_not_call_get_content_path():
    """A seed-pure torrent is skipped before content resolution (get_content_path not called).

    The mock raises AssertionError if get_content_path is called — so this test
    failing means the skip is missing or fires too late.
    """
    from personalscraper.core.tags import SEED_PURE

    torrent = _make_torrent("Ratio.Seed.2024", "aaa111", tags=[SEED_PURE])
    # _run_ingest's get_content_path.side_effect=AssertionError is the guard.
    # If the test reaches here without error, content resolution was correctly skipped.
    report, _ = _run_ingest([torrent])
    assert report.skip_count == 1


# ---------------------------------------------------------------------------
# Criterion 5 — non-tagged torrent is NOT skipped by the seed-pure check
# ---------------------------------------------------------------------------


def test_non_seed_pure_torrent_not_skipped_by_seed_check():
    """A torrent without the seed-pure tag is NOT skipped by the seed-pure check.

    We use a torrent with no tags — it should proceed past the seed-pure check.
    We stub get_content_path to return a non-existent path so it triggers the
    content-missing path, but skip_count is not incremented by the seed-pure check.
    """
    torrent = _make_torrent("Normal.Movie.2024", "bbb222", tags=[])

    # Override get_content_path to return a missing path (content-missing path)
    from personalscraper.ingest.ingest import run_ingest
    from personalscraper.core.event_bus import EventBus
    from personalscraper.pipeline_events import ItemProgressed

    emitted: list = []
    event_bus = EventBus()
    event_bus.subscribe(ItemProgressed, lambda e: emitted.append(e))

    mock_client = MagicMock()
    mock_client.get_completed.return_value = [torrent]
    mock_client.get_all_hashes.return_value = {torrent.hash}
    mock_client.get_content_path.return_value = Path("/nonexistent/Normal.Movie.2024")

    mock_config = MagicMock()
    mock_config.ingest.min_ratio = 0.0
    mock_config.paths.data_dir = Path("/tmp/test-no-seed-skip")
    mock_config.paths.staging_dir = Path("/tmp/test-staging")
    mock_config.thresholds.min_free_space_staging_gb = 0

    with patch("personalscraper.ingest.ingest.staging_path", return_value=Path("/tmp/test-staging")), \
         patch("personalscraper.ingest.ingest.find_ingest_dir", return_value="000-INGEST"), \
         patch("personalscraper.ingest.ingest.IngestTracker") as mock_tracker_cls:
        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(
            MagicMock(),
            config=mock_config,
            event_bus=event_bus,
            dry_run=True,
            torrent_client=mock_client,
        )

    # get_content_path WAS called (torrent passed the seed-pure check)
    mock_client.get_content_path.assert_called_once()

    # No seed_pure skip event was emitted
    seed_pure_events = [
        e for e in emitted
        if hasattr(e, "details") and e.details.get("reason") == "seed_pure"
    ]
    assert len(seed_pure_events) == 0, f"Unexpected seed_pure skip events: {seed_pure_events}"


# ---------------------------------------------------------------------------
# Criterion 6 — ordering: below-ratio + seed-pure counted once (ratio fires first)
# ---------------------------------------------------------------------------


def test_seed_pure_and_below_ratio_counted_once():
    """A torrent that is both below-ratio AND seed-pure is counted exactly once.

    The ratio check fires first (it precedes the seed-pure check in the loop).
    The torrent must NOT appear in seed_pure skip events — it is handled by ratio.
    skip_count == 1 (not 2).
    """
    from personalscraper.core.tags import SEED_PURE
    from personalscraper.pipeline_events import ItemProgressed

    # ratio=0.1, min_ratio=1.0 → ratio check fires first
    torrent = _make_torrent("Seed.And.Low.Ratio.2024", "ccc333", tags=[SEED_PURE], ratio=0.1)

    emitted: list = []
    from personalscraper.ingest.ingest import run_ingest
    from personalscraper.core.event_bus import EventBus

    event_bus = EventBus()
    event_bus.subscribe(ItemProgressed, lambda e: emitted.append(e))

    mock_client = MagicMock()
    mock_client.get_completed.return_value = [torrent]
    mock_client.get_all_hashes.return_value = {torrent.hash}
    mock_client.get_content_path.side_effect = AssertionError("should not reach content resolution")

    mock_config = MagicMock()
    mock_config.ingest.min_ratio = 1.0  # ratio check will fire
    mock_config.paths.data_dir = Path("/tmp/test-order")
    mock_config.paths.staging_dir = Path("/tmp/test-staging")
    mock_config.thresholds.min_free_space_staging_gb = 0

    with patch("personalscraper.ingest.ingest.staging_path", return_value=Path("/tmp/test-staging")), \
         patch("personalscraper.ingest.ingest.find_ingest_dir", return_value="000-INGEST"), \
         patch("personalscraper.ingest.ingest.IngestTracker") as mock_tracker_cls:
        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(
            MagicMock(),
            config=mock_config,
            event_bus=event_bus,
            dry_run=True,
            torrent_client=mock_client,
        )

    assert report.skip_count == 1, f"Expected skip_count=1 (counted once), got {report.skip_count}"

    # The reason should be ratio_below_threshold (ratio fires first), NOT seed_pure
    ratio_events = [
        e for e in emitted
        if hasattr(e, "details") and e.details.get("reason") == "ratio_below_threshold"
    ]
    seed_pure_events = [
        e for e in emitted
        if hasattr(e, "details") and e.details.get("reason") == "seed_pure"
    ]
    assert len(ratio_events) == 1, f"Expected 1 ratio_below_threshold event, got {ratio_events}"
    assert len(seed_pure_events) == 0, f"Expected 0 seed_pure events (ratio fired first), got {seed_pure_events}"
```

- [ ] **Step 2: Run tests to confirm they FAIL**

```bash
pytest tests/ingest/test_ingest_seed_pure.py --tb=short -q 2>&1 | head -20
```

Expected: tests fail because the seed-pure skip block does not exist yet (non-tagged torrent test may partially pass but the golden will fail).

### Task 3: Add the seed-pure skip to `ingest/ingest.py`

The ratio-skip block ends with `continue` around line 404. The content-resolution line (`source = client.get_content_path(torrent)`) is around line 407. The new block goes between them.

- [ ] **Step 1: Add `SEED_PURE` import at the top of `ingest/ingest.py`**

Find the existing import block in `personalscraper/ingest/ingest.py`:

```bash
rg "^from personalscraper" --type py personalscraper/ingest/ingest.py -n | head -15
```

Add the import alongside the existing core imports:

```python
from personalscraper.core.tags import SEED_PURE
```

- [ ] **Step 2: Insert the seed-pure skip block after the ratio-skip `continue`**

Locate the ratio-skip block (the `continue` around line 404) and the content-resolution line immediately after. Insert the following block between them:

```python
                    # Skip torrents tagged seed-pure — they were downloaded
                    # only for ratio seeding and must never enter the media
                    # library. This check is unconditional (no config gate).
                    # Check order: already-ingested → ratio → seed-pure →
                    # content resolution.
                    # ``tags`` is read defensively (mirroring the ratio guard's
                    # ``getattr(torrent, "ratio", None)``): a degenerate provider
                    # response may omit the attribute, in which case the torrent
                    # simply carries no tags and is never treated as seed-pure.
                    torrent_tags = getattr(torrent, "tags", None) or []
                    if SEED_PURE in torrent_tags:
                        log.info(
                            "ingest.seed_pure_skipped",
                            name=name,
                            tags=torrent_tags,
                        )
                        report.skip_count += 1
                        event_bus.emit(
                            ItemProgressed(
                                step="ingest",
                                item=name,
                                status="skipped",
                                details={"reason": "seed_pure"},
                            )
                        )
                        continue
```

- [ ] **Step 3: Run the ingest skip tests**

```bash
pytest tests/ingest/test_ingest_seed_pure.py -v
```

Expected: all tests pass, `0 failed`.

- [ ] **Step 4: Run the full ingest test suite to check for regressions**

```bash
pytest tests/ingest/ -v --tb=short -q
```

Expected: `0 failed`, `0 errors`.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/ingest/ingest.py tests/ingest/test_ingest_seed_pure.py
git commit -m "feat(seed-pure): always-on ingest skip for SEED_PURE-tagged torrents + tests"
```

---

## Phase 3 Gate

- [ ] **Run `make lint`** — must exit 0.
- [ ] **Run `make test`** — must show `0 failed`, `0 errors`.
- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must exit 0.
- [ ] **Residual literal check:** `rg '"seed-pure"' --type py personalscraper/ingest/` — must return no matches (the constant `SEED_PURE` is used, not a raw string literal).
