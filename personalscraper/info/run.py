"""Info command runner: collect and format pipeline status.

Gathers current version, config paths, and disk statistics for the
`personalscraper info` CLI command.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from personalscraper import __version__
from personalscraper.conf.models import Config


@dataclass(frozen=True)
class DiskStatus:
    """Status snapshot for a single configured storage disk.

    Attributes:
        name: Disk identifier from DiskConfig.id (e.g. "drive_a").
        path: Mount point Path, or None if the disk path is not configured.
        mounted: True when the path exists on the filesystem.
        total_bytes: Total capacity in bytes; 0 if not mounted.
        used_bytes: Used space in bytes; 0 if not mounted.
    """

    name: str
    path: Path | None
    mounted: bool
    total_bytes: int
    used_bytes: int


@dataclass(frozen=True)
class InfoReport:
    """Aggregated status report for the `info` command.

    Attributes:
        version: Current personalscraper version string.
        staging_path: Staging directory (A TRIER) from config.
        disks: Status snapshot for each configured disk.
    """

    version: str
    staging_path: Path
    disks: list[DiskStatus]


_EMPTY_THRESHOLD_BYTES = 1_000_000  # 1 MB — below this, disk is "mounted but empty"


def _human_bytes(n: int) -> str:
    """Format a byte count as a human-readable string with appropriate unit.

    Uses 1000-based units (KB, MB, GB, TB) matching common disk labelling.

    Args:
        n: Number of bytes.

    Returns:
        String like "1.2 TB", "800 GB", "512 MB".
    """
    value = float(n)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1000.0
        if abs(value) < 1000:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} PB"


def collect_info(config: Config) -> InfoReport:
    """Gather version, config paths, and disk stats from the current environment.

    For each disk in config.disks: checks if the path exists (mounted), then
    calls shutil.disk_usage to get capacity. Non-existent paths are reported
    as NOT MOUNTED with zero byte counts.

    Args:
        config: Loaded and validated pipeline Config.

    Returns:
        InfoReport with version, paths, and per-disk DiskStatus entries.
    """
    disks: list[DiskStatus] = []
    for disk_cfg in config.disks:
        path = disk_cfg.path
        if not path.exists():
            disks.append(DiskStatus(name=disk_cfg.id, path=None, mounted=False, total_bytes=0, used_bytes=0))
            continue

        usage = shutil.disk_usage(path)
        disks.append(
            DiskStatus(
                name=disk_cfg.id,
                path=path,
                mounted=True,
                total_bytes=usage.total,
                used_bytes=usage.used,
            )
        )

    return InfoReport(
        version=__version__,
        staging_path=config.paths.staging_dir,
        disks=disks,
    )


def format_info(report: InfoReport) -> str:
    """Render an InfoReport as a plain-text human-readable string.

    Format mirrors the DESIGN.md spec: version header, Config section with
    staging path, then Disks section with per-disk status.

    Args:
        report: InfoReport produced by collect_info().

    Returns:
        Multi-line string ready to print to stdout.
    """
    lines: list[str] = []

    # Header: version
    lines.append(f"personalscraper {report.version}")
    lines.append("")

    # Config section
    lines.append("Config")
    lines.append(f"  staging: {report.staging_path}")
    lines.append("")

    # Disks section
    lines.append(f"Disks ({len(report.disks)} configured)")
    for disk in report.disks:
        if not disk.mounted:
            lines.append(f"  {disk.name:<10} -                 NOT MOUNTED")
            continue

        if disk.used_bytes < _EMPTY_THRESHOLD_BYTES:
            path_str = str(disk.path) if disk.path else "-"
            lines.append(f"  {disk.name:<10} {path_str:<25} MOUNTED BUT EMPTY")
            continue

        used_str = _human_bytes(disk.used_bytes)
        total_str = _human_bytes(disk.total_bytes)
        percent = int(disk.used_bytes / disk.total_bytes * 100) if disk.total_bytes else 0
        path_str = str(disk.path) if disk.path else "-"
        lines.append(f"  {disk.name:<10} {path_str:<25} {used_str} / {total_str} ({percent}% used)")

    return "\n".join(lines)
