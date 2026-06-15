"""Tests for the Claude-tier installer (DESIGN §4.2).

Every test is fully isolated:

* ``subprocess.run`` is replaced by a ``MagicMock`` — no real ``claude`` CLI is invoked; the
  tests assert on the exact argv lists instead.
* The injectable ``runner`` pattern is exercised so idempotent skip and "not found" tolerance
  are verified without side effects.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from kanbanmate.cli.install import (
    ClaudeNotFoundError,
    ClaudePluginInstallError,
    claude_install,
    claude_uninstall,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[Any]:
    """Build a :class:`subprocess.CompletedProcess` for the mock runner to return."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


_REPO = Path("/tmp/kanbanmate")


# ============================================================================
# claude_install — argv correctness
# ============================================================================


class TestClaudeInstallArgv:
    """Assert the exact argv lists sent to the ``claude`` CLI on a fresh install."""

    def test_issues_marketplace_add_then_plugin_install(self) -> None:
        """When not yet installed, the expected two ``claude`` commands are issued."""
        # First call (plugin list) returns empty — no kanban installed.
        # Subsequent calls are the marketplace add and plugin install.
        mock_runner = MagicMock(
            side_effect=[
                _completed(stdout="No plugins installed.\n"),  # plugin list
                _completed(),  # marketplace add
                _completed(),  # plugin install
            ]
        )

        claude_install(_REPO, runner=mock_runner)

        # Three calls total: list check, marketplace add, plugin install.
        assert mock_runner.call_count == 3

        # Call 1: claude plugin list (idempotence check).
        mock_runner.assert_any_call(["claude", "plugin", "list"], capture_output=True, text=True)

        # Call 2: marketplace add.
        mock_runner.assert_any_call(
            ["claude", "plugin", "marketplace", "add", str(_REPO), "--scope", "user"],
            capture_output=True,
            text=True,
        )

        # Call 3: plugin install.
        mock_runner.assert_any_call(
            ["claude", "plugin", "install", "kanban@kanbanmate", "--scope", "user"],
            capture_output=True,
            text=True,
        )

    def test_all_calls_use_argv_lists_no_shell(self) -> None:
        """Every ``claude`` call passes an argv list and never sets ``shell=True``."""
        mock_runner = MagicMock(
            side_effect=[
                _completed(stdout="No plugins installed.\n"),
                _completed(),
                _completed(),
            ]
        )

        claude_install(_REPO, runner=mock_runner)

        for call_args in mock_runner.call_args_list:
            args, kwargs = call_args
            assert isinstance(args[0], list)
            assert kwargs.get("shell") is not True


# ============================================================================
# claude_install — idempotence (skip when already installed)
# ============================================================================


class TestClaudeInstallIdempotence:
    """When ``claude plugin list`` shows kanban already registered, the install is skipped."""

    def test_skip_when_kanban_in_plugin_list_output(self) -> None:
        """The ``claude plugin list`` output contains 'kanban' → no further calls."""
        mock_runner = MagicMock(
            return_value=_completed(stdout="kanban@kanbanmate  user  enabled\n")
        )

        claude_install(_REPO, runner=mock_runner)

        # A single call — plugin list — and nothing else.
        assert mock_runner.call_count == 1
        mock_runner.assert_called_once_with(
            ["claude", "plugin", "list"], capture_output=True, text=True
        )

    def test_skip_when_kanban_appears_anywhere_in_output(self) -> None:
        """Even if the table format varies, any 'kanban' match triggers the skip."""
        # Simulate a multi-plugin listing where kanban appears in the middle.
        mock_runner = MagicMock(
            return_value=_completed(
                stdout="other-plugin@foo  user  enabled\nkanban@kanbanmate  user  enabled\n"
            )
        )

        claude_install(_REPO, runner=mock_runner)

        # Only the list call was made — install skipped.
        assert mock_runner.call_count == 1


# ============================================================================
# claude_uninstall
# ============================================================================


class TestClaudeUninstall:
    """Teardown: correct argv, tolerance for "not found" outcomes."""

    def test_issues_uninstall_then_marketplace_remove(self) -> None:
        """Uninstall issues the expected two ``claude`` commands in order."""
        mock_runner = MagicMock(
            side_effect=[
                _completed(),  # plugin uninstall
                _completed(),  # marketplace remove
            ]
        )

        claude_uninstall(_REPO, runner=mock_runner)

        assert mock_runner.call_count == 2

        mock_runner.assert_any_call(
            ["claude", "plugin", "uninstall", "kanban"],
            capture_output=True,
            text=True,
        )

        mock_runner.assert_any_call(
            ["claude", "plugin", "marketplace", "remove", str(_REPO)],
            capture_output=True,
            text=True,
        )

    def test_tolerates_plugin_not_found(self) -> None:
        """A non-zero exit from ``uninstall`` (plugin absent) does not raise."""
        mock_runner = MagicMock(
            side_effect=[
                _completed(returncode=1, stderr="plugin not found: kanban"),
                _completed(),  # marketplace remove still runs
            ]
        )

        # Must not raise.
        claude_uninstall(_REPO, runner=mock_runner)

        assert mock_runner.call_count == 2

    def test_tolerates_marketplace_not_found(self) -> None:
        """A non-zero exit from ``marketplace remove`` (already gone) does not raise."""
        mock_runner = MagicMock(
            side_effect=[
                _completed(),  # plugin uninstall ok
                _completed(returncode=1, stderr="marketplace not found"),
            ]
        )

        # Must not raise.
        claude_uninstall(_REPO, runner=mock_runner)

        assert mock_runner.call_count == 2

    def test_tolerates_both_not_found(self) -> None:
        """Both steps failing (fully absent install) does not raise — idempotent."""
        mock_runner = MagicMock(
            side_effect=[
                _completed(returncode=1, stderr="plugin not found: kanban"),
                _completed(returncode=1, stderr="marketplace not found"),
            ]
        )

        # Must not raise.
        claude_uninstall(_REPO, runner=mock_runner)

    def test_uninstall_calls_use_argv_lists_no_shell(self) -> None:
        """Every uninstall call passes an argv list and never sets ``shell=True``."""
        mock_runner = MagicMock(side_effect=[_completed(), _completed()])

        claude_uninstall(_REPO, runner=mock_runner)

        for call_args in mock_runner.call_args_list:
            args, kwargs = call_args
            assert isinstance(args[0], list)
            assert kwargs.get("shell") is not True


# ============================================================================
# claude_install — failure surfacing (errors-2 / errors-7)
# ============================================================================


class TestClaudeInstallFailure:
    """A failed ``claude plugin install`` or missing ``claude`` binary must surface clearly."""

    def test_plugin_install_nonzero_raises(self) -> None:
        """A non-zero return from ``claude plugin install`` raises ClaudePluginInstallError."""
        mock_runner = MagicMock(
            side_effect=[
                _completed(stdout="No plugins installed.\n"),  # plugin list
                _completed(),  # marketplace add (best-effort, tolerated)
                _completed(returncode=1, stderr="network error"),  # plugin install FAILS
            ]
        )

        with pytest.raises(ClaudePluginInstallError, match="return code 1"):
            claude_install(_REPO, runner=mock_runner)

        # All three calls were attempted.
        assert mock_runner.call_count == 3

    def test_missing_claude_binary_raises_clean_error(self) -> None:
        """A missing ``claude`` binary raises ClaudeNotFoundError with an actionable message."""
        mock_runner = MagicMock(
            side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'claude'")
        )

        with pytest.raises(ClaudeNotFoundError, match="claude CLI not found"):
            claude_install(_REPO, runner=mock_runner)

        # Only the list check was attempted — no further calls on a missing binary.
        assert mock_runner.call_count == 1

    def test_missing_claude_binary_on_install_call(self) -> None:
        """FileNotFoundError on the install call itself also surfaces cleanly (defense-in-depth)."""
        mock_runner = MagicMock(
            side_effect=[
                _completed(stdout="No plugins installed.\n"),  # plugin list ok
                _completed(),  # marketplace add ok
                FileNotFoundError(
                    "[Errno 2] No such file or directory: 'claude'"
                ),  # install call fails
            ]
        )

        with pytest.raises(ClaudeNotFoundError, match="claude CLI not found"):
            claude_install(_REPO, runner=mock_runner)


# ============================================================================
# Module-level API contract
# ============================================================================


class TestModuleApi:
    """Smoke-checks on the claude-tier public surface used by ``cli/app.py``."""

    def test_importable_without_side_effects(self) -> None:
        """Importing the claude functions performs no I/O and exposes the expected callables."""
        from kanbanmate.cli import install as _install_mod

        assert callable(_install_mod.claude_install)
        assert callable(_install_mod.claude_uninstall)
