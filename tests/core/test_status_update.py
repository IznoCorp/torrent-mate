"""Pure unit tests for :mod:`kanbanmate.core.status_update` (NO I/O).

Covers the health mapping (one assertion per precedence branch), the approved
1-agent layout, the heartbeat / progress variants, the newest-first event
ordering, the idle body, and the determinism of the pure render.

All timestamps use a fixed UTC epoch and assert on the local ``HH:MM`` produced
by the module's own helper, so the tests are deterministic regardless of the
host timezone (we compute the expected ``HH:MM`` from the same epoch).
"""

from __future__ import annotations

import time

from kanbanmate.core.status_update import (
    EVENT_HEALTH_WINDOW_S,
    STATUS_VALUES,
    OrchestrationState,
    RunningAgent,
    StatusEvent,
    StatusUpdateRender,
    compute_status,
    render_status,
)

# A fixed reference epoch (timezone-independent assertions are derived from it).
_NOW = 1_700_000_000.0


def _hhmm(epoch: float) -> str:
    """Local ``HH:MM`` for ``epoch`` — mirrors the module's own formatter."""
    t = time.localtime(epoch)
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


def _agent(**kw: object) -> RunningAgent:
    """Build a :class:`RunningAgent` with sensible defaults overridable by kw."""
    base: dict[str, object] = {
        "issue": 140,
        "code": "LLM",
        "title": "Pipeline Assistant",
        "from_col": "Backlog",
        "to_col": "Spec",
        "profile": "docs",
        "launched_at": _NOW - 120,
        "heartbeat_age": 5.0,
        "progress": "brainstorm en cours",
    }
    base.update(kw)
    return RunningAgent(**base)  # type: ignore[arg-type]


def _state(**kw: object) -> OrchestrationState:
    """Build an :class:`OrchestrationState` with defaults overridable by kw."""
    base: dict[str, object] = {
        "agents": (),
        "queue_depth": 0,
        "cap": 3,
        "events": (),
        "paused": False,
        "now": _NOW,
    }
    base.update(kw)
    return OrchestrationState(**base)  # type: ignore[arg-type]


# ── health mapping (one per precedence branch) ──────────────────────────────


def test_status_paused_is_inactive() -> None:
    """Precedence 1: the kill-switch wins over everything → INACTIVE."""
    # Even with a blocked agent present, paused takes precedence.
    state = _state(paused=True, agents=(_agent(to_col="Blocked"),))
    assert compute_status(state) == "INACTIVE"


def test_status_block_event_is_off_track() -> None:
    """Precedence 2: a blocking event → BLOCKED."""
    ev = StatusEvent(ts=_NOW, kind="block", issue=137, detail="dep gate")
    assert compute_status(_state(events=(ev,))) == "BLOCKED"


def test_status_gate_fail_event_is_off_track() -> None:
    """Precedence 2: a gate_fail event → BLOCKED."""
    ev = StatusEvent(ts=_NOW, kind="gate_fail", issue=137, detail="CI red")
    assert compute_status(_state(events=(ev,))) == "BLOCKED"


def test_status_blocked_agent_is_off_track() -> None:
    """Precedence 2: an agent parked in Blocked → BLOCKED."""
    assert compute_status(_state(agents=(_agent(to_col="Blocked"),))) == "BLOCKED"


def test_status_stale_agent_is_at_risk() -> None:
    """Precedence 3: a stale heartbeat (>= threshold) → WAITING."""
    state = _state(agents=(_agent(heartbeat_age=2000.0),))
    assert compute_status(state) == "WAITING"


def test_status_reap_event_is_at_risk() -> None:
    """Precedence 3: a reap/relaunch event → WAITING."""
    ev = StatusEvent(ts=_NOW, kind="reap", issue=140, detail="relaunch")
    assert compute_status(_state(agents=(_agent(),), events=(ev,))) == "WAITING"


def test_status_rate_limit_event_is_at_risk() -> None:
    """Precedence 3: a rate-limit park event → WAITING."""
    ev = StatusEvent(ts=_NOW, kind="rate_limit", issue=None, detail="move parked")
    assert compute_status(_state(agents=(_agent(),), events=(ev,))) == "WAITING"


def test_status_queue_over_cap_is_at_risk() -> None:
    """Precedence 3: queue depth over the cap → WAITING."""
    assert compute_status(_state(agents=(_agent(),), queue_depth=4, cap=3)) == "WAITING"


def test_status_waiting_agent_is_at_risk() -> None:
    """Precedence 3 (phase-27 §B): an agent WAITING for human input → WAITING (needs attention).

    A fresh-heartbeat, non-blocked agent that is WAITING still degrades the pill — it needs the
    human, distinct from a truly-stale/hung agent (which the reaper kills).
    """
    state = _state(agents=(_agent(waiting=True, heartbeat_age=5.0),))
    assert compute_status(state) == "WAITING"


def test_render_waiting_agent_shows_marker() -> None:
    """A WAITING agent's line carries the ``⏳ waiting for input`` marker (phase-27 §B)."""
    body = render_status(_state(agents=(_agent(waiting=True),))).body
    assert "⏳ waiting for input" in body
    # The overall pill is WAITING (rendered into the header pill line).
    assert "`WAITING`" in body


def test_render_non_waiting_agent_has_no_marker() -> None:
    """A normal running agent does NOT render the waiting marker (no false signal)."""
    body = render_status(_state(agents=(_agent(waiting=False),))).body
    assert "⏳ waiting for input" not in body


def test_render_waiting_agent_shows_attach_hint() -> None:
    """31.2: a WAITING agent's dashboard block carries a concrete tmux attach command to answer."""
    body = render_status(_state(agents=(_agent(issue=140, waiting=True),))).body
    assert "tmux attach -t ticket-140" in body


def test_render_non_waiting_agent_has_no_attach_hint() -> None:
    """31.2: a normal running agent renders no attach hint (only WAITING agents do)."""
    body = render_status(_state(agents=(_agent(issue=140, waiting=False),))).body
    assert "tmux attach -t ticket-140" not in body


def test_status_stale_block_event_no_longer_drives_pill() -> None:
    """A block event OLDER than the freshness window stops driving the pill (phase-36).

    The ring has no time decay, so a morning block would otherwise pin BLOCKED all day. An aged
    block (here just past the 3600s window) no longer counts toward the verdict: with no agents the
    board reads ACTIVE (the stale event still renders in the events list — it just stops driving
    the pill).
    """
    aged = StatusEvent(ts=_NOW - 3601.0, kind="block", issue=151, detail="dep gate")
    assert compute_status(_state(events=(aged,))) == "ACTIVE"


def test_status_fresh_block_event_still_off_track() -> None:
    """A block event YOUNGER than the freshness window still drives BLOCKED (phase-36)."""
    fresh = StatusEvent(ts=_NOW - 60.0, kind="block", issue=151, detail="dep gate")
    assert compute_status(_state(events=(fresh,))) == "BLOCKED"


def test_status_event_freshness_boundary_is_inclusive() -> None:
    """The freshness window boundary is inclusive (phase-36): age == window still counts.

    An event exactly ``EVENT_HEALTH_WINDOW_S`` old still drives the pill (``<=`` comparison); one
    second past the window does not.
    """
    on_edge = StatusEvent(ts=_NOW - EVENT_HEALTH_WINDOW_S, kind="block", issue=151, detail="x")
    assert compute_status(_state(events=(on_edge,))) == "BLOCKED"
    just_past = StatusEvent(
        ts=_NOW - EVENT_HEALTH_WINDOW_S - 1.0, kind="block", issue=151, detail="x"
    )
    assert compute_status(_state(events=(just_past,))) == "ACTIVE"


def test_status_stale_degraded_event_no_longer_drives_pill() -> None:
    """An aged reap/rate-limit event no longer degrades the pill to WAITING (phase-36).

    With a healthy agent present and only an OLD reap event, the board reads ACTIVE rather than
    WAITING — the degraded signal is windowed alongside the blocking ones.
    """
    aged = StatusEvent(ts=_NOW - 3601.0, kind="reap", issue=140, detail="relaunch")
    assert compute_status(_state(agents=(_agent(),), events=(aged,))) == "ACTIVE"


def test_status_idle_is_complete() -> None:
    """Precedence 4: no agents and no events → COMPLETE (idle)."""
    assert compute_status(_state()) == "COMPLETE"


def test_status_active_is_on_track() -> None:
    """Precedence 5: a healthy running agent → ACTIVE."""
    assert compute_status(_state(agents=(_agent(),))) == "ACTIVE"


def test_status_custom_stale_threshold() -> None:
    """The per-state ``stale_after_s`` overrides the default threshold."""
    # heartbeat_age 600 is below the 1800 default but above a 300 override.
    assert compute_status(_state(agents=(_agent(heartbeat_age=600.0),))) == "ACTIVE"
    state = _state(agents=(_agent(heartbeat_age=600.0),), stale_after_s=300.0)
    assert compute_status(state) == "WAITING"


def test_status_none_heartbeat_is_not_stale() -> None:
    """A just-launched agent (no heartbeat yet) is not stale → ACTIVE."""
    assert compute_status(_state(agents=(_agent(heartbeat_age=None),))) == "ACTIVE"


# ── render returns the rendered status in the dataclass ─────────────────────


def test_render_returns_status_value() -> None:
    """The render carries the computed status, a member of STATUS_VALUES."""
    render = render_status(_state(agents=(_agent(),)))
    assert isinstance(render, StatusUpdateRender)
    assert render.status == "ACTIVE"
    assert render.status in STATUS_VALUES


# ── approved 1-agent layout ─────────────────────────────────────────────────


def test_render_one_agent_layout() -> None:
    """A 1-agent state matches the operator-approved layout, line by line."""
    agent = _agent(
        issue=140,
        code="LLM",
        title="Pipeline Assistant",
        from_col="Backlog",
        to_col="Spec",
        profile="docs",
        launched_at=_NOW - 60,
        heartbeat_age=5.0,
        progress="brainstorm milestone",
    )
    ev = StatusEvent(ts=_NOW - 30, kind="launch", issue=140, detail="brainstorm")
    body = render_status(_state(agents=(agent,), cap=3, queue_depth=0, events=(ev,))).body

    assert body.splitlines() == [
        "**KanbanMate — orchestration live** · `ACTIVE`",
        f"tick {_hhmm(_NOW)} · cap 3 · queue 0",
        "",
        "**Agents en cours (1)**",
        "- **#140** [LLM] Pipeline Assistant — `Backlog→Spec` · profil `docs`",
        f"  lancé {_hhmm(_NOW - 60)} · ❤ <1m · _« brainstorm milestone »_",
        "",
        "**Événements récents**",
        f"- {_hhmm(_NOW - 30)} 🚀 #140 brainstorm",
    ]


def test_render_omits_progress_line_when_none() -> None:
    """A None progress keeps the heartbeat line, drops the italic milestone."""
    agent = _agent(progress=None, heartbeat_age=5.0, launched_at=_NOW - 60)
    body = render_status(_state(agents=(agent,))).body
    assert f"  lancé {_hhmm(_NOW - 60)} · ❤ <1m" in body  # #10: bucketed to minutes
    assert "«" not in body  # no progress quote


def test_render_heartbeat_unknown_dash() -> None:
    """A None heartbeat age renders as ``❤ —``."""
    agent = _agent(heartbeat_age=None, progress=None, launched_at=_NOW - 60)
    body = render_status(_state(agents=(agent,))).body
    assert f"  lancé {_hhmm(_NOW - 60)} · ❤ —" in body


# ── events: newest-first, per-kind emoji, unknown-kind fallback ─────────────


def test_render_events_newest_first() -> None:
    """Events render newest-first regardless of input order."""
    older = StatusEvent(ts=_NOW - 100, kind="launch", issue=1, detail="a")
    newer = StatusEvent(ts=_NOW - 10, kind="gate_pass", issue=2, detail="→ Review")
    body = render_status(_state(events=(older, newer))).body
    lines = [ln for ln in body.splitlines() if ln.startswith("- ")]
    assert lines[0] == f"- {_hhmm(_NOW - 10)} ✅ #2 → Review"
    assert lines[1] == f"- {_hhmm(_NOW - 100)} 🚀 #1 a"


def test_render_event_emoji_per_kind() -> None:
    """Each documented kind renders its dedicated emoji."""
    expected = {
        "launch": "🚀",
        "teardown": "🧹",
        "cancel": "🧹",
        "gate_pass": "✅",
        "gate_fail": "❌",
        "auto": "🤖",
        "block": "⛔",
        "reap": "♻️",
        "rate_limit": "⏳",
    }
    for kind, emoji in expected.items():
        ev = StatusEvent(ts=_NOW, kind=kind, issue=7, detail="x")
        body = render_status(_state(events=(ev,))).body
        assert f"{emoji} #7 x" in body, kind


def test_render_unknown_event_kind_falls_back() -> None:
    """An unknown event kind renders a neutral bullet, never crashing."""
    ev = StatusEvent(ts=_NOW, kind="mystery", issue=None, detail="")
    body = render_status(_state(events=(ev,))).body
    assert f"- {_hhmm(_NOW)} •" in body


def test_render_event_without_issue_or_detail() -> None:
    """A board-wide event (no issue, no detail) renders cleanly with no trailing space."""
    ev = StatusEvent(ts=_NOW, kind="block", issue=None, detail="")
    body = render_status(_state(events=(ev,))).body
    assert f"- {_hhmm(_NOW)} ⛔" in body
    # No event line should end in a space.
    for line in body.splitlines():
        assert not line.endswith(" ")


# ── idle body ───────────────────────────────────────────────────────────────


def test_render_idle_body() -> None:
    """An empty state renders a clean idle body with both sections."""
    body = render_status(_state()).body
    assert body.splitlines() == [
        "**KanbanMate — orchestration live** · `COMPLETE`",
        f"tick {_hhmm(_NOW)} · cap 3 · queue 0",
        "",
        "**Agents en cours (0)**",
        "Aucun agent en cours.",
        "",
        "**Événements récents**",
        "_Aucun événement récent._",
    ]


# ── purity / determinism ────────────────────────────────────────────────────


def test_render_is_deterministic() -> None:
    """The render is a pure function of its argument (same input → same output)."""
    state = _state(agents=(_agent(),), events=(StatusEvent(_NOW, "launch", 140, "go"),))
    assert render_status(state) == render_status(state)


# ── operator pill override (cockpit PR3.3) ─────────────────────────────────


def test_override_enum_wins_over_computed_and_paused() -> None:
    # An explicit operator override forces the pill — over the computed health AND the kill-switch.
    assert compute_status(_state(override_enum="BLOCKED")) == "BLOCKED"
    assert compute_status(_state(paused=True, override_enum="ACTIVE")) == "ACTIVE"


def test_invalid_override_enum_is_ignored() -> None:
    # A bogus override falls through to the computed health (fully idle → COMPLETE).
    assert compute_status(_state(override_enum="BOGUS")) == "COMPLETE"


def test_render_shows_override_banner_and_note() -> None:
    body = render_status(_state(override_enum="WAITING", override_note="incident in prod")).body
    assert "`WAITING`" in body
    assert "opérateur" in body  # the forced-pill banner
    assert "incident in prod" in body
