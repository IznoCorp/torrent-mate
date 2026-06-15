"""L2 local-real integration test: full tick with real tmux + real git (GitHub faked).

Gated on ``KANBAN_LOCAL_REAL=1`` + ``tmux`` on PATH — skipped by default in CI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from kanbanmate.adapters.github.types import CommentRef, IssueContext
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.adapters.workspace.sessions import TmuxSessions
from kanbanmate.adapters.workspace.worktree import GitWorktreeWorkspace
from kanbanmate.app.actions import Deps
from kanbanmate.app.tick import PersistedState, TickConfig, tick
from kanbanmate.core.domain import BoardSnapshot, Column, ColumnClass, Ticket
from kanbanmate.core.transitions_defaults import default_transition_config

pytestmark = [
    pytest.mark.local_real,
    pytest.mark.skipif(
        not (os.environ.get("KANBAN_LOCAL_REAL") and shutil.which("tmux")),
        reason="opt-in: KANBAN_LOCAL_REAL=1 + tmux required",
    ),
]


class _FakeBoard:
    """Fake GitHub board: returns a static snapshot and swallows writes.

    Implements both ``BoardReader`` and ``BoardWriter`` Protocols structurally
    so the tick cycle can complete without a real GitHub token.
    """

    def __init__(self, snapshot: BoardSnapshot, probe: str = "probe-1") -> None:
        """Initialise with a fixed snapshot and probe token.

        Args:
            snapshot: The board state to return from :meth:`snapshot`.
            probe: The opaque probe token returned by :meth:`cheap_probe`.
        """
        self._snapshot = snapshot
        self._probe = probe

    def cheap_probe(self) -> str:
        """Return a static probe token (always signals "changed").

        Returns:
            The opaque probe string set at construction time.
        """
        return self._probe

    def snapshot(self) -> BoardSnapshot:
        """Return the static board snapshot.

        Returns:
            The pre-built :class:`BoardSnapshot`.
        """
        return self._snapshot

    def issue_state(self, number: int) -> bool:  # noqa: ARG002
        """Stub: always returns False (local tick tests never exercise off-board deps)."""
        return False

    def issue_context(self, number: int) -> IssueContext:  # noqa: ARG002
        """Stub: empty context (local tick tests never exercise launch-prompt enrichment, 18.2)."""
        return IssueContext(body="", comments=(), linked_issue_body=None)

    def move_card(self, item_id: str, column_key: str) -> None:
        """No-op: we are not testing board writes in this test.

        Args:
            item_id: Ignored.
            column_key: Ignored.
        """

    def comment(self, issue_number: int, body: str) -> None:
        """No-op: fake board swallows comments silently.

        Args:
            issue_number: Ignored.
            body: Ignored.
        """

    def close_open_pr_for_branch(self, head_branch: str) -> int | None:
        """No-op: fake board has no PRs (satisfies ``PullRequests`` port, 8.2.b).

        Args:
            head_branch: Ignored.

        Returns:
            ``None`` — there is never an open PR to close in this fake.
        """
        return None

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """No-op: fake board exposes no comments (widened BoardWriter port, 8.1.b).

        Args:
            issue_number: Ignored.

        Returns:
            An empty list.
        """
        return []

    def update_comment(self, comment_id: int, body: str) -> None:
        """No-op: fake board swallows comment edits silently (widened port, 8.1.b).

        Args:
            comment_id: Ignored.
            body: Ignored.
        """


class _FakeClock:
    """Frozen clock returning a fixed timestamp for deterministic tests."""

    def __init__(self, now: float = 1000000.0) -> None:
        """Initialise with a fixed POSIX timestamp.

        Args:
            now: The timestamp :meth:`now` will always return.
        """
        self._now = now

    def now(self) -> float:
        """Return the frozen timestamp.

        Returns:
            The fixed POSIX timestamp set at construction time.
        """
        return self._now


def test_tick_local_real_launch(tmp_path: Path) -> None:
    """Full tick cycle: a whitelisted prompt-transition triggers a real tmux session + git worktree.

    1. Creates a real git repo in ``tmp_path`` with an initial commit on ``main``
       so the worktree adapter has a valid base to branch from.
    2. Builds a fake ``BoardReader`` returning one ticket that has MOVED from
       ``PrepareFeature`` into ``InProgress`` — a whitelisted prompt-transition in
       the default flow (``_IMPLEMENT_PROMPT``), so ``decide`` → ``LAUNCH`` (DESIGN
       §8.0.6: the launch lives on the transition, not the column). Plus real
       ``FsStateStore``, ``GitWorktreeWorkspace``, and ``TmuxSessions``.
    3. Stubs the agent command to ``sleep 30`` so the tmux session lingers for assertions.
    4. Seeds the diff baseline so the ticket reads as ``PrepareFeature → InProgress``
       and supplies ``transitions=default_transition_config()`` — a whitelist is the
       SOLE trigger model (§8.0.6), never ``None``.
    5. Asserts a real tmux session ``ticket-1`` exists.
    6. Asserts the worktree directory ``<tmp>/worktrees/ticket-1`` was created.
    7. Teardown (finally): kills the tmux session and force-removes the worktree,
       even on assertion failure, leaving no residue.
    """
    # ── 1. Create a real git repo with origin so worktree-add works ──────────
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "-C", str(remote), "init", "--bare"], check=True)

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(remote), str(clone)], check=True)
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
    subprocess.run(
        ["git", "-C", str(clone), "push", "origin", "main"],
        check=True,
    )

    # ── 2. Build the bare board column set (transitions-only — all INERT) ────
    # In the transitions-only model (§8.0.6) columns carry no launch class; the
    # launch is decided by the PrepareFeature → InProgress whitelist entry below.
    columns: dict[str, Column] = {
        "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),
        "PrepareFeature": Column(
            key="PrepareFeature", name="Prepare feature", column_class=ColumnClass.INERT
        ),
        "InProgress": Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),
        "Done": Column(key="Done", name="Done", column_class=ColumnClass.INERT),
    }

    # ── 3. Build a snapshot with one ticket now in the launch-transition target ─
    ticket = Ticket(
        item_id="ITEM_1",
        issue_number=1,
        title="Test ticket",
        column_key="InProgress",
    )
    snapshot = BoardSnapshot(tickets=(ticket,), fetched_at=100.0)
    fake_board = _FakeBoard(snapshot, probe="probe-1")

    # ── 4. Real adapters, fake board + clock ────────────────────────────────
    store = FsStateStore(tmp_path / "kanban")
    workspace = GitWorktreeWorkspace(clone_dir=clone)
    sessions = TmuxSessions()
    clock = _FakeClock(now=1000000.0)

    # A command that lingers so we can assert the session is alive.
    agent_command = "sleep 30"

    deps = Deps(
        board_writer=fake_board,
        board_reader=fake_board,
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=fake_board,
        base="main",
        agent_command=agent_command,
    )

    # A whitelist is the SOLE trigger model (§8.0.6): supply the default flow so
    # PrepareFeature → InProgress resolves to the _IMPLEMENT_PROMPT launch.
    config = TickConfig(columns=columns, transitions=default_transition_config())

    session_name = "ticket-1"
    worktree_dir = tmp_path / "worktrees" / session_name

    try:
        # ── 5. Call tick with a seeded baseline (ticket was in PrepareFeature) ──
        # The diff then yields PrepareFeature → InProgress (a whitelisted prompt-
        # transition), not a first-contact NOOP, so a real LaunchAction fires.
        result, _next_state = tick(
            deps,
            config,
            PersistedState(columns_by_item={"ITEM_1": "PrepareFeature"}),
        )

        # ── 6. Assert a real tmux session exists ────────────────────────
        assert result.actions_executed == 1, (
            f"Expected 1 action executed, got {result.actions_executed}"
        )
        assert result.errors == 0, f"Expected 0 errors, got {result.errors}"
        assert sessions.is_alive(session_name), f"tmux session {session_name!r} should be alive"

        # Double-check with raw subprocess for belt-and-suspenders.
        probe = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )
        assert probe.returncode == 0, (
            f"tmux has-session {session_name!r} returned {probe.returncode}"
        )

        # ── 7. Assert the worktree directory was created ────────────────
        assert worktree_dir.exists(), f"worktree {worktree_dir} should exist"
        assert (worktree_dir / "README.md").exists(), "worktree should contain repo files"

    finally:
        # ── 8. Teardown: kill tmux session + remove worktree ───────────
        # Best-effort cleanup — runs even on assertion failure.
        try:
            sessions.kill(session_name)
        except Exception:
            pass
        try:
            workspace.remove_worktree(1, force=True)
        except Exception:
            pass
