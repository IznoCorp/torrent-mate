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
            provider="c411",
            message="C411_API_KEY absent",
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
            # The boundary now wires the fail-soft Redis event publisher on
            # the step bus (universal run journal) — isolate it here.
            patch("personalscraper.cli_helpers.build_redis_publisher", return_value=None),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.event_bus = MagicMock()
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
            # The boundary now wires the fail-soft Redis event publisher on
            # the step bus (universal run journal) — isolate it here.
            patch("personalscraper.cli_helpers.build_redis_publisher", return_value=None),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.event_bus = MagicMock()
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
            # The boundary now wires the fail-soft Redis event publisher on
            # the step bus (universal run journal) — isolate it here.
            patch("personalscraper.cli_helpers.build_redis_publisher", return_value=None),
        ):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.event_bus = MagicMock()
            mock_ctx.acquire = None
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with per_step_boundary(_config(), _settings()):
                pass  # must not raise


# -- tr4ker cred-gating tests ----------------------------------------------


def _tr4ker_tracker_config_enabled() -> MagicMock:
    """Build a minimal TrackerConfig with tr4ker enabled and no other providers."""
    cfg = MagicMock()
    # providers: only tr4ker enabled
    tr4ker_provider = MagicMock()
    tr4ker_provider.enabled = True
    cfg.providers = {"tr4ker": tr4ker_provider}
    cfg.priority = ["tr4ker"]
    cfg.priority_by_media_type = {}
    return cfg


class TestTr4kerCredGating:
    """tr4ker missing-cred fail-loud test via direct build_tracker_registry call.

    CI has no config.json5, so we call build_tracker_registry directly with an
    injected env dict (not via _build_app_context which loads real config).
    """

    def test_tr4ker_missing_cred_raises_tracker_config_error(self) -> None:
        """With tr4ker enabled and TR4KER_API_KEY absent, raises TrackerConfigError."""
        from personalscraper.api.tracker._factory import build_tracker_registry  # noqa: PLC0415
        from personalscraper.api.transport._policy import CircuitPolicy  # noqa: PLC0415
        from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

        event_bus = EventBus()
        cb_policy = CircuitPolicy()
        ranking = RankingConfig()

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                tracker_config=_tr4ker_tracker_config_enabled(),
                ranking=ranking,
                settings=MagicMock(),
                event_bus=event_bus,
                cb_policy=cb_policy,
                env={},  # No creds in env.
            )

        issues = exc_info.value.issues
        assert any(i.provider == "tr4ker" for i in issues), f"Expected tr4ker issue; got {issues!r}"
        assert any(i.code == "missing_credentials" for i in issues), f"Expected missing_credentials; got {issues!r}"

    def test_blank_cred_is_treated_as_missing(self) -> None:
        """An empty TR4KER_API_KEY value still fails boot (blank ≠ provisioned)."""
        from personalscraper.api.tracker._factory import build_tracker_registry  # noqa: PLC0415
        from personalscraper.api.transport._policy import CircuitPolicy  # noqa: PLC0415
        from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                tracker_config=_tr4ker_tracker_config_enabled(),
                ranking=RankingConfig(),
                settings=MagicMock(),
                event_bus=EventBus(),
                cb_policy=CircuitPolicy(),
                env={"TR4KER_API_KEY": ""},  # blank
            )

        issues = exc_info.value.issues
        assert any(i.provider == "tr4ker" and i.code == "missing_credentials" for i in issues)


class TestTr4kerFactoryConstruction:
    """tr4ker is built (network-free) via the uniform from_env contract when creds are present.

    Exercises the factory's uniform ``TrackerConstructible.from_env`` dispatch
    path without touching the network, and asserts the registry holds a real
    Tr4kerClient carrying the credential as the Torznab ``apikey=`` param.
    """

    def test_tr4ker_built_when_creds_present(self) -> None:
        """With tr4ker enabled and its API key present, the registry holds a Tr4kerClient."""
        from personalscraper.api.tracker._factory import build_tracker_registry  # noqa: PLC0415
        from personalscraper.api.tracker.tr4ker import Tr4kerClient  # noqa: PLC0415
        from personalscraper.api.transport._policy import CircuitPolicy  # noqa: PLC0415
        from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

        reg = build_tracker_registry(
            tracker_config=_tr4ker_tracker_config_enabled(),
            ranking=RankingConfig(),
            settings=MagicMock(),
            event_bus=EventBus(),
            cb_policy=CircuitPolicy(),
            env={"TR4KER_API_KEY": "secret"},
        )

        built = reg._trackers["tr4ker"]
        assert isinstance(built, Tr4kerClient)
        assert built._open_transport._policy.auth.auth_params() == {"apikey": "secret"}
