from pathlib import Path

from personalscraper.config import Settings


def test_settings_defaults():
    """Settings loads with defaults (no .env needed for fields with defaults)."""
    settings = Settings(_env_file=None)
    assert settings.qbit_host == "localhost"
    assert settings.qbit_port == 8081
    assert settings.scraper_language == "fr-FR"
    assert settings.min_free_space_staging_gb == 20
    assert settings.min_free_space_disk_gb == 100


def test_settings_from_env(tmp_path, monkeypatch):
    """Settings reads from environment variables."""
    monkeypatch.setenv("QBIT_HOST", "192.168.1.100")
    monkeypatch.setenv("QBIT_PORT", "9090")
    monkeypatch.setenv("STAGING_DIR", str(tmp_path))
    monkeypatch.setenv("TORRENT_COMPLETE_DIR", str(tmp_path))
    monkeypatch.setenv("DISK1_DIR", str(tmp_path))
    monkeypatch.setenv("DISK2_DIR", str(tmp_path))
    monkeypatch.setenv("DISK3_DIR", str(tmp_path))
    monkeypatch.setenv("DISK4_DIR", str(tmp_path))
    settings = Settings(_env_file=None)
    assert settings.qbit_host == "192.168.1.100"
    assert settings.qbit_port == 9090
    assert settings.staging_dir == tmp_path


def test_settings_paths_are_path_objects(mock_settings):
    """Path fields are actual Path objects, not strings."""
    assert isinstance(mock_settings.staging_dir, Path)
    assert isinstance(mock_settings.torrent_complete_dir, Path)
    assert isinstance(mock_settings.disk1_dir, Path)
