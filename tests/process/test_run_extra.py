"""Additional coverage tests for ``personalscraper.process.run``.

Targets these residual gaps:

* Per-step error isolation in ``run_process`` (clean / scrape / cleanup
  fatal exceptions converted to error reports).
* ``_revert_unmatched_recleans`` filesystem branches:
    - ``category_dir.exists()`` False short-circuit
    - Clean-name no longer present (already moved)
    - Original name reappeared (revert target conflict)
    - Dry-run logging path
    - OSError on rename
* ``run_clean`` propagating dedup failure counts.
* ``run_process`` invoking ``_revert_unmatched_recleans`` when both
  ``clean_report.renames`` and ``scrape_report.unmatched_paths`` are present.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.process.run import _revert_unmatched_recleans, run_clean, run_process
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_settings() -> MagicMock:
    """Return a minimal mocked Settings for orchestrator paths."""
    return MagicMock()


def _make_config(tmp_path: Path) -> MagicMock:
    """Return a minimal mocked Config rooted at ``tmp_path``."""
    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    return c


# ---------------------------------------------------------------------------
# _revert_unmatched_recleans
# ---------------------------------------------------------------------------


class TestRevertUnmatchedRecleansBranches:
    """Branch coverage for ``_revert_unmatched_recleans``."""

    def test_skip_when_category_dir_missing(self, tmp_path: Path) -> None:
        """A non-existent category dir is silently skipped (continue branch)."""
        missing = tmp_path / "no_such_dir"
        reverted = _revert_unmatched_recleans(
            category_dirs=[missing],
            unmatched_names={"X"},
            rename_map={"X": "Y"},
        )
        assert reverted == 0

    def test_skip_when_new_name_not_in_unmatched(self, tmp_path: Path) -> None:
        """A renamed folder absent from unmatched_names is left untouched."""
        category = tmp_path / "001-MOVIES"
        category.mkdir()
        (category / "Clean Name (2024)").mkdir()
        reverted = _revert_unmatched_recleans(
            category_dirs=[category],
            unmatched_names={"Other"},
            rename_map={"Clean Name (2024)": "Original.Torrent.Name"},
        )
        assert reverted == 0
        assert (category / "Clean Name (2024)").exists()

    def test_skip_when_clean_name_no_longer_present(self, tmp_path: Path) -> None:
        """Folder absent from disk (already moved) is silently skipped."""
        category = tmp_path / "001-MOVIES"
        category.mkdir()
        # Note: ``Clean Name (2024)`` does NOT exist on disk.
        reverted = _revert_unmatched_recleans(
            category_dirs=[category],
            unmatched_names={"Clean Name (2024)"},
            rename_map={"Clean Name (2024)": "Original.Torrent.Name"},
        )
        assert reverted == 0

    def test_dry_run_logs_without_renaming(self, tmp_path: Path) -> None:
        """Dry-run reports the would-be revert without touching disk."""
        category = tmp_path / "002-TVSHOWS"
        category.mkdir()
        clean = category / "Clean Show (2024)"
        clean.mkdir()
        reverted = _revert_unmatched_recleans(
            category_dirs=[category],
            unmatched_names={"Clean Show (2024)"},
            rename_map={"Clean Show (2024)": "Original.Torrent.Name"},
            dry_run=True,
        )
        assert reverted == 1
        # Dry-run keeps the clean-named directory in place.
        assert clean.exists()
        assert not (category / "Original.Torrent.Name").exists()

    def test_skip_when_original_already_exists(self, tmp_path: Path) -> None:
        """Revert target conflict (original name reappeared) → skip without rename."""
        category = tmp_path / "001-MOVIES"
        category.mkdir()
        clean = category / "Clean Title (2024)"
        clean.mkdir()
        original = category / "Clean.Title.2024.WEB"
        original.mkdir()  # conflict — already present
        reverted = _revert_unmatched_recleans(
            category_dirs=[category],
            unmatched_names={"Clean Title (2024)"},
            rename_map={"Clean Title (2024)": "Clean.Title.2024.WEB"},
        )
        assert reverted == 0
        # Both directories must remain (no destructive action).
        assert clean.exists()
        assert original.exists()

    def test_oserror_on_rename_is_logged_and_swallowed(self, tmp_path: Path) -> None:
        """An OSError while renaming a folder is caught (no propagation)."""
        category = tmp_path / "002-TVSHOWS"
        category.mkdir()
        clean = category / "Clean Show (2024)"
        clean.mkdir()

        with patch("pathlib.Path.rename", side_effect=OSError("EACCES")):
            reverted = _revert_unmatched_recleans(
                category_dirs=[category],
                unmatched_names={"Clean Show (2024)"},
                rename_map={"Clean Show (2024)": "Original.Name"},
            )
        # No revert succeeded, but the function did not propagate the OSError.
        assert reverted == 0


# ---------------------------------------------------------------------------
# run_clean
# ---------------------------------------------------------------------------


class TestRunCleanDedupFailures:
    """Cover the dedup_failed bookkeeping branch in ``run_clean``."""

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    @patch("personalscraper.process.dedup.dedup_folders")
    @patch("personalscraper.process.reclean.reclean_folders")
    @patch("personalscraper.process.reclean._has_polluted_folders", return_value=True)
    def test_dedup_failed_increments_error_count(
        self,
        _mock_polluted,
        mock_reclean,
        mock_dedup,
        _mock_cleanup,
        tmp_path: Path,
    ) -> None:
        """Failed dedup merges land in error_count and a warning entry."""
        mock_reclean.return_value = StepReport(name="reclean")
        mock_dedup.return_value = (0, 3)  # 0 merged, 3 failed
        report = run_clean(_make_settings(), _make_config(tmp_path), event_bus=EventBus())

        # 3 failures per category × 2 categories.
        assert report.error_count == 3 + 3
        # At least one warning per category.
        assert sum("Dedup" in w for w in report.warnings) >= 2


# ---------------------------------------------------------------------------
# run_process — error isolation + revert wiring
# ---------------------------------------------------------------------------


class TestRunProcessErrorIsolation:
    """Each sub-step exception is converted into a StepReport with error_count=1."""

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.run.run_clean", side_effect=RuntimeError("clean boom"))
    def test_clean_step_exception_converted_to_error_report(
        self,
        _mock_clean,
        mock_scrape,
        mock_cleanup,
        tmp_path: Path,
    ) -> None:
        """A fatal exception in run_clean does not stop scrape/cleanup."""
        mock_scrape.return_value = StepReport(name="scrape")
        mock_cleanup.return_value = StepReport(name="cleanup")

        clean, scrape, cleanup = run_process(_make_settings(), config=_make_config(tmp_path), event_bus=EventBus())

        assert clean.name == "clean"
        assert clean.error_count == 1
        assert any("clean boom" in d for d in clean.details)
        assert scrape.name == "scrape"
        assert cleanup.name == "cleanup"

    @patch("personalscraper.process.run.run_cleanup")
    @patch("personalscraper.scraper.run.run_scrape", side_effect=RuntimeError("scrape boom"))
    @patch("personalscraper.process.run.run_clean")
    def test_scrape_step_exception_converted_to_error_report(
        self,
        mock_clean,
        _mock_scrape,
        mock_cleanup,
        tmp_path: Path,
    ) -> None:
        """A fatal exception in run_scrape does not stop cleanup."""
        mock_clean.return_value = StepReport(name="clean")
        mock_cleanup.return_value = StepReport(name="cleanup")

        clean, scrape, cleanup = run_process(_make_settings(), config=_make_config(tmp_path), event_bus=EventBus())

        assert scrape.name == "scrape"
        assert scrape.error_count == 1
        assert any("scrape boom" in d for d in scrape.details)
        assert cleanup.name == "cleanup"

    @patch("personalscraper.process.run.run_cleanup", side_effect=RuntimeError("cleanup boom"))
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.run.run_clean")
    def test_cleanup_step_exception_converted_to_error_report(
        self,
        mock_clean,
        mock_scrape,
        _mock_cleanup,
        tmp_path: Path,
    ) -> None:
        """A fatal exception in run_cleanup is reported as a synthetic error."""
        mock_clean.return_value = StepReport(name="clean")
        mock_scrape.return_value = StepReport(name="scrape")

        _clean, _scrape, cleanup = run_process(_make_settings(), config=_make_config(tmp_path), event_bus=EventBus())

        assert cleanup.name == "cleanup"
        assert cleanup.error_count == 1
        assert any("cleanup boom" in d for d in cleanup.details)


class TestRunProcessRevertWiring:
    """Cover the revert-unmatched-recleans wiring inside run_process."""

    @patch("personalscraper.process.run._revert_unmatched_recleans")
    @patch("personalscraper.process.run.run_cleanup")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.run.run_clean")
    def test_revert_invoked_when_renames_and_unmatched_present(
        self,
        mock_clean,
        mock_scrape,
        mock_cleanup,
        mock_revert,
        tmp_path: Path,
    ) -> None:
        """When clean produces renames and scrape produces unmatched, revert is called."""
        clean_report = StepReport(name="clean")
        clean_report.renames = {"Clean Name (2024)": "Original.Name"}
        mock_clean.return_value = clean_report
        mock_scrape.return_value = StepReport(name="scrape", unmatched_paths=["Clean Name (2024)"])
        mock_cleanup.return_value = StepReport(name="cleanup")

        run_process(_make_settings(), config=_make_config(tmp_path), dry_run=True, event_bus=EventBus())

        assert mock_revert.called
        # Verify the rename map and unmatched names were forwarded.
        kwargs = mock_revert.call_args.kwargs
        assert kwargs["rename_map"] == {"Clean Name (2024)": "Original.Name"}
        assert kwargs["unmatched_names"] == {"Clean Name (2024)"}
        assert kwargs["dry_run"] is True

    @patch("personalscraper.process.run._revert_unmatched_recleans")
    @patch("personalscraper.process.run.run_cleanup")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.run.run_clean")
    def test_revert_skipped_when_no_renames(
        self,
        mock_clean,
        mock_scrape,
        mock_cleanup,
        mock_revert,
        tmp_path: Path,
    ) -> None:
        """When no folder was renamed by reclean, the revert pass is skipped."""
        mock_clean.return_value = StepReport(name="clean")  # renames={} (default)
        mock_scrape.return_value = StepReport(name="scrape", unmatched_paths=["Foo"])
        mock_cleanup.return_value = StepReport(name="cleanup")

        run_process(_make_settings(), config=_make_config(tmp_path), event_bus=EventBus())

        assert not mock_revert.called
