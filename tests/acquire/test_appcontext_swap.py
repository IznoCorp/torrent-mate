"""Verify AppContext.acquire replaces tracker_registry — acquire-lobe RP5c.

Locks the field swap (``acquire`` present, ``tracker_registry`` gone), the
composition-root wiring (``_build_app_context`` sets ``ctx.acquire`` to a real
:class:`AcquireContext` carrying the tracker registry), and the close
propagation (``per_step_boundary`` calls ``app_context.acquire.close()`` on
exit).
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, patch


def test_appcontext_has_acquire_field() -> None:
    """AppContext must have an 'acquire' field after the RP5c swap."""
    from personalscraper.core.app_context import AppContext

    fields = {f.name for f in dataclasses.fields(AppContext)}
    assert "acquire" in fields, "'acquire' field missing from AppContext"


def test_appcontext_no_tracker_registry_field() -> None:
    """AppContext must NOT have a 'tracker_registry' field after the RP5c swap."""
    from personalscraper.core.app_context import AppContext

    fields = {f.name for f in dataclasses.fields(AppContext)}
    assert "tracker_registry" not in fields, (
        "'tracker_registry' still present — should have been folded into AcquireContext"
    )


def _config() -> MagicMock:
    """Minimal config MagicMock for ``_build_app_context`` (no torrent client)."""
    cfg = MagicMock()
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300.0
    cfg.torrent.active = ""
    return cfg


def test_build_app_context_sets_acquire_with_tracker_registry() -> None:
    """_build_app_context must store a real AcquireContext carrying the registry.

    The composition root always sets ``ctx.acquire`` (never ``None`` in
    production); its ``tracker_registry`` is the live factory's return value.
    """
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.cli_helpers import _build_app_context

    stub_registry = MagicMock()

    with (
        patch(
            "personalscraper.acquire._factory.build_tracker_registry",
            return_value=stub_registry,
        ),
        patch("personalscraper.api.metadata.registry.ProviderRegistry"),
    ):
        ctx = _build_app_context(_config(), MagicMock())

    assert ctx.acquire is not None
    assert isinstance(ctx.acquire, AcquireContext)
    assert ctx.acquire.tracker_registry is stub_registry


def test_per_step_boundary_calls_acquire_close() -> None:
    """per_step_boundary must call app_context.acquire.close() on exit."""
    from personalscraper.cli_helpers import per_step_boundary

    fake_acquire = MagicMock()
    fake_acquire.close = MagicMock()

    fake_ctx = MagicMock()
    fake_ctx.acquire = fake_acquire
    fake_ctx.provider_registry = MagicMock()

    with patch("personalscraper.cli_helpers._build_app_context", return_value=fake_ctx):
        with per_step_boundary(MagicMock(), MagicMock()):
            pass

    fake_acquire.close.assert_called_once()
