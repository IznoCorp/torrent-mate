"""Shared-checkout .env resolution (plex-env #346).

The pipeline crons run the DEPLOY checkout, whose root ``.env`` lacked
``PLEX_TOKEN`` — so the post-dispatch Plex refresh was silently disabled and
dispatched media never appeared in Plex. The fix resolves a canonical ``.env``
(beside the ``config/`` the clone already points at via ``PERSONALSCRAPER_CONFIG``)
and overlays it UNDER the local one: the local file still wins for every key it
sets, the canonical only fills the gaps (the Plex token).
"""

from __future__ import annotations

from pathlib import Path

import pytest

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

    def test_explicit_override_wins_over_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """PERSONALSCRAPER_ENV_FILE points straight at the canonical .env."""
        _clear_env(monkeypatch)
        explicit = tmp_path / "secrets.env"
        explicit.write_text("PLEX_TOKEN=xyz\n", encoding="utf-8")
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(explicit))
        assert _canonical_env_path() == explicit
        assert _resolve_env_files()[0] == str(explicit)

    def test_missing_override_file_is_ignored(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A PERSONALSCRAPER_ENV_FILE that does not exist is ignored (fail-soft)."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("PERSONALSCRAPER_ENV_FILE", str(tmp_path / "nope.env"))
        assert _canonical_env_path() is None


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
