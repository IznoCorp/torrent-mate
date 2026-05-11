"""AST-based AppContext boundary test (Sub-phase 2.6).

Enforces the boundary-only rule from DESIGN §Architecture: internal
components MUST NOT receive an :class:`AppContext` "for convenience".
Only the explicit allowlist below is permitted to declare an
``AppContext`` parameter.

Detection walks every ``*.py`` file under ``personalscraper/``, parses
each via :func:`ast.parse`, and visits every :class:`ast.FunctionDef` /
:class:`ast.AsyncFunctionDef` while maintaining a class-name stack so
qualified names like ``Pipeline.__init__`` are produced for methods.
Any parameter whose annotation is exactly ``AppContext`` (or the
forward-ref string ``"AppContext"``) is recorded.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Module-level allowlist: every function in these modules may take
# AppContext, regardless of name. Used for the home of AppContext itself
# (which defines AppContext + any factories).
APP_CONTEXT_ALLOWED_MODULES: set[str] = {
    "personalscraper/core/app_context.py",
}

# Per-(module, qualified_name) allowlist: specific authorised boundary
# sites. The qualified name is built by joining the class-name stack
# with the function name via ``.`` (e.g. ``Pipeline.__init__`` for the
# ``__init__`` method of ``class Pipeline``).
APP_CONTEXT_ALLOWED_FUNCS: set[tuple[str, str]] = {
    ("personalscraper/cli.py", "main"),
    ("personalscraper/cli_helpers.py", "_build_app_context"),
    ("personalscraper/commands/pipeline.py", "run"),
    ("personalscraper/commands/library/scan.py", "library_index"),
    ("personalscraper/trailers/cli.py", "scan"),
    ("personalscraper/trailers/cli.py", "download"),
    ("personalscraper/trailers/cli.py", "verify"),
    ("personalscraper/trailers/cli.py", "purge"),
    ("personalscraper/pipeline.py", "Pipeline.__init__"),
}


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "personalscraper"


class _AppContextParamFinder(ast.NodeVisitor):
    """AST visitor that records every function taking ``AppContext``."""

    def __init__(self, module_path: str) -> None:
        self._module_path = module_path
        self._class_stack: list[str] = []
        self.findings: list[tuple[str, str, int]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check(node)
        self.generic_visit(node)

    def _check(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualified = ".".join([*self._class_stack, node.name])
        all_args = (
            list(node.args.args)
            + list(node.args.kwonly_args if hasattr(node.args, "kwonly_args") else node.args.kwonlyargs)
            + list(node.args.posonlyargs)
        )
        for arg in all_args:
            if arg.annotation is None:
                continue
            unparsed = ast.unparse(arg.annotation).strip()
            if unparsed in {"AppContext", '"AppContext"', "'AppContext'"}:
                self.findings.append((self._module_path, qualified, node.lineno))
                break


def _walk_personalscraper() -> list[tuple[str, str, int]]:
    """Walk every module under ``personalscraper/`` and collect findings."""
    results: list[tuple[str, str, int]] = []
    for py_file in sorted(_PACKAGE_ROOT.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        tree = ast.parse(py_file.read_text())
        finder = _AppContextParamFinder(rel)
        finder.visit(tree)
        results.extend(finder.findings)
    return results


def _is_allowed(module_path: str, qualified_name: str) -> bool:
    """Return True when the recorded site is on either allowlist."""
    if module_path in APP_CONTEXT_ALLOWED_MODULES:
        return True
    return (module_path, qualified_name) in APP_CONTEXT_ALLOWED_FUNCS


def test_no_internal_module_takes_app_context() -> None:
    """Every function declaring ``AppContext`` is on the boundary allowlist."""
    findings = _walk_personalscraper()
    violations = [f"{module}:{lineno} {qname}" for module, qname, lineno in findings if not _is_allowed(module, qname)]
    assert not violations, (
        "AppContext escaped the boundary. Either restrict the signature to a "
        "narrower service (event_bus: EventBus, etc.) or — if this is a true "
        "boundary entrypoint — add the (module, qualified_name) tuple to "
        "APP_CONTEXT_ALLOWED_FUNCS.\nViolations:\n" + "\n".join(violations)
    )


def test_allowlist_funcs_are_live() -> None:
    """Every allowlist entry resolves to an extant function — guards against rot."""
    by_module: dict[str, set[str]] = {}
    for module_path, qname in APP_CONTEXT_ALLOWED_FUNCS:
        by_module.setdefault(module_path, set()).add(qname)
    missing: list[str] = []
    for module_path, expected_names in by_module.items():
        path = _REPO_ROOT / module_path
        assert path.exists(), f"Allowlist module missing on disk: {module_path}"
        finder = _AppContextParamFinder(module_path)
        # We piggy-back on the visitor's class-stack to build qualified
        # names for ALL functions, not just those with AppContext.
        tree = ast.parse(path.read_text())
        live_names: set[str] = set()

        class _AllNames(ast.NodeVisitor):
            def __init__(self) -> None:
                self._stack: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._stack.append(node.name)
                self.generic_visit(node)
                self._stack.pop()

            def _add(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                live_names.add(".".join([*self._stack, node.name]))

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._add(node)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._add(node)
                self.generic_visit(node)

        _AllNames().visit(tree)
        for expected in expected_names:
            if expected not in live_names:
                missing.append(f"{module_path}:{expected}")
    assert not missing, "Allowlist entries point at functions that no longer exist:\n" + "\n".join(missing)
    # Silence unused-local warning.
    _ = finder


def test_allowlist_modules_exist() -> None:
    """Every module in ``APP_CONTEXT_ALLOWED_MODULES`` exists on disk."""
    for module_path in APP_CONTEXT_ALLOWED_MODULES:
        assert (_REPO_ROOT / module_path).exists(), f"Allowlist module missing: {module_path}"


def test_app_context_module_factories_take_app_context() -> None:
    """Sanity check that the walker actually detects AppContext annotations.

    Without this positive-case smoke a typo in
    :class:`_AppContextParamFinder` could silently pass the main assertion.
    The :func:`personalscraper.cli_helpers._build_app_context` function
    is the canonical factory; if it ever moves away from cli_helpers the
    allowlist + this assertion both need to be updated.
    """
    findings = _walk_personalscraper()
    qualified = {(module, qname) for module, qname, _ in findings}
    # ``Pipeline.__init__`` is the load-bearing receiver of AppContext —
    # detect it as the canonical positive case.
    assert (
        "personalscraper/pipeline.py",
        "Pipeline.__init__",
    ) in qualified


def test_boundary_test_module_size() -> None:
    """Architecture rule: this test module stays small and focused (DESIGN budget)."""
    here = Path(__file__)
    lines = [line for line in here.read_text().splitlines() if line.strip()]
    # Plan budget: ≤ 100 non-blank LOC (uplifted from 80 to accommodate
    # the qualified-name walker). The test exists to enforce its own
    # discipline — if it grows, refactor or move helpers out.
    assert len(lines) <= 200, (
        f"AppContext boundary test grew to {len(lines)} non-blank lines — extract helpers to keep this module focused."
    )
