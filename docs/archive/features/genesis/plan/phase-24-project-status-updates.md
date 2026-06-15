# Phase 24 — Project status updates (rolling, on-change orchestration dashboard)

**Trigger (operator):** surface orchestration activity in the GitHub Project's **"Status updates"**
section — agent/script triggering, what each agent is doing (live progress), and health.

**API (confirmed via live schema introspection):** `createProjectV2StatusUpdate` /
`updateProjectV2StatusUpdate` / `deleteProjectV2StatusUpdate`. `CreateProjectV2StatusUpdateInput`
= `{ projectId: ID!, status: ProjectV2StatusUpdateStatus, body: String, startDate: Date,
targetDate: Date }`. Status enum = `INACTIVE | ON_TRACK | AT_RISK | OFF_TRACK | COMPLETE`.

**Design (operator-chosen):** ONE **rolling** status update, refreshed **on state change** (not
every 10s tick), carrying the current state + recent events + **per-agent live progress** (v1+).

## Mechanism

- **Find/track the rolling update:** persist its node id in `~/.kanban` state. First post → `create`
  - store id. Thereafter → `update`. If `update` fails (id stale/deleted) → `create` + re-store
    (fail-soft; the status update is observability, NEVER a launch blocker).
- **On-change only:** persist a hash of the last-posted body; render each tick but only call the
  GraphQL mutation when the body (or status enum) differs from the last post. No spam.
- **Recent events ring:** a small fixed-size (≈10) ring in `~/.kanban` state; the tick appends an
  event per significant action (launch, teardown/cancel, script-gate result, auto-advance, block,
  reap/relaunch). Rendered newest-first.
- **Per-agent live progress (v1+):** for each running agent, read the latest `kanban-progress`
  milestone from its issue **sticky comment** (the agent appends progress to the sticky body, see
  `core/stage_comment.py`), parsed via the existing stage-comment helpers. Capped at the few
  running agents (≤ concurrency_cap), read only when rendering on-change.
- **Health → status enum:** `INACTIVE` when PAUSE kill-switch is set; `OFF_TRACK` when a ticket is
  Blocked or a gate failed; `AT_RISK` when an agent went stale (reaped/relaunched) or a move was
  rate-limit-parked or the queue is over cap; else `ON_TRACK`.
- **Fail-soft everywhere:** any error posting the update is logged and swallowed — it must NEVER
  break the tick or a launch. Network calls carry the client's connect+read timeouts.

## Sub-phase 24.1 — Pure render (`core/status_update.py`)

State model (pure dataclasses) + render:

- `RunningAgent(issue, code, title, from_col, to_col, profile, launched_at, heartbeat_age, progress)`.
- `StatusEvent(ts, kind, issue, detail)`.
- `OrchestrationState(agents: list[RunningAgent], queue_depth, cap, events: list[StatusEvent],
paused: bool, now)`.
- `render_status(state) -> StatusUpdate(body: str, status: str)` — pure; body = the approved layout
  (header pill line · agents-en-cours with per-agent progress · événements récents); status = the
  health mapping above. I/O-free (no clock/network — `now` injected).

**Acceptance:** `make check` green; render of a 1-agent state matches the approved layout; health
mapping unit-tested per branch (paused→INACTIVE, blocked→OFF_TRACK, stale→AT_RISK, else ON_TRACK);
empty state renders a clean "idle" body (COMPLETE or ON_TRACK + "no agents running").

## Sub-phase 24.2 — Adapter + port + state plumbing

- `ports/board.py`: a `ProjectStatusReporter` Protocol — `create_status_update(project_id, body,
status) -> str` (returns the update node id) and `update_status_update(update_id, body, status)`.
- `adapters/github/_queries.py` + `client.py`: implement both via `createProjectV2StatusUpdate` /
  `updateProjectV2StatusUpdate` (introspect `UpdateProjectV2StatusUpdateInput` for the exact field
  names — likely `statusUpdateId`, `body`, `status`). Map the body+status; GraphQLError on errors.
- `ports/store.py` + `adapters/store/fs_store.py`: persist `status_update_id` (str|None),
  `status_events` (ring, ≤10), and `status_body_hash` (str|None) under the runtime root, with the
  existing atomic-write discipline.

**Acceptance:** `make check` green; adapter methods issue the right mutation (mocked transport
test); fs state round-trips the id/ring/hash; the ring caps at 10 newest.

## Sub-phase 24.3 — App wiring + DESIGN + integration

- New `app/status_reporter.py` (or a tick step): after reap+drain+heartbeat, build the
  `OrchestrationState` from the tick's running-agent view + queue + the events ring + PAUSE flag;
  read each running agent's latest progress from its sticky comment (via the board adapter); call
  `render_status`; compare the body hash vs the stored one; on change, `create`-or-`update` the
  rolling status update and persist the new id/hash. Append tick actions to the events ring.
- Wire into `app/tick.py` (fail-soft; never blocks the tick).
- `docs/features/genesis/DESIGN.md`: a new "§ Project status updates" subsection (rolling, on-change,
  health mapping, fail-soft) + an H-row.

**Acceptance:** `make check` green; an integration test drives a tick with one running agent and
asserts a status update is created with the rendered body; a no-op tick (unchanged body) posts
NOTHING; a posting error is swallowed (tick still succeeds). Module-size under the 1000 ceiling.

### Phase gate (per sub-phase)

`rm -rf .mypy_cache && make check` green; diff confined to the sub-phase's files (NEVER the helm
prep / ROADMAP / IMPLEMENTATION / the phase-24 plan); `python -c "import kanbanmate"` smoke.
(Then: restart the live PM2 daemon so the dashboard goes live before the e2e.)
