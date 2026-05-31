import json
import sqlite3
from pathlib import Path

from personalscraper.conf import ids as CID
from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.scanner._modes._item_stage import (
    ISSUE_NFO_INCOMPLETE,
    ISSUE_NFO_MISSING,
    _detect_issues,
    _ensure_disk_row,
    build_item_row,
    scan_and_stage_dir,
    stage_library_items,
    upsert_item_with_attrs,
)
from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
    ISSUE_NTFS_UNSAFE,
    ISSUE_RELEASE_ARTIFACT,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# tests/indexer/scanner/_modes/ → parents[4] == repo root
MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"


def _make_db() -> sqlite3.Connection:
    """Real indexer schema (post-005) via apply_migrations — never drifts."""
    conn = sqlite3.connect(":memory:")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def test_build_item_row_routes_ids_and_canonical() -> None:
    """build_item_row routes provider IDs into external_ids_json + canonical."""
    row = build_item_row(
        title="The Godfather",
        kind="movie",
        year=1972,
        category_id="movies",
        tvdb_id=None,
        tmdb_id="238",
        nfo_default="tmdb",
        nfo_status="valid",
    )
    assert row["canonical_provider"] == "tmdb"
    assert row["title"] == "The Godfather"
    assert row["kind"] == "movie"
    # IDs live in external_ids_json (migration 005), NOT flat columns.
    assert json.loads(row["external_ids_json"])["tmdb"]["series_id"] == "238"


def test_upsert_item_with_attrs_creates_row() -> None:
    """upsert_item_with_attrs writes the media_item row and dispatch attrs."""
    conn = _make_db()
    row = build_item_row(
        title="Breaking Bad",
        kind="show",
        year=2008,
        category_id="tv_shows",
        tvdb_id="81189",
        tmdb_id="1396",
        nfo_default="tvdb",
        nfo_status="valid",
    )
    item_id = upsert_item_with_attrs(
        conn,
        row,
        attrs={
            item_repo._ATTR_DISPATCH_NORM_TITLE: "breaking bad",
            item_repo._ATTR_DISPATCH_DISK: "disk1",
            item_repo._ATTR_DISPATCH_PATH: "/mnt/disk1/series/Breaking Bad (2008)",
        },
    )
    assert isinstance(item_id, int)
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 1
    # show + tvdb_id → tvdb (kind beats the NFO-declared default).
    cp = conn.execute("SELECT canonical_provider FROM media_item WHERE id=?", (item_id,)).fetchone()[0]
    assert cp == "tvdb"
    # dispatch_normalized_title attr persisted (trailers / dispatch INNER JOIN on it).
    nt = conn.execute(
        "SELECT value FROM item_attribute WHERE item_id=? AND key=?",
        (item_id, item_repo._ATTR_DISPATCH_NORM_TITLE),
    ).fetchone()[0]
    assert nt == "breaking bad"


def test_upsert_item_nfo_missing_flags_issue() -> None:
    """NFO-less dirs must be indexed (folder-name fallback) AND flagged — never dropped."""
    conn = _make_db()
    row = build_item_row(
        title="Unknown Show",
        kind="show",
        year=None,
        category_id="tv_shows",
        tvdb_id=None,
        tmdb_id=None,
        nfo_default=None,
        nfo_status="missing",
    )
    item_id = upsert_item_with_attrs(
        conn,
        row,
        attrs={},
        issues=[{"type": "nfo_missing", "detail": None}],
    )
    # item must exist (folder-name fallback) — never silently dropped.
    assert conn.execute("SELECT COUNT(*) FROM media_item WHERE id=?", (item_id,)).fetchone()[0] == 1
    # issue must be flagged with a detected_at timestamp.
    issue_count = conn.execute(
        "SELECT COUNT(*) FROM item_issue WHERE item_id=? AND type='nfo_missing'", (item_id,)
    ).fetchone()[0]
    assert issue_count >= 1


# ===========================================================================
# Migrated coverage from tests/library/test_scanner.py (lib-fold Phase 3).
#
# These tests were ported from the doomed legacy ``library`` scanner module's
# unit/integration suite onto the NEW entry points that absorbed that logic:
# ``scan_and_stage_dir`` (per-dir scan+stage, replaces scan_movie_dir /
# scan_tvshow_dir), ``stage_library_items`` (full library walk, replaces
# scan_library), ``_detect_issues`` (directory-hygiene detection), and
# ``_ensure_disk_row`` (DEV #50 disk-row reconciliation). The fixture shapes
# and assertions mirror the legacy tests, adapted to the new return values /
# DB writes. NONE of these import the legacy module being deleted.
# ===========================================================================


# ---------------------------------------------------------------------------
# Config fixture (mirrors test_scanner.scanner_config / test_full_pass1).
# ---------------------------------------------------------------------------


def _scanner_config(tmp_path: Path) -> Config:
    """Two-disk Config for the migrated stage_library_items walk tests.

    Mirrors ``test_scanner.scanner_config``: drive_a hosts movies, tv_shows and
    audiobooks; drive_b hosts animated tv shows. Folder names follow the
    ``default_label`` pattern ("films", "series", ...).

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        A :class:`Config` with two disks suitable for the migrated walk tests.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[
            DiskConfig(
                id="drive_a",
                path=tmp_path / "drive_a",
                categories=[CID.MOVIES, CID.TV_SHOWS, CID.AUDIOBOOKS],
            ),
            DiskConfig(
                id="drive_b",
                path=tmp_path / "drive_b",
                categories=[CID.TV_SHOWS_ANIMATION],
            ),
        ],
        categories={
            CID.MOVIES: CategoryConfig(folder_name="films"),
            CID.TV_SHOWS: CategoryConfig(folder_name="series"),
            CID.AUDIOBOOKS: CategoryConfig(folder_name="livres audios"),
            CID.TV_SHOWS_ANIMATION: CategoryConfig(folder_name="series animations"),
        },
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


def _movie_cfg(tmp_path: Path) -> DiskConfig:
    """Return a single-disk DiskConfig hosting only the movies category."""
    return DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.MOVIES])


# ---------------------------------------------------------------------------
# stage_library_items — full library walk (replaces scan_library integration).
# ---------------------------------------------------------------------------


def test_stage_library_five_movies_two_shows(tmp_path: Path) -> None:
    """5 movies + 2 TV shows → correct row counts in all four tables.

    Migrated from ``test_scanner.test_five_movies_two_shows`` (drives
    ``stage_library_items`` instead of ``scan_library``).
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    films = disk_a / "films"
    series = disk_a / "series"
    films.mkdir(parents=True)
    series.mkdir(parents=True)

    for i in range(1, 6):
        movie = films / f"Movie {i} ({2010 + i})"
        movie.mkdir()
        (movie / f"Movie {i}.mkv").write_bytes(b"\x00" * 1000)
        (movie / f"Movie {i}.nfo").write_text(f'<movie><uniqueid type="tmdb">{100 + i}</uniqueid></movie>')

    for s in range(1, 3):
        show = series / f"Show {s} (202{s})"
        show.mkdir()
        (show / "tvshow.nfo").write_text(f'<tvshow><uniqueid type="tmdb">{200 + s}</uniqueid></tvshow>')
        (show / "poster.jpg").write_bytes(b"\x00")
        for sn in (1, 2):
            season_dir = show / f"Saison 0{sn}"
            season_dir.mkdir()
            for ep in range(1, 4):
                (season_dir / f"S0{sn}E0{ep} - Episode {ep}.mkv").write_bytes(b"\x00" * 100)
        (show / "season01-poster.jpg").write_bytes(b"\x00")

    staged = stage_library_items(conn, config, now_s=1000)

    assert staged == 7, f"expected 7 staged media dirs, got {staged}"
    count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    assert count == 7, f"expected 7 media_item rows, got {count}"
    movie_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind='movie'").fetchone()[0]
    show_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind='show'").fetchone()[0]
    assert movie_count == 5
    assert show_count == 2
    season_count = conn.execute("SELECT COUNT(*) FROM season").fetchone()[0]
    assert season_count == 4, f"expected 4 season rows, got {season_count}"
    episode_count = conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
    assert episode_count == 12, f"expected 12 episode rows, got {episode_count}"


def test_stage_library_media_item_fields_populated(tmp_path: Path) -> None:
    """media_item rows carry correct title, year, category_id, nfo_status, kind, ids.

    Migrated from ``test_scanner.test_media_item_fields_populated``.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "films").mkdir(parents=True)
    movie = disk_a / "films" / "Inception (2010)"
    movie.mkdir()
    (movie / "Inception.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Inception.nfo").write_text('<movie><uniqueid type="tmdb">27205</uniqueid></movie>')

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM media_item WHERE title = 'Inception'").fetchone()
    assert row is not None
    assert row["kind"] == "movie"
    assert row["year"] == 2010
    assert row["category_id"] == CID.MOVIES
    assert row["nfo_status"] == "valid"
    assert json.loads(row["external_ids_json"])["tmdb"]["series_id"] == "27205"


def test_stage_library_season_fields_populated(tmp_path: Path) -> None:
    """Season rows carry correct item_id, number, episode_count, has_poster.

    Migrated from ``test_scanner.test_season_fields_populated``.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "series").mkdir(parents=True)
    show = disk_a / "series" / "Fallout (2024)"
    show.mkdir()
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">106379</uniqueid></tvshow>')
    (show / "poster.jpg").write_bytes(b"\x00")
    s01 = show / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * 100)
    (s01 / "S01E02 - Second.mkv").write_bytes(b"\x00" * 100)
    (show / "season01-poster.jpg").write_bytes(b"\x00")

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    item_row = conn.execute("SELECT id FROM media_item WHERE title = 'Fallout'").fetchone()
    assert item_row is not None
    season_row = conn.execute(
        "SELECT * FROM season WHERE item_id = ? AND number = 1",
        (item_row["id"],),
    ).fetchone()
    assert season_row is not None
    assert season_row["episode_count"] == 2
    assert season_row["has_poster"] == 1


def test_stage_library_episode_stubs_created(tmp_path: Path) -> None:
    """Episode stubs are inserted (one per video file per season).

    Migrated from ``test_scanner.test_episode_stubs_created``.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "series").mkdir(parents=True)
    show = disk_a / "series" / "TestShow (2023)"
    show.mkdir()
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">9999</uniqueid></tvshow>')
    s01 = show / "Saison 01"
    s01.mkdir()
    for ep in range(1, 6):
        (s01 / f"S01E0{ep}.mkv").write_bytes(b"\x00" * 100)

    stage_library_items(conn, config, now_s=1000)

    ep_count = conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
    assert ep_count == 5


def test_stage_library_provider_ids_columns_populated_from_nfo(tmp_path: Path) -> None:
    """Rich NFO populates external_ids_json + ratings_json + canonical_provider.

    Migrated from ``test_scanner.test_provider_ids_columns_populated_from_nfo``
    (P7 regression: all three families surfaced, ratings source-mapped,
    canonical from <uniqueid default="true">). The new path derives
    ``canonical_provider`` deterministically from kind+IDs (show with tvdb_id →
    'tvdb'), which agrees with the NFO-declared default here.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "series").mkdir(parents=True)
    show = disk_a / "series" / "Breaking Bad (2008)"
    show.mkdir()
    (show / "tvshow.nfo").write_text(
        "<tvshow>"
        '<uniqueid type="tvdb" default="true">81189</uniqueid>'
        '<uniqueid type="tmdb">1396</uniqueid>'
        '<uniqueid type="imdb">tt0903747</uniqueid>'
        "<ratings>"
        '<rating name="imdb" max="10"><value>9.5</value><votes>2000000</votes></rating>'
        '<rating name="themoviedb" max="10"><value>8.9</value><votes>1500</votes></rating>'
        "</ratings>"
        "</tvshow>"
    )

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM media_item WHERE title = 'Breaking Bad'").fetchone()
    assert row is not None
    eids = json.loads(row["external_ids_json"])
    assert eids["tvdb"]["series_id"] == "81189"
    assert eids["tmdb"]["series_id"] == "1396"
    assert eids["imdb"]["series_id"] == "tt0903747"
    assert row["canonical_provider"] == "tvdb"
    ratings = json.loads(row["ratings_json"])
    sources = {entry["source"] for entry in ratings["entries"]}
    assert sources == {"imdb", "tmdb"}


def test_stage_library_canonical_show_tmdb_default_normalized_to_tvdb(tmp_path: Path) -> None:
    """A show NFO declaring tmdb-default must still resolve to canonical_provider='tvdb'.

    Migrated from
    ``test_scanner.test_canonical_provider_insertion_path_normalizes_show_tmdb_default``
    (Phase 14.1): kind-deterministic SSOT beats the NFO-declared default.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "series").mkdir(parents=True)
    show = disk_a / "series" / "12 Monkeys (2015)"
    show.mkdir()
    (show / "tvshow.nfo").write_text(
        "<tvshow>"
        '<uniqueid default="true" type="tmdb">60948</uniqueid>'
        '<uniqueid type="tvdb">272644</uniqueid>'
        '<uniqueid type="imdb">tt3148266</uniqueid>'
        "</tvshow>"
    )
    s01 = show / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01.mkv").write_bytes(b"\x00")

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT canonical_provider FROM media_item WHERE title = '12 Monkeys'").fetchone()
    assert row is not None
    assert row["canonical_provider"] == "tvdb", (
        f"Show with tvdb_id must yield canonical_provider='tvdb', got {row['canonical_provider']!r}"
    )


def test_stage_library_canonical_movie_tvdb_default_normalized_to_tmdb(tmp_path: Path) -> None:
    """A movie NFO declaring tvdb-default must still resolve to canonical_provider='tmdb'.

    Migrated from
    ``test_scanner.test_canonical_provider_insertion_path_normalizes_movie_tvdb_default``.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "films").mkdir(parents=True)
    movie = disk_a / "films" / "Inception (2010)"
    movie.mkdir()
    (movie / "Inception.nfo").write_text(
        "<movie>"
        '<uniqueid default="true" type="tvdb">99999</uniqueid>'
        '<uniqueid type="tmdb">27205</uniqueid>'
        '<uniqueid type="imdb">tt1375666</uniqueid>'
        "</movie>"
    )
    (movie / "Inception.mkv").write_bytes(b"\x00")

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT canonical_provider FROM media_item WHERE title = 'Inception'").fetchone()
    assert row is not None
    assert row["canonical_provider"] == "tmdb", (
        f"Movie with tmdb_id must yield canonical_provider='tmdb', got {row['canonical_provider']!r}"
    )


def test_stage_library_season_columns_refresh_on_rescan(tmp_path: Path) -> None:
    """Season columns (has_poster, episodes_with_nfo) refresh on every walk.

    Migrated from ``test_scanner.test_season_columns_refresh_on_rescan`` (P8):
    a row inserted before its poster/sibling-NFO landed must pick them up on
    the second walk (upsert_season, not INSERT OR IGNORE).
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "series").mkdir(parents=True)
    show = disk_a / "series" / "Fallout (2024)"
    show.mkdir()
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">106379</uniqueid></tvshow>')
    s01 = show / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - Pilot.mkv").write_bytes(b"\x00")

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    before = conn.execute("SELECT has_poster, episodes_with_nfo FROM season WHERE number = 1").fetchone()
    assert before["has_poster"] == 0
    assert before["episodes_with_nfo"] == 0

    (show / "season01-poster.jpg").write_bytes(b"\x00")
    (s01 / "S01E01 - Pilot.nfo").write_text("<episodedetails><title>Pilot</title></episodedetails>")

    stage_library_items(conn, config, now_s=2000)

    after = conn.execute("SELECT has_poster, episodes_with_nfo FROM season WHERE number = 1").fetchone()
    assert after["has_poster"] == 1
    assert after["episodes_with_nfo"] == 1


def test_stage_library_episode_title_persisted_from_nfo(tmp_path: Path) -> None:
    """episode.title is read from the sibling NFO; episodes without an NFO get NULL.

    Migrated from ``test_scanner.test_episode_title_persisted_from_nfo`` (P9).
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "series").mkdir(parents=True)
    show = disk_a / "series" / "TestShow (2023)"
    show.mkdir()
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">9999</uniqueid></tvshow>')
    s01 = show / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - Pilot.mkv").write_bytes(b"\x00")
    (s01 / "S01E01 - Pilot.nfo").write_text("<episodedetails><title>Pilot</title></episodedetails>")
    (s01 / "S01E02 - Second.mkv").write_bytes(b"\x00")
    (s01 / "S01E02 - Second.nfo").write_text("<episodedetails><title>The Second One</title></episodedetails>")
    (s01 / "S01E03 - Third.mkv").write_bytes(b"\x00")

    stage_library_items(conn, config, now_s=1000)

    rows = conn.execute(
        """
        SELECT e.number, e.title
        FROM episode e
        JOIN season s ON s.id = e.season_id
        JOIN media_item m ON m.id = s.item_id
        WHERE m.title = 'TestShow' AND s.number = 1
        ORDER BY e.number
        """
    ).fetchall()
    titles = {row[0]: row[1] for row in rows}
    assert titles[1] == "Pilot"
    assert titles[2] == "The Second One"
    assert titles[3] is None


def test_stage_library_unmounted_disk_skipped(tmp_path: Path) -> None:
    """Disks whose path does not exist are skipped; no rows inserted.

    Migrated from ``test_scanner.test_unmounted_disk_skipped``.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    # Neither drive_a nor drive_b directories are created.
    staged = stage_library_items(conn, config, now_s=1000)

    assert staged == 0
    count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    assert count == 0


def test_stage_library_idempotent_second_call(tmp_path: Path) -> None:
    """Calling stage_library_items twice does not create duplicate media_item rows.

    Migrated from ``test_scanner.test_idempotent_second_call`` (upsert on
    (kind, title)).
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "films").mkdir(parents=True)
    movie = disk_a / "films" / "Dune (2021)"
    movie.mkdir()
    (movie / "Dune.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Dune.nfo").write_text('<movie><uniqueid type="tmdb">438631</uniqueid></movie>')

    stage_library_items(conn, config, now_s=1000)
    stage_library_items(conn, config, now_s=2000)

    count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    assert count == 1, f"expected 1 after two calls (upsert), got {count}"


def test_stage_library_nfo_missing_status(tmp_path: Path) -> None:
    """Movie without NFO gets nfo_status='missing' AND an nfo_missing issue.

    Migrated from ``test_scanner.test_nfo_missing_status``. The new path adds
    the ``nfo_missing`` item_issue (DESIGN §4.3 decision #2) — a documented
    superset of the legacy behaviour, asserted here.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "films").mkdir(parents=True)
    movie = disk_a / "films" / "NoNfo (2024)"
    movie.mkdir()
    (movie / "NoNfo.mkv").write_bytes(b"\x00" * 1000)

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id, nfo_status FROM media_item WHERE title = 'NoNfo'").fetchone()
    assert row is not None
    assert row["nfo_status"] == "missing"
    nfo_missing = conn.execute(
        "SELECT COUNT(*) FROM item_issue WHERE item_id = ? AND type = ?",
        (row["id"], ISSUE_NFO_MISSING),
    ).fetchone()[0]
    assert nfo_missing >= 1


def test_stage_library_dispatch_attrs_written_for_each_item(tmp_path: Path) -> None:
    """Each item gets dispatch_path + dispatch_disk + dispatch_normalized_title.

    Migrated from ``test_scanner.test_dispatch_attrs_written_for_each_item``:
    downstream INNER JOINs (trailers cross-disk index, dispatch media-index,
    release_linker) rely on these flex attributes.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "films").mkdir(parents=True)
    movie = disk_a / "films" / "Tenet (2020)"
    movie.mkdir()
    (movie / "Tenet.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Tenet.nfo").write_text('<movie><uniqueid type="tmdb">577922</uniqueid></movie>')

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id FROM media_item WHERE title = 'Tenet'").fetchone()
    assert row is not None
    attrs = {
        r["key"]: r["value"]
        for r in conn.execute(
            "SELECT key, value FROM item_attribute WHERE item_id = ?",
            (row["id"],),
        ).fetchall()
    }
    assert attrs.get(item_repo._ATTR_DISPATCH_PATH) == str(movie)
    assert attrs.get(item_repo._ATTR_DISPATCH_DISK) == config.disks[0].id
    assert attrs.get(item_repo._ATTR_DISPATCH_NORM_TITLE) == "tenet"


def test_stage_library_item_issue_rows_persisted_for_dirty_dir(tmp_path: Path) -> None:
    """A movie with .actors/ + junk file gets matching item_issue rows.

    Migrated from ``test_scanner.test_item_issue_rows_persisted_for_dirty_dir``.
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "films").mkdir(parents=True)
    movie = disk_a / "films" / "Dirty (2024)"
    movie.mkdir()
    (movie / "Dirty.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Dirty.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / ".actors").mkdir()
    (movie / ".DS_Store").write_text("")

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    item_row = conn.execute("SELECT id FROM media_item WHERE title = 'Dirty'").fetchone()
    assert item_row is not None
    issue_types = {
        r["type"]
        for r in conn.execute(
            "SELECT type FROM item_issue WHERE item_id = ?",
            (item_row["id"],),
        ).fetchall()
    }
    assert ISSUE_ACTORS_DIR in issue_types
    assert ISSUE_JUNK_FILES in issue_types


def test_stage_library_item_issue_drops_resolved_on_rescan(tmp_path: Path) -> None:
    """Cleaning up an issue between walks removes the matching item_issue row.

    Migrated from ``test_scanner.test_item_issue_drops_resolved_issues_on_rescan``
    (upsert_item_with_attrs DELETEs the whole issue set on every scan).
    """
    conn = _make_db()
    config = _scanner_config(tmp_path)
    disk_a = config.disks[0].path
    (disk_a / "films").mkdir(parents=True)
    movie = disk_a / "films" / "Cleaned (2024)"
    movie.mkdir()
    (movie / "Cleaned.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Cleaned.nfo").write_text('<movie><uniqueid type="tmdb">2</uniqueid></movie>')
    actors_dir = movie / ".actors"
    actors_dir.mkdir()

    stage_library_items(conn, config, now_s=1000)

    conn.row_factory = sqlite3.Row
    item_row = conn.execute("SELECT id FROM media_item WHERE title = 'Cleaned'").fetchone()
    assert item_row is not None
    item_id = item_row["id"]
    before = {r["type"] for r in conn.execute("SELECT type FROM item_issue WHERE item_id = ?", (item_id,)).fetchall()}
    assert ISSUE_ACTORS_DIR in before

    actors_dir.rmdir()
    stage_library_items(conn, config, now_s=2000)

    after = {r["type"] for r in conn.execute("SELECT type FROM item_issue WHERE item_id = ?", (item_id,)).fetchall()}
    assert ISSUE_ACTORS_DIR not in after


# ---------------------------------------------------------------------------
# scan_and_stage_dir — per-media-dir scan+stage (replaces scan_movie_dir /
# scan_tvshow_dir). Drives a single directory directly.
# ---------------------------------------------------------------------------


def test_scan_and_stage_dir_complete_movie(tmp_path: Path) -> None:
    """A complete movie dir → one valid-NFO media_item row, no hygiene issues.

    Migrated from ``test_scanner.TestScanMovieDir.test_complete_movie``
    (drives ``scan_and_stage_dir`` and asserts on DB writes instead of the
    legacy ``LibraryItem`` return).
    """
    conn = _make_db()
    disk_cfg = _movie_cfg(tmp_path)
    movie = tmp_path / "films" / "The Matrix (1999)"
    movie.mkdir(parents=True)
    (movie / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
    (movie / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')
    (movie / "The Matrix-poster.jpg").write_bytes(b"\x00")
    (movie / "The Matrix-landscape.jpg").write_bytes(b"\x00")

    item_id = scan_and_stage_dir(conn, movie, disk_cfg, CID.MOVIES, "movie", now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert row["title"] == "The Matrix"
    assert row["year"] == 1999
    assert row["kind"] == "movie"
    assert row["nfo_status"] == "valid"
    assert row["category_id"] == CID.MOVIES
    assert json.loads(row["external_ids_json"])["tmdb"]["series_id"] == "603"
    artwork = json.loads(row["artwork_json"])
    assert artwork["poster"] is True
    assert artwork["landscape"] is True
    # A complete movie dir carries no item_issue rows.
    issue_count = conn.execute("SELECT COUNT(*) FROM item_issue WHERE item_id = ?", (item_id,)).fetchone()[0]
    assert issue_count == 0
    # No seasons for a movie.
    season_count = conn.execute("SELECT COUNT(*) FROM season WHERE item_id = ?", (item_id,)).fetchone()[0]
    assert season_count == 0


def test_scan_and_stage_dir_missing_nfo_flagged(tmp_path: Path) -> None:
    """A movie dir with no NFO → nfo_status='missing' + nfo_missing issue.

    Migrated from ``test_scanner.TestScanMovieDir.test_movie_missing_nfo``.
    """
    conn = _make_db()
    disk_cfg = _movie_cfg(tmp_path)
    movie = tmp_path / "films" / "NoNfo (2024)"
    movie.mkdir(parents=True)
    (movie / "NoNfo.mkv").write_bytes(b"\x00" * 1000)

    item_id = scan_and_stage_dir(conn, movie, disk_cfg, CID.MOVIES, "movie", now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT nfo_status FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert row["nfo_status"] == "missing"
    issue_types = {
        r["type"] for r in conn.execute("SELECT type FROM item_issue WHERE item_id = ?", (item_id,)).fetchall()
    }
    assert ISSUE_NFO_MISSING in issue_types


def test_scan_and_stage_dir_incomplete_nfo_flagged(tmp_path: Path) -> None:
    """A movie dir with a present-but-incomplete NFO → nfo_status='invalid' + nfo_incomplete.

    Exercises the ``ISSUE_NFO_INCOMPLETE`` branch of ``scan_and_stage_dir``
    (no legacy 1:1 test; the legacy nfo_status string covered it implicitly).
    """
    conn = _make_db()
    disk_cfg = _movie_cfg(tmp_path)
    movie = tmp_path / "films" / "Incomplete (2024)"
    movie.mkdir(parents=True)
    (movie / "Incomplete.mkv").write_bytes(b"\x00" * 1000)
    # Present NFO but no usable <uniqueid> → is_nfo_complete is False.
    (movie / "Incomplete.nfo").write_text("<movie><title>Incomplete</title></movie>")

    item_id = scan_and_stage_dir(conn, movie, disk_cfg, CID.MOVIES, "movie", now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT nfo_status FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert row["nfo_status"] == "invalid"
    issue_types = {
        r["type"] for r in conn.execute("SELECT type FROM item_issue WHERE item_id = ?", (item_id,)).fetchall()
    }
    assert ISSUE_NFO_INCOMPLETE in issue_types


def test_scan_and_stage_dir_complete_show_seasons_episodes(tmp_path: Path) -> None:
    """A complete show dir stages the show row + season + episode rows.

    Migrated from ``test_scanner.TestScanTvshowDir.test_complete_show``.
    """
    conn = _make_db()
    disk_cfg = DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.TV_SHOWS])
    show = tmp_path / "series" / "Fallout (2024)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">106379</uniqueid></tvshow>')
    (show / "poster.jpg").write_bytes(b"\x00")
    (show / "landscape.jpg").write_bytes(b"\x00")
    s01 = show / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 1000)
    (s01 / "S01E01 - The Beginning.nfo").write_text("<episodedetails/>")
    (show / "season01-poster.jpg").write_bytes(b"\x00")

    item_id = scan_and_stage_dir(conn, show, disk_cfg, CID.TV_SHOWS, "show", now_s=1000)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert row["title"] == "Fallout"
    assert row["year"] == 2024
    assert row["kind"] == "show"
    assert row["nfo_status"] == "valid"
    artwork = json.loads(row["artwork_json"])
    assert artwork["poster"] is True
    season = conn.execute("SELECT * FROM season WHERE item_id = ? AND number = 1", (item_id,)).fetchone()
    assert season is not None
    assert season["episode_count"] == 1
    assert season["has_poster"] == 1
    assert season["episodes_with_nfo"] == 1


def test_scan_and_stage_dir_show_multiple_seasons(tmp_path: Path) -> None:
    """A show with two season dirs → two season rows with matching episode counts.

    Migrated from ``test_scanner.TestScanTvshowDir.test_show_multiple_seasons``.
    """
    conn = _make_db()
    disk_cfg = DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.TV_SHOWS])
    show = tmp_path / "series" / "Show (2020)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
    (show / "poster.jpg").write_bytes(b"\x00")
    for sn in (1, 2):
        s = show / f"Saison 0{sn}"
        s.mkdir()
        for ep in range(1, 4):
            (s / f"S0{sn}E0{ep} - Ep.mkv").write_bytes(b"\x00" * 100)

    item_id = scan_and_stage_dir(conn, show, disk_cfg, CID.TV_SHOWS, "show", now_s=1000)

    conn.row_factory = sqlite3.Row
    seasons = conn.execute(
        "SELECT number, episode_count FROM season WHERE item_id = ? ORDER BY number", (item_id,)
    ).fetchall()
    assert len(seasons) == 2
    assert seasons[0]["episode_count"] == 3
    assert seasons[1]["episode_count"] == 3


# ---------------------------------------------------------------------------
# _detect_issues — directory-hygiene detection (port of scanner._detect_issues).
# Returns ``(deduped issue list, actors_dir bool)``.
# ---------------------------------------------------------------------------


def test_detect_issues_actors_dir(tmp_path: Path) -> None:
    """``.actors/`` subdir → ISSUE_ACTORS_DIR + actors_dir bool True.

    Migrated from ``test_scanner.TestScanMovieDir.test_movie_with_actors_dir``.
    """
    movie = tmp_path / "Movie (2024)"
    movie.mkdir()
    (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
    (movie / ".actors").mkdir()
    (movie / ".actors" / "Actor.jpg").write_bytes(b"\x00")

    issues, actors_dir = _detect_issues(movie, "Movie", 2024, is_tvshow=False, category_id=CID.MOVIES)

    assert actors_dir is True
    assert ISSUE_ACTORS_DIR in issues


def test_detect_issues_empty_subdir(tmp_path: Path) -> None:
    """An empty subdir in a movie → ISSUE_EMPTY_SUBDIR.

    Migrated from ``test_scanner.TestScanMovieDir.test_movie_with_empty_subdir``.
    """
    movie = tmp_path / "Movie (2024)"
    movie.mkdir()
    (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Subs").mkdir()

    issues, _ = _detect_issues(movie, "Movie", 2024, is_tvshow=False, category_id=CID.MOVIES)

    assert ISSUE_EMPTY_SUBDIR in issues


def test_detect_issues_junk_files(tmp_path: Path) -> None:
    """A ``.DS_Store`` junk file → ISSUE_JUNK_FILES.

    Migrated from ``test_scanner.TestScanMovieDir.test_movie_with_junk_files``.
    """
    movie = tmp_path / "Movie (2024)"
    movie.mkdir()
    (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
    (movie / ".DS_Store").write_bytes(b"\x00")

    issues, _ = _detect_issues(movie, "Movie", 2024, is_tvshow=False, category_id=CID.MOVIES)

    assert ISSUE_JUNK_FILES in issues


def test_detect_issues_bad_dir_name(tmp_path: Path) -> None:
    """A movie dir with no ``(Year)`` → ISSUE_BAD_DIR_NAME.

    Migrated from ``test_scanner.TestScanMovieDir.test_movie_bad_dir_name``.
    The year=None signal comes from parse_title_year, passed in here directly.
    """
    movie = tmp_path / "Some Movie"
    movie.mkdir()
    (movie / "movie.mkv").write_bytes(b"\x00" * 1000)

    issues, _ = _detect_issues(movie, "Some Movie", None, is_tvshow=False, category_id=CID.MOVIES)

    assert ISSUE_BAD_DIR_NAME in issues


def test_detect_issues_macos_resource_forks_flagged(tmp_path: Path) -> None:
    """MacOS resource fork files (``._*``) → ISSUE_JUNK_FILES.

    Migrated from ``test_scanner.TestScanMovieDir.test_macos_resource_forks_flagged``.
    """
    movie = tmp_path / "Movie (2024)"
    movie.mkdir()
    (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
    (movie / "._Movie.mkv").write_bytes(b"\x00" * 100)

    issues, _ = _detect_issues(movie, "Movie", 2024, is_tvshow=False, category_id=CID.MOVIES)

    assert ISSUE_JUNK_FILES in issues


def test_detect_issues_audiobook_no_year_not_flagged(tmp_path: Path) -> None:
    """Audiobooks by author name (no year) must NOT flag bad_dir_naming.

    Migrated from ``test_scanner.TestScanMovieDir.test_audiobook_no_year_not_flagged``.
    """
    book = tmp_path / "Isaac Asimov"
    book.mkdir()
    (book / "Foundation.mp3").write_bytes(b"\x00" * 1000)

    issues, _ = _detect_issues(book, "Isaac Asimov", None, is_tvshow=False, category_id=CID.AUDIOBOOKS)

    assert ISSUE_BAD_DIR_NAME not in issues


def test_detect_issues_ntfs_unsafe_filename_flagged(tmp_path: Path) -> None:
    """A file with an NTFS-illegal ':' → ISSUE_NTFS_UNSAFE.

    Migrated from ``test_scanner.TestNtfsUnsafeDetection.test_ntfs_unsafe_filename_flagged``.
    """
    movie = tmp_path / "Movie (2024)"
    movie.mkdir()
    (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Spirale : L'Héritage.txt").write_bytes(b"\x00")

    issues, _ = _detect_issues(movie, "Movie", 2024, is_tvshow=False, category_id=CID.MOVIES)

    assert ISSUE_NTFS_UNSAFE in issues


def test_detect_issues_release_artifact_for_non_season_empty_dir_in_show(tmp_path: Path) -> None:
    """A non-season empty dir inside a show → ISSUE_RELEASE_ARTIFACT (not EMPTY_SUBDIR).

    Covers the ``is_tvshow`` branch of _detect_issues, which the legacy
    movie-only tests never exercised directly.
    """
    show = tmp_path / "Show (2024)"
    show.mkdir()
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
    (show / "empty_release_dir").mkdir()  # non-season empty dir

    issues, _ = _detect_issues(show, "Show", 2024, is_tvshow=True, category_id=CID.TV_SHOWS)

    assert ISSUE_RELEASE_ARTIFACT in issues
    assert ISSUE_EMPTY_SUBDIR not in issues


# ---------------------------------------------------------------------------
# _ensure_disk_row — DEV #50 disk-row reconciliation (SELECT-by-label).
# ---------------------------------------------------------------------------


def test_ensure_disk_row_no_duplicate_when_row_has_real_uuid(tmp_path: Path) -> None:
    """No duplicate row when a bootstrap row already exists with a real VolumeUUID.

    Migrated from
    ``test_scanner.TestEnsureDiskRowNoDuplicate.test_ensure_disk_row_no_duplicate_when_row_has_real_uuid``
    (DEV #50): bootstrap inserts uuid=VolumeUUID, label=disk_cfg.id; the
    by-label lookup must find it so no second row is inserted.
    """
    conn = _make_db()
    disk_cfg = DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.MOVIES])

    real_uuid = "F7E3C03C-1234-5678-ABCD-000000000001"
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, NULL, 1, 0)",
        (real_uuid, disk_cfg.id, str(disk_cfg.path), 1000),
    )

    result = _ensure_disk_row(conn, disk_cfg, now_s=2000)

    disk_count = conn.execute("SELECT COUNT(*) FROM disk").fetchone()[0]
    assert disk_count == 1, (
        f"Expected 1 disk row after _ensure_disk_row, got {disk_count} (DEV #50 regression: duplicate row was inserted)"
    )
    assert result.uuid == real_uuid
    assert result.label == disk_cfg.id


def test_ensure_disk_row_inserts_when_no_existing_row(tmp_path: Path) -> None:
    """A new disk row is inserted when no row exists for the label.

    Migrated from
    ``test_scanner.TestEnsureDiskRowNoDuplicate.test_ensure_disk_row_inserts_when_no_existing_row``.
    """
    conn = _make_db()
    disk_cfg = DiskConfig(id="drive_b", path=tmp_path / "drive_b", categories=[CID.TV_SHOWS])

    result = _ensure_disk_row(conn, disk_cfg, now_s=1000)

    disk_count = conn.execute("SELECT COUNT(*) FROM disk").fetchone()[0]
    assert disk_count == 1, f"Expected 1 disk row after insert, got {disk_count}"
    assert result.label == disk_cfg.id
    assert result.id > 0


def test_ensure_disk_row_idempotent_when_row_uses_config_id_as_uuid(tmp_path: Path) -> None:
    """Idempotent when the existing row used uuid=disk_cfg.id (library fallback path).

    Migrated from
    ``test_scanner.TestEnsureDiskRowNoDuplicate.test_ensure_disk_row_idempotent_when_row_already_uses_config_id_as_uuid``.
    """
    conn = _make_db()
    disk_cfg = DiskConfig(id="drive_c", path=tmp_path / "drive_c", categories=[CID.MOVIES])

    _ensure_disk_row(conn, disk_cfg, now_s=1000)
    _ensure_disk_row(conn, disk_cfg, now_s=2000)

    disk_count = conn.execute("SELECT COUNT(*) FROM disk").fetchone()[0]
    assert disk_count == 1, f"Expected 1 disk row after two _ensure_disk_row calls, got {disk_count}"
