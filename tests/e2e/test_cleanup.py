"""Tests for E2E cleanup — staging, disk, torrent cleanup with safety checks."""

from unittest.mock import MagicMock

from tests.e2e.cleanup import TestCleanup
from tests.e2e.markers import place_marker
from tests.e2e.registry import TestRegistry


def _make_test_dir(base, name, session_id, registry):
    """Helper: create a directory with marker and register it."""
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "file.mkv").write_text("fake")
    place_marker(d, session_id)
    registry.register(d)
    return d


class TestCleanupStaging:
    """Tests for cleanup_staging()."""

    def test_dry_run_does_not_delete(self, tmp_path):
        """Dry run shows plan but does not delete files."""
        reg = TestRegistry(session_id="s1", base_dir=tmp_path)
        # Simulate A TRIER path
        staging = tmp_path / "A TRIER" / "001-MOVIES" / "TestMovie"
        staging.mkdir(parents=True)
        (staging / "movie.mkv").write_text("fake")
        place_marker(staging, "s1")
        reg.register(staging)

        cleanup = TestCleanup(registry=reg, dry_run=True)
        deleted = cleanup.cleanup_staging()

        assert len(deleted) == 1
        assert staging.exists()  # Not actually deleted in dry_run

    def test_real_cleanup_removes_files(self, tmp_path):
        """Real cleanup removes marked directories."""
        reg = TestRegistry(session_id="s2", base_dir=tmp_path)
        staging = tmp_path / "A TRIER" / "001-MOVIES" / "TestMovie"
        staging.mkdir(parents=True)
        (staging / "movie.mkv").write_text("fake")
        place_marker(staging, "s2")
        reg.register(staging)

        cleanup = TestCleanup(registry=reg, dry_run=False)
        deleted = cleanup.cleanup_staging()

        assert len(deleted) == 1
        assert not staging.exists()

    def test_skips_without_marker(self, tmp_path):
        """Directories without valid markers are skipped."""
        reg = TestRegistry(session_id="s3", base_dir=tmp_path)
        staging = tmp_path / "A TRIER" / "001-MOVIES" / "RealMovie"
        staging.mkdir(parents=True)
        reg.register(staging)  # Registered but NO marker placed

        cleanup = TestCleanup(registry=reg, dry_run=False)
        deleted = cleanup.cleanup_staging()

        assert len(deleted) == 0
        assert staging.exists()  # Not deleted — no marker


class TestCleanupDisks:
    """Tests for cleanup_disks() triple safety verification."""

    def test_removes_with_valid_triple_check(self, tmp_path):
        """Deletes directory when all 3 checks pass."""
        reg = TestRegistry(session_id="d1", base_dir=tmp_path)
        # Simulate Disk path
        disk_dir = tmp_path / "Volumes" / "Disk1" / "films" / "TestMovie"
        disk_dir.mkdir(parents=True)
        place_marker(disk_dir, "d1")
        reg.register(disk_dir)

        cleanup = TestCleanup(registry=reg, dry_run=False)
        deleted = cleanup.cleanup_disks()

        assert len(deleted) == 1
        assert not disk_dir.exists()

    def test_blocks_without_marker(self, tmp_path):
        """Refuses to delete when marker is missing."""
        reg = TestRegistry(session_id="d2", base_dir=tmp_path)
        disk_dir = tmp_path / "Volumes" / "Disk2" / "films" / "RealMovie"
        disk_dir.mkdir(parents=True)
        reg.register(disk_dir)  # No marker

        cleanup = TestCleanup(registry=reg, dry_run=False)
        deleted = cleanup.cleanup_disks()

        assert len(deleted) == 0
        assert disk_dir.exists()  # Safety block

    def test_blocks_wrong_uuid(self, tmp_path):
        """Refuses to delete when marker has wrong session_id."""
        reg = TestRegistry(session_id="d3", base_dir=tmp_path)
        disk_dir = tmp_path / "Volumes" / "Disk3" / "films" / "OldTestMovie"
        disk_dir.mkdir(parents=True)
        place_marker(disk_dir, "WRONG-UUID")  # Different UUID
        reg.register(disk_dir)

        cleanup = TestCleanup(registry=reg, dry_run=False)
        deleted = cleanup.cleanup_disks()

        assert len(deleted) == 0
        assert disk_dir.exists()  # Safety block


class TestCleanupTorrents:
    """Tests for cleanup_torrents()."""

    def test_removes_registered_torrents(self, tmp_path):
        """Deletes registered torrent hashes from qBit."""
        reg = TestRegistry(session_id="t1", base_dir=tmp_path)
        reg.register_torrent("hash1")
        reg.register_torrent("hash2")

        mock_client = MagicMock()
        cleanup = TestCleanup(registry=reg, dry_run=False)
        count = cleanup.cleanup_torrents(client=mock_client)

        assert count == 2
        assert mock_client.torrents_delete.call_count == 2

    def test_skips_when_no_client(self, tmp_path):
        """Returns 0 when no client provided."""
        reg = TestRegistry(session_id="t2", base_dir=tmp_path)
        reg.register_torrent("hash1")

        cleanup = TestCleanup(registry=reg, dry_run=False)
        assert cleanup.cleanup_torrents(client=None) == 0

    def test_handles_delete_failure(self, tmp_path):
        """Logs warning but doesn't crash on delete failure."""
        reg = TestRegistry(session_id="t3", base_dir=tmp_path)
        reg.register_torrent("bad_hash")

        mock_client = MagicMock()
        mock_client.torrents_delete.side_effect = Exception("not found")

        cleanup = TestCleanup(registry=reg, dry_run=False)
        count = cleanup.cleanup_torrents(client=mock_client)
        assert count == 0  # Failed, not counted


class TestCleanupAll:
    """Tests for cleanup_all() orchestration."""

    def test_cleanup_all_returns_summary(self, tmp_path):
        """cleanup_all returns counts for each cleanup type."""
        reg = TestRegistry(session_id="all1", base_dir=tmp_path)

        # Create a staging dir
        staging = tmp_path / "A TRIER" / "TestMovie"
        staging.mkdir(parents=True)
        place_marker(staging, "all1")
        reg.register(staging)

        cleanup = TestCleanup(registry=reg, dry_run=False)
        result = cleanup.cleanup_all()

        assert result["staging"] == 1
        assert result["disks"] == 0
        assert result["torrents"] == 0


class TestVerifyClean:
    """Tests for verify_clean()."""

    def test_finds_orphans(self, tmp_path):
        """Detects leftover markers after incomplete cleanup."""
        reg = TestRegistry(session_id="v1", base_dir=tmp_path)
        orphan = tmp_path / "leftover"
        orphan.mkdir()
        place_marker(orphan, "v1")

        cleanup = TestCleanup(registry=reg, dry_run=True)
        orphans = cleanup.verify_clean(base_paths=[tmp_path])
        assert orphan in orphans

    def test_clean_state(self, tmp_path):
        """Returns empty when no markers remain."""
        reg = TestRegistry(session_id="v2", base_dir=tmp_path)
        cleanup = TestCleanup(registry=reg, dry_run=True)
        assert cleanup.verify_clean(base_paths=[tmp_path]) == []
