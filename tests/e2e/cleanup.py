"""E2E test cleanup — safely remove test-created files from all locations.

CRITICAL SAFETY: Storage disks contain real media. Triple verification
(marker + UUID + registry) is mandatory before any deletion. dry_run=True
is the default — no deletions happen unless explicitly requested.
"""

import logging
import shutil
from pathlib import Path

from qbittorrentapi.exceptions import APIError

from tests.e2e.markers import find_orphan_markers, verify_marker
from tests.e2e.registry import TestRegistry

logger = logging.getLogger(__name__)


class TestCleanup:
    """Remove test-created files with multi-layer safety protections.

    Attributes:
        registry: TestRegistry tracking all test-created resources.
        dry_run: If True (default), show plan without deleting.
        staging_dir: Staging directory bound for cleanup_staging() safety scope.
            If None, cleanup_staging() skips every path.
        disk_paths: Storage-disk roots bound for cleanup_disks() safety scope.
            If empty, cleanup_disks() skips every path.
    """

    def __init__(
        self,
        registry: TestRegistry,
        dry_run: bool = True,
        staging_dir: Path | None = None,
        disk_paths: list[Path] | None = None,
    ) -> None:
        """Initialize cleanup with safety-first defaults.

        Args:
            registry: Registry of all test-created files and torrents.
            dry_run: If True (default), preview without deleting anything.
            staging_dir: Staging root. Only paths under this directory are
                considered by cleanup_staging(). When None, staging cleanup
                is a no-op (safe default).
            disk_paths: Storage-disk roots. Only paths under one of these
                directories are considered by cleanup_disks(). When empty,
                disk cleanup is a no-op (safe default).
        """
        self.registry = registry
        self.dry_run = dry_run
        self.staging_dir = Path(staging_dir) if staging_dir is not None else None
        self.disk_paths = [Path(p) for p in (disk_paths or [])]

    def _is_within(self, path: Path, root: Path) -> bool:
        """Return True when ``path`` is inside ``root`` after resolution.

        Both ``path`` and ``root`` are resolved via ``Path.resolve()`` before
        the relative_to check, which means:

        - **Symlinks are followed.** A symlink that points inside ``root``
          is considered in-scope; a symlink whose target lives outside
          ``root`` is rejected, even if the symlink's lexical path is under
          ``root``. Callers that need lexical (non-followed) matching must
          compare paths before calling ``.resolve()``.
        - **Non-existent paths are permitted.** ``Path.resolve()`` is called
          with its default ``strict=False``, which returns a best-effort
          absolute path for non-existent inputs without raising, so this
          helper does not require the path to exist on disk.
        - **Filesystem errors (permission denied, symlink loops) return
          False** — conservatively excluding the path from the scope rather
          than propagating the error to callers. A ``debug`` trace is
          emitted so orphan-file investigations can still surface the cause.

        Args:
            path: Candidate path to test.
            root: Scope root directory.

        Returns:
            True iff ``path`` resolves to a location inside ``root``.
        """
        try:
            path.resolve().relative_to(root.resolve())
        except (ValueError, OSError) as exc:
            logger.debug("_is_within: exclude %s under %s: %s", path, root, exc)
            return False
        return True

    def cleanup_staging(self) -> list[Path]:
        """Clean test files from the staging area.

        Verifies marker + session_id before each deletion.
        Deletes files individually (never rm -rf), then removes
        empty parent directories.

        Returns:
            List of paths that were (or would be) deleted.
        """
        deleted: list[Path] = []
        if self.staging_dir is None:
            if self.registry.get_cleanup_order():
                logger.warning(
                    "cleanup_staging skipped: no staging_dir configured "
                    "(registry has %d path(s) that will NOT be cleaned)",
                    len(list(self.registry.get_cleanup_order())),
                )
            return deleted
        for path in self.registry.get_cleanup_order():
            path = Path(path)
            if not path.exists():
                continue

            # Safety: only process paths inside the configured staging root.
            if not self._is_within(path, self.staging_dir):
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
        """Clean test files from the configured storage disks.

        TRIPLE VERIFICATION per directory:
        1. .e2e-test-marker exists in the directory
        2. Marker content matches this session's UUID
        3. Path is registered in the test registry

        If ANY check fails, the directory is NOT deleted and an alert is logged.

        Returns:
            List of paths that were (or would be) deleted.
        """
        deleted: list[Path] = []
        if not self.disk_paths:
            if self.registry.get_cleanup_order():
                logger.warning(
                    "cleanup_disks skipped: no disk_paths configured "
                    "(registry has %d path(s) that will NOT be cleaned)",
                    len(list(self.registry.get_cleanup_order())),
                )
            return deleted
        for path in self.registry.get_cleanup_order():
            path = Path(path)
            if not path.exists():
                continue

            # Safety: only process paths under one of the configured disk roots.
            if not any(self._is_within(path, root) for root in self.disk_paths):
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
            except APIError as exc:
                # Narrow to qBittorrent's API-error hierarchy: auth, HTTP, connection,
                # not-found. Programming bugs (AttributeError, TypeError) must bubble
                # up instead of being silently swallowed as a warning.
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

    def verify_clean(self, base_paths: list[Path]) -> list[Path]:
        """Post-cleanup verification: check for orphan markers.

        Scans the provided locations for leftover .e2e-test-marker files.
        Caller must supply the base paths from their Config/Settings (no
        hardcoded personal paths).

        Args:
            base_paths: Directories to scan (required). Typically the staging
                directory and configured storage disks from Config.

        Returns:
            List of directories still containing markers (should be empty).
        """
        return find_orphan_markers(base_paths)
