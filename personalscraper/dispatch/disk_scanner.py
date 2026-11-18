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

from personalscraper.conf.environment import is_sandboxed
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.sandbox_guard import SandboxGuardError, assert_sandbox_root
from personalscraper.core.sqlite._fs_probe import is_mounted as _volume_is_mounted
from personalscraper.logger import get_logger

log = get_logger("disk_scanner")


@dataclass
class DiskStatus:
    """Current runtime status of a storage disk.

    Attributes:
        config: Disk configuration (Pydantic DiskConfig from conf.models).
        free_space_gb: Available free space in GB (0.0 if unmounted or unreadable).
        is_mounted: Whether the disk's volume is really mounted (its folder is not
            merely present on the system disk); in a sandbox also whether the
            root holds the sandbox's marker.
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
    is_mounted = _volume_is_mounted(config.path)
    free_space_gb = 0.0

    if is_mounted and is_sandboxed():
        # A sandbox: a root nobody marked as this sandbox's own reads as not mounted,
        # so nothing is dispatched to it (the same refusal path as a missing disk).
        try:
            assert_sandbox_root(config.path)
        except SandboxGuardError as exc:
            log.error("preprod_root_refused", disk=config.id, error=str(exc))
            is_mounted = False

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
