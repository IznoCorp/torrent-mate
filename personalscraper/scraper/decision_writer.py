"""Decision writer for the ``scrape_decision`` table (scrape-arbiter feature).

Provides a durable, fail-soft writer for the interactive scraping decision
queue.  Each method opens a short-lived ``sqlite3`` connection, applies WAL
pragmas, performs its operation, commits, and closes — matching the indexer's
connection conventions.

The writer is **fail-soft**: every method wraps its DB work in a try/except,
logs a warning on failure, and never raises.  A decision-write error must
never abort the pipeline.

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
        scrape_decision.status='pending'`` — a resolved, dismissed, or
        superseded row is **never** resurrected (the ``WHERE`` clause
        causes the conflict to be silently ignored for non-pending rows,
        unlike ``INSERT OR REPLACE`` which would clobber the status).

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
                "updated_at = excluded.updated_at "
                "WHERE scrape_decision.status = 'pending'",
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
    ) -> None:
        """Mark a decision as resolved with the chosen provider identity.

        Sets ``status = 'resolved'``, stores the resolution details in
        ``resolution_json``, and records the resolution timestamp.

        Args:
            decision_id: Primary key of the ``scrape_decision`` row.
            provider: Metadata provider name (``'tmdb'`` or ``'tvdb'``).
            provider_id: Numeric identifier assigned by the provider.
            via: Resolution method (``'pick'`` for a candidate selection,
                ``'search_override'`` for a manual search override).
        """
        now = time.time()
        resolution = json.dumps({"provider": provider, "provider_id": provider_id, "via": via})
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                "UPDATE scrape_decision "
                "SET status = 'resolved', resolution_json = ?, resolved_at = ?, updated_at = ? "
                "WHERE id = ?",
                (resolution, now, now, decision_id),
            )
            conn.commit()
        except Exception:
            log.warning(
                "decision_writer.resolve_failed",
                decision_id=decision_id,
                provider=provider,
                provider_id=provider_id,
                via=via,
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def dismiss(self, decision_id: int) -> None:
        """Mark a decision as dismissed (manual or MediaElch path).

        Sets ``status = 'dismissed'`` and ``updated_at = now``.  The
        operator is expected to handle the item outside the pipeline
        (e.g. via MediaElch).

        Args:
            decision_id: Primary key of the ``scrape_decision`` row.
        """
        now = time.time()
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                "UPDATE scrape_decision SET status = 'dismissed', updated_at = ? WHERE id = ?",
                (now, decision_id),
            )
            conn.commit()
        except Exception:
            log.warning(
                "decision_writer.dismiss_failed",
                decision_id=decision_id,
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass
