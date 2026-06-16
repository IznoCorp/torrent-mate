"""Pure per-card Health mapping for the custom GitHub single-select chip (health-field).

GitHub's "Status updates" PILL uses the FIXED ``ProjectV2StatusUpdateStatus``
enum (INACTIVE / ON_TRACK / AT_RISK / OFF_TRACK / COMPLETE) — it cannot be
renamed, so the operator's OWN vocabulary never shows on that pill (see
:mod:`kanbanmate.core.status_update` and the adapter's ``_HEALTH_TO_GITHUB_STATUS``
boundary). The health-field feature works around this by maintaining a NEW
per-card single-select FIELD named **"Health"** whose 5 options carry the
operator's exact words + colours; GitHub renders single-select options with
custom names + colours as native chips on each card, so the operator's wording
DOES appear.

This module is the **pure** half: the ordered option specs (name + GitHub palette
colour) the adapter creates the field from, plus a single PURE
:func:`compute_health` that maps a card's (agent-state, column) onto one of the 5
:data:`~kanbanmate.core.status_update.StatusValue` domain names. It REUSES the
domain vocabulary already defined in :mod:`kanbanmate.core.status_update`
(``INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE``) rather than inventing a
parallel set — :data:`StatusValue` / :data:`STATUS_VALUES` come from that peer
``core`` module (allowed: ``core`` may import ``core``).

Layering: ``core`` imports NOTHING with I/O and nothing below it. This module
takes only booleans + column keys (the app layer derives ``is_running`` /
``is_waiting`` from :class:`~kanbanmate.ports.store.TicketStatus`), so it never
imports ``ports`` / ``adapters`` — it stays a side-effect-free heart.
"""

from __future__ import annotations

from typing import Final

from kanbanmate.core.status_update import StatusValue

# ---------------------------------------------------------------------------
# Option specs — the operator's 5 Health values + their GitHub palette colours.
# ---------------------------------------------------------------------------
#
# ``createProjectV2Field`` accepts one colour per single-select option from
# GitHub's FIXED palette (GRAY / BLUE / GREEN / YELLOW / ORANGE / RED / PINK /
# PURPLE). The colours below mirror the agent/board semantics the operator named:
# an ACTIVE agent is green (healthy/working), WAITING is yellow (needs a human),
# BLOCKED is red (stuck), INACTIVE is grey (idle), COMPLETE is purple (done).
HEALTH_OPTION_COLORS: Final[dict[str, str]] = {
    "ACTIVE": "GREEN",
    "WAITING": "YELLOW",
    "BLOCKED": "RED",
    "INACTIVE": "GRAY",
    "COMPLETE": "PURPLE",
}

# The order the options are CREATED on the field (= the chip order GitHub renders
# in the option dropdown). A stable order keeps a re-created field deterministic.
HEALTH_OPTIONS_ORDER: Final[tuple[str, ...]] = (
    "INACTIVE",
    "WAITING",
    "ACTIVE",
    "BLOCKED",
    "COMPLETE",
)


def compute_health(
    *,
    is_running: bool,
    is_waiting: bool,
    column_key: str,
    blocked_column: str,
    done_column: str,
) -> StatusValue:
    """Map a card's (agent-state, column) onto a Health value (PURE, no I/O).

    Precedence (FIRST MATCH WINS), mirroring the agent/board states the operator
    named:

    1. a live agent WAITING for human input -> ``WAITING`` (wins over the column,
       e.g. a card parked in Blocked whose agent is actually awaiting a reply).
    2. a live agent RUNNING -> ``ACTIVE`` (wins over the column, e.g. an agent
       still working a card that already reached Done).
    3. no live agent AND the card is in the Blocked column -> ``BLOCKED``.
    4. no live agent AND the card is in the Done column -> ``COMPLETE``.
    5. otherwise (an idle card: Backlog / Spec / Cancel / anything else with no
       agent) -> ``INACTIVE``.

    The ``blocked_column`` / ``done_column`` keys are PASSED IN (the app layer
    threads them from :class:`~kanbanmate.app.tick.TickConfig`) so the function is
    not hardcoded to the default board labels.

    Args:
        is_running: Whether the card has a live agent in the RUNNING state.
        is_waiting: Whether the card has a live agent WAITING for human input.
        column_key: The card's current column key (board column name).
        blocked_column: The Blocked column key (no-agent cards here read BLOCKED).
        done_column: The Done column key (no-agent cards here read COMPLETE).

    Returns:
        The matching :data:`~kanbanmate.core.status_update.StatusValue` — always
        one of the 5 domain names (a member of
        :data:`~kanbanmate.core.status_update.STATUS_VALUES`).
    """
    # A live agent's state wins over the column: a WAITING agent needs a human
    # (precedence 1) and a RUNNING agent is actively working (precedence 2),
    # regardless of which column the card currently sits in.
    if is_waiting:
        return "WAITING"
    if is_running:
        return "ACTIVE"
    # No live agent: the column decides. Blocked and Done are the two columns that
    # map to a non-idle chip; everything else (Backlog / Spec / Cancel / …) is idle.
    if column_key == blocked_column:
        return "BLOCKED"
    if column_key == done_column:
        return "COMPLETE"
    return "INACTIVE"
