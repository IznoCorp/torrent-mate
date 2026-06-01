"""Regression tests: dispatch rebuild rich-row + key-convention guarantees.

Prior to lib-fold Phase 3, :meth:`MediaIndex.rebuild` delegated to
:meth:`MediaIndex.add`, whose insert branch wrote its own minimal
``MediaItemRow(..., canonical_provider=None, ...)`` (``dispatch/media_index.py``
line ~418) without ever reading the on-disk NFO. A movie folder carrying a
valid ``<uniqueid type="tmdb">`` therefore landed in ``media_item`` with
``canonical_provider`` NULL — diverging from the rich rows produced by
``library-index --mode full`` (DESIGN single-creator decision #4).

The PR#31 review surfaced two follow-on regressions on the dispatch path once
``rebuild`` started delegating to ``scan_and_stage_dir`` directly:

* **M2** — ``scan_and_stage_dir`` stores the YEAR-STRIPPED indexer norm_title
  (golden parity), but the dispatch exact-match lookup + ``add()`` dedup key on
  the FULL folder name (incl. year). Rebuilt rows therefore no longer
  exact-matched dispatch lookups, and a later ``add()`` of the same item missed
  the dedup and inserted a DUPLICATE ``media_item``.
* **M1** — ``rebuild``'s inner loop called ``scan_and_stage_dir`` with no
  try/except, so one unreadable dir aborted the entire dispatch index build.

These tests pin all of the above as reproducers. They build REAL on-disk
fixtures with real NFO files and a real :class:`~personalscraper.conf.models.config.Config`
(modeled on ``tests/library/test_integration.py::mini_library``). A ``MagicMock``
config is deliberately NOT used: the redirect target ``scan_and_stage_dir``
accesses the real ``DiskConfig.id`` / ``DiskConfig.path`` and ``rebuild``
resolves ``config.disks`` / ``config.categories`` / ``folder_name`` — a mock
would silently break the write path the test is meant to exercise.
"""

import os
import sqlite3
from pathlib import Path

import pytest

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex, _normalize_key
from personalscraper.indexer.repos import item_repo
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture()
def tvshow_library(tmp_path: Path) -> Config:
    """Build a real one-show library config with a season + episode.

    Layout::

        <tmp>/Disk1/medias/series/Fallout (2024)/
            tvshow.nfo          (valid, TVDB id 363613)
            season01-poster.jpg
            Saison 01/
                S01E01 - The Beginning.mkv
                S01E01 - The Beginning.nfo

    The show NFO is the fixed ``tvshow.nfo`` (the convention
    ``_nfo_metadata_for_dir`` resolves for shows) and carries a TVDB
    ``<uniqueid>`` so the show rule resolves ``canonical_provider == "tvdb"``.
    The ``Saison 01/`` directory + ``S01E01`` video pin the season/episode
    rich-row walk through ``rebuild`` → ``scan_and_stage_dir`` end-to-end.

    Args:
        tmp_path: pytest temporary directory.

    Returns:
        A fully-built :class:`Config` whose single disk holds the show folder.
    """
    medias = tmp_path / "Disk1" / "medias"
    show_dir = medias / "series" / "Fallout (2024)"
    show_dir.mkdir(parents=True)
    (show_dir / "tvshow.nfo").write_text(
        '<?xml version="1.0"?><tvshow>'
        '<uniqueid type="tvdb" default="true">363613</uniqueid>'
        "<title>Fallout</title></tvshow>",
        encoding="utf-8",
    )
    (show_dir / "season01-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    s01 = show_dir / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 2000)
    (s01 / "S01E01 - The Beginning.nfo").write_text(
        "<episodedetails><title>The Beginning</title></episodedetails>", encoding="utf-8"
    )

    disk_cfg = DiskConfig(id="disk1", path=medias, categories=["tv_shows"])
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={"tv_shows": CategoryConfig(folder_name="series")},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


# ---------------------------------------------------------------------------
# Rich-row guarantee (pre-existing)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# M2 — rebuild stores a full-name (year-bearing) dispatch norm_title
# ---------------------------------------------------------------------------


def test_rebuild_norm_title_keys_on_full_folder_name(godfather_library: Config) -> None:
    """Rebuilt rows must exact-match the year-bearing dispatch lookup key.

    ``scan_and_stage_dir`` stores the YEAR-STRIPPED indexer norm_title
    (``"the godfather"``); the dispatch exact-match lookup keys on the FULL
    folder name incl. year (``"the godfather (1972)"``). ``rebuild`` must
    overwrite the stored attr with the full-name key so the dispatch exact
    lookup resolves.

    Pre-fix the stored attr was year-stripped, so
    :func:`item_repo.find_by_normalized_name` returns ``None`` for the
    full-name key and ``MediaIndex.find`` falls through to FUZZY — this
    assertion fails. Post-fix the exact-match path resolves.

    Args:
        godfather_library: Real one-movie :class:`Config` fixture.
    """
    db_path = godfather_library.indexer.db_path
    assert db_path is not None

    with MediaIndex(db_path, config=godfather_library, auto_rebuild=True, event_bus=EventBus()):
        pass

    # The exact-match path used by MediaIndex.find: a non-None result here means
    # the row is keyed on the full year-bearing folder name (match_type "exact"),
    # not the year-stripped indexer key (which would force a fuzzy fallback).
    conn = sqlite3.connect(db_path)
    try:
        full_key = _normalize_key("The Godfather (1972)")
        exact = item_repo.find_by_normalized_name(conn, full_key, "movie")
        assert exact is not None, (
            "rebuild must store dispatch_normalized_title keyed on the FULL folder name "
            "(incl. year) so the dispatch exact-match lookup resolves (PR#31 review M2)"
        )
        # And the year-stripped indexer key must NOT be what dispatch keys on.
        stripped_key = _normalize_key("The Godfather")
        assert item_repo.find_by_normalized_name(conn, stripped_key, "movie") is None, (
            "dispatch must not key on the year-stripped indexer norm_title"
        )
    finally:
        conn.close()


def test_rebuild_then_add_same_item_dedups_via_exact_match(godfather_library: Config) -> None:
    """``find`` after rebuild must resolve via EXACT match, and ``add`` must dedup.

    The user-visible M2 symptom: after a rebuild, a dispatch lookup for the
    year-bearing folder name no longer exact-matches the rebuilt row. This test
    pins the exact-match resolution that drives the ``add()`` dedup.

    The primary pin is the ``find`` exact-match: pre-fix, ``rebuild`` stored a
    year-stripped norm_title, so ``MediaIndex.find("The Godfather (1972)", ...)``
    could only resolve the row through the FUZZY fallback (or miss entirely),
    never the exact path. Asserting that ``item_repo.find_by_normalized_name``
    (the exact lookup ``find`` performs first) resolves the year-bearing key
    fails pre-fix. The follow-up ``add()`` + single-row check confirms no second
    ``media_item`` is created.

    Args:
        godfather_library: Real one-movie :class:`Config` fixture.
    """
    db_path = godfather_library.indexer.db_path
    assert db_path is not None
    movie_path = godfather_library.disks[0].path / "films" / "The Godfather (1972)"

    with MediaIndex(db_path, config=godfather_library, auto_rebuild=True, event_bus=EventBus()) as idx:
        assert idx.count == 1, "auto-rebuild must index exactly one movie"

        # PRIMARY M2 PIN: the rebuilt row must be reachable via the exact-match
        # lookup keyed on the FULL year-bearing folder name — the same lookup
        # MediaIndex.find performs first. Pre-fix this returns None (year-stripped
        # key) and find would fall through to fuzzy.
        full_key = _normalize_key("The Godfather (1972)")
        assert item_repo.find_by_normalized_name(idx._conn, full_key, "movie") is not None, (
            "rebuilt row must exact-match the year-bearing dispatch key (PR#31 review M2)"
        )

        idx.add(
            IndexEntry(
                name="The Godfather (1972)",
                disk="disk1",
                category="movies",
                path=str(movie_path),
                media_type="movie",
            )
        )

        assert idx.count == 1, "add() of an already-rebuilt item must dedup, not insert a duplicate (PR#31 review M2)"

    conn = sqlite3.connect(db_path)
    try:
        (n,) = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()
        assert n == 1, f"expected exactly one media_item row, found {n} (M2 duplicate regression)"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# M1 — rebuild survives one unreadable directory
# ---------------------------------------------------------------------------


def test_rebuild_skips_unreadable_dir_and_indexes_the_rest(tmp_path: Path) -> None:
    """One unreadable media dir must be skipped (warn + continue), not abort the build.

    Builds two movie dirs on one disk, makes the first unreadable (chmod 000),
    and asserts the rebuild still indexes the readable one instead of aborting
    at the first ``OSError``. Pre-fix (no try/except around
    ``scan_and_stage_dir``) the unreadable dir's ``OSError`` propagates out of
    ``rebuild`` and the whole index build fails.

    The unreadable directory is restored to ``0o755`` in a ``finally`` so the
    tmp tree can be torn down. Skipped on platforms where ``chmod`` cannot make
    a directory unreadable (e.g. running as root, where DAC checks are bypassed).

    Args:
        tmp_path: pytest temporary directory.
    """
    medias = tmp_path / "Disk1" / "medias"
    bad_dir = medias / "films" / "Bad Movie (2000)"
    good_dir = medias / "films" / "Good Movie (2001)"
    bad_dir.mkdir(parents=True)
    good_dir.mkdir(parents=True)
    (good_dir / "Good Movie.nfo").write_text(
        '<?xml version="1.0"?><movie><uniqueid type="tmdb">111</uniqueid>'
        "<title>Good Movie</title><year>2001</year></movie>",
        encoding="utf-8",
    )

    disk_cfg = DiskConfig(id="disk1", path=medias, categories=["movies"])
    config = Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={"movies": CategoryConfig(folder_name="films")},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )
    db_path = config.indexer.db_path
    assert db_path is not None

    # Make the bad dir unreadable. iterdir() inside scan_and_stage_dir (artwork
    # inventory / season scan) raises PermissionError (an OSError subclass).
    os.chmod(bad_dir, 0o000)
    # Confirm the OS actually denies access (running as root bypasses this).
    if os.access(bad_dir, os.R_OK):
        os.chmod(bad_dir, 0o755)
        pytest.skip("OS does not enforce directory read permission (running as root?)")

    try:
        with MediaIndex(db_path, config=config, auto_rebuild=False, event_bus=EventBus()) as idx:
            count = idx.rebuild([disk_cfg], categories=config.categories)
            # The good dir is indexed; the bad dir is skipped, not fatal.
            assert count == 1, f"rebuild must index the readable dir and skip the unreadable one, got count={count}"
            assert idx.find("Good Movie (2001)", "movie") is not None, (
                "the readable movie must be indexed despite a sibling unreadable dir (PR#31 review M1)"
            )
    finally:
        os.chmod(bad_dir, 0o755)


# ---------------------------------------------------------------------------
# M5 — add() over a real on-disk NFO-bearing folder derives canonical_provider
# ---------------------------------------------------------------------------


def test_add_real_movie_folder_derives_tmdb_provider(godfather_library: Config) -> None:
    """``add()`` of a real on-disk TMDB-bearing movie folder must derive ``"tmdb"``.

    All other ``add()`` tests pass fake non-existent paths, so the
    ``media_dir.is_dir()`` branch (which reads the NFO via
    ``_nfo_metadata_for_dir`` and derives a non-NULL canonical provider) is
    unpinned. This points ``add()`` at the real Godfather folder (TMDB id 238)
    and asserts the persisted ``canonical_provider == "tmdb"``.

    Uses a dedicated DB (``auto_rebuild`` disabled) so the only row is the one
    ``add()`` writes — isolating the ``add()`` insert branch.

    Args:
        godfather_library: Real one-movie :class:`Config` fixture (reused for
            its on-disk folder).
    """
    db_path = godfather_library.indexer.db_path
    assert db_path is not None
    movie_path = godfather_library.disks[0].path / "films" / "The Godfather (1972)"
    assert movie_path.is_dir(), "fixture must place a real movie folder on disk"

    with MediaIndex(db_path, config=godfather_library, auto_rebuild=False, event_bus=EventBus()) as idx:
        idx.add(
            IndexEntry(
                name="The Godfather (1972)",
                disk="disk1",
                category="movies",
                path=str(movie_path),
                media_type="movie",
            )
        )

    conn = sqlite3.connect(db_path)
    try:
        # Single-row DB (auto_rebuild disabled) — read the one row's provider
        # directly so the assertion is independent of how add() stores the title.
        rows = conn.execute("SELECT canonical_provider FROM media_item").fetchall()
        assert len(rows) == 1, f"add() must write exactly one media_item row, got {len(rows)}"
        (cp,) = rows[0]
        assert cp == "tmdb", (
            f"add() over a real TMDB-bearing folder must derive canonical_provider='tmdb', got {cp!r} "
            "(M5: the production _nfo_metadata_for_dir branch was unpinned)"
        )
    finally:
        conn.close()


def test_add_real_show_folder_derives_tvdb_provider(tvshow_library: Config) -> None:
    """``add()`` of a real on-disk TVDB-bearing show folder must derive ``"tvdb"``.

    TVDB variant of the M5 gap: points ``add()`` at the real Fallout show folder
    (``tvshow.nfo`` with TVDB id) and asserts the persisted
    ``canonical_provider == "tvdb"`` (the show rule prefers TVDB).

    Args:
        tvshow_library: Real one-show :class:`Config` fixture.
    """
    db_path = tvshow_library.indexer.db_path
    assert db_path is not None
    show_path = tvshow_library.disks[0].path / "series" / "Fallout (2024)"
    assert show_path.is_dir(), "fixture must place a real show folder on disk"

    with MediaIndex(db_path, config=tvshow_library, auto_rebuild=False, event_bus=EventBus()) as idx:
        idx.add(
            IndexEntry(
                name="Fallout (2024)",
                disk="disk1",
                category="tv_shows",
                path=str(show_path),
                media_type="tvshow",
            )
        )

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT canonical_provider FROM media_item").fetchall()
        assert len(rows) == 1, f"add() must write exactly one media_item row, got {len(rows)}"
        (cp,) = rows[0]
        assert cp == "tvdb", (
            f"add() over a real TVDB-bearing show folder must derive canonical_provider='tvdb', got {cp!r} (M5)"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# L5 — rebuild of a TV show pins seasons/episodes + tvdb provider end-to-end
# ---------------------------------------------------------------------------


def test_rebuild_tvshow_produces_seasons_episodes_and_tvdb_provider(tvshow_library: Config) -> None:
    """Auto-rebuild of a TV show must produce season + episode rows and ``"tvdb"``.

    Pins the rebuild → ``scan_and_stage_dir`` rich-row SHOW path end-to-end: a
    ``tvshow.nfo`` (tvdb id) + ``Saison 01/`` + an ``S01E01`` video must yield
    a ``season`` row and an ``episode`` row, and the ``media_item`` must derive
    ``canonical_provider == "tvdb"``. Pre-lib-fold the rebuild went through
    ``add()`` which never walked seasons and wrote a NULL provider.

    Args:
        tvshow_library: Real one-show :class:`Config` fixture.
    """
    db_path = tvshow_library.indexer.db_path
    assert db_path is not None

    with MediaIndex(db_path, config=tvshow_library, auto_rebuild=True, event_bus=EventBus()):
        pass

    conn = sqlite3.connect(db_path)
    try:
        (item_id, cp, kind) = conn.execute(
            "SELECT id, canonical_provider, kind FROM media_item WHERE title = ?", ("Fallout",)
        ).fetchone()
        assert kind == "show", "the show must be staged with kind='show'"
        assert cp == "tvdb", f"TVDB-bearing show must derive canonical_provider='tvdb', got {cp!r} (L5)"

        (season_count,) = conn.execute("SELECT COUNT(*) FROM season WHERE item_id = ?", (item_id,)).fetchone()
        assert season_count >= 1, f"rebuild must produce at least one season row, got {season_count} (L5)"

        (episode_count,) = conn.execute(
            "SELECT COUNT(*) FROM episode e JOIN season s ON e.season_id = s.id WHERE s.item_id = ?",
            (item_id,),
        ).fetchone()
        assert episode_count >= 1, f"rebuild must produce at least one episode row, got {episode_count} (L5)"
    finally:
        conn.close()
