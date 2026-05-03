"""Tests for the pipeline protocol primitives."""

# ruff: noqa: D103

from __future__ import annotations

import pytest

from personalscraper.models import StepReport
from personalscraper.pipeline_protocol import PipelineStep, StepContext, is_pipeline_step


def test_step_context_is_frozen() -> None:
    ctx = StepContext(
        config=None,  # type: ignore[arg-type]
        settings=None,  # type: ignore[arg-type]
        dry_run=False,
        interactive=False,
        verbose=False,
        console=None,  # type: ignore[arg-type]
        upstream={},
        extras={},
    )
    with pytest.raises((AttributeError, TypeError)):
        ctx.dry_run = True  # type: ignore[misc]


def test_protocol_runtime_check_accepts_compliant_class() -> None:
    class FakeStep:
        name = "fake"

        def __call__(self, ctx: StepContext) -> StepReport:
            return StepReport(name=self.name)

    assert isinstance(FakeStep(), PipelineStep)
    assert is_pipeline_step(FakeStep())


def test_is_pipeline_step_rejects_missing_name() -> None:
    class NoName:
        def __call__(self, ctx: StepContext) -> StepReport:
            return StepReport(name="anon")

    assert not is_pipeline_step(NoName())


def test_step_context_upstream_mapping() -> None:
    prior = StepReport(name="ingest", success_count=3)
    ctx = StepContext(
        config=None,  # type: ignore[arg-type]
        settings=None,  # type: ignore[arg-type]
        dry_run=False,
        interactive=False,
        verbose=False,
        console=None,  # type: ignore[arg-type]
        upstream={"ingest": prior},
        extras={},
    )
    assert ctx.upstream["ingest"].success_count == 3
