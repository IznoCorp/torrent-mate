"""F8 regression: real ``ItemProgressed(status="started")`` lifecycle.

The sort, dispatch and enforce steps historically emitted their per-item
``started`` events *after* the worker had already performed every item's work
(a post-hoc loop in the ``run_*`` runner). This is a fake lifecycle
(PIPELINE-CORE-05 / DESIGN §T2 F8): a subscriber sees all the filesystem work
happen and only *then* receives the ``started`` notifications.

These tests pin the real contract — ``started`` for an item must be observed on
the bus **before** that item's work executes — by driving each worker with a
probe that captures, at the moment the per-item work runs, which ``started``
events have already been seen.

Written test-first: they FAIL against the post-hoc emission and PASS once the
emission moves into the per-item processing loops.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import (
    find_by_file_type,
    find_ingest_dir,
    folder_name,
    staging_path,
)
from personalscraper.core.event_bus import EventBus
from personalscraper.core.media_types import FileType
from personalscraper.pipeline_events import ItemProgressed
from tests.fixtures.config import CANONICAL_STAGING_DIRS
from tests.fixtures.event_bus import CollectingSubscriber


def _real_config(tmp_path: Path) -> Config:
    """A real Config rooted at ``tmp_path`` with the canonical staging layout."""
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": [s.model_dump() for s in CANONICAL_STAGING_DIRS],
        }
    )


def _started_items(sub: CollectingSubscriber[ItemProgressed]) -> list[str]:
    """Names of items that have a ``started`` event on the bus so far."""
    return [e.item for e in sub.received if e.status == "started"]


# --- sort -----------------------------------------------------------------


def test_sort_emits_started_before_sort_item(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``Sorter.process`` must emit ``started`` before it works each item.

    Probe: ``Sorter.sort_item`` is wrapped to snapshot the started-items seen at
    call time. On post-hoc emission the snapshot is empty (the runner emits
    ``started`` only after the whole sort finished).
    """
    from personalscraper.models import SortResult
    from personalscraper.sorter.run import run_sort
    from personalscraper.sorter.sorter import Sorter

    config = _real_config(tmp_path)
    ingest_dir = staging_path(config, find_ingest_dir(config))
    ingest_dir.mkdir(parents=True, exist_ok=True)
    movie = ingest_dir / "Inception 2010 1080p"
    movie.mkdir()
    (movie / "Inception.mkv").write_bytes(b"x")

    bus = EventBus()
    sub: CollectingSubscriber[ItemProgressed] = CollectingSubscriber(bus, ItemProgressed)

    seen_at_work: list[tuple[str, list[str]]] = []
    original = Sorter.sort_item

    def traced(self: Sorter, item: Path, dest_root: Path) -> SortResult:
        seen_at_work.append((item.name, _started_items(sub)))
        return original(self, item, dest_root)

    monkeypatch.setattr(Sorter, "sort_item", traced)

    run_sort(MagicMock(), config.paths.staging_dir, config, dry_run=True, event_bus=bus)

    assert seen_at_work, "sort_item was never invoked — test setup broken"
    for name, started in seen_at_work:
        assert name in started, f"sort_item({name!r}) ran before its 'started' event; seen={started}"


# --- dispatch -------------------------------------------------------------


def test_dispatch_emits_started_before_dispatch_movie(
    test_config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Dispatcher.process`` must emit ``started`` before it dispatches an item.

    Probe: ``Dispatcher.dispatch_movie`` is replaced by a stub that snapshots
    the started-items seen at call time. On post-hoc emission the stub sees no
    ``started`` (the runner emits them only after ``process`` returned).
    """
    from personalscraper.dispatch._types import DispatchResult
    from personalscraper.dispatch.dispatcher import Dispatcher
    from personalscraper.dispatch.media_index import MediaIndex
    from personalscraper.verify.verifier import VerifyResult

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rsync" if name == "rsync" else None)

    bus = EventBus()
    sub: CollectingSubscriber[ItemProgressed] = CollectingSubscriber(bus, ItemProgressed)

    idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
    dispatcher = Dispatcher(test_config, MagicMock(), idx, dry_run=True, event_bus=bus)

    movie_dir = tmp_path / "Inception (2010)"
    movie_dir.mkdir()
    (movie_dir / "Inception.mkv").write_bytes(b"x")
    verified = [
        VerifyResult(media_path=movie_dir, media_type="movie", category="movies", status="valid"),
    ]

    seen_at_work: list[tuple[str, list[str]]] = []

    def stub_dispatch_movie(self: Dispatcher, path: Path, category: str) -> DispatchResult:
        seen_at_work.append((path.name, _started_items(sub)))
        return DispatchResult(source=path, action="skipped", reason="stubbed")

    monkeypatch.setattr(Dispatcher, "dispatch_movie", stub_dispatch_movie)

    try:
        dispatcher.process(verified=verified)
    finally:
        idx.close()

    assert seen_at_work, "dispatch_movie was never invoked — test setup broken"
    for name, started in seen_at_work:
        assert name in started, f"dispatch_movie({name!r}) ran before its 'started' event; seen={started}"


# --- enforce --------------------------------------------------------------


def test_enforce_emits_started_before_sanitize_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sanitize sub-component must emit ``started`` before it mutates a file.

    Probe: ``Path.unlink`` is wrapped to snapshot the started-items seen when the
    ``.DS_Store`` file is actually deleted. On post-hoc emission the snapshot is
    empty (``run_enforce`` emits ``started`` only after ``sanitize_files``
    already deleted the file). Structure/coherence sub-components are stubbed to
    isolate the sanitize path.
    """
    from personalscraper.enforce.run import run_enforce

    config = _real_config(tmp_path)
    staging = config.paths.staging_dir
    movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
    film = movies_dir / "Film (2024)"
    film.mkdir(parents=True)
    (film / "film.mkv").write_bytes(b"x")
    (film / ".DS_Store").write_bytes(b"x")

    monkeypatch.setattr("personalscraper.enforce.run.validate_structure", lambda *a, **k: [])
    monkeypatch.setattr("personalscraper.enforce.run.check_coherence", lambda *a, **k: [])

    bus = EventBus()
    sub: CollectingSubscriber[ItemProgressed] = CollectingSubscriber(bus, ItemProgressed)

    seen_at_work: list[tuple[str, list[str]]] = []
    original_unlink = Path.unlink

    def traced_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == ".DS_Store":
            seen_at_work.append((self.name, _started_items(sub)))
        return original_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", traced_unlink)

    run_enforce(MagicMock(), config, dry_run=False, event_bus=bus)

    assert seen_at_work, ".DS_Store was never unlinked — test setup broken"
    name, started = seen_at_work[0]
    assert name in started, f"sanitize deleted {name!r} before its 'started' event; seen={started}"
