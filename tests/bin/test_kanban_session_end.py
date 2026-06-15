"""Tests for the ``kanban-session-end`` agent helper (:mod:`kanbanmate.bin.kanban_session_end`).

The contract (DESIGN §8.1.f / §8.3):

* a valid issue exhaustively purges the ticket's cap slot + running state + markers via
  :meth:`~kanbanmate.adapters.store.fs_store.FsStateStore.purge_ticket` and exits ``0``;
* a bad/missing arg is a usage error (exit ``2``); a store failure is reported (exit ``1``),
  never a crash;
* the advance breadcrumb decides the ✅/⚠️ split — PRESENT → the sticky is left untouched (the
  daemon's 8.1.e already finalized ✅), ABSENT → the stage sticky is finalized ⚠️ *interrupted*;
* a PURGED state (Cancel teardown) early-returns with an idempotent slot release and NO GitHub I/O;
* the ⚠️ finalize is fail-soft (a GitHub/wiring error never breaks the always-run session-end);
* **ORDERING (load-bearing):** the breadcrumb is READ BEFORE ``purge_ticket`` (which PURGES it,
  DESIGN §8.1.d) — a clean advance must NOT be misread as "absent" and wrongly finalized ⚠️.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kanbanmate.bin import kanban_session_end
from kanbanmate.bin.kanban_session_end import main
from kanbanmate.ports.store import TicketState, TicketStatus


def _state(issue: int = 7, *, stage: str = "Implement") -> TicketState:
    """Build a widened :class:`TicketState` carrying a launch stage + metadata."""
    return TicketState(
        issue_number=issue,
        item_id="PVTI_node",
        session_id="sess-abc",
        status=TicketStatus.RUNNING,
        heartbeat=1000.0,
        stage=stage,
        profile="docs",
        mode="acceptEdits",
        started=900.0,
        worktree="/tmp/wt/ticket-7",
    )


def _patch_github(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stub the GitHub wiring (registry / token / client) and return the upsert spy."""
    monkeypatch.setattr(kanban_session_end, "_resolve_entry", lambda: MagicMock())
    monkeypatch.setattr(kanban_session_end, "load_token", lambda *a, **k: "tok")
    monkeypatch.setattr(kanban_session_end, "GithubClient", lambda *a, **k: MagicMock())
    upsert = MagicMock()
    monkeypatch.setattr(kanban_session_end, "upsert_stage_comment", upsert)
    return upsert


# ---------------------------------------------------------------------------
# Usage / argument handling (unchanged contract)
# ---------------------------------------------------------------------------


def test_missing_arg_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """No issue argument is a usage error (exit 2), store never touched."""
    store = MagicMock()
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)

    assert main([]) == 2
    store.purge_ticket.assert_not_called()


def test_non_int_arg_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-integer issue is rejected (exit 2), store never touched."""
    store = MagicMock()
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)

    assert main(["notanint"]) == 2
    store.purge_ticket.assert_not_called()


def test_store_failure_exits_one_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A store failure is reported (exit 1), never a traceback that crashes the agent."""
    store = MagicMock()
    store.load.side_effect = OSError("disk gone")
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)

    assert main(["7"]) == 1


# ---------------------------------------------------------------------------
# The ✅/⚠️ split (DESIGN §8.1.f)
# ---------------------------------------------------------------------------


def test_purged_state_releases_slot_no_github_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """A purged state (Cancel teardown) → idempotent slot release, NO GitHub I/O, no raise."""
    store = MagicMock()
    store.load.return_value = None
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    upsert = _patch_github(monkeypatch)
    # Guard: even if the breadcrumb reader were reachable, the early-return must precede it.
    store.recent_agent_advance.side_effect = AssertionError("must not read breadcrumb on purge")

    assert main(["7"]) == 0
    store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    upsert.assert_not_called()  # no ⚠️ finalize, no GitHub I/O on a purged ticket.


def test_recent_breadcrumb_keeps_sticky_and_releases_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WITH a recent breadcrumb → sticky untouched (no ⚠️), slot released, exit 0."""
    store = MagicMock()
    store.load.return_value = _state()
    store.recent_agent_advance.return_value = True
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    upsert = _patch_github(monkeypatch)

    assert main(["7"]) == 0
    store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    upsert.assert_not_called()  # the daemon's 8.1.e already finalized ✅ — leave the sticky.


def test_no_breadcrumb_finalizes_interrupted_and_releases_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WITHOUT a breadcrumb → ⚠️ flip (finished ts set) on the stage sticky, slot released."""
    store = MagicMock()
    store.load.return_value = _state(stage="Implement")
    store.recent_agent_advance.return_value = False
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    upsert = _patch_github(monkeypatch)

    assert main(["7"]) == 0
    store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    upsert.assert_called_once()
    # Positional args: (client, issue, stage); the header carries the ⚠️ interrupted status.
    args, kwargs = upsert.call_args
    assert args[1] == 7
    assert args[2] == "Implement"
    header = kwargs["header"]
    assert header.status == "interrupted"
    assert header.finished != ""  # a finished timestamp is stamped on the terminal sticky.
    # Full-parity metadata bullets come from the widened TicketState (8.1.d), not a bare header.
    assert header.session == "sess-abc"
    assert header.profile == "docs"
    assert header.worktree == "ticket-7"


def test_no_breadcrumb_empty_stage_is_silent_no_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A loaded state with no recorded stage → slot released, NO ⚠️ finalize (nothing to flip)."""
    store = MagicMock()
    store.load.return_value = _state(stage="")
    store.recent_agent_advance.return_value = False
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    upsert = _patch_github(monkeypatch)

    assert main(["7"]) == 0
    store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    upsert.assert_not_called()


def test_github_error_during_finalize_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A GitHub/wiring error during the ⚠️ finalize is swallowed — session-end still exits 0."""
    store = MagicMock()
    store.load.return_value = _state()
    store.recent_agent_advance.return_value = False
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    monkeypatch.setattr(kanban_session_end, "_resolve_entry", lambda: MagicMock())
    monkeypatch.setattr(kanban_session_end, "load_token", lambda *a, **k: "tok")

    def _boom(*_a: object, **_k: object) -> object:
        raise RuntimeError("github unreachable")

    monkeypatch.setattr(kanban_session_end, "GithubClient", _boom)

    # The finalize blows up, but the always-run session-end must never crash — slot still released.
    assert main(["7"]) == 0
    store.purge_ticket.assert_called_once_with(7, keep_budgets=True)


# ---------------------------------------------------------------------------
# Ordering regression (load-bearing — DESIGN §8.1.f CRITICAL ORDERING FIX)
# ---------------------------------------------------------------------------


def test_breadcrumb_read_before_purge_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    """REGRESSION: the breadcrumb is read BEFORE purge_ticket removes it.

    ``purge_ticket`` removes the advance breadcrumb (fs_store.py — DESIGN §8.1.d; session-end
    now routes to the exhaustive ``purge_ticket``, 13.7). If session-end purged before reading
    the breadcrumb, a clean ✅ advance would be misread as "absent" and wrongly finalized ⚠️.
    This test records the call order and asserts ``recent_agent_advance`` fires strictly before
    ``purge_ticket`` — so a recent breadcrumb is NOT lost to the purge, and a clean advance does
    NOT produce a ⚠️.
    """
    order: list[str] = []
    store = MagicMock()
    store.load.return_value = _state()

    def _recent(issue: int, *, now: float) -> bool:
        order.append("recent_agent_advance")
        return True  # a clean advance — the breadcrumb is present.

    def _purge(issue: int, *, keep_budgets: bool = False) -> None:
        order.append("purge_ticket")

    store.recent_agent_advance.side_effect = _recent
    store.purge_ticket.side_effect = _purge
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    upsert = _patch_github(monkeypatch)

    assert main(["7"]) == 0
    # The read MUST precede the purge, or the ✅/⚠️ split silently breaks.
    assert order == ["recent_agent_advance", "purge_ticket"]
    # And because the breadcrumb was seen present, a clean advance produces NO ⚠️.
    upsert.assert_not_called()
