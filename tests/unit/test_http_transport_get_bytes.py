"""Unit tests for ``HttpTransport.get_bytes`` — provider-agnostic binary GET.

Design: §5.1 — get_bytes uses the dedicated download circuit/limiter (D3);
absolute URL verbatim, relative joined onto base_url (D10); no auth-param
re-merge (D9); rejects empty body and oversized body with a provider-agnostic
``ValueError`` (D5); ``response_format=xml`` still returns raw bytes (survey F9).
Contract: the ``requests`` session is faked via monkeypatching ``_session.request``;
circuit isolation is verified by direct ``_download_circuit.state`` /
``_circuit.state`` inspection. No real network calls.

The ``TorrentFetchError`` surfacing for the empty/oversize cases is asserted at
the fetcher level in Phase 3 — the transport layer raises only ``ValueError``,
staying fully decoupled from any provider family.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._auth import ApiKeyAuth, NoAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.core.circuit import CircuitState
from personalscraper.core.event_bus import EventBus


def _make_transport(**overrides: Any) -> HttpTransport:
    """Build an :class:`HttpTransport` with bootstrap-friendly defaults.

    Args:
        **overrides: Field overrides forwarded to :class:`TransportPolicy`
            (e.g. ``base_url``, ``auth``, ``response_format``, ``circuit``).

    Returns:
        A freshly constructed transport wired to a no-subscriber EventBus.
    """
    kwargs: dict[str, Any] = {
        "provider_name": "TestAPI",
        "base_url": "https://test-api.example.com",
        "auth": NoAuth(),
        # max_attempts=1 keeps a failing call to a single HTTP round-trip so
        # the circuit-isolation tests count failures deterministically.
        "retry": RetryPolicy(max_attempts=1, initial_wait=0.001, max_wait=0.01),
        "circuit": CircuitPolicy(failure_threshold=2, cooldown_seconds=300.0, count_retries=False),
        "rate_limit": RateLimitPolicy(requests_per_second=0.0),
    }
    kwargs.update(overrides)
    return HttpTransport(TransportPolicy(**kwargs), event_bus=EventBus())


def _fake_response(*, status: int = 200, chunks: list[bytes] | None = None) -> MagicMock:
    """Build a fake :class:`requests.Response` for the streamed download path.

    Args:
        status: HTTP status code; ``ok`` is derived as ``status < 400``.
        chunks: Byte chunks yielded by ``iter_content``; defaults to a single
            non-empty chunk.

    Returns:
        A ``MagicMock`` exposing ``status_code``, ``ok``, ``url`` and an
        ``iter_content`` that yields ``chunks``.
    """
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.url = "https://test-api.example.com/dl"
    resp.reason = "Error"
    resp.json.side_effect = ValueError("not json")
    resp.text = ""
    payload = chunks if chunks is not None else [b"torrent-bytes"]
    resp.iter_content.return_value = iter(payload)
    return resp


class TestGetBytesUrlHandling:
    """Absolute vs relative URL handling — D10."""

    def test_absolute_url_used_verbatim(self) -> None:
        """An absolute URL is forwarded to ``requests.request`` unchanged.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, D10)
        Contract: ``get_bytes('https://c411.org/dl/abc?apikey=xyz')`` reaches
        the session with that exact URL — no base_url prefix, no rewrite.
        """
        transport = _make_transport()
        request_mock = MagicMock(return_value=_fake_response())
        transport._session.request = request_mock  # type: ignore[method-assign]

        transport.get_bytes("https://c411.org/dl/abc?apikey=xyz")

        called_url = request_mock.call_args.args[1]
        assert called_url == "https://c411.org/dl/abc?apikey=xyz"

    def test_relative_url_joined_onto_base_url(self) -> None:
        """A relative URL is joined onto ``policy.base_url``.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, D10)
        Contract: ``get_bytes('/api/download/abc123?token=jwt')`` with
        ``base_url='https://lacale.io'`` reaches the session as the full
        ``https://lacale.io/api/download/abc123?token=jwt``.
        """
        transport = _make_transport(base_url="https://lacale.io")
        request_mock = MagicMock(return_value=_fake_response())
        transport._session.request = request_mock  # type: ignore[method-assign]

        transport.get_bytes("/api/download/abc123?token=jwt")

        called_url = request_mock.call_args.args[1]
        assert called_url == "https://lacale.io/api/download/abc123?token=jwt"


class TestGetBytesNoAuthRemerge:
    """No auth-param re-merge on the binary/override path — D9."""

    def test_no_apikey_appended_to_absolute_url(self) -> None:
        """Query auth params are NOT re-appended on the download path.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, D9)
        Contract: even with ``ApiKeyAuth(location='query')`` configured, the
        verbatim absolute URL already carries its key, so ``params`` passed to
        ``requests.request`` is ``None``/empty — no second ``apikey``.
        """
        transport = _make_transport(auth=ApiKeyAuth("xyz", param="apikey", location="query"))
        request_mock = MagicMock(return_value=_fake_response())
        transport._session.request = request_mock  # type: ignore[method-assign]

        transport.get_bytes("https://c411.org/dl/abc?apikey=xyz")

        params = request_mock.call_args.kwargs["params"]
        assert not params  # None or empty dict — no re-merged apikey.


class TestGetBytesSizeCap:
    """Streamed size cap + empty-body reject — D5 (agnostic ValueError)."""

    def test_oversize_body_raises_value_error(self) -> None:
        """A body exceeding ``max_bytes`` aborts with a ``ValueError``.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, D5)
        Contract: ``iter_content`` yielding 100 bytes with ``max_bytes=10``
        raises a provider-agnostic ``ValueError`` mentioning ``max_bytes`` —
        NOT a ``TorrentFetchError`` (transport stays decoupled).
        """
        transport = _make_transport()
        request_mock = MagicMock(return_value=_fake_response(chunks=[b"x" * 100]))
        transport._session.request = request_mock  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="max_bytes"):
            transport.get_bytes("https://test-api.example.com/dl", max_bytes=10)

    def test_empty_body_raises_value_error(self) -> None:
        """An empty body aborts with a ``ValueError``.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, D5)
        Contract: ``iter_content`` yielding no chunks raises a
        provider-agnostic ``ValueError`` mentioning ``empty`` — NOT a
        ``TorrentFetchError`` (transport stays decoupled).
        """
        transport = _make_transport()
        request_mock = MagicMock(return_value=_fake_response(chunks=[]))
        transport._session.request = request_mock  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="empty"):
            transport.get_bytes("https://test-api.example.com/dl")


class TestGetBytesNon2xx:
    """Non-2xx responses raise ApiError (shared raise path)."""

    def test_401_raises_api_error(self) -> None:
        """A 401 response raises ``ApiError(http_status=401)``.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1)
        Contract: the download path shares ``_do_request_raw``'s non-2xx
        raise, so an unauthorized download surfaces as ``ApiError``.
        """
        transport = _make_transport()
        request_mock = MagicMock(return_value=_fake_response(status=401))
        transport._session.request = request_mock  # type: ignore[method-assign]

        with pytest.raises(ApiError) as excinfo:
            transport.get_bytes("https://test-api.example.com/dl")
        assert excinfo.value.http_status == 401

    def test_500_raises_api_error(self) -> None:
        """A 500 response raises ``ApiError(http_status=500)``.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1)
        Contract: a server error on the download path surfaces as
        ``ApiError`` with the upstream status preserved.
        """
        transport = _make_transport()
        request_mock = MagicMock(return_value=_fake_response(status=500))
        transport._session.request = request_mock  # type: ignore[method-assign]

        with pytest.raises(ApiError) as excinfo:
            transport.get_bytes("https://test-api.example.com/dl")
        assert excinfo.value.http_status == 500


class TestDownloadCircuitIsolation:
    """Download breaker/limiter isolation from the search ones — D3."""

    def test_download_500_does_not_open_search_circuit(self) -> None:
        """Download 5xx failures open the download circuit, not the search one.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, D3)
        Contract: with ``failure_threshold=2``, two failing ``get_bytes``
        calls open ``_download_circuit`` (OPEN) while ``_circuit`` (search)
        stays CLOSED — a download outage never trips the search breaker.
        """
        transport = _make_transport()
        request_mock = MagicMock(return_value=_fake_response(status=500))
        transport._session.request = request_mock  # type: ignore[method-assign]

        for _ in range(2):
            with pytest.raises(ApiError):
                transport.get_bytes("https://test-api.example.com/dl")

        assert transport._download_circuit.state == CircuitState.OPEN
        assert transport._circuit.state == CircuitState.CLOSED

    def test_search_rate_limiter_not_acquired_by_get_bytes(self) -> None:
        """``get_bytes`` acquires the download limiter, never the search one.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, D3)
        Contract: spying on ``_rate_limiter.acquire`` (search) shows it is
        never called by a succeeding ``get_bytes`` — only the dedicated
        ``_download_rate_limiter`` is used.
        """
        transport = _make_transport()
        request_mock = MagicMock(return_value=_fake_response())
        transport._session.request = request_mock  # type: ignore[method-assign]
        search_spy = MagicMock(wraps=transport._rate_limiter.acquire)
        transport._rate_limiter.acquire = search_spy  # type: ignore[method-assign]

        transport.get_bytes("https://test-api.example.com/dl")

        search_spy.assert_not_called()


class TestGetBytesResponseFormat:
    """Raw bytes are returned regardless of response_format — survey F9."""

    def test_xml_transport_returns_raw_bytes(self) -> None:
        """An ``xml`` transport's ``get_bytes`` returns raw ``bytes``.

        Design: docs/features/torrent-fetch/DESIGN.md (§5.1, F9)
        Contract: ``response_format='xml'`` does not route the download body
        through the XML parser — ``get_bytes`` returns the raw ``bytes``, not
        a parsed dict.
        """
        transport = _make_transport(response_format="xml")
        request_mock = MagicMock(return_value=_fake_response(chunks=[b"<x>raw</x>"]))
        transport._session.request = request_mock  # type: ignore[method-assign]

        result = transport.get_bytes("https://test-api.example.com/dl")

        assert isinstance(result, bytes)
        assert result == b"<x>raw</x>"
