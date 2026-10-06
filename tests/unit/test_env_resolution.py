"""Shared-checkout .env resolution (plex-env #346).

The pipeline crons run the DEPLOY checkout, whose root ``.env`` lacked
``PLEX_TOKEN`` — so the post-dispatch Plex refresh was silently disabled and
dispatched media never appeared in Plex. The fix resolves a canonical ``.env``
(beside the ``config/`` the clone already points at via ``PERSONALSCRAPER_CONFIG``)
and overlays it UNDER the local one: the local file still wins for every key it
sets, the canonical only fills the gaps (the Plex token). An explicit
``PERSONALSCRAPER_ENV_FILE`` is the exception: it is loaded alone, so an
environment pointed at its own secrets never reads the checkout's ``.env``.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

import personalscraper
from personalscraper import config as config_module
from personalscraper.config import Settings, _canonical_env_path, _resolve_env_files


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the env vars that steer .env resolution."""
    monkeypatch.delenv("PERSONALSCRAPER_ENV_FILE", raising=False)
    monkeypatch.delenv("PERSONALSCRAPER_CONFIG", raising=False)


class TestResolveEnvFiles:
    """_resolve_env_files ordering across the topology cases."""

    def test_no_override_is_local_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No config/override env vars ⇒ just the package-root .env (historical)."""
        _clear_env(monkeypatch)
        files = _resolve_env_files()
        assert len(files) == 1
        assert files[0].endswith("/.env")

    def test_config_sibling_env_is_prepended(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """PERSONALSCRAPER_CONFIG=<root>/config ⇒ <root>/.env prepended (canonical first)."""
        _clear_env(monkeypatch)
        root = tmp_path / "canonical"
        (root / "config").mkdir(parents=True)
        canonical_env = root / ".env"
        canonical_env.write_text("PLEX_TOKEN=abc\n", encoding="utf-8")
        monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(root / "config"))
        files = _resolve_env_files()
        assert len(files) == 2
        assert files[0] == str(canonical_env)  # canonical loaded FIRST (lower priority)
        assert files[1].endswith("/.env")  # local wins (loaded last)

    def test_config_without_sibling_env_is_local_only(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A config dir with no sibling .env ⇒ no canonical, local only (no crash)."""
        _clear_env(monkeypatch)
        (tmp_path / "config").mkdir()
        monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(tmp_path / "config"))
        assert _canonical_env_path() is None
        assert len(_resolve_env_files()) == 1

    def test_explicit_override_is_the_only_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """PERSONALSCRAPER_ENV_FILE is loaded ALONE: neither the config sibling nor the local .env joins it."""
        _clear_env(monkeypatch)
        root = tmp_path / "canonical"
        (root / "config").mkdir(parents=True)
        (root / ".env").write_text("PLEX_TOKEN=abc\n", encoding="utf-8")
        monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(root / "config"))
        explicit = tmp_path / "secrets.env"
        explicit.write_text("PLEX_TOKEN=xyz\n", encoding="utf-8")
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(explicit))
        assert _canonical_env_path() == explicit
        assert _resolve_env_files() == (str(explicit),)

    def test_missing_override_file_loads_nothing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A PERSONALSCRAPER_ENV_FILE that does not exist loads no file — never the local .env instead."""
        _clear_env(monkeypatch)
        missing = tmp_path / "nope.env"
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(missing))
        assert _canonical_env_path() is None
        assert _resolve_env_files() == (str(missing),)


class TestOverlaySemantics:
    """The overlay contract: local wins, canonical fills the gaps."""

    def test_canonical_fills_a_missing_key_while_local_wins_shared_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PLEX_TOKEN (only in canonical) is filled; a shared key keeps the LOCAL value."""
        # OS env vars outrank env_file in pydantic-settings; clear the two under
        # test so only the .env files decide (the host really exports PLEX_TOKEN).
        monkeypatch.delenv("PLEX_TOKEN", raising=False)
        monkeypatch.delenv("QBIT_USERNAME", raising=False)
        canonical = tmp_path / "canonical.env"
        local = tmp_path / "local.env"
        # canonical carries the token the local one lacks, plus a shared key.
        canonical.write_text("PLEX_TOKEN=from_canonical\nQBIT_USERNAME=canon_user\n", encoding="utf-8")
        # local overrides the shared key and has NO PLEX_TOKEN.
        local.write_text("QBIT_USERNAME=local_user\n", encoding="utf-8")

        settings = Settings(_env_file=(str(canonical), str(local)))  # type: ignore[call-arg]

        # Gap filled from the canonical .env — the exact bug this closes.
        assert settings.plex_token == "from_canonical"
        # Shared key: the LOCAL value wins (deploy/staging keep their own secrets).
        assert settings.qbit_username == "local_user"


class TestExplicitEnvFileIsolation:
    """An explicit PERSONALSCRAPER_ENV_FILE isolates an environment from the checkout's own .env."""

    def test_a_key_only_in_the_local_env_does_not_reach_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The preprod reads .env-staging alone: a key the checkout's .env defines never leaks in."""
        _clear_env(monkeypatch)
        # OS env vars outrank env_file in pydantic-settings; clear the keys under test.
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.delenv("QBIT_USERNAME", raising=False)
        local = tmp_path / "checkout" / ".env"
        local.parent.mkdir()
        local.write_text("TELEGRAM_CHAT_ID=from_local\nQBIT_USERNAME=local_user\n", encoding="utf-8")
        monkeypatch.setattr(config_module, "_local_env_path", lambda: local)
        explicit = tmp_path / "env-staging"
        explicit.write_text("QBIT_USERNAME=preprod_user\n", encoding="utf-8")
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(explicit))

        settings = Settings(_env_file=_resolve_env_files())  # type: ignore[call-arg]

        assert settings.telegram_chat_id == ""
        assert settings.qbit_username == "preprod_user"

    def test_without_env_file_the_local_env_still_loads(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No PERSONALSCRAPER_ENV_FILE: the checkout's .env is read, as before."""
        _clear_env(monkeypatch)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        local = tmp_path / "checkout" / ".env"
        local.parent.mkdir()
        local.write_text("TELEGRAM_CHAT_ID=from_local\n", encoding="utf-8")
        monkeypatch.setattr(config_module, "_local_env_path", lambda: local)

        settings = Settings(_env_file=_resolve_env_files())  # type: ignore[call-arg]

        assert settings.telegram_chat_id == "from_local"


class TestImportTimeLoad:
    """The package import loads PERSONALSCRAPER_ENV_FILE alone into ``os.environ``."""

    @staticmethod
    def _reload_package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, local_body: str) -> Path:
        """Re-run the package's import-time load against a fake checkout ``.env``.

        ``dotenv`` locates the checkout's ``.env`` through ``find_dotenv``; it is pointed at a
        file in ``tmp_path`` so the real one is never read. The probe keys are registered with
        the monkeypatch so ``os.environ`` is restored whatever the load wrote.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            tmp_path: Pytest tmp_path fixture value.
            local_body: Content of the fake checkout ``.env``.

        Returns:
            The fake checkout ``.env`` path.
        """
        for key in ("PROBE_LOCAL_ONLY", "PROBE_SHARED", "PROBE_EXPLICIT_ONLY"):
            monkeypatch.setenv(key, "placeholder")
            monkeypatch.delenv(key)
        local = tmp_path / "checkout" / ".env"
        local.parent.mkdir()
        local.write_text(local_body, encoding="utf-8")
        monkeypatch.setattr("dotenv.main.find_dotenv", lambda *_args, **_kwargs: str(local))
        return local

    def test_an_explicit_env_file_is_the_only_one_loaded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """With PERSONALSCRAPER_ENV_FILE set, the checkout's .env never reaches ``os.environ``."""
        _clear_env(monkeypatch)
        self._reload_package(monkeypatch, tmp_path, "PROBE_LOCAL_ONLY=from-local\nPROBE_SHARED=from-local\n")
        explicit = tmp_path / "env-staging"
        explicit.write_text("PROBE_EXPLICIT_ONLY=from-explicit\nPROBE_SHARED=from-explicit\n", encoding="utf-8")
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(explicit))

        importlib.reload(personalscraper)

        assert os.environ["PROBE_EXPLICIT_ONLY"] == "from-explicit"
        assert os.environ["PROBE_SHARED"] == "from-explicit"
        assert "PROBE_LOCAL_ONLY" not in os.environ

    def test_an_existing_variable_still_wins_over_the_explicit_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """``override=False``: a variable already exported is not replaced by the file."""
        _clear_env(monkeypatch)
        self._reload_package(monkeypatch, tmp_path, "")
        explicit = tmp_path / "env-staging"
        explicit.write_text("PROBE_SHARED=from-explicit\n", encoding="utf-8")
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(explicit))
        monkeypatch.setenv("PROBE_SHARED", "from-process")

        importlib.reload(personalscraper)

        assert os.environ["PROBE_SHARED"] == "from-process"

    def test_a_missing_explicit_file_loads_nothing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A named file that does not exist loads no file — never the checkout's .env instead."""
        _clear_env(monkeypatch)
        self._reload_package(monkeypatch, tmp_path, "PROBE_LOCAL_ONLY=from-local\n")
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(tmp_path / "nope.env"))

        importlib.reload(personalscraper)

        assert "PROBE_LOCAL_ONLY" not in os.environ

    def test_without_an_explicit_file_the_local_env_loads(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No PERSONALSCRAPER_ENV_FILE: the checkout's .env is loaded, as before."""
        _clear_env(monkeypatch)
        self._reload_package(monkeypatch, tmp_path, "PROBE_LOCAL_ONLY=from-local\n")

        importlib.reload(personalscraper)

        assert os.environ["PROBE_LOCAL_ONLY"] == "from-local"
