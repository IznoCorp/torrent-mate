"""Pipeline secrets and numeric thresholds via pydantic-settings.

Loads settings from environment variables and .env file.

V15 split: paths and disk structure live in config.json5 (see
``conf/models.py::Config``). This module retains only secrets
(API keys, credentials) and numeric thresholds that cannot go into a
version-controlled config file.
"""

from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pipeline secrets and thresholds loaded from .env and environment variables.

    V15 note: disk paths (disk1_dir..disk4_dir), staging_dir, torrent_complete_dir,
    and data_dir_name have been removed — they now live in ``Config.paths`` and
    ``Config.disks`` (conf/models.py). Only secrets and numeric thresholds remain here.

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
        ingest_dir_name: Ingest subdirectory name (relative to staging_dir in config.json5).
        movies_dir_name: Movies category directory name (staging area only).
        tvshows_dir_name: TV shows category directory name (staging area only).
        ebooks_dir_name: Ebooks category directory name (staging area only).
        audio_dir_name: Audio category directory name (staging area only).
        apps_dir_name: Apps category directory name (staging area only).
        other_dir_name: Other/misc category directory name (staging area only).
        library_preferences_file: Library preferences filename (legacy, kept for V14 compat).
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

    # Internal directories (relative to staging_dir from config.json5 if not absolute)
    ingest_dir_name: str = "097-TEMP"

    # Category directory names (staging area — override via env if needed)
    movies_dir_name: str = "001-MOVIES"
    tvshows_dir_name: str = "002-TVSHOWS"
    ebooks_dir_name: str = "003-EBOOKS"
    audio_dir_name: str = "004-AUDIO"
    apps_dir_name: str = "005-APPS"
    other_dir_name: str = "098-AUTRES"

    # Library maintenance preferences
    library_preferences_file: str = "library_preferences.json"

    # Circuit breaker (V8 — API outage detection)
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

    def ingest_dir(self, staging_dir: Path) -> Path:
        """Resolved ingest directory (where ingest deposits files).

        Args:
            staging_dir: Staging directory from config.json5 (Config.paths.staging_dir).

        Returns:
            Absolute path, resolved relative to staging_dir if not absolute.
        """
        p = Path(self.ingest_dir_name)
        return p if p.is_absolute() else staging_dir / p


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Returns:
        The Settings instance, loaded once and cached for all subsequent calls.
    """
    return Settings()
