"""The library as the v1 application reads it: one read-only view over ``library.db``.

The application never opens ``library.db`` itself: :class:`LibraryIndex` opens a reader
(read-only at the file and at the connection), and :class:`LibraryReader` answers every
question the library and media reads ask — a page of the listing, the categories, the
recent strip, the holders of a provider id, their folders and episodes, the disks.

A row is LIVE when at least one of its files is not tombstoned, and IDENTIFIED when it
carries at least one provider id: the listings serve only rows that are both (a row with
no id is repaired upstream, never served unidentified).

A page is filtered, ordered, counted and cut in SQL. The French collation and the
accent-insensitive search are derived keys SQLite cannot compute, so the reader registers
them on its connection: ``tm_fold(text)`` (:func:`fold`), ``tm_has_ids(json)`` (the
« identified » rule, :func:`parse_ids`) and the collation ``tm_french``
(:func:`french_key`). The « missing » order crosses ``acquire.db``: it stays in the
application, over :meth:`LibraryReader.live_items`.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import ContextManager, Final, Literal

from personalscraper.core.identity import ItemId, MediaRef

__all__ = [
    "LIBRARY_PAGE_SIZE",
    "MEDIA_FOLDER_DEPTH",
    "IndexItem",
    "IndexUnavailable",
    "LibraryIndex",
    "LibraryReader",
    "ListingOrder",
    "ListingPage",
    "folder_holders",
    "fold",
    "french_key",
    "live_episode_pairs",
    "live_folders",
    "matches",
    "mounted_media_folders",
    "parse_ids",
    "read_holders",
]

#: Rows one page of the listing carries (the maquette's page size).
LIBRARY_PAGE_SIZE: Final[int] = 24

# How long a read waits on a writer's checkpoint before failing (the canonical set's value).
_BUSY_TIMEOUT_MS: Final[int] = 5000

# Placeholder ids historical scrapes leaked into NFOs; they name no medium.
_PLACEHOLDER_IDS: Final[frozenset[str]] = frozenset({"", "0", "none"})

# The order a row's ids are written in: TVDB first for a show, TMDB for a movie,
# IMDb last — the order the wire's ``ids`` object is read in.
_ID_PROVIDERS: Final[tuple[str, ...]] = ("tvdb", "tmdb", "imdb")

# Ligatures French titles carry that Unicode decomposition does not split.
_LIGATURES: Final[Mapping[str, str]] = {"œ": "oe", "æ": "ae"}

# Whether a row has a live file: a movie through its release, a show through
# season → episode → release (the paths ``indexer/ownership.py`` reads).
_LIVE_SQL: Final[str] = (
    "(EXISTS (SELECT 1 FROM media_release r JOIN media_file f ON f.release_id = r.id"
    " WHERE r.item_id = m.id AND f.deleted_at IS NULL)"
    " OR EXISTS (SELECT 1 FROM season s JOIN episode e ON e.season_id = s.id"
    " JOIN media_release r ON r.episode_id = e.id JOIN media_file f ON f.release_id = r.id"
    " WHERE s.item_id = m.id AND f.deleted_at IS NULL))"
)

# A row the listings serve: live and identified (``tm_has_ids`` is registered by the reader).
_LISTED_SQL: Final[str] = f"{_LIVE_SQL} AND tm_has_ids(m.external_ids_json)"

_COLUMNS: Final[str] = (
    "m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, m.overview,"
    " m.external_ids_json, m.canonical_provider, m.poster_url, m.artwork_json, m.date_created, m.date_provider_read"
)

# The sort title as :class:`IndexItem` reads it: the title when the sort title is empty.
_SORT_TITLE_SQL: Final[str] = "COALESCE(NULLIF(m.title_sort, ''), m.title)"

# Every live file of the given items, with the disk and directory it lies in
# (movie releases and episode releases alike).
_LIVE_FOLDERS_SQL: Final[str] = (
    "SELECT r.item_id, f.path_id FROM media_file f JOIN media_release r ON r.id = f.release_id"
    " WHERE f.deleted_at IS NULL AND r.item_id IN ({ids})"
    " UNION ALL"
    " SELECT s.item_id, f.path_id FROM media_file f JOIN media_release r ON r.id = f.release_id"
    " JOIN episode e ON e.id = r.episode_id JOIN season s ON s.id = e.season_id"
    " WHERE f.deleted_at IS NULL AND s.item_id IN ({ids})"
)

# Every item's live files, whatever the item: the rule of ``_LIVE_FOLDERS_SQL`` over the
# whole index (a release of an episode holds no ``item_id`` of its own).
_ALL_LIVE_FOLDERS_SQL: Final[str] = (
    "SELECT r.item_id AS item_id, f.path_id AS path_id FROM media_file f"
    " JOIN media_release r ON r.id = f.release_id WHERE f.deleted_at IS NULL AND r.item_id IS NOT NULL"
    " UNION ALL"
    " SELECT s.item_id, f.path_id FROM media_file f JOIN media_release r ON r.id = f.release_id"
    " JOIN episode e ON e.id = r.episode_id JOIN season s ON s.id = e.season_id"
    " WHERE f.deleted_at IS NULL"
)

#: A disk holds ``<category folder>/<media folder>[/<sub folder>]``: the media folder
#: is the directory's first two segments (as ``indexer/duplicates.py`` reads it).
MEDIA_FOLDER_DEPTH: Final[int] = 2

# Path segments that name no folder of their own: a media folder spelt with one of them is
# not one.
_NOT_A_NAME: Final[frozenset[str]] = frozenset({"", ".", ".."})

# Every live (season, episode) pair of every show row, a multi-episode file owning its
# whole span — the rule of ``indexer/ownership.py``'s ``_OWNED_PAIRS_TMPL``, read for the
# whole library in one query instead of one per show and provider id.
_LIVE_PAIRS_SQL: Final[str] = (
    "SELECT DISTINCT s.item_id, s.number, e2.number FROM season s"
    " JOIN episode e ON e.season_id = s.id"
    " JOIN media_release mr ON mr.episode_id = e.id"
    " LEFT JOIN episode ee ON ee.id = mr.episode_end_id"
    " JOIN episode e2 ON e2.season_id = s.id"
    " AND e2.number BETWEEN e.number AND COALESCE(ee.number, e.number)"
    " JOIN media_file mf ON mf.release_id = mr.id"
    " WHERE mf.deleted_at IS NULL"
)


class IndexUnavailable(Exception):
    """library.db is absent, unopenable or not a database."""


class ListingOrder(StrEnum):
    """The listing's orders SQL computes, by their wire values."""

    RECENT = "recent"
    AZ = "az"


@dataclass(frozen=True)
class IndexItem:
    """One ``media_item`` row, as the library's reads use it.

    Attributes:
        item_id: ``media_item.id``.
        kind: ``"movie"`` or ``"show"``.
        title: The stored title.
        title_sort: The sort title (French articles stripped).
        original_title: The original-language title, or ``None``.
        year: The year, or ``None``.
        category_id: The engine's leaf category id.
        overview: The NFO's synopsis, or ``None``.
        ids: The provider ids, TVDB/TMDB as integers, IMDb as text; placeholders dropped.
        canonical_provider: The provider that drove the canonical scrape, or ``None``.
        poster_url: The provider poster URL the NFO names, or ``None``.
        has_local_poster: Whether the artwork inventory saw a poster file in the folder.
        date_created: When the row entered the index, epoch seconds.
        date_provider_read: When the provider data was last read (the NFO's mtime), or ``None``.
    """

    item_id: ItemId
    kind: Literal["movie", "show"]
    title: str
    title_sort: str
    original_title: str | None
    year: int | None
    category_id: str
    overview: str | None
    ids: Mapping[str, int | str]
    canonical_provider: str | None
    poster_url: str | None
    has_local_poster: bool
    date_created: int
    date_provider_read: float | None

    @property
    def local_poster(self) -> bool:
        """Whether the poster to show is the folder's own: none from the provider, one on disk."""
        return self.poster_url is None and self.has_local_poster

    def media_ref(self) -> MediaRef | None:
        """The row's ids as a :class:`MediaRef`, or ``None`` when it carries none."""
        if not self.ids:
            return None
        tvdb, tmdb, imdb = self.ids.get("tvdb"), self.ids.get("tmdb"), self.ids.get("imdb")
        return MediaRef(
            tvdb_id=tvdb if isinstance(tvdb, int) else None,
            tmdb_id=tmdb if isinstance(tmdb, int) else None,
            imdb_id=imdb if isinstance(imdb, str) else None,
        )


@dataclass(frozen=True)
class ListingPage:
    """One page of the listing, with its three counts.

    Attributes:
        items: The page's rows.
        total: The library's count when nothing filters, else ``matching``.
        matching: How many rows the question matches — what the page is a page of.
        loaded: How many rows the library holds, whatever is filtered.
    """

    items: tuple[IndexItem, ...]
    total: int
    matching: int
    loaded: int


def parse_ids(external_ids_json: str | None) -> dict[str, int | str]:
    """Map a row's ``external_ids_json`` to the wire's ids.

    Args:
        external_ids_json: ``{"tvdb": {"series_id": "391101", …}, …}``.

    Returns:
        ``{"tvdb": 391101, "tmdb": 113985, "imdb": "tt11685912"}`` in that order, without
        placeholders, malformed values or absent providers.
    """
    try:
        raw = json.loads(external_ids_json or "{}")
    except json.JSONDecodeError:
        return {}
    ids: dict[str, int | str] = {}
    if not isinstance(raw, dict):
        return ids
    for provider in _ID_PROVIDERS:
        entry = raw.get(provider)
        value = entry.get("series_id") if isinstance(entry, dict) else None
        if value is None or str(value).strip().lower() in _PLACEHOLDER_IDS:
            continue
        text = str(value).strip()
        if provider == "imdb":
            ids[provider] = text
        elif text.isdigit():
            ids[provider] = int(text)
    return ids


def _has_poster(artwork_json: str | None) -> bool:
    """Read the poster flag of an ``artwork_json`` inventory.

    Args:
        artwork_json: ``{"poster": true, …}`` or ``None``.

    Returns:
        Whether a poster file was seen.
    """
    try:
        inventory = json.loads(artwork_json or "{}")
    except json.JSONDecodeError:
        return False
    return isinstance(inventory, dict) and inventory.get("poster") is True


def _to_item(raw: sqlite3.Row) -> IndexItem:
    """Build an :class:`IndexItem` from a ``_COLUMNS`` row.

    Args:
        raw: The row, read with ``sqlite3.Row`` as its factory.

    Returns:
        The item.
    """
    read = raw["date_provider_read"]
    return IndexItem(
        item_id=ItemId(raw["id"]),
        kind="show" if raw["kind"] == "show" else "movie",
        title=raw["title"],
        title_sort=raw["title_sort"] or raw["title"],
        original_title=raw["original_title"],
        year=raw["year"],
        category_id=raw["category_id"],
        overview=raw["overview"] or None,
        ids=parse_ids(raw["external_ids_json"]),
        canonical_provider=raw["canonical_provider"],
        poster_url=raw["poster_url"] or None,
        has_local_poster=_has_poster(raw["artwork_json"]),
        date_created=raw["date_created"],
        date_provider_read=float(read) if read is not None else None,
    )


def read_holders(conn: sqlite3.Connection, provider: str, provider_id: str) -> list[IndexItem]:
    """Read every row, live or not, carrying one provider id, of the one kind the id names.

    TMDB's movie and TV id spaces are distinct, so one number can be held by a film and by
    a show; they are no duplicate of each other (the ``(kind, provider, id)`` grouping of
    ``indexer/duplicates.py``). A TVDB id names a show; a TMDB or an IMDb id names the movie
    holders when any exist, else the show holders.

    Args:
        conn: An open connection to ``library.db``, with ``sqlite3.Row`` as its row factory.
        provider: ``"tvdb"``, ``"tmdb"`` or ``"imdb"``.
        provider_id: The id at that provider, as text.

    Returns:
        The holding rows of that kind, by ``id``.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM media_item m"
        f" WHERE CAST(json_extract(m.external_ids_json, '$.{provider}.series_id') AS TEXT) = ?"
        " ORDER BY m.id",
        (provider_id,),
    ).fetchall()
    holders = [_to_item(row) for row in rows]
    shows = [row for row in holders if row.kind == "show"]
    if provider == "tvdb":
        return shows
    return [row for row in holders if row.kind == "movie"] or shows


def live_folders(conn: sqlite3.Connection, item_ids: Sequence[ItemId]) -> dict[ItemId, set[str]]:
    """Name the distinct media folders holding each item's live files.

    Args:
        conn: An open connection to ``library.db``.
        item_ids: The ``media_item`` ids asked about.

    Returns:
        ``{item_id: {"<disk id>:<category>/<media folder>", …}}`` for the items with live
        files (NFC names: macOS lists in NFD, the index may hold both).
    """
    if not item_ids:
        return {}
    marks = ", ".join("?" for _ in item_ids)
    query = (
        "SELECT x.item_id, p.disk_id, p.rel_path FROM (" + _LIVE_FOLDERS_SQL.format(ids=marks) + ") x"
        " JOIN path p ON p.id = x.path_id"
    )
    folders: dict[ItemId, set[str]] = {}
    for item_id, disk_id, rel_path in conn.execute(query, [*item_ids, *item_ids]):
        parts = unicodedata.normalize("NFC", rel_path).strip("/").split("/")
        folders.setdefault(item_id, set()).add(f"{disk_id}:{'/'.join(parts[:MEDIA_FOLDER_DEPTH])}")
    return folders


def folder_holders(conn: sqlite3.Connection, folders: Iterable[str]) -> dict[str, set[ItemId]]:
    """Name every item holding live files in some media folders, on the disks the index says are mounted.

    Args:
        conn: An open connection to ``library.db``.
        folders: Media folders as :func:`live_folders` names them
            (``"<disk id>:<category>/<media folder>"``, NFC).

    Returns:
        ``{folder: {item_id, …}}`` for the folders some item holds live files in (a file in
        a sub folder counts for its media folder); a folder on an unmounted disk holds none.
    """
    wanted = set(folders)
    disks = sorted({int(folder.split(":", 1)[0]) for folder in wanted})
    if not disks:
        return {}
    marks = ", ".join("?" for _ in disks)
    query = (
        "SELECT DISTINCT x.item_id, p.disk_id, p.rel_path FROM (" + _ALL_LIVE_FOLDERS_SQL + ") x"
        " JOIN path p ON p.id = x.path_id JOIN disk d ON d.id = p.disk_id"
        f" WHERE d.is_mounted = 1 AND p.disk_id IN ({marks})"
    )
    holders: dict[str, set[ItemId]] = {}
    for item_id, disk_id, rel_path in conn.execute(query, disks):
        parts = unicodedata.normalize("NFC", rel_path).strip("/").split("/")
        folder = f"{disk_id}:{'/'.join(parts[:MEDIA_FOLDER_DEPTH])}"
        if folder in wanted:
            holders.setdefault(folder, set()).add(item_id)
    return holders


def mounted_media_folders(conn: sqlite3.Connection, item_id: ItemId) -> list[tuple[str, str]]:
    """Name the media folders holding one item's live files on the disks the index says are mounted.

    Args:
        conn: An open connection to ``library.db``.
        item_id: The ``media_item`` id asked about.

    Returns:
        ``[(mount path, "<category>/<media folder>"), …]``, distinct and sorted; the folder is
        the index's own spelling, to be joined to the mount path as it stands. A path that
        does not name a media folder (fewer segments than ``MEDIA_FOLDER_DEPTH``, or an
        empty, ``.`` or ``..`` one among them) holds none: it would name a category or the
        disk itself.
    """
    query = (
        "SELECT DISTINCT d.mount_path, p.rel_path FROM (" + _LIVE_FOLDERS_SQL.format(ids="?") + ") x"
        " JOIN path p ON p.id = x.path_id JOIN disk d ON d.id = p.disk_id"
        " WHERE d.is_mounted = 1 AND d.mount_path IS NOT NULL"
    )
    folders: set[tuple[str, str]] = set()
    for mount_path, rel_path in conn.execute(query, (item_id, item_id)):
        segments = rel_path.strip("/").split("/")[:MEDIA_FOLDER_DEPTH]
        if len(segments) == MEDIA_FOLDER_DEPTH and not any(part in _NOT_A_NAME for part in segments):
            folders.add((mount_path, "/".join(segments)))
    return sorted(folders)


def live_episode_pairs(conn: sqlite3.Connection) -> dict[ItemId, set[tuple[int, int]]]:
    """Read the held ``(season, episode)`` pairs of every show row at once.

    Args:
        conn: An open connection to ``library.db``.

    Returns:
        ``{item_id: pairs}`` for the show rows holding at least one live episode.
    """
    pairs: dict[ItemId, set[tuple[int, int]]] = {}
    for item_id, season, episode in conn.execute(_LIVE_PAIRS_SQL):
        pairs.setdefault(item_id, set()).add((int(season), int(episode)))
    return pairs


def fold(text: str) -> str:
    """Fold a title for comparison: accents and case dropped, ligatures spelt out.

    Args:
        text: Any title, NFC or NFD.

    Returns:
        The folded text (« Élite » → « elite », « Œdipe » → « oedipe »).
    """
    decomposed = unicodedata.normalize("NFD", text)
    bare = "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()
    return "".join(_LIGATURES.get(char, char) for char in bare)


def french_key(title: str) -> tuple[str, str]:
    """The French collation key of a title, without ``locale``.

    The primary level ignores accents and case (« Élite » sorts between « Eagle » and
    « Eternals »); the secondary level puts the unaccented spelling first (« cote »
    before « côte »).

    Args:
        title: The title to order.

    Returns:
        ``(folded, NFC casefolded)``.
    """
    return fold(title), unicodedata.normalize("NFC", title).casefold()


def matches(item: IndexItem, query: str) -> bool:
    """Whether an item's title or original title contains the question, ignoring accents and case.

    Args:
        item: The item.
        query: The search text; blank matches every item.

    Returns:
        Whether it matches.
    """
    wanted = fold(query.strip())
    if not wanted:
        return True
    return wanted in fold(item.title) or (item.original_title is not None and wanted in fold(item.original_title))


def _tm_fold(text: str | None) -> str | None:
    """SQL ``tm_fold(text)``: :func:`fold`, ``NULL`` kept.

    Args:
        text: The column value.

    Returns:
        The folded text, or ``None`` for ``NULL``.
    """
    return fold(text) if text is not None else None


def _tm_has_ids(external_ids_json: str | None) -> int:
    """SQL ``tm_has_ids(json)``: whether the row carries a provider id :func:`parse_ids` keeps.

    Args:
        external_ids_json: ``media_item.external_ids_json``.

    Returns:
        ``1`` when it does, ``0`` otherwise.
    """
    return int(bool(parse_ids(external_ids_json)))


class LibraryReader:
    """One read-only connection to ``library.db``, and the questions the library asks of it.

    A context manager: leaving it closes the connection.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Take an open read-only connection and register the listing's functions on it.

        Args:
            conn: The connection, ``sqlite3.Row`` as its row factory.
        """
        self._conn = conn
        # The collation is called O(n log n) times on a page in ``AZ``: each title's key is
        # computed once per reader.
        keys: dict[str, tuple[str, str]] = {}

        def collate(left: str, right: str) -> int:
            """SQL collation ``tm_french``: compare :func:`french_key`.

            Args:
                left: One sort title.
                right: The other.

            Returns:
                Negative, zero or positive as ``left`` sorts before, with or after ``right``.
            """
            a = keys.get(left) or keys.setdefault(left, french_key(left))
            b = keys.get(right) or keys.setdefault(right, french_key(right))
            return (a > b) - (a < b)

        conn.create_function("tm_fold", 1, _tm_fold, deterministic=True)
        conn.create_function("tm_has_ids", 1, _tm_has_ids, deterministic=True)
        conn.create_collation("tm_french", collate)

    def __enter__(self) -> LibraryReader:
        """Hand the reader out.

        Returns:
            This reader.
        """
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        """Close the connection.

        Args:
            exc_type: The exception's type, if the block raised.
            exc: The exception, if the block raised.
            tb: Its traceback, if the block raised.
        """
        self._conn.close()

    def page(
        self,
        *,
        categories: frozenset[str],
        query: str | None,
        order: ListingOrder,
        reversed_: bool,
        page: int,
        size: int = LIBRARY_PAGE_SIZE,
    ) -> ListingPage:
        """Read one page of the live, identified rows, filtered, ordered and counted in SQL.

        ``RECENT`` is the most recently added first (``date_created``, then ``id``,
        descending); ``AZ`` is the French collation of the sort title, ties in the recent
        order. Reversing flips every key's direction: the whole order read backwards.

        Args:
            categories: The leaf categories to keep; empty keeps every one.
            query: The search text, matched in the title and the original title ignoring
                accents and case; ``None`` or blank matches every row.
            order: The order.
            reversed_: Whether to read it the other way round.
            page: The page, zero based; a page past the end is empty.
            size: Rows per page.

        Returns:
            The page and its three counts.

        Raises:
            ValueError: On a negative page or a size below one.
        """
        if page < 0 or size < 1:
            raise ValueError(f"page {page} of size {size} names no page")
        clauses: list[str] = []
        params: list[str] = []
        if categories:
            clauses.append(f"m.category_id IN ({', '.join('?' for _ in categories)})")
            params.extend(sorted(categories))
        wanted = fold(query.strip()) if query is not None else ""
        if wanted:
            clauses.append(
                "(instr(tm_fold(m.title), ?) > 0"
                " OR (m.original_title IS NOT NULL AND instr(tm_fold(m.original_title), ?) > 0))"
            )
            params.extend((wanted, wanted))
        selected = " AND ".join(clauses) or "1"
        down, up = ("ASC", "DESC") if reversed_ else ("DESC", "ASC")
        recent = f"m.date_created {down}, m.id {down}"
        keys = recent if order is ListingOrder.RECENT else f"{_SORT_TITLE_SQL} COLLATE tm_french {up}, {recent}"
        # One read transaction: the counts and the page see the same snapshot even if a
        # writer commits between the two statements.
        self._conn.execute("BEGIN")
        try:
            loaded, matching = self._conn.execute(
                f"SELECT COUNT(*), COALESCE(SUM({selected}), 0) FROM media_item m WHERE {_LISTED_SQL}", params
            ).fetchone()
            # A page past the end is empty; checked before binding, as an offset beyond
            # SQLite's 64-bit integer would raise ``OverflowError``.
            rows = (
                []
                if page * size >= matching
                else self._conn.execute(
                    f"SELECT {_COLUMNS} FROM media_item m WHERE {_LISTED_SQL} AND {selected}"
                    f" ORDER BY {keys} LIMIT ? OFFSET ?",
                    [*params, size, page * size],
                ).fetchall()
            )
        finally:
            if self._conn.in_transaction:
                self._conn.execute("COMMIT")
        filtered = bool(categories) or bool(query and query.strip())
        return ListingPage(
            items=tuple(_to_item(row) for row in rows),
            total=matching if filtered else loaded,
            matching=matching,
            loaded=loaded,
        )

    def live_items(self) -> list[IndexItem]:
        """Read every live, identified row, the most recently added first.

        Only the orders that cross ``acquire.db`` (« missing », the incomplete list) read
        the whole library this way; a page is :meth:`page`.

        Returns:
            The rows ordered by ``date_created`` descending, then ``id`` descending.
        """
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM media_item m WHERE {_LISTED_SQL} ORDER BY m.date_created DESC, m.id DESC"
        ).fetchall()
        return [_to_item(row) for row in rows]

    def category_counts(self) -> dict[str, int]:
        """Count the live, identified rows of each leaf category.

        Returns:
            ``{category_id: count}`` for the categories holding at least one row.
        """
        return dict(
            self._conn.execute(
                f"SELECT m.category_id, COUNT(*) FROM media_item m WHERE {_LISTED_SQL} GROUP BY m.category_id"
            ).fetchall()
        )

    def recent(self, limit: int) -> list[IndexItem]:
        """Read the most recently added live, identified rows.

        Args:
            limit: How many.

        Returns:
            At most ``limit`` rows, newest first.
        """
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM media_item m WHERE {_LISTED_SQL} ORDER BY m.date_created DESC, m.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_to_item(row) for row in rows]

    def holders(self, provider: str, provider_id: str) -> list[IndexItem]:
        """Every row, live or not, carrying one provider id (:func:`read_holders`).

        Args:
            provider: ``"tvdb"``, ``"tmdb"`` or ``"imdb"``.
            provider_id: The id at that provider, as text.

        Returns:
            The holding rows of the kind the id names, by ``id``.
        """
        return read_holders(self._conn, provider, provider_id)

    def live_folders(self, item_ids: Sequence[ItemId]) -> dict[ItemId, set[str]]:
        """The media folders of each item's live files (:func:`live_folders`).

        Args:
            item_ids: The ``media_item`` ids asked about.

        Returns:
            ``{item_id: {"<disk id>:<category>/<media folder>", …}}`` for the items with live files.
        """
        return live_folders(self._conn, item_ids)

    def folder_holders(self, folders: Iterable[str]) -> dict[str, set[ItemId]]:
        """Every item holding live files in some media folders (:func:`folder_holders`).

        Args:
            folders: Media folders as :meth:`live_folders` names them.

        Returns:
            ``{folder: {item_id, …}}`` for the folders some item holds live files in.
        """
        return folder_holders(self._conn, folders)

    def mounted_media_folders(self, item_id: ItemId) -> list[tuple[str, str]]:
        """One item's media folders on mounted disks (:func:`mounted_media_folders`).

        Args:
            item_id: The ``media_item`` id asked about.

        Returns:
            ``[(mount path, "<category>/<media folder>"), …]``, distinct and sorted.
        """
        return mounted_media_folders(self._conn, item_id)

    def live_episode_pairs(self) -> dict[ItemId, set[tuple[int, int]]]:
        """The held ``(season, episode)`` pairs of every show row (:func:`live_episode_pairs`).

        Returns:
            ``{item_id: pairs}`` for the show rows holding at least one live episode.
        """
        return live_episode_pairs(self._conn)

    def any_disk_unmounted(self) -> bool:
        """Whether a disk the index knows is not mounted (``disk.is_mounted = 0``).

        Returns:
            Whether one is.
        """
        return self._conn.execute("SELECT 1 FROM disk WHERE is_mounted = 0 LIMIT 1").fetchone() is not None

    def run_outcome(self, run_uid: str) -> str | None:
        """The outcome of one run's ``pipeline_run`` row.

        Args:
            run_uid: The run's uid.

        Returns:
            Its ``outcome`` (``'running'`` while unfinished); ``None`` when no row has that uid.
        """
        row = self._conn.execute("SELECT outcome FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
        return None if row is None else str(row["outcome"])


class LibraryIndex:
    """``library.db``, opened read-only for each read (a WAL read takes no lock)."""

    def __init__(self, db_path: Path) -> None:
        """Name the index; nothing is opened yet.

        Args:
            db_path: Path of ``library.db``.
        """
        self._db_path = db_path

    def reader(self) -> ContextManager[LibraryReader]:
        """Open a reader, at once, to be used as a context manager that closes it.

        Read-only at the file (``mode=ro``: an absent index is an error, never a new empty
        file) and at the connection (``query_only``). The core table is read once before the
        reader is handed out, so a file that is not a database is refused here rather than
        by the first query.

        Returns:
            The reader; its connection can take no writer lock.

        Raises:
            IndexUnavailable: When ``library.db`` is absent, cannot be opened or is not a
                database; the ``sqlite3.Error`` is its cause.
        """
        uri = f"{self._db_path.resolve().as_uri()}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True, isolation_level=None, check_same_thread=False)
        except sqlite3.Error as exc:
            raise IndexUnavailable(str(exc)) from exc
        try:
            # Not the canonical writer PRAGMA set: WAL ``journal_mode`` raises on a read-only
            # connection (scripts/check-pragma-discipline.py allow-lists this reader).
            conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
            conn.execute("PRAGMA query_only=ON")
            # The core table, not ``sqlite_master``: a 0-byte or schema-less file opens and passes
            # that, and the first real query then dies on « no such table ».
            conn.execute("SELECT 1 FROM media_item LIMIT 1").fetchone()
        except sqlite3.Error as exc:
            conn.close()
            raise IndexUnavailable(str(exc)) from exc
        conn.row_factory = sqlite3.Row
        return LibraryReader(conn)
