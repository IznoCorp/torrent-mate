"""H7 integration test: move a real card on a real board, run tick, verify NOOP.

Gated on ``KANBAN_TOKEN`` + ``KANBAN_TEST_PROJECT`` + auxiliary env vars —
skipped by default in CI and local runs (no network at import time).

Design: DESIGN §7 (H7), plan phase-04-integration-ci.md §4.3.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.types import CommentRef, IssueContext
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.app.actions import Deps
from kanbanmate.app.tick import PersistedState, TickConfig, tick
from kanbanmate.core.domain import BoardSnapshot, Column, ColumnClass, Ticket

# The test is gated on ALL required env vars — without them it skips cleanly.
# ``os.environ.get`` is NOT a network call so collection never touches the wire.
_ENV_VARS = (
    "KANBAN_TOKEN",
    "KANBAN_TEST_PROJECT",
    "KANBAN_TEST_REPO",
    "KANBAN_TEST_CARD_ITEM_ID",
    "KANBAN_TEST_INERT_COLUMN",
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(v) for v in _ENV_VARS),
        reason="set KANBAN_TOKEN + KANBAN_TEST_PROJECT to run against a real test org",
    ),
]


# ── Spy / fake adapters (no real tmux, no real worktrees, no network) ──────


class _SpySessions:
    """Spy sessions adapter: records :meth:`launch` calls without real tmux.

    Satisfies :class:`kanbanmate.ports.workspace.Sessions` structurally so
    the tick's command actions can execute without side effects.
    """

    def __init__(self) -> None:
        self.launches: list[str] = []
        self.sent: list[str] = []

    def launch(self, name: str, cwd: str, command: str) -> str:
        """Record the launch and return a fake session id.

        Args:
            name: Session name (recorded).
            cwd: Working directory (ignored).
            command: Agent command (ignored).

        Returns:
            A fake session identifier.
        """
        self.launches.append(name)
        return f"fake-session-{name}"

    def capture(self, name: str) -> str:
        """Return a ready-REPL pane so the prompt-delivery poll returns at once (phase-25 §25.1).

        Args:
            name: Session name (ignored).

        Returns:
            A capture-pane snapshot containing a ready-REPL marker.
        """
        return "│ > Welcome to Claude"

    def send_text(self, name: str, text: str, *, literal: bool = True, enter: bool = False) -> None:
        """Record literal prompt text typed into the (fake) REPL (phase-25 §25.1).

        Args:
            name: Session name (ignored).
            text: The text / key name sent (literal payloads are recorded).
            literal: Whether ``text`` is raw literal text (recorded) or a key name.
            enter: Whether a trailing Enter is appended (ignored — no real REPL).
        """
        if literal:
            self.sent.append(text)

    def is_alive(self, name: str) -> bool:
        """Always return ``False`` — no real session exists.

        Args:
            name: Session name (ignored).

        Returns:
            ``False``.
        """
        return False

    def kill(self, name: str) -> None:
        """No-op: no real session to kill.

        Args:
            name: Session name (ignored).
        """

    def end_session(self, name: str) -> None:
        """No-op: no real REPL to exit (#1 Protocol member).

        Args:
            name: Session name (ignored).
        """

    def kill_repl_process(self, name: str) -> None:
        """No-op: no real REPL process to SIGKILL (firm-exit Protocol member).

        Args:
            name: Session name (ignored).
        """


class _SpyWorkspace:
    """Spy workspace adapter: records :meth:`ensure_worktree` calls without real git.

    Satisfies :class:`kanbanmate.ports.workspace.Workspace` structurally so
    the tick's command actions can execute without side effects.
    """

    def __init__(self) -> None:
        self.ensured: list[int] = []

    def ensure_worktree(self, ticket: int, base: str = "main") -> Path:
        """Record the call and return a fake path.

        Args:
            ticket: Issue number (recorded).
            base: Integration base (ignored).

        Returns:
            A fake worktree path.
        """
        self.ensured.append(ticket)
        return Path(f"/tmp/fake-worktree-{ticket}")

    def ensure_clone(
        self, repo_url: str, base: str = "main", *, token_path: str | None = None
    ) -> Path:
        """No-op: return a fake clone path (14.1 — satisfies ``Workspace`` Protocol).

        Args:
            repo_url: Repo URL (ignored).
            base: Integration base (ignored).
            token_path: Token path (ignored).

        Returns:
            A fake clone path.
        """
        return Path("/tmp/fake-clone")

    def worktree_exists(self, ticket: int) -> bool:
        """Always report present (satisfies the widened ``Workspace`` port, phase 28.1).

        Args:
            ticket: Issue number (ignored).

        Returns:
            ``True`` — the spy has no real registry, so it reports the worktree present.
        """
        return True

    def has_unpushed_work(self, ticket: int) -> bool:
        """Report no unpushed work (satisfies the widened ``Workspace`` port, #9).

        Args:
            ticket: Issue number (ignored).

        Returns:
            ``False`` — the spy has no real git state, so reclaim proceeds without a block.
        """
        return False

    def remove_worktree(self, ticket: int, *, force: bool = False) -> None:
        """No-op: no real worktree to remove.

        Args:
            ticket: Issue number (ignored).
            force: Whether to force-remove (ignored).
        """

    def discover_branch(self, ticket: int) -> str | None:
        """Always return ``None`` — no real worktree to inspect.

        Args:
            ticket: Issue number (ignored).

        Returns:
            ``None``.
        """
        return None

    def delete_branch(self, ticket: int, branch: str) -> None:
        """No-op: no real branch to delete (satisfies the widened ``Workspace`` port, 8.2.b).

        Args:
            ticket: Issue number (ignored).
            branch: Branch name (ignored).
        """

    def run_transition_script(
        self, ticket: int, script: str, env: dict[str, str]
    ) -> tuple[int, str]:
        """No-op success: no real script to run (satisfies the widened ``Workspace`` port, 12.5).

        Args:
            ticket: Issue number (ignored).
            script: Script path (ignored).
            env: Script env (ignored).

        Returns:
            A ``(0, "")`` success verdict.
        """
        return (0, "")


class _FakeClock:
    """Frozen clock returning a fixed timestamp for deterministic tests.

    Satisfies :class:`kanbanmate.ports.clock.Clock` structurally.
    """

    def now(self) -> float:
        """Return a fixed POSIX timestamp.

        Returns:
            ``1000000.0`` (a fixed point far from any real heartbeat TTL).
        """
        return 1000000.0


class _FakeBoard:
    """Fake board adapter: returns a controlled snapshot, swallows writes.

    Satisfies both :class:`kanbanmate.ports.board.BoardReader` and
    :class:`kanbanmate.ports.board.BoardWriter` structurally so the tick can
    complete without hitting the real GitHub API.
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
        """Stub: always returns False (integration tick tests never exercise off-board deps)."""
        return False

    def issue_context(self, number: int) -> IssueContext:  # noqa: ARG002
        """Stub: empty context (integration tick never exercises launch-prompt enrichment, 18.2)."""
        return IssueContext(body="", comments=(), linked_issue_body=None)

    def move_card(self, item_id: str, column_key: str) -> None:
        """No-op: we are not testing board writes inside the tick.

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

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """No-op: fake board exposes no comments (widened BoardWriter, 8.1.b).

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

    def close_open_pr_for_branch(self, head_branch: str) -> int | None:
        """No-op: fake board has no PRs (satisfies ``PullRequests`` port, 8.2.b).

        Args:
            head_branch: Ignored.

        Returns:
            ``None`` — there is never an open PR to close in this fake.
        """
        return None


# ── The test ─────────────────────────────────────────────────────────────────


def test_poll_real_board_inert_move(tmp_path: Path) -> None:
    """Move a real card to an inert column via GitHub API, run tick, verify NOOP.

    1. Build a real :class:`GithubClient` and move a known card to an inert column.
    2. Take a real snapshot to confirm the card landed in the target column.
    3. Build a controlled fake board with just that card, and run :func:`tick`
       against it with spy sessions/workspace (no real tmux/git side effects).
    4. Assert no tmux session was launched (inert column → NOOP decision).
    5. Assert the persisted state was updated to reflect the card's new column.
    """
    token = os.environ["KANBAN_TOKEN"]
    project_id = os.environ["KANBAN_TEST_PROJECT"]
    repo = os.environ["KANBAN_TEST_REPO"]
    card_item_id = os.environ["KANBAN_TEST_CARD_ITEM_ID"]
    inert_column = os.environ["KANBAN_TEST_INERT_COLUMN"]

    # ── 1. Real GitHub: move card to the inert column ──────────────────
    client = GithubClient(token, project_id=project_id, repo=repo)
    client.move_card(card_item_id, inert_column)

    # ── 2. Real snapshot: confirm the card landed ──────────────────────
    snapshot = client.snapshot()
    card_ticket: Ticket | None = None
    for t in snapshot.tickets:
        if t.item_id == card_item_id:
            card_ticket = t
            break
    assert card_ticket is not None, f"Card {card_item_id!r} not found in board snapshot"
    assert card_ticket.column_key == inert_column, (
        f"Expected card in {inert_column!r}, got {card_ticket.column_key!r}"
    )

    # ── 3. Controlled tick: fake board with only our card ──────────────
    controlled_snapshot = BoardSnapshot(tickets=(card_ticket,), fetched_at=100.0)
    fake_board = _FakeBoard(controlled_snapshot, probe="probe-1")

    # The card was "previously" in a different column so diff detects a move.
    # Pick a column name that differs from the inert target to guarantee a
    # transition — both columns are INERT so the decision is always NOOP.
    old_column = "Backlog" if inert_column != "Backlog" else "Done"

    persisted = PersistedState(
        columns_by_item={card_item_id: old_column},
        last_probe="probe-0",  # different from probe-1 → triggers snapshot
    )

    spy_sessions = _SpySessions()
    spy_workspace = _SpyWorkspace()
    fake_clock = _FakeClock()
    store = FsStateStore(tmp_path / "kanban")

    deps = Deps(
        board_writer=fake_board,
        board_reader=fake_board,
        workspace=spy_workspace,
        sessions=spy_sessions,
        store=store,
        clock=fake_clock,
        pull_requests=fake_board,
        base="main",
        agent_command="echo test",
    )

    columns: dict[str, Column] = {
        inert_column: Column(
            key=inert_column,
            name=inert_column,
            column_class=ColumnClass.INERT,
        ),
        old_column: Column(
            key=old_column,
            name=old_column,
            column_class=ColumnClass.INERT,
        ),
    }
    config = TickConfig(columns=columns)

    # ── 4. Run tick ────────────────────────────────────────────────────
    result, next_state = tick(deps, config, persisted)

    # ── 5. Assert NO tmux session was launched ─────────────────────────
    assert len(spy_sessions.launches) == 0, f"Expected 0 tmux launches, got {spy_sessions.launches}"
    assert len(spy_workspace.ensured) == 0, (
        f"Expected 0 worktree creations, got {spy_workspace.ensured}"
    )

    # ── 6. Assert persisted state updated (diff detected the move) ─────
    assert next_state.columns_by_item.get(card_item_id) == inert_column, (
        f"Persisted state should show card in {inert_column!r}, "
        f"got {next_state.columns_by_item.get(card_item_id)!r}"
    )
    assert result.actions_executed == 0, (
        f"Expected 0 actions executed (NOOP for inert), got {result.actions_executed}"
    )
    assert result.snapshot_taken is True, "Expected a snapshot to be taken (probe changed)"
