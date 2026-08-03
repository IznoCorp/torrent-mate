"""Config model for the acquisition lobe (RP3).

Owns the ``acquire`` top-level key in the overlay layout.
Mirrors the WAL-safety validator from ``conf/models/indexer.py`` but imports
``probe_mount`` from ``core/sqlite/`` (no ``# layering: allow`` needed —
conf→core is a clean downward import).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator, model_validator

from personalscraper.api._units import ByteSize  # layering: allow
from personalscraper.conf.models import paths as _paths_model
from personalscraper.conf.models._base import _StrictModel


class CadenceTierConfig(_StrictModel):
    """Config for one Hot/Warm/Cold tier.

    Attributes:
        max_age_hours: Upper age bound (exclusive) for this tier, in hours.
        interval_minutes: Minimum gap between searches in this tier, in minutes.
    """

    max_age_hours: int
    interval_minutes: int


def _default_tiers() -> list[CadenceTierConfig]:
    """Return the canonical Hot/Warm/Cold tier defaults (DESIGN §3 frozen decision).

    Returns:
        Ordered list of the three canonical tiers (Hot, Warm, Cold).
    """
    return [
        CadenceTierConfig(max_age_hours=72, interval_minutes=120),  # Hot
        CadenceTierConfig(max_age_hours=336, interval_minutes=1440),  # Warm (14d)
        CadenceTierConfig(max_age_hours=720, interval_minutes=10080),  # Cold (30d)
    ]


class CadenceConfig(_StrictModel):
    """Global cadence policy config for the acquisition lobe.

    Attributes:
        tiers: Ordered list of :class:`CadenceTierConfig` (ascending max_age_hours).
            Defaults to the canonical Hot/Warm/Cold policy (DESIGN §3).
        cutoff_days: Age in days at which a wanted item is abandoned. Must exceed
            the last tier's max_age_hours / 24. Default: 30.
    """

    tiers: list[CadenceTierConfig] = Field(default_factory=_default_tiers)
    cutoff_days: int = 30

    @model_validator(mode="after")
    def _validate_tier_ladder(self) -> CadenceConfig:
        """Reject invalid tier ladders (DESIGN §4, ACCEPTANCE criterion 3).

        Enforces:
            - ``tiers`` is non-empty;
            - every ``max_age_hours > 0`` and every ``interval_minutes > 0``;
            - ``tiers`` are strictly increasing by ``max_age_hours``;
            - ``cutoff_days * 24 >= tiers[-1].max_age_hours`` (cutoff at or
              beyond the last tier — the canonical policy sets them equal at
              720h/30d, so the bound is ``>=`` not strict ``>``).

        Returns:
            The validated model instance.

        Raises:
            ValueError: If any invariant is violated (Pydantic wraps this into
                a ``ValidationError``).
        """
        if not self.tiers:
            raise ValueError("CadenceConfig.tiers must be non-empty.")

        for tier in self.tiers:
            if tier.max_age_hours <= 0:
                raise ValueError(f"CadenceConfig tier max_age_hours must be > 0, got {tier.max_age_hours}.")
            if tier.interval_minutes <= 0:
                raise ValueError(f"CadenceConfig tier interval_minutes must be > 0, got {tier.interval_minutes}.")

        for prev, curr in zip(self.tiers, self.tiers[1:]):
            if curr.max_age_hours <= prev.max_age_hours:
                raise ValueError(
                    "CadenceConfig.tiers must be strictly increasing by max_age_hours; "
                    f"got {prev.max_age_hours} >= {curr.max_age_hours}."
                )

        if self.cutoff_days * 24 < self.tiers[-1].max_age_hours:
            raise ValueError(
                "CadenceConfig.cutoff_days must reach at least the last tier; "
                f"cutoff_days*24 ({self.cutoff_days * 24}h) must be >= "
                f"the last tier max_age_hours ({self.tiers[-1].max_age_hours}h)."
            )

        return self


class BandwidthConfig(_StrictModel):
    """Per-torrent and global bandwidth caps for seed safety (O4).

    Values are in bytes per second.  Human-readable strings like ``"5MB"`` are
    coerced via :class:`ByteSize`.  ``None`` means "leave the current client
    setting untouched" (D2: zero is NOT the unlimited sentinel — it is rejected).

    Attributes:
        per_torrent_down: Per-torrent download cap, bytes/s. ``None`` = no cap.
        per_torrent_up: Per-torrent upload cap, bytes/s. ``None`` = no cap.
        global_down: Global download cap applied to the client, bytes/s.
            ``None`` = leave the current qBittorrent setting alone.
        global_up: Global upload cap applied to the client, bytes/s.
            ``None`` = leave the current qBittorrent setting alone.
    """

    per_torrent_down: int | None = None
    per_torrent_up: int | None = None
    global_down: int | None = None
    global_up: int | None = None

    @field_validator(
        "per_torrent_down",
        "per_torrent_up",
        "global_down",
        "global_up",
        mode="before",
    )
    @classmethod
    def _coerce_bytesize(cls, v: object) -> object:
        """Coerce human-readable byte-size strings to integer bytes.

        Delegates to :class:`ByteSize.parse` for string values; passes integers
        and ``None`` through unchanged (D10).

        Args:
            v: Raw value from config — can be ``str``, ``int``, or ``None``.

        Returns:
            Integer byte count, or ``None``.
        """
        if isinstance(v, str):
            return ByteSize.parse(v).bytes
        return v

    @field_validator("per_torrent_down", "per_torrent_up", "global_down", "global_up")
    @classmethod
    def _reject_zero(cls, v: int | None) -> int | None:
        """Reject zero and negative values.

        Zero is NOT the unlimited sentinel — unlimited is expressed by omitting
        the key (D2).  The qBittorrent wire value 0 is produced only by the
        mapper, never written by the operator.

        Args:
            v: The value after coercion.

        Returns:
            The value unchanged if valid.

        Raises:
            ValueError: If the value is ``<= 0``.
        """
        if v is not None and v <= 0:
            raise ValueError(
                f"Bandwidth cap must be > 0 (None = no cap); got {v}. "
                "Use None or omit the key to leave the client setting untouched."
            )
        return v


class AcquireConfig(_StrictModel):
    """Configuration for the acquire lobe SQLite store.

    The ``db_path`` defaults to ``None``; ``Config._resolve_derived_paths``
    fills it as ``paths.data_dir / 'acquire.db'`` when unset.

    Attributes:
        db_path: Path to the acquire SQLite database. ``None`` = auto-derive.
        cadence: Global Hot/Warm/Cold cadence policy (DESIGN §3). Defaults to
            the canonical policy via :class:`CadenceConfig`.
        bandwidth: Per-torrent and global bandwidth caps for seed safety (O4).
            Defaults to all-``None`` (no caps).

    Raises:
        ValueError: If ``db_path`` resolves to a WAL-unsafe filesystem
            (ntfs_macfuse or unknown mount under /Volumes/).
    """

    db_path: Path | None = Field(
        default=None,
        validate_default=True,
        description="Path to acquire.db. None = auto-derive from paths.data_dir.",
    )
    cadence: CadenceConfig = Field(default_factory=CadenceConfig)
    bandwidth: BandwidthConfig = Field(default_factory=BandwidthConfig)

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
            project_root = _paths_model._PROJECT_ROOT.get()
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


__all__ = ["AcquireConfig", "BandwidthConfig", "CadenceConfig", "CadenceTierConfig"]
