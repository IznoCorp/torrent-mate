"""AST-based layering guard: core/ and conf/ must not import upward (arch-cleanup-2 Phase 2).

Enforces the architecture invariant from docs/reference/architecture.md:
core/ and conf/ are the lowest layers and must not import from api/, scraper/,
pipeline/, dispatch/, verify/, library/, indexer/, or trailers/.

Allow-listed exceptions (documented boundaries):
- personalscraper.logger — leaf utility, allow-listed in core/ and conf/
- core/app_context.py importing personalscraper.api.metadata.registry
  under TYPE_CHECKING — the AppContext boundary, already tested separately
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "personalscraper"

# Upward targets that core/ and conf/ must never import at runtime.
_FORBIDDEN_PREFIXES = (
    "personalscraper.api",
    "personalscraper.scraper",
    "personalscraper.pipeline",
    "personalscraper.dispatch",
    "personalscraper.verify",
    "personalscraper.library",
    "personalscraper.indexer",
    "personalscraper.trailers",
)

# Modules that are structural exceptions — checked independently elsewhere.
_ALLOWED_MODULES = {
    "personalscraper/core/app_context.py",  # TYPE_CHECKING registry import — AppContext boundary
}


def _is_type_checking_block(node: ast.AST, tree: ast.Module) -> bool:
    """Return True if ``node`` is nested inside an ``if TYPE_CHECKING:`` block."""
    for top in ast.walk(tree):
        if isinstance(top, ast.If):
            test = top.test
            is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            )
            if is_tc:
                # Walk body and orelse — if node is in this subtree it's guarded.
                for child in ast.walk(top):
                    if child is node:
                        return True
    return False


def _collect_violations(py_file: Path) -> list[str]:
    """Return list of violation strings for ``py_file``."""
    rel = py_file.relative_to(_REPO_ROOT).as_posix()
    if rel in _ALLOWED_MODULES:
        return []
    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Determine the full module name being imported.
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                # Reconstruct absolute path from relative imports.
                if node.level and node.level > 0:
                    # Relative import — resolve against the file's package.
                    pkg_parts = rel.replace(".py", "").replace("/", ".").split(".")
                    base = pkg_parts[: -(node.level)]
                    module = ".".join(base) + ("." + module if module else "")
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            else:
                continue
            # Check against forbidden prefixes.
            for prefix in _FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    # Allow if guarded by TYPE_CHECKING.
                    if _is_type_checking_block(node, tree):
                        break
                    violations.append(f"{rel}:{node.lineno}: imports {module!r}")
                    break
    return violations


def test_core_does_not_import_upward() -> None:
    """No module under core/ imports api/, scraper/, or any upper layer at runtime."""
    core_root = _PACKAGE_ROOT / "core"
    violations: list[str] = []
    for py_file in sorted(core_root.rglob("*.py")):
        violations.extend(_collect_violations(py_file))
    assert not violations, "core/ has upward import leaks (fix by importing from core._contracts):\n" + "\n".join(
        violations
    )


def test_conf_does_not_import_upward() -> None:
    """No module under conf/ imports api/, scraper/, or any upper layer at runtime."""
    conf_root = _PACKAGE_ROOT / "conf"
    violations: list[str] = []
    for py_file in sorted(conf_root.rglob("*.py")):
        violations.extend(_collect_violations(py_file))
    assert not violations, (
        "conf/ has upward import leaks (fix by importing from core._contracts "
        "or conf/models/_ranking.py):\n" + "\n".join(violations)
    )


def test_core_contracts_has_no_upward_deps() -> None:
    """core/_contracts.py imports nothing from personalscraper (only stdlib/enum)."""
    contracts_file = _PACKAGE_ROOT / "core" / "_contracts.py"
    assert contracts_file.exists(), "core/_contracts.py does not exist"
    source = contracts_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            else:
                continue
            assert not module.startswith("personalscraper."), (
                f"core/_contracts.py:{node.lineno}: must not import "
                f"from personalscraper — found {module!r}. "
                "Only stdlib and enum are allowed."
            )
