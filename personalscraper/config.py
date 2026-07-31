"""Pipeline credentials via pydantic-settings.

Loads secrets and credentials from environment variables and .env file.

Config split: all paths, thresholds, scraper settings, and disk structure
live in config.json5 (see ``conf/models.py::Config``). This module retains
only secrets (API keys, passwords, tokens).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


def _canonical_env_path() -> Path | None:
    """The shared/canonical ``.env`` for a multi-checkout host, or ``None``.

    In the shared-checkout topology a deploy/staging clone points
    ``PERSONALSCRAPER_CONFIG`` at the CANONICAL checkout's ``config/`` dir (so all
    clones read one config). The full secret set lives beside that ``config/`` —
    at ``<config-parent>/.env`` — while the clone's OWN root ``.env`` may lack
    some (the recurring bug: the deploy ``.env`` had no ``PLEX_TOKEN``, so the
    post-dispatch Plex refresh was silently disabled and dispatched media never
    appeared in Plex). ``PERSONALSCRAPER_ENV_FILE`` is an explicit override.

    Returns:
        The canonical ``.env`` path if resolvable and present, else ``None``.
    """
    override = os.environ.get("PERSONALSCRAPER_ENV_FILE")
    if override:
        candidate = Path(override)
        return candidate if candidate.is_file() else None
    config_dir = os.environ.get("PERSONALSCRAPER_CONFIG")
    if config_dir:
        candidate = Path(config_dir).resolve().parent / ".env"
        if candidate.is_file():
            return candidate
    return None


def _resolve_env_files() -> tuple[str, ...]:
    """Resolve the ordered ``.env`` files pydantic-settings loads.

    The package-root ``.env`` (parent of this module — resolved absolutely, NOT
    CWD-relative, so a run launched from the staging dir still finds it) is the
    LOCAL one. When a distinct canonical ``.env`` exists (see
    :func:`_canonical_env_path`) it is prepended so the LOCAL file still wins for
    every key it defines — deploy/staging keep their own values — and the
    canonical only FILLS keys the local one omits (e.g. ``PLEX_TOKEN``).
    pydantic-settings loads a tuple left-to-right with later files taking
    precedence, so ``(canonical, local)`` gives exactly that.

    Returns:
        A tuple of ``.env`` paths in load order (canonical first when present).
    """
    local = Path(__file__).resolve().parent.parent / ".env"
    canonical = _canonical_env_path()
    if canonical is not None and canonical.resolve() != local.resolve():
        return (str(canonical), str(local))
    return (str(local),)


_ENV_FILES = _resolve_env_files()


class Settings(BaseSettings):
    """Pipeline credentials loaded from .env and environment variables.

    Only secrets, API keys, and credentials belong here. All paths,
    thresholds, and scraper tunables live in config.json5.

    Attributes:
        qbit_host: qBittorrent Web API hostname.
        qbit_port: qBittorrent Web API port.
        qbit_username: qBittorrent login username.
        qbit_password: qBittorrent login password.
        tmdb_api_key: The Movie Database API key (Bearer token).
        tvdb_api_key: TheTVDB API key (Negotiated Contract).
        youtube_api_key: YouTube Data API v3 key for trailer discovery.
        youtube_cookies_file: Path to a Netscape-format cookies.txt for yt-dlp.
        youtube_cookies_from_browser: Browser profile name for live cookie extraction.
        telegram_bot_token: Telegram bot token for notifications.
        telegram_chat_id: Telegram chat/user ID for notifications.
        healthcheck_url: Healthchecks.io ping URL for scheduling monitoring.
        plex_url: Plex server root for the post-dispatch library refresh.
        plex_token: Plex auth token; empty disables the refresh subscriber.
        web_password_hash: scrypt-hashed password for web UI login.
        web_jwt_secret: HS256 secret key for JWT session tokens.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    # qBittorrent
    qbit_host: str = "localhost"
    qbit_port: int = 8081
    qbit_username: str = ""
    qbit_password: str = ""

    # TMDB
    tmdb_api_key: str = ""

    # TVDB
    tvdb_api_key: str = ""

    # YouTube — trailer discovery (optional; empty values disable the primary tier)
    youtube_api_key: str = ""
    youtube_cookies_file: str = ""
    youtube_cookies_from_browser: str = ""

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Monitoring (optional)
    healthcheck_url: str = ""

    # Plex — post-dispatch library refresh (optional). An empty token leaves the
    # subscriber unwired: no request is ever made and the pipeline logs once why.
    plex_url: str = "http://localhost:32400"
    plex_token: str = ""

    # TorrentMate Web UI
    web_password_hash: str = ""
    web_jwt_secret: str = ""

    # Fields whose values must never appear in repr/str output (tracebacks, logs, etc.).
    _SECRET_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "qbit_password",
            "tmdb_api_key",
            "tvdb_api_key",
            "youtube_api_key",
            "telegram_bot_token",
            "healthcheck_url",
            "plex_token",
            "web_password_hash",
            "web_jwt_secret",
        }
    )

    def __repr__(self) -> str:
        """Return a repr that masks secret fields (prevents accidental leak via tracebacks)."""
        items = []
        for name, value in self.model_dump().items():
            if name in self._SECRET_FIELDS and value:
                items.append(f"{name}=<masked>")
            else:
                items.append(f"{name}={value!r}")
        return f"Settings({', '.join(items)})"

    __str__ = __repr__

    def __rich_repr__(self) -> Iterator[tuple[str, Any]]:
        """Rich-console repr that masks secrets.

        Rich's ``Traceback`` inspects live objects via ``__rich_repr__`` when
        present, otherwise falls back to ``__dict__``. Falling through to
        ``__dict__`` bypasses ``__repr__``'s masking, so this override is
        mandatory to keep ``qbit_password`` and API keys out of crash reports.
        """
        for name, value in self.model_dump().items():
            if name in self._SECRET_FIELDS and value:
                yield name, "<masked>"
            else:
                yield name, value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Returns:
        The Settings instance, loaded once and cached for all subsequent calls.
    """
    return Settings()
