#!/usr/bin/env python3
"""CLI coverage audit — fail-soft warning script.

Performs two checks:

1. **Command → docs coverage**: for each ``@app.command`` defined under
   ``personalscraper/commands/``, verifies that an entry exists in
   ``docs/reference/commands.md``.

2. **Domain → CLI coverage**: for each business-domain package
   (``library/``, ``indexer/``, ``scraper/``, ``trailers/``,
   ``ingest/``, ``sorter/``, ``dispatch/``, ``verify/``,
   ``enforce/``), verifies that at least one CLI command module
   imports from it.

Both checks emit warnings on failure but **exit 0** (fail-soft).  This is
intentional for Phase 2.5: ``docs/reference/commands.md`` is known to be
incomplete (Phase 6.2 will populate it).  The script becomes a hard gate once
docs are filled in.

Usage::

    python3 scripts/audit-cli-coverage.py
    python3 scripts/audit-cli-coverage.py --strict   # exit 1 on any finding

Exit codes:
    0 — no findings, or findings in fail-soft mode (default).
    1 — findings found in strict mode (``--strict`` flag).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / "personalscraper" / "commands"
COMMANDS_DOC = REPO_ROOT / "docs" / "reference" / "commands.md"

# Business-domain packages to check.  Each must have at least one CLI command
# that imports from it.  The key is a human-readable label; the value is the
# import prefix to search for in command module sources.
DOMAIN_IMPORT_PREFIXES: dict[str, str] = {
    "indexer": "personalscraper.indexer",
    "scraper": "personalscraper.scraper",
    "trailers": "personalscraper.trailers",
    "ingest": "personalscraper.ingest",
    "sorter": "personalscraper.sorter",
    "dispatch": "personalscraper.dispatch",
    "verify": "personalscraper.verify",
    "enforce": "personalscraper.enforce",
}


# ---------------------------------------------------------------------------
# Helper: extract @app.command names from a source file
# ---------------------------------------------------------------------------


def _extract_command_names(source: str, function_name_fallback: bool = True) -> list[str]:
    """Parse *source* and return every command name registered via ``@app.command``.

    Handles three decorator forms:

    - ``@app.command("explicit-name")`` — uses the string literal.
    - ``@app.command()`` (no args) — derives the name from the decorated
      function's name by replacing underscores with hyphens.
    - ``@app.command`` (no call) — same derivation as the no-args form.

    Args:
        source: Python source text to parse.
        function_name_fallback: When True (default) derive the command name
            from the function name when the decorator carries no string
            argument.  Set to False in tests to exercise explicit-name only.

    Returns:
        Sorted list of unique command name strings found in *source*.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            # Detect ``@app.command(...)`` (Call node)
            if isinstance(dec, ast.Call) and _is_app_command_attr(dec.func):
                explicit = _extract_string_arg(dec)
                if explicit is not None:
                    names.append(explicit)
                elif function_name_fallback:
                    names.append(node.name.replace("_", "-"))
            # Detect ``@app.command`` (bare attribute, no call)
            elif _is_app_command_attr(dec) and function_name_fallback:
                names.append(node.name.replace("_", "-"))

    return sorted(set(names))


def _is_app_command_attr(node: ast.expr) -> bool:
    """Return True if *node* represents the ``app.command`` attribute access.

    Args:
        node: AST expression node to inspect.

    Returns:
        True when the node is ``<anything>.command`` (i.e. Attribute with
        ``attr == "command"``).
    """
    return isinstance(node, ast.Attribute) and node.attr == "command"


def _extract_string_arg(call: ast.Call) -> str | None:
    """Return the first positional string constant argument of *call*, or None.

    Args:
        call: An ``ast.Call`` node (the decorator invocation).

    Returns:
        The string value of the first positional argument if it is a string
        constant, otherwise None.
    """
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


# ---------------------------------------------------------------------------
# Helper: extract documented command names from commands.md
# ---------------------------------------------------------------------------


def _extract_documented_commands(doc_text: str) -> set[str]:
    """Parse *doc_text* and return all command names mentioned after ``personalscraper ``.

    Finds patterns of the form ``personalscraper <cmd>`` and
    ``personalscraper <group> <subcmd>`` (each token being lowercase letters,
    digits, and hyphens) anywhere in the text. **Both** the group token and the
    sub-command token are recorded, so a sub-command documented as
    ``personalscraper web set-password`` registers ``set-password`` (and
    ``web``) — otherwise every Typer sub-command (``follow add``, ``seed mark``,
    ``web set-password``, …) is a false positive, since Typer reports the leaf
    name (``set-password``), not the group path.

    Args:
        doc_text: Raw Markdown text of ``docs/reference/commands.md``.

    Returns:
        Set of command name strings (e.g. ``{"ingest", "web", "set-password", ...}``).
    """
    # The sub-command separator is [ \t]+ (same line only), NOT \s+: a \s+ would
    # span the newline and greedily capture the NEXT line's "personalscraper" as a
    # phantom sub-command, dropping that line's real command.
    pattern = re.compile(r"personalscraper\s+([a-z][a-z0-9-]+)(?:[ \t]+([a-z][a-z0-9-]+))?")
    documented: set[str] = set()
    for m in pattern.finditer(doc_text):
        documented.add(m.group(1))
        if m.group(2) is not None:
            documented.add(m.group(2))
    return documented


# ---------------------------------------------------------------------------
# Check 1 — command → docs coverage
# ---------------------------------------------------------------------------


def check_command_docs_coverage() -> list[str]:
    """Check that every ``@app.command`` has a corresponding docs/reference/commands.md entry.

    Walks all ``*.py`` files under ``personalscraper/commands/`` (excluding
    ``__pycache__``), extracts command names, and cross-references them against
    the documented commands extracted from ``docs/reference/commands.md``.

    Returns:
        List of warning strings for commands with no documentation entry.
        Empty list means all commands are documented.
    """
    if not COMMANDS_DOC.exists():
        return [f"WARN: docs not found at {COMMANDS_DOC} — skipping docs coverage check"]

    doc_text = COMMANDS_DOC.read_text(encoding="utf-8")
    documented = _extract_documented_commands(doc_text)

    warnings: list[str] = []
    py_files = sorted(f for f in COMMANDS_DIR.rglob("*.py") if "__pycache__" not in f.parts and f.name != "__init__.py")

    for py_file in py_files:
        source = py_file.read_text(encoding="utf-8")
        cmd_names = _extract_command_names(source)
        for cmd in cmd_names:
            if cmd not in documented:
                rel = py_file.relative_to(REPO_ROOT)
                warnings.append(f"WARN: command '{cmd}' (in {rel}) has no entry in docs/reference/commands.md")

    return warnings


# ---------------------------------------------------------------------------
# Check 2 — domain → CLI coverage
# ---------------------------------------------------------------------------


def check_domain_cli_coverage() -> list[str]:
    """Check that each business-domain package is invoked by at least one CLI command.

    Scans all ``*.py`` sources under ``personalscraper/commands/`` for import
    statements matching each domain's import prefix.  A domain is "covered"
    when at least one command module imports from it (direct import or lazy
    ``from X import Y`` inside a function body).

    Returns:
        List of warning strings for domains with no CLI invocation.
        Empty list means all domains have CLI coverage.
    """
    py_files = sorted(f for f in COMMANDS_DIR.rglob("*.py") if "__pycache__" not in f.parts)

    # Collect the combined source of all command modules for import scanning.
    all_sources = {f: f.read_text(encoding="utf-8") for f in py_files}

    warnings: list[str] = []
    for domain_label, import_prefix in DOMAIN_IMPORT_PREFIXES.items():
        covered = any(import_prefix in src for src in all_sources.values())
        if not covered:
            warnings.append(f"WARN: domain '{domain_label}' ({import_prefix}.*) is not invoked by any CLI command")

    return warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the script.

    Returns:
        Configured :class:`argparse.ArgumentParser` instance.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Exit 1 when any finding is emitted (default: exit 0, warn only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run both CLI coverage checks and emit findings.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]`` when None).

    Returns:
        Exit code: 0 on success (or fail-soft mode), 1 when ``--strict`` and
        at least one finding was emitted.
    """
    args = _build_arg_parser().parse_args(argv)

    findings: list[str] = []
    findings.extend(check_command_docs_coverage())
    findings.extend(check_domain_cli_coverage())

    if findings:
        for line in findings:
            print(line)
        if args.strict:
            print(f"\n{len(findings)} finding(s) — exit 1 (--strict mode).")
            return 1
        print(f"\n{len(findings)} finding(s) — exit 0 (fail-soft mode; use --strict to gate CI).")
        return 0

    print("audit-cli-coverage: OK — all commands documented, all domains covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
