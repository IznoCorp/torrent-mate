"""Integration tests for tracker-registry composition-root wiring.

Verifies _build_app_context() populates the acquisition lobe handle
(``ctx.acquire.tracker_registry``), that TrackerConfigError surfaces at boot
through ``build_acquire_context``, and that per_step_boundary calls
``app_context.acquire.close()``. Network is not touched: build_tracker_registry
is patched throughout (RP5c delegates tracker construction to it unchanged).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.context import AcquireContext
from personalscraper.api.tracker._errors import TrackerConfigError, TrackerConfigIssue
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.cli_helpers import _build_app_context, per_step_boundary
from personalscraper.core.app_context import AppContext


def _config() -> MagicMock:
    cfg = MagicMock()
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300.0
    cfg.torrent.active = ""
    return cfg


def _settings() -> MagicMock:
    return MagicMock()


def _empty_registry() -> TrackerRegistry:
    return TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())


class TestBuildAppContextTrackerWiring:
    """_build_app_context wires the tracker registry via the acquire handle."""

    def test_tracker_registry_set_from_factory(self) -> None:
        """_build_app_context must store the factory's return value on ctx.acquire."""
        stub = _empty_registry()

        with (
            patch("personalscraper.acquire._factory.build_tracker_registry", return_value=stub),
            patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        ):
            ctx = _build_app_context(_config(), _settings())

        assert ctx.acquire is not None
        assert ctx.acquire.tracker_registry is stub

    def test_tracker_config_error_surfaces_at_boot(self) -> None:
        """TrackerConfigError must propagate out of _build_app_context.

        RP5c routes tracker construction through ``build_acquire_context``,
        which delegates to ``build_tracker_registry`` unchanged — so the error
        still surfaces at the same composition-root boundary.
        """
        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="LACALE_API_KEY absent",
        )

        with (
            patch("personalscraper.acquire._factory.build_tracker_registry", side_effect=TrackerConfigError([issue])),
            patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        ):
            with pytest.raises(TrackerConfigError) as exc_info:
                _build_app_context(_config(), _settings())

        assert exc_info.value.issues[0].code == "missing_credentials"

    def test_app_context_direct_construction_defaults_to_none(self) -> None:
        """Direct AppContext construction (test fixtures) still defaults acquire to None."""
        ctx = AppContext(
            config=MagicMock(),
            settings=MagicMock(),
            event_bus=MagicMock(),
            provider_registry=MagicMock(),
        )
        assert ctx.acquire is None


class TestPerStepBoundaryClose:
    """per_step_boundary calls app_context.acquire.close() in its finally.

    ``AcquireContext.close()`` owns ``tracker_registry.close()`` (RP5c), so
    these tests wrap the registry stub in a real ``AcquireContext`` and assert
    the registry's ``close()`` is reached through the acquire handle.
    """

    def test_close_called_on_normal_exit(self) -> None:
        """per_step_boundary must call acquire.close() (→ registry.close()) on normal exit."""
        stub_registry = MagicMock(spec=TrackerRegistry)
        acquire = AcquireContext(tracker_registry=stub_registry)

        with (
            patch("personalscraper.cli_helpers._build_app_context") as mock_build,
            patch("personalscraper.cli_helpers.current_correlation_id"),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.acquire = acquire
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with per_step_boundary(_config(), _settings()):
                pass

        stub_registry.close.assert_called_once()

    def test_close_called_when_body_raises(self) -> None:
        """per_step_boundary must call acquire.close() even when the body raises."""
        stub_registry = MagicMock(spec=TrackerRegistry)
        acquire = AcquireContext(tracker_registry=stub_registry)

        with (
            patch("personalscraper.cli_helpers._build_app_context") as mock_build,
            patch("personalscraper.cli_helpers.current_correlation_id"),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.acquire = acquire
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with pytest.raises(RuntimeError):
                with per_step_boundary(_config(), _settings()):
                    raise RuntimeError("body error")

        stub_registry.close.assert_called_once()

    def test_none_acquire_does_not_raise(self) -> None:
        """per_step_boundary must not crash when acquire is None."""
        with (
            patch("personalscraper.cli_helpers._build_app_context") as mock_build,
            patch("personalscraper.cli_helpers.current_correlation_id"),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.acquire = None
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with per_step_boundary(_config(), _settings()):
                pass  # must not raise
