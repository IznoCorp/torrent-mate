"""End-to-end kill-switch test for the ``~/.kanban/PAUSE`` sentinel (DESIGN §10 / H5).

These tests drive a full :func:`~kanbanmate.app.tick.tick` against a **real**
:class:`~kanbanmate.adapters.store.fs_store.FsStateStore` rooted at a ``tmp_path``,
so the kill-switch read goes through the genuine filesystem adapter. The remaining
ports (board reader/writer, workspace, sessions, clock) are mocks held for
assertion. The contract proven here is the operative H5 behaviour: while a
``PAUSE`` file exists under the store root, a move into an agent column produces
**no** ``LaunchAction``; remove the file and the next tick launches normally.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

from kanbanmate.adapters.github.types import IssueContext
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.app.actions import Deps
from kanbanmate.app.tick import PersistedState, TickConfig, tick
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import BoardSnapshot, Ticket
from kanbanmate.core.transitions import load_transitions

# A minimal bare board column set (DESIGN §8.0.6), matching the tick tests. The
# launch lives on the Backlog -> InProgress whitelist row, not on a column flag.
_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: InProgress
    name: In Progress
  - key: Done
    name: Done
"""

# Transitions-only (DESIGN §8.0.6): a whitelist is ALWAYS supplied. ``Backlog ->
# InProgress`` carries a prompt so it LAUNCHes (or BLOCKs under PAUSE) — the launch
# lives on the transition, not on a column class.
_WHITELIST = """
project: owner/repo
transitions:
  - from: Backlog
    to: InProgress
    prompt: "/implement:phase {{code}}"
    profile: dev
"""


class _FakeBoardReader:
    """A scripted board reader returning a fixed probe token and snapshot."""

    def __init__(self, probe: str, snapshot: BoardSnapshot) -> None:
        """Store the scripted probe token and snapshot.

        Args:
            probe: The token :meth:`cheap_probe` returns.
            snapshot: The board state :meth:`snapshot` returns.
        """
        self._probe = probe
        self._snapshot = snapshot

    def cheap_probe(self) -> str:
        """Return the scripted probe token."""
        return self._probe

    def snapshot(self) -> BoardSnapshot:
        """Return the scripted snapshot."""
        return self._snapshot

    def issue_state(self, number: int) -> bool:  # noqa: ARG002
        """Stub: always returns False (the killswitch tests never exercise deps)."""
        return False

    def issue_context(self, number: int) -> IssueContext:  # noqa: ARG002
        """Stub: empty context (killswitch tests never exercise launch-prompt enrichment, 18.2)."""
        return IssueContext(body="", comments=(), linked_issue_body=None)


@dataclass
class _Bundle:
    """The deps plus the workspace/sessions mocks needed to assert (no) launch."""

    deps: Deps
    workspace: MagicMock
    sessions: MagicMock
    store: FsStateStore


def _bundle(store_root: Path, probe: str, ticket: Ticket) -> _Bundle:
    """Wire a real fs store + mocked adapters into a :class:`Deps`.

    Args:
        store_root: The ``tmp_path`` root the real store (and its PAUSE read) uses.
        probe: The probe token the fake board reader returns.
        ticket: The single ticket the snapshot exposes.

    Returns:
        A :class:`_Bundle` exposing the deps and the launch-side mocks.
    """
    reader = _FakeBoardReader(probe, BoardSnapshot(tickets=(ticket,), fetched_at=0.0))
    board_writer = MagicMock()
    workspace = MagicMock()
    workspace.ensure_worktree.return_value = str(store_root / "wt" / "ticket-7")
    sessions = MagicMock()
    sessions.launch.return_value = "ticket-7"
    # Phase-25 §25.1: a prompt-bearing launch polls ``capture`` then send-keys the filled prompt.
    # Default the snapshot to a READY-REPL marker so the bounded poll returns at once.
    sessions.capture.return_value = "│ > Welcome to Claude"
    clock = MagicMock()
    clock.now.return_value = 1000.0
    store = FsStateStore(root=store_root)
    deps = Deps(
        board_writer=board_writer,
        board_reader=reader,
        workspace=workspace,
        sessions=sessions,
        store=store,
        clock=clock,
        pull_requests=MagicMock(),
        # No-op sleeper so the trust/ready poll runs offline (phase-25 §25.1).
        sleeper=lambda _seconds: None,
    )
    return _Bundle(deps=deps, workspace=workspace, sessions=sessions, store=store)


def _agent_move_state() -> PersistedState:
    """Baseline placing the ticket in Backlog (an inert -> agent transition next)."""
    return PersistedState(columns_by_item={"PVTI_7": "Backlog"}, last_probe="probe-0")


def test_pause_file_blocks_launch_then_removal_resumes(tmp_path: Path) -> None:
    """A PAUSE sentinel blocks the launch; removing it lets the next tick launch."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), transitions=load_transitions(_WHITELIST)
    )

    # --- Phase 1: PAUSE present -> the agent move is blocked, NOT launched. ---
    b = _bundle(tmp_path, "probe-1", ticket)
    pause = tmp_path / "PAUSE"
    pause.write_text("")  # drop the kill-switch sentinel

    result_paused, _ = tick(b.deps, config, _agent_move_state())

    b.sessions.launch.assert_not_called()
    b.workspace.ensure_worktree.assert_not_called()
    # The transition still resolved to an action (a BlockAction), so it counts as executed,
    # but emphatically no launch happened.
    assert result_paused.actions_executed == 1

    # --- Phase 2: remove PAUSE -> a fresh tick now launches the agent. ---
    b2 = _bundle(tmp_path, "probe-2", ticket)
    pause.unlink()  # lift the kill-switch

    result_live, _ = tick(b2.deps, config, _agent_move_state())

    b2.sessions.launch.assert_called_once()
    b2.workspace.ensure_worktree.assert_called_once_with(7, base="main")
    assert result_live.actions_executed == 1


def test_no_pause_file_launches(tmp_path: Path) -> None:
    """With no PAUSE sentinel, an agent move launches as usual."""
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    config = TickConfig(
        columns=load_columns(_COLUMNS_YAML), transitions=load_transitions(_WHITELIST)
    )
    b = _bundle(tmp_path, "probe-1", ticket)

    result, _ = tick(b.deps, config, _agent_move_state())

    b.sessions.launch.assert_called_once()
    assert result.actions_executed == 1
