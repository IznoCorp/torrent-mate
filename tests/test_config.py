"""Tests for personalscraper.config — Settings loading and validation."""

from personalscraper.config import Settings


def test_settings_defaults(monkeypatch):
    """Settings loads secret/credential defaults when no .env file is present."""
    for key in ("TMDB_API_KEY", "TVDB_API_KEY", "YOUTUBE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.qbit_host == "localhost"
    assert settings.qbit_port == 8081
    assert settings.tmdb_api_key == ""
    assert settings.tvdb_api_key == ""
    assert settings.youtube_api_key == ""


def test_settings_from_env(tmp_path, monkeypatch):
    """Settings reads and converts values from environment variables."""
    monkeypatch.setenv("QBIT_HOST", "192.168.1.100")
    monkeypatch.setenv("QBIT_PORT", "9090")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.qbit_host == "192.168.1.100"
    assert settings.qbit_port == 9090


def test_pipeline_tunables_are_ignored_by_settings(monkeypatch):
    """Pipeline tunables live in Config and are ignored by Settings."""
    monkeypatch.setenv("MIN_FREE_SPACE_DISK_GB", "200.5")
    monkeypatch.setenv("MIN_FREE_SPACE_STAGING_GB", "50")
    monkeypatch.setenv("SCRAPER_LANGUAGE", "en-US")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    rendered = s.model_dump()
    assert "min_free_space_disk_gb" not in rendered
    assert "min_free_space_staging_gb" not in rendered
    assert "scraper_language" not in rendered


def test_rich_repr_masks_secrets(monkeypatch):
    """Rich traceback renderer must not leak secrets when inspecting Settings.

    Reason: Rich's Traceback calls ``__rich_repr__`` if present; otherwise it
    walks ``__dict__`` directly and bypasses ``__repr__``'s masking. A missing
    ``__rich_repr__`` leaks qbit_password / API keys into any crash report.
    """
    monkeypatch.setenv("QBIT_PASSWORD", "supersecret")
    monkeypatch.setenv("TMDB_API_KEY", "tmdb-secret-key")
    monkeypatch.setenv("TVDB_API_KEY", "tvdb-secret-key")
    s = Settings(_env_file=None)  # type: ignore[call-arg]

    rendered = dict(s.__rich_repr__())
    assert rendered["qbit_password"] == "<masked>"
    assert rendered["tmdb_api_key"] == "<masked>"
    assert rendered["tvdb_api_key"] == "<masked>"
    # Non-secret fields must still be visible
    assert rendered["qbit_host"] == "localhost"
