"""Tests for verify progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.verify.run import run_verify


class TestVerifyProgress:
    """Verify run_verify accepts and uses observers."""

    def test_accepts_observers(self) -> None:
        """run_verify accepts observers without error."""
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")

        with patch("personalscraper.verify.run._has_items_to_verify", return_value=False):
            report, dispatchable = run_verify(settings, config, dry_run=True, observers=())
        assert report.name == "verify"
        assert dispatchable == []
