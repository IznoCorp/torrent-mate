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

# Every table of the indexer's schema (``personalscraper/indexer/migrations/*.sql``; written
# out, not read at run time, so a new table is a visible edit here).
_INDEX_TABLES = (
    "_migration_007_changes",
    "deleted_item",
    "destructive_op",
    "disk",
    "episode",
    "index_outbox",
    "item_attribute",
    "item_issue",
    "media_file",
    "media_item",
    "media_release",
    "media_stream",
    "path",
    "pending_op",
    "pipeline_run",
    "repair_queue",
    "scan_event",
    "scan_run",
    "schema_version",
    "scrape_decision",
    "season",
)

# A table of the indexer's schema, named where SQL names a table it reads or writes: any case,
# bare or quoted (``"t"``, ```t```, ``[t]``).
_INDEX_TABLE_SQL = re.compile(
    rf"\b(?:FROM|JOIN|INTO|UPDATE)\s+[\"`\[]?(?:{'|'.join(_INDEX_TABLES)})\b",
    re.IGNORECASE,
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


def _is_sqlite3(module: str) -> bool:
    """Whether a dotted module name is ``sqlite3`` or one of its submodules.

    Args:
        module: The dotted name.

    Returns:
        Whether it is.
    """
    return module == "sqlite3" or module.startswith("sqlite3.")


def _sql_violations(source: str) -> list[str]:
    """What of one source reaches ``library.db`` past the indexer.

    ``sqlite3`` may be imported only to name ``sqlite3.Error`` (an index failure the
    application reports); any other use of the module, the module imported under another
    name, and any string constant naming an indexer table after ``FROM``, ``JOIN``, ``INTO``
    or ``UPDATE`` (any case, the name bare or quoted) is a violation.

    Args:
        source: Python source.

    Returns:
        One line per violation: ``sqlite3.<name>`` or the offending SQL text.
    """
    tree = ast.parse(source)
    found: list[str] = []
    allowed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None and _is_sqlite3(node.module):
            found.extend(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "Error")
        elif isinstance(node, ast.Import):
            # Renamed, the module escapes the ``sqlite3.<attr>`` check below.
            found.extend(
                f"import {alias.name} as {alias.asname}"
                for alias in node.names
                if _is_sqlite3(alias.name) and alias.asname
            )
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


def test_the_sql_guard_sees_through_spelling() -> None:
    """POSITIVE control: a renamed module, lowercase SQL, a quoted name and each late-added table are flagged."""
    assert _sql_violations("import sqlite3 as db\ndb.connect('x')\n") == ["import sqlite3 as db"]
    assert _sql_violations("import sqlite3.dbapi2 as db\n") == ["import sqlite3.dbapi2 as db"]
    assert _sql_violations("from sqlite3.dbapi2 import connect\n") == ["sqlite3.dbapi2.connect"]
    assert _sql_violations('q = "select 1 from media_item"\n') == ["select 1 from media_item"]
    assert _sql_violations("q = 'SELECT 1 FROM \"media_item\"'\n") == ['SELECT 1 FROM "media_item"']
    assert _sql_violations('q = "SELECT 1 FROM [disk]"\n') == ["SELECT 1 FROM [disk]"]
    for table in ("deleted_item", "item_attribute", "item_issue"):
        assert _sql_violations(f'q = "DELETE FROM {table}"\n') == [f"DELETE FROM {table}"]
    assert _sql_violations("from sqlite3 import Error\n") == []
