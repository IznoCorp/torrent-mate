"""Tests for personalscraper.library.scanner — rewritten for sub-phase 7.1.

Verifies that ``scan_library(config, conn) -> None`` populates the indexer DB
(``media_item``, ``media_file``, ``season``, ``episode``) for a fake filesystem
containing 5 movies and 2 TV shows.

The helper functions (``scan_movie_dir``, ``scan_tvshow_dir``, ``parse_title_year``,
``extract_nfo_ids``) retain their original unit tests because they are still used
by other callers (trailers/scanner.py, library/rescraper.py).

Pattern:
    Each integration test with pyfakefs calls ``fs.pause()`` to apply DB migrations
    using the real filesystem, then ``fs.resume()`` to build the fake directory tree,
    then calls ``scan_library`` with ``guard_disk_mounted`` patched out.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.indexer.db import apply_migrations
from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
)
from personalscraper.library.scanner import (
    extract_nfo_ids,
    scan_library,
    scan_movie_dir,
    scan_tvshow_dir,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem

# ---------------------------------------------------------------------------
# Paths to migration scripts — must resolve from the REAL filesystem.
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# Guard patch target: same as used in tests/indexer/test_scanner.py
_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn_real() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied.

    Must be called while the real filesystem is active (i.e. after ``fs.pause()``).

    Returns:
        Open :class:`sqlite3.Connection` with migrations applied, FK checks on.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


# ---------------------------------------------------------------------------
# Config fixture for scanner tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def scanner_config(tmp_path: Path) -> Config:
    """Minimal Config for scanner unit tests.

    Two disks: drive_a (movies, tv_shows, audiobooks) and drive_b (tv_shows_animation).
    Folder names follow the default_label pattern: "films", "series", etc.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Config with two disks suitable for fake-filesystem scanner tests.
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


# ---------------------------------------------------------------------------
# Integration tests — scan_library() with pyfakefs
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="pyfakefs/xml.etree C-accelerator interop is broken on Python 3.10; "
    "the indexer scan FD-based syscalls also bypass the fake FS. "
    "Tested in CI on 3.11/3.12/3.13.",
)
class TestScanLibraryPopulatesDB:
    """scan_library(config, conn) writes media_item, media_file, season, episode rows."""

    def test_five_movies_two_shows(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """5 movies + 2 TV shows in fake FS → correct row counts in all four tables."""
        # Build DB on the real filesystem (apply_migrations reads SQL files from disk).
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        films = disk_a / "films"
        series = disk_a / "series"
        films.mkdir(parents=True)
        series.mkdir(parents=True)

        # --- 5 movies ---
        for i in range(1, 6):
            movie = films / f"Movie {i} ({2010 + i})"
            movie.mkdir()
            (movie / f"Movie {i}.mkv").write_bytes(b"\x00" * 1000)
            (movie / f"Movie {i}.nfo").write_text(f'<movie><uniqueid type="tmdb">{100 + i}</uniqueid></movie>')

        # --- 2 TV shows, each with 2 seasons ---
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

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        # --- media_item: 5 movies + 2 shows = 7 rows ---
        count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
        assert count == 7, f"expected 7 media_item rows, got {count}"

        # --- movies are kind='movie', shows are kind='show' ---
        movie_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind='movie'").fetchone()[0]
        show_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind='show'").fetchone()[0]
        assert movie_count == 5
        assert show_count == 2

        # --- season rows: 2 seasons × 2 shows = 4 ---
        season_count = conn.execute("SELECT COUNT(*) FROM season").fetchone()[0]
        assert season_count == 4, f"expected 4 season rows, got {season_count}"

        # --- episode rows: 3 episodes × 2 seasons × 2 shows = 12 ---
        episode_count = conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
        assert episode_count == 12, f"expected 12 episode rows, got {episode_count}"

        # --- media_file rows: at least the movie + episode video files exist ---
        file_count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert file_count >= 5, f"expected >= 5 media_file rows, got {file_count}"

    def test_media_item_fields_populated(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """media_item rows carry correct title, year, category_id, nfo_status, kind."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        movie = disk_a / "films" / "Inception (2010)"
        movie.mkdir()
        (movie / "Inception.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Inception.nfo").write_text('<movie><uniqueid type="tmdb">27205</uniqueid></movie>')

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM media_item WHERE title = 'Inception'").fetchone()
        assert row is not None
        assert row["kind"] == "movie"
        assert row["year"] == 2010
        assert row["category_id"] == CID.MOVIES
        assert row["nfo_status"] == "valid"
        assert row["tmdb_id"] == 27205

    def test_season_fields_populated(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Season rows carry correct item_id, number, episode_count, has_poster."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
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

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        conn.row_factory = sqlite3.Row
        item_row = conn.execute("SELECT id FROM media_item WHERE title = 'Fallout'").fetchone()
        assert item_row is not None
        item_id = item_row["id"]

        season_row = conn.execute(
            "SELECT * FROM season WHERE item_id = ? AND number = 1",
            (item_id,),
        ).fetchone()
        assert season_row is not None
        assert season_row["episode_count"] == 2
        assert season_row["has_poster"] == 1

    def test_episode_stubs_created(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Episode stubs are inserted (one per video file per season)."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "series").mkdir(parents=True)
        show = disk_a / "series" / "TestShow (2023)"
        show.mkdir()
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">9999</uniqueid></tvshow>')
        s01 = show / "Saison 01"
        s01.mkdir()
        for ep in range(1, 6):
            (s01 / f"S01E0{ep}.mkv").write_bytes(b"\x00" * 100)

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        ep_count = conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
        assert ep_count == 5

    def test_unmounted_disk_skipped(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Disks whose path does not exist are skipped; no rows inserted."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        # Neither disk_a nor disk_b directories are created in the fake FS.
        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
        assert count == 0

    def test_idempotent_second_call(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Calling scan_library twice does not create duplicate media_item rows."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        movie = disk_a / "films" / "Dune (2021)"
        movie.mkdir()
        (movie / "Dune.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Dune.nfo").write_text('<movie><uniqueid type="tmdb">438631</uniqueid></movie>')

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)
            scan_library(scanner_config, conn)

        count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
        assert count == 1, f"expected 1 after two calls (upsert), got {count}"

    def test_nfo_missing_status(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Movie without NFO gets nfo_status='missing' in the DB."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        movie = disk_a / "films" / "NoNfo (2024)"
        movie.mkdir()
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 1000)

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT nfo_status FROM media_item WHERE title = 'NoNfo'").fetchone()
        assert row is not None
        assert row["nfo_status"] == "missing"

    def test_dispatch_attrs_written_for_each_item(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Each media_item gets dispatch_path + dispatch_disk + dispatch_normalized_title.

        This guarantees that downstream consumers — in particular
        ``trailers/scanner.py``, ``indexer/release_linker.py``, and the
        ``find_by_normalized_name`` / ``list_all_dispatch_items`` queries
        in ``indexer/repos/item_repo.py`` (both INNER JOIN on
        ``dispatch_normalized_title``) — can locate the on-disk media
        directory and the item itself for any item discovered by the
        library scanner, not only by the dispatch layer.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        movie = disk_a / "films" / "Tenet (2020)"
        movie.mkdir()
        (movie / "Tenet.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Tenet.nfo").write_text('<movie><uniqueid type="tmdb">577922</uniqueid></movie>')

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id FROM media_item WHERE title = 'Tenet'").fetchone()
        assert row is not None
        item_id = row["id"]

        attrs = {
            r["key"]: r["value"]
            for r in conn.execute(
                "SELECT key, value FROM item_attribute WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        }
        assert attrs.get("dispatch_path") == str(movie)
        assert attrs.get("dispatch_disk") == scanner_config.disks[0].id
        # NFC-lowercased title — same normalization as
        # ``dispatch.media_index._normalize_key``.
        assert attrs.get("dispatch_normalized_title") == "tenet"

    def test_item_issue_rows_persisted_for_dirty_dir(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """A movie with .actors/ + junk file gets matching ``item_issue`` rows.

        Without these rows the report layer cannot surface
        directory-hygiene issues without re-walking the disks.
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        movie = disk_a / "films" / "Dirty (2024)"
        movie.mkdir()
        (movie / "Dirty.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Dirty.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
        # Two real, different issue triggers per _detect_issues:
        # .actors/ subdir → ISSUE_ACTORS_DIR; .DS_Store junk → ISSUE_JUNK_FILES.
        (movie / ".actors").mkdir()
        (movie / ".DS_Store").write_text("")

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

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

    def test_item_issue_drops_resolved_issues_on_rescan(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Cleaning up an issue between scans removes the matching ``item_issue`` row."""
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        movie = disk_a / "films" / "Cleaned (2024)"
        movie.mkdir()
        (movie / "Cleaned.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Cleaned.nfo").write_text('<movie><uniqueid type="tmdb">2</uniqueid></movie>')
        actors_dir = movie / ".actors"
        actors_dir.mkdir()

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        conn.row_factory = sqlite3.Row
        item_row = conn.execute("SELECT id FROM media_item WHERE title = 'Cleaned'").fetchone()
        assert item_row is not None
        item_id = item_row["id"]
        before = {
            r["type"]
            for r in conn.execute(
                "SELECT type FROM item_issue WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        }
        assert ISSUE_ACTORS_DIR in before

        # User cleaned up: .actors/ is removed, then re-scans.
        actors_dir.rmdir()
        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)

        after = {
            r["type"]
            for r in conn.execute(
                "SELECT type FROM item_issue WHERE item_id = ?",
                (item_id,),
            ).fetchall()
        }
        assert ISSUE_ACTORS_DIR not in after

    def test_consecutive_calls_increment_scan_generation(self, fs: "FakeFilesystem", scanner_config: Config) -> None:
        """Two consecutive scan_library calls produce strictly-increasing scan generations.

        Verifies DESIGN §8.1: generations are monotonic across library walks so
        that miss-strike escalation works correctly.  The first call produces
        generation 1; the second call must produce generation 2 (or higher).
        """
        fs.pause()
        conn = _make_conn_real()
        fs.resume()

        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        movie = disk_a / "films" / "Monotonic (2023)"
        movie.mkdir()
        (movie / "Monotonic.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Monotonic.nfo").write_text('<movie><uniqueid type="tmdb">999001</uniqueid></movie>')

        with patch(_GUARD_PATCH, return_value=None):
            scan_library(scanner_config, conn)
            gen_after_first: int = conn.execute("SELECT MAX(generation) FROM scan_run").fetchone()[0] or 0

            scan_library(scanner_config, conn)
            gen_after_second: int = conn.execute("SELECT MAX(generation) FROM scan_run").fetchone()[0] or 0

        assert gen_after_first >= 1, f"first scan generation must be >= 1, got {gen_after_first}"
        assert gen_after_second > gen_after_first, (
            f"second call must use a higher generation than the first ({gen_after_second} > {gen_after_first})"
        )


# ---------------------------------------------------------------------------
# Unit tests — scan_movie_dir (unchanged public API; still used by callers)
# ---------------------------------------------------------------------------


class TestScanMovieDir:
    """Tests for scan_movie_dir — single movie directory scanning."""

    def test_complete_movie(self, tmp_path: Path) -> None:
        """Movie with NFO, poster, landscape should have no issues."""
        movie = tmp_path / "The Matrix (1999)"
        movie.mkdir()
        (movie / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
        (movie / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')
        (movie / "The Matrix-poster.jpg").write_bytes(b"\x00")
        (movie / "The Matrix-landscape.jpg").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.title == "The Matrix"
        assert item.year == 1999
        assert item.nfo.present is True
        assert item.nfo.valid is True
        assert item.nfo.tmdb_id == "603"
        assert item.artwork.poster is True
        assert item.artwork.landscape is True
        assert item.issues == []
        assert item.seasons is None
        assert item.category == CID.MOVIES

    def test_movie_with_actors_dir(self, tmp_path: Path) -> None:
        """Movie with .actors/ should flag ISSUE_ACTORS_DIR."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
        (movie / ".actors").mkdir()
        (movie / ".actors" / "Actor.jpg").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.actors_dir is True
        assert ISSUE_ACTORS_DIR in item.issues

    def test_movie_missing_nfo(self, tmp_path: Path) -> None:
        """Movie without NFO should report nfo.present=False."""
        movie = tmp_path / "NoNfo (2024)"
        movie.mkdir()
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.nfo.present is False
        assert item.nfo.valid is False

    def test_movie_with_empty_subdir(self, tmp_path: Path) -> None:
        """Movie with empty subdirectory should flag it."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Subs").mkdir()  # empty subdir

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_EMPTY_SUBDIR in item.issues

    def test_movie_with_junk_files(self, tmp_path: Path) -> None:
        """Movie with .DS_Store should flag junk."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / ".DS_Store").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_JUNK_FILES in item.issues

    def test_movie_bad_dir_name(self, tmp_path: Path) -> None:
        """Movie without (Year) in name should flag bad naming."""
        movie = tmp_path / "Some Movie"
        movie.mkdir()
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.year is None
        assert ISSUE_BAD_DIR_NAME in item.issues

    def test_macos_resource_forks_flagged(self, tmp_path: Path) -> None:
        """MacOS resource fork files (._*) should be flagged as junk."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "._Movie.mkv").write_bytes(b"\x00" * 100)

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_JUNK_FILES in item.issues

    def test_audiobook_no_year_not_flagged(self, tmp_path: Path) -> None:
        """Audiobooks by author name (no year) should NOT flag bad_dir_naming."""
        book = tmp_path / "Isaac Asimov"
        book.mkdir()
        (book / "Foundation.mp3").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(book, disk_id="drive_a", category_id=CID.AUDIOBOOKS)

        assert item.year is None
        assert ISSUE_BAD_DIR_NAME not in item.issues

    def test_folder_size_calculated(self, tmp_path: Path) -> None:
        """Folder size should sum all files recursively."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1024 * 1024)  # 1 MB

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        # ~1 MB = ~0.001 GB, should be > 0
        assert item.folder_size_gb > 0


# ---------------------------------------------------------------------------
# Unit tests — scan_tvshow_dir
# ---------------------------------------------------------------------------


class TestScanTvshowDir:
    """Tests for scan_tvshow_dir — single TV show directory scanning."""

    def test_complete_show(self, tmp_path: Path) -> None:
        """Show with NFO, poster, seasons, episodes."""
        show = tmp_path / "Fallout (2024)"
        show.mkdir()
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">106379</uniqueid></tvshow>')
        (show / "poster.jpg").write_bytes(b"\x00")
        (show / "landscape.jpg").write_bytes(b"\x00")

        s01 = show / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 1000)
        (s01 / "S01E01 - The Beginning.nfo").write_text("<episodedetails/>")
        (show / "season01-poster.jpg").write_bytes(b"\x00")

        item = scan_tvshow_dir(show, disk_id="drive_a", category_id=CID.TV_SHOWS)

        assert item.title == "Fallout"
        assert item.year == 2024
        assert item.media_type == "tvshow"
        assert item.nfo.valid is True
        assert item.artwork.poster is True
        assert item.seasons is not None
        assert len(item.seasons) == 1
        assert item.seasons[0].number == 1
        assert item.seasons[0].episode_count == 1
        assert item.seasons[0].has_poster is True
        assert item.seasons[0].episodes_with_nfo == 1
        assert item.category == CID.TV_SHOWS

    def test_show_multiple_seasons(self, tmp_path: Path) -> None:
        """Show with 2 seasons."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
        (show / "poster.jpg").write_bytes(b"\x00")

        for sn in (1, 2):
            s = show / f"Saison 0{sn}"
            s.mkdir()
            for ep in range(1, 4):
                (s / f"S0{sn}E0{ep} - Ep.mkv").write_bytes(b"\x00" * 100)

        item = scan_tvshow_dir(show, disk_id="drive_a", category_id=CID.TV_SHOWS)

        assert item.seasons is not None
        assert len(item.seasons) == 2
        assert item.seasons[0].episode_count == 3
        assert item.seasons[1].episode_count == 3


# ---------------------------------------------------------------------------
# Unit tests — parse_title_year
# ---------------------------------------------------------------------------


class TestParseTitleYear:
    """Direct tests for parse_title_year public API."""

    def test_title_with_year(self) -> None:
        """Standard 'Title (2024)' format."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("The Matrix (1999)")
        assert title == "The Matrix"
        assert year == 1999

    def test_title_without_year(self) -> None:
        """No year in parentheses returns None."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("Some Movie")
        assert title == "Some Movie"
        assert year is None

    def test_title_with_spaces(self) -> None:
        """Extra spaces around year should be handled."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("Movie  (2024) ")
        assert title == "Movie"
        assert year == 2024

    def test_title_with_non_year_parens(self) -> None:
        """Non-4-digit parens should not match."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("Movie (Extended)")
        assert year is None


# ---------------------------------------------------------------------------
# Unit tests — extract_nfo_ids
# ---------------------------------------------------------------------------


class TestExtractNfoIds:
    """Direct tests for extract_nfo_ids public API."""

    def test_both_ids(self, tmp_path: Path) -> None:
        """NFO with both TMDB and IMDB IDs."""
        nfo = tmp_path / "test.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb">603</uniqueid><uniqueid type="imdb">tt0133093</uniqueid></movie>')
        tmdb, imdb = extract_nfo_ids(nfo)
        assert tmdb == "603"
        assert imdb == "tt0133093"

    def test_empty_uniqueid_text(self, tmp_path: Path) -> None:
        """NFO with empty uniqueid text should return None."""
        nfo = tmp_path / "test.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb"></uniqueid></movie>')
        tmdb, imdb = extract_nfo_ids(nfo)
        assert tmdb is None
        assert imdb is None

    def test_corrupt_xml(self, tmp_path: Path) -> None:
        """Corrupt XML should return (None, None)."""
        nfo = tmp_path / "test.nfo"
        nfo.write_text("<movie><broken")
        tmdb, imdb = extract_nfo_ids(nfo)
        assert tmdb is None
        assert imdb is None

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Missing file should return (None, None)."""
        tmdb, imdb = extract_nfo_ids(tmp_path / "missing.nfo")
        assert tmdb is None
        assert imdb is None


# ---------------------------------------------------------------------------
# Unit tests — NTFS unsafe detection
# ---------------------------------------------------------------------------


class TestNtfsUnsafeDetection:
    """Tests for NTFS-unsafe name detection in scanner."""

    def test_ntfs_unsafe_filename_flagged(self, tmp_path: Path) -> None:
        """File with NTFS-illegal ':' should flag ISSUE_NTFS_UNSAFE."""
        from personalscraper.library.models import ISSUE_NTFS_UNSAFE

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        # Create file with colon (common in TMDB French titles)
        (movie / "Spirale : L'Héritage.txt").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_NTFS_UNSAFE in item.issues
