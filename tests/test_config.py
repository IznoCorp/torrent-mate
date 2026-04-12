"""Tests for personalscraper.config — Settings loading and validation."""

from pathlib import Path

from personalscraper.config import Settings


def test_settings_defaults():
    """Settings loads with defaults when no .env file is present."""
    settings = Settings(_env_file=None)
    assert settings.qbit_host == "localhost"
    assert settings.qbit_port == 8081
    assert settings.scraper_language == "fr-FR"
    assert settings.min_free_space_staging_gb == 20
    assert settings.min_free_space_disk_gb == 100
    assert settings.scraper_prefer_local_title is True


def test_settings_from_env(tmp_path, monkeypatch):
    """Settings reads and converts values from environment variables."""
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


def test_ingest_dir_relative_default(tmp_path, monkeypatch):
    """ingest_dir resolves relative name against staging_dir."""
    monkeypatch.setenv("STAGING_DIR", str(tmp_path))
    s = Settings(_env_file=None)
    assert s.ingest_dir == tmp_path / "097-TEMP"


def test_ingest_dir_absolute_override(tmp_path, monkeypatch):
    """ingest_dir returns absolute path as-is when configured."""
    custom = tmp_path / "custom-ingest"
    monkeypatch.setenv("STAGING_DIR", str(tmp_path))
    monkeypatch.setenv("INGEST_DIR_NAME", str(custom))
    s = Settings(_env_file=None)
    assert s.ingest_dir == custom


def test_data_dir_relative_default(tmp_path, monkeypatch):
    """data_dir resolves relative name against staging_dir."""
    monkeypatch.setenv("STAGING_DIR", str(tmp_path))
    s = Settings(_env_file=None)
    assert s.data_dir == tmp_path / ".personalscraper"


def test_data_dir_absolute_override(tmp_path, monkeypatch):
    """data_dir returns absolute path as-is when configured."""
    custom = tmp_path / "custom-data"
    monkeypatch.setenv("STAGING_DIR", str(tmp_path))
    monkeypatch.setenv("DATA_DIR_NAME", str(custom))
    s = Settings(_env_file=None)
    assert s.data_dir == custom


def test_category_dir_names_configurable(monkeypatch):
    """Category directory names can be overridden via env vars."""
    monkeypatch.setenv("MOVIES_DIR_NAME", "films")
    monkeypatch.setenv("TVSHOWS_DIR_NAME", "series")
    s = Settings(_env_file=None)
    assert s.movies_dir_name == "films"
    assert s.tvshows_dir_name == "series"
