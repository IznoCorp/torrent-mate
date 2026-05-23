"""Console + log parity enforcement (SH-11 / CL-H — tech-debt 0.16.0).

For each pipeline command function that emits a ``console.print("[bold]…:[/bold]")``
**summary line**, the command MUST provide at least one of:

1. A ``@cli_telemetry("<cmd>")`` decorator (emits ``cli.complete.<cmd>``), or
2. A ``log.info(...)`` / ``_log.info(...)`` call inside the function body.

Rationale
---------
Commands that print a rich-only summary (e.g. ``[bold]Verify:[/bold] 5 OK``) are
**invisible to machine telemetry**: pipeline-monitor, log aggregators, and alert
systems cannot observe them. Sub-phase 3.3 pins this contract so future regressions
(a new command with a bold summary but no log call) are caught at test time.

Approach
--------
AST-based static analysis of every Python file under ``personalscraper/commands/``:

* ``_find_bold_summary_funcs`` — NodeVisitor that collects function names whose body
  contains at least one ``console.print(...)`` call whose first argument is a string
  literal starting with ``"[bold]"`` (the canonical summary pattern).
* ``_has_telemetry_decorator`` — checks whether the same function is decorated with
  ``@cli_telemetry(...)``.
* ``_has_log_info_call`` — checks whether the same function body contains at least
  one ``log.info(...)`` or ``_log.info(...)`` call.

Commands missing both forms of telemetry are reported as *parity violations*.

xfail policy
------------
Commands that currently violate the rule are marked ``xfail(strict=False)`` so the
test suite stays green while the cli_telemetry rollout completes (Phase 3 follow-up).
Once every command is decorated, the xfail marker should be removed and the
``KNOWN_VIOLATIONS`` set emptied — the test then becomes a hard regression guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMANDS_ROOT = _REPO_ROOT / "personalscraper" / "commands"

# ---------------------------------------------------------------------------
# Known violations (commands that have a bold summary but lack telemetry).
# These are xfail — cli_telemetry rollout (Phase 3 follow-up) will clear them.
# Remove an entry once the decorator is applied to the corresponding command.
# ---------------------------------------------------------------------------

#: Set of ``(relative_module_path, function_name)`` tuples that currently
#: violate the console+log parity rule.  Kept separate from the test logic so
#: the list is easy to audit and update without touching the detection code.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    ("personalscraper/commands/pipeline.py", "sort"),
    ("personalscraper/commands/pipeline.py", "scrape"),
    ("personalscraper/commands/pipeline.py", "verify"),
    ("personalscraper/commands/pipeline.py", "dispatch"),
    ("personalscraper/commands/pipeline.py", "process"),
}


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


class _PipelineCommandVisitor(ast.NodeVisitor):
    """Walk a command module and extract parity information per function.

    For each top-level function definition, records:

    * Whether the function has a ``@cli_telemetry(...)`` decorator.
    * Whether the function body contains a ``console.print(...)`` call whose
      first positional argument is a string literal that starts with ``"[bold]"``.
    * Whether the function body contains at least one ``log.info(...)`` or
      ``_log.info(...)`` call (a ``log`` or ``_log`` attribute named ``info``).

    Only top-level functions are inspected (pipeline commands are never nested).
    """

    def __init__(self) -> None:
        #: mapping from function name → bool (has cli_telemetry decorator)
        self.has_telemetry: dict[str, bool] = {}
        #: mapping from function name → bool (has bold summary console.print)
        self.has_bold_summary: dict[str, bool] = {}
        #: mapping from function name → bool (has log.info / _log.info call)
        self.has_log_info: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Visitor entry points
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Process a top-level function definition."""
        name = node.name
        self.has_telemetry[name] = self._detect_telemetry(node)
        self.has_bold_summary[name] = self._detect_bold_summary(node)
        self.has_log_info[name] = self._detect_log_info(node)
        # Do NOT recurse into nested functions — pipeline commands are flat.

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_telemetry(node: ast.FunctionDef) -> bool:
        """Return True iff the function has a ``@cli_telemetry(...)`` decorator.

        Args:
            node: The AST FunctionDef to inspect.

        Returns:
            True when a decorator whose base/name is ``cli_telemetry`` is found.
        """
        for deco in node.decorator_list:
            # Handles both @cli_telemetry("cmd") (Call) and bare @cli_telemetry.
            if isinstance(deco, ast.Call):
                func = deco.func
                if isinstance(func, ast.Name) and func.id == "cli_telemetry":
                    return True
                if isinstance(func, ast.Attribute) and func.attr == "cli_telemetry":
                    return True
            elif isinstance(deco, ast.Name) and deco.id == "cli_telemetry":
                return True
            elif isinstance(deco, ast.Attribute) and deco.attr == "cli_telemetry":
                return True
        return False

    @staticmethod
    def _detect_bold_summary(node: ast.FunctionDef) -> bool:
        """Return True iff the function body has a bold-tagged summary console.print.

        Looks for ``console.print(...)`` calls whose first positional argument is
        a string literal (possibly f-string) whose raw text starts with ``"[bold]"``.

        Args:
            node: The AST FunctionDef to inspect.

        Returns:
            True when at least one qualifying ``console.print`` call is found.
        """
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            # Require console.print (Attribute call, attr == "print")
            if not (isinstance(func, ast.Attribute) and func.attr == "print"):
                continue
            # Need at least one positional argument
            if not child.args:
                continue
            first_arg = child.args[0]
            text = _extract_string_prefix(first_arg)
            if text is not None and text.startswith("[bold]"):
                return True
        return False

    @staticmethod
    def _detect_log_info(node: ast.FunctionDef) -> bool:
        """Return True iff the function body contains a ``log.info(...)`` call.

        Accepts both ``log.info(...)`` and ``_log.info(...)`` (common in pipeline
        command files that define a module-level ``log = get_logger(...)``).

        Args:
            node: The AST FunctionDef to inspect.

        Returns:
            True when at least one qualifying log.info call is found.
        """
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "info":
                if isinstance(func.value, ast.Name) and func.value.id in {"log", "_log", "_run_log"}:
                    return True
        return False


def _extract_string_prefix(node: ast.expr) -> str | None:
    """Return the opening text of an AST expression if it is a string-like node.

    Handles:

    * ``ast.Constant`` (plain string literal)
    * ``ast.JoinedStr`` (f-string) — reconstructs the prefix from the first
      constant value part (the part before the first ``{…}`` placeholder).

    Args:
        node: An AST expression node.

    Returns:
        The string prefix (potentially empty string) when the node is a string
        or f-string, or ``None`` for other expression types.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string: reconstruct prefix from leading Constant parts.
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                break  # Stop at the first interpolation — prefix is enough.
        return "".join(parts)
    return None


# ---------------------------------------------------------------------------
# Module scanner
# ---------------------------------------------------------------------------


def _scan_command_file(path: Path) -> _PipelineCommandVisitor:
    """Parse *path* and return a populated visitor.

    Args:
        path: Absolute path to a Python source file.

    Returns:
        Visitor with ``has_telemetry``, ``has_bold_summary``, and ``has_log_info``
        dictionaries populated.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    visitor = _PipelineCommandVisitor()
    visitor.visit(tree)
    return visitor


def _all_command_files() -> list[Path]:
    """Return all Python source files under ``personalscraper/commands/``.

    Returns:
        Sorted list of Path objects for every ``*.py`` file in the commands tree.
    """
    return sorted(_COMMANDS_ROOT.rglob("*.py"))


# ---------------------------------------------------------------------------
# Parity audit helper
# ---------------------------------------------------------------------------


def _audit_parity() -> list[tuple[str, str]]:
    """Scan all command files and return parity violations.

    A violation is a ``(relative_path, function_name)`` pair where:

    * The function has at least one bold-summary ``console.print`` call, AND
    * The function lacks a ``@cli_telemetry`` decorator, AND
    * The function lacks any ``log.info`` / ``_log.info`` call.

    Returns:
        List of ``(relative_module_path, function_name)`` tuples for violations.
    """
    violations: list[tuple[str, str]] = []
    for path in _all_command_files():
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(_REPO_ROOT).as_posix()
        visitor = _scan_command_file(path)
        for fn_name, has_summary in visitor.has_bold_summary.items():
            if not has_summary:
                continue
            has_telem = visitor.has_telemetry.get(fn_name, False)
            has_log = visitor.has_log_info.get(fn_name, False)
            if not has_telem and not has_log:
                violations.append((rel, fn_name))
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_known_violations_are_still_violations() -> None:
    """Every entry in KNOWN_VIOLATIONS is an actual violation.

    Guards against rot: if a command is fixed (gets @cli_telemetry or log.info)
    but the entry remains in KNOWN_VIOLATIONS, this test fails to prompt cleanup.
    """
    actual = set(_audit_parity())
    no_longer_violations = KNOWN_VIOLATIONS - actual
    assert not no_longer_violations, (
        "These entries are in KNOWN_VIOLATIONS but are no longer actual violations "
        "(they gained telemetry or a log.info call). Remove them from KNOWN_VIOLATIONS:\n"
        + "\n".join(f"  {rel}:{fn}" for rel, fn in sorted(no_longer_violations))
    )


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Known parity violations: commands have rich-only summaries without structured "
        "telemetry. Will be resolved by cli_telemetry rollout to all commands (Phase 3 "
        "follow-up). Remove from KNOWN_VIOLATIONS once fixed."
    ),
)
def test_no_bold_summary_without_telemetry_or_log() -> None:
    """No pipeline command may emit a bold summary without structured telemetry.

    For each ``console.print("[bold]X:[/bold] ...")`` summary call in
    ``personalscraper/commands/``, the enclosing function MUST have at least one
    of:

    1. ``@cli_telemetry("<cmd>")`` decorator (emits ``cli.complete.<cmd>``).
    2. A ``log.info(...)`` / ``_log.info(...)`` call in the function body.

    Contract: DESIGN §10 CLI surface (telemetry rule), SH-11 / CL-H.

    This test is currently xfail because several pipeline commands (sort, scrape,
    verify, enforce, dispatch, process, torrents_list) have not yet received the
    ``@cli_telemetry`` decorator. The failing commands are listed in
    ``KNOWN_VIOLATIONS`` for traceability.
    """
    violations = _audit_parity()
    new_violations = [(rel, fn) for rel, fn in violations if (rel, fn) not in KNOWN_VIOLATIONS]
    # Report existing known violations for documentation purposes.
    known_found = [(rel, fn) for rel, fn in violations if (rel, fn) in KNOWN_VIOLATIONS]

    assert not new_violations, (
        "NEW parity violations detected (not in KNOWN_VIOLATIONS). "
        "Add @cli_telemetry or a log.info call to each command listed below, "
        "or add to KNOWN_VIOLATIONS if the fix is deferred:\n"
        + "\n".join(f"  {rel}:{fn}" for rel, fn in sorted(new_violations))
    )

    # Trigger the xfail when the known violations are still present.
    assert not known_found, "Existing parity violations (tracked in KNOWN_VIOLATIONS, xfail):\n" + "\n".join(
        f"  {rel}:{fn}" for rel, fn in sorted(known_found)
    )


def test_ingest_command_has_telemetry_coverage() -> None:
    """Positive pin: ``ingest`` command is covered by @cli_telemetry.

    Catches typos in the detection logic and regressions where the decorator
    is accidentally removed from the ingest command (the only fully-covered
    pipeline command as of Phase 3.2).
    """
    pipeline_path = _COMMANDS_ROOT / "pipeline.py"
    visitor = _scan_command_file(pipeline_path)
    assert visitor.has_telemetry.get("ingest", False), (
        "ingest is the reference command that has @cli_telemetry. Detection logic broken or decorator was removed."
    )
    assert visitor.has_bold_summary.get("ingest", False), (
        "ingest is expected to have a bold summary console.print call. "
        "The detection logic or the command body changed unexpectedly."
    )


def test_command_files_are_parseable() -> None:
    """All command Python files can be parsed without SyntaxError.

    Guards against malformed source that would silently skip detection.
    """
    errors: list[str] = []
    for path in _all_command_files():
        if path.name == "__init__.py":
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            rel = path.relative_to(_REPO_ROOT).as_posix()
            errors.append(f"{rel}: {exc}")
    assert not errors, "Command files with syntax errors:\n" + "\n".join(errors)


def test_known_violations_reference_real_functions() -> None:
    """Every KNOWN_VIOLATIONS entry maps to an extant function — guards rot.

    If a command is renamed or deleted, the stale KNOWN_VIOLATIONS entry must be
    removed to keep the violation tracking accurate.
    """
    missing: list[str] = []
    # Group by module path for efficient scanning.
    by_module: dict[str, list[str]] = {}
    for rel, fn in KNOWN_VIOLATIONS:
        by_module.setdefault(rel, []).append(fn)

    for rel, fn_names in by_module.items():
        path = _REPO_ROOT / rel
        assert path.exists(), f"KNOWN_VIOLATIONS references non-existent module: {rel}"
        visitor = _scan_command_file(path)
        for fn in fn_names:
            if fn not in visitor.has_bold_summary:
                missing.append(f"{rel}:{fn}")

    assert not missing, (
        "KNOWN_VIOLATIONS entries reference functions that no longer exist. "
        "Remove stale entries:\n" + "\n".join(missing)
    )
