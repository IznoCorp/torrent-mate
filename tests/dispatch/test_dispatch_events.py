"""Tests for the dispatch event emits — Sub-phase 4.3.

Covers :class:`ItemDispatched` emission from both per-action code paths
(``_movie.dispatch_movie`` and ``_tv.dispatch_tvshow``):

- A new movie placement emits ``action="moved"``.
- A movie dispatched on top of an existing folder emits ``action="replaced"``.
- A TV merge into an existing folder emits ``action="merged"``.
- Dry-run dispatches NEVER emit (catalog Notes: ItemDispatched records
  completed transfers only).
- The factory + envelope round-trip plumbing required for the Phase 4 gate.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.core.event_bus import (
    EventBus,
    event_from_envelope,
    event_to_envelope,
)
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
from tests.fixtures.event_bus import CollectingSubscriber, assert_event_round_trip
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES


@pytest.fixture(autouse=True)
def _rsync_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``shutil.which`` report rsync as available so ``Dispatcher.__init__`` doesn't raise."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rsync" if name == "rsync" else None)


def _make_dispatcher(
    test_config,
    tmp_path: Path,
    *,
    dry_run: bool = False,
    event_bus: EventBus | None = None,
) -> Dispatcher:
    """Build a :class:`Dispatcher` wired to a real :class:`MediaIndex` on tmp."""
    idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
    return Dispatcher(
        test_config,
        MagicMock(),
        idx,
        dry_run=dry_run,
        event_bus=event_bus,
    )


def test_dispatch_movie_emits_item_dispatched_moved(test_config, tmp_path: Path) -> None:
    """A new movie placement emits exactly one ``ItemDispatched`` with action="moved"."""
    bus = EventBus()
    collector: CollectingSubscriber[ItemDispatched] = CollectingSubscriber(bus, ItemDispatched)
    dispatcher = _make_dispatcher(test_config, tmp_path, event_bus=bus)

    movie_dir = tmp_path / "Inception (2010)"
    movie_dir.mkdir()
    (movie_dir / "Inception.mkv").write_bytes(b"\x00" * 1024)

    disk_root = tmp_path / "drive_a"
    with (
        patch(
            "personalscraper.dispatch._movie.get_disk_status",
        ) as mock_status,
        patch(
            "personalscraper.dispatch.dispatcher.Dispatcher._move_new",
            return_value=True,
        ),
    ):
        from personalscraper.dispatch.disk_scanner import DiskStatus

        mock_status.return_value = DiskStatus(
            config=DiskConfig(id="drive_a", path=disk_root, categories=["movies"]),
            free_space_gb=500,
            is_mounted=True,
        )
        result = dispatcher.dispatch_movie(movie_dir, "movies")

    assert result.action == "moved"
    assert len(collector.received) == 1
    event = collector.received[0]
    assert event.item == "Inception (2010)"
    assert event.target_disk == disk_root
    assert event.category_id == "movies"
    assert event.action == "moved"


def test_dispatch_movie_emits_item_dispatched_replaced(test_config, tmp_path: Path) -> None:
    """A movie dispatched on top of an existing entry emits action="replaced"."""
    bus = EventBus()
    collector: CollectingSubscriber[ItemDispatched] = CollectingSubscriber(bus, ItemDispatched)
    dispatcher = _make_dispatcher(test_config, tmp_path, event_bus=bus)

    disk_root = tmp_path / "drive_a"
    movie_dir = tmp_path / "Inception (2010)"
    movie_dir.mkdir()
    (movie_dir / "Inception.mkv").write_bytes(b"\x00" * 1024)
    existing_path = disk_root / "movies" / "Inception (2010)"
    existing_path.mkdir(parents=True)

    # Seed the index with the existing entry so the dispatcher hits the replace branch.
    dispatcher.index.add(
        IndexEntry(
            name="Inception (2010)",
            disk="drive_a",
            category="movies",
            path=str(existing_path),
            media_type="movie",
        ),
    )

    with (
        patch(
            "personalscraper.dispatch._movie.get_disk_status",
        ) as mock_status,
        patch(
            "personalscraper.dispatch._movie.replace",
            return_value=True,
        ),
    ):
        from personalscraper.dispatch.disk_scanner import DiskStatus

        mock_status.return_value = DiskStatus(
            config=DiskConfig(id="drive_a", path=disk_root, categories=["movies"]),
            free_space_gb=500,
            is_mounted=True,
        )
        result = dispatcher.dispatch_movie(movie_dir, "movies")

    assert result.action == "replaced"
    assert len(collector.received) == 1
    assert collector.received[0].action == "replaced"
    assert collector.received[0].target_disk == disk_root


def test_dispatch_tv_emits_item_dispatched_merged(test_config, tmp_path: Path) -> None:
    """A TV merge into an existing folder emits action="merged"."""
    bus = EventBus()
    collector: CollectingSubscriber[ItemDispatched] = CollectingSubscriber(bus, ItemDispatched)
    dispatcher = _make_dispatcher(test_config, tmp_path, event_bus=bus)

    disk_root = tmp_path / "drive_a"
    show_dir = tmp_path / "Severance"
    show_dir.mkdir()
    (show_dir / "Saison 02").mkdir()
    (show_dir / "Saison 02" / "S02E01 - Hello, Ms. Cobel.mkv").write_bytes(b"\x00" * 1024)
    existing_path = disk_root / "tv_shows" / "Severance"
    existing_path.mkdir(parents=True)

    dispatcher.index.add(
        IndexEntry(
            name="Severance",
            disk="drive_a",
            category="tv_shows",
            path=str(existing_path),
            media_type="tvshow",
        ),
    )

    with (
        patch(
            "personalscraper.dispatch._tv.get_disk_status",
        ) as mock_status,
        patch(
            "personalscraper.dispatch._tv.merge",
            return_value=True,
        ),
    ):
        from personalscraper.dispatch.disk_scanner import DiskStatus

        mock_status.return_value = DiskStatus(
            config=DiskConfig(id="drive_a", path=disk_root, categories=["tv_shows"]),
            free_space_gb=500,
            is_mounted=True,
        )
        result = dispatcher.dispatch_tvshow(show_dir, "tv_shows")

    assert result.action == "merged"
    assert len(collector.received) == 1
    assert collector.received[0].action == "merged"
    assert collector.received[0].item == "Severance"
    assert collector.received[0].target_disk == disk_root


def test_dispatch_dry_run_does_not_emit(test_config, tmp_path: Path) -> None:
    """Dry-run dispatch never emits ``ItemDispatched`` — only real transfers do."""
    bus = EventBus()
    collector: CollectingSubscriber[ItemDispatched] = CollectingSubscriber(bus, ItemDispatched)
    dispatcher = _make_dispatcher(test_config, tmp_path, dry_run=True, event_bus=bus)

    movie_dir = tmp_path / "Matrix (1999)"
    movie_dir.mkdir()
    (movie_dir / "Matrix.mkv").write_bytes(b"\x00" * 1024)

    with patch(
        "personalscraper.dispatch._movie.get_disk_status",
    ) as mock_status:
        from personalscraper.dispatch.disk_scanner import DiskStatus

        mock_status.return_value = DiskStatus(
            config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["movies"]),
            free_space_gb=500,
            is_mounted=True,
        )
        result = dispatcher.dispatch_movie(movie_dir, "movies")

    assert result.action == "moved"  # dry-run still sets action — for reporting
    assert collector.received == []  # ...but no event emitted


def test_item_dispatched_has_factory() -> None:
    """``ItemDispatched`` is registered in ``EVENT_SAMPLE_FACTORIES``."""
    assert ItemDispatched in EVENT_SAMPLE_FACTORIES


def test_item_dispatched_envelope_roundtrip() -> None:
    """``ItemDispatched`` survives envelope round-trip including ``Path`` coercion."""
    original = EVENT_SAMPLE_FACTORIES[ItemDispatched]()
    envelope = event_to_envelope(original)
    assert envelope["_type"] == "ItemDispatched"
    reconstructed = event_from_envelope(envelope)
    assert type(reconstructed) is ItemDispatched
    assert_event_round_trip(original, reconstructed)
    assert isinstance(reconstructed.target_disk, Path)  # type: ignore[attr-defined]


@pytest.mark.parametrize("action", ["moved", "merged", "replaced"])
def test_item_dispatched_action_literal_values(action: str) -> None:
    """Each declared ``action`` literal value round-trips correctly through the envelope."""
    original = ItemDispatched(
        item="Whatever",
        target_disk=Path("/Volumes/Disk1"),
        category_id="movies",
        action=action,  # type: ignore[arg-type]
    )
    envelope = event_to_envelope(original)
    reconstructed = event_from_envelope(envelope)
    assert isinstance(reconstructed, ItemDispatched)
    assert reconstructed.action == action
