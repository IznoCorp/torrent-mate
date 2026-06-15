"""Pure render for the rolling GitHub Project "status update" dashboard.

The GitHub Project v2 board carries a **"Status updates"** section. KanbanMate
maintains ONE *rolling* status update there (refreshed on state change, never on
every tick — see phase-24 plan §24) that surfaces live orchestration activity:
which agents are running, what each is doing (its latest progress milestone),
the launch queue depth, recent significant events, and an overall **health**
mapped onto GitHub's status enum (``INACTIVE | ON_TRACK | AT_RISK | OFF_TRACK |
COMPLETE``).

This module is the **pure** half (sub-phase 24.1): a small set of frozen value
objects (:class:`RunningAgent`, :class:`StatusEvent`, :class:`OrchestrationState`)
plus a single PURE :func:`render_status` that maps a snapshot of the
orchestration to a :class:`StatusUpdateRender` (markdown body + status enum
value). It mirrors the house style of :mod:`kanbanmate.core.stage_comment`: a
shared ``HH:MM`` timestamp helper, named format constants so the emoji/labels are
trivial to tweak, and ZERO I/O — ``now`` is injected via the state, never read
from a clock, and nothing here touches the network or the filesystem (the
layering guard enforces that ``core`` imports nothing with I/O).

The user-facing strings are **French** (operator decision for the live
dashboard) — distinct from the ENGLISH artifacts of ``stage_comment`` (those are
issue-comment headers; this is the operator's Project status pill).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final, Literal, cast

# ---------------------------------------------------------------------------
# Status vocabulary — GitHub's ProjectV2StatusUpdateStatus enum (5 values).
# ---------------------------------------------------------------------------

#: The five GitHub ``ProjectV2StatusUpdateStatus`` values, in their API spelling.
StatusValue = Literal["INACTIVE", "ON_TRACK", "AT_RISK", "OFF_TRACK", "COMPLETE"]

#: The same five values as a runtime set, for membership assertions in tests and
#: callers that validate a string before handing it to the GraphQL mutation.
STATUS_VALUES: Final[frozenset[str]] = frozenset(
    {"INACTIVE", "ON_TRACK", "AT_RISK", "OFF_TRACK", "COMPLETE"}
)

# ---------------------------------------------------------------------------
# Health-mapping thresholds (named so they are easy to tweak).
# ---------------------------------------------------------------------------

#: An agent whose last heartbeat is at least this many seconds old is "stale"
#: (a degraded signal that maps the dashboard to ``AT_RISK``). Mirrors the
#: reaper's staleness intuition; the precise reaper deadline lives in the app
#: layer — this is the dashboard's own degraded threshold (phase-24 §24.1).
DEFAULT_STALE_AFTER_S: Final[float] = 1800.0

#: Freshness window (seconds) past which a recent-events ring entry STOPS driving
#: the health pill. The ring (last ~10) has no time decay, so on a quiet board a
#: morning ``block`` would otherwise pin ``OFF_TRACK`` for hours (observed live:
#: 3 stale #151 blocks → OFF_TRACK all afternoon). Only events YOUNGER than this
#: window count toward the verdict; older ones still RENDER in the "Événements
#: récents" list, they just no longer drive the pill. Agents-based conditions
#: (waiting / Blocked-parked / stale heartbeat / queue>cap) are unaffected.
EVENT_HEALTH_WINDOW_S: Final[float] = 3600.0

#: Event kinds that mean the orchestration is *blocked / failing* (→ OFF_TRACK).
BLOCKING_EVENT_KINDS: Final[frozenset[str]] = frozenset({"block", "gate_fail"})

#: Event kinds that mean the orchestration is *degraded* (→ AT_RISK): a stale
#: agent was reaped/relaunched, or a move was rate-limit-parked.
DEGRADED_EVENT_KINDS: Final[frozenset[str]] = frozenset({"reap", "rate_limit"})

# ---------------------------------------------------------------------------
# Markdown format constants — emoji + labels grouped so they are easy to tweak.
# ---------------------------------------------------------------------------

#: Per-event-kind emoji prefix used in the "Événements récents" list. Unknown
#: kinds fall back to :data:`_EVENT_FALLBACK_EMOJI` so a new kind never crashes
#: the render — it just shows a neutral bullet glyph.
EVENT_EMOJI: Final[dict[str, str]] = {
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

#: Emoji shown for an event whose ``kind`` is not in :data:`EVENT_EMOJI`.
_EVENT_FALLBACK_EMOJI: Final[str] = "•"

#: Heart glyph prefixing each agent's heartbeat age.
_HEARTBEAT_GLYPH: Final[str] = "❤"

#: Placeholder shown when an agent has no heartbeat age yet (``None``).
_HEARTBEAT_UNKNOWN: Final[str] = "—"


def _fmt_heartbeat_age(age_seconds: float) -> str:
    """Render a heartbeat age BUCKETED so the dashboard body is stable across ticks (#10).

    The raw ``int(age)s`` rendering changed every tick (5s → 15s → 25s …), so the body hash also
    changed every tick — defeating the on-change discipline and causing a PATCH every poll. Bucketing
    keeps the rendered text stable while the agent is healthy: ``<1m`` for a fresh heartbeat, then a
    whole-minute count (``Nm``) so the value only changes once per minute, not once per 10s tick.

    Args:
        age_seconds: Seconds since the agent's last heartbeat.

    Returns:
        ``"<1m"`` when under a minute, else ``"<N>m"`` (whole minutes, floored).
    """
    minutes = int(age_seconds // 60)
    return "<1m" if minutes < 1 else f"{minutes}m"


#: Marker appended to a WAITING agent's line — it is alive but blocked on human
#: input and needs operator attention (phase-27 §B). Its presence also pushes the
#: overall pill to ``AT_RISK`` via :func:`compute_status`.
_WAITING_MARKER: Final[str] = "⏳ waiting for input"

#: Template for the concrete drop-in command a WAITING agent's dashboard block carries (31.2). The
#: tmux session name is ``ticket-<issue>`` everywhere, so the operator gets a copy-pasteable way to
#: attach and answer the pending prompt rather than being told only THAT intervention is needed.
_ATTACH_HINT_TEMPLATE: Final[str] = "→ pour répondre : `tmux attach -t ticket-{issue}`"

#: Title line of the dashboard body.
_HEADER_TITLE: Final[str] = "**KanbanMate — orchestration live**"

#: Body rendered in the agents section when no agent is running.
_NO_AGENTS_LINE: Final[str] = "Aucun agent en cours."


# ---------------------------------------------------------------------------
# Value objects (all frozen — core stays a pure, side-effect-free heart).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunningAgent:
    """A single agent currently running in the orchestration.

    All fields are a *snapshot* the app layer assembles at render time from the
    tick's running-agent view plus a read of the agent's sticky-comment progress
    (phase-24 §24.3); this module never reads them itself.

    Attributes:
        issue: The GitHub issue number the agent is working (its ticket).
        code: A short type tag shown in brackets (e.g. ``"LLM"``, ``"docs"``).
        title: The ticket title.
        from_col: The column the triggering transition moved the card *from*.
        to_col: The column the triggering transition moved the card *to*.
        profile: The agent's permission profile name (e.g. ``"docs"``).
        launched_at: Epoch seconds when the agent was launched.
        heartbeat_age: Seconds since the agent's last heartbeat, or ``None`` when
            no heartbeat has been recorded yet.
        progress: The agent's latest progress milestone text (from its sticky
            comment), or ``None`` when it has reported none yet.
        waiting: Whether the agent is parked WAITING for human input (phase-27
            §B). A waiting agent renders a ``⏳ waiting for input`` marker and
            pushes the overall pill to ``AT_RISK`` (it needs human attention).
            Defaulted ``False`` so existing call sites stay valid.
    """

    issue: int
    code: str
    title: str
    from_col: str
    to_col: str
    profile: str
    launched_at: float
    heartbeat_age: float | None
    progress: str | None
    waiting: bool = False


@dataclass(frozen=True)
class StatusEvent:
    """A single significant orchestration event for the "recent events" ring.

    Attributes:
        ts: Epoch seconds when the event occurred.
        kind: The event category — one of the keys of :data:`EVENT_EMOJI`
            (``launch`` / ``teardown`` / ``cancel`` / ``gate_pass`` /
            ``gate_fail`` / ``auto`` / ``block`` / ``reap`` / ``rate_limit``).
            An unknown kind renders with a neutral bullet, never crashing.
        issue: The issue number the event concerns, or ``None`` for a
            board-wide event (e.g. a pause toggle).
        detail: A short human-readable suffix (e.g. ``"brainstorm"`` or
            ``"→ Review"``).
    """

    ts: float
    kind: str
    issue: int | None
    detail: str


@dataclass(frozen=True)
class OrchestrationState:
    """An I/O-free snapshot of the orchestration, the input to render.

    Everything :func:`render_status` needs is here — including ``now`` — so the
    render is a pure function of its argument (no clock, no network).

    Attributes:
        agents: The running agents, as an immutable tuple (rendered in order).
        queue_depth: The number of launches waiting in the concurrency queue.
        cap: The concurrency cap (max simultaneous agents).
        events: The recent-events ring, as an immutable tuple. Rendered
            newest-first; the caller decides the ring size (≈10).
        paused: Whether the ``~/.kanban/PAUSE`` kill-switch is set.
        now: Epoch seconds to render the "tick" timestamp and to compute event
            ages — INJECTED, never read from a clock (keeps the render pure).
        stale_after_s: Heartbeat-age threshold (seconds) past which an agent is
            "stale" → degraded. Defaults to :data:`DEFAULT_STALE_AFTER_S`.
    """

    agents: tuple[RunningAgent, ...]
    queue_depth: int
    cap: int
    events: tuple[StatusEvent, ...]
    paused: bool
    now: float
    stale_after_s: float = DEFAULT_STALE_AFTER_S
    #: Operator pill override (cockpit ``pill set-health``): when one of :data:`STATUS_VALUES`, it
    #: FORCES the health pill regardless of the computed state, until the operator clears it.
    override_enum: str | None = None
    #: Operator dashboard note (cockpit ``pill note``): rendered as a prominent line when non-empty.
    override_note: str = ""


@dataclass(frozen=True)
class StatusUpdateRender:
    """The output of :func:`render_status`: a body + a GitHub status enum value.

    Attributes:
        body: The markdown body to post into the Project's status update.
        status: One of :data:`STATUS_VALUES` — the GitHub
            ``ProjectV2StatusUpdateStatus`` value that mirrors the health mapping.
    """

    body: str
    status: StatusValue


# ---------------------------------------------------------------------------
# Timestamp — shared HH:MM helper (mirrors stage_comment.fmt_timestamp, kept
# local so the module stays self-contained).
# ---------------------------------------------------------------------------


def _fmt_hhmm(epoch: float) -> str:
    """Format epoch seconds as a local-time ``HH:MM`` string.

    Mirrors :func:`kanbanmate.core.stage_comment.fmt_timestamp` but renders only
    the clock part (the dashboard is "live", so the date is implicit). Kept local
    so this module stays self-contained.

    Args:
        epoch: Epoch seconds.

    Returns:
        The ``HH:MM`` local-time string.
    """
    t = time.localtime(epoch)
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


# ---------------------------------------------------------------------------
# Health mapping.
# ---------------------------------------------------------------------------


def _agent_is_stale(agent: RunningAgent, stale_after_s: float) -> bool:
    """Return whether ``agent``'s last heartbeat is past the stale threshold.

    An agent with no heartbeat age yet (``None``) is NOT considered stale — it
    may simply have just launched.

    Args:
        agent: The running agent to inspect.
        stale_after_s: The staleness threshold in seconds.

    Returns:
        ``True`` when the agent has a heartbeat age at or beyond the threshold.
    """
    return agent.heartbeat_age is not None and agent.heartbeat_age >= stale_after_s


def _agent_is_blocked(agent: RunningAgent) -> bool:
    """Return whether ``agent`` is parked in a Blocked column.

    Args:
        agent: The running agent to inspect.

    Returns:
        ``True`` when the agent's current column name is ``"Blocked"``.
    """
    return agent.to_col == "Blocked"


def compute_status(state: OrchestrationState) -> StatusValue:
    """Map an :class:`OrchestrationState` onto a GitHub status enum value.

    Precedence (first match wins), per phase-24 plan §24.1:

    1. ``state.paused`` (kill-switch) → ``INACTIVE``.
    2. any blocking/failure event (``block`` / ``gate_fail``) OR an agent parked
       Blocked → ``OFF_TRACK``.
    3. any degraded signal — a stale agent (heartbeat past
       ``state.stale_after_s``), an agent WAITING for human input (phase-27 §B),
       a reap/relaunch or rate-limit-park event, or ``queue_depth > cap`` →
       ``AT_RISK``.
    4. no agents AND no recorded events (fully idle) → ``COMPLETE``.
    5. otherwise → ``ON_TRACK``.

    Only events YOUNGER than :data:`EVENT_HEALTH_WINDOW_S` count toward the
    block/gate-fail/reap/rate-limit health verdict (precedence 2 & 3): the ring
    has no time decay, so without this a single morning ``block`` pins the pill to
    ``OFF_TRACK`` for the rest of the day on an otherwise-quiet board. The stale
    events still RENDER in the dashboard's events list (:func:`render_status`
    reads the full ring) — they just stop driving the pill. Agents-based
    conditions are unaffected.

    Args:
        state: The orchestration snapshot.

    Returns:
        The matching :data:`StatusValue`.
    """
    # Operator override wins over everything (cockpit ``pill set-health``): an explicit operator
    # decision to pin the pill (e.g. AT_RISK during an incident) takes precedence over the computed
    # health AND the kill-switch, until the operator clears it.
    if state.override_enum in STATUS_VALUES:
        return cast("StatusValue", state.override_enum)

    if state.paused:
        return "INACTIVE"

    # Only FRESH events (younger than the freshness window) drive the health pill;
    # the full ring still renders. ``state.now`` is the injected clock, so this
    # stays a pure function of its argument.
    event_kinds = {e.kind for e in state.events if state.now - e.ts <= EVENT_HEALTH_WINDOW_S}

    if event_kinds & BLOCKING_EVENT_KINDS or any(_agent_is_blocked(a) for a in state.agents):
        return "OFF_TRACK"

    degraded = (
        bool(event_kinds & DEGRADED_EVENT_KINDS)
        or state.queue_depth > state.cap
        or any(_agent_is_stale(a, state.stale_after_s) for a in state.agents)
        # An agent WAITING for human input needs operator attention (phase-27 §B) — distinct from a
        # truly-stale/hung agent (which the reaper kills), so it degrades the pill to AT_RISK.
        or any(a.waiting for a in state.agents)
    )
    if degraded:
        return "AT_RISK"

    # Fully idle — no running agents and no recorded activity — reads as the work
    # being *done* rather than ongoing, so COMPLETE (not ON_TRACK). Unit-tested.
    if not state.agents and not state.events:
        return "COMPLETE"

    return "ON_TRACK"


# ---------------------------------------------------------------------------
# Body render.
# ---------------------------------------------------------------------------


def _render_agent_block(agent: RunningAgent) -> list[str]:
    """Render the markdown lines for one running agent.

    The first line carries the issue, code tag, title, the ``from→to`` transition
    and the profile; the second line carries the launch time, the heartbeat age
    (``❤ Ns``, or ``❤ —`` when unknown), and — only when present — the latest
    progress milestone as an italic French quote.

    Args:
        agent: The running agent to render.

    Returns:
        The agent's markdown lines (one or two, depending on ``progress``).
    """
    heartbeat = (
        f"{_HEARTBEAT_GLYPH} {_HEARTBEAT_UNKNOWN}"
        if agent.heartbeat_age is None
        # Bucket the age to minutes (#10) so the rendered body — and thus its hash — stays STABLE
        # across ticks while the agent is healthy, restoring the on-change discipline.
        else f"{_HEARTBEAT_GLYPH} {_fmt_heartbeat_age(agent.heartbeat_age)}"
    )
    # A WAITING agent (phase-27 §B) carries the ⏳ marker on its FIRST line so the operator spots
    # the need for intervention at a glance (and the pill is AT_RISK). A normal running agent has no
    # suffix here.
    waiting_suffix = f" · {_WAITING_MARKER}" if agent.waiting else ""
    lines = [
        f"- **#{agent.issue}** [{agent.code}] {agent.title} — "
        f"`{agent.from_col}→{agent.to_col}` · profil `{agent.profile}`{waiting_suffix}",
        f"  lancé {_fmt_hhmm(agent.launched_at)} · {heartbeat}",
    ]
    if agent.progress is not None:
        # The progress milestone hangs off the heartbeat line as an italic quote.
        lines[1] += f" · _« {agent.progress} »_"
    # A WAITING agent gets a concrete drop-in command (31.2): the operator can attach to the tmux
    # session and answer the pending prompt straight from the dashboard, instead of being told only
    # THAT a human is needed. Normal running agents carry no such line.
    if agent.waiting:
        lines.append(f"  {_ATTACH_HINT_TEMPLATE.format(issue=agent.issue)}")
    return lines


def _render_event_line(event: StatusEvent) -> str:
    """Render one recent-event line: ``HH:MM <emoji> [#issue] detail``.

    Args:
        event: The event to render.

    Returns:
        The event's single markdown bullet line.
    """
    emoji = EVENT_EMOJI.get(event.kind, _EVENT_FALLBACK_EMOJI)
    issue = f" #{event.issue}" if event.issue is not None else ""
    detail = f" {event.detail}" if event.detail else ""
    return f"- {_fmt_hhmm(event.ts)} {emoji}{issue}{detail}".rstrip()


def render_status(state: OrchestrationState) -> StatusUpdateRender:
    """Render the rolling Project status-update body + status enum (PURE).

    Produces the operator-approved layout: a header pill line, an
    "Agents en cours" section (one block per running agent, with per-agent live
    progress), and an "Événements récents" section (newest-first). When no agent
    is running, the agents section degrades to a single clean idle line. The
    status enum is :func:`compute_status` of the same state.

    No clock and no I/O — ``state.now`` is the only time source, so the render is
    a pure function of its argument (deterministic, fully unit-testable).

    Args:
        state: The orchestration snapshot to render.

    Returns:
        A :class:`StatusUpdateRender` carrying the markdown body and the GitHub
        status enum value.
    """
    status = compute_status(state)

    lines: list[str] = [
        f"{_HEADER_TITLE} · `{status}`",
        f"tick {_fmt_hhmm(state.now)} · cap {state.cap} · queue {state.queue_depth}",
    ]
    # Operator override banner (cockpit pill): make a pinned pill + any operator note explicit so the
    # dashboard does not look like a stuck/auto state when the operator forced it.
    if state.override_enum in STATUS_VALUES:
        lines.append(
            f"⚙️ pill forcé par l'opérateur (`{state.override_enum}`) — `kanban pill clear`"
        )
    if state.override_note:
        lines.append(f"**Note opérateur** — {state.override_note}")
    lines.extend(["", f"**Agents en cours ({len(state.agents)})**"])

    if state.agents:
        for agent in state.agents:
            lines.extend(_render_agent_block(agent))
    else:
        lines.append(_NO_AGENTS_LINE)

    lines.append("")
    lines.append("**Événements récents**")
    if state.events:
        # Newest-first: the ring is appended oldest→newest by the app layer.
        for event in sorted(state.events, key=lambda e: e.ts, reverse=True):
            lines.append(_render_event_line(event))
    else:
        lines.append("_Aucun événement récent._")

    return StatusUpdateRender(body="\n".join(lines), status=status)
