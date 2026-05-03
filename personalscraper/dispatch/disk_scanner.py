"""Disk scanner: free space queries and runtime disk status.

Scans storage disks for mount status and available space. The disk-to-category
mapping is driven by the loaded split configuration (``Config.disks``).

Key design decisions:
    - Storage categories come from ``Config.disks``.
    - ``get_disk_configs(config)`` returns ``config.disks`` directly.
    - ``DiskStatus`` is a pure runtime state dataclass.
"""

import shutil
from dataclasses import dataclass

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

    Args:
        config: The loaded and validated Config instance (conf/models.py).

    Returns:
        List of DiskConfig models, one per disk declared in storage config.
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
