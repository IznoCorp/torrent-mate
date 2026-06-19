"""CLI tests for the ``kanban mcp`` command (conduit Phase 3).

Drives the real Typer ``kanban`` app via ``CliRunner`` to prove: (1) ``kanban mcp --help`` lists the
required ``--issue`` option; (2) invoking ``mcp`` with no ``--issue`` fails (Typer's missing-option
exit, never a traceback); (3) the ``mcp`` body delegates to ``server.main`` with the resolved args
(patched so the test never starts a real stdio server / builds live GitHub deps); (4) the import
guard surfaces the friendly ``[mcp]`` message + a non-zero exit when the SDK extra is missing
(monkeypatching the lazy import to raise ``ImportError`` — mirrors the ``config serve`` ``[ui]`` guard).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kanbanmate.cli.app import app

runner = CliRunner()


def test_mcp_help_lists_required_issue() -> None:
    """``kanban mcp --help`` advertises ``--issue`` (the pinned-issue option)."""
    # Typer renders help via Rich, which styles + wraps/truncates to the terminal width. In CI's
    # non-TTY 80-col environment the option column gets squeezed, so a raw-substring check is brittle
    # (it passes in a wide interactive terminal but fails in CI). Force a wide width + strip ANSI so
    # the assertion tests the help CONTENT, not the rendering environment.
    result = runner.invoke(app, ["mcp", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--issue" in clean


def test_mcp_missing_issue_fails() -> None:
    """``kanban mcp`` with no ``--issue`` fails (Typer's required-option error, non-zero exit)."""
    result = runner.invoke(app, ["mcp"])
    assert result.exit_code != 0
    assert "issue" in result.output.lower()


def test_mcp_delegates_to_server_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``mcp`` body calls ``server.main`` with the resolved (root, issue, project, repo)."""
    calls: list[dict[str, object]] = []

    def _fake_main(*, root: Path, issue: int, project: str | None, repo: str | None) -> None:
        calls.append({"root": root, "issue": issue, "project": project, "repo": repo})

    # Patch the lazily-imported server module's main so no real stdio server / GitHub wiring runs.
    import kanbanmate.mcp.server as mcp_server

    monkeypatch.setattr(mcp_server, "main", _fake_main)
    result = runner.invoke(app, ["mcp", "--issue", "7", "--root", "/tmp/k"])
    assert result.exit_code == 0, result.output
    assert calls == [{"root": Path("/tmp/k"), "issue": 7, "project": None, "repo": None}]


def test_mcp_pin_mismatch_exits_clean_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``server.main`` ``PinMismatchError`` becomes a CLEAN non-zero exit (no traceback).

    Mirrors how ``serve`` converts its start-up guards: the CLI catches the start-up
    ``PinMismatchError`` and exits 1 with the actionable message on stderr, never a raw traceback.
    """
    import kanbanmate.mcp.server as mcp_server

    def _raise_mismatch(*, root: Path, issue: int, project: str | None, repo: str | None) -> None:
        raise mcp_server.PinMismatchError(
            f"kanban mcp: --issue {issue} disagrees with the worktree pin file (names #5)"
        )

    monkeypatch.setattr(mcp_server, "main", _raise_mismatch)
    result = runner.invoke(app, ["mcp", "--issue", "9", "--root", "/tmp/k"])
    assert result.exit_code == 1
    assert "disagrees with the worktree pin" in result.output
    assert "Traceback" not in result.output


def test_mcp_import_guard_friendly_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the ``[mcp]`` extra is absent, the guard prints the install hint + exits non-zero.

    Setting ``sys.modules['kanbanmate.mcp.server'] = None`` makes a fresh ``import`` of that module
    raise ``ImportError`` (the documented way to simulate a missing module) — so the lazy guarded
    import in the ``mcp`` command body trips exactly as it would without the ``[mcp]`` extra.
    """
    import kanbanmate.mcp as mcp_pkg

    # ``from kanbanmate.mcp import server`` resolves the already-imported submodule as a package
    # ATTRIBUTE; drop that attribute so the import machinery re-imports it, and point its
    # sys.modules slot at ``None`` so that re-import raises ImportError (the documented "missing
    # module" simulation) — tripping the guard exactly as a missing ``[mcp]`` extra would.
    monkeypatch.delattr(mcp_pkg, "server", raising=False)
    monkeypatch.setitem(sys.modules, "kanbanmate.mcp.server", None)
    result = runner.invoke(app, ["mcp", "--issue", "7"])
    assert result.exit_code == 1
    assert "[mcp]" in result.output
    assert "pip install 'kanbanmate[mcp]'" in result.output
