"""Tests for personalscraper.insights.reporter — DB-backed report generation.

``generate_report`` reads totals, distribution and top-largest data from
:class:`AnalysisResult` produced by
:func:`~personalscraper.insights.analytics.analyze` against the indexer DB.
Validation, recommendations, and rescrape data remain regular per-command
JSON outputs and are still consumed by the report.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.insights.analytics import analyze
from personalscraper.insights.models import AnalysisResult, ArtworkCounts, NfoStatusCounts
from personalscraper.insights.reporter import LibraryReport, format_report_text, generate_report

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
# DB helpers
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
             external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json,
             date_created, date_modified, date_metadata_refreshed,
             is_locked, preferred_lang)
        VALUES (?, ?, ?, NULL, NULL, ?, '{}', NULL, NULL, ?, ?, ?, ?, NULL, 0, 'fr')
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
    total_size_gb: float = 0.0,
    nfo_valid: int = 0,
    nfo_invalid: int = 0,
    nfo_missing: int = 0,
    poster_present: int = 0,
    poster_missing: int = 0,
    seasons_missing_poster: int = 0,
    items_needing_rescrape: int = 0,
    items_per_disk: dict[str, int] | None = None,
    items_per_category: dict[str, int] | None = None,
    size_per_disk_gb: dict[str, float] | None = None,
    top_largest: list[tuple[str, float]] | None = None,
) -> AnalysisResult:
    """Construct an :class:`AnalysisResult` with explicit counts.

    Args:
        total_items: Total media item count.
        total_size_gb: Total size across all media files.
        nfo_valid: Items with valid NFO.
        nfo_invalid: Items with invalid NFO.
        nfo_missing: Items with missing NFO.
        poster_present: Items with a poster.
        poster_missing: Items without a poster.
        seasons_missing_poster: Season rows without a poster.
        items_needing_rescrape: Rescrape candidate count.
        items_per_disk: Distribution of items across disks.
        items_per_category: Distribution of items across categories.
        size_per_disk_gb: Total size per disk in GB.
        top_largest: Top-largest item list as (title, size_gb) tuples.

    Returns:
        :class:`AnalysisResult` populated with the given counts.
    """
    return AnalysisResult(
        analyzed_at="2026-04-29T00:00:00+00:00",
        total_items=total_items,
        total_size_gb=total_size_gb,
        nfo=NfoStatusCounts(valid=nfo_valid, invalid=nfo_invalid, missing=nfo_missing),
        artwork=ArtworkCounts(poster_present=poster_present, poster_missing=poster_missing),
        seasons_missing_poster=seasons_missing_poster,
        items_needing_rescrape=items_needing_rescrape,
        items_per_disk=items_per_disk or {},
        items_per_category=items_per_category or {},
        size_per_disk_gb=size_per_disk_gb or {},
        top_largest=top_largest or [],
    )


# ---------------------------------------------------------------------------
# Suite 1 — generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """Tests for report generation — AnalysisResult is the SSOT."""

    def test_empty_report(self) -> None:
        """Report with no data should have zero counts."""
        report = generate_report(analysis_result=None, validation_data=None, recommendation_data=None)
        assert report.total_items == 0
        assert report.total_size_gb == 0.0

    def test_report_distribution_from_analysis_result(self) -> None:
        """Report aggregates disk / category distribution and sizes from AnalysisResult."""
        ar = _make_analysis_result(
            total_items=3,
            total_size_gb=20.5,
            items_per_disk={"Disk1": 2, "Disk2": 1},
            items_per_category={"films": 2, "series": 1},
            size_per_disk_gb={"Disk1": 5.5, "Disk2": 15.0},
            top_largest=[("Big TV Show", 15.0), ("Movie B", 3.5), ("Movie A", 2.0)],
        )
        report = generate_report(analysis_result=ar)
        assert report.total_items == 3
        assert report.total_size_gb == 20.5
        assert report.items_per_disk["Disk1"] == 2
        assert report.items_per_disk["Disk2"] == 1
        assert report.items_per_category["films"] == 2
        assert report.size_per_disk_gb["Disk1"] == 5.5
        assert report.top_largest[0][0] == "Big TV Show"

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

    def test_report_total_items_from_analysis_result(self) -> None:
        """total_items should come from AnalysisResult."""
        ar = _make_analysis_result(total_items=7)
        report = generate_report(analysis_result=ar)
        assert report.total_items == 7

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

    def test_report_uses_analysis_result_only_for_totals(self) -> None:
        """generate_report uses the supplied AnalysisResult for library totals."""
        conn = _make_conn()
        _seed_item(conn, title="Movie A", nfo_status="valid", artwork_json=_ARTWORK_POSTER)
        ar = analyze(conn)

        report = generate_report(analysis_result=ar)

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
        """Formatted report should include key sections when relevant data is present."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=100,
            total_size_gb=500.0,
            validation_valid=80,
            validation_issues=20,
            validation_errors={"nfo_present": 10, "nfo_valid": 10},
        )
        text = format_report_text(report)
        assert "RAPPORT DE SANTÉ" in text
        assert "VALIDATION" in text
        assert "ACTIONS SUGGÉRÉES" in text
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


# ---------------------------------------------------------------------------
# Suite 4 — generate_report extra branches
# ---------------------------------------------------------------------------


class TestGenerateReportExtras:
    """Tests for branches not covered by the base suite."""

    def test_scan_issues_populated_via_counter_most_common(self) -> None:
        """``scan_issues`` should be sorted by descending count via Counter.most_common()."""
        ar = _make_analysis_result(total_items=10)
        # AnalysisResult exposes scan_issues via dataclass field.
        ar.scan_issues = {"junk_files": 3, "actors_dir_present": 7}
        ar.actors_dir_count = 7

        report = generate_report(analysis_result=ar)
        # Most common first.
        keys = list(report.scan_issues.keys())
        assert keys[0] == "actors_dir_present"
        assert report.actors_dir_count == 7

    def test_disk_statuses_populates_disk_free_gb(self) -> None:
        """When ``disk_statuses`` is supplied, ``disk_free_gb`` is rounded by id."""

        class _FakeDiskCfg:
            def __init__(self, did: str) -> None:
                self.id = did

        class _FakeDiskStatus:
            def __init__(self, did: str, free: float) -> None:
                self.config = _FakeDiskCfg(did)
                self.free_space_gb = free

        statuses = [_FakeDiskStatus("disk1", 123.456), _FakeDiskStatus("disk2", 999.99)]
        report = generate_report(disk_statuses=statuses)
        assert report.disk_free_gb == {"disk1": 123.5, "disk2": 1000.0}

    def test_disk_statuses_missing_attributes_skipped(self) -> None:
        """Objects missing ``config``/``free_space_gb`` should be ignored, not raise."""

        class _Noop:
            pass

        report = generate_report(disk_statuses=[_Noop()])
        assert report.disk_free_gb == {}

    def test_rescrape_episodes_renamed_action(self) -> None:
        """``episodes_renamed`` action should bump rescrape_episodes_count."""
        rescrape_data = {
            "fixed_count": 1,
            "skipped_count": 0,
            "error_count": 0,
            "items": [{"actions_taken": ["episodes_renamed", "nfo_regenerated"]}],
        }
        report = generate_report(rescrape_data=rescrape_data)
        assert report.rescrape_episodes_count == 1
        assert report.rescrape_nfo_count == 1


# ---------------------------------------------------------------------------
# Suite 5 — format_report_text full sections
# ---------------------------------------------------------------------------


class TestFormatReportTextSections:
    """Exhaustive section-by-section coverage of ``format_report_text``."""

    def test_disks_section_rendered(self) -> None:
        """DISQUES section lists per-disk count, size, free space, and percentage."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=4,
            total_size_gb=100.0,
            items_per_disk={"disk1": 3, "disk2": 1},
            size_per_disk_gb={"disk1": 75.0, "disk2": 25.0},
            disk_free_gb={"disk1": 500.0, "disk2": 250.0},
        )
        text = format_report_text(report)
        assert "DISQUES" in text
        assert "disk1: 3 items" in text
        assert "500 GB libre" in text
        # Percentages: 3/4 = 75%, 1/4 = 25%.
        assert "[75%]" in text
        assert "[25%]" in text

    def test_categories_section_rendered(self) -> None:
        """CATÉGORIES section lists categories sorted by count desc."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=10,
            items_per_category={"films": 7, "series": 3},
        )
        text = format_report_text(report)
        assert "CATÉGORIES" in text
        # films appears before series (sorted descending by count).
        idx_films = text.index("films:")
        idx_series = text.index("series:")
        assert idx_films < idx_series

    def test_scan_section_rendered_with_fixes(self) -> None:
        """SCAN section enumerates issues + remediation commands."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=100,
            scan_issues={
                "actors_dir_present": 12,
                "junk_files": 5,
                "release_group_artifact": 2,
                "empty_subdir": 1,
            },
        )
        text = format_report_text(report)
        assert "1. SCAN" in text
        # Each issue type with explanation and fix.
        assert "actors_dir_present: 12" in text
        assert "library-clean --only actors --apply" in text
        # Cleanable summary should be sum of those that have fixes.
        assert "Nettoyable automatiquement: 20" in text
        assert "library-clean --apply" in text

    def test_validation_warnings_only_section(self) -> None:
        """Warnings-only validation should still render the warnings sub-block."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            validation_valid=10,
            validation_issues=2,
            validation_warnings={"artwork_landscape": 4},
        )
        text = format_report_text(report)
        assert "Avertissements" in text
        assert "artwork_landscape: 4" in text

    def test_validation_errors_with_fix_lines(self) -> None:
        """Validation errors with a known fix get a ``✓`` remediation line."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            validation_valid=10,
            validation_issues=2,
            validation_errors={"nfo_present": 1, "category": 1},
        )
        text = format_report_text(report)
        # ``nfo_present`` has a fix, ``category`` does not.
        assert "library-rescrape --only nfo" in text
        # Both errors listed.
        assert "nfo_present: 1" in text
        assert "category: 1" in text

    def test_analysis_section_rendered(self) -> None:
        """ANALYSE section shows codecs, audio profiles, and partial-coverage warning."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=200,
            analysis_item_count=100,
            analysis_file_count=120,
            codec_distribution={"h264": 80, "hevc": 40},
            audio_distribution={"vf": 60, "vostfr": 30, "multi": 20, "vo": 10, "weird": 5},
        )
        text = format_report_text(report)
        assert "3. ANALYSE" in text
        # Coverage 50% < 100 ⇒ partial-warning line.
        assert "library-analyze --incremental" in text
        assert "h264: 80 fichiers" in text
        # Audio labels resolved.
        assert "VF (français)" in text
        assert "VOSTFR" in text
        # Unknown profile falls back to its raw label.
        assert "weird:" in text or "weird " in text

    def test_recommendations_section_rendered(self) -> None:
        """RECOMMANDATIONS section emits priority counts + per-item details."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            recommendation_count=2,
            estimated_savings_gb=10.5,
            recommendations_by_priority={"high": 1, "medium": 1},
            recommendation_details=[
                {
                    "title": "Movie A",
                    "priority": "high",
                    "codec": "mpeg2",
                    "resolution": "1080p",
                    "size_gb": 8.0,
                    "audio_profile": "vf",
                    "reasons": ["rejected codec"],
                    "savings_gb": 5.0,
                },
                {
                    "title": "Movie B",
                    "priority": "medium",
                    "codec": "h264",
                    "resolution": "720p",
                    "size_gb": 5.0,
                    "audio_profile": "vo",
                    "reasons": ["upgrade resolution"],
                    "savings_gb": 5.5,
                },
            ],
        )
        text = format_report_text(report)
        assert "4. RECOMMANDATIONS" in text
        assert "Économie potentielle: ~10.5 GB" in text
        assert "Movie A" in text
        assert "rejected codec" in text
        assert "library-recommend --export csv" in text

    def test_top_largest_section_rendered(self) -> None:
        """TOP 20 section lists each item with rank and size."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            top_largest=[("Big A", 50.5), ("Big B", 30.1)],
        )
        text = format_report_text(report)
        assert "5. TOP 20" in text
        assert "Big A" in text
        assert "50.5 GB" in text

    def test_rescrape_section_full_lines(self) -> None:
        """RESCRAPE section emits every optional line when corresponding count > 0."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            rescrape_fixed=10,
            rescrape_skipped=5,
            rescrape_errors=2,
            rescrape_nfo_count=4,
            rescrape_artwork_count=3,
            rescrape_episodes_count=2,
        )
        text = format_report_text(report)
        assert "Épisodes renommés: 2" in text
        # Skipped warning line present.
        assert "items ignorés" in text
        assert "library-rescrape --interactive" in text

    def test_actions_section_full(self) -> None:
        """ACTIONS SUGGÉRÉES section lists every action the report can produce."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=100,
            scan_issues={"actors_dir_present": 5, "junk_files": 3},
            nfo_invalid_count=4,  # falls back when no validation errors
            poster_missing_count=2,
            analysis_item_count=50,  # less than total_items ⇒ ffprobe action
            recommendation_count=7,
        )
        text = format_report_text(report)
        # Every numbered/half-numbered action emitted.
        assert "Supprimer 5 dossiers .actors" in text
        assert "Supprimer 3 fichiers parasites" in text
        # Re-scrape uses nfo_invalid_count fallback when no validation_errors.
        assert "Re-scraper 4 items" in text
        assert "Récupérer l'artwork" in text
        assert "Compléter l'analyse ffprobe (50 items restants)" in text
        assert "Examiner 7 recommandations" in text
