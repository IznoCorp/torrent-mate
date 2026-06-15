"""Tests for the always-on SEED_PURE ingest skip (seed-pure feature, criteria 5-6).

Criterion 5 — golden: a completed torrent tagged seed-pure is skipped
(skip_count incremented, ItemProgressed emitted with reason='seed_pure',
no content resolution called).

Criterion 6 — ordering: a torrent that is both below-ratio AND seed-pure is
counted exactly once (the ratio check fires first; seed-pure never double-counts).
A non-tagged torrent is NOT skipped by the seed-pure check.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.api.torrent._base import TorrentItem
from personalscraper.core.event_bus import EventBus
from personalscraper.core.tags import SEED_PURE
from personalscraper.ingest.ingest import run_ingest
from personalscraper.pipeline_events import ItemProgressed


def _make_torrent(
    name: str,
    hash_: str,
    tags: list[str],
    ratio: float = 2.0,
    progress: float = 1.0,
) -> TorrentItem:
    """Build a minimal TorrentItem for ingest tests.

    Args:
        name: Torrent display name.
        hash_: Torrent info hash.
        tags: Tag labels carried by the torrent.
        ratio: Seed ratio (uploaded / downloaded).
        progress: Download progress (0.0 to 1.0).

    Returns:
        A TorrentItem populated with the given values.
    """
    return TorrentItem(
        hash=hash_,
        name=name,
        size_bytes=1024 * 1024 * 100,
        progress=progress,
        state="uploading",
        ratio=ratio,
        tags=tags,
    )


def _run_ingest(
    torrents: list[TorrentItem],
    min_ratio: float = 0.0,
    dry_run: bool = True,
) -> tuple[object, list[ItemProgressed]]:
    """Run run_ingest with a stub torrent client returning the given list.

    The stub's ``get_content_path`` raises ``AssertionError`` so any torrent
    reaching content resolution fails the test loudly — this is the guard that
    proves the seed-pure skip fires *before* content resolution.

    Args:
        torrents: Completed torrents the stub client returns.
        min_ratio: ``config.ingest.min_ratio`` value to use.
        dry_run: Whether to run in dry-run mode.

    Returns:
        A ``(report, emitted)`` pair where ``emitted`` collects every
        ``ItemProgressed`` event emitted during the run.
    """
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

    with (
        patch("personalscraper.ingest.ingest.staging_path", return_value=Path("/tmp/test-staging")),
        patch("personalscraper.ingest.ingest.find_ingest_dir", return_value="000-INGEST"),
        patch("personalscraper.ingest.ingest.IngestTracker") as mock_tracker_cls,
    ):
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


def test_seed_pure_torrent_is_skipped() -> None:
    """A completed torrent tagged seed-pure is skipped: skip_count += 1."""
    torrent = _make_torrent("Ratio.Seed.2024", "aaa111", tags=[SEED_PURE])
    report, _ = _run_ingest([torrent])

    assert report.skip_count == 1, f"Expected skip_count=1, got {report.skip_count}"
    assert report.success_count == 0
    assert report.error_count == 0


def test_seed_pure_skip_emits_item_progressed_event() -> None:
    """Skipping a seed-pure torrent emits ItemProgressed(status='skipped', reason='seed_pure')."""
    torrent = _make_torrent("Ratio.Seed.2024", "aaa111", tags=[SEED_PURE])
    _, emitted = _run_ingest([torrent])

    skipped_events = [
        e
        for e in emitted
        if isinstance(e, ItemProgressed) and e.status == "skipped" and e.details.get("reason") == "seed_pure"
    ]
    assert len(skipped_events) == 1, (
        f"Expected exactly 1 ItemProgressed(status='skipped', reason='seed_pure'), "
        f"got {len(skipped_events)}. All events: {emitted}"
    )
    assert skipped_events[0].item == "Ratio.Seed.2024"
    assert skipped_events[0].step == "ingest"


def test_seed_pure_skip_does_not_call_get_content_path() -> None:
    """A seed-pure torrent is skipped before content resolution (get_content_path not called).

    The mock raises AssertionError if get_content_path is called — so this test
    failing means the skip is missing or fires too late.
    """
    torrent = _make_torrent("Ratio.Seed.2024", "aaa111", tags=[SEED_PURE])
    # _run_ingest's get_content_path.side_effect=AssertionError is the guard.
    # If the test reaches here without error, content resolution was correctly skipped.
    report, _ = _run_ingest([torrent])
    assert report.skip_count == 1


# ---------------------------------------------------------------------------
# Criterion 5 — non-tagged torrent is NOT skipped by the seed-pure check
# ---------------------------------------------------------------------------


def test_non_seed_pure_torrent_not_skipped_by_seed_check() -> None:
    """A torrent without the seed-pure tag is NOT skipped by the seed-pure check.

    We use a torrent with no tags — it should proceed past the seed-pure check.
    We stub get_content_path to return a non-existent path so it triggers the
    content-missing path, but skip_count is not incremented by the seed-pure check.
    """
    torrent = _make_torrent("Normal.Movie.2024", "bbb222", tags=[])

    emitted: list[ItemProgressed] = []
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

    with (
        patch("personalscraper.ingest.ingest.staging_path", return_value=Path("/tmp/test-staging")),
        patch("personalscraper.ingest.ingest.find_ingest_dir", return_value="000-INGEST"),
        patch("personalscraper.ingest.ingest.IngestTracker") as mock_tracker_cls,
    ):
        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        run_ingest(
            MagicMock(),
            config=mock_config,
            event_bus=event_bus,
            dry_run=True,
            torrent_client=mock_client,
        )

    # get_content_path WAS called (torrent passed the seed-pure check)
    mock_client.get_content_path.assert_called_once()

    # No seed_pure skip event was emitted
    seed_pure_events = [e for e in emitted if e.details.get("reason") == "seed_pure"]
    assert len(seed_pure_events) == 0, f"Unexpected seed_pure skip events: {seed_pure_events}"


# ---------------------------------------------------------------------------
# Criterion 6 — ordering: below-ratio + seed-pure counted once (ratio fires first)
# ---------------------------------------------------------------------------


def test_seed_pure_and_below_ratio_counted_once() -> None:
    """A torrent that is both below-ratio AND seed-pure is counted exactly once.

    The ratio check fires first (it precedes the seed-pure check in the loop).
    The torrent must NOT appear in seed_pure skip events — it is handled by ratio.
    skip_count == 1 (not 2).
    """
    # ratio=0.1, min_ratio=1.0 → ratio check fires first
    torrent = _make_torrent("Seed.And.Low.Ratio.2024", "ccc333", tags=[SEED_PURE], ratio=0.1)

    emitted: list[ItemProgressed] = []
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

    with (
        patch("personalscraper.ingest.ingest.staging_path", return_value=Path("/tmp/test-staging")),
        patch("personalscraper.ingest.ingest.find_ingest_dir", return_value="000-INGEST"),
        patch("personalscraper.ingest.ingest.IngestTracker") as mock_tracker_cls,
    ):
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
    ratio_events = [e for e in emitted if e.details.get("reason") == "ratio_below_threshold"]
    seed_pure_events = [e for e in emitted if e.details.get("reason") == "seed_pure"]
    assert len(ratio_events) == 1, f"Expected 1 ratio_below_threshold event, got {ratio_events}"
    assert len(seed_pure_events) == 0, f"Expected 0 seed_pure events (ratio fired first), got {seed_pure_events}"
