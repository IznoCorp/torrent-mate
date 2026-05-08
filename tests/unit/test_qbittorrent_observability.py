"""Observability pins for api/torrent/qbittorrent.py.

These tests guard the log levels chosen in PR #19 (commit 4b3eaff —
"transport hardening + qbit observability"). Without explicit log-level
assertions, a future maintainer "silencing PM2 noise" could lower the
events back to ``debug`` and the regression would only surface on a real
production incident.

Pinned events:
- ``qbit_logout_failed``        → WARNING (logout on a long-lived daemon
  is always abnormal; debug would be silently dropped by prod log tiers).
- ``qbit_lockout_write_failed`` → ERROR with an operator-actionable hint
  field (lockout file is a security control — failure must be loud).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import qbittorrentapi

from personalscraper.api.torrent.qbittorrent import QBitClient, _set_lockout


def _records_for_event(records: list[logging.LogRecord], event: str) -> list[logging.LogRecord]:
    """Return records whose ``msg`` (structlog key) matches ``event``."""
    return [r for r in records if r.msg == event or event in r.getMessage()]


class TestQBitLogoutFailedLevel:
    """qbit_logout_failed must be emitted at WARNING (not debug)."""

    def test_logout_apiconnectionerror_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """APIConnectionError on logout → WARNING with the event name."""
        client = QBitClient("localhost", 8080, "admin", "pw")
        client._client = MagicMock()
        client._client.auth_log_out.side_effect = qbittorrentapi.APIConnectionError("boom")

        caplog.set_level(logging.WARNING, logger="api.torrent.qbittorrent")
        client.logout()

        records = _records_for_event(caplog.records, "qbit_logout_failed")
        assert records, "qbit_logout_failed must be emitted on APIConnectionError."
        assert any(r.levelno == logging.WARNING for r in records), (
            "qbit_logout_failed must be WARNING — DO NOT lower to debug. "
            "Silent logout failures mask network drops and admin-killed daemons."
        )

    def test_logout_oserror_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """OSError on logout (e.g. socket dropped) → WARNING."""
        client = QBitClient("localhost", 8080, "admin", "pw")
        client._client = MagicMock()
        client._client.auth_log_out.side_effect = OSError("socket closed")

        caplog.set_level(logging.WARNING, logger="api.torrent.qbittorrent")
        client.logout()

        records = _records_for_event(caplog.records, "qbit_logout_failed")
        assert records, "qbit_logout_failed must be emitted on OSError."
        assert any(r.levelno == logging.WARNING for r in records)


class TestQBitLockoutWriteFailedLevel:
    """qbit_lockout_write_failed must be ERROR with an actionable hint."""

    @patch("personalscraper.api.torrent.qbittorrent._LOCKOUT_FILE")
    def test_lockout_write_failure_logs_error_with_hint(
        self,
        mock_lockout: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """OSError writing the lockout file → ERROR with the operator hint."""
        mock_lockout.parent.mkdir.return_value = None
        mock_lockout.write_text.side_effect = OSError("permission denied")
        # Used in the formatted hint string.
        mock_lockout.parent = MagicMock()
        mock_lockout.parent.__str__ = lambda self: "/fake/lockdir"  # type: ignore[assignment]

        caplog.set_level(logging.ERROR, logger="api.torrent.qbittorrent")
        _set_lockout("test-reason")

        records = _records_for_event(caplog.records, "qbit_lockout_write_failed")
        assert records, "qbit_lockout_write_failed must be emitted on write failure."
        record = records[0]
        assert record.levelno == logging.ERROR, (
            "qbit_lockout_write_failed must be ERROR — lockout-file write failure "
            "is a security-control regression and must be loud, not informational."
        )

        # The actionable hint must be present somewhere on the record (structlog
        # routes kwargs through the record's ``__dict__``; depending on the
        # configured renderer, ``hint`` may be on the record directly or merged
        # into the formatted message). Accept either path.
        rendered_kwargs = " ".join(f"{k}={v}" for k, v in vars(record).items() if k not in ("args", "msg"))
        full = record.getMessage() + " " + rendered_kwargs
        assert "Cannot enforce auth lockout" in full, (
            "qbit_lockout_write_failed must include the operator-actionable hint "
            "'Cannot enforce auth lockout — credentials may keep retrying.'"
        )
