"""The stale-agent reaper: the tick's post-step that ages out silent agents (DESIGN §8.3).

Extracted from :mod:`kanbanmate.app.tick` (15.6 LOC budget — tick.py was at the 1000-LOC hard
ceiling once the script-routing branches landed). The reap step is self-contained: it lists the
persisted running tickets, and for any whose agent heartbeat aged past the TTL it either RELAUNCHES
the stale session once (the retry budget) or parks the card in the Blocked column.

The per-action watchdog (:func:`kanbanmate.app.tick._run_with_watchdog`) is LAZILY imported inside
:func:`reap_stale_agents` to avoid a circular import (``tick`` imports this module to call the reap
step). The watchdog stays in ``tick`` because :func:`~kanbanmate.app.tick._drain_queue` and the main
loop also use it, and a test monkeypatches ``tick._run_with_watchdog`` for the drain path.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2); this module names
only Protocols (via :class:`~kanbanmate.app.actions.Deps`) plus the pure core.
"""

from __future__ import annotations

import dataclasses
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from kanbanmate.app.actions import BlockAction, Deps, LaunchAction, TeardownAction
from kanbanmate.app.body_status import update_body_status
from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.core.antiloop import AntiLoopState, record_move
from kanbanmate.core.domain import Ticket
from kanbanmate.core.launch_keys import is_waiting_for_input
from kanbanmate.core.stage_comment import HeaderInfo, fmt_timestamp, header_from_state
from kanbanmate.ports.store import TicketState, TicketStatus

if TYPE_CHECKING:
    from kanbanmate.app.tick import TickConfig

logger = logging.getLogger(__name__)

# A stale/dead running session is RELAUNCHED at most this many times before the reaper parks it
# in Blocked (DESIGN §8.3; port of the PoC ``reaper.RETRY_LIMIT`` = 1). The first heartbeat miss
# kills the dead session, bumps ``TicketState.retries`` and refreshes the heartbeat, then relaunches
# the same stage once; the next miss (``retries >= RETRY_LIMIT``) goes straight to Blocked.
RETRY_LIMIT = 1

# A graceful done-exit (end_session: Escape→C-u→C-d→C-d→Enter) is dispatched at most this many times before
# the reaper ESCALATES to killing the claude REPL process. A genuinely-hung REPL or stubborn leftover
# state can swallow the keystrokes; after MAX_END_ATTEMPTS we SIGKILL the claude child (NOT the
# session/shell) so the surviving shell still runs ``; kanban-session-end``. Kept small (the keystroke
# path usually works on attempt 1-2; helm #5 needed the menu-close + double-C-d the robust sequence
# now sends in ONE dispatch).
MAX_END_ATTEMPTS = 3


@dataclass(frozen=True)
class _ReapMove:
    """An internal watchdog-bounded command that parks a reaped card in the Blocked column.

    The reap step (DESIGN §8.3) moves a stale agent's card to the Blocked column so the stall is
    visible on the board. That is a one-line ``BoardWriter.move_card`` call, but routing it through
    the same ``_run_with_watchdog`` path as the real actions gives it the same hang-protection
    (a hung GitHub move cannot freeze the sweep) and exception isolation, without inventing a new
    public :class:`~kanbanmate.app.actions.Action`. It is private to the reaper because it has no pure
    :class:`~kanbanmate.core.domain.Action` counterpart — it is a mechanical board label, not a
    decided transition.

    Attributes:
        item_id: The ``ProjectV2Item`` node id of the card to move (from persisted state).
        column: The destination column key (``config.blocked_column``).
    """

    item_id: str
    column: str

    def execute(self, deps: Deps) -> None:
        """Move the card into the Blocked column via the board writer.

        Args:
            deps: The adapter bundle to act through.
        """
        deps.board_writer.move_card(self.item_id, self.column)


def _session_alive(deps: Deps, issue_number: int) -> bool:
    """Return whether ``issue_number``'s tmux session is live — FAIL-CLOSED on the probe.

    The reap gate (#26) widens the skip condition to ``fresh AND alive``, so a dead session is
    reaped even with a fresh heartbeat. But the ``is_alive`` probe touches the live tmux server and
    could throw or hang transiently; a probe blip must NEVER (a) crash the sweep, nor (b) wrongly
    reap a fresh-heartbeat ticket. So on ANY probe exception we treat the session as ALIVE — that
    leaves the heartbeat-TTL path intact (the gate falls back to the heartbeat-only decision: a
    fresh ticket is skipped, a stale one is reaped). The dead-session trigger is best-effort
    additive resilience; the heartbeat TTL remains the durable backstop.

    Args:
        deps: The injected adapter bundle (the sessions port backing the tmux probe).
        issue_number: The ticket whose session liveness to probe. The session name is
            ``f"ticket-{issue_number}"`` — the same derivation :func:`_try_relaunch` uses.

    Returns:
        ``True`` if the tmux session ``ticket-<issue>`` exists OR the probe raised (fail-closed);
        ``False`` only when the probe DEFINITIVELY reports the session gone.
    """
    session_name = f"ticket-{issue_number}"
    try:
        return deps.sessions.is_alive(session_name)
    except Exception:
        # Fail-closed: a throwing/slow probe must not crash the sweep nor wrongly reap a fresh
        # ticket — report "alive" so the gate falls back to the heartbeat-only decision.
        logger.exception(
            "reaper is_alive probe failed for #%s; treating session as alive (fail-closed)",
            issue_number,
        )
        return True


def _pane_shows_waiting(deps: Deps, issue_number: int) -> bool:
    """Return whether ``issue_number``'s alive session is BLOCKED on a human prompt — FAIL-CLOSED (§B).

    Captures the tmux pane and classifies it with the pure
    :func:`kanbanmate.core.launch_keys.is_waiting_for_input`. A ``True`` verdict means the agent is
    waiting for a human decision (the reaper must NOT reap it — mark WAITING + signal instead). On
    ANY capture/classify exception we FAIL CLOSED — report ``False`` (NOT waiting) so a broken pane
    is reaped rather than wedging a concurrency slot forever on an undecidable pane (phase-27 §B,
    the conservative-reap operator call). Distinct fail direction from :func:`_session_alive` (which
    fails OPEN to preserve a fresh ticket): here a bad pane must NEVER pin a slot.

    Args:
        deps: The injected adapter bundle (the sessions port backing the pane capture).
        issue_number: The ticket whose pane to classify. The session name is
            ``f"ticket-{issue_number}"`` (the same derivation the rest of the reaper uses).

    Returns:
        ``True`` iff the captured pane shows a pending human-input prompt; ``False`` on no marker OR
        any capture/classify error (fail-closed → reap).
    """
    session_name = f"ticket-{issue_number}"
    try:
        pane = deps.sessions.capture(session_name)
        return is_waiting_for_input(pane)
    except Exception:
        # Fail-closed: a throwing capture/classify must not wedge a slot on a broken pane — treat as
        # NOT waiting so the ticket is reaped (the conservative call, phase-27 §B).
        logger.exception(
            "reaper pane-capture/classify failed for #%s; treating as NOT waiting (fail-closed reap)",
            issue_number,
        )
        return False


def _pane_has_active_turn(deps: Deps, issue_number: int) -> bool:
    """Return whether ``issue_number``'s alive session is mid-turn (``esc to interrupt``) — FAIL-CLOSED.

    Captures the pane and looks for the running-turn footer
    (:data:`kanbanmate.core.launch_keys.SUBMITTED_MARKERS`, i.e. ``esc to interrupt``) in only the
    LAST :data:`~kanbanmate.core.launch_keys.SUBMIT_SCAN_LINES` lines — the live input-box/footer
    region (mirrors :func:`~kanbanmate.core.launch_keys.prompt_pending`). Scanning the WHOLE captured
    pane would let a STALE ``esc to interrupt`` line left in scrollback false-positive "active turn"
    forever, so a finished done agent could never be cleanly exited. A ``True`` verdict means a turn
    is in flight — the reaper must NOT exit the REPL even if the agent signalled done (it would
    interrupt live work). FAIL-CLOSED to ``True`` (treat as active) on any capture/classify error so
    an undecidable pane is NEVER exited (the conservative call: an uncertain pane parks WAITING via
    the normal path, it is never cleanly exited).

    Args:
        deps: The injected adapter bundle (the sessions port backing the pane capture).
        issue_number: The ticket whose pane to classify (session ``ticket-<issue>``).

    Returns:
        ``True`` iff the pane TAIL shows a running turn OR the capture raised (fail-closed); ``False``
        only when the capture DEFINITIVELY shows an idle pane.
    """
    from kanbanmate.core.launch_keys import SUBMIT_SCAN_LINES, SUBMITTED_MARKERS

    session_name = f"ticket-{issue_number}"
    try:
        # Scan only the trailing live region (same idiom as prompt_pending) so a stale marker in
        # scrollback cannot pin the agent "active" forever.
        tail = "\n".join(deps.sessions.capture(session_name).splitlines()[-SUBMIT_SCAN_LINES:])
        lowered = tail.lower()
        return any(marker.lower() in lowered for marker in SUBMITTED_MARKERS)
    except Exception:
        logger.exception(
            "reaper active-turn probe failed for #%s; treating as active (fail-closed)",
            issue_number,
        )
        return True


def _end_done_session(deps: Deps, state: TicketState, now: float) -> bool:
    """Cleanly EXIT a done + idle alive session, escalating to a REPL kill after repeated failures.

    BOUNDED-RETRY-THEN-KILL escalation (firm-exit). On each tick this branch is entered for a done +
    idle + alive session; the helper reads the persisted attempt counter
    (:meth:`~kanbanmate.ports.store.StateStore.get_end_attempts`) and:

    * **attempts < :data:`MAX_END_ATTEMPTS`** — FIRST probe
      :meth:`~kanbanmate.ports.workspace.Sessions.repl_alive` (Candidate 2): if the ``claude`` REPL
      has ALREADY exited (a daemon restart raced the wrapper, so the done breadcrumb lingers but the
      child is gone), CONSUME the branch (return ``True``) WITHOUT re-sending keystrokes or bumping —
      session-end / purge completes on its own and the WAITING-park never fires. Otherwise dispatch
      the ROBUST graceful exit
      (:meth:`~kanbanmate.ports.workspace.Sessions.end_session`: Escape→C-u→C-d→C-d→Enter → ``claude``
      exits → the trailing ``; kanban-session-end <issue>`` runs the teardown), then BUMP the counter.
      The done breadcrumb is **LEFT in place** (the single-shot clear of the old contract is gone for
      this path), so the next tick RE-ENTERS the branch and re-dispatches until the REPL exits or the
      budget is hit. A FAILED dispatch returns ``False`` WITHOUT bumping or clearing — the keystrokes
      never reached ``claude`` (no ``; kanban-session-end`` collision risk), so the next tick simply
      retries the SAME attempt number.
    * **attempts >= :data:`MAX_END_ATTEMPTS`** — the graceful exit failed repeatedly (a genuinely-hung
      REPL or stubborn state swallowing the keystrokes). ESCALATE:
      :meth:`~kanbanmate.ports.workspace.Sessions.kill_repl_process` SIGKILLs the ``claude`` child
      (NOT the session/shell) so the surviving shell still runs ``; kanban-session-end`` → teardown.
      Then CLEAR the done breadcrumb AND the attempt counter (whether or not the SIGKILL landed
      cleanly — the graceful budget is spent), so the next tick falls through to Approach A: the
      still-dying session parks WAITING (non-destructive) until it dies → reaped, OR
      ``kanban-session-end`` purges its state (incl. both markers via ``purge_ticket``).

    Reversal of the earlier **SINGLE-SHOT** contract: that single dispatch could no-op on the helm #5
    leftover-box + background-shell condition and the consumed breadcrumb parked the finished agent
    WAITING forever. The robust ``end_session`` now sends the menu-close + clear + double-C-d in ONE
    dispatch, and the bounded retry + REPL-kill escalation is the engine guarantee.

    FAIL-SOFT throughout: every store/sessions call is guarded; an error is logged and never crashes
    the sweep. Approach A is preserved by the CALLER (this only ever runs for a done + idle + alive
    session — a WORKING/not-done session is never reached here).

    Args:
        deps: The injected adapter bundle (the sessions + store ports).
        state: The done + idle ticket's persisted state.
        now: The current wall-clock time (unused today; kept for symmetry with the WAITING helpers).

    Returns:
        ``True`` iff this tick consumed the branch (dispatched + bumped, or escalated + cleared);
        ``False`` only when the graceful dispatch RAISED (no bump/clear — retried next tick).
    """
    issue = state.issue_number
    # Read the persisted attempt budget; a read error degrades to 0 (treat as the first attempt — the
    # fs reader is already poison-tolerant, but guard the call so the sweep never crashes).
    try:
        attempts = deps.store.get_end_attempts(issue)
    except Exception:
        logger.exception("reaper get_end_attempts failed for #%s; treating as 0", issue)
        attempts = 0

    if attempts < MAX_END_ATTEMPTS:
        # Candidate 2 — daemon-restart mid-done-exit idempotency: before re-sending the graceful
        # end_session keystrokes, confirm the pane still hosts a live comm-verified claude child. A
        # daemon restart can race the wrapper — the REPL may have already exited (its trailing
        # ``; kanban-session-end`` is running / has run) while the done breadcrumb has not yet been
        # purged. Re-sending keystrokes then is wasted and could disturb the pane. When the REPL is
        # already gone, CONSUME the branch (return True) WITHOUT bumping/dispatching, so the
        # WAITING-park does not fire and session-end / purge completes on its own. FAIL-SOFT: the
        # probe never raises (it returns False on any error), so a probe failure simply falls through
        # to the normal graceful dispatch (no regression).
        try:
            if not deps.sessions.repl_alive(f"ticket-{issue}"):
                # The claude child already exited (restart raced the wrapper). Nothing to exit —
                # let session-end / purge complete; consume the branch (no keystrokes, no WAITING).
                return True
        except Exception:
            logger.exception(
                "reaper repl_alive probe failed for #%s; proceeding with graceful dispatch", issue
            )
        # Bounded-retry path: dispatch the robust graceful exit and bump the counter. Leave the done
        # breadcrumb so the next tick re-enters and re-dispatches until exit or the budget is hit.
        try:
            deps.sessions.end_session(f"ticket-{issue}")
        except Exception:
            # The keystrokes never reached claude → no ; kanban-session-end collision. Do NOT bump or
            # clear; the next tick retries the SAME attempt number.
            logger.exception(
                "reaper end_session failed for #%s; leaving for the next tick (no bump/clear)",
                issue,
            )
            return False
        try:
            deps.store.bump_end_attempt(issue)
        except Exception:
            # A bump failure must not crash the sweep; worst case the next tick re-dispatches at the
            # same (un-bumped) attempt number — still bounded by the eventual REPL exit / kill.
            logger.exception("reaper bump_end_attempt failed for #%s; continuing", issue)
        return True

    # ESCALATION: the graceful budget is exhausted → SIGKILL the claude REPL child (NOT the session)
    # so the surviving shell still runs ``; kanban-session-end``. Fail-soft — even if the kill raises
    # we still clear, because the graceful budget is spent and re-dispatching would only re-fail.
    try:
        deps.sessions.kill_repl_process(f"ticket-{issue}")
    except Exception:
        logger.exception(
            "reaper kill_repl_process failed for #%s; clearing anyway (budget spent)", issue
        )
    # PRESERVE THE DONE BREADCRUMB (helm #5 stranding fix). The SIGKILL only terminates a stuck REPL
    # whose AGENT already finished (it is in the ``done`` branch — it dropped ``kanban-done``); the kill
    # is cleanup of a stubborn exit dialog, NOT a failure. The surviving shell now runs the trailing
    # ``; kanban-session-end``, which reads the done breadcrumb and AUTO-ADVANCES the card (DESIGN §13).
    # Clearing the breadcrumb here used to RACE that wrapper — when the reaper won, session-end saw no
    # done and finalized ⚠️ interrupted with NO advance, stranding a legitimately-finished agent one
    # stage early. So we DO NOT clear ``done`` — session-end owns its consumption (it purges the
    # breadcrumb after reading + advancing). We DO clear the attempt counter (the graceful budget is
    # spent; a re-entry must not re-SIGKILL — and with claude now dead ``repl_alive`` is False, so the
    # next tick short-circuits without re-dispatching until session-end purges the ticket).
    try:
        deps.store.clear_end_attempts(issue)
    except Exception:
        logger.exception(
            "reaper clear_end_attempts failed for #%s after escalation; continuing", issue
        )
    return True


def _reset_stale_end_attempts(deps: Deps, issue_number: int) -> None:
    """Drop a lingering done-exit attempt counter for a NOT-done ``issue_number`` (firm-exit §3.4).

    The defensive reset point for the case where the done breadcrumb is gone but a stale
    ``end_attempts/<issue>`` counter lingers — e.g. a daemon restart mid-escalation, or an agent that
    never reached done. Reads the counter and clears it ONLY when ``> 0``, so a not-done session never
    carries a stale attempt count into a LATER done cycle. FAIL-SOFT: any store error is logged and
    never crashes the sweep (the primary reset is ``purge_ticket`` at teardown; this only catches the
    orphaned-counter edge case).

    Args:
        deps: The injected adapter bundle (the store port).
        issue_number: The not-done ticket whose lingering counter to reset.
    """
    try:
        if deps.store.get_end_attempts(issue_number) > 0:
            deps.store.clear_end_attempts(issue_number)
    except Exception:
        logger.exception(
            "reaper defensive clear_end_attempts failed for #%s; continuing", issue_number
        )


def _enter_waiting(deps: Deps, state: TicketState, now: float) -> None:
    """Persist ``WAITING`` for ``state`` and SIGNAL the user via the ⏳ stage sticky (§B).

    Idempotent: persists ``status=WAITING`` (a heartbeat-untouched, retries-untouched save — the
    agent is alive, just blocked on the human) and upserts the ⏳ "waiting for your input" header on
    the issue sticky so the GitHub issue surfaces that intervention is needed. The sticky upsert is
    fail-soft (a GitHub error must never affect the sweep). Re-entering WAITING on a later tick is a
    no-op-equivalent: the same status is re-saved and the same header re-rendered.

    Args:
        deps: The injected adapter bundle (the store + the board writer for the sticky).
        state: The stale-but-waiting ticket's persisted state.
        now: The current wall-clock time (NOT written to the heartbeat — the agent's silence is
            expected while it waits; only a real agent tool-call refreshes the heartbeat).
    """
    # Persist WAITING WITHOUT bumping retries or refreshing the heartbeat: the agent is alive and
    # legitimately silent, so its (stale) heartbeat stays as-is — a later REAL refresh (the human
    # answered → the agent resumed) is what flips it back to RUNNING.
    try:
        deps.store.save(replace(state, status=TicketStatus.WAITING))
    except Exception:
        logger.exception(
            "reaper WAITING-state write failed for #%s; continuing", state.issue_number
        )
    # SIGNAL the user on the GitHub issue: flip the stage sticky header to ⏳ "waiting for your
    # input" (replaces the 🟡 in-progress header). Skip when stage is empty (old-format state).
    if state.stage:
        try:
            upsert_stage_comment(
                deps.board_writer,
                state.issue_number,
                state.stage,
                header=HeaderInfo(
                    stage=state.stage,
                    status="waiting",
                    profile=state.profile,
                    mode=state.mode,
                    started=fmt_timestamp(state.started),
                    worktree=state.worktree,
                    log_hint=f"kanban logs {state.issue_number}",
                    # 31.2: tell the operator HOW to answer — a concrete tmux attach into the live
                    # session — not merely THAT the agent is waiting. Session name is ticket-<issue>.
                    attach_hint=f"tmux attach -t ticket-{state.issue_number}",
                ),
                now=now,
            )
        except Exception:
            logger.exception(
                "reaper ⏳ waiting sticky upsert failed for #%s stage=%r; continuing",
                state.issue_number,
                state.stage,
            )
        # FIX 5: mirror the ⏳ WAITING sticky in the body-top status header. Fully fail-soft.
        update_body_status(
            deps.seeder,
            state.issue_number,
            stage=state.stage,
            state="waiting",
            summary="waiting for your input",
            now=now,
        )


def _restore_running(deps: Deps, state: TicketState, now: float) -> None:
    """Restore a resumed WAITING ticket to RUNNING and re-flip the sticky to the 🟡 header (31.2).

    A WAITING ticket whose heartbeat just refreshed (the human answered → the agent resumed its tool
    calls) is restored to RUNNING. Before 31.2 the persisted status flipped back but the issue
    sticky kept its ⏳ "waiting for your input" header — a STALE signal telling the operator an agent
    is still blocked when it has resumed. This upserts the 🟡 "in progress" header so the sticky
    tracks the live state. Both writes are fail-soft (a store/GitHub error must never crash the
    sweep); the header upsert is skipped for old-format state with an empty ``stage`` (no sticky to
    flip). The header is rebuilt from the state's OWN metadata so it carries the original launch
    context, exactly as the launch/advance producers render it.

    Args:
        deps: The injected adapter bundle (the store + the board writer for the sticky).
        state: The resumed WAITING ticket's persisted state.
        now: The current wall-clock time (the sticky-upsert timestamp).
    """
    try:
        deps.store.save(replace(state, status=TicketStatus.RUNNING))
    except Exception:
        logger.exception(
            "reaper WAITING→RUNNING restore failed for #%s; continuing", state.issue_number
        )
    # Re-flip the stage sticky to the 🟡 "in progress" header so the resumed agent no longer reads
    # as ⏳ waiting (31.2). Skip when stage is empty (old-format state has no sticky to locate).
    if state.stage:
        try:
            upsert_stage_comment(
                deps.board_writer,
                state.issue_number,
                state.stage,
                header=header_from_state(
                    dataclasses.asdict(state),
                    state.issue_number,
                    state.stage,
                    "running",
                ),
                now=now,
            )
        except Exception:
            logger.exception(
                "reaper 🟡 running sticky restore failed for #%s stage=%r; continuing",
                state.issue_number,
                state.stage,
            )
        # FIX 5: re-flip the body-top status header back to "running" on a resumed WAITING ticket,
        # so the header tracks the live state (no stale "waiting" lingering). Fully fail-soft.
        update_body_status(
            deps.seeder,
            state.issue_number,
            stage=state.stage,
            state="running",
            summary="resumed",
            now=now,
        )


def reap_stale_agents(
    deps: Deps,
    config: TickConfig,
    executor: ThreadPoolExecutor,
    now: float,
    antiloop: AntiLoopState,
    *,
    kill_switch: bool = False,
    current_columns: dict[str, str] | None = None,
) -> tuple[int, int, int, AntiLoopState]:
    """Reap running agents whose tmux session has DIED; park live-but-silent agents WAITING (§8.3).

    **Approach A — the reaper never kills a LIVE session (operator decision 2026-06-15).** A running
    ticket is reaped (killed + parked) ONLY when its tmux session has DIED. A session that is still
    ALIVE is left running:

    * **alive + fresh heartbeat** → RUNNING (a working agent); a WAITING ticket whose heartbeat
      refreshed is restored to RUNNING (the human answered).
    * **alive + STALE heartbeat** (silent past ``config.heartbeat_ttl``) → parked WAITING + the
      operator signalled (⏳ sticky + tmux-attach hint), NEVER killed/relaunched. The agent is either
      blocked on a human (the free-text brainstorm Q&A shows no pane marker
      :func:`~kanbanmate.core.launch_keys.is_waiting_for_input` recognises) or hung — and killing a
      live session to "recover" it would destroy in-progress interactive work + unpushed changes (the
      helm #5 brainstorm-killed bug). A genuinely-hung live agent is the operator's call (attach, or
      ``kanban cancel``). The heartbeat TTL thus governs WHEN an alive agent flips to WAITING, not
      whether it is reaped.

    **Option 1 done-exit (#1) + firm-exit escalation — runs AHEAD of the WAITING parking.** Before the
    Approach-A handling, for an ALIVE session that has signalled DONE (the agent ran ``kanban-done`` →
    a persisted ``done/<issue>`` breadcrumb, :meth:`~kanbanmate.ports.store.StateStore.recent_agent_done`)
    AND whose pane is IDLE (no ``esc to interrupt`` active turn — :func:`_pane_has_active_turn`), the
    reaper drives the BOUNDED-RETRY-THEN-KILL escalation in :func:`_end_done_session`: it dispatches the
    ROBUST :meth:`~kanbanmate.ports.workspace.Sessions.end_session` (Escape→C-u→C-d→C-d→Enter, NOT ``kill``)
    so ``claude`` exits and the trailing ``; kanban-session-end <issue>`` runs the teardown → the card
    flows, KEEPING the done breadcrumb + bumping a persisted ``end_attempts/<issue>`` counter so the
    next tick re-dispatches until the REPL exits or :data:`MAX_END_ATTEMPTS` is hit — then it SIGKILLs
    the ``claude`` child (:meth:`~kanbanmate.ports.workspace.Sessions.kill_repl_process`, NOT the
    session/shell) and clears both markers. This replaces the earlier SINGLE-SHOT dispatch (which
    no-op'd on the helm #5 leftover-box + background-shell condition and parked the finished agent
    WAITING forever). It applies to BOTH fresh+alive and stale+alive done agents (a quick-finish is
    fresh; a long agent that finishes after going silent is stale). Approach A is UNCHANGED for every
    other case: a NOT-done alive session, or a done-but-WORKING session (the active-turn probe FAILS
    CLOSED to "active" on any error, so an undecidable pane is never exited), falls through to the
    WAITING / fresh handling and is never exited or killed; a DEAD session is reaped below. A NOT-done
    alive session also has any LINGERING ``end_attempts`` counter reset (:func:`_reset_stale_end_attempts`,
    §3.4) so a future done cycle on the same ticket starts clean.

    Only a DEAD session (the ``is_alive`` probe DEFINITIVELY reports it gone) is reaped — immediately,
    regardless of heartbeat freshness (#26: a crashed agent is not left for the full TTL). The probe
    is fail-OPEN (:func:`_session_alive` reports "alive" on any probe error) so an uncertain liveness
    state parks WAITING rather than killing. For each reaped (dead) ticket the stall reason is
    surfaced ONCE as a :class:`~kanbanmate.app.actions.BlockAction` sticky comment, then the reaper
    decides RETRY vs BLOCK (port of the PoC ``reaper.apply`` block-with-retry branch, reaper.py:106-184):

    * **RETRY** (``state.retries < RETRY_LIMIT`` AND ``state.stage != ""``): the dead session is
      relaunched ONCE via :func:`_try_relaunch` (bump retries + REFRESH heartbeat + relaunch the same
      stage; the kill is a no-op for an already-dead session). The bumped ``retries`` now rides onto
      the rebuilt LaunchAction (:attr:`~kanbanmate.app.actions.LaunchAction.retries`) so the budget
      SURVIVES the LaunchAction's fresh state write — without that the next reap would see
      ``retries == 0`` again and relaunch forever (the budget-reset bug). A successful retry is
      counted as ``relaunched`` (NOT ``reaped`` — the ticket keeps running); a relaunch that
      RAISES/times out falls through to BLOCK (one bad retry must not starve the sweep — port
      reaper.py:173-182).
    * **BLOCK** (``state.retries >= RETRY_LIMIT``, OR ``state.stage == ""`` fail-soft, OR a relaunch
      raised): the inline park-in-Blocked sequence (teardown + move-to-Blocked + ⛔ flip) mirroring
      the PoC ``reaper._move_to_blocked``. Increments ``reaped``.

    Args:
        deps: The injected adapter bundle.
        config: The per-tick policy inputs (TTL + watchdog budget + Blocked column).
        executor: The shared thread pool for the watchdog.
        now: The current wall-clock time.
        antiloop: The anti-loop state carried in from the persisted baseline.
        kill_switch: When ``True`` (``~/.kanban/PAUSE`` active, defect 6) the RETRY branch is
            SUPPRESSED — no relaunch is dispatched. A stale agent falls straight through to the
            non-destructive BLOCK park (kill + purge + move Blocked), so PAUSE genuinely stops every
            launch while leaving the reap BOOKKEEPING (the visible Blocked signal) intact.
        current_columns: The tick's live diff baseline (``item_id`` → current column key). Used to
            guard against a WRONG-STAGE relaunch: a dead-session state whose ``stage`` no longer
            matches the card's current column is PURGED (the card advanced past it) rather than
            relaunched onto the wrong stage. ``None`` (or a missing item entry) → the column is
            unknown, so the normal reap proceeds (no false purge).

    Returns:
        A ``(reaped, relaunched, errors, antiloop)`` quad: how many agents were parked in Blocked,
        how many were relaunched once (the reaper retry), how many reap actions failed (timed out
        or raised), and the anti-loop state with this tick's reap moves recorded.
    """
    # LAZY import to dodge the circular import (tick imports this module). The watchdog stays in
    # ``tick`` (the drain + the main loop also use it; a test monkeypatches ``tick._run_with_watchdog``).
    from kanbanmate.app.tick import _run_with_watchdog

    reaped = 0
    relaunched = 0
    errors = 0
    for state in deps.store.list_running():
        # #26 PORT (reaper.py PoC sweep:49-57) — TWO reap triggers, not one: a running ticket is
        # reaped when its heartbeat is STALE *or* its tmux session has DIED. A crashed agent whose
        # LAST heartbeat is recent (< TTL) but whose session is gone would otherwise wait up to the
        # full TTL (default 1800s) before the reaper noticed — the PoC reaped it immediately. So we
        # SKIP a running ticket only when it is BOTH fresh AND alive.
        fresh = (now - state.heartbeat) <= config.heartbeat_ttl
        alive = _session_alive(deps, state.issue_number)

        # Option 1 (#1): a DONE + IDLE alive session is cleanly EXITED so its trailing
        # ``; kanban-session-end`` fires (teardown → the card flows). This runs BEFORE the
        # Approach-A WAITING parking below (it applies to BOTH fresh+alive and stale+alive done
        # agents — a quick-finish is fresh+alive+done; a long agent that finishes after going silent
        # is stale+alive+done). Approach A is preserved EXACTLY: an alive session is exited ONLY when
        # it has signalled done AND its pane is IDLE (no ``esc to interrupt`` active turn). A not-done
        # alive session, or a done-but-WORKING session, falls through to the unchanged WAITING /
        # fresh handling and is NEVER exited. A dead session is handled by the reap path below.
        done = alive and deps.store.recent_agent_done(state.issue_number, now=now)
        if done:
            if not _pane_has_active_turn(deps, state.issue_number):
                # BOUNDED-RETRY THEN KILL-ESCALATION (firm-exit) — see :func:`_end_done_session`: it
                # dispatches the robust end_session and bumps a persisted attempt counter, KEEPING the
                # done breadcrumb so the next tick re-dispatches, until either the REPL exits or
                # MAX_END_ATTEMPTS is reached → it SIGKILLs the claude child (NOT the session) and
                # clears the breadcrumb + counter. Approach A intact: only ever a done + idle + alive
                # session reaches here.
                _end_done_session(deps, state, now)
                continue
            # Done but a turn is still running → do NOT interrupt it; fall through to the normal
            # fresh/stale handling (it will be re-evaluated next tick once the turn ends).
        else:
            # §3.4 defensive reset: this ticket is NOT in the done-exit cycle (no recent done
            # breadcrumb — never reached done, or the breadcrumb aged out / was cleared). A stale
            # attempt counter could linger across a daemon restart mid-escalation; drop it (fail-soft)
            # so a LATER done cycle on the same ticket starts its budget clean. Cheap: a read + a
            # conditional unlink, only when a counter is actually present.
            _reset_stale_end_attempts(deps, state.issue_number)

        # Phase-27 §B — WAITING / RESUME / WAITING-death handling, BEFORE the reap gate:
        if fresh and alive:
            # Fresh + alive: a working agent, leave it be. EXCEPTION: a ticket parked WAITING whose
            # heartbeat just REFRESHED means the human answered and the agent RESUMED its tool calls
            # → restore it to RUNNING so the dashboard/finalizers see a normal running agent again.
            if state.status is TicketStatus.WAITING:
                _restore_running(deps, state, now)
                continue
            # 31.2 early WAITING detection: a RUNNING agent that has been SILENT past the (short)
            # waiting-probe TTL — but is still fresh against the (long) reap TTL — may have hit a
            # human prompt the moment it stopped touching its heartbeat. Probe the pane NOW so a
            # blocked-on-human agent is signalled within minutes instead of after the full reap TTL.
            # Detection-only: a non-waiting silent agent just falls through to ``continue`` (left
            # untouched until the real reap TTL — this never reaps or changes the reap timing).
            silent_for = now - state.heartbeat
            if silent_for >= config.waiting_probe_ttl and _pane_shows_waiting(
                deps, state.issue_number
            ):
                _enter_waiting(deps, state, now)
            continue
        if alive:
            # Approach A (operator decision 2026-06-15): the reaper NEVER KILLS a live session.
            # A STALE-heartbeat but STILL-ALIVE agent is silent for one of two reasons — it is blocked
            # on a human (an interactive prompt, e.g. the free-text brainstorm Q&A) or it is hung —
            # and the pane cannot reliably tell them apart (a free-text prompt shows no marker that
            # :func:`~kanbanmate.core.launch_keys.is_waiting_for_input` recognises). Killing a live
            # session to "recover" it destroys the operator's in-progress INTERACTIVE work AND any
            # unpushed worktree changes — the worst outcome (the live helm #5 brainstorm-killed bug).
            # So an ALIVE session is ALWAYS parked WAITING + the operator signalled (⏳ sticky +
            # tmux-attach hint); it is never killed, torn down, relaunched, or moved. The destructive
            # kill+relaunch path below is reserved for DEAD sessions only (a crashed agent whose tmux
            # session is gone). A genuinely-hung LIVE agent is the operator's call: attach and answer,
            # or Ctrl-C / ``kanban cancel``.
            _enter_waiting(deps, state, now)
            continue
        # The session is DEAD (``not alive``). BEFORE relaunching it, guard against a WRONG-STAGE
        # relaunch: if the card has ALREADY ADVANCED past this agent's stage (its current board column
        # no longer equals ``state.stage``), the running-state is STALE — relaunching it would re-run
        # the OLD stage's prompt on a moved card (live helm #5: a Brainstorming state relaunched onto a
        # Spec card, re-delivering the brainstorm prompt). PURGE the stale state instead of
        # relaunching, and surface a one-line signal so the operator / `kanban-monitor` re-fires the
        # CORRECT stage. ``current_columns`` is the tick's live diff baseline (item_id → column); when
        # it is absent (first tick post-restart, empty baseline) or has no entry for this item, the
        # stage is UNKNOWN and we fall through to the normal reap (no false purge on missing data).
        if current_columns is not None:
            current_col = current_columns.get(state.item_id)
            if current_col is not None and state.stage and current_col != state.stage:
                logger.warning(
                    "reaper: #%s running-state stage=%r no longer matches card column=%r (card "
                    "advanced past this stage) — PURGING the stale state instead of relaunching the "
                    "wrong stage; re-fire the %r stage to resume",
                    state.issue_number,
                    state.stage,
                    current_col,
                    current_col,
                )
                try:
                    deps.board_writer.comment(
                        state.issue_number,
                        f"KanbanMate: cleared a stale `{state.stage}` agent state — the card has "
                        f"moved to `{current_col}`. Re-fire the `{current_col}` stage to resume "
                        f"(`/kanban-monitor --remediate`).",
                    )
                except Exception:
                    logger.exception(
                        "reaper stale-stage signal comment failed for #%s; continuing",
                        state.issue_number,
                    )
                try:
                    deps.store.purge_ticket(state.issue_number, keep_budgets=True)
                except Exception:
                    logger.exception(
                        "reaper stale-stage purge failed for #%s; continuing", state.issue_number
                    )
                continue
        # Reap as usual (this also covers a ticket parked WAITING whose session later died: it falls
        # straight through to the reap/relaunch path).
        # Minimal Ticket from persisted state (the reap actions only need issue + item id).
        ticket = Ticket(
            item_id=state.item_id,
            issue_number=state.issue_number,
            title=f"ticket-{state.issue_number}",
            column_key="",
        )
        # Surface the stall reason ONCE; both branches want the operator to see WHY the reaper
        # acted. The BLOCK branch reuses ``ok_block`` toward its reap tally, so a relaunch that
        # later falls through does NOT double-post the comment (port the PoC comment-first ordering).
        # Under Approach A the reap path is reached ONLY for a DEAD session (an alive session — even
        # one whose heartbeat aged past the TTL — is parked WAITING above and never reaches here), so
        # the trigger is always a crashed/gone tmux session.
        reap_reason = "dead agent session (reaped)"
        block = BlockAction(ticket=ticket, reason=reap_reason)
        ok_block = _run_with_watchdog(executor, block, deps, config.action_timeout)

        # RETRY branch (port reaper.py:156-182), gated on the per-ticket budget AND a recorded stage
        # (an empty stage cannot re-enter a column — fail-soft straight to BLOCK below). Under PAUSE
        # (kill_switch, defect 6) the relaunch is SUPPRESSED entirely so no agent launches while the
        # operator has the kill-switch on — the ticket parks in Blocked (reap bookkeeping) and a
        # later resume re-drives it. DESIGN §10 / CLAUDE.md "PAUSE stops launches".
        if not kill_switch and state.retries < RETRY_LIMIT and state.stage:
            if _try_relaunch(deps, config, executor, state, now):
                relaunched += 1
                continue
            errors += 1  # relaunch raised/timed out → fall through to BLOCK (no re-posted comment)

        # BLOCK branch (port reaper._move_to_blocked): teardown + park-in-Blocked + ⛔ flip. The
        # stall comment was already posted above (``ok_block``), so this never re-posts it.
        # keep_budgets=True (13.8): the parked ticket may continue, so its per-issue budgets
        # (``moves/`` + ``retries/``) SURVIVE the teardown — that is WHY the durable §6 counter
        # ACCUMULATES across reaps. Only Cancel / reset (default False) drops them.

        # Coherent terminal state BEFORE the teardown purge (port reaper._move_to_blocked
        # ordering, reaper.py:87-88): write a non-RUNNING status FIRST so a fail-soft
        # purge_ticket failure cannot leave a refreshed-heartbeat RUNNING zombie that the
        # next sweep skips as "fresh". IDLE = "no agent running" (the board's Blocked column
        # is the source of truth for the block itself). The happy path deletes this record in
        # the teardown step below; this write only matters if that purge fails.
        try:
            deps.store.save(replace(state, status=TicketStatus.IDLE))
        except Exception:
            logger.exception(
                "reaper terminal-state write failed for #%s; continuing", state.issue_number
            )

        # Defect 5: the reaper park-in-Blocked is NON-DESTRUCTIVE (PoC ``reaper._move_to_blocked``
        # parity) — kill the session + purge state ONLY. The ``reap`` flavour SKIPS worktree removal,
        # branch delete, and PR close, so a twice-stalled InProgress/PRCI/Review agent keeps its
        # unpushed work, its local branch, and its open PR. ``keep_budgets=True`` (13.8) keeps the
        # parked ticket's rate-limit/retry budgets so it may continue.
        teardown = TeardownAction(ticket=ticket, keep_budgets=True, flavour="reap")
        ok_teardown = _run_with_watchdog(executor, teardown, deps, config.action_timeout)
        # #22 NOTE — the reaper teardown deliberately does NOT ``forget`` the in-memory rate-limit
        # history (plan-drift from the 17.4 spec's "forget on the reaper teardown too"). The reaper
        # parks the card in Blocked with ``keep_budgets=True`` (13.8): the ticket MAY CONTINUE, so
        # both the DURABLE on-disk §6 counter (``moves/<issue>.json``) AND the volatile in-memory
        # anti-loop accumulator MUST survive the teardown so the runaway-loop backstop can observe
        # repeated reap moves across ticks (DESIGN §6; asserted by
        # ``test_antiloop_state_threads_across_two_ticks``). This matches the PoC, whose reaper
        # ``_move_to_blocked`` used the slot-only ``release_slot`` and never zeroed ``moves/`` — only
        # the deliberate Cancel/reset ``purge_ticket`` did. ``forget`` therefore fires ONLY on the
        # ABANDONMENT path (the Cancel ``TeardownAction`` in :func:`kanbanmate.app.tick.tick`), not
        # here. The reaper's OWN park move IS recorded below (a genuine AUTO move feeds the counter).
        # Park the card in the Blocked column so the stall is visible on the board (DESIGN §8.3),
        # under its own watchdog so a hung GitHub call cannot freeze the sweep.
        ok_move = _run_with_watchdog(
            executor,
            _ReapMove(item_id=state.item_id, column=config.blocked_column),
            deps,
            config.action_timeout,
        )
        if ok_move:
            # Record the daemon's own move so the anti-loop guard recognises it on a later tick
            # (defense-in-depth backstop, DESIGN §6). Only record a move that actually landed.
            antiloop = record_move(antiloop, state.item_id, config.blocked_column, now=now)
            # Candidate 1 (rate-limit conflation fix): the reaper park-in-Blocked is a TERMINAL
            # bookkeeping move (baseline→Blocked, never re-fired) — it MUST NOT consume the per-issue
            # FORWARD-ADVANCE budget (``moves/<issue>.json``) that the fix-CI / rework auto-advance
            # loops + the session-end advance:auto backstop gate on. Previously this branch fed
            # ``record_move_for_item`` here, so a busy ticket's genuine forward moves + the reaper's
            # bookkeeping parks shared one cap → a busy ticket could hit the cap and get parked
            # mid-flow needing manual intervention. The anti-loop ``record_move`` above (the runaway
            # backstop's feeder) is RETAINED; only the forward-budget feeder is removed here. The
            # script-route cap-park (``_park_runaway``) was already correct (it never fed
            # ``record_move_for_item``), so this aligns the reaper with it.
        # ⛔ Flip the stage sticky to "blocked" (DESIGN §8.1.c) from the stale state's OWN metadata,
        # so it carries the original launch context. Skip when stage is empty (old-format state).
        # The try/except is defense-in-depth: a GitHub error must never affect the reap tally.
        if state.stage:
            try:
                upsert_stage_comment(
                    deps.board_writer,
                    state.issue_number,
                    state.stage,
                    header=header_from_state(
                        dataclasses.asdict(state),
                        state.issue_number,
                        state.stage,
                        "blocked",
                        finished=fmt_timestamp(now),
                    ),
                    now=now,
                )
            except Exception:
                logger.exception(
                    "reaper ⛔ sticky flip failed for #%s stage=%r; continuing",
                    state.issue_number,
                    state.stage,
                )
            # FIX 5: mirror the ⛔ blocked sticky in the body-top status header. Fully fail-soft.
            update_body_status(
                deps.seeder,
                state.issue_number,
                stage=state.stage,
                state="blocked",
                summary="agent stalled — parked in Blocked",
                now=now,
            )
        if ok_block and ok_teardown and ok_move:
            reaped += 1
        else:
            errors += 1
    return reaped, relaunched, errors, antiloop


def _try_relaunch(
    deps: Deps,
    config: TickConfig,
    executor: ThreadPoolExecutor,
    state: TicketState,
    now: float,
) -> bool:
    """Kill the dead session, bump retries + REFRESH the heartbeat, and relaunch the SAME stage.

    Port of the PoC ``reaper.apply`` retry branch (reaper.py:156-182). The order mirrors the PoC:
    kill the dead tmux session, persist ``retries+1`` / ``status=running`` / ``heartbeat=now`` (the
    heartbeat REFRESH is LOAD-BEARING, DESIGN §8.3 — without it the very next sweep re-blocks the
    freshly-retried ticket), then dispatch a fresh :class:`~kanbanmate.app.actions.LaunchAction` for
    the SAME stage under the per-action watchdog so a hung relaunch cannot freeze the sweep. The
    relaunch RE-USES the dead session's IDEMPOTENT slot — it never reserves a new one (port
    reaper.py:167-172; the reaper teardown only runs on the BLOCK path).

    Args:
        deps: The injected adapter bundle (the live store + sessions + launch adapters).
        config: The per-tick policy inputs (the watchdog budget).
        executor: The shared thread pool backing the per-action watchdog.
        state: The stale ticket's persisted state (``retries`` / ``stage`` / coordinates).
        now: The current wall-clock time (the refreshed heartbeat stamp).

    Returns:
        ``True`` iff the relaunch dispatched cleanly (a successful retry); ``False`` on timeout or
        exception — the caller then FALLS THROUGH to the BLOCK branch.
    """
    # LAZY import to dodge the circular import (tick imports this module).
    from kanbanmate.app.tick import _run_with_watchdog

    session_name = f"ticket-{state.issue_number}"
    # Kill the dead tmux session if alive (mirror the PoC ``has_session`` → ``kill`` guard,
    # reaper.py:158-159). Fail-soft: a kill failure must not abort the retry.
    try:
        if deps.sessions.is_alive(session_name):
            deps.sessions.kill(session_name)
    except Exception:
        logger.exception(
            "reaper relaunch kill_session failed for #%s; continuing", state.issue_number
        )
    # Fresh-session breadcrumb hygiene (#FIX2, same as LaunchAction): the relaunch is a FRESH
    # session for the SAME stage, so a stale done/end_attempts marker from the prior (dead) session
    # must not done-exit it on the next tick. Clear both; fail-soft (a clear failure never aborts
    # the retry — the markers age out at their TTL regardless). NOTE: _try_relaunch does NOT call
    # purge_ticket (it reuses the slot), so these clears are the ONLY thing that resets the
    # breadcrumb on the relaunch path — exactly the gap they close.
    try:
        deps.store.clear_agent_done(state.issue_number)
    except Exception:
        logger.exception(
            "relaunch breadcrumb-clear (done) failed for #%s; continuing", state.issue_number
        )
    try:
        deps.store.clear_end_attempts(state.issue_number)
    except Exception:
        logger.exception(
            "relaunch breadcrumb-clear (end_attempts) failed for #%s; continuing",
            state.issue_number,
        )
    # Persist retries+1 / running / refreshed heartbeat BEFORE dispatching (port reaper.py:160-166):
    # even a relaunch the watchdog abandons leaves a bumped-retries record, so the NEXT sweep does
    # not retry again (the budget holds).
    deps.store.save(
        replace(state, retries=state.retries + 1, status=TicketStatus.RUNNING, heartbeat=now)
    )
    # Fresh LaunchAction for the SAME stage (re-enters the correct column), reusing the EXISTING
    # launch seam under the watchdog (no second launch path); a hung relaunch returns False.
    # Phase 20 (DESIGN §8.0.6): the agent launches AT the transition, so the profile lives on the
    # transition — but a reaper relaunch is an internal age-out RETRY, not a board move, so it has
    # no transition to read. It REBUILDS the LaunchAction from the PERSISTED RELAUNCH INPUTS
    # (phase-25 §25.2; PoC ``launch.py`` "Re-launch inputs persisted"): ``state.prompt`` /
    # ``state.script`` / ``state.mode`` (the permission_mode) / ``state.on_fail`` / ``state.advance``
    # / ``state.profile`` are all the fields the original launch persisted, so the relaunch RE-DELIVERS
    # the SAME prompt via the 25.1 send-keys path (NOT a promptless idle agent). An empty persisted
    # profile fails loud (§10). When the persisted ``advance`` is empty (old-format state predating
    # 25.2) fall back to the LaunchAction default so the rebuild stays well-formed.
    relaunch = LaunchAction(
        ticket=Ticket(
            item_id=state.item_id,
            issue_number=state.issue_number,
            # Rebuild from the PERSISTED title/body (defect 4), NOT a synthetic ``ticket-N`` /
            # empty body: an empty body makes parse_ticket_fields yield empty
            # codename/design_path/plan_paths, and the Plan/Prepare prompts hard-instruct "if
            # empty → DESYNC, END the session" — so a relaunched agent would self-DESYNC and burn
            # its one retry. The fallback ``ticket-N`` title preserves old-format states that
            # predate the persisted-title field.
            title=state.title or f"ticket-{state.issue_number}",
            column_key=state.stage,
            body=state.body,
        ),
        prompt=state.prompt,
        script=state.script,
        permission_mode=state.mode or "auto",
        on_fail=state.on_fail,
        advance=state.advance or "stop",
        profile=state.profile,
        # Carry the BUMPED retry budget onto the LaunchAction so its fresh state write persists
        # ``retries + 1`` — matching the pre-save above. Without this the LaunchAction defaults
        # ``retries`` to 0, resetting the budget and defeating RETRY_LIMIT (an infinite relaunch loop
        # — the live helm #5 bug: every reap saw retries == 0 and relaunched again).
        retries=state.retries + 1,
    )
    return _run_with_watchdog(executor, relaunch, deps, config.action_timeout)
