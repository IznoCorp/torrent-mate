"""Tests for the step report contract registry."""

from __future__ import annotations

from dataclasses import is_dataclass

from personalscraper.reports import STEP_REPORT_CONTRACT


def test_contract_has_nine_entries() -> None:
    """The pipeline's public steps have typed payload contracts."""
    assert len(STEP_REPORT_CONTRACT) == 9
    assert set(STEP_REPORT_CONTRACT) == {
        "ingest",
        "sort",
        "clean",
        "scrape",
        "cleanup",
        "enforce",
        "verify",
        "trailers",
        "dispatch",
    }


def test_contract_values_are_dataclasses() -> None:
    """Every contract entry points to a dataclass type."""
    for name, cls in STEP_REPORT_CONTRACT.items():
        assert is_dataclass(cls), f"{name} -> {cls.__name__} is not a dataclass"
