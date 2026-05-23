#!/usr/bin/env python3
"""Audit dead infrastructure — tables, columns, functions, Protocols.

Sub-phase 8.4 of the tech-debt 0.16.0 plan (SH-17 / CF-G / P11). Inventories
four categories of potentially-dead infrastructure and emits a markdown report
that operators can use to decide what to drop, wire, or keep:

1. **Empty tables** — tables in the live SQLite library DB with ``COUNT(*) == 0``.
2. **Never-populated columns** — columns in non-empty tables where every row
   has ``NULL`` (100 % NULL rate). These are candidates for DROP COLUMN.
3. **Dead function candidates** — ``def`` definitions whose name appears only
   at the definition site after light heuristic filtering (skips dunder methods,
   names listed in ``__all__``, common framework hooks).
4. **Dead Protocol candidates** — ``class X(Protocol):`` whose name is not
   referenced outside the definition module.

This is an INVENTORY pass only: it WRITES a markdown report. It does NOT
modify any code or DB rows. The report is the deliverable; the operator
decides per row whether to drop, wire, or keep.

Usage::

    python3 scripts/audit-dead-infrastructure.py \
        --output docs/features/tech-debt/audit/12-dead-infrastructure.md

    # Optional: target a different DB (default .data/library.db)
    python3 scripts/audit-dead-infrastructure.py --db /path/to/library.db

Exit codes:
    0 — report generated (regardless of findings count).
    1 — fatal error (missing files, IO error).

Cross-reference: sub-phase 8.2 (``audit/14-pending-op-item-issue.md``) already
established that ``pending_op`` and ``item_issue`` are live infrastructure with
full wiring, despite ``0 rows`` snapshots. This script will surface them again
under "empty tables" — that is expected, and the report annotates them as
``KEEP (see audit/14-...)`` rather than ``DROP candidate``.
"""

from __future__ import annotations

import argparse
import ast
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "personalscraper"
DEFAULT_DB = REPO_ROOT / ".data" / "library.db"
DEFAULT_REPORT = REPO_ROOT / "docs" / "features" / "tech-debt" / "audit" / "12-dead-infrastructure.md"

# Tables already audited and confirmed KEEP by sub-phase 8.2 — surface them
# under empty tables but annotate so reviewers know they are NOT drop candidates.
KEEP_ANNOTATED: dict[str, str] = {
    "pending_op": "KEEP — see audit/14-pending-op-item-issue.md (live hinted-handoff queue)",
    "item_issue": "KEEP — see audit/14-pending-op-item-issue.md (live hygiene tags)",
}

# Function names that virtually never trigger a textual grep hit beyond the
# definition site even when they ARE used (called by frameworks, dispatched by
# string name, exposed via __all__, etc.). Skipped to keep false-positive rate
# tractable. Dunder methods (__init__, __repr__, …) are also skipped via a
# separate prefix/suffix filter.
FUNC_NAME_DENYLIST: frozenset[str] = frozenset(
    {
        "main",
        "setup",
        "teardown",
        "configure",
        "register",
        "model_dump",
        "model_validate",
    }
)

# Skip files in these subdirectories when collecting function defs — they tend
# to define many private helpers used cross-module via stringified imports,
# which create false positives.
SKIP_PATH_PARTS: frozenset[str] = frozenset({"migrations", "__pycache__"})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EmptyTableFinding:
    """A table whose row count is 0 in the audited DB."""

    table: str
    row_count: int
    annotation: str = ""


@dataclass
class NullColumnFinding:
    """A column whose values are 100 % NULL in a non-empty table."""

    table: str
    column: str
    total_rows: int
    null_rows: int


@dataclass
class DeadFunctionFinding:
    """A function whose name is referenced only at its definition site."""

    name: str
    file: str
    line: int


@dataclass
class DeadProtocolFinding:
    """A Protocol class whose name is referenced only at its definition site."""

    name: str
    file: str
    line: int


@dataclass
class AuditReport:
    """Aggregate of all four sub-audits."""

    db_path: Path
    empty_tables: list[EmptyTableFinding] = field(default_factory=list)
    null_columns: list[NullColumnFinding] = field(default_factory=list)
    dead_functions: list[DeadFunctionFinding] = field(default_factory=list)
    dead_protocols: list[DeadProtocolFinding] = field(default_factory=list)
    scanned_tables: int = 0
    scanned_columns: int = 0
    scanned_functions: int = 0
    scanned_protocols: int = 0


# ---------------------------------------------------------------------------
# Sub-audit A — empty tables
# ---------------------------------------------------------------------------


def _list_user_tables(conn: sqlite3.Connection) -> list[str]:
    """Return user-defined table names (excludes sqlite_* internal tables)."""
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [row[0] for row in cur.fetchall()]


def audit_empty_tables(conn: sqlite3.Connection) -> tuple[list[EmptyTableFinding], int]:
    """Find tables whose row count is exactly 0.

    Returns:
        Tuple of (findings, total_tables_scanned).
    """
    findings: list[EmptyTableFinding] = []
    tables = _list_user_tables(conn)
    for table in tables:
        # Quoting via identifier reuse is safe: sqlite_master is authoritative.
        cur = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
        (count,) = cur.fetchone()
        if count == 0:
            findings.append(
                EmptyTableFinding(
                    table=table,
                    row_count=0,
                    annotation=KEEP_ANNOTATED.get(table, ""),
                )
            )
    return findings, len(tables)


# ---------------------------------------------------------------------------
# Sub-audit B — never-populated columns
# ---------------------------------------------------------------------------


def _list_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return column names for ``table`` via ``PRAGMA table_info``."""
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    return [row[1] for row in cur.fetchall()]


def audit_null_columns(conn: sqlite3.Connection) -> tuple[list[NullColumnFinding], int]:
    """Find columns where 100 % of values are NULL in NON-empty tables.

    Empty tables are skipped because every column trivially satisfies the
    predicate; they are surfaced separately by ``audit_empty_tables``.

    Returns:
        Tuple of (findings, total_columns_scanned).
    """
    findings: list[NullColumnFinding] = []
    scanned = 0
    for table in _list_user_tables(conn):
        cur = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
        (total,) = cur.fetchone()
        if total == 0:
            continue
        for column in _list_columns(conn, table):
            scanned += 1
            cur = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NULL')
            (null_count,) = cur.fetchone()
            if null_count == total:
                findings.append(
                    NullColumnFinding(
                        table=table,
                        column=column,
                        total_rows=total,
                        null_rows=null_count,
                    )
                )
    return findings, scanned


# ---------------------------------------------------------------------------
# Sub-audits C + D — Python AST walk
# ---------------------------------------------------------------------------


@dataclass
class _ModuleSymbols:
    """Symbols extracted from a single ``.py`` module."""

    path: Path
    functions: list[tuple[str, int]] = field(default_factory=list)  # (name, lineno)
    protocols: list[tuple[str, int]] = field(default_factory=list)  # (name, lineno)
    all_exports: set[str] = field(default_factory=set)  # names listed in __all__


def _iter_py_files(root: Path) -> Iterable[Path]:
    """Yield ``.py`` files under ``root`` excluding skip-listed dirs."""
    for path in root.rglob("*.py"):
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        yield path


def _extract_all_exports(tree: ast.Module) -> set[str]:
    """Return the literal strings listed in a module-level ``__all__`` assignment."""
    exports: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t for t in node.targets if isinstance(t, ast.Name) and t.id == "__all__"]
        if not targets:
            continue
        if isinstance(node.value, (ast.List, ast.Tuple)):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    exports.add(elt.value)
    return exports


def _is_dunder(name: str) -> bool:
    """Return True for ``__init__``, ``__repr__``, ``_x_`` style names."""
    return name.startswith("__") and name.endswith("__")


def _class_is_protocol(node: ast.ClassDef) -> bool:
    """Return True if ``node`` inherits (directly) from ``typing.Protocol``."""
    for base in node.bases:
        # ``Protocol`` (imported directly) or ``typing.Protocol``
        if isinstance(base, ast.Name) and base.id == "Protocol":
            return True
        if (
            isinstance(base, ast.Attribute)
            and base.attr == "Protocol"
            and isinstance(base.value, ast.Name)
            and base.value.id in {"typing", "t"}
        ):
            return True
    return False


def _class_is_abc(node: ast.ClassDef) -> bool:
    """Return True if ``node`` inherits from ``ABC`` or ``ABCMeta``-marked class."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in {"ABC", "ABCMeta"}:
            return True
    return False


def _collect_module_symbols(path: Path) -> _ModuleSymbols | None:
    """Parse ``path`` and collect function / Protocol / __all__ symbols.

    Methods (functions defined inside a class body) are skipped — they have
    enough call-site polymorphism that a textual grep cannot reliably classify
    them as dead. Only module-level functions are reported.

    Returns None on parse error.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return None

    symbols = _ModuleSymbols(path=path)
    symbols.all_exports = _extract_all_exports(tree)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if _is_dunder(name):
                continue
            if name in FUNC_NAME_DENYLIST:
                continue
            if name in symbols.all_exports:
                continue
            symbols.functions.append((name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            if _class_is_protocol(node) and not _class_is_abc(node):
                if node.name not in symbols.all_exports:
                    symbols.protocols.append((node.name, node.lineno))
    return symbols


def _count_name_occurrences(name: str, sources: dict[Path, str], own_path: Path) -> int:
    """Count occurrences of ``name`` as an isolated token across ``sources``.

    Naive substring count is enough for a first-pass heuristic; the report
    framing makes clear that hits must be verified manually before any drop.

    Excludes the file containing the definition (``own_path``) so a function
    that calls itself recursively in the same module is not falsely credited
    with external usage.
    """
    count = 0
    for path, text in sources.items():
        if path == own_path:
            continue
        count += text.count(name)
    return count


def audit_dead_functions_and_protocols(
    pkg_root: Path,
) -> tuple[list[DeadFunctionFinding], list[DeadProtocolFinding], int, int]:
    """Walk every ``.py`` module and surface unused functions / Protocols.

    Heuristic: a symbol is a "dead candidate" if its name appears 0 times in
    any module other than its definition module. False positives still happen
    (string dispatch, dynamic imports, dotted-attribute access) — the report
    flags this loudly so operators verify manually before dropping.

    Returns:
        Tuple of (dead_functions, dead_protocols, total_funcs_scanned,
        total_protocols_scanned).
    """
    modules: list[_ModuleSymbols] = []
    sources: dict[Path, str] = {}

    for path in _iter_py_files(pkg_root):
        symbols = _collect_module_symbols(path)
        if symbols is None:
            continue
        modules.append(symbols)
        # Re-read source for grep step (cheaper than ast.unparse).
        try:
            sources[path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            sources[path] = ""

    dead_funcs: list[DeadFunctionFinding] = []
    dead_protocols: list[DeadProtocolFinding] = []
    total_funcs = 0
    total_protocols = 0

    for module in modules:
        for name, lineno in module.functions:
            total_funcs += 1
            if _count_name_occurrences(name, sources, module.path) == 0:
                dead_funcs.append(
                    DeadFunctionFinding(
                        name=name,
                        file=str(module.path.relative_to(REPO_ROOT)),
                        line=lineno,
                    )
                )
        for name, lineno in module.protocols:
            total_protocols += 1
            if _count_name_occurrences(name, sources, module.path) == 0:
                dead_protocols.append(
                    DeadProtocolFinding(
                        name=name,
                        file=str(module.path.relative_to(REPO_ROOT)),
                        line=lineno,
                    )
                )
    return dead_funcs, dead_protocols, total_funcs, total_protocols


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _render_report(report: AuditReport) -> str:
    """Produce the markdown report from an ``AuditReport``."""
    lines: list[str] = []
    lines.append("# Audit — Dead infrastructure (SH-17 / CF-G / P11)")
    lines.append("")
    lines.append("> **Sub-phase**: 8.4 (phase-08-polish.md)")
    lines.append("> **Generated from**: `scripts/audit-dead-infrastructure.py`")
    lines.append(f"> **DB audited**: `{report.db_path}`")
    lines.append("")
    lines.append("> READ-ONLY inventory pass. The script writes this report and exits;")
    lines.append("> it does NOT drop tables, columns, or code. Each finding is a")
    lines.append("> CANDIDATE for review — false positives are expected (string")
    lines.append("> dispatch, dynamic imports, deserialisation paths). Operator decides.")
    lines.append("")
    lines.append("## Scan summary")
    lines.append("")
    lines.append(f"- Tables scanned: **{report.scanned_tables}**")
    lines.append(f"- Columns scanned: **{report.scanned_columns}**")
    lines.append(f"- Module-level functions scanned: **{report.scanned_functions}**")
    lines.append(f"- Protocol classes scanned: **{report.scanned_protocols}**")
    lines.append("")
    lines.append(f"- Empty-table findings: **{len(report.empty_tables)}**")
    lines.append(f"- Always-NULL column findings: **{len(report.null_columns)}**")
    lines.append(f"- Dead function candidates: **{len(report.dead_functions)}**")
    lines.append(f"- Dead Protocol candidates: **{len(report.dead_protocols)}**")
    lines.append("")

    # ---- Section A
    lines.append("## A. Empty tables (`COUNT(*) == 0`)")
    lines.append("")
    if not report.empty_tables:
        lines.append("_No empty tables found._")
    else:
        lines.append("| Table | Row count | Note |")
        lines.append("| --- | ---: | --- |")
        for f in sorted(report.empty_tables, key=lambda x: x.table):
            note = f.annotation if f.annotation else "DROP candidate — verify no production wiring (cross-caller grep)"
            lines.append(f"| `{f.table}` | {f.row_count} | {note} |")
    lines.append("")
    lines.append("**Phase 1 fix expectation** (plan §8.4): `deleted_item` should have rows")
    lines.append("post-Phase 1 BDD work. If it appears in the table above, Phase 1 closure")
    lines.append("did not wire deleted_item population — surface as a follow-up.")
    lines.append("")

    # ---- Section B
    lines.append("## B. Columns 100 % NULL in non-empty tables")
    lines.append("")
    if not report.null_columns:
        lines.append("_No always-NULL columns found in non-empty tables._")
    else:
        lines.append("| Table | Column | Total rows | NULL rows |")
        lines.append("| --- | --- | ---: | ---: |")
        for f in sorted(report.null_columns, key=lambda x: (x.table, x.column)):
            lines.append(f"| `{f.table}` | `{f.column}` | {f.total_rows} | {f.null_rows} |")
    lines.append("")
    lines.append("**Interpretation**: a column always NULL on a populated table is a")
    lines.append("strong DROP candidate, but verify it is not a write-path that fires")
    lines.append("rarely (per-disk, per-error, per-recovery). Check writers via")
    lines.append("`rg --type py 'set <col>' personalscraper/`.")
    lines.append("")

    # ---- Section C
    lines.append("## C. Dead function candidates")
    lines.append("")
    lines.append("Heuristic: name appears 0 times in any module other than its definition")
    lines.append("module. Dunder methods, names in `__all__`, common framework hooks")
    lines.append(f"({', '.join(sorted(FUNC_NAME_DENYLIST))}), and class methods are skipped.")
    lines.append("")
    lines.append("FALSE POSITIVE WARNING: a function called via")
    lines.append("`getattr(module, name)`, dispatched by string from a registry, exposed")
    lines.append("via Typer / Click decorators, or imported by a script under `scripts/`")
    lines.append("will appear here. Verify with full-tree grep before any deletion.")
    lines.append("")
    if not report.dead_functions:
        lines.append("_No dead function candidates._")
    else:
        lines.append(f"Showing all {len(report.dead_functions)} candidate(s):")
        lines.append("")
        lines.append("| Name | File | Line |")
        lines.append("| --- | --- | ---: |")
        for f in sorted(report.dead_functions, key=lambda x: (x.file, x.line)):
            lines.append(f"| `{f.name}` | `{f.file}` | {f.line} |")
    lines.append("")

    # ---- Section D
    lines.append("## D. Dead Protocol candidates")
    lines.append("")
    lines.append("Heuristic: ``class X(Protocol):`` whose name is referenced 0 times")
    lines.append("outside the definition module. Protocols used only via structural")
    lines.append("typing (e.g. duck-typed via `def f(x: SomeProtocol)`) with a single")
    lines.append("annotation site in the same module appear here as false positives.")
    lines.append("")
    if not report.dead_protocols:
        lines.append("_No dead Protocol candidates._")
    else:
        lines.append("| Name | File | Line |")
        lines.append("| --- | --- | ---: |")
        for f in sorted(report.dead_protocols, key=lambda x: (x.file, x.line)):
            lines.append(f"| `{f.name}` | `{f.file}` | {f.line} |")
    lines.append("")

    # ---- Cross-refs
    lines.append("## Cross-references")
    lines.append("")
    lines.append("- Sub-phase spec: `docs/features/tech-debt/plan/phase-08-polish.md` §8.4")
    lines.append("- Related sub-phase 8.2 audit: `docs/features/tech-debt/audit/14-pending-op-item-issue.md`")
    lines.append("- BDD audit baseline: `docs/features/tech-debt/audit/05-bdd-audit.md`")
    lines.append("- DESIGN.md §11 (architecture), §9 (BDD lifecycle invariants)")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append(f"python3 scripts/audit-dead-infrastructure.py --db {report.db_path}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit dead infrastructure (SH-17 / CF-G / P11).")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite library DB to audit (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"Markdown report output path (default: {DEFAULT_REPORT})",
    )
    parser.add_argument(
        "--pkg",
        type=Path,
        default=PKG_ROOT,
        help=f"Package root to walk for AST analysis (default: {PKG_ROOT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Generate the dead-infrastructure audit report.

    Returns:
        0 on success, 1 on fatal error (missing DB or write failure).
    """
    args = _parse_args(argv)
    db_path: Path = args.db
    out_path: Path = args.output
    pkg_root: Path = args.pkg

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 1
    if not pkg_root.is_dir():
        print(f"ERROR: package root not found: {pkg_root}", file=sys.stderr)
        return 1

    # Open the DB read-only via URI to guarantee no writes.
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        empty_tables, n_tables = audit_empty_tables(conn)
        null_columns, n_columns = audit_null_columns(conn)
    finally:
        conn.close()

    dead_funcs, dead_protos, n_funcs, n_protos = audit_dead_functions_and_protocols(pkg_root)

    report = AuditReport(
        db_path=db_path,
        empty_tables=empty_tables,
        null_columns=null_columns,
        dead_functions=dead_funcs,
        dead_protocols=dead_protos,
        scanned_tables=n_tables,
        scanned_columns=n_columns,
        scanned_functions=n_funcs,
        scanned_protocols=n_protos,
    )

    markdown = _render_report(report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    print(f"Wrote audit report to {out_path}")
    print(
        f"  empty_tables={len(empty_tables)} null_columns={len(null_columns)} "
        f"dead_funcs={len(dead_funcs)} dead_protocols={len(dead_protos)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
