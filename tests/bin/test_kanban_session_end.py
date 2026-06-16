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

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kanbanmate.bin import kanban_session_end
from kanbanmate.bin.kanban_session_end import main
from kanbanmate.ports.store import TicketState, TicketStatus


def _state(issue: int = 7, *, stage: str = "Implement", advance: str = "") -> TicketState:
    """Build a widened :class:`TicketState` carrying a launch stage + metadata + advance."""
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
        advance=advance,
    )


def _columns() -> dict[str, object]:
    """Build the shipped column model (key → Column) for KEY→NAME resolution in the backstop."""
    from kanbanmate.core.columns import load_columns  # noqa: PLC0415 — test-local

    # A minimal column model mirroring the shipped template's key→name map so the backstop's
    # KEY→NAME resolution lands ("PRCI" → "PR/CI", "Blocked" → "Blocked").
    yaml_text = (
        "columns:\n"
        "  - {key: Spec, name: Spec}\n"
        "  - {key: Plan, name: Plan}\n"
        "  - {key: Planned, name: Planned}\n"
        "  - {key: InProgress, name: In Progress}\n"
        "  - {key: PRCI, name: PR/CI}\n"
        "  - {key: Blocked, name: Blocked}\n"
    )
    return load_columns(yaml_text)  # type: ignore[return-value]


def _patch_backstop_config(monkeypatch: pytest.MonkeyPatch, *, rate_limit: int = 10) -> None:
    """Stub the per-clone column + transition config loaders the auto-advance backstop reads."""
    monkeypatch.setattr(kanban_session_end, "load_clone_columns", lambda entry: _columns())
    cfg = MagicMock()
    cfg.move_rate_limit_per_hour = rate_limit
    monkeypatch.setattr(kanban_session_end, "load_clone_transitions", lambda entry: cfg)


def _patch_github(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stub the GitHub wiring (registry / token / client) and return the upsert spy."""
    monkeypatch.setattr(kanban_session_end, "_resolve_entry", lambda: MagicMock())
    monkeypatch.setattr(kanban_session_end, "load_token", lambda *a, **k: "tok")
    monkeypatch.setattr(kanban_session_end, "GithubClient", lambda *a, **k: MagicMock())
    upsert = MagicMock()
    monkeypatch.setattr(kanban_session_end, "upsert_stage_comment", upsert)
    return upsert


def _patch_github_capture_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stub the GitHub wiring with a SINGLE shared client and return it (for move_card asserts)."""
    monkeypatch.setattr(kanban_session_end, "_resolve_entry", lambda: MagicMock())
    monkeypatch.setattr(kanban_session_end, "load_token", lambda *a, **k: "tok")
    client = MagicMock()
    monkeypatch.setattr(kanban_session_end, "GithubClient", lambda *a, **k: client)
    monkeypatch.setattr(kanban_session_end, "upsert_stage_comment", MagicMock())
    return client


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
    """WITHOUT either breadcrumb → ⚠️ flip (finished ts set) on the stage sticky, slot released."""
    store = MagicMock()
    store.load.return_value = _state(stage="Implement")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = False  # NEITHER breadcrumb → the ⚠️ path (#FIX3)
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
    store.recent_agent_done.return_value = False  # NEITHER breadcrumb → the ⚠️ path (#FIX3)
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
    store.recent_agent_done.return_value = False  # NEITHER breadcrumb → the ⚠️ path (#FIX3)
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


# ---------------------------------------------------------------------------
# FIX 3 — done-without-advance finalizes ✅ done (not ⚠️ interrupted)
# ---------------------------------------------------------------------------


def test_done_without_advance_finalizes_done_not_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX 3: a clean kanban-done WITHOUT advance finalizes the stage sticky ✅ done (NOT ⚠️).

    The advance:stop stages (brainstorm/design/plan) complete by running kanban-done (a DONE
    breadcrumb) and NEVER advance their card. Before the fix, session-end wrongly finalized ⚠️
    interrupted; now it finalizes ✅ done — a clean completion is not a crash.
    """
    store = MagicMock()
    store.load.return_value = _state(stage="Design")
    store.recent_agent_advance.return_value = False  # never advanced (advance:stop stage)
    store.recent_agent_done.return_value = True  # but signalled a clean kanban-done
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    upsert = _patch_github(monkeypatch)

    assert main(["7"]) == 0
    store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    upsert.assert_called_once()
    args, kwargs = upsert.call_args
    assert args[1] == 7
    assert args[2] == "Design"
    header = kwargs["header"]
    # ✅ DONE — not ⚠️ interrupted — with a finished timestamp + full-parity metadata bullets.
    assert header.status == "done"
    assert header.finished != ""
    assert header.session == "sess-abc"
    assert header.profile == "docs"
    assert header.worktree == "ticket-7"


def test_done_without_advance_empty_stage_is_silent_no_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX 3: a done-without-advance with NO recorded stage → exit 0, slot released, NO GitHub I/O."""
    store = MagicMock()
    store.load.return_value = _state(stage="")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    upsert = _patch_github(monkeypatch)

    assert main(["7"]) == 0
    store.purge_ticket.assert_called_once_with(7, keep_budgets=True)
    upsert.assert_not_called()


def test_done_breadcrumb_read_before_purge_ticket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX 3 pre-purge ordering: the DONE breadcrumb is read BEFORE purge_ticket clears it.

    Uses a REAL :class:`FsStateStore`: a recent done marker (no advance) is set, then ``main`` runs.
    The ✅ DONE path can only be taken if the done read PRECEDED the purge that would have deleted
    ``done/<issue>``. Asserting the upsert carried ✅ "done" proves the load-bearing ordering.
    """
    import time  # noqa: PLC0415 — test-local import (hook-safe: used in the same edit)

    from kanbanmate.adapters.store.fs_store import FsStateStore  # noqa: PLC0415

    real_store = FsStateStore(root=tmp_path)
    real_store.save(_state(stage="Plan"))
    # A clean done-without-advance: a recent done marker, NO advance breadcrumb. ``main`` reads it
    # with its own ``time.time()`` now, so stamp the marker with a current ts (within the TTL).
    now = time.time()
    real_store.record_agent_done(7, now=now)
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: real_store)
    upsert = _patch_github(monkeypatch)

    assert main(["7"]) == 0
    # The state + done marker were purged (the slot is freed).
    assert real_store.load(7) is None
    assert real_store.recent_agent_done(7, now=now) is False
    # The ✅ DONE finalize fired — only possible if the done read PRECEDED the purge.
    upsert.assert_called_once()
    _args, kwargs = upsert.call_args
    assert kwargs["header"].status == "done"


# ---------------------------------------------------------------------------
# CHANGE 1 — engine auto-advance backstop (DESIGN §13 hybrid flow)
# ---------------------------------------------------------------------------


def test_done_with_advance_auto_moves_card_to_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean-done launch stage with advance=auto:<col> + NOT advanced → the engine moves it.

    The previously-dead advance:auto config is now honoured for launch stages: a done-without-
    advance whose persisted advance is ``auto:Spec`` is moved to Spec by the engine, and the move
    is recorded (so the daemon diff fires the next stage). The ✅ sticky is still finalized.
    """
    store = MagicMock()
    store.load.return_value = _state(stage="Brainstorming", advance="auto:Spec")
    store.recent_agent_advance.return_value = False  # the agent did NOT advance its own card
    store.recent_agent_done.return_value = True  # clean done
    store.move_count_for_item_last_hour.return_value = 0  # within the rate limit
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    # The engine moved the card to the advance target (KEY Spec → NAME "Spec").
    client.move_card.assert_called_once_with("PVTI_node", "Spec")
    # The move is recorded (feeds the rate-limit + makes the daemon diff fire the next stage) —
    # NOT an agent advance (that breadcrumb is the ✅/⚠️ discriminator; the sticky is already ✅).
    store.record_move_for_item.assert_called_once_with(
        7, now=store.recent_agent_done.call_args.kwargs["now"]
    )


def test_done_with_advance_auto_records_move_not_agent_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine move calls record_move_for_item, NEVER record_agent_advance (no masquerade)."""
    store = MagicMock()
    store.load.return_value = _state(stage="Spec", advance="auto:Plan")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.move_count_for_item_last_hour.return_value = 0
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_called_once_with("PVTI_node", "Plan")
    store.record_move_for_item.assert_called_once()
    store.record_agent_advance.assert_not_called()


def test_done_with_advance_stop_does_not_move(monkeypatch: pytest.MonkeyPatch) -> None:
    """advance=stop (the Planned/Review human gates) → NO engine move; the card STOPS."""
    store = MagicMock()
    store.load.return_value = _state(stage="Plan", advance="stop")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_not_called()  # the human-review gate: no auto-advance.
    store.record_move_for_item.assert_not_called()


def test_done_with_advance_empty_does_not_move(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty advance directive → NO engine move (old-format / no directive)."""
    store = MagicMock()
    store.load.return_value = _state(stage="Plan", advance="")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_not_called()


def test_advanced_agent_returns_before_backstop_no_move(monkeypatch: pytest.MonkeyPatch) -> None:
    """An agent that advanced its OWN card returns at branch 4 — the engine never double-moves."""
    store = MagicMock()
    store.load.return_value = _state(stage="Brainstorming", advance="auto:Spec")
    store.recent_agent_advance.return_value = True  # agent self-advanced → branch 4 early return
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_not_called()  # no engine move — the agent already advanced.


def test_interrupt_no_breadcrumb_does_not_auto_advance(monkeypatch: pytest.MonkeyPatch) -> None:
    """NEITHER breadcrumb (a crash/interrupt) → the ⚠️ path, NO auto-advance even with auto:<col>."""
    store = MagicMock()
    store.load.return_value = _state(stage="Brainstorming", advance="auto:Spec")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = False  # NEITHER → ⚠️ interrupted
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_not_called()  # an interrupt never auto-advances.


def test_auto_advance_rate_limited_parks_in_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """At/over the per-issue rate limit → parked in Blocked instead of advancing (anti-loop bound)."""
    store = MagicMock()
    store.load.return_value = _state(stage="Brainstorming", advance="auto:Spec")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.move_count_for_item_last_hour.return_value = 10  # >= cap (10) → park
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch, rate_limit=10)

    assert main(["7"]) == 0
    # The card is parked in Blocked (NOT moved to the target Spec) + a recap comment.
    client.move_card.assert_called_once_with("PVTI_node", "Blocked")
    client.comment.assert_called_once()
    assert "rate limit" in client.comment.call_args.args[1].lower()
    store.record_move_for_item.assert_called_once()


def test_auto_advance_key_to_name_resolution_multiword(monkeypatch: pytest.MonkeyPatch) -> None:
    """A multiword target KEY resolves to its display NAME: advance=auto:PRCI → move to "PR/CI"."""
    store = MagicMock()
    store.load.return_value = _state(stage="InProgress", advance="auto:PRCI")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.move_count_for_item_last_hour.return_value = 0
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_called_once_with("PVTI_node", "PR/CI")


def test_auto_advance_move_card_raises_is_fail_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    """A move_card error during auto-advance is swallowed — session-end still exits 0, no loop."""
    store = MagicMock()
    store.load.return_value = _state(stage="Brainstorming", advance="auto:Spec")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.move_count_for_item_last_hour.return_value = 0
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    client.move_card.side_effect = RuntimeError("github unreachable")
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0  # fail-soft: the always-run session-end never crashes.
    # The card was not advanced (the move raised) → no record_move_for_item (so no loop).
    store.record_move_for_item.assert_not_called()


def test_auto_advance_unknown_target_is_fail_soft_no_move(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An advance target that is not a known column → fail-soft no-op (no move, exit 0)."""
    store = MagicMock()
    store.load.return_value = _state(stage="Brainstorming", advance="auto:Nonsense")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.move_count_for_item_last_hour.return_value = 0
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_not_called()


def test_auto_advance_honours_kanban_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multi-root: the FsStateStore is constructed from the resolved KANBAN_ROOT (#1 km-root)."""
    seen_roots: list[object] = []

    def _store_factory(root: object) -> MagicMock:
        seen_roots.append(root)
        store = MagicMock()
        store.load.return_value = _state(stage="Spec", advance="auto:Plan")
        store.recent_agent_advance.return_value = False
        store.recent_agent_done.return_value = True
        store.move_count_for_item_last_hour.return_value = 0
        return store

    monkeypatch.setenv("KANBAN_ROOT", "/tmp/km-root")
    monkeypatch.setattr(kanban_session_end, "FsStateStore", _store_factory)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    # The store was keyed on the resolved KANBAN_ROOT (the move targets the right registry/root).
    assert seen_roots == ["/tmp/km-root"]
    client.move_card.assert_called_once_with("PVTI_node", "Plan")
