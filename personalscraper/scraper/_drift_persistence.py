"""Helpers for persisting / clearing detected drift records in ``item_issue``.

Encapsulated as :class:`DriftIssueStore` so the config→db resolution + the
connection lifecycle are factored out of individual call sites.

Forward-imported by the scrape flow at call sites:

    store = DriftIssueStore.from_config(self.config)
    if store is not None:
        store.persist(show_dir, drift_reason)
        # ... later ...
        store.clear(show_dir)
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("scraper.drift_persistence")


class DriftIssueStore:
    """Persists / clears scrape-detected drift records in ``item_issue``.

    Construct via :meth:`from_config` — returns ``None`` when the database
    is unavailable. All operations are best-effort and fail-soft (log,
    no exception propagation).
    """

    def __init__(self, db_file: Path) -> None:
        self._db_file = db_file

    @classmethod
    def from_config(cls, config: "Config | None") -> "DriftIssueStore | None":
        """Resolve the indexer DB path from config; return None if unavailable.

        Performs the defensive checks once at construction:
        - config is None → skip (logged)
        - config.indexer.db_path is None → skip (logged)
        - db_path is not str/Path (MagicMock test stub) → skip (logged)
        - db_file does not exist on disk → skip (no log; legitimate
          unconfigured state for fresh staging)
        """
        if config is None:
            log.info("drift_store_unavailable", reason="config_is_none")
            return None
        db_path = config.indexer.db_path
        if db_path is None:
            log.info("drift_store_unavailable", reason="db_path_is_none")
            return None
        if isinstance(db_path, str):
            db_path = Path(db_path)
        if not isinstance(db_path, Path):
            log.info(
                "drift_store_unavailable",
                reason="db_path_not_path",
                type=type(db_path).__name__,
            )
            return None
        db_file = db_path.expanduser()
        if not db_file.is_absolute():
            db_file = Path.cwd() / db_file
        if not db_file.is_file():
            return None
        return cls(db_file)

    def persist(self, show_dir: Path, drift_reason: str) -> None:
        """Insert (or ignore) an ``item_issue`` row for the show's drift."""
        with self._open_conn() as conn:
            if conn is None:
                return
            try:
                row = conn.execute(
                    "SELECT m.id FROM media_item m "
                    "JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
                    "WHERE ia.value = ?",
                    (str(show_dir.resolve()),),
                ).fetchone()
                if row is None:
                    log.info("item_issue_persist_skipped_no_item", path=str(show_dir))
                    return
                item_id = row["id"]
                conn.execute(
                    "INSERT OR IGNORE INTO item_issue (item_id, type, detail, detected_at) "
                    "VALUES (?, 'episode_naming_drift', ?, unixepoch())",
                    (item_id, drift_reason),
                )
                conn.commit()
                log.info(
                    "item_issue_persisted",
                    item_id=item_id,
                    drift_reason=drift_reason,
                    path=str(show_dir),
                )
            except Exception:
                log.warning(
                    "item_issue_persist_failed",
                    path=str(show_dir),
                    exc_info=True,
                )

    def clear(self, show_dir: Path) -> None:
        """Delete any ``item_issue`` rows of type 'episode_naming_drift'."""
        with self._open_conn() as conn:
            if conn is None:
                return
            try:
                row = conn.execute(
                    "SELECT m.id FROM media_item m "
                    "JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
                    "WHERE ia.value = ?",
                    (str(show_dir.resolve()),),
                ).fetchone()
                if row is None:
                    return
                item_id = row["id"]
                conn.execute(
                    "DELETE FROM item_issue WHERE item_id = ? AND type = 'episode_naming_drift'",
                    (item_id,),
                )
                conn.commit()
            except Exception:
                log.warning(
                    "item_issue_clear_failed",
                    path=str(show_dir),
                    exc_info=True,
                )

    @contextmanager
    def _open_conn(self) -> Iterator[sqlite3.Connection | None]:
        """Yield a configured sqlite3 connection (or None on connect failure).

        Connect failures are logged (not silenced) so operators can
        diagnose missing/corrupt DBs. The connection is closed in finally.
        """
        from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

        try:
            conn = sqlite3.connect(str(self._db_file))
            _apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
        except Exception:
            log.warning(
                "item_issue_db_connect_failed",
                path=str(self._db_file),
                exc_info=True,
            )
            yield None
            return
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass
