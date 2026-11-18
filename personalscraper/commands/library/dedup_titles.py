"""De-duplicate ``media_item`` rows whose titles differ only by NFD/NFC normalization.

macOS ``iterdir()`` returns folder names in NFD (decomposed Unicode), while the
DB stores titles in NFC (precomposed). Without NFC normalization in
``_canonical_title``, every full scan of an accented-title folder inserted a
new NFD row, leaving the original NFC row as a stale orphan.

This command:

1. Groups all ``media_item`` rows by ``(NFC(canonical_title).lower(), kind, year)``.
2. For each group with > 1 row **and** identical ``dispatch_path`` values, selects
   a survivor, NFC-normalizes its ``title``, and deletes the others (``ON DELETE
   CASCADE`` removes child seasons/releases/files/attributes). The survivor is
   the row holding live files; among rows holding none, the newest
   ``date_metadata_refreshed`` (tie-break: highest ``id``). A group where two
   rows both hold files is reported and skipped, never merged.
3. NFC-normalizes the ``title`` of any non-duplicate row still stored as NFD.
4. ``--dry-run`` (default) prints the plan and mutates nothing.
   ``--apply`` executes all writes in one transaction then checkpoints WAL; each
   deleted row leaves a ``deleted_item`` tombstone and a ``destructive_op`` journal
   row, like ``library-remove-phantom-rows``.

Examples:
    personalscraper library-dedup-titles
    personalscraper library-dedup-titles --apply
    personalscraper library-dedup-titles --db /custom/path/library.db --apply
"""

from __future__ import annotations

import os
import re as _re
import sqlite3 as _sqlite3
import time
import unicodedata as _unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.commands.library._fix_stats_base import CliFixStatsMixin
from personalscraper.core.sqlite import refuse_newer_schema
from personalscraper.i18n import t
from personalscraper.indexer.migrations import MIGRATIONS_DIR as LIBRARY_MIGRATIONS_DIR
from personalscraper.indexer.phantom_rows import item_holds_live_files, journal_item_removal, tombstone_item
from personalscraper.logger import get_logger

log = get_logger("cli")

#: ``deleted_item.reason`` of a row this command removes.
_TOMBSTONE_REASON = "dedup_titles_removed"

#: Why a survivor was kept (``plan[].reason``) and why a group was skipped.
REASON_HOLDS_FILES = "holds_files"
REASON_NEWEST_REFRESH = "newest_refresh"
REASON_BOTH_HOLD_FILES = "both_hold_files"

# Mirrors _CANONICAL_RE in item_repo.py — strips trailing " (YYYY)".
_CANONICAL_RE = _re.compile(r"\s*\(\d{4}\)$")


def _canonical_key(title: str) -> str:
    """Return the NFC-normalized, lowercased base title used as a group key.

    Strips a trailing `` (YYYY)`` suffix, NFC-normalizes, then lowercases.

    The real indexer dedup (``item_repo.get_by_title_kind_year``) is
    case-SENSITIVE (``WHERE title = ?``, no ``lower()``).  The ``.lower()``
    here is an **intentionally broader** grouping — it can merge case-variant
    titles that the indexer would keep separate.  Since every group is guarded
    by the ``dispatch_path`` safety check (all members must share the same
    non-empty NFC path), even a case-variant group is safe: the guard skips
    any group that might merge truly distinct folders.

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

    Returns ``None`` when the attribute is absent, empty, or whitespace-only
    — all of which are treated as "unverifiable" by the dispatch_path guard.

    Args:
        conn: Open SQLite connection.
        item_id: ``media_item.id`` to look up.

    Returns:
        The ``dispatch_path`` string, or ``None`` when absent/empty.
    """
    row = conn.execute(
        "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'dispatch_path'",
        (item_id,),
    ).fetchone()
    value = str(row[0]).strip() if row is not None else None
    return value or None


def _select_survivor(rows: list[dict[str, object]]) -> tuple[dict[str, object], str]:
    """Select the survivor from a duplicate group.

    A row holding live files (``holds_files``) always wins over a row holding none.
    Among the candidates, the live row (non-NULL ``date_metadata_refreshed``) with
    the most recent timestamp wins; tie-break by highest ``id``. When no live row
    exists, the highest ``id`` wins (fail-safe). The caller guarantees at most one
    row of the group holds files.

    Args:
        rows: Row dicts with keys ``id``, ``date_metadata_refreshed`` and ``holds_files``.

    Returns:
        ``(survivor, reason)`` — the row dict kept and :data:`REASON_HOLDS_FILES` or
        :data:`REASON_NEWEST_REFRESH`.
    """
    holders = [r for r in rows if r["holds_files"]]
    if holders:
        return holders[0], REASON_HOLDS_FILES
    live = [r for r in rows if r["date_metadata_refreshed"] is not None]
    pool = live if live else rows
    return max(pool, key=lambda r: (r["date_metadata_refreshed"] or 0, r["id"])), REASON_NEWEST_REFRESH


@dataclass
class DedupTitlesStats(CliFixStatsMixin):
    """Counters and plan of ``library_dedup_titles``.

    Attributes:
        duplicate_groups: Groups with > 1 row sharing the same ``dispatch_path`` that are merged.
        deleted: Orphan rows removed (``would_delete`` in dry-run).
        normalized: NFD titles NFC-normalized (``would_normalize`` in dry-run).
        skipped: Groups skipped because rows lack a common ``dispatch_path``.
        skipped_both_hold_files: Groups skipped because two rows both hold live files.
        plan: Per merged group, ``{"survivor", "reason", "deleted"}``.
        skipped_groups: Per group skipped for holding files twice, ``{"ids", "reason"}``.
    """

    duplicate_groups: int = 0
    deleted: int = 0
    normalized: int = 0
    skipped: int = 0
    skipped_both_hold_files: int = 0
    plan: list[dict[str, Any]] = field(default_factory=list)
    skipped_groups: list[dict[str, Any]] = field(default_factory=list)

    def to_log_dict(self) -> dict[str, int]:
        """Project the counters (not the plan lists) to a ``dict[str, int]`` for structlog.

        Returns:
            The integer fields by name.
        """
        return {
            "duplicate_groups": self.duplicate_groups,
            "deleted": self.deleted,
            "normalized": self.normalized,
            "skipped": self.skipped,
            "skipped_both_hold_files": self.skipped_both_hold_files,
        }

    def to_cli_json(self, *, apply: bool) -> dict[str, Any]:
        """Project to the CLI JSON output shape.

        Args:
            apply: Whether ``--apply`` was passed (controls key names).

        Returns:
            Dict with ``apply`` flag, the counter keys, the per-group ``plan`` and the
            ``skipped_groups``.
        """
        return {
            "apply": apply,
            "duplicate_groups": self.duplicate_groups,
            "deleted" if apply else "would_delete": self.deleted,
            "normalized" if apply else "would_normalize": self.normalized,
            "skipped": self.skipped,
            "skipped_both_hold_files": self.skipped_both_hold_files,
            "plan": self.plan,
            "skipped_groups": self.skipped_groups,
        }


@app.command("library-dedup-titles", help=t("cli_library.dedup_titles.command_help"))
@handle_cli_errors
def library_dedup_titles(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help=t("cli_library.dedup_titles.apply_help")),
    config: Path | None = typer.Option(None, "--config", "-c", help=t("cli_library.dedup_titles.config_help")),
    db: Path | None = typer.Option(None, "--db", help=t("cli_library.dedup_titles.db_help")),
) -> None:
    """De-duplicate ``media_item`` rows that differ only by NFD/NFC normalization.

    Groups rows by ``(NFC(canonical_title).lower(), kind, year)``. For each
    group with > 1 row sharing the same ``dispatch_path``, keeps the row holding
    live files (else the newest ``date_metadata_refreshed``, tie-break: highest
    ``id``) and deletes the rest via ``ON DELETE CASCADE``, journaling each
    deletion. A group where two rows both hold files is reported and skipped.
    Also NFC-normalizes the ``title`` of any non-duplicate row stored as NFD.
    Dry-run by default.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

    cfg = ctx.obj.config if ctx.obj is not None else load_config(config)
    if db is not None:
        db_path = db
    elif cfg.indexer.db_path is not None:
        db_path = Path(cfg.indexer.db_path)
    else:
        typer.echo(t("cli_library.dedup_titles.db_path_not_configured"), err=True)
        raise typer.Exit(code=1)

    if not db_path.exists():
        typer.echo(t("cli_library.dedup_titles.db_not_found", path=str(db_path)), err=True)
        raise typer.Exit(code=1)

    conn = _sqlite3.connect(str(db_path))
    refuse_newer_schema(conn, LIBRARY_MIGRATIONS_DIR)
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
            path_values = list(paths.values())
            nfc_paths = {_unicodedata.normalize("NFC", p) for p in path_values if p}
            if any(not p for p in path_values) or len(nfc_paths) != 1:
                log.warning(
                    "dedup_titles.dispatch_path_unverifiable",
                    ids=list(paths),
                    paths=sorted(nfc_paths),
                    missing=[i for i, p in paths.items() if not p],
                )
                stats.skipped += 1
                continue

            for m in members:
                m["holds_files"] = item_holds_live_files(conn, int(m["id"]))  # type: ignore[call-overload]
            if sum(1 for m in members if m["holds_files"]) > 1:
                ids = sorted(int(m["id"]) for m in members)  # type: ignore[call-overload]
                log.warning("dedup_titles.both_hold_files", ids=ids)
                stats.skipped_both_hold_files += 1
                stats.skipped_groups.append({"ids": ids, "reason": REASON_BOTH_HOLD_FILES})
                continue

            stats.duplicate_groups += 1
            survivor, reason = _select_survivor(members)
            survivor_id = int(survivor["id"])  # type: ignore[call-overload]
            survivor_title = str(survivor["title"])
            if _is_nfd(survivor_title):
                to_normalize.append((_unicodedata.normalize("NFC", survivor_title), survivor_id))
            doomed = [int(m["id"]) for m in members if int(m["id"]) != survivor_id]  # type: ignore[call-overload]
            to_delete.extend(doomed)
            stats.plan.append({"survivor": survivor_id, "reason": reason, "deleted": doomed})

        stats.deleted = len(to_delete)
        stats.normalized = len(to_normalize)
        log.info("dedup_titles.plan", apply=apply, **stats.to_log_dict())

        if apply:
            now = int(time.time())
            conn.execute("BEGIN IMMEDIATE")
            try:
                for item_id in to_delete:
                    tombstone_item(conn, item_id, now, reason=_TOMBSTONE_REASON)
                    conn.execute("DELETE FROM media_item WHERE id = ?", (item_id,))
                for nfc_title, item_id in to_normalize:
                    conn.execute("UPDATE media_item SET title = ? WHERE id = ?", (nfc_title, item_id))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            run_uid = os.environ.get("PERSONALSCRAPER_RUN_UID") or uuid.uuid4().hex
            for item_id in to_delete:
                journal_item_removal(db_path, item_id, run_uid=run_uid)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            log.info("dedup_titles.done", deleted=stats.deleted, normalized=stats.normalized)

        emit(stats.snapshot().to_cli_json(apply=apply))
    finally:
        conn.close()
