"""The qBittorrent auth lockout file names its environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.api.torrent._errors import QBitAuthLockoutError
from personalscraper.api.torrent.qbittorrent import _check_lockout, _set_lockout, lockout_path
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

    def test_no_argument_under_prod_reads_the_historical_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No argument with ``PERSONALSCRAPER_ENV=prod`` → the historical path."""
        monkeypatch.setenv(ENV_VAR, "prod")
        assert lockout_path() == _HISTORICAL

    def test_none_reads_the_environment_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No argument with ``PERSONALSCRAPER_ENV=staging`` → the staging file."""
        monkeypatch.setenv(ENV_VAR, "staging")
        assert lockout_path() == _HISTORICAL.with_name("qbit_auth_lockout-staging")


class TestLockoutWiring:
    """``_set_lockout`` and ``_check_lockout`` use the current environment's file."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Redirect the home directory to ``tmp_path`` under ``PERSONALSCRAPER_ENV=staging``.

        Returns:
            The (created) ``~/.cache/personalscraper`` directory of the redirected home.
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv(ENV_VAR, "staging")
        directory = tmp_path / ".cache" / "personalscraper"
        directory.mkdir(parents=True)
        return directory

    def test_set_lockout_writes_the_environment_file(self, cache_dir: Path) -> None:
        """Under staging, the lockout lands in ``-staging`` and never in the bare prod file."""
        _set_lockout("login_failed")

        assert (cache_dir / "qbit_auth_lockout-staging").read_text() == "login_failed"
        assert not (cache_dir / "qbit_auth_lockout").exists()

    def test_check_ignores_the_prod_lockout(self, cache_dir: Path) -> None:
        """Under staging, a fresh prod lockout does not block (no raise)."""
        (cache_dir / "qbit_auth_lockout").write_text("login_failed")

        _check_lockout()

    def test_check_raises_on_the_environment_lockout(self, cache_dir: Path) -> None:
        """Under staging, a fresh ``-staging`` lockout blocks."""
        (cache_dir / "qbit_auth_lockout-staging").write_text("login_failed")

        with pytest.raises(QBitAuthLockoutError):
            _check_lockout()
