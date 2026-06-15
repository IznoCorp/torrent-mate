---
name: kanban-monitor
description: |
  Verify the KanbanMate orchestrator is fully functional — across EVERY daemon/board on the host.
  Runs a fixed health/conformity checklist (daemon liveness, engine via `kanban doctor`, board
  reachability, agent liveness + stuck-prompt detection, status-pill coherence, resilience) and
  returns a single verdict: HEALTHY / DEGRADED / BROKEN, with a DEVIATION LIST of anything wrong.
  Read-only by default; opt into safe auto-recovery with `--remediate`. Invoke with "/kanban-monitor".
  WHEN: You want to confirm the orchestrator and its agents are working (after a deploy/restart,
  during an incident, or as a periodic health sweep). Pairs with the `/kanban` CLI skill.
  WHEN NOT: A single ad-hoc lookup — use `/kanban state` or `kanban doctor` directly.
version: 1.0
---

# Kanban Monitor v1.0

Verify that **the whole KanbanMate orchestration is working** — not bug-hunting, **health/conformity
checking**. It sweeps every daemon on the host (the engine drives one project per runtime root, and a
host can run several — e.g. `~/.kanban` for one repo and `~/.kanban-km` for another), runs a fixed
checklist against each, classifies every observation, and returns ONE verdict plus a DEVIATION LIST.

It is a **thin orchestrator over the `kanban` CLI** (the same engine the `/kanban` skill wraps): it
calls `kanban doctor`, `kanban state --root <r>`, `kanban sessions`, and reads the on-disk
`daemon.heartbeat` / PM2 state. All authority lives in the engine; this skill interprets its output.

> **Paradigm**: verify everything works. Every check yields **PASS** (healthy), **WARN** (advisory /
> needs-an-operator-eye, not broken), or **FAIL** (broken — orchestration is not functioning). Only
> WARN/FAIL land in the DEVIATION LIST. A WAITING agent is **WARN** (it needs a human to answer — the
> orchestrator is fine), NOT a FAIL.

## CRITICAL RULES

1. **Read-only by default.** Without `--remediate` the skill ONLY observes + reports — it never
   restarts a daemon, reaps an agent, or sends keystrokes. (See `--remediate` below.)
2. **NEVER kill a live agent session, NEVER merge, NEVER force-push** — even under `--remediate`.
   Remediation is limited to the SAFE recoveries listed below; anything else is reported for the
   operator. This mirrors the engine's own autonomy floor (merge = human-only; the reaper never kills
   a live session).
3. **Create tasks BEFORE the sweep** — one per daemon discovered, so progress is trackable.
4. **Classify EVERY observation** as PASS/WARN/FAIL before recording it. Only WARN/FAIL enter the
   DEVIATION LIST.
5. **Sweep EVERY daemon** found in discovery — never report "healthy" from one daemon while another is
   down. The verdict is the WORST status across all daemons.
6. **Show the checklist result to the user** — a per-daemon table + the verdict + the DEVIATION LIST.

## `--remediate` flag

| Mode                | Default | Behavior                                                                                                                                                              |
| ------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Read-only (default) | YES     | Detect + classify + report. No state is changed.                                                                                                                      |
| `--remediate`       | NO      | After the report, apply ONLY the SAFE recoveries (below) to FAIL items, one at a time, re-checking after each. Anything not in the safe set is left for the operator. |

If the prompt contains `--remediate` (or the operator says "fix it / recover"), set `REMEDIATE = True`.

**Safe recoveries (the ONLY actions `--remediate` may take):**

- **Daemon down/stopped** → `pm2 resurrect` (or `pm2 restart <name>`), then re-check the heartbeat.
- **Dead-session zombie** (state RUNNING but tmux session gone) → `kanban cancel <issue> --root <r>`
  (the teardown only kills an ALREADY-DEAD session; it never touches a live one).
- **Stuck unsubmitted prompt** (A2 — alive + heartbeat never refreshed since launch + no active turn)
  → send a trailing SPACE then Enter, in a bounded LOOP until a turn starts. The space is required:
  launch prompts are slash commands (`/implement:…`) and a bare Enter interacts with the autocomplete
  instead of submitting (live #5); the space closes it so Enter submits (harmless on non-slash prompts):
  `for i in $(seq 1 6); do tmux capture-pane -p -t ticket-<issue> | grep -qi 'esc to interrupt' && break; tmux send-keys -t ticket-<issue> -l ' '; tmux send-keys -t ticket-<issue> Enter; sleep 4; done`.
  Extra cycles on an emptied box are harmless no-ops.
- **Wrong-stage relaunch** (A4 — the running agent's `stage` ≠ the card's column; a stale stage was
  relaunched after the card advanced) → cancel + re-fire the CORRECT stage: `kanban cancel`, stop the
  daemon, API-move the card to the target transition's FROM-column, restart the daemon (let one tick
  set the baseline), API-move to the TARGET column so the daemon fires the right-stage agent, then
  babysit A2. Full steps in `references/checks.md` §A4.
- **PM2 boot-persistence missing** → print the exact `sudo pm2 startup …` command for the operator to
  run (do NOT run sudo yourself).

## Discovery (FIRST action)

Find every KanbanMate daemon + its runtime root:

```bash
# Daemons PM2 supervises (names + status).
pm2 jlist 2>/dev/null | python3 -c "import sys,json;[print(p['name'],p['pm2_env']['status']) for p in json.load(sys.stdin) if 'kanban' in p['name']]"
# Runtime roots on disk (each holds projects.json + daemon.heartbeat).
ls -d ~/.kanban ~/.kanban-* 2>/dev/null
```

Pair each PM2 app with its root (the `run --root <r>` arg in its PM2 args; the default `kanban` app →
`~/.kanban`). Create one task per (daemon, root). If `pm2 jlist` returns no kanban apps → that is a
**FAIL** (the orchestrator is not running at all) — report it and, under `--remediate`, `pm2 resurrect`.

## The checklist (run per daemon/root)

Run each check; record PASS/WARN/FAIL. Exact commands + thresholds are in
`references/checks.md` — read it before the sweep (it is authoritative for the criteria).

| #      | Check                           | What it proves                                                                                                                                                 |
| ------ | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | PM2 process online              | the daemon process exists and is not errored/stopped                                                                                                           |
| **D2** | Heartbeat fresh                 | the daemon is actually ticking (age < 120s) — not hung/asleep                                                                                                  |
| **D3** | Tick healthy                    | `last_tick_ok=True`, `consecutive_failures=0` — ticks are succeeding                                                                                           |
| **D4** | No restart storm                | `restart_time` stable across two samples; `unstable_restarts=0`                                                                                                |
| **H1** | Engine/host (default root only) | `kanban doctor` exit 0 — engine importable, token scoped, board reachable, helper shims, tmux socket, non-root, orphan slots                                   |
| **B1** | Board reachable                 | `kanban state --root <r>` returns a board snapshot                                                                                                             |
| **A1** | No zombie agent                 | every state-RUNNING agent has a LIVE tmux session                                                                                                              |
| **A2** | No stuck prompt                 | the launch prompt actually submitted — heartbeat refreshed since launch / a turn is running (NOT just a `[Pasted text]` tail-grep, which a long prompt evades) |
| **A3** | WAITING agents (WARN, info)     | list agents parked WAITING — they need a human to attach + answer                                                                                              |
| **A4** | Stage/column coherence          | the running agent's `stage` matches the card's column — catches a stale WRONG-STAGE relaunch (e.g. a Brainstorm agent on a Spec card)                          |
| **P1** | Status-pill coherent            | persisted `last_status` is a valid domain health; no GraphQL invalid-enum / orphan-status-update error in the recent log                                       |
| **R1** | Boot-persistence                | a PM2 launchd/systemd startup item exists (survives reboot/sleep) — WARN if absent                                                                             |
| **R2** | No recurring errors             | the daemon error log since its last start has no Traceback / crash-loop / repeated DNS failure                                                                 |

## Verdict

After sweeping all daemons, emit:

```
KanbanMate monitor — <N> daemon(s) checked
  <daemon> (<root>): <PASS count> PASS · <WARN> WARN · <FAIL> FAIL
  …
VERDICT: HEALTHY | DEGRADED (warnings only) | BROKEN (one or more FAIL)
```

- **HEALTHY** — every check PASS (WARN allowed only for A3 WAITING + advisory token/pyenv notes).
- **DEGRADED** — only WARNs (e.g. an agent WAITING for input, boot-persistence absent, an advisory
  doctor warning). The orchestrator works; an operator eye is wanted.
- **BROKEN** — any FAIL (daemon down/hung, zombie agent, stuck prompt, board unreachable, pill error,
  crash-loop). List each in the DEVIATION LIST with the recommended action (and apply it under
  `--remediate` if it is a safe recovery).

Then the **DEVIATION LIST** — one row per WARN/FAIL: `severity · daemon · check · finding · action`.

## Relationship to the other skills

- Uses the **`/kanban` CLI** verbs (`doctor`, `state`, `sessions`, `cancel`) — it does not reimplement
  them.
- The **engine** owns every safety invariant this skill relies on (Approach-A reaper never kills a
  live session; the daemon's per-tick guard; the domain→GitHub-pill mapping). The monitor only
  observes their effects.
- Pattern modelled on the personalscraper `pipeline-monitor` skill (read-only default, `--remediate`
  opt-in, fixed checklist, classification, DEVIATION LIST) — but scoped to orchestrator HEALTH, not a
  multi-step pipeline.
