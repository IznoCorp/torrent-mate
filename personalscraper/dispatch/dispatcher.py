"""Media dispatch orchestrator: replace, merge, and move operations.

Handles cross-filesystem transfers from staging area (A TRIER/) to
storage disks (Disk1-4) using rsync for reliability. Movies are
replaced (delete old + move new), TV shows are merged (add new episodes).

The category is provided by V4 verify (VerifyResult.category).
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.dispatch.disk_scanner import (
    choose_disk,
    get_disk_configs,
    get_disk_status,
)
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
from personalscraper.genre_mapper import GenreMapper
from personalscraper.verify.verifier import VerifyResult

logger = logging.getLogger(__name__)

# Minimum free space threshold (GB) before any dispatch
MIN_FREE_GB = 10.0


class DispatchError(Exception):
    """Error during dispatch operation."""


@dataclass
class DispatchResult:
    """Result of dispatching a single media item.

    Attributes:
        source: Source directory path.
        destination: Destination path (None if skipped).
        disk: Target disk name (None if skipped).
        action: Operation performed.
        reason: Reason for skip or error.
        files_copied: Number of files transferred.
        size_mb: Total size transferred in MB.
    """

    source: Path
    destination: Path | None = None
    disk: str | None = None
    action: str = "error"
    reason: str | None = None
    files_copied: int = 0
    size_mb: float = 0


class Dispatcher:
    """Orchestrate media dispatch to storage disks.

    Handles replace (movies), merge (TV shows), and new item placement
    using rsync for cross-filesystem transfers.

    Attributes:
        dry_run: If True, preview operations without transferring.
    """

    def __init__(
        self,
        settings: Settings,
        index: MediaIndex,
        dry_run: bool = False,
    ):
        """Initialize the dispatcher.

        Args:
            settings: Pipeline configuration with disk paths.
            index: Media index for existing media lookup.
            dry_run: If True, preview without modifying files.

        Raises:
            DispatchError: If rsync is not available.
        """
        self.settings = settings
        self.index = index
        self.dry_run = dry_run
        self._genre_mapper = GenreMapper()
        self._disk_configs = get_disk_configs(settings)

        # Verify rsync is available
        if not shutil.which("rsync"):
            raise DispatchError("rsync is required but not found in PATH")

    def process(
        self,
        verified: list[VerifyResult] | None = None,
        staging_dir: Path | None = None,
    ) -> list[DispatchResult]:
        """Process media items for dispatch.

        Two modes:
        1. Pipeline (verified provided): uses category from V4
        2. Standalone (staging_dir provided): scans and categorizes

        Args:
            verified: List of VerifyResult from V4 (pipeline mode).
            staging_dir: Staging directory path (standalone mode).

        Returns:
            List of DispatchResult for each item.

        Raises:
            ValueError: If both or neither arguments are provided.
        """
        if verified is not None and staging_dir is not None:
            raise ValueError("Provide either verified or staging_dir, not both")
        if verified is None and staging_dir is None:
            raise ValueError("Provide either verified or staging_dir")

        results: list[DispatchResult] = []

        if verified is not None:
            for vr in verified:
                if not vr.category:
                    results.append(DispatchResult(
                        source=vr.media_path, action="skipped",
                        reason="No category assigned",
                    ))
                    continue
                if vr.media_type == "movie":
                    results.append(self.dispatch_movie(vr.media_path, vr.category))
                else:
                    results.append(self.dispatch_tvshow(vr.media_path, vr.category))

        return results

    def dispatch_movie(self, movie_dir: Path, category: str) -> DispatchResult:
        """Dispatch a movie: replace if exists, move to best disk if new.

        Args:
            movie_dir: Source movie directory.
            category: Dispatch category from V4.

        Returns:
            DispatchResult with operation details.
        """
        result = DispatchResult(source=movie_dir)

        # Get disk statuses
        disk_statuses = [get_disk_status(c) for c in self._disk_configs]

        # Calculate source size
        item_size_gb = self._dir_size_gb(movie_dir)

        # Check index for existing copy
        existing = self.index.find(movie_dir.name, "movie")

        if existing:
            # Replace existing on the same disk
            dest = Path(existing.path)
            result.disk = existing.disk
            result.destination = dest
            if self.dry_run:
                result.action = "replaced"
                result.reason = f"[DRY RUN] Would replace on {existing.disk}"
                return result
            success = self._replace(movie_dir, dest)
            result.action = "replaced" if success else "error"
        else:
            # Move to best disk
            target = choose_disk(disk_statuses, category, MIN_FREE_GB, item_size_gb)
            if not target:
                result.action = "skipped"
                result.reason = f"No disk with enough space for category '{category}'"
                return result

            dest = target.config.path / category / movie_dir.name
            result.disk = target.config.name
            result.destination = dest
            if self.dry_run:
                result.action = "moved"
                result.reason = f"[DRY RUN] Would move to {target.config.name}"
                return result
            success = self._move_new(movie_dir, dest)
            result.action = "moved" if success else "error"

        # Update index
        if result.action in ("replaced", "moved") and result.destination:
            self.index.add(IndexEntry(
                name=movie_dir.name,
                disk=result.disk or "",
                category=category,
                path=str(result.destination),
                media_type="movie",
            ))

        return result

    def dispatch_tvshow(self, show_dir: Path, category: str) -> DispatchResult:
        """Dispatch a TV show: merge if exists, move to best disk if new.

        Args:
            show_dir: Source TV show directory.
            category: Dispatch category from V4.

        Returns:
            DispatchResult with operation details.
        """
        result = DispatchResult(source=show_dir)
        disk_statuses = [get_disk_status(c) for c in self._disk_configs]
        item_size_gb = self._dir_size_gb(show_dir)

        existing = self.index.find(show_dir.name, "tvshow")

        if existing:
            dest = Path(existing.path)
            result.disk = existing.disk
            result.destination = dest
            if self.dry_run:
                result.action = "merged"
                result.reason = f"[DRY RUN] Would merge on {existing.disk}"
                return result
            success = self._merge(show_dir, dest)
            result.action = "merged" if success else "error"
        else:
            target = choose_disk(disk_statuses, category, MIN_FREE_GB, item_size_gb)
            if not target:
                result.action = "skipped"
                result.reason = f"No disk with enough space for category '{category}'"
                return result

            dest = target.config.path / category / show_dir.name
            result.disk = target.config.name
            result.destination = dest
            if self.dry_run:
                result.action = "moved"
                result.reason = f"[DRY RUN] Would move to {target.config.name}"
                return result
            success = self._move_new(show_dir, dest)
            result.action = "moved" if success else "error"

        if result.action in ("merged", "moved") and result.destination:
            self.index.add(IndexEntry(
                name=show_dir.name,
                disk=result.disk or "",
                category=category,
                path=str(result.destination),
                media_type="tvshow",
            ))

        return result

    def _replace(self, source: Path, dest: Path) -> bool:
        """Crash-safe cross-filesystem replace via rsync.

        Steps:
        1. rsync source → dest.new.tmp/
        2. os.rename(dest, dest.old.tmp)
        3. os.rename(dest.new.tmp, dest)
        4. shutil.rmtree(dest.old.tmp)
        5. shutil.rmtree(source)

        Args:
            source: Source directory.
            dest: Destination directory to replace.

        Returns:
            True if successful.
        """
        tmp_new = dest.parent / f"{dest.name}.new.tmp"
        tmp_old = dest.parent / f"{dest.name}.old.tmp"

        try:
            if not self._rsync(source, tmp_new):
                return False
            if dest.exists():
                os.rename(dest, tmp_old)
            os.rename(tmp_new, dest)
            if tmp_old.exists():
                shutil.rmtree(tmp_old)
            shutil.rmtree(source)
            return True
        except OSError as e:
            logger.error("Replace failed: %s", e)
            return False

    def _merge(self, source: Path, dest: Path) -> bool:
        """Merge TV show with backup for existing files.

        Args:
            source: Source TV show directory.
            dest: Existing destination directory.

        Returns:
            True if successful.
        """
        try:
            if not self._rsync(source, dest):
                return False
            # Verify transfer
            if self._verify_transfer(source, dest):
                shutil.rmtree(source)
                return True
            logger.error("Merge verification failed for %s", source.name)
            return False
        except OSError as e:
            logger.error("Merge failed: %s", e)
            return False

    def _move_new(self, source: Path, dest: Path) -> bool:
        """Move a new media item to disk via rsync.

        Args:
            source: Source directory.
            dest: Destination directory (should not exist).

        Returns:
            True if successful.
        """
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not self._rsync(source, dest):
                return False
            if self._verify_transfer(source, dest):
                shutil.rmtree(source)
                return True
            logger.error("Transfer verification failed for %s", source.name)
            return False
        except OSError as e:
            logger.error("Move failed: %s", e)
            return False

    def _rsync(self, source: Path, dest: Path, delete: bool = False) -> bool:
        """Execute rsync for cross-filesystem transfer.

        Args:
            source: Source path (trailing / added for contents).
            dest: Destination path.
            delete: If True, delete extraneous files in dest.

        Returns:
            True if rsync succeeded (returncode 0).
        """
        cmd = ["rsync", "-a", "--partial", "--checksum"]
        if delete:
            cmd.append("--delete")
        cmd.extend([f"{source}/", str(dest)])

        logger.info("rsync: %s → %s", source.name, dest)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3600,
            )
            if proc.returncode != 0:
                logger.error("rsync failed (rc=%d): %s", proc.returncode, proc.stderr)
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("rsync timed out for %s", source.name)
            return False

    def _verify_transfer(self, source: Path, dest: Path) -> bool:
        """Verify file sizes match after transfer.

        Args:
            source: Source directory.
            dest: Destination directory.

        Returns:
            True if all file sizes match.
        """
        for src_file in source.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(source)
            dst_file = dest / rel
            if not dst_file.exists():
                logger.warning("Missing after transfer: %s", rel)
                return False
            if src_file.stat().st_size != dst_file.stat().st_size:
                logger.warning("Size mismatch: %s", rel)
                return False
        return True

    @staticmethod
    def _dir_size_gb(directory: Path) -> float:
        """Calculate total size of a directory in GB.

        Args:
            directory: Directory to measure.

        Returns:
            Size in GB.
        """
        total = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
        return total / (1024 ** 3)
