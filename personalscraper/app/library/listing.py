"""The library's rows, read from the index, and the pure functions that filter, order and page them.

A row is LIVE when at least one of its files is not tombstoned, and IDENTIFIED when
it carries at least one provider id: the listings serve only rows that are both (a
row with no id is repaired upstream, never served unidentified).

The whole live library is read in one query (1 898 rows measured in production) and
filtered, ordered and paged in Python: the French collation, the accent-insensitive
search and the « missing » order are all derived keys SQLite cannot compute.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

from personalscraper.core.identity import MediaRef

#: Rows one page of the listing carries (the maquette's page size).
LIBRARY_PAGE_SIZE: Final[int] = 24

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

_COLUMNS: Final[str] = (
    "m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, m.overview,"
    " m.external_ids_json, m.canonical_provider, m.poster_url, m.artwork_json, m.date_created, m.date_provider_read"
)

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

# A disk holds ``<category folder>/<media folder>[/<sub folder>]``: the media folder
# is the directory's first two segments (as ``indexer/duplicates.py`` reads it).
_MEDIA_FOLDER_DEPTH: Final[int] = 2


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


class LibrarySort(StrEnum):
    """The listing's orders, by their wire values; ``RECENT`` is the order an absent ``sort`` asks for."""

    RECENT = "recent"
    AZ = "az"
    MISSING = "missing"


@dataclass(frozen=True)
class IndexRow:
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

    item_id: int
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


def _to_row(raw: sqlite3.Row) -> IndexRow:
    """Build an :class:`IndexRow` from a ``_COLUMNS`` row.

    Args:
        raw: The row, read with ``sqlite3.Row`` as its factory.

    Returns:
        The row.
    """
    read = raw["date_provider_read"]
    return IndexRow(
        item_id=raw["id"],
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


def read_live_rows(conn: sqlite3.Connection) -> list[IndexRow]:
    """Read every live, identified row, the most recently added first.

    Args:
        conn: An open connection to ``library.db``, with ``sqlite3.Row`` as its row factory.

    Returns:
        The rows ordered by ``date_created`` descending, then ``id`` descending.
    """
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM media_item m WHERE {_LIVE_SQL} ORDER BY m.date_created DESC, m.id DESC"
    ).fetchall()
    return [row for row in map(_to_row, rows) if row.ids]


def read_holders(conn: sqlite3.Connection, provider: str, provider_id: str) -> list[IndexRow]:
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
    holders = [_to_row(row) for row in rows]
    shows = [row for row in holders if row.kind == "show"]
    if provider == "tvdb":
        return shows
    return [row for row in holders if row.kind == "movie"] or shows


def live_folders(conn: sqlite3.Connection, item_ids: Sequence[int]) -> dict[int, set[str]]:
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
    folders: dict[int, set[str]] = {}
    for item_id, disk_id, rel_path in conn.execute(query, [*item_ids, *item_ids]):
        parts = unicodedata.normalize("NFC", rel_path).strip("/").split("/")
        folders.setdefault(item_id, set()).add(f"{disk_id}:{'/'.join(parts[:_MEDIA_FOLDER_DEPTH])}")
    return folders


def live_episode_pairs(conn: sqlite3.Connection) -> dict[int, set[tuple[int, int]]]:
    """Read the held ``(season, episode)`` pairs of every show row at once.

    Args:
        conn: An open connection to ``library.db``.

    Returns:
        ``{item_id: pairs}`` for the show rows holding at least one live episode.
    """
    pairs: dict[int, set[tuple[int, int]]] = {}
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


def matches(row: IndexRow, query: str) -> bool:
    """Whether a row's title or original title contains the question, ignoring accents and case.

    Args:
        row: The row.
        query: The search text; blank matches every row.

    Returns:
        Whether it matches.
    """
    wanted = fold(query.strip())
    if not wanted:
        return True
    return wanted in fold(row.title) or (row.original_title is not None and wanted in fold(row.original_title))


def ordered(
    rows: Iterable[IndexRow],
    sort: LibrarySort,
    reversed_: bool,
    missing_of: Callable[[IndexRow], int | None],
) -> list[IndexRow]:
    """Order rows the way the listing asks.

    ``RECENT`` keeps the rows' own order (most recently added first); ``AZ`` sorts by the
    French collation of the sort title; ``MISSING`` puts the most episodes missing first and
    every row with nothing known (a movie, a show never catalogued) last. Every sort is
    stable over the recent order. Reversing is a second pass over the result, never a
    second comparator (the maquette's rule).

    Args:
        rows: The rows, most recently added first.
        sort: The order.
        reversed_: Whether to read it the other way round.
        missing_of: How many aired episodes a row lacks, or ``None`` when nothing says.

    Returns:
        The ordered rows.
    """
    held = list(rows)
    if sort is LibrarySort.AZ:
        held.sort(key=lambda row: french_key(row.title_sort))
    elif sort is LibrarySort.MISSING:
        missing = {row.item_id: missing_of(row) for row in held}
        held.sort(key=lambda row: (missing[row.item_id] is None, -(missing[row.item_id] or 0)))
    if reversed_:
        held.reverse()
    return held


def page_of(rows: Sequence[IndexRow], page: int, size: int = LIBRARY_PAGE_SIZE) -> Sequence[IndexRow]:
    """Cut one page out of ordered rows.

    Args:
        rows: The ordered rows.
        page: The page, zero based; a page past the end is empty.
        size: Rows per page.

    Returns:
        The page's rows.
    """
    return rows[page * size : (page + 1) * size]
