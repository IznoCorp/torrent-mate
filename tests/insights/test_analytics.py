"""Tests for personalscraper.insights.analytics.

Migrated from ``tests/library/test_analyzer.py`` (lib-fold Phase 4). The
ffprobe ``analyze_library`` / ``_analyze_video_file`` suites were dropped —
those functions were deleted with the library ffprobe re-scan.

Three test suites remain:

1. ``TestDeduceAudioProfile`` — pure-logic unit tests for the audio-profile
   deduction helper (no DB required).

2. ``TestAnalyze`` — DB-query tests for :func:`analyze`.
   Seeds an in-memory SQLite DB with known ``media_item`` and ``season`` rows,
   then asserts that :func:`analyze` returns the expected :class:`AnalysisResult`
   counts.  No JSON file is written or read.

3. ``TestAnalyzeFromIndexExtraBranches`` — targeted branch tests for
   :func:`analyze_from_index` (reads ``media_stream``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.insights.analytics import AnalysisResult, analyze, deduce_audio_profile

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
             external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json,
             date_created, date_modified, date_metadata_refreshed,
             is_locked, preferred_lang)
        VALUES (?, ?, ?, NULL, NULL, ?, '{}', NULL, NULL, ?, ?, ?, ?, NULL, 0, 'fr')
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
                 external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json,
                 date_created, date_modified, date_metadata_refreshed,
                 is_locked, preferred_lang)
            VALUES ('movie','Scraped','Scraped',NULL,NULL,'movies','{}',NULL,NULL,'valid',NULL,?,?,?,0,'fr')
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

    def test_no_file_written(self, tmp_path: Path) -> None:
        """analyze() writes no files to disk."""
        conn = _make_conn()
        _seed_media_item(conn, title="Movie X")

        analyze(conn)

        assert list(tmp_path.iterdir()) == []

    def test_analyzed_at_is_iso8601(self) -> None:
        """analyzed_at field is a non-empty ISO 8601 string."""
        conn = _make_conn()
        result = analyze(conn)

        assert result.analyzed_at != ""
        # Should parse without raising
        from datetime import datetime

        dt = datetime.fromisoformat(result.analyzed_at)
        assert dt.tzinfo is not None

    def test_scan_issues_aggregated_from_item_issue(self) -> None:
        """``analyze()`` reports per-type counts sourced from the item_issue table."""
        conn = _make_conn()
        item_a = _seed_media_item(conn, kind="movie", title="A")
        item_b = _seed_media_item(conn, kind="movie", title="B")
        item_c = _seed_media_item(conn, kind="movie", title="C")
        # Two .actors offenders, one junk_files offender, plus an
        # additional issue type that should also surface in the dict.
        rows = [
            (item_a, "actors_dir_present", 1),
            (item_b, "actors_dir_present", 1),
            (item_c, "junk_files", 1),
            (item_a, "bad_dir_naming", 1),
        ]
        for item_id, issue_type, ts in rows:
            conn.execute(
                "INSERT INTO item_issue (item_id, type, detail, detected_at) VALUES (?, ?, NULL, ?)",
                (item_id, issue_type, ts),
            )
        result = analyze(conn)

        assert result.scan_issues == {
            "actors_dir_present": 2,
            "junk_files": 1,
            "bad_dir_naming": 1,
        }
        assert result.actors_dir_count == 2

    def test_scan_issues_empty_when_table_clean(self) -> None:
        """Without any item_issue rows the report fields stay empty/zero."""
        conn = _make_conn()
        _seed_media_item(conn, kind="movie", title="Clean")
        result = analyze(conn)

        assert result.scan_issues == {}
        assert result.actors_dir_count == 0


# ---------------------------------------------------------------------------
# Suite 3 — analyze_from_index branch tests
# ---------------------------------------------------------------------------


class TestAnalyzeFromIndexExtraBranches:
    """Targeted tests for branches missed by the broader suite."""

    def test_category_filter_excludes_other_categories(self) -> None:
        """``category_filter`` skips items in other categories."""
        import time

        from personalscraper.insights.analytics import analyze_from_index

        conn = _make_conn()

        # Movie in 'movies' category — should be excluded by category_filter.
        cur = conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
            "VALUES (?, ?, ?, ?, NULL, 1, 0)",
            ("Disk1", "Disk1", "/Volumes/Disk1", int(time.time())),
        )
        disk_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (?, 'films/A', NULL, NULL)",
            (disk_id,),
        )
        path_id = cur.lastrowid
        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
            " external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
            " date_created, date_modified, "
            " date_metadata_refreshed, is_locked, preferred_lang) "
            "VALUES ('movie', 'A', 'A', NULL, NULL, 'movies', '{}', NULL, NULL, 'valid', NULL, ?, ?, NULL, 0, 'fr')",
            (now, now),
        )
        item_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
            "VALUES (?, NULL, NULL, NULL, NULL)",
            (item_id,),
        )
        release_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns, "
            " oshash, xxh3_partial, xxh3_full, scan_generation, last_verified_at, enriched_at, "
            " miss_strikes, deleted_at) "
            "VALUES (?, ?, 'A.mkv', 1000, 0, NULL, NULL, NULL, NULL, 1, ?, ?, 0, NULL)",
            (release_id, path_id, now, now),
        )
        file_id = cur.lastrowid
        conn.execute(
            "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
            " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
            "VALUES (?, 0, 'video', 'h264', NULL, NULL, 1920, 1080, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
            (file_id,),
        )

        result = analyze_from_index(conn, category_filter="anime")
        assert result.item_count == 0
        # And same DB without the filter returns the item.
        result_all = analyze_from_index(conn)
        assert result_all.item_count == 1

    def test_item_with_no_files_skipped(self) -> None:
        """Items without any media_file rows do not appear."""
        import time

        from personalscraper.insights.analytics import analyze_from_index

        conn = _make_conn()
        # Item with no release, no files at all.
        now = int(time.time())
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
            " external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
            " date_created, date_modified, "
            " date_metadata_refreshed, is_locked, preferred_lang) "
            "VALUES ('movie', 'Empty', 'Empty', NULL, NULL, 'movies', '{}', NULL, NULL, "
            "'valid', NULL, ?, ?, NULL, 0, 'fr')",
            (now, now),
        )

        result = analyze_from_index(conn)
        assert result.item_count == 0

    def test_file_with_only_audio_streams_skipped(self) -> None:
        """A file row that has streams but no video stream is skipped.

        Covers the ``video_row is None`` early return inside
        ``_file_analysis_from_index``.
        """
        import time

        from personalscraper.insights.analytics import analyze_from_index

        conn = _make_conn()
        cur = conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
            "VALUES ('Disk1', 'Disk1', '/Volumes/Disk1', ?, NULL, 1, 0)",
            (int(time.time()),),
        )
        disk_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (?, 'films/A', NULL, NULL)",
            (disk_id,),
        )
        path_id = cur.lastrowid
        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
            " external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
            " date_created, date_modified, "
            " date_metadata_refreshed, is_locked, preferred_lang) "
            "VALUES ('movie', 'A', 'A', NULL, NULL, 'movies', '{}', NULL, NULL, 'valid', NULL, ?, ?, NULL, 0, 'fr')",
            (now, now),
        )
        item_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
            "VALUES (?, NULL, NULL, NULL, NULL)",
            (item_id,),
        )
        release_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns, "
            " oshash, xxh3_partial, xxh3_full, scan_generation, last_verified_at, enriched_at, "
            " miss_strikes, deleted_at) "
            "VALUES (?, ?, 'A.mkv', 1000, 0, NULL, NULL, NULL, NULL, 1, ?, ?, 0, NULL)",
            (release_id, path_id, now, now),
        )
        file_id = cur.lastrowid
        # ONLY audio stream — no video → file is skipped.
        conn.execute(
            "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
            " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
            "VALUES (?, 0, 'audio', 'aac', 'fra', 2, NULL, NULL, NULL, 128000, NULL, NULL, NULL, NULL, NULL)",
            (file_id,),
        )

        result = analyze_from_index(conn)
        assert result.item_count == 0
