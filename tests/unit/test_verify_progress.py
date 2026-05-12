"""Tests for verify progress events — migrated to EventBus + ``ItemProgressed``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.verify.run import run_verify
from personalscraper.verify.verifier import VerifyResult
from tests.fixtures.event_bus import CollectingSubscriber


class TestVerifyProgress:
    """Verify run_verify emits ``ItemProgressed`` events per DESIGN §9."""

    def test_fast_skip_emits_no_events(self) -> None:
        """When no items exist, verify returns early without emitting events."""
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        with patch("personalscraper.verify.run._has_items_to_verify", return_value=False):
            report, dispatchable = run_verify(MagicMock(), config, dry_run=True, event_bus=bus)

        assert report.name == "verify"
        assert dispatchable == []
        assert collector.received == []

    def test_emits_ok_and_blocked_events(self) -> None:
        """run_verify emits started → ok for valid/fixed and started → blocked for blocked."""
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        valid_result = VerifyResult(
            media_path=Path("/tmp/staging/Movies/OK"),
            media_type="movie",
            status="valid",
            category="movies",
            errors=[],
            fixes_applied=[],
        )
        blocked_result = VerifyResult(
            media_path=Path("/tmp/staging/Movies/BAD"),
            media_type="movie",
            status="blocked",
            category=None,
            errors=["missing nfo"],
            fixes_applied=[],
        )

        mock_verifier = MagicMock()
        mock_verifier.verify_all_movies.return_value = [valid_result, blocked_result]
        mock_verifier.verify_all_tvshows.return_value = []

        with (
            patch("personalscraper.verify.run._has_items_to_verify", return_value=True),
            patch("personalscraper.verify.run.Verifier", return_value=mock_verifier),
            patch("personalscraper.verify.run.find_by_file_type"),
            patch("personalscraper.verify.run.folder_name", side_effect=lambda _: "movies"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            run_verify(MagicMock(), config, dry_run=True, event_bus=bus)

        statuses = [e.status for e in collector.received]
        assert statuses.count("started") == 2
        assert "ok" in statuses
        assert "blocked" in statuses

        blocked_events = [e for e in collector.received if e.status == "blocked"]
        assert blocked_events[0].details["errors"] == ["missing nfo"]
