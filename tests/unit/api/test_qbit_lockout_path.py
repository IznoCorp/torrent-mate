"""The qBittorrent auth lockout file names its environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.api.torrent.qbittorrent import lockout_path
from personalscraper.conf.environment import ENV_VAR, Environment

_HISTORICAL = Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"


class TestLockoutPath:
    """``lockout_path`` keeps the prod name and suffixes every other environment."""

    def test_prod_keeps_the_historical_path(self) -> None:
        """Explicit prod → the bare historical file."""
        assert lockout_path(Environment.PROD) == _HISTORICAL

    @pytest.mark.parametrize("env", [Environment.STAGING, Environment.DEV])
    def test_other_environments_carry_their_name(self, env: Environment) -> None:
        """A non-prod environment → ``qbit_auth_lockout-<env>`` beside the prod file."""
        assert lockout_path(env) == _HISTORICAL.with_name(f"qbit_auth_lockout-{env.value}")

    def test_unset_environment_is_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No argument and no ``PERSONALSCRAPER_ENV`` → the historical path."""
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert lockout_path() == _HISTORICAL

    def test_none_reads_the_environment_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No argument with ``PERSONALSCRAPER_ENV=staging`` → the staging file."""
        monkeypatch.setenv(ENV_VAR, "staging")
        assert lockout_path() == _HISTORICAL.with_name("qbit_auth_lockout-staging")
