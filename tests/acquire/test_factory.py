"""Unit tests for build_acquire_context — acquire-lobe RP5c."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestBuildAcquireContext:
    """build_acquire_context() wires tracker_registry, leaves store=None, propagates torrent_client."""

    def _minimal_config(self) -> MagicMock:
        """Return a MagicMock config with the attributes build_acquire_context reads."""
        config = MagicMock()
        # build_tracker_registry reads config.tracker, config.ranking
        return config

    def test_store_is_none_by_default(self) -> None:
        """build_acquire_context sets store=None — RP3 fills it later."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        assert ctx.store is None

    def test_torrent_client_none_when_not_passed(self) -> None:
        """torrent_client defaults to None when not supplied."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        assert ctx.torrent_client is None

    def test_torrent_client_propagated_when_passed(self) -> None:
        """torrent_client is stored on the context when explicitly passed."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()
        fake_client = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(
                config,
                settings,
                event_bus=event_bus,
                cb_policy=cb_policy,
                torrent_client=fake_client,
            )

        assert ctx.torrent_client is fake_client

    def test_delegates_to_build_tracker_registry(self) -> None:
        """build_acquire_context calls build_tracker_registry with config.tracker, config.ranking."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            fake_registry = MagicMock()
            mock_build.return_value = fake_registry
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        mock_build.assert_called_once_with(
            config.tracker,
            config.ranking,
            settings=settings,
            event_bus=event_bus,
            cb_policy=cb_policy,
        )
        assert ctx.tracker_registry is fake_registry

    def test_tracker_config_error_surfaces(self) -> None:
        """TrackerConfigError from build_tracker_registry propagates unchanged."""
        from personalscraper.acquire._factory import build_acquire_context

        from personalscraper.api.tracker._errors import TrackerConfigError, TrackerConfigIssue

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="no key",
        )
        with patch(
            "personalscraper.acquire._factory.build_tracker_registry",
            side_effect=TrackerConfigError([issue]),
        ):
            with pytest.raises(TrackerConfigError):
                build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)
