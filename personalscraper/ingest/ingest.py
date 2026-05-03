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
from personalscraper.conf.staging import find_by_file_type, find_ingest_dir, folder_name, staging_path
from personalscraper.config import Settings
from personalscraper.ingest.qbit_client import QBitAuthLockoutError, QBitClient
from personalscraper.ingest.tracker import IngestTracker
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.sorter.file_type import FileType

log = get_logger("ingest")

STAGING_TMP_PREFIX = ".ingest_tmp_"


def _is_orphan_tracker_entry(entry: dict[str, object], ingest_dir: Path | None = None) -> bool:
    """Return ``True`` when a tracker entry's recorded destination is gone.

    Used to detect *orphan tracker entries*: items recorded as ``"copied"`` in
    ``ingested_torrents.json`` whose ``dest_path`` no longer exists on disk —
    typically because a downstream step (sort/process/dispatch) silently
    failed and removed the staging copy without producing a final
    destination. The tracker keeps skipping the hash on every subsequent
    ingest and the operator never sees the item lost.

    The check is intentionally conservative: it relies on the explicit
    ``dest_path`` field stored at ingest time. Legacy entries written before
    ``dest_path`` was recorded return ``False`` (no opinion) so the probe
    never produces false positives on torrents whose destination was never
    captured. Filename-based heuristics are not used here because the
    canonical downstream folder name diverges from the torrent name in
    too many lawful ways (year suffix, translated title, season layout).

    The ``ingest_dir`` argument suppresses a pervasive false positive: when
    sort moves the freshly-ingested file out of the ingest staging dir
    (e.g. ``097-TEMP``) into a category dir (``002-TVSHOWS``), the tracker
    keeps the old path.  Recorded paths inside ``ingest_dir`` that no
    longer exist are therefore *expected* — sort completed successfully —
    rather than orphaned.  Without this carve-out the warning fires on
    every pipeline run after the first successful sort, drowning the
    legitimate "downstream silently failed" signal.

    Args:
        entry: A single tracker dict as returned by
            :meth:`personalscraper.ingest.tracker.IngestTracker.get_entry`.
        ingest_dir: Resolved ingest staging directory.  When provided,
            ``dest_path`` values inside it are treated as "naturally moved
            by sort" and not flagged.

    Returns:
        ``True`` when ``entry['dest_path']`` is set, the path does not
        exist on disk, and (when ``ingest_dir`` is provided) the path is
        not inside the ingest staging area.
    """
    raw_dest = entry.get("dest_path") if isinstance(entry, dict) else None
    if not isinstance(raw_dest, str) or not raw_dest:
        return False
    dest_path = Path(raw_dest)
    if dest_path.exists():
        return False
    if ingest_dir is not None:
        try:
            dest_path.resolve().relative_to(ingest_dir.resolve())
        except (OSError, ValueError):
            # Recorded path is outside the ingest staging dir — it's a
            # final-destination path whose disappearance is a real
            # orphan signal.
            return True
        # Recorded path was inside the ingest staging dir; sort
        # consumed it, no longer interesting.
        return False
    return True


def _get_dir_size(path: Path) -> int:
    """Calculate total size of a directory tree in bytes.

    Uses ``os.scandir`` recursively rather than ``Path.rglob('*')`` +
    ``Path.stat()``: scandir returns DirEntry objects whose ``stat()``
    method reads from the same syscall used to enumerate the directory,
    saving one ``stat()`` per file on filesystems where ``rglob`` would
    issue a separate one (notably NTFS-via-macFUSE on USB).

    Handles permission errors gracefully to avoid crashing the ingest
    step on a single inaccessible file.  Broken symlinks are silently
    skipped (DirEntry.is_file() returns False for them when
    ``follow_symlinks=False``).

    Args:
        path: Directory or file path to measure.

    Returns:
        Total size in bytes.  For a file, returns its size directly.
    """
    if path.is_file():
        return path.stat().st_size

    total = 0
    pending: list[str] = [str(path)]
    while pending:
        current = pending.pop()
        try:
            it = os.scandir(current)
        except OSError as exc:
            log.warning("cannot_scan_dir", path=current, error=str(exc))
            continue
        with it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    log.warning("cannot_stat_file", path=entry.path)
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
    *,
    dry_run: bool = False,
    ingest_dir: Path | None = None,
    staging_dir: Path | None = None,
    config: Config,
) -> StepReport:
    """Run the ingest pipeline step.

    Connects to qBittorrent, lists completed torrents, and transfers
    new ones to the staging area. The lock is managed by the CLI caller.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview actions without modifying the filesystem.
        ingest_dir: Absolute path to the ingest directory ({ingest_dir}/).
            When None, resolved from ``config`` via find_ingest_dir.
        staging_dir: Explicit staging area override. When None, resolved from
            ``config.paths.staging_dir``.
        config: Loaded Config instance (required) for staging dir name resolution.

    Returns:
        StepReport with success/skip/error counts and details.
    """
    report = StepReport(name="ingest")

    # Resolve ingest_dir + staging_dir up-front so both the orphan-tracker
    # probe and the per-torrent transfer path use the same paths.
    resolved_ingest_dir: Path = ingest_dir if ingest_dir is not None else staging_path(config, find_ingest_dir(config))
    resolved_ingest_dir.mkdir(parents=True, exist_ok=True)
    resolved_staging_dir: Path = staging_dir if staging_dir is not None else config.paths.staging_dir

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
        log.error("qbit_init_failed", error=str(e), exc_info=True)
        report.error_count = 1
        report.details.append(f"qBittorrent init failed: {e}")
        return report

    try:
        with client:
            torrents = client.get_completed_torrents()
            active_hashes = client.get_all_torrent_hashes()
            log.info("torrents_found", completed=len(torrents), total=len(active_hashes))

            tracker = IngestTracker(config.paths.data_dir / "ingested_torrents.json")

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
                        # Orphan-tracker safety net: when a prior ingest
                        # recorded a dest_path and that file/directory has
                        # since vanished without a successor on disk, the
                        # tracker is silently lying — a likely sign of a
                        # mid-pipeline failure. Surface it so the operator
                        # can remove the entry and re-ingest. Legacy
                        # entries without dest_path are skipped (the helper
                        # returns False on missing field).
                        entry = tracker.get_entry(torrent_hash)
                        if entry is not None and _is_orphan_tracker_entry(entry, resolved_ingest_dir):
                            dest_str = str(entry.get("dest_path", ""))
                            warning_msg = (
                                f"{name}: tracker says ingested but recorded "
                                f"dest_path '{dest_str}' no longer exists — orphan entry"
                            )
                            log.warning(
                                "ingest.orphan_tracker_entry",
                                hash=torrent_hash,
                                name=name,
                                dest_path=dest_str,
                            )
                            report.warnings.append(warning_msg)
                        continue

                    # Skip torrents that have not yet reached the minimum ratio threshold.
                    # config.ingest.min_ratio == 0.0 (default) disables this guard so
                    # existing deployments that don't configure a threshold are unaffected.
                    torrent_ratio = getattr(torrent, "ratio", None)
                    if torrent_ratio is None:
                        # Attribute absent: warn so operators can diagnose silent skips
                        # when min_ratio > 0.0 causes the torrent to fall through to the
                        # guard below (0.0 < min_ratio → skip with no other diagnostic).
                        log.warning(
                            "ingest.torrent_ratio_missing",
                            hash=torrent_hash,
                            name=name,
                        )
                        torrent_ratio = 0.0
                    if config.ingest.min_ratio > 0.0 and torrent_ratio < config.ingest.min_ratio:
                        log.info(
                            "ingest.ratio_below_threshold",
                            name=name,
                            ratio=torrent_ratio,
                            min_ratio=config.ingest.min_ratio,
                        )
                        report.skip_count += 1
                        continue

                    # Resolve content path — if missing, check if already in staging
                    source = client.get_content_path(torrent)
                    if not source.exists():
                        # Check staging dirs for this content (already ingested pre-tracker).
                        _movies_dir = folder_name(find_by_file_type(config, FileType.MOVIE))
                        _tvshows_dir = folder_name(find_by_file_type(config, FileType.TVSHOW))
                        staging_dirs = [
                            resolved_staging_dir / _movies_dir,
                            resolved_staging_dir / _tvshows_dir,
                            resolved_ingest_dir,
                        ]
                        # Find the actual staging path so the orphan probe can
                        # validate it on subsequent runs.
                        staging_dest = next(
                            (d / source.name for d in staging_dirs if (d / source.name).exists()),
                            None,
                        )
                        if staging_dest is not None:
                            log.info("already_in_staging", name=name)
                            tracker.mark_ingested(
                                torrent_hash,
                                name,
                                "found_in_staging",
                                dest_path=str(staging_dest),
                            )
                            report.skip_count += 1
                        else:
                            log.warning("content_missing", name=name, path=str(source))
                            content_missing_count += 1
                            report.skip_count += 1
                            report.warnings.append(f"{name}: content path missing ({source})")
                        continue

                    # Destination in {ingest_dir}/ (sort picks up from here)
                    dest = resolved_ingest_dir / source.name
                    if dest.exists():
                        log.info("already_exists", name=name, dest=str(dest))
                        report.skip_count += 1
                        # Still mark as ingested to avoid re-checking
                        tracker.mark_ingested(torrent_hash, name, "skipped_exists", dest_path=str(dest))
                        continue

                    # Check disk space
                    source_size = _get_dir_size(source)
                    if not _check_disk_space(resolved_ingest_dir, source_size, config.thresholds.min_free_space_staging_gb):
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
                            tracker.mark_ingested(torrent_hash, name, action, dest_path=str(dest))
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
        log.exception("ingest_qbit_auth_lockout", error=str(e))
        report.error_count += 1
        report.details.append(f"qBittorrent auth lockout active: {e}")
    except qbittorrentapi.LoginFailed as e:
        log.exception("ingest_qbit_login_failed", error=str(e))
        report.error_count += 1
        report.details.append(f"qBittorrent login failed: {e}. Fix: check QBIT_USERNAME/QBIT_PASSWORD in .env")
    except qbittorrentapi.Forbidden403Error as e:
        # Must come before APIConnectionError (Forbidden403Error is a subclass)
        log.exception("ingest_qbit_forbidden", error=str(e))
        report.error_count += 1
        report.details.append(
            f"qBittorrent auth blocked (IP banned): {e}. "
            "Fix: unban IP in qBit > Preferences > Web UI > IP Banning, "
            "or wait for the ban to expire."
        )
    except (qbittorrentapi.APIConnectionError, requests.ConnectionError) as e:
        log.exception("ingest_qbit_unreachable", error=str(e))
        report.error_count += 1
        report.details.append(f"qBittorrent unreachable: {e}. Fix: verify qBit is running and Web UI is enabled.")
    except Exception as e:  # noqa: BLE001 — safety catch-all for tracker I/O and unexpected qbittorrentapi changes; preserves pipeline continuation on unknown failures
        # Safety catch-all for unexpected errors (e.g. tracker I/O, unexpected API changes)
        log.exception("ingest_unexpected_error", error=str(e), error_type=type(e).__name__)
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
