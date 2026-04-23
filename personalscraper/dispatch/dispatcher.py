"""Media dispatch orchestrator: replace, merge, and move operations.

Handles cross-filesystem transfers from staging area (A TRIER/) to
storage disks using rsync for reliability. Movies are replaced
(delete old + move new), TV shows are merged (add new episodes).

Dispatcher accepts ``Config`` as first argument. Category routing uses
``conf.resolver.pick_disk_for`` and ``conf.resolver.folder_for``. The
``category`` parameter is a category_id (e.g. ``"movies"``) rather than
a legacy label (e.g. ``"films"``).
"""

import logging
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from personalscraper.conf import resolver
from personalscraper.conf.models import Config
from personalscraper.config import Settings
from personalscraper.dispatch.disk_scanner import get_disk_configs, get_disk_status
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
from personalscraper.text_utils import _FILENAME_ILLEGAL
from personalscraper.verify.verifier import VerifyResult


def _force_rmtree(path: Path) -> None:
    """Remove a directory tree, handling macOS permission errors.

    Uses an onerror handler that adds owner rwx permissions before
    retrying deletion. Handles .actors and other macOS-protected dirs.
    Raises OSError if the directory could not be fully removed.

    Args:
        path: Directory to remove.

    Raises:
        OSError: If files remain after all retry attempts.
    """
    errors: list[tuple[str, OSError]] = []

    def _on_error(func: Callable[..., Any], fpath: str, exc: Any) -> None:
        """Add owner rwx permissions and retry deletion.

        Args:
            func: The function that raised the exception (os.remove, etc.).
            fpath: Path of the file/dir that could not be removed.
            exc: Exception info — tuple (type, value, tb) for onerror,
                or BaseException for onexc (Python 3.12+).
        """
        try:
            os.chmod(fpath, stat.S_IRWXU)
            func(fpath)
        except OSError as e:
            errors.append((fpath, e))

    # Python 3.12 deprecated onerror in favor of onexc
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_on_error)
    else:
        shutil.rmtree(path, onerror=_on_error)

    if errors and path.exists():
        for fpath, err in errors[:5]:
            logging.getLogger(__name__).warning(
                "rmtree: could not remove %s: %s",
                fpath,
                err,
            )
        raise OSError(f"_force_rmtree incomplete for {path}: {len(errors)} file(s) could not be removed")


logger = logging.getLogger(__name__)


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

    Accepts ``Config`` as first argument; routing uses
    ``conf.resolver.pick_disk_for`` and ``conf.resolver.folder_for``
    instead of the removed ``choose_disk()`` + DISK_CATEGORIES.

    Attributes:
        dry_run: If True, preview operations without transferring.
    """

    def __init__(
        self,
        config: Config,
        settings: Settings,
        index: MediaIndex,
        dry_run: bool = False,
    ):
        """Initialize the dispatcher.

        Args:
            config: Loaded Config with disk definitions and category mapping.
            settings: Pipeline settings with numeric thresholds and credentials.
            index: Media index for existing media lookup.
            dry_run: If True, preview without modifying files.

        Raises:
            DispatchError: If rsync is not available.
        """
        self.config = config
        self.settings = settings
        self.index = index
        self.dry_run = dry_run
        self._disk_configs = get_disk_configs(config)

        # Verify rsync is available
        if not shutil.which("rsync"):
            raise DispatchError("rsync is required but not found in PATH")

    def _cleanup_orphan_temps(self) -> int:
        """Clean up orphan temporary directories from previous failed runs.

        Scans all storage disks for _tmp_dispatch_* and .merge_backup/
        directories that were left behind by interrupted dispatch operations.

        Returns:
            Number of orphan directories cleaned up.
        """
        cleaned = 0
        for config in self._disk_configs:
            if not config.path.exists():
                continue
            try:
                category_dirs = list(config.path.iterdir())
            except OSError as e:
                logger.warning(
                    "Cannot scan %s for orphans: %s",
                    config.id,
                    e,
                )
                continue
            for category_dir in category_dirs:
                if not category_dir.is_dir():
                    continue
                try:
                    items = list(category_dir.iterdir())
                except OSError as e:
                    logger.warning(
                        "Cannot scan %s for orphans: %s",
                        category_dir,
                        e,
                    )
                    continue
                for item in items:
                    if not item.is_dir():
                        continue
                    # Clean _tmp_dispatch_* orphans
                    if item.name.startswith("_tmp_dispatch_"):
                        logger.warning("Cleaning orphan tmp: %s", item)
                        try:
                            _force_rmtree(item)
                            cleaned += 1
                        except OSError as e:
                            logger.error("Failed to clean orphan %s: %s", item, e)
                    # Clean .merge_backup/ orphans inside media dirs
                    backup = item / ".merge_backup"
                    if backup.exists():
                        logger.warning("Cleaning orphan merge backup: %s", backup)
                        try:
                            _force_rmtree(backup)
                            cleaned += 1
                        except OSError as e:
                            logger.error("Failed to clean backup %s: %s", backup, e)
        if cleaned:
            logger.info("Cleaned %d orphan temp directories", cleaned)
        return cleaned

    def process(
        self,
        verified: list[VerifyResult],
    ) -> list[DispatchResult]:
        """Process verified media items for dispatch.

        Cleans up orphan temp directories from previous runs before
        dispatching each item to the appropriate storage disk.

        Args:
            verified: List of VerifyResult from the verify step.

        Returns:
            List of DispatchResult for each item.
        """
        # Clean up orphan temp dirs from previous failed runs
        self._cleanup_orphan_temps()

        results: list[DispatchResult] = []

        for vr in verified:
            if not vr.category:
                results.append(
                    DispatchResult(
                        source=vr.media_path,
                        action="skipped",
                        reason="No category assigned",
                    )
                )
                continue
            if vr.media_type == "movie":
                results.append(self.dispatch_movie(vr.media_path, vr.category))
            else:
                results.append(self.dispatch_tvshow(vr.media_path, vr.category))

        return results

    def _resolve_existing_on_filesystem(
        self,
        name: str,
        media_type: str,
    ) -> IndexEntry | None:
        """Resolve an existing entry for ``name`` validated against the filesystem.

        media_index can drift when the user moves folders manually between disks.
        This helper trusts the filesystem over the index :

        1. Look up ``name`` in the in-memory index.
        2. If the stored path still exists → return the entry unchanged.
        3. If not → scan every configured disk for a directory named exactly
           ``name`` (under any category folder). If found, return a synthetic
           IndexEntry pointing at the real location (disk_id + path resolved
           from filesystem). The in-memory index is NOT mutated — persistence
           is library-scan's job, not dispatch's.
        4. If nowhere on any disk → return ``None`` (truly new).

        Args:
            name: Directory name (source folder basename).
            media_type: ``"movie"`` or ``"tvshow"``.

        Returns:
            IndexEntry with a validated (existing) path, or ``None`` if the
            item is not present on any disk.
        """
        entry = self.index.find(name, media_type, fuzzy_config=self.config.fuzzy_match)
        if entry is not None and Path(entry.path).exists():
            return entry

        # Index says a location that doesn't exist — scan disks for reality.
        for disk_cfg in self._disk_configs:
            if not disk_cfg.path.exists():
                continue
            try:
                category_dirs = [p for p in disk_cfg.path.iterdir() if p.is_dir()]
            except OSError:
                continue
            for category_dir in category_dirs:
                candidate = category_dir / name
                if candidate.is_dir():
                    if entry is not None:
                        logger.warning(
                            "media_index drift detected for '%s': index says %s at %s, "
                            "filesystem has it on %s — using filesystem truth",
                            name,
                            entry.disk,
                            entry.path,
                            disk_cfg.id,
                        )
                    return IndexEntry(
                        name=name,
                        disk=disk_cfg.id,
                        category=(entry.category if entry else category_dir.name),
                        path=str(candidate),
                        media_type=media_type,
                    )

        if entry is not None:
            logger.warning(
                "media_index stale entry for '%s': path %s does not exist on any disk, "
                "treating as NEW (dispatch will pick best disk)",
                name,
                entry.path,
            )
        return None

    def dispatch_movie(self, movie_dir: Path, category_id: str) -> DispatchResult:
        """Dispatch a movie: replace if exists, move to best disk if new.

        Args:
            movie_dir: Source movie directory.
            category_id: Category ID (e.g. ``"movies"``) from the classifier.

        Returns:
            DispatchResult with operation details.
        """
        result = DispatchResult(source=movie_dir)

        # Pre-scan for NTFS-illegal filenames before any rsync operation
        if self._has_ntfs_illegal_names(movie_dir):
            result.action = "skipped"
            result.reason = f"NTFS-illegal filenames in {movie_dir.name}. Run 'personalscraper process' to sanitize."
            logger.error("dispatch_ntfs_illegal: %s", movie_dir)
            return result

        # Get disk statuses keyed by disk ID for resolver
        disk_statuses = [get_disk_status(c) for c in self._disk_configs]
        free_space_by_id = {s.config.id: s.free_space_gb if s.is_mounted else 0.0 for s in disk_statuses}

        # Calculate source size
        item_size_gb = self._dir_size_gb(movie_dir)

        # Check index for existing copy, validated against filesystem to avoid
        # duplicating when the user has moved the folder between disks manually.
        existing = self._resolve_existing_on_filesystem(movie_dir.name, "movie")

        if existing:
            # Replace existing on the same disk (disk stored as disk_id in the index)
            dest = Path(existing.path)
            result.disk = existing.disk
            result.destination = dest

            # Check if disk has enough space for the replacement
            threshold = max(self.settings.min_free_space_disk_gb, item_size_gb * 1.5)
            disk_free = free_space_by_id.get(existing.disk, 0.0)
            if disk_free < threshold:
                result.action = "skipped"
                result.reason = f"Disk {existing.disk} full, cannot replace"
                return result

            if self.dry_run:
                result.action = "replaced"
                result.reason = f"[DRY RUN] Would replace on {existing.disk}"
                return result
            success = self._replace(movie_dir, dest)
            result.action = "replaced" if success else "error"
        else:
            # Move to best disk via resolver
            target_disk = resolver.pick_disk_for(
                self.config,
                category_id,
                free_space_by_id,
                self.settings.min_free_space_disk_gb,
                item_size_gb,
            )
            if not target_disk:
                result.action = "skipped"
                result.reason = f"No disk with enough space for category '{category_id}'"
                return result

            dest = resolver.folder_for(self.config, target_disk, category_id) / movie_dir.name
            result.disk = target_disk.id
            result.destination = dest
            if self.dry_run:
                result.action = "moved"
                result.reason = f"[DRY RUN] Would move to {target_disk.id}"
                return result
            success = self._move_new(movie_dir, dest)
            result.action = "moved" if success else "error"

        # Update index with current IDs
        if result.action in ("replaced", "moved") and result.destination:
            self.index.add(
                IndexEntry(
                    name=movie_dir.name,
                    disk=result.disk or "",
                    category=category_id,
                    path=str(result.destination),
                    media_type="movie",
                )
            )

        return result

    def dispatch_tvshow(self, show_dir: Path, category_id: str) -> DispatchResult:
        """Dispatch a TV show: merge if exists, move to best disk if new.

        Args:
            show_dir: Source TV show directory.
            category_id: Category ID (e.g. ``"tv_shows"``) from the classifier.

        Returns:
            DispatchResult with operation details.
        """
        result = DispatchResult(source=show_dir)

        # Pre-scan for NTFS-illegal filenames before any rsync operation
        if self._has_ntfs_illegal_names(show_dir):
            result.action = "skipped"
            result.reason = f"NTFS-illegal filenames in {show_dir.name}. Run 'personalscraper process' to sanitize."
            logger.error("dispatch_ntfs_illegal: %s", show_dir)
            return result

        disk_statuses = [get_disk_status(c) for c in self._disk_configs]
        free_space_by_id = {s.config.id: s.free_space_gb if s.is_mounted else 0.0 for s in disk_statuses}
        item_size_gb = self._dir_size_gb(show_dir)

        # Check index for existing copy, validated against filesystem to avoid
        # duplicating when the user has moved the folder between disks manually.
        existing = self._resolve_existing_on_filesystem(show_dir.name, "tvshow")

        if existing:
            dest = Path(existing.path)
            result.disk = existing.disk
            result.destination = dest

            # Check if disk has enough space for the merge
            threshold = max(self.settings.min_free_space_disk_gb, item_size_gb * 1.5)
            disk_free = free_space_by_id.get(existing.disk, 0.0)
            if disk_free < threshold:
                result.action = "skipped"
                result.reason = f"Disk {existing.disk} full, cannot merge"
                return result

            if self.dry_run:
                result.action = "merged"
                result.reason = f"[DRY RUN] Would merge on {existing.disk}"
                return result
            success = self._merge(show_dir, dest)
            result.action = "merged" if success else "error"
        else:
            # Move to best disk via resolver
            target_disk = resolver.pick_disk_for(
                self.config,
                category_id,
                free_space_by_id,
                self.settings.min_free_space_disk_gb,
                item_size_gb,
            )
            if not target_disk:
                result.action = "skipped"
                result.reason = f"No disk with enough space for category '{category_id}'"
                return result

            dest = resolver.folder_for(self.config, target_disk, category_id) / show_dir.name
            result.disk = target_disk.id
            result.destination = dest
            if self.dry_run:
                result.action = "moved"
                result.reason = f"[DRY RUN] Would move to {target_disk.id}"
                return result
            success = self._move_new(show_dir, dest)
            result.action = "moved" if success else "error"

        if result.action in ("merged", "moved") and result.destination:
            self.index.add(
                IndexEntry(
                    name=show_dir.name,
                    disk=result.disk or "",
                    category=category_id,
                    path=str(result.destination),
                    media_type="tvshow",
                )
            )

        return result

    def _replace(self, source: Path, dest: Path) -> bool:
        """Crash-safe cross-filesystem replace via rsync.

        Phase 1 (Transfer): rsync source → dest.new.tmp/
        Phase 2 (Atomic swap): rename dest → dest.old.tmp, rename dest.new.tmp → dest
        Phase 3 (Cleanup, non-critical): remove dest.old.tmp and source

        Phases 1-2 must succeed; Phase 3 failures are logged as warnings
        since the replace is already complete at that point. If Phase 2
        fails mid-way, the original is restored from dest.old.tmp.

        Args:
            source: Source directory.
            dest: Destination directory to replace.

        Returns:
            True if successful.
        """
        tmp_new = dest.parent / f"{dest.name}.new.tmp"
        tmp_old = dest.parent / f"{dest.name}.old.tmp"

        # Phase 1: Transfer (critical — must succeed)
        if not self._rsync(source, tmp_new):
            try:
                if tmp_new.exists():
                    _force_rmtree(tmp_new)
            except OSError as e:
                logger.warning("Failed to clean partial tmp_new %s: %s", tmp_new, e)
            return False

        # Phase 2: Atomic swap (critical — rollback on failure)
        try:
            if dest.exists():
                os.rename(dest, tmp_old)
            os.rename(tmp_new, dest)
        except OSError as e:
            logger.error(
                "Replace failed: %s (tmp_old=%s, tmp_new=%s)",
                e,
                tmp_old,
                tmp_new,
            )
            # Attempt to restore original from backup
            try:
                if tmp_old.exists() and not dest.exists():
                    os.rename(tmp_old, dest)
                    logger.info("Restored original from backup: %s", dest)
            except OSError as restore_err:
                logger.error("Failed to restore backup: %s", restore_err)
            return False

        # Phase 3: Cleanup (non-critical — replace already succeeded)
        try:
            if tmp_old.exists():
                _force_rmtree(tmp_old)
        except OSError as e:
            logger.warning("Failed to clean old copy %s: %s", tmp_old, e)
        try:
            _force_rmtree(source)
        except OSError as e:
            logger.warning("Failed to clean source %s: %s", source, e)
        return True

    def _merge(self, source: Path, dest: Path) -> bool:
        """Merge TV show with backup-based rollback for existing files.

        Uses rsync --backup to preserve overwritten files in
        .merge_backup/ within the destination. On failure, originals
        are restored from the backup directory.

        Args:
            source: Source TV show directory.
            dest: Existing destination directory.

        Returns:
            True if successful.
        """
        backup_dir = dest / ".merge_backup"

        try:
            # rsync with backup for overwritten files
            if not self._rsync_merge(source, dest, backup_dir):
                self._restore_merge_backup(dest, backup_dir)
                return False

            # Verify transfer
            if self._verify_transfer(source, dest):
                # Success — clean backup and source
                if backup_dir.exists():
                    _force_rmtree(backup_dir)
                _force_rmtree(source)
                return True

            logger.error("Merge verification failed for %s", source.name)
            self._restore_merge_backup(dest, backup_dir)
            return False
        except OSError as e:
            logger.error("Merge failed: %s", e)
            self._restore_merge_backup(dest, backup_dir)
            return False

    def _rsync_merge(
        self,
        source: Path,
        dest: Path,
        backup_dir: Path,
    ) -> bool:
        """Execute rsync with backup for merge operations.

        Backs up any overwritten files to backup_dir so they can
        be restored on failure.

        Args:
            source: Source directory.
            dest: Destination directory.
            backup_dir: Directory to store backups of overwritten files.

        Returns:
            True if rsync succeeded.
        """
        # Exclude macOS metadata files — same rationale as _rsync()
        cmd = [
            "rsync",
            "-a",
            "--no-perms",
            "--no-owner",
            "--no-group",
            "--partial",
            "--checksum",
            "--exclude=.DS_Store",
            "--exclude=._*",
            "--backup",
            f"--backup-dir={backup_dir}",
            f"{source}/",
            str(dest),
        ]

        logger.info("rsync merge: %s → %s (backup: %s)", source.name, dest, backup_dir)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode != 0:
                logger.error("rsync merge failed (rc=%d): %s", proc.returncode, proc.stderr)
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("rsync merge timed out for %s", source.name)
            return False

    @staticmethod
    def _restore_merge_backup(dest: Path, backup_dir: Path) -> int:
        """Restore overwritten files from merge backup.

        Copies files from backup_dir back to their original locations
        within dest, then removes the backup directory. Continues
        restoring remaining files even if one file fails.

        Args:
            dest: Destination directory to restore into.
            backup_dir: Backup directory with original files.

        Returns:
            Number of files restored (0 if backup_dir doesn't exist).
        """
        if not backup_dir.exists():
            return 0

        restored = 0
        failed = 0
        for backup_file in backup_dir.rglob("*"):
            if not backup_file.is_file():
                continue
            rel = backup_file.relative_to(backup_dir)
            original = dest / rel
            try:
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, original)
                restored += 1
                logger.info("Restored from backup: %s", rel)
            except OSError as e:
                failed += 1
                logger.error("Failed to restore %s: %s", rel, e)

        if failed:
            logger.error(
                "Merge backup restore: %d restored, %d failed",
                restored,
                failed,
            )
        else:
            # All files restored — safe to remove backup
            try:
                _force_rmtree(backup_dir)
            except OSError as e:
                logger.warning("Failed to clean backup dir: %s", e)

        return restored

    def _move_new(self, source: Path, dest: Path) -> bool:
        """Move a new media item to disk via staging→commit pattern.

        Writes to a temporary directory first (_tmp_dispatch_{name}),
        then atomically renames to the final destination. If rsync
        fails, the temp directory is cleaned up and the disk is left
        in a consistent state.

        Args:
            source: Source directory.
            dest: Destination directory (should not exist).

        Returns:
            True if successful.
        """
        tmp_dir = dest.parent / f"_tmp_dispatch_{dest.name}"

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Clean orphan tmp from a previous failed attempt
            if tmp_dir.exists():
                logger.warning("Cleaning orphan tmp: %s", tmp_dir)
                _force_rmtree(tmp_dir)

            # Stage: rsync to temporary directory
            if not self._rsync(source, tmp_dir):
                if tmp_dir.exists():
                    _force_rmtree(tmp_dir)
                return False

            # Commit: atomic rename to final destination
            os.rename(tmp_dir, dest)

            # Verify and clean source
            if self._verify_transfer(source, dest):
                _force_rmtree(source)
                return True

            # Verification failed — remove dest to restore clean state
            logger.error("Transfer verification failed for %s", source.name)
            try:
                if dest.exists():
                    _force_rmtree(dest)
                    logger.info("Cleaned failed destination: %s", dest)
            except OSError as cleanup_err:
                logger.warning("Failed to clean dest %s: %s", dest, cleanup_err)
            return False
        except OSError as e:
            logger.error("Move failed: %s", e)
            # Clean up temp or dest on any failure
            for path in (tmp_dir, dest):
                try:
                    if path.exists():
                        _force_rmtree(path)
                except OSError as cleanup_err:
                    logger.warning("Failed to clean %s: %s", path, cleanup_err)
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
        # -a minus -pgo: NTFS via macFUSE doesn't support Unix permissions
        # Exclude macOS metadata files — .DS_Store and ._* AppleDouble files
        # cause rsync errors on NTFS targets which don't support them.
        cmd = [
            "rsync",
            "-a",
            "--no-perms",
            "--no-owner",
            "--no-group",
            "--partial",
            "--checksum",
            "--exclude=.DS_Store",
            "--exclude=._*",
        ]
        if delete:
            cmd.append("--delete")
        cmd.extend([f"{source}/", str(dest)])

        logger.info("rsync: %s → %s", source.name, dest)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                encoding="utf-8",
                errors="replace",
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
            try:
                if not src_file.is_file():
                    continue
            except OSError:
                continue  # Broken symlink or NTFS metadata
            rel = src_file.relative_to(source)
            dst_file = dest / rel
            if not dst_file.exists():
                logger.warning("Missing after transfer: %s", rel)
                return False
            try:
                if src_file.stat().st_size != dst_file.stat().st_size:
                    logger.warning("Size mismatch: %s", rel)
                    return False
            except OSError as exc:
                logger.warning("Cannot verify %s: %s", rel, exc)
        return True

    @staticmethod
    def _has_ntfs_illegal_names(directory: Path) -> bool:
        r"""Check if any file in directory has NTFS-illegal characters.

        Scans recursively for filenames containing <>:"/\|?*.
        Used as a pre-check before rsync to NTFS disks.

        Args:
            directory: Directory to scan.

        Returns:
            True if any file has illegal characters.
        """
        illegal = [f for f in directory.rglob("*") if f.is_file() and _FILENAME_ILLEGAL.search(f.name)]
        for f in illegal:
            logger.warning("NTFS-illegal filename: %s", f)
        return len(illegal) > 0

    @staticmethod
    def _dir_size_gb(directory: Path) -> float:
        """Calculate total size of a directory in GB.

        Args:
            directory: Directory to measure.

        Returns:
            Size in GB.
        """
        total = 0
        for f in directory.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass  # Broken symlinks, NTFS metadata permission errors
        return total / (1024**3)
