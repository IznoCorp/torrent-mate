"""The Plex client's deletion calls: a section's scan state, its trash emptied, the bundles cleaned (K2-10).

A medium deleted from the library must leave Plex too: the deleted folder's parent is
rescanned (``refresh``), the deletion waits for that section's scan to end, then the
section's trash is emptied and the orphan bundles cleaned. Each call is fail-soft like
every method of the client: ``False`` (or ``None`` for the scan state) on any failure,
never a raise, and never the token in a URL or a log record.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
import requests

from personalscraper.api.plex import PlexClient

_TOKEN = "PLEX-T0KEN-DELETION-7c1e"
_BASE = "http://localhost:32400"


class _FakeResponse:
    """Minimal stand-in for :class:`requests.Response`."""

    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        """Return the canned payload, or raise like a non-JSON body would."""
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeSession:
    """Records every GET and PUT and replays one canned response (or exception) per method."""

    def __init__(self, *, get: Any = None, put: Any = None) -> None:
        self._get = get
        self._put = put
        self.calls: list[dict[str, Any]] = []

    def _answer(self, method: str, url: str, params: Any, headers: Any, allow_redirects: Any, nxt: Any) -> Any:
        self.calls.append(
            {"method": method, "url": url, "params": params, "headers": headers, "allow_redirects": allow_redirects}
        )
        if isinstance(nxt, Exception):
            raise nxt
        return nxt if nxt is not None else _FakeResponse(200, {})

    def get(
        self, url: str, *, params: Any = None, headers: Any = None, timeout: Any = None, allow_redirects: Any = None
    ) -> Any:
        """Record the GET and return the canned response."""
        return self._answer("GET", url, params, headers, allow_redirects, self._get)

    def put(
        self, url: str, *, params: Any = None, headers: Any = None, timeout: Any = None, allow_redirects: Any = None
    ) -> Any:
        """Record the PUT and return the canned response."""
        return self._answer("PUT", url, params, headers, allow_redirects, self._put)


def _client(session: _FakeSession) -> PlexClient:
    """Build a client over a fake session."""
    return PlexClient(_BASE, _TOKEN, session=session)  # type: ignore[arg-type]


def _sections(refreshing: Any) -> dict[str, Any]:
    """A ``/library/sections`` payload whose section 2 carries *refreshing*."""
    return {
        "MediaContainer": {
            "Directory": [
                {"key": "1", "title": "Films", "refreshing": False, "Location": [{"path": "/d1/films"}]},
                {"key": "2", "title": "Series", "refreshing": refreshing, "Location": [{"path": "/d1/series"}]},
            ]
        }
    }


_FAILURES = [
    pytest.param(requests.ConnectionError("down"), id="unreachable"),
    pytest.param(UnicodeEncodeError("utf-8", "x", 0, 1, "surrogate"), id="non-requests-error"),
    pytest.param(_FakeResponse(401), id="token-refused"),
    pytest.param(_FakeResponse(500), id="server-error"),
]


class TestEmptyTrash:
    """``PUT /library/sections/{key}/emptyTrash``."""

    def test_puts_the_section_empty_trash(self) -> None:
        """The section's trash is emptied by a PUT, the token in the header only, redirects not followed."""
        session = _FakeSession(put=_FakeResponse(200))

        assert _client(session).empty_trash("2") is True
        [call] = session.calls
        assert call["method"] == "PUT"
        assert call["url"] == f"{_BASE}/library/sections/2/emptyTrash"
        assert call["headers"]["X-Plex-Token"] == _TOKEN
        assert _TOKEN not in call["url"]
        assert call["allow_redirects"] is False

    @pytest.mark.parametrize("failure", _FAILURES)
    def test_any_failure_is_false_never_a_raise(self, failure: Any, caplog: pytest.LogCaptureFixture) -> None:
        """Unreachable, refused or failing: ``False``, and no log record carries the token."""
        caplog.set_level(logging.DEBUG)

        assert _client(_FakeSession(put=failure)).empty_trash("2") is False
        assert all(_TOKEN not in record.getMessage() for record in caplog.records)


class TestCleanBundles:
    """``PUT /library/clean/bundles``."""

    def test_puts_the_bundle_clean(self) -> None:
        """The orphan bundles are cleaned by one PUT on the server-wide path."""
        session = _FakeSession(put=_FakeResponse(200))

        assert _client(session).clean_bundles() is True
        [call] = session.calls
        assert call["method"] == "PUT"
        assert call["url"] == f"{_BASE}/library/clean/bundles"
        assert call["headers"]["X-Plex-Token"] == _TOKEN
        assert call["allow_redirects"] is False

    @pytest.mark.parametrize("failure", _FAILURES)
    def test_any_failure_is_false_never_a_raise(self, failure: Any) -> None:
        """Unreachable, refused or failing: ``False``."""
        assert _client(_FakeSession(put=failure)).clean_bundles() is False


class TestSectionRefreshing:
    """Whether a section's scan still runs, read fresh (never from the sections cache)."""

    @pytest.mark.parametrize(("value", "expected"), [(True, True), (False, False), ("1", True), ("0", False)])
    def test_reads_the_section_refreshing_flag(self, value: Any, expected: bool) -> None:
        """The flag is read as Plex spells it, a boolean or ``"1"`` / ``"0"``."""
        assert _client(_FakeSession(get=_FakeResponse(200, _sections(value)))).section_refreshing("2") is expected

    def test_absent_flag_is_an_idle_section(self) -> None:
        """A section listed without the flag is not scanning."""
        assert _client(_FakeSession(get=_FakeResponse(200, _sections(None)))).section_refreshing("2") is False

    def test_reads_fresh_every_call(self) -> None:
        """Two calls, two requests: the scan state moves, the sections cache is not consulted."""
        session = _FakeSession(get=_FakeResponse(200, _sections(True)))
        client = _client(session)
        client.sections()

        client.section_refreshing("2")
        client.section_refreshing("2")

        assert len(session.calls) == 3
        assert all(call["url"] == f"{_BASE}/library/sections" for call in session.calls)

    def test_unknown_section_is_none(self) -> None:
        """A key the server does not list: unknown, never « idle »."""
        assert _client(_FakeSession(get=_FakeResponse(200, _sections(False)))).section_refreshing("9") is None

    @pytest.mark.parametrize(
        "failure",
        [
            *_FAILURES,
            pytest.param(_FakeResponse(200, None), id="unparseable"),
            pytest.param(_FakeResponse(200, {"MediaContainer": []}), id="odd-shape"),
        ],
    )
    def test_any_failure_is_none_never_a_raise(self, failure: Any) -> None:
        """Unreachable, refused, failing or unparseable: ``None``."""
        assert _client(_FakeSession(get=failure)).section_refreshing("2") is None
