"""``ItemDispatched.media_ref`` and ``LibraryScanSkipped``.

Media reference: a dispatch names WHICH medium it touched, by provider id (read from the
item's NFO); no NFO → ``None``.
Skipped scan: a disk whose post-dispatch index refresh did not run (maintenance disabled
or the scan failed) is announced, so a library sheet never shows stale counts
silently.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import personalscraper.indexer.cli  # noqa: F401  (circular import with commands.scan)
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.core.event_bus import EventBus, event_from_envelope, event_to_envelope
from personalscraper.core.identity import MediaRef
from personalscraper.dispatch import post_maintenance
from personalscraper.dispatch.disk_scanner import DiskStatus
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.indexer.events import LibraryScanSkipped, ScanSkipReason
from tests.fixtures.event_bus import CollectingSubscriber


@pytest.fixture(autouse=True)
def _rsync_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``shutil.which`` report rsync so ``Dispatcher.__init__`` doesn't raise."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rsync" if name == "rsync" else None)


_MOVIE_NFO = (
    '<?xml version="1.0" encoding="UTF-8"?><movie><title>Inception</title>'
    '<uniqueid type="tmdb" default="true">27205</uniqueid>'
    '<uniqueid type="imdb">tt1375666</uniqueid></movie>'
)
_SHOW_NFO = (
    '<?xml version="1.0" encoding="UTF-8"?><tvshow><title>Severance</title>'
    '<uniqueid type="tvdb" default="true">371980</uniqueid></tvshow>'
)


def _dispatch_new_movie(test_config, tmp_path: Path, nfo: str | None) -> list[ItemDispatched]:
    """Dispatch one new movie (transfer mocked) and return the emitted events."""
    bus = EventBus()
    collector: CollectingSubscriber[ItemDispatched] = CollectingSubscriber(bus, ItemDispatched)
    dispatcher = Dispatcher(
        test_config,
        MagicMock(),
        MediaIndex(tmp_path / "index.db", event_bus=EventBus()),
        dry_run=False,
        event_bus=bus,
    )
    movie_dir = tmp_path / "Inception (2010)"
    movie_dir.mkdir()
    (movie_dir / "Inception.mkv").write_bytes(b"\x00" * 1024)
    if nfo is not None:
        (movie_dir / "Inception (2010).nfo").write_text(nfo, encoding="utf-8")
    disk_root = tmp_path / "drive_a"
    with (
        patch("personalscraper.dispatch._item.get_disk_status") as status,
        patch("personalscraper.dispatch.dispatcher.Dispatcher._move_new", return_value=True),
    ):
        status.return_value = DiskStatus(
            config=DiskConfig(id="drive_a", path=disk_root, categories=["movies"]),
            free_space_gb=500,
            is_mounted=True,
        )
        result = dispatcher.dispatch_movie(movie_dir, "movies")
    assert result.action == "moved"
    return collector.received


def test_item_dispatched_carries_the_nfo_provider_ids(test_config, tmp_path: Path) -> None:
    """A dispatched movie whose NFO carries tmdb/imdb ids names them in ``media_ref``."""
    events = _dispatch_new_movie(test_config, tmp_path, _MOVIE_NFO)
    assert len(events) == 1
    assert events[0].media_ref == MediaRef(tmdb_id=27205, imdb_id="tt1375666")


def test_item_dispatched_media_ref_none_without_nfo(test_config, tmp_path: Path) -> None:
    """No NFO → ``media_ref`` is ``None`` (existing subscribers keep working)."""
    events = _dispatch_new_movie(test_config, tmp_path, None)
    assert events[0].media_ref is None


def test_item_dispatched_tvdb_id_of_a_show(test_config, tmp_path: Path) -> None:
    """A TV dispatch reads ``tvshow.nfo`` and names the tvdb id as an int."""
    bus = EventBus()
    collector: CollectingSubscriber[ItemDispatched] = CollectingSubscriber(bus, ItemDispatched)
    dispatcher = Dispatcher(
        test_config,
        MagicMock(),
        MediaIndex(tmp_path / "index.db", event_bus=EventBus()),
        dry_run=False,
        event_bus=bus,
    )
    show_dir = tmp_path / "Severance"
    (show_dir / "Saison 01").mkdir(parents=True)
    (show_dir / "Saison 01" / "S01E01 - Good News About Hell.mkv").write_bytes(b"\x00" * 1024)
    (show_dir / "tvshow.nfo").write_text(_SHOW_NFO, encoding="utf-8")
    disk_root = tmp_path / "drive_a"
    with (
        patch("personalscraper.dispatch._item.get_disk_status") as status,
        patch("personalscraper.dispatch.dispatcher.Dispatcher._move_new", return_value=True),
    ):
        status.return_value = DiskStatus(
            config=DiskConfig(id="drive_a", path=disk_root, categories=["tv_shows"]),
            free_space_gb=500,
            is_mounted=True,
        )
        dispatcher.dispatch_tvshow(show_dir, "tv_shows")
    assert [e.media_ref for e in collector.received] == [MediaRef(tvdb_id=371980)]


@pytest.fixture
def mock_config() -> MagicMock:
    """Config stand-in with a resolved indexer db path."""
    cfg = MagicMock()
    cfg.indexer.db_path = "/tmp/test_library.db"
    cfg.indexer.post_dispatch_maintenance.enabled = True
    return cfg


def _skips(bus: EventBus) -> list[LibraryScanSkipped]:
    received: list[LibraryScanSkipped] = []
    bus.subscribe(LibraryScanSkipped, received.append)
    return received


def test_disabled_maintenance_announces_one_skip_per_touched_disk(mock_config: MagicMock) -> None:
    """``enabled=False`` → one ``LibraryScanSkipped(disabled)`` per touched disk."""
    bus = EventBus()
    skips = _skips(bus)
    post_maintenance.run_post_dispatch_maintenance(mock_config, {"disk_2", "disk_1"}, event_bus=bus, enabled=False)
    assert sorted((s.disk, s.reason) for s in skips) == [
        ("disk_1", ScanSkipReason.DISABLED),
        ("disk_2", ScanSkipReason.DISABLED),
    ]


@pytest.mark.parametrize("failure", ["raises", "nonzero"])
def test_failed_scan_announces_skip_and_dispatch_continues(mock_config: MagicMock, failure: str) -> None:
    """A raising / non-zero incremental scan → ``LibraryScanSkipped(failed)``; nothing raises."""
    bus = EventBus()
    skips = _skips(bus)
    scan = MagicMock(side_effect=RuntimeError("boom")) if failure == "raises" else MagicMock(return_value=1)
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", scan),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_repair_drain", return_value=0),
    ):
        post_maintenance.run_post_dispatch_maintenance(mock_config, {"disk_1"}, event_bus=bus, enabled=True)
    assert [(s.disk, s.reason) for s in skips] == [("disk_1", ScanSkipReason.FAILED)]


def test_successful_scan_announces_no_skip(mock_config: MagicMock) -> None:
    """A scan that succeeds announces nothing."""
    bus = EventBus()
    skips = _skips(bus)
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_repair_drain", return_value=0),
    ):
        post_maintenance.run_post_dispatch_maintenance(mock_config, {"disk_1"}, event_bus=bus, enabled=True)
    assert skips == []


def test_both_events_round_trip_the_envelope() -> None:
    """The bridge's envelope carries ``media_ref`` and ``LibraryScanSkipped`` intact."""
    dispatched = ItemDispatched(
        item="Inception (2010)",
        target_disk=Path("/Volumes/Disk1"),
        category_id="movies",
        action="moved",
        media_ref=MediaRef(tvdb_id=1, tmdb_id=2, imdb_id="tt3"),
    )
    skipped = LibraryScanSkipped(disk="disk_1", reason=ScanSkipReason.FAILED)
    for event in (dispatched, skipped):
        assert event_from_envelope(event_to_envelope(event)) == event
