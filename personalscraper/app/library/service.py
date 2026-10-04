"""``LibraryService``: the one service the v1 library and media routes call (K1 § C.3).

Reads over the index (``library.db``), the aired catalogue (``acquire.db``) and the
metadata providers, and two writes: a medium's rescrape, launched through the
maintenance path, and a medium's deletion (its folder, its index rows, its Plex entry,
``app/library/deletion.py``). Every read is ``library.read``, the rescrape
``library.rescrape`` and the deletion ``library.delete``, doors the v1 perimeter holds:
nothing filters by right, so ``actor`` is carried for the signature the routes share and
is consulted only to journal who deleted.

Identity is the provider id (Q15): a medium is read by the id the wire names, never by
its title. An id held by two rows, or by one row in two media folders, is a duplicate;
the reads never merge one, they count it, and the deletion refuses it (O-5 B).
"""

from __future__ import annotations

import mimetypes
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from personalscraper.acquire.catalogue import CatalogueEpisode, CatalogueStore, ProviderClients
from personalscraper.api.metadata._base import MediaDetails
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.errors import AppBadRequest, AppConflict, AppInternalError, AppNotFound, RefusalCode
from personalscraper.app.library.catalogue import (
    Completeness,
    aired_of_season,
    catalogue_key,
    completeness,
    off_catalogue,
)
from personalscraper.app.library.deletion import (
    DeletionReport,
    MediaDeletion,
    PlexOutcome,
    follow_up_plex,
    remove_empty_parents,
    remove_item_rows,
)
from personalscraper.app.library.facts import (
    EpisodeFact,
    MediaSheetFacts,
    ProviderSheet,
    ProviderSheetCache,
    SeasonSummaryFact,
    SheetClient,
    cast_of,
    cast_portraits_of,
    fetch_details,
    genres_of,
    hero_of,
    poster_of,
    refuse_not_found,
    status_of,
    trailer_key_of,
)
from personalscraper.app.library.identity import Provider, ref_key
from personalscraper.app.library.listing import (
    LIBRARY_PAGE_SIZE,
    IndexRow,
    LibrarySort,
    live_episode_pairs,
    live_folders,
    matches,
    mounted_media_folders,
    ordered,
    page_of,
    read_holders,
    read_live_rows,
    resolve_media_folder,
)
from personalscraper.app.maintenance.registry import REGISTRY, MaintenanceAction
from personalscraper.app.maintenance.service import LaunchedRun, launch_action, running_run
from personalscraper.conf.preprod_guard import PreprodGuardError
from personalscraper.core.artwork_naming import artwork_inventory
from personalscraper.core.delete_permit import AllowAllPermit, DeletePermit
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.deletion import DeleteOutcome, delete_media_folder
from personalscraper.indexer.ownership import IndexerOwnershipChecker
from personalscraper.lock import acquire_pipeline_lock, release_lock, scrape_locks_dir_for
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.plex import PlexClient
    from personalscraper.conf.models.config import Config

log = get_logger("app.library.service")

__all__ = [
    "LIBRARY_PAGE_SIZE",
    "POSTER_MAX_BYTES",
    "RECENT_LIMIT",
    "CategoryCount",
    "IncompleteEntry",
    "LibraryEntry",
    "LibraryPage",
    "LibraryService",
    "LibrarySort",
    "LocalPoster",
    "Membership",
    "RescrapeAccepted",
    "SeasonFacts",
    "SeasonsFacts",
]

#: Rows the « recently added » strip carries.
RECENT_LIMIT: Final[int] = 12

# How long a read waits on a writer's checkpoint before failing (the canonical set's value).
_BUSY_TIMEOUT_MS: Final[int] = 5000

#: The maintenance action that rescrapes one index row.
_RESCRAPE_ITEM_ACTION: Final[str] = "library-rescrape-item"

#: The largest poster file served, in bytes: a request reads it whole into memory, so a
#: file above this (no real poster is) is refused before it is read.
POSTER_MAX_BYTES: Final[int] = 20 * 1024 * 1024


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


@dataclass(frozen=True)
class RescrapeAccepted:
    """A medium's rescrape, accepted: launched, or already under way.

    Attributes:
        provider: The provider the medium was named at.
        provider_id: Its id there, as the wire named it.
        queued: Whether ``pipeline.lock`` was held: the run waits in the visible queue.
        run_uid: The run of the lowest holding row launched now (one run per row holding
            live files), else the lowest holding row's run already under way; ``None``
            when that run ended before it could be read.
    """

    provider: Provider
    provider_id: str
    queued: bool
    run_uid: str | None


@dataclass(frozen=True)
class LocalPoster:
    """The poster file a medium's library folder holds, read at request time.

    Attributes:
        content: The file's bytes.
        media_type: Its media type, from its extension (``image/jpeg``, ``image/png``).
    """

    content: bytes
    media_type: str


def _folder_poster(mount_path: str, folder: str) -> LocalPoster | None:
    """Read the item-level poster of one media folder, never anything outside it.

    The folder is resolved inside its disk (:func:`resolve_media_folder`), and the poster
    file (the name the artwork inventory recognises) must resolve directly inside the
    folder: a symlink or a ``..`` leading elsewhere is refused, whatever it reaches.

    Args:
        mount_path: The disk's mount point, as the index names it.
        folder: The media folder below it, as the index names it.

    Returns:
        The poster, or ``None`` when the disk, the folder or the poster is not there, when
        a path escapes, when a symlink loops, or when the poster exceeds
        ``POSTER_MAX_BYTES``.
    """
    resolved = resolve_media_folder(mount_path, folder)
    if resolved is None:
        return None
    _, directory = resolved
    try:
        name = artwork_inventory(directory)["poster"]
        if name is None:
            return None
        poster = (directory / name).resolve(strict=True)
        if poster.parent != directory or not poster.is_file():
            return None
        if poster.stat().st_size > POSTER_MAX_BYTES:
            return None
        content = poster.read_bytes()
    except (OSError, RuntimeError):
        # Python 3.12's strict resolve raises RuntimeError, not OSError, on a symlink loop.
        return None
    media_type, _ = mimetypes.guess_type(poster.name)
    return LocalPoster(content=content, media_type=media_type or "application/octet-stream")


@dataclass(frozen=True)
class _DeletionPlan:
    """What one validated medium's deletion touches.

    Attributes:
        ref: The medium, as the request named it.
        item_id: The one index row holding it.
        targets: Its media folders, resolved inside their disks: ``(mount point, folder)``.
        unresolved: Its mounted media folders that do not resolve inside their disk (or
            through a symlink): never deleted, counted failed.
        unreachable: Its media folders on a disk the index says is not mounted.
    """

    ref: MediaRef
    item_id: int
    targets: tuple[tuple[Path, Path], ...]
    unresolved: int
    unreachable: int


@dataclass(frozen=True)
class _Deleted:
    """One medium's deletion before Plex is told.

    Attributes:
        deletion: What was done, Plex not yet asked.
        survivors: The nearest surviving ancestor of each deleted folder.
    """

    deletion: MediaDeletion
    survivors: tuple[Path, ...]


def _deletable_folder(mounted: tuple[str, str]) -> tuple[Path, Path] | None:
    """Resolve a media folder for deletion: inside its disk, and reached through no symlink.

    Args:
        mounted: ``(mount path, "<category>/<media folder>")`` as the index names it.

    Returns:
        ``(mount point, folder)`` resolved, or ``None`` when the folder does not resolve
        inside its disk, or its own path or its category's is a symlink (deleting through
        a link would reach whatever it points to).
    """
    mount_path, folder = mounted
    literal = Path(mount_path) / folder
    if literal.is_symlink() or literal.parent.is_symlink():
        return None
    return resolve_media_folder(mount_path, folder)


def _entry(row: IndexRow) -> LibraryEntry:
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


def _sheet_ids(
    held: IndexRow | None, answered: Mapping[str, str], provider: str, provider_id: str
) -> dict[str, int | str]:
    """Merge the ids the library's row holds with those the provider answered.

    The row's ids win; the provider's fill the gaps. Placeholders (``""``, ``"0"``) name nothing.

    Args:
        held: The live row holding the medium, or ``None``.
        answered: The provider's ``external_ids`` (text values).
        provider: The provider asked.
        provider_id: The id it was asked at.

    Returns:
        ``{"tvdb": int, "tmdb": int, "imdb": str}`` in that order, the absent ones left out.
    """
    known = {**answered, provider: provider_id}
    ids: dict[str, int | str] = {}
    for name in ("tvdb", "tmdb", "imdb"):
        if held is not None and name in held.ids:
            ids[name] = held.ids[name]
            continue
        raw = str(known.get(name) or "").strip()
        if name == "imdb" and raw:
            ids[name] = raw
        elif raw.isdigit() and raw != "0":
            ids[name] = int(raw)
    return ids


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


class LibraryService:
    """The library's reads, its rescrape and its deletion.

    The index is opened read-only for each read (a WAL read takes no lock); the catalogue
    store and the ownership checker are shared, and serialised by one lock, since a web
    request thread may call while another runs.
    """

    def __init__(
        self,
        *,
        index_db: Path,
        data_dir: Path,
        catalogue: CatalogueStore,
        ownership: IndexerOwnershipChecker,
        providers: ProviderClients,
        clock: Callable[[], float] = time.time,
        plex: PlexClient | None = None,
        delete_permit: DeletePermit | None = None,
        config: Config | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Hold the stores and the clients; nothing is opened yet.

        Args:
            index_db: Path of ``library.db`` (it also holds the maintenance runs).
            data_dir: The pipeline data directory holding ``pipeline.lock``.
            catalogue: The aired catalogue's store (owned: closed by :meth:`close`).
            ownership: The ownership checker over ``library.db`` (owned: closed by :meth:`close`).
            providers: The metadata provider clients; ``None`` for an unconfigured one.
            clock: Epoch seconds; « today » for the aired counts and the provider cache's clock.
            plex: The Plex server a deletion tells; ``None`` when none is configured.
            delete_permit: The deletion authority a deletion consults (fail-open); allow-all
                when ``None``.
            config: The loaded configuration, naming preprod's roots: required under
                ``staging``, where a deletion without it deletes nothing.
            sleep: Pauses a deletion's wait for a Plex scan.
            monotonic: Monotonic seconds, bounding that wait.
        """
        self._index_db = index_db
        self._data_dir = data_dir
        self._catalogue = catalogue
        self._ownership = ownership
        self._providers = providers
        self._clock = clock
        self._lock = threading.Lock()
        self._sheets = ProviderSheetCache(clock)
        self._plex = plex
        self._delete_permit: DeletePermit = delete_permit if delete_permit is not None else AllowAllPermit()
        self._config = config
        self._sleep = sleep
        self._monotonic = monotonic

    def close(self) -> None:
        """Close the catalogue store and the ownership checker (idempotent)."""
        with self._lock:
            self._catalogue.close()
            self._ownership.close()

    # ------------------------------------------------------------------ helpers

    def _connect(self) -> sqlite3.Connection:
        """Open ``library.db`` read-only, with ``sqlite3.Row`` rows.

        Read-only at the file (``mode=ro``: an absent index is an error, never a new empty
        file) and at the connection (``query_only``).

        Returns:
            A connection that can take no writer lock.

        Raises:
            sqlite3.OperationalError: When ``library.db`` cannot be opened.
        """
        uri = f"{self._index_db.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, check_same_thread=False)
        # Not the canonical writer PRAGMA set: WAL ``journal_mode`` raises on a read-only
        # connection (scripts/check-pragma-discipline.py allow-lists this reader).
        conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA query_only=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _today(self) -> date:
        """« Today » by the service's clock, local time."""
        return date.fromtimestamp(self._clock())

    def _catalogue_of(self, row: IndexRow) -> list[CatalogueEpisode] | None:
        """Read a show's catalogue under the key the refresh writes it at.

        Args:
            row: The show's row.

        Returns:
            Its episodes, or ``None`` when it was never fetched or carries no TVDB/TMDB id.
        """
        key = catalogue_key(row.ids, row.canonical_provider)
        if key is None:
            return None
        with self._lock:
            return self._catalogue.episodes(*key)

    def _owned_pairs(self, row: IndexRow) -> set[tuple[int, int]]:
        """The ``(season, episode)`` pairs the library holds under a show's ids.

        Args:
            row: The show's row.

        Returns:
            The held pairs (empty for a row with no id).
        """
        ref = row.media_ref()
        if ref is None:
            return set()
        with self._lock:
            return self._ownership.owned_pairs(ref)

    def _completeness(self, row: IndexRow, today: date) -> Completeness | None:
        """How much of what a show has aired the library holds.

        Args:
            row: The show's row.
            today: The reference date.

        Returns:
            The counts, or ``None`` for a movie or a show never catalogued.
        """
        if row.kind != "show":
            return None
        episodes = self._catalogue_of(row)
        if episodes is None:
            return None
        return completeness(episodes, self._owned_pairs(row), today)

    def _library_completeness(
        self, conn: sqlite3.Connection, rows: Sequence[IndexRow], today: date
    ) -> dict[int, Completeness]:
        """Measure every catalogued show of the library at once.

        The held episodes are read in one query and united over the rows sharing a
        catalogue key (a duplicate's rows hold one identity); each key's catalogue is read
        once.

        Args:
            conn: The open index.
            rows: The live rows.
            today: The reference date.

        Returns:
            ``{item_id: completeness}`` for the show rows whose catalogue is known.
        """
        held = live_episode_pairs(conn)
        by_key: dict[tuple[str, str], list[IndexRow]] = {}
        for row in rows:
            key = catalogue_key(row.ids, row.canonical_provider) if row.kind == "show" else None
            if key is not None:
                by_key.setdefault(key, []).append(row)
        measured: dict[int, Completeness] = {}
        for key, sharing in by_key.items():
            with self._lock:
                episodes = self._catalogue.episodes(*key)
            if episodes is None:
                continue
            owned = set().union(*(held.get(row.item_id, set()) for row in sharing))
            counts = completeness(episodes, owned, today)
            if counts is not None:
                for row in sharing:
                    measured[row.item_id] = counts
        return measured

    def _holders(self, conn: sqlite3.Connection, ref: MediaRef) -> list[IndexRow]:
        """Every row carrying the reference's id.

        Args:
            conn: The open index.
            ref: The medium.

        Returns:
            The holding rows, live or not, by id.
        """
        provider, provider_id = ref_key(ref)
        return read_holders(conn, provider.value, provider_id)

    def _held(self, conn: sqlite3.Connection, ref: MediaRef) -> tuple[list[IndexRow], dict[int, set[str]]]:
        """The rows holding a reference and the media folders of their live files.

        Args:
            conn: The open index.
            ref: The medium.

        Returns:
            ``(holders, {item_id: folders})``; a holder absent from the mapping has no live file.
        """
        holders = self._holders(conn, ref)
        return holders, live_folders(conn, [row.item_id for row in holders])

    # ------------------------------------------------------------------ reads

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
            actor: Who reads (not consulted: every read is ``library.read``).
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
        """
        if page < 0:
            raise AppBadRequest("The page is negative.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["page"]})
        today = self._today()
        with closing(self._connect()) as conn:
            rows = read_live_rows(conn)
            measured = self._library_completeness(conn, rows, today) if sort is LibrarySort.MISSING else {}
        wanted = set(category or ())
        selected = [
            row for row in rows if (not wanted or row.category_id in wanted) and (query is None or matches(row, query))
        ]
        filtered = bool(wanted) or bool(query and query.strip())

        def missing_of(row: IndexRow) -> int | None:
            """The aired episodes a row lacks, or ``None`` when nothing says."""
            counts = measured.get(row.item_id)
            return counts.missing if counts is not None else None

        result = ordered(selected, sort, reversed_, missing_of)
        return LibraryPage(
            total=len(result) if filtered else len(rows),
            matching=len(result),
            loaded=len(rows),
            items=tuple(_entry(row) for row in page_of(result, page)),
        )

    def read_categories(self, actor: Actor) -> list[CategoryCount]:
        """Count the live entries of each engine leaf category.

        Args:
            actor: Who reads (not consulted).

        Returns:
            One count per leaf holding at least one entry, by category id.
        """
        with closing(self._connect()) as conn:
            rows = read_live_rows(conn)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.category_id] = counts.get(row.category_id, 0) + 1
        return [CategoryCount(category_id=leaf, count=counts[leaf]) for leaf in sorted(counts)]

    def read_recent(self, actor: Actor) -> list[LibraryEntry]:
        """Read the most recently added entries.

        Args:
            actor: Who reads (not consulted).

        Returns:
            The :data:`RECENT_LIMIT` newest live entries, newest first.
        """
        with closing(self._connect()) as conn:
            rows = read_live_rows(conn)
        return [_entry(row) for row in rows[:RECENT_LIMIT]]

    def read_incomplete(self, actor: Actor) -> list[IncompleteEntry]:
        """Read the library's shows missing aired episodes, library-wide.

        A show never catalogued is not listed: its completeness is unknown, never « complete »
        nor « incomplete ».

        Args:
            actor: Who reads (not consulted).

        Returns:
            The shows whose aired episodes outnumber the held ones, most missing first, then
            most recently added.
        """
        with closing(self._connect()) as conn:
            rows = read_live_rows(conn)
            measured = self._library_completeness(conn, rows, self._today())
        found: list[tuple[int, IncompleteEntry]] = []
        for row in rows:
            counts = measured.get(row.item_id)
            if counts is not None and counts.missing > 0:
                found.append((counts.missing, IncompleteEntry(_entry(row), counts.owned, counts.aired)))
        found.sort(key=lambda pair: -pair[0])
        return [entry for _, entry in found]

    def read_membership(self, actor: Actor, ref: MediaRef) -> Membership:
        """Say what the library holds of one medium.

        Args:
            actor: Who reads (not consulted).
            ref: The medium, by the one id the wire names.

        Returns:
            The membership. ``rows`` counts every holding row (a 0-file phantom included)
            plus the extra media folders of a row spread over several.
        """
        with closing(self._connect()) as conn:
            holders, folders = self._held(conn, ref)
        rows = sum(max(1, len(folders.get(row.item_id, ()))) for row in holders)
        live = [row for row in holders if row.item_id in folders]
        if not live:
            return Membership(in_library=False, rows=rows, incomplete=False, ids=None, kind=None)
        held = live[0]
        measured = self._completeness(held, self._today())
        return Membership(
            in_library=True,
            rows=rows,
            incomplete=measured is not None and measured.missing > 0,
            ids=held.ids,
            kind=held.kind,
        )

    def read_seasons(self, actor: Actor, ref: MediaRef) -> SeasonsFacts:
        """Read a show's seasons against its catalogue and the library.

        Args:
            actor: Who reads (not consulted).
            ref: The show.

        Returns:
            The catalogued and held seasons, the held episodes, the aired counts. A show
            never catalogued lists its held seasons with nothing known of them.

        Raises:
            AppNotFound: ``media.not_found`` for an id a held movie carries, for an IMDb id
                the library does not hold, and when the provider does not know the id.
            AppUnavailable: ``provider.unavailable`` when the provider is not configured or
                does not answer for an id the library does not hold.
        """
        with closing(self._connect()) as conn:
            holders, folders = self._held(conn, ref)
        shows = [row for row in holders if row.kind == "show"]
        provider, provider_id = ref_key(ref)
        if holders and not shows:
            raise refuse_not_found(provider.value)
        if not holders:
            if provider is Provider.IMDB:
                raise refuse_not_found(provider.value)
            self._provider_sheet(provider.value, provider_id, "show")
        held_row = next((row for row in shows if row.item_id in folders), shows[0] if shows else None)
        episodes = self._catalogue_of(held_row) if held_row is not None else None
        owned_pairs: set[tuple[int, int]] = set()
        for row in shows:
            owned_pairs |= self._owned_pairs(row)
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

    def read_sheet(self, actor: Actor, ref: MediaRef) -> MediaSheetFacts:
        """Read a medium's sheet: the provider's facts crossed with the library's.

        A medium the library does not hold is still answered (owned ``False``).

        Args:
            actor: Who reads (not consulted).
            ref: The medium.

        Returns:
            The sheet's facts.

        Raises:
            AppNotFound: ``media.not_found`` when the provider does not know the id, or for
                an IMDb id the library does not hold (no client reads a sheet by IMDb id).
            AppUnavailable: ``provider.unavailable`` when the provider is not configured or
                does not answer.
        """
        with closing(self._connect()) as conn:
            holders, folders = self._held(conn, ref)
        live = [row for row in holders if row.item_id in folders]
        held = live[0] if live else None
        provider, provider_id = self._provider_for(ref, held)
        answer = self._provider_sheet(provider, provider_id, held.kind if held is not None else None)
        details = answer.details
        ids = _sheet_ids(held, details.external_ids, provider, provider_id)
        is_show = answer.kind == "show"
        episodes: list[CatalogueEpisode] | None = None
        if is_show:
            key = catalogue_key(held.ids, held.canonical_provider) if held is not None else catalogue_key(ids, provider)
            if key is not None:
                with self._lock:
                    episodes = self._catalogue.episodes(*key)
        provider_poster = poster_of(details)
        poster_url = provider_poster or (held.poster_url if held is not None else None)
        refreshed = held.date_provider_read if held is not None else None
        tmdb_tv = ids.get("tmdb") if is_show else None
        return MediaSheetFacts(
            title=held.title if held is not None else details.title,
            kind=answer.kind,
            year=details.year if details.year is not None else (held.year if held is not None else None),
            rating=details.rating,
            genres=genres_of(details),
            runtime=details.runtime_minutes,
            overview=(held.overview if held is not None and held.overview else None) or details.overview or None,
            director=details.director,
            creator=answer.creator,
            cast=cast_of(details),
            cast_portraits=cast_portraits_of(details),
            trailer_key=trailer_key_of(details),
            trailer_name=details.trailer_name,
            trailer_language=details.trailer_language,
            ids=ids,
            status=status_of(details),
            owned=held is not None,
            episodes=self._episode_facts(episodes) if is_show else None,
            seasons=self._season_summaries(details, episodes) if is_show else None,
            tmdb_television_id=str(tmdb_tv) if tmdb_tv is not None else None,
            poster_url=poster_url,
            local_poster=poster_url is None and held is not None and held.has_local_poster,
            poster_high_definition_url=provider_poster,
            hero_url=hero_of(details),
            metadata_refreshed_at=datetime.fromtimestamp(refreshed).date() if refreshed is not None else None,
        )

    def read_local_poster(self, actor: Actor, ref: MediaRef) -> LocalPoster:
        """Read the poster file of the library folder holding a medium.

        The folder is the index's (the row the sheet reads: the lowest holding row with
        live files), on a disk the index says is mounted; the file is resolved now, never
        named by the request.

        Args:
            actor: Who reads (not consulted).
            ref: The medium.

        Returns:
            The poster's bytes and media type.

        Raises:
            AppNotFound: ``media.not_found`` when no row holding the id has a live file, or
                when none of its folders holds a poster that can be read inside it.
        """
        provider, _ = ref_key(ref)
        with closing(self._connect()) as conn:
            holders, folders = self._held(conn, ref)
            live = [row for row in holders if row.item_id in folders]
            mounted = mounted_media_folders(conn, live[0].item_id) if live else []
        for mount_path, folder in mounted:
            poster = _folder_poster(mount_path, folder)
            if poster is not None:
                return poster
        raise refuse_not_found(provider.value)

    # ------------------------------------------------------------------ writes

    def request_rescrape(self, actor: Actor, ref: MediaRef) -> RescrapeAccepted:
        """Rescrape one medium: each row holding it with live files, through the maintenance path.

        One ``library-rescrape-item`` run is reserved and spawned per holding row with live
        files (a duplicate with files in both rows rescrapes both), no dry run first. A held
        ``pipeline.lock`` is no refusal: the runs wait in the visible queue. A row whose
        rescrape already runs is no refusal either: the ask is accepted on that run (the
        contract's ``rescrapeMedia`` declares no 409).

        Args:
            actor: Who asks (not consulted: the v1 perimeter holds ``library.rescrape``).
            ref: The medium, by the one id the wire names.

        Returns:
            The acceptance, naming the lowest holding row's launched run, else the lowest
            holding row's run already under way; queued when any of them waits on the
            pipeline.

        Raises:
            AppNotFound: ``media.not_found`` when no row holding the id has a live file.
            AppInternalError: When a runner cannot be spawned; the runs spawned before it
                stay live.
        """
        provider, provider_id = ref_key(ref)
        with closing(self._connect()) as conn:
            holders, folders = self._held(conn, ref)
        live = [row.item_id for row in holders if row.item_id in folders]
        if not live:
            raise refuse_not_found(provider.value)
        action = next(a for a in REGISTRY if a.id == _RESCRAPE_ITEM_ACTION)
        launched: list[LaunchedRun] = []
        running: list[LaunchedRun] = []
        for item_id in sorted(live):
            run, joined = self._launch_or_join(action, item_id, provider)
            (running if joined else launched).append(run)
        log.info("app.library.rescrape_launched", provider=provider.value, item_ids=sorted(live))
        answered = launched[0] if launched else running[0]
        return RescrapeAccepted(
            provider=provider,
            provider_id=provider_id,
            queued=any(run.queued for run in (*launched, *running)),
            run_uid=answered.run_uid,
        )

    def _launch_or_join(self, action: MaintenanceAction, item_id: int, provider: Provider) -> tuple[LaunchedRun, bool]:
        """Launch one row's rescrape, or join the one already running.

        The duplicate guard refuses while the row's rescrape runs; that run may end
        between the refusal and the read that names it, and the launch is then retried
        once.

        Args:
            action: The per-medium rescrape.
            item_id: The holding row.
            provider: The provider the medium is asked by, for the logs.

        Returns:
            The run, and whether it was joined rather than launched.

        Raises:
            AppInternalError: When a runner cannot be spawned, or when the row's rescrape is
                refused as running twice yet never found running.
        """
        options = {"item_id": item_id}
        for _attempt in range(2):
            try:
                return launch_action(action, options, db_path=self._index_db, data_dir=self._data_dir), False
            except AppConflict:
                run = running_run(action, options, db_path=self._index_db, data_dir=self._data_dir)
            if run is not None:
                # This row's rescrape is already running: the ask is accepted on that run.
                log.info("app.library.rescrape_already_running", provider=provider.value, item_id=item_id)
                return run, True
            log.info("app.library.rescrape_ended_before_read", provider=provider.value, item_id=item_id)
        raise AppInternalError("the rescrape was refused as running but no run was found")

    def delete_media(self, actor: Actor, refs: Sequence[MediaRef]) -> DeletionReport:
        """Delete media everywhere: their folders on the disks, their index rows, their Plex entries.

        All or nothing at the refusal: ``pipeline.lock`` is taken for the whole request, and
        every reference is validated before any folder is touched. Then, per medium, its
        one media folder is deleted through the folder-deletion primitive (the deletion
        authority consulted, the deletion journaled with ``web:<account id>``, the indexer
        told), the parent folders it left empty are removed up to the library root, and
        its index rows are removed with their tombstones — only when no folder of it was
        kept. Plex is told last, per section touched (:func:`follow_up_plex`). Nothing is
        rolled back: a kept folder, a failed removal or a Plex failure is reported.

        Args:
            actor: Who deletes (an Admin: the v1 perimeter holds ``library.delete``).
            refs: The media, each by the one id the wire names; a medium named twice is
                deleted once.

        Returns:
            The report: how many media went entirely, and what each deletion did.

        Raises:
            AppConflict: ``library.locked`` while a run holds ``pipeline.lock``;
                ``media.ambiguous`` (``params.provider`` / ``params.providerId``) when two
                or more rows, or one row's live files in two or more media folders, hold an
                id (operator ruling O-5 B). Nothing is deleted.
            AppNotFound: ``media.not_found`` (``params.provider`` / ``params.providerId``)
                when no index row holds an id. Nothing is deleted.
        """
        lock_file = self._data_dir / "pipeline.lock"
        if not acquire_pipeline_lock(lock_file, scrape_locks_dir_for(self._data_dir)):
            raise AppConflict("The pipeline holds the library.", code=RefusalCode.LIBRARY_LOCKED)
        try:
            plans = self._deletion_plans(refs)
            done = [self._delete_one(actor, plan) for plan in plans]
            return self._told_plex(done)
        finally:
            release_lock(lock_file)

    def _deletion_plans(self, refs: Sequence[MediaRef]) -> list[_DeletionPlan]:
        """Validate every reference and name what each deletion touches; refuse before anything goes.

        Args:
            refs: The media asked.

        Returns:
            One plan per distinct medium, in request order.

        Raises:
            AppNotFound: ``media.not_found`` when no row holds an id.
            AppConflict: ``media.ambiguous`` when an id is held more than once.
        """
        plans: list[_DeletionPlan] = []
        seen: set[tuple[Provider, str]] = set()
        with closing(self._connect()) as conn:
            for ref in refs:
                key = ref_key(ref)
                if key in seen:
                    continue
                seen.add(key)
                provider, provider_id = key
                params = {"provider": provider.value, "providerId": provider_id}
                holders, folders = self._held(conn, ref)
                if not holders:
                    raise AppNotFound("No library row holds this id.", code=RefusalCode.MEDIA_NOT_FOUND, params=params)
                holdings = sum(max(1, len(folders.get(row.item_id, ()))) for row in holders)
                if holdings > 1:
                    raise AppConflict(
                        "Several library rows or folders hold this id.", code=RefusalCode.MEDIA_AMBIGUOUS, params=params
                    )
                [row] = holders
                mounted = mounted_media_folders(conn, row.item_id)
                targets = {
                    resolved[1]: resolved for resolved in map(_deletable_folder, mounted) if resolved is not None
                }
                unresolved = sum(1 for resolved in map(_deletable_folder, mounted) if resolved is None)
                plans.append(
                    _DeletionPlan(
                        ref=ref,
                        item_id=row.item_id,
                        targets=tuple(targets.values()),
                        unresolved=unresolved,
                        unreachable=max(0, len(folders.get(row.item_id, ())) - len(mounted)),
                    )
                )
        return plans

    def _delete_one(self, actor: Actor, plan: _DeletionPlan) -> _Deleted:
        """Delete one validated medium's folder, its emptied parents and, when nothing was kept, its rows.

        Args:
            actor: Who deletes.
            plan: What the medium's deletion touches.

        Returns:
            What was done, and the surviving parent of each deleted folder (for Plex).
        """
        who = f"web:{actor.account_id}"
        provider, provider_id = ref_key(plan.ref)
        deleted = vetoed = parents_removed = 0
        failed = plan.unresolved
        if plan.unresolved:
            log.warning("app.library.delete_folder_unresolved", provider=provider.value, item_id=plan.item_id)
        survivors: list[Path] = []
        for root, directory in plan.targets:
            try:
                result = delete_media_folder(
                    directory,
                    db_path=self._index_db,
                    actor=who,
                    label=f"media {provider.value}/{provider_id}",
                    permit=self._delete_permit,
                    config=self._config,
                )
            except PreprodGuardError as exc:
                log.warning("app.library.delete_preprod_refused", item_id=plan.item_id, error=str(exc))
                failed += 1
                continue
            if result.outcome is DeleteOutcome.VETOED:
                vetoed += 1
            elif result.outcome is DeleteOutcome.FAILED:
                failed += 1
            else:
                deleted += 1
                removed, survivor = remove_empty_parents(directory, root)
                parents_removed += removed
                survivors.append(survivor)
        unreachable = plan.unreachable
        rows = 0
        if vetoed + failed + unreachable == 0:
            rows = remove_item_rows(self._index_db, [plan.item_id], actor=who)
        log.info(
            "app.library.media_deleted",
            provider=provider.value,
            item_id=plan.item_id,
            folders_deleted=deleted,
            folders_vetoed=vetoed,
            folders_failed=failed,
            folders_unreachable=unreachable,
            rows_removed=rows,
        )
        return _Deleted(
            MediaDeletion(
                ref=plan.ref,
                folders_deleted=deleted,
                folders_vetoed=vetoed,
                folders_failed=failed,
                folders_unreachable=unreachable,
                parents_removed=parents_removed,
                rows_removed=rows,
                plex=PlexOutcome.NOT_NEEDED,
            ),
            tuple(survivors),
        )

    def _told_plex(self, done: Sequence[_Deleted]) -> DeletionReport:
        """Tell Plex of every deleted folder at once, and fold its steps into each medium's report.

        Args:
            done: Each medium's deletion and the surviving parents of its deleted folders.

        Returns:
            The request's report.
        """
        parents = [parent for one in done for parent in one.survivors]
        steps = (
            follow_up_plex(self._plex, parents, sleep=self._sleep, clock=self._monotonic)
            if self._plex is not None and parents
            else {}
        )
        media: list[MediaDeletion] = []
        for one in done:
            report = one.deletion
            if one.survivors and self._plex is None:
                report = replace(report, plex=PlexOutcome.NOT_CONFIGURED)
            elif one.survivors:
                mine = [steps[parent] for parent in one.survivors]
                failed = next((step for step in mine if step.outcome is PlexOutcome.FAILED), None)
                chosen = failed if failed is not None else mine[0]
                report = replace(report, plex=chosen.outcome, plex_steps=chosen)
            media.append(report)
        return DeletionReport(deleted=sum(1 for one in media if one.deleted), media=tuple(media))

    # ------------------------------------------------------------------ the sheet's parts

    def _provider_for(self, ref: MediaRef, held: IndexRow | None) -> tuple[str, str]:
        """Choose the provider and id a sheet is read at.

        TVDB and TMDB ids are read where the wire names them. An IMDb id is read at the held
        row's TVDB id for a show or TMDB id for a movie (then the other one).

        Args:
            ref: The medium.
            held: The live row holding it, or ``None``.

        Returns:
            ``(provider, id as text)``.

        Raises:
            AppNotFound: ``media.not_found`` for an IMDb id no live row resolves.
        """
        provider, provider_id = ref_key(ref)
        if provider is not Provider.IMDB:
            return provider.value, provider_id
        if held is not None:
            order = ("tvdb", "tmdb") if held.kind == "show" else ("tmdb", "tvdb")
            for name in order:
                if name in held.ids:
                    return name, str(held.ids[name])
        raise refuse_not_found(Provider.IMDB.value)

    def _provider_sheet(self, provider: str, provider_id: str, kind: Literal["movie", "show"] | None) -> ProviderSheet:
        """Read a provider's answer, through the five-minute cache.

        A TVDB show is crossed with TMDB through its TMDB id for what TVDB does not give:
        the creator when it names none (operator ruling 2026-08-04), the trailer and the
        rating (TVDB has neither, and the interface opens a show at TVDB first). Fail-soft:
        a failed cross leaves those facts unknown and the sheet answers from TVDB alone.

        Args:
            provider: ``"tvdb"`` or ``"tmdb"``.
            provider_id: The id at that provider.
            kind: The medium's kind when the library knows it.

        Returns:
            The answer.
        """
        cached = self._sheets.get((provider, provider_id))
        if cached is not None and (kind is None or cached.kind == kind):
            return cached
        details, answered = fetch_details(self._providers.get(provider), provider, provider_id, kind)
        creator = details.creator
        tmdb_id = details.external_ids.get("tmdb", "").strip()
        tmdb = self._providers.tmdb
        lacking = not creator or not details.trailer_url or details.rating is None
        if answered == "show" and lacking and provider == "tvdb" and tmdb_id not in ("", "0"):
            if isinstance(tmdb, SheetClient):
                try:
                    crossed = tmdb.get_tv(tmdb_id)
                except Exception as exc:  # noqa: BLE001 — fail-soft: the crossed facts stay unknown
                    log.debug("app.library.creator_cross_failed", tmdb_id=tmdb_id, error=str(exc))
                else:
                    creator = creator or crossed.creator
                    details = _crossed_trailer_and_rating(details, crossed)
        answer = ProviderSheet(details=details, kind=answered, creator=creator)
        self._sheets.put((provider, provider_id), answer)
        return answer

    @staticmethod
    def _episode_facts(episodes: Sequence[CatalogueEpisode] | None) -> dict[int, tuple[EpisodeFact, ...]] | None:
        """Group the catalogue's episodes by season for the sheet.

        Args:
            episodes: The show's catalogue, or ``None`` when never fetched.

        Returns:
            ``{season: episodes}``, or ``None`` when the catalogue is unknown.
        """
        if episodes is None:
            return None
        grouped: dict[int, list[EpisodeFact]] = {}
        for ep in episodes:
            grouped.setdefault(ep.season, []).append(EpisodeFact(ep.episode, ep.title, ep.air_date))
        return {season: tuple(grouped[season]) for season in sorted(grouped)}

    @staticmethod
    def _season_summaries(
        details: MediaDetails, episodes: Sequence[CatalogueEpisode] | None
    ) -> tuple[SeasonSummaryFact, ...]:
        """List a show's seasons as the provider knows them.

        Args:
            details: The provider's details (its ``seasons``).
            episodes: The show's catalogue, for each season's first air date, or ``None``.

        Returns:
            One summary per provider season; a count of 0 reads « not said ».
        """
        first: dict[int, date] = {}
        for ep in episodes or []:
            if ep.air_date is not None and (ep.season not in first or ep.air_date < first[ep.season]):
                first[ep.season] = ep.air_date
        return tuple(
            SeasonSummaryFact(
                number=season.season_number,
                episodes=season.episode_count or None,
                air_date=first.get(season.season_number),
            )
            for season in sorted(details.seasons, key=lambda s: s.season_number)
        )


def _crossed_trailer_and_rating(details: MediaDetails, crossed: MediaDetails) -> MediaDetails:
    """Fill a TVDB answer's missing trailer and rating from the TMDB answer for the same show.

    The trailer travels whole (URL, name, language) so its parts never mix two providers.

    Args:
        details: TVDB's answer.
        crossed: TMDB's answer for the same show.

    Returns:
        TVDB's answer with TMDB's trailer when TVDB has none, and TMDB's rating when TVDB
        has none.
    """
    trailer = details if details.trailer_url else crossed
    return replace(
        details,
        trailer_url=trailer.trailer_url,
        trailer_name=trailer.trailer_name,
        trailer_language=trailer.trailer_language,
        rating=details.rating if details.rating is not None else crossed.rating,
    )
