"""``ProviderSearch``: the metadata providers' search and lookup, in v1's layer (K3 P11a).

A copy of v0's ``run_media_search`` and ``run_media_lookup`` (``web/acquisition/service.py``),
kept apart on purpose: v1 never imports ``web/``, and v0 stays untouched until the switchover
removes it. The answers are v0's: the same candidates, the same ranking, the same page and
total, the same ownership flag, the same 404 on an id the provider does not know. Two things
are not: the ownership flag is named ``owned``, and every result also says whether it is
``followed`` (K3 P11b). The cache is the one v0 already fills (:mod:`personalscraper.app.acquisition.search_cache`).

What the layer changes is the seam, not the behaviour:

* the provider clients, the ownership probe and the cache are injected (a test builds the
  service over fakes; :func:`scoped_provider_clients` is the real clients' seam);
* each method is authorised by ``@requires`` before it asks a provider anything;
* v0's ``HTTPException`` 404 / 502 are the layer's ``media.not_found`` / ``provider.unavailable``.

Ranking is the RETRIEVAL engine (:mod:`personalscraper.scraper.search_ranking`), not the scrape
matcher: the latter answers « is this folder that media? » and its anti-false-positive guards
scored the wanted title at exactly 0.000 for a short keyword query.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.acquisition.search_cache import SEARCH_CACHE, SearchResultCache
from personalscraper.app.errors import AppBadRequest, AppUnavailable, RefusalCode
from personalscraper.app.library.facts import refuse_not_found
from personalscraper.core import ApiError
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.ownership import IndexerOwnershipChecker
from personalscraper.logger import get_logger
from personalscraper.scraper.search_ranking import (
    RankedResult,
    TvProvidersFailed,
    gather_tv_candidates,
    rank_search_results,
)

if TYPE_CHECKING:
    from personalscraper.acquire.domain import FollowedSeries, FollowKind
    from personalscraper.api.metadata._base import SearchResult
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "ProviderSearch",
    "SearchKind",
    "SearchPage",
    "SearchedMedium",
    "scoped_provider_clients",
]

logger = get_logger(__name__)

#: A kind restriction on a search: films, shows, or (``None``) both.
type SearchKind = Literal["movie", "tv"]

#: Rows a search page carries when the caller names no limit (v0's default).
DEFAULT_LIMIT: Final[int] = 20

#: The most rows one search page may carry: the bound the contract declares on ``limit``.
MAX_LIMIT: Final[int] = 100

#: The provider the movie chain asks, named in the refusal when it fails.
_MOVIE_PROVIDER: Final[str] = "tmdb"

#: The provider the television chain is named after when both of its providers fail.
_TV_PROVIDER: Final[str] = "tvdb"

#: A provider's answer for an id it does not hold.
_NOT_FOUND: Final[int] = 404

#: The kinds a lookup by identifier asks, the shows first.
_LOOKUP_KINDS: Final[tuple[SearchKind, ...]] = ("tv", "movie")

#: The field a malformed identifier is refused on.
_ID_FIELD: Final[str] = "id"

#: How each source writes an identifier: digits for TMDB and TVDB, « tt » and digits for IMDb.
_ID_FORMAT: Final[dict[str, re.Pattern[str]]] = {
    "tmdb": re.compile(r"[0-9]{1,18}"),
    "tvdb": re.compile(r"[0-9]{1,18}"),
    "imdb": re.compile(r"tt[0-9]{1,18}"),
}


class _OwnershipProbe(Protocol):
    """The part of the indexer's ownership checker the search reads."""

    def owns(self, media_ref: MediaRef, *, kind: Literal["movie", "episode"]) -> bool:
        """Whether a live file holds the film."""
        ...

    def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
        """The ``(season, episode)`` pairs a live file holds for the show."""
        ...

    def close(self) -> None:
        """Release the probe's connection."""
        ...


class _FollowLookup(Protocol):
    """The part of the acquire store's follow sub-store the search reads."""

    def find_all_by_refs(self, lookups: Sequence[tuple[MediaRef, FollowKind | None]]) -> list[list[FollowedSeries]]:
        """Every follow row holding any id of each lookup's ref, within its kind, one list per lookup."""
        ...


@dataclass(frozen=True)
class SearchedMedium:
    """One medium a provider knows, as the search and the lookup answer it.

    Attributes:
        provider: ``"tmdb"`` or ``"tvdb"``.
        provider_id: The provider's numeric id (``0`` when it ever returns a non-numeric one).
        title: The provider's title.
        year: The release or first-air year, or ``None``.
        kind: ``"movie"`` or ``"tv"``, read off the candidate's own media type.
        poster_url: The poster URL, or ``None``.
        overview: The synopsis, or ``None``.
        score: The ranking score (``1.0`` for a lookup, which ranks nothing).
        owned: Whether the library holds it by provider id; a show counts as soon as
            ANY live episode file exists (presence, not completeness). ``False`` when no
            indexer is configured: the flag degrades, the search does not fail. (P11a named it
            ``already_owned``, v0's wire name; the plan's name is ``owned``.)
        followed: Whether a standing follow holds its provider id: a ``followed_series`` row of
            scope ``follow`` that is not removed (paused counts, a request row and a removed
            follow do not). By id, never by title. ``False`` when no follow store is wired.
    """

    provider: str
    provider_id: int
    title: str
    year: int | None
    kind: SearchKind
    poster_url: str | None
    overview: str | None
    score: float
    owned: bool = False
    followed: bool = False


@dataclass(frozen=True)
class SearchPage:
    """One page of a search.

    Attributes:
        results: The requested page, best first.
        total: How many ranked candidates the search holds, not how many the page carries.
        offset: The zero-based index of the page's first row.
        limit: The most rows the page may carry.
    """

    results: tuple[SearchedMedium, ...]
    total: int
    offset: int
    limit: int


@contextmanager
def scoped_provider_clients(config: Config, settings: Settings) -> Iterator[tuple[object, object]]:
    """Yield request-scoped TMDB and TVDB clients, then release the registry.

    A fresh application context and provider registry for this single call, never stored on
    the application (the composition-boundary rule): a live search is an infrequent operator
    action, not a hot polling endpoint.

    Two properties this seam owns:

    * **Bounded**: the providers are built with ONE attempt (``ONE_ATTEMPT``) through the
      registry's ``retry`` parameter, a real construction seam. The pipeline's default (4
      attempts and an exponential backoff over a 10 s / 15 s timeout) is right for a background
      step and wrong for a user waiting: against a host that accepts the TCP connection and
      never answers, one lookup burned ~60-75 s with the worker thread held throughout.
    * **Closed**: ``ProviderRegistry.close()`` releases each provider's session and its
      connection pool. It runs in a ``finally``, so it also runs when the body raises.

    Args:
        config: The typed JSON5 configuration.
        settings: The environment settings (API keys).

    Yields:
        A ``(tmdb_client, tvdb_client)`` tuple of provider client objects.

    Raises:
        AppUnavailable: ``provider.unavailable`` when the provider registry cannot be built.
    """
    from personalscraper.app.composition import (  # noqa: PLC0415 — composition imports the app layer
        ONE_ATTEMPT,
        build_app_context,
    )

    try:
        app_context = build_app_context(config, settings, provider_retry=ONE_ATTEMPT)
    except Exception as exc:
        logger.error("acquisition_search_registry_failed", error=str(exc))
        raise AppUnavailable("A metadata provider did not answer.", code=RefusalCode.PROVIDER_UNAVAILABLE) from exc
    try:
        try:
            tmdb_client = app_context.provider_registry.get("tmdb")
            tvdb_client = app_context.provider_registry.get("tvdb")
        except Exception as exc:  # inside the teardown's scope: a built registry is always closed
            logger.error("acquisition_search_registry_failed", error=str(exc))
            raise AppUnavailable("A metadata provider did not answer.", code=RefusalCode.PROVIDER_UNAVAILABLE) from exc
        yield tmdb_client, tvdb_client
    finally:
        # Teardown mirrors the CLI's ``per_step_boundary``: registry first, then the acquisition
        # handle. Fail-soft: a teardown error must never turn a served answer into a failure.
        try:
            app_context.provider_registry.close()
        except Exception:  # teardown must not mask the answer
            logger.warning("acquisition_provider_registry_close_failed", exc_info=True)
        if app_context.acquire is not None:
            try:
                app_context.acquire.close()
            except Exception:  # same contract
                logger.warning("acquisition_acquire_context_close_failed", exc_info=True)


class ProviderSearch:
    """Search the metadata providers, or resolve one medium by its provider id."""

    def __init__(
        self,
        *,
        clients: Callable[[], AbstractContextManager[tuple[object, object]]],
        indexer_db: Path | None,
        ownership: Callable[[Path], _OwnershipProbe] | None = None,
        cache: SearchResultCache = SEARCH_CACHE,
        follows: _FollowLookup | None = None,
    ) -> None:
        """Hold the seams; no provider is asked and no database opened yet.

        Args:
            clients: Opens the ``(tmdb, tvdb)`` clients for one call and closes them after;
                :func:`scoped_provider_clients` over the configuration in production.
            indexer_db: ``library.db``'s path, or ``None`` when no indexer is configured (no
                result is then flagged owned).
            ownership: Builds the ownership probe over ``library.db``; the indexer's own
                checker when ``None``.
            cache: The ranked-lot cache; the process-wide one v0 already fills by default.
            follows: The acquire store's follow sub-store, read for ``followed``; ``None`` when
                no acquire store is configured (no result is then flagged followed). The
                composer owns its lifecycle.
        """
        self._clients = clients
        self._indexer_db = indexer_db
        self._ownership: Callable[[Path], _OwnershipProbe] = ownership or IndexerOwnershipChecker
        self._cache = cache
        self._follows = follows

    @requires("searchProviders")
    def search(
        self,
        actor: Actor,
        query: str,
        kind: SearchKind | None,
        *,
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> SearchPage:
        """Run the movie and TV search chains and answer one page of the ranked lot.

        Paging does not replay the provider sweep: the ranked lot of an exact ``(query, kind)``
        is cached, so page 2 and beyond cost nothing at the providers. ``owned`` and
        ``followed`` are deliberately NOT cached: they are recomputed on every call (the
        indexer, the follow store), because the library and the follows change while a search
        sits on screen and a stale badge would drive a wrong choice.

        The provider clients are opened only on a cache miss. v0's route opened them before
        looking at the cache, so a page served from the cache still built and tore down a
        registry (and answered 502 if it could not be built); the answers are the same, the
        wasted registry and that one failure mode are not carried over.

        Args:
            actor: Who searches; authorised by ``@requires`` (``acquisition.request``).
            query: The title to search for.
            kind: ``"movie"`` or ``"tv"`` to restrict the search, ``None`` for both.
            offset: Zero-based index of the first row to return.
            limit: Most rows to return.

        Returns:
            The requested page and the TOTAL number of ranked candidates.

        Raises:
            AppUnavailable: ``provider.unavailable`` when the provider registry cannot be built
                or the movie chain fails.
        """
        cached = self._cache.get(query, kind)
        if cached is not None:
            ranked = cached
        else:
            ranked = self._ranked(query, kind)
            self._cache.put(query, kind, ranked)
        page = [_medium_of(item) for item in ranked[offset : offset + limit]]
        return SearchPage(results=tuple(self._flag_facts(page)), total=len(ranked), offset=offset, limit=limit)

    @requires("searchProviderById")
    def by_id(self, actor: Actor, provider: str, id: int, kind: SearchKind) -> SearchedMedium:
        """Resolve ONE medium by provider id into a search result.

        It RESOLVES and returns, it never follows. The same ownership pass as the search, so
        ``owned`` and ``followed`` are as true here as there.

        Args:
            actor: Who looks up; authorised by ``@requires`` (``acquisition.request``).
            provider: ``"tvdb"`` or ``"tmdb"``.
            id: The provider's numeric identifier.
            kind: ``"movie"`` or ``"tv"``.

        Returns:
            The resolved medium.

        Raises:
            AppNotFound: ``media.not_found`` when the provider knows no such id, or answers one
                without a title.
            AppUnavailable: ``provider.unavailable`` when the provider registry cannot be built, the
                provider is not configured, or the call failed: a failure is never taken for an id
                the provider does not know.
        """
        with self._clients() as (tmdb_client, tvdb_client):
            medium = self._fetch(tvdb_client if provider == "tvdb" else tmdb_client, provider, id, kind)
        if medium is None:
            raise refuse_not_found(provider)
        return self._flag_facts([medium])[0]

    @requires("searchProviderById")
    def lookup(self, actor: Actor, provider: str, provider_id: str) -> tuple[SearchedMedium, ...]:
        """Resolve the medium or media a source knows under one identifier, kind unknown.

        The wire names no kind, and a TMDB or TVDB number is held by a film and by a show alike
        (the two are numbered apart), so both kinds are asked and each that answers is returned.
        An IMDb id is never handed to TMDB as if it were a TMDB id: TMDB's find endpoint
        resolves it to the TMDB ids it numbers, and those are fetched. It RESOLVES and returns,
        it never follows; ``owned`` and ``followed`` are flagged as in the search.

        Args:
            actor: Who looks up; authorised by ``@requires`` (``acquisition.request``).
            provider: ``"tmdb"``, ``"tvdb"`` or ``"imdb"``.
            provider_id: The identifier, in that source's format.

        Returns:
            The media found, empty when the source knows none under the identifier.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``id`` when the identifier is not in the
                source's format; nothing is asked of a provider.
            AppUnavailable: ``provider.unavailable`` when the provider is not configured, cannot
                be reached or fails: a failure is never answered as « no result ».
        """
        _check_identifier(provider, provider_id)
        found: list[SearchedMedium | None] = []
        with self._clients() as (tmdb_client, tvdb_client):
            if provider == "imdb":
                found.extend(self._by_imdb(tmdb_client, provider_id))
            else:
                client = tvdb_client if provider == "tvdb" else tmdb_client
                found.extend(self._fetch(client, provider, int(provider_id), kind) for kind in _LOOKUP_KINDS)
        return tuple(self._flag_facts([medium for medium in found if medium is not None]))

    def _by_imdb(self, tmdb_client: object, imdb_id: str) -> list[SearchedMedium | None]:
        """Resolve an IMDb id at TMDB's find endpoint and fetch what it numbers.

        Args:
            tmdb_client: The TMDB client.
            imdb_id: A well-formed IMDb id.

        Returns:
            The media TMDB holds under the TMDB ids the IMDb id resolves to.

        Raises:
            AppUnavailable: ``provider.unavailable`` naming ``tmdb`` when it cannot resolve the id.
        """
        find = getattr(tmdb_client, "find_ids_by_imdb", None)
        if find is None:
            raise _unavailable("tmdb", LookupError("no client able to resolve an IMDb id"))
        try:
            tmdb_ids: dict[str, int] = find(imdb_id)
        except ApiError as exc:
            if exc.http_status == _NOT_FOUND:
                return []
            raise _unavailable("tmdb", exc) from exc
        except Exception as exc:  # a provider down is a failure, whatever it raised
            raise _unavailable("tmdb", exc) from exc
        return [self._fetch(tmdb_client, "tmdb", tmdb_ids[kind], kind) for kind in _LOOKUP_KINDS if kind in tmdb_ids]

    def _fetch(self, client: object | None, provider: str, provider_id: int, kind: SearchKind) -> SearchedMedium | None:
        """Ask one provider for one medium of one kind.

        Args:
            client: The provider's client, or ``None`` when it is not configured.
            provider: ``"tvdb"`` or ``"tmdb"``.
            provider_id: The provider's numeric identifier.
            kind: ``"movie"`` or ``"tv"``.

        Returns:
            The medium; ``None`` when the provider holds no such id (a 404, an answer its own
            parser refuses, or one without a title).

        Raises:
            AppUnavailable: ``provider.unavailable`` when the client is missing or the call
                failed in any other way.
        """
        method = "get_movie" if kind == "movie" else ("get_series" if provider == "tvdb" else "get_tv")
        call = getattr(client, method, None)
        if call is None:
            raise _unavailable(provider, LookupError(f"no client able to {method}"))
        try:
            details = call(provider_id)
        except ApiError as exc:
            if exc.http_status == _NOT_FOUND:
                return None
            raise _unavailable(provider, exc) from exc
        except ValueError:
            # The provider's own parser refused its answer: nothing usable sits under the id (v0's
            # reading of an id it cannot resolve, kept for the cases that pin it).
            logger.warning("acquisition_lookup_unparsable", provider=provider, provider_id=provider_id, exc_info=True)
            return None
        except Exception as exc:  # a provider down is a failure, never a missing id
            raise _unavailable(provider, exc) from exc
        title = str(getattr(details, "title", "") or "")
        if title == "":
            return None
        year = getattr(details, "year", None)
        overview = getattr(details, "overview", None)
        return SearchedMedium(
            provider=provider,
            provider_id=provider_id,
            title=title,
            year=year if isinstance(year, int) else None,
            kind=kind,
            poster_url=_poster_url_of(details),
            overview=overview if isinstance(overview, str) and overview.strip() else None,
            score=1.0,
        )

    def _ranked(self, query: str, kind: SearchKind | None) -> list[RankedResult]:
        """Gather the candidates of the asked kinds and rank them in ONE pass.

        Args:
            query: The title to search for.
            kind: The kind restriction, or ``None`` for both.

        Returns:
            The ranked candidates, best first.

        Raises:
            AppUnavailable: ``provider.unavailable`` when the registry cannot be built or the
                movie chain fails.
        """
        candidates: list[SearchResult] = []
        with self._clients() as (tmdb_client, tvdb_client):
            if kind in (None, "movie"):
                try:
                    candidates.extend(tmdb_client.search_movie(query, None))  # type: ignore[attr-defined]
                except Exception as exc:
                    logger.error("acquisition_search_movie_failed", error=str(exc))
                    raise AppUnavailable(
                        "A metadata provider did not answer.",
                        code=RefusalCode.PROVIDER_UNAVAILABLE,
                        params={"provider": _MOVIE_PROVIDER},
                    ) from exc
            if kind in (None, "tv"):
                # Both TV providers, merged: TVDB alone cannot rank (it publishes no popularity),
                # and the scrape rule « TMDB only when TVDB is silent » hid the right answer
                # whenever TVDB returned any row at all.
                try:
                    candidates.extend(gather_tv_candidates(tvdb_client, tmdb_client, query, raise_when_all_fail=True))
                except TvProvidersFailed as exc:
                    # Nobody answered for shows. A lot that is films only is partial, served (and
                    # cached, v0's rule); a lot with nothing at all is a failure, never an empty answer.
                    if not candidates:
                        raise AppUnavailable(
                            "A metadata provider did not answer.",
                            code=RefusalCode.PROVIDER_UNAVAILABLE,
                            params={"provider": _TV_PROVIDER},
                        ) from exc
                    logger.warning("acquisition_search_tv_failed_partial_lot", query=query)
        # ONE ranking pass over the union, never one per kind. Popularity is normalised against
        # the most popular candidate in the lot, so ranking each kind separately runs that
        # normalisation on two different maxima and yields two incomparable 1.000s. Measured in
        # production 2026-08-05: 'monarch' put « Monarch City » (popularity 2.19, merely the best
        # of a weak film lot) ahead of « Monarch: Legacy of Monsters » (popularity 34.45), a 16x
        # gap erased, with recency then breaking the tie the wrong way.
        return rank_search_results(query, candidates, kind=kind or "all", now_year=datetime.now(tz=UTC).year)

    def _flag_facts(self, media: list[SearchedMedium]) -> list[SearchedMedium]:
        """Flag what the library and the follows already hold, by provider id.

        ``owned``: the pipeline REPLACES an existing version, so the interface asks before
        following one. A film is owned when a live file holds it; a show as soon as ANY live
        episode file exists. ``followed``: a standing follow holds the id. Neither probe runs
        when it is not wired (no indexer, no follow store) or there is nothing to flag. A probe
        that is wired but cannot be read raises: a degraded read never affirms a value, and
        ``followed=False`` on a title the reader follows would be a false one.

        Args:
            media: The media to flag.

        Returns:
            The same media, in the same order, with ``owned`` and ``followed`` set.
        """
        if not media:
            return media
        flagged = media
        if self._indexer_db is not None:
            checker = self._ownership(Path(self._indexer_db))
            try:
                flagged = [replace(medium, owned=_is_owned(checker, medium)) for medium in flagged]
            finally:
                checker.close()
        follows = self._follows
        if follows is not None:
            flagged = _flag_followed(follows, flagged)
        return flagged


def _poster_url_of(details: Any) -> str | None:
    """Return the first poster URL among a details object's artwork.

    Args:
        details: A provider details object exposing an ``images`` sequence of items with
            ``type`` / ``url`` attributes.

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


def _ref_of(medium: SearchedMedium) -> MediaRef:
    """Return the provider id the medium is known by, as the stores key it.

    Args:
        medium: The medium.

    Returns:
        A :class:`MediaRef` holding the medium's TMDB or TVDB id.
    """
    return MediaRef(tmdb_id=medium.provider_id) if medium.provider == "tmdb" else MediaRef(tvdb_id=medium.provider_id)


def _is_owned(checker: _OwnershipProbe, medium: SearchedMedium) -> bool:
    """Whether the library holds the medium, by its provider id, live files only.

    Args:
        checker: The ownership probe.
        medium: The medium.

    Returns:
        ``True`` for a film a live file holds, or a show with any live episode file.
    """
    ref = _ref_of(medium)
    return checker.owns(ref, kind="movie") if medium.kind == "movie" else len(checker.owned_pairs(ref)) > 0


def _flag_followed(follows: _FollowLookup, media: list[SearchedMedium]) -> list[SearchedMedium]:
    """Flag which media a standing follow holds, in ONE lookup for the whole page.

    The lookup is P1's, within each medium's kind (TMDB numbers films and shows apart). A row
    stands when its scope is ``follow`` (a one-off request is not a follow) and it is not
    removed; a paused follow stands.

    Args:
        follows: The follow lookup.
        media: The media of the page.

    Returns:
        The same media, in the same order, with ``followed`` set.
    """
    kinds: list[FollowKind] = ["movie" if medium.kind == "movie" else "show" for medium in media]
    answers = follows.find_all_by_refs([(_ref_of(medium), kind) for medium, kind in zip(media, kinds, strict=True)])
    return [
        replace(medium, followed=any(row.scope == "follow" and row.removed_at is None for row in rows))
        for medium, rows in zip(media, answers, strict=True)
    ]


def _check_identifier(provider: str, provider_id: str) -> None:
    """Refuse an identifier that is not in its source's format, before any provider is asked.

    Args:
        provider: ``"tmdb"``, ``"tvdb"`` or ``"imdb"``.
        provider_id: The identifier as typed.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``id``.
    """
    pattern = _ID_FORMAT.get(provider)
    if pattern is None or not pattern.fullmatch(provider_id):
        raise AppBadRequest(
            "The identifier is not in its source's format.",
            code=RefusalCode.REQUEST_INVALID,
            params={"fields": [_ID_FIELD]},
        )


def _unavailable(provider: str, exc: BaseException) -> AppUnavailable:
    """Build the refusal for a provider that did not answer, and log why.

    Args:
        provider: The provider asked.
        exc: What the call raised.

    Returns:
        ``provider.unavailable``, naming the provider.
    """
    logger.warning("acquisition_lookup_failed", provider=provider, error=str(exc))
    return AppUnavailable(
        "A metadata provider did not answer.", code=RefusalCode.PROVIDER_UNAVAILABLE, params={"provider": provider}
    )


def _medium_of(candidate: RankedResult) -> SearchedMedium:
    """Map a scored candidate to a search result.

    The ``kind`` tag is read off the candidate's own ``media_type`` rather than from the chain
    that produced it: films and shows are ranked in a single pass over the union, so there is no
    per-chain context left to inherit, and the provider's own classification is the more honest
    source anyway.

    Args:
        candidate: The ranked provider candidate.

    Returns:
        The tagged result.
    """
    result = candidate.result
    # provider_id is a str on SearchResult but an int on the wire; a provider that ever returns a
    # non-numeric id must not fail the whole search.
    try:
        provider_id = int(result.provider_id)
    except (TypeError, ValueError):
        provider_id = 0
    return SearchedMedium(
        provider=result.provider,
        provider_id=provider_id,
        title=result.title,
        year=result.year,
        kind="tv" if str(result.media_type) == "tv" else "movie",
        poster_url=result.poster_url or None,
        overview=result.overview or None,
        score=candidate.score,
    )
