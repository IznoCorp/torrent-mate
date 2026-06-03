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
    is_sample_filename,
    is_sample_path,
)
from personalscraper.logger import get_logger
from personalscraper.models import StepReport

log = get_logger("process.extract")

# New-style multi-volume RAR entry/continuation: ``name.partNN.rar``.
_PART_RAR_RE = re.compile(r"\.part(\d+)\.rar$", re.IGNORECASE)


class _SymlinkMemberError(Exception):
    """A RAR carries a symlink member — rejected as a filesystem-escape risk."""


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


def _archive_set_base(name: str) -> str:
    """Return the base stem of a RAR-set entry volume.

    ``release.part01.rar`` → ``release``; ``release.rar`` → ``release``. Used to
    locate the set's ``.sfv`` sidecar for set-scoped removal.

    Args:
        name: Entry-volume filename (basename only).

    Returns:
        The set's base stem.
    """
    part = _PART_RAR_RE.search(name)
    if part:
        return name[: part.start()]
    if name.casefold().endswith(".rar"):
        return name[:-4]
    return Path(name).stem


def _has_real_video(directory: Path) -> bool:
    """Check whether a directory holds a non-sample video file (non-recursive).

    Args:
        directory: Release directory to inspect — the extracted video lands
            directly next to the archives.

    Returns:
        ``True`` if a non-sample video file exists directly in ``directory``.
    """
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not is_sample_path(f):
            return True
    return False


def _remove_extracted_set(volumes: list[Path], base: str, release_dir: Path) -> None:
    """Delete ONLY the just-extracted set's volumes (+ its ``.sfv``).

    Set-scoped (not directory-scoped) so a sibling RAR set in the same release
    directory — a 2-CD movie, or a season pack with one set per episode flat in
    one folder — is never destroyed before it is extracted (DEV #1 / review
    BUG-1). Failures are logged, never raised.

    Args:
        volumes: The exact volume files of the extracted set (``rf.volumelist()``).
        base: The set's base stem, for the ``{base}.sfv`` sidecar.
        release_dir: Directory holding the set.
    """
    targets = list(volumes)
    sfv = release_dir / f"{base}.sfv"
    if sfv.exists():
        targets.append(sfv)
    for f in targets:
        try:
            if f.exists():
                f.unlink()
        except OSError as exc:
            log.warning("process_extract_part_remove_failed", filename=f.name, exc_info=True, error=str(exc))


def extract_release_archives(
    category_dir: Path,
    dry_run: bool = False,
) -> StepReport:
    """Extract multi-part RAR sets in place before scrape (DEV #1 C).

    For every entry-volume ``.rar`` found under ``category_dir``, extracts the
    contained files next to the archive (so the scraper's recursive video
    discovery finds the real video) and removes ONLY that set's consumed volumes
    on success. Idempotence is structural: once a set is extracted its volumes
    are removed, so a finished release has no entry volume left and re-runs are a
    no-op — while a partial extraction, a sibling set, or a redundant loose video
    next to still-present archives keeps its entry volume and is (re-)extracted so
    the archives are always consumed (and never left to block dispatch).

    Safety guards (review-hardened):
    - Set-scoped removal (never deletes a sibling set's archives — BUG-1).
    - Symlink members are rejected (a malicious target can escape the release
      dir; ``rarfile`` does not sanitize symlink targets).
    - Archives are removed only after a real video is verified present, so a
      backend that exits 0 without producing a video keeps its source.
    Fail-soft throughout: a missing ``unrar`` backend, a corrupt/locked archive,
    a symlink member, or a no-video result logs a warning, leaves the archives in
    place, and counts as an error — the ``no_archive_files`` verify check then
    blocks the item from dispatch.

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
            # A prior iteration's set-scoped removal already consumed this set.
            continue

        if dry_run:
            log.info("process_extract_would_extract", archive=entry.name, directory=release_dir.name)
            report.success_count += 1
            report.details.append(f"[DRY-RUN] extract {entry.name}")
            continue

        base = _archive_set_base(entry.name)
        try:
            import rarfile

            with rarfile.RarFile(str(entry)) as rf:
                if any(info.is_symlink() for info in rf.infolist()):
                    raise _SymlinkMemberError(entry.name)
                volumes = [Path(v) for v in rf.volumelist()]
                rf.extractall(path=str(release_dir))
        except Exception as exc:  # rarfile.Error subclasses + OSError + symlink (fail-soft)
            log.warning(
                "process_extract_failed",
                archive=entry.name,
                directory=release_dir.name,
                exc_info=True,
                error=f"{type(exc).__name__}: {exc}",
            )
            report.error_count += 1
            report.warnings.append(f"Extract failed for {entry.name}: {exc}")
            continue

        # Only delete the archives once a real video is verified present.
        if not _has_real_video(release_dir):
            log.warning("process_extract_no_video", archive=entry.name, directory=release_dir.name)
            report.error_count += 1
            report.warnings.append(f"Extract produced no video for {entry.name}")
            continue

        _remove_extracted_set(volumes, base, release_dir)
        log.info("process_extract_done", archive=entry.name, directory=release_dir.name)
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
            log.info("process_sample_would_strip", path=str(rel))
            report.success_count += 1
            report.details.append(f"[DRY-RUN] {rel}")
            continue
        try:
            shutil.rmtree(sample_dir)
            log.info("process_sample_stripped", path=str(rel))
            report.success_count += 1
            report.details.append(str(rel))
        except OSError as exc:
            log.warning("process_sample_strip_failed", path=str(rel), exc_info=True, error=str(exc))
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
            log.info("process_sample_would_strip", path=str(rel))
            report.success_count += 1
            report.details.append(f"[DRY-RUN] {rel}")
            continue
        try:
            f.unlink()
            log.info("process_sample_stripped", path=str(rel))
            report.success_count += 1
            report.details.append(str(rel))
        except OSError as exc:
            log.warning("process_sample_strip_failed", path=str(rel), exc_info=True, error=str(exc))
            report.error_count += 1

    return report
