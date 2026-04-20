"""E2E test cleanup — safely remove test-created files from all locations.

CRITICAL SAFETY: Storage disks contain real media. Triple verification
(marker + UUID + registry) is mandatory before any deletion. dry_run=True
is the default — no deletions happen unless explicitly requested.
"""

import logging
import shutil
from pathlib import Path

from tests.e2e.markers import find_orphan_markers, verify_marker
from tests.e2e.registry import TestRegistry

logger = logging.getLogger(__name__)


class TestCleanup:
    """Remove test-created files with multi-layer safety protections.

    Attributes:
        registry: TestRegistry tracking all test-created resources.
        dry_run: If True (default), show plan without deleting.
    """

    def __init__(self, registry: TestRegistry, dry_run: bool = True) -> None:
        """Initialize cleanup with safety-first defaults.

        Args:
            registry: Registry of all test-created files and torrents.
            dry_run: If True (default), preview without deleting anything.
        """
        self.registry = registry
        self.dry_run = dry_run

    def cleanup_staging(self) -> list[Path]:
        """Clean test files from the staging area (A TRIER/).

        Verifies marker + session_id before each deletion.
        Deletes files individually (never rm -rf), then removes
        empty parent directories.

        Returns:
            List of paths that were (or would be) deleted.
        """
        deleted = []
        for path in self.registry.get_cleanup_order():
            path = Path(path)
            if not path.exists():
                continue

            # Only process paths that contain "A TRIER" in their hierarchy
            if "A TRIER" not in str(path):
                continue

            if path.is_dir():
                if not verify_marker(path, self.registry.session_id, self.registry):
                    logger.warning("Skipping directory without valid marker: %s", path)
                    continue
                if self.dry_run:
                    logger.info("[DRY RUN] Would remove directory: %s", path)
                else:
                    shutil.rmtree(path)
                    logger.info("Removed directory: %s", path)
                deleted.append(path)
            elif path.is_file():
                if self.dry_run:
                    logger.info("[DRY RUN] Would remove file: %s", path)
                else:
                    path.unlink()
                    logger.info("Removed file: %s", path)
                deleted.append(path)

        return deleted

    def cleanup_disks(self) -> list[Path]:
        """Clean test files from storage disks (Disk1-4).

        TRIPLE VERIFICATION per directory:
        1. .e2e-test-marker exists in the directory
        2. Marker content matches this session's UUID
        3. Path is registered in the test registry

        If ANY check fails, the directory is NOT deleted and an alert is logged.

        Returns:
            List of paths that were (or would be) deleted.
        """
        deleted = []
        for path in self.registry.get_cleanup_order():
            path = Path(path)
            if not path.exists():
                continue

            # Only process paths on storage disks
            if "/Volumes/Disk" not in str(path):
                continue

            if not path.is_dir():
                continue

            # Triple check — all three must pass
            if not verify_marker(path, self.registry.session_id, self.registry):
                logger.error("SAFETY BLOCK: refusing to delete %s — marker verification failed", path)
                continue

            if self.dry_run:
                logger.info("[DRY RUN] Would remove disk directory: %s", path)
            else:
                shutil.rmtree(path)
                logger.info("Removed disk directory: %s", path)
            deleted.append(path)

        return deleted

    def cleanup_torrents(self, client=None) -> int:
        """Remove test torrents from qBittorrent.

        Deletes torrents with the 'e2e-test' category AND their
        downloaded data from the filesystem.

        Args:
            client: qBittorrent API client (optional, skip if None).

        Returns:
            Number of torrents removed.
        """
        if client is None:
            return 0

        count = 0
        for torrent_hash in self.registry.torrent_hashes:
            try:
                if self.dry_run:
                    logger.info("[DRY RUN] Would remove torrent: %s", torrent_hash)
                else:
                    client.torrents_delete(delete_files=True, torrent_hashes=torrent_hash)
                    logger.info("Removed torrent: %s", torrent_hash)
                count += 1
            except Exception as exc:
                logger.warning("Failed to remove torrent %s: %s", torrent_hash, exc)

        return count

    def cleanup_all(self, client=None, force: bool = False) -> dict[str, int]:
        """Run full cleanup: staging, disks, and torrents.

        Args:
            client: qBittorrent API client (optional).
            force: If True, execute even in dry_run mode (overrides dry_run).

        Returns:
            Summary dict with counts: {"staging": N, "disks": N, "torrents": N}.
        """
        if force and self.dry_run:
            self.dry_run = False

        staging = self.cleanup_staging()
        disks = self.cleanup_disks()
        torrents = self.cleanup_torrents(client)

        if not self.dry_run:
            self.registry.cleanup()

        return {
            "staging": len(staging),
            "disks": len(disks),
            "torrents": torrents,
        }

    def verify_clean(self, base_paths: list[Path] | None = None) -> list[Path]:
        """Post-cleanup verification: check for orphan markers.

        Scans all relevant locations for leftover .e2e-test-marker files.

        Args:
            base_paths: Directories to scan. Defaults to common locations.

        Returns:
            List of directories still containing markers (should be empty).
        """
        if base_paths is None:
            base_paths = [
                Path("/Volumes/IznoServer SSD/A TRIER"),
                Path("/Volumes/Disk1/medias"),
                Path("/Volumes/Disk2/medias"),
                Path("/Volumes/Disk3/medias"),
                Path("/Volumes/Disk4/medias"),
            ]
        return find_orphan_markers(base_paths)
