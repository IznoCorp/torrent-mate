"""Pydantic models for the 5 API config files.

Implements DESIGN SS8.2-S8.6: MetadataConfig, TorrentConfig, TrackerConfig,
RankingConfig, and NotifyConfig. RankingConfig is re-exported from
api/tracker/_ranking.py so config validation and runtime ranking share
one source of truth.
"""

from pydantic import Field, model_validator

from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry
from personalscraper.conf.models._base import _StrictModel

__all__ = [
    "MetadataConfig",
    "MetadataDefaults",
    "MetadataEpisodeScrapingPolicy",
    "MetadataPriorities",
    "MetadataProviderConfig",
    "NotifyConfig",
    "NotifyProviderConfig",
    "RankingBonuses",
    "RankingConfig",
    "RankingCriterion",
    "ThresholdEntry",
    "TorrentClientEntry",
    "TorrentConfig",
    "TrackerConfig",
    "TrackerProviderConfig",
]

# ---------------------------------------------------------------------------
# Metadata config (DESIGN S8.2)
# ---------------------------------------------------------------------------


class MetadataProviderConfig(_StrictModel):
    """Per-provider toggle in metadata.json5.

    Attributes:
        enabled: Whether this provider is active.
    """

    enabled: bool = True


class MetadataPriorities(_StrictModel):
    """Per-use-case provider priority ordering.

    Each field maps provider name → priority (lower = higher priority).
    """

    movie_scraping: dict[str, int] = Field(default_factory=dict)
    series_scraping: dict[str, int] = Field(default_factory=dict)
    episode_scraping: dict[str, int] = Field(default_factory=dict)
    recommendations: dict[str, int] = Field(default_factory=dict)
    notations: dict[str, int] = Field(default_factory=dict)


class MetadataDefaults(_StrictModel):
    """Default settings for metadata scraping.

    Attributes:
        language: Preferred language code (e.g. "fr-FR").
        fallback_language: Fallback when primary language is unavailable.
        prefer_local_title: Use localized titles when available.
    """

    language: str = "fr-FR"
    fallback_language: str = "en-US"
    prefer_local_title: bool = True


class MetadataEpisodeScrapingPolicy(_StrictModel):
    """Episode scraping behavior contract (provider lock + rename policy).

    These flags lock the episode-scraping flow against a recurring regression:
    previously, when a series matched on TVDB but its episodes were missing
    (empty season payload), the code fell back to TMDB at episode level.
    This violates the invariant "TVDB-first for series; once matched on a
    provider, stay on that provider for its episodes".

    Attributes:
        lock_to_series_provider: When True (default), episodes are fetched
            ONLY from the provider that matched the series. The
            ``episode_scraping`` priority list is bypassed in this mode.
            When False, the legacy behavior is restored: providers are tried
            in order of ``priorities.episode_scraping`` regardless of which
            provider matched the series.
        allow_synthetic_rename_on_unmatched: When False (default), files
            whose (season, episode) is absent from the locked provider's
            catalog stay at the show-folder root with their raw filename —
            no rename, no ``Saison NN/`` directory created. When True,
            the legacy behavior is restored: file is renamed with a
            synthetic ``"{episode_default_name} N"`` title.
            NOTE: this is distinct from the case where the provider returns
            an episode object with an empty/None ``name`` — that case
            legitimately produces ``"Episode N"`` and is unaffected.
    """

    lock_to_series_provider: bool = True
    allow_synthetic_rename_on_unmatched: bool = False


class MetadataConfig(_StrictModel):
    """Top-level metadata.json5 model.

    Attributes:
        providers: Per-provider enable/disable toggles.
        priorities: Per-use-case priority ordering.
        defaults: Language and title preferences.
        episode_scraping_policy: Provider-lock and rename-on-unmatched contract.
    """

    providers: dict[str, MetadataProviderConfig] = Field(default_factory=dict)
    priorities: MetadataPriorities = Field(default_factory=MetadataPriorities)
    defaults: MetadataDefaults = Field(default_factory=MetadataDefaults)
    episode_scraping_policy: MetadataEpisodeScrapingPolicy = Field(default_factory=MetadataEpisodeScrapingPolicy)


# ---------------------------------------------------------------------------
# Torrent config (DESIGN S8.3)
# ---------------------------------------------------------------------------


class TorrentClientEntry(_StrictModel):
    """Configuration for a single torrent client.

    Attributes:
        enabled: Whether this client is available.
        host: Hostname or IP address.
        port: WebUI port number.
    """

    enabled: bool = True
    host: str = "localhost"
    port: int = 8080


class TorrentConfig(_StrictModel):
    """Top-level torrent.json5 model.

    Attributes:
        active: Name of the ONE client the pipeline uses.
        clients: Per-client configuration keyed by provider name.
    """

    active: str = ""
    clients: dict[str, TorrentClientEntry] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tracker config (DESIGN S8.4)
# ---------------------------------------------------------------------------


class TrackerProviderConfig(_StrictModel):
    """Per-tracker toggle in tracker.json5.

    Attributes:
        enabled: Whether this tracker is active.
    """

    enabled: bool = False


class TrackerConfig(_StrictModel):
    """Top-level tracker.json5 model.

    Attributes:
        providers: Per-tracker enable/disable toggles.
        priority: Ordered list of tracker names (first = highest priority).
            Used as the fallback when no ``priority_by_media_type``
            override applies to the call.
        priority_by_media_type: Optional ``{media_type: [tracker, …]}``
            overrides used by :class:`~personalscraper.api.tracker._registry.TrackerRegistry`
            (provider-ids feature, sub-phase 12.3 — DESIGN §6.7).
            Every list must be a subset of ``providers.keys()`` —
            references to unknown trackers are rejected at validation
            time so the runtime never silently skips a typo.
        max_total_results: Global cap on results across all trackers.
        max_per_tracker: Cap on results from any single tracker.
        timeout_per_tracker: Per-tracker HTTP timeout in seconds.
    """

    providers: dict[str, TrackerProviderConfig] = Field(default_factory=dict)
    priority: list[str] = Field(default_factory=list)
    priority_by_media_type: dict[str, list[str]] = Field(default_factory=dict)
    max_total_results: int = 50
    max_per_tracker: int = 30
    timeout_per_tracker: int = 15

    @model_validator(mode="after")
    def _validate_priority_by_media_type(self) -> "TrackerConfig":
        """Reject ``priority_by_media_type`` references to unknown trackers.

        DESIGN §6.7 — every list value must be a subset of
        ``providers.keys()``. Typos are surfaced at config-load time
        rather than silently producing an empty search at runtime.
        """
        known = set(self.providers)
        for media_type, order in self.priority_by_media_type.items():
            unknown = [name for name in order if name not in known]
            if unknown:
                raise ValueError(f"priority_by_media_type[{media_type!r}] references unknown trackers: {unknown}")
        return self


# ---------------------------------------------------------------------------
# Notify config (DESIGN S8.6)
# ---------------------------------------------------------------------------


class NotifyProviderConfig(_StrictModel):
    """Per-notifier toggle in notify.json5.

    Attributes:
        enabled: Whether this notifier is active.
    """

    enabled: bool = False


class NotifyConfig(_StrictModel):
    """Top-level notify.json5 model.

    Attributes:
        telegram: Telegram bot configuration.
        healthchecks: Healthchecks ping configuration.
    """

    telegram: NotifyProviderConfig = Field(default_factory=NotifyProviderConfig)
    healthchecks: NotifyProviderConfig = Field(default_factory=NotifyProviderConfig)
