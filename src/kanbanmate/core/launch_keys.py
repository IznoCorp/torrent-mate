"""Pure send-keys delivery primitives: the pane classifier + the ordered key sequence.

Functional core — no I/O, no imports below :mod:`core` (the layering guard enforces this). This
module owns the PURE decisions of the interactive launch flow that the PoC ``engine/launch.py``
made: classifying a ``tmux capture-pane`` snapshot into ``trust`` / ``ready`` / ``pending``, and
building the ordered ``send-keys`` actions that drive a fresh interactive ``claude`` (dismiss the
trust dialog if seen, then type the filled prompt literally, then submit with Enter).

Ported faithfully from the PoC at
``PersonnalScaper/.claude/skills/kanban/kanbanmate/engine/launch.py``:
``_TRUST_MARKER`` / ``_REPL_READY_MARKERS`` / ``_TRUST_POLL_ATTEMPTS`` / ``_TRUST_POLL_INTERVAL``
(L27-44) and ``build_sendkeys_sequence`` (L47-77). The PoC's ``poll_trust_dialog`` is the bounded
capture-pane poll; here the PURE half is :func:`classify_pane` (the per-snapshot verdict) and the
poll LOOP lives in the app layer (which owns the I/O of ``capture`` + the injected sleeper).
"""

from __future__ import annotations

from typing import Literal

# Bounded poll for the trust dialog (PoC launch.py:27-28 / DESIGN §4.6 Step 0). Real ``claude``
# needs a few seconds to render; a single immediate capture misses it. The app layer polls
# ``capture-pane`` up to N times with a short wait until the trust marker OR a ready-REPL marker
# appears, then proceeds. These two constants are the PoC defaults, exported for the app poll loop.
TRUST_POLL_ATTEMPTS = 20
TRUST_POLL_INTERVAL = 0.5  # seconds between captures (overridable for offline tests)

# Trust-dialog marker seen in capture-pane (PoC launch.py:44 / DESIGN §4.6 Step 0). We match the
# dialog's question phrase ("...a project you trust?") rather than the bare word "trust" so an
# already-trusted pane (e.g. "already trusted, prompt> ") does not false-positive.
TRUST_MARKER = "you trust"

# A claude REPL that is ready to accept input shows a prompt box; match a couple of stable
# indicators (PoC launch.py:31) so an already-trusted pane stops the poll without waiting the full
# timeout.
#
# Phase 35 — claude v2.1.170 chrome. The boxed ``│ >`` prompt was replaced by a bare ``❯`` prompt
# with an ``⏵⏵ auto mode on (shift+tab to cycle)`` footer, none of which matched the PoC set — so
# EVERY launch's readiness poll timed out (20×0.5s) and sent anyway (+10s latency). A rendered ``❯``
# means the REPL is ready for send-keys, and the auto-mode footer is the v2.1.170 ready signal; both
# are added here. NOTE: this is a READY marker only — it does NOT change
# :func:`is_waiting_for_input`, where a BARE ``❯`` stays NOT-waiting (an idle prompt is not a pending
# human decision). The two classifiers are independent.
REPL_READY_MARKERS = (
    "│ >",
    "for shortcuts",
    "? for shortcuts",
    "Welcome to Claude",
    "❯",
    "auto mode on",
    "shift+tab to cycle",
)

# Phase-27 §B — markers of a PENDING interactive prompt: a choice/confirmation the agent CANNOT
# answer itself and is BLOCKED waiting for the human on. An agent stalled here is NOT hung (do NOT
# reap it — mark it WAITING and signal the user). Matched case-insensitively in
# :func:`is_waiting_for_input`. Tunable: add a phrase here as ``claude``'s prompts evolve.
#
# Coverage rationale:
#   * "enter to select" / "esc to cancel" — the interactive picker/selector footer (a menu choice).
#   * "❯ 1." — the highlighted first option of a NUMBERED picker (the ❯ cursor on an enumerated
#     option, distinct from a BARE idle ❯ prompt which carries no question — that is NOT waiting).
#   * "(y/n)" — a yes/no confirmation.
#   * "do you want" — the lead-in of claude's permission/confirmation questions ("Do you want to
#     proceed?", "Do you want to make this edit?").
WAITING_FOR_INPUT_MARKERS = (
    "enter to select",
    "esc to cancel",
    "❯ 1.",
    "(y/n)",
    "do you want",
)

# How many TRAILING pane lines :func:`is_waiting_for_input` scans for a pending-prompt marker (31.2).
# A ``tmux capture-pane`` snapshot includes the whole visible scrollback, so an OLD prompt that the
# agent already answered (and scrolled past) would false-positive on a full-buffer scan — pinning a
# live agent's concurrency slot in WAITING forever. The pending prompt the human must answer is, by
# construction, the agent's CURRENT bottom-of-pane state; restricting the scan to the last ~15 lines
# matches only that live prompt and ignores stale scrollback. 15 is comfortably more than any single
# claude prompt footer spans while staying well clear of the prior turn's output.
WAITING_SCAN_LINES = 15

# The verdict :func:`classify_pane` returns for one capture-pane snapshot.
PaneState = Literal["trust", "ready", "pending"]

# One ordered send-keys step. ``("enter",)`` presses Enter (a tmux key NAME, NOT literal text);
# ``("text", <str>)`` types ``<str>`` LITERALLY (``send-keys -l``) so slash-commands and spaces are
# typed verbatim rather than interpreted as key names.
SendKeysStep = tuple[str, ...]


def classify_pane(pane: str) -> PaneState:
    """Classify one ``tmux capture-pane`` snapshot into ``trust`` / ``ready`` / ``pending``.

    Pure per-snapshot verdict (the PoC ``poll_trust_dialog`` loop body, launch.py:160-165): the
    app poll loop calls this on each capture and stops on the first non-``pending`` result —
    ``trust`` (send the dismiss Enter first) or ``ready`` (already trusted; skip the Enter). The
    trust check wins over ready so a pane showing BOTH the dialog and a stale prompt is treated as
    needing the dismiss Enter.

    Args:
        pane: The raw ``capture-pane`` text (may be empty). Matched case-insensitively.

    Returns:
        ``"trust"`` when the trust-dialog marker is present, ``"ready"`` when a ready-REPL marker
        is present (and no trust marker), else ``"pending"`` (keep polling).
    """
    lowered = (pane or "").lower()
    if TRUST_MARKER in lowered:
        return "trust"
    if any(marker.lower() in lowered for marker in REPL_READY_MARKERS):
        return "ready"
    return "pending"


def build_sendkeys_sequence(prompt: str, *, trust_prompt_seen: bool) -> list[SendKeysStep]:
    """Build the ordered send-keys steps to drive a fresh interactive ``claude`` (DESIGN §4.6).

    Ported from the PoC ``build_sendkeys_sequence`` (launch.py:47-77). The sequence:

      0. (only if ``trust_prompt_seen``) a bare Enter to dismiss the "Is this a project you
         trust?" dialog BEFORE typing the prompt.
      1. the prompt, sent LITERALLY (``tmux send-keys -l``) so slash-commands / spaces are typed
         verbatim, not interpreted as key names.
      2. a trailing literal space — closes the slash-command autocomplete menu so the following
         Enter submits instead of accepting a completion.
      3. Enter as a SEPARATE event to submit.

    Args:
        prompt: The filled prompt to type (must contain non-whitespace).
        trust_prompt_seen: ``True`` iff the trust dialog was observed in capture-pane.

    Returns:
        The ordered steps: ``("enter",)`` to press Enter, ``("text", <str>)`` to type literally.

    Raises:
        ValueError: If ``prompt`` is empty / whitespace-only (a blank prompt must never be typed —
            the agent would sit idle, the exact bug this delivery path exists to prevent).
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be non-empty")
    seq: list[SendKeysStep] = []
    if trust_prompt_seen:
        seq.append(("enter",))
    seq.append(("text", prompt))
    seq.append(("text", " "))
    seq.append(("enter",))
    return seq


# How many TRAILING pane lines :func:`prompt_pending` scans for unsent prompt content (submit-retry).
# Restricted to the bottom INPUT-BOX region so a SENT message that lingers in scrollback (claude also
# renders a sent paste as ``[Pasted text]`` in the transcript) does not read as still-pending. The
# window must be large enough to cover a BIG prompt's input box: a long prompt (the Spec/design prompt
# embeds the ticket body) collapses to SEVERAL ``[Pasted text #N]`` blocks + many wrapped lines, so
# the live ``[Pasted text]`` marker sits well above the footer — a 6-line tail (the original size)
# MISSED it and the submit-retry exited early, leaving the prompt stuck (live helm #5). 30 lines
# covers the input box while staying clear of most of the conversation; the running-turn marker
# (:data:`SUBMITTED_MARKERS`) still wins, and an over-eager re-send is a harmless no-op on an empty box.
SUBMIT_SCAN_LINES = 30

# Minimum verbatim prompt-slice length for the :func:`prompt_pending` echo check (mirrors the
# observability probe). A whole prompt line this long still in the input box is unambiguous "not
# submitted"; a shorter token could legitimately echo, so a substantial slice avoids false positives.
SUBMIT_MIN_PROBE_LEN = 40

# Markers that a SUBMIT already landed — a turn is running / the message left the input box. When the
# pane tail shows one of these the prompt is NOT pending (do not re-send Enter). Matched
# case-insensitively. ``esc to interrupt`` is claude's running-turn footer.
SUBMITTED_MARKERS = ("esc to interrupt",)

# The collapsed multi-line-paste marker claude shows in the input box for an UNSENT pasted prompt
# (e.g. ``[Pasted text #1 +20 lines]``). Its presence in the input-box window means the prompt is
# still sitting unsubmitted. Matched case-insensitively.
PENDING_PASTE_MARKER = "pasted text"

# Input-box footer hints claude shows ONLY when the input box holds UNSENT content (they vanish once
# the box is empty / a turn runs). Strong, transcript-free pending signals — they complement the
# ``[Pasted text]`` marker (which a huge prompt can still push out of even a 30-line window, and which
# also echoes in the transcript). Matched case-insensitively.
INPUT_CONTENT_MARKERS = ("paste again to expand", "ctrl+g to edit")


def prompt_pending(pane: str, filled: str) -> bool:
    """Return whether the filled prompt is STILL sitting unsubmitted in the input box (submit-retry).

    Pure, marker-based — the verdict the submit-retry loop
    (:func:`kanbanmate.app.prompt_delivery.submit_prompt_with_retries`) polls after sending the
    submit Enter. On claude v2.1.x the REPL renders a ready prompt (``❯`` / ``auto mode on``) a beat
    BEFORE it accepts input, so the single submit Enter can be ABSORBED and the prompt is left in the
    input box (shown as a collapsed ``[Pasted text …]`` for a multi-line prompt, or verbatim for a
    short one). This detects that state so the caller re-sends Enter until it lands.

    Only the last :data:`SUBMIT_SCAN_LINES` lines (the live input-box region) are scanned: claude also
    renders a SENT paste as ``[Pasted text]`` in the transcript above, so a full-buffer scan would
    read a successfully-submitted prompt as still-pending and spam Enter.

    Precedence: a running-turn marker (:data:`SUBMITTED_MARKERS`) wins → NOT pending (the submit
    landed and a turn is in flight). Then an input-box content hint (:data:`INPUT_CONTENT_MARKERS` —
    the expand/edit footer claude shows only while the box holds unsent text), the collapsed-paste
    marker, or a verbatim probe slice → pending. An EMPTY tail is NOT pending (nothing to resubmit —
    never spam Enter at a blank pane).

    Args:
        pane: The raw ``capture-pane`` text (may be empty). Matched case-insensitively.
        filled: The filled prompt that was sent (its first non-blank line is the verbatim probe).

    Returns:
        ``True`` iff the prompt appears still-unsubmitted in the input box; ``False`` otherwise
        (submitted, a turn running, or an empty/indeterminate pane).
    """
    tail = "\n".join((pane or "").splitlines()[-SUBMIT_SCAN_LINES:])
    lowered = tail.lower()
    if not lowered.strip():
        # Blank tail: nothing to resubmit. Never spam Enter at an empty pane.
        return False
    if any(marker in lowered for marker in SUBMITTED_MARKERS):
        # A turn is running → the submit landed.
        return False
    if any(marker in lowered for marker in INPUT_CONTENT_MARKERS):
        # The input box still holds unsent content (its expand/edit footer hint is showing) → pending.
        return True
    if PENDING_PASTE_MARKER in lowered:
        # A collapsed multi-line paste sitting in the input box → not submitted.
        return True
    # Short prompts are typed verbatim (not collapsed): a long enough slice still in the input box
    # is unambiguous "not submitted".
    probe = next((line.strip() for line in (filled or "").splitlines() if line.strip()), "")
    probe = probe[:80].lower()
    return len(probe) >= SUBMIT_MIN_PROBE_LEN and probe in lowered


def is_waiting_for_input(pane: str) -> bool:
    """Return whether a captured pane shows an agent BLOCKED on a PENDING human prompt (§B).

    Pure, marker-based — mirrors :func:`classify_pane`. The reaper calls this on a STALE-heartbeat
    but STILL-ALIVE session's captured pane to tell "waiting for the human" (do NOT reap — mark
    WAITING + signal) from "hung/idle/crashed" (reap as usual). A match means the pane shows one of
    the :data:`WAITING_FOR_INPUT_MARKERS` — an interactive choice/confirmation the agent cannot
    answer itself.

    A BARE idle ``❯`` prompt with NO question is deliberately NOT a match: an agent sitting at an
    empty prompt has finished its turn / gone idle (→ reap), it is not awaiting a decision. Only the
    explicit question/picker markers count.

    **Last-lines scan (31.2).** Only the last :data:`WAITING_SCAN_LINES` lines of ``pane`` are
    scanned. A ``capture-pane`` snapshot carries the whole visible scrollback, so a marker from a
    PRIOR prompt the agent already answered would false-positive and pin a live agent's slot in
    WAITING forever. The prompt the human must answer is the agent's CURRENT bottom-of-pane state,
    so restricting to the trailing lines matches only the live prompt and ignores stale scrollback.

    Args:
        pane: The raw ``capture-pane`` text (may be empty). Matched case-insensitively.

    Returns:
        ``True`` iff the pane's TRAILING lines contain a pending-prompt marker; ``False`` otherwise
        (including the empty pane, the bare idle ``❯`` prompt, and a marker only in stale scrollback).
    """
    # Scan only the trailing lines (31.2): a marker in already-answered scrollback must not pin a
    # live slot. ``splitlines()[-N:]`` is the same pane-tail idiom the launch observability uses.
    tail = "\n".join((pane or "").splitlines()[-WAITING_SCAN_LINES:])
    lowered = tail.lower()
    # The markers are already lower-case except the picker glyph; lower-casing both sides keeps the
    # match case-insensitive without per-marker special casing.
    return any(marker.lower() in lowered for marker in WAITING_FOR_INPUT_MARKERS)
