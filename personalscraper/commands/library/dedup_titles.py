"""De-duplicate ``media_item`` rows whose titles differ only by NFD/NFC normalization.

macOS ``iterdir()`` returns folder names in NFD (decomposed Unicode), while the
DB stores titles in NFC (precomposed). Without NFC normalization in
``_canonical_title``, every full scan of an accented-title folder inserted a
new NFD row, leaving the original NFC row as a stale orphan.

This command:

1. Groups all ``media_item`` rows by ``(NFC(canonical_title).lower(), kind, year)``.
2. For each group with > 1 row **and** identical ``dispatch_path`` values, selects
   a survivor (live row = newest ``date_metadata_refreshed``, tie-break: highest
   ``id``), NFC-normalizes its ``title``, and deletes the others (``ON DELETE
   CASCADE`` removes child seasons/releases/files/attributes).
3. NFC-normalizes the ``title`` of any non-duplicate row still stored as NFD.
4. ``--dry-run`` (default) prints the plan and mutates nothing.
   ``--apply`` executes all writes in one transaction then checkpoints WAL.

Examples:
    personalscraper library-dedup-titles
    personalscraper library-dedup-titles --apply
    personalscraper library-dedup-titles --db /custom/path/library.db --apply
"""

from __future__ import annotations

import re as _re
import sqlite3 as _sqlite3
import unicodedata as _unicodedata
from dataclasses import dataclass
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.commands.library._fix_stats_base import CliFixStatsMixin
from personalscraper.logger import get_logger

log = get_logger("cli")

# Mirrors _CANONICAL_RE in item_repo.py — strips trailing " (YYYY)".
_CANONICAL_RE = _re.compile(r"\s*\(\d{4}\)$")


def _canonical_key(title: str) -> str:
    """Return the NFC-normalized, lowercased base title used as a group key.

    Strips a trailing `` (YYYY)`` suffix, NFC-normalizes, then lowercases.
    Matches the dedup key applied by ``_canonical_title`` + SQLite ``lower()``.

    Args:
        title: Raw title from ``media_item.title``.

    Returns:
        Normalized string suitable for grouping duplicate rows.
    """
    stripped = _CANONICAL_RE.sub("", title)
    return _unicodedata.normalize("NFC", stripped).lower()


def _is_nfd(title: str) -> bool:
    """Return ``True`` when *title* is not NFC-normalized.

    Args:
        title: String to test.

    Returns:
        ``True`` if ``unicodedata.normalize('NFC', title) != title``.
    """
    return _unicodedata.normalize("NFC", title) != title


def _get_dispatch_path(conn: _sqlite3.Connection, item_id: int) -> str | None:
    """Fetch the ``dispatch_path`` attribute for *item_id*, or ``None``.

    Args:
        conn: Open SQLite connection.
        item_id: ``media_item.id`` to look up.

    Returns:
        The ``dispatch_path`` string, or ``None`` when absent.
    """
    row = conn.execute(
        "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'dispatch_path'",
        (item_id,),
    ).fetchone()
    return str(row[0]) if row is not None else None


def _select_survivor(rows: list[dict[str, object]]) -> dict[str, object]:
    """Select the survivor from a duplicate group.

    Survivor = live row (non-NULL ``date_metadata_refreshed``) with the most
    recent timestamp; tie-break by highest ``id``. When no live row exists,
    the highest ``id`` wins (fail-safe).

    Args:
        rows: List of row dicts with keys ``id`` and ``date_metadata_refreshed``.

    Returns:
        The row dict chosen as survivor.
    """
    live = [r for r in rows if r["date_metadata_refreshed"] is not None]
    pool = live if live else rows
    return max(pool, key=lambda r: (r["date_metadata_refreshed"] or 0, r["id"]))


@dataclass
class DedupTitlesStats(CliFixStatsMixin):
    """Counters for ``library_dedup_titles``.

    Attributes:
        duplicate_groups: Groups with > 1 row sharing the same ``dispatch_path``.
        deleted: Orphan rows removed (``would_delete`` in dry-run).
        normalized: NFD titles NFC-normalized (``would_normalize`` in dry-run).
        skipped: Groups skipped because rows lack a common ``dispatch_path``.
    """

    duplicate_groups: int = 0
    deleted: int = 0
    normalized: int = 0
    skipped: int = 0

    def to_cli_json(self, *, apply: bool) -> dict[str, int | bool]:
        """Project to the CLI JSON output shape.

        Args:
            apply: Whether ``--apply`` was passed (controls key names).

        Returns:
            Dict with ``apply`` flag and the relevant counter keys.
        """
        return {
            "apply": apply,
            "duplicate_groups": self.duplicate_groups,
            "deleted" if apply else "would_delete": self.deleted,
            "normalized" if apply else "would_normalize": self.normalized,
            "skipped": self.skipped,
        }


@app.command("library-dedup-titles")
@handle_cli_errors
def library_dedup_titles(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (default: dry-run)."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """De-duplicate ``media_item`` rows that differ only by NFD/NFC normalization.

    Groups rows by ``(NFC(canonical_title).lower(), kind, year)``. For each
    group with > 1 row sharing the same ``dispatch_path``, keeps the live
    survivor (newest ``date_metadata_refreshed``, tie-break: highest ``id``)
    and deletes the rest via ``ON DELETE CASCADE``. Also NFC-normalizes the
    ``title`` of any non-duplicate row stored as NFD. Dry-run by default.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

    cfg = ctx.obj.config if ctx.obj is not None else load_config(config)
    if db is not None:
        db_path = db
    elif cfg.indexer.db_path is not None:
        db_path = Path(cfg.indexer.db_path)
    else:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)

    conn = _sqlite3.connect(str(db_path))
    _apply_pragmas(conn)
    conn.row_factory = _sqlite3.Row
    try:
        stats = DedupTitlesStats()
        all_rows = conn.execute("SELECT id, title, kind, year, date_metadata_refreshed FROM media_item").fetchall()

        groups: dict[tuple[str, str, int | None], list[dict[str, object]]] = {}
        for r in all_rows:
            key = (_canonical_key(str(r["title"])), str(r["kind"]), r["year"])
            groups.setdefault(key, []).append(dict(r))

        to_delete: list[int] = []
        to_normalize: list[tuple[str, int]] = []

        for _key, members in groups.items():
            if len(members) == 1:
                sole = members[0]
                raw_title = str(sole["title"])
                if _is_nfd(raw_title):
                    to_normalize.append((_unicodedata.normalize("NFC", raw_title), int(sole["id"])))  # type: ignore[call-overload]
                continue

            paths = {int(m["id"]): _get_dispatch_path(conn, int(m["id"])) for m in members}  # type: ignore[call-overload]
            unique_paths = {p for p in paths.values() if p is not None}
            if len(unique_paths) != 1:
                log.warning("dedup_titles.dispatch_path_mismatch", ids=list(paths), paths=list(unique_paths))
                stats.skipped += 1
                continue

            stats.duplicate_groups += 1
            survivor = _select_survivor(members)
            survivor_id = int(survivor["id"])  # type: ignore[call-overload]
            to_normalize.append((_unicodedata.normalize("NFC", str(survivor["title"])), survivor_id))
            to_delete.extend(int(m["id"]) for m in members if int(m["id"]) != survivor_id)  # type: ignore[call-overload]

        stats.deleted = len(to_delete)
        stats.normalized = len(to_normalize)
        log.info("dedup_titles.plan", apply=apply, **stats.to_log_dict())

        if apply:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for item_id in to_delete:
                    conn.execute("DELETE FROM media_item WHERE id = ?", (item_id,))
                for nfc_title, item_id in to_normalize:
                    conn.execute("UPDATE media_item SET title = ? WHERE id = ?", (nfc_title, item_id))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            log.info("dedup_titles.done", deleted=stats.deleted, normalized=stats.normalized)

        emit(stats.snapshot().to_cli_json(apply=apply))
    finally:
        conn.close()
