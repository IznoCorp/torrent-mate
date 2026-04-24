"""Tests for E2E cleanup — staging, disk, torrent cleanup with safety checks."""

from unittest.mock import MagicMock

from qbittorrentapi.exceptions import NotFound404Error

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
        staging_root = tmp_path / "staging"
        staging = staging_root / "001-MOVIES" / "TestMovie"
        staging.mkdir(parents=True)
        (staging / "movie.mkv").write_text("fake")
        place_marker(staging, "s1")
        reg.register(staging)

        cleanup = TestCleanup(registry=reg, dry_run=True, staging_dir=staging_root)
        deleted = cleanup.cleanup_staging()

        assert len(deleted) == 1
        assert staging.exists()  # Not actually deleted in dry_run

    def test_real_cleanup_removes_files(self, tmp_path):
        """Real cleanup removes marked directories."""
        reg = TestRegistry(session_id="s2", base_dir=tmp_path)
        staging_root = tmp_path / "staging"
        staging = staging_root / "001-MOVIES" / "TestMovie"
        staging.mkdir(parents=True)
        (staging / "movie.mkv").write_text("fake")
        place_marker(staging, "s2")
        reg.register(staging)

        cleanup = TestCleanup(registry=reg, dry_run=False, staging_dir=staging_root)
        deleted = cleanup.cleanup_staging()

        assert len(deleted) == 1
        assert not staging.exists()

    def test_skips_without_marker(self, tmp_path):
        """Directories without valid markers are skipped."""
        reg = TestRegistry(session_id="s3", base_dir=tmp_path)
        staging_root = tmp_path / "staging"
        staging = staging_root / "001-MOVIES" / "RealMovie"
        staging.mkdir(parents=True)
        reg.register(staging)  # Registered but NO marker placed

        cleanup = TestCleanup(registry=reg, dry_run=False, staging_dir=staging_root)
        deleted = cleanup.cleanup_staging()

        assert len(deleted) == 0
        assert staging.exists()  # Not deleted — no marker

    def test_returns_empty_when_staging_dir_is_none(self, tmp_path):
        """Missing staging_dir scope is a safe no-op — nothing is deleted."""
        reg = TestRegistry(session_id="s4", base_dir=tmp_path)
        candidate = tmp_path / "somewhere" / "001-MOVIES" / "Movie"
        candidate.mkdir(parents=True)
        place_marker(candidate, "s4")
        reg.register(candidate)

        cleanup = TestCleanup(registry=reg, dry_run=False)  # no staging_dir
        deleted = cleanup.cleanup_staging()

        assert deleted == []
        assert candidate.exists()  # scope absent → no deletion

    def test_skips_path_outside_staging_dir(self, tmp_path):
        """Registered paths outside the configured scope are left alone."""
        reg = TestRegistry(session_id="s5", base_dir=tmp_path)
        staging_root = tmp_path / "staging"
        staging_root.mkdir()
        outside = tmp_path / "elsewhere" / "Movie"
        outside.mkdir(parents=True)
        place_marker(outside, "s5")
        reg.register(outside)

        cleanup = TestCleanup(registry=reg, dry_run=False, staging_dir=staging_root)
        deleted = cleanup.cleanup_staging()

        assert deleted == []
        assert outside.exists()  # scope excluded it

    def test_rejects_sibling_with_shared_prefix(self, tmp_path):
        """`stage_X` is NOT inside `stage` — guard against str.startswith regressions."""
        reg = TestRegistry(session_id="s6", base_dir=tmp_path)
        staging_root = tmp_path / "stage"
        staging_root.mkdir()
        sibling = tmp_path / "stage_X" / "Movie"
        sibling.mkdir(parents=True)
        place_marker(sibling, "s6")
        reg.register(sibling)

        cleanup = TestCleanup(registry=reg, dry_run=False, staging_dir=staging_root)
        deleted = cleanup.cleanup_staging()

        assert deleted == []
        assert sibling.exists()


class TestCleanupDisks:
    """Tests for cleanup_disks() triple safety verification."""

    def test_removes_with_valid_triple_check(self, tmp_path):
        """Deletes directory when all 3 checks pass."""
        reg = TestRegistry(session_id="d1", base_dir=tmp_path)
        disk_root = tmp_path / "storage" / "disk_a"
        disk_dir = disk_root / "films" / "TestMovie"
        disk_dir.mkdir(parents=True)
        place_marker(disk_dir, "d1")
        reg.register(disk_dir)

        cleanup = TestCleanup(registry=reg, dry_run=False, disk_paths=[disk_root])
        deleted = cleanup.cleanup_disks()

        assert len(deleted) == 1
        assert not disk_dir.exists()

    def test_blocks_without_marker(self, tmp_path):
        """Refuses to delete when marker is missing."""
        reg = TestRegistry(session_id="d2", base_dir=tmp_path)
        disk_root = tmp_path / "storage" / "disk_b"
        disk_dir = disk_root / "films" / "RealMovie"
        disk_dir.mkdir(parents=True)
        reg.register(disk_dir)  # No marker

        cleanup = TestCleanup(registry=reg, dry_run=False, disk_paths=[disk_root])
        deleted = cleanup.cleanup_disks()

        assert len(deleted) == 0
        assert disk_dir.exists()  # Safety block

    def test_blocks_wrong_uuid(self, tmp_path):
        """Refuses to delete when marker has wrong session_id."""
        reg = TestRegistry(session_id="d3", base_dir=tmp_path)
        disk_root = tmp_path / "storage" / "disk_c"
        disk_dir = disk_root / "films" / "OldTestMovie"
        disk_dir.mkdir(parents=True)
        place_marker(disk_dir, "WRONG-UUID")  # Different UUID
        reg.register(disk_dir)

        cleanup = TestCleanup(registry=reg, dry_run=False, disk_paths=[disk_root])
        deleted = cleanup.cleanup_disks()

        assert len(deleted) == 0
        assert disk_dir.exists()  # Safety block

    def test_returns_empty_when_disk_paths_empty(self, tmp_path):
        """Missing disk_paths scope is a safe no-op — nothing is deleted."""
        reg = TestRegistry(session_id="d4", base_dir=tmp_path)
        candidate = tmp_path / "storage" / "disk_a" / "films" / "Movie"
        candidate.mkdir(parents=True)
        place_marker(candidate, "d4")
        reg.register(candidate)

        cleanup = TestCleanup(registry=reg, dry_run=False)  # no disk_paths
        deleted = cleanup.cleanup_disks()

        assert deleted == []
        assert candidate.exists()

    def test_skips_path_outside_all_disks(self, tmp_path):
        """Registered paths under no configured disk root are left alone."""
        reg = TestRegistry(session_id="d5", base_dir=tmp_path)
        disk_root = tmp_path / "storage" / "disk_a"
        disk_root.mkdir(parents=True)
        outside = tmp_path / "elsewhere" / "Movie"
        outside.mkdir(parents=True)
        place_marker(outside, "d5")
        reg.register(outside)

        cleanup = TestCleanup(registry=reg, dry_run=False, disk_paths=[disk_root])
        deleted = cleanup.cleanup_disks()

        assert deleted == []
        assert outside.exists()


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
        """Logs warning but doesn't crash on a qBittorrent API error."""
        reg = TestRegistry(session_id="t3", base_dir=tmp_path)
        reg.register_torrent("bad_hash")

        mock_client = MagicMock()
        mock_client.torrents_delete.side_effect = NotFound404Error("not found")

        cleanup = TestCleanup(registry=reg, dry_run=False)
        count = cleanup.cleanup_torrents(client=mock_client)
        assert count == 0  # Failed, not counted


class TestCleanupAll:
    """Tests for cleanup_all() orchestration."""

    def test_cleanup_all_returns_summary(self, tmp_path):
        """cleanup_all returns counts for each cleanup type."""
        reg = TestRegistry(session_id="all1", base_dir=tmp_path)

        staging_root = tmp_path / "staging"
        staging = staging_root / "TestMovie"
        staging.mkdir(parents=True)
        place_marker(staging, "all1")
        reg.register(staging)

        cleanup = TestCleanup(registry=reg, dry_run=False, staging_dir=staging_root)
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
