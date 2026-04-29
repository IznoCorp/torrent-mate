"""Tests for personalscraper.library.analyzer — rewritten for sub-phase 7.2.

Two test suites:

1. ``TestDeduceAudioProfile`` — pure-logic unit tests for the audio-profile
   deduction helper (unchanged from pre-7.2; no DB required).

2. ``TestAnalyze`` — DB-query tests for :func:`analyze`.
   Seeds an in-memory SQLite DB with known ``media_item`` and ``season`` rows,
   then asserts that :func:`analyze` returns the expected :class:`AnalysisResult`
   counts.  No JSON file is written or read.

3. ``TestAnalyzeLibrary`` — ffprobe iteration tests for :func:`analyze_library`
   (filesystem-level; uses ``unittest.mock.patch`` for ``extract_stream_info``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf.models import CategoryConfig, Config, DiskConfig, PathConfig
from personalscraper.indexer.db import apply_migrations
from personalscraper.library.analyzer import AnalysisResult, analyze, deduce_audio_profile
from tests.fixtures.config import CANONICAL_STAGING_DIRS

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Shared artwork JSON fixtures
# ---------------------------------------------------------------------------

_ARTWORK_ALL_ABSENT = (
    '{"poster":false,"fanart":false,"landscape":false,"banner":false,'
    '"clearlogo":false,"clearart":false,"discart":false,"characterart":false}'
)
_ARTWORK_POSTER_PRESENT = (
    '{"poster":true,"fanart":false,"landscape":false,"banner":false,'
    '"clearlogo":false,"clearart":false,"discart":false,"characterart":false}'
)

# ---------------------------------------------------------------------------
# Paths to migration scripts
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied.

    Returns:
        Open :class:`sqlite3.Connection` with migrations applied and FK checks on.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------


def _make_v15_config(
    disk_path: Path,
    disk_id: str,
    folder_name: str,
    category_id: str,
    tmp_path: Path,
) -> Config:
    """Create a minimal V15 Config for a single disk/category.

    Args:
        disk_path: Root path of the disk.
        disk_id: Disk identifier.
        folder_name: Category folder name.
        category_id: Category ID.
        tmp_path: Pytest temporary directory.

    Returns:
        :class:`Config` with one disk and one category.
    """
    disk_cfg = DiskConfig(id=disk_id, path=disk_path, categories=[category_id])
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={category_id: CategoryConfig(folder_name=folder_name)},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_media_item(
    conn: sqlite3.Connection,
    *,
    kind: str = "movie",
    title: str = "Test",
    category_id: str = "movies",
    nfo_status: str = "valid",
    artwork_json: str | None = None,
) -> int:
    """Insert a minimal ``media_item`` row and return its PK.

    Args:
        conn: Open SQLite connection.
        kind: ``'movie'`` or ``'show'``.
        title: Item title.
        category_id: Category ID string.
        nfo_status: ``'valid'``, ``'invalid'``, or ``'missing'``.
        artwork_json: Raw JSON string or None.

    Returns:
        PK of the inserted row.
    """
    import time

    now = int(time.time())
    if artwork_json is None:
        artwork_json = _ARTWORK_ALL_ABSENT
    cur = conn.execute(
        """
        INSERT INTO media_item
            (kind, title, title_sort, original_title, year, category_id,
             tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json,
             date_created, date_modified, date_metadata_refreshed,
             is_locked, preferred_lang)
        VALUES (?, ?, ?, NULL, NULL, ?, NULL, NULL, NULL, ?, ?, ?, ?, NULL, 0, 'fr')
        """,
        (kind, title, title, category_id, nfo_status, artwork_json, now, now),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_season(conn: sqlite3.Connection, *, item_id: int, number: int = 1, has_poster: int = 1) -> int:
    """Insert a minimal ``season`` row and return its PK.

    Args:
        conn: Open SQLite connection.
        item_id: FK to the owning ``media_item`` row (must be ``kind='show'``).
        number: Season number.
        has_poster: 1 if poster present, 0 otherwise.

    Returns:
        PK of the inserted row.
    """
    cur = conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, ?, 0, ?, 0)",
        (item_id, number, has_poster),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Suite 1 — pure-logic audio profile tests
# ---------------------------------------------------------------------------


class TestDeduceAudioProfile:
    """Tests for audio profile detection logic."""

    def test_multi_two_languages(self) -> None:
        """Two different audio languages = multi."""
        tracks = [
            {"language": "fra", "is_default": True},
            {"language": "eng", "is_default": False},
        ]
        assert deduce_audio_profile(tracks, []) == "multi"

    def test_vf_single_french(self) -> None:
        """Single French audio = vf."""
        tracks = [{"language": "fra", "is_default": True}]
        assert deduce_audio_profile(tracks, []) == "vf"

    def test_vostfr_eng_audio_french_sub(self) -> None:
        """English audio + French subtitle = vostfr."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"

    def test_vostfr_japanese_audio_french_sub(self) -> None:
        """Japanese audio + French subtitle = vostfr (anime)."""
        audio = [{"language": "jpn", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"

    def test_vo_english_no_french_subs(self) -> None:
        """English audio without French subtitles = vo."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "eng"}]
        assert deduce_audio_profile(audio, subs) == "vo"

    def test_vo_no_tracks(self) -> None:
        """No audio tracks = vo (unknown)."""
        assert deduce_audio_profile([], []) == "vo"

    def test_multi_three_languages(self) -> None:
        """Three different languages = multi."""
        tracks = [
            {"language": "fra", "is_default": True},
            {"language": "eng", "is_default": False},
            {"language": "jpn", "is_default": False},
        ]
        assert deduce_audio_profile(tracks, []) == "multi"

    def test_vf_fre_iso639_2b(self) -> None:
        """ISO 639-2/B 'fre' should be recognized as French (VF)."""
        tracks = [{"language": "fre", "is_default": True}]
        assert deduce_audio_profile(tracks, []) == "vf"

    def test_vostfr_fre_subtitle(self) -> None:
        """ISO 639-2/B 'fre' in subtitles should be recognized as VOSTFR."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "fre"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"

    def test_vf_fra_with_subs(self) -> None:
        """French audio with French subtitle should still be VF (not VOSTFR)."""
        audio = [{"language": "fra", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vf"

    def test_vo_und_language(self) -> None:
        """'und' (undefined) language without French subtitles = vo."""
        audio = [{"language": "und", "is_default": True}]
        assert deduce_audio_profile(audio, []) == "vo"

    def test_vo_empty_subs(self) -> None:
        """English audio without subtitles = vo."""
        audio = [{"language": "eng", "is_default": True}]
        assert deduce_audio_profile(audio, []) == "vo"

    def test_vostfr_via_second_sub(self) -> None:
        """Should detect VOSTFR even with multiple subtitle tracks."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "eng"}, {"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"


# ---------------------------------------------------------------------------
# Suite 2 — analyze(conn) DB-query tests
# ---------------------------------------------------------------------------


class TestAnalyze:
    """Tests for analyze(conn) — DB-query health summary."""

    def test_empty_db_returns_zero_counts(self) -> None:
        """analyze() on an empty DB returns all-zero AnalysisResult."""
        conn = _make_conn()
        result = analyze(conn)

        assert isinstance(result, AnalysisResult)
        assert result.total_items == 0
        assert result.movies_count == 0
        assert result.shows_count == 0
        assert result.nfo.valid == 0
        assert result.nfo.invalid == 0
        assert result.nfo.missing == 0
        assert result.artwork.poster_present == 0
        assert result.artwork.poster_missing == 0
        assert result.seasons_missing_poster == 0
        assert result.items_needing_rescrape == 0
        assert result.analyzed_at != ""

    def test_total_and_kind_counts(self) -> None:
        """total_items, movies_count, shows_count are correct."""
        conn = _make_conn()
        _seed_media_item(conn, kind="movie", title="Film A")
        _seed_media_item(conn, kind="movie", title="Film B")
        show_id = _seed_media_item(conn, kind="show", title="Serie A")
        _seed_season(conn, item_id=show_id)

        result = analyze(conn)

        assert result.total_items == 3
        assert result.movies_count == 2
        assert result.shows_count == 1

    def test_nfo_status_breakdown(self) -> None:
        """NFO valid/invalid/missing counts match seeded rows."""
        conn = _make_conn()
        _seed_media_item(conn, title="Valid NFO", nfo_status="valid")
        _seed_media_item(conn, title="Invalid NFO", nfo_status="invalid")
        _seed_media_item(conn, title="Missing NFO", nfo_status="missing")

        result = analyze(conn)

        assert result.nfo.valid == 1
        assert result.nfo.invalid == 1
        assert result.nfo.missing == 1

    def test_poster_presence_counts(self) -> None:
        """poster_present and poster_missing counts match artwork_json content."""
        conn = _make_conn()
        # Item with poster=true
        _seed_media_item(
            conn,
            title="Has Poster",
            artwork_json='{"poster":true,"fanart":false,"landscape":false,"banner":false,"clearlogo":false,"clearart":false,"discart":false,"characterart":false}',
        )
        # Item with poster=false
        _seed_media_item(
            conn,
            title="No Poster",
            artwork_json='{"poster":false,"fanart":false,"landscape":false,"banner":false,"clearlogo":false,"clearart":false,"discart":false,"characterart":false}',
        )

        result = analyze(conn)

        assert result.artwork.poster_present == 1
        assert result.artwork.poster_missing == 1

    def test_seasons_missing_poster_count(self) -> None:
        """seasons_missing_poster counts season rows with has_poster=0."""
        conn = _make_conn()
        show_id = _seed_media_item(conn, kind="show", title="ShowX")
        _seed_season(conn, item_id=show_id, number=1, has_poster=1)
        _seed_season(conn, item_id=show_id, number=2, has_poster=0)
        _seed_season(conn, item_id=show_id, number=3, has_poster=0)

        result = analyze(conn)

        assert result.seasons_missing_poster == 2

    def test_nfo_invalid_by_category(self) -> None:
        """nfo_invalid_by_category groups invalid-NFO items per category."""
        conn = _make_conn()
        _seed_media_item(conn, title="A", category_id="movies", nfo_status="invalid")
        _seed_media_item(conn, title="B", category_id="movies", nfo_status="missing")
        _seed_media_item(conn, kind="show", title="C", category_id="tv_shows", nfo_status="invalid")
        _seed_media_item(conn, title="D", category_id="movies", nfo_status="valid")

        result = analyze(conn)

        assert result.nfo_invalid_by_category.get("movies", 0) == 2
        assert result.nfo_invalid_by_category.get("tv_shows", 0) == 1
        # Valid item must not appear under invalid breakdown
        assert result.nfo_invalid_by_category.get("movies", 0) != 3

    def test_poster_missing_by_category(self) -> None:
        """poster_missing_by_category groups poster-missing items per category."""
        conn = _make_conn()
        poster_absent = _ARTWORK_ALL_ABSENT
        poster_present = _ARTWORK_POSTER_PRESENT
        _seed_media_item(conn, title="A", category_id="movies", artwork_json=poster_absent)
        _seed_media_item(conn, title="B", category_id="movies", artwork_json=poster_present)
        _seed_media_item(conn, kind="show", title="C", category_id="tv_shows", artwork_json=poster_absent)

        result = analyze(conn)

        assert result.poster_missing_by_category.get("movies", 0) == 1
        assert result.poster_missing_by_category.get("tv_shows", 0) == 1

    def test_items_needing_rescrape(self) -> None:
        """items_needing_rescrape counts rows with invalid NFO or no metadata refresh."""
        import time

        conn = _make_conn()
        # Valid NFO and has been scraped → NOT a rescrape candidate
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO media_item
                (kind, title, title_sort, original_title, year, category_id,
                 tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json,
                 date_created, date_modified, date_metadata_refreshed,
                 is_locked, preferred_lang)
            VALUES ('movie','Scraped','Scraped',NULL,NULL,'movies',NULL,NULL,NULL,'valid',NULL,?,?,?,0,'fr')
            """,
            (now, now, now),
        )
        # Invalid NFO, no metadata refresh → rescrape candidate
        _seed_media_item(conn, title="Needs Rescrape", nfo_status="invalid")
        # Valid NFO but never scraped → also a candidate
        _seed_media_item(conn, title="Never Scraped", nfo_status="valid")

        result = analyze(conn)

        # "Scraped" is NOT a candidate (valid NFO + refreshed); the other 2 are
        assert result.items_needing_rescrape == 2

    def test_no_json_file_written(self, tmp_path: Path) -> None:
        """analyze() writes no JSON file to disk."""
        conn = _make_conn()
        _seed_media_item(conn, title="Movie X")

        analyze(conn)

        # Confirm no library_analysis.json was written anywhere in tmp_path
        json_files = list(tmp_path.rglob("library_analysis.json"))
        assert json_files == []

    def test_analyzed_at_is_iso8601(self) -> None:
        """analyzed_at field is a non-empty ISO 8601 string."""
        conn = _make_conn()
        result = analyze(conn)

        assert result.analyzed_at != ""
        # Should parse without raising
        from datetime import datetime

        dt = datetime.fromisoformat(result.analyzed_at)
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# Suite 3 — analyze_library (ffprobe) tests (kept for regression coverage)
# ---------------------------------------------------------------------------


class TestAnalyzeLibrary:
    """Tests for analyze_library — disk iteration, filtering, incremental."""

    def _make_stream_info(self) -> dict:  # type: ignore[type-arg]
        """Create a minimal stream info dict for mocking extract_stream_info.

        Returns:
            Minimal stream info dict accepted by _analyze_video_file.
        """
        return {
            "video": {
                "codec": "hevc",
                "width": 1920,
                "height": 1080,
                "bitrate_kbps": 5000,
                "hdr": {"is_hdr": False, "hdr_type": None},
            },
            "audio": [{"codec": "aac", "language": "fra", "channels": 2, "is_atmos": False, "is_default": True}],
            "subtitle": [],
            "duration_seconds": 7200.0,
        }

    def test_disk_filter(self, tmp_path: Path) -> None:
        """--disk filter should only analyze the specified disk."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk1 = tmp_path / "d1" / "medias"
        disk2 = tmp_path / "d2" / "medias"
        (disk1 / "films" / "A (2024)").mkdir(parents=True)
        (disk1 / "films" / "A (2024)" / "a.mkv").write_bytes(b"\x00" * 1000)
        (disk2 / "films" / "B (2024)").mkdir(parents=True)
        (disk2 / "films" / "B (2024)" / "b.mkv").write_bytes(b"\x00" * 1000)

        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[
                DiskConfig(id="disk1", path=disk1, categories=["movies"]),
                DiskConfig(id="disk2", path=disk2, categories=["movies"]),
            ],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )

        with patch("personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()):
            result = analyze_library(config, disk_filter="disk1")

        assert result.item_count == 1

    def test_max_items(self, tmp_path: Path) -> None:
        """--max-items should limit items analyzed."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        for name in ("A (2024)", "B (2024)", "C (2024)"):
            d = disk / "films" / name
            d.mkdir(parents=True)
            (d / "movie.mkv").write_bytes(b"\x00" * 1000)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)

        with patch("personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()):
            result = analyze_library(config, max_items=2)

        assert result.item_count == 2

    def test_incremental_skips_unchanged(self, tmp_path: Path) -> None:
        """Incremental mode should skip files with matching size_gb."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        video = movie / "Movie.mkv"
        video.write_bytes(b"\x00" * 1000)
        size_gb = round(video.stat().st_size / (1024**3), 3)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        existing = {str(video): size_gb}

        with patch(
            "personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()
        ) as mock_extract:
            result = analyze_library(config, incremental=True, existing_sizes=existing)

        mock_extract.assert_not_called()
        assert result.file_count == 0

    def test_macos_resource_forks_skipped(self, tmp_path: Path) -> None:
        """MacOS resource fork files (._*) should be skipped."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "._Movie.mkv").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)

        with patch(
            "personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()
        ) as mock_extract:
            analyze_library(config)

        assert mock_extract.call_count == 1
