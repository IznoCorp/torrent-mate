"""Remove the 0-file phantom rows of the provider-id duplicate groups (index rows only).

A phantom is a ``media_item`` row holding no live file in a duplicate group
(:func:`personalscraper.indexer.duplicates.find_provider_id_duplicates`) where at
least one other row holds live files — typically the canonical-title row created
beside an old "Title (YYYY)" row that holds the files. Removing it deletes the
index row and its empty seasons and episodes by cascade; no file on disk is
touched, a row holding a live file is never deleted, and a group whose every row
holds no file is left alone (an id is never emptied of its rows).

Each removal leaves a ``deleted_item`` tombstone with the row's columns, then a
``destructive_op`` journal row. :func:`phantom_rows` chooses the rows;
:func:`remove_phantom_rows` removes them. The CLI action
``library-remove-phantom-rows`` runs both, dry run unless ``--apply``.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path

from personalscraper.indexer.destructive_journal import OP_DELETE, record_destruction
from personalscraper.indexer.duplicates import _PROVIDER_ID_SQL, _PROVIDER_SQL, DuplicateGroup
from personalscraper.indexer.repos import log_repo
from personalscraper.indexer.schema import DeletedItemRow
from personalscraper.logger import get_logger

log = get_logger(__name__)

#: ``deleted_item.reason`` and ``destructive_op.actor`` of a removal.
_TOMBSTONE_REASON = "phantom_row_removed"
_JOURNAL_ACTOR = "maintenance"

# Whether an item holds at least one live file, through a movie release or an episode release.
_HOLDS_LIVE_FILES_SQL = """
SELECT EXISTS (
    SELECT 1 FROM media_file f
    JOIN media_release r ON r.id = f.release_id
    WHERE f.deleted_at IS NULL
      AND (r.item_id = :item_id
           OR r.episode_id IN (SELECT e.id FROM episode e JOIN season s ON s.id = e.season_id
                               WHERE s.item_id = :item_id))
)
"""

# The rows of the same duplicate group as :item_id (same kind, provider and provider id, as
# ``find_provider_id_duplicates`` keys them), other than itself, that hold a live file.
_SIBLING_HOLDS_LIVE_FILES_SQL = f"""
WITH keyed AS (
    SELECT id, kind, {_PROVIDER_SQL} AS provider, {_PROVIDER_ID_SQL} AS provider_id FROM media_item
)
SELECT EXISTS (
    SELECT 1 FROM keyed me JOIN keyed sib
      ON sib.kind = me.kind AND sib.provider = me.provider
         AND lower(trim(sib.provider_id)) = lower(trim(me.provider_id)) AND sib.id != me.id
    WHERE me.id = :item_id
      AND EXISTS (
        SELECT 1 FROM media_file f
        JOIN media_release r ON r.id = f.release_id
        WHERE f.deleted_at IS NULL
          AND (r.item_id = sib.id
               OR r.episode_id IN (SELECT e.id FROM episode e JOIN season s ON s.id = e.season_id
                                   WHERE s.item_id = sib.id))
      )
)
"""


def phantom_rows(groups: Sequence[DuplicateGroup]) -> list[int]:
    """In each group holding ≥ 1 row with live files: the rows with 0 live files (never a row with files).

    Args:
        groups: The provider-id duplicate groups.

    Returns:
        The phantom ``media_item`` ids, in group order then row order; empty when none.
    """
    phantoms: list[int] = []
    for group in groups:
        if any(row.live_files > 0 for row in group.rows):
            phantoms.extend(row.item_id for row in group.rows if row.live_files == 0)
    return phantoms


def _removable(conn: sqlite3.Connection, item_id: int) -> bool:
    """Return whether *item_id* still exists, holds no live file, and a sibling of its group does.

    The sibling clause keeps the module's promise that an id is never emptied of its
    rows, even when the plan is stale (a scan tombstoned the sibling's files) or the
    caller passed the wrong ids.

    Args:
        conn: Open connection on the indexer database.
        item_id: ``media_item.id`` to check.

    Returns:
        ``True`` when the row exists, none of its files is live, and at least one other
        row of the same provider id and kind still holds a live file.
    """
    if conn.execute("SELECT 1 FROM media_item WHERE id = ?", (item_id,)).fetchone() is None:
        return False
    if item_holds_live_files(conn, item_id):
        return False
    return bool(conn.execute(_SIBLING_HOLDS_LIVE_FILES_SQL, {"item_id": item_id}).fetchone()[0])


def item_holds_live_files(conn: sqlite3.Connection, item_id: int) -> bool:
    """Return whether *item_id* holds a live file, through a movie release or an episode release.

    Args:
        conn: Open connection on the indexer database.
        item_id: ``media_item.id`` to check.

    Returns:
        ``True`` when at least one ``media_file`` of the item has no ``deleted_at``.
    """
    return bool(conn.execute(_HOLDS_LIVE_FILES_SQL, {"item_id": item_id}).fetchone()[0])


def journal_item_removal(db_path: Path, item_id: int, *, run_uid: str) -> None:
    """Write the ``destructive_op`` journal row of a removed ``media_item`` (best-effort).

    Args:
        db_path: Path of the indexer database, for the journal's own connection.
        item_id: The row that was deleted.
        run_uid: The run correlating the journal rows.
    """
    record_destruction(db_path, op=OP_DELETE, path=f"index:media_item/{item_id}", actor=_JOURNAL_ACTOR, run_uid=run_uid)


def _tombstone(conn: sqlite3.Connection, item_id: int, now: int) -> None:
    """Write the phantom-row tombstone of *item_id* (see :func:`tombstone_item`).

    Args:
        conn: Open connection inside the removal's transaction.
        item_id: The row about to be deleted.
        now: Epoch seconds of the removal.
    """
    tombstone_item(conn, item_id, now, reason=_TOMBSTONE_REASON)


def tombstone_item(conn: sqlite3.Connection, item_id: int, now: int, *, reason: str) -> None:
    """Write the ``deleted_item`` tombstone of *item_id* with a snapshot of its columns.

    Args:
        conn: Open connection inside the removal's transaction.
        item_id: The row about to be deleted.
        now: Epoch seconds of the removal.
        reason: ``deleted_item.reason`` of the removal.
    """
    cursor = conn.execute("SELECT * FROM media_item WHERE id = ?", (item_id,))
    columns = [d[0] for d in cursor.description]
    snapshot = dict(zip(columns, cursor.fetchone(), strict=True))
    log_repo.insert_deleted_item(
        conn,
        DeletedItemRow(
            id=0,  # ignored on insert
            kind="item",
            original_id=item_id,
            deleted_at=now,
            reason=reason,
            payload_json=json.dumps({"kind": "item", "snapshot": snapshot}),
        ),
    )


def remove_phantom_rows(
    conn: sqlite3.Connection, item_ids: Sequence[int], *, db_path: Path, run_uid: str, dry_run: bool
) -> int:
    """Delete those media_item rows (tombstone as today) and journal each; files untouched.

    Each id is checked again before it is deleted: a row that no longer exists or
    holds a live file, or whose group has no other row holding one, is skipped
    (logged), never deleted. The deletions run in one transaction; the journal rows (``record_destruction(op="delete",
    path="index:media_item/<id>", actor="maintenance")``) are written after it
    commits, through the journal's own connection.

    Args:
        conn: Open connection on the indexer database with ``foreign_keys=ON`` and no
            open transaction.
        item_ids: The rows to remove (from :func:`phantom_rows`).
        db_path: Path of the same database, for the journal.
        run_uid: The run correlating the journal rows.
        dry_run: When ``True``, count the rows that would be removed and write nothing.

    Returns:
        The number of rows removed (would be removed, in a dry run).

    Raises:
        Exception: Whatever fails inside the transaction (a ``sqlite3.Error`` or any
            other); it is rolled back, nothing is removed, and the error propagates.
    """
    candidates = list(dict.fromkeys(item_ids))
    if dry_run:
        doomed = [item_id for item_id in candidates if _removable(conn, item_id)]
        log.info("indexer.phantom_rows.plan", dry_run=True, rows=doomed)
        return len(doomed)

    now = int(time.time())
    doomed = []
    conn.execute("BEGIN IMMEDIATE")
    try:
        for item_id in candidates:
            if not _removable(conn, item_id):
                log.warning("indexer.phantom_rows.skipped", item_id=item_id)
                continue
            _tombstone(conn, item_id, now)
            conn.execute("DELETE FROM media_item WHERE id = ?", (item_id,))
            doomed.append(item_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    for item_id in doomed:
        journal_item_removal(db_path, item_id, run_uid=run_uid)
        log.info("indexer.phantom_rows.removed", item_id=item_id, run_uid=run_uid)
    return len(doomed)
