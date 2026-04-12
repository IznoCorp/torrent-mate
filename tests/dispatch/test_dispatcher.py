"""Tests for the dispatch orchestrator.

Tests dispatch logic with mocked rsync, disk statuses, and index.
Covers movie replace, TV show merge, new item placement, dry-run,
and insufficient space handling.
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.verify.verifier import VerifyResult


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock Settings."""
    s = MagicMock()
    s.disk1_dir = "/Volumes/Disk1/medias"
    s.disk2_dir = "/Volumes/Disk2/medias"
    s.disk3_dir = "/Volumes/Disk3/medias"
    s.disk4_dir = "/Volumes/Disk4/medias"
    s.min_free_space_disk_gb = 100.0
    return s


# ---------------------------------------------------------------------------
# Dispatcher initialization
# ---------------------------------------------------------------------------

class TestDispatcherInit:
    """Tests for Dispatcher initialization."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_init_with_rsync(self, mock_which: MagicMock, mock_settings: MagicMock) -> None:
        """Should initialize when rsync is available."""
        idx = MediaIndex()
        d = Dispatcher(mock_settings, idx)
        assert d is not None

    @patch("shutil.which", return_value=None)
    def test_init_without_rsync(self, mock_which: MagicMock, mock_settings: MagicMock) -> None:
        """Should raise DispatchError when rsync is missing."""
        from personalscraper.dispatch.dispatcher import DispatchError
        idx = MediaIndex()
        with pytest.raises(DispatchError, match="rsync"):
            Dispatcher(mock_settings, idx)


# ---------------------------------------------------------------------------
# Movie dispatch
# ---------------------------------------------------------------------------

class TestDispatchMovie:
    """Tests for dispatch_movie."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_new_movie_dry_run(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Dry run should report action without moving."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "Matrix.mkv").write_bytes(b"\x00" * 1024)

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["films"]),
                free_space_gb=500,
                is_mounted=True,
            )

            result = d.dispatch_movie(movie_dir, "films")

        assert result.action == "moved"
        assert movie_dir.exists()  # Not moved in dry run

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_no_space_skips(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should skip when no disk has enough space."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["films"]),
                free_space_gb=0.5,  # Not enough
                is_mounted=True,
            )

            result = d.dispatch_movie(movie_dir, "films")

        assert result.action == "skipped"
        assert "space" in (result.reason or "").lower()


# ---------------------------------------------------------------------------
# TV show dispatch
# ---------------------------------------------------------------------------

class TestDispatchTvshow:
    """Tests for dispatch_tvshow."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_new_tvshow_dry_run(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Dry run for new show should report action."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["series"]),
                free_space_gb=500,
                is_mounted=True,
            )

            result = d.dispatch_tvshow(show_dir, "series")

        assert result.action == "moved"


# ---------------------------------------------------------------------------
# Process verified items
# ---------------------------------------------------------------------------

class TestProcess:
    """Tests for process() method."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_process_verified_items(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should dispatch each verified item."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()

        verified = [
            VerifyResult(
                media_path=movie_dir, media_type="movie",
                category="films", status="valid",
            ),
        ]

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["films"]),
                free_space_gb=500,
                is_mounted=True,
            )

            results = d.process(verified=verified)

        assert len(results) == 1
        assert results[0].action in ("moved", "replaced")

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_skip_no_category(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should skip items without a category."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        verified = [
            VerifyResult(
                media_path=tmp_path, media_type="movie",
                category=None, status="blocked",
            ),
        ]

        results = d.process(verified=verified)
        assert len(results) == 1
        assert results[0].action == "skipped"

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_process_requires_one_mode(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should raise ValueError with both or neither args."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        with pytest.raises(ValueError):
            d.process(verified=[], staging_dir=tmp_path)

        with pytest.raises(ValueError):
            d.process()


# ---------------------------------------------------------------------------
# Verify transfer
# ---------------------------------------------------------------------------

class TestVerifyTransfer:
    """Tests for _verify_transfer."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_matching_files(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should return True when all files match."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        content = b"\x00" * 1024
        (src / "file.mkv").write_bytes(content)
        (dst / "file.mkv").write_bytes(content)

        assert d._verify_transfer(src, dst) is True

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_missing_file_fails(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should return False when dest file is missing."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)

        assert d._verify_transfer(src, dst) is False

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_size_mismatch_fails(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Should return False when file sizes differ."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

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

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_replace_rsync_failure_cleanup(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Rsync failure should clean tmp_new and return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

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

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_replace_atomic_swap_failure_restore(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """If atomic swap fails, original should be restored from tmp_old."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (dest / "original.mkv").write_bytes(b"\x00" * 512)

        tmp_new = dest.parent / f"{dest.name}.new.tmp"

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

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_replace_success(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Successful replace: rsync → swap → cleanup old + source."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

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

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_merge_rsync_failure(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Rsync failure should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        with patch.object(d, "_rsync_merge", return_value=False):
            result = d._merge(source, dest)

        assert result is False

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_merge_verify_failure(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Verification failure after rsync should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "S01E01.mkv").write_bytes(b"\x00" * 1024)

        with patch.object(d, "_rsync_merge", return_value=True), \
             patch.object(d, "_verify_transfer", return_value=False):
            result = d._merge(source, dest)

        assert result is False

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_merge_success(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Successful merge: rsync + verify → source removed."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "S01E01.mkv").write_bytes(b"\x00" * 1024)

        with patch.object(d, "_rsync_merge", return_value=True), \
             patch.object(d, "_verify_transfer", return_value=True):
            result = d._merge(source, dest)

        assert result is True
        assert not source.exists()

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_merge_os_error(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """OSError during merge should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

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

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_move_new_success(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Successful move: rsync to tmp → rename → verify → source removed."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "films" / "Movie (2024)"
        source.mkdir()
        (source / "file.mkv").write_bytes(b"\x00" * 1024)

        # Mock rsync to create the tmp dir (staging→commit pattern)
        tmp_dir = dest.parent / f"_tmp_dispatch_{dest.name}"

        def mock_rsync(src, dst, **kwargs):
            dst.mkdir(parents=True, exist_ok=True)
            return True

        with patch.object(d, "_rsync", side_effect=mock_rsync), \
             patch.object(d, "_verify_transfer", return_value=True):
            result = d._move_new(source, dest)

        assert result is True
        assert not source.exists()
        assert dest.exists()
        assert not tmp_dir.exists()

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_move_new_rsync_failure(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Rsync failure should return False, dest should not exist."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "films" / "Movie (2024)"
        source.mkdir()

        with patch.object(d, "_rsync", return_value=False):
            result = d._move_new(source, dest)

        assert result is False
        assert not dest.exists()

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_move_new_verify_failure(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Verification failure should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "films" / "Movie (2024)"
        source.mkdir()

        def mock_rsync(src, dst, **kwargs):
            dst.mkdir(parents=True, exist_ok=True)
            return True

        with patch.object(d, "_rsync", side_effect=mock_rsync), \
             patch.object(d, "_verify_transfer", return_value=False):
            result = d._move_new(source, dest)

        assert result is False

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_move_new_orphan_tmp_cleaned(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Existing orphan _tmp_dispatch_* is cleaned before new attempt."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        source = tmp_path / "source"
        dest = tmp_path / "dest" / "films" / "Movie (2024)"
        source.mkdir()
        (source / "file.mkv").write_bytes(b"\x00" * 1024)

        # Create orphan tmp dir
        tmp_dir = dest.parent / f"_tmp_dispatch_{dest.name}"
        tmp_dir.mkdir(parents=True)
        (tmp_dir / "partial.mkv").write_bytes(b"\x00" * 512)

        def mock_rsync(src, dst, **kwargs):
            dst.mkdir(parents=True, exist_ok=True)
            return True

        with patch.object(d, "_rsync", side_effect=mock_rsync), \
             patch.object(d, "_verify_transfer", return_value=True):
            result = d._move_new(source, dest)

        assert result is True
        assert not tmp_dir.exists()


# ---------------------------------------------------------------------------
# Rsync wrapper
# ---------------------------------------------------------------------------

class TestRsync:
    """Tests for _rsync subprocess wrapper."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_rsync_success(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Successful rsync returns True."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = d._rsync(src, dst)

        assert result is True
        mock_run.assert_called_once()

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_rsync_failure_returns_false(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Failed rsync (non-zero returncode) returns False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=23, stderr="partial transfer")
            result = d._rsync(src, dst)

        assert result is False

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_rsync_timeout(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Timeout should return False."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="rsync", timeout=3600)
            result = d._rsync(src, dst)

        assert result is False

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_rsync_delete_flag(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """delete=True should include --delete flag."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)

        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()

        with patch("personalscraper.dispatch.dispatcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            d._rsync(src, dst, delete=True)

        cmd = mock_run.call_args[0][0]
        assert "--delete" in cmd


# ---------------------------------------------------------------------------
# Dispatch with existing items (replace/merge paths)
# ---------------------------------------------------------------------------

class TestDispatchExisting:
    """Tests for dispatch with existing items in the index."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_dispatch_movie_replace_existing(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Movie existing in index should trigger replace, not move."""
        idx = MediaIndex(tmp_path / "index.json")
        from personalscraper.dispatch.media_index import IndexEntry
        existing_path = tmp_path / "disk1" / "films" / "Matrix (1999)"
        existing_path.mkdir(parents=True)
        idx.add(IndexEntry(
            name="Matrix (1999)", disk="Disk1", category="films",
            path=str(existing_path), media_type="movie",
        ))

        d = Dispatcher(mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "Matrix.mkv").write_bytes(b"\x00" * 1024)

        result = d.dispatch_movie(movie_dir, "films")

        assert result.action == "replaced"
        assert result.disk == "Disk1"

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_dispatch_tvshow_merge_existing(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """TV show existing in index should trigger merge, not move."""
        idx = MediaIndex(tmp_path / "index.json")
        from personalscraper.dispatch.media_index import IndexEntry
        existing_path = tmp_path / "disk1" / "series" / "Fallout (2024)"
        existing_path.mkdir(parents=True)
        idx.add(IndexEntry(
            name="Fallout (2024)", disk="Disk1", category="series",
            path=str(existing_path), media_type="tvshow",
        ))

        d = Dispatcher(mock_settings, idx, dry_run=True)

        show_dir = tmp_path / "Fallout (2024)"
        show_dir.mkdir()

        result = d.dispatch_tvshow(show_dir, "series")

        assert result.action == "merged"
        assert result.disk == "Disk1"

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_dispatch_movie_new_best_disk(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """New movie should be placed on disk with most free space."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "NewMovie (2024)"
        movie_dir.mkdir()
        (movie_dir / "file.mkv").write_bytes(b"\x00" * 1024)

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk3", Path("/Volumes/Disk3/medias"), ["films"]),
                free_space_gb=800,
                is_mounted=True,
            )

            result = d.dispatch_movie(movie_dir, "films")

        assert result.action == "moved"
        assert result.disk == "Disk3"

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_dispatch_tvshow_new(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """New TV show should be moved to best disk."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        show_dir = tmp_path / "NewShow (2024)"
        show_dir.mkdir()

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk2", Path("/Volumes/Disk2/medias"), ["series"]),
                free_space_gb=600,
                is_mounted=True,
            )

            result = d.dispatch_tvshow(show_dir, "series")

        assert result.action == "moved"

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_dispatch_no_category_skip(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """VerifyResult without category should be skipped in process()."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        verified = [
            VerifyResult(
                media_path=tmp_path / "Unknown", media_type="movie",
                category=None, status="blocked",
            ),
        ]
        results = d.process(verified=verified)
        assert len(results) == 1
        assert results[0].action == "skipped"
        assert "category" in (results[0].reason or "").lower()

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_dispatch_dry_run_no_transfer(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Dry run should not call rsync or modify filesystem."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        movie_dir = tmp_path / "DryRunMovie (2024)"
        movie_dir.mkdir()
        (movie_dir / "file.mkv").write_bytes(b"\x00" * 1024)

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status, \
             patch.object(d, "_rsync") as mock_rsync:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["films"]),
                free_space_gb=500,
                is_mounted=True,
            )

            d.dispatch_movie(movie_dir, "films")

        mock_rsync.assert_not_called()
        assert movie_dir.exists()

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_process_tvshow_type(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Process with tvshow type should call dispatch_tvshow."""
        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx, dry_run=True)

        show_dir = tmp_path / "Show (2024)"
        show_dir.mkdir()

        verified = [
            VerifyResult(
                media_path=show_dir, media_type="tvshow",
                category="series", status="valid",
            ),
        ]

        with patch(
            "personalscraper.dispatch.dispatcher.get_disk_status",
        ) as mock_status:
            from personalscraper.dispatch.disk_scanner import DiskConfig, DiskStatus
            mock_status.return_value = DiskStatus(
                config=DiskConfig("Disk1", Path("/Volumes/Disk1/medias"), ["series"]),
                free_space_gb=500,
                is_mounted=True,
            )

            results = d.process(verified=verified)

        assert len(results) == 1
        assert results[0].action == "moved"


# ---------------------------------------------------------------------------
# Orphan cleanup
# ---------------------------------------------------------------------------


class TestOrphanCleanup:
    """Tests for _cleanup_orphan_temps."""

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_cleans_tmp_dispatch_orphans(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Orphan _tmp_dispatch_* directories are cleaned up."""
        from personalscraper.dispatch.disk_scanner import DiskConfig

        # Create disk structure with orphan
        disk = tmp_path / "Disk1" / "medias"
        films_dir = disk / "films"
        films_dir.mkdir(parents=True)
        orphan = films_dir / "_tmp_dispatch_Movie (2024)"
        orphan.mkdir()
        (orphan / "partial.mkv").write_bytes(b"\x00" * 512)

        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)
        d._disk_configs = [DiskConfig("Disk1", disk, ["films"])]

        cleaned = d._cleanup_orphan_temps()

        assert cleaned == 1
        assert not orphan.exists()

    @patch("shutil.which", return_value="/usr/bin/rsync")
    def test_cleans_merge_backup_orphans(
        self, mock_which: MagicMock, mock_settings: MagicMock, tmp_path: Path,
    ) -> None:
        """Orphan .merge_backup directories inside media dirs are cleaned."""
        from personalscraper.dispatch.disk_scanner import DiskConfig

        disk = tmp_path / "Disk1" / "medias"
        series_dir = disk / "series"
        show_dir = series_dir / "Show (2024)"
        show_dir.mkdir(parents=True)
        backup = show_dir / ".merge_backup"
        backup.mkdir()
        (backup / "old_file.mkv").write_bytes(b"\x00" * 100)

        idx = MediaIndex(tmp_path / "index.json")
        d = Dispatcher(mock_settings, idx)
        d._disk_configs = [DiskConfig("Disk1", disk, ["series"])]

        cleaned = d._cleanup_orphan_temps()

        assert cleaned == 1
        assert not backup.exists()
