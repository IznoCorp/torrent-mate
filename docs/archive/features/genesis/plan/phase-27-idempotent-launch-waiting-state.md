# Phase 27 — Idempotent launch (A) + agent "waiting-for-input" state (B) (e2e-driven)

**Trigger (live e2e #91):** advancing #91 `Spec→Plan` FAILED to launch — `tmux new-session -s
ticket-91` exited 1 because a STALE session (#91's old churning brainstrom agent) already existed
(`actions.py:352`→`sessions.py:63`). Root: (A) `TmuxSessions.launch` isn't idempotent — a leftover
session blocks any new launch; (B) the reaper relaunched a hung INTERACTIVE agent that was actually
waiting for human input (it can't tell "waiting" from "hung"), which created the stale session.

## Fix A — idempotent `TmuxSessions.launch`

A leftover/stale session with the same name must never block a launch.

- `src/kanbanmate/adapters/workspace/sessions.py` `launch(name, cwd, command)`: BEFORE
  `tmux new-session -s <name>`, kill any pre-existing session of that name (idempotent — e.g. call
  `kill(name)` / `tmux kill-session -t <name>` ignoring "no such session", then create). Keep
  argv-list, no shell=True. (The PoC's tmux wrapper tolerated re-launch; restore that.)
- Tests (`tests/adapters/test_workspace.py`): launching when a session of that name exists kills it
  first then creates (fake runner asserts the kill precedes the new-session); launching with no prior
  session does NOT error on the (no-op) kill.

**Acceptance:** `make check` green; a second `launch` of the same name succeeds (no exit-1); the
launch sequence is kill(name)→new-session→send command.

## Fix B — "waiting-for-input" state (never reap an agent awaiting the human)

The operator-approved rule: **do NOT reap an agent that is waiting for human input — mark it
`WAITING` and SIGNAL the user that intervention is needed.** Only genuinely hung/crashed agents are
reaped.

- `src/kanbanmate/core/domain.py`: add `TicketStatus.WAITING` (an agent alive + waiting for human
  input). (Keep RUNNING / and the terminal/blocked states.)
- `src/kanbanmate/core/launch_keys.py` (or a new pure helper): add `is_waiting_for_input(pane: str)
-> bool` — detect a PENDING interactive prompt in the captured pane: the choice/confirmation
  markers (e.g. `"Enter to select"`, a numbered-option picker `"❯ 1."`, `"Esc to cancel"`,
  y/n confirmations `"(y/n)"`, `"Do you want"`). A BARE idle `❯` prompt with no question is NOT
  waiting (that's done/idle → reap). Pure, marker-based (mirror the trust/REPL classifier). Markers
  in named constants for easy tuning.
- `src/kanbanmate/app/reaper.py`: before reaping a STALE running agent (heartbeat > TTL) whose tmux
  session is STILL ALIVE, capture the pane (`deps.sessions.capture`) and classify:
  - `is_waiting_for_input` → set `TicketStatus.WAITING` (persist), DO NOT reap, DO NOT relaunch.
    Signal once (see below). On a later tick, if the heartbeat refreshed (human answered → agent
    resumed → tool calls) the agent is no longer stale → restore `RUNNING`; if the session died →
    reap as usual.
  - not waiting (idle/hung/errored pane, or session dead) → reap/relaunch as today.
  - Fail-soft: a capture/classify error → treat as NOT waiting (reap) so a broken pane never wedges
    a slot forever (OR — operator's call — log + skip; pick the conservative reap to avoid leaks, but
    document it).
- **Signal the user** that an agent is WAITING:
  - `src/kanbanmate/core/stage_comment.py`: a WAITING header variant — `⏳ <stage> — waiting for your
input` (replaces the `🟡 in progress` header while waiting), so the GitHub issue shows it.
  - `src/kanbanmate/app/status_reporter.py` + `core/status_update.py`: render WAITING agents
    distinctly on the dashboard — a `⏳ waiting for input` marker on the agent line, and the overall
    status pill = `AT_RISK` when any agent is WAITING (it needs human attention). (Distinct from a
    truly-stale/hung agent.)
- Tests: reaper sets WAITING (no reap/relaunch) when the pane shows a waiting marker + stale
  heartbeat; reaper reaps when stale + idle/no-marker pane; a WAITING ticket whose heartbeat refreshes
  returns to RUNNING; a WAITING ticket whose session died is reaped; the stage header + dashboard
  render the WAITING signal; `is_waiting_for_input` unit tests (positive markers + bare-`❯` negative).

**Acceptance:** `make check` green; a stale agent at an interactive prompt is marked WAITING (not
reaped/relaunched) and signalled (sticky ⏳ + dashboard AT_RISK + "waiting for input"); a stale idle
agent is still reaped; WAITING→RUNNING on heartbeat refresh; WAITING→reap on dead session.

## Sub-phases

- **27.1** — Fix A (`sessions.py` idempotent launch + test). Small.
- **27.2** — Fix B (domain WAITING + pure `is_waiting_for_input` + reaper logic + stage_comment +
  status_reporter/status_update signalling + tests).

### Phase gate (per sub-phase + final)

`rm -rf .mypy_cache && make check` green; diff confined to the sub-phase files (NEVER the helm prep /
ROADMAP / IMPLEMENTATION / the phase-27 plan); `python -c "import kanbanmate"` smoke. Then restart the
live daemon so A + B go live before re-testing #91.
