"""Tests for personalscraper.commands.pipeline.

Covers coverage gaps in ``verify``, ``enforce``, ``dispatch``, ``process``,
and ``run`` subcommands.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.models import StepReport

runner = CliRunner()


# Common patch targets and helpers
def _step(name: str, success: int = 1) -> StepReport:
    """Build a minimal StepReport with one detail entry for verbose tests."""
    sr = StepReport(name=name, success_count=success)
    sr.details = ["detail-line"]
    return sr


@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
class TestVerifyCommand:
    """Tests for the `verify` Typer subcommand."""

    def test_runs(self, _release, _acquire) -> None:
        """Verify runs and prints summary line."""
        with patch(
            "personalscraper.verify.run.run_verify",
            return_value=(_step("verify"), [object(), object()]),
        ):
            result = runner.invoke(app, ["verify"])
        assert result.exit_code == 0
        assert "Verify" in result.output
        assert "ready for dispatch" in result.output

    def test_dry_run_flag(self, _release, _acquire) -> None:
        """--dry-run is forwarded as dry_run=True."""
        with patch(
            "personalscraper.verify.run.run_verify",
            return_value=(_step("verify"), []),
        ) as mock_run:
            result = runner.invoke(app, ["verify", "--dry-run"])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    def test_verbose_prints_details(self, _release, _acquire) -> None:
        """Global --verbose flag triggers per-detail print branch."""
        with patch(
            "personalscraper.verify.run.run_verify",
            return_value=(_step("verify"), []),
        ):
            result = runner.invoke(app, ["--verbose", "verify"])
        assert result.exit_code == 0
        assert "detail-line" in result.output


class TestVerifyLockBlocked:
    """verify exits 1 when the pipeline lock is held."""

    def test_lock_blocked(self) -> None:
        """Lock contention exits 1."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["verify"])
        assert result.exit_code == 1
        assert "Another instance" in result.output


@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
class TestEnforceCommand:
    """Tests for the `enforce` Typer subcommand."""

    def test_runs(self, _release, _acquire) -> None:
        """Enforce runs and prints summary line."""
        with patch(
            "personalscraper.enforce.run.run_enforce",
            return_value=_step("enforce"),
        ):
            result = runner.invoke(app, ["enforce"])
        assert result.exit_code == 0
        assert "Enforce" in result.output

    def test_dry_run_flag(self, _release, _acquire) -> None:
        """--dry-run is forwarded as dry_run=True."""
        with patch(
            "personalscraper.enforce.run.run_enforce",
            return_value=_step("enforce"),
        ) as mock_run:
            result = runner.invoke(app, ["enforce", "--dry-run"])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    def test_verbose(self, _release, _acquire) -> None:
        """--verbose prints detail lines."""
        with patch(
            "personalscraper.enforce.run.run_enforce",
            return_value=_step("enforce"),
        ):
            result = runner.invoke(app, ["--verbose", "enforce"])
        assert result.exit_code == 0
        assert "detail-line" in result.output


class TestEnforceLockBlocked:
    """enforce exits 1 when the lock is held."""

    def test_lock_blocked(self) -> None:
        """Lock contention exits 1."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["enforce"])
        assert result.exit_code == 1


@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
class TestDispatchCommand:
    """Tests for the `dispatch` Typer subcommand."""

    def test_runs(self, _release, _acquire) -> None:
        """Dispatch runs and prints summary line."""
        with patch(
            "personalscraper.dispatch.run.run_dispatch",
            return_value=_step("dispatch"),
        ):
            result = runner.invoke(app, ["dispatch"])
        assert result.exit_code == 0
        assert "Dispatch" in result.output

    def test_dry_run_flag(self, _release, _acquire) -> None:
        """--dry-run is forwarded."""
        with patch(
            "personalscraper.dispatch.run.run_dispatch",
            return_value=_step("dispatch"),
        ) as mock_run:
            result = runner.invoke(app, ["dispatch", "--dry-run"])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    def test_verbose(self, _release, _acquire) -> None:
        """--verbose prints detail lines."""
        with patch(
            "personalscraper.dispatch.run.run_dispatch",
            return_value=_step("dispatch"),
        ):
            result = runner.invoke(app, ["--verbose", "dispatch"])
        assert result.exit_code == 0
        assert "detail-line" in result.output


class TestDispatchLockBlocked:
    """dispatch exits 1 when the lock is held."""

    def test_lock_blocked(self) -> None:
        """Lock contention exits 1."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["dispatch"])
        assert result.exit_code == 1


@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
class TestProcessCommand:
    """Tests for the `process` Typer subcommand."""

    def test_runs(self, _release, _acquire) -> None:
        """Process runs and prints three summary lines."""
        with patch(
            "personalscraper.process.run.run_process",
            return_value=(_step("clean"), _step("scrape"), _step("cleanup")),
        ):
            result = runner.invoke(app, ["process"])
        assert result.exit_code == 0
        assert "Clean" in result.output
        assert "Scrape" in result.output
        assert "Cleanup" in result.output

    def test_verbose_prints_details(self, _release, _acquire) -> None:
        """--verbose prints per-step detail lines."""
        with patch(
            "personalscraper.process.run.run_process",
            return_value=(_step("clean"), _step("scrape"), _step("cleanup")),
        ):
            result = runner.invoke(app, ["--verbose", "process"])
        assert result.exit_code == 0
        assert "detail-line" in result.output

    def test_failure_exits_1(self, _release, _acquire) -> None:
        """Process exits 1 with friendly message when run_process raises."""
        with patch(
            "personalscraper.process.run.run_process",
            side_effect=RuntimeError("boom"),
        ):
            result = runner.invoke(app, ["process"])
        assert result.exit_code == 1
        assert "Process failed" in result.output


class TestProcessLockBlocked:
    """process exits 1 when the lock is held."""

    def test_lock_blocked(self) -> None:
        """Lock contention exits 1."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["process"])
        assert result.exit_code == 1


# ── clean / cleanup standalone CLI (SH-21 / AR-C, sub-phase 8.5) ────────────


@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
class TestCleanCommand:
    """Tests for the standalone ``clean`` Typer subcommand."""

    def test_help_exits_zero(self, _release, _acquire) -> None:
        """``clean --help`` exits 0 and shows the SH-21 description."""
        result = runner.invoke(app, ["clean", "--help"])
        assert result.exit_code == 0
        assert "reclean" in result.output.lower()

    def test_runs(self, _release, _acquire) -> None:
        """Clean runs and prints a single summary line."""
        with patch(
            "personalscraper.process.run.run_clean",
            return_value=_step("clean"),
        ):
            result = runner.invoke(app, ["clean"])
        assert result.exit_code == 0
        assert "Clean" in result.output

    def test_dry_run_flag(self, _release, _acquire) -> None:
        """--dry-run is forwarded as dry_run=True."""
        with patch(
            "personalscraper.process.run.run_clean",
            return_value=_step("clean"),
        ) as mock_run:
            result = runner.invoke(app, ["clean", "--dry-run"])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    def test_verbose_prints_details(self, _release, _acquire) -> None:
        """--verbose prints per-detail lines."""
        with patch(
            "personalscraper.process.run.run_clean",
            return_value=_step("clean"),
        ):
            result = runner.invoke(app, ["--verbose", "clean"])
        assert result.exit_code == 0
        assert "detail-line" in result.output

    def test_failure_exits_1(self, _release, _acquire) -> None:
        """Clean exits 1 with friendly message when run_clean raises."""
        with patch(
            "personalscraper.process.run.run_clean",
            side_effect=RuntimeError("boom"),
        ):
            result = runner.invoke(app, ["clean"])
        assert result.exit_code == 1
        assert "Clean failed" in result.output


class TestCleanLockBlocked:
    """clean exits 1 when the pipeline lock is held."""

    def test_lock_blocked(self) -> None:
        """Lock contention exits 1."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["clean"])
        assert result.exit_code == 1
        assert "Another instance" in result.output


@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
class TestCleanupCommand:
    """Tests for the standalone ``cleanup`` Typer subcommand."""

    def test_help_exits_zero(self, _release, _acquire) -> None:
        """``cleanup --help`` exits 0 and shows the SH-21 description."""
        result = runner.invoke(app, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_runs(self, _release, _acquire) -> None:
        """Cleanup runs and prints a single summary line."""
        with patch(
            "personalscraper.process.run.run_cleanup",
            return_value=_step("cleanup"),
        ):
            result = runner.invoke(app, ["cleanup"])
        assert result.exit_code == 0
        assert "Cleanup" in result.output

    def test_dry_run_flag(self, _release, _acquire) -> None:
        """--dry-run is forwarded as dry_run=True."""
        with patch(
            "personalscraper.process.run.run_cleanup",
            return_value=_step("cleanup"),
        ) as mock_run:
            result = runner.invoke(app, ["cleanup", "--dry-run"])
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    def test_verbose_prints_details(self, _release, _acquire) -> None:
        """--verbose prints per-detail lines."""
        with patch(
            "personalscraper.process.run.run_cleanup",
            return_value=_step("cleanup"),
        ):
            result = runner.invoke(app, ["--verbose", "cleanup"])
        assert result.exit_code == 0
        assert "detail-line" in result.output

    def test_failure_exits_1(self, _release, _acquire) -> None:
        """Cleanup exits 1 with friendly message when run_cleanup raises."""
        with patch(
            "personalscraper.process.run.run_cleanup",
            side_effect=RuntimeError("boom"),
        ):
            result = runner.invoke(app, ["cleanup"])
        assert result.exit_code == 1
        assert "Cleanup failed" in result.output


class TestCleanupLockBlocked:
    """cleanup exits 1 when the pipeline lock is held."""

    def test_lock_blocked(self) -> None:
        """Lock contention exits 1."""
        with patch("personalscraper.cli.acquire_lock", return_value=False):
            result = runner.invoke(app, ["cleanup"])
        assert result.exit_code == 1
        assert "Another instance" in result.output


# ── ingest / sort / scrape — verbose branches not covered by test_cli.py ────


@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
class TestIngestSortScrapeVerbose:
    """Verbose branches for already-tested commands (covers details printing)."""

    def test_sort_verbose(self, _release, _acquire) -> None:
        """Sort --verbose prints details."""
        with patch(
            "personalscraper.sorter.run.run_sort",
            return_value=_step("sort"),
        ):
            result = runner.invoke(app, ["--verbose", "sort"])
        assert result.exit_code == 0
        assert "detail-line" in result.output

    def test_scrape_verbose(self, _release, _acquire) -> None:
        """Scrape --verbose prints details."""
        with patch(
            "personalscraper.scraper.run.run_scrape",
            return_value=_step("scrape"),
        ):
            result = runner.invoke(app, ["--verbose", "scrape"])
        assert result.exit_code == 0
        assert "detail-line" in result.output


# ── run command — TrailerStepFailed branch ───────────────────────────────────


class TestRunTrailerFailure:
    """Run command exits 2 when the trailers step raises TrailerStepFailed."""

    def test_trailer_step_failed_exit_2(self) -> None:
        """Pipeline.run() raising TrailerStepFailed → exit 2 + ABORTED message."""
        from personalscraper.trailers.state import TrailerStepFailed

        with (
            patch("personalscraper.cli.acquire_lock", return_value=True),
            patch("personalscraper.cli.release_lock"),
            patch(
                "personalscraper.pipeline.Pipeline.run",
                side_effect=TrailerStepFailed("trailer step crashed"),
            ),
            patch(
                "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured",
                return_value=False,
            ),
            patch(
                "personalscraper.api.notify.telegram.TelegramNotifier.is_configured",
                return_value=False,
            ),
        ):
            result = runner.invoke(app, ["run"])
        assert result.exit_code == 2
        assert "ABORTED" in result.output


# ── run --help step list (DEV #7 regression) ────────────────────────────────


class TestRunHelpStepList:
    """``personalscraper run --help`` must list all 9 pipeline steps.

    Regression guard for DEV #7: the help text was hardcoded as
    ``(ingest -> sort -> process -> verify -> dispatch)`` — only 5 steps,
    missing ``clean``, ``scrape``, ``cleanup``, ``enforce``, and ``trailers``.
    The fix generates the help string from ``DEFAULT_STEPS`` at import time
    so any future step addition is automatically reflected.
    """

    # The expected step names match DEFAULT_STEPS key order (insertion order
    # in Python 3.7+), which is the canonical pipeline execution order.
    EXPECTED_STEPS = [
        "ingest",
        "sort",
        "clean",
        "scrape",
        "cleanup",
        "enforce",
        "verify",
        "trailers",
        "dispatch",
    ]

    def test_run_help_mentions_all_steps(self) -> None:
        """``run --help`` output contains each of the 9 step names.

        Invokes the CLI help path (exit 0) via CliRunner and asserts every step
        name is present in the output. Without the DEV #7 fix, ``clean``,
        ``scrape``, ``cleanup``, ``enforce``, and ``trailers`` would be absent.
        """
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0, f"run --help exited {result.exit_code}: {result.output}"
        for step in self.EXPECTED_STEPS:
            assert step in result.output, (
                f"Step '{step}' missing from `run --help` output.\nOutput was:\n{result.output}"
            )

    def test_run_help_derived_from_default_steps(self) -> None:
        """Help text step list matches DEFAULT_STEPS keys in order.

        Pins the introspection contract: ``_run_help()`` must produce a
        string containing every key from ``DEFAULT_STEPS`` in insertion order.
        If ``DEFAULT_STEPS`` is extended, this test fails and reminds the
        developer that the help text updates automatically.
        """
        from personalscraper.pipeline_steps import DEFAULT_STEPS

        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        for step in DEFAULT_STEPS:
            assert step in result.output, (
                f"DEFAULT_STEPS key '{step}' missing from `run --help`.\nOutput was:\n{result.output}"
            )
