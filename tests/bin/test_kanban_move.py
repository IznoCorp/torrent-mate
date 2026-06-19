"""Tests for the ``kanban-move`` agent helper (:mod:`kanbanmate.bin.kanban_move`).

Since 0.4.0 (move-unification) the helper ENQUEUES a ``move`` intent into the SAME ``intents/`` queue
the operator uses rather than calling GitHub directly — the daemon is the sole board writer. The
contracts under test:

* it enqueues a ``move`` intent carrying the canonical column KEY + ``caller="agent"`` (advisory);
* it is **network-free** (no GitHub client / token — the helper no longer talks to GitHub);
* it nudges the daemon after enqueuing (so the move drains near-instantly);
* it writes the advance breadcrumb SYNCHRONOUSLY (keyed by ISSUE number) ONLY on a CONFIRMED
  (non-rejected) move — i.e. the ``--wait`` ``done``/timeout path; ``--no-wait`` writes NONE (it
  cannot confirm the move, so it must not leave a false ✅);
* the cheap pre-flight anti-loop guard (DESIGN §8.0.5) refuses a launch-transition target BEFORE
  enqueuing (UX guard; the daemon is authoritative);
* the R1 pin mismatch refuses BEFORE any write;
* ``--wait`` (default) writes NO breadcrumb + returns 1 on a daemon ``rejected`` result, and writes
  the breadcrumb + returns 0 on ``done``; ``--no-wait`` returns 0 immediately after enqueue and writes
  no breadcrumb at all.

A fake store records the enqueue/nudge/breadcrumb calls so no test touches the network; the column
model and the transition whitelist are supplied directly so nothing is read off the clone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from kanbanmate.bin import kanban_move
from kanbanmate.bin.kanban_move import main, resolve_target_column
from kanbanmate.core.domain import Column, ColumnClass
from kanbanmate.core.transitions import load_transitions

# A small board model covering the columns the launch-target tests target. The
# ``column_class`` here is irrelevant to the guard (which keys on the transition
# whitelist, not the class, DESIGN §8.0.5) — it only satisfies the Column model; the
# guard verdict comes entirely from ``_TRANSITIONS`` below.
_COLUMNS: dict[str, Column] = {
    "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),
    "ReadyToDev": Column(key="ReadyToDev", name="Ready to dev", column_class=ColumnClass.INERT),
    "InProgress": Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),
    "PRCI": Column(key="PRCI", name="PR/CI", column_class=ColumnClass.INERT),
    "Review": Column(key="Review", name="Review", column_class=ColumnClass.INERT),
    "Cancel": Column(key="Cancel", name="Cancel", column_class=ColumnClass.REACTIVE),
    "Merge": Column(key="Merge", name="Merge", column_class=ColumnClass.INERT),
    "Done": Column(key="Done", name="Done", column_class=ColumnClass.INERT),
}

# A transition whitelist mirroring the load-bearing shape of DEFAULT_TRANSITIONS: the
# prompt-bearing rows (PrepareFeature→InProgress, PRCI→Review, Review→Merge — the autonomous merge
# AGENT), the SCRIPT-gate row (InProgress→PRCI, engine-owned — no prompt), the Merge→Review blocker
# route + Merge→Done success route (no-ops), and inert no-ops (Backlog, ReadyToDev, Done reachable).
# The pre-flight guard keys on whether the SPECIFIC (from, to) pair is TRIGGERING (prompt OR script),
# NOT on the destination being some launch target.
_TRANSITIONS = load_transitions(
    "project: test/repo\n"
    "transitions:\n"
    "  - {from: 'Backlog', to: 'ReadyToDev'}\n"  # no-op → ReadyToDev is inert
    "  - {from: 'PrepareFeature', to: 'InProgress', prompt: 'implement'}\n"
    "  - {from: 'InProgress', to: 'PRCI', script: 'check-pr-ready.sh'}\n"  # SCRIPT-gate (engine-owned)
    "  - {from: 'PRCI', to: 'Review', prompt: 'review'}\n"
    "  - {from: 'Review', to: 'Merge', prompt: 'merge'}\n"  # autonomous merge agent (prompt-bearing)
    "  - {from: 'Merge', to: 'Done'}\n"  # success route (no-op)
    "  - {from: 'Merge', to: 'Review'}\n"  # blocker route (no-op) — must NOT be refused
    "  - {from: '*', to: 'Cancel'}\n"  # reactive no-op
)


@dataclass
class FakeStore:
    """A store double recording enqueue / nudge / breadcrumb calls (never hits the network).

    ``record_agent_advance`` records the ``(issue, now)`` pair so a test can assert the breadcrumb
    was dropped keyed by ISSUE number (the 8.1.d invariant). ``load_intent_result`` returns an
    injected terminal result so the ``--wait`` paths can be exercised. Setting ``raise_on_advance``
    makes the breadcrumb write blow up so the warn-not-abort path is exercised.
    """

    result: dict[str, object] | None = None
    raise_on_advance: bool = False
    intents: dict[str, dict[str, object]] = field(default_factory=dict)
    advances: list[tuple[int, float]] = field(default_factory=list)
    cleared: list[int] = field(default_factory=list)
    nudges: int = 0
    # Injected running-agent state for the pair-aware pre-flight guard; None = no running agent
    # (operator use), which skips the guard (the daemon stays authoritative).
    loaded_state: object | None = None

    def load(self, issue_number: int) -> object | None:
        return self.loaded_state

    def enqueue_intent(self, intent_id: str, payload: dict[str, object]) -> None:
        self.intents[intent_id] = dict(payload)

    def nudge_daemon(self) -> None:
        self.nudges += 1

    def record_agent_advance(self, issue_number: int, *, now: float) -> None:
        if self.raise_on_advance:
            raise OSError("disk full")
        self.advances.append((issue_number, now))

    def clear_agent_advance(self, issue_number: int) -> None:
        self.cleared.append(issue_number)

    def load_intent_result(self, intent_id: str) -> dict[str, object] | None:
        return self.result


@dataclass(frozen=True)
class _FakeEntry:
    """A minimal stand-in for :class:`~kanbanmate.cli.init.ProjectEntry`."""

    repo: str = "IznoCorp/demo"
    project_id: str = "PVT_PROJECT"
    clone: str = "/tmp/clone"
    status_field_node_id: str = "PVTSSF"
    option_map: dict[str, str] = field(default_factory=dict)


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: dict[str, object] | None = None,
    raise_on_advance: bool = False,
    stage: str | None = None,
) -> FakeStore:
    """Patch registry/columns/transitions/store so ``main`` uses the fakes (no GitHub).

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        result: The terminal result the fake store's ``load_intent_result`` returns (for ``--wait``).
        raise_on_advance: When ``True``, the fake store's ``record_agent_advance`` raises so the
            breadcrumb-write-failure (warn-not-abort) path is exercised.

    Returns:
        The :class:`FakeStore` wired in, so a test can assert the recorded enqueue/nudge/advances.
    """
    # ``stage`` injects a running-agent state so the pair-aware pre-flight guard has a from_col;
    # None (default) = no running agent (operator use) → the guard is skipped (daemon authoritative).
    loaded = SimpleNamespace(stage=stage) if stage is not None else None
    store = FakeStore(result=result, raise_on_advance=raise_on_advance, loaded_state=loaded)
    monkeypatch.setattr(kanban_move, "_resolve_entry", lambda: _FakeEntry())
    monkeypatch.setattr(kanban_move, "_load_clone_columns", lambda entry: _COLUMNS)
    monkeypatch.setattr(kanban_move, "_load_clone_transitions", lambda entry: _TRANSITIONS)
    monkeypatch.setattr(kanban_move, "FsStateStore", lambda *a, **k: store)
    # Make --wait poll instantly (no real sleep) so the wait tests don't burn 15 s. Patch the global
    # ``time`` module the helper imports (string path avoids mypy's no-implicit-reexport on the attr).
    monkeypatch.setattr("kanbanmate.bin.kanban_move.time.sleep", lambda _s: None)
    return store


def _only_intent(store: FakeStore) -> dict[str, object]:
    """Return the single enqueued intent payload (fails if not exactly one)."""
    assert len(store.intents) == 1, f"expected exactly one intent, got {len(store.intents)}"
    return next(iter(store.intents.values()))


# ---------------------------------------------------------------------------
# resolve_target_column: key OR name resolution
# ---------------------------------------------------------------------------


def test_resolve_target_column_by_key() -> None:
    """A column is resolvable by its stable ``key``."""
    assert resolve_target_column(_COLUMNS, "InProgress").name == "In Progress"


def test_resolve_target_column_by_name() -> None:
    """A column is also resolvable by its human-readable ``name``."""
    assert resolve_target_column(_COLUMNS, "In Progress").key == "InProgress"


def test_resolve_target_column_unknown_raises() -> None:
    """An unknown target raises ``KeyError`` listing the known columns."""
    with pytest.raises(KeyError):
        resolve_target_column(_COLUMNS, "Nope")


# ---------------------------------------------------------------------------
# Enqueue path: the move now goes through the intent queue (0.4.0 unification)
# ---------------------------------------------------------------------------


def test_enqueues_move_intent_with_column_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-launch target enqueues a ``move`` intent carrying the column KEY + advisory caller."""
    store = _wire(monkeypatch)
    # --no-wait so we assert the bare enqueue without polling for a result.
    assert main(["7", "Done", "--no-wait"]) == 0
    payload = _only_intent(store)
    assert payload["kind"] == "move"
    assert payload["issue"] == 7
    assert payload["args"] == {"to_col": "Done"}  # column KEY, not name
    assert payload["caller"] == "agent"  # ADVISORY only — the daemon derives authority


def test_enqueues_key_when_given_a_human_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """A target given as a human NAME is resolved locally to its canonical KEY before enqueue."""
    store = _wire(monkeypatch)
    assert main(["7", "Ready to dev", "--no-wait"]) == 0
    assert _only_intent(store)["args"] == {"to_col": "ReadyToDev"}


def test_helper_is_network_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper no longer constructs a GitHub client or loads a token (network-free, 0.4.0)."""
    _wire(monkeypatch)
    # The direct-GitHub wiring is gone — these names must not even exist on the module any more.
    assert not hasattr(kanban_move, "GithubClient")
    assert not hasattr(kanban_move, "load_token")
    # And nothing in main() reaches GitHub: a --no-wait run completes purely against the fake store.
    assert main(["7", "Done", "--no-wait"]) == 0


def test_enqueue_nudges_the_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper nudges the daemon after enqueuing so the move drains near-instantly (0.4.0)."""
    store = _wire(monkeypatch)
    assert main(["7", "Done", "--no-wait"]) == 0
    assert store.nudges == 1


# ---------------------------------------------------------------------------
# Cheap pre-flight anti-loop guard (DESIGN §8.0.5) — refuses a launch target
# ---------------------------------------------------------------------------


def test_refuses_re_fire_pair_no_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    """REFUSE: an agent move whose (from, to) pair is itself prompt-bearing would re-fire a launch.

    The pre-flight is PAIR-aware: it reads the agent's launched stage (from_col) and refuses ONLY a
    move that re-fires a prompt-bearing transition. Here the agent was launched at ``PrepareFeature``;
    moving to ``InProgress`` re-fires ``PrepareFeature → InProgress`` → refused BEFORE enqueuing (the
    daemon's wildcard-aware check is authoritative, but this is the fast UX path).
    """
    store = _wire(monkeypatch, stage="PrepareFeature")
    assert main(["7", "InProgress"]) == 1
    assert main(["7", "In Progress"]) == 1  # by human name (resolved to its key) too
    # The whole point: no intent was ever enqueued for a re-fire.
    assert store.intents == {}
    assert store.nudges == 0


def test_refuses_script_gate_pair_no_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    """REFUSE (BUG B): an agent move into a SCRIPT-gate column is refused early (no enqueue).

    ``InProgress → PR/CI`` carries a SCRIPT but no prompt — it is engine-owned (only the daemon's
    RUN_SCRIPT path enters it). Before the fix the cheap pre-flight keyed on ``pair.prompt`` only, so
    this move was ACCEPTED and the in-memory diff baseline jumped past the gate → ``check-pr-ready.sh``
    + auto:Review + the ✅ left-stage finalize were all skipped. The widened ``pair.has_action`` guard
    (prompt OR script) now refuses it BEFORE enqueuing, in parity with the daemon-side guard.
    """
    store = _wire(monkeypatch, stage="InProgress")
    assert main(["7", "PRCI"]) == 1
    assert main(["7", "PR/CI"]) == 1  # by human name too
    assert store.intents == {}
    assert store.nudges == 0


def test_operator_move_to_launch_target_not_re_fire_guarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW: with no running agent (operator use) the pre-flight is skipped — operator moves are
    not re-fire-guarded (the daemon derives operator authority). Even a launch-target dest enqueues.
    """
    store = _wire(monkeypatch)  # no stage → no running state
    assert main(["7", "InProgress", "--no-wait"]) == 0
    assert _only_intent(store)["args"] == {"to_col": "InProgress"}


def test_allows_move_to_launch_target_from_non_firing_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW (audit regression): the merge agent in ``Merge`` routing a blocked merge to ``Review``
    must NOT be refused — ``(Merge, Review)`` is a no-op edge, even though ``Review`` is a launch
    target via ``PRCI → Review``. The prior destination-only guard wrongly refused this and stranded
    the card in Merge. The success route ``Merge → Done`` is likewise allowed.
    """
    store = _wire(monkeypatch, stage="Merge")
    assert main(["7", "Review", "--no-wait"]) == 0  # blocker route — NOT refused
    assert _only_intent(store)["args"] == {"to_col": "Review"}
    store2 = _wire(monkeypatch, stage="Merge")
    assert main(["7", "Done", "--no-wait"]) == 0  # success route
    assert _only_intent(store2)["args"] == {"to_col": "Done"}


def test_enqueues_to_inert_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLOW: a non-launch (inert/terminal) target enqueues a move."""
    store = _wire(monkeypatch)
    assert main(["7", "Backlog", "--no-wait"]) == 0
    assert _only_intent(store)["args"] == {"to_col": "Backlog"}


def test_agent_in_review_refused_moving_into_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    """REFUSE: an agent launched at ``Review`` moving to ``Merge`` re-fires the merge agent —
    ``(Review, Merge)`` is prompt-bearing — so the pre-flight refuses (a human, not an agent, lands a
    card in Merge to trigger the autonomous merge). An operator move (no running state) is allowed.
    """
    store = _wire(monkeypatch, stage="Review")
    assert main(["7", "Merge"]) == 1
    assert store.intents == {}
    # Operator (no running state) may land a card in Merge to trigger the merge agent.
    op_store = _wire(monkeypatch)
    assert main(["7", "Merge", "--no-wait"]) == 0
    assert _only_intent(op_store)["args"] == {"to_col": "Merge"}


# ---------------------------------------------------------------------------
# main(): argv + wiring failure handling
# ---------------------------------------------------------------------------


def test_bad_arity_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrong number of positionals is a usage error (exit 2), nothing enqueued."""
    store = _wire(monkeypatch)
    assert main(["7"]) == 2
    assert main(["7", "Backlog", "extra"]) == 2
    assert store.intents == {}


def test_non_int_issue_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-integer issue is rejected (exit 2), not a crash."""
    store = _wire(monkeypatch)
    assert main(["notanint", "Backlog"]) == 2
    assert store.intents == {}


def test_hash_prefixed_issue_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A leading ``#`` on the issue arg is stripped defensively (defect 3), not rejected."""
    store = _wire(monkeypatch)
    assert main(["#7", "Backlog", "--no-wait"]) == 0
    assert _only_intent(store)["issue"] == 7


def test_wiring_failure_exits_one_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry/token failure is caught and reported (exit 1), never a traceback."""

    def _boom() -> _FakeEntry:
        raise RuntimeError("no registered project")

    monkeypatch.setattr(kanban_move, "_resolve_entry", _boom)
    assert main(["7", "Backlog", "--no-wait"]) == 1


# ---------------------------------------------------------------------------
# R1 pin enforcement — refuses a mismatched worktree pin BEFORE any write
# ---------------------------------------------------------------------------


def test_pin_mismatch_refuses_before_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    """A worktree pinned to a DIFFERENT issue refuses (exit 1) and enqueues nothing (R1, layer 1)."""
    store = _wire(monkeypatch)
    monkeypatch.setattr(kanban_move, "check_pin", lambda issue, **k: "refusing: pinned to #99")
    assert main(["7", "Backlog"]) == 1
    assert store.intents == {}
    assert store.nudges == 0
    assert store.advances == []


# ---------------------------------------------------------------------------
# Advance breadcrumb — written ONLY on a confirmed (non-rejected) move
# ---------------------------------------------------------------------------


def test_no_breadcrumb_under_no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--no-wait`` enqueues the move but writes NO advance breadcrumb (the false-✅ fix).

    Under ``--no-wait`` the helper returns immediately and never polls the daemon's terminal result,
    so it cannot tell an accepted move from a daemon-REJECTED one. Writing the optimistic breadcrumb
    there would leave a FALSE ✅ on a rejected move — so it must write NONE. The intent is still
    enqueued + nudged (those are unconditional); only the breadcrumb is gated on confirmation.
    """
    store = _wire(monkeypatch)
    assert main(["7", "Backlog", "--no-wait"]) == 0
    assert len(store.intents) == 1  # the move IS enqueued
    assert store.nudges == 1  # and the daemon nudged
    assert store.advances == []  # but NO breadcrumb (the move is unconfirmed under --no-wait)


def test_advance_breadcrumb_failure_does_not_fail_the_move(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A breadcrumb-write failure on a confirmed move warns to stderr but NEVER aborts (warn-not-abort).

    The move is already enqueued + confirmed ``done``, so a failing ``record_agent_advance`` must not
    change the exit code — the helper still returns ``0`` and only logs a warning. Exercised on the
    ``--wait`` ``done`` path (the only path that writes the breadcrumb now).
    """
    store = _wire(
        monkeypatch,
        result={"state": "done", "detail": "moved Backlog->Done"},
        raise_on_advance=True,
    )
    assert main(["7", "Backlog"]) == 0  # default --wait, daemon confirmed done
    assert len(store.intents) == 1  # the intent landed despite the breadcrumb failure
    assert "warning" in capsys.readouterr().err.lower()


def test_no_breadcrumb_when_refused_for_re_fire(monkeypatch: pytest.MonkeyPatch) -> None:
    """An anti-loop pre-flight refusal (a re-fire pair) enqueues nothing and drops no breadcrumb."""
    store = _wire(
        monkeypatch, stage="PrepareFeature"
    )  # PrepareFeature→InProgress is prompt-bearing
    assert main(["7", "InProgress"]) == 1
    assert store.intents == {}
    assert store.advances == []


# ---------------------------------------------------------------------------
# --wait: terminal result handling (done writes the breadcrumb; rejected writes none)
# ---------------------------------------------------------------------------


def test_wait_done_returns_zero_and_writes_breadcrumb(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--wait`` (default) on a daemon ``done`` result returns 0 and WRITES the breadcrumb.

    The breadcrumb is written ONLY here (a confirmed move), keyed by the issue (``7``), so
    session-end reads it as ✅ advanced.
    """
    store = _wire(monkeypatch, result={"state": "done", "detail": "moved Backlog->Done"})
    assert main(["7", "Done"]) == 0  # default --wait
    assert [issue for issue, _ in store.advances] == [7]  # breadcrumb written on confirmation


def test_wait_reject_writes_no_breadcrumb_and_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--wait`` on a daemon ``rejected`` result writes NO breadcrumb and returns 1.

    A refused move must not leave a false ✅-signal for session-end to read. Because the breadcrumb is
    now written only on a CONFIRMED move (never optimistically at enqueue), a rejection simply drops
    nothing — there is no breadcrumb to clear.
    """
    store = _wire(monkeypatch, result={"state": "rejected", "detail": "would re-fire a launch"})
    assert main(["7", "Done"]) == 1
    assert store.advances == []  # never written for a rejected move
    assert store.cleared == []  # nothing to clear (none was ever written)


def test_wait_timeout_writes_breadcrumb_and_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--wait`` that times out (no terminal result) writes the breadcrumb (benign-accept) + returns 0.

    A timeout is benign — the daemon still applies the un-rejected move on a later tick — so the
    breadcrumb is written (the expected outcome is acceptance) and the helper returns 0.
    """
    # No injected result → load_intent_result returns None forever → the wait loop times out.
    store = _wire(monkeypatch, result=None)
    # Make the deadline fire after one poll so the test does not burn the real 15 s budget.
    monkeypatch.setattr("kanbanmate.bin.kanban_move._WAIT_TIMEOUT_SECONDS", 0.0)
    assert main(["7", "Done"]) == 0
    assert [issue for issue, _ in store.advances] == [7]  # benign-accept → breadcrumb written


def test_no_wait_returns_zero_without_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--no-wait`` returns 0 immediately after enqueue (no result polling, NO breadcrumb)."""
    # A rejected result is injected, but --no-wait must NOT read it (and writes no breadcrumb anyway).
    store = _wire(monkeypatch, result={"state": "rejected", "detail": "x"})
    assert main(["7", "Done", "--no-wait"]) == 0
    assert store.advances == []  # --no-wait never confirms, so never writes
    assert store.cleared == []  # and never clears


# ---------------------------------------------------------------------------
# $KANBAN_ROOT routing
# ---------------------------------------------------------------------------


def test_kanban_root_env_routes_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    """``$KANBAN_ROOT`` is passed to the store so the enqueue targets the launching daemon's root."""
    captured: dict[str, object] = {}

    def _capture_store(root: object = None, *a: object, **k: object) -> FakeStore:
        captured["root"] = root
        return FakeStore()

    monkeypatch.setenv("KANBAN_ROOT", "/tmp/kanban-km")
    monkeypatch.setattr(kanban_move, "_resolve_entry", lambda: _FakeEntry())
    monkeypatch.setattr(kanban_move, "_load_clone_columns", lambda entry: _COLUMNS)
    monkeypatch.setattr(kanban_move, "_load_clone_transitions", lambda entry: _TRANSITIONS)
    monkeypatch.setattr(kanban_move, "FsStateStore", _capture_store)

    assert main(["7", "Backlog", "--no-wait"]) == 0
    assert captured["root"] == "/tmp/kanban-km"
