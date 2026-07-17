"""Cross-family helpers for consuming capability protocols.

A collection primitive that iterates a heterogeneous provider list
and filters by capability via :func:`isinstance` against the
``@runtime_checkable`` protocols introduced in sub-phase 1.2 and 1.5 :

- :func:`gather_ratings` — bundle ratings from every
  :class:`~personalscraper.api.metadata._contracts.RatingProvider`.

Cross-provider ID resolution is owned by the external-ids flow
(``scraper._xref`` + the indexer backfill), not by a helper here.

Plus :exc:`ProviderFeatureUnavailable` — a typed business exception
raised by a client that *declares* a capability but cannot fulfil it
for a specific request (e.g. OMDb returns a payload with no Rotten
Tomatoes entry for a given movie). Callers catch it and continue ;
``None`` already covers the absence-of-data case at the protocol level
— ``ProviderFeatureUnavailable`` is reserved for the structural
mismatch case (DESIGN §4).
"""

from __future__ import annotations

from typing import Any

from personalscraper.api.metadata._base import Notations
from personalscraper.api.metadata._contracts import RatingProvider


class ProviderFeatureUnavailable(Exception):
    """Raised when a provider declares a capability but cannot fulfil this call.

    Distinct from ``return None`` semantics : a ``None`` rating means
    the provider was queried successfully and reported no score, while
    ``ProviderFeatureUnavailable`` means the provider cannot answer
    this specific request at all (missing field in the upstream
    payload, deprecated endpoint, …). Callers may swallow the
    exception and move on without treating it as a hard failure.

    Attributes:
        provider: Provider identifier (``"omdb"``, ``"tmdb"``, …).
        feature: Capability name or method name that was attempted.
        reason: Human-readable cause for logging / telemetry.
    """

    def __init__(self, provider: str, feature: str, reason: str) -> None:
        self.provider = provider
        self.feature = feature
        self.reason = reason
        super().__init__(f"{provider} cannot fulfil {feature}: {reason}")


def gather_ratings(providers: list[Any], provider_id: str) -> list[Notations]:
    """Collect ratings from every ``RatingProvider``-capable entry.

    Filters the heterogeneous ``providers`` list with
    :func:`isinstance` against :class:`RatingProvider`, calls
    :meth:`RatingProvider.get_rating` on each match, and flattens the
    non-empty results into a single list of :class:`Notations` (the
    existing dataclass from ``api.metadata._base``).

    Providers returning ``None`` are silently skipped — that signals
    "queried successfully, no rating". Providers returning an empty
    list are also skipped (same semantics). Providers that raise
    :exc:`ProviderFeatureUnavailable` are caught here and ignored so
    callers do not need to wrap every helper invocation in a
    ``try/except``.

    Args:
        providers: Heterogeneous list of provider client instances.
        provider_id: Provider-side identifier passed to every
            :meth:`get_rating` call.

    Returns:
        Flattened list of :class:`Notations` from every capable
        provider. Empty list when no provider answers.
    """
    results: list[Notations] = []
    for provider in providers:
        if not isinstance(provider, RatingProvider):
            continue
        try:
            ratings = provider.get_rating(provider_id)
        except ProviderFeatureUnavailable:
            continue
        if ratings:
            results.extend(ratings)
    return results


__all__ = [
    "ProviderFeatureUnavailable",
    "gather_ratings",
]
