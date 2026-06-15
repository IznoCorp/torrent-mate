"""Whitelist-verdict tests for :func:`kanbanmate.core.decide.decide`.

These port the PoC ``tests/test_decide_transition.py`` + ``tests/test_transitions.py``
verdict assertions onto NEW's ``decide``: with a
:class:`~kanbanmate.core.transitions.TransitionConfig` supplied via
:class:`~kanbanmate.core.decide.DecideContext`, a concrete ``(from, to)`` move is
classified launch | run_script | noop | rollback exactly as the PoC's pure
``decide_transition`` did — while NEW additionally carries the per-transition
routing fields onto the resulting :class:`~kanbanmate.core.domain.Action`.

The load-bearing cases are:

* an **unlisted** pair → ROLLBACK whose ``to_column`` is the bounce target
  (``from_col``);
* a **first-contact** item (``from_column is None``) into an unlisted column →
  NOOP, never a rollback (no origin to bounce to);
* a **name-vs-key** move resolves to the right whitelist entry (the whitelist is
  authored in column KEYS, the board emits Status NAMES).
"""

from __future__ import annotations

from kanbanmate.core.decide import DecideContext, decide
from kanbanmate.core.domain import (
    Action,
    ActionKind,
    Column,
    ColumnClass,
    Ticket,
    Transition,
)
from kanbanmate.core.transitions import load_transitions

# A board model exercising the name/key seam: a column's name ("In Progress")
# differs from its key ("InProgress"), so a whitelist authored in keys must still
# match a board move authored in names. In the transitions-only model (§8.0.6) the
# column class does NOT gate the launch — every non-reactive column is INERT and a
# whitelisted prompt-transition launches regardless.
COLUMNS: dict[str, Column] = {
    "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),
    "Planned": Column(key="Planned", name="Planned", column_class=ColumnClass.INERT),
    "InProgress": Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),
    "PRCI": Column(key="PRCI", name="PR/CI", column_class=ColumnClass.INERT),
    "ReadyToDev": Column(key="ReadyToDev", name="Ready to dev", column_class=ColumnClass.INERT),
    "Done": Column(key="Done", name="Done", column_class=ColumnClass.INERT),
}


def _ticket(item_id: str = "item-1", issue_number: int | None = 42) -> Ticket:
    """Build a minimal :class:`Ticket` for the verdict tests."""
    return Ticket(item_id=item_id, issue_number=issue_number, title="t", column_key="x")


def _transition(to_column: str, from_column: str | None) -> Transition:
    """Build a :class:`Transition` for the shared ticket."""
    return Transition(ticket=_ticket(), from_column=from_column, to_column=to_column)


def _decide(to_column: str, from_column: str | None, yaml_text: str) -> Action:
    """Decide a single move against a whitelist parsed from ``yaml_text``."""
    ctx = DecideContext(transitions=load_transitions(yaml_text))
    return decide(_transition(to_column, from_column), COLUMNS, ctx)


# A whitelist authored in column KEYS covering each verdict shape.
WHITELIST = """
project: owner/repo
transitions:
  - from: Planned
    to: InProgress
    prompt: "/implement:phase {{code}}"
    profile: dev
    permission_mode: auto
    advance: "auto:PRCI"
    on_fail: "move:Blocked"
  - from: InProgress
    to: PRCI
    script: bin/check-pr-ready.sh
    on_fail: "move:InProgress"
    advance: stop
  - from: Planned
    to: ReadyToDev
  - from: ReadyToDev
    to: InProgress
    prompt: "/implement:phase {{code}}"
    script: bin/gate.sh
    profile: dev
"""


class TestWhitelistVerdicts:
    """Each whitelisted/un-whitelisted move maps to the right verdict."""

    def test_whitelisted_prompt_launches_carrying_prompt(self) -> None:
        """A pair with a prompt → LAUNCH carrying the prompt + routing fields."""
        action = _decide("InProgress", "Planned", WHITELIST)
        assert action.kind is ActionKind.LAUNCH
        assert action.prompt == "/implement:phase {{code}}"
        assert action.profile == "dev"
        assert action.permission_mode == "auto"
        assert action.advance == "auto:PRCI"
        assert action.on_fail == "move:Blocked"
        # The LAUNCH records the resolved destination KEY.
        assert action.to_column == "InProgress"

    def test_script_only_runs_script_carrying_on_fail_and_advance(self) -> None:
        """A script-but-no-prompt pair → RUN_SCRIPT carrying on_fail/advance."""
        action = _decide("PRCI", "InProgress", WHITELIST)
        assert action.kind is ActionKind.RUN_SCRIPT
        assert action.script == "bin/check-pr-ready.sh"
        assert action.on_fail == "move:InProgress"
        assert action.advance == "stop"
        assert action.prompt is None
        assert action.to_column == "PRCI"

    def test_allowed_no_op_is_noop(self) -> None:
        """A whitelisted pair with neither prompt nor script → NOOP."""
        action = _decide("ReadyToDev", "Planned", WHITELIST)
        assert action.kind is ActionKind.NOOP
        assert action.to_column == "ReadyToDev"

    def test_unlisted_pair_rolls_back_to_from_col(self) -> None:
        """An un-whitelisted pair → ROLLBACK whose to_column is the bounce target.

        This is load-bearing: ``Action.to_column`` carries the ``from_col`` the
        card must be returned to (mirroring the PoC ``Decision.column`` dual use).
        """
        action = _decide("Done", "InProgress", WHITELIST)
        assert action.kind is ActionKind.ROLLBACK
        # Bounce target is the resolved origin's DISPLAY NAME (defect 2), not the rejected
        # destination and not the stable key: the baseline must equal the snapshot NAME or the
        # diff re-fires the rollback every poll (endless recap comments).
        assert action.to_column == "In Progress"

    def test_launch_with_both_script_and_prompt_launches_carrying_both(self) -> None:
        """A launch transition gated by a script → LAUNCH carrying both."""
        action = _decide("InProgress", "ReadyToDev", WHITELIST)
        assert action.kind is ActionKind.LAUNCH
        assert action.prompt == "/implement:phase {{code}}"
        assert action.script == "bin/gate.sh"
        assert action.profile == "dev"

    def test_first_contact_into_unlisted_column_is_noop(self) -> None:
        """A first-contact item (from_column is None) into an unlisted column → NOOP.

        There is no origin to bounce to, so the rollback carve-out downgrades it
        to a recording NOOP rather than a rollback.
        """
        action = _decide("Done", None, WHITELIST)
        assert action.kind is ActionKind.NOOP

    def test_first_contact_into_listed_prompt_column_still_rolls_through(self) -> None:
        """A first-contact item lands NOOP even into a column listed only with a from.

        ``Planned->InProgress`` is whitelisted but ``None->InProgress`` is not, and
        a first-contact item has no origin — so it records a NOOP, never launches
        off a wildcard it does not match and never rolls back.
        """
        action = _decide("InProgress", None, WHITELIST)
        assert action.kind is ActionKind.NOOP


class TestNameVsKeyResolution:
    """A board move authored in NAMES resolves to a key-authored whitelist entry."""

    def test_name_move_resolves_to_key_entry(self) -> None:
        """`Planned -> "In Progress"` (NAME) matches the `Planned -> InProgress` (KEY) entry."""
        # The board emits the Status NAME "In Progress"; the whitelist is keyed by
        # "InProgress". Resolution must bridge the seam → the prompt LAUNCH fires.
        action = _decide("In Progress", "Planned", WHITELIST)
        assert action.kind is ActionKind.LAUNCH
        assert action.prompt == "/implement:phase {{code}}"
        assert action.to_column == "InProgress"

    def test_name_origin_rolls_back_to_resolved_name(self) -> None:
        """An unlisted move from a NAME origin bounces back to the resolved DISPLAY NAME."""
        # "In Progress" (name) -> "Done" is unlisted → ROLLBACK to the origin's display NAME
        # (defect 2): the bounce target/baseline must be the NAME the snapshot reports so the
        # diff stops re-firing the rollback.
        action = _decide("Done", "In Progress", WHITELIST)
        assert action.kind is ActionKind.ROLLBACK
        assert action.to_column == "In Progress"


class TestWildcardWhitelist:
    """Wildcard rows (parking / Cancel routing) resolve through decide too."""

    def test_wildcard_destination_parks_via_run_script_or_noop(self) -> None:
        """A `*->Blocked` style park row resolves for any source."""
        yaml_text = """
project: owner/repo
transitions:
  - from: "*"
    to: Blocked
"""
        # Add Blocked to the model so it resolves; an allowed no-op park.
        columns = dict(COLUMNS)
        columns["Blocked"] = Column(key="Blocked", name="Blocked", column_class=ColumnClass.INERT)
        ctx = DecideContext(transitions=load_transitions(yaml_text))
        action = decide(_transition("Blocked", "InProgress"), columns, ctx)
        assert action.kind is ActionKind.NOOP
        assert action.to_column == "Blocked"
