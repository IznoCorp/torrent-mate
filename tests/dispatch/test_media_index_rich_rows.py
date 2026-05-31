"""Regression test: dispatch auto-rebuild must produce rich rows.

Prior to lib-fold Phase 3, :meth:`MediaIndex.rebuild` delegated to
:meth:`MediaIndex.add`, whose insert branch wrote its own minimal
``MediaItemRow(..., canonical_provider=None, ...)`` (``dispatch/media_index.py``
line ~418) without ever reading the on-disk NFO. A movie folder carrying a
valid ``<uniqueid type="tmdb">`` therefore landed in ``media_item`` with
``canonical_provider`` NULL — diverging from the rich rows produced by
``library-index --mode full`` (DESIGN single-creator decision #4).

This test pins that degradation as a reproducer: it builds a REAL
:class:`~personalscraper.conf.models.config.Config` (modeled on
``tests/library/test_integration.py::mini_library``), drops a movie directory
with a TMDB-bearing NFO on a real on-disk path, lets the ``MediaIndex``
constructor fire its empty-DB auto-rebuild, then asserts every ``media_item``
row resolves a non-NULL ``canonical_provider``. A ``MagicMock`` config is
deliberately NOT used: the redirect target ``scan_and_stage_dir`` accesses the
real ``DiskConfig.id`` / ``DiskConfig.path`` and ``rebuild`` resolves
``config.disks`` / ``config.categories`` / ``folder_name`` — a mock would
silently break the write path the test is meant to exercise.
"""

import sqlite3
from pathlib import Path

import pytest

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch.media_index import MediaIndex
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture()
def godfather_library(tmp_path: Path) -> Config:
    """Build a real one-movie library config for the auto-rebuild path.

    Layout::

        <tmp>/Disk1/medias/films/The Godfather (1972)/
            The Godfather.nfo   (valid, TMDB id 238)

    The movie NFO is named ``<title-without-year>.nfo`` — the convention the
    write path resolves (``scan_and_stage_dir`` parses the folder name with
    ``parse_title_year`` and looks up ``<title>.nfo``), mirroring the Matrix
    folder in ``tests/library/test_integration.py::mini_library``.

    The NFO carries a TMDB ``<uniqueid>`` so the kind-deterministic canonical
    provider derivation resolves ``"tmdb"`` (not ``None``) once the write path
    actually reads the NFO.

    Args:
        tmp_path: pytest temporary directory.

    Returns:
        A fully-built :class:`Config` whose single disk holds the movie folder.
        ``indexer.db_path`` resolves to ``<tmp>/.data/library.db`` (a WAL-safe,
        non-``/Volumes`` path) so ``MediaIndex`` opens a real DB.
    """
    medias = tmp_path / "Disk1" / "medias"
    movie_dir = medias / "films" / "The Godfather (1972)"
    movie_dir.mkdir(parents=True)
    (movie_dir / "The Godfather.nfo").write_text(
        '<?xml version="1.0"?><movie>'
        '<uniqueid type="tmdb" default="true">238</uniqueid>'
        "<title>The Godfather</title><year>1972</year></movie>",
        encoding="utf-8",
    )

    disk_cfg = DiskConfig(id="disk1", path=medias, categories=["movies"])
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={"movies": CategoryConfig(folder_name="films")},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


def test_dispatch_auto_rebuild_produces_rich_rows(godfather_library: Config) -> None:
    """Dispatch auto-rebuild must never write ``canonical_provider`` NULL for an ID-bearing item.

    Constructs ``MediaIndex`` with the real config and ``auto_rebuild=True``;
    the empty-DB branch of ``__init__`` fires ``rebuild`` immediately. After
    construction the single movie row must carry a derived
    ``canonical_provider`` (``"tmdb"`` from the NFO), proving the dispatch path
    produces the same rich rows as ``library-index --mode full``.

    Args:
        godfather_library: Real one-movie :class:`Config` fixture.
    """
    db_path = godfather_library.indexer.db_path
    assert db_path is not None, "Config must resolve indexer.db_path"

    with MediaIndex(db_path, config=godfather_library, auto_rebuild=True, event_bus=EventBus()):
        pass

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT title, canonical_provider FROM media_item").fetchall()
    finally:
        conn.close()

    assert rows, "auto-rebuild must create at least one media_item row"
    for title, canonical_provider in rows:
        assert canonical_provider is not None, (
            f"canonical_provider=None found for {title!r} — dispatch auto-rebuild must "
            "produce rich rows (lib-fold Phase 3 regression)"
        )
    # The Godfather NFO declares a TMDB id, so the movie rule resolves "tmdb".
    assert any(cp == "tmdb" for _title, cp in rows), "TMDB-bearing movie must derive canonical_provider='tmdb'"
