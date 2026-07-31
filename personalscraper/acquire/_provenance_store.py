"""Provenance sub-store — the advisory staging registry (feature ``provenance``, F0).

Records the journey of a **follow-driven** acquisition through the pipeline
(grab → ingest → sort/rename → scrape → dispatch) so the scrape can resolve
identity DETERMINISTICALLY (#30) instead of re-inferring it from the renamed
folder. Keyed on the torrent info-hash (one hash = one staging folder, even for a
season-pack that spans many ``wanted`` rows).

ADVISORY OVERLAY — the filesystem stays the source of truth:

- **Every write is best-effort**: an error is logged and swallowed, NEVER raised
  to a pipeline step (a provenance write must never fail a grab/ingest/dispatch).
- **Only :meth:`_ProvenanceSubStore.upsert_grab` creates a row**, and it is called
  ONLY for a follow-driven grab (a ``wanted`` item with a known identity). Every
  other method is UPDATE-only — a no-op when no row exists. So a **manual/direct
  torrent** (no wanted → no ``upsert_grab``) gets NO row and no method touches it
  (ACC-06), in BOTH senses: a torrent added straight into qBittorrent, and any
  personalscraper grab launched without a follow.
- **Reads are fail-soft**: any error → ``None`` (the caller falls back to the #29
  inference, then free match).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from personalscraper.acquire._store_rows import _media_ref_from_json, _media_ref_to_json
from personalscraper.core.identity import MediaRef
from personalscraper.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class ProvenanceRow:
    """One acquisition's provenance record (a row of ``staging_provenance``)."""

    info_hash: str
    followed_id: int | None
    media_ref: MediaRef | None
    kind: str | None
    ingest_path: str | None
    current_path: str | None
    scraped_ref: MediaRef | None
    dispatch_path: str | None
    grabbed_at: int | None
    ingested_at: int | None
    scraped_at: int | None
    dispatched_at: int | None
    status: str | None


def _row_to_provenance(row: sqlite3.Row) -> ProvenanceRow:
    """Decode a ``staging_provenance`` row into a :class:`ProvenanceRow` VO."""
    media_json = row["media_ref_json"]
    scraped_json = row["scraped_ref_json"]
    return ProvenanceRow(
        info_hash=row["info_hash"],
        followed_id=row["followed_id"],
        media_ref=_media_ref_from_json(media_json) if media_json else None,
        kind=row["kind"],
        ingest_path=row["ingest_path"],
        current_path=row["current_path"],
        scraped_ref=_media_ref_from_json(scraped_json) if scraped_json else None,
        dispatch_path=row["dispatch_path"],
        grabbed_at=row["grabbed_at"],
        ingested_at=row["ingested_at"],
        scraped_at=row["scraped_at"],
        dispatched_at=row["dispatched_at"],
        status=row["status"],
    )


class _ProvenanceSubStore:
    """Advisory writer + reader for ``staging_provenance`` (all writes best-effort)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        write_tx: Callable[[sqlite3.Connection], AbstractContextManager[None]],
    ) -> None:
        """Initialise with the shared connection and the write-transaction factory.

        Args:
            conn: The shared ``acquire.db`` connection.
            write_tx: The ``_write_tx`` context-manager factory (BEGIN IMMEDIATE).
        """
        self._conn = conn
        self._write_tx = write_tx

    # -- writes (best-effort: an error NEVER escapes to the pipeline step) -------

    def _safe_write(self, sql: str, params: tuple[object, ...]) -> None:
        """Run one write in its own transaction, swallowing any error (advisory)."""
        try:
            with self._write_tx(self._conn):
                self._conn.execute(sql, params)
        except Exception as exc:  # noqa: BLE001 — advisory: a provenance write never fails a step
            log.warning("acquire.provenance.write_failed", error=str(exc))

    def upsert_grab(
        self,
        info_hash: str,
        *,
        followed_id: int | None,
        media_ref: MediaRef | None,
        kind: str | None,
        grabbed_at: int,
    ) -> None:
        """Create/refresh the row for a FOLLOW-DRIVEN grab (the identity seed).

        The ONLY row-creating method — called exclusively when a grab carries a
        wanted-derived identity. A manual/direct grab never reaches here, so it
        never gets a row (ACC-06).
        """
        self._safe_write(
            """
            INSERT INTO staging_provenance
              (info_hash, followed_id, media_ref_json, kind, grabbed_at, status)
            VALUES (?, ?, ?, ?, ?, 'grabbed')
            ON CONFLICT(info_hash) DO UPDATE SET
              followed_id    = excluded.followed_id,
              media_ref_json = excluded.media_ref_json,
              kind           = excluded.kind,
              grabbed_at     = excluded.grabbed_at,
              status         = 'grabbed'
            """,
            (
                info_hash.lower(),
                followed_id,
                _media_ref_to_json(media_ref) if media_ref is not None else None,
                kind,
                grabbed_at,
            ),
        )

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int) -> None:
        """Record the staging folder at ingest (UPDATE-only — no-op if untracked)."""
        self._safe_write(
            "UPDATE staging_provenance SET ingest_path = ?, current_path = ?, "
            "ingested_at = ?, status = 'ingested' WHERE info_hash = ?",
            (ingest_path, ingest_path, ingested_at, info_hash.lower()),
        )

    def set_current_path(self, info_hash: str, *, path: str) -> None:
        """Keep ``current_path`` live across a sort/rename (UPDATE-only)."""
        self._safe_write(
            "UPDATE staging_provenance SET current_path = ? WHERE info_hash = ?",
            (path, info_hash.lower()),
        )

    def set_scraped(self, info_hash: str, *, scraped_ref: MediaRef | None, scraped_at: int) -> None:
        """Record the identity actually scraped (audit; UPDATE-only)."""
        self._safe_write(
            "UPDATE staging_provenance SET scraped_ref_json = ?, scraped_at = ?, "
            "status = 'scraped' WHERE info_hash = ?",
            (
                _media_ref_to_json(scraped_ref) if scraped_ref is not None else None,
                scraped_at,
                info_hash.lower(),
            ),
        )

    def set_dispatch(self, info_hash: str, *, dispatch_path: str, dispatched_at: int) -> None:
        """Record the final destination at dispatch (UPDATE-only)."""
        self._safe_write(
            "UPDATE staging_provenance SET dispatch_path = ?, dispatched_at = ?, "
            "status = 'dispatched' WHERE info_hash = ?",
            (dispatch_path, dispatched_at, info_hash.lower()),
        )

    # -- path-keyed writes (pipeline steps work on folders, not hashes) ---------

    def move_path(self, old_path: str, new_path: str) -> None:
        """Re-point a tracked folder from *old_path* to *new_path* (sort/rename).

        Keyed on ``current_path`` so a pipeline step that only knows the folder
        (not the hash) keeps the join key live across a move. UPDATE-only — a
        no-op when the moved folder is untracked (a manual/direct item).
        """
        self._safe_write(
            "UPDATE staging_provenance SET current_path = ? WHERE current_path = ?",
            (new_path, old_path),
        )

    def record_dispatch_by_path(self, staging_path: str, *, dispatch_path: str, dispatched_at: int) -> None:
        """Record the dispatch of the folder currently at *staging_path* (UPDATE-only).

        Keyed on ``current_path`` (the live staging folder) so dispatch needs no
        hash. No-op when untracked.
        """
        self._safe_write(
            "UPDATE staging_provenance SET dispatch_path = ?, dispatched_at = ?, "
            "status = 'dispatched' WHERE current_path = ?",
            (dispatch_path, dispatched_at, staging_path),
        )

    # -- reads (fail-soft: None on any error) -----------------------------------

    def by_hash(self, info_hash: str) -> ProvenanceRow | None:
        """Return the row for *info_hash*, or ``None`` (fail-soft)."""
        return self._read_one("WHERE info_hash = ?", (info_hash.lower(),))

    def by_path(self, path: str) -> ProvenanceRow | None:
        """Return the row whose ``current_path`` equals *path*, or ``None``.

        The #30 scrape consumer's join: a staging folder → its provenance seed.
        """
        return self._read_one("WHERE current_path = ?", (path,))

    def _read_one(self, where: str, params: tuple[object, ...]) -> ProvenanceRow | None:
        """Fetch one row for *where*/*params*, fail-soft (``None`` on any error)."""
        try:
            self._conn.row_factory = sqlite3.Row
            row = self._conn.execute(
                f"SELECT * FROM staging_provenance {where}",
                params,  # noqa: S608 — fixed literals
            ).fetchone()
            return _row_to_provenance(row) if row is not None else None
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error is a miss, never a crash
            log.warning("acquire.provenance.read_failed", error=str(exc))
            return None

    def prune_stale(self, exists_fn: Callable[[str], bool]) -> int:
        """Delete rows whose ``current_path`` no longer exists on disk (FS = truth).

        The FS is NEVER mutated to match the DB — only the DB is pruned. Best-effort.

        Args:
            exists_fn: Predicate ``path -> bool`` (typically ``os.path.exists``).

        Returns:
            The count of rows pruned (0 on any error).
        """
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT info_hash, current_path FROM staging_provenance WHERE current_path IS NOT NULL"
            ).fetchall()
            stale = [r["info_hash"] for r in rows if not exists_fn(r["current_path"])]
            for info_hash in stale:
                self._safe_write("DELETE FROM staging_provenance WHERE info_hash = ?", (info_hash,))
            return len(stale)
        except Exception as exc:  # noqa: BLE001 — advisory prune never crashes a caller
            log.warning("acquire.provenance.prune_failed", error=str(exc))
            return 0
