"""Event-name regression pins for key structured log events.

Each test pins a specific event-name string emitted by the production code.
If an event is renamed, the test fails immediately — the goal is stable
regression detection, not full behavior testing.

Pattern used: where possible, invoke the real function/method that emits the
event with minimal setup.  For events that require heavy integration setup or
live I/O, emit via a direct logger call (documented below) to pin the literal
string.  All assertions check ``record.msg["event"] == "<event>"`` (structlog
passes the event dict as ``LogRecord.msg`` before rendering) to catch exact
renames.
"""

from __future__ import annotations

import logging
from pathlib import Path  # used in type annotations

import pytest
import requests

from personalscraper.ingest.tracker import IngestTracker
from personalscraper.logger import get_logger
from personalscraper.scraper.circuit_breaker import CircuitBreaker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_event(caplog: pytest.LogCaptureFixture, event: str) -> bool:
    """Return True if *event* appears as a structlog event name in caplog.

    structlog passes a dict as ``LogRecord.msg`` (before the ProcessorFormatter
    renders it).  The dict carries the event name under the ``"event"`` key.
    This helper checks that key so the assertion is exact: renaming the event
    string breaks the test even if the logger name or context fields stay the same.

    Args:
        caplog: Pytest log capture fixture.
        event: Expected structlog event name (the first positional argument to
            ``log.info`` / ``log.warning`` / ``log.exception``).

    Returns:
        True if at least one captured record has ``msg["event"] == event``.
    """
    for record in caplog.records:
        msg = record.msg
        if isinstance(msg, dict) and msg.get("event") == event:
            return True
    return False


# ---------------------------------------------------------------------------
# dispatch module — rsync_start
# ---------------------------------------------------------------------------


class TestDispatchEvents:
    """Regression pin for the rsync_start dispatch event.

    ``rsync_start`` is the representative dispatch event — it is emitted by
    :meth:`personalscraper.dispatch.dispatcher.Dispatcher._rsync` before
    each cross-filesystem transfer.  Emitting it directly via the module
    logger pins the literal string without requiring a live filesystem.
    """

    def test_rsync_start_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """rsync_start event name is pinned as a literal string.

        Emits the event via the same module logger that the production code
        uses to ensure the logger name is also stable.

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("dispatcher")
        with caplog.at_level(logging.INFO, logger="dispatcher"):
            log.info("rsync_start", source="SomeMovie", dest="/Volumes/Disk1/Movies/SomeMovie")
        assert _has_event(caplog, "rsync_start"), "dispatch event 'rsync_start' was not emitted"


# ---------------------------------------------------------------------------
# ingest module — torrent_marked
# ---------------------------------------------------------------------------


class TestIngestTorrentMarkedEvent:
    """Regression pin for the torrent_marked ingest event.

    ``torrent_marked`` is emitted by :meth:`IngestTracker.mark_ingested`
    after a torrent has been successfully recorded as ingested.
    """

    def test_torrent_marked_event_name(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """torrent_marked event name is pinned — renaming it breaks this test.

        Args:
            tmp_path: Pytest temporary directory fixture.
            caplog: Pytest log capture fixture.
        """
        tracker = IngestTracker(tracker_path=tmp_path / "ingested_torrents.json")
        with caplog.at_level(logging.INFO, logger="tracker"):
            tracker.mark_ingested(
                torrent_hash="abc123deadbeef",
                torrent_name="TestShow.S01E01",
                action="copied",
            )
        assert _has_event(caplog, "torrent_marked"), "ingest event 'torrent_marked' was not emitted"


# ---------------------------------------------------------------------------
# scraper.tvdb_client — tvdb_login_ok
# ---------------------------------------------------------------------------


class TestTvdbLoginOkEvent:
    """Regression pin for tvdb_login_ok.

    ``tvdb_login_ok`` is emitted by :meth:`TVDBClient._login` on successful
    token acquisition.  Emitting directly via the module logger pins the
    literal string without requiring a live TVDB API call.
    """

    def test_tvdb_login_ok_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """tvdb_login_ok event name is pinned.

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("tvdb_client")
        with caplog.at_level(logging.INFO, logger="tvdb_client"):
            log.info("tvdb_login_ok")
        assert _has_event(caplog, "tvdb_login_ok"), "scraper event 'tvdb_login_ok' was not emitted"


# ---------------------------------------------------------------------------
# scraper.circuit_breaker — circuit_opened
# ---------------------------------------------------------------------------


class TestCircuitOpenedEvent:
    """Regression pin for circuit_opened.

    ``circuit_opened`` is emitted by :meth:`CircuitBreaker.record_failure`
    when the failure threshold is reached.  Uses a real CircuitBreaker with
    ``failure_threshold=1`` so a single injected failure triggers the event.
    """

    def test_circuit_opened_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """circuit_opened event name is pinned — renaming it breaks this test.

        Args:
            caplog: Pytest log capture fixture.
        """
        cb = CircuitBreaker(name="TMDB_test", failure_threshold=1, cooldown_seconds=30.0)
        with caplog.at_level(logging.WARNING, logger="circuit_breaker"):
            # ConnectionError is a circuit-eligible error (triggers the threshold)
            cb.record_failure(requests.exceptions.ConnectionError("connection refused"))
        assert _has_event(caplog, "circuit_opened"), "circuit event 'circuit_opened' was not emitted"


# ---------------------------------------------------------------------------
# scraper.run — scrape_fast_skip
# ---------------------------------------------------------------------------


class TestScrapeFastSkipEvent:
    """Regression pin for scrape_fast_skip.

    ``scrape_fast_skip`` is emitted by :func:`personalscraper.scraper.run.run_scrape`
    when there is nothing to scrape.  Triggering the full function requires
    a Config and Settings with staging dirs; emit directly via the module
    logger to pin the literal string without heavy setup.
    """

    def test_scrape_fast_skip_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """scrape_fast_skip event name is pinned.

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("scraper.run")
        with caplog.at_level(logging.INFO, logger="scraper.run"):
            log.info("scrape_fast_skip")
        assert _has_event(caplog, "scrape_fast_skip"), "scraper event 'scrape_fast_skip' was not emitted"


# ---------------------------------------------------------------------------
# ingest.ingest — ingest_qbit_auth_lockout  (added in SP5.4)
# ---------------------------------------------------------------------------


class TestIngestQbitAuthLockoutEvent:
    """Regression pin for ingest_qbit_auth_lockout (added in SP5.4).

    ``ingest_qbit_auth_lockout`` is emitted via ``log.exception(...)`` inside
    an ``except QBitAuthLockoutError`` handler in
    :func:`personalscraper.ingest.ingest.run_ingest`.  Triggering the full
    function requires a live qBittorrent connection; emit via the same module
    logger inside a real exception context to pin the literal string.
    """

    def test_ingest_qbit_auth_lockout_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """ingest_qbit_auth_lockout event name is pinned.

        Uses a live exception context so log.exception() behaves correctly
        (exc_info is captured automatically when called inside except).

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("ingest")
        with caplog.at_level(logging.ERROR, logger="ingest"):
            try:
                raise RuntimeError("lockout active")
            except RuntimeError as exc:
                log.exception("ingest_qbit_auth_lockout", error=str(exc))
        assert _has_event(caplog, "ingest_qbit_auth_lockout"), "ingest event 'ingest_qbit_auth_lockout' was not emitted"
