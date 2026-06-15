"""Tests for the decision core in :mod:`kanbanmate.core.decide` and the
dependency gate in :mod:`kanbanmate.core.dependency_gate`.

The decide tests exercise every :class:`ActionKind` branch and the precedence of
BLOCK over LAUNCH for whitelisted prompt-transitions.  Since the transitions-only
re-architecture (DESIGN §8.0.6) a whitelist is ALWAYS supplied and a prompt-bearing
whitelisted transition that passes the BLOCK guards LAUNCHes unconditionally — there
is no per-column agent-class gate, no dormant stage, and no ``transitions=None``
column-class fallback.  The dependency-gate tests cover the ready / not-ready
verdicts including the no-dependencies and missing-from-board edge cases.
"""

from __future__ import annotations

import importlib.resources

import pytest

from kanbanmate.core.antiloop import AntiLoopState, record_move
from kanbanmate.core.columns import load_columns
from kanbanmate.core.decide import DecideContext, decide
from kanbanmate.core.dependency_gate import evaluate, parse_dependencies
from kanbanmate.core.domain import (
    ActionKind,
    BoardSnapshot,
    Column,
    ColumnClass,
    Ticket,
    Transition,
)
from kanbanmate.core.transitions import TransitionConfig, load_transitions
from kanbanmate.core.transitions_defaults import default_transition_config

# A small board model reused across the decide tests: the columns whose CLASS the
# transitions-only ``decide`` still consults (REACTIVE for teardown/reset routing,
# INERT/terminal markers) plus the Backlog reset target. The columns carry NO
# launch configuration — the launch lives entirely on the transition (DESIGN §8.0.6).
COLUMNS: dict[str, Column] = {
    "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),
    "InProgress": Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),
    "Cancel": Column(key="Cancel", name="Cancel", column_class=ColumnClass.REACTIVE),
    "Done": Column(key="Done", name="Done", column_class=ColumnClass.INERT),
}

# The whitelist driving the shared board. ``Backlog -> InProgress`` carries a
# prompt (always LAUNCHes); the other edges are absent (un-whitelisted) so they
# exercise ROLLBACK / NOOP. A whitelist is ALWAYS supplied to ``decide``
# (transitions-only, DESIGN §8.0.6) — there is no column-class fallback.
_BOARD_WHITELIST = """
project: owner/repo
transitions:
  - from: Backlog
    to: InProgress
    prompt: "/implement:phase {{code}}"
    profile: dev
"""


def _whitelist() -> TransitionConfig:
    """Build the shared board whitelist (a prompt on ``Backlog -> InProgress``)."""
    return load_transitions(_BOARD_WHITELIST)


def _ctx(**kwargs: object) -> DecideContext:
    """Build a :class:`DecideContext` with the shared whitelist always supplied.

    The transitions-only ``decide`` requires a non-``None`` whitelist (DESIGN
    §8.0.6); this helper threads :func:`_whitelist` unless a caller overrides it.
    """
    kwargs.setdefault("transitions", _whitelist())
    return DecideContext(**kwargs)  # type: ignore[arg-type]


def _ticket(item_id: str = "item-1", issue_number: int | None = 42) -> Ticket:
    """Build a minimal :class:`Ticket` for decide tests."""
    return Ticket(item_id=item_id, issue_number=issue_number, title="t", column_key="x")


def _transition(to_column: str, from_column: str | None) -> Transition:
    """Build a :class:`Transition` for the shared ticket."""
    return Transition(ticket=_ticket(), from_column=from_column, to_column=to_column)


class TestDecideBranches:
    """Each transition maps to exactly one :class:`ActionKind`."""

    def test_prompt_transition_launches(self) -> None:
        """A whitelisted prompt-transition with no guards yields LAUNCH.

        ``Backlog -> InProgress`` carries a prompt, so it LAUNCHes unconditionally
        — the destination column's class is irrelevant (transitions-only, §8.0.6).
        """
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, _ctx())
        assert action.kind is ActionKind.LAUNCH

    def test_reactive_destination_tears_down(self) -> None:
        """A move into the reactive Cancel column yields TEARDOWN."""
        action = decide(_transition("Cancel", "InProgress"), COLUMNS, _ctx())
        assert action.kind is ActionKind.TEARDOWN

    def test_cancel_to_backlog_resets(self) -> None:
        """A Cancel → Backlog transition yields RESET, not teardown."""
        action = decide(_transition("Backlog", "Cancel"), COLUMNS, _ctx())
        assert action.kind is ActionKind.RESET

    def test_unwhitelisted_pair_rolls_back(self) -> None:
        """A move absent from the whitelist (Backlog → Done) rolls back to origin."""
        action = decide(_transition("Done", "Backlog"), COLUMNS, _ctx())
        assert action.kind is ActionKind.ROLLBACK
        assert action.to_column == "Backlog"

    def test_brand_new_unwhitelisted_is_noop(self) -> None:
        """A brand-new ticket (no origin) on an un-whitelisted move is a noop.

        A first-contact item (``from_column is None``) has no origin to bounce to,
        so an un-whitelisted move falls through to NOOP rather than ROLLBACK.
        """
        action = decide(_transition("Backlog", None), COLUMNS, _ctx())
        assert action.kind is ActionKind.NOOP

    def test_no_whitelist_is_hard_error(self) -> None:
        """``ctx.transitions is None`` is a wiring bug → hard error (no column fallback).

        After the transitions-only re-architecture a whitelist is ALWAYS supplied
        (the daemon falls back to DEFAULT_TRANSITIONS); a ``None`` must never
        silently degrade to a column-class model (DESIGN §8.0.6).
        """
        with pytest.raises(ValueError, match="transition whitelist"):
            decide(_transition("InProgress", "Backlog"), COLUMNS, DecideContext())


class TestReducedVerdictSet:
    """The 9→5 ActionKind reduction (genesis #23 KEEP+DOC) — the mapping is pinned.

    The PoC's 9-kind ``DecisionKind`` (``launch | run_script | noop | rollback`` + the runner's
    ``skip | queue | block | teardown | reset``) collapses to 5 ActionKind; ``skip`` re-homes to
    the tick dedup / diff baseline (an idempotent re-tick → NOOP, never a distinct ``skip``).
    """

    def test_action_kind_has_exactly_five_terminal_members(self) -> None:
        """``ActionKind`` exposes exactly the 5 terminal verdicts (+ the 2 phase-12 restorations).

        No ``SKIP``/``QUEUE`` member exists — they re-homed to the tick / reserve_slot path (#23).
        """
        members = {k.name for k in ActionKind}
        assert members == {
            "LAUNCH",
            "TEARDOWN",
            "RESET",
            "BLOCK",
            "NOOP",
            "ROLLBACK",
            "RUN_SCRIPT",
        }
        assert (
            "SKIP" not in members
        )  # the PoC `skip` is the tick's diff-baseline NOOP, not a verdict
        assert "QUEUE" not in members  # the PoC `queue` is the app-layer reserve_slot path

    def test_whitelisted_no_action_is_noop_not_skip(self) -> None:
        """A whitelisted no-action move yields NOOP — the home of the PoC ``skip`` verdict (#23)."""
        whitelist = load_transitions(
            """
project: owner/repo
transitions:
  - from: InProgress
    to: Done
"""
        )
        action = decide(_transition("Done", "InProgress"), COLUMNS, _ctx(transitions=whitelist))
        assert action.kind is ActionKind.NOOP


class TestBlockPrecedence:
    """BLOCK overrides LAUNCH for whitelisted prompt-transitions."""

    def test_kill_switch_blocks_launch(self) -> None:
        """With the kill-switch set, a prompt-transition is BLOCKed not LAUNCHed."""
        ctx = _ctx(kill_switch=True)
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, ctx)
        assert action.kind is ActionKind.BLOCK

    def test_antiloop_blocks_launch(self) -> None:
        """A tripped anti-loop guard BLOCKs an otherwise-launchable move."""
        # Record a recent move into InProgress so the dedup guard trips.
        state = record_move(AntiLoopState(), "item-1", "InProgress", now=100.0)
        ctx = _ctx(antiloop_state=state, now=101.0)
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, ctx)
        assert action.kind is ActionKind.BLOCK

    def test_kill_switch_does_not_block_teardown(self) -> None:
        """The kill-switch only guards launches; teardown still proceeds."""
        ctx = _ctx(kill_switch=True)
        action = decide(_transition("Cancel", "InProgress"), COLUMNS, ctx)
        assert action.kind is ActionKind.TEARDOWN

    def test_unblocked_move_launches(self) -> None:
        """An anti-loop move for a different target leaves the launch allowed."""
        state = record_move(AntiLoopState(), "item-1", "Review", now=100.0)
        ctx = _ctx(antiloop_state=state, now=101.0)
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, ctx)
        assert action.kind is ActionKind.LAUNCH


class TestActionReason:
    """Every action carries a human-readable reason."""

    def test_reason_mentions_kind_and_issue(self) -> None:
        """The reason names the chosen kind and the issue number."""
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, _ctx())
        assert "launch" in action.reason
        assert "#42" in action.reason


def _shipped_columns() -> dict[str, Column]:
    """Load the engine-bundled ``columns.yml.tmpl`` (the real default board).

    The shipped template deliberately uses key != name for the agent columns
    (``InProgress``/"In Progress", ``PRCI``/"PR/CI"), which is exactly the seam
    the name/key resolution must bridge. Loading the real asset (not a hand-built
    dict) proves the production board classifies correctly.
    """
    text = (importlib.resources.files("kanbanmate.assets") / "columns.yml.tmpl").read_text(
        encoding="utf-8"
    )
    return load_columns(text)


class TestAdapterNameSeam:
    """The adapter emits the Status option NAME; decide must still classify it.

    The github adapter sets ``Ticket.column_key`` (and thus ``transition.to_column``)
    to the GitHub Status option NAME (e.g. "In Progress"), while the column model is
    keyed by the stable KEY (e.g. "InProgress"). Before the name/key resolution these
    moves missed the model entirely — so a key-authored whitelist (DEFAULT_TRANSITIONS)
    never matched a name-authored board move. These tests exercise that real
    adapter→decide seam (key != name) against the shipped default whitelist.
    """

    def test_prompt_transition_by_option_name_launches(self) -> None:
        """A prompt-transition addressed by option NAMEs LAUNCHes via the key-authored whitelist.

        ``Prepare feature → In Progress`` carries the ``_IMPLEMENT_PROMPT`` in
        DEFAULT_TRANSITIONS (keyed ``PrepareFeature → InProgress``). The adapter
        emits the NAMES; name-then-key resolution must bridge them so the whitelist
        lookup hits and the prompt LAUNCHes.
        """
        columns = _shipped_columns()
        ctx = _ctx(transitions=default_transition_config())
        action = decide(_transition("In Progress", "Prepare feature"), columns, ctx)
        assert action.kind is ActionKind.LAUNCH

    def test_prompt_transition_by_key_still_launches(self) -> None:
        """The stable KEYs still resolve and LAUNCH (back-compat / config path)."""
        columns = _shipped_columns()
        ctx = _ctx(transitions=default_transition_config())
        action = decide(_transition("InProgress", "PrepareFeature"), columns, ctx)
        assert action.kind is ActionKind.LAUNCH

    def test_first_agent_step_by_option_name_launches(self) -> None:
        """``Backlog → Brainstorming`` (the interactive brainstorm step) LAUNCHes by NAMEs."""
        columns = _shipped_columns()
        ctx = _ctx(transitions=default_transition_config())
        action = decide(_transition("Brainstorming", "Backlog"), columns, ctx)
        assert action.kind is ActionKind.LAUNCH

    def test_cancel_option_name_tears_down(self) -> None:
        """The reactive Cancel option NAME resolves and tears down (column class seam)."""
        columns = _shipped_columns()
        ctx = _ctx(transitions=default_transition_config())
        action = decide(_transition("Cancel", "In Progress"), columns, ctx)
        assert action.kind is ActionKind.TEARDOWN

    def test_cancel_to_backlog_name_resets(self) -> None:
        """A Cancel → Backlog move (by name) still RESETs after resolution."""
        columns = _shipped_columns()
        ctx = _ctx(transitions=default_transition_config())
        action = decide(_transition("Backlog", "Cancel"), columns, ctx)
        assert action.kind is ActionKind.RESET

    def test_unknown_option_name_rolls_back(self) -> None:
        """A move to a column unknown to the whitelist rolls back to its origin."""
        columns = _shipped_columns()
        ctx = _ctx(transitions=default_transition_config())
        action = decide(_transition("Totally Unknown", "Backlog"), columns, ctx)
        assert action.kind is ActionKind.ROLLBACK

    def test_rollback_target_is_display_name_for_divergent_origin(self) -> None:
        """ROLLBACK carries the origin's DISPLAY NAME, not its stable key (defect 2).

        A baseline recorded as the KEY ("InProgress") never equals the snapshot NAME ("In
        Progress"), so the diff would re-fire the rollback every poll (endless recap comments).
        The bounce target/baseline must be the display NAME so it lands and does not re-loop.
        """
        columns = _shipped_columns()
        ctx = _ctx(transitions=default_transition_config())
        # In Progress → Done is un-whitelisted → ROLLBACK back to the origin "In Progress".
        action = decide(_transition("Done", "In Progress"), columns, ctx)
        assert action.kind is ActionKind.ROLLBACK
        assert action.to_column == "In Progress"


# A whitelist (authored in column KEYS) used by the precedence tests.
# ``Backlog -> InProgress`` is whitelisted with a prompt (it always LAUNCHes), so
# the reactive-routing precedence and the BLOCK-guard precedence can be asserted
# against a known-launching move.
_PRECEDENCE_WHITELIST = """
project: owner/repo
transitions:
  - from: Backlog
    to: InProgress
    prompt: "/implement:phase {{code}}"
    profile: dev
"""


class TestWhitelistPrecedence:
    """The whitelist layers under the reactive routing and over the BLOCK guards.

    These assert the fixed precedence (DESIGN §8.0.6): reactive routing wins
    BEFORE the whitelist verdict, and the BLOCK guards still downgrade a
    whitelisted prompt LAUNCH. A whitelist is ALWAYS supplied (transitions-only).
    """

    def test_reactive_teardown_wins_over_whitelist(self) -> None:
        """A move INTO Cancel tears down even with a whitelist present.

        Cancel is not in the whitelist; without the reactive-first precedence the
        whitelist would roll it back. The reactive routing must win first.
        """
        ctx = DecideContext(transitions=load_transitions(_PRECEDENCE_WHITELIST))
        action = decide(_transition("Cancel", "InProgress"), COLUMNS, ctx)
        assert action.kind is ActionKind.TEARDOWN

    def test_reactive_reset_wins_over_whitelist(self) -> None:
        """A Cancel → Backlog move resets even with a whitelist present."""
        ctx = DecideContext(transitions=load_transitions(_PRECEDENCE_WHITELIST))
        action = decide(_transition("Backlog", "Cancel"), COLUMNS, ctx)
        assert action.kind is ActionKind.RESET

    def test_kill_switch_blocks_whitelisted_launch(self) -> None:
        """The kill-switch downgrades a whitelisted prompt LAUNCH to BLOCK."""
        ctx = DecideContext(transitions=load_transitions(_PRECEDENCE_WHITELIST), kill_switch=True)
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, ctx)
        assert action.kind is ActionKind.BLOCK

    def test_antiloop_blocks_whitelisted_launch(self) -> None:
        """A tripped anti-loop guard downgrades a whitelisted LAUNCH to BLOCK."""
        state = record_move(AntiLoopState(), "item-1", "InProgress", now=100.0)
        ctx = DecideContext(
            transitions=load_transitions(_PRECEDENCE_WHITELIST),
            antiloop_state=state,
            now=101.0,
        )
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, ctx)
        assert action.kind is ActionKind.BLOCK


# A whitelist whose prompt-bearing edges target columns of DIFFERENT classes —
# ``Done`` (formerly inert) and ``InProgress``. Under the transitions-only model
# the destination column's class is irrelevant to LAUNCH: a prompt always launches.
_PROMPT_TRANSITIONS = """
project: owner/repo
transitions:
  - from: Backlog
    to: Done
    prompt: "/implement:brainstorm {{code}}"
    profile: docs
  - from: Backlog
    to: InProgress
    prompt: "/implement:phase {{code}}"
    profile: dev
"""


class TestTransitionsOnlyLaunch:
    """A whitelisted prompt-transition LAUNCHes regardless of destination class.

    The phase-12.6 HYBRID per-column agent-class gate is REMOVED (DESIGN §8.0.6).
    The launch lives entirely on the transition: a prompt-bearing whitelisted pair
    that passes the BLOCK guards LAUNCHes unconditionally — there is no dormant
    stage and no destination-column-class check (PoC parity: every stage launches).
    """

    def test_prompt_into_formerly_inert_destination_launches(self) -> None:
        """A whitelisted prompt into a (formerly-inert) column now LAUNCHes.

        ``Backlog → Done`` carries a prompt; ``Done`` is an inert/terminal column.
        Under the old HYBRID gate this was a dormant NOOP — it is now an
        unconditional LAUNCH carrying its routing (the inversion of the old test).
        """
        ctx = DecideContext(transitions=load_transitions(_PROMPT_TRANSITIONS))
        action = decide(_transition("Done", "Backlog"), COLUMNS, ctx)
        assert action.kind is ActionKind.LAUNCH
        assert action.prompt == "/implement:brainstorm {{code}}"
        assert action.profile == "docs"
        assert action.to_column == "Done"

    def test_prompt_into_any_destination_launches_with_routing(self) -> None:
        """A prompt transition LAUNCHes carrying its routing (prompt/profile/to_column)."""
        ctx = DecideContext(transitions=load_transitions(_PROMPT_TRANSITIONS))
        action = decide(_transition("InProgress", "Backlog"), COLUMNS, ctx)
        assert action.kind is ActionKind.LAUNCH
        assert action.prompt == "/implement:phase {{code}}"
        assert action.profile == "dev"
        assert action.to_column == "InProgress"


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets in a :class:`BoardSnapshot`."""
    return BoardSnapshot(tickets=tickets, fetched_at=0.0)


def _dep_ticket(issue_number: int, column_key: str) -> Ticket:
    """Build a ticket carrying an issue number and column for gate tests."""
    return Ticket(
        item_id=f"item-{issue_number}",
        issue_number=issue_number,
        title="t",
        column_key=column_key,
    )


class TestParseDependencies:
    """Parsing of ``Depends on #N`` references from an issue body."""

    def test_no_dependencies(self) -> None:
        """A body without the marker yields no dependencies."""
        assert parse_dependencies("Just a plain issue body.") == []

    def test_case_insensitive_and_multiple(self) -> None:
        """References are matched case-insensitively and de-duplicated in order."""
        body = "Depends on #5\nAlso DEPENDS ON #7 and depends on #5 again."
        assert parse_dependencies(body) == [5, 7]


class TestDependencyGate:
    """Tri-state verdict evaluation (#13). The exhaustive contract lives in
    ``tests/core/test_dependency_gate.py``; these pin the verdict shape from
    ``decide``'s neighbourhood after the snapshot-only → tri-state refactor."""

    def test_no_dependencies_is_met(self) -> None:
        """A ticket with no dependencies is fully met by the snapshot alone."""
        verdict = evaluate("No deps here.", _snapshot())
        assert verdict.fully_met() is True
        assert verdict.unresolved == ()
        assert "no declared dependencies" in verdict.reason

    def test_all_dependencies_done_is_met(self) -> None:
        """All dependencies in a done column makes the ticket fully met."""
        snapshot = _snapshot(_dep_ticket(5, "Done"), _dep_ticket(7, "Merge"))
        verdict = evaluate("Depends on #5\nDepends on #7", snapshot)
        assert verdict.fully_met() is True
        assert "all dependencies satisfied" in verdict.reason

    def test_unmet_dependency_blocks(self) -> None:
        """A dependency still in progress is a hard block (``met`` is ``False``)."""
        snapshot = _snapshot(_dep_ticket(5, "InProgress"))
        verdict = evaluate("Depends on #5", snapshot)
        assert verdict.met is False
        assert verdict.unresolved == ()
        assert "#5 (in InProgress)" in verdict.reason

    def test_dependency_absent_from_board_is_unresolved(self) -> None:
        """A dependency absent from the board is UNKNOWN → reported for the live fallback.

        The pure gate no longer blocks an off-board dep (the snapshot cannot decide it);
        it reports it in ``unresolved`` so the imperative shell resolves it via
        ``issue_state`` (#13 hybrid gate). ``met`` reflects only the on-board deps.
        """
        verdict = evaluate("Depends on #99", _snapshot())
        assert verdict.met is True
        assert verdict.unresolved == (99,)
        assert verdict.fully_met() is False
        assert "#99" in verdict.reason
