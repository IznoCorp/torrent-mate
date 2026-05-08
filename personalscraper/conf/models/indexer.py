"""Media indexer sub-system config models."""

from pathlib import Path

from pydantic import Field, field_validator

from personalscraper.conf.models._base import _StrictModel
from personalscraper.conf.models.paths import _PROJECT_ROOT


class IndexerScanConfig(_StrictModel):
    """Scan-engine tunables for the media indexer.

    Attributes:
        budget_seconds: Hard time cap per scan run in seconds. Crash-resume
            picks up where the scan left off.
        checkpoint_every_n_files: Write a checkpoint row every N files so a
            crashed scan resumes from a known-good point.
        max_workers_total: Maximum parallel scan workers, capped at the number
            of currently mounted disks.
        n_strikes_for_softdelete: Number of consecutive missed scans before a
            file is soft-deleted (``deleted_at`` set).
        read_rate_mb_per_sec: IO throttle in MB/s. ``None`` = unlimited.
        drop_indexes_during_full_scan: Drop non-PK indexes during a full
            cold scan and rebuild them on finish.
        paranoia_window_seconds: Look-back window in seconds for the
            quick-mode paranoia branch.
    """

    budget_seconds: int = Field(default=1800, gt=0, description="Hard time cap per scan run in seconds.")
    checkpoint_every_n_files: int = Field(default=100, gt=0, description="Write checkpoint every N files.")
    max_workers_total: int = Field(default=4, gt=0, description="Max parallel scan workers.")
    n_strikes_for_softdelete: int = Field(default=3, gt=0, description="Missed scans before soft-delete.")
    read_rate_mb_per_sec: float | None = Field(
        default=None,
        ge=0.0,
        description="IO throttle in MB/s. None = unlimited.",
    )
    drop_indexes_during_full_scan: bool = Field(
        default=True,
        description="Drop and rebuild non-PK indexes around a full cold scan for faster bulk inserts.",
    )
    paranoia_window_seconds: int = Field(
        default=86400,
        ge=0,
        description=(
            "Look-back window (seconds) for the quick-mode paranoia branch (DESIGN §17.1). "
            "scan_event rows with event LIKE 'outbox.%' within this window are re-checked "
            "against on-disk state regardless of dir-mtime status. "
            "Set to 0 to disable the paranoia branch entirely."
        ),
    )


class IndexerDriftConfig(_StrictModel):
    """Drift detection tunables for the media indexer.

    Attributes:
        merkle_delta_freeze_threshold: Halt the scan if the Merkle delta
            exceeds this fraction (suggests a bulk restore). Set to 1.0 to
            disable the freeze entirely.
    """

    merkle_delta_freeze_threshold: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description=(
            "Halt scan if Merkle delta exceeds this fraction (suggests bulk restore). "
            "Set to 1.0 to disable the freeze entirely."
        ),
    )


class IndexerSpotlightConfig(_StrictModel):
    """Spotlight (CoreSpotlight / mdutil) integration tunables.

    Note: macFUSE-NTFS volumes are not Spotlight-indexable. These settings
    apply only to APFS volumes where Spotlight is available.

    Attributes:
        use_when_available: Delegate change detection to Spotlight when available.
    """

    use_when_available: bool = Field(
        default=True,
        description="Delegate change detection to Spotlight when available.",
    )


class IndexerLogConfig(_StrictModel):
    """Retention policy for indexer audit tables.

    Attributes:
        deleted_item_retention_days: How many days to keep ``deleted_item``
            tombstone rows before hard-purge by ``purge_old_tombstones``.
    """

    deleted_item_retention_days: int = Field(
        default=365,
        gt=0,
        description="Days to retain deleted_item tombstone rows before hard-purge.",
    )


class IndexerConfig(_StrictModel):
    """Configuration for the media indexer sub-system (DESIGN §5.3).

    All defaults match the reference indexer.json5 from the design doc.
    The ``db_path`` is validated to reject external / macFUSE mounts because
    SQLite WAL mode is unreliable on network or FUSE filesystems.

    Attributes:
        db_path: Path to the SQLite library database. Relative paths are
            resolved against the current working directory at load-time and
            stored as absolute paths. Must not reside on a macFUSE or external
            mount. Recommended: place the DB under ``paths.data_dir``.
        scan: Scan-engine tunables.
        drift: Drift detection tunables.
        spotlight: Spotlight integration tunables.
        log: Audit-table retention policy.
    """

    db_path: Path | None = Field(
        default=None,
        description=(
            "Path to the SQLite library database. Defaults to paths.data_dir / 'library.db' "
            "when not set. Must not be on an external/macFUSE mount."
        ),
        validate_default=True,
    )
    scan: IndexerScanConfig = Field(default_factory=IndexerScanConfig)
    drift: IndexerDriftConfig = Field(default_factory=IndexerDriftConfig)
    spotlight: IndexerSpotlightConfig = Field(default_factory=IndexerSpotlightConfig)
    log: IndexerLogConfig = Field(default_factory=IndexerLogConfig)

    @field_validator("db_path", mode="after")
    @classmethod
    def _reject_external_mount(cls, v: Path | None) -> Path | None:
        """Resolve ``db_path`` to an absolute path and reject macFUSE / external mounts.

        When ``db_path`` is ``None``, the Config-level ``_resolve_db_path``
        validator will fill it from ``paths.data_dir``.

        Two invariants enforced here:

        1. **Absolute path.** Relative ``db_path`` values are resolved against
           the project root (config_dir.parent) at load-time so every consumer
           sees the same path regardless of where ``personalscraper`` is invoked
           from.
        2. **No external mount.** SQLite WAL mode is unreliable on macFUSE-NTFS
           and network mounts. The database must live on the internal APFS
           volume. Detection heuristic: the resolved path starts with
           ``/Volumes/`` (macOS convention for all external mounts).

        Args:
            v: Raw Path value for db_path (may be relative, may be None).

        Returns:
            Absolute Path with ``~`` expanded, or None if not set.

        Raises:
            ValueError: If the resolved path is under ``/Volumes/``.
        """
        if v is None:
            return v
        resolved = v.expanduser()
        if not resolved.is_absolute():
            base = _PROJECT_ROOT if _PROJECT_ROOT is not None else Path.cwd()
            resolved = (base / resolved).resolve()
        if str(resolved).startswith("/Volumes/"):
            raise ValueError(
                f"db_path '{v}' resolves under /Volumes/ which indicates an external or macFUSE mount. "
                "SQLite WAL mode is unreliable on such filesystems. "
                "Move the database to the internal APFS volume (e.g. ~/.data/library.db)."
            )
        return resolved
