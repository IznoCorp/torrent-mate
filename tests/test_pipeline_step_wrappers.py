"""Tests for pipeline step adapters."""

# ruff: noqa: D103

from __future__ import annotations

import pytest

from personalscraper.pipeline_protocol import is_pipeline_step
from personalscraper.pipeline_steps import (
    DEFAULT_STEPS,
    CleanStep,
    CleanupStep,
    DispatchStep,
    EnforceStep,
    IngestStep,
    ScrapeStep,
    SortStep,
    TrailersStep,
    VerifyStep,
)


@pytest.mark.parametrize(
    "cls",
    [IngestStep, SortStep, CleanStep, ScrapeStep, CleanupStep, EnforceStep, VerifyStep, TrailersStep, DispatchStep],
)
def test_step_class_conforms_to_protocol(cls: type) -> None:
    assert is_pipeline_step(cls())


def test_default_steps_registry_has_nine_entries() -> None:
    assert len(DEFAULT_STEPS) == 9
    assert set(DEFAULT_STEPS) == {
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


def test_default_steps_names_match_keys() -> None:
    for key, step in DEFAULT_STEPS.items():
        assert step.name == key
