"""Fail-soft series title resolver for the acquire lobe (Follow D1).

Resolves a canonical human-readable title for a :class:`~personalscraper.core.identity.MediaRef`
by calling the first available ``TvDetailsProvider`` in the metadata
``provider_registry`` chain.  Any failure (network, auth, circuit-open,
not-found, unexpected exception) falls back gracefully — a metadata hiccup
must **never** block a follow.

The provider title is preferred; the fallbacks below apply only when it is
unavailable.

Fallback precedence (when the provider lookup fails or is skipped):
1. ``fallback_title`` argument (if provided and non-empty).
2. ``"tvdb:<tvdb_id>"`` when ``tvdb_id`` is set.
3. ``"tmdb:<tmdb_id>"`` when only ``tmdb_id`` is set.
4. ``"imdb:<imdb_id>"`` when only ``imdb_id`` is set.

Import direction: ``acquire/`` imports ``api/`` (allowed) + ``core/`` + stdlib.
Never imports triage packages (indexer, scraper, commands).

Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.metadata._contracts import TvDetailsProvider
from personalscraper.core.identity import MediaRef
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry

log = get_logger("acquire.title_resolver")


def resolve_series_title(
    media_ref: MediaRef,
    registry: "ProviderRegistry",
    *,
    fallback_title: str | None = None,
) -> str:
    """Resolve the canonical title for a TV series via the provider registry.

    Calls the first available ``TvDetailsProvider`` in the chain with the
    ``tvdb_id`` from *media_ref*.  Any error (``ApiError``, ``CircuitOpenError``,
    or any unexpected exception) is caught and logged; the function always
    returns a non-empty string.

    Args:
        media_ref: Provider-ID key; ``tvdb_id`` is used for the lookup (primary).
        registry: The live ``ProviderRegistry`` from the composition root.
        fallback_title: Optional user-supplied title string. Used as the first
            fallback when the provider call fails.

    Returns:
        The canonical series title from the provider, the ``fallback_title`` if
        given, or a ``"<provider>:<id>"`` placeholder (e.g. ``"tvdb:81189"``).
    """
    # Determine the id to pass to the provider and the placeholder to use on failure.
    provider_id: int | str | None = media_ref.tvdb_id
    placeholder = _placeholder(media_ref)

    if provider_id is not None:
        providers = registry.chain(TvDetailsProvider)  # type: ignore[type-abstract]
        if providers:
            try:
                provider = cast(TvDetailsProvider, providers[0])
                details = provider.get_tv(provider_id)
                title = getattr(details, "title", None)
                if title:
                    return str(title)
                # Provider returned details but title is empty/None — fall through.
                log.warning(
                    "acquire.title_resolver.empty_title",
                    tvdb_id=provider_id,
                )
            except (ApiError, CircuitOpenError) as exc:
                log.warning(
                    "acquire.title_resolver.provider_error",
                    tvdb_id=provider_id,
                    error=str(exc),
                )
            except Exception as exc:  # noqa: BLE001 — fail-soft: must not block a follow
                log.warning(
                    "acquire.title_resolver.unexpected_error",
                    tvdb_id=provider_id,
                    error=str(exc),
                )
        else:
            log.debug("acquire.title_resolver.no_tv_provider_in_chain")

    # Fall back: user-supplied title > placeholder.
    if fallback_title:
        return fallback_title
    return placeholder


def _placeholder(media_ref: MediaRef) -> str:
    """Build a ``"<provider>:<id>"`` placeholder for a :class:`MediaRef`.

    Args:
        media_ref: Provider-ID key.

    Returns:
        E.g. ``"tvdb:81189"``, ``"tmdb:1234"``, or ``"imdb:tt0903747"``.
    """
    if media_ref.tvdb_id is not None:
        return f"tvdb:{media_ref.tvdb_id}"
    if media_ref.tmdb_id is not None:
        return f"tmdb:{media_ref.tmdb_id}"
    return f"imdb:{media_ref.imdb_id}"


__all__ = ["resolve_series_title"]
