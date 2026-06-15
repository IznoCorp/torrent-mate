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
)

if TYPE_CHECKING:
    from kanbanmate.app.actions import Deps

logger = logging.getLogger(__name__)

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
