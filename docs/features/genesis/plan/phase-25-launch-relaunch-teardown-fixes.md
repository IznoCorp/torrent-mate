# Phase 25 — Launch / relaunch / teardown PoC-conformance fixes (e2e findings)

**Trigger:** a live e2e (operator-driven, 2026-06-10) surfaced four genesis defects, three of them
PoC-conformance regressions. The perms / interval / dashboard work is proven live; these are the
launch-path bugs that make agents non-functional.

## Findings & root causes

- **B (CRITICAL) — the agent never receives its prompt.** Genesis composes the filled prompt as a
  POSITIONAL in the launch command string (`claude … '<prompt>' ; kanban-session-end`). claude opens
  the REPL but the message is never submitted (no Enter sent _inside_ the REPL) → the agent sits idle
  at `❯`, never does a tool call, never heartbeats, gets reaped at the TTL. The **PoC** launched a
  BARE `claude`, polled capture-pane for the trust/REPL-ready markers, then **send-keys the filled
  prompt INTO the REPL + Enter** (`engine/launch.py` `start_session` + `poll_trust_dialog` +
  `_default_claude_runner`). Genesis dropped this for the positional — a regression.
- **A (CRITICAL) — the reaper relaunch is promptless.** `app/reaper.py:339` builds
  `LaunchAction(ticket=…, profile=state.profile)` — no prompt/script/permission_mode/on_fail/advance —
  and `TicketState` doesn't persist them. The PoC persisted the relaunch inputs
  (`prompt/profile/to_option_id/clone_dir/config_dir/dev_repo_path`) so the reaper could rebuild the
  exact command. Genesis drops the prompt → every relaunch is idle (confirmed: #140 relaunched 3× at
  the 1800s TTL, each idle).
- **C (minor) — `kanban cancel` leaves the card in the triggering column.** Cancel tears the agent
  down but does NOT reset the card to Backlog, leaving it in `Spec` (the daemon won't re-launch a
  sitting card, but the board state is inconsistent).
- **D (minor) — teardown `branch_delete` ordering.** `actions.py:613` calls
  `discover_branch(issue)` AFTER the worktree is removed → `git -C <gone-worktree> rev-parse` exits
  128 (caught fail-soft). Discover the branch BEFORE removing the worktree.
- **E (minor) — dashboard title renders `[#140]`** instead of the real issue title (the status
  reporter's snapshot title lookup falls back wrongly).

## Sub-phase 25.1 — Restore send-keys prompt delivery (bug B)

Port the PoC's interactive delivery. Read the PoC `engine/launch.py`
(`start_session` L171+, `poll_trust_dialog`, `_default_claude_runner`, the `_TRUST_MARKER` /
`_REPL_READY_MARKERS` / `_TRUST_POLL_ATTEMPTS` / `_TRUST_POLL_INTERVAL` constants) and
`engine/tmux.py` (`capture` / `send_keys`).

- `adapters/workspace/sessions.py` (`TmuxSessions`): add `capture(name) -> str` (`tmux capture-pane
-p`) and a `send_text(name, text, *, enter)` (or reuse send-keys) so the app can poll + type the
  prompt into the live REPL. Keep argv-list calls (no `shell=True`).
- `ports/workspace.py` (`Sessions` Protocol): widen with `capture` + the prompt-send method.
- A pure/poll helper (port `poll_trust_dialog` — bounded capture-pane poll for the trust marker OR a
  ready-REPL marker; injectable sleeper for tests) — place in `core/` if pure, or in the app launch
  flow with an injected sleeper.
- `app/actions.py` `_agent_command` / `execute`: launch **bare** claude (build_claude_argv WITHOUT
  the positional prompt — remove the `argv = [*argv, filled]` append), then: poll trust/ready →
  (send Enter if the trust dialog was seen) → **send-keys the FILLED prompt + Enter** into the REPL.
  The prompt is still filled via `_launch_context` + `fill` (fail-loud unchanged). `wrap_with_session_end`
  still wraps the bare claude command (the `; kanban-session-end` semantics are unchanged).
- Tests: drive the launch with a fake tmux (capture returns a trust marker, then a ready marker) +
  an injected sleeper; assert the prompt is typed into the REPL + Enter sent; assert a bare launch
  (no prompt) sends no prompt text.

**Acceptance:** `make check` green; a launch with a prompt send-keys the filled prompt + Enter after
the trust/ready poll; the launch command no longer carries the positional prompt; bypass guards intact.

## Sub-phase 25.2 — Persist relaunch inputs; faithful reaper relaunch (bug A)

- `ports/store.py` `TicketState`: add `prompt: str | None`, `script: str | None`,
  `permission_mode` (already present as `mode`), `on_fail: str`, `advance: str` (the relaunch inputs).
  Persist them in `actions.py` `execute` at the `store.save(TicketState(...))` site.
- `app/reaper.py` relaunch: rebuild the `LaunchAction` from the PERSISTED state — pass
  `prompt=state.prompt, script=state.script, permission_mode=state.mode, on_fail=state.on_fail,
advance=state.advance, profile=state.profile` (+ the ticket). So a relaunch re-delivers the prompt
  via the 25.1 path. Keep the empty-profile fail-loud.
- Tests: a reaper relaunch of a persisted state carries the prompt into the rebuilt LaunchAction; an
  end-to-end-ish test that the relaunch path delivers the prompt (fake tmux).

**Acceptance:** `make check` green; a relaunch reconstructs the full LaunchAction (prompt included)
from persisted state; no field regressions in the terminal-header finalizers that read TicketState.

## Sub-phase 25.3 — Cancel resets the card + teardown ordering (bugs C, D)

- `kanban cancel`: after tearing the agent down, **reset the card to the reset target (Backlog)** so
  it doesn't sit in a triggering column (mirror the Cancel→Backlog reset). Confirm the exact reset
  target from the columns/reset model; do it via the board writer (move_card).
- Teardown (`actions.py:~613`): discover the branch BEFORE removing the worktree (reorder the steps)
  so `discover_branch` doesn't run against a gone worktree. Keep the fail-soft wrapper.
- Tests: cancel moves the card to Backlog (fake board writer asserts the move); teardown discovers
  the branch first (no exit-128 path on the happy case).

**Acceptance:** `make check` green; cancel leaves the card in Backlog; teardown discovers branch
pre-removal.

## Sub-phase 25.4 — Dashboard title render (bug E)

- `app/status_reporter.py`: fix the `RunningAgent.title` resolution so it shows the real issue title
  from the snapshot board item (not the `[#<n>]` fallback). Confirm how the snapshot exposes the
  title and map it; keep a graceful fallback only when genuinely absent.
- Tests: a running agent whose snapshot has a title renders that title (not `[#n]`).

**Acceptance:** `make check` green; the dashboard body shows the real title.

### Phase gate (per sub-phase + final)

`rm -rf .mypy_cache && make check` green; diff confined to the sub-phase files (NEVER the helm prep /
ROADMAP / IMPLEMENTATION / the phase-25 plan); `python -c "import kanbanmate"` smoke. After the phase:
restart the live PM2 daemon so all four fixes go live before the next operator e2e.
