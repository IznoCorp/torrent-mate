"""Main ingest orchestrator — run_ingest() entry point.

Coordinates QBitClient, IngestTracker, and atomic file transfers
to move completed torrents from torrents/complete/ to staging area.
The lock is managed by the CLI caller, not by this module.
"""

import os
import shutil
from pathlib import Path

import qbittorrentapi
import requests

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.ingest.qbit_client import QBitAuthLockoutError, QBitClient
from personalscraper.ingest.tracker import IngestTracker
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.sorter.file_type import FileType

log = get_logger("ingest")

STAGING_TMP_PREFIX = ".ingest_tmp_"


def _get_dir_size(path: Path) -> int:
    """Calculate total size of a directory tree in bytes.

    Handles permission errors gracefully to avoid crashing the ingest
    step on a single inaccessible file. Broken symlinks are silently
    skipped (is_file() returns False for them).

    Args:
        path: Directory or file path to measure.

    Returns:
        Total size in bytes. For a file, returns its size directly.
    """
    if path.is_file():
        return path.stat().st_size
    total = 0
    for f in path.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            log.warning("cannot_stat_file", path=str(f))
    return total


def _verify_transfer(source: Path, dest: Path) -> bool:
    """Verify that dest matches source in total size.

    Compares aggregate file sizes (recursive for directories).
    Catches 99% of corruption cases without reading file contents.

    Args:
        source: Original source path.
        dest: Transferred destination path.

    Returns:
        True if sizes match.
    """
    if not dest.exists():
        return False
    return _get_dir_size(source) == _get_dir_size(dest)


def _cleanup_orphan_temps(staging_dir: Path) -> int:
    """Remove orphaned .ingest_tmp_* directories from interrupted runs.

    Args:
        staging_dir: The staging directory to scan.

    Returns:
        Number of orphaned temp directories removed.
    """
    cleaned = 0
    try:
        entries = list(staging_dir.iterdir())
    except OSError as e:
        log.warning("cannot_scan_for_orphans", path=str(staging_dir), error=str(e))
        return 0
    for item in entries:
        if item.name.startswith(STAGING_TMP_PREFIX) and item.is_dir():
            try:
                shutil.rmtree(item)
                log.info("orphan_cleaned", path=str(item))
                cleaned += 1
            except OSError as e:
                log.warning("orphan_cleanup_failed", path=str(item), error=str(e))
    return cleaned


def _check_disk_space(staging_dir: Path, required_bytes: int, min_free_gb: int) -> bool:
    """Check if staging disk has enough free space.

    Args:
        staging_dir: Path on the target filesystem.
        required_bytes: Space needed for the transfer (bytes).
        min_free_gb: Minimum free space threshold (GB).

    Returns:
        True if there is enough space.
    """
    usage = shutil.disk_usage(staging_dir)
    free_after = usage.free - required_bytes
    return free_after >= min_free_gb * (1024**3)


def transfer_torrent(source: Path, dest: Path, copy: bool, dry_run: bool = False) -> bool:
    """Transfer a torrent's content to staging via atomic copy or move.

    For copy (seeding torrents): copies to a .ingest_tmp_ directory first,
    verifies size, then renames atomically. For move (stopped torrents):
    uses shutil.move which is an atomic rename on the same filesystem.

    Args:
        source: Source path in torrents/complete/.
        dest: Destination path in staging area.
        copy: True to copy (torrent is seeding), False to move.
        dry_run: If True, log the action without performing it.

    Returns:
        True if transfer succeeded (or dry_run), False on failure.
    """
    action = "copy" if copy else "move"

    if dry_run:
        log.info("transfer_dry_run", source=str(source), dest=str(dest), action=action)
        return True

    try:
        if copy:
            # Atomic copy: write to temp dir, verify, then rename
            tmp_dest = dest.parent / f"{STAGING_TMP_PREFIX}{dest.name}"
            if source.is_dir():
                shutil.copytree(source, tmp_dest)
            else:
                tmp_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, tmp_dest)

            # Verify size before committing
            if not _verify_transfer(source, tmp_dest):
                log.error("transfer_size_mismatch", source=str(source), tmp=str(tmp_dest))
                try:
                    shutil.rmtree(tmp_dest) if tmp_dest.is_dir() else tmp_dest.unlink()
                except OSError as cleanup_err:
                    log.warning("cleanup_failed_after_mismatch", path=str(tmp_dest), error=str(cleanup_err))
                return False

            # Atomic rename (same filesystem)
            os.rename(tmp_dest, dest)
        else:
            # Move: atomic rename on same filesystem (SSD)
            shutil.move(str(source), str(dest))

            if not dest.exists():
                log.error("transfer_dest_missing", source=str(source), dest=str(dest))
                return False

        log.info("transfer_complete", source=str(source), dest=str(dest), action=action)
        return True

    except (OSError, PermissionError) as e:
        log.error("transfer_failed", source=str(source), dest=str(dest), error=str(e))
        return False


def run_ingest(
    settings: Settings,
    dry_run: bool = False,
    ingest_dir: Path | None = None,
    staging_dir: Path | None = None,
    config: Config | None = None,
) -> StepReport:
    """Run the ingest pipeline step.

    Connects to qBittorrent, lists completed torrents, and transfers
    new ones to the staging area. The lock is managed by the CLI caller.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview actions without modifying the filesystem.
        ingest_dir: Absolute path to the ingest directory (097-TEMP/).
            Falls back to ``settings.ingest_dir`` attribute for MagicMock tests.
        staging_dir: Absolute path to the staging area (from Config.paths).
            Falls back to ``settings.staging_dir`` attribute for MagicMock tests.
        config: Loaded Config for staging dir name resolution. When provided,
            uses folder_name(find_by_file_type(config, FileType.X)) to derive
            staging dir names. Falls back to hardcoded defaults when None.

    Returns:
        StepReport with success/skip/error counts and details.
    """
    report = StepReport(name="ingest")

    # Ingest deposits into ingest_dir (097-TEMP/) so sort processes only media
    # getattr fallback: MagicMock tests set ingest_dir directly as a Path attribute.
    resolved_ingest_dir: Path = ingest_dir if ingest_dir is not None else Path(getattr(settings, "ingest_dir", "."))
    resolved_ingest_dir.mkdir(parents=True, exist_ok=True)

    # Clean orphaned temp dirs from interrupted runs
    if not dry_run:
        _cleanup_orphan_temps(resolved_ingest_dir)

    try:
        client = QBitClient(
            host=settings.qbit_host,
            port=settings.qbit_port,
            username=settings.qbit_username,
            password=settings.qbit_password,
        )
    except Exception as e:
        log.error("qbit_init_failed", error=str(e))
        report.error_count = 1
        report.details.append(f"qBittorrent init failed: {e}")
        return report

    try:
        with client:
            torrents = client.get_completed_torrents()
            active_hashes = client.get_all_torrent_hashes()
            log.info("torrents_found", completed=len(torrents), total=len(active_hashes))

            tracker = IngestTracker()

            # Clean tracker of removed torrents
            tracker.cleanup(active_hashes)

            content_missing_count = 0
            consecutive_errors = 0
            last_error_type = None
            for torrent in torrents:
                name = torrent.name
                torrent_hash = torrent.hash

                try:
                    # Skip already ingested
                    if tracker.is_ingested(torrent_hash):
                        log.debug("already_ingested", name=name)
                        report.skip_count += 1
                        continue

                    # Resolve content path — if missing, check if already in staging
                    source = client.get_content_path(torrent)
                    if not source.exists():
                        # Check staging dirs for this content (already ingested pre-tracker)
                        resolved_staging = (
                            staging_dir if staging_dir is not None else Path(getattr(settings, "staging_dir", "."))
                        )
                        if config is not None:
                            _movies_dir = folder_name(find_by_file_type(config, FileType.MOVIE))
                            _tvshows_dir = folder_name(find_by_file_type(config, FileType.TVSHOW))
                        else:
                            _movies_dir = getattr(settings, "movies_dir_name", "001-MOVIES")
                            _tvshows_dir = getattr(settings, "tvshows_dir_name", "002-TVSHOWS")
                        staging_dirs = [
                            resolved_staging / _movies_dir,
                            resolved_staging / _tvshows_dir,
                            resolved_ingest_dir,
                        ]
                        found_in_staging = any((d / source.name).exists() for d in staging_dirs)
                        if found_in_staging:
                            log.info("already_in_staging", name=name)
                            tracker.mark_ingested(torrent_hash, name, "found_in_staging")
                            report.skip_count += 1
                        else:
                            log.warning("content_missing", name=name, path=str(source))
                            content_missing_count += 1
                            report.skip_count += 1
                            report.warnings.append(f"{name}: content path missing ({source})")
                        continue

                    # Destination in 097-TEMP/ (sort picks up from here)
                    dest = resolved_ingest_dir / source.name
                    if dest.exists():
                        log.info("already_exists", name=name, dest=str(dest))
                        report.skip_count += 1
                        # Still mark as ingested to avoid re-checking
                        tracker.mark_ingested(torrent_hash, name, "skipped_exists")
                        continue

                    # Check disk space
                    source_size = _get_dir_size(source)
                    if not _check_disk_space(resolved_ingest_dir, source_size, settings.min_free_space_staging_gb):
                        log.warning("insufficient_space", name=name, size_mb=source_size // (1024 * 1024))
                        report.skip_count += 1
                        report.warnings.append(f"{name}: insufficient disk space")
                        continue

                    # Transfer
                    is_copy = client.is_seeding(torrent)
                    action = "copied" if is_copy else "moved"
                    success = transfer_torrent(source, dest, copy=is_copy, dry_run=dry_run)

                    if success:
                        report.success_count += 1
                        report.details.append(f"{name} → {action}")
                        if not dry_run:
                            tracker.mark_ingested(torrent_hash, name, action)
                    else:
                        report.error_count += 1
                        report.details.append(f"{name}: transfer failed")

                except Exception as torrent_err:
                    # Isolate per-torrent failures so other torrents still process.
                    # OSError/PermissionError from filesystem operations are the most
                    # common — a bad disk sector should not block the whole batch.
                    log.error(
                        "torrent_ingest_failed",
                        name=name,
                        error=str(torrent_err),
                        exc_info=True,
                    )
                    report.error_count += 1
                    report.details.append(f"{name}: {type(torrent_err).__name__}: {torrent_err}")

                    # Abort on 2 consecutive identical errors (systemic failure)
                    err_key = type(torrent_err).__name__
                    if err_key == last_error_type:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 1
                        last_error_type = err_key
                    if consecutive_errors >= 2:
                        log.error(
                            "systemic_failure_detected",
                            error_type=err_key,
                            count=consecutive_errors,
                        )
                        report.details.append(f"Aborted: {consecutive_errors} consecutive {err_key} failures")
                        break

            # Escalate if ALL completed torrents had missing content paths
            # — likely means the source volume is unmounted
            if content_missing_count and content_missing_count == len(torrents):
                log.error(
                    "all_content_missing",
                    count=content_missing_count,
                )
                report.error_count += 1
                report.details.append(
                    f"ALL {content_missing_count} torrents have missing content. Check: is the source volume mounted?"
                )

    except QBitAuthLockoutError as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(f"qBittorrent auth lockout active: {e}")
    except qbittorrentapi.LoginFailed as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(f"qBittorrent login failed: {e}. Fix: check QBIT_USERNAME/QBIT_PASSWORD in .env")
    except qbittorrentapi.Forbidden403Error as e:
        # Must come before APIConnectionError (Forbidden403Error is a subclass)
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(
            f"qBittorrent auth blocked (IP banned): {e}. "
            "Fix: unban IP in qBit > Preferences > Web UI > IP Banning, "
            "or wait for the ban to expire."
        )
    except (qbittorrentapi.APIConnectionError, requests.ConnectionError) as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(f"qBittorrent unreachable: {e}. Fix: verify qBit is running and Web UI is enabled.")
    except Exception as e:
        # Safety catch-all for unexpected errors (e.g. tracker I/O, unexpected API changes)
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(f"Ingest failed: {type(e).__name__}: {e}")

    log.info(
        "ingest_complete",
        success=report.success_count,
        skipped=report.skip_count,
        errors=report.error_count,
        dry_run=dry_run,
    )
    return report
