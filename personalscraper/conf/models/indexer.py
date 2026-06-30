"""Media indexer sub-system config models.

Defines pydantic models for the indexer block of ``config.json5``: scan-engine
tunables, drift-detection thresholds, Spotlight integration, audit-table
retention and the SQLite ``db_path``. All defaults match the reference
``indexer.json5`` from DESIGN §5.3.

The ``IndexerConfig._reject_external_mount`` validator resolves a relative
``db_path`` against the project root (set by :func:`personalscraper.conf.loader.load_config_dir`)
rather than CWD, so the indexer database lands in the same location regardless
of where ``personalscraper`` is invoked from.
"""

from pathlib import Path

from pydantic import Field, field_validator

from personalscraper.conf.models import paths as _paths_model
from personalscraper.conf.models._base import _StrictModel


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


class PostDispatchMaintenanceConfig(_StrictModel):
    """Post-dispatch index maintenance tunables.

    Attributes:
        enabled: When ``True`` (default), automatically run per-disk
            incremental scan + relink + fix-season-counts after every
            dispatch that moved ≥1 item.
    """

    enabled: bool = Field(default=True, description="Run index maintenance automatically after dispatch.")


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
    post_dispatch_maintenance: PostDispatchMaintenanceConfig = Field(
        default_factory=PostDispatchMaintenanceConfig,
    )

    @field_validator("db_path", mode="after")
    @classmethod
    def _reject_external_mount(cls, v: Path | None) -> Path | None:
        """Resolve ``db_path`` and reject WAL-unsafe filesystem types.

        When ``db_path`` is ``None``, the Config-level ``_resolve_db_path``
        validator will fill it from ``paths.data_dir``.

        Invariants enforced here:

        1. **Absolute path.** Relative ``db_path`` values are resolved against
           the project root (config_dir.parent) at load-time so every consumer
           sees the same path regardless of where ``personalscraper`` is invoked
           from.
        2. **No WAL-unsafe mount.** SQLite WAL mode is unreliable on macFUSE-NTFS
           and network mounts. Detection is capability-aware: probe the mount
           point and reject only ``ntfs_macfuse`` (and ``unknown`` as a
           conservative fallback). A legitimate APFS / HFS+ / exFAT / ext4
           volume — even when mounted under ``/Volumes/`` — is accepted. This
           replaces the former blunt ``/Volumes/`` prefix check, which wrongly
           rejected an APFS database at e.g. ``/Volumes/Data/library.db``.

           **Effective fs-type.** ``probe_mount`` returns the *longest-prefix*
           mount for a path. A fake or unmounted ``/Volumes/X/...`` path on a
           real Darwin host therefore falls back to the root ``/`` (apfs) mount
           — there is no actual external volume there. To honour the legacy
           safety net (and keep the pre-existing ``/Volumes/`` rejection tests
           green on Darwin), a probe is only *trusted* for a ``/Volumes/`` path
           when the matched mount point is itself under ``/Volumes/`` (i.e. a
           real external volume is mounted there). Otherwise the fs-type is
           treated as undetectable.

           When the effective fs-type is undetectable (non-Darwin CI, an
           unmounted/fake path, or a root-fallback under ``/Volumes/``) AND the
           resolved path is under ``/Volumes/``, the legacy safety net applies:
           conservatively reject. Undetectable *local* paths (relative,
           ``/Users/...``, ``/tmp/...``) are accepted.

        Args:
            v: Raw Path value for db_path (may be relative, may be None).

        Returns:
            Absolute Path with ``~`` expanded, or None if not set.

        Raises:
            ValueError: If the resolved path is on a WAL-unsafe filesystem
                (detected ``ntfs_macfuse``/``unknown``, or an undetectable
                mount under ``/Volumes/``).
        """
        if v is None:
            return v
        resolved = v.expanduser()
        if not resolved.is_absolute():
            # Read at call time via module attribute so the value mutated by
            # ``load_config_dir`` is honoured (a ``from … import _PROJECT_ROOT``
            # would value-bind the original ``None`` and silently fall back to
            # CWD).
            project_root = _paths_model._PROJECT_ROOT
            base = project_root if project_root is not None else Path.cwd()
            resolved = (base / resolved).resolve()

        # Capability-aware WAL-safety check. Import here (not at module level)
        # because this is a Pydantic validator — lazy avoids the conf import
        # scanning the whole core tree at model-class definition time.
        # conf→core is a legal downward import (DESIGN: db_path WAL-safety
        # needs FsProbe).
        try:
            from personalscraper.core.sqlite._fs_probe import (
                probe_mount,  # lazy WAL-safety probe (conf→core, clean layering)
            )

            info = probe_mount(str(resolved))
            fs_type = info.fs_type if info is not None else None

            # A /Volumes/ path whose probe fell back to a NON-/Volumes/ mount
            # point (typically the root "/" apfs mount) is not actually backed
            # by an external volume — treat its fs-type as undetectable so the
            # legacy /Volumes/ safety net below still fires.
            if (
                info is not None
                and str(resolved).startswith("/Volumes/")
                and not info.mount_point.startswith("/Volumes/")
            ):
                fs_type = None

            # Reject known WAL-unsafe filesystem types outright.
            wal_unsafe = {"ntfs_macfuse", "unknown"}
            if fs_type in wal_unsafe:
                raise ValueError(
                    f"db_path '{v}' resolves to a '{fs_type}' mount, which is WAL-unsafe. "
                    "SQLite WAL mode is unreliable on macFUSE-NTFS filesystems. "
                    "Move the database to an APFS or HFS+ volume."
                )
            # Undetectable filesystem under the macOS external-mount convention:
            # conservative reject (preserves the legacy /Volumes/ safety net).
            # Detected-safe types (apfs/hfsplus/exfat/ext4) and undetectable
            # *local* paths fall through and are accepted.
            if fs_type is None and str(resolved).startswith("/Volumes/"):
                raise ValueError(
                    f"db_path '{v}' resolves under /Volumes/ which indicates an external or macFUSE mount, "
                    "and its filesystem type could not be detected. SQLite WAL mode is unreliable on such "
                    "filesystems. Move the database to the internal APFS volume (e.g. ~/.data/library.db)."
                )
        except ImportError:
            # FsProbe not yet available (bootstrap scenario) — fall back to the
            # legacy /Volumes/ heuristic as defence-in-depth.
            if str(resolved).startswith("/Volumes/"):
                raise ValueError(
                    f"db_path '{v}' resolves under /Volumes/ which may indicate an external or macFUSE mount. "
                    "SQLite WAL mode is unreliable on such filesystems."
                )

        return resolved
