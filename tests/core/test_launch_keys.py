"""Tests for the pure send-keys primitives (:mod:`kanbanmate.core.launch_keys`).

Pure unit tests — no I/O, no tmux. They assert the per-snapshot pane verdict
(:func:`classify_pane`) and the ordered send-keys sequence
(:func:`build_sendkeys_sequence`) ported from the PoC ``engine/launch.py``.
"""

from __future__ import annotations

import pytest

from kanbanmate.core.launch_keys import (
    REPL_READY_MARKERS,
    TRUST_MARKER,
    TRUST_POLL_ATTEMPTS,
    TRUST_POLL_INTERVAL,
    WAITING_FOR_INPUT_MARKERS,
    build_sendkeys_sequence,
    classify_pane,
    is_waiting_for_input,
)

# ---------------------------------------------------------------------------
# classify_pane
# ---------------------------------------------------------------------------


def test_classify_pane_trust_marker() -> None:
    """A pane showing the trust-dialog question phrase classifies as ``trust``."""
    assert classify_pane("Do you trust the files in this folder?") == "trust"
    # The PoC matches the phrase fragment, case-insensitively.
    assert TRUST_MARKER == "you trust"
    assert classify_pane("...A PROJECT YOU TRUST?") == "trust"


def test_classify_pane_ready_markers() -> None:
    """Each ready-REPL marker classifies a (non-trust) pane as ``ready``."""
    for marker in REPL_READY_MARKERS:
        assert classify_pane(f"some chrome {marker} more chrome") == "ready"


def test_classify_pane_ready_includes_v2_1_170_chrome() -> None:
    """Phase 35: the v2.1.170 bare-``❯`` prompt + auto-mode footer are READY markers."""
    # The new chrome tokens must be present in the marker set so the readiness poll stops on them
    # instead of timing out (+10s latency).
    assert "❯" in REPL_READY_MARKERS
    assert "auto mode on" in REPL_READY_MARKERS
    assert "shift+tab to cycle" in REPL_READY_MARKERS


def test_classify_pane_ready_on_v2_1_170_pane_fixture() -> None:
    """Phase 35: a realistic claude v2.1.170 pane (bare ``❯`` + auto-mode footer) classifies ready.

    Reproduces the live e2e capture: a bare ``❯`` prompt and the
    ``⏵⏵ auto mode on (shift+tab to cycle)`` footer, none of which matched the PoC marker set — so
    the readiness poll timed out and sent late. With the new markers the pane is ``ready``.
    """
    pane = (
        "\n"
        "  Some prior agent output scrolled above.\n"
        "\n"
        "❯\n"
        "\n"
        "  ⏵⏵ auto mode on (shift+tab to cycle)\n"
    )
    assert classify_pane(pane) == "ready"


def test_classify_pane_pending_when_neither() -> None:
    """A pane with neither a trust nor a ready marker is still ``pending`` (keep polling)."""
    assert classify_pane("booting...") == "pending"
    assert classify_pane("") == "pending"


def test_classify_pane_trust_wins_over_ready() -> None:
    """A pane showing BOTH the trust dialog and a stale prompt is ``trust`` (dismiss Enter first)."""
    assert classify_pane("│ > previous output\nIs this a project you trust?") == "trust"


# ---------------------------------------------------------------------------
# build_sendkeys_sequence
# ---------------------------------------------------------------------------


def test_sequence_without_trust_is_prompt_space_enter() -> None:
    """With no trust dialog seen: [literal prompt, literal space, Enter] (no dismiss Enter)."""
    seq = build_sendkeys_sequence("/implement:phase #7", trust_prompt_seen=False)
    assert seq == [("text", "/implement:phase #7"), ("text", " "), ("enter",)]


def test_sequence_with_trust_prepends_dismiss_enter() -> None:
    """With the trust dialog seen: a leading Enter dismisses it BEFORE the literal prompt."""
    seq = build_sendkeys_sequence("/implement:phase #7", trust_prompt_seen=True)
    assert seq == [
        ("enter",),
        ("text", "/implement:phase #7"),
        ("text", " "),
        ("enter",),
    ]


def test_sequence_preserves_multiline_prompt_literally() -> None:
    """A prompt with newlines/spaces is carried as ONE literal step (typed verbatim)."""
    prompt = "The CI is red:\nfix it now."
    seq = build_sendkeys_sequence(prompt, trust_prompt_seen=False)
    assert ("text", prompt) in seq


def test_sequence_empty_prompt_raises() -> None:
    """An empty / whitespace-only prompt raises — a blank prompt must never be typed (the bug)."""
    with pytest.raises(ValueError, match="non-empty"):
        build_sendkeys_sequence("", trust_prompt_seen=False)
    with pytest.raises(ValueError, match="non-empty"):
        build_sendkeys_sequence("   \n\t ", trust_prompt_seen=True)


# ---------------------------------------------------------------------------
# constants (PoC parity)
# ---------------------------------------------------------------------------


def test_poll_constants_match_poc() -> None:
    """The bounded-poll constants are the PoC defaults (launch.py:27-28)."""
    assert TRUST_POLL_ATTEMPTS == 20
    assert TRUST_POLL_INTERVAL == 0.5


# ---------------------------------------------------------------------------
# is_waiting_for_input (phase-27 §B)
# ---------------------------------------------------------------------------


def test_is_waiting_for_input_choice_and_confirmation_markers() -> None:
    """Each pending-prompt marker classifies the pane as waiting for human input."""
    assert is_waiting_for_input("Use arrow keys. Enter to select, Esc to cancel.") is True
    assert is_waiting_for_input("❯ 1. Yes\n  2. No") is True
    assert is_waiting_for_input("Overwrite the file? (y/n)") is True
    assert is_waiting_for_input("Do you want to proceed with this edit?") is True
    # Matched case-insensitively (an uppercased prompt still counts).
    assert is_waiting_for_input("DO YOU WANT TO CONTINUE?") is True


def test_is_waiting_for_input_bare_idle_prompt_is_not_waiting() -> None:
    """A BARE idle ``❯`` prompt with NO question is NOT waiting (→ reap, not WAITING)."""
    # The bare cursor / idle prompt carries no pending decision — an idle/finished agent.
    assert is_waiting_for_input("❯ ") is False
    assert is_waiting_for_input("│ > ") is False


def test_is_waiting_for_input_empty_and_plain_output_not_waiting() -> None:
    """An empty pane or plain running output is not waiting (no pending-prompt marker)."""
    assert is_waiting_for_input("") is False
    assert is_waiting_for_input("running tests...\nedited file foo.py") is False


def test_waiting_markers_are_named_constants() -> None:
    """The markers live in a named, tunable constant tuple (easy to evolve with claude)."""
    assert "do you want" in WAITING_FOR_INPUT_MARKERS
    assert "(y/n)" in WAITING_FOR_INPUT_MARKERS
    assert "❯ 1." in WAITING_FOR_INPUT_MARKERS


def test_is_waiting_for_input_ignores_stale_scrollback_marker() -> None:
    """31.2: a marker only in OLD scrollback (already answered) is NOT a match (last-lines scan).

    A ``capture-pane`` snapshot carries the whole visible buffer. A pending-prompt marker that the
    agent already answered, now scrolled far above the live bottom of the pane, must not pin the
    slot in WAITING — only the CURRENT bottom-of-pane prompt counts.
    """
    # The waiting marker is on line 0; the live bottom of the pane is plain running output well
    # past the WAITING_SCAN_LINES window, so the stale marker is ignored.
    stale = "Do you want to proceed?\n" + "\n".join(f"running step {i}" for i in range(40))
    assert is_waiting_for_input(stale) is False


def test_is_waiting_for_input_matches_marker_in_last_lines() -> None:
    """31.2: a marker WITHIN the last-lines window (the live prompt) still matches."""
    from kanbanmate.core.launch_keys import WAITING_SCAN_LINES

    # Old output above, then the live prompt at the very bottom (within the scan window).
    pane = "\n".join(f"old line {i}" for i in range(40)) + "\n(y/n)"
    assert is_waiting_for_input(pane) is True
    # The scan window is the named, tunable constant.
    assert WAITING_SCAN_LINES == 15


# ---------------------------------------------------------------------------
# prompt_pending — the submit-retry verdict (submit-reliability fix). True iff the filled prompt is
# still sitting UNSUBMITTED in the input box; False once a turn is running / the box emptied.
# ---------------------------------------------------------------------------


def test_prompt_pending_collapsed_paste_is_pending() -> None:
    """A collapsed multi-line paste in the input box ⇒ pending (the submit Enter was absorbed)."""
    from kanbanmate.core.launch_keys import prompt_pending

    pane = "❯ [Pasted text #1 +20 lines]\n  ⏵⏵ auto mode on (shift+tab to cycle)"
    assert prompt_pending(pane, "/implement:brainstorm do the thing\nmore lines") is True


def test_prompt_pending_verbatim_short_prompt_is_pending() -> None:
    """A short prompt typed verbatim and still in the input box ⇒ pending."""
    from kanbanmate.core.launch_keys import prompt_pending

    filled = "/implement:plan prepare the plan for #7 now please"  # > 40 chars
    pane = f"❯ {filled}\n  ⏵⏵ auto mode on"
    assert prompt_pending(pane, filled) is True


def test_prompt_pending_running_turn_marker_is_submitted() -> None:
    """A running-turn marker (esc to interrupt) ⇒ NOT pending even if the paste lingers above."""
    from kanbanmate.core.launch_keys import prompt_pending

    pane = "[Pasted text #1 +20 lines]\n● working…\n  esc to interrupt"
    assert prompt_pending(pane, "/implement:brainstorm do the thing") is False


def test_prompt_pending_empty_input_box_is_submitted() -> None:
    """An empty input box (prompt gone) ⇒ NOT pending (the submit landed)."""
    from kanbanmate.core.launch_keys import prompt_pending

    pane = "user: ...\nassistant: starting\n❯ \n  ⏵⏵ auto mode on (shift+tab to cycle)"
    assert prompt_pending(pane, "/implement:brainstorm do the thing here now") is False


def test_prompt_pending_empty_pane_is_not_pending() -> None:
    """A blank pane is NOT pending — never spam Enter at an empty pane."""
    from kanbanmate.core.launch_keys import prompt_pending

    assert prompt_pending("", "/implement:brainstorm do the thing") is False
    assert prompt_pending("   \n  ", "/implement:brainstorm do the thing") is False


def test_prompt_pending_only_scans_input_box_tail_not_scrollback() -> None:
    """A sent paste lingering in scrollback (above the input box) does NOT read as pending."""
    from kanbanmate.core.launch_keys import SUBMIT_SCAN_LINES, prompt_pending

    # The [Pasted text] is far up in scrollback; the live input box (last lines) is empty.
    pane = "[Pasted text #1 +20 lines]\n" + "\n".join(f"line {i}" for i in range(SUBMIT_SCAN_LINES))
    pane += "\n❯ \n  ⏵⏵ auto mode on"
    assert prompt_pending(pane, "/implement:brainstorm do the thing here") is False


def test_prompt_pending_large_prompt_pasted_marker_above_old_window() -> None:
    """A LARGE prompt whose [Pasted text] marker sits >6 lines above the footer is still PENDING.

    Regression (helm #5): the design/Spec prompt collapses to several [Pasted text #N] blocks + many
    wrapped lines, pushing the marker past the original 6-line tail — so it read as submitted and the
    submit-retry exited, leaving the prompt stuck. The widened window (SUBMIT_SCAN_LINES=30) catches it.
    """
    from kanbanmate.core.launch_keys import prompt_pending

    # [Pasted text] then ~12 wrapped prompt lines then the footer — marker is ~14 lines up (was missed
    # by the old 6-line window, caught by 30).
    body = "\n".join(f"  …design prompt line {i}…" for i in range(12))
    pane = (
        "❯ [Pasted text #1 +9 lines][Pasted text #2 +13 lines]\n"
        + body
        + "\n────────\n  ⏵⏵ auto mode on (shift+tab to cycle)"
    )
    assert prompt_pending(pane, "Write the design for #5 from the brainstorm output above") is True


def test_prompt_pending_input_box_footer_hint_is_pending() -> None:
    """The input-box expand/edit footer hint (shown only with unsent content) ⇒ pending."""
    from kanbanmate.core.launch_keys import prompt_pending

    pane = "  …prompt text…\n────────\n  paste again to expand        ctrl+g to edit in VS Code"
    assert prompt_pending(pane, "/implement:plan prepare the plan") is True


def test_prompt_pending_window_is_30() -> None:
    """The submit scan window is the widened, named constant (large-prompt coverage)."""
    from kanbanmate.core.launch_keys import SUBMIT_SCAN_LINES

    assert SUBMIT_SCAN_LINES == 30


# ---------------------------------------------------------------------------
# turn_running — the STRICT post-submit success signal: a turn is actually in flight. Distinguishes a
# genuinely-submitted prompt (a running turn) from an EATEN paste (empty box, no turn) so the delivery
# can re-paste an eaten prompt instead of falsely declaring success (claude v2.1.175 intro-screen race).
# ---------------------------------------------------------------------------


def test_turn_running_detects_running_marker() -> None:
    """A running-turn footer (esc to interrupt) ⇒ a turn is in flight."""
    from kanbanmate.core.launch_keys import turn_running

    assert turn_running("● Pouncing…\n  esc to interrupt") is True


def test_turn_running_empty_or_idle_welcome_is_false() -> None:
    """An empty box / the bare v2.1.175 welcome screen ⇒ NO turn (the eaten-paste signal)."""
    from kanbanmate.core.launch_keys import turn_running

    assert turn_running("") is False
    welcome = (
        "Welcome to Claude\n  Using flicker-free rendering\n❯ \n"
        "  ⏵⏵ auto mode on (shift+tab to cycle)"
    )
    assert turn_running(welcome) is False


def test_turn_running_only_scans_input_box_tail_not_scrollback() -> None:
    """A running-turn marker far up in scrollback (a prior turn) does NOT count — only the live tail."""
    from kanbanmate.core.launch_keys import SUBMIT_SCAN_LINES, turn_running

    pane = "● esc to interrupt\n" + "\n".join(f"line {i}" for i in range(SUBMIT_SCAN_LINES + 5))
    pane += "\n❯ \n  ⏵⏵ auto mode on"
    assert turn_running(pane) is False
