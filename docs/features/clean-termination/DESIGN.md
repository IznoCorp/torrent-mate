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

**SINGLE-SHOT dispatch contract (SUPERSEDED — see §8.x firm-exit follow-up below).** The done-exit
was originally dispatched AT MOST ONCE per agent: after a SUCCESSFUL `end_session` the reaper cleared
the done breadcrumb so a later tick could not re-send `C-c`/`C-d` into an in-flight
`; kanban-session-end`. The helm #5 live finding (2026-06-16) showed that single dispatch could
NO-OP entirely — a finished brainstorm/plan agent left a `/implement:plan` slash-command in the input
box (autocomplete open) and "N shells still running", so a naive two-key `C-c`/`C-d` never landed on
an idle empty prompt; the single-shot clear then CONSUMED the done breadcrumb and the finished agent
parked WAITING **forever**. The contract is therefore **REVERSED** to a bounded-retry-then-kill
escalation — see the **§8.x firm-exit follow-up** section below for the robust `end_session` sequence,
the `MAX_END_ATTEMPTS` counter, and the `kill_repl_process` escalation. The active-turn probe scans
only the trailing `SUBMIT_SCAN_LINES` (~30) lines (unchanged), so a stale `esc to interrupt` line in
scrollback cannot false-positive "active" and block the exit forever.

`purge_ticket` purges the `done/<issue>` breadcrumb on BOTH teardown paths (`keep_budgets=True` and
`False`) so a done signal never leaks past teardown.

## §8.3 — Workspace ports — `Sessions.end_session(name)` — #1

New `Sessions` Protocol member. Contract: cleanly EXIT the `claude` REPL WITHOUT
`tmux kill-session`. It MUST NOT call `kill-session`, or the trailing `; kanban-session-end` would
never run. The keystroke sequence is now the ROBUST firm-exit sequence (the original two-key
`C-c`/`C-d` was too weak) — see §8.x below.

## §8.x — Reaper clean-termination robustness (firm-exit follow-up)

The §8.x SINGLE-SHOT contract above is **REVERSED** here. Live finding (helm #5, 2026-06-16): a
finished brainstorm/plan agent runs `kanban-done` correctly but the deployed two-key `end_session`
(`C-c` then `C-d`, no delay, single EOF) NO-OPs because the agent leaves **(a)** a `/implement:plan`
slash-command in the input box (autocomplete open) and **(b)** "N shells still running" (claude needs
a SECOND `C-d` to confirm exit). The single-shot clear then consumed the done breadcrumb and the
finished agent parked WAITING forever (cleared manually twice). This blocked the autonomous lifecycle
for every brainstorm/plan stage. The fix has three parts:

### Robust `end_session` keystroke sequence (`TmuxSessions.end_session`)

`Escape` → sleep(`_END_MENU_DELAY`=0.3s) → `C-u` → sleep(`_END_CLEAR_DELAY`=0.3s) → `C-d` →
sleep(`_END_CONFIRM_DELAY`=0.5s) → `C-d`. `Escape` closes the slash-command autocomplete/menu; `C-u`
clears the input line so the EOF lands on an EMPTY idle prompt; the FIRST `C-d` may only surface the
"N shells still running, press again to exit" confirm, and the SECOND `C-d` confirms past the
background-shell warning. Every `send-keys` stays `check=True`; each event is a tmux KEY NAME (no
`-l`). Delays route through the existing `sleeper` seam (offline unit tests pay zero wall time); the
worst-case wall time is 1.1s, well under the ~1.5s budget — and the sequence runs only once per
finished session, rarely, from the reaper sweep. A **BSpace burst** fallback (`_END_BSPACE_BURST`=64
× `BSpace` via `_clear_input_line`) is documented for the case where `C-u` proves unreliable on the
live claude widget (a one-line swap). The **no-`kill-session` invariant is restated**: the trailing
`; kanban-session-end` must still run.

### `Sessions.kill_repl_process(name)` — escalation primitive

New `Sessions` Protocol member. SIGKILLs the `claude` REPL **child** of the pane's shell — NOT the
session/shell. It resolves the pane shell PID (`tmux list-panes -t <name> -F '#{pane_pid}'`), finds
its child (`pgrep -P <pane_pid>`, with a `ps -o ppid=,pid= -A` scan fallback; when several children
exist it prefers the one whose `comm` contains `claude`), and `os.kill(child, SIGKILL)`. The REPL
dies but the SURVIVING shell still runs the trailing `; kanban-session-end <issue>` → teardown fires.
It MUST NOT `kill-session` (kills the shell, the wrapper never runs) and MUST NOT kill the shell PID.
FAIL-SOFT: any resolution/kill error is swallowed (the reaper logs and still clears the breadcrumb).

**Why SIGKILL, not SIGTERM (RESOLVED — was the residual below).** The first cut sent SIGTERM and a
known residual remained: a finished `claude` REPL with a background shell still running (the
"N shells still running" exit confirm) **traps/survives SIGTERM**, so the agent never terminated and
re-parked WAITING. This escalation only ever runs AFTER `MAX_END_ATTEMPTS` graceful keystroke
dispatches (Escape → `C-u` → `C-d` → `C-d`) have already failed, so graceful was given every chance —
SIGKILL is the guaranteed-termination escalation (it cannot be trapped). A live test confirmed a
manual SIGKILL of the same comm-verified `claude` PID killed the REPL cleanly while the surviving pane
shell still ran the trailing `; kanban-session-end <issue>` wrapper (state purged on the correct
root). Because ONLY the `claude` child is killed (never the session, never the pane shell PID), the
pane shell still runs the wrapper → teardown still fires.

### Reaper bounded-retry-then-kill escalation (`_end_done_session`)

A per-session attempt counter replaces the single-shot clear. New issue-keyed marker
`end_attempts/<issue>` = `{"n": <int>}` on `AgentBreadcrumbsMixin`
(`get_end_attempts`/`bump_end_attempt`/`clear_end_attempts`, on the `StateStore` port too). Logic:

* **attempts < `MAX_END_ATTEMPTS` (=3)** — dispatch the robust `end_session`, BUMP the counter, and
  **KEEP** the done breadcrumb so the next tick re-dispatches. A FAILED dispatch returns without
  bumping or clearing (the keystrokes never reached claude → no `; kanban-session-end` collision; the
  next tick retries the SAME attempt number).
* **attempts >= `MAX_END_ATTEMPTS`** — ESCALATE: `kill_repl_process` SIGKILLs the claude child, then
  CLEAR the done breadcrumb AND the attempt counter (whether or not the SIGKILL landed — the graceful
  budget is spent). The next tick falls through to Approach A: the still-dying session parks WAITING
  (non-destructive) until it dies → reaped, or `kanban-session-end` purges its state.

**Counter reset.** Two points: (1) `purge_ticket` ALWAYS unlinks `end_attempts/<issue>` (a RUNTIME
marker, both `keep_budgets` paths) — the primary reset on every teardown/session-end; (2) a defensive
reset in the reaper sweep (`_reset_stale_end_attempts`) clears a lingering counter when a NOT-done
session is processed (e.g. a daemon restart mid-escalation), so a future done cycle on the same ticket
starts clean. **Approach A is preserved exactly**: this whole branch only ever runs for a done +
IDLE (no active turn) + ALIVE session — a WORKING/not-done session is never exited or killed.

### `_CLEAN_STOP` prompt instruction (belt-and-suspenders)

A shared `_CLEAN_STOP` constant is appended to all 8 launch prompts whose terminal step is
`kanban-done` (`_BRAINSTORM`/`_DESIGN`/`_PLAN`/`_PREPARE`/`_IMPLEMENT`/`_FIXCI`/`_REVIEW`/`_REWORK`):
"AFTER running kanban-done, END your turn IMMEDIATELY — do NOT type/suggest/run the next-stage command
(e.g. /implement:plan), and do NOT leave background shells running (no trailing `&`)." This reduces
the leftover-box + background-shell condition at the source; the engine fix above is the guarantee.
The illustrative `(e.g. /implement:plan)` is NEGATIVE example text, not a runnable command.

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

## Robustness batch 1 — five contained fixes (branch `fix/robustness-batch-1`)

An audit of this arc surfaced five clearly-correct, independent robustness fixes (none depends on
an open lifecycle-design decision). FIXES 1-4 shipped in this batch; FIX 5 shipped subsequently in
the zero-deferrals batch (v0.3.0) — see "FIX 5 — DONE" below.

### FIX 1 — multi-root completeness (extends §4.x)

The §4.x km-root fix had missed three agent helpers — `bin/kanban_comment.py`,
`bin/kanban_update_body.py`, `bin/kanban_update_main.py` — that still resolved `projects.json` from
the import-time-frozen `~/.kanban` (`DEFAULT_KANBAN_ROOT`). On the `kanban-km` daemon they acted on
the WRONG repo. They now resolve the registry via `_projects_path(_registry_root())`
(`comment`/`update_body`, mirroring `kanban_move`) or a lazy `_registry_root` import
(`update_main._resolve_from_registry`). None uses an `FsStateStore`, so the registry root is the
whole change; the `~/.kanban` fallback (unset `$KANBAN_ROOT`) is preserved.

### FIX 2 — fresh-session breadcrumb hygiene (extends §8.x firm-exit)

A stale `done/<issue>` (1800s TTL) or `end_attempts/<issue>` counter from stage N could survive into
stage N+1 and make the reaper done-exit the FRESH agent prematurely. `LaunchAction.execute` and
`reaper._try_relaunch` now clear both (each independently fail-soft) before persisting the running
state, so a new session's done-exit gate depends ONLY on its own `kanban-done`. `_try_relaunch`
reuses the slot (no `purge_ticket`), so these clears are the only reset on the relaunch path.

### FIX 3 — done-without-advance finalizes ✅ (extends §8.1.f split)

The advance:stop stages (brainstorm/design/plan) complete cleanly via `kanban-done` (a DONE
breadcrumb) and NEVER advance their card, so `kanban-session-end` was wrongly showing ⚠️ interrupted.
It now reads the DONE breadcrumb (`recent_agent_done`) BEFORE `purge_ticket` (same load-bearing
ordering as the advance breadcrumb — purge clears `done/<issue>` too) and finalizes ✅ done when
EITHER advance OR done is present; ⚠️ interrupted is now reserved for NEITHER present (a genuine
crash/interrupt). The advance→✅ path (daemon already finalized via §8.1.e) is untouched.

### FIX 4 — tick probe-failure resilience, reconciled with the circuit-breaker (extends §3.1 / §5 poll loop)

`cheap_probe()` was called outside the try/except, so a transient GitHub 401/403/5xx on the probe
raised out of `tick()` and skipped the ENTIRE tick — reap, done-exit, drain, heartbeat and health all
stranded (a finished agent + a freed slot waited for the backoff window). The probe is now wrapped, but
the wrap must satisfy TWO goals that initially conflicted:

* **(a) don't strand finished agents** — a probe failure sets a `probe_failed` flag that gates out the
  snapshot+diff+decide (the launch path) while EVERY post-step (reap / done-exit / drain / intents /
  heartbeat / health) still runs. `last_probe` is left at the prior token so the next tick re-probes and
  recovery re-triggers a snapshot.
* **(b) don't mask the failure** — the first cut returned a clean `TickResult` and swallowed the
  exception, so the daemon loop counted the poll as a SUCCESS: it reset `consecutive_failures` to 0,
  cleared the DEGRADED sentinel, and wrote `last_tick_ok=True` every tick. A dead token / DNS outage then
  looked perfectly healthy — full-cadence polling forever, doctor + monitor **D3** green — which defeats
  the §5 circuit-breaker and the dead-token observability (#1/#2).

Reconciliation: `tick()` carries the failure back on the result (`TickResult.probe_failed` +
`probe_error`, the original exception). The daemon loop (`daemon/loop.py`) treats a returned tick with
`probe_failed=True` as a FAILED poll — it increments `consecutive_failures` (NOT reset), leaves the
DEGRADED sentinel in place, and runs `_log_actionable_auth_failure(probe_error)` for the 401/403
breadcrumb, exactly as it does for a tick that raised outright. So `last_tick_ok`/`consecutive_failures`
reflect reality: a **sustained** probe failure trips the geometric backoff at `_BACKOFF_AFTER_FAILURES`
(and surfaces FAIL to doctor/D3), while a **transient** one self-heals the next tick (the re-probe
succeeds → a clean tick resets the run to 0 and clears DEGRADED). `snapshot_taken` stays `False` so the
*idle* cadence is unaffected by the failure itself; the *failure* cadence is now driven correctly by the
backoff. Both goals hold: post-steps run AND the breaker engages.

### FIX 5 — DONE (zero-deferrals batch, v0.3.0): body-top current-status header

**Shipped** on `feat/zero-deferrals` (no longer deferred). An always-visible current-status block is
maintained at the TOP of the issue BODY (GitHub cannot pin a timeline comment), updated on each stage
transition the engine already finalizes a sticky for, fully fail-soft, idempotent, body-diff-gated,
region-disjoint from the `**roadmap**`/`**codename**`/`**design**`/`**plans**` markers and the
`## Brainstorm` section. As-built:

- **Pure core** — `core/body_edit.set_status_header(body, *, stage, state, summary, timestamp)`
  inserts/replaces a single `<!-- kanban:status:begin -->`/`<!-- kanban:status:end -->` delimited
  block (HTML comments → invisible, marker-disjoint, GitHub round-trip-safe). A `_STATUS_BLOCK` regex
  (`re.escape` on the literal comments, `count=1`) REPLACES an existing block in place (idempotent) or
  PREPENDS it at the top when absent. The `sub` uses a callable replacement so a summary containing
  backslashes is inserted literally (no regex backreference).
- **Fail-soft app orchestrator** — `app/body_status.update_body_status(seeder, issue, *, stage, state,
  summary, now)`: no-op when `seeder is None`; else `fetch_issue` → `set_status_header` → BODY-DIFF
  GATE (skip the write when unchanged — bounds API cost + shrinks the last-writer-wins race window) →
  `update_issue_body`. The whole body is wrapped in try/except → it can NEVER raise into the tick.
- **Wiring** — reuses the EXISTING `Seeder` surface (`fetch_issue` + `update_issue_body`) and the
  already-wired `Deps.seeder` (the production `GithubClient` satisfies `Seeder`); no port change.
- **Call sites** (each fail-soft, mirroring `upsert_stage_comment`): launch `running` from
  `app/transition_step` (NOT `actions.py`, which is at the LOC ceiling); advance `done` from
  `app/tick._finalize_left_stage`; reaper `blocked` + `waiting` (+ restore `running`) from
  `app/reaper`; session-end `done`/`blocked`/`interrupted` from `bin/kanban_session_end`.
- **Race handling** (the carried risk): `update_issue_body` replaces the WHOLE body, so a daemon
  header write can race an agent's `kanban-update-body --set-field` (last-writer-wins). The header
  region is disjoint from every `**key**:` marker, so even a losing race only stales the header region
  for one tick; the body-diff gate makes the write a no-op when unchanged. Adversarially tested:
  set-header-on-a-body-with-all-markers+`## Brainstorm` preserves every marker + the whole section
  byte-for-byte and inserts the header exactly once; a second call replaces (never duplicates).
