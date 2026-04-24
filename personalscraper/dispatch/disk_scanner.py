"""Disk scanner: free space queries and runtime disk status.

Scans storage disks for mount status and available space. The disk-to-category
mapping is driven by config.json5 (``Config.disks``) rather than a hardcoded
``DISK_CATEGORIES`` dict.

Key design decisions:
    - ``DISK_CATEGORIES`` dict removed — categories come from ``Config.disks``.
    - ``DiskConfig`` dataclass removed — use ``conf.models.DiskConfig`` (Pydantic).
    - ``get_disk_configs(config)`` returns ``config.disks`` directly.
    - ``choose_disk()`` kept as compatibility shim — prefer ``conf.resolver.pick_disk_for()``.
    - ``DiskStatus`` is a pure runtime state dataclass (not config).
"""

import shutil
from dataclasses import dataclass

# Re-export DiskConfig from conf.models so callers that do
#   ``from personalscraper.dispatch.disk_scanner import DiskConfig``
# continue to work without modification.
from personalscraper.conf.models import Config, DiskConfig  # noqa: F401
from personalscraper.logger import get_logger

log = get_logger("disk_scanner")


@dataclass
class DiskStatus:
    """Current runtime status of a storage disk.

    Attributes:
        config: Disk configuration (Pydantic DiskConfig from conf.models).
        free_space_gb: Available free space in GB (0.0 if unmounted or unreadable).
        is_mounted: Whether the disk mount point currently exists and is accessible.
    """

    config: DiskConfig
    free_space_gb: float
    is_mounted: bool


def get_disk_configs(config: Config) -> list[DiskConfig]:
    """Return the list of DiskConfig objects from a loaded Config.

    Formerly built DiskConfig dataclasses from ``settings.disk{1-4}_dir`` and the
    hardcoded ``DISK_CATEGORIES`` dict. Now simply returns ``config.disks`` which
    are Pydantic ``DiskConfig`` models validated at load time.

    Args:
        config: The loaded and validated Config instance (conf/models.py).

    Returns:
        List of DiskConfig Pydantic models, one per disk declared in config.json5.
    """
    return list(config.disks)


def get_disk_status(config: DiskConfig) -> DiskStatus:
    """Get current free space and mount status for a disk.

    Args:
        config: Disk configuration (Pydantic DiskConfig).

    Returns:
        DiskStatus with free space in GB and mount status.
    """
    is_mounted = config.path.exists()
    free_space_gb = 0.0

    if is_mounted:
        try:
            usage = shutil.disk_usage(config.path)
            free_space_gb = usage.free / (1024**3)
        except OSError as exc:
            # Cannot read disk usage — treat as unmounted to avoid
            # dispatching to an unusable disk.
            log.error("disk_usage_failed", disk=config.id, error=str(exc))
            is_mounted = False

    return DiskStatus(
        config=config,
        free_space_gb=round(free_space_gb, 2),
        is_mounted=is_mounted,
    )


def choose_disk(
    disks: list[DiskStatus],
    category: str,
    min_free_gb: float,
    item_size_gb: float = 0,
    allow_create_category: bool = False,
) -> DiskStatus | None:
    """Choose the best disk for a media item (compatibility shim).

    .. deprecated::
        Use ``conf.resolver.pick_disk_for()`` for new code. This function is
        retained for callers not yet migrated to Config-based routing.
        It operates on ``DiskStatus`` objects and uses ``config.categories``
        (list of category IDs) rather than ``Config.disks_accepting()``.

    Two-pass strategy:
        1. Disks that have the category AND enough space (most free wins).
        2. If none found AND allow_create_category=True: any mounted disk
           with enough space (category dir created by caller).

    Threshold formula: ``free_space_gb >= max(min_free_gb, item_size_gb * 1.5)``

    Args:
        disks: List of DiskStatus objects.
        category: Category ID to match against ``disk.config.categories``.
        min_free_gb: Minimum free space threshold in GB.
        item_size_gb: Size of the item being dispatched in GB.
        allow_create_category: If True, fall back to any mounted disk with space
            when no disk accepts the category.

    Returns:
        Best DiskStatus, or None if no disk qualifies.
    """
    threshold = max(min_free_gb, item_size_gb * 1.5)

    # Pass 1: disks accepting the category with enough space
    eligible = [d for d in disks if d.is_mounted and category in d.config.categories and d.free_space_gb >= threshold]

    if eligible:
        eligible.sort(key=lambda d: d.free_space_gb, reverse=True)
        return eligible[0]

    # Pass 2: any mounted disk with enough space (create category dir)
    if allow_create_category:
        fallback = [d for d in disks if d.is_mounted and d.free_space_gb >= threshold]
        if fallback:
            fallback.sort(key=lambda d: d.free_space_gb, reverse=True)
            chosen = fallback[0]
            disk_id = chosen.config.id
            if category not in chosen.config.categories:
                log.warning("choose_disk_overflow", category=category, disk=disk_id)
            else:
                log.info("choose_disk_fallback", category=category, disk=disk_id)
            return chosen

    return None
