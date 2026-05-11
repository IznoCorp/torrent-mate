"""Tests for the pipeline protocol primitives."""

# ruff: noqa: D103

from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest

from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline_protocol import PipelineStep, StepContext, is_pipeline_step


def _make_app() -> AppContext:
    """Build a synthetic AppContext for protocol-shape tests."""
    return AppContext(config=Mock(), settings=Mock(), event_bus=EventBus())


def test_step_context_is_frozen() -> None:
    ctx = StepContext(
        app=_make_app(),
        run_id=uuid4(),
        dry_run=False,
        interactive=False,
        verbose=False,
        observers=(),
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
        app=_make_app(),
        run_id=uuid4(),
        dry_run=False,
        interactive=False,
        verbose=False,
        observers=(),
        upstream={"ingest": prior},
        extras={},
    )
    assert ctx.upstream["ingest"].success_count == 3


def test_step_context_app_is_required_field() -> None:
    """Sub-phase 2.2c: app is the only source for config/settings now.

    The legacy mirrors were dropped — callers MUST read via ctx.app.config
    and ctx.app.settings.
    """
    app = _make_app()
    ctx = StepContext(
        app=app,
        run_id=uuid4(),
        dry_run=False,
        interactive=False,
        verbose=False,
        observers=(),
        upstream={},
        extras={},
    )
    assert ctx.app is app
    # Legacy mirrors are GONE — no more ctx.config / ctx.settings.
    assert not hasattr(ctx, "config")
    assert not hasattr(ctx, "settings")
