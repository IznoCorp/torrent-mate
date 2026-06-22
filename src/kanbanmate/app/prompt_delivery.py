"""Prompt-delivery observability helpers for :class:`~kanbanmate.app.actions.LaunchAction` (#11).

Extracted from :mod:`kanbanmate.app.actions` (the module hit the 1000-LOC hard ceiling when the #11
post-send verification landed). These are the I/O-loop + observability halves of the phase-25 §25.1
send-keys delivery:

* :func:`poll_pane` — the bounded ``capture-pane`` poll for the trust dialog / ready REPL, now with a
  loud timeout log (the pure per-snapshot verdict stays in :mod:`kanbanmate.core.launch_keys`).
* :func:`verify_prompt_delivered` — the WARN-ONLY post-send check that surfaces an undelivered prompt
  (claude UI drift / a send-keys miss) without ever hard-failing a good launch (rank-11 verdict).
* :func:`pane_tail` — a small diagnostic helper returning the trailing pane lines.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2). ``Deps`` lives in
:mod:`kanbanmate.app.actions` which imports this module, so it is referenced only under
``TYPE_CHECKING`` to avoid a runtime import cycle.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.core.launch_keys import (
    TRUST_POLL_ATTEMPTS,
    TRUST_POLL_INTERVAL,
    classify_pane,
    is_waiting_for_input,
    prompt_pending,
    turn_running,
)

if TYPE_CHECKING:
    from kanbanmate.app.actions import Deps

logger = logging.getLogger(__name__)

# How many times the submit-retry loop re-sends Enter when the prompt is still sitting in the input
# box (#submit-reliability). On claude v2.1.x the REPL shows a ready prompt a beat before it accepts
# input, so the FIRST submit Enter can be absorbed; re-sending Enter once claude is truly ready lands
# the submit. 8 (raised from 4) gives a LARGE multi-chunk prompt — the Spec/design prompt that embeds
# the ticket body — enough cycles to settle and accept the Enter (4×0.6s≈2.4s was too short and left
# helm #5 stuck). Bounded so a genuinely undeliverable prompt still terminates (→ the WARN below).
SUBMIT_RETRY_ATTEMPTS = 8

# Seconds between submit-retry capture+resend cycles. Long enough for claude to render the post-submit
# state (so a landed submit is seen and NOT re-Entered), short enough to keep launch latency low.
SUBMIT_RETRY_INTERVAL = 0.6

# How many times the loop RE-PASTES the whole prompt when the input box is EMPTY with no running turn
# — the EATEN-paste case (claude v2.1.175's intro/welcome screen swallows the launch paste). Distinct
# from the Enter-resend path (which only helps when the prompt is still sitting in the box): an eaten
# paste leaves nothing to submit, so re-sending Enter is futile and the agent sits idle forever (the
# live #27 Review stall). Bounded so a genuinely undeliverable prompt still terminates (→ the WARN).
REDELIVER_ATTEMPTS = 2

# How many trailing lines of a captured tmux pane to surface in a diagnostic log (#11). Enough to
# show the REPL's current state without flooding the structured log with the full scrollback.
_PANE_TAIL_LINES = 12

# The minimum probe length (#11). A whole prompt line at least this long still sitting verbatim in
# the pane is unambiguous "the keystrokes did not land"; a shorter token could legitimately echo, so
# requiring a substantial slice avoids false-positive warnings.
_MIN_PROBE_LEN = 40


def pane_tail(capture: str) -> str:
    """Return the last :data:`_PANE_TAIL_LINES` lines of a captured pane for a diagnostic (#11).

    Args:
        capture: The raw ``capture-pane`` snapshot (may be empty).

    Returns:
        The trailing lines joined by newlines, or a placeholder when the capture is empty.
    """
    if not capture.strip():
        return "(empty pane capture)"
    return "\n".join(capture.splitlines()[-_PANE_TAIL_LINES:])


def poll_pane(deps: Deps, session_name: str) -> bool:
    """Poll ``capture-pane`` until the trust dialog OR a ready REPL appears; return trust_seen (#11).

    Ported from the PoC ``poll_trust_dialog`` (launch.py:145-168) — the I/O LOOP half (the pure
    per-snapshot verdict lives in :func:`~kanbanmate.core.launch_keys.classify_pane`). Returns
    ``True`` as soon as the trust marker is seen (the caller sends the dismiss Enter first), ``False``
    once a stable REPL prompt is observed (already trusted → skip the Enter), and falls back to
    ``False`` after :data:`~kanbanmate.core.launch_keys.TRUST_POLL_ATTEMPTS` captures (timeout) so the
    launch still proceeds. ``deps.sleeper`` (default :func:`time.sleep`) is injected so offline tests
    drive the loop without real waiting.

    On TIMEOUT (#11) it logs a warning with the captured pane TAIL — previously a silent
    ``return False`` against claude UI drift — so an operator can see what the REPL actually showed.

    Args:
        deps: The adapter bundle (the sessions ``capture`` seam + the injected sleeper).
        session_name: The tmux session name to snapshot (``ticket-<n>``).

    Returns:
        ``True`` iff the trust dialog was observed (the caller sends a dismiss Enter first).
    """
    last_capture = ""
    for i in range(TRUST_POLL_ATTEMPTS):
        last_capture = deps.sessions.capture(session_name)
        verdict = classify_pane(last_capture)
        if verdict == "trust":
            return True
        if verdict == "ready":
            return False
        # Wait before the next capture, but not after the LAST attempt (no point sleeping just to
        # time out). Real ``claude`` needs seconds to render — a single capture misses it.
        if i < TRUST_POLL_ATTEMPTS - 1:
            deps.sleeper(TRUST_POLL_INTERVAL)
    # TIMEOUT: neither the trust dialog nor a ready REPL was seen within the budget (#11). Log the
    # captured pane tail so the previously-silent marker-heuristic timeout is observable; the launch
    # still proceeds (the send-keys is attempted anyway) — this is observability, not a gate.
    logger.warning(
        "launch poll for session %s timed out after %d attempts (no trust dialog / ready REPL "
        "seen); proceeding with send-keys. Pane tail:\n%s",
        session_name,
        TRUST_POLL_ATTEMPTS,
        pane_tail(last_capture),
    )
    return False


def verify_prompt_delivered(
    deps: Deps, issue: int, session_name: str, filled: str, column_key: str
) -> None:
    """WARN (never kill) when the prompt is visibly sitting UNTYPED after the send (#11).

    Captures the pane once and checks whether a distinctive slice of the filled prompt is still
    present verbatim — the unambiguous "the keystrokes did not land" signal. On that evidence it logs
    a warning and upserts a ⚠️ sticky note so the operator notices; it does NOT raise or otherwise
    fail the launch (a false negative from a redraw must never kill a good launch — rank-11 verdict).
    Fully fail-soft: any error here is swallowed.

    Args:
        deps: The adapter bundle (the sessions ``capture`` seam + the board writer).
        issue: The ticket issue number (for the sticky note).
        session_name: The tmux session to re-capture.
        filled: The filled prompt that was just sent.
        column_key: The ticket's column key (the stage sticky to annotate).
    """
    try:
        pane = deps.sessions.capture(session_name)
    except Exception:  # noqa: BLE001 — verification is best-effort; never break the launch
        logger.warning(
            "post-send pane capture failed for #%s session %s; skipping delivery check",
            issue,
            session_name,
        )
        return
    # A whole prompt line still present verbatim is unambiguous evidence the keystrokes did not land;
    # require a substantial slice (``_MIN_PROBE_LEN``) so a short echoed token is not a false positive.
    first_line = next((ln for ln in filled.splitlines() if ln.strip()), "")
    probe = first_line.strip()[:80]
    if len(probe) >= _MIN_PROBE_LEN and probe in pane:
        logger.warning(
            "prompt for #%s appears UNDELIVERED — its text is still sitting in the pane after the "
            "submit (claude UI drift / send-keys miss?). Pane tail:\n%s",
            issue,
            pane_tail(pane),
        )
        # Drop a ⚠️ sticky note so the operator sees it on the ticket (best-effort).
        try:
            upsert_stage_comment(
                deps.board_writer,
                issue,
                column_key,
                append="prompt may not have been delivered to the agent (send-keys verification "
                "flagged it sitting untyped) — check the tmux session",
            )
        except Exception:  # noqa: BLE001 — the sticky is advisory; never break the launch
            logger.warning("post-send warning sticky failed for #%s; continuing", issue)


def submit_prompt_with_retries(
    deps: Deps, issue: int, session_name: str, filled: str, column_key: str
) -> bool:
    """Confirm a turn actually started — re-sending Enter OR re-delivering an eaten paste.

    Two distinct delivery failures both leave an AUTONOMOUS stage (Spec / Plan / dev) with no human to
    rescue it, so the agent never starts and — post-Approach-A — parks ``WAITING`` forever:

    * **Absorbed Enter** — the REPL renders a ready prompt (``❯`` / ``auto mode on``) a beat before it
      accepts input, so the submit Enter lands while the input loop is not yet listening and the filled
      prompt is left sitting in the input box (a collapsed ``[Pasted text …]`` for a multi-line prompt).
      While the prompt is still :func:`~kanbanmate.core.launch_keys.prompt_pending`, re-send Enter.
    * **Eaten paste** — claude v2.1.175's intro/welcome screen swallows the literal paste itself, so the
      input box ends up EMPTY (the live #27 Review stall). The old ``not prompt_pending`` success check
      read that empty box as "submitted" and gave up; re-sending Enter is futile (nothing to submit).
      When NEITHER a running turn NOR a pending prompt is seen, the whole prompt is RE-DELIVERED (paste
      + autocomplete-closing space + Enter), bounded by :data:`REDELIVER_ATTEMPTS`.

    Success is now the STRICT :func:`~kanbanmate.core.launch_keys.turn_running` signal (a turn in
    flight), NOT merely "the box emptied" — that is what lets the loop tell a real submit from an eaten
    paste. The whole loop is bounded by :data:`SUBMIT_RETRY_ATTEMPTS`; an Enter / re-paste at an already
    empty or already-submitted box is a harmless no-op, so an over-eager resend never corrupts a turn.

    Fully fail-soft: a capture/send error ends the loop quietly (the launch already happened). On
    exhaustion (no running turn confirmed) it WARNs + drops an advisory sticky — via
    :func:`verify_prompt_delivered` for a still-VISIBLE stuck prompt, or an explicit empty-box /
    no-turn warning for an eaten paste — so an operator always sees a genuinely undelivered prompt.

    Args:
        deps: The adapter bundle (the sessions ``capture`` / ``send_text`` seams + the injected
            sleeper).
        issue: The ticket issue number (for the fallback warning sticky).
        session_name: The tmux session to poll + re-submit into (``ticket-<n>``).
        filled: The filled prompt that was sent (its probe slice detects the pending state).
        column_key: The ticket's column key (the stage sticky the fallback annotates).

    Returns:
        ``True`` iff the prompt was confirmed submitted within the retry budget; ``False`` on
        exhaustion or a fail-soft early exit (the fallback warning has been emitted on exhaustion).
    """
    redeliveries = 0
    for _attempt in range(SUBMIT_RETRY_ATTEMPTS):
        # Give claude a beat to render the post-submit state BEFORE judging, so a submit that DID
        # land is seen as submitted and not needlessly re-Entered.
        deps.sleeper(SUBMIT_RETRY_INTERVAL)
        try:
            pane = deps.sessions.capture(session_name)
        except Exception:  # noqa: BLE001 — best-effort; a capture blip must not break the launch
            logger.warning(
                "submit-retry pane capture failed for #%s session %s; stopping retries",
                issue,
                session_name,
            )
            return False
        # STRICT success: a turn is actually in flight. Unlike the old ``not prompt_pending`` check,
        # this does NOT treat an EMPTY input box as success — an empty box is BOTH a real submit AND an
        # eaten paste, and conflating them is exactly the silent-stall bug (live #27).
        if turn_running(pane):
            return True
        if prompt_pending(pane, filled):
            # The prompt is still sitting in the input box → the submit Enter was absorbed; re-send it.
            try:
                deps.sessions.send_text(session_name, "Enter", literal=False)
            except Exception:  # noqa: BLE001 — best-effort; a send blip must not break the launch
                logger.warning(
                    "submit-retry Enter resend failed for #%s session %s; stopping retries",
                    issue,
                    session_name,
                )
                return False
            continue
        if is_waiting_for_input(pane):
            # The submit landed and the agent immediately hit a permission/menu prompt — it is ENGAGED,
            # not eaten. Re-pasting the whole prompt INTO that menu would corrupt it, so treat this as
            # delivered (the reaper owns the WAITING state from here).
            return True
        # NEITHER a running turn NOR the prompt in the box → the input box is EMPTY: the paste was
        # EATEN (claude v2.1.175's intro/welcome screen swallowed it). Re-sending Enter is futile —
        # RE-DELIVER the whole prompt (paste + the autocomplete-closing space + Enter), bounded, so
        # the agent actually starts instead of sitting idle forever.
        if redeliveries < REDELIVER_ATTEMPTS:
            redeliveries += 1
            try:
                deps.sessions.send_text(session_name, filled, literal=True, enter=False)
                deps.sessions.send_text(session_name, " ", literal=True, enter=False)
                deps.sessions.send_text(session_name, "Enter", literal=False)
            except Exception:  # noqa: BLE001 — best-effort; a send blip must not break the launch
                logger.warning(
                    "submit-retry prompt re-delivery failed for #%s session %s; stopping retries",
                    issue,
                    session_name,
                )
                return False
    # Budget spent without a confirmed running turn → surface it so a bad launch is NEVER silently
    # dropped. The two failure shapes need different messages: a still-VISIBLE prompt is the
    # "sitting untyped" case (:func:`verify_prompt_delivered`), while an EATEN paste — an EMPTY input
    # box with no running turn — is invisible to that text-probe check, so it is warned explicitly
    # here (the live #27 silent Review stall: empty box, agent idle, no sticky). One sticky either way.
    try:
        final_pane = deps.sessions.capture(session_name)
    except Exception:  # noqa: BLE001 — best-effort observability; never break the launch
        final_pane = ""
    if prompt_pending(final_pane, filled):
        verify_prompt_delivered(deps, issue, session_name, filled, column_key)
    else:
        logger.warning(
            "launch prompt for #%s appears UNDELIVERED — no running turn after %d submit retries + "
            "%d re-deliveries (input box empty; the claude REPL ate the paste?). Pane tail:\n%s",
            issue,
            SUBMIT_RETRY_ATTEMPTS,
            REDELIVER_ATTEMPTS,
            pane_tail(final_pane),
        )
        try:
            upsert_stage_comment(
                deps.board_writer,
                issue,
                column_key,
                append="the launch prompt could not be confirmed delivered (the agent's input box "
                "was empty with no running turn after re-delivery) — the agent may be sitting idle; "
                "check the tmux session",
            )
        except Exception:  # noqa: BLE001 — the sticky is advisory; never break the launch
            logger.warning("post-exhaustion warning sticky failed for #%s; continuing", issue)
    return False
