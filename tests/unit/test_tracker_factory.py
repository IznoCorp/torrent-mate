"""Unit tests for build_tracker_registry — tracker-wiring RP5a.

All I/O mocked (HttpTransport patched). Part A: error cases and silent boot.
Part B (phase-03b): warning case, severity split, happy path.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.tracker._errors import TrackerConfigError
from personalscraper.api.tracker._factory import build_tracker_registry
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.api.transport._policy import CircuitPolicy
from personalscraper.conf.models.api_config import TrackerConfig, TrackerProviderConfig
from personalscraper.core.event_bus import EventBus

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _ranking() -> RankingConfig:
    """Return a default RankingConfig for test boots."""
    return RankingConfig()


def _policy() -> CircuitPolicy:
    """Return a low-cooldown CircuitPolicy for test boots."""
    return CircuitPolicy(failure_threshold=5, cooldown_seconds=1.0)


def _settings() -> MagicMock:
    """Return a MagicMock stand-in for Settings."""
    return MagicMock()


def _cfg(providers: dict[str, bool], priority: list[str] | None = None) -> TrackerConfig:
    """Build a TrackerConfig from enabled flags with optional priority list."""
    return TrackerConfig(
        providers={k: TrackerProviderConfig(enabled=v) for k, v in providers.items()},
        priority=priority if priority is not None else list(providers),
    )


def _env(*names: str) -> dict[str, str]:
    """Build a fake env dict with one fake value per key name."""
    return {n: f"fake_{n}" for n in names}


# ---------------------------------------------------------------------------
# Stub clients
# ---------------------------------------------------------------------------


class _StubSearchable:
    """Forward stub for phase 3b happy-path tests — kept here as a shared helper."""

    provider_name: str = "stub"

    @classmethod
    def policy(cls, api_key: str) -> MagicMock:
        """Return a MagicMock transport policy."""
        return MagicMock()

    @classmethod
    def from_env(cls, *, env: Any, event_bus: Any, required: Any, provider_cfg: Any) -> "_StubSearchable":
        """Build the stub via the uniform TrackerConstructible.from_env contract."""
        return cls(MagicMock())

    def __init__(self, transport: Any) -> None:
        """Initialise with a transport instance.

        Args:
            transport: The transport layer (mocked in tests).
        """
        self._transport = transport

    def search(self, query: str, media_type: Any = None, year: int | None = None) -> list[Any]:
        """Return an empty result list (stub)."""
        return []


class _NotSearchable:
    """Stub client that does NOT implement TorrentSearchable."""

    provider_name: str = "bad"

    @classmethod
    def policy(cls, api_key: str) -> MagicMock:
        """Return a MagicMock transport policy."""
        return MagicMock()

    @classmethod
    def from_env(cls, *, env: Any, event_bus: Any, required: Any, provider_cfg: Any) -> "_NotSearchable":
        """Build the stub via the uniform from_env contract (still fails TorrentSearchable)."""
        return cls(MagicMock())

    def __init__(self, transport: Any) -> None:
        """Initialise with a transport instance.

        Args:
            transport: The transport layer (mocked in tests).
        """
        self._transport = transport


# ---------------------------------------------------------------------------
# Error: missing_credentials
# ---------------------------------------------------------------------------


class TestMissingCredentials:
    """Tests for the missing_credentials error code."""

    def test_enabled_tracker_no_key_raises(self) -> None:
        """A tracker enabled without its API key must raise TrackerConfigError."""
        cfg = _cfg({"tr4ker": True}, priority=["tr4ker"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

        codes = [i.code for i in exc_info.value.issues]
        assert "missing_credentials" in codes

    def test_error_names_the_provider(self) -> None:
        """The error issue must mention the provider that was missing credentials."""
        cfg = _cfg({"tr4ker": True}, priority=["tr4ker"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

        providers = [i.provider for i in exc_info.value.issues]
        assert "tr4ker" in providers

    def test_error_names_the_missing_key(self) -> None:
        """The error message must name the missing env var."""
        cfg = _cfg({"c411": True}, priority=["c411"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

        assert any("C411_API_KEY" in i.message for i in exc_info.value.issues)


# ---------------------------------------------------------------------------
# Error: unknown_provider (name in priority absent from providers)
# ---------------------------------------------------------------------------


class TestUnknownProvider:
    """Tests for the unknown_provider error code."""

    def test_ghost_in_priority_raises(self) -> None:
        """A name in priority that is absent from providers must raise TrackerConfigError."""
        cfg = TrackerConfig(
            providers={"tr4ker": TrackerProviderConfig(enabled=False)},
            priority=["tr4ker", "ghost"],
        )

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

        codes = [i.code for i in exc_info.value.issues]
        assert "unknown_provider" in codes
        providers = [i.provider for i in exc_info.value.issues]
        assert "ghost" in providers


# ---------------------------------------------------------------------------
# Error: protocol_mismatch
# ---------------------------------------------------------------------------


class TestProtocolMismatch:
    """Tests for the protocol_mismatch error code."""

    def test_non_searchable_client_raises(self) -> None:
        """A client that fails isinstance(client, TorrentSearchable) must raise."""
        cfg = _cfg({"tr4ker": True}, priority=["tr4ker"])

        with (
            patch(
                "personalscraper.api.tracker._factory._TRACKER_CLASSES",
                {"tr4ker": "tests.unit.test_tracker_factory:_NotSearchable"},
            ),
            patch("personalscraper.api.transport._http.HttpTransport"),
        ):
            with pytest.raises(TrackerConfigError) as exc_info:
                build_tracker_registry(
                    cfg,
                    _ranking(),
                    settings=_settings(),
                    event_bus=EventBus(),
                    cb_policy=_policy(),
                    env=_env("TR4KER_API_KEY"),
                )

        codes = [i.code for i in exc_info.value.issues]
        assert "protocol_mismatch" in codes


# ---------------------------------------------------------------------------
# All-disabled: silent boot, empty registry
# ---------------------------------------------------------------------------


class TestAllDisabled:
    """Tests for the all-disabled silent-boot case."""

    def test_all_disabled_returns_empty_registry(self) -> None:
        """When all trackers are disabled, an empty TrackerRegistry is returned."""
        cfg = _cfg({"tr4ker": False, "c411": False}, priority=[])

        registry = build_tracker_registry(
            cfg,
            _ranking(),
            settings=_settings(),
            event_bus=EventBus(),
            cb_policy=_policy(),
            env={},
        )

        assert isinstance(registry, TrackerRegistry)
        assert registry._trackers == {}

    def test_all_disabled_no_warning_emitted(self, caplog: pytest.LogCaptureFixture) -> None:
        """disabled_in_priority must NOT be emitted when zero trackers are active."""
        cfg = TrackerConfig(
            providers={
                "tr4ker": TrackerProviderConfig(enabled=False),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["tr4ker", "c411"],
        )

        with caplog.at_level("WARNING"):
            registry = build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

        assert registry._trackers == {}
        assert "disabled_in_priority" not in caplog.text


# ---------------------------------------------------------------------------
# Warning: disabled_in_priority (non-fatal, only when >=1 active)
# ---------------------------------------------------------------------------


class TestDisabledInPriority:
    """Tests for the disabled_in_priority warning code."""

    def test_disabled_in_priority_does_not_raise(self) -> None:
        """disabled_in_priority is a warning; boot must succeed."""
        cfg = TrackerConfig(
            providers={
                "tr4ker": TrackerProviderConfig(enabled=True),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["tr4ker", "c411"],
        )

        with (
            patch(
                "personalscraper.api.tracker._factory._TRACKER_CLASSES",
                {
                    "tr4ker": "tests.unit.test_tracker_factory:_StubSearchable",
                    "c411": "tests.unit.test_tracker_factory:_StubSearchable",
                },
            ),
            patch("personalscraper.api.transport._http.HttpTransport"),
        ):
            registry = build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env=_env("TR4KER_API_KEY"),
            )

        assert isinstance(registry, TrackerRegistry)
        assert "tr4ker" in registry._trackers
        assert "c411" not in registry._trackers

    def test_disabled_in_priority_only_active_tracker_built(self) -> None:
        """Only the enabled tracker is present in the returned registry."""
        cfg = TrackerConfig(
            providers={
                "tr4ker": TrackerProviderConfig(enabled=True),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["tr4ker", "c411"],
        )

        with (
            patch(
                "personalscraper.api.tracker._factory._TRACKER_CLASSES",
                {"tr4ker": "tests.unit.test_tracker_factory:_StubSearchable"},
            ),
            patch("personalscraper.api.transport._http.HttpTransport"),
        ):
            registry = build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env=_env("TR4KER_API_KEY"),
            )

        assert list(registry._trackers) == ["tr4ker"]

    def test_disabled_in_priority_warning_is_emitted(self) -> None:
        """The disabled_in_priority warning IS logged when >=1 tracker is active."""
        cfg = TrackerConfig(
            providers={
                "tr4ker": TrackerProviderConfig(enabled=True),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["tr4ker", "c411"],
        )

        with (
            patch(
                "personalscraper.api.tracker._factory._TRACKER_CLASSES",
                {"tr4ker": "tests.unit.test_tracker_factory:_StubSearchable"},
            ),
            patch("personalscraper.api.transport._http.HttpTransport"),
            patch("personalscraper.api.tracker._factory.log") as mock_log,
        ):
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env=_env("TR4KER_API_KEY"),
            )

        warn_codes = [c.kwargs.get("code") for c in mock_log.warning.call_args_list]
        assert "disabled_in_priority" in warn_codes


# ---------------------------------------------------------------------------
# Severity split: error raises, warning does not
# ---------------------------------------------------------------------------


class TestSeveritySplit:
    """Tests confirming error-severity issues raise, warning-severity do not."""

    def test_error_severity_raises_tracker_config_error(self) -> None:
        """Missing key → error severity → TrackerConfigError raised."""
        cfg = _cfg({"tr4ker": True}, priority=["tr4ker"])

        with pytest.raises(TrackerConfigError):
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

    def test_warning_severity_does_not_raise(self) -> None:
        """disabled_in_priority → warning severity → no exception."""
        cfg = TrackerConfig(
            providers={
                "tr4ker": TrackerProviderConfig(enabled=True),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["tr4ker", "c411"],
        )

        with (
            patch(
                "personalscraper.api.tracker._factory._TRACKER_CLASSES",
                {"tr4ker": "tests.unit.test_tracker_factory:_StubSearchable"},
            ),
            patch("personalscraper.api.transport._http.HttpTransport"),
        ):
            # Must not raise:
            registry = build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env=_env("TR4KER_API_KEY"),
            )

        assert isinstance(registry, TrackerRegistry)


# ---------------------------------------------------------------------------
# Happy path: 2 enabled + credentialed trackers
# ---------------------------------------------------------------------------


class TestErrorAggregation:
    """Non-vacuous aggregation invariant: the factory never fails fast."""

    def test_multiple_missing_credentials_aggregated(self) -> None:
        """Two enabled, keyless trackers → TrackerConfigError carries BOTH issues."""
        cfg = _cfg({"tr4ker": True, "c411": True}, priority=["tr4ker", "c411"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

        issues = exc_info.value.issues
        assert len(issues) == 2
        providers = {i.provider for i in issues}
        assert providers == {"tr4ker", "c411"}


# ---------------------------------------------------------------------------
# Happy path: 2 enabled + credentialed trackers
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Tests for the normal, error-free boot path."""

    def test_two_credentialed_trackers_returns_registry_with_both(self) -> None:
        """2 enabled+credentialed trackers → TrackerRegistry with 2 entries."""
        cfg = _cfg({"tr4ker": True, "c411": True}, priority=["tr4ker", "c411"])

        with (
            patch(
                "personalscraper.api.tracker._factory._TRACKER_CLASSES",
                {
                    "tr4ker": "tests.unit.test_tracker_factory:_StubSearchable",
                    "c411": "tests.unit.test_tracker_factory:_StubSearchable",
                },
            ),
            patch("personalscraper.api.transport._http.HttpTransport"),
        ):
            registry = build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env=_env("TR4KER_API_KEY", "C411_API_KEY"),
            )

        assert isinstance(registry, TrackerRegistry)
        assert len(registry._trackers) == 2
        assert "tr4ker" in registry._trackers
        assert "c411" in registry._trackers


# ---------------------------------------------------------------------------
# Regression guard: pre-existing dict-ctor tests still compile
# ---------------------------------------------------------------------------


class TestDictCtorRegressionGuard:
    """Regression guard: the TrackerRegistry direct-ctor path is unchanged."""

    def test_tracker_registry_dict_ctor_unchanged(self) -> None:
        """TrackerRegistry.__init__ signature unchanged — factory layered above it."""
        stub = MagicMock()
        stub.search = MagicMock(return_value=[])
        r = TrackerRegistry(
            trackers={"tr4ker": stub},
            priority=["tr4ker"],
            ranking=RankingConfig(),
            priority_by_media_type={"movie": ["tr4ker"]},
        )
        assert r._priority == ["tr4ker"]
        assert r._priority_by_media_type == {"movie": ["tr4ker"]}


# ---------------------------------------------------------------------------
# TrackerConstructible conformance: every real client exposes from_env
# ---------------------------------------------------------------------------


class TestTrackerConstructibleConformance:
    """Every real tracker client implements the uniform from_env contract.

    The factory dispatches construction UNIFORMLY through
    ``TrackerConstructible.from_env`` (no provider-name literal, no cred-style
    branch). Every concrete client must therefore expose a callable
    ``from_env`` classmethod — a conformance guard so a future client that
    forgets it is caught here rather than at boot.
    """

    def test_all_real_clients_expose_from_env(self) -> None:
        """c411 / tr4ker both expose a callable from_env classmethod."""
        from personalscraper.api.tracker.c411 import C411Client  # noqa: PLC0415
        from personalscraper.api.tracker.tr4ker import Tr4kerClient  # noqa: PLC0415

        for cls in (C411Client, Tr4kerClient):
            assert hasattr(cls, "from_env"), f"{cls.__name__} missing from_env"
            assert callable(cls.from_env)

    def test_tr4ker_resolves_through_the_real_class_map(self) -> None:
        """tr4ker boots end-to-end through the REAL _TRACKER_CLASSES entry.

        No stub substitution: this is the wiring the operator gets once
        TR4KER_API_KEY is in the environment — the factory must import
        ``Tr4kerClient``, build it via the uniform ``from_env`` and expose its
        transport to the grab seam.
        """
        from personalscraper.api.tracker.tr4ker import Tr4kerClient  # noqa: PLC0415

        cfg = _cfg({"c411": True, "tr4ker": True}, priority=["c411", "tr4ker"])

        registry = build_tracker_registry(
            cfg,
            _ranking(),
            settings=_settings(),
            event_bus=EventBus(),
            cb_policy=_policy(),
            env=_env("C411_API_KEY", "TR4KER_API_KEY"),
        )

        assert isinstance(registry._trackers["tr4ker"], Tr4kerClient)
        assert sorted(registry.transports()) == ["c411", "tr4ker"]

    def test_tr4ker_enabled_without_key_fails_boot_loudly(self) -> None:
        """An enabled tr4ker with no API key is a boot ERROR, never a silent skip.

        The tracker factory's contract is fail-loud (parity with
        ``RegistryConfigError``): enabling tr4ker in config while removing
        ``TR4KER_API_KEY`` from the environment breaks boot on purpose, rather
        than quietly searching one tracker short.
        """
        cfg = _cfg({"tr4ker": True}, priority=["tr4ker"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg,
                _ranking(),
                settings=_settings(),
                event_bus=EventBus(),
                cb_policy=_policy(),
                env={},
            )

        assert any("TR4KER_API_KEY" in i.message for i in exc_info.value.issues)
        assert [i.code for i in exc_info.value.issues] == ["missing_credentials"]

    def test_api_key_client_from_env_builds_instance(self) -> None:
        """C411Client.from_env builds a real client from a single API key (no network)."""
        from personalscraper.api.tracker.c411 import C411Client  # noqa: PLC0415

        with patch("personalscraper.api.tracker.torznab.HttpTransport") as mock_transport:
            client = C411Client.from_env(
                env={"C411_API_KEY": "secret"},
                event_bus=EventBus(),
                required=["C411_API_KEY"],
                provider_cfg=TrackerProviderConfig(enabled=True),
            )
        assert isinstance(client, C411Client)
        mock_transport.assert_called_once()
