"""``LibraryReads``: the library's listing and membership reads (K1 § C.3).

Reads over the index (``library.db``) and the aired catalogue (``acquire.db``). Every read
is ``library.read``: each method is authorised by ``@requires`` before it opens anything,
the same door the v1 perimeter holds; nothing filters by right past it.

Identity is the provider id (Q15): a medium is read by the id the wire names, never by
its title. An id held by two rows, or by one row in two media folders, is a duplicate;
the reads never merge one, they count it.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from personalscraper.acquire.catalogue import CatalogueEpisode
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.library.catalogue import aired_of_season, off_catalogue
from personalscraper.app.library.completeness import CatalogueView
from personalscraper.app.library.facts import refuse_not_found
from personalscraper.app.library.identity import Provider, ref_key
from personalscraper.app.library.listing import (
    LibrarySort,
    held_of,
    open_reader,
    ordered_by_missing,
    page_of,
)
from personalscraper.app.library.sheets import MediaSheets
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import LIBRARY_PAGE_SIZE, IndexItem, LibraryIndex, ListingOrder, matches

__all__ = [
    "LIBRARY_PAGE_SIZE",
    "RECENT_LIMIT",
    "CategoryCount",
    "IncompleteEntry",
    "LibraryEntry",
    "LibraryPage",
    "LibraryReads",
    "LibrarySort",
    "Membership",
    "SeasonFacts",
    "SeasonsFacts",
]

#: Rows the « recently added » strip carries.
RECENT_LIMIT: Final[int] = 12


@dataclass(frozen=True)
class LibraryEntry:
    """One library entry, as a listing serves it: facts, never a pre-formatted line.

    Attributes:
        title: The title the library files it under.
        year: The year, or ``None``.
        kind: ``"movie"`` or ``"show"``.
        category_id: The engine's leaf category id.
        overview: The NFO's synopsis, or ``None``.
        ids: Every provider id (at least one), TVDB/TMDB as integers, IMDb as text.
        poster_url: The provider poster URL the NFO names, or ``None``.
        local_poster: Whether the poster to show is the folder's own file (no URL known,
            a poster file seen): the v1 image route serves it.
    """

    title: str
    year: int | None
    kind: Literal["movie", "show"]
    category_id: str
    overview: str | None
    ids: Mapping[str, int | str]
    poster_url: str | None
    local_poster: bool = False


@dataclass(frozen=True)
class LibraryPage:
    """One page of the listing.

    Attributes:
        total: The library's count when nothing filters, else ``matching``.
        matching: How many entries the question matches — what the page is a page of.
        loaded: How many entries the library holds, whatever is filtered.
        items: The page's entries.
    """

    total: int
    matching: int
    loaded: int
    items: tuple[LibraryEntry, ...]


@dataclass(frozen=True)
class CategoryCount:
    """How many live entries one engine leaf category holds.

    Attributes:
        category_id: The leaf category id.
        count: Its live entries.
    """

    category_id: str
    count: int


@dataclass(frozen=True)
class IncompleteEntry:
    """A show missing aired episodes.

    Attributes:
        entry: The show.
        owned: Its aired episodes the library holds.
        aired: Its aired episodes.
    """

    entry: LibraryEntry
    owned: int
    aired: int


@dataclass(frozen=True)
class Membership:
    """What the library holds of one medium, named by a provider id.

    Attributes:
        in_library: Whether some live row holds the id.
        rows: How many holdings the id names — rows, and the extra media folders of a row
            spread over several; two or more is a duplicate.
        incomplete: Whether it is a show the library holds with aired episodes missing.
        ids: The held row's provider ids, or ``None`` when no live row holds it.
        kind: The held row's kind, or ``None`` when no live row holds it.
    """

    in_library: bool
    rows: int
    incomplete: bool
    ids: Mapping[str, int | str] | None
    kind: Literal["movie", "show"] | None


@dataclass(frozen=True)
class SeasonFacts:
    """One season of a show, as the catalogue and the library know it.

    Attributes:
        number: The season number.
        episodes: How many episodes the catalogue lists, or ``None`` when never catalogued.
        air_date: The season's first catalogued air date, or ``None``.
        off_catalogue: Held episode numbers above the last one the catalogue lists.
    """

    number: int
    episodes: int | None
    air_date: date | None
    off_catalogue: tuple[int, ...]


@dataclass(frozen=True)
class SeasonsFacts:
    """A show's seasons, what the library holds of them and what has aired.

    Attributes:
        seasons: The catalogued seasons and the held ones, by number.
        owned: The held episode numbers per season.
        aired: The aired count per season; ``None`` when nothing dated says.
    """

    seasons: tuple[SeasonFacts, ...]
    owned: Mapping[int, tuple[int, ...]]
    aired: Mapping[int, int | None]


def _entry(row: IndexItem) -> LibraryEntry:
    """Serve an index row as a library entry.

    Args:
        row: The row.

    Returns:
        The entry.
    """
    return LibraryEntry(
        title=row.title,
        year=row.year,
        kind=row.kind,
        category_id=row.category_id,
        overview=row.overview,
        ids=row.ids,
        poster_url=row.poster_url,
        local_poster=row.local_poster,
    )


def _by_season(pairs: set[tuple[int, int]]) -> dict[int, tuple[int, ...]]:
    """Group ``(season, episode)`` pairs by season.

    Args:
        pairs: The pairs.

    Returns:
        ``{season: sorted episode numbers}``, by season.
    """
    grouped: dict[int, list[int]] = {}
    for season, episode in pairs:
        grouped.setdefault(season, []).append(episode)
    return {season: tuple(sorted(grouped[season])) for season in sorted(grouped)}


class LibraryReads:
    """The library's listing, membership and seasons reads.

    The index is opened read-only for each read (a WAL read takes no lock); the catalogue
    view is shared with the sheets.
    """

    def __init__(
        self,
        *,
        index: LibraryIndex,
        view: CatalogueView,
        sheets: MediaSheets,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Hold the index, the catalogue view and the sheets; nothing is opened yet.

        Args:
            index: ``library.db``, read-only.
            view: The aired catalogue and the ownership checker (shared: closed by its owner).
            sheets: The sheets, whose provider cache a show's seasons check an id against.
            clock: Epoch seconds; « today » for the aired counts.
        """
        self._index = index
        self._view = view
        self._media_sheets = sheets
        self._clock = clock

    def _today(self) -> date:
        """« Today » by the service's clock, local time."""
        return date.fromtimestamp(self._clock())

    # ------------------------------------------------------------------ reads

    @requires("readLibraryItems")
    def read_items(
        self,
        actor: Actor,
        *,
        category: Sequence[str] | None,
        sort: LibrarySort,
        reversed_: bool,
        query: str | None,
        page: int,
    ) -> LibraryPage:
        """Read one page of the library.

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).
            category: The engine leaf categories to keep; ``None`` or empty keeps every one.
            sort: The order.
            reversed_: Whether to read it the other way round.
            query: The search text, matched in the title and the original title ignoring
                accents and case; ``None`` or blank matches every entry.
            page: The page, zero based.

        Returns:
            The page and its three counts.

        Raises:
            AppBadRequest: ``request.invalid`` on a negative page.
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        if page < 0:
            raise AppBadRequest("The page is negative.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["page"]})
        wanted = set(category or ())
        if sort is not LibrarySort.MISSING:
            with open_reader(self._index) as reader:
                listed = reader.page(
                    categories=frozenset(wanted),
                    query=query,
                    order=ListingOrder(sort.value),
                    reversed_=reversed_,
                    page=page,
                )
            return LibraryPage(
                total=listed.total,
                matching=listed.matching,
                loaded=listed.loaded,
                items=tuple(_entry(row) for row in listed.items),
            )
        # « Missing » crosses the aired catalogue (``acquire.db``): the one order SQL over
        # ``library.db`` cannot compute, read over every live row in Python.
        today = self._today()
        with open_reader(self._index) as reader:
            rows = reader.live_items()
            measured = self._view.library_completeness(reader, rows, today)
        selected = [
            row for row in rows if (not wanted or row.category_id in wanted) and (query is None or matches(row, query))
        ]
        filtered = bool(wanted) or bool(query and query.strip())

        def missing_of(row: IndexItem) -> int | None:
            """The aired episodes a row lacks, or ``None`` when nothing says."""
            counts = measured.get(row.item_id)
            return counts.missing if counts is not None else None

        result = ordered_by_missing(selected, reversed_, missing_of)
        return LibraryPage(
            total=len(result) if filtered else len(rows),
            matching=len(result),
            loaded=len(rows),
            items=tuple(_entry(row) for row in page_of(result, page)),
        )

    @requires("readLibraryCategories")
    def read_categories(self, actor: Actor) -> list[CategoryCount]:
        """Count the live entries of each engine leaf category.

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).

        Returns:
            One count per leaf holding at least one entry, by category id.

        Raises:
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        with open_reader(self._index) as reader:
            counts = reader.category_counts()
        return [CategoryCount(category_id=leaf, count=counts[leaf]) for leaf in sorted(counts)]

    @requires("readLibraryRecent")
    def read_recent(self, actor: Actor) -> list[LibraryEntry]:
        """Read the most recently added entries.

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).

        Returns:
            The :data:`RECENT_LIMIT` newest live entries, newest first.

        Raises:
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        with open_reader(self._index) as reader:
            rows = reader.recent(RECENT_LIMIT)
        return [_entry(row) for row in rows]

    @requires("readLibraryIncomplete")
    def read_incomplete(self, actor: Actor) -> list[IncompleteEntry]:
        """Read the library's shows missing aired episodes, library-wide.

        A show never catalogued is not listed: its completeness is unknown, never « complete »
        nor « incomplete ».

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).

        Returns:
            The shows whose aired episodes outnumber the held ones, most missing first, then
            most recently added.

        Raises:
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        with open_reader(self._index) as reader:
            rows = reader.live_items()
            measured = self._view.library_completeness(reader, rows, self._today())
        found: list[tuple[int, IncompleteEntry]] = []
        for row in rows:
            counts = measured.get(row.item_id)
            if counts is not None and counts.missing > 0:
                found.append((counts.missing, IncompleteEntry(_entry(row), counts.owned, counts.aired)))
        found.sort(key=lambda pair: -pair[0])
        return [entry for _, entry in found]

    @requires("readLibraryMembership")
    def read_membership(self, actor: Actor, ref: MediaRef) -> Membership:
        """Say what the library holds of one medium.

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).
            ref: The medium, by the one id the wire names.

        Returns:
            The membership. ``rows`` counts every holding row (a 0-file phantom included)
            plus the extra media folders of a row spread over several.

        Raises:
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        with open_reader(self._index) as reader:
            holders, folders = held_of(reader, ref)
        rows = sum(max(1, len(folders.get(row.item_id, ()))) for row in holders)
        live = [row for row in holders if row.item_id in folders]
        if not live:
            return Membership(in_library=False, rows=rows, incomplete=False, ids=None, kind=None)
        held = live[0]
        measured = self._view.completeness(held, self._today())
        return Membership(
            in_library=True,
            rows=rows,
            incomplete=measured is not None and measured.missing > 0,
            ids=held.ids,
            kind=held.kind,
        )

    @requires("readMediaSeasons")
    def read_seasons(self, actor: Actor, ref: MediaRef) -> SeasonsFacts:
        """Read a show's seasons against its catalogue and the library.

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).
            ref: The show.

        Returns:
            The catalogued and held seasons, the held episodes, the aired counts. A show
            never catalogued lists its held seasons with nothing known of them.

        Raises:
            AppNotFound: ``media.not_found`` for an id a held movie carries, for an IMDb id
                the library does not hold, and when the provider does not know the id.
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read;
                ``provider.unavailable`` when the provider is not configured or
                does not answer for an id the library does not hold.
        """
        with open_reader(self._index) as reader:
            holders, folders = held_of(reader, ref)
        shows = [row for row in holders if row.kind == "show"]
        provider, provider_id = ref_key(ref)
        if holders and not shows:
            raise refuse_not_found(provider.value)
        if not holders:
            if provider is Provider.IMDB:
                raise refuse_not_found(provider.value)
            self._media_sheets.provider_sheet(provider.value, provider_id, "show")
        held_row = next((row for row in shows if row.item_id in folders), shows[0] if shows else None)
        episodes = self._view.catalogue_of(held_row) if held_row is not None else None
        owned_pairs: set[tuple[int, int]] = set()
        for row in shows:
            owned_pairs |= self._view.owned_pairs(row)
        owned = _by_season(owned_pairs)
        catalogued: dict[int, list[CatalogueEpisode]] = {}
        for episode in episodes or []:
            catalogued.setdefault(episode.season, []).append(episode)
        today = self._today()
        seasons: list[SeasonFacts] = []
        aired: dict[int, int | None] = {}
        for number in sorted(set(catalogued) | set(owned)):
            listed = catalogued.get(number, [])
            dates = [ep.air_date for ep in listed if ep.air_date is not None]
            seasons.append(
                SeasonFacts(
                    number=number,
                    episodes=len(listed) if episodes is not None else None,
                    air_date=min(dates, default=None),
                    off_catalogue=(
                        off_catalogue(owned.get(number, ()), [ep.episode for ep in listed])
                        if episodes is not None
                        else ()
                    ),
                )
            )
            aired[number] = aired_of_season(listed, today)
        return SeasonsFacts(seasons=tuple(seasons), owned=owned, aired=aired)
