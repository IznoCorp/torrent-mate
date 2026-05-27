"""Lock the post-3.7b :class:`StepContext` shape.

The ``observers`` field has been removed; subscribers register against
``ctx.app.event_bus`` instead.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.pipeline_protocol import StepContext


def _make_step_context() -> StepContext:
    """Build a minimal :class:`StepContext` for shape assertions."""
    app = AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )
    return StepContext(
        app=app,
        run_id=uuid4(),
        dry_run=False,
        interactive=False,
        verbose=False,
        upstream={},
        extras={},
    )


def test_step_context_does_not_have_observers_attribute() -> None:
    """``StepContext`` exposes no ``observers`` field after Phase 3.7b."""
    ctx = _make_step_context()
    assert not hasattr(ctx, "observers")


def test_step_context_carries_event_bus_via_app() -> None:
    """The bus is reachable through ``ctx.app.event_bus`` — the only emit substrate."""
    ctx = _make_step_context()
    assert isinstance(ctx.app.event_bus, EventBus)
