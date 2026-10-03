"""The library service is HTTP-free: ``app/library`` imports no ``fastapi``, no ``web``, no ``http_v1``."""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LIBRARY_DIR = _ROOT / "personalscraper" / "app" / "library"
_PACKAGE = "personalscraper.app.library"
_FORBIDDEN = ("fastapi", "starlette", "personalscraper.web", "personalscraper.http_v1")


def _imports(source: str, package: str) -> list[str]:
    """List every module a source imports, at any depth, relative imports resolved.

    A ``from`` import records its module and each imported name under it, so
    ``from personalscraper import web`` names ``personalscraper.web``.

    Args:
        source: Python source.
        package: The dotted package the source lives in (what a single dot resolves to).

    Returns:
        The imported module names.
    """
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package.split(".")[: len(package.split(".")) - (node.level - 1)] if node.level else []
            parts = [*base, *([node.module] if node.module else [])]
            if parts:
                names.append(".".join(parts))
                names.extend(".".join([*parts, alias.name]) for alias in node.names)
    return names


def _violations(source: str, package: str = _PACKAGE) -> list[str]:
    """The forbidden imports of one source.

    Args:
        source: Python source.
        package: The dotted package the source lives in.

    Returns:
        The forbidden module names it imports.
    """
    return [
        name for name in _imports(source, package) if any(name == f or name.startswith(f + ".") for f in _FORBIDDEN)
    ]


def test_app_library_imports_no_http_layer() -> None:
    """No module of ``app/library`` imports an HTTP framework, v0's ``web`` or v1's ``http_v1``."""
    modules = sorted(_LIBRARY_DIR.rglob("*.py"))
    assert modules, "personalscraper/app/library/ is missing (the guard would scan nothing)"

    found = {
        str(path.relative_to(_LIBRARY_DIR)): _violations(
            path.read_text(encoding="utf-8"), ".".join(path.parent.relative_to(_ROOT).parts)
        )
        for path in modules
    }

    assert {name: bad for name, bad in found.items() if bad} == {}


def test_the_guard_bites() -> None:
    """POSITIVE control: each forbidden import form is flagged, a sibling app import is not."""
    source = (
        "import fastapi\nfrom personalscraper.web.app import x\nfrom personalscraper.http_v1 import y\n"
        "from personalscraper.app.errors import AppRefusal\nimport personalscraper.webhooks\n"
    )

    assert _violations(source) == [
        "fastapi",
        "personalscraper.web.app",
        "personalscraper.web.app.x",
        "personalscraper.http_v1",
        "personalscraper.http_v1.y",
    ]


def test_the_guard_sees_a_package_imported_by_its_parent() -> None:
    """``from personalscraper import web`` names the forbidden package through its alias."""
    assert _violations("from personalscraper import web\n") == ["personalscraper.web"]
    assert _violations("from personalscraper import http_v1 as v1\n") == ["personalscraper.http_v1"]
    assert _violations("from personalscraper import app\n") == []


def test_the_guard_resolves_relative_imports() -> None:
    """A relative import is resolved against the module's package before it is judged."""
    assert _violations("from ... import web\n") == ["personalscraper.web"]
    assert _violations("from ...web import x\n") == ["personalscraper.web", "personalscraper.web.x"]
    assert _violations("from ...http_v1.routes import x\n") == [
        "personalscraper.http_v1.routes",
        "personalscraper.http_v1.routes.x",
    ]
    assert _violations("from .. import web\nfrom . import catalogue\nfrom .identity import ref_key\n") == []
    # One package deeper (the guard walks subpackages), the same dots reach a different package.
    assert _violations("from .... import web\n", package="personalscraper.app.library.deeper") == [
        "personalscraper.web"
    ]
