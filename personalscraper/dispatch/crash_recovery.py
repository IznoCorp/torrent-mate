"""Single-owner crash-recovery orphan sweep (PIPELINE-CORE-07).

Consolidates the four historical orphan-cleanup implementations
(``Dispatcher._cleanup_orphan_temps``, ``dispatch/run.py::_cleanup_staging_orphans``,
``pipeline.py::_recover_from_previous_run`` and ``ingest/ingest.py::_cleanup_orphan_temps``)
into ONE declarative sweep.

The **artifact table** (:data:`ARTIFACT_TABLE`) is the single home for every
orphan marker (``_tmp_dispatch_*`` staging dirs, ``.merge_backup/`` restore
snapshots, ``.ingest_tmp_*`` copy stages) and the stale qBittorrent auth-lockout
file.  Each :class:`SweepRoot` a caller supplies is tagged with a
:class:`RootKind` (how the root is walked) and a :class:`DryRunPolicy` (what the
root does in dry-run mode), so per-site behaviour is preserved without
duplicating logic.

Removal uses :func:`~personalscraper.dispatch._transfer.force_rmtree` (the
NTFS/macOS-safe primitive) for directory artifacts — strictly the safest of the
former implementations' semantics: it never deletes more than plain
``shutil.rmtree`` would, but succeeds on read-only NTFS entries the plain call
would leave behind.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from personalscraper.dispatch._transfer import force_rmtree
from personalscraper.logger import get_logger

log = get_logger("crash_recovery")

# ---------------------------------------------------------------------------
# Orphan markers — the SINGLE home for these prefixes/names.
# ---------------------------------------------------------------------------

#: Prefix of the staged-commit temp directory created during a dispatch move.
DISPATCH_TMP_PREFIX = "_tmp_dispatch_"
#: Prefix of the copy-stage temp directory created during ingest transfers.
INGEST_TMP_PREFIX = ".ingest_tmp_"
#: Name of the merge-backup snapshot directory left inside a media folder.
MERGE_BACKUP_NAME = ".merge_backup"
#: A qBittorrent auth-lockout file is considered stale after this age (seconds).
LOCKOUT_STALE_AGE_S = 3600


class RootKind(Enum):
    """How a :class:`SweepRoot` is walked to locate its orphan artifacts."""

    #: ``<root>/<category>/<media>`` — storage disks and the staging root.
    #: Sweeps ``_tmp_dispatch_*`` media dirs and their ``.merge_backup/`` subdirs.
    MEDIA_TREE = "media_tree"
    #: ``<root>/<tmp>`` — an ingest directory. Sweeps ``.ingest_tmp_*`` dirs.
    INGEST_DIR = "ingest_dir"
    #: The root path IS a file — a stale qBit auth-lockout, age-gated unlink.
    LOCKOUT_FILE = "lockout_file"


class Shape(Enum):
    """Where an orphan marker sits relative to the walked directory level."""

    #: The marker names a media directory (``<category>/<marker>*``).
    MEDIA_DIR = "media_dir"
    #: The marker is a subdirectory inside each media dir (``<media>/<marker>``).
    MEDIA_SUBDIR = "media_subdir"
    #: The marker names a directory directly under the root (``<root>/<marker>*``).
    TOP_LEVEL_DIR = "top_level_dir"
    #: The root itself is a stale file removed once past its age threshold.
    STALE_FILE = "stale_file"


class DryRunPolicy(Enum):
    """What a root's sweep does when ``dry_run`` is True."""

    #: Do nothing at all in dry-run (the historical boot/ingest/staging sweeps).
    SKIP = "skip"
    #: Count and log ``would clean`` but do not delete (the historical
    #: ``Dispatcher._cleanup_orphan_temps`` — keeps ``dispatch --dry-run``
    #: side-effect-free yet visible).
    REPORT = "report"


@dataclass(frozen=True)
class OrphanArtifact:
    """One declarative row of the artifact table: a marker + its shape + kind."""

    marker: str
    root_kind: RootKind
    shape: Shape


@dataclass(frozen=True)
class SweepRoot:
    """A root to sweep, tagged with how to walk it and its dry-run policy."""

    path: Path
    kind: RootKind
    dry_run: DryRunPolicy = DryRunPolicy.SKIP


#: The declarative artifact table — marker prefix/name, root kind, and shape for
#: every orphan the sweep recognises. This is the ONE place markers live.
ARTIFACT_TABLE: tuple[OrphanArtifact, ...] = (
    OrphanArtifact(DISPATCH_TMP_PREFIX, RootKind.MEDIA_TREE, Shape.MEDIA_DIR),
    OrphanArtifact(MERGE_BACKUP_NAME, RootKind.MEDIA_TREE, Shape.MEDIA_SUBDIR),
    OrphanArtifact(INGEST_TMP_PREFIX, RootKind.INGEST_DIR, Shape.TOP_LEVEL_DIR),
    OrphanArtifact("", RootKind.LOCKOUT_FILE, Shape.STALE_FILE),
)


def sweep_orphans(
    roots: Sequence[SweepRoot],
    *,
    artifacts: Sequence[OrphanArtifact] = ARTIFACT_TABLE,
    dry_run: bool,
) -> int:
    """Sweep crash-recovery orphans across *roots* (the single-owner sweep).

    For each root, the artifact rows matching its :class:`RootKind` are applied
    according to their :class:`Shape`.  Directory artifacts are removed with
    :func:`force_rmtree`; the stale lockout file is unlinked once past
    :data:`LOCKOUT_STALE_AGE_S`.  Every removal is guarded so a single failing
    entry never aborts the sweep.

    Args:
        roots: Roots to sweep, each carrying its walk kind and dry-run policy.
        artifacts: The declarative artifact table (defaults to
            :data:`ARTIFACT_TABLE`; overridable for tests).
        dry_run: When True, ``SKIP`` roots do nothing and ``REPORT`` roots log
            what they *would* clean (and count it) without deleting.

    Returns:
        Number of orphan artifacts cleaned (or, for ``REPORT`` roots in dry-run,
        that *would* have been cleaned).
    """
    total = 0
    for root in roots:
        rules = tuple(a for a in artifacts if a.root_kind == root.kind)
        if root.kind is RootKind.MEDIA_TREE:
            total += _sweep_media_tree(root, rules, dry_run=dry_run)
        elif root.kind is RootKind.INGEST_DIR:
            total += _sweep_ingest_dir(root, rules, dry_run=dry_run)
        elif root.kind is RootKind.LOCKOUT_FILE:
            total += _sweep_lockout_file(root, dry_run=dry_run)
    if total:
        log.info("orphans_swept", count=total, dry_run=dry_run)
    return total


def _remove_dir(target: Path, root: SweepRoot, *, dry_run: bool, kind: str) -> int:
    """Remove *target* (or report it in dry-run per the root's policy).

    Args:
        target: Directory to remove.
        root: The owning sweep root (supplies the dry-run policy).
        dry_run: Whether the sweep is in dry-run mode.
        kind: Short marker kind for structured logging.

    Returns:
        1 when the artifact was cleaned or counted; 0 otherwise.
    """
    if dry_run:
        if root.dry_run is DryRunPolicy.SKIP:
            return 0
        log.info("orphan_would_clean", path=str(target), kind=kind)
        return 1
    try:
        force_rmtree(target)
    except OSError as exc:
        log.warning("orphan_sweep_failed", path=str(target), kind=kind, error=str(exc))
        return 0
    log.info("orphan_swept", path=str(target), kind=kind)
    return 1


def _sweep_media_tree(root: SweepRoot, rules: Sequence[OrphanArtifact], *, dry_run: bool) -> int:
    """Sweep a ``<root>/<category>/<media>`` tree for its media-level artifacts.

    Args:
        root: The media-tree root (a storage disk or the staging root).
        rules: Artifact rows applicable to :attr:`RootKind.MEDIA_TREE`.
        dry_run: Whether the sweep is in dry-run mode.

    Returns:
        Number of artifacts cleaned (or counted in dry-run REPORT mode).
    """
    if not root.path.exists():
        return 0
    try:
        categories = list(root.path.iterdir())
    except OSError as exc:
        log.warning("orphan_scan_failed", path=str(root.path), error=str(exc))
        return 0

    count = 0
    for category in categories:
        if not category.is_dir():
            continue
        try:
            media_dirs = list(category.iterdir())
        except OSError as exc:
            log.warning("orphan_scan_failed", path=str(category), error=str(exc))
            continue
        for media in media_dirs:
            if not media.is_dir():
                continue
            for rule in rules:
                if rule.shape is Shape.MEDIA_DIR:
                    if media.name.startswith(rule.marker):
                        count += _remove_dir(media, root, dry_run=dry_run, kind="tmp_dispatch")
                elif rule.shape is Shape.MEDIA_SUBDIR:
                    subdir = media / rule.marker
                    if subdir.exists():
                        count += _remove_dir(subdir, root, dry_run=dry_run, kind="merge_backup")
    return count


def _sweep_ingest_dir(root: SweepRoot, rules: Sequence[OrphanArtifact], *, dry_run: bool) -> int:
    """Sweep an ingest directory for top-level ``.ingest_tmp_*`` artifacts.

    Args:
        root: The ingest-directory root.
        rules: Artifact rows applicable to :attr:`RootKind.INGEST_DIR`.
        dry_run: Whether the sweep is in dry-run mode.

    Returns:
        Number of artifacts cleaned (or counted in dry-run REPORT mode).
    """
    if not root.path.exists():
        return 0
    try:
        items = list(root.path.iterdir())
    except OSError as exc:
        log.warning("orphan_scan_failed", path=str(root.path), error=str(exc))
        return 0

    count = 0
    for item in items:
        for rule in rules:
            if rule.shape is Shape.TOP_LEVEL_DIR and item.name.startswith(rule.marker) and item.is_dir():
                count += _remove_dir(item, root, dry_run=dry_run, kind="ingest_tmp")
    return count


def _sweep_lockout_file(root: SweepRoot, *, dry_run: bool) -> int:
    """Unlink the qBit auth-lockout file once it is older than the threshold.

    Args:
        root: The lockout-file root (``root.path`` is the file itself).
        dry_run: Whether the sweep is in dry-run mode.

    Returns:
        1 when the stale lockout was removed (or counted); 0 otherwise.
    """
    path = root.path
    if not path.exists():
        return 0
    try:
        age = time.time() - path.stat().st_mtime
    except OSError as exc:
        log.warning("orphan_sweep_failed", path=str(path), kind="stale_lockout", error=str(exc))
        return 0
    if age <= LOCKOUT_STALE_AGE_S:
        return 0
    if dry_run:
        if root.dry_run is DryRunPolicy.SKIP:
            return 0
        log.info("orphan_would_clean", path=str(path), kind="stale_lockout")
        return 1
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("orphan_sweep_failed", path=str(path), kind="stale_lockout", error=str(exc))
        return 0
    log.info("orphan_swept", path=str(path), kind="stale_lockout", age_s=int(age))
    return 1


__all__ = [
    "ARTIFACT_TABLE",
    "DISPATCH_TMP_PREFIX",
    "INGEST_TMP_PREFIX",
    "LOCKOUT_STALE_AGE_S",
    "MERGE_BACKUP_NAME",
    "DryRunPolicy",
    "OrphanArtifact",
    "RootKind",
    "Shape",
    "SweepRoot",
    "sweep_orphans",
]
