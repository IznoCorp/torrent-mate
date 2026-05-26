#!/usr/bin/env python3
"""Audit foreign-key orphans in the indexer database.

SH-5 / BD-AE — tech-debt 0.16.0 Phase 4.4.

Runs one SELECT per FK constraint defined in the schema and reports
any rows whose foreign key references a non-existent parent.

Background
----------
SQLite enforces FK constraints only on connections where
``PRAGMA foreign_keys=ON`` is active **at write time**.  Scripts that
bypass :func:`personalscraper.indexer.db.open_db` (raw ``sqlite3.connect``,
the ``sqlite3`` CLI, DBeaver, etc.) can therefore insert orphan rows
silently.  Phase 1.2 (tech-debt 0.16.0) added a ``PRAGMA
foreign_key_check`` pre-boot guard inside ``open_db`` that raises
:class:`~personalscraper.indexer.db.IndexerFKOrphansError` if any orphan
is found.

This script provides an independent, operator-run audit that:

1. Opens the database **without** going through ``open_db`` (so it does
   not trigger the boot guard that would abort on the first orphan).
2. Runs a hand-crafted ``SELECT`` for each FK relationship in the schema
   so the report can attribute each orphan to its specific constraint.
3. Exits 0 when zero orphans are found, non-zero otherwise.

Usage
-----
::

    python scripts/audit-fk-orphans.py [DB_PATH]

If ``DB_PATH`` is omitted the script falls back to the path returned by
``personalscraper.indexer.config.indexer_db_path()``.

Exit codes
----------
* 0 — zero orphans found (DB is clean).
* 1 — one or more FK orphans detected; details logged to stdout.
* 2 — usage error (bad arguments, missing DB file, etc.).
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# FK constraint catalogue
# ---------------------------------------------------------------------------
# Each entry describes one FK relationship as (child_table, fk_column,
# parent_table, parent_pk, nullable) so the audit query can be generated
# programmatically.  Nullable=True means the FK column may be NULL (i.e.
# ``REFERENCES … ON DELETE SET NULL`` or declared without NOT NULL) — NULL
# values are **not** orphans, they are valid absent-parent indicators.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FKConstraint:
    """One foreign-key constraint to audit.

    Args:
        child_table: Table that holds the FK column.
        fk_column: Name of the column that references the parent.
        parent_table: Table being referenced.
        parent_pk: Primary-key column of the parent table (usually ``id``).
        nullable: Whether the FK column allows NULL (NULL rows are skipped
            — they are *not* orphans, they indicate an absent parent via the
            SET NULL ON DELETE semantic).
        description: Human-readable label for the relationship, used in
            the audit report.
    """

    child_table: str
    fk_column: str
    parent_table: str
    parent_pk: str = "id"
    nullable: bool = False
    description: str = ""


# Catalogue derived from migrations 001–006 (all FK REFERENCES).
# Order mirrors the schema declaration order for readability.
_FK_CONSTRAINTS: list[FKConstraint] = [
    # path → disk
    FKConstraint(
        child_table="path",
        fk_column="disk_id",
        parent_table="disk",
        nullable=False,
        description="path.disk_id → disk.id (ON DELETE RESTRICT)",
    ),
    # item_attribute → media_item
    FKConstraint(
        child_table="item_attribute",
        fk_column="item_id",
        parent_table="media_item",
        nullable=False,
        description="item_attribute.item_id → media_item.id (ON DELETE CASCADE)",
    ),
    # season → media_item
    FKConstraint(
        child_table="season",
        fk_column="item_id",
        parent_table="media_item",
        nullable=False,
        description="season.item_id → media_item.id (ON DELETE CASCADE)",
    ),
    # episode → season
    FKConstraint(
        child_table="episode",
        fk_column="season_id",
        parent_table="season",
        nullable=False,
        description="episode.season_id → season.id (ON DELETE CASCADE)",
    ),
    # media_release → media_item (nullable: movies set this, episodes set episode_id)
    FKConstraint(
        child_table="media_release",
        fk_column="item_id",
        parent_table="media_item",
        nullable=True,
        description="media_release.item_id → media_item.id (ON DELETE CASCADE, nullable)",
    ),
    # media_release → episode (nullable: TV episodes set this, movies set item_id)
    FKConstraint(
        child_table="media_release",
        fk_column="episode_id",
        parent_table="episode",
        nullable=True,
        description="media_release.episode_id → episode.id (ON DELETE CASCADE, nullable)",
    ),
    # media_file → media_release (nullable after migration 002 SET NULL)
    FKConstraint(
        child_table="media_file",
        fk_column="release_id",
        parent_table="media_release",
        nullable=True,
        description="media_file.release_id → media_release.id (ON DELETE SET NULL, nullable)",
    ),
    # media_file → path
    FKConstraint(
        child_table="media_file",
        fk_column="path_id",
        parent_table="path",
        nullable=False,
        description="media_file.path_id → path.id (ON DELETE RESTRICT)",
    ),
    # media_stream → media_file
    FKConstraint(
        child_table="media_stream",
        fk_column="file_id",
        parent_table="media_file",
        nullable=False,
        description="media_stream.file_id → media_file.id (ON DELETE CASCADE)",
    ),
    # item_issue → media_item
    FKConstraint(
        child_table="item_issue",
        fk_column="item_id",
        parent_table="media_item",
        nullable=False,
        description="item_issue.item_id → media_item.id (ON DELETE CASCADE)",
    ),
    # pending_op → disk
    FKConstraint(
        child_table="pending_op",
        fk_column="disk_id",
        parent_table="disk",
        nullable=False,
        description="pending_op.disk_id → disk.id (ON DELETE CASCADE)",
    ),
    # scan_event → scan_run
    FKConstraint(
        child_table="scan_event",
        fk_column="scan_id",
        parent_table="scan_run",
        nullable=False,
        description="scan_event.scan_id → scan_run.id (ON DELETE CASCADE)",
    ),
    # scan_event → media_item (nullable: SET NULL on item delete)
    FKConstraint(
        child_table="scan_event",
        fk_column="item_id",
        parent_table="media_item",
        nullable=True,
        description="scan_event.item_id → media_item.id (ON DELETE SET NULL, nullable)",
    ),
    # scan_event → media_file (nullable: SET NULL on file delete)
    FKConstraint(
        child_table="scan_event",
        fk_column="file_id",
        parent_table="media_file",
        nullable=True,
        description="scan_event.file_id → media_file.id (ON DELETE SET NULL, nullable)",
    ),
]


# ---------------------------------------------------------------------------
# Audit result types
# ---------------------------------------------------------------------------


@dataclass
class OrphanRow:
    """A single orphan detected for a FK constraint.

    Args:
        child_table: Table containing the orphan row.
        fk_column: Name of the FK column with the dangling reference.
        fk_value: The value of the FK column (the missing parent id).
        child_pk: ``rowid`` of the orphan row in *child_table* (SQLite
            internal row identifier, present on every regular table even
            when the declared PK is composite).
    """

    child_table: str
    fk_column: str
    fk_value: Any
    child_pk: int


@dataclass
class ConstraintReport:
    """Audit result for one FK constraint.

    Args:
        constraint: The FK constraint that was checked.
        orphans: List of orphan rows found (empty when clean).
    """

    constraint: FKConstraint
    orphans: list[OrphanRow] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True when no orphans were detected for this constraint."""
        return len(self.orphans) == 0


# ---------------------------------------------------------------------------
# Core audit logic
# ---------------------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Return True if *table* exists in the database.

    Args:
        conn: Open SQLite connection.
        table: Table name to check.

    Returns:
        True if the table is present in ``sqlite_master``.
    """
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def audit_constraint(
    conn: sqlite3.Connection,
    constraint: FKConstraint,
) -> ConstraintReport:
    """Run the orphan SELECT for a single FK constraint.

    Skips the audit and returns an empty report when either the child or
    the parent table does not exist in the database (e.g. future migrations
    have not been applied yet, or the table was renamed).

    Args:
        conn: Open SQLite connection.  FK enforcement does not need to be
            active — we run plain ``SELECT`` queries.
        constraint: The FK relationship to audit.

    Returns:
        A :class:`ConstraintReport` with the list of orphan rows found
        (empty when clean or when the table is absent).
    """
    report = ConstraintReport(constraint=constraint)

    # Skip gracefully when the table does not yet exist (forward-compat).
    if not _table_exists(conn, constraint.child_table):
        return report
    if not _table_exists(conn, constraint.parent_table):
        return report

    # Build the orphan query.
    # For nullable FKs we add ``AND c.{fk_column} IS NOT NULL`` so we skip
    # valid "no parent" sentinel NULLs introduced by ON DELETE SET NULL.
    # Use ``c.rowid`` as the child identifier: every regular SQLite table has
    # a rowid even when the declared PK is composite (item_attribute, item_issue).
    null_filter = f" AND c.{constraint.fk_column} IS NOT NULL" if constraint.nullable else ""
    sql = f"""
        SELECT c.rowid AS child_pk, c.{constraint.fk_column} AS fk_value
          FROM {constraint.child_table} c
         WHERE NOT EXISTS (
               SELECT 1
                 FROM {constraint.parent_table} p
                WHERE p.{constraint.parent_pk} = c.{constraint.fk_column}
         ){null_filter}
    """
    rows = conn.execute(sql).fetchall()
    for child_pk, fk_value in rows:
        report.orphans.append(
            OrphanRow(
                child_table=constraint.child_table,
                fk_column=constraint.fk_column,
                fk_value=fk_value,
                child_pk=child_pk,
            )
        )
    return report


def audit_all(conn: sqlite3.Connection) -> list[ConstraintReport]:
    """Run the orphan audit for every FK constraint in the catalogue.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of :class:`ConstraintReport`, one per FK constraint.
        Reports for constraints with no orphans have an empty
        :attr:`ConstraintReport.orphans` list.
    """
    return [audit_constraint(conn, fk) for fk in _FK_CONSTRAINTS]


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def print_report(reports: list[ConstraintReport], db_path: Path) -> int:
    """Print the audit report to stdout and return an exit code.

    Args:
        reports: List of :class:`ConstraintReport` from :func:`audit_all`.
        db_path: Path to the database file (for display only).

    Returns:
        0 if all constraints are clean, 1 if any orphans were found.
    """
    total_orphans = sum(len(r.orphans) for r in reports)
    dirty = [r for r in reports if not r.is_clean]

    if total_orphans == 0:
        print(f"[OK] {db_path} — zero FK orphans across {len(reports)} constraints.")
        return 0

    print(f"[FAIL] {db_path} — {total_orphans} FK orphan(s) across {len(dirty)} constraint(s).")
    print()
    for report in dirty:
        c = report.constraint
        print(f"  Constraint : {c.description}")
        print(f"  Child table: {c.child_table}, FK column: {c.fk_column}")
        print(f"  Orphan count: {len(report.orphans)}")
        for orphan in report.orphans[:20]:  # cap output for very large orphan sets
            print(
                f"    child_pk={orphan.child_pk}  {c.fk_column}={orphan.fk_value!r} "
                f"(no matching {c.parent_table}.{c.parent_pk})"
            )
        if len(report.orphans) > 20:
            print(f"    … and {len(report.orphans) - 20} more (truncated).")
        print()

    print("Run  sqlite3 <db>  'PRAGMA foreign_key_check;'  for the SQLite-native summary.")
    print("Fix orphans before restarting the indexer (open_db will raise IndexerFKOrphansError).")
    return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _resolve_db_path(argv: list[str]) -> Path:
    """Resolve the database path from CLI argv or fall back to config.

    Args:
        argv: ``sys.argv[1:]`` — optional single positional argument.

    Returns:
        Resolved :class:`~pathlib.Path` to the SQLite database.

    Raises:
        SystemExit(2): When more than one argument is provided, or the
            resolved path does not exist.
    """
    if len(argv) > 1:
        print(f"Usage: {sys.argv[0]} [DB_PATH]", file=sys.stderr)
        sys.exit(2)

    if len(argv) == 1:
        db_path = Path(argv[0]).expanduser().resolve()
    else:
        # Fall back to the configured indexer DB path.
        try:
            from personalscraper.indexer.config import indexer_db_path  # noqa: PLC0415

            db_path = indexer_db_path()
        except Exception as exc:  # noqa: BLE001
            print(
                f"Error: could not determine the indexer DB path from config: {exc}\n"
                f"Pass the DB path explicitly:  {sys.argv[0]} /path/to/library.db",
                file=sys.stderr,
            )
            sys.exit(2)

    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(2)

    return db_path


def main(argv: list[str] | None = None) -> int:
    """Audit FK orphans and return an exit code.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 when the database is clean, 1 when orphans are found, 2 on usage
        errors.
    """
    if argv is None:
        argv = sys.argv[1:]

    db_path = _resolve_db_path(argv)

    # Open with FK enforcement OFF so we can query orphans without triggering
    # open_db's pre-check (which aborts on first orphan).  This script is the
    # diagnostic tool — it needs to inspect, not abort.
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        reports = audit_all(conn)
    finally:
        conn.close()

    return print_report(reports, db_path)


if __name__ == "__main__":
    sys.exit(main())
