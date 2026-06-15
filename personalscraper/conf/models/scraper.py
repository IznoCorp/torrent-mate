"""Scraper runtime config models (scraper, ingest, sort, process_clean, thresholds)."""

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel

__all__ = [
    "IngestConfig",
    "ProcessCleanConfig",
    "ScraperConfig",
    "SortConfig",
    "ThresholdsConfig",
]


class ScraperConfig(_StrictModel):
    """Scraper runtime tunables.

    Attributes:
        language: Primary metadata language for titles and episode names.
            Uses TMDB BCP-47 format (e.g. ``"fr-FR"``). TVDB calls are mapped
            to their 3-letter language codes internally.
        fallback_language: Fallback metadata language when ``language`` has no
            translation.
        prefer_local_title: Prefer the configured-language title over the API
            match title when available.
        episode_default_name: Prefix for the synthetic episode title used when
            the provider lacks the episode and no phantom-season remap was
            found (``"{episode_default_name} {N}"``). Default ``"Episode"``
            gives ``"Episode 8"`` for an E08 fallback.
        artwork_language: Preferred language for artwork selection (ISO 639-1).
    """

    language: str = Field(default="fr-FR", min_length=2)
    fallback_language: str = Field(default="en-US", min_length=2)
    prefer_local_title: bool = Field(default=True)
    episode_default_name: str = Field(default="Episode", min_length=1)
    artwork_language: str = Field(default="en", min_length=2)


class IngestConfig(_StrictModel):
    """Ingest step runtime tunables.

    Attributes:
        min_ratio: Minimum seeding ratio required before a completed torrent
            is eligible for ingest. Torrents whose ratio is below this
            threshold are skipped (left in qBittorrent for continued seeding).
            Default ``0.0`` disables the threshold (all completed torrents
            are eligible regardless of ratio).
    """

    min_ratio: float = Field(
        default=0.0,
        ge=0.0,
        description=("Minimum seeding ratio for ingest eligibility. 0.0 (default) disables the guard."),
    )


class SortConfig(_StrictModel):
    """Sort step runtime tunables.

    Attributes:
        verify_seed_pure: Opt-in seed-pure sort guard. When ``True``, the sort
            step asks the torrent client for the set of completed torrents
            tagged ``seed-pure`` and genuinely excludes any staging item whose
            name matches one of them (reported as a ``skipped`` result, never
            moved into the library). Enforced (the sort guard is active). The
            always-on ingest skip (phase 3) remains the primary guardrail; this
            opt-in guard is a defense-in-depth layer for items that bypassed
            ingest. Default ``False`` (guard inactive).
    """

    verify_seed_pure: bool = Field(
        default=False,
        description=(
            "Opt-in seed-pure sort guard. Enforced: when True, seed-pure-tagged "
            "completed torrents are genuinely excluded from the sort (skipped, not moved)."
        ),
    )


class ProcessCleanConfig(_StrictModel):
    """Process clean sub-step runtime tunables.

    Attributes:
        verify_seed_pure: Reserved — not yet enforced; the clean-side guard is
            intentionally not implemented (post-sort name-matching is
            unreliable). The active guardrails are the always-on ingest skip +
            the opt-in sort guard. Default ``False``.
    """

    verify_seed_pure: bool = Field(
        default=False,
        description=(
            "Reserved — not yet enforced. The clean-side seed-pure guard is intentionally "
            "not implemented (post-sort name-matching is unreliable). The active guardrails "
            "are the always-on ingest skip + the opt-in sort guard."
        ),
    )


class ThresholdsConfig(_StrictModel):
    """Operational thresholds for the pipeline.

    Attributes:
        min_free_space_staging_gb: Minimum free space on staging drive (GB)
            before ingest.
        min_free_space_disk_gb: Minimum free space on storage disks (GB)
            before dispatch.
        circuit_breaker_threshold: Consecutive errors before opening circuit
            breaker for API clients.
        circuit_breaker_cooldown: Seconds to wait before retrying after
            circuit breaker opens.
    """

    min_free_space_staging_gb: int = Field(default=20, ge=0)
    min_free_space_disk_gb: float = Field(default=100, ge=0)
    circuit_breaker_threshold: int = Field(default=5, ge=1)
    circuit_breaker_cooldown: int = Field(default=300, ge=0)
