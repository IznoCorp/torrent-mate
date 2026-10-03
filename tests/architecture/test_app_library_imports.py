"""The library service is HTTP-free: ``app/library`` imports no ``fastapi``, no ``web``, no ``http_v1``."""

from __future__ import annotations

import ast
from pathlib import Path

_LIBRARY_DIR = Path(__file__).resolve().parents[2] / "personalscraper" / "app" / "library"
_FORBIDDEN = ("fastapi", "starlette", "personalscraper.web", "personalscraper.http_v1")


def _imports(source: str) -> list[str]:
    """List every module a source imports, at any depth.

    Args:
        source: Python source.

    Returns:
        The imported module names.
    """
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _violations(source: str) -> list[str]:
    """The forbidden imports of one source.

    Args:
        source: Python source.

    Returns:
        The forbidden module names it imports.
    """
    return [name for name in _imports(source) if any(name == f or name.startswith(f + ".") for f in _FORBIDDEN)]


def test_app_library_imports_no_http_layer() -> None:
    """No module of ``app/library`` imports an HTTP framework, v0's ``web`` or v1's ``http_v1``."""
    modules = sorted(_LIBRARY_DIR.glob("*.py"))
    assert modules, "personalscraper/app/library/ is missing (the guard would scan nothing)"

    found = {str(path.name): _violations(path.read_text(encoding="utf-8")) for path in modules}

    assert {name: bad for name, bad in found.items() if bad} == {}


def test_the_guard_bites() -> None:
    """POSITIVE control: each forbidden import is flagged, a sibling app import is not."""
    source = (
        "import fastapi\nfrom personalscraper.web.app import x\nfrom personalscraper.http_v1 import y\n"
        "from personalscraper.app.errors import AppRefusal\nimport personalscraper.webhooks\n"
    )

    assert _violations(source) == ["fastapi", "personalscraper.web.app", "personalscraper.http_v1"]
