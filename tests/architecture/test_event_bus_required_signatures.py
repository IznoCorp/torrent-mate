r"""Signature tests for the Sub-phase 5.2 required-bus contract.

After Phase 4 every production component received an ``event_bus`` parameter
under the migration contract ``event_bus: EventBus | None = None``. Sub-phase
5.1 tightened :class:`~personalscraper.core.circuit.CircuitBreaker`. Sub-phase
5.2 tightens the rest: every entry point, orchestrator, client, and helper
listed below now declares ``event_bus`` as a required keyword-only parameter
with annotation ``EventBus`` (no ``| None``, no default).

The tests are parametrized over the full site list so the gate audit grep
(``rg 'event_bus: EventBus \\| None' personalscraper/`` → 0) is mirrored by
in-process signature checks: a future regression that re-introduces a
``| None`` default at any of these sites is caught here, not at gate time.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from personalscraper.api.metadata.tvdb import TVDBClient
from personalscraper.api.transport._http import HttpTransport
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.dispatch.run import run_dispatch
from personalscraper.enforce.run import run_enforce
from personalscraper.indexer import cli as _indexer_cli  # noqa: F401 — imported first to break circular import
from personalscraper.indexer._disk_guard import handle_disk_full
from personalscraper.indexer.breaker import DiskCircuitBreaker
from personalscraper.indexer.commands.diagnose import config_migrate_category_command
from personalscraper.indexer.commands.query import (
    library_search_command,
    library_show_command,
    library_status_command,
    library_verify_command,
)
from personalscraper.indexer.commands.repair import library_repair_command
from personalscraper.indexer.commands.scan import library_index_command
from personalscraper.indexer.db import check_free_space, open_db
from personalscraper.indexer.scanner import scan as indexer_scan
from personalscraper.ingest.ingest import run_ingest
from personalscraper.library.rescraper import rescrape_library
from personalscraper.library.scanner import scan_library
from personalscraper.process.run import run_clean, run_cleanup, run_process
from personalscraper.scraper.orchestrator import Scraper
from personalscraper.scraper.run import run_scrape
from personalscraper.sorter.run import run_sort
from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.step import run_trailers
from personalscraper.verify.run import run_verify

# Each entry is (qualified_id, callable_or_class) where ``callable_or_class``
# is either a free function or a class (we then check ``__init__``).
REQUIRED_BUS_SITES: list[tuple[str, Callable[..., Any] | type]] = [
    ("HttpTransport.__init__", HttpTransport),
    ("DiskCircuitBreaker.__init__", DiskCircuitBreaker),
    ("Dispatcher.__init__", Dispatcher),
    ("TVDBClient.__init__", TVDBClient),
    ("Scraper.__init__", Scraper),
    ("TrailersOrchestrator.__init__", TrailersOrchestrator),
    ("ingest.run_ingest", run_ingest),
    ("sorter.run_sort", run_sort),
    ("process.run_process", run_process),
    ("process.run_clean", run_clean),
    ("process.run_cleanup", run_cleanup),
    ("scraper.run_scrape", run_scrape),
    ("enforce.run_enforce", run_enforce),
    ("dispatch.run_dispatch", run_dispatch),
    ("verify.run_verify", run_verify),
    ("trailers.run_trailers", run_trailers),
    ("indexer.scanner.scan", indexer_scan),
    ("indexer.commands.scan.library_index_command", library_index_command),
    ("indexer.commands.diagnose.config_migrate_category_command", config_migrate_category_command),
    ("indexer.commands.query.library_status_command", library_status_command),
    ("indexer.commands.query.library_verify_command", library_verify_command),
    ("indexer.commands.query.library_search_command", library_search_command),
    ("indexer.commands.query.library_show_command", library_show_command),
    ("indexer.commands.repair.library_repair_command", library_repair_command),
    ("indexer.db.open_db", open_db),
    ("indexer.db.check_free_space", check_free_space),
    ("indexer._disk_guard.handle_disk_full", handle_disk_full),
    ("library.scanner.scan_library", scan_library),
    ("library.rescraper.rescrape_library", rescrape_library),
    ("MediaIndex.__init__", MediaIndex),
]


def _resolve_signature(target: Callable[..., Any] | type) -> inspect.Signature:
    """Return the :class:`inspect.Signature` of the callable / class init."""
    if inspect.isclass(target):
        return inspect.signature(target.__init__)
    return inspect.signature(target)


@pytest.mark.parametrize("name,target", REQUIRED_BUS_SITES, ids=[s[0] for s in REQUIRED_BUS_SITES])
def test_event_bus_parameter_has_no_default(name: str, target: Callable[..., Any] | type) -> None:
    """Each Phase 5.2 site declares ``event_bus`` without a default value.

    Args:
        name: Qualified site id (used as the pytest id).
        target: The callable or class to inspect.
    """
    sig = _resolve_signature(target)
    assert "event_bus" in sig.parameters, f"{name}: missing event_bus parameter"
    assert sig.parameters["event_bus"].default is inspect.Parameter.empty, (
        f"{name}: event_bus must have no default (was {sig.parameters['event_bus'].default!r})"
    )


@pytest.mark.parametrize("name,target", REQUIRED_BUS_SITES, ids=[s[0] for s in REQUIRED_BUS_SITES])
def test_event_bus_annotation_excludes_none(name: str, target: Callable[..., Any] | type) -> None:
    """Each Phase 5.2 site annotates ``event_bus`` as ``EventBus`` (no ``| None``).

    Args:
        name: Qualified site id (used as the pytest id).
        target: The callable or class to inspect.
    """
    sig = _resolve_signature(target)
    annotation = sig.parameters["event_bus"].annotation
    annotation_str = str(annotation)
    assert "None" not in annotation_str, f"{name}: event_bus annotation must not allow None; got {annotation_str!r}"


# ---------------------------------------------------------------------------
# AST sweep — exhaustive guard against future regressions
# ---------------------------------------------------------------------------
#
# The whitelist above is hand-maintained and can rot: a contributor adding a
# new public function with ``event_bus: EventBus | None = None`` would not
# show up here. The AST sweep below walks every ``personalscraper/**/*.py``
# file and asserts that **no function signature** declares ``event_bus`` as
# ``EventBus | None`` or with a ``None`` default value, regardless of whether
# the site is on the explicit list.
#
# Add new exemptions to ``_AST_SWEEP_EXEMPT`` only with a written rationale.


_PERSONALSCRAPER_ROOT = Path(__file__).parent.parent.parent / "personalscraper"

# Documented exemptions: (module path relative to repo root, qualified name).
# Empty by design — the contract is "no exemptions". Any future entry must
# come with a written explanation in DESIGN.md.
_AST_SWEEP_EXEMPT: frozenset[tuple[str, str]] = frozenset()


def _iter_event_bus_params(tree: ast.AST) -> list[tuple[str, ast.arg, ast.AST | None]]:
    """Yield ``(qualified_name, arg_node, default_node)`` for each ``event_bus`` parameter.

    Walks the module AST, descending into classes and nested functions, and
    returns the qualified name (e.g. ``ClassName.method``) of every function
    whose signature contains an ``event_bus`` parameter.

    Args:
        tree: The parsed module AST.

    Returns:
        A list of ``(qualified_name, arg_node, default_or_None)`` tuples.
    """
    out: list[tuple[str, ast.arg, ast.AST | None]] = []

    def visit(node: ast.AST, prefix: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qname = f"{prefix}{node.name}" if prefix else node.name
            args = node.args
            all_args = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
            all_defaults: list[ast.AST | None] = (
                [None] * (len(args.posonlyargs) + len(args.args) - len(args.defaults))
                + list(args.defaults)
                + list(args.kw_defaults)
            )
            for arg, default in zip(all_args, all_defaults, strict=False):
                if arg.arg == "event_bus":
                    out.append((qname, arg, default))
            new_prefix = f"{qname}."
            for child in node.body:
                visit(child, new_prefix)
        elif isinstance(node, ast.ClassDef):
            cls_prefix = f"{prefix}{node.name}." if prefix else f"{node.name}."
            for child in node.body:
                visit(child, cls_prefix)
        elif isinstance(node, ast.Module):
            for child in node.body:
                visit(child, prefix)

    visit(tree, "")
    return out


def _annotation_allows_none(annotation: ast.AST | None) -> bool:
    """Return True if the AST annotation declares ``EventBus | None`` (PEP 604) or ``Optional[EventBus]``.

    Detects both shapes:
    - ``EventBus | None`` → ``ast.BinOp(op=BitOr, ..., ast.Constant(None))``
    - ``Optional[EventBus]`` → ``ast.Subscript(value=Name(id="Optional"), ...)``
    - ``Union[EventBus, None]`` → ``ast.Subscript(value=Name(id="Union"), slice=Tuple(...))``
    """
    if annotation is None:
        return False
    # PEP 604 union: X | None
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        for side in (annotation.left, annotation.right):
            if isinstance(side, ast.Constant) and side.value is None:
                return True
            if isinstance(side, ast.Name) and side.id == "None":
                return True
    # typing.Optional[X] or typing.Union[X, None]
    if isinstance(annotation, ast.Subscript):
        if isinstance(annotation.value, ast.Name) and annotation.value.id == "Optional":
            return True
        if isinstance(annotation.value, ast.Name) and annotation.value.id == "Union":
            slice_node = annotation.slice
            if isinstance(slice_node, ast.Tuple):
                for elt in slice_node.elts:
                    if isinstance(elt, ast.Constant) and elt.value is None:
                        return True
    return False


def test_ast_sweep_no_event_bus_optional_annotation() -> None:
    """No ``personalscraper/**/*.py`` function signature may declare ``event_bus`` as ``Optional``.

    Catches future regressions where a contributor adds a new public function
    with ``event_bus: EventBus | None = None`` outside the hand-maintained
    REQUIRED_BUS_SITES list. The architecture contract is: every public site
    that takes an ``event_bus`` parameter MUST take it as required ``EventBus``.
    """
    violations: list[str] = []
    for py_file in sorted(_PERSONALSCRAPER_ROOT.rglob("*.py")):
        rel = py_file.relative_to(_PERSONALSCRAPER_ROOT.parent)
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — defensive
            continue
        for qname, arg, _default in _iter_event_bus_params(tree):
            if (str(rel), qname) in _AST_SWEEP_EXEMPT:
                continue
            if _annotation_allows_none(arg.annotation):
                violations.append(f"{rel}:{qname} — event_bus annotation allows None")
    assert not violations, "AST sweep found Optional event_bus parameters:\n  " + "\n  ".join(violations)


def test_ast_sweep_no_event_bus_default() -> None:
    """No ``personalscraper/**/*.py`` function signature may give ``event_bus`` a default value.

    A default value (``= None`` or any other) lets callers forget the bus and
    silently route emits to nowhere — exactly the silent-regression class the
    Phase 5 required-bus contract was written to eliminate.
    """
    violations: list[str] = []
    for py_file in sorted(_PERSONALSCRAPER_ROOT.rglob("*.py")):
        rel = py_file.relative_to(_PERSONALSCRAPER_ROOT.parent)
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — defensive
            continue
        for qname, _arg, default in _iter_event_bus_params(tree):
            if (str(rel), qname) in _AST_SWEEP_EXEMPT:
                continue
            if default is not None:
                violations.append(f"{rel}:{qname} — event_bus has a default value")
    assert not violations, "AST sweep found event_bus parameters with defaults:\n  " + "\n  ".join(violations)
