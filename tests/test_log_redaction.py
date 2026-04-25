"""Tests for the redact_secrets structlog processor (DESIGN §12).

Verifies that API keys, cookies, and URL key= parameters are redacted from
log event dicts before they reach any renderer.
"""

from personalscraper.logger import redact_secrets


def test_redact_top_level_api_key() -> None:
    """redact_secrets() replaces a top-level api_key value with ***REDACTED***."""
    result = redact_secrets(None, "info", {"event": "test", "api_key": "secret123"})
    assert result["api_key"] == "***REDACTED***"
    assert "secret123" not in str(result)


def test_redact_nested_cookie() -> None:
    """redact_secrets() recurses into nested dicts to redact cookie values."""
    result = redact_secrets(None, "info", {"event": "test", "request": {"headers": {"cookie": "sid=abc"}}})
    assert result["request"]["headers"]["cookie"] == "***REDACTED***"


def test_redact_url_key_param() -> None:
    """redact_secrets() strips the key= query param from URL-shaped string fields."""
    url = "https://www.googleapis.com/youtube/v3/search?key=AIzaSecret&q=foo"
    result = redact_secrets(None, "info", {"event": "test", "url": url})
    assert "AIzaSecret" not in result["url"]
    assert "***REDACTED***" in result["url"]


def test_non_secret_fields_unchanged() -> None:
    """redact_secrets() leaves non-secret fields untouched."""
    result = redact_secrets(None, "info", {"event": "test", "count": 42, "title": "x"})
    assert result == {"event": "test", "count": 42, "title": "x"}


# ── Sub-phase 10.4 — compound field-name redaction ───────────────────────────


def test_redacts_youtube_api_key_field() -> None:
    """redact_secrets() redacts a compound field named youtube_api_key."""
    result = redact_secrets(None, "info", {"event": "test", "youtube_api_key": "AIzaSecret"})
    assert result["youtube_api_key"] == "***REDACTED***"
    assert "AIzaSecret" not in str(result)


def test_redacts_tmdb_api_key_field() -> None:
    """redact_secrets() redacts a compound field named tmdb_api_key."""
    result = redact_secrets(None, "info", {"event": "test", "tmdb_api_key": "bearer-xyz"})
    assert result["tmdb_api_key"] == "***REDACTED***"
    assert "bearer-xyz" not in str(result)


def test_redacts_tvdb_api_key_field() -> None:
    """redact_secrets() redacts a compound field named tvdb_api_key."""
    result = redact_secrets(None, "info", {"event": "test", "tvdb_api_key": "tvdb-secret"})
    assert result["tvdb_api_key"] == "***REDACTED***"
    assert "tvdb-secret" not in str(result)


def test_redacts_cookies_file_path() -> None:
    """redact_secrets() redacts a field named cookies_file."""
    result = redact_secrets(
        None,
        "info",
        {"event": "test", "cookies_file": "/Users/foo/.config/youtube_cookies.txt"},
    )
    assert result["cookies_file"] == "***REDACTED***"
    assert "/Users/foo" not in str(result)


def test_redacts_cookie_file_path() -> None:
    """redact_secrets() redacts a field named cookie_file (singular)."""
    result = redact_secrets(
        None,
        "info",
        {"event": "test", "cookie_file": "/tmp/cookies.txt"},
    )
    assert result["cookie_file"] == "***REDACTED***"


def test_existing_exact_match_still_redacted() -> None:
    """Existing short-form exact-match keys (api_key, token, password) still redacted."""
    result = redact_secrets(None, "info", {"api_key": "k", "token": "t", "password": "p"})
    assert result["api_key"] == "***REDACTED***"
    assert result["token"] == "***REDACTED***"
    assert result["password"] == "***REDACTED***"
