"""Tests for ingest orchestration — run_ingest() entry point.

Covers the run_ingest orchestrator with mocked QBitClient, IngestTracker,
and filesystem operations. Tests the main dispatch paths: no torrents,
already ingested, copy (seeding), move (done), disk space check, verify
fail, dry run, and multiple torrents.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.ingest.ingest import (
    _check_disk_space,
    _cleanup_orphan_temps,
    _get_dir_size,
    _is_orphan_tracker_entry,
    _verify_transfer,
    run_ingest,
    transfer_torrent,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS


class TestIsOrphanTrackerEntry:
    """Regression tests for the ingest_dir carve-out in _is_orphan_tracker_entry.

    The function probes whether a tracker entry recorded by ingest is an
    orphan (its dest_path no longer exists).  The carve-out for paths inside
    ``ingest_dir`` exists because sort consumes ingest staging files into
    category dirs without rewriting tracker entries; without the carve-out
    the warning fires on every pipeline run after the first successful sort.
    """

    def test_no_dest_path_is_not_orphan(self) -> None:
        """Legacy entries without dest_path return False (no opinion)."""
        assert _is_orphan_tracker_entry({"hash": "abc"}) is False
        assert _is_orphan_tracker_entry({"hash": "abc", "dest_path": ""}) is False

    def test_existing_dest_path_is_not_orphan(self, tmp_path: Path) -> None:
        """Existing dest_path returns False regardless of ingest_dir."""
        existing = tmp_path / "movie"
        existing.mkdir()
        assert _is_orphan_tracker_entry({"dest_path": str(existing)}) is False

    def test_missing_outside_ingest_dir_is_orphan(self, tmp_path: Path) -> None:
        """A missing path outside ingest_dir is the real orphan signal."""
        missing = tmp_path / "category" / "movie"
        ingest_dir = tmp_path / "ingest_staging"
        ingest_dir.mkdir()
        # Without ingest_dir context: any missing path is orphan.
        assert _is_orphan_tracker_entry({"dest_path": str(missing)}) is True
        # With ingest_dir context: outside ingest_dir is still orphan.
        assert _is_orphan_tracker_entry({"dest_path": str(missing)}, ingest_dir) is True

    def test_missing_inside_ingest_dir_is_carved_out(self, tmp_path: Path) -> None:
        """A missing path inside ingest_dir is treated as 'sort consumed it'."""
        ingest_dir = tmp_path / "ingest_staging"
        ingest_dir.mkdir()
        consumed = ingest_dir / "freshly-sorted-movie"
        # consumed never created — sort moved it out of ingest_staging
        assert _is_orphan_tracker_entry({"dest_path": str(consumed)}, ingest_dir) is False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestGetDirSize:
    """Tests for _get_dir_size helper."""

    def test_file_size(self, tmp_path: Path) -> None:
        """Should return file size for a single file."""
        f = tmp_path / "test.mkv"
        f.write_bytes(b"\x00" * 2048)
        assert _get_dir_size(f) == 2048

    def test_dir_size(self, tmp_path: Path) -> None:
        """Should return total size of all files in directory."""
        (tmp_path / "a.mkv").write_bytes(b"\x00" * 1000)
        (tmp_path / "b.mkv").write_bytes(b"\x00" * 500)
        assert _get_dir_size(tmp_path) == 1500

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory should return 0."""
        assert _get_dir_size(tmp_path) == 0


class TestVerifyTransfer:
    """Tests for _verify_transfer helper."""

    def test_matching_sizes(self, tmp_path: Path) -> None:
        """Should return True when sizes match."""
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)
        (dst / "file.mkv").write_bytes(b"\x00" * 1024)
        assert _verify_transfer(src, dst) is True

    def test_missing_dest(self, tmp_path: Path) -> None:
        """Should return False when dest doesn't exist."""
        src = tmp_path / "src"
        src.mkdir()
        assert _verify_transfer(src, tmp_path / "nonexistent") is False

    def test_size_mismatch(self, tmp_path: Path) -> None:
        """Should return False when sizes differ."""
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)
        (dst / "file.mkv").write_bytes(b"\x00" * 512)
        assert _verify_transfer(src, dst) is False


class TestCleanupOrphanTemps:
    """Tests for _cleanup_orphan_temps helper."""

    def test_cleanup_orphan(self, tmp_path: Path) -> None:
        """Should remove .ingest_tmp_* directories."""
        orphan = tmp_path / ".ingest_tmp_Movie"
        orphan.mkdir()
        (orphan / "file.mkv").write_bytes(b"\x00" * 100)

        removed = _cleanup_orphan_temps(tmp_path)

        assert removed == 1
        assert not orphan.exists()

    def test_ignore_non_temp(self, tmp_path: Path) -> None:
        """Should not remove directories without the prefix."""
        normal = tmp_path / "Movie (2024)"
        normal.mkdir()

        removed = _cleanup_orphan_temps(tmp_path)

        assert removed == 0
        assert normal.exists()


class TestCheckDiskSpace:
    """Tests for _check_disk_space helper."""

    def test_enough_space(self, tmp_path: Path) -> None:
        """Should return True when there is enough free space."""
        # tmp_path is on a real filesystem with plenty of space
        result = _check_disk_space(tmp_path, 1024, 0)
        assert result is True

    def test_insufficient_space(self, tmp_path: Path) -> None:
        """Should return False when min_free_gb is impossibly high."""
        result = _check_disk_space(tmp_path, 0, 999999)
        assert result is False


# ---------------------------------------------------------------------------
# transfer_torrent
# ---------------------------------------------------------------------------


class TestTransferTorrent:
    """Tests for transfer_torrent function."""

    def test_dry_run_no_transfer(self, tmp_path: Path) -> None:
        """Dry run should return True without moving/copying."""
        src = tmp_path / "src"
        src.mkdir()
        dest = tmp_path / "dest"

        result = transfer_torrent(src, dest, copy=True, dry_run=True)

        assert result is True
        assert src.exists()
        assert not dest.exists()

    def test_copy_directory(self, tmp_path: Path) -> None:
        """Copy should create dest and keep source."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)
        dest = tmp_path / "dest"

        result = transfer_torrent(src, dest, copy=True)

        assert result is True
        assert src.exists()
        assert dest.exists()
        assert (dest / "file.mkv").exists()

    def test_move_directory(self, tmp_path: Path) -> None:
        """Move should create dest and remove source."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.mkv").write_bytes(b"\x00" * 1024)
        dest = tmp_path / "dest"

        result = transfer_torrent(src, dest, copy=False)

        assert result is True
        assert not src.exists()
        assert dest.exists()

    def test_copy_file(self, tmp_path: Path) -> None:
        """Copy should work for single files too."""
        src = tmp_path / "movie.mkv"
        src.write_bytes(b"\x00" * 2048)
        dest = tmp_path / "dest_movie.mkv"

        result = transfer_torrent(src, dest, copy=True)

        assert result is True
        assert src.exists()
        assert dest.exists()


# ---------------------------------------------------------------------------
# run_ingest orchestration
# ---------------------------------------------------------------------------


def _make_torrent(name: str, torrent_hash: str) -> MagicMock:
    """Create a mock torrent object."""
    t = MagicMock()
    t.name = name
    t.hash = torrent_hash
    return t


def _make_config(tmp_path: Path) -> MagicMock:
    """Create a minimal config mock with staging_dirs and staging path.

    Args:
        tmp_path: Temporary directory used as the staging root.

    Returns:
        MagicMock with staging_dirs and paths.staging_dir configured.
    """
    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    c.ingest.min_ratio = 0.0  # disable ratio guard — matches IngestConfig default
    c.thresholds.min_free_space_staging_gb = 0  # disable disk-space guard in tests
    return c


class TestRunIngest:
    """Tests for run_ingest orchestrator."""

    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_no_completed_torrents(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """No completed torrents should return success_count=0."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = []
        mock_client.get_all_torrent_hashes.return_value = set()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.success_count == 0
        assert report.error_count == 0

    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_already_ingested_skip(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Already-ingested torrents should be skipped."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        torrent = _make_torrent("Movie (2024)", "abc123")
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"abc123"}
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = True
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.skip_count == 1
        assert report.success_count == 0

    @patch("personalscraper.ingest.ingest.transfer_torrent", return_value=True)
    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_copy_seeding(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        mock_transfer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Seeding torrent should be copied (not moved)."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        torrent = _make_torrent("SeedingMovie", "hash1")
        source = tmp_path / "complete" / "SeedingMovie"
        source.mkdir(parents=True)
        (source / "file.mkv").write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"hash1"}
        mock_client.get_content_path.return_value = source
        mock_client.is_seeding.return_value = True
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.success_count == 1
        mock_transfer.assert_called_once()
        call_kwargs = mock_transfer.call_args
        assert call_kwargs[1].get("copy") is True or call_kwargs[0][2] is True

    @patch("personalscraper.ingest.ingest.transfer_torrent", return_value=True)
    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_move_done(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        mock_transfer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Completed (not seeding) torrent should be moved."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        torrent = _make_torrent("DoneMovie", "hash2")
        source = tmp_path / "complete" / "DoneMovie"
        source.mkdir(parents=True)
        (source / "file.mkv").write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"hash2"}
        mock_client.get_content_path.return_value = source
        mock_client.is_seeding.return_value = False
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.success_count == 1
        mock_transfer.assert_called_once()
        call_kwargs = mock_transfer.call_args
        assert call_kwargs[1].get("copy") is False or call_kwargs[0][2] is False

    @patch("personalscraper.ingest.ingest._check_disk_space", return_value=False)
    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_disk_space_fail(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        mock_space: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Insufficient disk space should skip the torrent."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        config = _make_config(tmp_path)
        config.thresholds.min_free_space_staging_gb = 999

        torrent = _make_torrent("BigMovie", "hash3")
        source = tmp_path / "complete" / "BigMovie"
        source.mkdir(parents=True)
        (source / "file.mkv").write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"hash3"}
        mock_client.get_content_path.return_value = source
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=config)

        assert report.skip_count == 1
        assert report.success_count == 0

    @patch("personalscraper.ingest.ingest.transfer_torrent", return_value=False)
    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_transfer_fail(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        mock_transfer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Transfer failure should increment error_count."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        torrent = _make_torrent("FailMovie", "hash4")
        source = tmp_path / "complete" / "FailMovie"
        source.mkdir(parents=True)
        (source / "file.mkv").write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"hash4"}
        mock_client.get_content_path.return_value = source
        mock_client.is_seeding.return_value = False
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.error_count == 1
        assert report.success_count == 0

    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_dry_run(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Dry run should not call _cleanup_orphan_temps or mark ingested."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        torrent = _make_torrent("DryMovie", "hash5")
        source = tmp_path / "complete" / "DryMovie"
        source.mkdir(parents=True)
        (source / "file.mkv").write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"hash5"}
        mock_client.get_content_path.return_value = source
        mock_client.is_seeding.return_value = False
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, dry_run=True, config=_make_config(tmp_path))

        assert report.success_count == 1
        mock_tracker.mark_ingested.assert_not_called()

    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_step_report_counts(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """StepReport should have correct name and initial counts."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = []
        mock_client.get_all_torrent_hashes.return_value = set()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.name == "ingest"
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0

    @patch("personalscraper.ingest.ingest.transfer_torrent", return_value=True)
    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_multiple_torrents(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        mock_transfer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Multiple torrents: 1 seeding (copy) + 1 done (move) + 1 already ingested."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        t1 = _make_torrent("Seeding", "h1")
        t2 = _make_torrent("Done", "h2")
        t3 = _make_torrent("Already", "h3")

        src1 = tmp_path / "complete" / "Seeding"
        src2 = tmp_path / "complete" / "Done"
        for s in (src1, src2):
            s.mkdir(parents=True, exist_ok=True)
            (s / "file.mkv").write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [t1, t2, t3]
        mock_client.get_all_torrent_hashes.return_value = {"h1", "h2", "h3"}
        mock_client.get_content_path.side_effect = [src1, src2]
        mock_client.is_seeding.side_effect = [True, False]
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        # t3 is already ingested
        mock_tracker = MagicMock()
        mock_tracker.is_ingested.side_effect = [False, False, True]
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.success_count == 2
        assert report.skip_count == 1

    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_qbit_init_failure(
        self,
        mock_qbit_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """QBitClient init failure should return error report."""
        settings = MagicMock()

        mock_qbit_cls.side_effect = ConnectionError("Cannot connect")

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.error_count == 1
        assert "init failed" in report.details[0].lower()

    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_content_path_missing(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Missing content path should increment skip_count (file likely already processed)."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        torrent = _make_torrent("Ghost", "hash6")

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"hash6"}
        mock_client.get_content_path.return_value = tmp_path / "nonexistent"
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.skip_count == 1
        # Escalated to error because ALL torrents had missing content
        assert report.error_count == 1
        assert any("source volume mounted" in d for d in report.details)

    @patch("personalscraper.ingest.ingest.transfer_torrent")
    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_one_torrent_failure_does_not_block_others(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        mock_transfer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """OSError on one transfer should not prevent the others from completing."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        t1 = _make_torrent("Good1", "h1")
        t2 = _make_torrent("Bad", "h2")
        t3 = _make_torrent("Good2", "h3")

        for name in ("Good1", "Bad", "Good2"):
            src = tmp_path / "complete" / name
            src.mkdir(parents=True)
            (src / "file.mkv").write_bytes(b"\x00" * 100)

        src1 = tmp_path / "complete" / "Good1"
        src2 = tmp_path / "complete" / "Bad"
        src3 = tmp_path / "complete" / "Good2"

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [t1, t2, t3]
        mock_client.get_all_torrent_hashes.return_value = {"h1", "h2", "h3"}
        mock_client.get_content_path.side_effect = [src1, src2, src3]
        mock_client.is_seeding.return_value = False
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        # 2nd call raises OSError, 1st and 3rd succeed
        mock_transfer.side_effect = [True, OSError("Disk I/O error"), True]

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.success_count == 2
        assert report.error_count == 1
        assert any("Bad" in d for d in report.details)

    @patch("personalscraper.ingest.ingest.transfer_torrent")
    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_consecutive_errors_abort_loop(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        mock_transfer: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Two consecutive identical errors should abort the loop (systemic failure)."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        t1 = _make_torrent("Fail1", "h1")
        t2 = _make_torrent("Fail2", "h2")
        t3 = _make_torrent("NeverReached", "h3")

        for name in ("Fail1", "Fail2", "NeverReached"):
            src = tmp_path / "complete" / name
            src.mkdir(parents=True)
            (src / "file.mkv").write_bytes(b"\x00" * 100)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [t1, t2, t3]
        mock_client.get_all_torrent_hashes.return_value = {"h1", "h2", "h3"}
        mock_client.get_content_path.side_effect = [
            tmp_path / "complete" / "Fail1",
            tmp_path / "complete" / "Fail2",
            tmp_path / "complete" / "NeverReached",
        ]
        mock_client.is_seeding.return_value = False
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        # Both transfers raise the same error type → triggers abort after 2nd
        mock_transfer.side_effect = [OSError("Disk dead"), OSError("Disk dead")]

        report = run_ingest(settings, config=_make_config(tmp_path))

        # 2 errors, loop aborted before reaching torrent 3
        assert report.error_count == 2
        assert report.success_count == 0
        assert any("Aborted" in d for d in report.details)
        # Transfer was only called twice (3rd torrent never reached)
        assert mock_transfer.call_count == 2

    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_forbidden_403_actionable_message(
        self,
        mock_qbit_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Forbidden403Error should produce IP-banned message, not generic unreachable."""
        import qbittorrentapi

        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=qbittorrentapi.Forbidden403Error())
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.error_count >= 1
        combined = " ".join(report.details).lower()
        # Must mention IP ban, not generic "unreachable"
        assert "banned" in combined or "blocked" in combined
        assert "unreachable" not in combined

    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_login_failed_actionable_message(
        self,
        mock_qbit_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """LoginFailed should produce an actionable message mentioning auth or login."""
        import qbittorrentapi

        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=qbittorrentapi.LoginFailed())
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.error_count >= 1
        combined = " ".join(report.details).lower()
        assert "auth" in combined or "login" in combined

    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_api_connection_error_actionable_message(
        self,
        mock_qbit_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """APIConnectionError should produce an actionable message mentioning unreachable or running."""
        import qbittorrentapi

        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=qbittorrentapi.APIConnectionError("Connection refused"))
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.error_count >= 1
        combined = " ".join(report.details).lower()
        assert "unreachable" in combined or "running" in combined

    @patch("personalscraper.ingest.ingest.IngestTracker")
    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_dest_already_exists_skip(
        self,
        mock_qbit_cls: MagicMock,
        mock_tracker_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """If destination already exists in staging, skip and mark ingested."""
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        torrent = _make_torrent("Existing", "hash7")
        source = tmp_path / "complete" / "Existing"
        source.mkdir(parents=True)
        (source / "file.mkv").write_bytes(b"\x00" * 100)

        # Destination already exists in 097-TEMP/ (where ingest deposits)
        dest = tmp_path / "097-TEMP" / "Existing"
        dest.mkdir(parents=True)

        mock_client = MagicMock()
        mock_client.get_completed_torrents.return_value = [torrent]
        mock_client.get_all_torrent_hashes.return_value = {"hash7"}
        mock_client.get_content_path.return_value = source
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        mock_tracker = MagicMock()
        mock_tracker.is_ingested.return_value = False
        mock_tracker_cls.return_value = mock_tracker

        report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.skip_count == 1
        mock_tracker.mark_ingested.assert_called_once()

    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_ingest_unexpected_error_logs_and_increments(
        self,
        mock_qbit_cls: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Unexpected exception on QBitClient.__enter__ emits ingest_unexpected_error and increments error_count.

        The catch-all ``except Exception`` handler in ``run_ingest`` must emit
        the ``ingest_unexpected_error`` event with ``error_type`` set to the
        exception class name and must increment ``report.error_count``.

        Args:
            mock_qbit_cls: Patched QBitClient class.
            tmp_path: Pytest temporary directory fixture.
            caplog: Pytest log capture fixture.
        """
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=RuntimeError("boom"))
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        with caplog.at_level(logging.ERROR, logger="ingest"):
            report = run_ingest(settings, config=_make_config(tmp_path))

        assert report.error_count >= 1

        # Verify the ingest_unexpected_error event was emitted with error_type
        matching = [
            r for r in caplog.records if isinstance(r.msg, dict) and r.msg.get("event") == "ingest_unexpected_error"
        ]
        assert matching, "ingest event 'ingest_unexpected_error' was not emitted"
        # ``LogRecord.msg`` is typed as ``str | object`` so explicit narrowing
        # is required before reading dict keys.
        msg = matching[0].msg
        assert isinstance(msg, dict)
        assert msg.get("error_type") == "RuntimeError", (
            f"expected error_type='RuntimeError', got {msg.get('error_type')!r}"
        )
