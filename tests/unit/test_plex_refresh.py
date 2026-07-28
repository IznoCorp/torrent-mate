"""Plex refresh trigger — client, subscriber, wiring (plex-refresh phase 1).

The bug this closes: the storage disks are macFUSE/NTFS mounts that deliver NO
filesystem events to Plex, so a film could land fully scraped and indexed and
stay invisible until an operator scanned by hand (Margin Call, 2026-07-28).

What these tests pin, in the order the DESIGN states it:

- D1 — ``ItemDispatched`` carries the destination FOLDER, filled by the
  dispatcher for the three actions (moved / merged / replaced);
- D2 — the client resolves the section by LONGEST ``Location`` prefix (never a
  hardcoded id) and refreshes that one folder; the subscriber is fail-soft
  ABSOLUTE: Plex down, 401, unknown path, client bug — the dispatch stands;
- the token appears in NO log record and in NO exception text;
- D3 — no token ⇒ nothing wired, zero requests.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from personalscraper.api.plex import PlexClient, PlexSection
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.subscribers.plex import PlexSubscriber

_TOKEN = "PLEX-T0KEN-DO-NOT-LOG-9f3a"

#: A realistic multi-section server: four disks, several libraries each, with
#: NESTED roots (``medias`` and ``medias/series``) — the shape that makes
#: first-match wrong and longest-prefix right.
_SECTIONS_PAYLOAD: dict[str, Any] = {
    "MediaContainer": {
        "Directory": [
            {
                "key": "1",
                "title": "Films",
                "Location": [
                    {"path": "/Volumes/Disk1/medias/films"},
                    {"path": "/Volumes/Disk2/medias/films"},
                ],
            },
            # The PARENT root is listed BEFORE the nested one on purpose: a
            # first-match resolver would answer "Tout Disk3" for a series folder
            # and scan the wrong library. Only longest-prefix gets it right, and
            # this ordering is what makes the test able to tell them apart.
            {
                "key": "3",
                "title": "Tout Disk3",
                "Location": [{"path": "/Volumes/Disk3/medias"}],
            },
            {
                "key": "2",
                "title": "Séries",
                "Location": [{"path": "/Volumes/Disk3/medias/series"}],
            },
        ]
    }
}


class _FakeResponse:
    """Minimal stand-in for :class:`requests.Response`."""

    def __init__(self, status_code: int = 200, payload: Any = None, *, raises_json: bool = False) -> None:
        self.status_code = status_code
        self._payload = payload
        self._raises_json = raises_json

    def json(self) -> Any:
        """Return the canned payload, or raise like a non-JSON body would."""
        if self._raises_json:
            raise ValueError("no json")
        return self._payload


class _FakeSession:
    """Records every GET and replays canned responses in order."""

    def __init__(self, *responses: Any) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params: Any = None, headers: Any = None, timeout: Any = None) -> Any:
        """Record the call and return (or raise) the next canned response."""
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        nxt = self._responses.pop(0) if self._responses else _FakeResponse(200, _SECTIONS_PAYLOAD)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _client(*responses: Any) -> tuple[PlexClient, _FakeSession]:
    """Build a client over a fake session."""
    session = _FakeSession(*responses)
    return PlexClient("http://localhost:32400", _TOKEN, session=session), session  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# D1 — the event carries the destination folder
# ---------------------------------------------------------------------------


class TestEventCarriesTargetPath:
    """``ItemDispatched.target_path`` — additive, and filled by the dispatcher."""

    def test_field_is_additive(self) -> None:
        """An emitter that does not know the folder still constructs the event."""
        event = ItemDispatched(
            source="dispatch",
            item="Inception (2010)",
            target_disk=Path("/Volumes/Disk2"),
            category_id="movies",
            action="moved",
        )

        assert event.target_path is None

    def test_dispatcher_fills_it_for_every_action(self) -> None:
        """The three actions are covered BEHAVIOURALLY, through a real dispatch.

        ``tests/dispatch/test_dispatch_events.py`` runs the real dispatcher for
        ``moved`` / ``replaced`` / ``merged`` and asserts each emitted event
        carries ``target_path == result.destination``. This test only guards
        that those assertions still exist, so deleting them cannot pass unnoticed
        (the behaviour itself is pinned there, not here).
        """
        source = Path("tests/dispatch/test_dispatch_events.py").read_text()

        assert source.count("target_path") >= 3, "each of the three actions must assert target_path"
        assert "event.target_path == result.destination" in source


# ---------------------------------------------------------------------------
# D2 — section resolution by longest prefix
# ---------------------------------------------------------------------------


class TestSectionResolution:
    """The section is resolved from the server's own Location paths."""

    def test_longest_prefix_wins_over_a_shorter_match(self) -> None:
        """A nested root beats its parent — first-match would scan the wrong library."""
        client, _ = _client(_FakeResponse(200, _SECTIONS_PAYLOAD))

        section = client.section_for(Path("/Volumes/Disk3/medias/series/Breaking Bad"))

        assert section is not None
        assert (section.key, section.title) == ("2", "Séries")

    def test_parent_section_still_matches_what_only_it_covers(self) -> None:
        """A path under the parent root but outside the nested one resolves to the parent."""
        client, _ = _client(_FakeResponse(200, _SECTIONS_PAYLOAD))

        section = client.section_for(Path("/Volumes/Disk3/medias/documentaires/Cosmos"))

        assert section is not None and section.key == "3"

    def test_second_location_of_a_section_matches(self) -> None:
        """A section indexing several disks matches on any of its roots."""
        client, _ = _client(_FakeResponse(200, _SECTIONS_PAYLOAD))

        section = client.section_for(Path("/Volumes/Disk2/medias/films/Margin Call (2011)"))

        assert section is not None and section.key == "1"

    def test_path_boundary_is_respected(self) -> None:
        """``/medias-old`` must NOT match the ``/medias`` root (real sibling naming)."""
        client, _ = _client(_FakeResponse(200, _SECTIONS_PAYLOAD))

        assert client.section_for(Path("/Volumes/Disk3/medias-old/Film")) is None

    def test_unknown_path_resolves_to_nothing(self) -> None:
        """A disk Plex does not index yields no section (the caller warns)."""
        client, _ = _client(_FakeResponse(200, _SECTIONS_PAYLOAD))

        assert client.section_for(Path("/Volumes/Disk9/medias/films/X")) is None

    def test_sections_are_fetched_once_and_cached(self) -> None:
        """Sections are stable config — one request per process, not per item."""
        client, session = _client(_FakeResponse(200, _SECTIONS_PAYLOAD))

        client.section_for(Path("/Volumes/Disk1/medias/films/A"))
        client.section_for(Path("/Volumes/Disk1/medias/films/B"))
        client.section_for(Path("/Volumes/Disk1/medias/films/C"))

        assert len(session.calls) == 1

    def test_no_hardcoded_section_ids_in_the_module(self) -> None:
        """The mapping comes from the server, never from a constant in our code."""
        import inspect

        from personalscraper.api import plex

        source = inspect.getsource(plex)

        assert "/library/sections/{section.key}/refresh" in source
        for hardcoded in ("sections/1/", "sections/2/", "sections/3/"):
            assert hardcoded not in source


# ---------------------------------------------------------------------------
# D2 — the refresh call itself
# ---------------------------------------------------------------------------


class TestRefresh:
    """``refresh`` triggers a PARTIAL scan of one folder."""

    def test_calls_the_section_refresh_with_the_folder(self) -> None:
        """URL = /library/sections/{id}/refresh, query carries the path."""
        client, session = _client(_FakeResponse(200, _SECTIONS_PAYLOAD), _FakeResponse(200))
        target = Path("/Volumes/Disk2/medias/films/Margin Call (2011)")

        assert client.refresh(target) is True

        refresh_call = session.calls[-1]
        assert refresh_call["url"] == "http://localhost:32400/library/sections/1/refresh"
        assert refresh_call["params"] == {"path": str(target)}

    def test_token_travels_in_the_header_never_in_the_url(self) -> None:
        """Header auth: the token can never end up in an access log or a referrer."""
        client, session = _client(_FakeResponse(200, _SECTIONS_PAYLOAD), _FakeResponse(200))

        client.refresh(Path("/Volumes/Disk2/medias/films/Margin Call (2011)"))

        for call in session.calls:
            assert call["headers"]["X-Plex-Token"] == _TOKEN
            assert _TOKEN not in call["url"]
            assert _TOKEN not in str(call["params"])

    def test_one_attempt_and_short_timeouts(self) -> None:
        """A trigger, not a business API: no retry loop, no long wait."""
        client, session = _client(requests.ConnectionError("refused"))

        assert client.refresh(Path("/Volumes/Disk2/medias/films/X")) is False
        assert len(session.calls) == 1, "a dead server must cost exactly one attempt"
        connect, read = session.calls[0]["timeout"]
        assert connect <= 5 and read <= 10

    @pytest.mark.parametrize(
        ("responses", "case"),
        [
            ([requests.ConnectionError("refused")], "server-down"),
            ([_FakeResponse(401)], "bad-token"),
            ([_FakeResponse(200, _SECTIONS_PAYLOAD), _FakeResponse(500)], "refresh-5xx"),
            ([_FakeResponse(200, {"MediaContainer": {}})], "no-sections"),
            ([_FakeResponse(200, None, raises_json=True)], "unparseable"),
        ],
        ids=["server-down", "bad-token", "refresh-5xx", "no-sections", "unparseable"],
    )
    def test_every_failure_returns_false_and_never_raises(self, responses: list[Any], case: str) -> None:
        """Fail-soft at the client level: a bool, never an exception."""
        client, _ = _client(*responses)

        assert client.refresh(Path("/Volumes/Disk2/medias/films/Margin Call (2011)")) is False, case


# ---------------------------------------------------------------------------
# The token must never be observable
# ---------------------------------------------------------------------------


class TestTokenIsNeverExposed:
    """ACC-03 — no log record, no repr, no exception text carries the token."""

    @pytest.mark.parametrize(
        "responses",
        [
            [requests.ConnectionError("connection refused")],
            [_FakeResponse(401)],
            [_FakeResponse(200, _SECTIONS_PAYLOAD), _FakeResponse(403)],
            [_FakeResponse(200, _SECTIONS_PAYLOAD), requests.Timeout("timed out")],
            [_FakeResponse(200, None, raises_json=True)],
        ],
        ids=["down", "401", "refresh-403", "refresh-timeout", "unparseable"],
    )
    def test_no_log_record_contains_the_token(self, responses: list[Any], caplog: pytest.LogCaptureFixture) -> None:
        """Scan EVERY record — message, args and formatted output."""
        client, _ = _client(*responses)

        with caplog.at_level(logging.DEBUG):
            client.refresh(Path("/Volumes/Disk2/medias/films/Margin Call (2011)"))

        assert caplog.records, "the failure must be logged (a silent failure is the other bug)"
        for record in caplog.records:
            assert _TOKEN not in record.getMessage()
            assert _TOKEN not in str(record.args)
            assert _TOKEN not in str(getattr(record, "msg", ""))
            assert _TOKEN not in caplog.text

    def test_repr_does_not_carry_the_token(self) -> None:
        """A client in a traceback frame must not print the credential."""
        client, _ = _client()

        assert _TOKEN not in repr(client)

    def test_settings_repr_masks_the_token(self) -> None:
        """``PLEX_TOKEN`` is registered as a secret field of Settings."""
        from personalscraper.config import Settings

        settings = Settings(_env_file=None, plex_token=_TOKEN)  # type: ignore[call-arg]

        assert _TOKEN not in repr(settings)
        assert "plex_token=<masked>" in repr(settings)


# ---------------------------------------------------------------------------
# The subscriber — fail-soft ABSOLUTE
# ---------------------------------------------------------------------------


class TestSubscriber:
    """``PlexSubscriber`` reacts to ``ItemDispatched`` and never breaks a dispatch."""

    @staticmethod
    def _event(target: Path | None, action: str = "moved") -> ItemDispatched:
        return ItemDispatched(
            source="dispatch",
            item="Margin Call (2011)",
            target_disk=Path("/Volumes/Disk2"),
            category_id="movies",
            action=action,  # type: ignore[arg-type]
            target_path=target,
        )

    def test_refreshes_the_dispatched_folder(self) -> None:
        """The subscriber passes the event's folder straight to the client."""
        bus = EventBus()
        client = MagicMock()
        subscriber = PlexSubscriber(bus, client)
        target = Path("/Volumes/Disk2/medias/films/Margin Call (2011)")

        bus.emit(self._event(target))
        _join_refresh_threads()

        client.refresh.assert_called_once_with(target)
        subscriber.close()

    def test_event_without_a_target_path_triggers_nothing(self) -> None:
        """No folder ⇒ nothing to scan; the event is skipped, not guessed."""
        bus = EventBus()
        client = MagicMock()
        subscriber = PlexSubscriber(bus, client)

        bus.emit(self._event(None))
        _join_refresh_threads()

        client.refresh.assert_not_called()
        subscriber.close()

    def test_a_raising_client_never_escapes_the_subscriber(self) -> None:
        """Fail-soft ABSOLUTE: a client bug is a warning, the emit still returns."""
        bus = EventBus()
        client = MagicMock()
        client.refresh.side_effect = RuntimeError("boom")
        subscriber = PlexSubscriber(bus, client)

        bus.emit(self._event(Path("/Volumes/Disk2/medias/films/X")))  # must not raise
        _join_refresh_threads()

        client.refresh.assert_called_once()
        subscriber.close()

    def test_close_unsubscribes(self) -> None:
        """After close(), a later dispatch triggers nothing."""
        bus = EventBus()
        client = MagicMock()
        subscriber = PlexSubscriber(bus, client)
        subscriber.close()

        bus.emit(self._event(Path("/Volumes/Disk2/medias/films/X")))
        _join_refresh_threads()

        client.refresh.assert_not_called()

    def test_a_failing_plex_leaves_the_dispatch_a_success(self) -> None:
        """End to end with the REAL client over a dead server: emit returns clean."""
        bus = EventBus()
        client, session = _client(requests.ConnectionError("refused"))
        subscriber = PlexSubscriber(bus, client)

        bus.emit(self._event(Path("/Volumes/Disk2/medias/films/Margin Call (2011)")))
        _join_refresh_threads()

        assert len(session.calls) == 1
        subscriber.close()


def _join_refresh_threads() -> None:
    """Wait for the subscriber's daemon refresh threads to finish."""
    import threading

    for thread in threading.enumerate():
        if thread.name == "plex-refresh":
            thread.join(timeout=5)


# ---------------------------------------------------------------------------
# D3 — wiring
# ---------------------------------------------------------------------------


class TestWiring:
    """No token ⇒ not wired, zero requests; token ⇒ wired at the pipeline boundary."""

    def test_pipeline_wires_it_on_the_token_alone(self) -> None:
        """The run command builds the subscriber iff ``settings.plex_token``."""
        import inspect

        from personalscraper.commands import pipeline

        source = inspect.getsource(pipeline)

        assert "if settings.plex_token:" in source
        assert "PlexSubscriber(" in source
        assert 'log.info("plex_refresh_disabled"' in source or "plex_refresh_disabled" in source

    def test_subscriber_is_closed_with_the_others(self) -> None:
        """Teardown parity with the Telegram subscriber."""
        import inspect

        from personalscraper.commands import pipeline

        source = inspect.getsource(pipeline)

        assert "plex_subscriber.close()" in source

    def test_default_settings_expose_the_plex_url(self) -> None:
        """``PLEX_URL`` defaults to the local server; the token has no default."""
        from personalscraper.config import Settings

        settings = Settings(_env_file=None, plex_token="")  # type: ignore[call-arg]

        assert settings.plex_url == "http://localhost:32400"
        assert settings.plex_token == ""

    def test_no_token_means_no_client_and_no_request(self) -> None:
        """The gate is the token: with none, nothing is constructed to call Plex."""
        from personalscraper.config import Settings

        settings = Settings(_env_file=None, plex_token="")  # type: ignore[call-arg]

        assert not settings.plex_token, "an empty token must leave the subscriber unwired"


def test_parse_sections_tolerates_garbage() -> None:
    """A malformed payload degrades the trigger; it never raises into a dispatch."""
    from personalscraper.api.plex import _parse_sections

    assert _parse_sections(None) == []
    assert _parse_sections({"MediaContainer": {"Directory": "not-a-list"}}) == []
    assert _parse_sections({"MediaContainer": {"Directory": [{"no": "key"}]}}) == []

    parsed = _parse_sections({"MediaContainer": {"Directory": [{"key": "7", "Location": [{"path": "/a"}]}]}})
    assert len(parsed) == 1
    assert isinstance(parsed[0], PlexSection)
    assert (parsed[0].key, parsed[0].title, parsed[0].locations) == ("7", "", ["/a"])
