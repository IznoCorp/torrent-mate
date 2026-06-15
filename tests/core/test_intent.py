"""Tests for the pure intent value objects + authority/guardrail validation (cockpit PR2 core).

``validate_intent`` is the security heart of the cockpit intent queue: the daemon DERIVES the
authority (``operator`` vs ``agent``) from its own launch bookkeeping and passes it in — the
spoofable ``caller`` field on the intent is advisory and must NEVER drive a security decision. These
tests pin: operator breadth, the agent guardrails (re-fire guard via the wildcard-aware
``transitions.get``, the Merge universal-deny, R1 own-issue binding, operator-only kinds), structural
checks (unknown kind / unknown destination), and that ``caller`` is ignored for authority.
"""

from __future__ import annotations

import pytest

from kanbanmate.core.columns import load_columns
from kanbanmate.core.intent import Intent, IntentRejected, validate_intent
from kanbanmate.core.transitions import load_transitions

_COLUMNS = load_columns(
    """
columns:
  - key: Backlog
    name: Backlog
  - key: Spec
    name: Spec
  - key: Review
    name: Review
  - key: Merge
    name: Merge
  - key: Done
    name: Done
"""
)

_TRANS = load_transitions(
    """
project: owner/repo
transitions:
  - from: Backlog
    to: Spec
    profile: docs
    prompt: "design it"
  - from: Review
    to: Merge
    script: "gate.sh"
"""
)


def _move(issue: int, to_col: str, **kw: object) -> Intent:
    return Intent(kind="move", issue=issue, args={"to_col": to_col}, requested_at=1.0, **kw)  # type: ignore[arg-type]


# ── operator authority (broad) ────────────────────────────────────────────


def test_operator_move_to_known_column_ok() -> None:
    validate_intent(
        _move(7, "Spec"),
        authority="operator",
        transitions=_TRANS,
        columns=_COLUMNS,
        from_col="Backlog",
    )


def test_operator_move_into_merge_ok() -> None:
    # Operator may move a card into Merge (the Review->Merge script gate); merge itself stays human.
    validate_intent(
        _move(7, "Merge"),
        authority="operator",
        transitions=_TRANS,
        columns=_COLUMNS,
        from_col="Review",
    )


def test_operator_ticket_create_ok() -> None:
    validate_intent(
        Intent(kind="ticket_create", issue=None, args={"title": "t"}, requested_at=1.0),
        authority="operator",
        transitions=_TRANS,
        columns=_COLUMNS,
    )


# ── structural checks (both authorities) ──────────────────────────────────


def test_move_to_unknown_column_rejected() -> None:
    with pytest.raises(IntentRejected, match="destination"):
        validate_intent(
            _move(7, "Nope"),
            authority="operator",
            transitions=_TRANS,
            columns=_COLUMNS,
            from_col="Backlog",
        )


def test_unknown_kind_rejected() -> None:
    with pytest.raises(IntentRejected, match="unknown intent kind"):
        validate_intent(
            Intent(kind="frobnicate", issue=7, args={}, requested_at=1.0),
            authority="operator",
            transitions=_TRANS,
            columns=_COLUMNS,
        )


# ── agent authority (bridled) ─────────────────────────────────────────────


def test_agent_move_into_prompt_target_rejected_refire() -> None:
    # Backlog->Spec is prompt-bearing → an agent move there would re-fire a launch.
    with pytest.raises(IntentRejected, match="re-fire"):
        validate_intent(
            _move(7, "Spec"),
            authority="agent",
            transitions=_TRANS,
            columns=_COLUMNS,
            from_col="Backlog",
            launching_issue=7,
        )


def test_agent_move_into_merge_rejected() -> None:
    with pytest.raises(IntentRejected, match="Merge"):
        validate_intent(
            _move(7, "Merge"),
            authority="agent",
            transitions=_TRANS,
            columns=_COLUMNS,
            from_col="Review",
            launching_issue=7,
        )


def test_agent_move_to_non_trigger_column_ok() -> None:
    # Spec->Done is not prompt-bearing here → a bridled agent may make this move.
    validate_intent(
        _move(7, "Done"),
        authority="agent",
        transitions=_TRANS,
        columns=_COLUMNS,
        from_col="Spec",
        launching_issue=7,
    )


def test_agent_move_cross_issue_rejected_r1() -> None:
    # R1: an agent may only act on its OWN launching issue.
    with pytest.raises(IntentRejected, match="launching"):
        validate_intent(
            _move(7, "Done"),
            authority="agent",
            transitions=_TRANS,
            columns=_COLUMNS,
            from_col="Spec",
            launching_issue=8,
        )


def test_agent_ticket_create_rejected() -> None:
    with pytest.raises(IntentRejected, match="may not"):
        validate_intent(
            Intent(kind="ticket_create", issue=None, args={}, requested_at=1.0),
            authority="agent",
            transitions=_TRANS,
            columns=_COLUMNS,
            launching_issue=7,
        )


def test_caller_field_is_advisory_not_security() -> None:
    # An agent-authority intent whose spoofable caller claims 'operator' is STILL bridled — the
    # daemon-derived authority is what governs, never the caller field (§5).
    with pytest.raises(IntentRejected, match="re-fire"):
        validate_intent(
            _move(7, "Spec", caller="operator"),
            authority="agent",
            transitions=_TRANS,
            columns=_COLUMNS,
            from_col="Backlog",
            launching_issue=7,
        )


# ── ticket_create initial-column guard ─────────────────────────────────────


def _create(**args: object) -> Intent:
    return Intent(kind="ticket_create", issue=None, args=dict(args), requested_at=1.0)


def test_operator_ticket_create_into_launch_column_rejected() -> None:
    # Backlog->Spec is prompt-bearing → Spec is a launch target → refuse creating directly into it.
    with pytest.raises(IntentRejected, match="launch column"):
        validate_intent(
            _create(title="N", column="Spec"),
            authority="operator",
            transitions=_TRANS,
            columns=_COLUMNS,
        )


def test_operator_ticket_create_into_non_trigger_column_ok() -> None:
    validate_intent(
        _create(title="N", column="Done"),
        authority="operator",
        transitions=_TRANS,
        columns=_COLUMNS,
    )


def test_ticket_create_unknown_initial_column_rejected() -> None:
    with pytest.raises(IntentRejected, match="unknown initial column"):
        validate_intent(
            _create(title="N", column="Nope"),
            authority="operator",
            transitions=_TRANS,
            columns=_COLUMNS,
        )
