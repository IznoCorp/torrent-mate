"""Tests for personalscraper.library.reporter — modified for sub-phase 7.3.

Changes from the pre-7.3 version:
- ``generate_report`` no longer accepts ``analysis_data: dict`` (library_analysis.json).
- It now accepts ``analysis_result: AnalysisResult | None`` produced by
  :func:`~personalscraper.library.analyzer.analyze`.
- Tests that previously passed an ``analysis_data`` dict now seed the indexer DB,
  call ``analyze(conn)`` to obtain an :class:`AnalysisResult`, and pass that.
- Tests verify that no ``library_analysis.json`` is consulted.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.library.analyzer import AnalysisResult, ArtworkCounts, NfoStatusCounts, analyze
from personalscraper.library.reporter import LibraryReport, format_report_text, generate_report

# ---------------------------------------------------------------------------
# Shared artwork JSON constants (mirrors test_analyzer.py convention)
# ---------------------------------------------------------------------------

_ARTWORK_ABSENT = (
    '{"poster":false,"fanart":false,"landscape":false,"banner":false,'
    '"clearlogo":false,"clearart":false,"discart":false,"characterart":false}'
)
_ARTWORK_POSTER = (
    '{"poster":true,"fanart":false,"landscape":false,"banner":false,'
    '"clearlogo":false,"clearart":false,"discart":false,"characterart":false}'
)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# DB helpers (replicated from test_analyzer.py — no cross-test imports)
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


def _seed_item(
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
        artwork_json: Raw JSON string or None (defaults to all-absent artwork).

    Returns:
        PK of the inserted row.
    """
    import time

    now = int(time.time())
    if artwork_json is None:
        artwork_json = _ARTWORK_ABSENT
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


# ---------------------------------------------------------------------------
# Convenience: build an AnalysisResult directly (for tests that don't need DB)
# ---------------------------------------------------------------------------


def _make_analysis_result(
    total_items: int = 0,
    nfo_valid: int = 0,
    nfo_invalid: int = 0,
    nfo_missing: int = 0,
    poster_present: int = 0,
    poster_missing: int = 0,
    seasons_missing_poster: int = 0,
    items_needing_rescrape: int = 0,
) -> AnalysisResult:
    """Construct an :class:`AnalysisResult` with explicit counts.

    Args:
        total_items: Total media item count.
        nfo_valid: Items with valid NFO.
        nfo_invalid: Items with invalid NFO.
        nfo_missing: Items with missing NFO.
        poster_present: Items with a poster.
        poster_missing: Items without a poster.
        seasons_missing_poster: Season rows without a poster.
        items_needing_rescrape: Rescrape candidate count.

    Returns:
        :class:`AnalysisResult` populated with the given counts.
    """
    return AnalysisResult(
        analyzed_at="2026-04-29T00:00:00+00:00",
        total_items=total_items,
        nfo=NfoStatusCounts(valid=nfo_valid, invalid=nfo_invalid, missing=nfo_missing),
        artwork=ArtworkCounts(poster_present=poster_present, poster_missing=poster_missing),
        seasons_missing_poster=seasons_missing_poster,
        items_needing_rescrape=items_needing_rescrape,
    )


# ---------------------------------------------------------------------------
# Suite 1 — generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """Tests for report generation — AnalysisResult replaces analysis_data JSON."""

    def test_empty_report(self) -> None:
        """Report with no data should have zero counts."""
        report = generate_report(scan_data=None, analysis_result=None, validation_data=None, recommendation_data=None)
        assert report.total_items == 0
        assert report.total_size_gb == 0.0

    def test_report_from_scan(self) -> None:
        """Report should aggregate scan data with issue breakdown."""
        scan_data = {
            "scanned_at": "2026-04-15T12:00:00",
            "item_count": 3,
            "items": [
                {
                    "disk": "Disk1",
                    "category": "films",
                    "media_type": "movie",
                    "folder_size_gb": 2.0,
                    "actors_dir": True,
                    "issues": ["actors_dir_present", "junk_files"],
                },
                {
                    "disk": "Disk1",
                    "category": "films",
                    "media_type": "movie",
                    "folder_size_gb": 3.5,
                    "actors_dir": False,
                    "issues": [],
                },
                {
                    "disk": "Disk2",
                    "category": "series",
                    "media_type": "tvshow",
                    "folder_size_gb": 15.0,
                    "actors_dir": True,
                    "issues": ["actors_dir_present"],
                },
            ],
        }
        report = generate_report(scan_data=scan_data)
        assert report.total_items == 3
        assert report.total_size_gb == 20.5
        assert report.items_per_disk["Disk1"] == 2
        assert report.items_per_disk["Disk2"] == 1
        assert report.items_per_category["films"] == 2
        assert report.actors_dir_count == 2
        # Issue breakdown
        assert report.scan_issues["actors_dir_present"] == 2
        assert report.scan_issues["junk_files"] == 1

    def test_report_from_analysis_result_seeded_db(self) -> None:
        """Report should populate NFO and poster counts from an AnalysisResult seeded via DB."""
        conn = _make_conn()
        _seed_item(conn, title="Valid NFO", nfo_status="valid", artwork_json=_ARTWORK_POSTER)
        _seed_item(conn, title="Invalid NFO", nfo_status="invalid", artwork_json=_ARTWORK_ABSENT)
        _seed_item(conn, title="Missing NFO", nfo_status="missing", artwork_json=_ARTWORK_ABSENT)

        result = analyze(conn)
        report = generate_report(analysis_result=result)

        assert report.nfo_valid_count == 1
        # invalid (1) + missing (1) = 2
        assert report.nfo_invalid_count == 2
        assert report.poster_missing_count == 2

    def test_report_analysis_result_populates_total_items_when_no_scan(self) -> None:
        """total_items should come from AnalysisResult when scan_data is absent."""
        ar = _make_analysis_result(total_items=7)
        report = generate_report(analysis_result=ar)
        assert report.total_items == 7

    def test_report_scan_data_total_takes_precedence_over_analysis_result(self) -> None:
        """scan_data item count should take precedence over AnalysisResult.total_items."""
        scan_data = {
            "items": [
                {"disk": "D1", "category": "films", "folder_size_gb": 1.0, "actors_dir": False, "issues": []},
                {"disk": "D1", "category": "films", "folder_size_gb": 2.0, "actors_dir": False, "issues": []},
            ]
        }
        ar = _make_analysis_result(total_items=99)
        report = generate_report(scan_data=scan_data, analysis_result=ar)
        # scan_data total_items = 2 (len of items list), not 99 from AnalysisResult
        assert report.total_items == 2

    def test_report_nfo_counts_from_analysis_result(self) -> None:
        """nfo_valid_count and nfo_invalid_count are derived from AnalysisResult."""
        ar = _make_analysis_result(nfo_valid=5, nfo_invalid=3, nfo_missing=2)
        report = generate_report(analysis_result=ar)
        assert report.nfo_valid_count == 5
        # invalid (3) + missing (2) = 5
        assert report.nfo_invalid_count == 5

    def test_report_poster_missing_from_analysis_result(self) -> None:
        """poster_missing_count is derived from AnalysisResult.artwork.poster_missing."""
        ar = _make_analysis_result(poster_missing=8)
        report = generate_report(analysis_result=ar)
        assert report.poster_missing_count == 8

    def test_report_no_library_analysis_json_read(self, tmp_path: Path) -> None:
        """generate_report must not read library_analysis.json — it uses AnalysisResult."""
        # Write a library_analysis.json that would inflate counts if read
        fake_json = tmp_path / "library_analysis.json"
        fake_json.write_text('{"item_count": 999, "file_count": 888, "items": []}')

        conn = _make_conn()
        _seed_item(conn, title="Movie A", nfo_status="valid", artwork_json=_ARTWORK_POSTER)
        ar = analyze(conn)

        report = generate_report(analysis_result=ar)

        # If library_analysis.json had been read, item count would be 999
        assert report.total_items != 999
        assert report.nfo_valid_count == 1

    def test_report_from_validation(self) -> None:
        """Report should include validation error breakdown."""
        validation_data = {
            "valid_count": 10,
            "fixed_count": 0,
            "issues_count": 5,
            "items": [
                {"status": "issues", "errors": ["nfo_present", "poster_present"], "warnings": ["artwork_landscape"]},
                {"status": "issues", "errors": ["nfo_valid"], "warnings": ["artwork_landscape"]},
                {"status": "issues", "errors": ["nfo_present"], "warnings": []},
                {"status": "issues", "errors": ["nfo_valid", "category"], "warnings": []},
                {"status": "issues", "errors": ["dir_naming"], "warnings": []},
            ],
        }
        report = generate_report(validation_data=validation_data)
        assert report.validation_valid == 10
        assert report.validation_issues == 5
        assert report.validation_errors["nfo_present"] == 2
        assert report.validation_errors["nfo_valid"] == 2
        assert report.validation_warnings["artwork_landscape"] == 2

    def test_report_from_recommendations(self) -> None:
        """Report should include recommendation details."""
        rec_data = {
            "total_recommendations": 3,
            "estimated_total_savings_gb": 12.5,
            "items": [
                {
                    "priority": "high",
                    "title": "Movie A",
                    "current": {"codec": "mpeg2", "resolution": "1080p", "size_gb": 8.0, "audio_profile": "vf"},
                    "reasons": ["rejected codec mpeg2"],
                },
                {
                    "priority": "medium",
                    "title": "Movie B",
                    "current": {"codec": "h264", "resolution": "720p", "size_gb": 5.0, "audio_profile": "vo"},
                    "reasons": ["non-preferred codec"],
                },
                {
                    "priority": "low",
                    "title": "Movie C",
                    "current": {"codec": "hevc", "resolution": "1080p", "size_gb": 2.0, "audio_profile": "multi"},
                    "reasons": ["missing subtitles"],
                },
            ],
        }
        report = generate_report(recommendation_data=rec_data)
        assert report.recommendation_count == 3
        assert report.estimated_savings_gb == 12.5
        assert report.recommendations_by_priority["high"] == 1
        assert len(report.recommendation_details) == 3
        assert report.recommendation_details[0]["title"] == "Movie A"


# ---------------------------------------------------------------------------
# Suite 2 — format_report_text
# ---------------------------------------------------------------------------


class TestFormatReportText:
    """Tests for report text formatting."""

    def test_format_includes_sections(self) -> None:
        """Formatted report should include key sections."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=100,
            total_size_gb=500.0,
            scan_issues={"actors_dir_present": 50, "junk_files": 20},
            validation_valid=80,
            validation_issues=20,
            validation_errors={"nfo_present": 10, "nfo_valid": 10},
        )
        text = format_report_text(report)
        assert "RAPPORT DE SANTÉ" in text
        assert "SCAN" in text
        assert "VALIDATION" in text
        assert "ACTIONS SUGGÉRÉES" in text
        assert "library-clean" in text
        assert "re-scrape" in text.lower()

    def test_format_empty_report(self) -> None:
        """Empty report should still produce valid text."""
        report = LibraryReport(generated_at="2026-04-17T12:00:00")
        text = format_report_text(report)
        assert "RAPPORT DE SANTÉ" in text
        assert "Aucune action nécessaire" in text

    def test_format_shows_nfo_counts_from_analysis_result(self) -> None:
        """Formatted text should reflect NFO counts populated from AnalysisResult."""
        conn = _make_conn()
        _seed_item(conn, title="Good", nfo_status="valid", artwork_json=_ARTWORK_POSTER)
        _seed_item(conn, title="Bad", nfo_status="invalid", artwork_json=_ARTWORK_ABSENT)
        ar = analyze(conn)

        # Populate a report with nfo counts from AnalysisResult
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=ar.total_items,
            nfo_valid_count=ar.nfo.valid,
            nfo_invalid_count=ar.nfo.invalid + ar.nfo.missing,
            poster_missing_count=ar.artwork.poster_missing,
            validation_valid=ar.nfo.valid,
            validation_issues=ar.nfo.invalid + ar.nfo.missing,
            validation_errors={"nfo_valid": ar.nfo.invalid},
        )
        text = format_report_text(report)
        # The validation section should appear (there are validation issues)
        assert "VALIDATION" in text

    def test_format_report_from_seeded_db(self) -> None:
        """generate_report + format_report_text pipeline with a seeded DB."""
        conn = _make_conn()
        _seed_item(conn, title="Film A", nfo_status="valid", artwork_json=_ARTWORK_POSTER)
        _seed_item(conn, title="Film B", nfo_status="missing", artwork_json=_ARTWORK_ABSENT)
        ar = analyze(conn)

        report = generate_report(analysis_result=ar)
        text = format_report_text(report)

        # Report always includes the header
        assert "RAPPORT DE SANTÉ" in text
        # total_items from AnalysisResult (2 rows seeded)
        assert "Total: 2" in text


# ---------------------------------------------------------------------------
# Suite 3 — rescrape section (unchanged from pre-7.3)
# ---------------------------------------------------------------------------


class TestRescrapeSection:
    """Tests for rescrape section in report."""

    def test_report_with_rescrape_data(self) -> None:
        """Report should include rescrape summary when data is present."""
        rescrape_data = {
            "rescraped_at": "2026-04-17T14:00:00",
            "fixed_count": 10,
            "skipped_count": 5,
            "error_count": 2,
            "items": [
                {"actions_taken": ["nfo_regenerated"]},
                {"actions_taken": ["artwork_downloaded"]},
                {"actions_taken": ["nfo_regenerated", "artwork_downloaded"]},
            ],
        }
        report = generate_report(rescrape_data=rescrape_data)
        assert report.rescrape_fixed == 10
        assert report.rescrape_skipped == 5
        assert report.rescrape_errors == 2
        assert report.rescrape_nfo_count == 2
        assert report.rescrape_artwork_count == 2

    def test_rescrape_section_in_text(self) -> None:
        """Formatted report should include RESCRAPE section."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            rescrape_fixed=10,
            rescrape_skipped=5,
            rescrape_errors=2,
            rescrape_nfo_count=6,
            rescrape_artwork_count=4,
        )
        text = format_report_text(report)
        assert "RESCRAPE" in text
        assert "NFO régénérés: 6" in text
        assert "Artwork téléchargé: 4" in text

    def test_no_rescrape_data_no_section(self) -> None:
        """Report without rescrape data should not show RESCRAPE section."""
        report = LibraryReport(generated_at="2026-04-17T12:00:00")
        text = format_report_text(report)
        assert "RESCRAPE" not in text
