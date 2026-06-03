"""Repository for the ``media_item`` and ``item_attribute`` tables.

Provides CRUD operations for media items and their flexible attributes.
All write methods emit structlog events following the ``indexer.{component}.{action}``
convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import re
import sqlite3

from personalscraper.indexer.schema import ItemAttributeRow, MediaItemRow
from personalscraper.logger import get_logger

log = get_logger("indexer.item")

# Regex matching a trailing " (YYYY)" suffix on a title string.
# Accepts 0+ whitespace before the opening paren so that ``"Movie  (2020)"``,
# ``"Movie (2020)"``, and ``"Movie(2020)"`` all canonicalise to ``"Movie"``.
# Used by ``_canonical_title`` to normalise lookup keys.
_CANONICAL_RE = re.compile(r"\s*\(\d{4}\)$")

# Provider family → JSON path into ``media_item.external_ids_json`` for the
# series-level id. Whitelist used by :func:`find_by_external_id`: the provider
# name is interpolated into the ``json_extract`` path (which SQLite cannot
# parameterise), so only these keys may ever reach the SQL string — an unknown
# provider returns ``None`` rather than risking an injected path.
_EXTERNAL_ID_JSON_PATHS: dict[str, str] = {
    "tvdb": "$.tvdb.series_id",
    "tmdb": "$.tmdb.series_id",
    "imdb": "$.imdb.series_id",
}

# Placeholder / non-identifying values that historical scrapes leaked into NFO
# ``<uniqueid>`` elements (a literal ``0`` or ``None``). They are stored verbatim
# in ``external_ids_json`` (``"0".isdigit()`` is true; imdb is stored unfiltered),
# so an id match on one of them would join *every* row carrying the same
# placeholder and trigger a false merge/replace. :func:`find_by_external_id`
# refuses to match on them.
_PLACEHOLDER_PROVIDER_IDS = frozenset({"", "0", "none"})


def _canonical_title(title: str) -> str:
    """Strip a trailing `` (YYYY)`` suffix from *title* if present.

    Normalises both the stored title (post-migration 007) and the lookup key
    so that ``_upsert_media_item`` deduplicates by the base title regardless of
    whether the caller includes a release year in the title string.
    See migration 007 (``007_media_item_dedup.sql``) and DEV #53 for the
    dedup rationale.

    Args:
        title: Raw title, which may or may not end with `` (2020)``.

    Returns:
        The title without the trailing year suffix.
    """
    return _CANONICAL_RE.sub("", title)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_item(row: sqlite3.Row) -> MediaItemRow:
    """Convert a ``sqlite3.Row`` from ``media_item`` to a :class:`MediaItemRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`MediaItemRow` instance.
    """
    return MediaItemRow(
        id=row["id"],
        kind=row["kind"],
        title=row["title"],
        title_sort=row["title_sort"],
        original_title=row["original_title"],
        year=row["year"],
        category_id=row["category_id"],
        external_ids_json=row["external_ids_json"],
        ratings_json=row["ratings_json"],
        canonical_provider=row["canonical_provider"],
        nfo_status=row["nfo_status"],
        artwork_json=row["artwork_json"],
        date_created=row["date_created"],
        date_modified=row["date_modified"],
        date_metadata_refreshed=row["date_metadata_refreshed"],
        is_locked=row["is_locked"],
        preferred_lang=row["preferred_lang"],
    )


def _row_to_attr(row: sqlite3.Row) -> ItemAttributeRow:
    """Convert a ``sqlite3.Row`` from ``item_attribute`` to an :class:`ItemAttributeRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`ItemAttributeRow` instance.
    """
    return ItemAttributeRow(
        item_id=row["item_id"],
        key=row["key"],
        value=row["value"],
    )


# ---------------------------------------------------------------------------
# media_item table operations
# ---------------------------------------------------------------------------


def insert(conn: sqlite3.Connection, row: MediaItemRow) -> int:
    """Insert a new media item and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaItemRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: On constraint violation.
    """
    cursor = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, original_title, year, category_id,
            external_ids_json, ratings_json, canonical_provider,
            nfo_status, artwork_json,
            date_created, date_modified, date_metadata_refreshed,
            is_locked, preferred_lang
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.kind,
            row.title,
            row.title_sort,
            row.original_title,
            row.year,
            row.category_id,
            row.external_ids_json,
            row.ratings_json,
            row.canonical_provider,
            row.nfo_status,
            row.artwork_json,
            row.date_created,
            row.date_modified,
            row.date_metadata_refreshed,
            row.is_locked,
            row.preferred_lang,
        ),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.item.insert", title=row.title, kind=row.kind, rowid=rowid)
    return rowid


def get_by_id(conn: sqlite3.Connection, id: int) -> MediaItemRow | None:
    """Fetch a media item row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`MediaItemRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT id, kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang "
        "FROM media_item WHERE id = ?",
        (id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def find_by_tmdb_id(conn: sqlite3.Connection, tmdb_id: int) -> MediaItemRow | None:
    """Fetch the first media item matching a TMDB numeric ID.

    Args:
        conn: Open SQLite connection.
        tmdb_id: TMDB numeric ID to search for.

    Returns:
        :class:`MediaItemRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT id, kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang "
        "FROM media_item "
        "WHERE CAST(json_extract(external_ids_json, '$.tmdb.series_id') AS TEXT) = CAST(? AS TEXT)",
        (tmdb_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def find_by_external_id(
    conn: sqlite3.Connection,
    provider: str,
    series_id: str,
    kind: str,
) -> tuple[MediaItemRow, str, str] | None:
    """Find a media item by an external provider series id + dispatch attrs.

    Mirrors :func:`find_by_normalized_name` (identical return shape and
    ``item_attribute`` JOIN for the dispatch disk/path) but matches on a
    provider id stored in ``external_ids_json`` rather than the normalized
    title. The dispatch lookup uses this to recognise a show/movie already on
    disk under a *different* folder name (localized title, wrong year) as the
    same item, keying on the canonical provider id instead of the spelling —
    closing the "same TVDB id, two folders" split.

    The match is filtered by ``kind`` (a movie and a show never share an
    identity) and, on ties, returns the most-recently-modified row (consistent
    with :func:`find_by_normalized_name`).

    Args:
        conn: Open SQLite connection.
        provider: Provider family — one of ``"tvdb"``, ``"tmdb"``, ``"imdb"``.
            Any other value returns ``None`` (whitelist guard).
        series_id: The provider's series id, in string form.
        kind: ``'movie'`` or ``'show'``.

    Returns:
        A ``(MediaItemRow, dispatch_disk, dispatch_path)`` triple when found,
        or ``None`` when no matching item exists or ``provider`` is unknown.
    """
    json_path = _EXTERNAL_ID_JSON_PATHS.get(provider)
    if json_path is None:
        return None
    # Never match on a placeholder id (``0``/``None``): it would join every
    # unrelated row carrying the same leaked value and cause a false dispatch.
    if series_id.strip().lower() in _PLACEHOLDER_PROVIDER_IDS:
        return None
    _set_row_factory(conn)
    # Fetch up to two rows to detect (and surface) an ambiguous id — two on-disk
    # folders sharing one provider id, e.g. a pre-existing split.
    rows = conn.execute(
        "SELECT m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, "
        "m.external_ids_json, m.ratings_json, m.canonical_provider, m.nfo_status, m.artwork_json, "
        "m.date_created, m.date_modified, m.date_metadata_refreshed, m.is_locked, m.preferred_lang, "
        "a1.value AS dispatch_disk, a2.value AS dispatch_path "
        "FROM media_item m "
        "LEFT JOIN item_attribute a1 ON a1.item_id = m.id AND a1.key = ? "
        "LEFT JOIN item_attribute a2 ON a2.item_id = m.id AND a2.key = ? "
        f"WHERE CAST(json_extract(m.external_ids_json, '{json_path}') AS TEXT) = CAST(? AS TEXT) "
        "AND m.kind = ? "
        "ORDER BY m.date_modified DESC "
        "LIMIT 2",
        (_ATTR_DISPATCH_DISK, _ATTR_DISPATCH_PATH, series_id, kind),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        # Newest-modified wins (consistent with find_by_normalized_name), but
        # log the ambiguity so the operator can reconcile the duplicate folders.
        log.warning(
            "indexer.dispatch.external_id_ambiguous",
            provider=provider,
            series_id=series_id,
            kind=kind,
            matched=len(rows),
        )
    row = rows[0]
    item = _row_to_item(row)
    dispatch_disk: str = row["dispatch_disk"] or ""
    dispatch_path: str = row["dispatch_path"] or ""
    return (item, dispatch_disk, dispatch_path)


def delete(conn: sqlite3.Connection, id: int) -> bool:
    """Hard-delete a media item row (cascades to child tables via ON DELETE CASCADE).

    Hard-delete is intentional here: this function is **test-only** and is used
    exclusively by test fixtures to clean up rows they inserted.  ``media_item``
    has no ``deleted_at`` column, so soft-delete is not available at the schema
    level.  Production callers must never use this function — use
    :func:`remove_by_id` for dispatch-cache eviction (also a hard-delete, but
    justified separately; see its docstring).

    Args:
        conn: Open SQLite connection.
        id: PK of the media item to delete.

    Returns:
        ``True`` if a row was deleted, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute("DELETE FROM media_item WHERE id = ?", (id,))
    deleted = cursor.rowcount > 0
    if deleted:
        log.info("indexer.item.delete", id=id)
    return deleted


# ---------------------------------------------------------------------------
# item_attribute table operations
# ---------------------------------------------------------------------------


def upsert_attr(conn: sqlite3.Connection, row: ItemAttributeRow) -> int:
    """Upsert a flex attribute, replacing ``value`` on conflict.

    Args:
        conn: Open SQLite connection.
        row: :class:`ItemAttributeRow` to upsert.

    Returns:
        The ``rowid`` of the upserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO item_attribute (item_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(item_id, key) DO UPDATE SET value = excluded.value
        """,
        (row.item_id, row.key, row.value),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.item.upsert_attr", item_id=row.item_id, key=row.key, rowid=rowid)
    return rowid


def get_attr(conn: sqlite3.Connection, item_id: int, key: str) -> ItemAttributeRow | None:
    """Fetch a single flex attribute by ``(item_id, key)``.

    Args:
        conn: Open SQLite connection.
        item_id: FK of the owning media item.
        key: Attribute key string.

    Returns:
        :class:`ItemAttributeRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT item_id, key, value FROM item_attribute WHERE item_id = ? AND key = ?",
        (item_id, key),
    ).fetchone()
    if row is None:
        return None
    return _row_to_attr(row)


# ---------------------------------------------------------------------------
# Dispatch-layer helpers
# ---------------------------------------------------------------------------

#: Attribute key for the config-level disk identifier stored by the dispatch
#: layer (e.g. ``"drive_a"``).  This is distinct from ``disk.label`` in the
#: DB, which is the volume display name.  The dispatch layer stores config IDs
#: so it can map back to ``DiskConfig`` objects without a secondary DB lookup.
_ATTR_DISPATCH_DISK = "dispatch_disk"

#: Attribute key for the full filesystem path of the media item root directory
#: as seen by the dispatch layer (e.g. ``"/Volumes/Disk1/movies/Inception (2010)"``).
_ATTR_DISPATCH_PATH = "dispatch_path"

#: Attribute key for the NFC-normalized, lowercased title used as the dispatch
#: lookup key.  Stored as an attribute so that cross-filesystem Unicode
#: normalization differences (APFS precomposed vs NTFS decomposed) are resolved
#: at write time rather than at query time (SQLite's ``lower()`` is ASCII-only
#: and does not perform Unicode NFC normalization).
_ATTR_DISPATCH_NORM_TITLE = "dispatch_normalized_title"


def upsert(conn: sqlite3.Connection, row: MediaItemRow) -> int:
    """Insert or update a :class:`MediaItemRow` keyed by ``(kind, title)``.

    Performs a SELECT-then-UPDATE-or-INSERT to handle the dispatch layer's
    one-row-per-``(kind, title)`` invariant.  The title is canonicalised via
    :func:`_canonical_title` before lookup and insert so that callers passing
    ``"Inception (2010)"`` match an already-stored row with ``title="Inception"``
    (DEV #53 dedup fix).

    When a matching row already exists, ``category_id`` and ``date_modified``
    are refreshed.  Otherwise a new row is inserted with the canonicalised title.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaItemRow` to upsert.  The ``id`` field is ignored;
            ``title`` may carry a trailing `` (YYYY)`` suffix which will be
            stripped before storage.

    Returns:
        The ``rowid`` (= ``id``) of the inserted or updated row.
    """
    canonical = _canonical_title(row.title)
    existing = get_by_title_and_kind(conn, canonical, row.kind)
    if existing is not None:
        conn.execute(
            "UPDATE media_item SET category_id = ?, date_modified = ? WHERE id = ?",
            (row.category_id, row.date_modified, existing.id),
        )
        log.info("indexer.item.upsert_update", title=canonical, kind=row.kind, id=existing.id)
        return existing.id
    cursor = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, original_title, year, category_id,
            external_ids_json, ratings_json, canonical_provider,
            nfo_status, artwork_json,
            date_created, date_modified, date_metadata_refreshed,
            is_locked, preferred_lang
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.kind,
            canonical,
            row.title_sort,
            row.original_title,
            row.year,
            row.category_id,
            row.external_ids_json,
            row.ratings_json,
            row.canonical_provider,
            row.nfo_status,
            row.artwork_json,
            row.date_created,
            row.date_modified,
            row.date_metadata_refreshed,
            row.is_locked,
            row.preferred_lang,
        ),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.item.upsert_insert", title=canonical, kind=row.kind, rowid=rowid)
    return rowid


def get_by_title_and_kind(conn: sqlite3.Connection, title: str, kind: str) -> MediaItemRow | None:
    """Fetch a media item row by its ``(title, kind)`` unique pair.

    Canonicalises *title* via :func:`_canonical_title` before querying so
    that ``"Inception (2010)"`` and ``"Inception"`` resolve to the same row
    (DEV #53 dedup fix).

    Args:
        conn: Open SQLite connection.
        title: Display title, possibly with a trailing `` (YYYY)`` suffix.
        kind: ``'movie'`` or ``'show'``.

    Returns:
        :class:`MediaItemRow` if found, ``None`` otherwise.
    """
    canonical = _canonical_title(title)
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT id, kind, title, title_sort, original_title, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang "
        "FROM media_item WHERE title = ? AND kind = ?",
        (canonical, kind),
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def find_by_normalized_name(
    conn: sqlite3.Connection,
    normalized_name: str,
    kind: str,
) -> tuple[MediaItemRow, str, str] | None:
    """Find a media item by its NFC-normalized title and retrieve dispatch attrs.

    Queries ``media_item`` joined with ``item_attribute`` rows keyed by
    :data:`_ATTR_DISPATCH_NORM_TITLE` (lookup key), :data:`_ATTR_DISPATCH_DISK`,
    and :data:`_ATTR_DISPATCH_PATH`.  The ``normalized_name`` must already be
    NFC-lowercased (the caller is responsible for normalization via
    ``_normalize_key``).

    Using a stored normalized-title attribute (rather than ``lower(m.title)``)
    is intentional: SQLite's ``lower()`` is ASCII-only and cannot perform
    Unicode NFC normalization, so matching NFD-encoded titles stored by
    macFUSE-NTFS disks against NFC queries from APFS would silently fail.

    Args:
        conn: Open SQLite connection.
        normalized_name: NFC-normalized, lowercased title (output of
            ``_normalize_key`` in ``dispatch/media_index.py``).
        kind: ``'movie'`` or ``'show'``.

    Returns:
        A ``(MediaItemRow, dispatch_disk, dispatch_path)`` triple when found,
        or ``None`` when no matching item exists.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, "
        "m.external_ids_json, m.ratings_json, m.canonical_provider, m.nfo_status, m.artwork_json, "
        "m.date_created, m.date_modified, m.date_metadata_refreshed, m.is_locked, m.preferred_lang, "
        "a1.value AS dispatch_disk, a2.value AS dispatch_path "
        "FROM media_item m "
        "INNER JOIN item_attribute anorm ON anorm.item_id = m.id AND anorm.key = ? AND anorm.value = ? "
        "LEFT JOIN item_attribute a1 ON a1.item_id = m.id AND a1.key = ? "
        "LEFT JOIN item_attribute a2 ON a2.item_id = m.id AND a2.key = ? "
        "WHERE m.kind = ? "
        "ORDER BY m.date_modified DESC "
        "LIMIT 1",
        (_ATTR_DISPATCH_NORM_TITLE, normalized_name, _ATTR_DISPATCH_DISK, _ATTR_DISPATCH_PATH, kind),
    ).fetchone()
    if row is None:
        return None
    item = _row_to_item(row)
    dispatch_disk: str = row["dispatch_disk"] or ""
    dispatch_path: str = row["dispatch_path"] or ""
    return (item, dispatch_disk, dispatch_path)


def find_on_disk(
    conn: sqlite3.Connection,
    disk_id: int,
) -> list[tuple[MediaItemRow, str, str]]:
    """List all media items whose files reside on a specific disk.

    Joins ``media_item`` → ``media_release`` → ``media_file`` → ``path`` to
    find every item that has at least one file on ``disk_id``.  Returns unique
    ``(MediaItemRow, mount_path, rel_path)`` triples where ``rel_path`` is the
    deepest ``path`` row matching the item (i.e. the directory containing the
    item's primary video file).

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the ``disk`` row to query.

    Returns:
        List of ``(MediaItemRow, mount_path, rel_path)`` triples.
        ``mount_path`` is the disk's ``mount_path`` column value (may be ``None``
        if the disk is not currently mounted, in which case an empty string is
        returned).  ``rel_path`` is the relative directory path from ``path``.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT DISTINCT "
        "m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, "
        "m.external_ids_json, m.ratings_json, m.canonical_provider, m.nfo_status, m.artwork_json, "
        "m.date_created, m.date_modified, m.date_metadata_refreshed, m.is_locked, m.preferred_lang, "
        "d.mount_path AS disk_mount, p.rel_path AS item_rel_path "
        "FROM media_item m "
        "INNER JOIN media_release mr ON mr.item_id = m.id "
        "INNER JOIN media_file mf ON mf.release_id = mr.id "
        "INNER JOIN path p ON p.id = mf.path_id "
        "INNER JOIN disk d ON d.id = p.disk_id "
        "WHERE p.disk_id = ? "
        "ORDER BY m.id",
        (disk_id,),
    ).fetchall()
    result: list[tuple[MediaItemRow, str, str]] = []
    for row in rows:
        item = _row_to_item(row)
        mount_path: str = row["disk_mount"] or ""
        rel_path: str = row["item_rel_path"] or ""
        result.append((item, mount_path, rel_path))
    return result


def find_items_needing_rescrape(conn: sqlite3.Connection) -> list[tuple[MediaItemRow, str, str]]:
    """Return items with invalid/missing NFO or no metadata refresh, with their filesystem paths.

    Queries ``media_item`` for rows where ``nfo_status != 'valid'`` or
    ``date_metadata_refreshed IS NULL`` and ``is_locked = 0``.  Joins to ``path``
    and ``disk`` to reconstruct the filesystem path.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(MediaItemRow, mount_path, rel_path)`` triples for items that
        need rescraping.  Items without any associated file rows are excluded.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT DISTINCT "
        "m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, "
        "m.external_ids_json, m.ratings_json, m.canonical_provider, m.nfo_status, m.artwork_json, "
        "m.date_created, m.date_modified, m.date_metadata_refreshed, m.is_locked, m.preferred_lang, "
        "d.mount_path AS disk_mount, p.rel_path AS item_rel_path "
        "FROM media_item m "
        "INNER JOIN media_release mr ON mr.item_id = m.id "
        "INNER JOIN media_file mf ON mf.release_id = mr.id "
        "INNER JOIN path p ON p.id = mf.path_id "
        "INNER JOIN disk d ON d.id = p.disk_id "
        "WHERE m.is_locked = 0 "
        "  AND (m.nfo_status != 'valid' OR m.date_metadata_refreshed IS NULL) "
        "ORDER BY m.id",
    ).fetchall()
    result: list[tuple[MediaItemRow, str, str]] = []
    for row in rows:
        item = _row_to_item(row)
        mount_path: str = row["disk_mount"] or ""
        rel_path: str = row["item_rel_path"] or ""
        result.append((item, mount_path, rel_path))
    return result


def remove_by_id(conn: sqlite3.Connection, item_id: int) -> bool:
    """Hard-delete a dispatch-cache media item by primary key.

    Hard-delete is intentional here: callers (``MediaIndex.rebuild`` and
    ``MediaIndex.remove_stale``) operate on **dispatch-attributed** rows
    that act as a transient filesystem cache — they store no independently
    scraped metadata (no seasons, no episodes, no NFO data).  The entire
    purpose of ``rebuild()`` is a clean-slate re-walk from disk, so stale
    rows must be fully removed, not tombstoned.  Soft-delete would require:

    1. A schema migration adding ``deleted_at`` to ``media_item``, and
    2. Filtering ``deleted_at IS NULL`` in every dispatch lookup query.

    Neither is warranted for a cache that is rebuilt from the filesystem on
    demand.  ON DELETE CASCADE propagates the removal to ``item_attribute``
    child rows automatically.

    Args:
        conn: Open SQLite connection.
        item_id: Primary key of the dispatch-attributed media item to remove.

    Returns:
        ``True`` if a row was deleted, ``False`` if no row matched.
    """
    # Hard-delete justified: dispatch cache eviction — rows are ephemeral
    # filesystem-cache entries rebuilt from disk via MediaIndex.rebuild().
    cursor = conn.execute("DELETE FROM media_item WHERE id = ?", (item_id,))
    deleted = cursor.rowcount > 0
    if deleted:
        log.info("indexer.item.remove", id=item_id)
    return deleted


def list_all_dispatch_items(conn: sqlite3.Connection) -> list[tuple[MediaItemRow, str, str]]:
    """List all media items that have dispatch attributes stored.

    Returns all ``media_item`` rows that have :data:`_ATTR_DISPATCH_NORM_TITLE`,
    :data:`_ATTR_DISPATCH_DISK`, and :data:`_ATTR_DISPATCH_PATH` attributes
    set, along with the disk and path attribute values.  Items inserted
    directly by the scanner (without dispatch attrs) are excluded.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(MediaItemRow, dispatch_disk, dispatch_path)`` triples.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, "
        "m.external_ids_json, m.ratings_json, m.canonical_provider, m.nfo_status, m.artwork_json, "
        "m.date_created, m.date_modified, m.date_metadata_refreshed, m.is_locked, m.preferred_lang, "
        "a1.value AS dispatch_disk, a2.value AS dispatch_path "
        "FROM media_item m "
        "INNER JOIN item_attribute anorm ON anorm.item_id = m.id AND anorm.key = ? "
        "INNER JOIN item_attribute a1 ON a1.item_id = m.id AND a1.key = ? "
        "INNER JOIN item_attribute a2 ON a2.item_id = m.id AND a2.key = ? ",
        (_ATTR_DISPATCH_NORM_TITLE, _ATTR_DISPATCH_DISK, _ATTR_DISPATCH_PATH),
    ).fetchall()
    result: list[tuple[MediaItemRow, str, str]] = []
    for row in rows:
        item = _row_to_item(row)
        dispatch_disk: str = row["dispatch_disk"] or ""
        dispatch_path: str = row["dispatch_path"] or ""
        result.append((item, dispatch_disk, dispatch_path))
    return result
