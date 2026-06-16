# Implementation Progress — health-field (per-card "Health" GitHub single-select field)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: health-field — a per-card "Health" single-select FIELD carrying the operator's own
vocabulary (`INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE`) as native GitHub chips, maintained
by the daemon ON CHANGE (a workaround for GitHub's fixed, un-renameable status-update pill enum)
**Version bump**: minor (Y+1)
**Branch**: `feat/health-field`
**PR merge**: manual (human-only)
**PR**: _(created after the gate)_
**Design**: `docs/features/health-field/DESIGN.md`
**Master plan**: _(single feature branch — sub-phases below)_

## Phases

| Phase | Scope | Status | Commit |
|-------|-------|--------|--------|
| 1 | core + ports + types: pure `core/health.compute_health` + option specs; `HealthField` value object; `ProjectHealthReporter` port + `StateStore` Protocol health methods | DONE | `feat(health-field): per-card Health single-select field maintained by the daemon` |
| 2 | GraphQL surface: `_queries.create_project_field_single_select` (the only new query) + `_parsers.parse_health_field` / `parse_created_single_select_field` | DONE | (same commit) |
| 3 | client: `_health.ensure_health_field` helper + `GithubClient.ensure_health_field` / `set_item_health` (reuses `move_item`); cached `_health_field` | DONE | (same commit) |
| 4 | store mixin: `fs_health_state.HealthStateMixin` (field id/options + per-card last-written + rebind clear), mixed into `FsStateStore` (`health/` dirs) | DONE | (same commit) |
| 5 | app step + tick wire: `app/health_reporter.apply_health` (on-change, fail-soft, rebind guard) + tick Step 4e; `health_reporter` on `Deps` + `wiring`; `_NullStatusReporter` moved to `status_reporter.py` (actions.py LOC headroom) | DONE | (same commit) |
| 6 | init surface: best-effort `ensure_health_field` after `ensure_columns` (non-fatal) | DONE | (same commit) |
| 7 | tests + docs: pure mapping, parsers/queries, client ensure/set, store mixin, app on-change/fail-soft/multi-root/rebind, tick wiring; DESIGN doc + this row | DONE | (same commit) |

## Behaviour deltas (gate requirement)

- **New per-card "Health" single-select field.** The daemon find-or-creates a custom "Health" field
  (5 options, operator colours: ACTIVE=GREEN, WAITING=YELLOW, BLOCKED=RED, INACTIVE=GRAY,
  COMPLETE=PURPLE) and sets each card's Health every tick — but ONLY when the computed value CHANGED
  (the on-change discipline; per-card last-written value persisted under `<root>/health/last/`).
- **Pure per-card mapping** (`core/health.compute_health`): WAITING agent → WAITING; RUNNING agent →
  ACTIVE; no agent + Blocked column → BLOCKED; no agent + Done column → COMPLETE; otherwise INACTIVE.
  First-match-wins; the Blocked/Done column keys come from `TickConfig` (not hardcoded).
- **Idempotent provisioning, zero manual step.** First tick post-merge/restart ensures the field
  (creates it once); the field id + option ids are persisted in the STORE (board-wide,
  per-kanban-root) so every later tick is a cache hit. `kanban init` also best-effort ensures it.
- **Fail-soft.** The whole Health step + each per-card write swallow every exception (logged WARNING)
  — it NEVER raises into the tick or blocks a launch (mirrors `report_status`).
- **Multi-root.** Markers live under each daemon's own `<root>/health/`; a project-rebind guard drops
  stale ids when the registry is re-pointed. Both `~/.kanban` and `~/.kanban-km` get their own field.
- **GraphQL reuse.** Only `createProjectV2Field` is new; the read reuses `status_option_map`, the SET
  reuses `move_item` (`updateProjectV2ItemFieldValue`), and the reconcile reuses
  `update_status_field_options` (a generic single-select REPLACE preserving option ids).

See `docs/features/health-field/DESIGN.md` for the full delta.

## Next action

**Phase gate green** (`make check`: ruff + ruff format --check + mypy + 1619 tests + size guard, exit
0). Awaiting human review + merge (merge is human-only). The operator redeploys the daemons after
merge; the "Health" field then auto-appears on the next tick of each daemon (zero manual step).

---

# Follow-up — firm-exit (reaper clean-termination robustness)

> Focused engine bugfix on branch `fix/end-session-robust` (SemVer **patch / Z+1**). A separate,
> standalone fix from the health-field feature above — extends the clean-termination (#1) reaper
> done-exit so a finished brainstorm/plan agent is reliably terminated. DESIGN delta:
> `docs/features/clean-termination/DESIGN.md` §8.x (firm-exit follow-up).

## Phases

| Phase | Scope | Status | Commit |
|-------|-------|--------|--------|
| 1 | adapter + port: robust `TmuxSessions.end_session` (Escape→C-u→C-d→C-d, sleeper-seam delays, BSpace fallback, no kill-session) + new `Sessions.kill_repl_process` (pane-PID → claude child → SIGTERM, fail-soft) + its `Sessions` Protocol method | DONE | `fix(reaper): robust end_session + kill-escalation for finished agents` |
| 2 | store: `AgentBreadcrumbsMixin` `end_attempts/` counter (`get_end_attempts`/`bump_end_attempt`/`clear_end_attempts`) + `StateStore` Protocol stubs; `FsStateStore.__init__` dir + `purge_ticket` unlink (both paths) | DONE | (same commit) |
| 3 | reaper: `MAX_END_ATTEMPTS`=3; `_end_done_session` bounded-retry-then-kill escalation (dispatch+bump < MAX, keep breadcrumb; kill_repl_process + clear at MAX); `_reset_stale_end_attempts` defensive not-done reset; Approach A intact | DONE | (same commit) |
| 4 | prompt tweak: shared `_CLEAN_STOP` appended to all 8 `kanban-done` launch prompts | DONE | (same commit) |
| 5 | tests + DESIGN delta + this row: robust end_session order + delays; kill_repl_process SIGKILL-not-session + 4 fail-soft paths; counter mixin (8); reaper escalation/retry/reset (7); clean-stop in all 8 prompts | DONE | (same commit) |
| 6 | SIGKILL hardening (branch `fix/escalation-sigkill`, patch Z+1): `kill_repl_process` sends `signal.SIGKILL` (not SIGTERM) to the comm-verified `claude` child — SIGTERM was trapped/survived by a finished REPL with a background shell, re-parking WAITING; SIGKILL guarantees termination while the pane shell still runs the `; kanban-session-end` wrapper. Test + docs updated. | DONE | `fix(reaper): SIGKILL (not SIGTERM) on kill-escalation so a finished REPL with background shells always dies` |

## Behaviour deltas (gate requirement)

- **Robust `end_session`.** Escape (close the slash-command menu) → C-u (clear the box) → C-d → C-d
  (the second confirms exit past "N shells still running"), with small `sleeper`-seam delays
  (0.3/0.3/0.5s, worst-case 1.1s < 1.5s budget). Fixes the helm #5 NO-OP where a leftover
  `/implement:plan` + background shells blocked the old two-key `C-c`/`C-d`. Never `kill-session`.
- **`kill_repl_process` escalation primitive.** SIGKILLs the `claude` REPL child (resolved via
  `tmux list-panes` pane-PID → `pgrep`/`ps` child), NOT the session/shell, so the surviving shell
  still runs `; kanban-session-end`. Fail-soft on every resolution/kill error. SIGKILL (not SIGTERM,
  fixed on `fix/escalation-sigkill`): a finished REPL with a background shell traps/survives SIGTERM
  and re-parks WAITING; SIGKILL cannot be trapped → guaranteed termination, pane shell still runs the
  wrapper. Runs only AFTER `MAX_END_ATTEMPTS` graceful keystroke dispatches have failed.
- **Bounded-retry-then-kill (REVERSES the SINGLE-SHOT contract).** The reaper re-dispatches
  `end_session` each tick (KEEPING the done breadcrumb + bumping a persisted `end_attempts/<issue>`
  counter) until the REPL exits or `MAX_END_ATTEMPTS`=3 is hit → then it kills the REPL process and
  clears both markers. A failed dispatch does not bump/clear (retries the same attempt). Counter reset
  on `purge_ticket` (both paths) + a defensive not-done sweep reset.
- **Approach A preserved.** Only ever acts on a done + IDLE + ALIVE session; a WORKING/not-done/dead
  session is never exited or REPL-killed by this branch.
- **`_CLEAN_STOP` prompt instruction.** Belt-and-suspenders on all 8 `kanban-done` prompts: end the
  turn immediately after `kanban-done`, no next-stage command, no trailing background shells.

See `docs/features/clean-termination/DESIGN.md` §8.x for the full delta.

## Next action

**Phase gate green** (`make check` exit 0; `python -c "import kanbanmate"` OK). Awaiting human review +
merge (merge is human-only). The operator redeploys the daemons after merge; finished brainstorm/plan
agents then terminate reliably (robust keystrokes + REPL-kill escalation).

---

# Follow-up — Robustness batch 1 (five contained, lifecycle-design-independent fixes)

> Focused engine bugfix batch on branch `fix/robustness-batch-1` (SemVer **patch / Z+1**). Five
> clearly-correct, independent robustness fixes surfaced by an audit of the 2026-06-16 board-fix
> arc (clean-termination + reaper end_session/SIGKILL + Health field + km-root helper fix). Each is
> contained and does NOT depend on any open lifecycle-design decision. FIX 5 is DEFERRED (no
> daemon-side body-write hook to reuse — see its row + the deferred design below).

## Fixes

| # | Scope | Status | Commit |
|---|-------|--------|--------|
| 1 | multi-root completeness: route the three MISSED agent helpers (`bin/kanban_comment.py`, `bin/kanban_update_body.py`, `bin/kanban_update_main.py`) through `bin/_pin._registry_root()` so they resolve the registry from `$KANBAN_ROOT` (not hardcoded `~/.kanban`), mirroring `kanban_move`/`kanban_progress`/`kanban_session_end` | DONE | `aa9f376` fix(bin): root-aware registry resolution for comment/update-body/update-main helpers |
| 2 | done-breadcrumb clear-at-launch: clear `done/<issue>` + `end_attempts/<issue>` (fail-soft) in `LaunchAction.execute` (before the running-state save) and `reaper._try_relaunch` (before the bump-save), so a fresh session's done-exit gate depends only on its own `kanban-done` | DONE | `42c3d29` fix(launch): clear stale done/end_attempts breadcrumbs at fresh-session launch + relaunch |
| 3 | done-sticky finalize ✅: `bin/kanban_session_end.py` reads the DONE breadcrumb (`recent_agent_done`) BEFORE `purge_ticket` and finalizes ✅ done when EITHER advance OR done is present; ⚠️ interrupted ONLY when NEITHER (a clean advance:stop stage no longer shows ⚠️) | DONE | `e3d7b58` fix(session-end): done-without-advance finalizes done sticky, not interrupted |
| 4 | tick resilience on probe failure: wrap `cheap_probe()` in try/except in `tick()`; on failure log + skip snapshot+diff+decide (no new launches) but STILL run reap + done-exit + drain + heartbeat + report/health; `last_probe` left unchanged so the next tick re-probes | DONE | `314e542` fix(tick): degrade probe failure to no-new-launches instead of skipping the whole tick |
| 5 | body-top current-status header ("pinned" equivalent) | **DEFERRED** | — (concrete design below) |

## Behaviour deltas (gate requirement)

- **FIX 1 — multi-root completeness.** The km-worktree-helper-root fix (#1) had missed three agent
  helpers that still resolved `projects.json` from the import-time-frozen `~/.kanban`
  (`DEFAULT_KANBAN_ROOT`); on the `kanban-km` daemon (`$KANBAN_ROOT=~/.kanban-km`) they acted on the
  WRONG repo. `kanban_comment`/`kanban_update_body` now resolve the registry via
  `_projects_path(_registry_root())` (identical to `kanban_move`); `kanban_update_main`'s
  `_resolve_from_registry` lazy-imports `_registry_root`. None of the three use an `FsStateStore`, so
  the registry root is the whole change. The `~/.kanban` fallback (unset `$KANBAN_ROOT`) is preserved.
- **FIX 2 — fresh-session breadcrumb hygiene.** A stale `done/<issue>` (1800s TTL) or
  `end_attempts/<issue>` counter from stage N could survive into stage N+1 and make the reaper
  done-exit the FRESH agent prematurely. `LaunchAction.execute` and `reaper._try_relaunch` now clear
  both (each independently fail-soft) before persisting the running state, so the new session's
  done-exit gate depends ONLY on its own `kanban-done`. The relaunch path reuses the slot (no
  `purge_ticket`), so these clears are the only reset there — exactly the gap.
- **FIX 3 — done-without-advance finalizes ✅, not ⚠️.** The advance:stop stages
  (brainstorm/design/plan) complete cleanly via `kanban-done` (a DONE breadcrumb) and NEVER advance
  their card, so `kanban-session-end` was wrongly showing ⚠️ interrupted. It now reads the DONE
  breadcrumb BEFORE `purge_ticket` (same load-bearing ordering as the advance breadcrumb — purge
  clears `done/<issue>` too) and finalizes ✅ done when EITHER advance OR done is present; ⚠️
  interrupted is now reserved for NEITHER present (a genuine crash/interrupt). The advance→✅ path
  (daemon already finalized) is untouched.
- **FIX 4 — tick probe-failure resilience.** `cheap_probe()` was outside the try/except, so a
  transient GitHub 401/403/5xx on the probe raised out of `tick()` and skipped the ENTIRE tick —
  reap, done-exit, drain, heartbeat and health all stranded (a finished agent + a freed slot waited
  for the backoff window). The probe is now wrapped: a failure logs + sets a `probe_failed` flag that
  gates out the snapshot+diff+decide (the launch path) while every post-step still runs. `last_probe`
  is left at the prior token, so the next tick re-probes and recovery re-triggers a snapshot.
  `snapshot_taken` stays `False` (same as an unchanged board), so the daemon-loop cadence backoff is
  unchanged.
- **FIX 5 — DEFERRED.** A body-top current-status header at every transition is cross-cutting: there
  is NO daemon-side body-write hook to reuse (every stage finalizer writes TIMELINE COMMENTS via
  `app/stage_signal.upsert_stage_comment`; body writes live only in the `kanban-update-body` agent
  helper + the `Seeder` Protocol, with `Deps.seeder` defaulted `None` and not threaded into the stage
  producers). Implementing it safely needs (a) a new pure `core/body_edit.set_status_header` helper
  preserving the `**roadmap**`/`**codename**`/`**design**`/`**plans**` markers + `## Brainstorm`, (b)
  a new fail-soft `app/body_status.py` orchestrator (`fetch_issue` → pure transform → `update_issue_body`,
  body-diff-gated, no-op when `seeder is None`), (c) threading a body-writer port through `Deps`/wiring,
  and (d) 5 fail-soft wires across `actions.py`/`tick.py`/`reaper.py`/`bin/kanban_session_end.py` (all
  at/near the 1000-LOC ceiling). Per the task instruction, FIXES 1-4 are implemented fully and FIX 5
  is deferred with the concrete design below. **Risk to carry into the FIX-5 PR**: `update_issue_body`
  replaces the WHOLE body, so a daemon header write could race an agent's `kanban-update-body
  --set-field` (last-writer-wins) — keep the header write idempotent + body-diff-gated, region-disjoint
  from the markers, and adversarially test marker/section preservation.

### Deferred FIX 5 — concrete design (for a future contained PR)

- **Delimiter + block.** A single idempotent block at the VERY TOP of the body, fenced by HTML
  comments so it never collides with the `**key**: value` markers or `## Brainstorm`:
  `<!-- kanban:status:begin -->` … `<!-- kanban:status:end -->`. Shows stage key + state
  (running/done/blocked/waiting/interrupted) + short summary + UTC timestamp.
- **Pure core helper** `core/body_edit.set_status_header(body, *, stage, state, summary, ts) -> str`
  (190-LOC module, wide headroom): replace an existing `begin…end` block in place; prepend a fresh
  block when absent; leave everything below `end` byte-identical; no-op-equivalent on identical input.
- **Fail-soft app orchestrator** `app/body_status.update_status_header(seeder, issue, *, stage, state,
  summary, now)` (~60 LOC new module): `fetch_issue` → `set_status_header` → `update_issue_body`,
  wholly fail-soft, no-op when `seeder is None`, body-diff-gated (skip the PATCH when new == fetched).
- **Wire at the 5 transition points**, each a single fail-soft call mirroring the existing
  `upsert_stage_comment` calls: `actions.LaunchAction.execute` (running) · `bin/kanban_session_end.py`
  ⚠️ branch (interrupted) + the FIX-3 ✅ branch (done) · `reaper` ⛔ flip (blocked) + `_enter_waiting`
  (waiting) · advance ✅ via `tick._finalize_left_stage` (done). Thread `deps.seeder` (already on
  `Deps`) into the app-layer producers; for the bins, the existing `GithubClient` already implements
  `Seeder`.

## Next action

**Phase gate green** (`make check` exit 0; `python -c "import kanbanmate"` OK). Awaiting human review +
merge (merge is human-only). FIXES 1-4 ship in this batch; FIX 5 is a deferred follow-up with the
concrete design above.
