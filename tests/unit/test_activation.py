"""Tests for ProviderActivation resolution."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from personalscraper.api._activation import PROVIDER_CREDS, resolve_active


@dataclass
class _FakeProvider:
    enabled: bool = True


class TestResolveActive:
    """resolve_active() tests per DESIGN S8.7."""

    def test_enabled_with_creds(self) -> None:
        """enabled=True + creds present → in active list."""
        env = {"TMDB_API_KEY": "key123"}
        providers = {"tmdb": _FakeProvider(enabled=True)}
        result = resolve_active(providers, "metadata", env=env)
        assert result == ["tmdb"]

    def test_enabled_missing_creds(self, caplog: pytest.LogCaptureFixture) -> None:
        """enabled=True + creds missing → not in list, WARNING logged."""
        caplog.set_level(logging.WARNING)
        providers = {"tmdb": _FakeProvider(enabled=True)}
        result = resolve_active(providers, "metadata", env={})
        assert result == []
        assert "provider_disabled" in caplog.text
        assert "tmdb" in caplog.text

    def test_disabled_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """enabled=False → not in list, no warning."""
        caplog.set_level(logging.WARNING)
        providers = {"omdb": _FakeProvider(enabled=False)}
        result = resolve_active(providers, "metadata", env={})
        assert result == []
        assert "provider_disabled" not in caplog.text

    def test_multiple_required_missing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Multiple required creds, partial missing → not active, all missing listed."""
        caplog.set_level(logging.WARNING)
        providers = {"telegram": _FakeProvider(enabled=True)}
        result = resolve_active(providers, "notify", env={"TELEGRAM_BOT_TOKEN": "tok"})
        assert result == []
        assert "TELEGRAM_CHAT_ID" in caplog.text

    def test_all_creds_present(self) -> None:
        """All required creds present → active. Trakt app-only needs only CLIENT_ID."""
        env = {"TRAKT_CLIENT_ID": "id"}
        providers = {"trakt": _FakeProvider(enabled=True)}
        result = resolve_active(providers, "metadata", env=env)
        assert result == ["trakt"]

    def test_mixed_providers(self) -> None:
        """Mixed enabled/disabled with varying cred presence."""
        env = {"TMDB_API_KEY": "k1", "TVDB_API_KEY": "k2"}
        providers = {
            "tmdb": _FakeProvider(enabled=True),
            "tvdb": _FakeProvider(enabled=True),
            "omdb": _FakeProvider(enabled=False),
        }
        result = resolve_active(providers, "metadata", env=env)
        assert result == ["tmdb", "tvdb"]

    def test_family_is_logging_only(self, caplog: pytest.LogCaptureFixture) -> None:
        """Family param appears in log record but doesn't affect resolution."""
        caplog.set_level(logging.WARNING)
        providers = {"tmdb": _FakeProvider(enabled=True)}
        result = resolve_active(providers, "metadata", env={})
        assert result == []
        assert "metadata" in caplog.text


class TestProviderCreds:
    """PROVIDER_CREDS structure tests."""

    def test_has_12_entries(self) -> None:
        """PROVIDER_CREDS has exactly 12 entries.

        The two extra entries (``imdb`` and ``rotten_tomatoes``) are
        façades over the OMDb HTTP backend introduced by the
        ``provider-ids`` feature ; they share OMDb's credential.
        """
        assert len(PROVIDER_CREDS) == 12

    def test_known_providers(self) -> None:
        """Expected provider keys are present."""
        expected = {
            "tmdb",
            "tvdb",
            "omdb",
            "imdb",
            "rotten_tomatoes",
            "trakt",
            "qbittorrent",
            "transmission",
            "lacale",
            "c411",
            "telegram",
            "healthchecks",
        }
        assert set(PROVIDER_CREDS) == expected

    def test_imdb_and_rt_share_omdb_key(self) -> None:
        """The IMDb and Rotten Tomatoes façades share the OMDb credential.

        Both façades go through the same ``OMDbAdapter`` instance at
        construction time, so the credential mapping must agree —
        provisioning either is gated on ``OMDB_API_KEY`` alone.
        """
        assert PROVIDER_CREDS["imdb"] == ["OMDB_API_KEY"]
        assert PROVIDER_CREDS["rotten_tomatoes"] == ["OMDB_API_KEY"]
        assert PROVIDER_CREDS["omdb"] == ["OMDB_API_KEY"]
