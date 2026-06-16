# KanbanMate — clean-termination — Design Delta

> **Type**: bug fix (engine). **Branch**: `fix/clean-termination`.
> **Grounded against**: HEAD `51bf13a` (branch `main`).
> This is a focused DESIGN delta for two engine bugs (#1 clean agent termination via Option 1, and
> #3 status-update English-only). It documents only the behaviour that changed; the full engine
> design lives in `docs/archive/features/genesis/DESIGN.md`.

## §8.x — Agent termination (Option 1: engine-driven clean termination) — #1

### The bug

Every per-transition launch prompt ended with prose ("End the session" / "end the session"), but
the agent runs an INTERACTIVE `claude` REPL:

```
[export KANBAN_ROOT=<root>; ] export PATH=<bin>:"$PATH"; claude --session-id <uuid> … ; kanban-session-end <issue>
```

In interactive auto-mode the model can only end its TURN, not exit the REPL. A finished agent
printed "Ending the session" and then `claude` IDLED FOREVER, so the trailing
`; kanban-session-end <issue>` never ran: the slot was never freed, state never purged, the sticky
never finalized, and the card could not advance. ALL autonomous stages were affected. The teardown
machinery (`bin/kanban_session_end.py`) was correct; it just never fired.

### The fix (Option 1 — operator decision)

1. **The agent's terminal step is now a concrete command**: `kanban-done <issue>` (replacing the
   no-op prose). It drops a persisted DONE breadcrumb keyed by the issue number
   (`StateStore.record_agent_done` / `recent_agent_done` / `clear_agent_done`; the fs adapter
   marker is `done/<issue>` = `{"ts": now}`, TTL `_DONE_TTL` = 1800 s — the reaper HEARTBEAT_TTL
   horizon, so a done signal a hung daemon never consumed still ages out). The advance/done
   breadcrumb methods live in `adapters/store/fs_breadcrumbs.py::AgentBreadcrumbsMixin` (a
   behaviour-preserving extraction keeping `fs_store.py` under the 1000-LOC ceiling).
2. **The reaper exits a DONE + IDLE alive session.** Each tick, for an ALIVE session whose done
   breadcrumb is present AND whose pane is IDLE (no `esc to interrupt` running-turn footer), the
   reaper calls the new `Sessions.end_session(name)` (C-c then C-d → `claude` exits), so the trailing
   `; kanban-session-end <issue>` fires → teardown → the card flows. This branch runs AHEAD of the
   Approach-A WAITING parking and applies to BOTH fresh+alive and stale+alive done agents.

**Approach A is preserved EXACTLY.** A NOT-done alive session, or a done-but-WORKING session (the
active-turn probe fails CLOSED to "active" on any error), falls through to the unchanged WAITING /
fresh handling and is NEVER exited. A DEAD session is reaped as before. The reaper never kills a
live session; `end_session` is a clean REPL exit (C-c/C-d), NOT `kill` (which would prevent the
trailing wrapper from running).

**SINGLE-SHOT dispatch contract.** The done-exit is dispatched AT MOST ONCE per agent. After a
SUCCESSFUL `end_session` dispatch the reaper CLEARS the done breadcrumb (`clear_agent_done`,
fail-soft) so a subsequent tick no longer re-enters the done-exit branch. This is load-bearing:
`claude` may exit slowly AND the out-of-band `; kanban-session-end` then does multi-second GitHub
I/O — during that window the tmux session is STILL ALIVE with no active turn, so a naive reaper
would re-send `C-c`/`C-d` and could INTERRUPT `kanban-session-end` mid-teardown (leaving state
half-purged). With the breadcrumb cleared, a still-alive-but-stale session instead parks WAITING via
the Approach-A path on the next tick (non-destructive, operator-visible). A FAILED dispatch does NOT
clear the breadcrumb — `kanban-session-end` was never triggered, so there is no collision risk and
the next tick simply retries the exit. The active-turn probe scans only the trailing
`SUBMIT_SCAN_LINES` (~30) lines, so a stale `esc to interrupt` line left in scrollback cannot
false-positive "active" and block the exit forever.

`purge_ticket` purges the `done/<issue>` breadcrumb on BOTH teardown paths (`keep_budgets=True` and
`False`) so a done signal never leaks past teardown.

## §8.3 — Workspace ports — `Sessions.end_session(name)` — #1

New `Sessions` Protocol member. Contract: cleanly EXIT the `claude` REPL WITHOUT
`tmux kill-session`. The adapter (`TmuxSessions.end_session`) sends two SEPARATE `send-keys` events
— `C-c` (clear partial input) then `C-d` (EOF → `claude` exits at the idle prompt) — both as tmux
KEY NAMES (no `-l`). It MUST NOT call `kill-session`, or the trailing `; kanban-session-end` would
never run.

## §4.x — `KANBAN_ROOT` injection for non-default daemons (km-worktree-helper-root fix) — #1

The kanban-* helpers (`kanban-session-end`, `kanban-done`, `kanban-move`, `kanban-progress`)
defaulted to `~/.kanban`, wrong for a non-default daemon (e.g. the kanban-km daemon at
`~/.kanban-km`). Without this fix the trailing `; kanban-session-end` and the agent's helpers read
the WRONG root on a non-default daemon, so the #1 fix would silently no-op there.

The minimal seam: the launching daemon's runtime root is threaded onto `Deps.kanban_root` (from
`WiringConfig.kanban_root`), and `LaunchAction._agent_command` prefixes
`export KANBAN_ROOT=<quoted root>; ` on the launched command — ONLY when non-empty, so the default
`~/.kanban` daemon keeps a byte-identical command line. `bin/_pin.py::resolve_kanban_root()` reads
`$KANBAN_ROOT` (None when unset); `kanban_done`, `kanban_session_end`, `kanban_move`, and
`kanban_progress` build `FsStateStore(resolve_kanban_root())` and resolve their `projects.json`
registry from the same root. The reaper's own `end_session` is engine-side and already uses the
correct root via `deps`.

`kanban-done` is provisioned into every worktree's `.claude/kanban-bin` (`_KANBAN_HELPER_BINS`) and
allowed in ALL FOUR permission profiles (`docs` / `prepare` / `dev` / `check`) — it is the universal
terminal action.

## §8.7 — Status update body is ENGLISH; enum mapping corrected — #3

`core/status_update.py` rendered the rolling GitHub status-update BODY in FRENCH. It is a published
GitHub artifact, so all user-facing strings are now ENGLISH ("No agents running.", "Agents running",
"Recent events", "No recent events.", "started", "profile", "→ to reply:", straight-quoted progress,
"pill forced by the operator", "Operator note"). The DOMAIN health vocabulary
(`INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE`) is unchanged.

The stale module docstring/comment claiming GitHub's enum is `ACTIVE→ACTIVE, WAITING→WAITING,
BLOCKED→BLOCKED` was corrected: the real `ProjectV2StatusUpdateStatus` enum is
`INACTIVE / ON_TRACK / AT_RISK / OFF_TRACK / COMPLETE`, and the adapter
(`adapters/github/client.py::_HEALTH_TO_GITHUB_STATUS`) maps `ACTIVE→ON_TRACK`, `WAITING→AT_RISK`,
`BLOCKED→OFF_TRACK` (INACTIVE / COMPLETE unchanged).
