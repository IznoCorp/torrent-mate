"""Pipeline configuration via pydantic-settings.

Loads settings from environment variables and .env file.
Single source of truth for all pipeline configuration (V0-V9).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pipeline configuration loaded from .env and environment variables.

    Attributes:
        qbit_host: qBittorrent Web API hostname.
        qbit_port: qBittorrent Web API port.
        qbit_username: qBittorrent login username.
        qbit_password: qBittorrent login password.
        torrent_complete_dir: Directory where completed torrents land.
        staging_dir: Staging area ("A TRIER") for media processing.
        disk1_dir: Storage disk 1 mount point.
        disk2_dir: Storage disk 2 mount point.
        disk3_dir: Storage disk 3 mount point.
        disk4_dir: Storage disk 4 mount point.
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
        ingest_dir_name: Ingest subdirectory name (relative to staging_dir).
        data_dir_name: Data directory name for lock/tracker (relative to staging_dir).
        movies_dir_name: Movies category directory name.
        tvshows_dir_name: TV shows category directory name.
        ebooks_dir_name: Ebooks category directory name.
        audio_dir_name: Audio category directory name.
        apps_dir_name: Apps category directory name.
        other_dir_name: Other/misc category directory name.
        circuit_breaker_threshold: Consecutive errors before opening circuit.
        circuit_breaker_cooldown: Seconds to wait before retrying after circuit opens.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # qBittorrent
    qbit_host: str = "localhost"
    qbit_port: int = 8081
    qbit_username: str = "izno"
    qbit_password: str = ""

    # Paths
    torrent_complete_dir: Path = Path("/Volumes/IznoServer SSD/torrents/complete")
    staging_dir: Path = Path("/Volumes/IznoServer SSD/A TRIER")
    disk1_dir: Path = Path("/Volumes/Disk1/medias")
    disk2_dir: Path = Path("/Volumes/Disk2/medias")
    disk3_dir: Path = Path("/Volumes/Disk3/medias")
    disk4_dir: Path = Path("/Volumes/Disk4/medias")

    # TMDB
    tmdb_api_key: str = ""

    # TVDB
    tvdb_api_key: str = ""

    # Scraper
    scraper_language: str = "fr-FR"
    scraper_fallback_language: str = "en-US"
    scraper_prefer_local_title: bool = True

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Monitoring (optional)
    healthcheck_url: str = ""

    # Thresholds
    min_free_space_staging_gb: int = 20
    min_free_space_disk_gb: float = 100

    # Internal directories (relative to staging_dir if not absolute)
    ingest_dir_name: str = "097-TEMP"
    data_dir_name: str = ".personalscraper"

    # Category directory names
    movies_dir_name: str = "001-MOVIES"
    tvshows_dir_name: str = "002-TVSHOWS"
    ebooks_dir_name: str = "003-EBOOKS"
    audio_dir_name: str = "004-AUDIO"
    apps_dir_name: str = "005-APPS"
    other_dir_name: str = "098-AUTRES"

    # Circuit breaker (V8 — API outage detection)
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown: int = 300

    @property
    def ingest_dir(self) -> Path:
        """Resolved ingest directory (where ingest deposits files).

        Returns:
            Absolute path, resolved relative to staging_dir if not absolute.
        """
        p = Path(self.ingest_dir_name)
        return p if p.is_absolute() else self.staging_dir / p

    @property
    def data_dir(self) -> Path:
        """Resolved data directory (lock file, tracker JSON).

        Returns:
            Absolute path, resolved relative to staging_dir if not absolute.
        """
        p = Path(self.data_dir_name)
        return p if p.is_absolute() else self.staging_dir / p


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Returns:
        The Settings instance, loaded once and cached for all subsequent calls.
    """
    return Settings()
