"""Decision writer for the ``scrape_decision`` table (scrape-arbiter feature).

Provides a durable, fail-soft writer for the interactive scraping decision
queue.  Each method opens a short-lived ``sqlite3`` connection, applies WAL
pragmas, performs its operation, commits, and closes — matching the indexer's
connection conventions.

Fail-soft vs fail-loud (coherence study F05/F29):

* The **pipeline-path** methods :meth:`DecisionWriter.upsert` and
  :meth:`DecisionWriter.mark_superseded_orphans` are **fail-soft** — a DB
  failure logs a warning and never raises, so a decision-write error can never
  abort the pipeline.
* The **operator-verdict** methods :meth:`DecisionWriter.resolve` and
  :meth:`DecisionWriter.dismiss` are **fail-loud**: they enforce the
  ``pending``-only state-machine transition (returning ``False`` when no
  pending row matched) and raise :class:`DecisionWriteError` on a DB error, so
  a silent "resolved OK" that never actually wrote the status is impossible.

Usage inside ``scraper/run.py``::

    from personalscraper.scraper.decision_writer import DecisionWriter

    writer = DecisionWriter(db_path)
    writer.upsert(staging_path, "movie", "Inception", 2010, "mid_band",
                  candidates_json, run_uid)
    writer.mark_superseded_orphans()

See docs/features/scrape-arbiter/DESIGN.md §4 for the writer contract and
§3 for the table schema.
"""

from __future__ import annotations

import json
import sqlite3
import time
import unicodedata
from pathlib import Path

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger

log = get_logger("decision_writer")


class DecisionWriteError(Exception):
    """Raised by the operator-verdict writer methods on an unrecoverable DB error.

    Only :meth:`DecisionWriter.resolve` and :meth:`DecisionWriter.dismiss` raise
    this — the pipeline-path methods stay fail-soft.  Callers (the scrape-resolve
    CLI, the dismiss route) map it to a non-zero exit / 5xx instead of silently
    reporting success (coherence study F05/F29).
    """


class DecisionWriter:
    """Durable decision writer for the ``scrape_decision`` table.

    Opens a short-lived ``sqlite3`` connection for each method call so that
    a DB failure never affects the pipeline's main loop.  All methods are
    fail-soft — they catch and log exceptions without re-raising.

    Args:
        db_path: Path to the indexer SQLite database (``library.db``).
    """

    def __init__(self, db_path: Path) -> None:
        """Store the DB path.

        Args:
            db_path: Path to the indexer SQLite database.
        """
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert(
        self,
        staging_path: Path | str,
        media_kind: str,
        extracted_title: str,
        extracted_year: int | None,
        trigger: str,
        candidates_json: str,
        run_uid: str | None,
    ) -> None:
        """Insert a new pending row or refresh an existing pending row.

        Normalizes *staging_path* to NFC before the upsert.  Uses
        ``INSERT ... ON CONFLICT(staging_path) DO UPDATE ... WHERE
        scrape_decision.status IN ('pending', 'superseded')``:

        * a **pending** row is refreshed (candidates/trigger/run_uid);
        * a **superseded** row is **revived** to ``pending`` (F07 recycle):
          the enqueue only runs for items that were just scanned (their path
          exists), so a folder re-created at a path a previous run superseded
          re-enters the queue instead of being blacklisted forever.  Its
          stale ``resolution_json`` / ``resolved_at`` are cleared and
          ``created_at`` is reset;
        * a **resolved** or **dismissed** row (an operator verdict) is
          **never** touched — the ``WHERE`` clause ignores the conflict.

        Args:
            staging_path: Absolute path to the staging item
                (NFC-normalized internally).
            media_kind: ``'movie'`` or ``'tvshow'``.
            extracted_title: Title guessed from the folder name.
            extracted_year: Year guessed, or ``None`` when unknown.
            trigger: Decision trigger (``'below_threshold'``,
                ``'mid_band'``, or ``'ambiguous'``).
            candidates_json: JSON array of scored
                :class:`DecisionCandidate` objects.
            run_uid: Run identifier that enqueued the row, or ``None``.
        """
        now = time.time()
        normalized = unicodedata.normalize("NFC", str(staging_path))
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                "INSERT INTO scrape_decision "
                "(staging_path, media_kind, extracted_title, extracted_year, "
                '"trigger", candidates_json, status, run_uid, created_at, updated_at) '
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?) "
                "ON CONFLICT(staging_path) DO UPDATE SET "
                "candidates_json = excluded.candidates_json, "
                '"trigger" = excluded."trigger", '
                "run_uid = excluded.run_uid, "
                "updated_at = excluded.updated_at, "
                # Revive a superseded row (F07): reset status + created_at and
                # clear the stale resolution fields. A pending row keeps its
                # own values (no-op branch).
                "status = 'pending', "
                "created_at = CASE WHEN scrape_decision.status = 'superseded' "
                "THEN excluded.created_at ELSE scrape_decision.created_at END, "
                "resolution_json = CASE WHEN scrape_decision.status = 'superseded' "
                "THEN NULL ELSE scrape_decision.resolution_json END, "
                "resolved_at = CASE WHEN scrape_decision.status = 'superseded' "
                "THEN NULL ELSE scrape_decision.resolved_at END "
                "WHERE scrape_decision.status IN ('pending', 'superseded')",
                (
                    normalized,
                    media_kind,
                    extracted_title,
                    extracted_year,
                    trigger,
                    candidates_json,
                    run_uid,
                    now,
                    now,
                ),
            )
            conn.commit()
        except Exception:
            log.warning(
                "decision_writer.upsert_failed",
                staging_path=normalized,
                media_kind=media_kind,
                trigger=trigger,
                run_uid=run_uid,
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def mark_superseded_orphans(self) -> None:
        """Mark pending rows whose staging path no longer exists on disk.

        Sets ``status = 'superseded'`` and ``updated_at = now`` for every
        row where ``status = 'pending'`` and the ``staging_path`` does not
        resolve to an existing filesystem entry.

        Run at enqueue time and listing time to garbage-collect rows for
        staging items that have been deleted or dispatched since the row
        was created.
        """
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            rows = conn.execute("SELECT id, staging_path FROM scrape_decision WHERE status = 'pending'").fetchall()
            now = time.time()
            superseded_ids: list[int] = []
            for row_id, path_str in rows:
                if not Path(path_str).exists():
                    superseded_ids.append(row_id)
            if superseded_ids:
                placeholders = ",".join("?" for _ in superseded_ids)
                conn.execute(
                    f"UPDATE scrape_decision SET status = 'superseded', updated_at = ? WHERE id IN ({placeholders})",
                    [now, *superseded_ids],
                )
            conn.commit()
        except Exception:
            log.warning(
                "decision_writer.mark_superseded_orphans_failed",
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def resolve(
        self,
        decision_id: int,
        provider: str,
        provider_id: int,
        via: str = "pick",
    ) -> bool:
        """Mark a *pending* decision as resolved with the chosen provider identity.

        Sets ``status = 'resolved'``, stores the resolution details in
        ``resolution_json``, and records the resolution timestamp — **only when
        the row is still ``pending``** (``WHERE id = ? AND status = 'pending'``),
        so a completed resolve cannot silently overwrite a concurrent dismiss and
        a terminal row is never mutated (F28/F33/F34).

        Args:
            decision_id: Primary key of the ``scrape_decision`` row.
            provider: Metadata provider name (``'tmdb'`` or ``'tvdb'``).
            provider_id: Numeric identifier assigned by the provider.
            via: Resolution method (``'pick'`` for a candidate selection,
                ``'search_override'`` for a manual search override).

        Returns:
            ``True`` when exactly one pending row was updated; ``False`` when the
            row was not pending (already resolved / dismissed / superseded /
            absent) — the caller decides how to surface a no-op.

        Raises:
            DecisionWriteError: On any DB error — this is fail-loud (F05/F29): a
                resolve that never wrote must not report success.
        """
        now = time.time()
        resolution = json.dumps({"provider": provider, "provider_id": provider_id, "via": via})
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            cur = conn.execute(
                "UPDATE scrape_decision "
                "SET status = 'resolved', resolution_json = ?, resolved_at = ?, updated_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (resolution, now, now, decision_id),
            )
            conn.commit()
            return cur.rowcount == 1
        except Exception as exc:
            log.error(
                "decision_writer.resolve_failed",
                decision_id=decision_id,
                provider=provider,
                provider_id=provider_id,
                via=via,
                exc_info=True,
            )
            raise DecisionWriteError(f"resolve({decision_id}) failed: {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def dismiss(self, decision_id: int) -> bool:
        """Mark a *pending* decision as dismissed (manual or MediaElch path).

        Sets ``status = 'dismissed'`` and ``updated_at = now`` **only when the
        row is still ``pending``** — a resolved row keeps its resolution record,
        and a dismiss racing an in-flight resolve cannot silently erase the
        operator's verdict (F28/F33).

        Args:
            decision_id: Primary key of the ``scrape_decision`` row.

        Returns:
            ``True`` when exactly one pending row was updated; ``False`` when the
            row was not pending.

        Raises:
            DecisionWriteError: On any DB error (fail-loud, F29).
        """
        now = time.time()
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            cur = conn.execute(
                "UPDATE scrape_decision SET status = 'dismissed', updated_at = ? WHERE id = ? AND status = 'pending'",
                (now, decision_id),
            )
            conn.commit()
            return cur.rowcount == 1
        except Exception as exc:
            log.error(
                "decision_writer.dismiss_failed",
                decision_id=decision_id,
                exc_info=True,
            )
            raise DecisionWriteError(f"dismiss({decision_id}) failed: {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
