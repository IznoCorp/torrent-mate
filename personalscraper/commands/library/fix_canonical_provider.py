"""Repair canonical_provider corruption in media_item rows (DEVIATION #7, ACC #4).

Some ``media_item`` rows have an incorrect ``canonical_provider`` column:
- ``kind='show'`` rows with ``canonical_provider='tmdb'`` that actually have a
  valid ``tvdb.series_id`` in ``external_ids_json``.
- ``kind='movie'`` rows with ``canonical_provider IS NULL`` that actually have
  a valid ``tmdb.id`` in ``external_ids_json``.

The command runs two idempotent SQL UPDATE statements inside a single transaction.
Re-running the command produces 0 additional fixes because the WHERE clauses only
target rows that are still in the wrong state.

Dry-run by default — use ``--apply`` to execute the UPDATE.

Examples:
    personalscraper library-fix-canonical-provider
    personalscraper library-fix-canonical-provider --apply
    personalscraper library-fix-canonical-provider --db /custom/path/library.db --apply
"""

from __future__ import annotations

import sqlite3 as _sqlite3
from dataclasses import dataclass, fields, replace
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.logger import get_logger

log = get_logger("cli")

_SHOWS_REPAIR_SQL = """
UPDATE media_item SET canonical_provider='tvdb'
WHERE kind='show' AND canonical_provider='tmdb'
  AND json_extract(external_ids_json, '$.tvdb.series_id') IS NOT NULL
"""

_SHOWS_COUNT_SQL = """
SELECT COUNT(*) FROM media_item
WHERE kind='show' AND canonical_provider='tmdb'
  AND json_extract(external_ids_json, '$.tvdb.series_id') IS NOT NULL
"""

_MOVIES_REPAIR_SQL = """
UPDATE media_item SET canonical_provider='tmdb'
WHERE kind='movie' AND canonical_provider IS NULL
  AND json_extract(external_ids_json, '$.tmdb.id') IS NOT NULL
"""

_MOVIES_COUNT_SQL = """
SELECT COUNT(*) FROM media_item
WHERE kind='movie' AND canonical_provider IS NULL
  AND json_extract(external_ids_json, '$.tmdb.id') IS NOT NULL
"""


@dataclass
class FixCanonicalProviderStats:
    """Counters for ``library_fix_canonical_provider``.

    ``shows_fixed`` tracks ``kind='show'`` rows repaired (canonical_provider
    switched from ``'tmdb'`` to ``'tvdb'``).  ``movies_fixed`` tracks
    ``kind='movie'`` rows repaired (canonical_provider set from ``NULL`` to
    ``'tmdb'``).
    """

    shows_fixed: int = 0
    movies_fixed: int = 0

    def frozen(self) -> "FixCanonicalProviderStats":
        """Return an independent copy (defensive for downstream emitters)."""
        return replace(self)

    def to_cli_json(self, *, apply: bool) -> dict[str, int | bool]:
        """Project to the CLI JSON output shape.

        Args:
            apply: Whether ``--apply`` was passed. Controls the key prefix
                (``"would_fix_"`` vs ``"fixed_"``).

        Returns:
            Dict with ``apply`` flag and the relevant count keys.
        """
        if apply:
            return {
                "apply": True,
                "fixed_shows": self.shows_fixed,
                "fixed_movies": self.movies_fixed,
            }
        return {
            "apply": False,
            "would_fix_shows": self.shows_fixed,
            "would_fix_movies": self.movies_fixed,
        }

    def to_log_dict(self) -> dict[str, int]:
        """Project to a ``dict[str, int]`` suitable for structlog ``stats=``."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


@app.command("library-fix-canonical-provider")
@handle_cli_errors
def library_fix_canonical_provider(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (default: dry-run preview)."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Repair incorrect canonical_provider values in media_item rows.

    Fixes two classes of corruption:
    - TV shows wrongly marked ``canonical_provider='tmdb'`` when a valid
      ``tvdb.series_id`` exists in ``external_ids_json``.
    - Movies with ``canonical_provider IS NULL`` when a valid ``tmdb.id``
      exists in ``external_ids_json``.

    Dry-run by default — use ``--apply`` to execute the UPDATE statements.
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

    stats = FixCanonicalProviderStats()

    log.info("canonical_provider_fix_scan_started")

    if apply:
        # Execute both UPDATE statements in a single transaction.
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(_SHOWS_REPAIR_SQL)
            stats.shows_fixed = cur.rowcount if cur.rowcount >= 0 else 0
            cur = conn.execute(_MOVIES_REPAIR_SQL)
            stats.movies_fixed = cur.rowcount if cur.rowcount >= 0 else 0
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        try:
            row = conn.execute(_SHOWS_COUNT_SQL).fetchone()
            stats.shows_fixed = row[0] if row is not None else 0
            row = conn.execute(_MOVIES_COUNT_SQL).fetchone()
            stats.movies_fixed = row[0] if row is not None else 0
        finally:
            conn.close()

    log.info("canonical_provider_fix_done", stats=stats.to_log_dict())

    emit(stats.frozen().to_cli_json(apply=apply))
