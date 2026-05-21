"""Provider activation resolution.

Implements DESIGN S8.7: PROVIDER_CREDS hardcoded credential mapping and
resolve_active() for checking enabled toggles against credential presence.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from personalscraper.logger import get_logger

log = get_logger("api.activation")

PROVIDER_CREDS: dict[str, list[str]] = {
    "tmdb": ["TMDB_API_KEY"],
    "tvdb": ["TVDB_API_KEY"],
    "omdb": ["OMDB_API_KEY"],
    # IMDb + Rotten Tomatoes are *façades* over the OMDb HTTP backend
    # (DESIGN §4). They share the OMDb credential — provisioning either
    # façade is gated on a single ``OMDB_API_KEY``. Both façades
    # consume the same :class:`OMDbAdapter` instance at construction
    # time so the rate-limit / circuit-breaker budget stays shared.
    "imdb": ["OMDB_API_KEY"],
    "rotten_tomatoes": ["OMDB_API_KEY"],
    # Trakt app-only auth (search/details/ratings/related/trending) needs only CLIENT_ID
    # in the trakt-api-key header. CLIENT_SECRET is OAuth-only and out of scope (per
    # DESIGN S1.2): OAuth user endpoints are deliberately not supported here.
    "trakt": ["TRAKT_CLIENT_ID"],
    "qbittorrent": ["QBIT_USERNAME", "QBIT_PASSWORD"],
    "transmission": ["TRANSMISSION_USERNAME", "TRANSMISSION_PASSWORD"],
    "lacale": ["LACALE_API_KEY"],
    "c411": ["C411_API_KEY"],
    "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "healthchecks": ["HEALTHCHECK_URL"],
}


def resolve_active(
    providers: dict[str, Any],
    family: str,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    """Return names of providers that are enabled AND have all required creds.

    Args:
        providers: Dict of provider_name → config object with ``enabled`` attr.
        family: Logging-only label attached to structured log records
                (e.g. "metadata", "torrent", "tracker", "notify").
        env: Credential source (defaults to os.environ; pass-through for testability).

    Returns:
        Provider names sorted by insertion order in `providers`.
    """
    if env is None:
        env = os.environ

    active: list[str] = []
    for name, cfg in providers.items():
        if not getattr(cfg, "enabled", False):
            continue

        required = PROVIDER_CREDS.get(name, [])
        missing = [k for k in required if not env.get(k)]

        if missing:
            log.warning(
                "provider_disabled",
                family=family,
                provider=name,
                missing=missing,
            )
            continue

        active.append(name)

    return active
