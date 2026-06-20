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
    "torr9": ["TORR9_USERNAME", "TORR9_PASSWORD"],
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


# ---------------------------------------------------------------------------
# Optional secrets (non-gating) — tracker-economy RP2
# ---------------------------------------------------------------------------

PROVIDER_OPTIONAL_SECRETS: dict[str, list[str]] = {
    # Announce passkeys — never consulted by resolve_active(); a missing
    # passkey never deactivates a tracker. Consumers (Vague 5 Ratio C1,
    # Seed-Safety O2) decide what to do with a missing value.
    "lacale": ["LACALE_PASSKEY"],
    "c411": ["C411_PASSKEY"],
    "torr9": ["TORR9_PASSKEY"],
}


def resolve_optional_secret(
    provider: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, str | None]:
    """Resolve a provider's optional, non-activation-gating secrets from the environment.

    Unlike :data:`PROVIDER_CREDS` (consumed by :func:`resolve_active` to gate
    activation), an absent value here returns ``None`` and never deactivates
    the provider nor fails boot. A blank/empty-string value is likewise
    normalized to ``None`` (the load-bearing ``env.get(k) or None``), so a
    future consumer is not surprised by an empty string slipping through.

    Args:
        provider: Provider name (e.g. ``"lacale"``, ``"c411"``).
        env: Secret source (defaults to ``os.environ``; injectable for testing).

    Returns:
        Dict mapping each optional secret name to its value or ``None`` if
        absent or blank. Empty dict for providers not in
        ``PROVIDER_OPTIONAL_SECRETS``.
    """
    if env is None:
        env = os.environ

    keys = PROVIDER_OPTIONAL_SECRETS.get(provider, [])
    return {k: env.get(k) or None for k in keys}
