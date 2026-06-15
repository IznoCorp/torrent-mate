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
