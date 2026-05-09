"""Tests for personalscraper.commands.library.maintenance.

Covers the remaining gaps in ``library-verify``, ``library-repair``,
``library-clean``, and ``library-validate``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.library.disk_cleaner import CleanResult
from personalscraper.library.models import LibraryValidationResult

runner = CliRunner()


# ── library-verify ───────────────────────────────────────────────────────────


class TestLibraryVerify:
    """Tests for the library-verify Typer command."""

    def test_help(self) -> None:
        """library-verify --help should display usage."""
        result = runner.invoke(app, ["library-verify", "--help"])
        assert result.exit_code == 0
        assert "--disk" in result.output
        assert "--budget" in result.output

    def test_default_invocation(self) -> None:
        """Default invocation calls library_verify_command and exits 0."""
        with patch(
            "personalscraper.indexer.cli.library_verify_command",
            return_value=0,
        ) as mock_cmd:
            result = runner.invoke(app, ["library-verify"])
        assert result.exit_code == 0
        mock_cmd.assert_called_once()
        _, kwargs = mock_cmd.call_args
        assert kwargs["disk"] is None
        assert kwargs["budget_seconds"] is None

    def test_budget_forwarded(self) -> None:
        """--budget value is forwarded as float to library_verify_command."""
        with patch(
            "personalscraper.indexer.cli.library_verify_command",
            return_value=0,
        ) as mock_cmd:
            result = runner.invoke(app, ["library-verify", "--budget", "300", "--disk", "drive_a"])
        assert result.exit_code == 0
        _, kwargs = mock_cmd.call_args
        assert kwargs["budget_seconds"] == 300.0
        assert kwargs["disk"] == "drive_a"

    def test_non_zero_rc_propagates(self) -> None:
        """Non-zero rc from the indexer cli is re-raised as Typer exit."""
        with patch(
            "personalscraper.indexer.cli.library_verify_command",
            return_value=4,
        ):
            result = runner.invoke(app, ["library-verify"])
        assert result.exit_code == 4


# ── library-repair ───────────────────────────────────────────────────────────


class TestLibraryRepair:
    """Tests for the library-repair Typer command."""

    def test_help(self) -> None:
        """library-repair --help should display usage."""
        result = runner.invoke(app, ["library-repair", "--help"])
        assert result.exit_code == 0
        assert "--budget" in result.output

    def test_default_budget(self) -> None:
        """Default budget is 60.0 and is forwarded to the indexer cli."""
        with patch(
            "personalscraper.indexer.cli.library_repair_command",
            return_value=0,
        ) as mock_cmd:
            result = runner.invoke(app, ["library-repair"])
        assert result.exit_code == 0
        _, kwargs = mock_cmd.call_args
        assert kwargs["budget_seconds"] == 60.0

    def test_custom_budget(self) -> None:
        """--budget overrides the default."""
        with patch(
            "personalscraper.indexer.cli.library_repair_command",
            return_value=0,
        ) as mock_cmd:
            result = runner.invoke(app, ["library-repair", "--budget", "120"])
        assert result.exit_code == 0
        _, kwargs = mock_cmd.call_args
        assert kwargs["budget_seconds"] == 120.0

    def test_non_zero_rc_propagates(self) -> None:
        """Non-zero rc propagates as Typer exit code."""
        with patch(
            "personalscraper.indexer.cli.library_repair_command",
            return_value=2,
        ):
            result = runner.invoke(app, ["library-repair"])
        assert result.exit_code == 2


# ── library-clean ────────────────────────────────────────────────────────────


class TestLibraryClean:
    """Coverage gaps for library-clean."""

    def test_invalid_only_errors(self) -> None:
        """--only with bogus value exits 1."""
        result = runner.invoke(app, ["library-clean", "--only", "bogus"])
        assert result.exit_code == 1
        assert "Invalid --only" in result.output

    def test_apply_lock_blocked(self) -> None:
        """--apply with held lock exits 1 with 'Another instance' message."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["library-clean", "--apply"])
        assert result.exit_code == 1
        assert "Another instance" in result.output

    def test_apply_reports_deleted_count(self) -> None:
        """--apply prints the deleted count and freed bytes summary."""
        cresult = CleanResult(dry_run=False, deleted_count=4, freed_bytes=2 * 1024 * 1024)
        with (
            patch("personalscraper.library.disk_cleaner.clean_library", return_value=cresult),
            patch("personalscraper.cli.acquire_lock", return_value=True),
            patch("personalscraper.cli.release_lock"),
        ):
            result = runner.invoke(app, ["library-clean", "--apply"])
        assert result.exit_code == 0
        assert "Deleted" in result.output
        assert "4" in result.output

    def test_apply_with_errors_lists_failures(self) -> None:
        """--apply with errors prints the per-error lines."""
        cresult = CleanResult(
            dry_run=False,
            deleted_count=0,
            freed_bytes=0,
            error_count=1,
            errors=["NTFS-fail: /foo/bar"],
        )
        with (
            patch("personalscraper.library.disk_cleaner.clean_library", return_value=cresult),
            patch("personalscraper.cli.acquire_lock", return_value=True),
            patch("personalscraper.cli.release_lock"),
        ):
            result = runner.invoke(app, ["library-clean", "--apply"])
        assert result.exit_code == 0
        assert "Errors" in result.output
        assert "NTFS-fail" in result.output

    def test_orphan_dry_run_preview(self) -> None:
        """--only orphans dry-run shows the preview block."""
        cresult = CleanResult(
            dry_run=True,
            deleted_count=2,
            freed_bytes=0,
            details=["/disk/Movies/Test1", "/disk/Movies/Test2"],
        )
        with patch("personalscraper.library.disk_cleaner.clean_library", return_value=cresult):
            result = runner.invoke(app, ["library-clean", "--only", "orphans"])
        assert result.exit_code == 0
        assert "Preview" in result.output
        assert "Test1" in result.output

    def test_orphan_dry_run_truncated_preview(self) -> None:
        """--only orphans dry-run with >20 details prints '… and N more' line."""
        details = [f"/disk/Movies/Test{i}" for i in range(25)]
        cresult = CleanResult(
            dry_run=True,
            deleted_count=25,
            freed_bytes=0,
            details=details,
        )
        with patch("personalscraper.library.disk_cleaner.clean_library", return_value=cresult):
            result = runner.invoke(app, ["library-clean", "--only", "orphans"])
        assert result.exit_code == 0
        assert "more" in result.output


# ── library-validate ─────────────────────────────────────────────────────────


class TestLibraryValidateGaps:
    """Coverage gaps for library-validate (from-index, lock, etc.)."""

    def _empty_validation(self) -> LibraryValidationResult:
        return LibraryValidationResult(
            validated_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            total_items=0,
            valid_count=0,
            fixed_count=0,
            issues_count=0,
        )

    def test_from_index_with_fix_errors(self) -> None:
        """--from-index + --fix is rejected with exit code 1."""
        result = runner.invoke(app, ["library-validate", "--from-index", "--fix"])
        assert result.exit_code == 1
        assert "from-index" in result.output

    def test_from_index_path(self) -> None:
        """--from-index uses validate_from_index and opens the indexer DB."""
        with (
            patch(
                "personalscraper.library.validator.validate_from_index",
                return_value=self._empty_validation(),
            ) as mock_val,
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.indexer.db.apply_migrations"),
        ):
            result = runner.invoke(app, ["library-validate", "--from-index"])
        assert result.exit_code == 0
        mock_val.assert_called_once()
        assert "from index" in result.output

    def test_fix_apply_lock_blocked(self) -> None:
        """--fix --apply with held lock exits 1."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["library-validate", "--fix", "--apply"])
        assert result.exit_code == 1
        assert "Another instance" in result.output

    def test_fix_with_remaining_issues_suggests_rescrape(self) -> None:
        """--fix with leftover issues suggests library-rescrape."""
        vresult = LibraryValidationResult(
            validated_at="2026",
            disk_filter=None,
            category_filter=None,
            total_items=2,
            valid_count=0,
            fixed_count=1,
            issues_count=1,
        )
        with (
            patch(
                "personalscraper.library.validator.validate_library",
                return_value=vresult,
            ),
            patch("personalscraper.library.models.write_json"),
        ):
            result = runner.invoke(app, ["library-validate", "--fix"])
        assert result.exit_code == 0
        assert "library-rescrape" in result.output
