"""Pre-scrape release preparation — RAR extraction and sample stripping.

Scene releases ship the real video inside a multi-part RAR set
(``release.rar`` + ``release.r00``..``release.rNN``, or
``release.partNN.rar``) alongside a small ``Sample/`` preview clip. The scraper
only understands plain video files, so without preparation it would (a) mistake
the 30-50 MB sample clip for the real episode/feature and (b) never reach the
real video locked inside the archives.

This module runs in the CLEAN sub-step, BEFORE scrape:

- :func:`extract_release_archives` (C): extracts each multi-part RAR set in
  place (next to the archives) so the scraper finds the real video, then
  removes the consumed archive parts on success. Fail-soft — a missing
  ``unrar`` backend or a corrupt archive logs a warning and leaves the archives
  untouched so the downstream ``no_archive_files`` verify check blocks the item
  from dispatch (no silent data loss, no archive ever shipped).
- :func:`strip_sample_artifacts` (A): removes ``Sample/`` directories and
  ``*-sample.*`` clips so no sample survives into scrape or dispatch. Archives
  are deliberately NOT removed here (only on successful extraction) so a failed
  extraction keeps the real content for manual recovery.

Both are idempotent and ``--dry-run`` aware.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from personalscraper.core.media_types import (
    SAMPLE_DIR_NAMES,
    VIDEO_EXTENSIONS,
    is_archive_filename,
    is_sample_filename,
    is_sample_path,
)
from personalscraper.logger import get_logger
from personalscraper.models import StepReport

log = get_logger("process.extract")

# New-style multi-volume RAR entry/continuation: ``name.partNN.rar``.
_PART_RAR_RE = re.compile(r"\.part(\d+)\.rar$", re.IGNORECASE)
# Scene checksum sidecar, consumed alongside the archives on success.
_SFV_RE = re.compile(r"\.sfv$", re.IGNORECASE)


def _is_first_volume(name: str) -> bool:
    """Check whether a ``.rar`` filename is the entry volume of its set.

    rarfile follows continuation volumes automatically, so only the FIRST
    volume must be opened. Old-style sets start at ``name.rar`` (continuations
    are ``.r00``..``.rNN``, which are not ``*.rar`` files). New-style sets start
    at ``name.part01.rar`` / ``name.part1.rar``.

    Args:
        name: Filename (basename only) ending in ``.rar``.

    Returns:
        ``True`` if this is the entry volume to hand to the extractor.
    """
    part = _PART_RAR_RE.search(name)
    if part:
        return int(part.group(1)) == 1
    return name.casefold().endswith(".rar")


def _find_rar_entrypoints(category_dir: Path) -> list[Path]:
    """Find first-volume ``.rar`` files under a category directory (recursive).

    Args:
        category_dir: Movies or TV-shows staging directory.

    Returns:
        Sorted list of entry-volume ``.rar`` paths (deterministic order).
    """
    return sorted(
        f for f in category_dir.rglob("*.rar") if f.is_file() and not is_sample_path(f) and _is_first_volume(f.name)
    )


def _has_real_video(directory: Path) -> bool:
    """Check whether a directory already holds a non-sample video file.

    Used for extraction idempotence: if the real video is already present
    (a prior run extracted it), skip re-extraction.

    Args:
        directory: Release directory to inspect (non-recursive — the extracted
            video lands directly next to the archives).

    Returns:
        ``True`` if a non-sample video file exists directly in ``directory``.
    """
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not is_sample_path(f):
            return True
    return False


def _remove_archive_parts(directory: Path) -> None:
    """Delete every archive part and ``.sfv`` sidecar in a directory.

    Called only after a successful extraction so the consumed RAR set does not
    reach dispatch. Failures are logged but never raised — a leftover archive
    is caught by the ``no_archive_files`` verify check.

    Args:
        directory: Directory whose archive parts should be removed.
    """
    for f in directory.iterdir():
        if not f.is_file():
            continue
        if is_archive_filename(f.name) or _SFV_RE.search(f.name):
            try:
                f.unlink()
            except OSError as exc:
                log.warning("archive_part_remove_failed", filename=f.name, error=str(exc))


def extract_release_archives(
    category_dir: Path,
    dry_run: bool = False,
) -> StepReport:
    """Extract multi-part RAR sets in place before scrape (DEV #1 C).

    For every entry-volume ``.rar`` found under ``category_dir``, extracts the
    contained files next to the archive (so the scraper's recursive video
    discovery finds the real video) and removes the consumed archive parts on
    success. Extraction is skipped when a non-sample video already exists in the
    release directory (idempotent). Fail-soft: a missing ``unrar`` backend or a
    corrupt/locked archive logs a warning, leaves the archives in place, and
    counts as an error so the operator is alerted — the archives are then
    blocked from dispatch by the ``no_archive_files`` verify check.

    Args:
        category_dir: Movies or TV-shows staging directory.
        dry_run: If True, log intended extractions without extracting.

    Returns:
        StepReport with ``success_count`` = archives extracted (or that would be
        extracted in dry-run) and ``error_count`` = extraction failures.
    """
    report = StepReport(name="extract")
    if not category_dir.exists():
        return report

    for entry in _find_rar_entrypoints(category_dir):
        release_dir = entry.parent
        if not entry.exists():
            # A prior iteration's extraction already consumed this set.
            continue
        if _has_real_video(release_dir):
            log.info("archive_extract_skip_existing_video", directory=release_dir.name)
            report.skip_count += 1
            continue

        if dry_run:
            log.info("archive_would_extract", archive=entry.name, directory=release_dir.name)
            report.success_count += 1
            report.details.append(f"[DRY-RUN] extract {entry.name}")
            continue

        try:
            import rarfile

            with rarfile.RarFile(str(entry)) as rf:
                rf.extractall(path=str(release_dir))
        except Exception as exc:  # rarfile.Error subclasses + OSError (fail-soft)
            log.warning(
                "archive_extract_failed",
                archive=entry.name,
                directory=release_dir.name,
                error=f"{type(exc).__name__}: {exc}",
            )
            report.error_count += 1
            report.warnings.append(f"Extract failed for {entry.name}: {exc}")
            continue

        _remove_archive_parts(release_dir)
        log.info("archive_extracted", archive=entry.name, directory=release_dir.name)
        report.success_count += 1
        report.details.append(f"extracted {entry.name}")

    return report


def strip_sample_artifacts(
    category_dir: Path,
    dry_run: bool = False,
) -> StepReport:
    """Remove scene ``Sample/`` directories and ``*-sample.*`` clips (DEV #1 A).

    Runs before scrape so no sample clip can be matched as an episode/feature or
    survive into dispatch. Only sample artifacts are removed; archive parts are
    left in place (they are removed only on successful extraction) so a failed
    extraction preserves the real content for manual recovery.

    Args:
        category_dir: Movies or TV-shows staging directory.
        dry_run: If True, log intended removals without deleting.

    Returns:
        StepReport with ``success_count`` = sample artifacts removed (or that
        would be removed in dry-run).
    """
    report = StepReport(name="sample_strip")
    if not category_dir.exists():
        return report

    # Remove sample directories first (deepest-first so nested cases are safe).
    sample_dirs = sorted(
        (d for d in category_dir.rglob("*") if d.is_dir() and d.name.casefold() in SAMPLE_DIR_NAMES),
        key=lambda d: len(d.parts),
        reverse=True,
    )
    for sample_dir in sample_dirs:
        if not sample_dir.exists():
            continue
        rel = sample_dir.relative_to(category_dir)
        if dry_run:
            log.info("sample_would_strip", path=str(rel))
            report.success_count += 1
            report.details.append(f"[DRY-RUN] {rel}")
            continue
        try:
            shutil.rmtree(sample_dir)
            log.info("sample_stripped", path=str(rel))
            report.success_count += 1
            report.details.append(str(rel))
        except OSError as exc:
            log.warning("sample_strip_failed", path=str(rel), error=str(exc))
            report.error_count += 1

    # Remove loose ``*-sample.*`` files not inside a Sample/ dir (those are
    # already handled by the directory removal above — skip them so dry-run does
    # not double-count and real runs do not chase deleted paths).
    for f in sorted(category_dir.rglob("*")):
        if not f.is_file() or not is_sample_filename(f.name):
            continue
        if any(part.casefold() in SAMPLE_DIR_NAMES for part in f.parent.parts):
            continue
        if not f.exists():
            continue
        rel = f.relative_to(category_dir)
        if dry_run:
            log.info("sample_would_strip", path=str(rel))
            report.success_count += 1
            report.details.append(f"[DRY-RUN] {rel}")
            continue
        try:
            f.unlink()
            log.info("sample_stripped", path=str(rel))
            report.success_count += 1
            report.details.append(str(rel))
        except OSError as exc:
            log.warning("sample_strip_failed", path=str(rel), error=str(exc))
            report.error_count += 1

    return report
