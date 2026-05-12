"""Signature smoke tests for the E2E pipeline wiring.

The real pipeline E2E tests (``test_pipeline_movies.py``,
``test_pipeline_tvshows.py``) are gated by the ``e2e_torrent`` marker
and deselected in CI, so any drift in the kwargs they pass to
``run_sort`` / ``run_verify`` / ``run_dispatch`` / ``TestCleanup``
would only surface during a manual run.

These collection-time tests assert that every kwarg used by the E2E
suite still exists on its target callee. They run under default
``pytest`` invocation and catch signature drift before the next manual
E2E run does.
"""

from __future__ import annotations

import inspect

from personalscraper.dispatch.run import run_dispatch
from personalscraper.sorter.run import run_sort
from personalscraper.verify.run import run_verify
from tests.e2e.cleanup import TestCleanup


def _has_parameter(func, name: str) -> bool:
    """Return True iff ``func`` accepts a parameter named ``name``."""
    return name in inspect.signature(func).parameters


def test_run_sort_accepts_e2e_kwargs():
    """E2E tests call run_sort(settings, staging_dir=, config=, dry_run=)."""
    for kwarg in ("staging_dir", "config", "dry_run"):
        assert _has_parameter(run_sort, kwarg), f"run_sort lost kwarg '{kwarg}'"


def test_run_verify_accepts_e2e_kwargs():
    """E2E tests call run_verify(settings, config=, dry_run=, movies_only=, tvshows_only=)."""
    for kwarg in ("config", "dry_run", "movies_only", "tvshows_only"):
        assert _has_parameter(run_verify, kwarg), f"run_verify lost kwarg '{kwarg}'"


def test_run_dispatch_accepts_e2e_kwargs():
    """E2E tests call run_dispatch(settings, config=, dry_run=, verified=)."""
    for kwarg in ("config", "dry_run", "verified"):
        assert _has_parameter(run_dispatch, kwarg), f"run_dispatch lost kwarg '{kwarg}'"


def test_test_cleanup_accepts_e2e_kwargs():
    """E2E tests construct TestCleanup(registry=, dry_run=, staging_dir=, disk_paths=)."""
    for kwarg in ("registry", "dry_run", "staging_dir", "disk_paths"):
        assert _has_parameter(TestCleanup.__init__, kwarg), f"TestCleanup lost kwarg '{kwarg}'"
