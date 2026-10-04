"""The media sheet's facts: what the providers say of a medium, as closed tokens and plain values.

No sentence reaches the sheet (X4/X5): a genre is a :class:`GenreId`, a status a
:class:`MediaStatus`, an image a provider URL, a trailer its YouTube key. A provider's
answer is cached for five minutes (v0's sheet semantics, moved here); the index's
facts are read fresh on every call by the service.

What the providers' clients do not return is ``None`` (« unknown »), never an empty
« none »; what they return empty (a cast no provider lists) stays empty.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final, Literal, Protocol, runtime_checkable

from personalscraper.api.metadata._base import MediaDetails
from personalscraper.app.errors import AppNotFound, AppUnavailable, RefusalCode
from personalscraper.app.library.listing import fold
from personalscraper.core._contracts import ApiError
from personalscraper.logger import get_logger

log = get_logger("app.library.facts")

#: How long a provider's answer is reused, seconds (v0's sheet cache).
PROVIDER_CACHE_TTL_S: Final[float] = 300.0
#: How many provider answers the cache keeps.
PROVIDER_CACHE_MAX: Final[int] = 256

_NOT_FOUND: Final[int] = 404
_YOUTUBE_KEY: Final[re.Pattern[str]] = re.compile(r"(?:[?&]v=|youtu\.be/)([A-Za-z0-9_-]{6,})")


class GenreId(StrEnum):
    """The contract's closed genre tokens; the interface names each one."""

    ACTION = "action"
    ACTION_ADVENTURE = "action_adventure"
    ADVENTURE = "adventure"
    ANIMATION = "animation"
    COMEDY = "comedy"
    CRIME = "crime"
    DOCUMENTARY = "documentary"
    DRAMA = "drama"
    FAMILY = "family"
    FANTASY = "fantasy"
    HISTORY = "history"
    HORROR = "horror"
    KIDS = "kids"
    MUSIC = "music"
    MYSTERY = "mystery"
    REALITY = "reality"
    ROMANCE = "romance"
    SCIENCE_FICTION = "science_fiction"
    SCI_FI_FANTASY = "sci_fi_fantasy"
    THRILLER = "thriller"
    TV_MOVIE = "tv_movie"
    WAR = "war"
    WAR_POLITICS = "war_politics"
    WESTERN = "western"


class MediaStatus(StrEnum):
    """Where a medium stands at its provider, as the contract's closed token."""

    CONTINUING = "continuing"
    ENDED = "ended"
    CANCELED = "canceled"
    RELEASED = "released"
    IN_PRODUCTION = "in_production"
    PLANNED = "planned"


# TMDB's genre ids (movie and TV lists); its names are localised, its ids are not.
_TMDB_GENRES: Final[Mapping[int, GenreId]] = {
    28: GenreId.ACTION,
    12: GenreId.ADVENTURE,
    16: GenreId.ANIMATION,
    35: GenreId.COMEDY,
    80: GenreId.CRIME,
    99: GenreId.DOCUMENTARY,
    18: GenreId.DRAMA,
    10751: GenreId.FAMILY,
    14: GenreId.FANTASY,
    36: GenreId.HISTORY,
    27: GenreId.HORROR,
    10402: GenreId.MUSIC,
    9648: GenreId.MYSTERY,
    10749: GenreId.ROMANCE,
    878: GenreId.SCIENCE_FICTION,
    10770: GenreId.TV_MOVIE,
    53: GenreId.THRILLER,
    10752: GenreId.WAR,
    37: GenreId.WESTERN,
    10759: GenreId.ACTION_ADVENTURE,
    10762: GenreId.KIDS,
    10764: GenreId.REALITY,
    10765: GenreId.SCI_FI_FANTASY,
    10768: GenreId.WAR_POLITICS,
}

# TVDB's genre names (English, and the French spellings a localised answer carries),
# folded to lower case without accents.
_NAMED_GENRES: Final[Mapping[str, GenreId]] = {
    "action": GenreId.ACTION,
    "adventure": GenreId.ADVENTURE,
    "aventure": GenreId.ADVENTURE,
    "animation": GenreId.ANIMATION,
    "comedy": GenreId.COMEDY,
    "comedie": GenreId.COMEDY,
    "crime": GenreId.CRIME,
    "documentary": GenreId.DOCUMENTARY,
    "documentaire": GenreId.DOCUMENTARY,
    "drama": GenreId.DRAMA,
    "drame": GenreId.DRAMA,
    "family": GenreId.FAMILY,
    "familial": GenreId.FAMILY,
    "famille": GenreId.FAMILY,
    "fantasy": GenreId.FANTASY,
    "fantastique": GenreId.FANTASY,
    "history": GenreId.HISTORY,
    "histoire": GenreId.HISTORY,
    "horror": GenreId.HORROR,
    "horreur": GenreId.HORROR,
    "children": GenreId.KIDS,
    "kids": GenreId.KIDS,
    "enfants": GenreId.KIDS,
    "music": GenreId.MUSIC,
    "musical": GenreId.MUSIC,
    "musique": GenreId.MUSIC,
    "mystery": GenreId.MYSTERY,
    "mystere": GenreId.MYSTERY,
    "reality": GenreId.REALITY,
    "telerealite": GenreId.REALITY,
    "romance": GenreId.ROMANCE,
    "science fiction": GenreId.SCIENCE_FICTION,
    "science-fiction": GenreId.SCIENCE_FICTION,
    "thriller": GenreId.THRILLER,
    "war": GenreId.WAR,
    "guerre": GenreId.WAR,
    "western": GenreId.WESTERN,
}

# Provider status names (TMDB's and TVDB's), lower case.
_STATUSES: Final[Mapping[str, MediaStatus]] = {
    "returning series": MediaStatus.CONTINUING,
    "continuing": MediaStatus.CONTINUING,
    "ended": MediaStatus.ENDED,
    "canceled": MediaStatus.CANCELED,
    "cancelled": MediaStatus.CANCELED,
    "released": MediaStatus.RELEASED,
    "in production": MediaStatus.IN_PRODUCTION,
    "post production": MediaStatus.IN_PRODUCTION,
    "planned": MediaStatus.PLANNED,
    "upcoming": MediaStatus.PLANNED,
    "rumored": MediaStatus.PLANNED,
}


@runtime_checkable
class SheetClient(Protocol):
    """The two calls a provider client answers for the sheet."""

    def get_movie(self, movie_id: str | int) -> MediaDetails:
        """Return a movie's details."""
        ...

    def get_tv(self, provider_id: str | int) -> MediaDetails:
        """Return a show's details."""
        ...


@dataclass(frozen=True)
class CastFact:
    """One cast member.

    Attributes:
        name: The person's name.
        role: The character played.
    """

    name: str
    role: str


@dataclass(frozen=True)
class EpisodeFact:
    """One catalogued episode, as the sheet lists it.

    Attributes:
        number: Episode number within its season.
        title: The episode's title, or ``None``.
        air_date: When it aired or is announced to, or ``None``.
    """

    number: int
    title: str | None
    air_date: date | None


@dataclass(frozen=True)
class SeasonSummaryFact:
    """A season as the provider knows it.

    Attributes:
        number: Season number (0 = specials).
        episodes: How many episodes the provider lists, or ``None`` when it does not say.
        air_date: The season's first air date in the catalogue, or ``None``.
    """

    number: int
    episodes: int | None
    air_date: date | None


@dataclass(frozen=True)
class MediaSheetFacts:
    """Every property of the contract's ``MediaSheet``, as facts (K2-G6, K2-G7).

    Attributes:
        title: The title the library files it under, else the provider's.
        kind: ``"movie"`` or ``"show"``.
        year: The provider's year, else the index's; ``None`` when neither states one.
        rating: The provider's average (0–10), or ``None``.
        genres: Genre tokens in the provider's order; genres no token names are left out.
        runtime: Minutes, or ``None``.
        overview: The synopsis the library's NFO holds, else the provider's; ``None`` when none.
        director: The director's name, or ``None``.
        creator: A show's creator, or ``None``.
        cast: The provider's cast in its order (TMDB ``order``, TVDB ``sort``); empty when
            it lists none.
        cast_portraits: Each cast member's portrait URL keyed by name, only for members
            the provider gives one; a name listed twice keeps its first portrait.
        trailer_key: The YouTube key of the provider's first trailer, or ``None``.
        trailer_name: That trailer's title, or ``None``.
        trailer_language: That trailer's language code as the provider gives it, or ``None``.
        ids: Every provider id known (the library's row merged with the provider's answer).
        status: Where the medium stands at its provider, or ``None`` when it says nothing.
        owned: Whether some live library row holds it.
        episodes: A show's catalogued episodes by season; ``None`` for a movie or a show
            never catalogued.
        seasons: A show's seasons as the provider knows them; ``None`` for a movie.
        tmdb_television_id: A show's TMDB id, or ``None`` (always for a movie).
        poster_url: The provider's poster URL, else the one the library's NFO names, or ``None``.
        local_poster: Whether the poster to show is the library folder's own file (no URL known).
        poster_high_definition_url: The provider's poster URL at gallery definition, or ``None``.
        hero_url: The provider's wide visual (backdrop) URL, or ``None``.
        metadata_refreshed_at: The local date the library last read the provider data (the
            NFO's write), or ``None`` when the library holds none.
    """

    title: str
    kind: Literal["movie", "show"]
    year: int | None
    rating: float | None
    genres: tuple[GenreId, ...]
    runtime: int | None
    overview: str | None
    director: str | None
    creator: str | None
    cast: tuple[CastFact, ...]
    cast_portraits: Mapping[str, str]
    trailer_key: str | None
    trailer_name: str | None
    trailer_language: str | None
    ids: Mapping[str, int | str]
    status: MediaStatus | None
    owned: bool
    episodes: Mapping[int, tuple[EpisodeFact, ...]] | None
    seasons: tuple[SeasonSummaryFact, ...] | None
    tmdb_television_id: str | None
    poster_url: str | None
    local_poster: bool
    poster_high_definition_url: str | None
    hero_url: str | None
    metadata_refreshed_at: date | None


@dataclass(frozen=True)
class ProviderSheet:
    """One provider answer, as the sheet reads it.

    Attributes:
        details: The provider's details.
        kind: ``"movie"`` or ``"show"`` — the call that answered.
        creator: The show's creator, crossed from TMDB when TVDB names none.
    """

    details: MediaDetails
    kind: Literal["movie", "show"]
    creator: str | None


def genres_of(details: MediaDetails) -> tuple[GenreId, ...]:
    """Map a provider's genres onto the contract's tokens.

    TMDB is read by genre id (its names are localised); TVDB by name.

    Args:
        details: The provider's details.

    Returns:
        The tokens, in the provider's order, without duplicates or unmapped genres.
    """
    if details.provider == "tmdb":
        found = [_TMDB_GENRES.get(genre_id) for genre_id in details.genre_ids]
    else:
        found = [_NAMED_GENRES.get(fold(name).strip()) for name in details.genres]
    return tuple(dict.fromkeys(genre for genre in found if genre is not None))


def status_of(details: MediaDetails) -> MediaStatus | None:
    """Map a provider's production status onto the contract's token.

    Args:
        details: The provider's details.

    Returns:
        The token, or ``None`` when the provider says nothing a token names.
    """
    if not details.series_status:
        return None
    return _STATUSES.get(details.series_status.strip().lower())


def trailer_key_of(details: MediaDetails) -> str | None:
    """Read the YouTube key out of a provider's trailer URL.

    Args:
        details: The provider's details.

    Returns:
        The key, or ``None`` when there is no trailer or the URL names none.
    """
    if not details.trailer_url:
        return None
    found = _YOUTUBE_KEY.search(details.trailer_url)
    return found.group(1) if found else None


def cast_of(details: MediaDetails) -> tuple[CastFact, ...]:
    """The provider's cast as the sheet lists it, in the provider's order.

    Args:
        details: The provider's details.

    Returns:
        One fact per cast member, a person listed twice (two roles) included twice.
    """
    return tuple(CastFact(name=member.name, role=member.role) for member in details.cast)


def cast_portraits_of(details: MediaDetails) -> dict[str, str]:
    """The cast's portrait URLs keyed by name.

    Args:
        details: The provider's details.

    Returns:
        Only the members the provider gives a portrait; a name listed twice keeps its
        first portrait.
    """
    portraits: dict[str, str] = {}
    for member in details.cast:
        if member.portrait_url:
            portraits.setdefault(member.name, member.portrait_url)
    return portraits


def poster_of(details: MediaDetails) -> str | None:
    """The provider's first poster URL, or ``None``."""
    return next((image.url for image in details.images if image.type == "poster" and image.url), None)


def hero_of(details: MediaDetails) -> str | None:
    """The provider's first backdrop URL, else its top-level backdrop, or ``None``."""
    backdrop = next((image.url for image in details.images if image.type == "backdrop" and image.url), None)
    return backdrop or details.primary_backdrop_url or None


def _refuse_unavailable(provider: str, exc: BaseException) -> AppUnavailable:
    """Build the refusal for a provider that did not answer, and log why.

    Args:
        provider: The provider asked.
        exc: What the call raised.

    Returns:
        ``provider.unavailable``, naming the provider.
    """
    log.warning("app.library.provider_unavailable", provider=provider, error=str(exc))
    return AppUnavailable(
        "A metadata provider did not answer.", code=RefusalCode.PROVIDER_UNAVAILABLE, params={"provider": provider}
    )


def refuse_not_found(provider: str) -> AppNotFound:
    """Build the refusal for an id the provider does not know.

    Args:
        provider: The provider asked.

    Returns:
        ``media.not_found``, naming the provider.
    """
    return AppNotFound("No medium answers this id.", code=RefusalCode.MEDIA_NOT_FOUND, params={"provider": provider})


def fetch_details(
    client: object | None,
    provider: str,
    provider_id: str,
    kind: Literal["movie", "show"] | None,
) -> tuple[MediaDetails, Literal["movie", "show"]]:
    """Ask a provider for a medium's details.

    With no ``kind`` (a medium the library does not hold), the show is asked first and the
    movie only on a genuine 404 — any other failure is the provider's, not the id's.

    Args:
        client: The provider's client, or ``None`` when it is not configured.
        provider: ``"tvdb"`` or ``"tmdb"``.
        provider_id: The id at that provider.
        kind: The medium's kind when the library knows it.

    Returns:
        ``(details, kind)``.

    Raises:
        AppNotFound: ``media.not_found`` when the provider does not know the id.
        AppUnavailable: ``provider.unavailable`` when the provider is not configured or
            did not answer.
    """
    if not isinstance(client, SheetClient):
        raise _refuse_unavailable(provider, LookupError("no client configured"))
    tries: tuple[Literal["movie", "show"], ...] = (kind,) if kind is not None else ("show", "movie")
    for attempt in tries:
        call = client.get_tv if attempt == "show" else client.get_movie
        try:
            return call(provider_id), attempt
        except ApiError as exc:
            if exc.http_status != _NOT_FOUND:
                raise _refuse_unavailable(provider, exc) from exc
        except Exception as exc:  # noqa: BLE001 — a provider down is a 503, never a 500
            raise _refuse_unavailable(provider, exc) from exc
    raise refuse_not_found(provider)


class ProviderSheetCache:
    """A bounded, expiring cache of provider answers, safe across request threads."""

    def __init__(self, clock: Callable[[], float]) -> None:
        """Start empty.

        Args:
            clock: The service's clock, epoch seconds.
        """
        self._clock = clock
        self._entries: OrderedDict[tuple[str, str], tuple[ProviderSheet, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str]) -> ProviderSheet | None:
        """Return a fresh answer, or ``None``.

        Args:
            key: ``(provider, provider id)``.

        Returns:
            The cached answer when it has not expired.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry[1] <= self._clock():
                return None
            self._entries.move_to_end(key)
            return entry[0]

    def put(self, key: tuple[str, str], sheet: ProviderSheet) -> None:
        """Keep an answer for :data:`PROVIDER_CACHE_TTL_S`, evicting the oldest past the bound.

        Args:
            key: ``(provider, provider id)``.
            sheet: The answer.
        """
        with self._lock:
            self._entries[key] = (sheet, self._clock() + PROVIDER_CACHE_TTL_S)
            self._entries.move_to_end(key)
            while len(self._entries) > PROVIDER_CACHE_MAX:
                self._entries.popitem(last=False)
