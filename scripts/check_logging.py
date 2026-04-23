"""AST-based logging convention audit script for personalscraper.

Walks Python source files and flags three categories of violations:

- ERROR: bare ``print()`` calls inside ``personalscraper/`` (except ``tests/``).
- ERROR: ``logging.getLogger()`` calls inside ``personalscraper/`` except
  ``personalscraper/logger.py``, where the stdlib logger is legitimately
  configured.
- WARN: f-string arguments passed to a structlog bound-logger obtained via
  ``get_logger()`` — signals string-mode (eager) interpolation instead of
  the preferred keyword-argument style.

Exit code: 0 when ``--report-only`` is given, or when there are no ERROR-severity
findings. 1 when at least one ERROR-severity finding is present (and not
``--report-only``).

Usage::

    python scripts/check_logging.py [--report-only] [path ...]

If no path arguments are given the script defaults to scanning ``personalscraper/``
relative to the repository root (the parent directory of ``scripts/``).

Baseline (as of 2026-04-23): 0 ERROR offenders, 0 WARN offenders.
"""

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single logging-convention violation found in a source file.

    Attributes:
        path: Absolute (or relative) path to the source file.
        line: 1-based line number of the offending node.
        col: 0-based column offset of the offending node.
        severity: Either ``"ERROR"`` or ``"WARN"``.
        rule: Short identifier for the violated rule.
        message: Human-readable description of the violation.
    """

    path: Path
    line: int
    col: int
    severity: str  # "ERROR" | "WARN"
    rule: str
    message: str


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------


class _LoggingVisitor(ast.NodeVisitor):
    """Collect logging-convention violations from a single AST.

    Attributes:
        findings: Accumulated findings after visiting.
        _structlog_vars: Set of variable names assigned from ``get_logger()``.
        _path: Path of the file being analyzed (used in Finding objects).
        _check_print: Whether to flag bare ``print()`` calls.
        _check_get_logger: Whether to flag ``logging.getLogger()`` calls.
    """

    def __init__(self, path: Path, *, check_print: bool, check_get_logger: bool) -> None:
        """Initialize the visitor.

        Args:
            path: Source file being visited.
            check_print: Emit findings for bare ``print()`` calls.
            check_get_logger: Emit findings for ``logging.getLogger()`` calls.
        """
        self.findings: list[Finding] = []
        self._path = path
        self._check_print = check_print
        self._check_get_logger = check_get_logger
        # Variable names that are bound to a structlog logger via get_logger().
        self._structlog_vars: set[str] = set()

    # ------------------------------------------------------------------
    # First pass: collect get_logger() bindings
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track ``<var> = get_logger(...)`` assignments.

        Args:
            node: An ``Assign`` AST node.
        """
        if isinstance(node.value, ast.Call) and _is_name_call(node.value, "get_logger"):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._structlog_vars.add(target.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Track ``<var>: T = get_logger(...)`` annotated assignments.

        Args:
            node: An ``AnnAssign`` AST node.
        """
        if (
            node.value is not None
            and isinstance(node.value, ast.Call)
            and _is_name_call(node.value, "get_logger")
            and isinstance(node.target, ast.Name)
        ):
            self._structlog_vars.add(node.target.id)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Second pass: flag violations
    # ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        """Inspect each function call for convention violations.

        Args:
            node: A ``Call`` AST node.
        """
        # Rule 1 — bare print()
        if self._check_print and _is_name_call(node, "print"):
            self.findings.append(
                Finding(
                    path=self._path,
                    line=node.lineno,
                    col=node.col_offset,
                    severity="ERROR",
                    rule="no-print",
                    message="bare print() call — use get_logger() instead",
                )
            )

        # Rule 2 — logging.getLogger()
        if self._check_get_logger and _is_attr_call(node, obj="logging", attr="getLogger"):
            self.findings.append(
                Finding(
                    path=self._path,
                    line=node.lineno,
                    col=node.col_offset,
                    severity="ERROR",
                    rule="no-stdlib-logger",
                    message="logging.getLogger() call — use personalscraper.logger.get_logger() instead",
                )
            )

        # Rule 3 — f-string passed to a structlog bound-logger level method
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in self._structlog_vars
            and node.func.attr in {"debug", "info", "warning", "error", "critical", "exception"}
            and node.args
            and isinstance(node.args[0], ast.JoinedStr)
        ):
            self.findings.append(
                Finding(
                    path=self._path,
                    line=node.lineno,
                    col=node.col_offset,
                    severity="WARN",
                    rule="no-fstring-log",
                    message=(
                        f'{node.func.value.id}.{node.func.attr}(f"...") — '
                        "pass keyword args instead of f-strings to structlog"
                    ),
                )
            )

        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_name_call(node: ast.Call, name: str) -> bool:
    """Return True if *node* is a call to a bare name (e.g. ``print(...)``).

    Args:
        node: AST Call node.
        name: Expected function name.

    Returns:
        True when the call's func is an ``ast.Name`` with ``id == name``.
    """
    return isinstance(node.func, ast.Name) and node.func.id == name


def _is_attr_call(node: ast.Call, obj: str, attr: str) -> bool:
    """Return True if *node* is a call to ``obj.attr(...)``.

    Args:
        node: AST Call node.
        obj: Expected object name (e.g. ``"logging"``).
        attr: Expected attribute name (e.g. ``"getLogger"``).

    Returns:
        True when the call's func is an ``ast.Attribute`` matching ``obj.attr``.
    """
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == obj
        and node.func.attr == attr
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

#: Log-level method names recognized on structlog bound loggers.
_LOG_LEVELS = frozenset({"debug", "info", "warning", "error", "critical", "exception"})

#: Name of the module that legitimately calls ``logging.getLogger``.
_LOGGER_MODULE = "logger.py"


def analyze_file(path: Path) -> list[Finding]:
    """Parse and analyze a single Python source file.

    Applies only the rules that are appropriate for the given file:

    * ``no-print`` — applied to all files under analysis.
    * ``no-stdlib-logger`` — skipped for ``personalscraper/logger.py``.
    * ``no-fstring-log`` — applied to all files under analysis.

    Args:
        path: Path to the ``.py`` file to analyze.

    Returns:
        A list of :class:`Finding` objects (may be empty).

    Raises:
        SyntaxError: If the file cannot be parsed as valid Python.
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        raise

    # logging.getLogger is allowed in the one module that wraps it.
    check_get_logger = path.name != _LOGGER_MODULE

    visitor = _LoggingVisitor(path, check_print=True, check_get_logger=check_get_logger)
    visitor.visit(tree)
    return visitor.findings


def analyze_paths(paths: Sequence[Path]) -> list[Finding]:
    """Recursively analyze all ``.py`` files under the given paths.

    Args:
        paths: List of files or directories to scan.

    Returns:
        Aggregated list of :class:`Finding` objects across all files.
    """
    all_findings: list[Finding] = []
    for base in paths:
        targets = sorted(base.rglob("*.py")) if base.is_dir() else [base]
        for py_file in targets:
            try:
                all_findings.extend(analyze_file(py_file))
            except SyntaxError as exc:
                print(f"PARSE ERROR {py_file}: {exc}", file=sys.stderr)
    return all_findings


def _default_scan_root() -> Path:
    """Return the default ``personalscraper/`` directory.

    Resolves relative to the parent of this script (i.e. the repository root).

    Returns:
        Path to ``<repo_root>/personalscraper/``.
    """
    return Path(__file__).resolve().parent.parent / "personalscraper"


def _print_findings(findings: list[Finding]) -> None:
    """Print findings to stdout in a human-readable format.

    Args:
        findings: List of findings to display.
    """
    for f in findings:
        print(f"{f.path}:{f.line}:{f.col}: [{f.severity}] {f.rule}: {f.message}")

    errors = [f for f in findings if f.severity == "ERROR"]
    warns = [f for f in findings if f.severity == "WARN"]
    print(f"\n{len(findings)} finding(s): {len(errors)} error(s), {len(warns)} warning(s)")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the logging-convention audit script.

    Args:
        argv: Command-line arguments. Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        Exit code: 0 if no ERROR-severity findings (or ``--report-only``), 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Audit personalscraper/ for logging-convention violations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Always exit 0 — report offenders without failing (e.g. for CI dashboards).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        metavar="PATH",
        help="Files or directories to scan. Defaults to personalscraper/.",
    )
    args = parser.parse_args(argv)

    scan_paths: list[Path] = args.paths if args.paths else [_default_scan_root()]

    findings = analyze_paths(scan_paths)
    _print_findings(findings)

    if args.report_only:
        return 0

    has_errors = any(f.severity == "ERROR" for f in findings)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
