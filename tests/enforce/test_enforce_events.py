"""Regression tests for enforce step structlog event emission.

Verifies bracket events (enforce_start / enforce_complete), ok counterparts
(enforce_structure_ok / enforce_coherence_ok), and enforce_sanitize_filename.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.enforce.coherence_checker import CoherenceResult
from personalscraper.enforce.file_sanitizer import SanitizeResult
from personalscraper.enforce.run import run_enforce
from personalscraper.enforce.structure_validator import StructureResult


def _has_event(caplog: pytest.LogCaptureFixture, event: str) -> bool:
    """Return True if *event* appears as a structlog event name in caplog."""
    for record in caplog.records:
        msg = record.msg
        if isinstance(msg, dict) and msg.get("event") == event:
            return True
    return False


def _get_event(caplog: pytest.LogCaptureFixture, event: str) -> dict | None:
    """Return the first record whose msg["event"] == *event*, or None."""
    for record in caplog.records:
        msg = record.msg
        if isinstance(msg, dict) and msg.get("event") == event:
            return msg
    return None


class TestEnforceBracketEvents:
    """enforce_start and enforce_complete bracket the step."""

    @patch("personalscraper.enforce.run.check_coherence", return_value=[])
    @patch("personalscraper.enforce.run.validate_structure", return_value=[])
    @patch("personalscraper.enforce.run.sanitize_files", return_value=[])
    def test_emits_start_and_complete(
        self,
        mock_sanitize: MagicMock,
        mock_structure: MagicMock,
        mock_coherence: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """enforce_start and enforce_complete appear when all sub-components return empty."""
        run_enforce(MagicMock(), MagicMock(), dry_run=True, event_bus=EventBus())

        assert _has_event(caplog, "enforce_start"), "enforce_start not found in caplog"
        assert _has_event(caplog, "enforce_complete"), "enforce_complete not found in caplog"

        start_event = _get_event(caplog, "enforce_start")
        assert start_event is not None
        assert start_event["dry_run"] is True

        complete_event = _get_event(caplog, "enforce_complete")
        assert complete_event is not None
        assert complete_event["success"] == 0
        assert complete_event["skip"] == 0
        assert complete_event["error"] == 0
        assert complete_event["warnings"] == 0

        # Verify order: start before complete
        start_idx = next(
            i for i, r in enumerate(caplog.records) if isinstance(r.msg, dict) and r.msg.get("event") == "enforce_start"
        )
        complete_idx = next(
            i
            for i, r in enumerate(caplog.records)
            if isinstance(r.msg, dict) and r.msg.get("event") == "enforce_complete"
        )
        assert start_idx < complete_idx, "enforce_start must appear before enforce_complete"


class TestEnforceOkEvents:
    """Ok counterparts for structure and coherence."""

    @patch("personalscraper.enforce.run.check_coherence")
    @patch("personalscraper.enforce.run.validate_structure")
    @patch("personalscraper.enforce.run.sanitize_files", return_value=[])
    def test_emits_ok_events_for_validated_items(
        self,
        mock_sanitize: MagicMock,
        mock_structure: MagicMock,
        mock_coherence: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """enforce_structure_ok and enforce_coherence_ok for clean items."""
        fake_path = Path("/tmp/staging/001-MOVIES/Film (2025)")
        mock_structure.return_value = [
            StructureResult(path=fake_path, media_type="movie", action="validated"),
        ]
        mock_coherence.return_value = [
            CoherenceResult(path=fake_path, checks=["ids", "genre"], warnings=[]),
        ]

        run_enforce(MagicMock(), MagicMock(), dry_run=True, event_bus=EventBus())

        assert _has_event(caplog, "enforce_structure_ok"), "enforce_structure_ok not found"
        assert _has_event(caplog, "enforce_coherence_ok"), "enforce_coherence_ok not found"

        structure_ok = _get_event(caplog, "enforce_structure_ok")
        assert structure_ok is not None
        assert structure_ok["item"] == "Film (2025)"

        coherence_ok = _get_event(caplog, "enforce_coherence_ok")
        assert coherence_ok is not None
        assert coherence_ok["item"] == "Film (2025)"


class TestEnforceCompleteStats:
    """enforce_complete fields match StepReport."""

    @patch("personalscraper.enforce.run.check_coherence", return_value=[])
    @patch("personalscraper.enforce.run.validate_structure", return_value=[])
    @patch("personalscraper.enforce.run.sanitize_files")
    def test_complete_stats_match_step_report(
        self,
        mock_sanitize: MagicMock,
        mock_structure: MagicMock,
        mock_coherence: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """enforce_complete success/skip/error match the returned StepReport."""
        fake_path = Path("/tmp/staging/001-MOVIES/Film (2025)")
        # 2 successes (renamed files), 1 skip
        mock_sanitize.return_value = [
            SanitizeResult(path=fake_path, action="renamed", old_name="bad:name.mkv", new_name="bad_name.mkv"),
            SanitizeResult(path=fake_path, action="renamed", old_name="bad:name2.mkv", new_name="bad_name2.mkv"),
            SanitizeResult(path=fake_path, action="skipped", old_name="clean.mkv"),
        ]

        report = run_enforce(MagicMock(), MagicMock(), dry_run=True, event_bus=EventBus())

        complete_event = _get_event(caplog, "enforce_complete")
        assert complete_event is not None
        assert complete_event["success"] == report.success_count
        assert complete_event["skip"] == report.skip_count
        assert complete_event["error"] == report.error_count
        assert complete_event["warnings"] == len(report.warnings)


class TestEnforceSanitizeFilename:
    """enforce_sanitize_filename emitted for rename/duplicate actions."""

    @patch("personalscraper.enforce.run.check_coherence", return_value=[])
    @patch("personalscraper.enforce.run.validate_structure", return_value=[])
    @patch("personalscraper.enforce.run.sanitize_files")
    def test_rename_action_emits_sanitize_filename(
        self,
        mock_sanitize: MagicMock,
        mock_structure: MagicMock,
        mock_coherence: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """'renamed' action emits enforce_sanitize_filename alongside enforce_sanitize_action."""
        fake_path = Path("/tmp/staging/001-MOVIES/Film (2025)")
        mock_sanitize.return_value = [
            SanitizeResult(path=fake_path, action="renamed", old_name="bad:name.mkv", new_name="bad_name.mkv"),
        ]

        run_enforce(MagicMock(), MagicMock(), dry_run=True, event_bus=EventBus())

        assert _has_event(caplog, "enforce_sanitize_action"), "enforce_sanitize_action should still be emitted"
        assert _has_event(caplog, "enforce_sanitize_filename"), "enforce_sanitize_filename not found for renamed action"

        event = _get_event(caplog, "enforce_sanitize_filename")
        assert event is not None
        assert event["action"] == "renamed"
        assert event["old_name"] == "bad:name.mkv"
        assert event["new_name"] == "bad_name.mkv"

    @patch("personalscraper.enforce.run.check_coherence", return_value=[])
    @patch("personalscraper.enforce.run.validate_structure", return_value=[])
    @patch("personalscraper.enforce.run.sanitize_files")
    def test_deleted_ds_store_does_not_emit_sanitize_filename(
        self,
        mock_sanitize: MagicMock,
        mock_structure: MagicMock,
        mock_coherence: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """'deleted_ds_store' action does NOT emit enforce_sanitize_filename."""
        fake_path = Path("/tmp/staging/001-MOVIES/Film (2025)")
        mock_sanitize.return_value = [
            SanitizeResult(path=fake_path, action="deleted_ds_store", old_name=".DS_Store"),
        ]

        run_enforce(MagicMock(), MagicMock(), dry_run=True, event_bus=EventBus())

        assert _has_event(caplog, "enforce_sanitize_action"), "enforce_sanitize_action should be emitted"
        assert not _has_event(caplog, "enforce_sanitize_filename"), (
            "enforce_sanitize_filename should NOT be emitted for .DS_Store"
        )
