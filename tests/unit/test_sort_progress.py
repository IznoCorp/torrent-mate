"""Tests for sort progress events — migrated to EventBus + ``ItemProgressed``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.sorter.run import run_sort
from tests.fixtures.event_bus import CollectingSubscriber


def _make_config(staging_dir: Path) -> MagicMock:
    config = MagicMock()
    config.paths.staging_dir = staging_dir
    ingest_entry = MagicMock()
    ingest_entry.id = 97
    ingest_entry.role = "ingest"
    config.staging_dirs = [ingest_entry]
    return config


class TestSortProgress:
    """Verify run_sort emits ``ItemProgressed`` via the bus."""

    def test_accepts_event_bus_param(self) -> None:
        """run_sort accepts ``event_bus`` without error."""
        staging_dir = Path("/tmp/staging")
        bus = EventBus()
        with patch("personalscraper.sorter.run._has_unsorted_items", return_value=False):
            report = run_sort(
                MagicMock(),
                staging_dir=staging_dir,
                dry_run=True,
                config=_make_config(staging_dir),
                event_bus=bus,
            )
        assert report.name == "sort"

    def test_emits_progress_per_item(self) -> None:
        """Each sorted item emits a terminal ``moved`` event from run_sort.

        ``started`` is now emitted from INSIDE ``Sorter.process`` (F8 real
        lifecycle); the sorter is mocked here so only run_sort's terminal event
        is observed. The started-before-work contract is pinned in
        tests/event_bus/test_real_started_lifecycle.py.
        """
        from personalscraper.sorter.sorter import Sorter

        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        staging_dir = Path("/tmp/staging")

        fake_result = MagicMock()
        fake_result.source = MagicMock()
        fake_result.source.name = "Inception.2010.mkv"
        fake_result.status = "moved"
        fake_result.message = None
        fake_result.destination = Path("/tmp/staging/001-MOVIES/Inception (2010).mkv")

        with patch.object(Sorter, "process", return_value=[fake_result]):
            with patch("personalscraper.sorter.run._has_unsorted_items", return_value=True):
                report = run_sort(
                    MagicMock(),
                    staging_dir=staging_dir,
                    dry_run=False,
                    config=_make_config(staging_dir),
                    event_bus=bus,
                )

        assert report.name == "sort"
        moved = [e for e in collector.received if e.status == "moved"]
        assert len(moved) >= 1, "expected at least 1 moved event"
        assert moved[0].step == "sort"

    def test_step_survives_crashing_subscriber(self) -> None:
        """A subscriber callback that raises must NOT crash the step (bus 1.4 contract)."""
        bus = EventBus()
        bus.subscribe(ItemProgressed, lambda _ev: (_ for _ in ()).throw(RuntimeError("subscriber crash")))

        staging_dir = Path("/tmp/staging")
        with patch("personalscraper.sorter.run._has_unsorted_items", return_value=False):
            report = run_sort(
                MagicMock(),
                staging_dir=staging_dir,
                dry_run=True,
                config=_make_config(staging_dir),
                event_bus=bus,
            )
        assert report.name == "sort"
