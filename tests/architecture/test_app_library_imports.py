"""The library service is HTTP-free and SQL-free.

``app/library`` imports no ``fastapi``, no ``web``, no ``http_v1``; and it reads and writes
``library.db`` only through the indexer: no ``sqlite3`` but its ``Error`` type, no SQL
naming a table of the indexer's schema.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LIBRARY_DIR = _ROOT / "personalscraper" / "app" / "library"
_PACKAGE = "personalscraper.app.library"
_FORBIDDEN = ("fastapi", "starlette", "personalscraper.web", "personalscraper.http_v1")

# A table of the indexer's schema, named where SQL names a table it reads or writes.
_INDEX_TABLE_SQL = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE)\s+(?:media_item|media_file|media_release|season|episode|path|disk)\b"
)


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


def _sql_violations(source: str) -> list[str]:
    """What of one source reaches ``library.db`` past the indexer.

    ``sqlite3`` may be imported only to name ``sqlite3.Error`` (an index failure the
    application reports); any other use of the module, and any string constant naming an
    indexer table after ``FROM``, ``JOIN``, ``INTO`` or ``UPDATE``, is a violation.

    Args:
        source: Python source.

    Returns:
        One line per violation: ``sqlite3.<name>`` or the offending SQL text.
    """
    tree = ast.parse(source)
    found: list[str] = []
    allowed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "sqlite3":
            found.extend(f"sqlite3.{alias.name}" for alias in node.names if alias.name != "Error")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "sqlite3":
            allowed.add(id(node.value))
            if node.attr != "Error":
                found.append(f"sqlite3.{node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and _INDEX_TABLE_SQL.search(node.value):
            found.append(node.value)
    found.extend(
        "sqlite3"
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "sqlite3" and id(node) not in allowed
    )
    return found


def test_app_library_reaches_library_db_only_through_the_indexer() -> None:
    """No module of ``app/library`` uses ``sqlite3`` beyond ``sqlite3.Error``, nor names an indexer table in SQL."""
    modules = sorted(_LIBRARY_DIR.rglob("*.py"))
    assert modules, "personalscraper/app/library/ is missing (the guard would scan nothing)"

    found = {str(path.relative_to(_LIBRARY_DIR)): _sql_violations(path.read_text(encoding="utf-8")) for path in modules}

    assert {name: bad for name, bad in found.items() if bad} == {}


def test_the_sql_guard_bites() -> None:
    """POSITIVE control: a planted query, a connection and a bare module use are flagged; ``sqlite3.Error`` is not."""
    assert _sql_violations('conn.execute("SELECT 1 FROM media_item")\n') == ["SELECT 1 FROM media_item"]
    assert _sql_violations('q = "DELETE FROM disk WHERE id = ?"\n') == ["DELETE FROM disk WHERE id = ?"]
    assert _sql_violations('q = "x JOIN episode e ON 1"\n') == ["x JOIN episode e ON 1"]
    assert _sql_violations("import sqlite3\nsqlite3.connect('x')\n") == ["sqlite3.connect"]
    assert _sql_violations("from sqlite3 import connect, Error\n") == ["sqlite3.connect"]
    assert _sql_violations("import sqlite3\nf(sqlite3)\n") == ["sqlite3"]
    assert _sql_violations("import sqlite3\ntry:\n    pass\nexcept sqlite3.Error:\n    pass\n") == []
    assert _sql_violations('"""Read from the library on a disk; the episode path."""\n') == []
