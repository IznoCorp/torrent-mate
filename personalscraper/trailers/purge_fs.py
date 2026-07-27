"""Filesystem-truth helpers for ``trailers purge`` (P6.4 single-truth).

Leaf primitives extracted from :mod:`personalscraper.trailers.cli` so the CLI
module stays within the module-size budget: the orphan/keep decision is driven
by what is physically on disk, and a present-but-unindexed media dir is healed
back into the index rather than treated as an orphan.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_sample_path, is_trailer_filename
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.indexer.schema import MediaItemKind

log = get_logger("trailers.purge_fs")


class _HealTarget(NamedTuple):
    """A present-on-disk media dir missing from the index — to be re-indexed.

    Attributes:
        disk_cfg: Config entry for the owning storage disk.
        category_id: Logical category ID the dir belongs to.
        kind: ``"movie"`` or ``"show"`` (drives season/episode staging).
        media_dir: Absolute path to the media directory.
    """

    disk_cfg: Any
    category_id: str
    kind: MediaItemKind
    media_dir: Path


def _media_dir_has_content(media_dir: Path) -> bool:
    """Return True iff a real media video is present under *media_dir*.

    A "real media video" is a :data:`VIDEO_EXTENSIONS` file that is not a
    trailer (:func:`is_trailer_filename`), not a sample (:func:`is_sample_path`),
    and not inside a ``Trailers/`` subfolder. Bounded to two levels — the flat
    movie layout (video beside the trailer) and the TV ``Saison NN/`` layout
    (episodes one level down) — so a media dir that is present on disk is never
    mistaken for an orphan merely because the index does not know it.

    Args:
        media_dir: The media directory to probe.

    Returns:
        True if the dir still holds its media video, False otherwise.
    """

    def _is_media_video(p: Path) -> bool:
        return (
            p.is_file()
            and p.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not is_trailer_filename(p.name)
            and not is_sample_path(p)
        )

    try:
        for entry in media_dir.iterdir():
            if _is_media_video(entry):
                return True
            # One level down for TV episodes (Saison NN/), skipping Trailers/.
            if entry.is_dir() and entry.name != "Trailers":
                try:
                    if any(_is_media_video(sub) for sub in entry.iterdir()):
                        return True
                except OSError:
                    continue
    except OSError:
        return False
    return False


def _staging_root(config: Any) -> Path | None:
    """Return the staging root Path if configured and existing, else None.

    Args:
        config: Loaded pipeline Config.

    Returns:
        The staging directory Path, or None when unconfigured or absent.
    """
    try:
        staging = Path(str(config.paths.staging_dir))
    except (AttributeError, TypeError):
        return None
    return staging if staging.exists() else None


def _heal_index_gaps(config: Any, app_context: Any, gaps: list[_HealTarget]) -> int:
    """Re-index present-but-unindexed media dirs via the scanner stage primitive.

    Opens the indexer DB and calls :func:`scan_and_stage_dir` for each gap,
    committing once. Fail-soft per item: a scan/OS error on one dir is logged
    and skipped; a DB that cannot be opened yields zero heals (the trailers were
    already spared by the discovery pass).

    Args:
        config: Loaded pipeline Config.
        app_context: The AppContext (supplies the shared ``event_bus``).
        gaps: Present media dirs missing from the index.

    Returns:
        Count of dirs successfully re-indexed.
    """
    if not gaps:
        return 0

    import sqlite3  # noqa: PLC0415 — deferred to avoid top-level import cost

    from personalscraper.indexer.db import open_db  # noqa: PLC0415
    from personalscraper.indexer.scanner._modes._item_stage import scan_and_stage_dir  # noqa: PLC0415

    db_path = getattr(getattr(config, "indexer", None), "db_path", None)
    if not isinstance(db_path, (str, Path)):
        return 0
    try:
        conn = open_db(Path(db_path), event_bus=app_context.event_bus)
    except (sqlite3.Error, OSError):
        log.warning("trailers_purge_heal_index_unavailable", db_path=str(db_path))
        return 0

    healed = 0
    try:
        for target in gaps:
            try:
                scan_and_stage_dir(conn, target.media_dir, target.disk_cfg, target.category_id, target.kind)
                healed += 1
                log.info("trailers_purge_index_healed", path=str(target.media_dir), category=target.category_id)
            except (sqlite3.Error, OSError) as exc:
                log.warning("trailers_purge_heal_failed", path=str(target.media_dir), error=str(exc))
        conn.commit()
    finally:
        conn.close()
    return healed
