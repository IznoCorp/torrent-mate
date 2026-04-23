"""Tests for personalscraper.config — Settings loading and validation.

V15 note: disk paths (disk1_dir..disk4_dir), staging_dir, torrent_complete_dir,
and data_dir were removed from Settings in P6.1 — they now live in Config (conf/models.py).
Tests for those removed fields have been deleted accordingly.
"""

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
    settings = Settings(_env_file=None)
    assert settings.qbit_host == "192.168.1.100"
    assert settings.qbit_port == 9090


def test_settings_thresholds_configurable(monkeypatch):
    """Numeric thresholds can be overridden via env vars."""
    monkeypatch.setenv("MIN_FREE_SPACE_DISK_GB", "200.5")
    monkeypatch.setenv("MIN_FREE_SPACE_STAGING_GB", "50")
    s = Settings(_env_file=None)
    assert s.min_free_space_disk_gb == 200.5
    assert s.min_free_space_staging_gb == 50


def test_library_preferences_file_default():
    """library_preferences_file should default to 'library_preferences.json'."""
    settings = Settings(_env_file=None)
    assert settings.library_preferences_file == "library_preferences.json"


def test_rich_repr_masks_secrets(monkeypatch):
    """Rich traceback renderer must not leak secrets when inspecting Settings.

    Reason: Rich's Traceback calls ``__rich_repr__`` if present; otherwise it
    walks ``__dict__`` directly and bypasses ``__repr__``'s masking. A missing
    ``__rich_repr__`` leaks qbit_password / API keys into any crash report.
    """
    monkeypatch.setenv("QBIT_PASSWORD", "supersecret")
    monkeypatch.setenv("TMDB_API_KEY", "tmdb-secret-key")
    monkeypatch.setenv("TVDB_API_KEY", "tvdb-secret-key")
    s = Settings(_env_file=None)

    rendered = dict(s.__rich_repr__())
    assert rendered["qbit_password"] == "<masked>"
    assert rendered["tmdb_api_key"] == "<masked>"
    assert rendered["tvdb_api_key"] == "<masked>"
    # Non-secret fields must still be visible
    assert rendered["scraper_language"] == "fr-FR"
