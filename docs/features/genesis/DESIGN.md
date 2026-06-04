# KanbanMate — Extraction & Hardening — Design Spec

> **Status**: brainstormed & approved through architecture (2026-06-04), pending final spec review.
> **Repo**: `~/dev/KanbanMate` → `git@github.com:IznoCorp/kanban-mate.git` (fresh, empty).
> **Source of the code being extracted**: the PoC at
> `PersonalScraper/.claude/skills/kanban/` (portable-config repo, branch `personal-scraper`).
> **Both in-progress PoC features shipped** (2026-06-04): sticky comments per step; Cancel-column
> teardown + Cancel→Backlog resume. The extraction MUST re-sync the latest PoC code first — see §11.
> **Major architecture pivot (2026-06-04)**: ingress switched from **n8n webhooks → unified polling**.
> n8n, HMAC, raw-body handling, and `payload.py` are **removed**. See §3.

## 1. Purpose & motivation

KanbanMate is a **reusable Kanban orchestrator**: each roadmap item is a **ticket** moved
column by column on a **GitHub Projects v2** board; moving a card into a triggering column
fires an autonomous **Claude Code agent** in an isolated **tmux + git-worktree** workspace. The
agent comments on the ticket, may re-move the card (only to non-triggering columns), and its
session is **resumable** (`tmux attach` / `claude --resume <uuid>`). A single background daemon
drives the board; no open Claude session is required for the board to react.

Today this lives buried inside `PersonalScraper/.claude/skills/kanban/` (~18 kLOC incl. tests).
It is **transverse infrastructure** unrelated to the media pipeline. This effort extracts it into
its own autonomous project and **hardens it**.

**Motivation, in priority order** (user-stated): (1) **harden the PoC**; (2) **clean personal
multi-repo use**; (3) **publishable**; (4) **decouple from the media repo**. Decoupling is the
through-line; hardening is the dominant driver; publishability is a goal but not the primary
optimisation target.

## 2. Identity & artifacts

One repo, **two distributable artifacts**:

| Artifact | What | Install channel |
|---|---|---|
| **Engine** | Python package `kanbanmate` + console script `kanban` + bundled assets (PM2 ecosystem file, `columns.yml` template, agent helper bins) | `pip install` (editable for dev; pipx for runtime) |
| **Claude plugin** | `.claude-plugin/marketplace.json` at repo root → skill `/kanban` (thin: shells to the `kanban` CLI) + agent helper commands | `claude plugin marketplace add` + `claude plugin install` |

The repo **is** its own Claude plugin marketplace. **All logic lives in the engine**; the
plugin/skill only invokes `kanban …`. Naming: package `kanbanmate`, console entry `kanban`,
plugin `kanban`, marketplace `kanbanmate` (GitHub repo `IznoCorp/kanban-mate`). Fresh git history.

## 3. Architecture

### 3.1 Ingress — unified polling (no webhooks, no n8n)

A single long-running daemon polls the board and reconciles it against persisted state. There is
**no webhook, no n8n, no HMAC, no public endpoint**. Latency is bounded by the poll interval
(default 10 s); GraphQL rate-limit cost is negligible (~7 %/h of the 5000 pt/h budget at 10 s).

```
                         ┌──────────────────────────────────────────────┐
   PM2 supervises  ─────▶│  kanban run  (daemon, non-root user)          │
   (restart/boot)        │  loop:  read_config_if_changed                │
                         │         → tick()                              │
                         │         → sleep(adaptive interval)            │
                         └───────────────────┬──────────────────────────┘
                                             ▼  one tick =
   GitHub Projects v2  ◀── cheap_probe (items orderBy UPDATED_AT first:5)
   (GraphQL, PAT)      ◀── snapshot (only if probe changed; cursor-paginated)
                                             │
                                  diff(persisted_state, snapshot) → [Transition]
                                             │
                          ∀ transition:  decide() → Action ──┬─ LaunchAction  (agent col)
                                                             ├─ TeardownAction (Cancel col)
                                                             ├─ ResetAction    (Cancel→Backlog)
                                                             ├─ BlockAction    (dep gate / rate)
                                                             └─ noop
                                             │
                          then: reap dead sessions · drain queue · write heartbeat
                                             ▼
   Agent (claude, tmux, worktree): works · kanban-comment (sticky) · kanban-move (push/PR, NEVER merge)
                                             ▲
   You: ssh + tmux attach -t ticket-<n> · iTerm2 -CC · claude --resume <uuid> · /kanban (management)
```

The daemon is the **single heartbeat**: it subsumes the PoC's separate webhook receiver and
launchd reaper. The `tick` is **idempotent** — on restart it rebuilds from persisted state + a
fresh snapshot, and the diff naturally recovers any moves made during downtime. Agent tmux
sessions are independent processes that survive a daemon crash and are re-discovered via state +
`tmux has-session`.

### 3.2 Layering — hexagonal (ports & adapters)

```
cli/ (typer) ─┐
              ├─▶ app/ (orchestration) ─▶ core/ (pure, zero I/O)
daemon/ ──────┘                       └─▶ ports/ (Protocols)
                                           ▲
                             adapters/ ────┘  (github · workspace · store · clock)
```

Import direction is **downward only**, enforced by a layering guard (mirrors the `acquire/` guard
in PersonalScraper). `core` depends on nothing; `ports` are Protocols; `adapters` implement them;
`app` is the composition root; `cli`/`daemon` are entrypoints.

### 3.3 Module map

**`core/` (pure, testable with no I/O)**
- `domain.py` — `Ticket, Column, ColumnClass{agent|reactive|inert}, BoardSnapshot, Transition, Decision, Action`
- `diff.py` — the heart of polling: `(persisted_state, fresh_snapshot) → [Transition]` (replaces all payload parsing)
- `decide.py` — `decide(transition, ctx) → Action` (pure; carried over from PoC)
- `columns.py` — column-class resolution from the `columns.yml` model
- `antiloop.py` — target-keyed guard + per-ticket rate-limit (pure given state)
- `dependency_gate.py` — parse `Depends on #N`, evaluate against board state
- `interval.py` — adaptive poll-interval **strategy** (active/idle back-off)

**`ports/` (Protocols)** — `BoardReader{snapshot, cheap_probe}` · `BoardWriter{move_card, comment}` ·
`Seeder{create_issue, add_to_project, ensure_labels}` · `Workspace{ensure_worktree, remove_worktree, discover_branch}` ·
`Sessions{launch, is_alive, kill}` · `StateStore` · `Clock{now}`

**`adapters/`**
- `github/` — typed **urllib** client (injected transport + mandatory connect/max timeouts):
  GraphQL board read (cursor-paginated, H3) + cheap-probe + `updateProjectV2ItemFieldValue`;
  REST issues/comments/labels. PAT auth (`project` + `repo` only).
- `workspace/` — git worktree + tmux (Sessions/Workspace), `shlex.quote` on argv (paths with spaces)
- `store/` — filesystem `~/.kanban` with atomic `O_EXCL` + `flock` (H-subset)

**`app/`**
- `tick.py` — the imperative shell (see §3.1): probe → snapshot → diff → decide → execute, then reap + drain + heartbeat
- `actions.py` — **command pattern**: `LaunchAction / TeardownAction / ResetAction / BlockAction`, each `execute(deps)`
- `wiring.py` — composition root (build adapters, inject into actions/tick)

**Entrypoints**
- `daemon/loop.py` — `kanban run`: standalone blocking loop, **supervisor-agnostic** (see §5)
- `cli/` — typer app: `install · uninstall · doctor · init · seed · status · sessions · cancel · logs · reset · run · poll --once`
- `bin/` — agent helpers (thin urllib-client wrappers): `kanban-comment` (sticky, §8.1),
  `kanban-move`, `kanban-heartbeat` (liveness, §8.3), `kanban-progress`, `kanban-session-end`,
  `check-pr-ready.sh`, `check-merge-ready.sh`, `kanban-update-main`. (Exact set per the §11 re-sync;
  the PoC source is authoritative.)

**Design patterns**: hexagonal · functional-core/imperative-shell · command (actions) · strategy
(interval) · the PoC's injectable seams formalised as Protocols.

## 4. Install model — self-bootstrapping ("everything via the project")

Single entry point `kanban install`, in **three idempotent tiers**:

### 4.1 Host tier (1×/machine)
Creates `~/.kanban/` skeleton (token `600`), installs the **PM2-supervised daemon** (writes the
PM2 ecosystem file, `pm2 start kanban -- run`, `pm2 save`, `pm2 startup` for boot persistence),
seeds the kill-switch primitives. No secret, no webhook, no n8n. `kanban uninstall` runs
`pm2 delete kanban` + host teardown.

### 4.2 Claude tier (1×/machine) — fully automatic
The Claude plugin manager exposes a **non-interactive CLI** (`claude` v2.1.156, verified), so
`kanban install` drives it directly — no manual `/plugin` step, no hand-editing internal JSON:

```
claude plugin marketplace add <repo-path> --scope user
claude plugin install kanban@kanbanmate --scope user [--config engine_path=…]
```

`marketplace add` accepts a **local path** source; `install` installs **and** enables in one shot.
`kanban doctor` verifies via `claude plugin list` + `claude plugin validate <path> --strict`.
`kanban uninstall` runs `claude plugin uninstall` + `marketplace remove`.

### 4.3 Per-repo tier (per target project)
`kanban init --repo org/repo` — fresh org Project v2, reuse the auto Status field, ensure columns,
`wave:*`/`prio:*` labels, write `<clone>/.claude/kanban/columns.yml`, register in `projects.json`
(keyed by project node id). **No webhook/n8n step anymore.** + `kanban seed <ROADMAP.md>` (issues
+ `Depends on` rewrite, in Backlog).

`kanban doctor` validates all three tiers: engine importable, PM2 daemon up + heartbeat fresh,
plugin present, GitHub token reachable + scopes not over-broad (`project`+`repo`, **not**
`admin:org_hook`), branch protection on, non-root, tmux socket owned by the user.

## 5. Daemon design (`kanban run`, PM2-supervised + agnostic core)

The daemon process knows **nothing** about PM2 — it is a clean standalone process, which keeps it
testable in CI without PM2 and debuggable in a bare terminal. PM2 is the sole install/ops path
(`pm2 logs/restart kanban`), but the core stays agnostic so launchd/systemd/manual remain possible.

- **Single instance**: `flock ~/.kanban/daemon.lock` held for process lifetime; a second daemon
  detects the lock and exits (belt-and-suspenders with PM2's per-name singleton).
- **Crash-safety**: the tick is idempotent; `~/.kanban` is the source of truth with atomic writes
  (`O_EXCL`/`flock`). A crash mid-tick is safe; restart + diff recovers downtime moves.
- **Hang protection** (PM2/launchd restart on *exit*, not on *hang*): (a) mandatory HTTP
  connect/max timeouts on the urllib client (matches the project network-safety rule); (b) a
  **per-tick watchdog timeout** — a stuck ticket aborts the tick and the loop continues; (c) a
  **heartbeat** the daemon writes each tick so `kanban doctor` flags a wedged daemon.
- **Logs**: structured JSONL, size-rotated, `~/.kanban/log/daemon.jsonl` (+ PM2 stdout capture);
  per-ticket `~/.kanban/log/ticket-<n>.log`. `kanban logs` reads both.
- **Graceful shutdown**: SIGTERM → finish current tick, release lock, exit.
- **Config reload**: re-read `columns.yml`/config at the top of a tick when `mtime` changed (no SIGHUP).
- **Restart for upgrade**: `kanban install` runs `pm2 restart kanban`.

## 6. Hardening (post-pivot)

The polling pivot **erases two of the seven PoC should-fix items by construction**:
- ~~H1 delivery dedup (`O_EXCL` processed/)~~ — no deliveries exist; the diff ignores already-applied
  state. Reduced to: atomic slot reservation under `flock` + trivial in-tick guard (single process).
- ~~H2 bot-move TTL dedup~~ — a bot move recorded in persisted state produces no diff on the next poll.

Anti-loop reduces to: (a) `kanban-move` refuses agent-triggering targets; (b) atomic slot reserve;
(c) diff-against-persisted-state idempotence. Remaining, fully in-scope hardening:

| # | Requirement |
|---|---|
| H3 | **Pagination**: `projectItems` GraphQL cursor-follow (board with many items must not truncate) |
| H4 | Permission profiles **materialised** into the worktree's `.claude/settings.json` (`defaultMode` pinned — mitigates mid-session reset #39057); `safe` (concrete `permissions.allow`) vs `trusted`; both ban `gh pr merge`, `git push --force`, history rewrite. The same worktree settings file also carries the **PostToolUse heartbeat hook** (§8.3) |
| H5 | **Kill-switch** `~/.kanban/PAUSE` → downgrade all profiles to `safe` + **unattended-hours** window → zero launches |
| H6 | **Real captured GraphQL responses** (board snapshot, fieldValueByName, move mutation) as fixtures — replaces synthetic fixtures and pins the exact shape |
| H7 | **Real GitHub integration tests** actually executed against a dedicated test org/Project (no longer gated-and-skipped-forever) — see §7 |

## 7. Testing & CI strategy (the core of "harden")

Three levels:

1. **Unit** (offline, deterministic) — carried over; `core/` is pure so `diff`/`decide`/`antiloop`/
   `interval` are fully unit-tested without any I/O.
2. **Local-real** (real tmux + real git; GitHub faked, `claude`=`echo`) — drives `tick()`/`kanban run`
   **directly** (no PM2 needed in CI — the agnostic-core payoff). Proves a real column move spawns a
   real tmux session in a real worktree.
3. **Integration-real** (real GitHub Projects v2) — gated on a `KANBAN_TOKEN` CI secret pointing at a
   **dedicated test org/Project**. **No n8n container needed anymore** (ingress is polling). Runs the
   real poll→diff→move loop against the live board.

CI split: **PR** = L1 + L2 + `claude plugin validate .claude-plugin --strict` (free, no secrets).
**Nightly** = L3.

## 8. Column contract — three column classes

| Class | `columns.yml` shape | Behaviour |
|---|---|---|
| **agent** | `triggers_agent: true` (+ `prompt`, `permission_profile`, `interactive_only`) | launch agent in worktree (`LaunchAction`) |
| **reactive** | `action: teardown` | run a dispatcher side-effect, no agent (`TeardownAction`) |
| **inert** | neither | human-gate / terminal; diff produces no launch |

`kanban-move` refuses **agent** targets (anti-loop); reactive/inert targets are permitted for
bot/agent moves. The diff is column-class-aware: an inert→agent transition launches; a move to a
reactive column runs its action; an inert→inert move is a noop.

### 8.1 Sticky comments per step (agent→ticket signalling)
`kanban-comment --sticky <step-key>` keeps **one comment per (ticket, step)** updated in place via
an HTML marker (`<!-- kanban:step=<column-key> -->`): list the issue's comments, match the marker,
**edit** the existing one or **create** it if absent. Append mode stays for free-form notes. Durable
progress surface that doesn't spam the timeline.

### 8.2 Cancel column — teardown + resume
A **`Cancel`** reactive column. A card moved into it triggers **full teardown** (`TeardownAction`):
kill the tmux session, `worktree remove` (no `--force`), release the slot, drop the in-flight guard,
clear/transition persisted state, post a final sticky comment. This shares the teardown core with the
`kanban cancel` CLI. **Resume**: a **Cancel → Backlog** transition (`ResetAction`) purges the ticket
to a clean, re-startable state (fresh uuid/worktree on a later move into an agent column). Both Cancel
and Backlog are non-agent, so neither move relaunches an agent; teardown keys on the destination
(`Cancel`), reset on the transition (`Cancel→Backlog`).

### 8.3 Agent liveness heartbeat (PoC #67 — shipped)
Two **distinct** heartbeats exist, do not conflate them:
- **Agent heartbeat** (this section) — proves the *agent* is working.
- **Daemon heartbeat** (§5) — proves the *daemon* is alive; `kanban doctor` checks it.

`LaunchAction` bakes a **PostToolUse hook with matcher `"*"`** into the worktree's
`.claude/settings.json` (alongside the H4 perms), so it fires after *every* tool the agent uses.
Per the Claude Code hook schema the hook is a **command string with the issue baked in by the
dispatcher** (`kanban-heartbeat <issue>` — a command string, **not** exec-form args); the hook's
stdin JSON payload is ignored. Each firing calls `Store.touch_heartbeat(issue, now)` — an
**atomic** (temp + `os.replace`) write that refreshes `state[issue].heartbeat`. A working agent
therefore never stales; an agent that *stops emitting tools* for the whole TTL goes silent and is reaped.

Hard contracts of the shim (`bin/kanban-heartbeat`):
- **Always exits 0** (non-blocking, zero influence on the agent); exit 2 would *block* the agent and
  is never emitted. A bare `try/except` swallows any missed heartbeat.
- **Import-light**: argv is parsed to `int` *before* importing `kanbanmate`, so a missing/non-int
  arg short-circuits to exit 0 without paying the package-import cost (it fires synchronously after
  every tool; cold start ~100 ms, negligible and never blocking).
- **No resurrection**: `touch_heartbeat` is a **no-op when `state/<issue>.json` is absent**, so a
  late hook firing *after a Cancel teardown* (§8.2) never recreates a torn-down ticket's state.

The daemon's reap step (part of every `tick`) blocks a `running` ticket whose agent heartbeat is
older than `HEARTBEAT_TTL` (default 1800 s): comment + move to `Blocked` + kill the dead session +
release the slot. A retry refreshes the heartbeat so the next tick does not immediately re-block it.

## 9. Default columns & triggering

| Column | Class | Note |
|---|---|---|
| Backlog | inert | manual; also the reset target from Cancel |
| Spec | inert (human-gate) | brainstorm = interactive |
| Planned | inert | create-branch = interactive |
| Ready to dev | inert | human gate |
| **In Progress** | **agent** | `/implement:phase` (unattended-safe) |
| **PR/CI** | **agent** | `/implement:feature-pr` |
| **Review** | **agent** | `/implement:pr-review` (no auto-merge) |
| Merge | inert (human only) | bot cannot reach it; merge is human |
| **Cancel** | **reactive: teardown** | full teardown; Cancel→Backlog = resume reset |
| Done | inert | terminal |
| Blocked | inert | agent/daemon parks here |

The `implement:*` defaults live **only** in the `columns.yml` template (per-repo, user-editable) —
the engine stays generic.

## 10. Security & autonomy
Merge = human only (agents push + open PR, never merge); ban `gh pr merge` / `--force` / history
rewrite across all profiles. `safe` profile = concrete `permissions.allow` + pinned `defaultMode`.
Token in `~/.kanban/token` (600, off-git); v1 = user PAT scoped **`project` + `repo`** (no
`admin:org_hook` — webhooks are gone; anti-loop is target-keyed, not identity-keyed). Kill-switch
(H5). Non-root daemon (tmux socket ownership; `bypassPermissions` refuses under root). GitHub App =
optional future upgrade (§13).

## 11. Cutover & decommission (rule: no back-compat before v1.0)
- **No migration script** (project rule: <1.0 ⇒ no migrations). Existing `~/.kanban/` PoC state is
  disposable; `kanban install` starts fresh; `kanban reset` archives the old one.
- **Pre-implementation re-sync gate (⚠️ blocking)**: pull the latest PoC code from
  `.claude/skills/kanban/` (both features now shipped) before extraction. The actual code is the
  source of truth for §8.1/§8.2.
- **Decommission old location**: remove `skills/kanban/` from the portable-config repo, **remove the
  old launchd reaper plist** (`xyz.iznogoudatall.kanban-reaper`), clean `.claude/CLAUDE.md` refs. The
  old reaper is fully replaced by the new daemon.

## 12. Repository layout (target)

```
~/dev/KanbanMate/
├── README.md                      # what/why + quickstart
├── pyproject.toml                 # package kanbanmate, console_scripts: kanban
├── ecosystem.config.js            # PM2 ecosystem file (kanban run)
├── .claude-plugin/marketplace.json
├── plugin/                        # Claude plugin payload (skill /kanban, agent helpers)
│   └── skills/kanban/SKILL.md
├── src/kanbanmate/
│   ├── core/                      # domain, diff, decide, columns, antiloop, dependency_gate, interval
│   ├── ports/                     # Protocols
│   ├── adapters/                  # github (urllib), workspace (tmux/git), store (fs)
│   ├── app/                       # tick, actions, wiring
│   ├── daemon/                    # loop (kanban run)
│   └── cli/                       # typer app
├── bin/                           # kanban-comment, kanban-move
├── assets/columns.yml.tmpl
├── tests/                         # unit + local-real + gated integration
├── docs/{install,how-it-works,columns}.md  +  docs/superpowers/specs/…
├── ROADMAP.md
└── .github/workflows/             # pr.yml (L1+L2+validate), nightly.yml (L3)
```

## 13. Out of scope / ROADMAP (deferred)
- **Optional webhook ingress adapter** — for anyone wanting sub-second latency, a `kanban serve`
  webhook receiver could slot in behind the same `BoardReader` boundary. Not needed; polling is the
  default and only supported ingress in v1.
- **GitHub App** upgrade (identity-keyed anti-loop + clean attribution + short scoped tokens).
- Multi-org; MCP helpers (urllib helpers in v1); auto-merge (permanently forbidden).

## 14. Implementation phasing (for the plan)
- **P1** — bootstrap repo + packaging (`pyproject`, hexagonal layout §12) + port the reusable engine
  (`core` pure logic, `adapters/workspace`, `adapters/store`, GraphQL read/move) ; CI green on unit +
  local-real. **Build `diff`/`tick`/`daemon` here** (the new polling core); drop `payload`/HMAC/n8n.
- **P2** — installer 3 tiers (`install/uninstall/doctor`) + PM2 daemon wiring + plugin marketplace + `validate` gate.
- **P3** — hardening H3–H5.
- **P4** — real GraphQL fixtures H6 + integration CI H7 (test org).
- **P5** — sticky comments (§8.1) + Cancel column (§8.2) wired to the column-class/action model; docs;
  cutover + decommission of the old location.
