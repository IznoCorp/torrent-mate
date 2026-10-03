"""Provider-id duplicates in the index (read only).

A medium is identified by its canonical provider id (TVDB for a show, TMDB for a
movie, TMDB for a show whose ``canonical_provider`` says so — Q15). The index never
merges two rows that hold the same id; this module names them:

* an id held by two or more ``media_item`` rows (typically an old row that holds
  the files and a 0-file phantom beside it), or
* an id held by one row whose live files lie in two or more media folders
  (« Friends » / « Friends [UNCUT] »).

Nothing here writes. The CLI action ``library-duplicates-by-id`` and the library
service both read through :func:`find_provider_id_duplicates`.
"""

from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass

from personalscraper.core.identity import MediaRef

# The id a row is identified by, as ``(provider, series id text)``; NULL when the row
# carries none. Mirrors ``item_repo._canonical_series_id``: a show is keyed by TVDB
# unless its ``canonical_provider`` says TMDB, a movie by TMDB.
_PROVIDER_SQL = "CASE WHEN kind = 'show' AND canonical_provider IS NOT 'tmdb' THEN 'tvdb' ELSE 'tmdb' END"
_PROVIDER_ID_SQL = (
    "CAST(CASE WHEN kind = 'show' AND canonical_provider IS NOT 'tmdb' "
    "THEN json_extract(external_ids_json, '$.tvdb.series_id') "
    "ELSE json_extract(external_ids_json, '$.tmdb.series_id') END AS TEXT)"
)

# Placeholder ids historical scrapes leaked into NFOs; they name no medium
# (same set as ``item_repo._PLACEHOLDER_PROVIDER_IDS``).
_PLACEHOLDER_IDS = frozenset({"", "0", "none"})

# A disk holds ``<category folder>/<media folder>[/<sub folder>]``: season folders,
# trailers and extras all lie below the media folder, so it is the first two segments.
_MEDIA_FOLDER_DEPTH = 2

# Live (non tombstoned) files of every item, movie releases and episode releases alike.
_LIVE_FILES_SQL = """
SELECT r.item_id AS item_id, p.rel_path AS rel_path
FROM media_file f
JOIN media_release r ON r.id = f.release_id
JOIN path p ON p.id = f.path_id
WHERE f.deleted_at IS NULL AND r.item_id IS NOT NULL
UNION ALL
SELECT s.item_id, p.rel_path
FROM media_file f
JOIN media_release r ON r.id = f.release_id
JOIN episode e ON e.id = r.episode_id
JOIN season s ON s.id = e.season_id
JOIN path p ON p.id = f.path_id
WHERE f.deleted_at IS NULL
"""


@dataclass(frozen=True)
class DuplicateRow:
    """One ``media_item`` row of a duplicate group.

    Attributes:
        item_id: ``media_item.id``.
        title: The row's stored title.
        live_files: Number of non-deleted ``media_file`` rows of the item.
        folders: Distinct media folders (NFC, relative to their disk) holding the
            item's live files, sorted.
    """

    item_id: int
    title: str
    live_files: int
    folders: tuple[str, ...]


@dataclass(frozen=True)
class DuplicateGroup:
    """A provider id that names two rows or two media folders.

    Attributes:
        provider: ``"tvdb"`` or ``"tmdb"``.
        provider_id: The provider's series id, as text.
        kind: ``"movie"`` or ``"show"``.
        rows: The rows holding the id, by ``item_id``.
    """

    provider: str
    provider_id: str
    kind: str
    rows: tuple[DuplicateRow, ...]


def _media_folder(rel_path: str) -> str:
    """Return the media folder a file's directory lies in.

    The name is NFC-normalised: macOS lists folders in NFD, the index may hold both.

    Args:
        rel_path: ``path.rel_path`` of the file's directory
            (``series/Friends (1994)/Saison 01``).

    Returns:
        The NFC media folder, relative to its disk (``series/Friends (1994)``).
    """
    parts = unicodedata.normalize("NFC", rel_path).strip("/").split("/")
    return "/".join(parts[:_MEDIA_FOLDER_DEPTH])


def find_provider_id_duplicates(conn: sqlite3.Connection) -> list[DuplicateGroup]:
    """Report the ids held by two or more rows, or by one row spread over two media folders.

    Args:
        conn: Open connection on the indexer database (read only use).

    Returns:
        One :class:`DuplicateGroup` per duplicated id, ordered by ``(kind, provider, provider_id)``;
        a group's rows are ordered by ``item_id``. Empty when the index holds none.
    """
    items = conn.execute(
        f"SELECT id, kind, title, {_PROVIDER_SQL}, {_PROVIDER_ID_SQL} FROM media_item ORDER BY id"
    ).fetchall()

    folders: dict[int, set[str]] = {}
    live_files: dict[int, int] = {}
    for item_id, rel_path in conn.execute(_LIVE_FILES_SQL):
        folders.setdefault(item_id, set()).add(_media_folder(rel_path))
        live_files[item_id] = live_files.get(item_id, 0) + 1

    holders: dict[tuple[str, str, str], list[DuplicateRow]] = {}
    for item_id, kind, title, provider, provider_id in items:
        if provider_id is None or provider_id.strip().lower() in _PLACEHOLDER_IDS:
            continue
        row = DuplicateRow(
            item_id=item_id,
            title=title,
            live_files=live_files.get(item_id, 0),
            folders=tuple(sorted(folders.get(item_id, ()))),
        )
        holders.setdefault((kind, provider, provider_id.strip()), []).append(row)

    groups: list[DuplicateGroup] = []
    for (kind, provider, provider_id), rows in sorted(holders.items()):
        # Several rows, or one row whose files lie in two media folders.
        if len(rows) > 1 or len(rows[0].folders) > 1:
            groups.append(DuplicateGroup(provider=provider, provider_id=provider_id, kind=kind, rows=tuple(rows)))
    return groups


def rows_holding(conn: sqlite3.Connection, ref: MediaRef, kind: str | None = None) -> list[int]:
    """List the ``media_item`` ids holding *ref*'s canonical id, live or not.

    A row holds the id when its own canonical id (TVDB for a show unless its
    ``canonical_provider`` says TMDB, TMDB for a movie) equals the matching id of
    *ref*. A placeholder id (``0``) names nothing.

    Args:
        conn: Open connection on the indexer database.
        ref: The medium's provider ids.
        kind: ``"movie"`` or ``"show"`` to restrict the rows; ``None`` for both.

    Returns:
        The holding ``media_item.id`` values, ascending; empty when none holds it.
    """
    wanted = {"tvdb": ref.tvdb_id, "tmdb": ref.tmdb_id}
    clauses: list[str] = []
    params: list[object] = []
    for provider, value in wanted.items():
        if value is None or str(value).strip().lower() in _PLACEHOLDER_IDS:
            continue
        clauses.append(f"({_PROVIDER_SQL} = ? AND {_PROVIDER_ID_SQL} = ?)")
        params.extend([provider, str(value)])
    if not clauses:
        return []
    sql = f"SELECT id FROM media_item WHERE ({' OR '.join(clauses)})"
    if kind is not None:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY id"
    return [row[0] for row in conn.execute(sql, params)]
