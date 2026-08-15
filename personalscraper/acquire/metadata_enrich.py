"""Fail-soft card-metadata enricher for the acquire lobe (acq-states phase 7).

Resolves the three card fields a followed item needs to be *shown* — poster,
overview, year — from the metadata providers, by **provider ID**, and only for
the fields that are still missing.

Why it exists: the poster used to come exclusively from the search candidate
posted by the client, so every add path that does not carry one (the manual
by-ID form, the CLI, a script, a future third-party call) produced a
permanently posterless card even though the provider exposed the artwork.  The
server is responsible, not the client — so the resolution lives here, once, and
every add path inherits it.

Source order (plan §7 « Ordre des sources »):
1. The values already at hand (``existing``) — a client candidate comes from a
   search the operator validated visually; re-querying would waste an API call
   and risk a different answer (search vs by-id are different endpoints).
2. The provider, looked up **by its own ID**, respecting the strict provider
   separation (TVDB primary for shows, TMDB primary for movies, the other one
   only as a complement and only with ITS OWN id — never cross-contaminated).

Fail-soft contract: a provider outage, a missing method, a malformed payload —
all yield ``None`` for the field and a WARNING log.  The caller's own operation
(creating a follow, backfilling a row) must never fail because a nicety could
not be fetched.

Import direction: ``acquire/`` imports ``api/`` + ``core/`` + stdlib only.
Never ``web/``, never ``commands/`` — both are callers, so importing either
would invert the dependency.

Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.identity import MediaRef

log = get_logger("acquire.metadata_enrich")

#: A single provider lookup: (client, method name, provider id).
_Source = tuple[object, str, int]


@dataclass(frozen=True)
class FollowMetadata:
    """The three card fields a followed item shows before anything is acquired.

    Attributes:
        poster_url: Absolute URL of the poster artwork, or ``None``.
        overview: Plot summary, or ``None``.  Empty strings are normalised to
            ``None`` (``MediaDetails.overview`` defaults to ``""``).
        year: Release/first-air year, or ``None``.
        title: The provider's display title, or ``None``.
    """

    poster_url: str | None = None
    overview: str | None = None
    year: int | None = None
    #: The provider's display title. Filled by the enrichment so a client that
    #: knows only an ID never creates a NAMELESS follow (the add-by-ID form
    #: sent no title and the row showed as blank everywhere — operator report
    #: 2026-08-08). Never overwrites a title the client did send.
    title: str | None = None
    #: The provider's ORIGINAL-language title (#435). Captured opportunistically
    #: from the same by-id details the card fields come from, so the movie
    #: identity filter can match a release named in the original language
    #: (« Avant d'aller dormir » vs `Before.I.Go.To.Sleep.2014...`).
    #: Deliberately NOT part of :attr:`is_complete`: a client posting a full
    #: card must keep making zero provider calls — a row that misses only this
    #: field is healed by the detect-pass backfill instead.
    original_title: str | None = None

    @property
    def is_complete(self) -> bool:
        """Whether every card field is populated.

        Returns:
            ``True`` when no field is ``None`` — nothing left to fetch.
        """
        return (
            self.poster_url is not None
            and self.overview is not None
            and self.year is not None
            and self.title is not None
        )

    @property
    def is_empty(self) -> bool:
        """Whether every field is still missing.

        Returns:
            ``True`` when the three fields are ``None`` (nothing to persist).
        """
        return self.poster_url is None and self.overview is None and self.year is None

    def fill_from(self, other: "FollowMetadata") -> "FollowMetadata":
        """Return a copy where each missing field is taken from *other*.

        Never overwrites a value already present — the first source to answer
        for a field wins (plan §7 source order).

        Args:
            other: The candidate values to fill the gaps with.

        Returns:
            A new :class:`FollowMetadata`.
        """
        return replace(
            self,
            poster_url=self.poster_url if self.poster_url is not None else other.poster_url,
            overview=self.overview if self.overview is not None else other.overview,
            year=self.year if self.year is not None else other.year,
            title=self.title if self.title is not None else other.title,
            original_title=self.original_title if self.original_title is not None else other.original_title,
        )


def enrich_follow_metadata(
    media_ref: "MediaRef",
    kind: str,
    *,
    tmdb_client: object | None,
    tvdb_client: object | None,
    existing: FollowMetadata | None = None,
) -> FollowMetadata:
    """Fill the missing card fields of a follow from the metadata providers.

    Makes ZERO provider calls when *existing* is already complete, and stops as
    soon as every field is filled — a show whose TVDB record answers all three
    never touches TMDB.

    Args:
        media_ref: The follow's provider IDs.  Each provider is queried with
            its OWN id only (no cross-contamination).
        kind: ``"movie"`` or ``"show"`` — selects which provider is primary.
        tmdb_client: The TMDB client, or ``None`` when unavailable.
        tvdb_client: The TVDB client, or ``None`` when unavailable.
        existing: Values already known (client candidate, DB row).  They always
            win over the provider.

    Returns:
        A :class:`FollowMetadata` carrying *existing* plus whatever the
        providers could add.  Never raises.
    """
    resolved = existing if existing is not None else FollowMetadata()
    if resolved.is_complete:
        return resolved

    for client, method_name, provider_id in _sources(media_ref, kind, tmdb_client, tvdb_client):
        details = _fetch_details(client, method_name, provider_id)
        if details is None:
            continue
        resolved = resolved.fill_from(_extract(details))
        if resolved.is_complete:
            break
    return resolved


def _sources(
    media_ref: "MediaRef",
    kind: str,
    tmdb_client: object | None,
    tvdb_client: object | None,
) -> list[_Source]:
    """Build the ordered provider lookups for a follow, primary source first.

    Enforces the strict multi-provider separation: TVDB is primary for shows,
    TMDB for movies, and each client is only ever handed the id that belongs to
    it.  A missing client or a missing id simply drops that source.

    Args:
        media_ref: The follow's provider IDs.
        kind: ``"movie"`` or ``"show"``.
        tmdb_client: The TMDB client, or ``None``.
        tvdb_client: The TVDB client, or ``None``.

    Returns:
        The ordered ``(client, method_name, provider_id)`` lookups.
    """
    tvdb_id = media_ref.tvdb_id
    tmdb_id = media_ref.tmdb_id
    sources: list[_Source] = []
    if kind == "movie":
        # Movies: TMDB is the primary catalogue; TVDB only completes the gaps.
        if tmdb_client is not None and tmdb_id is not None:
            sources.append((tmdb_client, "get_movie", tmdb_id))
        if tvdb_client is not None and tvdb_id is not None:
            sources.append((tvdb_client, "get_movie", tvdb_id))
        return sources
    # Shows: TVDB is primary (``get_series`` is its by-id series endpoint);
    # TMDB completes with ``get_tv`` and its own id.
    if tvdb_client is not None and tvdb_id is not None:
        sources.append((tvdb_client, "get_series", tvdb_id))
    if tmdb_client is not None and tmdb_id is not None:
        sources.append((tmdb_client, "get_tv", tmdb_id))
    return sources


def _fetch_details(client: object, method_name: str, provider_id: int) -> Any | None:
    """Call one provider by ID, swallowing every failure.

    Args:
        client: The provider client object.
        method_name: The by-id details method to call (e.g. ``"get_series"``).
        provider_id: The id belonging to THAT provider.

    Returns:
        The provider's details object, or ``None`` on any failure.
    """
    method = getattr(client, method_name, None)
    if not callable(method):
        log.warning(
            "acquire.metadata_enrich.method_missing",
            method=method_name,
            client=type(client).__name__,
        )
        return None
    try:
        return method(provider_id)
    except (ApiError, CircuitOpenError) as exc:
        log.warning(
            "acquire.metadata_enrich.provider_error",
            method=method_name,
            provider_id=provider_id,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 — fail-soft: a nicety must never block the caller
        log.warning(
            "acquire.metadata_enrich.unexpected_error",
            method=method_name,
            provider_id=provider_id,
            error=str(exc),
        )
    return None


def _extract(details: Any) -> FollowMetadata:
    """Map a provider details object to the three card fields.

    Reads by ``getattr`` rather than by attribute so a partial stand-in (or a
    provider whose payload lost a field) degrades to ``None`` instead of
    raising.  ``MediaDetails.overview`` defaults to ``""``, so empty strings are
    normalised to ``None`` — an empty overview is an absent overview, and
    storing ``""`` would make the row look enriched forever.

    Args:
        details: A :class:`~personalscraper.api.metadata._base.MediaDetails`
            (or any object exposing ``year`` / ``overview`` / ``images``).

    Returns:
        The extracted :class:`FollowMetadata`.
    """
    year = getattr(details, "year", None)
    overview = getattr(details, "overview", None)
    title = getattr(details, "title", None)
    original_title = getattr(details, "original_title", None)
    return FollowMetadata(
        poster_url=_first_poster_url(details),
        overview=str(overview) if isinstance(overview, str) and overview.strip() else None,
        year=int(year) if isinstance(year, int) else None,
        title=str(title) if isinstance(title, str) and title.strip() else None,
        original_title=(
            str(original_title) if isinstance(original_title, str) and original_title.strip() else None
        ),
    )


def _first_poster_url(details: Any) -> str | None:
    """Return the first poster URL among a details object's artwork.

    Args:
        details: A provider details object exposing an ``images`` sequence of
            items with ``type`` / ``url`` attributes.

    Returns:
        The poster URL, or ``None`` when the provider exposed none.
    """
    images = getattr(details, "images", None)
    if not isinstance(images, (list, tuple)):
        return None
    for image in images:
        if getattr(image, "type", None) != "poster":
            continue
        url = getattr(image, "url", None)
        if isinstance(url, str) and url.strip():
            return url
    return None


__all__ = ["FollowMetadata", "enrich_follow_metadata"]
