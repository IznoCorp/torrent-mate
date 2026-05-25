"""Helpers for persisting / clearing detected drift records in ``item_issue``.

Extracted from ``tv_service.py`` to keep that module under 800 LOC
(CLAUDE.md).  Forward-imported by the scrape flow at call sites.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("scraper.drift_persistence")


def persist_drift_issue(config: "Config | None", show_dir: Path, drift_reason: str) -> None:
    """Persist a detected scrape drift as an ``item_issue`` row for audit trail.

    Best-effort only — if the database is unavailable or the show has no
    ``media_item`` row yet, the drift is logged but no row is inserted.

    Args:
        config: Application config (may be None if unconfigured).
        show_dir: Absolute path to the TV show directory.
        drift_reason: Human-readable drift reason string.
    """
    if config is None:
        log.info("item_issue_persist_skipped_no_db", reason="config_is_none")
        return
    db_path = config.indexer.db_path
    if db_path is None:
        log.info("item_issue_persist_skipped_no_db", reason="db_path_is_none")
        return
    if isinstance(db_path, str):
        db_path = Path(db_path)
    if not isinstance(db_path, Path):
        log.info(
            "item_issue_persist_skipped_db_path_not_path",
            reason="config.indexer.db_path is not a string or Path (likely MagicMock test stub)",
            type=type(db_path).__name__,
        )
        return
    db_file = db_path.expanduser()
    if not db_file.is_absolute():
        from pathlib import Path as _Path

        db_file = _Path.cwd() / db_file
    if not db_file.is_file():
        log.info("item_issue_persist_skipped_no_db", db_path=str(db_file))
        return

    try:
        from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

        conn = sqlite3.connect(str(db_file))
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
    except Exception:
        log.warning("item_issue_persist_db_connect_failed", db_path=str(db_file), exc_info=True)
        return
    try:
        row = conn.execute(
            "SELECT m.id FROM media_item m "
            "JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
            "WHERE ia.value = ?",
            (str(show_dir.resolve()),),
        ).fetchone()
        if row is None:
            log.info("item_issue_persist_skipped_no_item", path=str(show_dir.resolve()))
            return
        item_id = row["id"]
        now_s = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO item_issue (item_id, type, detail, detected_at) "
            "VALUES (?, 'episode_naming_drift', ?, ?)",
            (item_id, drift_reason, now_s),
        )
        conn.commit()
    except Exception:
        log.warning("item_issue_persist_failed", path=str(show_dir), exc_info=True)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def clear_drift_issue(config: "Config | None", show_dir: Path) -> None:
    """Clear a previously persisted drift issue after a successful rescrape.

    Idempotent — if no drift row exists the DELETE is a no-op.

    Args:
        config: Application config (may be None if unconfigured).
        show_dir: Absolute path to the TV show directory.
    """
    if config is None:
        return
    db_path = config.indexer.db_path
    if db_path is None:
        return
    if isinstance(db_path, str):
        db_path = Path(db_path)
    if not isinstance(db_path, Path):
        log.info(
            "item_issue_clear_skipped_db_path_not_path",
            reason="config.indexer.db_path is not a string or Path (likely MagicMock test stub)",
            type=type(db_path).__name__,
        )
        return
    db_file = db_path.expanduser()
    if not db_file.is_absolute():
        from pathlib import Path as _Path

        db_file = _Path.cwd() / db_file
    if not db_file.is_file():
        return

    try:
        from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

        conn = sqlite3.connect(str(db_file))
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
    except Exception:
        log.warning("item_issue_clear_db_connect_failed", path=str(show_dir), exc_info=True)
        return
    try:
        row = conn.execute(
            "SELECT m.id FROM media_item m "
            "JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
            "WHERE ia.value = ?",
            (str(show_dir.resolve()),),
        ).fetchone()
        if row is not None:
            item_id = row["id"]
            conn.execute(
                "DELETE FROM item_issue WHERE item_id = ? AND type = 'episode_naming_drift'",
                (item_id,),
            )
            conn.commit()
    except Exception:
        log.warning("item_issue_clear_failed", path=str(show_dir), exc_info=True)
    finally:
        try:
            conn.close()
        except Exception:
            pass
