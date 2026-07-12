"""Opt-in dispatch-target preview for a staged media (webui-overhaul OBJ2A).

Answers "if this were dispatched now, where would it go?" — the same decision
the dispatcher makes, previewed read-only. Movies replace a same-named folder,
TV shows merge into it, and a media with no existing folder goes to the disk
with the most free space (``conf.resolver.pick_disk_for``). Best-effort and
fully fail-soft: any resolution error yields ``mode="unknown"`` rather than
failing the list response. Only computed when the list endpoint is called with
``with_dispatch=true`` (a per-disk ``statvfs`` + per-disk folder ``stat``).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.conf.resolver import folder_for, pick_disk_for
from personalscraper.dispatch.disk_scanner import get_disk_status
from personalscraper.logger import get_logger
from personalscraper.web.models.staging import (
    StagingDispatchMode,
    StagingDispatchTarget,
    StagingMediaKind,
)

logger = get_logger(__name__)

#: Kind → default storage category id when the NFO carries no ``<category>``.
_KIND_TO_CATEGORY: dict[str, str] = {"movie": "movies", "tvshow": "tv_shows"}


def build_free_space_by_id(config: Config) -> dict[str, float]:
    """Query current free space (GB) for every configured disk.

    Unmounted/unreadable disks report ``0.0`` (``get_disk_status`` contract), so
    :func:`~personalscraper.conf.resolver.pick_disk_for` filters them out.

    Args:
        config: The loaded config (its ``disks`` list).

    Returns:
        Mapping ``disk.id → free_space_gb``.
    """
    free: dict[str, float] = {}
    for disk in config.disks:
        try:
            free[disk.id] = get_disk_status(disk).free_space_gb
        except OSError as exc:  # pragma: no cover — statvfs failure is rare
            logger.debug("staging_disk_status_failed", disk=disk.id, error=str(exc))
            free[disk.id] = 0.0
    return free


def _resolve_category_id(config: Config, media_kind: StagingMediaKind, category_hint: str | None) -> str | None:
    """Resolve the storage category id for a staged media.

    Prefers the NFO ``<category>`` hint when it is a category the config knows,
    else falls back to the kind default (``movies`` / ``tv_shows``).

    Args:
        config: The loaded config.
        media_kind: The read-model media kind.
        category_hint: The NFO ``<category>`` value, or ``None``.

    Returns:
        A category id, or ``None`` when the kind has no storage mapping.
    """
    if category_hint:
        try:
            # ``disks_accepting`` returning any disk proves the category is known.
            if config.disks_accepting(category_hint):
                return category_hint
        except (KeyError, ValueError):
            pass
    return _KIND_TO_CATEGORY.get(media_kind)


def preview_dispatch(
    config: Config,
    *,
    media_kind: StagingMediaKind,
    media_dir: Path,
    category_hint: str | None,
    size_bytes: int,
    free_space_by_id: dict[str, float],
) -> StagingDispatchTarget:
    """Preview where a staged media would be dispatched.

    Args:
        config: The loaded config.
        media_kind: The read-model media kind.
        media_dir: The staged media folder (its name is matched against existing
            storage folders).
        category_hint: The NFO ``<category>`` value, or ``None``.
        size_bytes: The media folder size, for the free-space threshold.
        free_space_by_id: Free-space map from :func:`build_free_space_by_id`.

    Returns:
        A :class:`StagingDispatchTarget` — ``replace``/``merge`` when a same-named
        folder exists, ``new`` with the most-free eligible disk otherwise, or
        ``unknown`` on any resolution error.
    """
    try:
        category_id = _resolve_category_id(config, media_kind, category_hint)
        if category_id is None:
            return StagingDispatchTarget(mode="unknown", reason="Type de média non dispatchable.")

        candidates = config.disks_accepting(category_id)
        folder = media_dir.name

        # Existing same-named folder → replace (movie) / merge (TV show).
        for disk in candidates:
            if (folder_for(config, disk, category_id) / folder).exists():
                mode: StagingDispatchMode = "merge" if media_kind == "tvshow" else "replace"
                verb = "fusionné dans" if mode == "merge" else "remplacé sur"
                return StagingDispatchTarget(
                    mode=mode,
                    disk=disk.id,
                    category_id=category_id,
                    reason=f"Dossier existant — {verb} {disk.id}.",
                )

        # New media → disk with the most free space.
        chosen = pick_disk_for(
            config,
            category_id,
            free_space_by_id,
            float(config.thresholds.min_free_space_disk_gb),
            size_bytes / 1_000_000_000,
        )
        if chosen is None:
            return StagingDispatchTarget(
                mode="new",
                disk=None,
                category_id=category_id,
                reason="Nouveau média — aucun disque avec assez d'espace libre.",
            )
        return StagingDispatchTarget(
            mode="new",
            disk=chosen.id,
            category_id=category_id,
            reason=f"Nouveau média — disque le plus libre ({chosen.id}).",
        )
    except Exception as exc:  # noqa: BLE001 — preview is best-effort, never 500s the list
        logger.debug("staging_dispatch_preview_failed", folder=media_dir.name, error=str(exc))
        return StagingDispatchTarget(mode="unknown", reason="Prévisualisation indisponible.")
