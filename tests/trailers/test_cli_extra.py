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
    """Orphan detection from LEGACY ledger entries (kept as HINTS post-P6.4).

    Historical note: these tests pin the ledger-driven orphan path, which used
    to be the ONLY source purge consulted. Since P6.4 a successful download
    CLEARS its ledger entry, so the ledger can no longer find orphans of new
    downloads — the FILESYSTEM is now the primary truth (see
    ``TestPurgeFilesystemTruth``). The ledger is still honoured as a HINT for
    pre-P6.4 ``DOWNLOADED`` rows, which is what these tests exercise.
    """

    def test_purge_dry_run_lists_orphan_trailers(self, tmp_path: Path) -> None:
        """A legacy ledger entry (media_path gone, trailer_path present) → orphan hint.

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


class TestPurgeFilesystemTruth:
    """FS-truth orphan detection (P6.4): the ledger no longer records downloads.

    A trailer whose download was never ledger-recorded (or whose row was cleared
    on success) must STILL be found — from the filesystem, cross-referenced
    against the indexer item set. A trailer under a LIVE (indexed) media dir must
    be spared; a trailer under an unindexed media dir is an orphan.
    """

    def test_purge_finds_fs_orphan_never_ledger_recorded(self, tmp_path: Path) -> None:
        """An orphan trailer absent from the ledger IS found via FS truth.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from types import SimpleNamespace

        # A storage disk with a category holding two movie dirs.
        disk_dir = tmp_path / "Disk1"
        cat = disk_dir / "001-MOVIES"
        cat.mkdir(parents=True)

        # LIVE movie (indexed) — its trailer must be SPARED.
        live_movie = cat / "Live Movie (2020)"
        live_movie.mkdir()
        (live_movie / "Live Movie (2020)-trailer.mp4").write_bytes(b"x" * 200000)

        # ORPHAN movie (NOT indexed) — download succeeded so the ledger row was
        # cleared (P6.4). Its trailer must be found on FS truth alone.
        orphan_movie = cat / "Ghost Movie (1999)"
        orphan_movie.mkdir()
        orphan_trailer = orphan_movie / "Ghost Movie (1999)-trailer.mp4"
        orphan_trailer.write_bytes(b"x" * 200000)

        cfg = _fake_config(tmp_path)
        cfg.indexer.db_path = tmp_path / "library.db"
        cfg.indexer.db_path.write_bytes(b"")  # exists → real db_path path taken
        disk = MagicMock()
        disk.id = "Disk1"
        disk.path = str(disk_dir)
        disk.categories = ["movies"]
        cfg.disks = [disk]
        cfg.category.side_effect = lambda cid: SimpleNamespace(folder_name="001-MOVIES")
        # Empty staging root (no orphans there).
        staging = tmp_path / "staging"
        staging.mkdir()
        cfg.paths.staging_dir = staging

        # The indexer knows ONLY the live movie dir.
        live_item = SimpleNamespace(path=live_movie)

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCANNER) as MockScanner,
            patch(_PATCH_OPEN_DB),
            patch(_PATCH_STATE_STORE) as MockStore,
        ):
            MockScanner.return_value.scan_library_all.return_value = [live_item]
            MockStore.return_value.all_entries.return_value = {}  # EMPTY ledger
            result = runner.invoke(app, ["trailers", "purge", "--dry-run"])

        assert result.exit_code == 0, result.output
        # Exactly one orphan — the unindexed Ghost Movie trailer; the live one spared.
        assert "1 orphan" in result.output
        assert "Ghost Movie (1999)-trailer.mp4" in result.output
        assert "Live Movie (2020)-trailer.mp4" not in result.output

    def test_purge_keeps_present_media_missing_from_index_and_reports_gap(self, tmp_path: Path) -> None:
        """Present media with a real video, absent from the index, is not an orphan.

        Regression (Finding A): a PRESENT media dir (real video + trailer) the
        index does not know is NOT deleted — its trailer is kept and the dir is
        reported as an index gap to re-index.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from types import SimpleNamespace

        disk_dir = tmp_path / "Disk1"
        cat = disk_dir / "001-MOVIES"
        cat.mkdir(parents=True)

        # PRESENT media: a real movie video AND its trailer, but the index knows
        # nothing about it (e.g. MediaElch-managed / not yet dispatched).
        movie = cat / "Real Movie (2021)"
        movie.mkdir()
        (movie / "Real Movie (2021).mkv").write_bytes(b"x" * 200000)  # real media video
        trailer = movie / "Real Movie (2021)-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)

        cfg = _fake_config(tmp_path)
        cfg.indexer.db_path = tmp_path / "library.db"
        cfg.indexer.db_path.write_bytes(b"")
        disk = MagicMock()
        disk.id = "Disk1"
        disk.path = str(disk_dir)
        disk.categories = ["movies"]
        cfg.disks = [disk]
        cfg.category.side_effect = lambda cid: SimpleNamespace(folder_name="001-MOVIES")
        staging = tmp_path / "staging"
        staging.mkdir()
        cfg.paths.staging_dir = staging

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCANNER) as MockScanner,
            patch(_PATCH_OPEN_DB),
            patch(_PATCH_STATE_STORE) as MockStore,
        ):
            MockScanner.return_value.scan_library_all.return_value = []  # index knows NOTHING
            MockStore.return_value.all_entries.return_value = {}
            result = runner.invoke(app, ["trailers", "purge", "--dry-run"])

        assert result.exit_code == 0, result.output
        # Present media with a real video is NEVER an orphan.
        assert "0 orphan" in result.output
        # It is surfaced as an index gap to re-index (rien en silence).
        assert "re-index 1" in result.output
        assert "Real Movie (2021)" in result.output

    def test_purge_heals_present_media_gap_and_keeps_trailer(self, tmp_path: Path) -> None:
        """A real purge re-indexes the present-but-unindexed dir and keeps its trailer.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from types import SimpleNamespace

        disk_dir = tmp_path / "Disk1"
        cat = disk_dir / "001-MOVIES"
        cat.mkdir(parents=True)
        movie = cat / "Real Movie (2021)"
        movie.mkdir()
        (movie / "Real Movie (2021).mkv").write_bytes(b"x" * 200000)
        trailer = movie / "Real Movie (2021)-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)

        cfg = _fake_config(tmp_path)
        cfg.indexer.db_path = tmp_path / "library.db"
        cfg.indexer.db_path.write_bytes(b"")
        disk = MagicMock()
        disk.id = "Disk1"
        disk.path = str(disk_dir)
        disk.categories = ["movies"]
        cfg.disks = [disk]
        cfg.category.side_effect = lambda cid: SimpleNamespace(folder_name="001-MOVIES")
        staging = tmp_path / "staging"
        staging.mkdir()
        cfg.paths.staging_dir = staging

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCANNER) as MockScanner,
            patch(_PATCH_OPEN_DB),
            patch(_PATCH_STATE_STORE) as MockStore,
            patch("personalscraper.indexer.scanner._modes._item_stage.scan_and_stage_dir") as MockStage,
        ):
            MockScanner.return_value.scan_library_all.return_value = []
            MockStore.return_value.all_entries.return_value = {}
            result = runner.invoke(app, ["trailers", "purge"])

        assert result.exit_code == 0, result.output
        # Trailer of present media survives the purge.
        assert trailer.exists(), "present-media trailer must be kept"
        # The index gap was healed via the scanner's single-dir stage primitive.
        assert MockStage.called, "scan_and_stage_dir must be called to heal the index gap"
        healed_dirs = [str(call.args[1]) for call in MockStage.call_args_list]
        assert any("Real Movie (2021)" in d for d in healed_dirs)
        assert "Re-indexed 1" in result.output

    def test_purge_skips_fs_walk_when_index_unavailable(self, tmp_path: Path) -> None:
        """No db_path ⇒ FS walk skipped (never flags every on-disk trailer).

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        # A disk with an unindexed movie + trailer, but NO resolvable index.
        disk_dir = tmp_path / "Disk1"
        cat = disk_dir / "001-MOVIES"
        cat.mkdir(parents=True)
        movie = cat / "Some Movie (2020)"
        movie.mkdir()
        (movie / "Some Movie (2020)-trailer.mp4").write_bytes(b"x" * 200000)

        cfg = _fake_config(tmp_path)
        # db_path left as the default MagicMock (not a str/Path) → index
        # unavailable → _live_item_dirs returns None → FS walk skipped.
        disk = MagicMock()
        disk.id = "Disk1"
        disk.path = str(disk_dir)
        cfg.disks = [disk]
        cfg.paths.staging_dir = tmp_path / "staging"
        (tmp_path / "staging").mkdir()

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_STATE_STORE) as MockStore,
        ):
            MockStore.return_value.all_entries.return_value = {}
            result = runner.invoke(app, ["trailers", "purge", "--dry-run"])

        assert result.exit_code == 0, result.output
        # Index unavailable ⇒ zero FS orphans (safety: no destructive false-positive).
        assert "0 orphan" in result.output
