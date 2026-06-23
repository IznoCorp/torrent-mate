"""Tests for ``hooks/reference-transaction`` — the branch-deletion safety guard.

The hook ABORTS deleting a local branch unless its work is integrated into
``main``.  The original implementation recognised only *ancestry* merges (the
branch tip is an ancestor of ``main``).  But this repo **squash-merges every
PR**, and a squash collapses the branch into ONE new commit on ``main`` — so a
squash-merged branch's tip is *never* an ancestor of ``main``.  The guard must
therefore ALSO recognise squash merges (via patch-id equivalence), otherwise it
blocks the deletion of every correctly-merged branch.

These tests build throwaway git repos, install the real shipped hook via
``core.hooksPath``, and assert the deletion outcome (exit code + ref survival).
No mocks — the actual hook script runs against real git ref transactions.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _REPO_ROOT / "hooks" / "reference-transaction"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git -C <repo> <args>`` capturing output (30 s timeout)."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _init_repo_with_hook(tmp_path: Path) -> Path:
    """Create a fresh git repo on ``main`` with the real hook installed.

    The hook is copied into an isolated ``hooks/`` dir under *tmp_path* (so the
    test exercises the shipped file but is immune to any other hook that might
    later be added to the repo's hooks dir), and wired via ``core.hooksPath``.
    """
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    dest = hooks_dir / "reference-transaction"
    shutil.copy(_HOOK, dest)
    dest.chmod(0o755)

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.hooksPath", str(hooks_dir))
    (repo / "f").write_text("a\n")
    _git(repo, "add", "f")
    _git(repo, "commit", "-qm", "init")
    return repo


def _branch_exists(repo: Path, branch: str) -> bool:
    """Return True iff ``refs/heads/<branch>`` resolves in *repo*."""
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def _make_squash_merged_branch(repo: Path, branch: str) -> None:
    """Create *branch*, add commits, then squash-merge it into ``main``.

    Leaves ``main`` checked out and the (now squash-merged) *branch* present.
    """
    _git(repo, "switch", "-qc", branch)
    (repo / "f").write_text("a\nb\n")
    _git(repo, "add", "f")
    _git(repo, "commit", "-qm", f"{branch} work 1")
    (repo / "f").write_text("a\nb\nc\n")
    _git(repo, "add", "f")
    _git(repo, "commit", "-qm", f"{branch} work 2")
    _git(repo, "switch", "-q", "main")
    _git(repo, "merge", "--squash", branch)
    _git(repo, "commit", "-qm", f"squash: {branch} (#1)")


# --------------------------------------------------------------------------- #
# Existence + executable bit
# --------------------------------------------------------------------------- #


def test_hook_exists_and_executable() -> None:
    """The shipped reference-transaction hook must be present and chmod +x."""
    assert _HOOK.exists(), f"{_HOOK} is missing"
    import os

    assert os.access(_HOOK, os.X_OK), f"{_HOOK} is not executable"


# --------------------------------------------------------------------------- #
# Protection preserved: un-merged work cannot be deleted
# --------------------------------------------------------------------------- #


def test_blocks_deletion_of_unmerged_branch(tmp_path: Path) -> None:
    """A branch with commits NOT in main must be protected from deletion."""
    repo = _init_repo_with_hook(tmp_path)
    _git(repo, "switch", "-qc", "feature")
    (repo / "f").write_text("a\nz\n")
    _git(repo, "add", "f")
    _git(repo, "commit", "-qm", "unmerged work")
    _git(repo, "switch", "-q", "main")

    result = _git(repo, "branch", "-D", "feature")
    assert result.returncode != 0, "un-merged branch deletion must be refused"
    assert _branch_exists(repo, "feature"), "un-merged branch must survive the refused deletion"


# --------------------------------------------------------------------------- #
# Ancestry (fast-forward / true) merge still allowed
# --------------------------------------------------------------------------- #


def test_allows_deletion_of_ancestor_merged_branch(tmp_path: Path) -> None:
    """A branch whose tip is an ancestor of main (ff merge) deletes cleanly."""
    repo = _init_repo_with_hook(tmp_path)
    _git(repo, "switch", "-qc", "feature")
    (repo / "f").write_text("a\nb\n")
    _git(repo, "add", "f")
    _git(repo, "commit", "-qm", "ff work")
    _git(repo, "switch", "-q", "main")
    _git(repo, "merge", "--ff-only", "feature")  # main now contains feature's tip

    result = _git(repo, "branch", "-D", "feature")
    assert result.returncode == 0, (
        f"ancestor-merged branch deletion must succeed; stderr: {result.stderr}"
    )
    assert not _branch_exists(repo, "feature")


# --------------------------------------------------------------------------- #
# THE FIX: squash-merged branch must be deletable
# --------------------------------------------------------------------------- #


def test_allows_deletion_of_squash_merged_branch(tmp_path: Path) -> None:
    """A squash-merged branch (tip NOT an ancestor) must be recognised as merged.

    This is the core regression the fix addresses: every PR in this repo is
    squash-merged, so the ancestry-only check produced a false "not merged" and
    blocked the cleanup of correctly-merged branches.
    """
    repo = _init_repo_with_hook(tmp_path)
    _make_squash_merged_branch(repo, "feature")
    # Sanity: the tip is genuinely NOT an ancestor (so ancestry alone would block).
    assert _git(repo, "merge-base", "--is-ancestor", "feature", "main").returncode != 0, (
        "test setup wrong: squash tip should not be an ancestor of main"
    )

    result = _git(repo, "branch", "-D", "feature")
    assert result.returncode == 0, (
        f"squash-merged branch deletion must succeed; stderr: {result.stderr}"
    )
    assert not _branch_exists(repo, "feature")


def test_allows_deletion_of_squash_merged_branch_with_no_remote(tmp_path: Path) -> None:
    """Squash-merged + remote auto-deleted on merge (no origin/<branch>) → deletable.

    GitHub's delete-on-merge removes the remote branch the moment a squash PR
    merges, so the *normal* state of a merged branch is: integrated in main AND
    no remote.  The guard must not block exactly that case (the original hook's
    separate ``pushed`` requirement did).
    """
    repo = _init_repo_with_hook(tmp_path)
    # No origin remote is configured at all → pushed check would be 0.
    assert (
        _git(repo, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/feature").returncode
        != 0
    )
    _make_squash_merged_branch(repo, "feature")

    result = _git(repo, "branch", "-D", "feature")
    assert result.returncode == 0, (
        f"squash-merged branch with no remote must delete; stderr: {result.stderr}"
    )
    assert not _branch_exists(repo, "feature")


def test_allows_deletion_of_squash_merged_slashed_branch(tmp_path: Path) -> None:
    """A real-world slashed branch name (e.g. ``fix/foo``) resolves + deletes.

    The tip is resolved by ref name (``refs/heads/<branch>``) because git zeroes
    the old-value at the prepared stage; this guards that a slash in the name does
    not break the resolution.
    """
    repo = _init_repo_with_hook(tmp_path)
    _make_squash_merged_branch(repo, "fix/foo")

    result = _git(repo, "branch", "-D", "fix/foo")
    assert result.returncode == 0, (
        f"squash-merged slashed branch must delete; stderr: {result.stderr}"
    )
    assert not _branch_exists(repo, "fix/foo")
