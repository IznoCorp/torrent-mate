"""Every raw ``sqlite3.connect`` that may write a store refuses a store newer than the code.

The checkouts of this host share ``library.db``, ``acquire.db`` and ``app.db``: a store a newer
checkout migrated must not be written by older code. ``apply_migrations`` refuses it for the
stores' own openers; a function that opens a store with a raw ``sqlite3.connect`` must call
``refuse_newer_schema`` (or ``apply_migrations``) itself, open the file ``mode=ro``, or be a
reader listed below with the reason it cannot write.

A new raw connect fails this test until it is classified: guarded, read-only, or a listed reader.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_DIR = Path(__file__).parent.parent.parent / "personalscraper"

#: The calls that refuse a newer store before a write.
_GUARDS = ("refuse_newer_schema(", "apply_migrations(")

#: Functions that open a store with a raw read-write connect but only read it: a read cannot
#: corrupt a newer store. ``path::function`` (path relative to the package) → why it only reads.
_READERS: dict[str, str] = {
    "app/decisions/runner.py::_read_decision_row": "one SELECT on scrape_decision",
    "app/maintenance/service.py::_waits_on_pipeline": "one SELECT on pipeline_run",
    "app/maintenance/service.py::running_run_uid": "SELECT of the live duplicate run",
    "commands/follow.py::follow_backfill_metadata": "SELECTs; writes go through the acquire store, which migrates",
    "commands/library/audit.py::_count_nfo_missing": "one COUNT on item_issue",
    "commands/scrape_resolve.py::_lookup_decision": "SELECT on scrape_decision",
    "conf/loader.py::_check_category_orphans": "SELECT DISTINCT category_id",
    "core/sqlite/_open.py::_quarantine_if_corrupt": "integrity_check probe; open_db's callers then migrate",
    "core/sqlite/_open.py::open_db": "the stores' opener; its callers run apply_migrations",
    "indexer/destructive_journal.py::list_recent": "SELECT on destructive_op",
    "indexer/library_view.py::reader": "mode=ro URI built in a variable, and query_only",
    "indexer/outbox/_disk.py::disk_id_for_path": "SELECT on disk",
    "indexer/ownership.py::_ensure_open": "PRAGMA query_only=ON",
    "scraper/run.py::_read_follow_years": "SELECT on followed_series",
    "web/acquisition/_helpers.py::_backfill_from_indexer": "SELECTs on media_item and season",
    "web/acquisition/service.py::_query_watcher_recent_runs": "web read route",
    "web/routes/acquisition.py::get_acquisition_status": "web read route",
    "web/routes/acquisition.py::get_followed": "web read route",
    "web/routes/acquisition.py::get_obligations": "web read route",
    "web/routes/acquisition.py::get_wanted": "web read route",
    "web/routes/acquisition_overview.py::_count_pending_decisions": "web read route",
    "web/routes/acquisition_overview.py::_read_last_successful_run_at": "web read route",
    "web/routes/acquisition_triggers.py::_live_run_uid": "SELECT of the live run",
    "web/routes/decisions.py::_fetch_decision_row": "web read route",
    "web/routes/decisions.py::decision_activity": "web read route",
    "web/routes/decisions.py::list_decisions": "web read route",
    "web/routes/maintenance.py::_cron_schedulers": "web read route",
    "web/routes/maintenance.py::_watcher_scheduler": "web read route",
    "web/routes/maintenance.py::get_index_health": "web read route",
    "web/routes/pipeline.py::_build_status": "web read route",
    "web/routes/pipeline.py::_newest_running_kind": "web read route",
    "web/routes/pipeline.py::pipeline_history": "web read route",
    "web/routes/pipeline.py::pipeline_history_detail": "web read route",
    "web/routes/pipeline.py::pipeline_stages": "web read route",
    "web/routes/staging.py::_is_journal_writable": "SELECT 1 probe on destructive_op",
    "web/staging/read_model.py::_load_pending_decisions": "web read model",
}


def _is_raw_connect(node: ast.AST) -> bool:
    """Tell whether *node* is a ``sqlite3.connect(...)`` call.

    Args:
        node: An AST node.

    Returns:
        ``True`` for ``sqlite3.connect`` or ``_sqlite3.connect``.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"sqlite3", "_sqlite3"}
    )


def _connecting_functions() -> dict[str, tuple[str, list[ast.Call]]]:
    """Map each function holding a raw connect to its source and its connect calls.

    A connect belongs to its innermost enclosing function.

    Returns:
        ``path::function`` → ``(function source, connect calls)``.
    """
    found: dict[str, tuple[str, list[ast.Call]]] = {}
    for path in sorted(_PACKAGE_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            inner = {
                id(node)
                for child in ast.walk(function)
                if child is not function and isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                for node in ast.walk(child)
            }
            calls = [node for node in ast.walk(function) if _is_raw_connect(node) and id(node) not in inner]
            if calls:
                key = f"{path.relative_to(_PACKAGE_DIR).as_posix()}::{function.name}"
                found[key] = (ast.get_source_segment(text, function) or "", calls)
    return found


def test_every_raw_connect_is_guarded_read_only_or_a_listed_reader() -> None:
    """A raw connect either refuses a newer store, opens ``mode=ro``, or is a listed reader."""
    unclassified = sorted(
        key
        for key, (source, calls) in _connecting_functions().items()
        if key not in _READERS
        and not any(guard in source for guard in _GUARDS)
        and not all("mode=ro" in ast.unparse(call) for call in calls)
    )

    assert unclassified == [], (
        "raw sqlite3.connect without refuse_newer_schema — guard the writer, open it mode=ro, "
        f"or list the reader in _READERS: {unclassified}"
    )


def test_every_listed_reader_still_connects() -> None:
    """A listed reader that no longer opens a raw connection leaves the list."""
    stale = sorted(set(_READERS) - set(_connecting_functions()))

    assert stale == []
