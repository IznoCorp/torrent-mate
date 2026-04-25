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
