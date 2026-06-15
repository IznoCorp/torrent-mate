"""Pure domain model for KanbanMate.

This module defines the immutable data types that represent the board, its
columns and tickets, transitions between columns, and the actions the daemon
can decide to take.  All dataclasses are frozen so the core layer remains a
pure, side-effect-free functional heart (DESIGN §3.2).

The module imports only the standard library — :mod:`dataclasses`, :mod:`enum`,
and :mod:`typing`.  No I/O, no dependency on any other KanbanMate layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ColumnClass(Enum):
    """Class of a board column that determines how the daemon reacts to it.

    In the transitions-only model (DESIGN §8.0.6) a column carries **no** launch
    configuration — the agent launches at the transition, never at a column — so
    there is no ``AGENT`` class. Only the two **non-launch** classifications NEW's
    architecture still needs survive:

    Members:
        REACTIVE: The column triggers a mechanical side-effect (e.g. Cancel ->
            teardown the running agent). Declared via ``action: teardown``.
        INERT: The column is informational / terminal only; no action is triggered.
            Used to validate the board and resolve the Blocked-park / Backlog-reset
            targets.
    """

    REACTIVE = "reactive"
    INERT = "inert"


@dataclass(frozen=True)
class Column:
    """A board column — its key, label and non-launch classification.

    The transitions-only model (DESIGN §8.0.6) keeps the launch configuration
    entirely on the ``(from, to)`` transition (``transitions.yml``); a column is a
    bare member of the board's column SET. It therefore carries no
    ``triggers_agent`` / ``permission_profile`` / ``interactive_only`` — those
    fields were the removed per-column autonomy gate.

    Attributes:
        key: Stable machine-readable identifier (e.g. ``InProgress``).
        name: Human-readable label (e.g. ``In Progress``).
        column_class: The non-launch classification — ``REACTIVE`` (Cancel
            teardown) or ``INERT`` (human gate / terminal). See
            :class:`ColumnClass`.
    """

    key: str
    name: str
    column_class: ColumnClass


@dataclass(frozen=True)
class Ticket:
    """A single item on the GitHub Projects v2 board.

    Attributes:
        item_id: The opaque GraphQL ``ProjectV2Item`` node id.
        issue_number: The GitHub issue number if the item is linked to an
            issue, or ``None`` for draft items.
        title: The item title (issue title or draft note).
        column_key: The stable key of the column the item currently occupies.
        body: The linked issue's markdown body, used by the dependency gate
            (DESIGN §9) to parse ``Depends on #N`` references before a launch.
            Empty for draft items / non-Issue content, which carry no body.
    """

    item_id: str
    issue_number: int | None
    title: str
    column_key: str
    body: str = ""


@dataclass(frozen=True)
class BoardSnapshot:
    """A point-in-time capture of the board state.

    Attributes:
        tickets: Every item visible on the board at fetch time.  Stored as an
            immutable tuple to prevent accidental mutation inside :mod:`core`.
        fetched_at: The wall-clock (POSIX) timestamp when the snapshot was
            captured — informational; not wired into the interval strategy.
    """

    tickets: tuple[Ticket, ...]
    fetched_at: float


@dataclass(frozen=True)
class Transition:
    """A detected movement of a ticket between two polls.

    This is the output of :func:`kanbanmate.core.diff.diff` and the input to
    :func:`kanbanmate.core.decide.decide`.

    .. note::

        This dataclass is the **diff record** (a namesake-only match for
        :class:`kanbanmate.core.transitions.Transition`, which represents a
        **single whitelist entry** in the per-(from,to) transition configuration).
        The two types share a name but live in different modules and model
        different concepts — this one records a board movement, the other one
        describes what action (if any) a given pair should trigger.

    Attributes:
        ticket: The ticket whose column changed (or that appeared for the first
            time).
        from_column: The column key the ticket was in during the previous poll,
            or ``None`` when the ticket is brand-new (first time seen).
        to_column: The column key the ticket currently occupies.
    """

    ticket: Ticket
    from_column: str | None
    to_column: str


class ActionKind(Enum):
    """Category of action the daemon can decide to execute.

    **The reduced verdict set (genesis #23 — 9 PoC verdicts → 5 ActionKind, KEEP+DOC).**
    The PoC ``dispatch.py:18-21`` carried a 9-kind ``DecisionKind`` Literal
    (``launch | run_script | noop | rollback`` from the pure classifier, plus
    ``skip | queue | block | teardown | reset`` the runner constructed). NEW keeps
    only the five terminal categories below; the four "missing" PoC verdicts are NOT
    lost — each was re-homed where the polling model actually decides it, so a reader
    can trace the reorganisation:

    * ``skip`` → **tick dedup / diff baseline.** The PoC's idempotency/dedup ``skip``
      has no verdict in NEW: an already-processed move produces NO diff next poll
      (the diff-against-persisted baseline is the idempotence net, DESIGN §6), so an
      idempotent re-tick simply yields :attr:`NOOP`, never a distinct ``skip``.
    * ``queue`` → **``reserve_slot`` / enqueue path (phase 13).** Concurrency-cap
      divert is an app-layer side-effect in ``tick`` (``reserve_slot`` full →
      ``enqueue_launch``), not a pure verdict — the LAUNCH verdict stands and the cap
      gate routes it to the queue.
    * ``rollback`` → :attr:`ROLLBACK` (restored as a first-class verdict in phase 12).
    * ``run_script`` → :attr:`RUN_SCRIPT` (restored in phase 12/15).
    * ``block | teardown | reset | noop | launch`` → the five members below 1:1.

    Members:
        LAUNCH: Start a Claude Code agent for a ticket that just entered an
            agent-triggering column.
        TEARDOWN: Stop the running agent for a ticket moved to the Cancel column.
        RESET: Re-open a ticket moved from Cancel back to Backlog (clear
            persisted state so it can start fresh).
        BLOCK: Prevent action — e.g. anti-loop guard, kill-switch, or dependency
            gate not satisfied.
        NOOP: Nothing to do; the transition requires no action. This is ALSO where
            the PoC's ``skip`` verdict lands — an idempotent re-tick of an
            already-processed move yields NOOP (the diff baseline absorbs the
            dedup), never a distinct ``skip`` (#23).
        ROLLBACK: An un-whitelisted (from,to) move; bounce the card BACK to the
            ``from_col``.  The rollback target is load-bearing — it is the
            column key the ticket is returned to.
        RUN_SCRIPT: A transition that carries a script but no prompt; run the
            script mechanically with no LLM invocation.
    """

    LAUNCH = "launch"
    TEARDOWN = "teardown"
    RESET = "reset"
    BLOCK = "block"
    NOOP = "noop"
    ROLLBACK = "rollback"
    RUN_SCRIPT = "run_script"


@dataclass(frozen=True)
class Action:
    """A concrete decision to act on a ticket transition.

    Produced by :func:`kanbanmate.core.decide.decide` and consumed by the
    command-pattern action objects in :mod:`kanbanmate.app.actions`.

    Attributes:
        kind: What kind of action to take.
        ticket: The ticket the action applies to.
        reason: A human-readable explanation of why this action was chosen,
            useful for audit logs and sticky comments.
        to_column: The destination column key (the ``to`` of the matched
            transition).  On ROLLBACK this carries the ``from_col`` the card is
            bounced back to — a dual use that mirrors the PoC's
            ``Decision.column`` from ``dispatch.py:31``.
        prompt: The matched transition's launch prompt template, filled at
            dispatch time by the placeholder engine.  ``None`` for non-launch
            verdicts.
        script: The matched transition's script — a gate on a launch transition,
            or the sole action on a ``run_script`` transition.
        on_fail: The matched transition's ``on_fail`` policy (``""``,
            ``"move:<col>"``, or ``"rollback"``), threaded for phase 13's
            fix-CI loop to consume.
        advance: The matched transition's ``advance`` directive (``"stop"`` or
            ``"auto:<col>"``), threaded for phase 13's auto-advance to consume.
        profile: The matched transition's permission profile.
        permission_mode: The matched transition's ``claude --permission-mode``.
    """

    kind: ActionKind
    ticket: Ticket
    reason: str
    to_column: str = ""
    prompt: str | None = None
    script: str | None = None
    on_fail: str = ""
    advance: str = "stop"
    profile: str = ""
    permission_mode: str = "auto"
