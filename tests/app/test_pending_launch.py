"""Tests for the restart-durable pending-launch recovery in the tick (#55).

A launch-bearing operator move records a durable ``pending_launch`` breadcrumb (see
``tests/app/test_intents.py`` for the record side). The daemon's in-memory diff baseline is wiped on
a restart (#20), so without recovery a card already parked in a launch column looks first-contact
(``from=None`` → ``decide`` NOOP) and the launch is silently dropped. The tick OVERLAYS the
breadcrumb's recorded ``from`` column back onto the baseline so the genuine transition is re-detected
and the entry agent fires — and clears the breadcrumb when it is consumed (launch) or stale (the card
left the launch column).

The store is a ``MagicMock`` whose ``pending_launches`` is scripted to model "a breadcrumb survived
the restart"; the real fs round-trip is proven in ``tests/adapters/test_fs_store.py``.
"""

from __future__ import annotations

from kanbanmate.app.tick import PersistedState, tick
from kanbanmate.core.domain import Ticket
from kanbanmate.ports.store import PendingLaunch

from tests.app.test_tick import _FakeBoardReader, _config, _mocks, _snapshot

# The test board's launch edge is ``Backlog -> InProgress`` (see ``tests/app/test_tick.py``).


def test_tick_relaunches_after_restart_via_breadcrumb() -> None:
    """A surviving breadcrumb re-fires the launch after a restart wiped the baseline (#55).

    The #55 scenario: the card is parked in the launch column (``InProgress``) and the in-memory
    baseline is EMPTY (a fresh ``PersistedState`` == post-restart). The overlay re-creates the
    ``Backlog -> InProgress`` transition from the breadcrumb so the launch fires, and the launch
    consumes the breadcrumb.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    m = _mocks(_FakeBoardReader("probe-1", _snapshot(ticket)))
    m.store.pending_launches.return_value = {
        "PVTI_7": PendingLaunch(item_id="PVTI_7", from_col="Backlog", to_col="InProgress", ts=999.0)
    }
    # Restart: the in-memory baseline is empty (the bug trigger).
    state = PersistedState(columns_by_item={}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    m.sessions.launch.assert_called_once()
    m.store.save.assert_called_once()
    assert result.actions_executed == 1
    # The launch consumed the breadcrumb (fires exactly once — LaunchAction.execute clears it).
    m.store.clear_pending_launch.assert_called_once_with("PVTI_7")
    # The baseline advanced so the next diff does not re-fire.
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_tick_no_relaunch_without_breadcrumb_after_restart() -> None:
    """Storm guard: with NO breadcrumb, a restart must NOT re-launch a settled card (#55 / #20).

    The card sits in the launch column with an empty baseline (post-restart) but no breadcrumb, so it
    is a genuine first-contact item — recorded as a NOOP, never launched. This is the load-bearing
    #20 property the fix must preserve: only explicitly-breadcrumbed items recover, never all cards.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    m = _mocks(_FakeBoardReader("probe-1", _snapshot(ticket)))
    m.store.pending_launches.return_value = {}
    state = PersistedState(columns_by_item={}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    m.sessions.launch.assert_not_called()
    assert result.actions_executed == 0
    # First-contact recorded so it is not re-evaluated next tick (no churn).
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"


def test_tick_clears_stale_breadcrumb_when_card_left_launch_column() -> None:
    """A breadcrumb whose card has left the launch column is stale → cleared, no spurious launch.

    The card advanced to ``Done`` (or the operator pulled it back), so the recorded launch into
    ``InProgress`` no longer applies. The overlay drops the breadcrumb and fires no launch.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="Done")
    m = _mocks(_FakeBoardReader("probe-1", _snapshot(ticket)))
    m.store.pending_launches.return_value = {
        "PVTI_7": PendingLaunch(item_id="PVTI_7", from_col="Backlog", to_col="InProgress", ts=999.0)
    }
    state = PersistedState(columns_by_item={"PVTI_7": "InProgress"}, last_probe="probe-0")

    result, _next_state = tick(m.deps, _config(), state)

    m.store.clear_pending_launch.assert_called_once_with("PVTI_7")
    m.sessions.launch.assert_not_called()


def test_tick_overrides_a_stale_baseline_via_breadcrumb() -> None:
    """A STALE-WRONG baseline (not just an absent one) is overridden by the breadcrumb (#27).

    The live #27 bug: the card had advanced to ReadyToDev but the daemon's in-memory baseline was
    still ``Plan`` (it never caught up). The operator's launch-edge move ``ReadyToDev → PrepareFeature``
    was therefore diffed as the un-whitelisted ``Plan → PrepareFeature`` and ROLLED BACK to Plan
    instead of launching. The breadcrumb records the TRUE origin (the card's actual column at move
    time), so the overlay must OVERRIDE the stale baseline — not merely fill an absent one — and
    re-create the genuine launch transition.

    Test board analogue: launch edge ``Backlog → InProgress``; the stale baseline says ``Done`` (an
    un-whitelisted ``Done → InProgress`` edge that would otherwise rollback), and the breadcrumb's
    ``from`` is ``Backlog``.
    """
    ticket = Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    m = _mocks(_FakeBoardReader("probe-1", _snapshot(ticket)))
    m.store.pending_launches.return_value = {
        "PVTI_7": PendingLaunch(item_id="PVTI_7", from_col="Backlog", to_col="InProgress", ts=999.0)
    }
    # Stale-WRONG baseline: the daemon thinks #7 is in Done, while it is actually in InProgress.
    state = PersistedState(columns_by_item={"PVTI_7": "Done"}, last_probe="probe-0")

    result, next_state = tick(m.deps, _config(), state)

    # The breadcrumb's true origin (Backlog) wins → the launch edge fires (no rollback to Done).
    m.sessions.launch.assert_called_once()
    assert result.actions_executed == 1
    m.store.clear_pending_launch.assert_called_once_with("PVTI_7")
    assert next_state.columns_by_item["PVTI_7"] == "InProgress"
