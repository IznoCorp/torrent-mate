"""Integration tests for tracker-registry composition-root wiring.

Verifies _build_app_context() populates tracker_registry, that
TrackerConfigError surfaces at boot, and that per_step_boundary calls close().
Network is not touched: build_tracker_registry is patched throughout.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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
    """_build_app_context wires tracker_registry from the live factory."""

    def test_tracker_registry_set_from_factory(self) -> None:
        """_build_app_context must store the factory's return value."""
        stub = _empty_registry()

        with (
            patch("personalscraper.api.tracker._factory.build_tracker_registry", return_value=stub),
            patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        ):
            ctx = _build_app_context(_config(), _settings())

        assert ctx.tracker_registry is stub

    def test_tracker_config_error_surfaces_at_boot(self) -> None:
        """TrackerConfigError from the factory must propagate out of _build_app_context."""
        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="LACALE_API_KEY absent",
        )

        with (
            patch(
                "personalscraper.api.tracker._factory.build_tracker_registry", side_effect=TrackerConfigError([issue])
            ),
            patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        ):
            with pytest.raises(TrackerConfigError) as exc_info:
                _build_app_context(_config(), _settings())

        assert exc_info.value.issues[0].code == "missing_credentials"

    def test_app_context_direct_construction_defaults_to_none(self) -> None:
        """Direct AppContext construction (test fixtures) still defaults to None."""
        ctx = AppContext(
            config=MagicMock(),
            settings=MagicMock(),
            event_bus=MagicMock(),
            provider_registry=MagicMock(),
        )
        assert ctx.tracker_registry is None


class TestPerStepBoundaryClose:
    """per_step_boundary calls tracker_registry.close() in its finally."""

    def test_close_called_on_normal_exit(self) -> None:
        """per_step_boundary must call tracker_registry.close() on normal exit."""
        stub_registry = MagicMock(spec=TrackerRegistry)

        with (
            patch("personalscraper.cli_helpers._build_app_context") as mock_build,
            patch("personalscraper.cli_helpers.current_correlation_id"),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.tracker_registry = stub_registry
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with per_step_boundary(_config(), _settings()):
                pass

        stub_registry.close.assert_called_once()

    def test_close_called_when_body_raises(self) -> None:
        """per_step_boundary must call close() even when the body raises."""
        stub_registry = MagicMock(spec=TrackerRegistry)

        with (
            patch("personalscraper.cli_helpers._build_app_context") as mock_build,
            patch("personalscraper.cli_helpers.current_correlation_id"),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.tracker_registry = stub_registry
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with pytest.raises(RuntimeError):
                with per_step_boundary(_config(), _settings()):
                    raise RuntimeError("body error")

        stub_registry.close.assert_called_once()

    def test_none_tracker_registry_does_not_raise(self) -> None:
        """per_step_boundary must not crash when tracker_registry is None."""
        with (
            patch("personalscraper.cli_helpers._build_app_context") as mock_build,
            patch("personalscraper.cli_helpers.current_correlation_id"),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.tracker_registry = None
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with per_step_boundary(_config(), _settings()):
                pass  # must not raise
