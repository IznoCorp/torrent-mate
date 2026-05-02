"""Tests for the dispatch orchestrator.

Tests dispatch logic with mocked rsync, disk statuses, and index.
Covers movie replace, TV show merge, new item placement, dry-run,
and insufficient space handling.

V15 P6.3: Dispatcher now accepts Config as first argument. Category IDs
are V15 IDs (e.g. "movies", "tv_shows") rather than V14 labels ("films").
DiskConfig uses ``id`` field (Pydantic) rather than ``name`` (dataclass).

# ---------------------------------------------------------------------------
# Tests removed — moved to integration tier (phase 2-3)
# ---------------------------------------------------------------------------
# The following tests were deleted because their primary invariants are
# now covered end-to-end by the integration suite:
#
#   test_dispatch_movie_replace_existing
#       → tests/integration/test_dispatch_replace.py
#         (test_dispatch_replaces_existing_movie)
#
#   test_dispatch_tvshow_merge_existing
#       → tests/integration/test_dispatch_merge.py
#         (test_dispatch_merges_tvshow_new_episodes)
#
#   test_dispatch_movie_new_best_disk
#   test_dispatch_tvshow_new
#       → tests/integration/test_dispatch_new.py
#         (test_dispatch_picks_disk_with_most_space)
#
#   test_process_tvshow_type
#       → covered by test_process_verified_items (process routing) and
#         tests/integration/test_dispatch_new.py
#
#   test_dispatch_no_category_skip
#       → duplicate of test_skip_no_category in TestProcess
# ---------------------------------------------------------------------------
"""

import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.conf.models import DiskConfig
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.verify.verifier import VerifyResult


@pytest.fixture(autouse=True)
def _rsync_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make shutil.which report rsync as available for every test by default.

    Tests that need rsync to be absent (e.g. test_init_without_rsync) override
    this via their own @patch("shutil.which", return_value=None) decorator,
    which takes precedence over this autouse monkeypatch.
    """
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rsync" if name == "rsync" else None)


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock Settings (V15: no disk paths — thresholds only)."""
    s = MagicMock()
    s.min_free_space_disk_gb = 100.0
    return s


# ---------------------------------------------------------------------------
# Dispatcher initialization
# ---------------------------------------------------------------------------


class TestDispatcherInit:
    """Tests for Dispatcher initialization."""

    def test_init_with_rsync(self, test_config, mock_settings: MagicMock, tmp_path: Path) -> None:
        """Should initialize when rsync is available."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)
        assert d is not None

    @patch("shutil.which", return_value=None)
    def test_init_without_rsync(
        self, mock_which: MagicMock, test_config, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        """Should raise DispatchError when rsync is missing."""
        from personalscraper.dispatch.dispatcher import DispatchError

        idx = MediaIndex(tmp_path / "index.json")
        with pytest.raises(DispatchError, match="rsync"):
            Dispatcher(test_config, mock_settings, idx)


# ---------------------------------------------------------------------------
# Movie dispatch
# ---------------------------------------------------------------------------


class TestDispatchMovie:
    """Tests for dispatch_movie."""

    def test_new_movie_dry_run(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Dry run should report action without moving."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "Matrix.mkv").write_bytes(b"\x00" * 1024)

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskStatus

            mock_status.return_value = DiskStatus(
                config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["movies"]),
                free_space_gb=500,
                is_mounted=True,
            )

            result = d.dispatch_movie(movie_dir, "movies")

        assert result.action == "moved"
        assert movie_dir.exists()  # Not moved in dry run

    def test_no_space_skips(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should skip when no disk has enough space."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskStatus

            mock_status.return_value = DiskStatus(
                config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["movies"]),
                free_space_gb=0.5,  # Not enough
                is_mounted=True,
            )

            result = d.dispatch_movie(movie_dir, "movies")

        assert result.action == "skipped"
        assert "space" in (result.reason or "").lower()


# ---------------------------------------------------------------------------
# TV show dispatch
# ---------------------------------------------------------------------------


class TestDispatchTvshow:
    """Tests for dispatch_tvshow."""

    def test_new_tvshow_dry_run(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Dry run for new show should report action."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx, dry_run=True)

        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskStatus

            mock_status.return_value = DiskStatus(
                config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["tv_shows"]),
                free_space_gb=500,
                is_mounted=True,
            )

            result = d.dispatch_tvshow(show_dir, "tv_shows")

        assert result.action == "moved"


# ---------------------------------------------------------------------------
# Process verified items
# ---------------------------------------------------------------------------


class TestProcess:
    """Tests for process() method."""

    def test_process_verified_items(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should dispatch each verified item."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()

        verified = [
            VerifyResult(
                media_path=movie_dir,
                media_type="movie",
                category="movies",
                status="valid",
            ),
        ]

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskStatus

            mock_status.return_value = DiskStatus(
                config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["movies"]),
                free_space_gb=500,
                is_mounted=True,
            )

            results = d.process(verified=verified)

        assert len(results) == 1
        assert results[0].action in ("moved", "replaced")

    def test_skip_no_category(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should skip items without a category."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx, dry_run=True)

        verified = [
            VerifyResult(
                media_path=tmp_path,
                media_type="movie",
                category=None,
                status="blocked",
            ),
        ]

        results = d.process(verified=verified)
        assert len(results) == 1
        assert results[0].action == "skipped"

    def test_process_empty_verified(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should return empty results for empty verified list."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        results = d.process(verified=[])
        assert results == []


# ---------------------------------------------------------------------------
# Verify transfer
# ---------------------------------------------------------------------------


class TestVerifyTransfer:
    """Tests for _verify_transfer."""

    def test_matching_files(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should return True when all files match."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        content = b"\x00" * 1024
        (src / "file.mkv").write_bytes(content)
        (dst / "file.mkv").write_bytes(content)

        assert d._verify_transfer(src, dst) is True

    def test_missing_file_fails(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should return False when dest file is missing."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)

        assert d._verify_transfer(src, dst) is False

    def test_size_mismatch_fails(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should return False when file sizes differ."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)
        (dst / "file.mkv").write_bytes(b"\x00" * 512)

        assert d._verify_transfer(src, dst) is False


# ---------------------------------------------------------------------------
# Replace operation (_replace)
# ---------------------------------------------------------------------------


class TestReplace:
    """Tests for _replace crash-safe replace logic."""

    def test_replace_rsync_failure_cleanup(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Rsync failure should clean tmp_new and return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "file.mkv").write_bytes(b"\x00" * 1024)

        with patch.object(d, "_rsync", return_value=False):
            result = d._replace(source, dest)

        assert result is False
        # tmp_new should have been cleaned up (or never created)
        tmp_new = dest.parent / f"{dest.name}.new.tmp"
        assert not tmp_new.exists()

    def test_replace_atomic_swap_failure_restore(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """If atomic swap fails, original should be restored from tmp_old."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (dest / "original.mkv").write_bytes(b"\x00" * 512)

        def fake_rsync(src: Path, dst: Path, delete: bool = False) -> bool:
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "new.mkv").write_bytes(b"\x00" * 1024)
            return True

        # Make second os.rename fail (tmp_new → dest)
        original_rename = os.rename
        call_count = 0

        def failing_rename(src, dst):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("Simulated rename failure")
            return original_rename(src, dst)

        with patch.object(d, "_rsync", side_effect=fake_rsync):
            with patch("personalscraper.dispatch.dispatcher.os.rename", side_effect=failing_rename):
                result = d._replace(source, dest)

        assert result is False

    def test_replace_success(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Successful replace: rsync → swap → cleanup old + source."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "file.mkv").write_bytes(b"\x00" * 1024)
        (dest / "old.mkv").write_bytes(b"\x00" * 512)

        def fake_rsync(src: Path, dst: Path, delete: bool = False) -> bool:
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "file.mkv").write_bytes(b"\x00" * 1024)
            return True

        with patch.object(d, "_rsync", side_effect=fake_rsync):
            result = d._replace(source, dest)

        assert result is True
        assert dest.exists()
        assert (dest / "file.mkv").exists()
        # Source should be cleaned up
        assert not source.exists()


# ---------------------------------------------------------------------------
# Merge operation (_merge)
# ---------------------------------------------------------------------------


class TestMerge:
    """Tests for _merge TV show merge logic."""

    def test_merge_rsync_failure(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Rsync failure should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        with patch.object(d, "_rsync_merge", return_value=False):
            result = d._merge(source, dest)

        assert result is False

    def test_merge_verify_failure(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verification failure after rsync should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "S01E01.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch.object(d, "_rsync_merge", return_value=True),
            patch.object(d, "_verify_transfer", return_value=False),
        ):
            result = d._merge(source, dest)

        assert result is False

    def test_merge_success(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Successful merge: rsync + verify → source removed."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "S01E01.mkv").write_bytes(b"\x00" * 1024)

        with patch.object(d, "_rsync_merge", return_value=True), patch.object(d, "_verify_transfer", return_value=True):
            result = d._merge(source, dest)

        assert result is True
        assert not source.exists()

    def test_merge_os_error(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """OSError during merge should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        with patch.object(d, "_rsync_merge", side_effect=OSError("disk error")):
            result = d._merge(source, dest)

        assert result is False


# ---------------------------------------------------------------------------
# Move new operation (_move_new)
# ---------------------------------------------------------------------------


class TestMoveNew:
    """Tests for _move_new placement logic."""

    def test_move_new_success(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Successful move: rsync to tmp → rename → verify → source removed."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "movies" / "Movie (2024)"
        source.mkdir()
        (source / "file.mkv").write_bytes(b"\x00" * 1024)

        # Mock rsync to create the tmp dir (staging→commit pattern)
        tmp_dir = dest.parent / f"_tmp_dispatch_{dest.name}"

        def mock_rsync(src, dst, **kwargs):
            dst.mkdir(parents=True, exist_ok=True)
            return True

        with patch.object(d, "_rsync", side_effect=mock_rsync), patch.object(d, "_verify_transfer", return_value=True):
            result = d._move_new(source, dest)

        assert result is True
        assert not source.exists()
        assert dest.exists()
        assert not tmp_dir.exists()

    def test_move_new_rsync_failure(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Rsync failure should return False, dest should not exist."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "movies" / "Movie (2024)"
        source.mkdir()

        with patch.object(d, "_rsync", return_value=False):
            result = d._move_new(source, dest)

        assert result is False
        assert not dest.exists()

    def test_move_new_verify_failure(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verification failure should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "movies" / "Movie (2024)"
        source.mkdir()

        def mock_rsync(src, dst, **kwargs):
            dst.mkdir(parents=True, exist_ok=True)
            return True

        with patch.object(d, "_rsync", side_effect=mock_rsync), patch.object(d, "_verify_transfer", return_value=False):
            result = d._move_new(source, dest)

        assert result is False

    def test_move_new_orphan_tmp_cleaned(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Existing orphan _tmp_dispatch_* is cleaned before new attempt."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "movies" / "Movie (2024)"
        source.mkdir()
        (source / "file.mkv").write_bytes(b"\x00" * 1024)

        # Create orphan tmp dir
        tmp_dir = dest.parent / f"_tmp_dispatch_{dest.name}"
        tmp_dir.mkdir(parents=True)
        (tmp_dir / "partial.mkv").write_bytes(b"\x00" * 512)

        def mock_rsync(src, dst, **kwargs):
            dst.mkdir(parents=True, exist_ok=True)
            return True

        with patch.object(d, "_rsync", side_effect=mock_rsync), patch.object(d, "_verify_transfer", return_value=True):
            result = d._move_new(source, dest)

        assert result is True
        assert not tmp_dir.exists()


# ---------------------------------------------------------------------------
# Rsync wrapper
# ---------------------------------------------------------------------------


class TestRsync:
    """Tests for _rsync subprocess wrapper."""

    def test_rsync_success(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Successful rsync returns True."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = d._rsync(src, dst)

        assert result is True
        mock_run.assert_called_once()

    def test_rsync_failure_returns_false(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Failed rsync (non-zero returncode) returns False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=23, stderr="partial transfer")
            result = d._rsync(src, dst)

        assert result is False

    def test_rsync_timeout(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Timeout should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="rsync", timeout=3600)
            result = d._rsync(src, dst)

        assert result is False

    def test_rsync_delete_flag(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """delete=True should include --delete flag."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            d._rsync(src, dst, delete=True)

        cmd = mock_run.call_args[0][0]
        assert "--delete" in cmd

    def test_rsync_excludes_ds_store(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Rsync command should exclude .DS_Store and ._* files (Bug #1)."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            d._rsync(src, dst)

        cmd = mock_run.call_args[0][0]
        assert "--exclude=.DS_Store" in cmd
        assert "--exclude=._*" in cmd

    def test_rsync_merge_excludes_ds_store(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Rsync merge command should also exclude .DS_Store and ._* files (Bug #1)."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        backup = dst / ".merge_backup"

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            d._rsync_merge(src, dst, backup)

        cmd = mock_run.call_args[0][0]
        assert "--exclude=.DS_Store" in cmd
        assert "--exclude=._*" in cmd


# ---------------------------------------------------------------------------
# Dispatch dry-run guard
# ---------------------------------------------------------------------------


class TestDispatchDryRun:
    """Tests for dry-run behaviour in dispatch methods."""

    def test_dispatch_dry_run_no_transfer(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Dry run should not call rsync or modify filesystem."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "DryRunMovie (2024)"
        movie_dir.mkdir()
        (movie_dir / "file.mkv").write_bytes(b"\x00" * 1024)

        with (
            patch(
                "personalscraper.dispatch.dispatcher.get_disk_status",
            ) as mock_status,
            patch.object(d, "_rsync") as mock_rsync,
        ):
            from personalscraper.dispatch.disk_scanner import DiskStatus

            mock_status.return_value = DiskStatus(
                config=DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=["movies"]),
                free_space_gb=500,
                is_mounted=True,
            )

            d.dispatch_movie(movie_dir, "movies")

        mock_rsync.assert_not_called()
        assert movie_dir.exists()


# ---------------------------------------------------------------------------
# Orphan cleanup
# ---------------------------------------------------------------------------


class TestOrphanCleanup:
    """Tests for _cleanup_orphan_temps."""

    def test_cleans_tmp_dispatch_orphans(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Orphan _tmp_dispatch_* directories are cleaned up."""
        # Create disk structure with orphan
        disk = tmp_path / "drive_a" / "medias"
        movies_dir = disk / "movies"
        movies_dir.mkdir(parents=True)
        orphan = movies_dir / "_tmp_dispatch_Movie (2024)"
        orphan.mkdir()
        (orphan / "partial.mkv").write_bytes(b"\x00" * 512)

        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)
        d._disk_configs = [DiskConfig(id="drive_a", path=disk, categories=["movies"])]

        cleaned = d._cleanup_orphan_temps()

        assert cleaned == 1
        assert not orphan.exists()

    def test_cleans_merge_backup_orphans(
        self,
        test_config,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Orphan .merge_backup directories inside media dirs are cleaned."""
        disk = tmp_path / "drive_a" / "medias"
        series_dir = disk / "tv_shows"
        show_dir = series_dir / "Show (2024)"
        show_dir.mkdir(parents=True)
        backup = show_dir / ".merge_backup"
        backup.mkdir()
        (backup / "old_file.mkv").write_bytes(b"\x00" * 100)

        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(test_config, mock_settings, idx)
        d._disk_configs = [DiskConfig(id="drive_a", path=disk, categories=["tv_shows"])]

        cleaned = d._cleanup_orphan_temps()

        assert cleaned == 1
        assert not backup.exists()


# ---------------------------------------------------------------------------
# Merge backup restore
# ---------------------------------------------------------------------------


class TestRestoreMergeBackup:
    """Tests for Dispatcher._restore_merge_backup."""

    def test_restores_all_files(self, tmp_path: Path) -> None:
        """All backup files are restored to their original locations."""
        dest = tmp_path / "Show (2024)"
        dest.mkdir()
        # Existing file that was overwritten
        (dest / "S01E01.mkv").write_bytes(b"new")

        # Backup contains the original
        backup = dest / ".merge_backup"
        backup.mkdir()
        (backup / "S01E01.mkv").write_bytes(b"original")

        restored = Dispatcher._restore_merge_backup(dest, backup)

        assert restored == 1
        assert (dest / "S01E01.mkv").read_bytes() == b"original"
        assert not backup.exists()  # Cleaned after successful restore

    def test_continues_on_per_file_error(self, tmp_path: Path) -> None:
        """Per-file error does not abort remaining restores."""
        dest = tmp_path / "Show (2024)"
        dest.mkdir()

        backup = dest / ".merge_backup"
        backup.mkdir()
        (backup / "good.mkv").write_bytes(b"good-data")
        # Create a subdirectory backup
        (backup / "Saison 01").mkdir()
        (backup / "Saison 01" / "ep.mkv").write_bytes(b"ep-data")

        # Make one target read-only to force an error
        read_only_dir = dest / "Saison 01"
        read_only_dir.mkdir()
        read_only_target = read_only_dir / "ep.mkv"
        read_only_target.write_bytes(b"locked")
        read_only_target.chmod(0o000)

        try:
            Dispatcher._restore_merge_backup(dest, backup)
            # At least the good file should be restored
            assert (dest / "good.mkv").read_bytes() == b"good-data"
            # Backup NOT removed because some files failed
            assert backup.exists()
        finally:
            # Restore permissions for cleanup
            read_only_target.chmod(0o644)

    def test_empty_backup_dir(self, tmp_path: Path) -> None:
        """Empty backup dir returns 0 and is cleaned up."""
        dest = tmp_path / "Show"
        dest.mkdir()
        backup = dest / ".merge_backup"
        backup.mkdir()

        restored = Dispatcher._restore_merge_backup(dest, backup)

        assert restored == 0
        assert not backup.exists()

    def test_nonexistent_backup_dir(self, tmp_path: Path) -> None:
        """Nonexistent backup dir returns 0 immediately."""
        dest = tmp_path / "Show"
        dest.mkdir()
        backup = dest / ".merge_backup"

        restored = Dispatcher._restore_merge_backup(dest, backup)
        assert restored == 0


# ---------------------------------------------------------------------------
# NTFS pre-scan
# ---------------------------------------------------------------------------


class TestNtfsPreScan:
    """Tests for NTFS-illegal filename pre-scan before rsync."""

    def test_item_with_colon_skipped(self, tmp_path: Path) -> None:
        """Dispatch should skip items with NTFS-illegal filenames."""
        from personalscraper.dispatch.dispatcher import Dispatcher

        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie : Subtitle-poster.jpg").write_bytes(b"bad")

        result = Dispatcher._has_ntfs_illegal_names(movie_dir)

        assert result is True

    def test_clean_item_passes(self, tmp_path: Path) -> None:
        """Items with clean filenames should pass the pre-scan."""
        from personalscraper.dispatch.dispatcher import Dispatcher

        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie-poster.jpg").write_bytes(b"ok")

        result = Dispatcher._has_ntfs_illegal_names(movie_dir)

        assert result is False


# ---------------------------------------------------------------------------
# Episode-conflict purge (SxxExx-keyed merge dedup)
# ---------------------------------------------------------------------------


class TestPurgeEpisodeConflicts:
    """Tests for ``_purge_episode_conflicts``.

    The unique key for a TV episode file is the (season, episode) tuple
    parsed from the filename, NOT the full filename. A re-scrape that
    swaps the title segment (English original ↔ French localised) must
    NOT leave both copies on disk. The pre-rsync purge moves any dest
    file whose key matches a source file under a different filename
    into the merge backup directory.
    """

    @staticmethod
    def _purge(source: Path, dest: Path, backup_dir: Path) -> None:
        """Invoke the unbound method directly — no Dispatcher state required."""
        from personalscraper.dispatch.dispatcher import Dispatcher

        Dispatcher._purge_episode_conflicts(None, source, dest, backup_dir)  # type: ignore[arg-type]

    def test_renamed_episode_purged_to_backup(self, tmp_path: Path) -> None:
        """Same SxxExx, different filename → dest copy goes to backup."""
        src = tmp_path / "src" / "Show (2021)" / "Saison 04"
        dst = tmp_path / "dst" / "Show (2021)" / "Saison 04"
        src.mkdir(parents=True)
        dst.mkdir(parents=True)
        (src / "S04E06 - YOU LOOK HORRIBLE.mkv").write_bytes(b"new")
        (src / "S04E06 - YOU LOOK HORRIBLE.nfo").write_bytes(b"new")
        (dst / "S04E06 - T'AS UNE SALE GUEULE.mkv").write_bytes(b"old_fr")
        (dst / "S04E06 - T'AS UNE SALE GUEULE.nfo").write_bytes(b"old_fr")
        backup = dst.parent / ".merge_backup"

        self._purge(src.parent, dst.parent, backup)

        assert not (dst / "S04E06 - T'AS UNE SALE GUEULE.mkv").exists()
        assert not (dst / "S04E06 - T'AS UNE SALE GUEULE.nfo").exists()
        backed = list(backup.rglob("S04E06*"))
        assert len(backed) == 2, f"Expected mkv+nfo in backup, got: {backed}"

    def test_same_filename_left_alone(self, tmp_path: Path) -> None:
        """Same SxxExx AND same filename → leave for rsync to overwrite."""
        src = tmp_path / "src" / "Show (2021)" / "Saison 04"
        dst = tmp_path / "dst" / "Show (2021)" / "Saison 04"
        src.mkdir(parents=True)
        dst.mkdir(parents=True)
        (src / "S04E06 - SAME TITLE.mkv").write_bytes(b"new")
        (dst / "S04E06 - SAME TITLE.mkv").write_bytes(b"old")
        backup = dst.parent / ".merge_backup"

        self._purge(src.parent, dst.parent, backup)

        # File still on dst; rsync handles the overwrite normally.
        assert (dst / "S04E06 - SAME TITLE.mkv").exists()
        assert not backup.exists() or not list(backup.rglob("*.mkv"))

    def test_unrelated_episode_left_alone(self, tmp_path: Path) -> None:
        """Dest episode with no source counterpart must NOT be purged."""
        src = tmp_path / "src" / "Show (2021)" / "Saison 04"
        dst = tmp_path / "dst" / "Show (2021)" / "Saison 04"
        src.mkdir(parents=True)
        dst.mkdir(parents=True)
        (src / "S04E08 - NEW.mkv").write_bytes(b"new")
        (dst / "S04E07 - EXISTING.mkv").write_bytes(b"keep_me")
        backup = dst.parent / ".merge_backup"

        self._purge(src.parent, dst.parent, backup)

        # E07 is unrelated to source's E08 — must stay put.
        assert (dst / "S04E07 - EXISTING.mkv").exists()

    def test_no_dest_dir_is_noop(self, tmp_path: Path) -> None:
        """Missing dest directory → noop, no exception."""
        src = tmp_path / "src" / "Show (2021)" / "Saison 04"
        src.mkdir(parents=True)
        (src / "S04E01 - TITLE.mkv").write_bytes(b"new")

        # Should not raise.
        self._purge(src.parent, tmp_path / "nope", tmp_path / "backup")

    def test_files_without_se_pattern_ignored(self, tmp_path: Path) -> None:
        """Files that do not parse as SxxExx are not considered for purge."""
        src = tmp_path / "src" / "Show (2021)" / "Saison 04"
        dst = tmp_path / "dst" / "Show (2021)" / "Saison 04"
        src.mkdir(parents=True)
        dst.mkdir(parents=True)
        (src / "trailer.mkv").write_bytes(b"new")
        (dst / "fanart.jpg").write_bytes(b"keep")
        backup = dst.parent / ".merge_backup"

        self._purge(src.parent, dst.parent, backup)

        assert (dst / "fanart.jpg").exists()
