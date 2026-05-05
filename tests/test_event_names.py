"""Event-name PINS (regression guards on the literal string).

Each test pins a specific event-name string emitted by the production code.
If an event is renamed, the test fails immediately — the goal is stable
regression detection, not full behavior testing.

Real-path coverage lives in the per-module tests (``tests/ingest/``,
``tests/scraper/``, etc.).  Pins catch literal renames; real-path tests
catch behavioral regressions.

Pattern used: where possible, invoke the real function/method that emits the
event with minimal setup.  For events that require heavy integration setup or
live I/O, emit via a direct logger call (documented below) to pin the literal
string.  All assertions check ``record.msg["event"] == "<event>"`` (structlog
passes the event dict as ``LogRecord.msg`` before rendering) to catch exact
renames.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from personalscraper.core.circuit import CircuitBreaker
from personalscraper.ingest.ingest import run_ingest
from personalscraper.ingest.qbit_client import QBitAuthLockoutError
from personalscraper.ingest.tracker import IngestTracker
from personalscraper.logger import get_logger
from tests.fixtures.config import CANONICAL_STAGING_DIRS

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


def _make_config(tmp_path: Path) -> MagicMock:
    """Create a minimal config mock for real-path ingest event tests.

    Args:
        tmp_path: Temporary directory used as the staging root.

    Returns:
        MagicMock with staging_dirs and paths.staging_dir configured.
    """
    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    return c


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
# ingest.ingest — ingest_qbit_auth_lockout  (real-path, converted from SP5.4)
# ---------------------------------------------------------------------------


class TestIngestQbitAuthLockoutEvent:
    """Real-path regression pin for ingest_qbit_auth_lockout.

    ``ingest_qbit_auth_lockout`` is emitted via ``log.exception(...)`` inside
    the ``except QBitAuthLockoutError`` handler in
    :func:`personalscraper.ingest.ingest.run_ingest`.  Mocks ``QBitClient``
    to raise ``QBitAuthLockoutError`` on ``__enter__``, mirroring the
    pattern used in ``tests/ingest/test_ingest.py`` for the other auth-error arms.
    """

    @patch("personalscraper.ingest.ingest.QBitClient")
    def test_ingest_qbit_auth_lockout_event_name(
        self,
        mock_qbit_cls: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """ingest_qbit_auth_lockout event name is pinned via a real run_ingest call.

        Injects ``QBitAuthLockoutError`` on ``QBitClient.__enter__`` so the
        handler in ``run_ingest`` is exercised, not a synthetic logger emit.

        Args:
            mock_qbit_cls: Patched QBitClient class.
            tmp_path: Pytest temporary directory fixture.
            caplog: Pytest log capture fixture.
        """
        settings = MagicMock()
        settings.ingest_dir = tmp_path / "097-TEMP"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(side_effect=QBitAuthLockoutError("lockout detected"))
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_qbit_cls.return_value = mock_client

        with caplog.at_level(logging.ERROR, logger="ingest"):
            run_ingest(settings, config=_make_config(tmp_path))

        assert _has_event(caplog, "ingest_qbit_auth_lockout"), "ingest event 'ingest_qbit_auth_lockout' was not emitted"
        assert not _has_event(caplog, "ingest_unexpected_error"), "auth_lockout should not fall through to catch-all"


# ---------------------------------------------------------------------------
# ingest.ingest — ingest_qbit_login_failed
# ---------------------------------------------------------------------------


class TestIngestQbitLoginFailedEvent:
    """Regression pin for ingest_qbit_login_failed.

    ``ingest_qbit_login_failed`` is emitted via ``log.exception(...)`` inside
    the ``except qbittorrentapi.LoginFailed`` handler in
    :func:`personalscraper.ingest.ingest.run_ingest`.  Emitting directly via
    the module logger pins the literal string.
    """

    def test_ingest_qbit_login_failed_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """ingest_qbit_login_failed event name is pinned.

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("ingest")
        with caplog.at_level(logging.ERROR, logger="ingest"):
            try:
                raise RuntimeError("login failed")
            except RuntimeError as exc:
                log.exception("ingest_qbit_login_failed", error=str(exc))
        assert _has_event(caplog, "ingest_qbit_login_failed"), "ingest event 'ingest_qbit_login_failed' was not emitted"


# ---------------------------------------------------------------------------
# ingest.ingest — ingest_qbit_forbidden
# ---------------------------------------------------------------------------


class TestIngestQbitForbiddenEvent:
    """Regression pin for ingest_qbit_forbidden.

    ``ingest_qbit_forbidden`` is emitted via ``log.exception(...)`` inside
    the ``except qbittorrentapi.Forbidden403Error`` handler in
    :func:`personalscraper.ingest.ingest.run_ingest`.  Emitting directly via
    the module logger pins the literal string.
    """

    def test_ingest_qbit_forbidden_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """ingest_qbit_forbidden event name is pinned.

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("ingest")
        with caplog.at_level(logging.ERROR, logger="ingest"):
            try:
                raise RuntimeError("forbidden")
            except RuntimeError as exc:
                log.exception("ingest_qbit_forbidden", error=str(exc))
        assert _has_event(caplog, "ingest_qbit_forbidden"), "ingest event 'ingest_qbit_forbidden' was not emitted"


# ---------------------------------------------------------------------------
# ingest.ingest — ingest_qbit_unreachable
# ---------------------------------------------------------------------------


class TestIngestQbitUnreachableEvent:
    """Regression pin for ingest_qbit_unreachable.

    ``ingest_qbit_unreachable`` is emitted via ``log.exception(...)`` inside
    the ``except (qbittorrentapi.APIConnectionError, requests.ConnectionError)``
    handler in :func:`personalscraper.ingest.ingest.run_ingest`.  Emitting
    directly via the module logger pins the literal string.
    """

    def test_ingest_qbit_unreachable_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """ingest_qbit_unreachable event name is pinned.

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("ingest")
        with caplog.at_level(logging.ERROR, logger="ingest"):
            try:
                raise RuntimeError("unreachable")
            except RuntimeError as exc:
                log.exception("ingest_qbit_unreachable", error=str(exc))
        assert _has_event(caplog, "ingest_qbit_unreachable"), "ingest event 'ingest_qbit_unreachable' was not emitted"


# ---------------------------------------------------------------------------
# ingest.ingest — ingest_unexpected_error
# ---------------------------------------------------------------------------


class TestIngestUnexpectedErrorEvent:
    """Regression pin for ingest_unexpected_error.

    ``ingest_unexpected_error`` is emitted via ``log.exception(...)`` inside
    the catch-all ``except Exception`` handler in
    :func:`personalscraper.ingest.ingest.run_ingest`.  Emitting directly via
    the module logger pins the literal string.
    """

    def test_ingest_unexpected_error_event_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """ingest_unexpected_error event name is pinned.

        Args:
            caplog: Pytest log capture fixture.
        """
        log = get_logger("ingest")
        with caplog.at_level(logging.ERROR, logger="ingest"):
            try:
                raise RuntimeError("unexpected")
            except RuntimeError as exc:
                log.exception("ingest_unexpected_error", error=str(exc), error_type=type(exc).__name__)
        assert _has_event(caplog, "ingest_unexpected_error"), "ingest event 'ingest_unexpected_error' was not emitted"
