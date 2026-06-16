"""Tests for the PURE per-card Health mapping (:mod:`kanbanmate.core.health`)."""

from __future__ import annotations

import pytest

from kanbanmate.core.health import (
    HEALTH_OPTION_COLORS,
    HEALTH_OPTIONS_ORDER,
    compute_health,
)
from kanbanmate.core.status_update import STATUS_VALUES

# The default board labels the tick threads (assets/columns.yml.tmpl).
BLOCKED = "Blocked"
DONE = "Done"


def _health(
    *,
    is_running: bool = False,
    is_waiting: bool = False,
    column_key: str = "Backlog",
    blocked: str = BLOCKED,
    done: str = DONE,
) -> str:
    """Call :func:`compute_health` with the common defaults overridden as needed."""
    return compute_health(
        is_running=is_running,
        is_waiting=is_waiting,
        column_key=column_key,
        blocked_column=blocked,
        done_column=done,
    )


def test_waiting_agent_maps_to_waiting_in_any_column() -> None:
    """A WAITING agent reads WAITING regardless of the column it sits in."""
    for column in ("Backlog", "Spec", BLOCKED, DONE, "Cancel"):
        assert _health(is_waiting=True, column_key=column) == "WAITING"


def test_running_agent_maps_to_active_in_any_column() -> None:
    """A RUNNING agent reads ACTIVE regardless of the column it sits in."""
    for column in ("Backlog", "Spec", BLOCKED, DONE, "Cancel"):
        assert _health(is_running=True, column_key=column) == "ACTIVE"


def test_no_agent_in_blocked_maps_to_blocked() -> None:
    """A card with no agent parked in the Blocked column reads BLOCKED."""
    assert _health(column_key=BLOCKED) == "BLOCKED"


def test_no_agent_in_done_maps_to_complete() -> None:
    """A card with no agent in the Done column reads COMPLETE."""
    assert _health(column_key=DONE) == "COMPLETE"


@pytest.mark.parametrize("column", ["Backlog", "Spec", "Cancel", "Review", "anything-else"])
def test_no_agent_idle_columns_map_to_inactive(column: str) -> None:
    """A card with no agent in any non-Blocked/Done column reads INACTIVE."""
    assert _health(column_key=column) == "INACTIVE"


def test_waiting_wins_over_blocked_column() -> None:
    """Precedence: a WAITING agent wins over the column being Blocked."""
    assert _health(is_waiting=True, column_key=BLOCKED) == "WAITING"


def test_running_wins_over_done_column() -> None:
    """Precedence: a RUNNING agent wins over the column being Done."""
    assert _health(is_running=True, column_key=DONE) == "ACTIVE"


def test_non_default_blocked_done_columns_honoured() -> None:
    """The Blocked/Done keys are arguments, not hardcoded labels."""
    assert _health(column_key="Parked", blocked="Parked", done="Shipped") == "BLOCKED"
    assert _health(column_key="Shipped", blocked="Parked", done="Shipped") == "COMPLETE"
    # The DEFAULT labels no longer match when custom keys are supplied.
    assert _health(column_key=BLOCKED, blocked="Parked", done="Shipped") == "INACTIVE"


def test_every_returned_value_is_a_known_health_value() -> None:
    """Every mapping output is one of the 5 domain health values."""
    cases = [
        _health(is_waiting=True),
        _health(is_running=True),
        _health(column_key=BLOCKED),
        _health(column_key=DONE),
        _health(column_key="Backlog"),
    ]
    for value in cases:
        assert value in STATUS_VALUES


def test_option_specs_cover_all_five_values_with_palette_colours() -> None:
    """The ordered option specs name exactly the 5 values; colours are palette tokens."""
    assert set(HEALTH_OPTIONS_ORDER) == STATUS_VALUES
    assert set(HEALTH_OPTION_COLORS) == STATUS_VALUES
    palette = {"GRAY", "BLUE", "GREEN", "YELLOW", "ORANGE", "RED", "PINK", "PURPLE"}
    assert set(HEALTH_OPTION_COLORS.values()) <= palette
    # The operator-chosen colours (spec §0).
    assert HEALTH_OPTION_COLORS["ACTIVE"] == "GREEN"
    assert HEALTH_OPTION_COLORS["WAITING"] == "YELLOW"
    assert HEALTH_OPTION_COLORS["BLOCKED"] == "RED"
    assert HEALTH_OPTION_COLORS["INACTIVE"] == "GRAY"
    assert HEALTH_OPTION_COLORS["COMPLETE"] == "PURPLE"
