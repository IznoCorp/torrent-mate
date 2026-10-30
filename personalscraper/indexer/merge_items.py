"""Merge ``media_item`` rows that share one ``dispatch_path`` into the oldest.

A media folder is one work, so one item. An older build split some folders in
two: the dispatch re-index wrote the folder name WITH its year into ``title``,
the next scan's year-stripped upsert missed that row and inserted a second item
carrying the same ``dispatch_path``. The cause is fixed at the source
(``MediaIndex.add`` and ``item_repo.upsert(existing_id=…)``); this module
repairs the pairs already in a store.

Every child row is re-pointed to the keeper before the duplicate is deleted, so
the ``ON DELETE CASCADE`` that follows removes nothing of value:

- ``media_release`` (item-level) — re-pointed; when the keeper already holds a
  release of the same signature its files move onto that release instead;
- ``season`` — re-pointed; when the keeper already has that season number its
  episodes move into the keeper's season, and an episode number both carry
  hands its releases (``episode_id`` and ``episode_end_id``) to the keeper's;
- ``item_attribute`` / ``item_issue`` — copied where the keeper lacks the key;
- ``scan_event`` and ``repair_queue`` (``scope='item'``) — re-pointed.

The keeper takes the freshest metadata of the pair (the most recently modified
row's NFO-derived columns, merged provider ids) and a ``deleted_item``
tombstone records each merged row.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field

from personalscraper.indexer.repos import item_repo
from personalscraper.logger import get_logger

log = get_logger("indexer.merge_items")

#: ``deleted_item.reason`` of a row merged into its folder's keeper.
MERGE_REASON = "merged_duplicate"


@dataclass(frozen=True)
class DuplicateGroup:
    """Items sharing one ``dispatch_path``.

    Attributes:
        dispatch_path: The media folder the items share.
        keeper_id: The oldest item (smallest ``date_created``, then ``id``).
        duplicate_ids: The other items, merged into the keeper.
        titles: ``id → title`` of every member, for the report.
    """

    dispatch_path: str
    keeper_id: int
    duplicate_ids: tuple[int, ...]
    titles: dict[int, str] = field(default_factory=dict)


@dataclass
class MergeReport:
    """Outcome of :func:`merge_duplicate_items`.

    Attributes:
        groups: The duplicate groups found (merged unless ``skipped``).
        skipped: Groups left alone, with the reason (see :func:`_skip_reason`).
        merged: Number of duplicate rows merged (0 on a dry run).
    """

    groups: list[DuplicateGroup] = field(default_factory=list)
    skipped: list[tuple[DuplicateGroup, str]] = field(default_factory=list)
    merged: int = 0


def find_duplicate_groups(conn: sqlite3.Connection) -> list[DuplicateGroup]:
    """List every ``dispatch_path`` carried by more than one item.

    Paths compare on :func:`~personalscraper.indexer.repos.item_repo.dispatch_path_key`
    (NFC, casefolded).

    Args:
        conn: Open SQLite connection.

    Returns:
        One :class:`DuplicateGroup` per shared path, ordered by the keeper's
        path; members ordered oldest first.
    """
    rows = conn.execute(
        "SELECT a.value, m.id, m.title FROM item_attribute a "
        "JOIN media_item m ON m.id = a.item_id "
        "WHERE a.key = ? ORDER BY m.date_created, m.id",
        (item_repo._ATTR_DISPATCH_PATH,),
    ).fetchall()
    # Grouped on the path key, not the bytes: an NFD (HFS+ walk) or case
    # variant of the NFC path the dispatch wrote is the same folder.
    by_key: dict[str, list[tuple[str, int, str]]] = {}
    for path, item_id, title in rows:
        by_key.setdefault(item_repo.dispatch_path_key(str(path)), []).append((str(path), int(item_id), str(title)))
    groups = [
        DuplicateGroup(
            dispatch_path=members[0][0],
            keeper_id=members[0][1],
            duplicate_ids=tuple(item_id for _path, item_id, _title in members[1:]),
            titles={item_id: title for _path, item_id, title in members},
        )
        for members in by_key.values()
        if len(members) > 1
    ]
    return sorted(groups, key=lambda group: group.dispatch_path)


def _same_signature_release(
    conn: sqlite3.Connection, release_id: int, *, item_id: int | None, episode_id: int | None
) -> int | None:
    """Return the release of *item_id* / *episode_id* sharing *release_id*'s signature.

    Args:
        conn: Open SQLite connection.
        release_id: The release being moved.
        item_id: The target item (item-level releases), or ``None``.
        episode_id: The target episode (episode releases), or ``None``.

    Returns:
        The matching release id on the target, or ``None``.
    """
    row = conn.execute(
        "SELECT t.id FROM media_release s JOIN media_release t "
        "ON t.quality IS s.quality AND t.edition IS s.edition AND t.primary_lang IS s.primary_lang "
        # A span (S01E01-E02) is not the single episode it starts on.
        "AND t.episode_end_id IS s.episode_end_id "
        "WHERE s.id = ? AND t.id != s.id AND t.item_id IS ? AND t.episode_id IS ? LIMIT 1",
        (release_id, item_id, episode_id),
    ).fetchone()
    return int(row[0]) if row is not None else None


def _fold_release(conn: sqlite3.Connection, release_id: int, target_id: int) -> None:
    """Move every file of *release_id* onto *target_id*, then drop the emptied release.

    Args:
        conn: Open SQLite connection.
        release_id: The release to fold away.
        target_id: The release that receives its files.
    """
    conn.execute("UPDATE media_file SET release_id = ? WHERE release_id = ?", (target_id, release_id))
    conn.execute("DELETE FROM media_release WHERE id = ?", (release_id,))


def _move_episode_releases(conn: sqlite3.Connection, from_episode: int, to_episode: int) -> None:
    """Hand every release of *from_episode* to *to_episode*.

    Args:
        conn: Open SQLite connection.
        from_episode: The episode being merged away.
        to_episode: The keeper's episode of the same number.
    """
    # ``episode_end_id`` carries no ON DELETE action: it must leave the episode
    # before the episode can be deleted.
    conn.execute("UPDATE media_release SET episode_end_id = ? WHERE episode_end_id = ?", (to_episode, from_episode))
    for (release_id,) in conn.execute("SELECT id FROM media_release WHERE episode_id = ?", (from_episode,)).fetchall():
        twin = _same_signature_release(conn, release_id, item_id=None, episode_id=to_episode)
        if twin is not None:
            _fold_release(conn, release_id, twin)
        else:
            conn.execute("UPDATE media_release SET episode_id = ? WHERE id = ?", (to_episode, release_id))


def _merge_season(conn: sqlite3.Connection, season_id: int, keeper_season: int) -> None:
    """Move the episodes of *season_id* into *keeper_season*, then drop the emptied season.

    Args:
        conn: Open SQLite connection.
        season_id: The duplicate's season.
        keeper_season: The keeper's season of the same number.
    """
    episodes = conn.execute("SELECT id, number, title FROM episode WHERE season_id = ?", (season_id,)).fetchall()
    for episode_id, number, title in episodes:
        twin = conn.execute(
            "SELECT id FROM episode WHERE season_id = ? AND number = ?", (keeper_season, number)
        ).fetchone()
        if twin is None:
            conn.execute("UPDATE episode SET season_id = ? WHERE id = ?", (keeper_season, episode_id))
            continue
        _move_episode_releases(conn, episode_id, int(twin[0]))
        conn.execute("UPDATE episode SET title = COALESCE(title, ?) WHERE id = ?", (title, int(twin[0])))
        conn.execute("DELETE FROM episode WHERE id = ?", (episode_id,))
    conn.execute(
        "UPDATE season SET has_poster = MAX(has_poster, (SELECT has_poster FROM season WHERE id = ?)),"
        " episodes_with_nfo = MAX(episodes_with_nfo, (SELECT episodes_with_nfo FROM season WHERE id = ?))"
        " WHERE id = ?",
        (season_id, season_id, keeper_season),
    )
    conn.execute("DELETE FROM season WHERE id = ?", (season_id,))


def _merge_item(conn: sqlite3.Connection, duplicate_id: int, keeper_id: int, now_s: int) -> None:
    """Re-point every child of *duplicate_id* to *keeper_id*, then delete the duplicate.

    Args:
        conn: Open SQLite connection.
        duplicate_id: The row merged away.
        keeper_id: The row that survives.
        now_s: Epoch seconds stamped on the tombstone.
    """
    for (release_id,) in conn.execute("SELECT id FROM media_release WHERE item_id = ?", (duplicate_id,)).fetchall():
        twin = _same_signature_release(conn, release_id, item_id=keeper_id, episode_id=None)
        if twin is not None:
            _fold_release(conn, release_id, twin)
        else:
            conn.execute("UPDATE media_release SET item_id = ? WHERE id = ?", (keeper_id, release_id))

    for season_id, number in conn.execute(
        "SELECT id, number FROM season WHERE item_id = ?", (duplicate_id,)
    ).fetchall():
        twin = conn.execute("SELECT id FROM season WHERE item_id = ? AND number = ?", (keeper_id, number)).fetchone()
        if twin is None:
            conn.execute("UPDATE season SET item_id = ? WHERE id = ?", (keeper_id, season_id))
        else:
            _merge_season(conn, int(season_id), int(twin[0]))

    conn.execute(
        "INSERT OR IGNORE INTO item_attribute (item_id, key, value) "
        "SELECT ?, key, value FROM item_attribute WHERE item_id = ?",
        (keeper_id, duplicate_id),
    )
    conn.execute(
        "INSERT OR IGNORE INTO item_issue (item_id, type, detail, detected_at) "
        "SELECT ?, type, detail, detected_at FROM item_issue WHERE item_id = ?",
        (keeper_id, duplicate_id),
    )
    conn.execute("UPDATE scan_event SET item_id = ? WHERE item_id = ?", (keeper_id, duplicate_id))
    conn.execute(
        "UPDATE repair_queue SET scope_id = ? WHERE scope = 'item' AND scope_id = ?",
        (keeper_id, duplicate_id),
    )

    keeper = item_repo.get_by_id(conn, keeper_id)
    duplicate = item_repo.get_by_id(conn, duplicate_id)
    assert keeper is not None and duplicate is not None  # both read inside the same transaction
    fresher = duplicate if duplicate.date_modified > keeper.date_modified else keeper
    older, newer = (keeper, duplicate) if fresher is duplicate else (duplicate, keeper)

    conn.execute(
        "INSERT INTO deleted_item (kind, original_id, deleted_at, reason, payload_json) VALUES ('item', ?, ?, ?, ?)",
        (
            duplicate_id,
            now_s,
            MERGE_REASON,
            json.dumps(
                {
                    "merged_into": keeper_id,
                    "title": duplicate.title,
                    "year": duplicate.year,
                    "kind": duplicate.kind,
                    "category_id": duplicate.category_id,
                    "external_ids_json": duplicate.external_ids_json,
                }
            ),
        ),
    )
    conn.execute("DELETE FROM media_item WHERE id = ?", (duplicate_id,))

    # Deleted first: the keeper may now take the canonical (title, kind, year)
    # the duplicate held under the UNIQUE index.
    conn.execute(
        "UPDATE media_item SET category_id = ?, external_ids_json = ?, ratings_json = ?,"
        " canonical_provider = ?, nfo_status = ?, artwork_json = ?, year = COALESCE(year, ?),"
        " date_metadata_refreshed = MAX(COALESCE(date_metadata_refreshed, 0), COALESCE(?, 0)),"
        " date_modified = MAX(date_modified, ?), is_locked = MAX(is_locked, ?) WHERE id = ?",
        (
            fresher.category_id,
            item_repo._merge_external_ids(older.external_ids_json, newer.external_ids_json),
            fresher.ratings_json,
            fresher.canonical_provider,
            fresher.nfo_status,
            fresher.artwork_json,
            duplicate.year,
            duplicate.date_metadata_refreshed,
            duplicate.date_modified,
            duplicate.is_locked,
            keeper_id,
        ),
    )
    conn.execute(
        "UPDATE media_item SET date_metadata_refreshed = NULL WHERE id = ? AND date_metadata_refreshed = 0",
        (keeper_id,),
    )
    conn.execute(
        "UPDATE OR IGNORE media_item SET title = ? WHERE id = ?",
        (item_repo._canonical_title(keeper.title), keeper_id),
    )
    log.info("indexer.merge_items.merged", keeper_id=keeper_id, duplicate_id=duplicate_id)


def _provider_ids(raw: str | None) -> dict[str, str]:
    """Flatten an ``external_ids_json`` to ``"family.key" → id``, empty values dropped.

    Args:
        raw: The stored JSON, or ``None``.

    Returns:
        The ids, e.g. ``{"tmdb.series_id": "97546"}``.
    """
    try:
        parsed = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    flat: dict[str, str] = {}
    for family, value in parsed.items() if isinstance(parsed, dict) else ():
        if isinstance(value, dict):
            flat.update({f"{family}.{key}": str(v) for key, v in value.items() if v not in (None, "")})
        elif value not in (None, ""):
            flat[str(family)] = str(value)
    return flat


def _skip_reason(conn: sqlite3.Connection, group: DuplicateGroup) -> str | None:
    """Return why *group* must not be merged, or ``None`` when it is a split of one work.

    A folder shared by two works is not a split the merge can decide; it is
    left for the operator:

    - ``mixed_kinds``: a movie and a show (seasons cannot hang under a movie);
    - ``different_years``: two explicit years — a remake and its original;
    - ``conflicting_provider_ids``: one provider naming two different ids.

    Args:
        conn: Open SQLite connection.
        group: The group to judge.

    Returns:
        The reason, or ``None``.
    """
    member_ids = (group.keeper_id, *group.duplicate_ids)
    placeholders = ",".join("?" for _ in member_ids)
    rows = conn.execute(
        f"SELECT id, title, kind, year, external_ids_json FROM media_item WHERE id IN ({placeholders})",  # noqa: S608 — placeholders only
        member_ids,
    ).fetchall()
    if len({row[2] for row in rows}) > 1:
        return "mixed_kinds"
    years = {int(row[3]) for row in rows if row[3] is not None}
    if len(years) > 1:
        return "different_years"
    seen: dict[str, str] = {}
    for row in rows:
        for key, value in _provider_ids(row[4]).items():
            if seen.setdefault(key, value) != value:
                return "conflicting_provider_ids"
    return None


def merge_duplicate_items(conn: sqlite3.Connection, *, dry_run: bool, now_s: int | None = None) -> MergeReport:
    """Merge every group of items sharing a ``dispatch_path`` into its oldest item.

    A dry run lists the groups and writes nothing. Otherwise the whole merge
    runs in one transaction: either every group is merged or none is.

    Args:
        conn: Open SQLite connection (autocommit or not; the merge opens its
            own ``BEGIN IMMEDIATE``).
        dry_run: When ``True``, only report the groups.
        now_s: Epoch seconds stamped on the tombstones; defaults to now.

    Returns:
        The :class:`MergeReport`.
    """
    report = MergeReport()
    for group in find_duplicate_groups(conn):
        reason = _skip_reason(conn, group)
        if reason is not None:
            log.warning(
                "indexer.merge_items.group_skipped",
                dispatch_path=group.dispatch_path,
                ids=[group.keeper_id, *group.duplicate_ids],
                reason=reason,
            )
            report.skipped.append((group, reason))
            continue
        report.groups.append(group)

    if dry_run or not report.groups:
        return report

    stamp = int(time.time()) if now_s is None else now_s
    if conn.in_transaction:
        conn.commit()
    # item_repo.get_by_id switches the connection to sqlite3.Row; the caller's
    # factory is put back so its later reads keep the shape it chose.
    row_factory = conn.row_factory
    conn.execute("BEGIN IMMEDIATE")
    try:
        for group in report.groups:
            for duplicate_id in group.duplicate_ids:
                _merge_item(conn, duplicate_id, group.keeper_id, stamp)
                report.merged += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.row_factory = row_factory
    return report
