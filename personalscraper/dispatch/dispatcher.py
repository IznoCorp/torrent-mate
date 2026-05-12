"""Media dispatch orchestrator: replace, merge, and move operations.

Handles cross-filesystem transfers from the staging area (``paths.staging_dir``)
to storage disks using rsync for reliability. Movies are replaced (delete old
+ move new), TV shows are merged (add new episodes).

Dispatcher accepts ``Config`` as first argument. Category routing uses
``conf.resolver.pick_disk_for`` and ``conf.resolver.folder_for``. The
``category`` parameter is a category_id (e.g. ``"movies"``) rather than
a legacy label (e.g. ``"films"``).

Module-split: core logic lives in ``_movie.py``, ``_tv.py``, ``_transfer.py``
and ``_types.py``. This file is a thin orchestrator with delegator methods
for backward-compatible calls from ``_move_new`` and tests.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.dispatch import _movie, _transfer, _tv
from personalscraper.dispatch._types import DispatchError, DispatchResult
from personalscraper.dispatch.disk_scanner import get_disk_configs
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
from personalscraper.logger import get_logger
from personalscraper.verify.verifier import VerifyResult

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus

log = get_logger("dispatcher")


class Dispatcher:
    """Orchestrate media dispatch to storage disks.

    Handles replace (movies), merge (TV shows), and new item placement
    using rsync for cross-filesystem transfers.

    Accepts ``Config`` as first argument; routing uses
    ``conf.resolver.pick_disk_for`` and ``conf.resolver.folder_for``.

    Attributes:
        dry_run: If True, preview operations without transferring.
    """

    def __init__(
        self,
        config: Config,
        settings: Settings,
        index: MediaIndex,
        dry_run: bool = False,
        *,
        event_bus: EventBus | None = None,
    ):
        """Initialize the dispatcher.

        Args:
            config: Loaded Config with disk definitions and category mapping.
            settings: Pipeline settings with numeric thresholds and credentials.
            index: Media index for existing media lookup.
            dry_run: If True, preview without modifying files.
            event_bus: Optional :class:`EventBus`. When provided,
                ``_movie.dispatch_movie`` and ``_tv.dispatch_tvshow`` emit
                :class:`ItemDispatched` after every successful real
                transfer (dry-run never emits, by design — the catalog
                only records completed transfers). Optional in Phase 4;
                required in Phase 5.2.

        Raises:
            DispatchError: If rsync is not available.
        """
        self.config = config
        self.settings = settings
        self.index = index
        self.dry_run = dry_run
        self._event_bus = event_bus
        self._disk_configs = get_disk_configs(config)

        # Verify rsync is available
        if not shutil.which("rsync"):
            raise DispatchError("rsync is required but not found in PATH")

    # ------------------------------------------------------------------
    # Internal helpers (kept inline -- orchestrator-level logic)
    # ------------------------------------------------------------------

    def _cleanup_orphan_temps(self) -> int:
        """Clean up orphan temporary directories from previous failed runs.

        Scans all storage disks for ``_tmp_dispatch_*`` and ``.merge_backup/``
        directories that were left behind by interrupted dispatch operations.

        Honors :attr:`dry_run`: when True, every orphan is reported via
        ``orphan_*_found_dry_run`` log events but no destructive action is
        taken.  This guarantees ``personalscraper dispatch --dry-run`` is
        actually side-effect-free.

        Returns:
            Number of orphan directories cleaned up (or, in dry-run mode,
            the number that *would have been* cleaned).
        """
        cleaned = 0
        for config in self._disk_configs:
            if not config.path.exists():
                continue
            try:
                category_dirs = list(config.path.iterdir())
            except OSError as e:
                log.warning("orphan_scan_failed", disk=config.id, error=str(e))
                continue
            for category_dir in category_dirs:
                if not category_dir.is_dir():
                    continue
                try:
                    items = list(category_dir.iterdir())
                except OSError as e:
                    log.warning("orphan_scan_failed", path=str(category_dir), error=str(e))
                    continue
                for item in items:
                    if not item.is_dir():
                        continue
                    # Clean _tmp_dispatch_* orphans
                    if item.name.startswith("_tmp_dispatch_"):
                        if self.dry_run:
                            log.warning("orphan_tmp_found_dry_run", path=str(item))
                            cleaned += 1
                        else:
                            log.warning("orphan_tmp_found", path=str(item))
                            try:
                                _transfer.force_rmtree(item)
                                cleaned += 1
                            except OSError as e:
                                log.error("orphan_tmp_cleanup_failed", path=str(item), error=str(e))
                    # Clean .merge_backup/ orphans inside media dirs
                    backup = item / ".merge_backup"
                    if backup.exists():
                        if self.dry_run:
                            log.warning("orphan_backup_found_dry_run", path=str(backup))
                            cleaned += 1
                        else:
                            log.warning("orphan_backup_found", path=str(backup))
                            try:
                                _transfer.force_rmtree(backup)
                                cleaned += 1
                            except OSError as e:
                                log.error("orphan_backup_cleanup_failed", path=str(backup), error=str(e))
        if cleaned:
            log.info("orphans_cleaned", count=cleaned, dry_run=self.dry_run)
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
        2. If the stored path still exists -> return the entry unchanged.
        3. If not -> scan every configured disk for a directory named exactly
           ``name`` (under any category folder). If found, return a synthetic
           IndexEntry pointing at the real location (disk_id + path resolved
           from filesystem). Index maintenance is handled by the write-through
           and indexer scan paths.
        4. If nowhere on any disk -> return ``None`` (truly new).

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

        # Index says a location that doesn't exist -- scan disks for reality.
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
                        log.warning(
                            "index_drift_detected",
                            name=name,
                            index_disk=entry.disk,
                            index_path=entry.path,
                            fs_disk=disk_cfg.id,
                        )
                    return IndexEntry(
                        name=name,
                        disk=disk_cfg.id,
                        category=(entry.category if entry else category_dir.name),
                        path=str(candidate),
                        media_type=media_type,
                    )

        if entry is not None:
            log.warning(
                "index_stale_entry",
                name=name,
                stale_path=entry.path,
            )
        return None

    # ------------------------------------------------------------------
    # Dispatch dispatchers (delegates to extracted sub-modules)
    # ------------------------------------------------------------------

    def dispatch_movie(self, movie_dir: Path, category_id: str) -> DispatchResult:
        """Dispatch a movie: replace if exists, move to best disk if new.

        Delegates to :func:`_movie.dispatch_movie`.

        Args:
            movie_dir: Source movie directory.
            category_id: Category ID (e.g. ``"movies"``) from the classifier.

        Returns:
            DispatchResult with operation details.
        """
        return _movie.dispatch_movie(self, movie_dir, category_id)

    def dispatch_tvshow(self, show_dir: Path, category_id: str) -> DispatchResult:
        """Dispatch a TV show: merge if exists, move to best disk if new.

        Delegates to :func:`_tv.dispatch_tvshow`.

        Args:
            show_dir: Source TV show directory.
            category_id: Category ID (e.g. ``"tv_shows"``) from the classifier.

        Returns:
            DispatchResult with operation details.
        """
        return _tv.dispatch_tvshow(self, show_dir, category_id)

    # ------------------------------------------------------------------
    # Delegator methods (kept so ``_move_new`` and tests still work)
    # ------------------------------------------------------------------

    @staticmethod
    def _replace(source: Path, dest: Path) -> bool:
        """Delegate to ``_movie.replace``."""
        return _movie.replace(source, dest)

    @staticmethod
    def _merge(source: Path, dest: Path) -> bool:
        """Delegate to ``_tv.merge``."""
        return _tv.merge(source, dest)

    @staticmethod
    def _purge_episode_conflicts(
        source: Path,
        dest: Path,
        backup_dir: Path,
    ) -> None:
        """Delegate to ``_tv.purge_episode_conflicts``."""
        _tv.purge_episode_conflicts(source, dest, backup_dir)

    @staticmethod
    def _rsync(source: Path, dest: Path, delete: bool = False) -> bool:
        """Delegate to ``_transfer.rsync``."""
        return _transfer.rsync(source, dest, delete=delete)

    @staticmethod
    def _rsync_merge(
        source: Path,
        dest: Path,
        backup_dir: Path,
    ) -> bool:
        """Delegate to ``_transfer.rsync_merge``."""
        return _transfer.rsync_merge(source, dest, backup_dir)

    @staticmethod
    def _restore_merge_backup(dest: Path, backup_dir: Path) -> int:
        """Delegate to ``_transfer.restore_merge_backup``."""
        return _transfer.restore_merge_backup(dest, backup_dir)

    @staticmethod
    def _verify_transfer(source: Path, dest: Path) -> bool:
        """Delegate to ``_transfer.verify_transfer``."""
        return _transfer.verify_transfer(source, dest)

    @staticmethod
    def _has_ntfs_illegal_names(directory: Path) -> bool:
        """Delegate to ``_transfer.has_ntfs_illegal_names``."""
        return _transfer.has_ntfs_illegal_names(directory)

    @staticmethod
    def _dir_size_gb(directory: Path) -> float:
        """Delegate to ``_transfer.dir_size_gb``."""
        return _transfer.dir_size_gb(directory)

    @staticmethod
    def _dir_stats(directory: Path) -> tuple[int, int]:
        """Delegate to ``_transfer.dir_stats``."""
        return _transfer.dir_stats(directory)

    # ------------------------------------------------------------------
    # Move-new (kept inline -- calls delegator methods above)
    # ------------------------------------------------------------------

    def _move_new(self, source: Path, dest: Path) -> bool:
        """Move a new media item to disk via staging->commit pattern.

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
                log.warning("orphan_tmp_found", path=str(tmp_dir))
                _transfer.force_rmtree(tmp_dir)

            # Stage: rsync to temporary directory
            if not self._rsync(source, tmp_dir):
                if tmp_dir.exists():
                    _transfer.force_rmtree(tmp_dir)
                return False

            # Commit: atomic rename to final destination
            os.rename(tmp_dir, dest)

            # Verify and clean source
            if self._verify_transfer(source, dest):
                _transfer.force_rmtree(source)
                return True

            # Verification failed -- remove dest to restore clean state
            log.error("transfer_verify_failed", source=source.name)
            try:
                if dest.exists():
                    _transfer.force_rmtree(dest)
                    log.info("failed_dest_cleaned", dest=str(dest))
            except OSError as cleanup_err:
                log.warning("failed_dest_cleanup_failed", dest=str(dest), error=str(cleanup_err))
            return False
        except OSError as e:
            log.error("move_failed", error=str(e), exc_info=True)
            # Clean up temp or dest on any failure
            for path in (tmp_dir, dest):
                try:
                    if path.exists():
                        _transfer.force_rmtree(path)
                except OSError as cleanup_err:
                    log.warning("move_cleanup_failed", path=str(path), error=str(cleanup_err))
            return False
