"""Tests for verify progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.pipeline_observer import CollectorObserver
from personalscraper.verify.run import run_verify
from personalscraper.verify.verifier import VerifyResult


class TestVerifyProgress:
    """Verify run_verify emits StepEvents per DESIGN §9 (started → ok / blocked)."""

    def test_fast_skip_emits_no_events(self) -> None:
        """When no items exist, verify returns early without emitting events."""
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        collector = CollectorObserver()

        with patch("personalscraper.verify.run._has_items_to_verify", return_value=False):
            report, dispatchable = run_verify(settings, config, dry_run=True, observers=(collector,))

        assert report.name == "verify"
        assert dispatchable == []
        assert collector.progress == []

    def test_emits_ok_and_blocked_events(self) -> None:
        """run_verify emits started → ok for valid/fixed and started → blocked for blocked."""
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        collector = CollectorObserver()

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
            run_verify(settings, config, dry_run=True, observers=(collector,))

        statuses = [e.status for e in collector.progress]
        # Each item produces started + (ok|blocked). Order: started, ok, started, blocked.
        assert statuses.count("started") == 2
        assert "ok" in statuses
        assert "blocked" in statuses

        blocked_events = [e for e in collector.progress if e.status == "blocked"]
        assert blocked_events[0].details["errors"] == ["missing nfo"]
