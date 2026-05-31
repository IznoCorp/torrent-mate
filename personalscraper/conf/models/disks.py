"""Disk storage config model."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel


class DiskConfig(_StrictModel):
    """Disque de stockage avec ses catégories acceptées.

    Attributes:
        id: Free-form disk identifier (must match ``^[a-z][a-z0-9_]*$``).
        path: Absolute mounted path.
        categories: Category IDs accepted on this disk.
        fs_type: Optional canonical filesystem-type override. When set, the
            override beats auto-detection via ``probe_mount`` (useful for
            unrecognised driver tokens such as ``fuse-t`` variants or Paragon
            NTFS). Must be one of the canonical keys: ``"ntfs_macfuse"``,
            ``"apfs"``, ``"hfsplus"``, ``"exfat"``, ``"ext4"``, ``"unknown"``.
            The field is a ``Literal``: an unrecognised value (e.g. ``"ntfs"``,
            ``"APFS"``, ``"apfs "``) raises a ``ValidationError`` at config load
            rather than silently degrading to the NTFS-safe ``"unknown"``
            capability. When ``None`` (default), the filesystem type is
            auto-detected at runtime. (The ``capability_for`` resolver keeps its
            own ``unknown`` fallback as defense-in-depth for any non-config
            path.)
    """

    id: str = Field(
        ...,
        min_length=1,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Identifiant libre (disk_a, nas_main, ...).",
    )
    path: Path = Field(..., description="Chemin monté absolu.")
    categories: Annotated[list[str], Field(min_length=1)] = Field(..., description="IDs acceptés sur ce disque.")
    fs_type: Literal["ntfs_macfuse", "apfs", "hfsplus", "exfat", "ext4", "unknown"] | None = Field(
        default=None,
        description=(
            "Optional canonical fs-type override (e.g. 'apfs', 'hfsplus', 'ntfs_macfuse'). "
            "When None, auto-detected via FsProbe at runtime. "
            "Must be one of the canonical keys; a typo (e.g. 'ntfs', 'APFS', 'apfs ') "
            "now raises a ValidationError at config load instead of silently degrading "
            "to the NTFS-safe 'unknown' capability."
        ),
    )
