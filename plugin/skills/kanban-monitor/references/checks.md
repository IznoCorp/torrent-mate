# Kanban Monitor — check reference (authoritative criteria)

Exact commands + PASS/WARN/FAIL thresholds for every check in `SKILL.md`. Run per daemon/root unless
marked "default root only". `<r>` = the daemon's runtime root (`~/.kanban`, `~/.kanban-km`, …);
`<name>` = its PM2 app name (`kanban`, `kanban-km`, …).

All commands are READ-ONLY. The `--remediate` actions live in `SKILL.md`, not here.

---

## D1 — PM2 process online

```bash
pm2 jlist 2>/dev/null | python3 -c "import sys,json
for p in json.load(sys.stdin):
    if p['name']=='<name>': print(p['pm2_env']['status'])"
```

- **PASS** — `online`.
- **FAIL** — `stopped` / `errored` / not in the list (the daemon process is not running).

## D2 — Heartbeat fresh (the daemon is actually ticking)

```bash
python3 -c "import json,time;d=json.load(open('<r>/daemon.heartbeat'));print(int(time.time()-d['ts']))"
```

- **PASS** — age < 120s.
- **WARN** — 120–600s (a slow/degraded loop, or a long sleep window).
- **FAIL** — > 600s, or the file is missing/garbage (the daemon is hung / dead / asleep — the exact
  "daemon vanished" incident signature).

## D3 — Tick healthy

Read the same heartbeat JSON: `last_tick_ok` + `consecutive_failures`.

- **PASS** — `last_tick_ok=True` and `consecutive_failures=0`.
- **WARN** — `consecutive_failures` 1–3 (transient — a GitHub blip the circuit-breaker is backing off).
- **FAIL** — `consecutive_failures > 3` or `last_tick_ok=False` sustained across two reads (a
  persistent failure — dead token, DNS outage, config gone).

## D4 — No restart storm

Sample `restart_time` twice ~8s apart; also read `unstable_restarts`.

```bash
pm2 jlist 2>/dev/null | python3 -c "import sys,json
for p in json.load(sys.stdin):
    if p['name']=='<name>': e=p['pm2_env']; print(e['restart_time'], e.get('unstable_restarts',0))"
```

- **PASS** — `restart_time` identical across the two samples, `unstable_restarts=0`.
- **WARN** — `restart_time` grew by 1 (a single recent restart).
- **FAIL** — `restart_time` climbing fast (≥2 between samples) or `unstable_restarts>0` (crash-loop;
  the PM2 hardening `max_restarts=15`/`min_uptime=30s` will eventually stop it `errored`).

## H1 — Engine / host (DEFAULT ROOT ONLY)

`kanban doctor` has no `--root`; it checks `~/.kanban`. Run it once for the default daemon:

```bash
kanban doctor; echo "exit=$?"
```

- **PASS** — `exit=0` ("All checks passed"). Advisory WARNINGs inside a PASS row (over-scoped token,
  pyenv twin) stay **WARN**, not FAIL.
- **FAIL** — `exit=1` (any check FAILed: engine import, pm2, heartbeat, plugin, token, board, helper
  shims, tmux socket, non-root, orphan slots).
- For NON-default roots, H1 is not available (doctor is single-root) — rely on D1–D4 + B1 + A\* + P1.
  Note this limitation in the report.

## B1 — Board reachable

```bash
kanban state --root <r> 2>&1 | sed -n '1,30p'
```

- **PASS** — prints the board (columns + TOTAL) and a `Daemon:` line. Capture the `Health:` value and
  the `Running agents:` block for A1–A3/P1.
- **FAIL** — error / empty output / `Daemon: FAILING` (cross-check with D2).

## A1 — No zombie agent (RUNNING but session dead)

For each agent in `kanban state --root <r>` "Running agents" (each line has `#<issue>` +
`session=<uuid>` + `status=…`):

```bash
tmux has-session -t ticket-<issue> 2>/dev/null && echo ALIVE || echo DEAD
```

- **PASS** — every RUNNING agent's `ticket-<issue>` session is ALIVE.
- **FAIL** — an agent is state-RUNNING but its session is DEAD (a zombie the next reap will clear; under
  `--remediate`, `kanban cancel <issue> --root <r>`). A WAITING agent with a dead session is also a
  zombie (same FAIL).

## A2 — No stuck (unsubmitted) prompt — the launch never started

The prompt-delivery path can leave the launch prompt sitting UNSUBMITTED in the input box (claude
v2.1.x absorbs the submit Enter; the in-engine submit-retry budget is too short for a LARGE
multi-chunk prompt — e.g. the Spec/design prompt that embeds the ticket body). The agent then reads
RUNNING but does nothing.

**Robust detection — do NOT key on the literal `[Pasted text]` in the pane tail.** A long prompt
pushes that marker out of the last lines (the real miss this check was hardened against). The reliable
signal is the **heartbeat never refreshing since launch + no active turn**: a working agent refreshes
its heartbeat within seconds (the PostToolUse hook fires on its first tool call).

```bash
# never_refreshed = the heartbeat still equals the launch time (the agent has done nothing).
python3 -c "import json,time;d=json.load(open('<r>/state/<issue>.json'));print('hb_age=%d'%(time.time()-d['heartbeat']),'never_refreshed=%s'%(abs(d['heartbeat']-d.get('started',d['heartbeat']))<2))"
tmux capture-pane -p -t ticket-<issue> 2>/dev/null | grep -qi 'esc to interrupt' && echo TURN_RUNNING || echo NO_TURN
```

- **PASS** — a turn is running (`esc to interrupt`), OR the heartbeat has refreshed since launch
  (`never_refreshed=False`), OR the input box is empty.
- **FAIL** — session ALIVE **and** `never_refreshed=True` **and** `hb_age > 90` **and** NO active turn
  → the launch prompt never submitted (corroborate with input-box content anywhere in the pane:
  `[Pasted text]` / `paste again to expand` / `ctrl+g to edit` / the prompt text).
  **Remediate** — send Enter until a turn starts (adequate budget for a large prompt; extra Enters on
  an emptied box are harmless no-ops):
  ```bash
  for i in $(seq 1 6); do
    tmux capture-pane -p -t ticket-<issue> 2>/dev/null | grep -qi 'esc to interrupt' && { echo SUBMITTED; break; }
    tmux send-keys -t ticket-<issue> Enter; sleep 4
  done
  ```
  Re-check A2 after; if still stuck past the budget, escalate to the A4 stage re-fire or flag the
  operator.

## A3 — WAITING agents (WARN — info for the operator)

From `kanban state --root <r>`: any agent with `status=…WAITING`.

- **WARN** (never FAIL) — list each: `#<issue> WAITING — attach: tmux attach -t ticket-<issue>`. The
  orchestrator is healthy; these need a human to answer the agent's prompt.

## A4 — Stage/column coherence (no wrong-stage relaunch)

The reaper can relaunch a STALE running-state whose `stage` no longer matches the card's column — e.g.
the card advanced Brainstorming→Spec but the OLD Brainstorming running-state was relaunched, so a
BRAINSTORM agent runs on a Spec card (it re-delivers the WRONG prompt and the correct-stage agent
never ran). This is invisible to A1/A2 (the session is alive and may even submit) — it needs its own
check.

```bash
python3 -c "import json;print('stage=',json.load(open('<r>/state/<issue>.json')).get('stage'))"   # persisted stage
kanban state --root <r> 2>&1 | grep "#<issue> " | grep -oE 'column=\S+'                            # board column
```

- **PASS** — the running agent's `stage` equals the card's current column.
- **FAIL** — they differ AND the card has advanced PAST the agent's stage (e.g. `stage=Brainstorming`
  but `column=Spec`) → a stale wrong-stage relaunch; the correct-stage agent never ran.
  **Remediate** — cancel + re-fire the CORRECT stage (the column the card is in). Re-firing needs a
  real board transition INTO that column, and the daemon ROLLS BACK an un-whitelisted backward move,
  so route it while the daemon is stopped:
  1. `kanban cancel <issue> --root <r>` — clears the stale agent + state (kills only an already-dead
     session; safe).
  2. `pm2 stop <name>` — so the daemon can't roll back the next move.
  3. API-move the card to the FROM-column of the target stage's transition (e.g. the Spec agent fires
     on `Brainstorming→Spec`, so move to **Brainstorming**) via the GraphQL
     `updateProjectV2ItemFieldValue` mutation (the option ids are in `<root>/projects.json`
     `option_map`).
  4. `pm2 start <name>`; wait ~12s for one tick (first-contact baseline → NOOP, no spurious launch).
  5. API-move the card to the **target column** → the daemon fires the correct-stage agent.
  6. Babysit A2 (the new launch is large → run the Enter-resubmit loop until a turn starts).

## P1 — Status-pill coherent

```bash
cat <r>/status/last_status 2>/dev/null   # expect a domain health: INACTIVE|BLOCKED|WAITING|ACTIVE|COMPLETE
# recent pill errors in the daemon log since its last start:
tail -60 ~/.pm2/logs/<name>-error.log 2>/dev/null | grep -iE "ProjectV2StatusUpdate|invalid.*enum|statusUpdate' doesn't exist"
```

- **PASS** — `last_status` is one of the 5 DOMAIN names, and NO recent status-update GraphQL error.
- **WARN** — `last_status` empty/unknown (no pill posted yet) — benign on a fresh board.
- **FAIL** — a recent `invalid enum` / `Field 'statusUpdate' doesn't exist` error (the domain→wire
  mapping or the delete query is broken). NOTE: a Traceback dated BEFORE the daemon's last
  `daemon started` line is HISTORICAL — ignore it; only post-restart errors count.

## R1 — Boot-persistence (survives reboot/sleep-shutdown)

```bash
launchctl list 2>/dev/null | grep -i pm2 || ls ~/Library/LaunchAgents 2>/dev/null | grep -i pm2 || echo NONE
```

- **PASS** — a PM2 launchd (macOS) / systemd (Linux) startup item exists.
- **WARN** — `NONE` — PM2 will NOT auto-resurrect after a reboot/sleep-shutdown (the daemon-vanished
  incident root cause). Recommend: `pm2 startup` + run the printed `sudo …` command, then `pm2 save`.

## R2 — No recurring errors since the last start

```bash
# Everything in the error log AFTER the most recent "daemon started":
awk '/daemon started/{s=NR} {L[NR]=$0} END{for(i=s;i<=NR;i++)print L[i]}' ~/.pm2/logs/<name>-error.log 2>/dev/null \
  | grep -iE "Traceback|Error|gaierror|No buffer space|GraphQL"
```

- **PASS** — nothing (clean since the last start).
- **WARN** — isolated transient (one DNS `gaierror`, one timeout) — the per-tick guard absorbed it.
- **FAIL** — a repeating Traceback / a crash-loop signature / sustained network failures (the daemon
  is failing every tick).
