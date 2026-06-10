"""Tests for pipeline step adapters."""

# ruff: noqa: D103

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from personalscraper.pipeline_protocol import StepContext, is_pipeline_step
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


# ── DispatchStep authority wiring (DESIGN §7.4) ──


def _dispatch_ctx(acquire: object) -> StepContext:
    """Build a minimal StepContext whose ``ctx.app.acquire`` is *acquire*.

    DispatchStep only reads ``ctx.app.{settings,config,event_bus,acquire}`` and
    ``ctx.dry_run`` / ``ctx.extras``, so a lightweight namespace stands in for
    the full AppContext (avoids building the heavy ProviderRegistry).

    Args:
        acquire: The object to expose as ``ctx.app.acquire`` (or ``None``).

    Returns:
        A ready-to-call :class:`StepContext`.
    """
    app = SimpleNamespace(
        settings=MagicMock(name="settings"),
        config=MagicMock(name="config"),
        event_bus=MagicMock(name="event_bus"),
        acquire=acquire,
    )
    return StepContext(
        app=app,  # type: ignore[arg-type]
        run_id=uuid4(),
        dry_run=False,
        interactive=False,
        verbose=False,
        upstream={},
        extras={},
    )


def test_dispatch_step_forwards_authority_as_permit_and_recorder(monkeypatch: pytest.MonkeyPatch) -> None:
    """The single delete_authority handle is forwarded as BOTH permit= and recorder=.

    Prevents a C2-class regression: the DispatchStep must thread the live
    authority (the composing permit + recorder) into run_dispatch unchanged,
    not silently drop it to the AllowAllPermit defaults.
    """
    captured: dict[str, object] = {}

    def _fake_run_dispatch(settings: object, **kwargs: object) -> object:
        captured.update(kwargs)
        captured["settings"] = settings
        return MagicMock(name="StepReport")

    monkeypatch.setattr("personalscraper.dispatch.run.run_dispatch", _fake_run_dispatch)

    sentinel_authority = object()
    acquire = SimpleNamespace(delete_authority=sentinel_authority)
    ctx = _dispatch_ctx(acquire)

    DispatchStep()(ctx)

    # The SAME object must arrive as both permit= and recorder= (DESIGN §7.4 —
    # the authority composes DeletePermit + SeedObligationRecorder).
    assert captured["permit"] is sentinel_authority
    assert captured["recorder"] is sentinel_authority
    assert captured["settings"] is ctx.app.settings
    assert captured["config"] is ctx.app.config
    assert captured["event_bus"] is ctx.app.event_bus


def test_dispatch_step_acquire_none_degrades_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ctx with acquire=None → run_dispatch called with NO permit/recorder kwargs.

    Falling through to run_dispatch's AllowAllPermit defaults (no crash) is the
    fail-open contract when the acquisition lobe is absent.
    """
    captured: dict[str, object] = {}

    def _fake_run_dispatch(settings: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return MagicMock(name="StepReport")

    monkeypatch.setattr("personalscraper.dispatch.run.run_dispatch", _fake_run_dispatch)

    ctx = _dispatch_ctx(None)

    # Must not raise — the kwargs simply omit permit/recorder so run_dispatch
    # uses its AllowAllPermit() defaults.
    DispatchStep()(ctx)

    assert "permit" not in captured
    assert "recorder" not in captured
