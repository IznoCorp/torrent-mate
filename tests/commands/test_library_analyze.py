"""Tests for the library-* analysis Typer commands.

Covers ``library-analyze``, ``library-recommend``, ``library-rescrape``,
and ``library-report``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.library.models import (
    LibraryAnalysisResult,
    LibraryRecommendationResult,
    LibraryRescrapeResult,
    LibraryValidationResult,
)

runner = CliRunner()


# Helpers ────────────────────────────────────────────────────────────────────


def _empty_analysis() -> LibraryAnalysisResult:
    return LibraryAnalysisResult(
        analyzed_at="2026-04-15T12:00:00",
        disk_filter=None,
        category_filter=None,
        item_count=0,
        file_count=0,
        items=[],
    )


def _empty_recommend() -> LibraryRecommendationResult:
    return LibraryRecommendationResult(
        generated_at="2026-04-15T12:00:00",
        total_recommendations=0,
        estimated_total_savings_gb=0.0,
        items=[],
    )


# ── library-analyze ──────────────────────────────────────────────────────────


class TestLibraryAnalyze:
    """Tests for the library-analyze Typer command."""

    def test_runs_ffprobe_path(self) -> None:
        """Default invocation runs analyze_library and prints summary."""
        with patch(
            "personalscraper.library.analyzer.analyze_library",
            return_value=_empty_analysis(),
        ) as mock_an:
            result = runner.invoke(app, ["library-analyze"])
        assert result.exit_code == 0
        mock_an.assert_called_once()
        assert "Analysis complete" in result.output

    def test_from_index_path(self) -> None:
        """--from-index uses analyze_from_index and opens the indexer DB."""
        with (
            patch(
                "personalscraper.library.analyzer.analyze_from_index",
                return_value=_empty_analysis(),
            ) as mock_an,
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.indexer.db.apply_migrations"),
        ):
            result = runner.invoke(app, ["library-analyze", "--from-index"])
        assert result.exit_code == 0
        mock_an.assert_called_once()
        assert "from index" in result.output

    def test_with_filters_passes_kwargs(self) -> None:
        """--disk / --max-items reach the analyze_library call."""
        with patch(
            "personalscraper.library.analyzer.analyze_library",
            return_value=_empty_analysis(),
        ) as mock_an:
            result = runner.invoke(
                app,
                ["library-analyze", "--disk", "drive_a", "--max-items", "5"],
            )
        assert result.exit_code == 0
        _, kwargs = mock_an.call_args
        assert kwargs["disk_filter"] == "drive_a"
        assert kwargs["max_items"] == 5

    def test_codec_audio_aggregation(self) -> None:
        """Codec / audio profile counts appear in the summary."""
        from personalscraper.library.models import (
            LibraryAnalysisItem,
            MediaFileAnalysis,
            VideoInfo,
        )

        video = VideoInfo(codec="h264", width=1920, height=1080, bitrate_kbps=None, hdr=False, hdr_type=None)
        mfa = MediaFileAnalysis(
            path="/x/f.mkv",
            size_gb=1.0,
            duration_seconds=None,
            video=video,
            audio_tracks=[],
            subtitle_tracks=[],
            audio_profile="stereo",
        )
        item = LibraryAnalysisItem(
            path="/x",
            disk="d",
            category="c",
            media_type="movie",
            title="t",
            year=None,
            files=[mfa],
        )
        result = LibraryAnalysisResult(
            analyzed_at="2026",
            disk_filter=None,
            category_filter=None,
            item_count=1,
            file_count=1,
            items=[item],
        )
        with patch("personalscraper.library.analyzer.analyze_library", return_value=result):
            r = runner.invoke(app, ["library-analyze"])
        assert r.exit_code == 0
        assert "Codecs" in r.output
        assert "h264" in r.output
        assert "Audio profiles" in r.output
        assert "stereo" in r.output


# ── library-recommend ────────────────────────────────────────────────────────


class TestLibraryRecommend:
    """Tests for the library-recommend Typer command."""

    def test_default_path(self, tmp_path) -> None:
        """Default run produces a recommendations file and prints summary."""
        with (
            patch(
                "personalscraper.library.analyzer.analyze_library",
                return_value=_empty_analysis(),
            ),
            patch(
                "personalscraper.library.recommender.generate_recommendations",
                return_value=_empty_recommend(),
            ),
            patch("personalscraper.library.models.write_json") as mock_write,
        ):
            result = runner.invoke(app, ["library-recommend"])
        assert result.exit_code == 0
        mock_write.assert_called_once()
        assert "Recommendations" in result.output

    def test_invalid_sort_errors(self) -> None:
        """--sort with bad value exits 1."""
        result = runner.invoke(app, ["library-recommend", "--sort", "bogus"])
        assert result.exit_code == 1
        assert "Invalid --sort" in result.output

    def test_from_index_path(self, tmp_path) -> None:
        """--from-index uses analyze_from_index."""
        with (
            patch(
                "personalscraper.library.analyzer.analyze_from_index",
                return_value=_empty_analysis(),
            ) as mock_an,
            patch(
                "personalscraper.library.recommender.generate_recommendations",
                return_value=_empty_recommend(),
            ),
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.indexer.db.apply_migrations"),
        ):
            result = runner.invoke(app, ["library-recommend", "--from-index"])
        assert result.exit_code == 0
        mock_an.assert_called_once()

    def test_export_csv(self, tmp_path, test_config) -> None:
        """--export csv writes a CSV alongside the JSON output."""
        # data_dir must exist for the CSV write.
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        from personalscraper.library.models import (
            CurrentState,
            Recommendation,
            TargetState,
        )

        rec = Recommendation(
            path="/x",
            title="Movie X",
            media_type="movie",
            disk="d",
            category="c",
            tmdb_id=None,
            imdb_id=None,
            current=CurrentState(
                codec="h264",
                resolution="1080p",
                size_gb=10.0,
                audio_profile="stereo",
            ),
            target=TargetState(codec="hevc", resolution=None, max_size_gb=None),
            estimated_savings_gb=5.0,
            priority="high",
            reasons=["bigger than target"],
        )
        rec_result = LibraryRecommendationResult(
            generated_at="2026",
            total_recommendations=1,
            estimated_total_savings_gb=5.0,
            items=[rec],
        )

        with (
            patch(
                "personalscraper.library.analyzer.analyze_library",
                return_value=_empty_analysis(),
            ),
            patch(
                "personalscraper.library.recommender.generate_recommendations",
                return_value=rec_result,
            ),
            patch("personalscraper.library.models.write_json"),
        ):
            result = runner.invoke(app, ["library-recommend", "--export", "csv", "--sort", "size"])
        assert result.exit_code == 0
        assert "CSV exported" in result.output


# ── library-rescrape ─────────────────────────────────────────────────────────


class TestLibraryRescrape:
    """Tests for the library-rescrape Typer command."""

    def test_dry_run(self, tmp_path) -> None:
        """--dry-run does not acquire the lock and reports DRY-RUN mode."""
        rresult = LibraryRescrapeResult(
            rescraped_at="2026",
            disk_filter=None,
            category_filter=None,
            only_filter=None,
            dry_run=True,
            fixed_count=0,
            skipped_count=0,
            error_count=0,
        )
        with (
            patch(
                "personalscraper.library.rescraper.rescrape_library",
                return_value=rresult,
            ),
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.cli.acquire_lock") as mock_acquire,
        ):
            result = runner.invoke(app, ["library-rescrape", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        mock_acquire.assert_not_called()

    def test_invalid_only_errors(self) -> None:
        """--only with invalid value exits 1."""
        result = runner.invoke(app, ["library-rescrape", "--only", "bogus"])
        assert result.exit_code == 1
        assert "Invalid --only" in result.output

    def test_live_acquires_lock(self, tmp_path) -> None:
        """A non dry-run invocation acquires and releases the pipeline lock."""
        rresult = LibraryRescrapeResult(
            rescraped_at="2026",
            disk_filter=None,
            category_filter=None,
            only_filter=None,
            dry_run=False,
            fixed_count=2,
            skipped_count=1,
            error_count=0,
        )
        with (
            patch(
                "personalscraper.library.rescraper.rescrape_library",
                return_value=rresult,
            ),
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.cli.acquire_lock", return_value=True) as mock_acquire,
            patch("personalscraper.cli.release_lock") as mock_release,
        ):
            result = runner.invoke(app, ["library-rescrape"])
        assert result.exit_code == 0
        mock_acquire.assert_called_once()
        mock_release.assert_called_once()

    def test_live_lock_blocked(self) -> None:
        """A non dry-run invocation exits 1 when the lock is held."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["library-rescrape"])
        assert result.exit_code == 1
        assert "Another instance" in result.output


# ── library-report ───────────────────────────────────────────────────────────


class TestLibraryReport:
    """Tests for the library-report Typer command."""

    def test_no_data_exits_1(self) -> None:
        """Without any library JSON or DB, command exits 1."""
        with patch("pathlib.Path.exists", return_value=False):
            result = runner.invoke(app, ["library-report"])
        assert result.exit_code == 1
        assert "No library data" in result.output

    def test_text_format(self, tmp_path) -> None:
        """Text format prints a formatted report."""
        from personalscraper.library.analyzer import AnalysisResult

        analysis = AnalysisResult(total_items=1, total_size_gb=1.0)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.library.analyzer.analyze", return_value=analysis),
            patch("personalscraper.library.models.read_json", return_value=None),
            patch(
                "personalscraper.dispatch.disk_scanner.get_disk_status",
                return_value=MagicMock(),
            ),
            patch(
                "personalscraper.library.reporter.generate_report",
                return_value=MagicMock(),
            ),
            patch(
                "personalscraper.library.reporter.format_report_text",
                return_value="LIBRARY REPORT",
            ),
        ):
            result = runner.invoke(app, ["library-report"])
        assert result.exit_code == 0
        assert "LIBRARY REPORT" in result.output

    def test_json_format(self, tmp_path) -> None:
        """JSON format calls write_json and prints output path."""
        from personalscraper.library.analyzer import AnalysisResult

        analysis = AnalysisResult(total_items=0, total_size_gb=0.0)
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.library.analyzer.analyze", return_value=analysis),
            patch("personalscraper.library.models.read_json", return_value=None),
            patch(
                "personalscraper.dispatch.disk_scanner.get_disk_status",
                return_value=MagicMock(),
            ),
            patch(
                "personalscraper.library.reporter.generate_report",
                return_value=MagicMock(),
            ),
            patch("personalscraper.library.models.write_json") as mock_write,
        ):
            result = runner.invoke(app, ["library-report", "--format", "json"])
        assert result.exit_code == 0
        mock_write.assert_called_once()
        # Console output may wrap the path across lines; collapse whitespace.
        flat = result.output.replace("\n", "")
        assert "library_report" in flat

    def test_corrupted_supplementary_data(self, tmp_path) -> None:
        """A corrupt supplementary JSON triggers a warning, not a crash."""
        from personalscraper.library.analyzer import AnalysisResult

        analysis = AnalysisResult(total_items=0, total_size_gb=0.0)

        def _raise(*a, **kw):
            raise ValueError("corrupt JSON")

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.library.analyzer.analyze", return_value=analysis),
            patch("personalscraper.library.models.read_json", side_effect=_raise),
            patch(
                "personalscraper.dispatch.disk_scanner.get_disk_status",
                return_value=MagicMock(),
            ),
            patch(
                "personalscraper.library.reporter.generate_report",
                return_value=MagicMock(),
            ),
            patch(
                "personalscraper.library.reporter.format_report_text",
                return_value="REPORT",
            ),
        ):
            result = runner.invoke(app, ["library-report"])
        assert result.exit_code == 0
        assert "corrupted" in result.output

    def test_indexer_query_failure(self, tmp_path) -> None:
        """A failing indexer DB query triggers a warning, not a crash."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "personalscraper.indexer.db.open_db",
                side_effect=RuntimeError("db boom"),
            ),
            patch(
                "personalscraper.library.models.read_json",
                return_value={"x": 1},
            ),
            patch(
                "personalscraper.dispatch.disk_scanner.get_disk_status",
                return_value=MagicMock(),
            ),
            patch(
                "personalscraper.library.reporter.generate_report",
                return_value=MagicMock(),
            ),
            patch(
                "personalscraper.library.reporter.format_report_text",
                return_value="REPORT",
            ),
        ):
            result = runner.invoke(app, ["library-report"])
        assert result.exit_code == 0
        assert "indexer DB query failed" in result.output


# ── unknown category alias error path (covers cli_helpers._resolve_category) ──


class TestUnknownCategory:
    """Tests for the --category error path in _resolve_category."""

    def test_unknown_category_exits_2(self) -> None:
        """Unknown --category value triggers _resolve_category error path (exit 2)."""
        # Use library-validate (also routes through _resolve_category) to
        # exercise the unknown-category branch in cli_helpers.
        result = runner.invoke(
            app,
            ["library-validate", "--category", "totally_bogus_alias"],
        )
        assert result.exit_code == 2
        assert "Unknown category" in result.output


# Suppress unused imports warning for fixtures referenced only via decorators.
_ = (LibraryValidationResult,)
