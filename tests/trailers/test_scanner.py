"""Unit tests for trailers/scanner.py -- media-without-trailer detection.

Uses tmpdir fixtures to build fake media trees (movies and TV shows with/without
trailers). Library scanning path uses a seeded in-memory SQLite DB that mirrors
the indexer schema, asserting that find_items_without_trailer drives the result.
"""

from pathlib import Path

import pytest

from personalscraper.trailers.scanner import Scanner

# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def _make_movie_dir(parent: Path, name: str, with_trailer: bool = False) -> Path:
    """Create a fake movie directory with a minimal NFO.

    Args:
        parent: Parent directory to create the movie dir in.
        name: Directory name (e.g. "Fight Club (1999)").
        with_trailer: Whether to place a valid-size trailer file.

    Returns:
        Path to the created movie directory.
    """
    d = parent / name
    d.mkdir(parents=True)
    title = name.split("(")[0].strip()
    nfo = d / f"{title}.nfo"
    nfo.write_text(
        f'<movie><title>{title}</title><uniqueid type="tmdb">550</uniqueid></movie>',
        encoding="utf-8",
    )
    if with_trailer:
        (d / f"{name}-trailer.mp4").write_bytes(b"x" * 200000)
    return d


def _make_tvshow_dir(parent: Path, name: str, with_trailer: bool = False) -> Path:
    """Create a fake TV show directory with tvshow.nfo.

    Args:
        parent: Parent directory to create the show dir in.
        name: Directory name (e.g. "Breaking Bad (2008)").
        with_trailer: Whether to place a valid-size trailer file at show root.

    Returns:
        Path to the created TV show directory.
    """
    d = parent / name
    d.mkdir(parents=True)
    nfo = d / "tvshow.nfo"
    nfo.write_text(
        '<tvshow><title>Breaking Bad</title><uniqueid type="tmdb">1396</uniqueid></tvshow>',
        encoding="utf-8",
    )
    if with_trailer:
        # Flat convention: {show_name}-trailer.mp4 at show root.
        (d / f"{name}-trailer.mp4").write_bytes(b"x" * 200000)
    return d


def _make_tvshow_with_seasons(parent: Path, name: str, season_count: int) -> Path:
    """Create a fake TV show directory with N Saison XX/ subfolders.

    No trailers are placed -- every season is missing its trailer file.

    Args:
        parent: Parent directory for the show directory.
        name: Directory name (e.g. "Breaking Bad (2008)").
        season_count: Number of Saison XX/ subdirectories to create.

    Returns:
        Path to the created TV show directory.
    """
    d = _make_tvshow_dir(parent, name, with_trailer=False)
    for n in range(1, season_count + 1):
        (d / f"Saison {n:02d}").mkdir()
    return d


# ---------------------------------------------------------------------------
# Seeded indexer DB fixture helpers
# ---------------------------------------------------------------------------


def _open_seeded_db(schema_sql: str, seed_sql: str):  # type: ignore[no-untyped-def]
    """Open an in-memory SQLite connection with schema and seed data applied.

    Args:
        schema_sql: DDL statements to create tables.
        seed_sql: DML statements to insert test rows.

    Returns:
        An open :class:`sqlite3.Connection` (in-memory).
    """
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_sql)
    conn.executescript(seed_sql)
    return conn


_MINIMAL_SCHEMA = """
CREATE TABLE media_item (
    id                      INTEGER PRIMARY KEY,
    kind                    TEXT NOT NULL,
    title                   TEXT NOT NULL,
    title_sort              TEXT NOT NULL,
    original_title          TEXT,
    year                    INTEGER,
    category_id             TEXT NOT NULL,
    tmdb_id                 INTEGER,
    imdb_id                 TEXT,
    tvdb_id                 INTEGER,
    nfo_status              TEXT,
    artwork_json            TEXT,
    date_created            INTEGER NOT NULL,
    date_modified           INTEGER NOT NULL,
    date_metadata_refreshed INTEGER,
    is_locked               INTEGER NOT NULL DEFAULT 0,
    preferred_lang          TEXT NOT NULL DEFAULT 'fr'
);

CREATE TABLE item_attribute (
    item_id INTEGER NOT NULL REFERENCES media_item(id) ON DELETE CASCADE,
    key     TEXT NOT NULL,
    value   TEXT,
    PRIMARY KEY(item_id, key)
);
"""


# ---------------------------------------------------------------------------
# scan_staging
# ---------------------------------------------------------------------------


class TestScanStaging:
    """Tests for Scanner.scan_staging()."""

    def test_finds_movie_without_trailer(self, tmp_path: Path) -> None:
        """scan_staging returns a ScanItem for a movie missing its trailer."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].title == "Fight Club"

    def test_skips_movie_with_existing_trailer(self, tmp_path: Path) -> None:
        """scan_staging skips media whose trailer already exists and is large enough."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=True)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []

    def test_finds_tvshow_without_trailer(self, tmp_path: Path) -> None:
        """scan_staging returns ScanItem for TV show missing its trailer."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_dir(tvshows_dir, "Breaking Bad (2008)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].media_type == "tvshow"

    def test_scan_item_has_tmdb_id(self, tmp_path: Path) -> None:
        """ScanItem.tmdb_id is populated from the NFO."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items[0].tmdb_id == "550"

    def test_empty_staging_returns_empty_list(self, tmp_path: Path) -> None:
        """scan_staging returns [] for an empty staging directory."""
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []


# ---------------------------------------------------------------------------
# ScanItem dataclass
# ---------------------------------------------------------------------------


class TestScanItem:
    """Tests for ScanItem field population."""

    def test_scan_item_fields(self, tmp_path: Path) -> None:
        """ScanItem carries path, media_type, title, year, tmdb_id."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        item = items[0]
        assert item.path.is_dir()
        assert item.media_type == "movie"
        assert item.title == "Fight Club"
        assert item.year == 1999

    def test_scan_item_is_frozen(self, tmp_path: Path) -> None:
        """ScanItem is frozen — mutation raises FrozenInstanceError."""
        from dataclasses import FrozenInstanceError

        from personalscraper.trailers.scanner import ScanItem

        item = ScanItem(
            path=tmp_path,
            media_type="movie",
            title="X",
            year=2020,
            tmdb_id="1",
        )
        with pytest.raises(FrozenInstanceError):
            item.title = "Y"  # type: ignore[misc]

    def test_scan_item_negative_season_rejected(self, tmp_path: Path) -> None:
        """ScanItem rejects negative season_number values at construction."""
        from personalscraper.trailers.scanner import ScanItem

        with pytest.raises(ValueError, match="season_number"):
            ScanItem(
                path=tmp_path,
                media_type="tvshow",
                title="X",
                year=2020,
                tmdb_id="1",
                season_number=-3,
            )


# ---------------------------------------------------------------------------
# Season-aware scanning
# ---------------------------------------------------------------------------


class TestSeasonAwareScanning:
    """Tests for opt-in season-level ScanItem emission."""

    def test_season_scanner_emits_one_item_per_saison_folder_when_enabled(self, tmp_path: Path) -> None:
        """With seasons_enabled=True, scan emits show-level item + one item per season."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_with_seasons(tvshows_dir, "Breaking Bad (2008)", season_count=3)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=True)
        items = scanner.scan_staging(tmp_path)
        # Show-level + 3 seasons = 4 items
        assert len(items) == 4
        season_numbers = sorted(i.season_number for i in items if i.season_number is not None)
        assert season_numbers == [1, 2, 3]
        # Exactly one show-level entry (season_number is None)
        assert sum(1 for i in items if i.season_number is None) == 1

    def test_season_scanner_skips_seasons_when_disabled(self, tmp_path: Path) -> None:
        """With seasons_enabled=False (default), only the show-level ScanItem is emitted."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_with_seasons(tvshows_dir, "Breaking Bad (2008)", season_count=3)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=False)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].season_number is None


# ---------------------------------------------------------------------------
# Edge-case and library-scan coverage
# ---------------------------------------------------------------------------


class TestScanStagingEdgeCases:
    """Edge-case tests for Scanner.scan_staging() to cover missing-dir and hidden dirs."""

    def test_missing_staging_dir_returns_empty_list(self, tmp_path: "Path") -> None:
        """scan_staging returns [] and logs a warning when staging_dir does not exist."""
        missing = tmp_path / "does_not_exist"
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(missing)
        assert items == []

    def test_hidden_category_dir_is_skipped(self, tmp_path: "Path") -> None:
        """Directories starting with "." inside staging are silently skipped."""
        hidden = tmp_path / ".hidden_category"
        hidden.mkdir()
        movie_dir = hidden / "Some Movie (2020)"
        movie_dir.mkdir()
        (movie_dir / "Some Movie.nfo").write_text(
            '<movie><title>Some Movie</title><uniqueid type="tmdb">9999</uniqueid></movie>',
            encoding="utf-8",
        )
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []

    def test_hidden_media_dir_is_skipped(self, tmp_path: "Path") -> None:
        """Media directories starting with "." are silently skipped."""
        cat = tmp_path / "001-MOVIES"
        cat.mkdir()
        hidden_media = cat / ".hidden_movie"
        hidden_media.mkdir()
        (hidden_media / "title.nfo").write_text("<movie><title>Title</title></movie>", encoding="utf-8")
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []

    def test_season_with_existing_trailer_is_skipped(self, tmp_path: "Path") -> None:
        """scan_staging skips season whose trailer file already exists and is large enough.

        Plex per-season extras live under ``Saison NN/Trailers/`` so the scanner's
        existence check has to look there, not at a flat sibling.
        """
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        show_dir = _make_tvshow_dir(tvshows_dir, "Breaking Bad (2008)", with_trailer=False)
        saison_dir = show_dir / "Saison 01"
        (saison_dir / "Trailers").mkdir(parents=True)
        trailer_file = saison_dir / "Trailers" / "Breaking Bad (2008) - Saison 01.mp4"
        trailer_file.write_bytes(b"x" * 200000)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=True)
        items = scanner.scan_staging(tmp_path)
        season_items = [i for i in items if i.season_number is not None]
        assert season_items == [], f"Expected no season items but got {season_items}"


class TestScanStagingFileTypeWhitelist:
    """When config is provided, scan_staging restricts to MOVIE/TVSHOW staging entries.

    Regression: 2026-04-25 — without the whitelist, audio/ebook/scripts dirs
    were classified as movies and 47 audio books triggered YouTube downloads.
    """

    @staticmethod
    def _stub_config(staging_root: "Path", entries: list[tuple[int, str, str]]) -> object:
        """Build a duck-typed config with a configurable staging_dirs list.

        Args:
            staging_root: Path to inject as ``config.paths.staging_dir``.
            entries: List of ``(id, name, file_type)`` tuples driving
                ``config.staging_dirs``.

        Returns:
            A SimpleNamespace-like object the scanner accepts.
        """
        from types import SimpleNamespace

        staging_dirs = [SimpleNamespace(id=i, name=n, file_type=ft, role=None) for i, n, ft in entries]
        return SimpleNamespace(
            paths=SimpleNamespace(staging_dir=staging_root),
            staging_dirs=staging_dirs,
        )

    def test_skips_non_movie_non_tvshow_dirs_when_config_passed(self, tmp_path: "Path") -> None:
        """scan_staging(config=…) ignores audio/ebook/scripts dirs entirely."""
        # Layout matches a real personalscraper staging tree.
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        tvshows = tmp_path / "002-TVSHOWS"
        tvshows.mkdir()
        audio = tmp_path / "004-AUDIO"
        audio.mkdir()
        scripts = tmp_path / "099-SCRIPTS"
        scripts.mkdir()

        # Place a "movie-looking" item in each non-MOVIE/TVSHOW dir to prove it
        # is skipped by the whitelist, not by accidental absence of an NFO.
        for parent in (audio, scripts):
            book = parent / "Bernard Werber - Les Thanatonautes"
            book.mkdir()
            (book / "Bernard Werber - Les Thanatonautes.nfo").write_text(
                '<movie><title>Les Thanatonautes</title><uniqueid type="tmdb">1</uniqueid></movie>',
                encoding="utf-8",
            )

        # Real movie + tvshow that should appear in the result.
        movie_dir = movies / "Fight Club (1999)"
        movie_dir.mkdir()
        (movie_dir / "Fight Club (1999).nfo").write_text(
            '<movie><title>Fight Club</title><uniqueid type="tmdb">550</uniqueid></movie>',
            encoding="utf-8",
        )
        show_dir = tvshows / "Breaking Bad (2008)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text(
            '<tvshow><title>Breaking Bad</title><uniqueid type="tmdb">1396</uniqueid></tvshow>',
            encoding="utf-8",
        )

        config = self._stub_config(
            tmp_path,
            entries=[
                (1, "movies", "movie"),
                (2, "tvshows", "tvshow"),
                (4, "audio", "audio"),
                (99, "scripts", "other"),
            ],
        )
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path, config)

        paths = sorted(str(i.path) for i in items)
        assert paths == sorted([str(movie_dir), str(show_dir)])
        # No audio/scripts item leaked into the result.
        assert not any("004-AUDIO" in p or "099-SCRIPTS" in p for p in paths)
        # Items in 001-MOVIES are forced to media_type="movie", not inferred from NFO presence.
        movie_items = [i for i in items if i.path == movie_dir]
        assert movie_items and movie_items[0].media_type == "movie"

    def test_legacy_branch_walks_every_subdir_when_config_is_none(self, tmp_path: "Path") -> None:
        """Backwards compat: without config, scan_staging keeps the old permissive walk.

        This branch is what the existing tests rely on. The fix introduces the
        whitelist as opt-in via ``config``; legacy callers must keep working.
        """
        weird = tmp_path / "999-WEIRD"
        weird.mkdir()
        item = weird / "Some Item"
        item.mkdir()
        (item / "Some Item.nfo").write_text(
            '<movie><title>Some Item</title><uniqueid type="tmdb">7</uniqueid></movie>',
            encoding="utf-8",
        )
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)  # no config → legacy walk
        assert any(i.path == item for i in items)


# ---------------------------------------------------------------------------
# scan_library — indexer-query-based tests
# ---------------------------------------------------------------------------


class TestScanLibrary:
    """Tests for Scanner.scan_library() -- uses seeded in-memory indexer DB."""

    def _seed_movie(
        self,
        conn: object,  # sqlite3.Connection
        tmp_path: Path,
        *,
        item_id: int,
        title: str,
        tmdb_id: int | None = 550,
        with_trailer_attr: bool = False,
        with_dispatch_path: bool = True,
    ) -> Path:
        """Insert a movie row into the DB and create a fake directory.

        Args:
            conn: Open in-memory SQLite connection.
            tmp_path: Base temp directory for creating fake media dirs.
            item_id: Primary key for the media_item row.
            title: Movie title.
            tmdb_id: TMDB integer ID (or None).
            with_trailer_attr: If True, insert ``item_attribute(key='trailer_found')``.
            with_dispatch_path: If True, insert ``dispatch_path`` attribute pointing
                to the created media directory.

        Returns:
            Path to the fake media directory created on disk.
        """
        import sqlite3 as _sqlite3

        assert isinstance(conn, _sqlite3.Connection)
        movie_dir = tmp_path / f"{title} (1999)"
        movie_dir.mkdir(exist_ok=True)

        conn.execute(
            "INSERT INTO media_item (id, kind, title, title_sort, year, category_id, "
            "tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json, "
            "date_created, date_modified, is_locked, preferred_lang) "
            "VALUES (?, 'movie', ?, ?, 1999, 'movies', ?, NULL, NULL, 'valid', NULL, 0, 0, 0, 'fr')",
            (item_id, title, title, tmdb_id),
        )
        if with_trailer_attr:
            conn.execute(
                "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'trailer_found', ?)",
                (item_id, str(movie_dir / f"{title}-trailer.mp4")),
            )
        if with_dispatch_path:
            conn.execute(
                "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
                (item_id, str(movie_dir)),
            )
        conn.commit()
        return movie_dir

    def test_scan_library_returns_items_missing_trailers(self, tmp_path: Path) -> None:
        """scan_library returns ScanItems for library entries without trailer_found attribute."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club", tmdb_id=550)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_library(conn)

        assert len(items) == 1
        assert items[0].title == "Fight Club"
        assert items[0].tmdb_id == "550"
        assert items[0].media_type == "movie"

    def test_scan_library_skips_item_with_trailer_found_attribute(self, tmp_path: Path) -> None:
        """scan_library skips items that have a trailer_found attribute in the DB."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club", with_trailer_attr=True)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_library(conn)

        assert items == []

    def test_scan_library_skips_item_with_existing_trailer_on_disk(self, tmp_path: Path) -> None:
        """scan_library skips items whose trailer file exists on disk even when DB has no trailer_found."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        movie_dir = self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club")
        # Place a real trailer file — scan_library checks filesystem existence.
        (movie_dir / "Fight Club (1999)-trailer.mp4").write_bytes(b"x" * 200000)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_library(conn)

        assert items == []

    def test_scan_library_skips_item_without_dispatch_path(self, tmp_path: Path) -> None:
        """scan_library silently skips items that have no dispatch_path attribute."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        # Seed without dispatch_path so scanner cannot locate the directory.
        self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club", with_dispatch_path=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_library(conn)

        assert items == []

    def test_scan_library_disk_filter_excludes_other_disks(self, tmp_path: Path) -> None:
        """scan_library respects disk_filter by checking dispatch_disk attribute."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club")
        # Add dispatch_disk attribute pointing to a different disk.
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (1, 'dispatch_disk', 'drive_b')",
        )
        conn.commit()

        scanner = Scanner(min_file_size_bytes=102400)
        # Filtering to "drive_a" should return empty because our item is on "drive_b".
        items = scanner.scan_library(conn, disk_filter="drive_a")
        assert items == []

    def test_scan_library_disk_filter_includes_matching_disk(self, tmp_path: Path) -> None:
        """scan_library returns items when disk_filter matches dispatch_disk."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club")
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (1, 'dispatch_disk', 'drive_a')",
        )
        conn.commit()

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_library(conn, disk_filter="drive_a")
        assert len(items) == 1
        assert items[0].title == "Fight Club"

    def test_scan_library_category_filter(self, tmp_path: Path) -> None:
        """scan_library respects category_filter by checking media_item.category_id."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club")
        # Fight Club has category_id='movies'; filtering on 'animation' returns nothing.
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_library(conn, category_filter="animation")
        assert items == []

    def test_scan_library_multiple_items_partial_trailer_found(self, tmp_path: Path) -> None:
        """scan_library returns only items missing trailer_found when multiple are seeded."""
        conn = _open_seeded_db(_MINIMAL_SCHEMA, "")
        # Item 1: no trailer → should appear
        self._seed_movie(conn, tmp_path, item_id=1, title="Fight Club")
        # Item 2: has trailer_found → should be excluded
        self._seed_movie(conn, tmp_path, item_id=2, title="Inception", with_trailer_attr=True)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_library(conn)

        titles = [i.title for i in items]
        assert "Fight Club" in titles
        assert "Inception" not in titles
        assert len(items) == 1
