"""Pure intent value objects + authority/guardrail validation (cockpit PR2 core).

The cockpit skill mutates the board through an **intent queue** whose only writer is the daemon. An
:class:`Intent` is a small frozen value object the CLI/agent enqueues and the daemon executes on its
tick. :func:`validate_intent` is the **security heart**: it enforces the operator-vs-agent guardrails.

**Authority is derived by the daemon, never trusted from the intent.** Launched agents run non-root
as the same UID as the daemon and can write the intents directory, so the ``caller`` field on an
:class:`Intent` is **advisory only** and is NEVER read here for a security decision. The daemon
computes the real ``authority`` (``"operator"`` / ``"agent"``) from state it owns — its
``issue ↔ session ↔ worktree`` launch bookkeeping — and passes it in, along with the agent's bound
``launching_issue`` (for the R1 own-ticket rule) and the card's current ``from_col`` (for the
wildcard-aware re-fire guard). This module stays **pure** (no I/O): it imports only the pure
``core`` whitelist/columns models, so the layering guard keeps it side-effect-free and unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from kanbanmate.core.domain import Column
from kanbanmate.core.transitions import TransitionConfig

#: The full intent vocabulary. v1 wires only ``move`` live (operator); the rest are designed +
#: validated here for PR3 (ticket/pill CRUD) and the deferred agent-move unification.
IntentKind = Literal[
    "move",
    "ticket_create",
    "ticket_edit",
    "ticket_close",
    "status_post",
    "status_edit",
    "status_delete",
    "pill_set_health",
    "pill_note",
    "pill_clear",
]

#: Authority is DERIVED by the daemon from its launch bookkeeping — not from the intent's caller.
Authority = Literal["operator", "agent"]

#: Every recognised intent kind (membership guard).
VALID_KINDS: frozenset[str] = frozenset(
    {
        "move",
        "ticket_create",
        "ticket_edit",
        "ticket_close",
        "status_post",
        "status_edit",
        "status_delete",
        "pill_set_health",
        "pill_note",
        "pill_clear",
    }
)

#: Kinds a bridled AGENT may issue. Everything else is operator-only (ticket/pill/status authority
#: stays with the operator). v1 keeps this to ``move`` — and even that is operator-only live until the
#: agent ``kanban-move`` unification (deferred); the agent rules here are designed + tested ahead.
AGENT_ALLOWED_KINDS: frozenset[str] = frozenset({"move"})

#: The human-only Merge column: a daemon-executed agent move bypasses the agent Bash deny-list, so an
#: agent may NOT move a card into Merge (merge=human-only, DESIGN §5 universal deny).
_MERGE_COLUMN: str = "Merge"


class IntentRejected(Exception):
    """Raised by :func:`validate_intent` when an intent violates policy (the daemon writes it as a
    ``rejected`` result so the caller's ``--wait`` surfaces the reason)."""


@dataclass(frozen=True)
class Intent:
    """One atomic board-mutation request enqueued by an operator or agent.

    Attributes:
        kind: One of :data:`IntentKind`.
        issue: The target issue number (``None`` for ``ticket_create``).
        args: Kind-specific arguments (e.g. ``{"to_col": "Done"}`` for ``move``); ``to_col`` is a
            column KEY (the app layer canonicalises a name → key before validation).
        requested_at: Epoch seconds the intent was enqueued (the drain orders by this).
        caller: An ADVISORY hint of who enqueued it — NEVER the security decision (see module docs).
    """

    kind: str
    issue: int | None
    args: dict[str, object] = field(default_factory=dict)
    requested_at: float = 0.0
    caller: str = "operator"


@dataclass(frozen=True)
class IntentResult:
    """The terminal (or interim) outcome of an intent, polled by the CLI ``--wait``.

    Attributes:
        intent_id: The intent's id (its queue filename stem).
        state: ``pending`` | ``claimed`` | ``done`` | ``rejected`` | ``deferred`` | ``held``.
        detail: A short human note (e.g. a rejection reason or a deferral cause).
    """

    intent_id: str
    state: str
    detail: str = ""


def validate_intent(
    intent: Intent,
    *,
    authority: Authority,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    from_col: str | None = None,
    launching_issue: int | None = None,
) -> None:
    """Enforce the operator-vs-agent guardrails for ``intent`` (pure; raises on violation).

    Operators are broad (only structural checks apply). Agents are bridled: they may issue only
    :data:`AGENT_ALLOWED_KINDS`, only against their own ``launching_issue`` (R1), never into Merge,
    and never a move that resolves (wildcard-aware) to a prompt-bearing transition (which would
    re-fire a launch). ``authority`` is the daemon-derived decision — the intent's ``caller`` field is
    ignored here.

    Args:
        intent: The intent to validate.
        authority: The daemon-derived authority (``"operator"`` / ``"agent"``).
        transitions: The whitelist (its wildcard-aware :meth:`~TransitionConfig.get` drives the
            re-fire guard).
        columns: The board columns by key (destination existence check).
        from_col: The card's CURRENT column key (resolved by the daemon from the snapshot), needed
            for the move re-fire guard; ``None`` skips that guard.
        launching_issue: For an agent, the issue the daemon launched it for (R1 binding).

    Raises:
        IntentRejected: When the intent violates policy.
    """
    if intent.kind not in VALID_KINDS:
        raise IntentRejected(f"unknown intent kind {intent.kind!r}")

    if authority == "agent":
        _validate_agent(intent, transitions, from_col, launching_issue)

    # Structural checks apply to every authority.
    if intent.kind == "move":
        _validate_move_destination(intent, columns)
    elif intent.kind == "ticket_create":
        _validate_ticket_create_column(intent, transitions, columns)


def _validate_move_destination(intent: Intent, columns: dict[str, Column]) -> None:
    """Reject a ``move`` whose ``to_col`` is not a known column key."""
    to_col = intent.args.get("to_col")
    if not isinstance(to_col, str) or to_col not in columns:
        raise IntentRejected(f"unknown destination column {to_col!r}")


def _validate_ticket_create_column(
    intent: Intent, transitions: TransitionConfig, columns: dict[str, Column]
) -> None:
    """Reject a ``ticket_create`` whose initial column is unknown or a launch target.

    A brand-new card dropped straight into a prompt-bearing (launch) column would spawn an
    autonomous session outside the normal flow; creating into a launch column is therefore refused
    (create the ticket in a non-triggering column and move it). An absent column is fine — the new
    card lands wherever ``add_to_project`` places it (a non-triggering default).
    """
    col = intent.args.get("column")
    if not isinstance(col, str) or not col:
        return
    if col not in columns:
        raise IntentRejected(f"unknown initial column {col!r}")
    if col in transitions.launch_target_columns():
        raise IntentRejected(
            f"cannot create a ticket directly into launch column {col!r}; "
            f"create it in a non-triggering column and move it"
        )


def _validate_agent(
    intent: Intent,
    transitions: TransitionConfig,
    from_col: str | None,
    launching_issue: int | None,
) -> None:
    """Apply the bridled-agent guardrails (kind allow-set, R1, Merge deny, re-fire guard)."""
    if intent.kind not in AGENT_ALLOWED_KINDS:
        raise IntentRejected(f"agents may not issue {intent.kind!r} intents")
    # R1: an agent may only act on the issue the daemon launched it for.
    if launching_issue is None or intent.issue != launching_issue:
        raise IntentRejected(
            f"agent intent issue {intent.issue!r} != launching issue {launching_issue!r}"
        )
    if intent.kind == "move":
        to_col = intent.args.get("to_col")
        # Universal deny: forbid an agent move into the human-only Merge column.
        if to_col == _MERGE_COLUMN:
            raise IntentRejected("agents may not move a card into Merge (merge=human-only)")
        # Re-fire guard (wildcard-aware): a move resolving to a prompt-bearing transition would
        # re-launch an agent. Uses transitions.get so (from,*)/(*,to) wildcards are honoured (the
        # static launch_target_columns set misses to='*' entries — a real escalation hole).
        if from_col is not None and isinstance(to_col, str):
            t = transitions.get(from_col, to_col)
            if t is not None and t.prompt:
                raise IntentRejected(f"agent move {from_col!r}->{to_col!r} would re-fire a launch")
