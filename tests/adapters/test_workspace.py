"""Tests for :mod:`kanbanmate.adapters.workspace`.

Two test groups:
1. **Unit** (default): mock ``subprocess.run`` — assert argv building,
   ``discover_branch`` HEAD→None mapping, ``--force`` gating, ``is_alive``
   return-code parsing. No real tmux or git.
2. **local_real** (opt-in): real ``tmux`` and ``git`` in throwaway temp
   directories. Skipped by default; set ``KANBAN_LOCAL_REAL=1`` to run.
"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kanbanmate.adapters.workspace.sessions import (
    _END_CLEAR_DELAY,
    _END_CONFIRM_DELAY,
    _END_MENU_CONFIRM_DELAY,
    _END_MENU_DELAY,
    TmuxSessions,
)
from kanbanmate.adapters.workspace.worktree import (
    _PACKAGE_ROOT,
    GIT_TIMEOUT,
    GitWorktreeWorkspace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a :class:`subprocess.CompletedProcess` with the given fields."""
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _target_for(clone_dir: Path, ticket: int) -> Path:
    """Return the expected worktree target path for *ticket* under *clone_dir*."""
    return (clone_dir.parent / "worktrees" / f"ticket-{ticket}").resolve()


# ============================================================================
# UNIT TESTS — GitWorktreeWorkspace
# ============================================================================


class TestGitWorktreeWorkspaceUnit:
    """Unit tests for :class:`GitWorktreeWorkspace` with a mock subprocess runner."""

    # -- ensure_worktree -----------------------------------------------------

    def test_ensure_worktree_creates_when_absent(self, tmp_path: Path) -> None:
        """When no worktree AND no WIP branch exist yet, a worktree on a NEW WIP branch is added.

        Hybrid flow (DESIGN §13): the worktree is checked out on the per-ticket WIP branch
        ``kanban/ticket-<n>``, created off ``origin/<base>`` with ``-b`` when the branch is absent.
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 42)
        mock_runner = MagicMock()
        # _worktree_paths (no match) → fetch → rev-parse --verify (branch ABSENT, rc=1) → add -b →
        # _ensure_identity probes (config user.name / user.email — non-empty → already set, no set).
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /some/other/path\n"),
            _completed_process(),  # fetch
            _completed_process(returncode=1),  # rev-parse --verify: WIP branch absent
            _completed_process(),  # worktree add -b
            _completed_process(stdout="Existing Operator\n"),  # config user.name (already set)
            _completed_process(stdout="op@example.com\n"),  # config user.email (already set)
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        result = ws.ensure_worktree(42)

        assert result == target
        # Verify the worktree-add command CREATED the WIP branch (``-b kanban/ticket-42``).
        mock_runner.assert_any_call(
            [
                "git",
                "-C",
                str(clone),
                "worktree",
                "add",
                "-b",
                "kanban/ticket-42",
                str(target),
                "origin/main",
            ],
            check=True,
            timeout=GIT_TIMEOUT,
        )

    def test_ensure_worktree_reuses_existing_wip_branch(self, tmp_path: Path) -> None:
        """When the WIP branch already EXISTS (a prior stage made it), reuse it WITHOUT ``-b``.

        Hybrid flow (DESIGN §13): the existing ``kanban/ticket-<n>`` carries the prior stage's
        committed artifacts, so the worktree is checked out on it directly (no ``-b``, no base ref)
        — that is how the next stage sees the design/plan commits via the shared ``.git``.
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 42)
        mock_runner = MagicMock()
        # _worktree_paths (no match) → fetch → rev-parse --verify (branch PRESENT, rc=0) → add →
        # _ensure_identity probes (config user.name / user.email — non-empty → already set, no set).
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /some/other/path\n"),
            _completed_process(),  # fetch
            _completed_process(returncode=0),  # rev-parse --verify: WIP branch present
            _completed_process(),  # worktree add (reuse)
            _completed_process(stdout="Existing Operator\n"),  # config user.name (already set)
            _completed_process(stdout="op@example.com\n"),  # config user.email (already set)
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        result = ws.ensure_worktree(42)

        assert result == target
        # The add REUSES the branch (no ``-b``, no ``origin/<base>``).
        mock_runner.assert_any_call(
            [
                "git",
                "-C",
                str(clone),
                "worktree",
                "add",
                str(target),
                "kanban/ticket-42",
            ],
            check=True,
            timeout=GIT_TIMEOUT,
        )
        # And the absent-branch ``-b`` form was NOT issued.
        for call in mock_runner.call_args_list:
            argv = call.args[0]
            assert not (isinstance(argv, list) and "add" in argv and "-b" in argv)

    def test_ensure_worktree_reuses_existing(self, tmp_path: Path) -> None:
        """When the target is already registered, it is returned without re-adding."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 99)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        result = ws.ensure_worktree(99)

        assert result == target
        # Only _worktree_paths was called — no fetch or worktree add.
        assert mock_runner.call_count == 1

    def test_ensure_worktree_custom_base(self, tmp_path: Path) -> None:
        """A non-default base is passed to fetch and the NEW-WIP-branch worktree-add."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /other\n"),
            _completed_process(),  # fetch
            _completed_process(returncode=1),  # rev-parse --verify: WIP branch absent
            _completed_process(),  # worktree add -b
            _completed_process(stdout="Existing Operator\n"),  # config user.name (already set)
            _completed_process(stdout="op@example.com\n"),  # config user.email (already set)
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_worktree(7, base="develop")

        mock_runner.assert_any_call(
            ["git", "-C", str(clone), "fetch", "origin", "develop"],
            check=True,
            timeout=GIT_TIMEOUT,
        )
        mock_runner.assert_any_call(
            [
                "git",
                "-C",
                str(clone),
                "worktree",
                "add",
                "-b",
                "kanban/ticket-7",
                str(_target_for(clone, 7)),
                "origin/develop",
            ],
            check=True,
            timeout=GIT_TIMEOUT,
        )

    # -- ensure_worktree fallback git identity (finding 2 / DESIGN §13) ------

    def test_ensure_worktree_sets_fallback_identity_when_unset(self, tmp_path: Path) -> None:
        """When the clone has NO git identity, ensure_worktree sets the LOCAL fallback.

        The doc stages run ``git commit`` in the worktree (durable cross-stage carry, DESIGN §13);
        ``git commit`` aborts without an identity. ``_ensure_identity`` probes ``user.name`` /
        ``user.email`` (both EMPTY here) and writes the ``kanbanmate`` / ``kanbanmate@localhost``
        fallbacks via ``git config --local``, so the carry commit always succeeds.
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 42)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /other\n"),  # _worktree_paths
            _completed_process(),  # fetch
            _completed_process(returncode=1),  # rev-parse --verify (WIP branch absent)
            _completed_process(),  # worktree add -b
            _completed_process(stdout=""),  # config user.name → empty (unset)
            _completed_process(stdout=""),  # config user.email → empty (unset)
            _completed_process(),  # config --local user.name (fallback set)
            _completed_process(),  # config --local user.email (fallback set)
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        result = ws.ensure_worktree(42)

        assert result == target
        # Both fallbacks were written --local to the clone.
        mock_runner.assert_any_call(
            ["git", "-C", str(clone), "config", "--local", "user.name", "kanbanmate"],
            check=False,
            timeout=GIT_TIMEOUT,
        )
        mock_runner.assert_any_call(
            ["git", "-C", str(clone), "config", "--local", "user.email", "kanbanmate@localhost"],
            check=False,
            timeout=GIT_TIMEOUT,
        )

    def test_ensure_worktree_keeps_existing_identity(self, tmp_path: Path) -> None:
        """When the clone ALREADY has a git identity, ensure_worktree does NOT override it.

        The probe finds a non-empty ``user.name``, so no ``config --local user.name/user.email``
        set call is issued — an operator's global/repo identity is preserved.
        """
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /other\n"),  # _worktree_paths
            _completed_process(),  # fetch
            _completed_process(returncode=1),  # rev-parse --verify (WIP branch absent)
            _completed_process(),  # worktree add -b
            _completed_process(stdout="Existing Operator\n"),  # config user.name (already set)
            _completed_process(stdout="op@example.com\n"),  # config user.email (already set)
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_worktree(42)

        # No fallback SET was issued — the existing identity is untouched.
        for call in mock_runner.call_args_list:
            argv = call.args[0]
            assert not (isinstance(argv, list) and "--local" in argv), (
                "an existing identity must NOT be overridden with the --local fallback"
            )

    def test_ensure_worktree_identity_probe_failure_is_fail_soft(self, tmp_path: Path) -> None:
        """A raising identity probe never aborts the launch (fail-soft).

        ``_ensure_identity`` swallows any subprocess error: the worktree is still returned so a
        flaky ``git config`` probe cannot freeze a launch (a real missing identity surfaces later
        as the commit's own failure, which the agent reports).
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 42)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /other\n"),  # _worktree_paths
            _completed_process(),  # fetch
            _completed_process(returncode=1),  # rev-parse --verify (WIP branch absent)
            _completed_process(),  # worktree add -b
            subprocess.CalledProcessError(1, ["git", "config", "user.name"]),  # probe raises
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        # Must NOT raise — the worktree path is returned despite the probe failure.
        assert ws.ensure_worktree(42) == target

    # -- discover_branch -----------------------------------------------------

    def test_discover_branch_returns_branch_name(self, tmp_path: Path) -> None:
        """When rev-parse returns a named branch, it is returned as-is."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout="feat/my-feature\n")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        branch = ws.discover_branch(10)

        assert branch == "feat/my-feature"

    def test_discover_branch_returns_none_for_head(self, tmp_path: Path) -> None:
        """A detached HEAD (rev-parse returns 'HEAD') is mapped to None."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout="HEAD\n")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        branch = ws.discover_branch(10)

        assert branch is None

    def test_discover_branch_returns_none_for_empty(self, tmp_path: Path) -> None:
        """An empty result from rev-parse is mapped to None."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout="")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        branch = ws.discover_branch(10)

        assert branch is None

    def test_discover_branch_returns_none_for_whitespace_only(self, tmp_path: Path) -> None:
        """A whitespace-only result is mapped to None."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout="   \n")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        branch = ws.discover_branch(10)

        assert branch is None

    def test_discover_branch_gone_worktree_returns_none_not_raise(self, tmp_path: Path) -> None:
        """A GONE worktree (git exit 128) maps to None, never raises (defect 10).

        After a reap teardown removes the worktree and the ticket is re-dragged into PR/CI,
        ``git -C <gone> rev-parse`` exits 128. With ``check=True`` that raised and STRANDED the
        card; now it maps to ``None`` so the caller routes on ``KANBAN_BRANCH=""`` (honest fail).
        """
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(
            returncode=128, stderr="fatal: not a working tree"
        )

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.discover_branch(10) is None

    def test_discover_branch_runner_raises_returns_none_not_propagate(self, tmp_path: Path) -> None:
        """A runner that RAISES (gone worktree / spawn error) is swallowed → None (defect 10)."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.side_effect = subprocess.CalledProcessError(128, ["git"])

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.discover_branch(10) is None

    # -- remove_worktree -----------------------------------------------------

    def test_remove_worktree_without_force(self, tmp_path: Path) -> None:
        """Normal removal does NOT include --force."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 5)
        mock_runner = MagicMock()

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.remove_worktree(5)

        mock_runner.assert_called_once_with(
            ["git", "-C", str(clone), "worktree", "remove", str(target)],
            check=True,
            timeout=GIT_TIMEOUT,
        )

    def test_remove_worktree_with_force(self, tmp_path: Path) -> None:
        """When force=True, --force appears before the target path."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 5)
        mock_runner = MagicMock()

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.remove_worktree(5, force=True)

        mock_runner.assert_called_once_with(
            ["git", "-C", str(clone), "worktree", "remove", "--force", str(target)],
            check=True,
            timeout=GIT_TIMEOUT,
        )

    def test_remove_worktree_default_is_no_force(self, tmp_path: Path) -> None:
        """Calling remove_worktree without explicit force omits --force (the default)."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 5)
        mock_runner = MagicMock()

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.remove_worktree(5)

        argv = mock_runner.call_args[0][0]
        assert "--force" not in argv
        assert argv == ["git", "-C", str(clone), "worktree", "remove", str(target)]

    # -- worktree_exists (phase 28.1 replay-safety probe) --------------------

    def test_worktree_exists_true_when_registered(self, tmp_path: Path) -> None:
        """``worktree_exists`` returns True when the target is in the clone's worktree registry.

        It reads ``git -C <clone> worktree list`` (NEVER ``git -C <worktree>``), so a present
        worktree is detected without any exit-128 risk.
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout=f"worktree {target}\n")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.worktree_exists(7) is True
        # The probe ran against the CLONE registry, never `git -C <worktree>`.
        argv = mock_runner.call_args[0][0]
        assert argv == ["git", "-C", str(clone), "worktree", "list", "--porcelain"]

    def test_worktree_exists_false_when_absent(self, tmp_path: Path) -> None:
        """``worktree_exists`` returns False when the target is NOT in the registry (replay case)."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        # The registry lists only some OTHER worktree — the target is gone.
        mock_runner.return_value = _completed_process(stdout="worktree /some/other/path\n")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.worktree_exists(7) is False

    # -- has_unpushed_work (#9 Done-arrival reclaim guard) --------------------

    def test_has_unpushed_work_false_when_worktree_gone(self, tmp_path: Path) -> None:
        """#9: a missing worktree has nothing to protect → False (the reclaim proceeds)."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout="worktree /other\n")  # target absent

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is False

    def test_has_unpushed_work_true_when_dirty(self, tmp_path: Path) -> None:
        """#9: a dirty working tree (non-empty status) → True (don't destroy uncommitted work)."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),  # worktree_exists → present
            _completed_process(stdout=" M somefile.py\n"),  # status --porcelain → dirty
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is True

    def test_has_unpushed_work_true_when_ahead_of_upstream(self, tmp_path: Path) -> None:
        """#9: clean tree but commits ahead of @{u} → True (unpushed commits)."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),  # worktree_exists
            _completed_process(stdout=""),  # status → clean
            _completed_process(returncode=0, stdout="abc123 a local commit\n"),  # @{u}..HEAD ahead
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is True

    def test_has_unpushed_work_false_when_clean_and_pushed(self, tmp_path: Path) -> None:
        """#9: clean tree and no commits ahead → False (safe to reclaim)."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),  # worktree_exists
            _completed_process(stdout=""),  # status → clean
            _completed_process(returncode=0, stdout=""),  # @{u}..HEAD → not ahead
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is False

    def test_has_unpushed_work_false_when_only_merge_mode_pin(self, tmp_path: Path) -> None:
        """Phase 35: the SOLE dirtiness is the orchestrator's ``**PR merge**:`` pin → ignore it.

        ``ensure_manual_merge_mode`` rewrites IMPLEMENTATION.md's ``**PR merge**:`` line at EVERY
        launch, so a freshly launched but idle worktree always shows `` M IMPLEMENTATION.md``. That
        is the orchestrator's own edit, NOT agent work — it must not false-positive the reclaim.
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        pin_diff = (
            "diff --git a/IMPLEMENTATION.md b/IMPLEMENTATION.md\n"
            "index 1111111..2222222 100644\n"
            "--- a/IMPLEMENTATION.md\n"
            "+++ b/IMPLEMENTATION.md\n"
            "@@ -3,1 +3,1 @@\n"
            "-**PR merge**: auto\n"
            "+**PR merge**: manual\n"
        )
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),  # worktree_exists
            _completed_process(stdout=" M IMPLEMENTATION.md\n"),  # status → only the pin file
            _completed_process(stdout=pin_diff),  # diff → only the pin line changed
            _completed_process(returncode=0, stdout=""),  # @{u}..HEAD → not ahead
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is False

    def test_has_unpushed_work_true_when_pin_plus_real_edit(self, tmp_path: Path) -> None:
        """Phase 35: IMPLEMENTATION.md modified with the pin AND a real edit → True (agent work)."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        mixed_diff = (
            "diff --git a/IMPLEMENTATION.md b/IMPLEMENTATION.md\n"
            "index 1111111..2222222 100644\n"
            "--- a/IMPLEMENTATION.md\n"
            "+++ b/IMPLEMENTATION.md\n"
            "@@ -3,2 +3,2 @@\n"
            "-**PR merge**: auto\n"
            "+**PR merge**: manual\n"
            "+| 35 | a new phase row the agent added |\n"
        )
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),  # worktree_exists
            _completed_process(stdout=" M IMPLEMENTATION.md\n"),  # status → only the pin file
            _completed_process(stdout=mixed_diff),  # diff → pin + a real content edit
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is True

    def test_has_unpushed_work_true_when_other_file_dirty(self, tmp_path: Path) -> None:
        """Phase 35: another modified path alongside the pin file → True (never ignore other work).

        Two porcelain entries means the merge-mode-pin short-circuit must NOT engage — the second
        path is real uncommitted work. The diff is never consulted (the single-entry guard fails
        first), so no diff process is queued.
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),  # worktree_exists
            _completed_process(stdout=" M IMPLEMENTATION.md\n M src/foo.py\n"),  # two dirty paths
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is True

    def test_has_unpushed_work_true_when_pin_only_dirty_but_ahead(self, tmp_path: Path) -> None:
        """Phase 35: pin-only dirty BUT commits ahead of upstream → True (unpushed commits).

        The merge-mode-pin ignore only suppresses the working-tree dirtiness; probe 2 (commits
        ahead) still runs and reports the unpushed commit, so real work is never destroyed.
        """
        clone = tmp_path / "clone"
        target = _target_for(clone, 7)
        pin_diff = (
            "--- a/IMPLEMENTATION.md\n"
            "+++ b/IMPLEMENTATION.md\n"
            "-**PR merge**: auto\n"
            "+**PR merge**: manual\n"
        )
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),  # worktree_exists
            _completed_process(stdout=" M IMPLEMENTATION.md\n"),  # status → only the pin file
            _completed_process(stdout=pin_diff),  # diff → only the pin line changed
            _completed_process(returncode=0, stdout="abc123 a local commit\n"),  # ahead of @{u}
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        assert ws.has_unpushed_work(7) is True

    # -- delete_branch -------------------------------------------------------

    def test_delete_branch_force_deletes_in_clone(self, tmp_path: Path) -> None:
        """delete_branch issues ``git -C <clone> branch -D <branch>`` with check=False."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=0)

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.delete_branch(7, "feat/genesis")

        mock_runner.assert_called_once_with(
            ["git", "-C", str(clone), "branch", "-D", "feat/genesis"],
            check=False,
            timeout=GIT_TIMEOUT,
        )

    def test_delete_branch_noop_for_empty(self, tmp_path: Path) -> None:
        """An empty branch name is a clean no-op (no subprocess call)."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.delete_branch(7, "")

        mock_runner.assert_not_called()

    def test_delete_branch_noop_for_head(self, tmp_path: Path) -> None:
        """A detached ``"HEAD"`` is a clean no-op (no feature branch to delete)."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.delete_branch(7, "HEAD")

        mock_runner.assert_not_called()

    def test_delete_branch_fail_soft_on_missing_branch(self, tmp_path: Path) -> None:
        """A missing branch (git exits 1/128 on a replay) is swallowed — no raise.

        ``check=False`` means git's non-zero exit does not raise; the call still
        returns normally. This is the replay case (the branch was already deleted).
        """
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=128, stderr="branch not found")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        # Must NOT raise.
        ws.delete_branch(7, "feat/gone")

        mock_runner.assert_called_once()

    def test_delete_branch_fail_soft_on_runner_exception(self, tmp_path: Path) -> None:
        """An injected runner that raises is swallowed (defensive fail-soft)."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.side_effect = OSError("git unavailable")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        # Must NOT raise — fail-soft mirrors the PoC ``_soft`` swallow.
        ws.delete_branch(7, "feat/genesis")

        mock_runner.assert_called_once()

    def test_delete_branch_uses_argv_list_no_shell(self, tmp_path: Path) -> None:
        """delete_branch passes an argv list and never sets shell=True."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process()

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.delete_branch(7, "feat/x")

        args, kwargs = mock_runner.call_args
        assert isinstance(args[0], list)
        assert kwargs.get("shell") is not True

    # -- safety (argv lists, no shell) ---------------------------------------

    def test_all_calls_use_argv_lists_no_shell(self, tmp_path: Path) -> None:
        """Every subprocess call must pass an argv list WITHOUT shell=True."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /other\n"),  # _worktree_paths
            _completed_process(),  # fetch
            _completed_process(returncode=1),  # rev-parse --verify (WIP branch absent)
            _completed_process(),  # worktree add -b
            _completed_process(returncode=1),  # config user.name (unset)
            _completed_process(returncode=1),  # config user.email (unset)
            _completed_process(),  # config --local user.name (fallback set)
            _completed_process(),  # config --local user.email (fallback set)
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_worktree(1)

        for call_args in mock_runner.call_args_list:
            args, kwargs = call_args
            # First positional arg must be a list (not a string).
            assert isinstance(args[0], list)
            # shell must not be True.
            assert kwargs.get("shell") is not True

    # -- run_transition_script -----------------------------------------------

    def test_run_transition_script_runs_argv_with_env_cwd_timeout(self, tmp_path: Path) -> None:
        """run_transition_script runs an argv-list subprocess with env, cwd=worktree, timeout.

        Returns ``(returncode, stdout+stderr)``. The relative script path resolves against the
        PACKAGE ROOT (where the shipped ``bin/check-*.sh`` package data lives, PoC
        ``_SKILL_ROOT`` parity, defect 1) — NOT the per-repo clone; the cwd is the per-ticket
        worktree.
        """
        clone = tmp_path / "clone"
        worktree = _target_for(clone, 7)
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=0, stdout="ok\n", stderr="warn\n")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        rc, out = ws.run_transition_script(
            7, "bin/check-pr-ready.sh", {"KANBAN_REPO": "owner/repo", "KANBAN_BRANCH": "feat/x"}
        )

        assert rc == 0
        # stdout and stderr are merged.
        assert out == "ok\nwarn\n"

        # The script ran as an argv list (the resolved absolute path), with cwd=worktree and a
        # timeout, the env merged, and capture_output/text set.
        args, kwargs = mock_runner.call_args
        argv = args[0]
        assert isinstance(argv, list)
        assert argv == [str((_PACKAGE_ROOT / "bin/check-pr-ready.sh").resolve())]
        assert kwargs["cwd"] == str(worktree)
        assert kwargs["timeout"] == 120
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        # The caller env is merged on top of os.environ (caller values present).
        assert kwargs["env"]["KANBAN_REPO"] == "owner/repo"
        assert kwargs["env"]["KANBAN_BRANCH"] == "feat/x"

    def test_run_transition_script_returns_nonzero_exit(self, tmp_path: Path) -> None:
        """A failing check (non-zero exit) is returned, not raised — the exit IS the verdict."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=1, stdout="check failed")

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        rc, out = ws.run_transition_script(7, "bin/check.sh", {})

        assert rc == 1
        assert "check failed" in out

    def test_run_transition_script_absolute_path_used_verbatim(self, tmp_path: Path) -> None:
        """An absolute script path is used verbatim (not re-rooted on the clone)."""
        clone = tmp_path / "clone"
        abs_script = "/usr/local/bin/check.sh"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=0)

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.run_transition_script(7, abs_script, {})

        argv = mock_runner.call_args[0][0]
        assert argv == [abs_script]

    def test_run_transition_script_never_uses_shell(self, tmp_path: Path) -> None:
        """run_transition_script passes an argv list and never sets shell=True."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=0)

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.run_transition_script(7, "bin/check.sh", {})

        args, kwargs = mock_runner.call_args
        assert isinstance(args[0], list)
        assert kwargs.get("shell") is not True

    def test_shipped_check_scripts_resolve_to_existing_package_data(self, tmp_path: Path) -> None:
        """The two shipped gate scripts resolve to files that ACTUALLY exist (defect 1).

        The campaign's PR/CI and Merge gates reference ``bin/check-pr-ready.sh`` /
        ``bin/check-merge-ready.sh`` as relative entries; they must resolve to executable
        package data, not a missing path in the target clone.
        """
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=0)
        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)

        for rel in ("bin/check-pr-ready.sh", "bin/check-merge-ready.sh"):
            ws.run_transition_script(7, rel, {})
            resolved = Path(mock_runner.call_args[0][0][0])
            assert resolved == (_PACKAGE_ROOT / rel).resolve()
            assert resolved.is_file(), f"shipped gate script missing: {resolved}"


# ============================================================================
# UNIT TESTS — ensure_clone
# ============================================================================


class TestEnsureCloneUnit:
    """Unit tests for :meth:`GitWorktreeWorkspace.ensure_clone` with a mock runner."""

    # -- fresh dir, no .git ----------------------------------------------------

    def test_fresh_dir_no_git_init_then_add_origin_then_fetch(self, tmp_path: Path) -> None:
        """A fresh dir with no ``.git`` runs ``git init``, THEN ``remote add``,
        THEN ``fetch`` — in that order, with the correct verb."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        # Probe for origin returns non-zero (missing); fetch returns ok.
        mock_runner.side_effect = [
            _completed_process(),  # git init (no .git yet)
            _completed_process(returncode=1),  # remote get-url origin → missing
            _completed_process(),  # remote add origin <url>
            _completed_process(),  # fetch origin <base>
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        result = ws.ensure_clone("https://github.com/owner/repo.git")

        assert result == clone.resolve()

        # Order: git init → remote get-url (probe) → remote add → fetch
        calls = mock_runner.call_args_list
        assert len(calls) == 4  # init + probe + add + fetch

        # 1. git init
        assert calls[0][0][0] == ["git", "init", str(clone)]
        assert calls[0][1] == {"check": True, "timeout": GIT_TIMEOUT}

        # 2. remote get-url origin (probe)
        assert calls[1][0][0] == [
            "git",
            "-C",
            str(clone),
            "remote",
            "get-url",
            "origin",
        ]
        assert calls[1][1] == {
            "capture_output": True,
            "text": True,
            "check": False,
            "timeout": GIT_TIMEOUT,
        }

        # 3. remote ADD (not set-url — origin was missing)
        assert calls[2][0][0] == [
            "git",
            "-C",
            str(clone),
            "remote",
            "add",
            "origin",
            "https://github.com/owner/repo.git",
        ]
        assert calls[2][1] == {"check": True, "timeout": GIT_TIMEOUT}

        # 4. fetch
        assert calls[3][0][0] == [
            "git",
            "-C",
            str(clone),
            "fetch",
            "origin",
            "main",
        ]
        assert calls[3][1] == {"check": True, "timeout": GIT_TIMEOUT}

    # -- existing clone WITH origin --------------------------------------------

    def test_existing_clone_with_origin_no_init_set_url(self, tmp_path: Path) -> None:
        """When ``.git`` exists and origin is present, NO ``git init`` runs and
        the verb is ``set-url`` (not ``add``)."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # .git exists
        mock_runner = MagicMock()
        # Probe returns 0 → origin exists; fetch returns ok.
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # remote get-url → present
            _completed_process(),  # remote set-url origin <url>
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        result = ws.ensure_clone("https://github.com/owner/repo.git")

        assert result == clone.resolve()

        # No git init — first call is the probe.
        first_call_argv = mock_runner.call_args_list[0][0][0]
        assert "init" not in first_call_argv

        # Second call must be set-url (not add).
        assert mock_runner.call_args_list[1][0][0] == [
            "git",
            "-C",
            str(clone),
            "remote",
            "set-url",
            "origin",
            "https://github.com/owner/repo.git",
        ]

    # -- partial clone (.git present, origin missing) --------------------------

    def test_partial_clone_git_present_origin_missing_self_heals(self, tmp_path: Path) -> None:
        """A partial clone (``.git`` present but origin missing) self-heals:
        NO ``git init``, verb is ``add`` (not ``set-url``)."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # .git exists
        mock_runner = MagicMock()
        # Probe returns non-zero → origin missing (partial clone).
        mock_runner.side_effect = [
            _completed_process(returncode=1),  # remote get-url → missing
            _completed_process(),  # remote add origin <url>
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_clone("https://github.com/owner/repo.git")

        # No git init.
        for call in mock_runner.call_args_list:
            assert "init" not in call[0][0]

        # Verb is "add" (self-heal, not "set-url").
        mock_runner.assert_any_call(
            [
                "git",
                "-C",
                str(clone),
                "remote",
                "add",
                "origin",
                "https://github.com/owner/repo.git",
            ],
            check=True,
            timeout=GIT_TIMEOUT,
        )

    # -- returned path ---------------------------------------------------------

    def test_returns_resolved_clone_path(self, tmp_path: Path) -> None:
        """The return value is ``clone.resolve()``."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # so init is skipped
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        result = ws.ensure_clone("https://github.com/o/r.git")

        assert result == clone.resolve()
        assert isinstance(result, Path)
        assert result.is_absolute()

    # -- token_path=None → no credential calls ---------------------------------

    def test_token_path_none_no_credential_calls(self, tmp_path: Path) -> None:
        """When ``token_path=None``, no ``git config`` credential commands are
        issued — the placeholder is a no-op."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # so init is skipped
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_clone("https://github.com/o/r.git")

        # No git config credential calls anywhere.
        for call in mock_runner.call_args_list:
            argv = call[0][0]
            # "config" should NOT appear with credential-related sub-commands.
            if "config" in argv:
                # If config appears, it must not be credential.*
                flat = " ".join(argv)
                assert "credential" not in flat, f"Unexpected credential config call: {argv}"

    # -- token_path truthy → credential helper (security) -----------------------

    def test_token_path_credential_helper_token_isolation(self, tmp_path: Path) -> None:
        """SECURITY: with *token_path*, origin stays TOKENLESS and a credential
        helper reads the token from the file — the token VALUE must appear in NO
        git argv (never persisted in ``.git/config``).

        Ports the security assertions from PoC
        ``tests/test_worktree_cmd.py:92-121``.
        """
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # .git exists → init skipped
        token_path = tmp_path / "token"
        token_path.write_text("ghp_supersecret")

        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe → origin exists
            _completed_process(),  # remote set-url
            _completed_process(),  # config --replace-all username
            _completed_process(),  # config --replace-all helper ""
            _completed_process(),  # config --add helper <fn>
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_clone(
            "https://github.com/IznoCorp/demo.git",
            token_path=str(token_path),
        )

        # Collect all git argv lists from the mock.
        calls = [call[0][0] for call in mock_runner.call_args_list]

        # (a) origin URL is tokenless — no ``x-access-token:<tok>@`` embedded.
        assert [
            "git",
            "-C",
            str(clone),
            "remote",
            "set-url",
            "origin",
            "https://github.com/IznoCorp/demo.git",
        ] in calls, "origin URL must be the tokenless repo_url"

        # (b) username configured for github.com via --replace-all.
        assert [
            "git",
            "-C",
            str(clone),
            "config",
            "--replace-all",
            "credential.https://github.com.username",
            "x-access-token",
        ] in calls, "credential.username must be set to x-access-token"

        # (c) helper chain is RESET with "" first (via --replace-all).
        assert [
            "git",
            "-C",
            str(clone),
            "config",
            "--replace-all",
            "credential.https://github.com.helper",
            "",
        ] in calls, 'helper chain must be reset with "" first'

        # (d) file helper is --add'ed after the reset, and its value contains
        #     the token FILE PATH (not the token VALUE).
        add_helper_calls = [
            c for c in calls if "--add" in c and c[-2] == "credential.https://github.com.helper"
        ]
        assert add_helper_calls, "credential.helper was not --add'ed after the reset"
        helper_value = add_helper_calls[0][-1]
        assert str(token_path) in helper_value, "helper must reference the token FILE PATH"

        # (e) The secret token VALUE must not leak into ANY git argv.
        assert not any("ghp_supersecret" in part for c in calls for part in c), (
            "token VALUE leaked into git argv — it would land in .git/config"
        )

        # (f) Order: "" reset FIRST, THEN --add file helper SECOND.
        helper_indices = [
            i
            for i, c in enumerate(calls)
            if "config" in c and "credential.https://github.com.helper" in c
        ]
        assert len(helper_indices) == 2, (
            f"Expected 2 helper config calls, got {len(helper_indices)}"
        )
        assert helper_indices[0] < helper_indices[1], "reset must come before --add"
        assert calls[helper_indices[0]][-1] == "", 'first helper call must be the "" reset'
        assert "--add" in calls[helper_indices[1]], "second helper call must be --add"

    # -- safety: argv lists, no shell ------------------------------------------

    def test_all_git_calls_are_argv_lists_no_shell(self, tmp_path: Path) -> None:
        """Every git call must pass an argv list WITHOUT ``shell=True``."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # so init is skipped
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_clone("https://github.com/o/r.git")

        for call_args in mock_runner.call_args_list:
            args, kwargs = call_args
            assert isinstance(args[0], list), f"Expected list, got {type(args[0])}"
            assert kwargs.get("shell") is not True

    # -- custom base -----------------------------------------------------------

    def test_custom_base_passed_to_fetch(self, tmp_path: Path) -> None:
        """A non-default *base* is passed to the ``fetch`` command."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # so init is skipped
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner)
        ws.ensure_clone("https://github.com/o/r.git", base="develop")

        # The last call must be the fetch with the custom base.
        fetch_call = mock_runner.call_args_list[-1]
        assert fetch_call[0][0] == [
            "git",
            "-C",
            str(clone),
            "fetch",
            "origin",
            "develop",
        ]


# ============================================================================
# UNIT TESTS — resource_lock (per-repo flock serialising clone mutations)
# ============================================================================


class TestResourceLock:
    """Unit tests for the per-repo advisory-lock context manager (14.3)."""

    # -- lock file creation ---------------------------------------------------

    def test_ensure_clone_creates_resource_lock_file(self, tmp_path: Path) -> None:
        """ensure_clone with ``repo="owner/name"`` creates the sanified lock file."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)  # skip init
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe → origin exists
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(
            clone_dir=clone, runner=mock_runner, repo="IznoCorp/demo", kanban_root=tmp_path
        )
        ws.ensure_clone("https://github.com/IznoCorp/demo.git")

        lock_path = tmp_path / "locks" / "repo__IznoCorp_demo.lock"
        assert lock_path.exists(), f"Lock file not created at {lock_path}"

    def test_ensure_worktree_creates_resource_lock_file(self, tmp_path: Path) -> None:
        """ensure_worktree with ``repo="owner/name"`` creates the sanified lock file."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /other\n"),
            _completed_process(),  # fetch (inside lock)
            _completed_process(returncode=1),  # rev-parse --verify (WIP branch absent)
            _completed_process(),  # worktree add -b (inside lock)
            _completed_process(stdout="op\n"),  # config user.name (already set)
            _completed_process(stdout="op@x\n"),  # config user.email (already set)
        ]

        ws = GitWorktreeWorkspace(
            clone_dir=clone, runner=mock_runner, repo="IznoCorp/demo", kanban_root=tmp_path
        )
        ws.ensure_worktree(42)

        lock_path = tmp_path / "locks" / "repo__IznoCorp_demo.lock"
        assert lock_path.exists(), f"Lock file not created at {lock_path}"

    # -- resource name sanitisation -------------------------------------------

    def test_resource_name_sanitises_slashes(self, tmp_path: Path) -> None:
        """The lock sanitiser turns ``owner/name`` → ``owner_name`` in the file name."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(
            clone_dir=clone, runner=mock_runner, repo="owner/name", kanban_root=tmp_path
        )
        ws.ensure_clone("https://github.com/owner/name.git")

        # The sanitiser replaces "/" with "_", so "repo__owner/name" → "repo__owner_name"
        lock_path = tmp_path / "locks" / "repo__owner_name.lock"
        assert lock_path.exists(), f"Expected lock at {lock_path} (slashes sanified to underscores)"

    # -- repo="" fallback -----------------------------------------------------

    def test_repo_resource_falls_back_to_clone_basename(self, tmp_path: Path) -> None:
        """When ``repo=""``, the lock resource name falls back to the clone basename."""
        clone = tmp_path / "my-clone"
        ws = GitWorktreeWorkspace(clone_dir=clone, repo="")
        assert ws._repo_resource() == "repo__my-clone"

    def test_repo_empty_uses_clone_name_in_lock_path(self, tmp_path: Path) -> None:
        """When ``repo=""``, the lock file is named after the clone dir."""
        clone = tmp_path / "my-clone"
        (clone / ".git").mkdir(parents=True)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(
            clone_dir=clone, runner=mock_runner, repo="", kanban_root=tmp_path
        )
        ws.ensure_clone("https://github.com/owner/repo.git")

        lock_path = tmp_path / "locks" / "repo__my-clone.lock"
        assert lock_path.exists(), f"Lock file not created at {lock_path}"

    # -- lock release after block ---------------------------------------------

    def test_resource_lock_released_after_ensure_clone(self, tmp_path: Path) -> None:
        """After ensure_clone returns, the lock is released so a second acquire
        with LOCK_NB succeeds without blocking."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(
            clone_dir=clone, runner=mock_runner, repo="o/r", kanban_root=tmp_path
        )
        ws.ensure_clone("https://github.com/o/r.git")

        lock_path = tmp_path / "locks" / "repo__o_r.lock"
        assert lock_path.exists()

        # A second acquire with LOCK_NB must succeed (non-blocking) — the lock
        # was released by the finally block in _resource_lock.
        with open(lock_path, "a+") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def test_resource_lock_released_after_ensure_worktree(self, tmp_path: Path) -> None:
        """After ensure_worktree returns, the lock is released so a second
        acquire with LOCK_NB succeeds without blocking."""
        clone = tmp_path / "clone"
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout="worktree /other\n"),
            _completed_process(),  # fetch
            _completed_process(returncode=1),  # rev-parse --verify (WIP branch absent)
            _completed_process(),  # worktree add -b
            _completed_process(stdout="op\n"),  # config user.name (already set)
            _completed_process(stdout="op@x\n"),  # config user.email (already set)
        ]

        ws = GitWorktreeWorkspace(
            clone_dir=clone, runner=mock_runner, repo="o/r", kanban_root=tmp_path
        )
        ws.ensure_worktree(42)

        lock_path = tmp_path / "locks" / "repo__o_r.lock"
        assert lock_path.exists()

        with open(lock_path, "a+") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    # -- read-only paths are NOT locked ---------------------------------------

    def test_ensure_worktree_reuses_existing_no_lock(self, tmp_path: Path) -> None:
        """When the worktree already exists (read-only path), no lock file is
        created — only the mutating path acquires the lock."""
        clone = tmp_path / "clone"
        target = _target_for(clone, 99)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(stdout=f"worktree {target}\n"),
        ]

        ws = GitWorktreeWorkspace(
            clone_dir=clone, runner=mock_runner, repo="o/r", kanban_root=tmp_path
        )
        ws.ensure_worktree(99)

        # Early return: no lock file is created because the mutating path
        # (fetch + worktree add) is never reached.
        lock_path = tmp_path / "locks" / "repo__o_r.lock"
        assert not lock_path.exists(), (
            "Lock file should not be created for the read-only (existing) path"
        )

    # -- default kanban_root is clone parent ----------------------------------

    def test_default_kanban_root_is_clone_parent(self, tmp_path: Path) -> None:
        """When kanban_root is not passed, the lock dir is created under the
        clone's parent directory."""
        clone = tmp_path / "clone"
        (clone / ".git").mkdir(parents=True)
        mock_runner = MagicMock()
        mock_runner.side_effect = [
            _completed_process(returncode=0),  # probe
            _completed_process(),  # set-url
            _completed_process(),  # fetch
        ]

        ws = GitWorktreeWorkspace(clone_dir=clone, runner=mock_runner, repo="o/r")
        ws.ensure_clone("https://github.com/o/r.git")

        # Default kanban_root = clone.parent = tmp_path
        lock_path = tmp_path / "locks" / "repo__o_r.lock"
        assert lock_path.exists(), f"Lock file not created at {lock_path}"


# ============================================================================
# UNIT TESTS — TmuxSessions
# ============================================================================


class TestTmuxSessionsUnit:
    """Unit tests for :class:`TmuxSessions` with a mock subprocess runner."""

    # -- launch ---------------------------------------------------------------

    def test_launch_returns_session_name(self) -> None:
        """launch returns the name that was passed in."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        result = sessions.launch("ticket-42", "/tmp/worktrees/ticket-42", "claude --resume abc")

        assert result == "ticket-42"

    def test_launch_creates_detached_session(self) -> None:
        """launch calls tmux new-session -d with the correct name and cwd."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        sessions.launch("my-session", "/home/user/project", "echo hi")

        mock_runner.assert_any_call(
            ["tmux", "new-session", "-d", "-s", "my-session", "-c", "/home/user/project"],
            check=True,
        )

    def test_launch_sends_command_literally_then_enter(self) -> None:
        """The command is sent with send-keys -l (literal) followed by Enter."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        sessions.launch("sess", "/tmp/wt", "claude --dangerously-bypass-permissions")

        # First send-keys: literal command text.
        mock_runner.assert_any_call(
            [
                "tmux",
                "send-keys",
                "-t",
                "sess",
                "-l",
                "--",
                "claude --dangerously-bypass-permissions",
            ],
            check=True,
        )
        # Second send-keys: Enter key.
        mock_runner.assert_any_call(
            ["tmux", "send-keys", "-t", "sess", "Enter"],
            check=True,
        )

    def test_launch_kills_stale_same_named_session_before_new_session(self) -> None:
        """IDEMPOTENT LAUNCH (phase-27 §A): a pre-existing same-named session is killed FIRST.

        A leftover/stale session (e.g. an old churning agent's) must never block the launch — the
        live #91 e2e bug where ``tmux new-session -s ticket-91`` exited 1 because the session
        already existed. The pre-launch kill runs ``kill-session`` with ``check=False`` (tolerant of
        "no such session") and MUST precede the ``new-session``.
        """
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        sessions.launch("ticket-91", "/tmp/worktrees/ticket-91", "claude --resume abc")

        argvs = [c.args[0] for c in mock_runner.call_args_list]
        # The tolerant pre-launch kill is issued (check=False so an absent session is a no-op).
        mock_runner.assert_any_call(
            ["tmux", "kill-session", "-t", "ticket-91"],
            check=False,
        )
        # The kill PRECEDES the new-session (the leftover session is torn down before re-creating).
        kill_idx = argvs.index(["tmux", "kill-session", "-t", "ticket-91"])
        new_idx = argvs.index(
            ["tmux", "new-session", "-d", "-s", "ticket-91", "-c", "/tmp/worktrees/ticket-91"]
        )
        assert kill_idx < new_idx, "the stale-session kill must precede the new-session"

    def test_launch_with_no_prior_session_tolerant_kill_is_noop_then_creates(self) -> None:
        """A first launch (no prior session) does NOT error on the tolerant pre-launch kill.

        With ``check=False`` the runner is never raised against — tmux's non-zero "no such session"
        exit is swallowed — and the launch proceeds to ``new-session`` + the literal command + Enter.
        """
        mock_runner = MagicMock()
        # The pre-launch kill exits non-zero (no session yet); check=False means it does NOT raise.
        mock_runner.return_value = _completed_process(returncode=1, stderr="can't find session")
        # No-op sleeper so the shell-readiness poll does not real-sleep when the mock pane is empty.
        sessions = TmuxSessions(runner=mock_runner, sleeper=lambda _s: None)

        # Must NOT raise — the tolerant kill swallows the no-session exit.
        result = sessions.launch("ticket-7", "/tmp/wt", "echo hi")

        assert result == "ticket-7"
        # The pre-launch kill ran tolerantly (check=False), then new-session proceeded.
        mock_runner.assert_any_call(["tmux", "kill-session", "-t", "ticket-7"], check=False)
        mock_runner.assert_any_call(
            ["tmux", "new-session", "-d", "-s", "ticket-7", "-c", "/tmp/wt"],
            check=True,
        )

    def test_launch_preserves_special_characters_in_command(self) -> None:
        """The literal send-keys preserves slashes, quotes, and special chars."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner, sleeper=lambda _s: None)

        sessions.launch("s", "/d", "/implement:phase --codename 'my-feat'")

        mock_runner.assert_any_call(
            ["tmux", "send-keys", "-t", "s", "-l", "--", "/implement:phase --codename 'my-feat'"],
            check=True,
        )

    def test_launch_waits_for_shell_ready_before_sending_command(self) -> None:
        """The launch polls capture-pane until the shell rendered before typing (first-char race).

        ``tmux new-session -d`` returns before the interactive shell has printed its prompt; an
        immediate send-keys drops the leading character (the live ``export`` → ``xport`` failure).
        The launch must capture-pane until the pane is NON-EMPTY (the shell printed its prompt) and
        only THEN send-keys the command — so the command's first char is never dropped. Here the
        first two capture probes return an empty pane; the third returns a rendered prompt.
        """
        calls: list[list[str]] = []
        captures = iter(["", "", "➜  ticket-7"])  # empty, empty, then the shell prompt rendered

        def runner(argv, **_kw):  # type: ignore[no-untyped-def]
            calls.append(argv)
            if argv[:2] == ["tmux", "capture-pane"]:
                return _completed_process(stdout=next(captures, "➜  ready"))
            return _completed_process()

        sleeps: list[float] = []
        sessions = TmuxSessions(runner=runner, sleeper=sleeps.append)

        sessions.launch("ticket-7", "/tmp/wt", "export PATH=/x:$PATH; claude")

        # The command send-keys MUST come AFTER at least one capture-pane probe (shell-ready gate).
        send_idx = next(
            i for i, a in enumerate(calls) if a[:2] == ["tmux", "send-keys"] and "-l" in a
        )
        first_capture_idx = next(
            i for i, a in enumerate(calls) if a[:2] == ["tmux", "capture-pane"]
        )
        assert first_capture_idx < send_idx, "the command was sent before any shell-ready probe"
        # The command's literal send carries the FULL command (leading 'export' intact, not 'xport').
        cmd_send = calls[send_idx]
        assert cmd_send[-1] == "export PATH=/x:$PATH; claude"
        # It polled (slept) while the pane was empty, then proceeded once it rendered.
        assert len(sleeps) >= 1

    # -- capture --------------------------------------------------------------

    def test_capture_returns_pane_stdout(self) -> None:
        """capture returns the active pane's stdout (tmux capture-pane -p -J)."""
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout="│ > Welcome to Claude\n")
        sessions = TmuxSessions(runner=mock_runner)

        out = sessions.capture("ticket-7")

        assert out == "│ > Welcome to Claude\n"
        mock_runner.assert_called_once_with(
            ["tmux", "capture-pane", "-p", "-J", "-t", "ticket-7"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_capture_empty_stdout_returns_empty_string(self) -> None:
        """A None/empty stdout from the runner maps to ``""`` (never None)."""
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(stdout="")
        sessions = TmuxSessions(runner=mock_runner)

        assert sessions.capture("ticket-7") == ""

    # -- send_text ------------------------------------------------------------

    def test_send_text_literal_no_enter(self) -> None:
        """send_text(literal=True) sends raw text via -l -- and presses NO Enter by default."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        sessions.send_text("ticket-7", "/implement:phase #7", literal=True)

        mock_runner.assert_called_once_with(
            ["tmux", "send-keys", "-t", "ticket-7", "-l", "--", "/implement:phase #7"],
            check=True,
        )

    def test_send_text_literal_with_enter(self) -> None:
        """send_text(enter=True) sends the literal text THEN a separate Enter key event."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        sessions.send_text("ticket-7", "the prompt", literal=True, enter=True)

        # First call: literal text. Second call: a separate Enter key event.
        assert mock_runner.call_args_list[0].args[0] == [
            "tmux",
            "send-keys",
            "-t",
            "ticket-7",
            "-l",
            "--",
            "the prompt",
        ]
        assert mock_runner.call_args_list[1].args[0] == [
            "tmux",
            "send-keys",
            "-t",
            "ticket-7",
            "Enter",
        ]

    def test_send_text_key_name_not_literal(self) -> None:
        """send_text(literal=False) sends a tmux key NAME (e.g. Enter), not raw -l text."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        sessions.send_text("ticket-7", "Enter", literal=False)

        mock_runner.assert_called_once_with(
            ["tmux", "send-keys", "-t", "ticket-7", "Enter"],
            check=True,
        )

    def test_send_text_large_literal_is_chunked(self) -> None:
        """A large literal prompt is split into <= _SEND_CHUNK_SIZE-char send-keys writes (#helm5).

        A single huge send-keys write can fail under load (the helm #5 launch abort); chunking keeps
        every write small. The concatenation of the chunks must equal the original payload exactly.
        """
        from kanbanmate.adapters.workspace.sessions import _SEND_CHUNK_SIZE

        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)
        big = "x" * (_SEND_CHUNK_SIZE * 2 + 17)  # 2 full chunks + a remainder

        sessions.send_text("ticket-7", big, literal=True)

        argvs = [c.args[0] for c in mock_runner.call_args_list]
        assert len(argvs) == 3  # ceil((2*N+17)/N) = 3 chunks
        sent = ""
        for argv in argvs:
            assert argv[:6] == ["tmux", "send-keys", "-t", "ticket-7", "-l", "--"]
            assert len(argv[6]) <= _SEND_CHUNK_SIZE
            sent += argv[6]
        assert sent == big  # lossless: chunks reconstruct the exact prompt

    def test_send_text_literal_retries_transient_send_failure(self) -> None:
        """A transient send-keys CalledProcessError is RETRIED (not propagated) so a launch survives.

        The launch's prompt delivery must not abort on a momentary send-keys failure (helm #5). The
        chunk is re-sent after a backoff; the second attempt succeeds.
        """
        import subprocess

        calls = {"n": 0}

        def flaky_runner(argv, **kwargs):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            if calls["n"] == 1:
                raise subprocess.CalledProcessError(1, argv)
            return MagicMock(returncode=0)

        sleeps: list[float] = []
        sessions = TmuxSessions(runner=flaky_runner, sleeper=sleeps.append)

        sessions.send_text("ticket-7", "the prompt", literal=True)

        assert calls["n"] == 2  # failed once, retried once, succeeded
        assert len(sleeps) == 1  # one backoff between the two attempts

    def test_send_text_literal_propagates_persistent_send_failure(self) -> None:
        """A send-keys failure that never recovers propagates after the retry budget is spent."""
        import subprocess

        from kanbanmate.adapters.workspace.sessions import _SEND_CHUNK_RETRIES

        def always_fails(argv, **kwargs):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(1, argv)

        attempts: list[float] = []
        sessions = TmuxSessions(runner=always_fails, sleeper=attempts.append)

        with pytest.raises(subprocess.CalledProcessError):
            sessions.send_text("ticket-7", "the prompt", literal=True)
        # _SEND_CHUNK_RETRIES attempts → _SEND_CHUNK_RETRIES - 1 backoffs before the final raise.
        assert len(attempts) == _SEND_CHUNK_RETRIES - 1

    # -- is_alive -------------------------------------------------------------

    def test_is_alive_true_when_returncode_zero(self) -> None:
        """has-session returning 0 means the session exists."""
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=0)

        sessions = TmuxSessions(runner=mock_runner)
        assert sessions.is_alive("ticket-1") is True

        mock_runner.assert_called_once_with(
            ["tmux", "has-session", "-t", "ticket-1"],
            capture_output=True,
            text=True,
        )

    def test_is_alive_false_when_returncode_nonzero(self) -> None:
        """has-session returning non-zero means the session is absent."""
        mock_runner = MagicMock()
        mock_runner.return_value = _completed_process(returncode=1)

        sessions = TmuxSessions(runner=mock_runner)
        assert sessions.is_alive("gone-session") is False

    # -- kill -----------------------------------------------------------------

    def test_kill_calls_tmux_kill_session(self) -> None:
        """kill invokes tmux kill-session with the correct session name."""
        mock_runner = MagicMock()
        sessions = TmuxSessions(runner=mock_runner)

        sessions.kill("ticket-7")

        mock_runner.assert_called_once_with(
            ["tmux", "kill-session", "-t", "ticket-7"],
            check=True,
        )

    def test_end_session_robust_sequence_in_order(self) -> None:
        """end_session (firm-exit) sends Escape→C-u→C-d→C-d→Enter, with delays, NEVER kill-session.

        The robust exit closes any open slash-command menu (Escape), clears the input line (C-u),
        then EOFs TWICE (surfacing claude v2.1.x's background-shell exit MENU), then presses Enter to
        CONFIRM the highlighted "Exit anyway" option — a second C-d does NOT confirm that menu, so
        without the trailing Enter a finished agent with background shells stays stuck at the dialog
        forever (reproduced live: #5's plan stage). Each send-keys is a tmux KEY NAME (no ``-l``) and
        ``check=True``; the four delays go through the injected sleeper in order; and there is NO
        kill-session (the trailing ``; kanban-session-end`` must still run).
        """
        mock_runner = MagicMock()
        mock_sleeper = MagicMock()
        sessions = TmuxSessions(runner=mock_runner, sleeper=mock_sleeper)

        sessions.end_session("ticket-7")

        argvs = [c.args[0] for c in mock_runner.call_args_list]
        # Exactly five send-keys events, in order: Escape, C-u, C-d, C-d, Enter (each a KEY NAME).
        assert argvs == [
            ["tmux", "send-keys", "-t", "ticket-7", "Escape"],
            ["tmux", "send-keys", "-t", "ticket-7", "C-u"],
            ["tmux", "send-keys", "-t", "ticket-7", "C-d"],
            ["tmux", "send-keys", "-t", "ticket-7", "C-d"],
            ["tmux", "send-keys", "-t", "ticket-7", "Enter"],
        ]
        # Every send-keys is check=True (no swallowed failures on the exit path).
        for call in mock_runner.call_args_list:
            assert call.kwargs.get("check") is True
        # CRUCIAL: no kill-session — that would prevent the trailing wrapper from firing.
        assert not any("kill-session" in argv for argv in argvs)
        # The four delays fired in order (menu close → line clear → confirm-EOF → menu-confirm).
        assert [c.args[0] for c in mock_sleeper.call_args_list] == [
            _END_MENU_DELAY,
            _END_CLEAR_DELAY,
            _END_CONFIRM_DELAY,
            _END_MENU_CONFIRM_DELAY,
        ]

    def test_end_session_uses_no_real_sleep_offline(self) -> None:
        """The injected fake sleeper proves end_session pays ZERO real wall time offline.

        Every delay routes through the ``sleeper`` seam (not ``time.sleep``), so the unit suite runs
        the robust sequence with no real waiting. The fake records three calls (one per delay).
        """
        mock_runner = MagicMock()
        sleeps: list[float] = []
        sessions = TmuxSessions(runner=mock_runner, sleeper=sleeps.append)

        sessions.end_session("ticket-7")

        assert sleeps == [
            _END_MENU_DELAY,
            _END_CLEAR_DELAY,
            _END_CONFIRM_DELAY,
            _END_MENU_CONFIRM_DELAY,
        ]

    # -- kill_repl_process (escalation primitive) ----------------------------

    def test_kill_repl_process_sigkills_pane_child_not_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """kill_repl_process SIGKILLs the SINGLE claude REPL child — never kill-session, never the shell.

        Resolves the pane shell PID via ``tmux list-panes`` (4242), finds its sole child via
        ``pgrep -P 4242`` (4243), comm-verifies it IS claude (``ps -o comm= -p 4243`` → ``claude``),
        and sends SIGKILL to 4243 — the claude REPL. SIGKILL (not SIGTERM) is the guaranteed-
        termination escalation: a finished REPL with a background shell traps/survives SIGTERM. It
        must NOT kill the tmux session (the surviving shell runs ``; kanban-session-end``) nor the
        shell PID itself.
        """

        def _runner(argv: list[str], **_kwargs: object) -> MagicMock:
            res = MagicMock()
            if argv[:2] == ["tmux", "list-panes"]:
                res.stdout = "4242\n"
            elif argv[:1] == ["pgrep"]:
                res.stdout = "4243\n"
            elif argv[:3] == ["ps", "-o", "comm="]:
                res.stdout = "claude\n"  # the sole child IS the claude REPL
            else:
                res.stdout = ""
            return res

        mock_runner = MagicMock(side_effect=_runner)
        sessions = TmuxSessions(runner=mock_runner)
        mock_kill = MagicMock()
        monkeypatch.setattr("kanbanmate.adapters.workspace.sessions.os.kill", mock_kill)

        sessions.kill_repl_process("ticket-7")

        mock_kill.assert_called_once_with(4243, signal.SIGKILL)
        argvs = [c.args[0] for c in mock_runner.call_args_list]
        assert not any("kill-session" in argv for argv in argvs)

    def test_kill_repl_process_skips_single_non_claude_child(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """kill_repl_process does NOT SIGKILL a SINGLE child that is NOT claude (the teardown guard).

        Adversarial-review fix: at escalation time claude may have ALREADY exited, leaving the
        surviving shell running ``; kanban-session-end`` (teardown) as its SOLE child. The old code
        returned ``children[0]`` unconditionally for a single child and would SIGKILL that teardown
        process. The comm-verify guard now runs in the single-child path too: the sole child
        (``kanban-session-end``) is NOT claude → ``_child_pid`` returns ``None`` → no ``os.kill``.
        """

        def _runner(argv: list[str], **_kwargs: object) -> MagicMock:
            res = MagicMock()
            if argv[:2] == ["tmux", "list-panes"]:
                res.stdout = "4242\n"
            elif argv[:1] == ["pgrep"]:
                res.stdout = "4243\n"  # a single child …
            elif argv[:3] == ["ps", "-o", "comm="]:
                res.stdout = "kanban-session-end\n"  # … but it is the teardown, NOT claude
            else:
                res.stdout = ""
            return res

        sessions = TmuxSessions(runner=MagicMock(side_effect=_runner))
        mock_kill = MagicMock()
        monkeypatch.setattr("kanbanmate.adapters.workspace.sessions.os.kill", mock_kill)

        sessions.kill_repl_process("ticket-7")  # must not raise

        # CRUCIAL: the lone non-claude child is NEVER signalled (no killing the teardown mid-flight).
        mock_kill.assert_not_called()

    def test_kill_repl_process_failsoft_when_pane_unresolved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """kill_repl_process is a no-op (no os.kill) when the pane PID cannot be resolved."""

        def _runner(argv: list[str], **_kwargs: object) -> MagicMock:
            res = MagicMock()
            res.stdout = ""  # list-panes returns nothing → pane gone
            return res

        sessions = TmuxSessions(runner=MagicMock(side_effect=_runner))
        mock_kill = MagicMock()
        monkeypatch.setattr("kanbanmate.adapters.workspace.sessions.os.kill", mock_kill)

        sessions.kill_repl_process("ticket-7")  # must not raise

        mock_kill.assert_not_called()

    def test_kill_repl_process_failsoft_when_no_child(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """kill_repl_process is a no-op (no os.kill) when the shell has no resolvable child.

        ``pgrep`` AND the ``ps`` fallback both return nothing → no claude REPL to kill.
        """

        def _runner(argv: list[str], **_kwargs: object) -> MagicMock:
            res = MagicMock()
            if argv[:2] == ["tmux", "list-panes"]:
                res.stdout = "4242\n"
            else:
                res.stdout = ""  # pgrep + ps fallback both empty
            return res

        sessions = TmuxSessions(runner=MagicMock(side_effect=_runner))
        mock_kill = MagicMock()
        monkeypatch.setattr("kanbanmate.adapters.workspace.sessions.os.kill", mock_kill)

        sessions.kill_repl_process("ticket-7")

        mock_kill.assert_not_called()

    def test_kill_repl_process_failsoft_on_oskill_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """kill_repl_process swallows an os.kill error (the child raced away) — no raise."""

        def _runner(argv: list[str], **_kwargs: object) -> MagicMock:
            res = MagicMock()
            if argv[:2] == ["tmux", "list-panes"]:
                res.stdout = "4242\n"
            elif argv[:1] == ["pgrep"]:
                res.stdout = "4243\n"
            elif argv[:3] == ["ps", "-o", "comm="]:
                res.stdout = "claude\n"  # comm-verify passes so os.kill is reached
            else:
                res.stdout = ""
            return res

        sessions = TmuxSessions(runner=MagicMock(side_effect=_runner))
        monkeypatch.setattr(
            "kanbanmate.adapters.workspace.sessions.os.kill",
            MagicMock(side_effect=ProcessLookupError("gone")),
        )

        sessions.kill_repl_process("ticket-7")  # must not raise

    def test_kill_repl_process_failsoft_on_runner_error(self) -> None:
        """kill_repl_process swallows a runner exception while resolving the pane PID — no raise."""
        mock_runner = MagicMock(side_effect=RuntimeError("tmux server unreachable"))
        sessions = TmuxSessions(runner=mock_runner)

        sessions.kill_repl_process("ticket-7")  # must not raise

    # -- repl_alive (Candidate 2 done-exit idempotency probe) ----------------

    def test_repl_alive_true_when_claude_child_present(self) -> None:
        """repl_alive returns True when the pane shell hosts a comm-verified claude child."""

        def _runner(argv: list[str], **_kwargs: object) -> MagicMock:
            res = MagicMock()
            if argv[:2] == ["tmux", "list-panes"]:
                res.stdout = "4242\n"
            elif argv[:1] == ["pgrep"]:
                res.stdout = "4243\n"
            elif argv[:3] == ["ps", "-o", "comm="]:
                res.stdout = "claude\n"
            else:
                res.stdout = ""
            return res

        sessions = TmuxSessions(runner=MagicMock(side_effect=_runner))
        assert sessions.repl_alive("ticket-7") is True

    def test_repl_alive_false_when_child_is_not_claude(self) -> None:
        """repl_alive returns False when the sole child is the teardown (claude already exited)."""

        def _runner(argv: list[str], **_kwargs: object) -> MagicMock:
            res = MagicMock()
            if argv[:2] == ["tmux", "list-panes"]:
                res.stdout = "4242\n"
            elif argv[:1] == ["pgrep"]:
                res.stdout = "4243\n"
            elif argv[:3] == ["ps", "-o", "comm="]:
                res.stdout = "kanban-session-end\n"  # the REPL already exited
            else:
                res.stdout = ""
            return res

        sessions = TmuxSessions(runner=MagicMock(side_effect=_runner))
        assert sessions.repl_alive("ticket-7") is False

    def test_repl_alive_false_when_pane_unresolved(self) -> None:
        """repl_alive returns False (fail-soft) when the pane PID cannot be resolved."""
        sessions = TmuxSessions(runner=MagicMock(return_value=MagicMock(stdout="")))
        assert sessions.repl_alive("ticket-7") is False

    def test_repl_alive_false_on_runner_error(self) -> None:
        """repl_alive returns False (fail-soft) when the runner raises — never propagates."""
        sessions = TmuxSessions(runner=MagicMock(side_effect=RuntimeError("tmux down")))
        assert sessions.repl_alive("ticket-7") is False

    # -- safety (argv lists, no shell) ---------------------------------------

    def test_all_tmux_calls_use_argv_lists_no_shell(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every tmux call must pass an argv list WITHOUT shell=True."""
        mock_runner = MagicMock()
        # list-panes/pgrep return parseable stdout so kill_repl_process traverses its argv seams.
        mock_runner.return_value.stdout = "4242\n"
        sessions = TmuxSessions(runner=mock_runner, sleeper=lambda _s: None)
        monkeypatch.setattr("kanbanmate.adapters.workspace.sessions.os.kill", MagicMock())

        sessions.launch("s", "/d", "cmd")
        sessions.capture("s")
        sessions.send_text("s", "txt", literal=True, enter=True)
        sessions.is_alive("s")
        sessions.kill("s")
        sessions.end_session("s")
        sessions.repl_alive("s")
        sessions.kill_repl_process("s")

        for call_args in mock_runner.call_args_list:
            args, kwargs = call_args
            assert isinstance(args[0], list)
            assert kwargs.get("shell") is not True


# ============================================================================
# LOCAL-REAL TESTS — real tmux + git (opt-in, skipped by default)
# ============================================================================


_LOCAL_REAL_REASON = "opt-in: set KANBAN_LOCAL_REAL=1 to run real tmux/git tests"


@pytest.mark.local_real
@pytest.mark.skipif(not os.environ.get("KANBAN_LOCAL_REAL"), reason=_LOCAL_REAL_REASON)
class TestWorktreeLocalReal:
    """Real git worktree lifecycle in a throwaway temp repository.

    These tests create a real git repo, exercise ensure/remove/discover,
    and clean up afterwards. They require ``git`` on PATH.
    """

    def test_ensure_discover_remove_cycle(self, tmp_path: Path) -> None:
        """Full lifecycle: create worktree on the WIP branch, discover its name, remove.

        Hybrid flow (DESIGN §13): the fresh worktree is checked out on ``kanban/ticket-<n>`` (not
        a detached HEAD), so ``discover_branch`` returns the WIP branch name. ``origin`` points at
        the clone's own first commit so the in-method ``git fetch origin main`` resolves.
        """
        clone = tmp_path / "clone"
        clone.mkdir()
        subprocess.run(["git", "-C", str(clone), "init", "-b", "main"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.email", "test@kanbanmate.local"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.name", "KanbanMate Test"],
            check=True,
        )
        (clone / "README.md").write_text("# test\n")
        subprocess.run(["git", "-C", str(clone), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "commit", "-m", "initial"],
            check=True,
        )
        # The in-method ``git fetch origin main`` needs an origin → point it at the clone itself.
        subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", str(clone)], check=True)

        ws = GitWorktreeWorkspace(clone_dir=clone)

        # ensure_worktree on the WIP branch
        target = ws.ensure_worktree(42)
        assert target.exists()
        assert (target / "README.md").exists()

        # discover_branch now returns the per-ticket WIP branch name (DESIGN §13).
        branch = ws.discover_branch(42)
        assert branch == "kanban/ticket-42"

        # remove_worktree (normal, no force)
        ws.remove_worktree(42)
        assert not target.exists()

    def test_ensure_worktree_carries_commits_across_recreated_worktree(
        self, tmp_path: Path
    ) -> None:
        """INTEGRATION (DESIGN §13): a commit on the WIP branch in worktree A is visible in B.

        The durable cross-stage carry: stage N commits ``docs/features/<codename>/`` to the shared
        ``kanban/ticket-<n>`` branch in its worktree; stage N+1 gets a FRESH worktree (after the
        first is removed) re-using the SAME branch, and sees the committed file in its working tree
        — proving the carry without any push (worktrees share one ``.git``).
        """
        clone = tmp_path / "clone"
        clone.mkdir()
        subprocess.run(["git", "-C", str(clone), "init", "-b", "main"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.email", "test@kanbanmate.local"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.name", "KanbanMate Test"],
            check=True,
        )
        (clone / "README.md").write_text("# test\n")
        subprocess.run(["git", "-C", str(clone), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(clone), "commit", "-m", "initial"], check=True)
        subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", str(clone)], check=True)

        ws = GitWorktreeWorkspace(clone_dir=clone)

        # Stage N: create the worktree on the WIP branch, write + COMMIT a design artifact.
        wt_a = ws.ensure_worktree(55)
        design_dir = wt_a / "docs" / "features" / "demo"
        design_dir.mkdir(parents=True)
        (design_dir / "DESIGN.md").write_text("# Demo design\n")
        subprocess.run(
            ["git", "-C", str(wt_a), "config", "user.email", "test@kanbanmate.local"], check=True
        )
        subprocess.run(
            ["git", "-C", str(wt_a), "config", "user.name", "KanbanMate Test"], check=True
        )
        subprocess.run(["git", "-C", str(wt_a), "add", "docs/features/demo/"], check=True)
        subprocess.run(["git", "-C", str(wt_a), "commit", "-m", "docs(demo): design"], check=True)

        # Tear the first worktree down (the stage's session ended) — the branch + commit survive.
        ws.remove_worktree(55, force=True)
        assert not wt_a.exists()

        # Stage N+1: a FRESH worktree re-uses the SAME WIP branch — the committed design is present.
        wt_b = ws.ensure_worktree(55)
        carried = wt_b / "docs" / "features" / "demo" / "DESIGN.md"
        assert carried.is_file(), "the WIP-branch commit must carry into the recreated worktree"
        assert carried.read_text() == "# Demo design\n"
        assert ws.discover_branch(55) == "kanban/ticket-55"

        ws.remove_worktree(55, force=True)

    def test_ensure_worktree_idempotent(self, tmp_path: Path) -> None:
        """Calling ensure_worktree twice returns the same path and does not error."""
        clone = tmp_path / "clone"
        clone.mkdir()
        subprocess.run(["git", "-C", str(clone), "init", "-b", "main"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.email", "test@kanbanmate.local"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.name", "KanbanMate Test"],
            check=True,
        )
        (clone / "file.txt").write_text("data\n")
        subprocess.run(["git", "-C", str(clone), "add", "file.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "commit", "-m", "init"],
            check=True,
        )
        subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", str(clone)], check=True)

        ws = GitWorktreeWorkspace(clone_dir=clone)

        first = ws.ensure_worktree(77)
        second = ws.ensure_worktree(77)

        assert first == second
        assert first.exists()

        # Clean up (force: the worktree is now on a named WIP branch).
        ws.remove_worktree(77, force=True)

    def test_discover_branch_after_branch_creation(self, tmp_path: Path) -> None:
        """After create-branch branches feat/<codename> OFF the WIP branch, discover returns it.

        Hybrid flow (DESIGN §13): the worktree starts on ``kanban/ticket-<n>``; create-branch checks
        out ``feat/<codename>`` from there (inheriting any carried commits), and ``discover_branch``
        then reports the feature branch.
        """
        clone = tmp_path / "clone"
        clone.mkdir()
        subprocess.run(["git", "-C", str(clone), "init", "-b", "main"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.email", "test@kanbanmate.local"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.name", "KanbanMate Test"],
            check=True,
        )
        (clone / "x").write_text("x\n")
        subprocess.run(["git", "-C", str(clone), "add", "x"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "commit", "-m", "init"],
            check=True,
        )
        subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", str(clone)], check=True)

        ws = GitWorktreeWorkspace(clone_dir=clone)
        target = ws.ensure_worktree(88)

        # Fresh worktree is on the WIP branch.
        assert ws.discover_branch(88) == "kanban/ticket-88"

        # create-branch checks out feat/<codename> OFF the current WIP HEAD.
        subprocess.run(
            ["git", "-C", str(target), "checkout", "-b", "feat/test-branch"],
            check=True,
        )

        branch = ws.discover_branch(88)
        assert branch == "feat/test-branch"

        # Clean up: force-remove since we have a branch now.
        ws.remove_worktree(88, force=True)

    def test_remove_worktree_force_dirty(self, tmp_path: Path) -> None:
        """Force-removal succeeds even when the worktree has uncommitted changes."""
        clone = tmp_path / "clone"
        clone.mkdir()
        subprocess.run(["git", "-C", str(clone), "init", "-b", "main"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.email", "test@kanbanmate.local"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.name", "KanbanMate Test"],
            check=True,
        )
        (clone / "a").write_text("a\n")
        subprocess.run(["git", "-C", str(clone), "add", "a"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "commit", "-m", "init"],
            check=True,
        )
        # ensure_worktree now fetches origin/main (the WIP-branch checkout, DESIGN §13) → origin needed.
        subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", str(clone)], check=True)

        ws = GitWorktreeWorkspace(clone_dir=clone)
        target = ws.ensure_worktree(99)

        # Dirty the worktree.
        (target / "b").write_text("dirty\n")

        # Force-remove should succeed.
        ws.remove_worktree(99, force=True)
        assert not target.exists()

    def test_delete_branch_real_force_delete_and_replay(self, tmp_path: Path) -> None:
        """Real ``git branch -D``: deletes an existing branch, then no-ops fail-soft on replay."""
        clone = tmp_path / "clone"
        clone.mkdir()
        subprocess.run(["git", "-C", str(clone), "init"], check=True)
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.email", "test@kanbanmate.local"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "config", "user.name", "KanbanMate Test"],
            check=True,
        )
        (clone / "f").write_text("f\n")
        subprocess.run(["git", "-C", str(clone), "add", "f"], check=True)
        subprocess.run(["git", "-C", str(clone), "commit", "-m", "init"], check=True)
        # Create a branch to delete (from HEAD, not checked out).
        subprocess.run(["git", "-C", str(clone), "branch", "feat/doomed"], check=True)

        ws = GitWorktreeWorkspace(clone_dir=clone)
        # Force-delete the branch.
        ws.delete_branch(1, "feat/doomed")
        listing = subprocess.run(
            ["git", "-C", str(clone), "branch", "--list", "feat/doomed"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feat/doomed" not in listing.stdout

        # Replay: deleting an already-gone branch is fail-soft (no raise).
        ws.delete_branch(1, "feat/doomed")


@pytest.mark.local_real
@pytest.mark.skipif(not os.environ.get("KANBAN_LOCAL_REAL"), reason=_LOCAL_REAL_REASON)
class TestSessionsLocalReal:
    """Real tmux session lifecycle in a throwaway directory.

    These tests require ``tmux`` on PATH and a running tmux server.
    """

    def test_launch_is_alive_kill_cycle(self, tmp_path: Path) -> None:
        """Create a tmux session, verify it is alive, then kill it."""
        sessions = TmuxSessions()
        name = f"kanbanmate-test-{os.getpid()}"

        try:
            result = sessions.launch(name, str(tmp_path), "echo 'hello from test'")
            assert result == name

            assert sessions.is_alive(name) is True

            sessions.kill(name)
            assert sessions.is_alive(name) is False
        finally:
            # Best-effort cleanup in case of mid-test failure.
            try:
                sessions.kill(name)
            except Exception:
                pass

    def test_is_alive_unknown_session(self) -> None:
        """Probing a session that never existed returns False."""
        sessions = TmuxSessions()
        assert sessions.is_alive("kanbanmate-nonexistent-99999") is False
