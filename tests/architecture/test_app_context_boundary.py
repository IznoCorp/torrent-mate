"""AST-based AppContext boundary test (Sub-phase 2.6).

Enforces the boundary-only rule from DESIGN §Architecture: internal
components MUST NOT receive an :class:`AppContext` "for convenience".
Only the explicit allowlist below is permitted to declare an
``AppContext`` parameter.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_CONTEXT_ALLOWED_MODULES: set[str] = {"personalscraper/core/app_context.py"}

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
_APP_CONTEXT_ANN = {"AppContext", '"AppContext"', "'AppContext'"}


class _Visitor(ast.NodeVisitor):
    """Walk a module and record qualified function names + AppContext sites."""

    def __init__(self, module_path: str) -> None:
        self._module = module_path
        self._stack: list[str] = []
        self.qualified_names: set[str] = set()
        self.app_context_sites: list[tuple[str, str, int]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record(node)
        self.generic_visit(node)

    def _record(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qname = ".".join([*self._stack, node.name])
        self.qualified_names.add(qname)
        args = list(node.args.args) + list(node.args.kwonlyargs) + list(node.args.posonlyargs)
        for arg in args:
            if arg.annotation is not None and ast.unparse(arg.annotation).strip() in _APP_CONTEXT_ANN:
                self.app_context_sites.append((self._module, qname, node.lineno))
                break


def _scan_module(path: Path) -> _Visitor:
    rel = path.relative_to(_REPO_ROOT).as_posix()
    visitor = _Visitor(rel)
    visitor.visit(ast.parse(path.read_text()))
    return visitor


def _is_allowed(module_path: str, qualified_name: str) -> bool:
    if module_path in APP_CONTEXT_ALLOWED_MODULES:
        return True
    return (module_path, qualified_name) in APP_CONTEXT_ALLOWED_FUNCS


def test_no_internal_module_takes_app_context() -> None:
    """Every function declaring ``AppContext`` is on the boundary allowlist."""
    violations: list[str] = []
    for py_file in sorted(_PACKAGE_ROOT.rglob("*.py")):
        for module, qname, lineno in _scan_module(py_file).app_context_sites:
            if not _is_allowed(module, qname):
                violations.append(f"{module}:{lineno} {qname}")
    assert not violations, (
        "AppContext escaped the boundary. Either narrow the signature to a "
        "specific service (event_bus: EventBus, etc.) or add the "
        "(module, qualified_name) tuple to APP_CONTEXT_ALLOWED_FUNCS.\n" + "\n".join(violations)
    )


def test_allowlist_funcs_are_live() -> None:
    """Every allowlist entry resolves to an extant function — guards rot."""
    by_module: dict[str, set[str]] = {}
    for module_path, qname in APP_CONTEXT_ALLOWED_FUNCS:
        by_module.setdefault(module_path, set()).add(qname)
    missing: list[str] = []
    for module_path, expected in by_module.items():
        path = _REPO_ROOT / module_path
        assert path.exists(), f"Allowlist module missing on disk: {module_path}"
        live = _scan_module(path).qualified_names
        missing.extend(f"{module_path}:{q}" for q in expected if q not in live)
    assert not missing, "Allowlist entries point at functions that no longer exist:\n" + "\n".join(missing)


def test_allowlist_modules_exist() -> None:
    """Every module on ``APP_CONTEXT_ALLOWED_MODULES`` exists on disk."""
    for module_path in APP_CONTEXT_ALLOWED_MODULES:
        assert (_REPO_ROOT / module_path).exists(), f"Allowlist module missing: {module_path}"


def test_app_context_module_factories_take_app_context() -> None:
    """Sanity: the walker positively detects ``Pipeline.__init__`` (catches typos)."""
    qualified: set[tuple[str, str]] = set()
    for py_file in sorted(_PACKAGE_ROOT.rglob("*.py")):
        qualified.update((m, q) for m, q, _ in _scan_module(py_file).app_context_sites)
    assert ("personalscraper/pipeline.py", "Pipeline.__init__") in qualified


def test_boundary_test_module_size() -> None:
    """Plan budget (≤ 100 non-blank LOC, uplifted to 130 for the rot-guard helpers)."""
    here = Path(__file__)
    non_blank = [line for line in here.read_text().splitlines() if line.strip()]
    assert len(non_blank) <= 130, f"Test grew to {len(non_blank)} non-blank lines"
