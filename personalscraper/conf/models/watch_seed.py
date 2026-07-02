"""Watch + cross-seed configuration models (watch-seed feature).

See docs/features/watch-seed/DESIGN.md §Config.
"""

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel


class WatchConfig(_StrictModel):
    """Watcher daemon configuration.

    Attributes:
        enabled: Global kill-switch for the watcher daemon. When False,
            ``personalscraper watch`` exits immediately.
        poll_interval_s: Seconds between poll cycles (default 60).
        debounce_s: Quiet window after a pipeline trigger — new completions
            do not fire another run during this window (default 900 = 15 min).
        safety_net_hours: If no successful pipeline run for this many hours,
            fire a safety-net run regardless of debounce (default 24).
    """

    enabled: bool = False
    poll_interval_s: int = Field(default=60, ge=10, le=3600)
    debounce_s: int = Field(default=900, ge=60, le=86400)
    safety_net_hours: int = Field(default=24, ge=1, le=168)


class CrossSeedConfig(_StrictModel):
    """Cross-seeding engine configuration.

    Attributes:
        enabled: Global kill-switch. When False, all cross-seed activity
            (per-completion + sweep) is disabled.
        max_searches_per_day: Daily quota for search operations (back-catalog
            sweep). Per-completion searches are NOT counted against this quota
            (they are targeted, one hash = one search).
        min_delay_between_searches_s: Minimum seconds between two search
            operations (throttle).
        exclude_recent_search_days: Skip torrents whose info_hash was already
            searched within this many days.
    """

    enabled: bool = False
    max_searches_per_day: int = Field(default=250, ge=1)
    min_delay_between_searches_s: int = Field(default=30, ge=5)
    exclude_recent_search_days: int = Field(default=3, ge=1)
