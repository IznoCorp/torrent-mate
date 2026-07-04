"""Pipeline credentials via pydantic-settings.

Loads secrets and credentials from environment variables and .env file.

Config split: all paths, thresholds, scraper settings, and disk structure
live in config.json5 (see ``conf/models.py::Config``). This module retains
only secrets (API keys, passwords, tokens).
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the package root (parent of this config module),
# not CWD.  pydantic-settings treats a relative env_file as CWD-relative,
# which breaks when the pipeline is launched from the staging directory
# (config.json5 + .env live at the project root, not inside staging).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


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
        web_password_hash: scrypt-hashed password for web UI login.
        web_jwt_secret: HS256 secret key for JWT session tokens.
    """

    model_config = SettingsConfigDict(env_file=str(_ENV_PATH), extra="ignore")

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
