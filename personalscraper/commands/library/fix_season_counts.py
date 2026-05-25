"""Repair season.episode_count drift (DEVIATION #9, invariant AP).

Some ``season`` rows have an ``episode_count`` cached value that doesn't
match the actual ``COUNT(*)`` of rows in the ``episode`` table. This command
recalculates and repairs those incorrect counts.

As of migration 008, ``season.episode_count`` is auto-maintained by triggers
(``trg_season_episode_count_after_{insert,delete,update}``). This CLI remains
available as a safety net for trigger-bypass paths (manual sqlite3 writes,
partially-applied migrations), not a pre-migration tool.

Dry-run by default — use ``--apply`` to execute the UPDATE.
Re-running is a no-op because the WHERE clause only targets drifting rows.

Examples:
    personalscraper library-fix-season-counts
    personalscraper library-fix-season-counts --apply
    personalscraper library-fix-season-counts --db /custom/path/library.db --apply
"""

from __future__ import annotations

import sqlite3 as _sqlite3
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.commands.library._fix_stats_base import CliFixStatsMixin
from personalscraper.logger import get_logger

log = get_logger("cli")

_DRIFT_SELECT_SQL = """
SELECT s.id, s.item_id, s.number, s.episode_count AS old_count,
       (SELECT COUNT(*) FROM episode e WHERE e.season_id = s.id) AS actual_count
FROM season s
WHERE s.episode_count != (SELECT COUNT(*) FROM episode e WHERE e.season_id = s.id)
"""

_SEASONS_TOTAL_SQL = "SELECT COUNT(*) FROM season"

_UPDATE_SQL = """
UPDATE season
SET episode_count = (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
WHERE episode_count != (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
"""


@dataclass
class FixSeasonCountsStats(CliFixStatsMixin):
    """Counters for ``library_fix_season_counts``.

    ``seasons_scanned`` is the total number of rows in the ``season`` table.
    ``fixed`` tracks the number of seasons whose ``episode_count`` was corrected
    (or would be corrected in dry-run mode).
    ``details`` lists per-season drift data for operator inspection (dry-run only).
    """

    seasons_scanned: int = 0
    fixed: int = 0
    details: list[dict[str, int]] = field(default_factory=list)

    def snapshot(self) -> "FixSeasonCountsStats":
        """Return an independent (non-aliased) copy — safe to hand to log emitters that may mutate."""
        return replace(self, details=list(self.details))

    def to_cli_json(self, *, apply: bool) -> dict[str, Any]:
        """Project to the CLI JSON output shape.

        Args:
            apply: Whether ``--apply`` was passed. Controls the key name
                (``"fixed"`` vs ``"would_fix"``).

        Returns:
            Dict with ``apply`` flag, ``seasons_scanned``, count key, and
            ``details`` list.
        """
        key = "fixed" if apply else "would_fix"
        return {
            "apply": apply,
            "seasons_scanned": self.seasons_scanned,
            key: self.fixed,
            "details": self.details,
        }

    def to_log_dict(self) -> dict[str, int]:
        """Project to a ``dict[str, int]`` suitable for structlog ``stats=``."""
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != "details"}


@app.command("library-fix-season-counts")
@handle_cli_errors
def library_fix_season_counts(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (default: dry-run preview)."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Repair season.episode_count drift where cached count != actual episode rows.

    Compares each season's ``episode_count`` against the actual number of
    ``episode`` rows and repairs any mismatch. The UPDATE is predicate-guarded
    so re-running the command is a no-op.

    Dry-run by default — use ``--apply`` to execute the UPDATE.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415

    cfg = ctx.obj.config if ctx.obj is not None else load_config(config)

    if db is not None:
        db_path = db
    elif cfg.indexer.db_path is not None:
        db_path = Path(cfg.indexer.db_path)
    else:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)

    from personalscraper.indexer.db import _apply_pragmas as _db_apply_pragmas  # noqa: PLC0415

    conn = _sqlite3.connect(str(db_path))
    _db_apply_pragmas(conn)
    conn.row_factory = _sqlite3.Row

    stats = FixSeasonCountsStats()

    log.info("season_count_fix_scan_started")

    total_row = conn.execute(_SEASONS_TOTAL_SQL).fetchone()
    stats.seasons_scanned = total_row[0] if total_row is not None else 0

    if apply:
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(_UPDATE_SQL)
            stats.fixed = cur.rowcount if cur.rowcount >= 0 else 0
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        try:
            drifting = conn.execute(_DRIFT_SELECT_SQL).fetchall()
            stats.fixed = len(drifting)
            for row in drifting:
                stats.details.append(
                    {
                        "item_id": int(row["item_id"]),
                        "number": int(row["number"]),
                        "old_count": int(row["old_count"]),
                        "actual_count": int(row["actual_count"]),
                    }
                )
        finally:
            conn.close()

    log.info("season_count_fix_done", stats=stats.to_log_dict())

    emit(stats.snapshot().to_cli_json(apply=apply))
