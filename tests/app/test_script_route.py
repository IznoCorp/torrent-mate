"""Tests for the script-verdict routing (:mod:`kanbanmate.app.script_route`).

The routing OWNS the board moves + the 15.1 fix-CI ledger ops, but RETURNS the diff baseline +
anti-loop state for the tick to record. These tests assert the PoC-faithful contract directly on
:func:`route_script_verdict` (the keystone): which verdict triggers a re-fire vs a bookkeeping
bounce, the fix-CI cap (N=2 → park Blocked), independent per-loop budgets, the success ledger
reset + finalize, the ``{{script_output}}`` persist/clear, and fail-soft on every board op.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from kanbanmate.app.script_route import (
    _FIXCI_CAP,
    RouteOutcome,
    _park_runaway,
    fixci_key,
    route_script_verdict,
)
from kanbanmate.core.antiloop import AntiLoopState
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import Column, Ticket, Transition

_ITEM = "PVTI_7"
_ISSUE = 7


def _transition(*, from_column: str | None, to_column: str) -> Transition:
    """Build a diff :class:`Transition` for issue 7 carrying ``from``/``to`` columns."""
    ticket = Ticket(item_id=_ITEM, issue_number=_ISSUE, title="t", column_key=to_column)
    return Transition(ticket=ticket, from_column=from_column, to_column=to_column)


def _deps() -> MagicMock:
    """Build a MagicMock ``Deps`` with a default ``bump_retry`` of 1 (first failure).

    The durable per-issue move counter defaults to ``0`` so the cross-loop rate-limit gate
    (``move_count_for_item_last_hour >= move_rate_limit_per_hour``) is WITHIN limit by default —
    a bare ``MagicMock`` return would raise on the ``>=`` comparison. Tests exercising the runaway
    park set a high return value explicitly.
    """
    deps = MagicMock()
    deps.store.bump_retry.return_value = 1
    deps.store.move_count_for_item_last_hour.return_value = 0
    return deps


def _route(
    deps: MagicMock,
    *,
    to_column: str,
    from_column: str | None = "InProgress",
    on_fail: str = "",
    advance: str = "stop",
    exit_code: int,
    output: str = "",
    blocked_column: str = "Blocked",
    move_rate_limit_per_hour: int = 10,
    antiloop: AntiLoopState | None = None,
    now: float = 1000.0,
    columns: "dict[str, Column] | None" = None,
) -> RouteOutcome:
    """Invoke :func:`route_script_verdict` with test defaults."""
    return route_script_verdict(
        deps,
        _transition(from_column=from_column, to_column=to_column),
        to_column=to_column,
        from_column=from_column,
        on_fail=on_fail,
        advance=advance,
        exit_code=exit_code,
        output=output,
        blocked_column=blocked_column,
        move_rate_limit_per_hour=move_rate_limit_per_hour,
        antiloop=antiloop or AntiLoopState(),
        now=now,
        columns=columns,
    )


# Two divergent-name columns from the shipped board (key != name): the campaign's
# fix-CI bounce (move:InProgress) and gate destination (PR/CI) both diverge. The
# defect-2 regression below routes through this real model.
_SHIPPED_COLUMNS_YAML = (
    "columns:\n"
    "  - {key: InProgress, name: In Progress}\n"
    "  - {key: PRCI, name: PR/CI}\n"
    "  - {key: Review, name: Review}\n"
    "  - {key: Blocked, name: Blocked}\n"
)


def _shipped_columns() -> dict[str, Column]:
    """The divergent-name column model the defect-2 regression resolves against."""
    return load_columns(_SHIPPED_COLUMNS_YAML)


# ---------------------------------------------------------------------------
# SUCCESS path
# ---------------------------------------------------------------------------


def test_success_advance_auto_triggering_move_baseline_is_script_column() -> None:
    """exit 0 + ``advance:auto:Next`` → move to Next, but baseline stays the SCRIPT column.

    The auto-move is a TRIGGERING bot move: leaving the baseline at the script column makes the
    NEXT poll's diff fire ``(PRCI → Next)`` (port ``_auto_move``'s "re-processed normally"). It
    feeds the per-issue move rate-limit (``record_move_for_item``) but is NOT anti-loop-recorded.
    A success also resets THIS loop's fix-CI counter and finalizes the LEFT stage ✅.
    """
    deps = _deps()
    outcome = _route(deps, to_column="PRCI", advance="auto:Next", exit_code=0)

    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Next")
    deps.store.record_move_for_item.assert_called_once_with(_ISSUE, now=1000.0)
    deps.store.reset_retry.assert_called_once_with(_ISSUE, fixci_key("PRCI"))
    # baseline = the SCRIPT column (re-fire), NOT the auto-move target Next.
    assert outcome.baseline_column == "PRCI"
    assert outcome.finalize_left is True
    assert outcome.error is False
    # An auto-move is NOT anti-loop-recorded (it FEEDS the rate-limit, not the dedup).
    assert ("PVTI_7", "Next") not in outcome.antiloop.recent_targets


def test_success_advance_stop_no_move_baseline_is_script_column() -> None:
    """exit 0 + ``advance:stop`` → NO move; baseline = the script column; finalize ✅."""
    deps = _deps()
    outcome = _route(deps, to_column="PRCI", advance="stop", exit_code=0)

    deps.board_writer.move_card.assert_not_called()
    deps.store.record_move_for_item.assert_not_called()
    deps.store.reset_retry.assert_called_once_with(_ISSUE, fixci_key("PRCI"))
    assert outcome.baseline_column == "PRCI"
    assert outcome.finalize_left is True
    assert outcome.error is False


def test_success_clears_stashed_script_output() -> None:
    """exit 0 clears the ``{{script_output}}`` sink so a stale failure never bleeds (15.6)."""
    deps = _deps()
    _route(deps, to_column="PRCI", advance="stop", exit_code=0)
    deps.store.save_script_output.assert_called_once_with(_ISSUE, "")


# ---------------------------------------------------------------------------
# FAILURE path — on_fail:move (the fix-CI loop)
# ---------------------------------------------------------------------------


def test_failure_on_fail_move_within_cap_bounces_and_baseline_is_script_column() -> None:
    """exit ≠0 + ``on_fail:move:Back`` (count 1) → bump + move to Back; baseline = script col.

    The on_fail bounce is the TRIGGERING fix-CI loop: baseline stays the script column so the next
    diff re-fires ``(PRCI → Back)``. It feeds the rate-limit (``record_move_for_item``) but does NOT
    finalize the LEFT stage (a bounce is not a forward advance).
    """
    deps = _deps()
    deps.store.bump_retry.return_value = 1
    outcome = _route(deps, to_column="PRCI", on_fail="move:Back", exit_code=1)

    deps.store.bump_retry.assert_called_once_with(_ISSUE, fixci_key("PRCI"))
    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Back")
    deps.store.record_move_for_item.assert_called_once_with(_ISSUE, now=1000.0)
    assert outcome.baseline_column == "PRCI"
    assert outcome.finalize_left is False
    assert outcome.error is False


def test_failure_on_fail_move_over_cap_parks_blocked_resets_records_antiloop() -> None:
    """The (cap+1)-th failure parks in Blocked + resets the counter + recap + anti-loop records it.

    ``bump_retry`` returns ``_FIXCI_CAP + 1`` → reset the counter, move the card to ``blocked_column``
    (bookkeeping, NO re-fire), post the recap comment, and record the park move in the anti-loop
    state. The baseline becomes the Blocked column so the diff does NOT re-fire.
    """
    deps = _deps()
    deps.store.bump_retry.return_value = _FIXCI_CAP + 1  # 3 > 2 → cap reached
    outcome = _route(
        deps, to_column="PRCI", on_fail="move:Back", exit_code=1, blocked_column="Blocked"
    )

    deps.store.reset_retry.assert_called_once_with(_ISSUE, fixci_key("PRCI"))
    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Blocked")
    deps.board_writer.comment.assert_called_once()
    recap: str = deps.board_writer.comment.call_args.args[1]
    assert "Blocked" in recap
    assert str(_FIXCI_CAP) in recap
    # baseline = Blocked (bookkeeping; no re-fire) and the park move is anti-loop recorded.
    assert outcome.baseline_column == "Blocked"
    assert outcome.finalize_left is False
    assert ("PVTI_7", "Blocked") in outcome.antiloop.recent_targets
    # A cap-park is NOT counted toward the rate-limit auto-move counter (it is a bookkeeping move).
    deps.store.record_move_for_item.assert_not_called()


# ---------------------------------------------------------------------------
# FAILURE path — on_fail:rollback / "" (bookkeeping return-to-origin)
# ---------------------------------------------------------------------------


def test_failure_on_fail_rollback_returns_to_from_column() -> None:
    """exit ≠0 + ``on_fail:rollback`` → move back to from_col; baseline = from_col (no re-fire)."""
    deps = _deps()
    outcome = _route(deps, to_column="Merge", from_column="Review", on_fail="rollback", exit_code=1)

    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Review")
    deps.board_writer.comment.assert_called_once()
    assert outcome.baseline_column == "Review"
    assert outcome.finalize_left is False


def test_failure_empty_on_fail_behaves_like_rollback() -> None:
    """exit ≠0 + ``on_fail:""`` behaves exactly like rollback (returns to from_col)."""
    deps = _deps()
    outcome = _route(deps, to_column="Merge", from_column="Review", on_fail="", exit_code=1)

    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Review")
    assert outcome.baseline_column == "Review"


def test_failure_rollback_falls_back_to_to_column_when_from_is_none() -> None:
    """A rollback with ``from_column=None`` falls back to the script column as the target."""
    deps = _deps()
    outcome = _route(deps, to_column="Merge", from_column=None, on_fail="rollback", exit_code=1)

    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Merge")
    assert outcome.baseline_column == "Merge"


def test_failure_persists_script_output_for_fixci_consumer() -> None:
    """A failing run stashes its output for the fix-CI ``{{script_output}}`` (15.7) consumer."""
    deps = _deps()
    _route(deps, to_column="PRCI", on_fail="move:Back", exit_code=1, output="red CI log")
    deps.store.save_script_output.assert_called_once_with(_ISSUE, "red CI log")


def test_failure_empty_output_does_not_stash() -> None:
    """A failure with NO output does not write the marker (nothing to stash)."""
    deps = _deps()
    _route(deps, to_column="PRCI", on_fail="move:Back", exit_code=1, output="")
    deps.store.save_script_output.assert_not_called()


# ---------------------------------------------------------------------------
# Independent per-loop budgets (fix-CI cap keying)
# ---------------------------------------------------------------------------


def test_two_on_fail_loops_keep_independent_budgets() -> None:
    """Two distinct destination columns → distinct ``fixci_key`` → independent budgets.

    The two shipped on_fail loops (``InProgress→PRCI`` and ``Review→Merge``) must NOT share a
    budget — ``fixci_key`` keys on the destination column, never a shared constant.
    """
    assert fixci_key("PRCI") != fixci_key("Merge")

    deps = _deps()
    deps.store.bump_retry.return_value = 1
    _route(deps, to_column="PRCI", on_fail="move:InProgress", exit_code=1)
    _route(deps, to_column="Merge", on_fail="move:Review", exit_code=1)

    keys = {c.args[1] for c in deps.store.bump_retry.call_args_list}
    assert keys == {fixci_key("PRCI"), fixci_key("Merge")}


# ---------------------------------------------------------------------------
# Cross-loop move-rate-limit PARK gate (the OUTER backstop over _FIXCI_CAP)
# ---------------------------------------------------------------------------


def test_independent_loops_exceed_rate_limit_then_auto_advance_parks() -> None:
    """N independent loops push the durable count to the cap → the next auto-advance PARKS.

    Each loop has its OWN fix-CI budget (distinct ``to_column`` keys), so none individually hits
    ``_FIXCI_CAP`` — yet together they have churned the card ``move_rate_limit_per_hour`` times this
    hour. The durable per-issue counter is the cross-loop backstop: when it is already ``>= cap``,
    the next TRIGGERING auto-advance is parked in Blocked INSTEAD of moving to the advance target.
    """
    cap = 3
    deps = _deps()
    # Two prior loops each advanced once (within their own fix-CI budget) without parking.
    deps.store.move_count_for_item_last_hour.return_value = 0
    _route(deps, to_column="PRCI", advance="auto:Next", exit_code=0, move_rate_limit_per_hour=cap)
    _route(deps, to_column="Lint", advance="auto:Next", exit_code=0, move_rate_limit_per_hour=cap)
    deps.board_writer.move_card.assert_called_with(_ITEM, "Next")  # both proceeded

    # A third INDEPENDENT loop fires after the durable count has reached the cap → PARK.
    deps.reset_mock()
    deps.store.move_count_for_item_last_hour.return_value = cap  # >= cap
    outcome = _route(
        deps, to_column="Build", advance="auto:Next", exit_code=0, move_rate_limit_per_hour=cap
    )

    # The card is parked in Blocked, NOT moved to the auto-advance target.
    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Blocked")
    deps.board_writer.comment.assert_called_once()
    recap: str = deps.board_writer.comment.call_args.args[1]
    assert "rate limit" in recap.lower()
    # No durable move is recorded for a park (it is a bookkeeping move), and the baseline = Blocked.
    deps.store.record_move_for_item.assert_not_called()
    assert outcome.baseline_column == "Blocked"
    assert outcome.finalize_left is False
    assert ("PVTI_7", "Blocked") in outcome.antiloop.recent_targets


def test_on_fail_bounce_over_rate_limit_parks_instead_of_bouncing() -> None:
    """A within-fix-CI-cap on_fail bounce is PARKED when the durable rate-limit is exceeded.

    The fix-CI counter is within the per-loop cap (``bump_retry`` returns 1), so this would normally
    be a TRIGGERING bounce. But the durable cross-loop counter is already at the cap, so the gate
    parks the card in Blocked instead of issuing the bounce move. The rate-park ENDS the on_fail
    loop, so it MUST reset the per-loop fix-CI budget too — exactly like the cap-park above (PoC
    parity); otherwise the ``bump_retry`` above survives and starves a later re-entry of bounces.
    """
    cap = 2
    deps = _deps()
    deps.store.bump_retry.return_value = 1  # within fix-CI cap → would bounce
    deps.store.move_count_for_item_last_hour.return_value = cap  # >= cap → park
    outcome = _route(
        deps, to_column="PRCI", on_fail="move:Back", exit_code=1, move_rate_limit_per_hour=cap
    )

    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Blocked")
    deps.store.record_move_for_item.assert_not_called()
    # The rate-park clears the per-loop fix-CI budget (consistent with the cap-park branch).
    deps.store.reset_retry.assert_called_once_with(_ISSUE, fixci_key("PRCI"))
    assert outcome.baseline_column == "Blocked"
    assert outcome.finalize_left is False
    assert ("PVTI_7", "Blocked") in outcome.antiloop.recent_targets


def test_within_limit_auto_advance_is_unaffected() -> None:
    """A within-limit single loop advances normally + records the durable move (no park)."""
    deps = _deps()
    deps.store.move_count_for_item_last_hour.return_value = 1  # < cap
    outcome = _route(
        deps, to_column="PRCI", advance="auto:Next", exit_code=0, move_rate_limit_per_hour=10
    )

    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Next")
    deps.store.record_move_for_item.assert_called_once_with(_ISSUE, now=1000.0)
    assert outcome.baseline_column == "PRCI"  # the SCRIPT column (not Blocked)
    assert outcome.finalize_left is True


def test_within_limit_on_fail_bounce_is_unaffected() -> None:
    """A within-limit on_fail bounce moves to its target + records the durable move (no park)."""
    deps = _deps()
    deps.store.bump_retry.return_value = 1
    deps.store.move_count_for_item_last_hour.return_value = 0  # < cap
    outcome = _route(
        deps, to_column="PRCI", on_fail="move:Back", exit_code=1, move_rate_limit_per_hour=10
    )

    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Back")
    deps.store.record_move_for_item.assert_called_once_with(_ISSUE, now=1000.0)
    assert outcome.baseline_column == "PRCI"


def test_park_runaway_helper_moves_to_blocked_and_records_antiloop() -> None:
    """:func:`_park_runaway` moves to ``blocked_column``, comments, and records the park move."""
    deps = _deps()
    outcome = _park_runaway(
        deps,
        issue=_ISSUE,
        item_id=_ITEM,
        blocked_column="Blocked",
        antiloop=AntiLoopState(),
        now=1000.0,
        reason="auto-advance",
    )
    deps.board_writer.move_card.assert_called_once_with(_ITEM, "Blocked")
    deps.board_writer.comment.assert_called_once()
    assert outcome.baseline_column == "Blocked"
    assert outcome.error is False
    assert ("PVTI_7", "Blocked") in outcome.antiloop.recent_targets


def test_park_runaway_move_raise_is_fail_soft_error_true() -> None:
    """A ``move_card`` raise during the runaway park is swallowed → ``error=True``; antiloop set."""
    deps = _deps()
    deps.board_writer.move_card.side_effect = RuntimeError("github down")
    outcome = _park_runaway(
        deps,
        issue=_ISSUE,
        item_id=_ITEM,
        blocked_column="Blocked",
        antiloop=AntiLoopState(),
        now=1000.0,
        reason="on_fail bounce",
    )
    assert outcome.error is True
    assert outcome.baseline_column == "Blocked"
    assert ("PVTI_7", "Blocked") in outcome.antiloop.recent_targets


# ---------------------------------------------------------------------------
# Fail-soft on every board op
# ---------------------------------------------------------------------------


def test_success_auto_move_failure_is_fail_soft_error_true() -> None:
    """A ``move_card`` raise on the success auto-move is swallowed → ``error=True``, no raise."""
    deps = _deps()
    deps.board_writer.move_card.side_effect = RuntimeError("github down")
    outcome = _route(deps, to_column="PRCI", advance="auto:Next", exit_code=0)
    assert outcome.error is True
    # The baseline is still set (the routing did not raise out of the sweep).
    assert outcome.baseline_column == "PRCI"


def test_failure_move_raise_is_fail_soft_error_true() -> None:
    """A ``move_card`` raise on the on_fail bounce is swallowed → ``error=True``."""
    deps = _deps()
    deps.store.bump_retry.return_value = 1
    deps.board_writer.move_card.side_effect = RuntimeError("github down")
    outcome = _route(deps, to_column="PRCI", on_fail="move:Back", exit_code=1)
    assert outcome.error is True


def test_park_blocked_move_raise_is_fail_soft_error_true() -> None:
    """A ``move_card`` raise during the cap-park is swallowed → ``error=True``; still records antiloop."""
    deps = _deps()
    deps.store.bump_retry.return_value = _FIXCI_CAP + 1
    deps.board_writer.move_card.side_effect = RuntimeError("github down")
    outcome = _route(deps, to_column="PRCI", on_fail="move:Back", exit_code=1)
    assert outcome.error is True
    assert outcome.baseline_column == "Blocked"


def test_rollback_move_raise_is_fail_soft_error_true() -> None:
    """A ``move_card`` raise on the rollback is swallowed → ``error=True``."""
    deps = _deps()
    deps.board_writer.move_card.side_effect = RuntimeError("github down")
    outcome = _route(deps, to_column="Merge", from_column="Review", on_fail="rollback", exit_code=1)
    assert outcome.error is True
    assert outcome.baseline_column == "Review"


# ---------------------------------------------------------------------------
# Draft item (no issue number)
# ---------------------------------------------------------------------------


def test_no_issue_number_is_safe_noop() -> None:
    """A draft item (no issue number) routes nothing: baseline = script col, no board op."""
    deps = _deps()
    ticket = Ticket(item_id=_ITEM, issue_number=None, title="t", column_key="PRCI")
    transition = Transition(ticket=ticket, from_column="InProgress", to_column="PRCI")
    outcome = route_script_verdict(
        deps,
        transition,
        to_column="PRCI",
        from_column="InProgress",
        on_fail="move:Back",
        advance="stop",
        exit_code=1,
        output="x",
        blocked_column="Blocked",
        move_rate_limit_per_hour=10,
        antiloop=AntiLoopState(),
        now=1000.0,
    )
    deps.board_writer.move_card.assert_not_called()
    assert outcome.baseline_column == "PRCI"
    assert outcome.finalize_left is False
    assert outcome.error is False


# ---------------------------------------------------------------------------
# Defect 2 — key→name resolution: fix-CI bounce + rollback on multiword columns
# ---------------------------------------------------------------------------


class TestKeyNameResolution:
    """The move-target/baseline must be the board DISPLAY NAME on divergent columns (defect 2).

    The fix-CI loop's ``on_fail: move:InProgress`` and the gate destination ``PR/CI`` carry the
    stable KEY in config but GitHub options are keyed by display NAME. Before the fix, move_card
    raised KeyError on these (card never bounced on red CI), and a rollback baseline recorded as the
    KEY never matched the snapshot NAME → the diff re-fired the rollback every poll (endless recap
    comments). These tests assert the directive KEY now resolves to the display NAME for BOTH the
    board move and the recorded baseline.
    """

    def test_onfail_move_resolves_key_to_display_name(self) -> None:
        """``on_fail: move:InProgress`` moves the card to the NAME "In Progress" (not the KEY)."""
        deps = _deps()
        _route(
            deps,
            to_column="PR/CI",
            on_fail="move:InProgress",
            exit_code=1,
            columns=_shipped_columns(),
        )
        deps.board_writer.move_card.assert_called_once_with(_ITEM, "In Progress")

    def test_rollback_baseline_is_display_name_so_no_reloop(self) -> None:
        """A rollback to a divergent-name origin records the NAME baseline (no re-fire loop).

        The from-column arrives as the display NAME already (the diff emits the snapshot NAME); the
        baseline MUST stay that NAME so ``snapshot.column_key == baseline`` next poll and the bounce
        does not re-fire. Resolution is idempotent on an already-NAME token.
        """
        deps = _deps()
        outcome = _route(
            deps,
            to_column="Merge",
            from_column="Review",
            on_fail="rollback",
            exit_code=1,
            columns=_shipped_columns(),
        )
        deps.board_writer.move_card.assert_called_once_with(_ITEM, "Review")
        assert outcome.baseline_column == "Review"

    def test_advance_auto_resolves_key_to_display_name(self) -> None:
        """``advance: auto:PRCI`` moves the card to the NAME "PR/CI" (not the KEY)."""
        deps = _deps()
        _route(
            deps,
            to_column="In Progress",
            advance="auto:PRCI",
            exit_code=0,
            columns=_shipped_columns(),
        )
        deps.board_writer.move_card.assert_called_once_with(_ITEM, "PR/CI")


# ---------------------------------------------------------------------------
# Defect 9 — run_check_script exports GH_TOKEN + the repo/branch env
# ---------------------------------------------------------------------------


def test_run_check_script_exports_repo_branch_and_gh_token(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """run_check_script passes KANBAN_REPO + KANBAN_BRANCH + GH_TOKEN to the script (defect 9).

    Under PM2 the daemon may not inherit an interactive ``gh auth`` session, so the gate script's
    ``gh`` calls depend on GH_TOKEN being exported from ~/.kanban/token. The repo/branch env feeds
    the script's KANBAN_* guards.
    """
    import kanbanmate.app.script_route as sr  # noqa: PLC0415 — test-local patch target

    monkeypatch.setattr(sr, "load_token", lambda: "ghp_secrettoken")
    deps = MagicMock()
    deps.repo = "owner/repo"
    deps.workspace.discover_branch.return_value = "feat/x"
    deps.workspace.run_transition_script.return_value = (0, "ok")

    sr.run_check_script(deps, 7, "bin/check-pr-ready.sh")

    _issue, _script, env = deps.workspace.run_transition_script.call_args.args
    assert env["KANBAN_REPO"] == "owner/repo"
    assert env["KANBAN_BRANCH"] == "feat/x"
    assert env["GH_TOKEN"] == "ghp_secrettoken"


def test_run_check_script_token_load_failure_is_fail_soft(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A token-load failure does NOT abort the gate — it falls back to ambient gh auth (defect 9)."""
    import kanbanmate.app.script_route as sr  # noqa: PLC0415 — test-local patch target

    def _boom() -> str:
        raise RuntimeError("no token file")

    monkeypatch.setattr(sr, "load_token", _boom)
    deps = MagicMock()
    deps.repo = "owner/repo"
    deps.workspace.discover_branch.return_value = "feat/x"
    deps.workspace.run_transition_script.return_value = (0, "ok")

    code, _out = sr.run_check_script(deps, 7, "bin/check-pr-ready.sh")

    assert code == 0  # the gate still ran
    _issue, _script, env = deps.workspace.run_transition_script.call_args.args
    assert "GH_TOKEN" not in env  # no token exported — script falls back to ambient gh auth
