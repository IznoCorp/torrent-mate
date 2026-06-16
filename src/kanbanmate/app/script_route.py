"""Script-verdict routing: act on a check-script's exit code (DESIGN §6 / §11).

A ``run_script`` transition (or a launch-gate script) runs a mechanical check and yields an
``(exit_code, output)`` verdict. This module turns that verdict into the board moves + ledger
operations the PoC ``runner.py`` performed around ``_apply_script`` / ``_apply_launch``:

* **success** (exit 0) → reset this loop's fix-CI counter, then either an ``advance:auto:<col>``
  TRIGGERING bot move (so the next poll re-fires the chain) or, on ``advance:stop``, just record
  the column; finalize the LEFT stage ✅.
* **failure** (exit ≠0) with ``on_fail:move:<col>`` → bump the per-(issue, dest-col) fix-CI
  counter; within the cap (:data:`_FIXCI_CAP`) a TRIGGERING bounce (the fix-CI loop), beyond it a
  bookkeeping PARK in Blocked (no re-fire).
* **failure** with ``on_fail:rollback`` (or ``""``) → bookkeeping return-to-origin (no re-fire).

The split between TRIGGERING and bookkeeping moves is the load-bearing anti-loop seam (DESIGN §6):
this function does NOT own the tick's ``next_columns`` baseline or the anti-loop state — it RETURNS
a :class:`RouteOutcome` telling the tick what to record. Leaving ``baseline_column`` at the SCRIPT
column re-fires the move on the next poll (``(script_col → target)`` diffs again); setting it to the
bounce target suppresses any re-fire (the NEW analog of the PoC's ``record_bot_move`` bookkeeping —
NEW has no webhook/dedup, the diff baseline IS the idempotency mechanism, DESIGN §6).

Every board op (``move_card`` / ``comment``) is fail-soft (try/except → ``logger.exception`` +
``error=True``): a transient GitHub failure is logged and surfaced via the tick's error count, it
never raises out of the sweep. Ledger writes (the 15.1 ``bump_retry`` / ``reset_retry`` per-(issue,
key) counters) are local fs ops and not separately wrapped — a failing local ledger op is a real
fault the caller's watchdog isolation already catches.

Layering: ``app`` may import ``core`` + ``ports``; this module names only Protocols (via
:class:`~kanbanmate.app.actions.Deps`) plus the pure :class:`~kanbanmate.core.domain.Transition`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kanbanmate.adapters.github.token import load_token
from kanbanmate.app.actions import Deps
from kanbanmate.core.antiloop import AntiLoopState, record_move
from kanbanmate.core.columns import resolve_column
from kanbanmate.core.domain import Column, Transition

logger = logging.getLogger(__name__)


def _to_board_name(columns: dict[str, Column] | None, token: str) -> str:
    """Resolve a config column token (key OR name) to the board's display NAME (defect 2).

    A ``move:<col>`` / ``advance:auto:<col>`` directive carries the stable column KEY (e.g.
    ``"InProgress"``, ``"PRCI"``), but :meth:`GithubClient.move_card` resolves against the GitHub
    Status options, which are keyed by display NAME ("In Progress", "PR/CI"). Passing a KEY where
    the option name differs raised ``KeyError`` and the fix-CI bounce / rollback never moved the
    card. Resolving to the display NAME both lands the move AND keeps the recorded baseline
    NAME-consistent with the snapshot (so a bounce does not re-fire every poll).

    Args:
        columns: The board column model (key → :class:`Column`); ``None`` in unit tests that pass
            bare tokens — then the token is returned verbatim (no model to resolve against).
        token: The directive's destination column (a key or a name).

    Returns:
        The column's display NAME when ``columns`` resolves the token, else ``token`` unchanged.
    """
    if columns is None:
        return token
    resolved = resolve_column(columns, token)
    return resolved.name if resolved is not None else token


# fix-CI loop cap (DESIGN §6, N=2): an ``on_fail:move`` bounce is bounded; beyond the cap the
# ticket is parked in Blocked instead of bouncing forever. Port of the PoC ``runner.py`` ``_FIXCI_CAP``
# (runner.py:45-47) — DISTINCT from the concurrency cap (the max concurrent agent sessions).
_FIXCI_CAP = 2


def fixci_key(column: str) -> str:
    """Per-loop retry-counter key for the fix-CI cap (port ``runner.py::_fixci_key``, :97-105).

    Each ``on_fail:move`` loop gets its OWN budget, keyed by the loop's DESTINATION column (the
    ``to`` column of the transition that ran the gate — e.g. ``"PRCI"`` for ``InProgress→PRCI``,
    ``"Merge"`` for ``Review→Merge``). Two transitions both carrying ``on_fail: move:`` must NOT
    share a single budget, or parking one loop would consume the other's remaining tries.

    Args:
        column: The destination column key the fix-CI loop keys on.

    Returns:
        The per-loop ledger key (``"onfail:<column>"``).
    """
    return f"onfail:{column}"


@dataclass(frozen=True)
class RouteOutcome:
    """What the tick must record after a script verdict was routed.

    The routing issues the board moves + ledger ops directly (through :class:`Deps`), but it does
    NOT own the tick's diff baseline / anti-loop state — those it RETURNS here so the tick stays the
    single owner of ``next_columns`` / ``antiloop`` (mirroring the PoC's split between the runner's
    moves and the dispatcher's bookkeeping).

    Attributes:
        baseline_column: What ``next_columns[item_id]`` must become. Set to the SCRIPT column for a
            TRIGGERING move (so the next poll's diff re-fires ``(script_col → target)``); set to the
            bounce target (Blocked / from_col) for a bookkeeping move (so it does NOT re-fire).
        finalize_left: Whether the tick must finalize the LEFT stage ✅ — ``True`` only on an
            accepted, non-rollback forward SUCCESS (port ``_apply_script`` :618-620); ``False`` on
            any failure routing (a bounce/park/rollback is not a forward advance).
        antiloop: The (possibly updated) anti-loop state. The park-in-Blocked records its move here
            (defense-in-depth backstop, DESIGN §6); a TRIGGERING auto/on_fail move does NOT record
            anti-loop (port ``_auto_move``'s "NOT recorded as a recent bot move", :233-235) — it
            feeds the per-issue move rate-limit instead.
        error: ``True`` iff a routing board op hard-failed (logged, fail-soft) — the tick adds it to
            its error count without aborting the sweep.
    """

    baseline_column: str
    finalize_left: bool
    antiloop: AntiLoopState
    error: bool


def route_script_verdict(
    deps: Deps,
    transition: Transition,
    *,
    to_column: str,
    from_column: str | None,
    on_fail: str,
    advance: str,
    exit_code: int,
    output: str,
    blocked_column: str,
    move_rate_limit_per_hour: int,
    antiloop: AntiLoopState,
    now: float,
    columns: dict[str, Column] | None = None,
) -> RouteOutcome:
    """Route a check-script verdict into board moves + ledger ops (port ``_apply_script``/``_on_fail``).

    The single entry point for BOTH the ``run_script`` path and the launch-gate path (the gate's
    ``on_fail`` IS the same routing — port ``_apply_launch`` :650-652). Every board op is fail-soft;
    the persisted ``{{script_output}}`` sink (15.7) is updated on every verdict (the failing output
    is stashed for the fix-CI launch, the success path clears it so a stale failure never bleeds).

    Args:
        deps: The injected adapter bundle (board writer + store ledger).
        transition: The diff transition being routed (its ticket carries the item id + issue).
        to_column: The script transition's destination column (the loop budget key + re-fire seam).
        from_column: The transition's origin column (the rollback target); may be ``None`` (a
            brand-new item) — falls back to ``to_column``.
        on_fail: The ``on_fail`` policy (``"move:<col>"`` | ``"rollback"`` | ``""``).
        advance: The ``advance`` directive (``"auto:<col>"`` | ``"stop"``).
        exit_code: The script's exit code (0 = success).
        output: The script's combined stdout/stderr (persisted for ``{{script_output}}``).
        blocked_column: The Blocked column key a fix-CI-capped ticket is parked in.
        move_rate_limit_per_hour: The per-issue AUTO/bot-move ceiling (config default, 13.4). The
            OUTER cross-loop backstop over the per-loop :data:`_FIXCI_CAP`: a triggering auto-advance
            or on_fail bounce that would push the durable move count to/over this cap parks the card
            in Blocked instead of moving (the canonical ``>= cap`` forward-budget semantics; the
            reaper park is EXCLUDED from this budget — Candidate 1).
        antiloop: The anti-loop state carried in from the tick's baseline.
        now: The current wall-clock time (move timestamps + ledger window).
        columns: The board column model used to resolve ``move:``/``auto:`` destination KEYS to the
            GitHub display NAMES :meth:`move_card` expects (defect 2). ``None`` in unit tests that
            pass bare tokens — then directives move verbatim.

    Returns:
        The :class:`RouteOutcome` the tick records (baseline + finalize flag + antiloop + error).
    """
    issue = transition.ticket.issue_number
    item_id = transition.ticket.item_id
    if issue is None:
        # A draft item with no issue cannot key the worktree/ledger — nothing to route. Leave the
        # baseline at the script column (the safe no-op) and finalize nothing.
        return RouteOutcome(
            baseline_column=to_column, finalize_left=False, antiloop=antiloop, error=False
        )

    if exit_code == 0:
        return _route_success(
            deps,
            issue=issue,
            item_id=item_id,
            to_column=to_column,
            advance=advance,
            blocked_column=blocked_column,
            move_rate_limit_per_hour=move_rate_limit_per_hour,
            antiloop=antiloop,
            now=now,
            columns=columns,
        )
    # Failure: stash the failing output for the fix-CI launch's {{script_output}} (15.7) BEFORE
    # routing, so the marker is present even if a board op below fails fail-soft. The success path
    # CLEARS this (see _route_success) so a stale failure output never bleeds into a later launch.
    if output:
        try:
            deps.store.save_script_output(issue, output)
        except Exception:
            # Fail-soft: a failed marker write only loses the {{script_output}} fill, never the route.
            logger.exception("script_output stash failed for #%s; continuing", issue)
    return _route_failure(
        deps,
        issue=issue,
        item_id=item_id,
        to_column=to_column,
        from_column=from_column,
        on_fail=on_fail,
        blocked_column=blocked_column,
        move_rate_limit_per_hour=move_rate_limit_per_hour,
        antiloop=antiloop,
        now=now,
        columns=columns,
    )


def _park_runaway(
    deps: Deps,
    *,
    issue: int,
    item_id: str,
    blocked_column: str,
    antiloop: AntiLoopState,
    now: float,
    reason: str,
) -> RouteOutcome:
    """Park a runaway card in Blocked when the per-issue move rate-limit is exceeded (port ``_park_blocked``).

    The OUTER cross-loop backstop (DESIGN §6, port PoC ``runner.py:504-518`` ``if count >= cap:
    _park_blocked()``) over the per-loop :data:`_FIXCI_CAP` inner bound. Multiple INDEPENDENT
    auto/on_fail loops (distinct ``onfail:<col>`` budget keys) can churn one card faster than any
    single loop's fix-CI cap; this gate bounds the durable per-issue move count (fed by every
    auto-advance + on_fail bounce). It fires ONLY on AUTO/bot moves — a human launch or the agent's
    own ``kanban-move`` never feeds ``record_move_for_item``, so this path is never reached by them
    (the §6 cap guards the bot loop, not the human workflow).

    A bookkeeping move: the card goes to Blocked, the daemon's OWN park move is anti-loop recorded
    (defense-in-depth so a later tick recognises it), and the baseline is set to Blocked so the diff
    does NOT re-fire. Every board op is fail-soft (try/except → ``logger.exception`` + ``error``).

    Args:
        deps: The injected adapter bundle (board writer).
        issue: The ticket's issue number (the recap-comment target).
        item_id: The board card node id (the move target).
        blocked_column: The Blocked column key the runaway is parked in.
        antiloop: The anti-loop state carried in (the park records its move here).
        now: The current wall-clock time (the anti-loop move timestamp).
        reason: A short cause tag woven into the recap comment (e.g. ``"auto-advance"``).

    Returns:
        The :class:`RouteOutcome` (baseline = Blocked, finalize_left ``False``, antiloop updated).
    """
    error = False
    try:
        deps.board_writer.move_card(item_id, blocked_column)
        deps.board_writer.comment(
            issue,
            f"KanbanMate: move rate limit exceeded ({reason}) — parked in Blocked.",
        )
    except Exception:
        logger.exception("rate-limit park-in-Blocked failed for #%s; continuing", issue)
        error = True
    # Record the daemon's own park move so the anti-loop guard recognises it on a later tick
    # (defense-in-depth, DESIGN §6). The baseline = Blocked so the diff does NOT re-fire.
    antiloop = record_move(antiloop, item_id, blocked_column, now=now)
    return RouteOutcome(
        baseline_column=blocked_column,
        finalize_left=False,
        antiloop=antiloop,
        error=error,
    )


def _route_success(
    deps: Deps,
    *,
    issue: int,
    item_id: str,
    to_column: str,
    advance: str,
    blocked_column: str,
    move_rate_limit_per_hour: int,
    antiloop: AntiLoopState,
    now: float,
    columns: dict[str, Column] | None = None,
) -> RouteOutcome:
    """Route a success (exit 0): reset the loop counter + advance (port ``_apply_script`` success).

    Resets THIS loop's fix-CI counter and clears the stashed ``{{script_output}}`` (so a stale
    failure output never bleeds into a later launch). On ``advance:auto:<col>`` a TRIGGERING bot move
    re-enters the board (baseline stays at the script column so the next diff re-fires the chain);
    on ``advance:stop`` no move (baseline = the script column where the card already sits). A success
    finalizes the LEFT stage ✅ either way.

    Before the auto-advance move, the OUTER cross-loop rate-limit gate is checked: if the durable
    per-issue move count is already ``>= move_rate_limit_per_hour`` (the canonical forward-budget
    ``>= cap`` semantics — the cap-th move allowed, the (cap+1)-th parked), the card is parked in Blocked via
    :func:`_park_runaway` INSTEAD of the move (AUTO/bot moves only). ``advance:stop`` issues no move,
    so it bypasses the gate. The per-loop :data:`_FIXCI_CAP` stays the inner bound.

    Args:
        deps: The injected adapter bundle.
        issue: The ticket's issue number (the ledger / output key).
        item_id: The board card node id (the move target).
        to_column: The script column (the loop budget key + the diff baseline / re-fire seam).
        advance: The ``advance`` directive (``"auto:<col>"`` | ``"stop"``).
        blocked_column: The Blocked column a rate-limited runaway is parked in.
        move_rate_limit_per_hour: The per-issue AUTO/bot-move ceiling (the OUTER backstop, ``>= cap``).
        antiloop: The anti-loop state carried in (unchanged on a within-limit auto-move — it is NOT
            anti-loop-recorded; a park records the park move).
        now: The current wall-clock time (the move rate-limit timestamp).

    Returns:
        The :class:`RouteOutcome` (baseline = the script column on a within-limit advance; finalize
        ``True``) or the :func:`_park_runaway` outcome (baseline = Blocked) when the cap is exceeded.
    """
    # Reset THIS loop's fix-CI counter on success (port _apply_script :608) + clear the stashed
    # output so the next launch never sees a stale failure dump.
    deps.store.reset_retry(issue, fixci_key(to_column))
    try:
        deps.store.save_script_output(issue, "")
    except Exception:
        logger.exception("script_output clear failed for #%s; continuing", issue)

    error = False
    if advance.startswith("auto:"):
        target = advance[len("auto:") :].strip()
        # OUTER cross-loop backstop (port runner.py:504-518): a card that has already made >= cap
        # AUTO/bot moves this hour (across ALL independent auto/on_fail loops) is parked in Blocked
        # instead of advancing again. The per-loop _FIXCI_CAP is the inner bound; this is the outer.
        if deps.store.move_count_for_item_last_hour(issue, now=now) >= move_rate_limit_per_hour:
            return _park_runaway(
                deps,
                issue=issue,
                item_id=item_id,
                blocked_column=blocked_column,
                antiloop=antiloop,
                now=now,
                reason="auto-advance",
            )
        # TRIGGERING bot move (port _auto_move): re-enter the board so the next diff reacts. The
        # move is NOT anti-loop-recorded ("NOT recorded as a recent bot move", :233-235); it feeds
        # ONLY the per-issue move rate-limit backstop (record_move_for_item). Resolve the directive
        # KEY to the board's display NAME (defect 2) so move_card lands on a multiword column.
        target_name = _to_board_name(columns, target)
        try:
            deps.board_writer.move_card(item_id, target_name)
            deps.store.record_move_for_item(issue, now=now)
        except Exception:
            logger.exception(
                "advance auto-move to %r failed for #%s; continuing", target_name, issue
            )
            error = True
    # advance == "stop" (or any non-auto): no move — the card already sits in the script column.
    # baseline stays the SCRIPT column either way (an auto-move re-fires (script_col→target) on the
    # next diff; a stop just records the column). finalize the LEFT stage ✅ (port :618-620).
    return RouteOutcome(
        baseline_column=to_column, finalize_left=True, antiloop=antiloop, error=error
    )


def _route_failure(
    deps: Deps,
    *,
    issue: int,
    item_id: str,
    to_column: str,
    from_column: str | None,
    on_fail: str,
    blocked_column: str,
    move_rate_limit_per_hour: int,
    antiloop: AntiLoopState,
    now: float,
    columns: dict[str, Column] | None = None,
) -> RouteOutcome:
    """Route a failure (exit ≠0): on_fail move (capped) / rollback (port ``_on_fail``, :536-570).

    ``on_fail:move:<col>`` bumps the per-(issue, dest-col) fix-CI counter: within the cap a
    TRIGGERING bounce (the fix-CI loop, baseline = the script column so it re-fires); beyond the cap
    a bookkeeping PARK in Blocked (counter reset, baseline = Blocked so it does NOT re-fire,
    anti-loop recorded). ``on_fail:rollback`` (or ``""``) is a bookkeeping return-to-origin (baseline
    = from_col so it does NOT re-fire). A failure never finalizes the LEFT stage ✅.

    Before a within-cap bounce issues its triggering move, the OUTER cross-loop rate-limit gate is
    checked: if the durable per-issue move count is already ``>= move_rate_limit_per_hour`` (matching
    the canonical forward-budget ``>= cap`` check — the cap-th move allowed, the (cap+1)-th parked),
    the card is parked in
    Blocked via :func:`_park_runaway` INSTEAD of bouncing (AUTO/bot moves only). The per-loop fix-CI
    cap stays the inner per-loop bound; this gate is the cross-loop OUTER bound checked on the
    triggering bounce (the cap-park and the rollback path issue no auto/bot move, so they bypass it).

    Args:
        deps: The injected adapter bundle.
        issue: The ticket's issue number (the ledger key).
        item_id: The board card node id (the move target).
        to_column: The script column (the fix-CI loop budget key + the re-fire seam).
        from_column: The transition origin (the rollback target); ``None`` falls back to ``to_column``.
        on_fail: The ``on_fail`` policy (``"move:<col>"`` | ``"rollback"`` | ``""``).
        blocked_column: The Blocked column a fix-CI-capped or rate-limited ticket is parked in.
        move_rate_limit_per_hour: The per-issue AUTO/bot-move ceiling (the OUTER backstop, ``>= cap``).
        antiloop: The anti-loop state carried in (the park records its move here).
        now: The current wall-clock time (move timestamps).

    Returns:
        The :class:`RouteOutcome` (baseline depends on the branch; finalize_left always ``False``).
    """
    if on_fail.startswith("move:"):
        target = on_fail[len("move:") :].strip()
        # Per-loop budget keyed by THIS transition's destination column so the two on_fail loops
        # (InProgress→PRCI and Review→Merge) never share one budget (port :546-548).
        count = deps.store.bump_retry(issue, fixci_key(to_column))
        if count > _FIXCI_CAP:
            # Cap reached → PARK in Blocked (bookkeeping; NO re-trigger). Reset the counter so a
            # later re-entry starts fresh (port _on_fail :551 + _park_blocked :212-227).
            deps.store.reset_retry(issue, fixci_key(to_column))
            error = False
            try:
                deps.board_writer.move_card(item_id, blocked_column)
                deps.board_writer.comment(
                    issue,
                    f"KanbanMate: check {to_column} failed after {_FIXCI_CAP} attempts "
                    "— parked in Blocked.",
                )
            except Exception:
                logger.exception("fix-CI park-in-Blocked failed for #%s; continuing", issue)
                error = True
            # Record the daemon's own park move so the anti-loop guard recognises it on a later tick
            # (defense-in-depth, DESIGN §6). The baseline = Blocked so the diff does NOT re-fire.
            antiloop = record_move(antiloop, item_id, blocked_column, now=now)
            return RouteOutcome(
                baseline_column=blocked_column,
                finalize_left=False,
                antiloop=antiloop,
                error=error,
            )
        # OUTER cross-loop backstop (port runner.py:504-518): before the within-cap bounce, park the
        # card if it has already made >= cap AUTO/bot moves this hour. The per-loop fix-CI cap above
        # is the inner bound; independent on_fail loops (distinct onfail:<col> keys) can churn a card
        # faster than any single budget, so this triggering bounce is gated on the durable counter.
        if deps.store.move_count_for_item_last_hour(issue, now=now) >= move_rate_limit_per_hour:
            # The rate-park ENDS this on_fail loop, so clear its per-loop fix-CI budget — consistent
            # with the cap-park above (PoC parity: a park ends the loop → resets its budget). Without
            # this the bump above survives and starves a later re-entry of fix-CI bounces.
            deps.store.reset_retry(issue, fixci_key(to_column))
            return _park_runaway(
                deps,
                issue=issue,
                item_id=item_id,
                blocked_column=blocked_column,
                antiloop=antiloop,
                now=now,
                reason="on_fail bounce",
            )
        # Within cap → TRIGGERING on_fail bounce (the fix-CI loop). NOT anti-loop-recorded (port
        # _auto_move); feeds ONLY the per-issue move rate-limit. baseline stays the SCRIPT column so
        # the next diff re-fires (script_col → target) and the chain proceeds. Resolve the directive
        # KEY (e.g. ``move:InProgress``) to the board's display NAME (defect 2) so the fix-CI bounce
        # lands on a multiword column instead of raising KeyError inside move_card.
        target_name = _to_board_name(columns, target)
        error = False
        try:
            deps.board_writer.move_card(item_id, target_name)
            deps.store.record_move_for_item(issue, now=now)
        except Exception:
            logger.exception("on_fail move to %r failed for #%s; continuing", target_name, issue)
            error = True
        return RouteOutcome(
            baseline_column=to_column, finalize_left=False, antiloop=antiloop, error=error
        )

    # rollback (or empty on_fail) → bookkeeping return-to-origin (port _on_fail :564-570 — the
    # guarded rollback target is `from`). NEW has no ROLLBACK ActionKind here (out of scope); this
    # is a best-effort move_card + recap comment. baseline = the from_col so it does NOT re-fire.
    # Resolve to the board's display NAME (defect 2): the baseline is this target, and it MUST equal
    # the snapshot NAME or the diff re-fires the rollback every poll (the endless recap-comment loop).
    target = _to_board_name(columns, from_column or to_column)
    error = False
    try:
        deps.board_writer.move_card(item_id, target)
        deps.board_writer.comment(
            issue,
            f"KanbanMate: check {to_column} failed — card returned to {target}.",
        )
    except Exception:
        logger.exception("on_fail rollback to %r failed for #%s; continuing", target, issue)
        error = True
    return RouteOutcome(baseline_column=target, finalize_left=False, antiloop=antiloop, error=error)


def run_check_script(deps: Deps, issue_number: int, script: str) -> tuple[int, str]:
    """Discover the worktree branch, build the env, and run a check script (port ``_apply_script``).

    The thin "discover branch + env + run" unit shared by the ``run_script`` path AND the launch
    gate. The worktree is on its WIP branch ``kanban/ticket-<n>`` (or ``feat/<codename>`` post
    create-branch); a still-detached / GONE worktree reports no branch → ``KANBAN_BRANCH=""`` (an
    honest answer that correctly FAILS a PR check, port ``_discover_branch`` :573-582). The check
    scripts hard-require
    ``KANBAN_REPO`` + ``KANBAN_BRANCH`` (their ``: "${KANBAN_REPO:?}"`` guards, port ``_script_env``
    :585-592). The subprocess itself is bounded inside
    :meth:`~kanbanmate.ports.workspace.Workspace.run_transition_script`.

    Args:
        deps: The injected adapter bundle (the workspace port runs the script).
        issue_number: The ticket whose worktree roots the run.
        script: The script path to run (relative to the clone, or absolute).

    Returns:
        The ``(exit_code, combined_output)`` tuple the workspace runner returns.
    """
    branch = deps.workspace.discover_branch(issue_number) or ""
    env = {"KANBAN_REPO": deps.repo, "KANBAN_BRANCH": branch}
    # Export GH_TOKEN from ~/.kanban/token (or $KANBAN_TOKEN) into the script env (defect 9): under
    # PM2 the daemon may not inherit an interactive ``gh auth login`` session, so the check scripts'
    # ``gh`` calls would otherwise depend on ambient auth and fail. ``gh`` honours GH_TOKEN. Fail-SOFT:
    # a missing/unreadable token must NOT abort the gate — the script then falls back to ambient gh
    # auth (and honestly fails the gate if there is none), which is the correct routing signal.
    try:
        token = load_token()
        if token:
            env["GH_TOKEN"] = token
    except Exception:
        logger.exception(
            "could not load GH_TOKEN for check script #%s; relying on ambient gh auth", issue_number
        )
    return deps.workspace.run_transition_script(issue_number, script, env)


__all__ = ["RouteOutcome", "route_script_verdict", "run_check_script", "fixci_key", "_FIXCI_CAP"]
