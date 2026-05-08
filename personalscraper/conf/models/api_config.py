"""Pydantic models for the 5 API config files.

Implements DESIGN SS8.2-S8.6: MetadataConfig, TorrentConfig, TrackerConfig,
RankingConfig, and NotifyConfig. RankingConfig is re-exported from
api/tracker/_ranking.py so config validation and runtime ranking share
one source of truth.
"""

from pydantic import Field

from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry
from personalscraper.conf.models._base import _StrictModel

__all__ = [
    "MetadataConfig",
    "MetadataDefaults",
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


class MetadataConfig(_StrictModel):
    """Top-level metadata.json5 model.

    Attributes:
        providers: Per-provider enable/disable toggles.
        priorities: Per-use-case priority ordering.
        defaults: Language and title preferences.
    """

    providers: dict[str, MetadataProviderConfig] = Field(default_factory=dict)
    priorities: MetadataPriorities = Field(default_factory=MetadataPriorities)
    defaults: MetadataDefaults = Field(default_factory=MetadataDefaults)


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
        max_total_results: Global cap on results across all trackers.
        max_per_tracker: Cap on results from any single tracker.
        timeout_per_tracker: Per-tracker HTTP timeout in seconds.
    """

    providers: dict[str, TrackerProviderConfig] = Field(default_factory=dict)
    priority: list[str] = Field(default_factory=list)
    max_total_results: int = 50
    max_per_tracker: int = 30
    timeout_per_tracker: int = 15


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
