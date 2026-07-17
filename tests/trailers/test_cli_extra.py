"""Additional CLI tests for personalscraper trailers — uncovered branches.

Targets the missing line ranges identified during coverage analysis:
  * 246-247, 251-257 — _resolve_category_token edge cases
  * 300-301         — _apply_filters disk loop AttributeError
  * 575             — audit season trailer_path_for_season branch
  * 622-623         — audit --deep ffprobe stdout ValueError fallback
  * 706-712         — purge orphan trailer detection
  * 716-724         — purge --disk filtering
  * 736-741         — purge actual file deletion + OSError
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_ORCH = "personalscraper.trailers.cli.TrailersOrchestrator"
_PATCH_SCANNER = "personalscraper.trailers.cli.Scanner"
_PATCH_OPEN_DB = "personalscraper.indexer.db.open_db"
_PATCH_STATE_STORE = "personalscraper.trailers.cli.TrailerStateStore"


def _fake_config(tmp_path: Path) -> MagicMock:
    """Build a minimal mock config for CLI tests.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        MagicMock configured for the trailers CLI.
    """
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.paths.staging_dir = tmp_path
    cfg.disks = []
    cfg.trailers.seasons.enabled = False
    cfg.trailers.library_check.movies = False
    cfg.trailers.library_check.tv_shows = True
    cfg.trailers.filters.allowed_extensions = {"mp4", "mkv", "webm"}
    # No torrent client configured (DESIGN D9): keep ``torrent.active`` falsey
    # so the boot fail-fast in _build_app_context does not trip.
    cfg.torrent.active = ""
    return cfg


class TestResolveCategoryToken:
    """Cover lines 246-247, 251-257 — _resolve_category_token branches."""

    def test_resolve_category_token_returns_raw_when_staging_dirs_missing(self, tmp_path: Path) -> None:
        """When config has no staging_dirs attribute, the raw token is returned.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.cli import _resolve_category_token

        cfg = MagicMock(spec=["disks"])  # no staging_dirs attr
        result = _resolve_category_token(cfg, "any-token")
        assert result == "any-token"

    def test_resolve_category_token_matches_by_file_type(self, tmp_path: Path) -> None:
        """A token matching staging_dirs[*].file_type resolves to the folder name.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.cli import _resolve_category_token

        cfg = MagicMock()
        entry = MagicMock()
        entry.name = "tvshows"
        entry.file_type = "tvshow"
        cfg.staging_dirs = [entry]

        with patch(
            "personalscraper.conf.staging.folder_name",
            return_value="002-TVSHOWS",
        ):
            # Match by file_type → resolves to folder_name return value.
            result = _resolve_category_token(cfg, "tvshow")
        assert result == "002-TVSHOWS"

    def test_resolve_category_token_no_match_returns_raw(self, tmp_path: Path) -> None:
        """When the token matches none of name/file_type/folder, returns raw input.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.cli import _resolve_category_token

        cfg = MagicMock()
        entry = MagicMock()
        entry.name = "tvshows"
        entry.file_type = "tvshow"
        cfg.staging_dirs = [entry]

        with patch(
            "personalscraper.conf.staging.folder_name",
            return_value="002-TVSHOWS",
        ):
            result = _resolve_category_token(cfg, "completely-unrelated")
        assert result == "completely-unrelated"


class TestApplyFiltersDiskAttributeError:
    """Cover lines 300-301 — config.disks raises AttributeError/TypeError."""

    def test_apply_filters_disk_attribute_error_no_filtering(self, tmp_path: Path) -> None:
        """When iterating config.disks raises, the disk filter is silently skipped.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.cli import _apply_filters
        from personalscraper.trailers.scanner import ScanItem

        # Build a config whose .disks attribute access raises AttributeError.
        cfg = MagicMock()
        type(cfg).disks = property(lambda self: (_ for _ in ()).throw(AttributeError("no disks")))

        item = ScanItem(
            path=tmp_path / "X (2020)",
            media_type="movie",
            title="X",
            year=2020,
            tmdb_id=None,
        )
        result = _apply_filters(
            [item],
            cfg,
            disk="Disk1",
            category=None,
            since_dt=None,
            level="both",
            season=None,
            limit=None,
        )
        # The disk filter was skipped: item survives.
        assert result == [item]


class TestAuditDeepStdoutValueError:
    """Cover lines 622-623 — ffprobe stdout that cannot be parsed as float."""

    def test_audit_deep_handles_non_numeric_ffprobe_output(self, tmp_path: Path) -> None:
        """A non-numeric duration string is treated as 0.0 → flagged unplayable (exit 2).

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        import subprocess

        from personalscraper.trailers.scanner import ScanItem

        show_dir = tmp_path / "ShowZ (2024)"
        show_dir.mkdir()
        trailer_file = show_dir / "ShowZ-trailer.mp4"
        trailer_file.write_bytes(b"x" * 200000)

        item = ScanItem(
            path=show_dir,
            media_type="tvshow",
            title="ShowZ",
            year=2024,
            tmdb_id=None,
        )

        bad_proc = subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout="N/A\n",  # not a float
            stderr="",
        )

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_SCANNER) as MockScanner,
            patch(_PATCH_OPEN_DB),
            patch("personalscraper.trailers.placement.trailer_path_for") as mock_tp,
            patch("personalscraper.trailers.cli.subprocess.run", return_value=bad_proc),
        ):
            MockScanner.return_value.scan_library_all.return_value = [item]
            mock_tp.return_value = trailer_file
            result = runner.invoke(app, ["trailers", "audit", "--deep"])
        # ValueError → duration_val=0.0 → unplayable issue → exit 2.
        assert result.exit_code == 2, result.output


class TestAuditSeasonTrailerPath:
    """Cover line 575 — audit uses trailer_path_for_season for season-level items."""

    def test_audit_season_item_uses_seasonal_path(self, tmp_path: Path) -> None:
        """A ScanItem with season_number=N goes through trailer_path_for_season.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.scanner import ScanItem

        show_dir = tmp_path / "ShowS (2020)"
        show_dir.mkdir()

        cfg = _fake_config(tmp_path)
        cfg.trailers.seasons.enabled = True

        item = ScanItem(
            path=show_dir,
            media_type="tvshow",
            title="ShowS",
            year=2020,
            tmdb_id=None,
            season_number=1,
        )

        # seasonal trailer file does not exist → "missing" issue → exit 2.
        missing_seasonal = show_dir / "Trailers" / "Season 1-trailer.mp4"

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCANNER) as MockScanner,
            patch(_PATCH_OPEN_DB),
            patch("personalscraper.trailers.placement.trailer_path_for_season") as mock_tps,
        ):
            MockScanner.return_value.scan_library_all.return_value = [item]
            mock_tps.return_value = missing_seasonal
            result = runner.invoke(app, ["trailers", "audit"])

        assert result.exit_code == 2, result.output
        mock_tps.assert_called()


class TestPurgeOrphanDetection:
    """Cover lines 706-712 — orphan trailer path detection from state entries."""

    def test_purge_dry_run_lists_orphan_trailers(self, tmp_path: Path) -> None:
        """A state entry whose media_path is missing AND trailer_path exists → orphan.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.state import TrailerState, TrailerStatus

        # Trailer file present, but media dir does not exist → orphan candidate.
        orphan_trailer = tmp_path / "Trailers" / "orphan-trailer.mp4"
        orphan_trailer.parent.mkdir(parents=True)
        orphan_trailer.write_bytes(b"x" * 200000)

        # Entry with non-existent media_path
        entry_orphan = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(tmp_path / "missing-media-dir"),
            trailer_path=str(orphan_trailer),
        )
        # Entry with existent media_path → NOT orphan
        live_dir = tmp_path / "live-media"
        live_dir.mkdir()
        entry_alive = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(live_dir),
            trailer_path=str(orphan_trailer),
        )

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_STATE_STORE) as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {
                "orphan": entry_orphan,
                "alive": entry_alive,
            }
            result = runner.invoke(app, ["trailers", "purge", "--dry-run"])

        assert result.exit_code == 0, result.output
        # Output mentions exactly 1 orphan.
        assert "1 orphan" in result.output


class TestPurgeDiskFilter:
    """Cover lines 716-724 — --disk filter applied to orphan paths."""

    def test_purge_disk_filter_drops_paths_outside_disk(self, tmp_path: Path) -> None:
        """Orphan trailers outside the --disk path are filtered out.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.state import TrailerState, TrailerStatus

        # Two disks: Disk1 under tmp_path/disk1, Disk2 outside this prefix.
        disk1_dir = tmp_path / "disk1"
        disk1_dir.mkdir()
        disk2_dir = tmp_path / "disk2"
        disk2_dir.mkdir()

        # Orphan trailer ON Disk1.
        orphan_d1 = disk1_dir / "orphan_d1-trailer.mp4"
        orphan_d1.write_bytes(b"x" * 200000)
        # Orphan trailer ON Disk2.
        orphan_d2 = disk2_dir / "orphan_d2-trailer.mp4"
        orphan_d2.write_bytes(b"x" * 200000)

        cfg = _fake_config(tmp_path)
        d1 = MagicMock()
        d1.id = "Disk1"
        d1.path = str(disk1_dir)
        d2 = MagicMock()
        d2.id = "Disk2"
        d2.path = str(disk2_dir)
        cfg.disks = [d1, d2]

        e1 = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(tmp_path / "missing1"),
            trailer_path=str(orphan_d1),
        )
        e2 = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(tmp_path / "missing2"),
            trailer_path=str(orphan_d2),
        )

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_STATE_STORE) as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {"e1": e1, "e2": e2}
            result = runner.invoke(app, ["trailers", "purge", "--dry-run", "--disk", "Disk1"])

        assert result.exit_code == 0, result.output
        # Only the Disk1 orphan should be reported.
        assert "1 orphan" in result.output


class TestPurgeRealDeletion:
    """Cover lines 736-741 — actual unlink success and OSError logging."""

    def test_purge_unlinks_orphan_trailers(self, tmp_path: Path) -> None:
        """Real (non-dry-run) purge calls unlink on orphan trailer files.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.state import TrailerState, TrailerStatus

        orphan = tmp_path / "orphan-trailer.mp4"
        orphan.write_bytes(b"x" * 200000)

        entry = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(tmp_path / "missing"),
            trailer_path=str(orphan),
        )

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_STATE_STORE) as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {"e": entry}
            result = runner.invoke(app, ["trailers", "purge"])

        assert result.exit_code == 0, result.output
        assert not orphan.exists(), "orphan trailer must have been deleted"
        assert "Purged 1" in result.output

    def test_purge_oserror_during_unlink_logs_warning_and_continues(self, tmp_path: Path) -> None:
        """OSError on unlink does not abort the run; logs and proceeds.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from personalscraper.trailers.state import TrailerState, TrailerStatus

        orphan = tmp_path / "orphan-trailer.mp4"
        orphan.write_bytes(b"x" * 200000)

        entry = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(tmp_path / "missing"),
            trailer_path=str(orphan),
        )

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_STATE_STORE) as MockStore,
            patch.object(Path, "unlink", side_effect=OSError("permission denied")),
        ):
            MockStore.return_value.all_entries.return_value = {"e": entry}
            result = runner.invoke(app, ["trailers", "purge"])

        # CLI still exits cleanly even though no file was deleted.
        assert result.exit_code == 0, result.output
        assert "Purged 0" in result.output
