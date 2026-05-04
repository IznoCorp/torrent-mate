"""Reference integration test for HttpTransport consuming TransportPolicy."""

from __future__ import annotations

import re
from typing import Any

import pytest
import responses

from personalscraper.api._contracts import CircuitOpenError
from personalscraper.api.transport._auth import ApiKeyAuth, NoAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import CircuitPolicy, RetryPolicy, TransportPolicy

BASE = "http://test-api.example.com"


def _make_policy(**overrides: Any) -> TransportPolicy:
    kwargs: dict[str, Any] = {
        "provider_name": "TestAPI",
        "base_url": BASE,
        "auth": ApiKeyAuth("test-key", location="query"),
        "retry": RetryPolicy(max_attempts=3, initial_wait=0.001, max_wait=0.01),
        "circuit": CircuitPolicy(failure_threshold=2, cooldown_seconds=0.1, count_retries=False),
    }
    kwargs.update(overrides)
    return TransportPolicy(**kwargs)


class TestQueryAuthParam:
    """Auth query param is sent on every request."""

    @responses.activate
    def test_query_auth_sent(self) -> None:
        """ApiKeyAuth(location='query') adds api_key to query params."""
        responses.add(responses.GET, re.compile(rf"{BASE}/test"), json={"ok": True})

        transport = HttpTransport(_make_policy())
        transport.get("/test")
        transport.close()

        req = responses.calls[0].request
        assert req.url is not None
        assert "api_key=test-key" in req.url


class TestRetryBehavior:
    """Retry on 503, success on 3rd call."""

    @responses.activate
    def test_retries_on_503(self) -> None:
        """Retries 503 twice, succeeds on third attempt."""
        url = f"{BASE}/flaky"
        responses.add(responses.GET, url, json={"error": "boom"}, status=503)
        responses.add(responses.GET, url, json={"error": "boom"}, status=503)
        responses.add(responses.GET, url, json={"ok": True}, status=200)

        transport = HttpTransport(_make_policy())
        result = transport.get("/flaky")
        transport.close()

        assert isinstance(result, dict)
        assert result["ok"] is True
        assert len(responses.calls) == 3


class TestCircuitBreaker:
    """Circuit opens after 2 final failures (not 2 attempts inside one call)."""

    @responses.activate
    def test_circuit_opens_after_two_failures(self) -> None:
        """Circuit opens after 2 final failures (count_retries=False)."""
        url = f"{BASE}/down"

        # Call 1: fails after 3 attempts (max_attempts=3), 1 final failure
        for _ in range(3):
            responses.add(responses.GET, url, json={"error": "down"}, status=500)
        # Call 2: fails after 3 attempts, 2nd final failure -> circuit opens
        for _ in range(3):
            responses.add(responses.GET, url, json={"error": "down"}, status=500)

        transport = HttpTransport(_make_policy())

        # Call 1 — fails, circuit records 1 final failure
        with pytest.raises(Exception):
            transport.get("/down")
        # Call 2 — fails, circuit records 2nd final failure -> opens
        with pytest.raises(Exception):
            transport.get("/down")
        # Call 3 — circuit is open
        with pytest.raises(CircuitOpenError, match="Circuit breaker OPEN"):
            transport.get("/down")

        transport.close()


class TestResponseFormats:
    """response_format controls body parsing."""

    @responses.activate
    def test_text_format(self) -> None:
        """'text' response_format returns resp.text unchanged."""
        url = f"{BASE}/text"
        responses.add(responses.GET, url, body="plain text response", status=200)

        transport = HttpTransport(_make_policy(response_format="text", auth=NoAuth()))
        result = transport.get("/text")
        transport.close()

        assert result == "plain text response"

    @responses.activate
    def test_xml_format(self) -> None:
        """'xml' response_format parses XML into a dict."""
        url = f"{BASE}/xml"
        responses.add(
            responses.GET,
            url,
            body="<root><item>value</item></root>",
            status=200,
            content_type="application/xml",
        )

        transport = HttpTransport(_make_policy(response_format="xml", auth=NoAuth()))
        result = transport.get("/xml")
        transport.close()

        assert result == {"root": {"item": "value"}}
