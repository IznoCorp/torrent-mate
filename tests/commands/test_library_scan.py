"""Regression tests for ``personalscraper library-scan`` CLI command.

Since the lib-fold single-creator cutover, ``library-scan`` is a **visible
re-pointed alias of ``library-index --mode full``** (DESIGN OQ-4): it no longer
runs a bespoke ``scan_library`` pass.  It delegates to the shared internal
:func:`~personalscraper.indexer.commands.scan.library_index_command` with
``mode="full"`` and forwards ``--disk`` / ``--dry-run`` / ``--config``.

Verifies:
- ``library-scan --help`` exits 0 and surfaces ``--disk`` and ``--dry-run``.
- ``library-scan`` delegates to ``library_index_command(mode="full", ...)``
  exactly once and forwards the user-supplied options.
- A non-zero return code from the delegate becomes a ``typer.Exit(rc)``.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

# The alias imports ``library_index_command`` from ``personalscraper.indexer.cli``
# at call time (``from personalscraper.indexer.cli import library_index_command``),
# so the spy must replace the name in that namespace.
_DELEGATE_PATH = "personalscraper.indexer.cli.library_index_command"


# ── smoke test ────────────────────────────────────────────────────────────────


class TestLibraryScanHelp:
    """``library-scan --help`` must exit 0 and surface expected flags."""

    def test_help_exits_zero(self) -> None:
        """``library-scan --help`` exits 0."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert result.exit_code == 0, result.output

    def test_help_contains_disk_flag(self) -> None:
        """``--disk`` is documented in the help text."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert "--disk" in result.output

    def test_help_contains_dry_run_flag(self) -> None:
        """``--dry-run`` is documented in the help text."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert "--dry-run" in result.output


# ── delegation contract ───────────────────────────────────────────────────────


class TestLibraryScanDelegatesToIndex:
    """``library-scan`` forwards to ``library_index_command(mode="full", ...)``."""

    def test_delegates_with_mode_full(self, test_config) -> None:
        """A plain ``library-scan`` calls the delegate once with ``mode='full'``."""
        with patch(_DELEGATE_PATH, return_value=0) as mock_delegate:
            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0, result.output
        mock_delegate.assert_called_once()
        kwargs = mock_delegate.call_args.kwargs
        assert kwargs["mode"] == "full"
        # Defaults forwarded for the unset options.
        assert kwargs["disk"] is None
        assert kwargs["dry_run"] is False
        # The bus is always threaded from the CLI boundary (required-bus contract).
        assert kwargs["event_bus"] is not None

    def test_forwards_disk_option(self, test_config) -> None:
        """``--disk drive_a`` is forwarded to the delegate as ``disk='drive_a'``."""
        with patch(_DELEGATE_PATH, return_value=0) as mock_delegate:
            result = runner.invoke(app, ["library-scan", "--disk", "drive_a"])

        assert result.exit_code == 0, result.output
        mock_delegate.assert_called_once()
        assert mock_delegate.call_args.kwargs["disk"] == "drive_a"
        assert mock_delegate.call_args.kwargs["mode"] == "full"

    def test_forwards_dry_run_option(self, test_config) -> None:
        """``--dry-run`` is forwarded to the delegate as ``dry_run=True``."""
        with patch(_DELEGATE_PATH, return_value=0) as mock_delegate:
            result = runner.invoke(app, ["library-scan", "--dry-run"])

        assert result.exit_code == 0, result.output
        mock_delegate.assert_called_once()
        assert mock_delegate.call_args.kwargs["dry_run"] is True
        assert mock_delegate.call_args.kwargs["mode"] == "full"

    def test_no_mode_option_exposed(self) -> None:
        """The alias drops ``--mode`` — passing it is an unknown-flag error."""
        with patch(_DELEGATE_PATH, return_value=0):
            result = runner.invoke(app, ["library-scan", "--mode", "quick"])
        # ``--mode`` is no longer a valid option for this command.
        assert result.exit_code != 0


# ── return-code propagation ───────────────────────────────────────────────────


class TestLibraryScanReturnCode:
    """A non-zero delegate return code becomes a non-zero CLI exit."""

    def test_nonzero_rc_propagates(self, test_config) -> None:
        """``library_index_command`` returning 2 (unknown disk) → CLI exit 2."""
        with patch(_DELEGATE_PATH, return_value=2):
            result = runner.invoke(app, ["library-scan", "--disk", "unknown_disk"])

        # rc != 0 → ``raise typer.Exit(rc)``; CliRunner surfaces the code.
        assert result.exit_code == 2, result.output

    def test_zero_rc_exits_zero(self, test_config) -> None:
        """``library_index_command`` returning 0 → CLI exit 0."""
        with patch(_DELEGATE_PATH, return_value=0):
            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0, result.output
