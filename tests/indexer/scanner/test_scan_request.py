"""Tests for the frozen :class:`ScanRequest` and the ``scan()`` compat wrapper.

Phase 7 (T8) collapses the ~22-argument ``scan()`` signature into a single
frozen :class:`ScanRequest` consumed by ``scan_with(request)``. ``scan()`` keeps
its historical positional/keyword signature and builds a ``ScanRequest``
internally so behaviour is byte-identical.

These tests pin the refactor's contract:

* ``ScanRequest`` is frozen (no post-construction mutation).
* ``event_bus`` is a REQUIRED field (the required-bus contract carried through
  the value object).
* ``scan()`` threads *every* one of its parameters into the ``ScanRequest`` it
  hands to ``scan_with`` — the single most likely regression in this refactor is
  a dropped or swapped parameter in the wrapper, so the parity test uses a
  distinctive value per field.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.breaker import DiskCircuitBreaker
from personalscraper.indexer.scanner import ScanMode, ScanRequest, ScanRunResult, scan
from personalscraper.indexer.schema import DiskRow


def _distinctive_scan_kwargs() -> dict[str, Any]:
    """Build a full set of ``scan()`` kwargs with a distinctive value per field.

    Every value is chosen to be non-default and unique so the parity test below
    detects a wrapper that drops a parameter or wires one field's value into
    another field.

    Returns:
        A mapping of every ``scan()`` parameter name → a distinctive value.
    """
    return {
        "disks": [MagicMock(spec=DiskRow)],
        "mode": ScanMode.quick,
        "generation": 7,
        "conn": MagicMock(spec=sqlite3.Connection),
        "disk_filter": "Disk9",
        "drop_indexes": True,
        "budget_seconds": 12.5,
        "db_path": Path("/tmp/library-scan-request.db"),
        "checkpoint_every_n_files": 13,
        "disk_breaker": MagicMock(spec=DiskCircuitBreaker),
        "confirm_bulk_change": True,
        "merkle_delta_freeze_threshold": 0.33,
        "quick_enrich": True,
        "backfill_streams": True,
        "max_workers": 9,
        "read_rate_mb_per_sec": 4.5,
        "staging_dir": "/stage/scan-request",
        "spotlight_enabled": True,
        "paranoia_window_seconds": 99,
        "no_enqueue": True,
        "fs_type_overrides": {"Disk9": "ntfs"},
        "event_bus": EventBus(),
        "config": MagicMock(),
    }


def test_scan_request_is_frozen() -> None:
    """A ``ScanRequest`` cannot be mutated after construction."""
    request = ScanRequest(**_distinctive_scan_kwargs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.generation = 999  # type: ignore[misc]


def test_scan_request_requires_event_bus() -> None:
    """``event_bus`` is a required field (constructing without it raises)."""
    kwargs = _distinctive_scan_kwargs()
    kwargs.pop("event_bus")
    with pytest.raises(TypeError):
        ScanRequest(**kwargs)  # type: ignore[call-arg]


def test_scan_request_is_keyword_only() -> None:
    """Every field is keyword-only — positional construction is rejected."""
    with pytest.raises(TypeError):
        ScanRequest([MagicMock(spec=DiskRow)], ScanMode.full, 1, MagicMock())  # type: ignore[misc]


def test_scan_threads_every_param_into_scan_request() -> None:
    """``scan()`` builds a ``ScanRequest`` carrying every parameter unchanged.

    Patches ``scan_with`` so ``scan()`` performs only request construction, then
    asserts each distinctive input value round-trips onto the matching field of
    the ``ScanRequest`` handed to ``scan_with``.
    """
    kwargs = _distinctive_scan_kwargs()
    captured: list[ScanRequest] = []

    def _fake_scan_with(request: ScanRequest) -> ScanRunResult:
        captured.append(request)
        return ScanRunResult(scan_run_id=1, files_visited=0, dirs_visited=0, status="ok")

    with patch("personalscraper.indexer.scanner.scan_with", side_effect=_fake_scan_with):
        scan(**kwargs)

    assert len(captured) == 1, "scan() must delegate to scan_with exactly once"
    request = captured[0]
    assert isinstance(request, ScanRequest)
    for name, value in kwargs.items():
        assert getattr(request, name) == value, f"scan() dropped/swapped parameter {name!r}"
