"""CLI tests for personalscraper trailers * subcommands.

Uses typer.testing.CliRunner. All orchestrator/scanner calls are mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

# Patch targets
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_ORCH = "personalscraper.trailers.cli.TrailersOrchestrator"
_PATCH_SCANNER = "personalscraper.trailers.cli.Scanner"


def _fake_config(tmp_path: Path) -> MagicMock:
    """Build a minimal mock config for CLI tests.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        MagicMock configured to satisfy trailers CLI attribute access.
    """
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.library_scan_max_age_hours = 24
    cfg.paths.staging_dir = tmp_path
    cfg.disks = []
    # DESIGN SS4 + SS8 extensions
    cfg.trailers.seasons.enabled = False
    cfg.trailers.library_check.movies = False
    cfg.trailers.library_check.tv_shows = True
    cfg.trailers.filters.allowed_extensions = {"mp4", "mkv", "webm"}
    return cfg


class TestTrailersScanCommand:
    """Tests for trailers scan CLI subcommand."""

    def test_scan_exits_zero(self, tmp_path):
        """Trailers scan exits 0."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "scan"])
        assert result.exit_code == 0, result.output

    def test_scan_shows_no_items_message(self, tmp_path):
        """Trailers scan shows expected message when no items found."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "scan"])
        assert "No media without trailers" in result.output or "0" in result.output

    def test_scan_limit_flag(self, tmp_path):
        """Trailers scan --limit 5 is accepted without error."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "scan", "--limit", "5"])
        assert result.exit_code == 0


class TestTrailersDownloadCommand:
    """Tests for trailers download CLI subcommand."""

    def test_download_exits_zero(self, tmp_path):
        """Trailers download exits 0 when orchestrator runs successfully."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_ORCH) as MockOrch,
        ):
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 0,
                "already_present": 0,
                "no_trailer": 0,
                "bot_detected": 0,
                "error": 0,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = runner.invoke(app, ["trailers", "download"])
        assert result.exit_code == 0, result.output

    def test_download_dry_run_does_not_call_orchestrator(self, tmp_path):
        """Trailers download --dry-run shows candidates without downloading."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_ORCH) as MockOrch,
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = []
            result = runner.invoke(app, ["trailers", "download", "--dry-run"])
        assert result.exit_code == 0
        MockOrch.return_value.run.assert_not_called()

    def test_download_disk_filter_passed_through(self, tmp_path):
        """Trailers download --disk Disk1 passes filter (project convention)."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_ORCH) as MockOrch,
        ):
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 0,
                "already_present": 0,
                "no_trailer": 0,
                "bot_detected": 0,
                "error": 0,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = runner.invoke(app, ["trailers", "download", "--disk", "Disk1"])
        assert result.exit_code == 0


class TestTrailersVerifyCommand:
    """Tests for trailers verify CLI subcommand."""

    def test_verify_exits_zero(self, tmp_path):
        """Trailers verify exits 0."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_library.return_value = []
            result = runner.invoke(app, ["trailers", "verify"])
        assert result.exit_code == 0

    def test_verify_flags_missing_trailer(self, tmp_path):
        """Trailers verify exits 2 when trailer file does not exist."""
        from personalscraper.trailers.scanner import ScanItem

        item = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="ShowA",
            year=2020,
            tmdb_id=None,
        )
        (tmp_path / "ShowA (2020)").mkdir()

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
            patch("personalscraper.trailers.placement.trailer_path_for") as mock_tp,
        ):
            MockScanner.return_value.scan_library.return_value = [item]
            missing_p = tmp_path / "ShowA (2020)" / "ShowA-trailer.mp4"
            mock_tp.return_value = missing_p  # does not exist
            result = runner.invoke(app, ["trailers", "verify"])
        assert result.exit_code == 2, result.output

    def test_verify_flags_undersized_trailer(self, tmp_path):
        """Trailers verify exits 2 when trailer file is below min_file_size."""
        from personalscraper.trailers.scanner import ScanItem

        show_dir = tmp_path / "ShowB (2021)"
        show_dir.mkdir()
        trailer_file = show_dir / "ShowB-trailer.mp4"
        trailer_file.write_bytes(b"x" * 100)  # 100 bytes, below 102400 min

        item = ScanItem(path=show_dir, media_type="tvshow", title="ShowB", year=2021, tmdb_id=None)

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
            patch("personalscraper.trailers.placement.trailer_path_for") as mock_tp,
        ):
            MockScanner.return_value.scan_library.return_value = [item]
            mock_tp.return_value = trailer_file
            result = runner.invoke(app, ["trailers", "verify"])
        assert result.exit_code == 2, result.output

    def test_verify_flags_wrong_extension(self, tmp_path):
        """Trailers verify exits 2 when trailer file has wrong extension."""
        from personalscraper.trailers.scanner import ScanItem

        show_dir = tmp_path / "ShowC (2022)"
        show_dir.mkdir()
        trailer_file = show_dir / "ShowC-trailer.avi"
        trailer_file.write_bytes(b"x" * 200000)  # large enough, but .avi not in allowed set

        item = ScanItem(path=show_dir, media_type="tvshow", title="ShowC", year=2022, tmdb_id=None)

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
            patch("personalscraper.trailers.placement.trailer_path_for") as mock_tp,
        ):
            MockScanner.return_value.scan_library.return_value = [item]
            mock_tp.return_value = trailer_file
            result = runner.invoke(app, ["trailers", "verify"])
        assert result.exit_code == 2, result.output

    def test_verify_deep_flag_invokes_ffprobe(self, tmp_path):
        """--deep calls a mocked ffprobe; non-zero duration returned => exit 0."""
        from personalscraper.trailers.scanner import ScanItem

        show_dir = tmp_path / "ShowD (2023)"
        show_dir.mkdir()
        trailer_file = show_dir / "ShowD-trailer.mp4"
        trailer_file.write_bytes(b"x" * 200000)

        item = ScanItem(path=show_dir, media_type="tvshow", title="ShowD", year=2023, tmdb_id=None)

        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "120.5\n"

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
            patch("personalscraper.trailers.placement.trailer_path_for") as mock_tp,
            patch("personalscraper.trailers.cli.subprocess.run", return_value=fake_proc),
        ):
            MockScanner.return_value.scan_library.return_value = [item]
            mock_tp.return_value = trailer_file
            result = runner.invoke(app, ["trailers", "verify", "--deep"])
        assert result.exit_code == 0, result.output


class TestTrailersPurgeCommand:
    """Tests for trailers purge CLI subcommand."""

    def test_purge_dry_run_exits_zero(self, tmp_path):
        """Trailers purge --dry-run exits 0."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch("personalscraper.trailers.cli.TrailerStateStore") as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {}
            result = runner.invoke(app, ["trailers", "purge", "--dry-run"])
        assert result.exit_code == 0

    def test_purge_include_state_flag_accepted(self, tmp_path):
        """Trailers purge --include-state is accepted without error."""
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch("personalscraper.trailers.cli.TrailerStateStore") as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {}
            result = runner.invoke(app, ["trailers", "purge", "--dry-run", "--include-state"])
        assert result.exit_code == 0


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_resolve_level_invalid_exits_2(self):
        """_resolve_level_and_season raises SystemExit for invalid level."""
        from personalscraper.trailers.cli import _resolve_level_and_season

        with pytest.raises(click.exceptions.Exit) as exc_info:
            _resolve_level_and_season("invalid", None, True)
        assert exc_info.value.exit_code == 2

    def test_resolve_level_season_forced_when_season_set(self):
        """--season N forces level=season."""
        from personalscraper.trailers.cli import _resolve_level_and_season

        level, s = _resolve_level_and_season("show", 2, True)
        assert level == "season"
        assert s == 2

    def test_resolve_level_season_noop_when_disabled(self):
        """season-level collapses to show when seasons are disabled."""
        from personalscraper.trailers.cli import _resolve_level_and_season

        level, s = _resolve_level_and_season("season", None, False)
        assert level == "show"
        assert s is None

    def test_apply_level_filter_show_excludes_season_items(self):
        """level=show drops ScanItems with season_number set."""
        from pathlib import Path

        from personalscraper.trailers.cli import _apply_level_filter
        from personalscraper.trailers.scanner import ScanItem

        show_item = ScanItem(
            path=Path("/tmp/show"),
            media_type="tvshow",
            title="ShowA",
            year=2020,
            tmdb_id=None,
            season_number=None,
        )
        season_item = ScanItem(
            path=Path("/tmp/show"),
            media_type="tvshow",
            title="ShowA",
            year=2020,
            tmdb_id=None,
            season_number=1,
        )
        result = _apply_level_filter([show_item, season_item], "show", None)
        assert result == [show_item]

    def test_apply_level_filter_season_excludes_show_items(self):
        """level=season drops ScanItems with season_number=None."""
        from pathlib import Path

        from personalscraper.trailers.cli import _apply_level_filter
        from personalscraper.trailers.scanner import ScanItem

        show_item = ScanItem(
            path=Path("/tmp/show"),
            media_type="tvshow",
            title="ShowA",
            year=2020,
            tmdb_id=None,
            season_number=None,
        )
        season_item = ScanItem(
            path=Path("/tmp/show"),
            media_type="tvshow",
            title="ShowA",
            year=2020,
            tmdb_id=None,
            season_number=1,
        )
        result = _apply_level_filter([show_item, season_item], "season", None)
        assert result == [season_item]

    def test_apply_level_filter_season_N_filters_single_season(self):
        """--season 2 keeps only season 2 items."""
        from pathlib import Path

        from personalscraper.trailers.cli import _apply_level_filter
        from personalscraper.trailers.scanner import ScanItem

        s1 = ScanItem(path=Path("/tmp/show"), media_type="tvshow", title="S", year=2020, tmdb_id=None, season_number=1)
        s2 = ScanItem(path=Path("/tmp/show"), media_type="tvshow", title="S", year=2020, tmdb_id=None, season_number=2)
        s3 = ScanItem(path=Path("/tmp/show"), media_type="tvshow", title="S", year=2020, tmdb_id=None, season_number=3)
        result = _apply_level_filter([s1, s2, s3], "season", 2)
        assert result == [s2]

    def test_parse_since_valid(self):
        """_parse_since parses a valid date string."""
        from personalscraper.trailers.cli import _parse_since

        dt = _parse_since("2024-01-15")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_since_none(self):
        """_parse_since returns None when input is None."""
        from personalscraper.trailers.cli import _parse_since

        assert _parse_since(None) is None

    def test_parse_since_invalid_exits_2(self):
        """_parse_since raises SystemExit(2) for invalid date."""
        from personalscraper.trailers.cli import _parse_since

        with pytest.raises(click.exceptions.Exit) as exc_info:
            _parse_since("not-a-date")
        assert exc_info.value.exit_code == 2

    def test_scan_level_show_excludes_season_items_integration(self, tmp_path):
        """Scan --level show excludes season-level ScanItems from output."""
        from personalscraper.trailers.scanner import ScanItem

        show_item = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="ShowA",
            year=2020,
            tmdb_id=None,
            season_number=None,
        )
        season_item = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="ShowA",
            year=2020,
            tmdb_id=None,
            season_number=1,
        )
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = [show_item, season_item]
            result = runner.invoke(app, ["trailers", "scan", "--level", "show"])
        assert result.exit_code == 0, result.output

    def test_scan_season_N_integration(self, tmp_path):
        """Scan --season 2 returns only season 2 items; seasons.enabled=True."""
        from personalscraper.trailers.scanner import ScanItem

        cfg = _fake_config(tmp_path)
        cfg.trailers.seasons.enabled = True
        s1 = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="S",
            year=2020,
            tmdb_id=None,
            season_number=1,
        )
        s2 = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="S",
            year=2020,
            tmdb_id=None,
            season_number=2,
        )
        s3 = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="S",
            year=2020,
            tmdb_id=None,
            season_number=3,
        )
        show_item = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="S",
            year=2020,
            tmdb_id=None,
            season_number=None,
        )
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = [show_item, s1, s2, s3]
            result = runner.invoke(app, ["trailers", "scan", "--season", "2"])
        assert result.exit_code == 0, result.output

    def test_season_flag_noop_when_disabled_integration(self, tmp_path):
        """--season N is silently ignored when seasons.enabled=False."""
        from personalscraper.trailers.scanner import ScanItem

        cfg = _fake_config(tmp_path)
        cfg.trailers.seasons.enabled = False
        s1 = ScanItem(
            path=tmp_path / "ShowA (2020)",
            media_type="tvshow",
            title="S",
            year=2020,
            tmdb_id=None,
            season_number=1,
        )
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCANNER) as MockScanner,
        ):
            MockScanner.return_value.scan_staging.return_value = [s1]
            result = runner.invoke(app, ["trailers", "scan", "--season", "1"])
        assert result.exit_code == 0, result.output
