"""Pipeline secrets and numeric thresholds via pydantic-settings.

Loads settings from environment variables and .env file.

Config split: paths and disk structure live in config.json5 (see
``conf/models.py::Config``). This module retains only secrets
(API keys, credentials) and numeric thresholds that cannot go into a
version-controlled config file.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Any, ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pipeline secrets and thresholds loaded from .env and environment variables.

    Note: disk paths (disk1_dir..disk4_dir), staging_dir, torrent_complete_dir,
    data_dir_name, and all *_dir_name fields have been removed — staging layout
    now lives in ``Config.staging_dirs`` (conf/models.py + conf/staging.py).
    Only secrets and numeric thresholds remain here.

    Attributes:
        qbit_host: qBittorrent Web API hostname.
        qbit_port: qBittorrent Web API port.
        qbit_username: qBittorrent login username.
        qbit_password: qBittorrent login password.
        tmdb_api_key: The Movie Database API key (Bearer token).
        tvdb_api_key: TheTVDB API key (Negotiated Contract).
        scraper_language: Primary language for API queries (TMDB format: "fr-FR").
        scraper_fallback_language: Fallback language when primary unavailable.
        scraper_prefer_local_title: Use local (FR) title for folder renaming.
        telegram_bot_token: Telegram bot token for notifications (empty = disabled).
        telegram_chat_id: Telegram chat/user ID for notifications (empty = disabled).
        healthcheck_url: Healthchecks.io ping URL for scheduling monitoring (empty = disabled).
        min_free_space_staging_gb: Minimum free space on SSD before ingest (GB).
        min_free_space_disk_gb: Minimum free space on storage disks before dispatch (GB).
        library_preferences_file: Library preferences filename (legacy, kept for backward compat).
        circuit_breaker_threshold: Consecutive errors before opening circuit.
        circuit_breaker_cooldown: Seconds to wait before retrying after circuit opens.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # qBittorrent
    qbit_host: str = "localhost"
    qbit_port: int = 8081
    qbit_username: str = ""
    qbit_password: str = ""

    # TMDB
    tmdb_api_key: str = ""

    # TVDB
    tvdb_api_key: str = ""

    # Scraper
    scraper_language: str = "fr-FR"
    scraper_fallback_language: str = "en-US"
    scraper_prefer_local_title: bool = True
    artwork_language: str = "en"

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Monitoring (optional)
    healthcheck_url: str = ""

    # Thresholds
    min_free_space_staging_gb: int = 20
    min_free_space_disk_gb: float = 100

    # Library maintenance preferences
    library_preferences_file: str = "library_preferences.json"

    # Circuit breaker — API outage detection
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown: int = 300

    # Fields whose values must never appear in repr/str output (tracebacks, logs, etc.).
    _SECRET_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "qbit_password",
            "tmdb_api_key",
            "tvdb_api_key",
            "telegram_bot_token",
            "healthcheck_url",
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
