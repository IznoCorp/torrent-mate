"""Shared provider-candidate search for scrape decisions.

Factored out of the ``POST /api/decisions/{id}/search`` route so that BOTH the
interactive search endpoint AND the staging enqueue path seed candidates through
the *same* provider matchers — never a hand-rolled second search mechanism
(product-intent.md §3: a non-matched item must enter the resolution selector WITH
proposals).

The helpers raise :class:`ProviderSearchError` on any client-build or provider
failure. Each caller decides what that means:

* interactive search (``search_decision``) maps it to an HTTP 502;
* staging enqueue (``enqueue_staging_decision``) treats it fail-soft — the decision
  is still created, but with ``candidates_seeded=False`` so the UI shows an explicit
  "no automatic proposal" state instead of a silently empty grid.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from fastapi import Request

    from personalscraper.scraper.decision_candidate import DecisionCandidate

logger = get_logger(__name__)


class ProviderSearchError(Exception):
    """Raised when provider-backed candidate search cannot complete.

    Wraps both provider-registry build failures (missing API keys / disabled
    providers) and per-provider search failures so callers handle a single
    exception type.
    """


def build_provider_clients(request: Request) -> tuple[object, object]:
    """Create request-scoped TMDB and TVDB clients for a candidate search.

    Builds a fresh :class:`AppContext` with a :class:`ProviderRegistry` for this
    single request — never stored on ``app.state`` (composition-boundary rule).
    The AppContext build is expensive relative to a pure-db route, but live
    provider search is an infrequent operator action, not a hot polling endpoint.

    Args:
        request: The incoming FastAPI request (carries ``app.state.config`` and
            ``app.state.settings``).

    Returns:
        A ``(tmdb_client, tvdb_client)`` tuple of raw provider client objects; the
        caller casts them to the specific types it needs.

    Raises:
        ProviderSearchError: When the provider registry cannot be built (missing
            API keys or a misconfigured/disabled provider).
    """
    from personalscraper.cli_helpers import _build_app_context

    config = request.app.state.config
    settings = request.app.state.settings

    try:
        app_context = _build_app_context(config, settings)
        # provider_registry.get raises UnknownProviderError when a provider is not
        # registered (disabled in the registry overlay) — keep it inside the try so
        # it maps to ProviderSearchError, not an untyped 500.
        tmdb_client = app_context.provider_registry.get("tmdb")
        tvdb_client = app_context.provider_registry.get("tvdb")
    except Exception as exc:
        logger.error("decisions_search_registry_failed", error=str(exc))
        raise ProviderSearchError("Provider registry unavailable") from exc

    return tmdb_client, tvdb_client


def search_candidates(
    request: Request,
    media_kind: str,
    title: str,
    year: int | None,
) -> list[DecisionCandidate]:
    """Return scored provider candidates for a title/year, by media kind.

    Delegates to the detailed confidence matchers
    (:func:`~personalscraper.scraper.confidence.match_movie_detailed` for movies,
    :func:`~personalscraper.scraper.confidence.match_tvshow_detailed` for shows).
    This is the single provider-search entry point shared by the interactive
    search route and the enqueue-seeding path.

    Args:
        request: The incoming FastAPI request (used to build provider clients).
        media_kind: ``'movie'`` or ``'tvshow'``.
        title: Search title (the operator-editable guess, not necessarily the
            folder-derived one).
        year: Optional release/first-air year to disambiguate.

    Returns:
        A list of scored :class:`DecisionCandidate` objects (possibly empty when
        the providers genuinely return no match).

    Raises:
        ProviderSearchError: On client-build failure or a provider search error.
    """
    tmdb_client, tvdb_client = build_provider_clients(request)

    if media_kind == "movie":
        from personalscraper.scraper.confidence import match_movie_detailed

        try:
            _, candidates = match_movie_detailed(tmdb_client, title, year)
        except Exception as exc:
            logger.error("decisions_search_movie_failed", error=str(exc))
            raise ProviderSearchError(f"TMDB search failed: {exc}") from exc
    else:
        from personalscraper.scraper.confidence import match_tvshow_detailed

        try:
            _, candidates = match_tvshow_detailed(tvdb_client, tmdb_client, title, year)
        except Exception as exc:
            logger.error("decisions_search_tvshow_failed", error=str(exc))
            raise ProviderSearchError(f"Provider search failed: {exc}") from exc

    return candidates
