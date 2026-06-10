"""Config model for the acquisition lobe (RP3).

Owns the ``acquire`` top-level key in the overlay layout.
Mirrors the WAL-safety validator from ``conf/models/indexer.py`` but imports
``probe_mount`` from ``core/sqlite/`` (no ``# layering: allow`` needed —
conf→core is a clean downward import).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator

from personalscraper.conf.models import paths as _paths_model
from personalscraper.conf.models._base import _StrictModel


class AcquireConfig(_StrictModel):
    """Configuration for the acquire lobe SQLite store.

    The ``db_path`` defaults to ``None``; ``Config._resolve_derived_paths``
    fills it as ``paths.data_dir / 'acquire.db'`` when unset.

    Attributes:
        db_path: Path to the acquire SQLite database. ``None`` = auto-derive.

    Raises:
        ValueError: If ``db_path`` resolves to a WAL-unsafe filesystem
            (ntfs_macfuse or unknown mount under /Volumes/).
    """

    db_path: Path | None = Field(
        default=None,
        validate_default=True,
        description="Path to acquire.db. None = auto-derive from paths.data_dir.",
    )

    @field_validator("db_path", mode="after")
    @classmethod
    def _reject_external_mount(cls, v: Path | None) -> Path | None:
        """Resolve db_path and reject WAL-unsafe filesystem types.

        Mirrors IndexerConfig._reject_external_mount but imports probe_mount
        from core/sqlite/ (conf→core is a clean downward import; no marker needed).

        Args:
            v: Raw Path value (may be relative, may be None).

        Returns:
            Absolute Path with ``~`` expanded, or None if not set.

        Raises:
            ValueError: If the resolved path is on a WAL-unsafe filesystem.
        """
        if v is None:
            return v
        resolved = v.expanduser()
        if not resolved.is_absolute():
            project_root = _paths_model._PROJECT_ROOT
            base = project_root if project_root is not None else Path.cwd()
            resolved = (base / resolved).resolve()

        try:
            from personalscraper.core.sqlite._fs_probe import probe_mount

            info = probe_mount(str(resolved))
            fs_type = info.fs_type if info is not None else None

            if (
                info is not None
                and str(resolved).startswith("/Volumes/")
                and not info.mount_point.startswith("/Volumes/")
            ):
                fs_type = None

            if fs_type in ("ntfs_macfuse", "unknown"):
                raise ValueError(
                    f"acquire.db_path {resolved} is on a WAL-unsafe filesystem "
                    f"({fs_type}). The acquire database must reside on an APFS volume."
                )

            if fs_type is None and str(resolved).startswith("/Volumes/"):
                raise ValueError(
                    f"acquire.db_path {resolved} appears to be on an external volume "
                    "whose filesystem type could not be determined. "
                    "The acquire database must reside on the internal APFS disk."
                )
        except ImportError:
            pass

        return resolved


__all__ = ["AcquireConfig"]
