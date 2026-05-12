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

import inspect
from collections.abc import Callable
from typing import Any

import pytest

from personalscraper.api.metadata.tvdb import TVDBClient
from personalscraper.api.transport._http import HttpTransport
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.run import run_dispatch
from personalscraper.enforce.run import run_enforce
from personalscraper.indexer import cli as _indexer_cli  # noqa: F401 — imported first to break circular import
from personalscraper.indexer._disk_guard import handle_disk_full
from personalscraper.indexer.breaker import DiskCircuitBreaker
from personalscraper.indexer.commands.scan import library_index_command
from personalscraper.indexer.db import check_free_space, open_db
from personalscraper.indexer.scanner import scan as indexer_scan
from personalscraper.ingest.ingest import run_ingest
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
    ("indexer.db.open_db", open_db),
    ("indexer.db.check_free_space", check_free_space),
    ("indexer._disk_guard.handle_disk_full", handle_disk_full),
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
