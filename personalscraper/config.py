from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Monitoring (optional)
    healthcheck_url: str = ""

    # Thresholds
    min_free_space_staging_gb: int = 20
    min_free_space_disk_gb: float = 100


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
