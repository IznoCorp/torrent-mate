"""Disk scanner: configuration, free space, and disk selection.

Scans storage disks for mount status and available space. Provides
disk selection logic based on category compatibility and free space
thresholds.

The disk-to-category mapping is hardcoded (matches physical disk layout
from CLAUDE.md "Storage Disks"). Categories are validated against
GenreMapper.KNOWN_CATEGORIES at import time.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.genre_mapper import KNOWN_CATEGORIES

logger = logging.getLogger(__name__)


# Disk → category mapping (matches CLAUDE.md "Storage Disks" table)
DISK_CATEGORIES: dict[str, list[str]] = {
    "Disk1": [
        "films", "films animations", "films documentaires", "livres audios",
        "series", "series animations", "series documentaires",
        "spectacles", "theatres", "emissions",
    ],
    "Disk2": ["series", "series animes"],
    "Disk3": [
        "films", "films animations", "films documentaires", "livres audios",
        "series", "series animations", "series documentaires",
        "spectacles", "theatres", "emissions",
    ],
    "Disk4": [
        "films", "films animations", "series", "series animations",
        "series documentaires", "emissions",
    ],
}

# Validate all categories at import time
for _disk, _cats in DISK_CATEGORIES.items():
    for _cat in _cats:
        assert _cat in KNOWN_CATEGORIES, f"Unknown category '{_cat}' in {_disk}"


@dataclass
class DiskConfig:
    """Configuration for a storage disk.

    Attributes:
        name: Disk identifier (e.g. "Disk1").
        path: Mount point path (e.g. /Volumes/Disk1/medias).
        categories: List of media categories this disk accepts.
    """

    name: str
    path: Path
    categories: list[str]


@dataclass
class DiskStatus:
    """Current status of a storage disk.

    Attributes:
        config: Disk configuration.
        free_space_gb: Available free space in GB.
        is_mounted: Whether the disk is currently mounted.
    """

    config: DiskConfig
    free_space_gb: float
    is_mounted: bool


def get_disk_configs(settings: Settings) -> list[DiskConfig]:
    """Build disk configurations from settings.

    Maps settings disk paths (disk1_dir through disk4_dir) to
    DiskConfig objects with their category assignments.

    Args:
        settings: Pipeline configuration with disk paths.

    Returns:
        List of DiskConfig for all 4 disks.
    """
    disk_paths = {
        "Disk1": Path(settings.disk1_dir),
        "Disk2": Path(settings.disk2_dir),
        "Disk3": Path(settings.disk3_dir),
        "Disk4": Path(settings.disk4_dir),
    }

    configs = []
    for name, path in disk_paths.items():
        configs.append(DiskConfig(
            name=name,
            path=path,
            categories=DISK_CATEGORIES[name],
        ))

    return configs


def get_disk_status(config: DiskConfig) -> DiskStatus:
    """Get current free space and mount status for a disk.

    Args:
        config: Disk configuration.

    Returns:
        DiskStatus with free space and mount status.
    """
    is_mounted = config.path.exists()
    free_space_gb = 0.0

    if is_mounted:
        try:
            usage = shutil.disk_usage(config.path)
            free_space_gb = usage.free / (1024 ** 3)
        except OSError as exc:
            # Can't read disk usage — treat as unmounted to avoid
            # dispatching to an unusable disk
            logger.error("Cannot read disk usage for %s: %s — treating as unmounted", config.name, exc)
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
    """Choose the best disk for a media item.

    Two-pass strategy:
    1. Disks that have the category AND enough space (most free wins)
    2. If none found AND allow_create_category=True: any mounted disk
       with enough space (the category dir will be created by the caller)

    The category directory is NOT created here — just the disk is chosen.

    Threshold formula: free_space_gb >= max(min_free_gb, item_size_gb * 1.5)

    Args:
        disks: List of disk statuses.
        category: Media category to dispatch.
        min_free_gb: Minimum free space threshold.
        item_size_gb: Size of the item to dispatch.
        allow_create_category: If True, fall back to any disk with space
            when no disk has the category. Used for new items only.

    Returns:
        Best DiskStatus, or None if no disk qualifies.
    """
    threshold = max(min_free_gb, item_size_gb * 1.5)

    # Pass 1: disks with the category and enough space
    eligible = [
        d for d in disks
        if d.is_mounted
        and category in d.config.categories
        and d.free_space_gb >= threshold
    ]

    if eligible:
        eligible.sort(key=lambda d: d.free_space_gb, reverse=True)
        return eligible[0]

    # Pass 2: any mounted disk with enough space (create category)
    if allow_create_category:
        fallback = [
            d for d in disks
            if d.is_mounted
            and d.free_space_gb >= threshold
        ]
        if fallback:
            fallback.sort(key=lambda d: d.free_space_gb, reverse=True)
            chosen = fallback[0]
            # Warn if the chosen disk is not configured for this category
            if category not in chosen.config.categories:
                logger.warning(
                    "Category '%s' not in %s config — creating anyway "
                    "(overflow: no configured disk has space)",
                    category, chosen.config.name,
                )
            else:
                logger.info(
                    "No disk has category '%s' with space — "
                    "falling back to %s (most free)",
                    category, chosen.config.name,
                )
            return chosen

    return None
