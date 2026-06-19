"""Tests for :mod:`kanbanmate.adapters.workspace.base_sync`.

The base-clone git sync was relocated here from ``bin/kanban_update_main`` (conduit §11.2). These
unit tests mock ``subprocess.run`` and assert the argv shape (``git -C <cwd> <subcmd> ...``), the
fatal-on-non-zero ``fetch_base`` contract (raises :class:`BaseFetchError`), and ``ff_dev_clone``'s
best-effort behaviour (dirty / off-main skip; clean-on-main fast-forward; never a merge or force).
No real git is touched (DESIGN §10 — merge is human-only).
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from kanbanmate.adapters.workspace.base_sync import BaseFetchError, fetch_base, ff_dev_clone


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Build a fake :class:`subprocess.CompletedProcess` for a stubbed git call."""
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class _GitRecorder:
    """Records every ``git`` invocation and replays scripted results by sub-command."""

    def __init__(self, results: dict[str, subprocess.CompletedProcess[str]]) -> None:
        """Seed scripted results keyed by the git sub-command (argv[3], e.g. ``fetch``)."""
        self.results = results
        self.calls: list[list[str]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Record the argv and return the scripted result for its sub-command (default: ok)."""
        argv = list(args[0])
        self.calls.append(argv)
        # argv == ["git", "-C", <cwd>, <subcmd>, ...]; key on the (possibly two-word) sub-command.
        subcmd = argv[3] if len(argv) > 3 else ""
        joined = " ".join(argv[3:5]) if len(argv) > 4 else subcmd
        return self.results.get(joined, self.results.get(subcmd, _completed()))


def _install(monkeypatch: pytest.MonkeyPatch, recorder: _GitRecorder) -> None:
    """Route the adapter's ``subprocess.run`` through the recorder (no real git)."""
    monkeypatch.setattr("kanbanmate.adapters.workspace.base_sync.subprocess.run", recorder)


class TestFetchBase:
    """``fetch_base`` runs ``git fetch origin main`` and is fatal on non-zero exit."""

    def test_fetches_origin_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A successful fetch issues exactly ``git -C <clone> fetch origin main`` and returns None."""
        rec = _GitRecorder({"fetch origin": _completed()})
        _install(monkeypatch, rec)

        fetch_base("/base")
        assert rec.calls == [["git", "-C", "/base", "fetch", "origin", "main"]]

    def test_raises_on_non_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-zero fetch raises :class:`BaseFetchError` carrying the trimmed stderr."""
        rec = _GitRecorder({"fetch origin": _completed(returncode=1, stderr=" boom \n")})
        _install(monkeypatch, rec)

        with pytest.raises(BaseFetchError) as excinfo:
            fetch_base("/base")
        assert excinfo.value.stderr == "boom"


class TestFfDevClone:
    """``ff_dev_clone`` fast-forwards only a clean clone on main; else best-effort skip."""

    def test_clean_on_main_fast_forwards(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A clean clone on main is fast-forwarded with ``pull --ff-only`` (no merge/force)."""
        rec = _GitRecorder(
            {
                "diff --quiet": _completed(returncode=0),
                "diff --cached": _completed(returncode=0),
                "status --porcelain": _completed(stdout=""),
                "rev-parse --abbrev-ref": _completed(stdout="main\n"),
                "pull --ff-only": _completed(),
            }
        )
        _install(monkeypatch, rec)

        ff_dev_clone("/dev")
        assert ["git", "-C", "/dev", "pull", "--ff-only"] in rec.calls
        banned = {"--force", "-f", "merge", "rebase", "reset", "push"}
        assert not any(banned & set(argv) for argv in rec.calls)

    def test_progress_line_goes_to_stderr_not_stdout(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The happy-path "Fast-forwarding" message must hit stderr — stdout is the MCP JSON-RPC
        stream when ``update_main`` runs inside the conduit stdio server; a stray stdout write would
        corrupt the protocol frames the client parses."""
        rec = _GitRecorder(
            {
                "diff --quiet": _completed(returncode=0),
                "diff --cached": _completed(returncode=0),
                "status --porcelain": _completed(stdout=""),
                "rev-parse --abbrev-ref": _completed(stdout="main\n"),
                "pull --ff-only": _completed(),
            }
        )
        _install(monkeypatch, rec)

        ff_dev_clone("/dev")
        captured = capsys.readouterr()
        assert captured.out == ""  # nothing on stdout — would corrupt the JSON-RPC stream
        assert "Fast-forwarding dev clone on main" in captured.err

    def test_dirty_skips_without_pulling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A dirty clone is skipped (never pulled), returning without raising."""
        rec = _GitRecorder({"diff --quiet": _completed(returncode=1)})
        _install(monkeypatch, rec)

        ff_dev_clone("/dev")
        assert not any("pull" in argv for argv in rec.calls)

    def test_off_main_skips_without_pulling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A clean clone NOT on main is skipped (never pulled)."""
        rec = _GitRecorder(
            {
                "diff --quiet": _completed(returncode=0),
                "diff --cached": _completed(returncode=0),
                "status --porcelain": _completed(stdout=""),
                "rev-parse --abbrev-ref": _completed(stdout="feat/x\n"),
            }
        )
        _install(monkeypatch, rec)

        ff_dev_clone("/dev")
        assert not any("pull" in argv for argv in rec.calls)

    def test_failed_pull_is_best_effort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed ``pull --ff-only`` is reported but never raised (post-merge hook never blocks)."""
        rec = _GitRecorder(
            {
                "diff --quiet": _completed(returncode=0),
                "diff --cached": _completed(returncode=0),
                "status --porcelain": _completed(stdout=""),
                "rev-parse --abbrev-ref": _completed(stdout="main\n"),
                "pull --ff-only": _completed(returncode=1, stderr="diverged"),
            }
        )
        _install(monkeypatch, rec)

        ff_dev_clone("/dev")
