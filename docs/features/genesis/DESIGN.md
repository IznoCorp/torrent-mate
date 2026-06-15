# KanbanMate — Extraction & Hardening — Design Spec

> **Status**: brainstormed & approved through architecture (2026-06-04), pending final spec review.
> **Repo**: `~/dev/KanbanMate` → `git@github.com:IznoCorp/kanban-mate.git` (fresh, empty).
> **Source of the code being extracted**: the PoC at
> `PersonnalScaper/.claude/skills/kanban/` (portable-config repo, branch `personal-scraper`).
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

Today this lives buried inside `PersonnalScaper/.claude/skills/kanban/` (~18 kLOC incl. tests).
It is **transverse infrastructure** unrelated to the media pipeline. This effort extracts it into
its own autonomous project and **hardens it**.

**Motivation, in priority order** (user-stated): (1) **harden the PoC**; (2) **clean personal
multi-repo use**; (3) **publishable**; (4) **decouple from the media repo**. Decoupling is the
through-line; hardening is the dominant driver; publishability is a goal but not the primary
optimisation target.

## 2. Identity & artifacts

One repo, **two distributable artifacts**:

| Artifact          | What                                                                                                                                   | Install channel                                           |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **Engine**        | Python package `kanbanmate` + console script `kanban` + bundled assets (PM2 ecosystem file, `columns.yml` template, agent helper bins) | `pip install` (editable for dev; pipx for runtime)        |
| **Claude plugin** | `.claude-plugin/marketplace.json` at repo root → skill `/kanban` (thin: shells to the `kanban` CLI) + agent helper commands            | `claude plugin marketplace add` + `claude plugin install` |

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
                         │         → sleep(fixed 10 s interval)          │
                         └───────────────────┬──────────────────────────┘
                                             ▼  one tick =
   GitHub Projects v2  ◀── cheap_probe (items orderBy UPDATED_AT first:5)
   (GraphQL, PAT)      ◀── snapshot (only if probe changed; cursor-paginated)
                                             │
                                  diff(persisted_state, snapshot) → [Transition]
                                             │
           ∀ transition:  decide_transition(from,to,transitions) → Action ──┬─ LaunchAction
                                                             ├─ RunScriptAction
                                                             ├─ RollbackAction
                                                             ├─ TeardownAction (Cancel col)
                                                             ├─ ResetAction    (Cancel→Backlog)
                                                             └─ BlockAction    (dep gate / rate)
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

`decide` is **`decide_transition(from, to, transitions)`** against the per-`(from,to)` whitelist
(§8), yielding `launch | run_script | noop | rollback` (+ the runner-added
`skip | queue | block | teardown | reset`). The action set is
`LaunchAction | RunScriptAction | RollbackAction | TeardownAction | ResetAction | BlockAction`.
**Before** each launch the runner `reserve_slot`s (§8.4.1); on cap-full it writes a queue marker
(§8.4.2). The "drain queue" post-step is now **live** (dequeue when a slot frees), not a stub.

### 3.2 Layering — hexagonal (ports & adapters)

```
cli/ (typer) ─┐
              ├─▶ app/ (orchestration) ─▶ core/ (pure, zero I/O)
daemon/ ──────┘                       └─▶ ports/ (Protocols)
                                           ▲
                             adapters/ ────┘  (github · workspace · store · clock)
```

Import direction is **downward only**, enforced by a layering guard (mirrors the `acquire/` guard
in PersonnalScaper). `core` depends on nothing; `ports` are Protocols; `adapters` implement them;
`app` is the composition root; `cli`/`daemon` are entrypoints.

### 3.3 Module map

**`core/` (pure, testable with no I/O)**

- `domain.py` — `Ticket, Column, ColumnClass{reactive|inert}, BoardSnapshot, Transition, Decision, Action`
- `diff.py` — the heart of polling: `(persisted_state, fresh_snapshot) → [Transition]` (replaces all payload parsing)
- `decide.py` — `decide(transition, ctx) → Action` (pure; carried over from PoC)
- `columns.py` — column-class resolution from the `columns.yml` model
- `antiloop.py` — target-keyed guard + per-ticket rate-limit (pure given state)
- `dependency_gate.py` — parse `Depends on #N`, evaluate against board state
- `interval.py` — poll-interval **strategy**: a **fixed 10 s cadence by default** (idle back-off disabled); the geometric active/idle back-off is opt-in only (explicit `idle_max > base`)

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

**Restored modules (per the transition-whitelist model, §8):**

- `core/transitions.py` — parse `transitions.yml` → `TransitionConfig` (whitelist + wildcards), PURE.
- `core/dispatch.py` — `decide_transition` (PURE, four verdicts).
- `core/placeholders.py` — `fill({{key}})`, PURE.
- `app/` — the runner glue: `reserve_slot`/`release_slot` gate, queue write/drain, `_guarded_rollback`,
  `_on_fail`/fix-CI cap, `_auto_move` (advance), prompt `fill` + launch.
- `adapters/workspace/` — `ensure_clone` (tokenless credential helper), `provision_worktree_skills`,
  `ensure_manual_merge_mode`, flock `resource_lock`.
- `adapters/store/` — persisted `slots/`, `queue/`, `moves/`, `retries/` markers (the durable
  cap/queue/rate-limit/retry ledgers).

Layering is preserved: `core/transitions.py` / `core/dispatch.py` / `core/placeholders.py` are PURE
(zero I/O); the cap/queue/clone/provisioning side-effects live in `adapters/` behind `ports/`; the
runner composition lives in `app/`. Downward-only imports (enforced by `tests/test_layering.py`).

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

- `Depends on` rewrite, in Backlog).

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
- **Hang protection** (PM2/launchd restart on _exit_, not on _hang_): (a) mandatory HTTP
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

| #   | Requirement                                                                                                                                                                                                                                                                                                                                                                                        |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H3  | **Pagination**: `projectItems` GraphQL cursor-follow (board with many items must not truncate)                                                                                                                                                                                                                                                                                                     |
| H4  | Permission profiles **materialised** into the worktree's `.claude/settings.json` (`defaultMode` pinned — mitigates mid-session reset #39057); four per-stage profiles `docs`/`prepare`/`dev`/`check`, each a concrete `permissions.allow`; all four ban `gh pr merge`, `git push --force`, history rewrite. The same worktree settings file also carries the **PostToolUse heartbeat hook** (§8.3) |
| H5  | **Kill-switch** `~/.kanban/PAUSE` → downgrade all profiles to `docs` (the minimal floor) + **unattended-hours** window → zero launches                                                                                                                                                                                                                                                             |
| H6  | **Real captured GraphQL responses** (board snapshot, fieldValueByName, move mutation) as fixtures — replaces synthetic fixtures and pins the exact shape                                                                                                                                                                                                                                           |
| H7  | **Real GitHub integration tests** actually executed against a dedicated test org/Project (no longer gated-and-skipped-forever) — see §7                                                                                                                                                                                                                                                            |
| H8  | **Rolling project status-update dashboard** (§8.7): ONE on-change status update in the Project's "Status updates" section — running agents + per-agent live progress + recent events + health enum, refreshed only when the rendered body changes (no per-tick spam), wholly **fail-soft** (observability, never a launch blocker; a stale id self-heals via create-fallback)                      |

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

## 8. Board contract — per-`(from,to)` transition whitelist (`transitions.yml`)

The board logic is **NOT** a destination-column-class model. It is a per-`(from_col, to_col)`
**transition whitelist** loaded from `<clone>/.claude/kanban/transitions.yml` (PoC
`transitions.py` + `dispatch.py`; source of truth per §11). The `(from, to)` **pair is the
dispatch key**: a move is legal **only** if its pair (or a matching wildcard) is present in the
whitelist. An un-whitelisted move is **rejected and the card is rolled back** to `from_col`. This
is the board's self-healing guarantee — the board cannot drift into an un-modelled state.

#### 8.0.1 The `Transition` entry (PoC `transitions.py:25–41`)

Each whitelisted entry carries its own action, keyed `(from_col, to_col)`:

| field             | type / default                                    | meaning                                                                                                                                                                                                                                  |
| ----------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `from` / `to`     | `str \| list[str] \| "*"` (required)              | the pair; each side accepts a **single** column, a **list** `[a, b, c]` (expanded at load to the cartesian product of `(from × to)` edges — `[a,b] → [c,d]` ≡ four entries `a→c, a→d, b→c, b→d`), or `"*"` (wildcard, any column)        |
| `profile`         | `str = ""`                                        | permission profile materialised into the worktree settings (`docs`/`prepare`/`dev`/`check`)                                                                                                                                              |
| `prompt`          | `str \| null`                                     | the per-transition LLM prompt template (`{{key}}` placeholders, §8.6)                                                                                                                                                                    |
| `script`          | `str \| null`                                     | a shell script: mechanical action (no prompt) **or** an LLM gate (with a prompt)                                                                                                                                                         |
| `advance`         | `"stop" \| "auto:<col>"` (default `"stop"`)       | on success, auto-move the card to `<col>` (a triggering bot move, §8.4)                                                                                                                                                                  |
| `on_fail`         | `"" \| "move:<col>" \| "rollback"` (default `""`) | failure routing for the script/agent (§8.4)                                                                                                                                                                                              |
| `permission_mode` | `str = "auto"`                                    | `claude --permission-mode` for the launched session; validated against `{default, acceptEdits, auto, dontAsk, plan}`; `bypassPermissions` **banned** (it skips the deny layer); non-string YAML values (`no`/`yes`/`5`/`null`) fail loud |

`has_action = bool(prompt) or bool(script)`. A pair present with NEITHER is an **allowed no-op**
(e.g. `Plan → Ready to dev`).

#### 8.0.2 Wildcards & precedence (PoC `transitions.py:63–78`)

`TransitionConfig.get(from, to)` resolves with **explicit-wins** precedence:
**explicit `(from, to)` pair** > **`(from, "*")`** (any destination from this source) >
**`("*", to)`** (any source into this destination). A `"*" → "*"` entry is **rejected at load**
(`ValueError`). Wildcards model the parking/Cancel rows: `("*", "Blocked")`, `("Blocked", "*")`,
`("*", "Cancel")`, `("Cancel", "Backlog")`.

**List expansion (genesis phase 20).** A `from`/`to` **list** is expanded at load into its concrete
`(from_col, to_col)` edges (cartesian product) before the lookup tables are built, so each expanded
pair is an ordinary **explicit** entry — i.e. a list member `[a, b] → c` wins over a `("*", c)`
wildcard exactly as a hand-written `a → c` would. Precedence is therefore unchanged: **explicit (incl.
list-expanded) > single-side wildcard > **; a list is pure authoring sugar, not a new precedence tier.
A duplicate pair produced by two overlapping list/explicit rows is **rejected at load** (`ValueError`,
no silent last-wins).

#### 8.0.3 `decide_transition` verdicts (PURE — PoC `dispatch.py:42–92`)

The pure decision classifies a `(from, to)` move against the whitelist and returns one of **four**
verdicts; the runner/tick layer adds **five** more (it never returns those four-plus-five on the
pure path — they are constructed around `decide_transition`):

| verdict                     | condition                                                     | effect                                                                                |
| --------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `launch`                    | pair present, has a `prompt` (optionally gated by a `script`) | start an agent in the worktree (run the gate script first if present)                 |
| `run_script`                | pair present, has a `script` but **no** `prompt`              | run the script **mechanically** (no LLM); exit 0 → advance/record, exit≠0 → `on_fail` |
| `noop`                      | pair present, no action                                       | record the column and continue                                                        |
| `rollback`                  | pair **absent** from the whitelist                            | move the card **back to `from_col`** (guarded — see below)                            |
| _(runner-added)_ `skip`     | idempotency / kill-switch / paused                            | record, do nothing                                                                    |
| _(runner-added)_ `queue`    | concurrency cap full (§8.4)                                   | persist a relaunch marker, defer                                                      |
| _(runner-added)_ `block`    | misconfigured board / anti-loop / unattended window           | park in `Blocked`                                                                     |
| _(runner-added)_ `teardown` | a move **into `Cancel`** (§8.2)                               | mechanical raze, no agent                                                             |
| _(runner-added)_ `reset`    | `Cancel → Backlog` (§8.2)                                     | resume re-arm                                                                         |

#### 8.0.4 Guarded rollback (PoC `runner.py:170–209`)

On a `rollback` verdict the runner moves the card BACK to `from_col`, **records the move as a
bookkeeping bot move** (so the resulting board change does NOT re-trigger the dispatcher), comments
`transition not allowed — card returned to <from>`, and persists the column. `_guarded_rollback`
serves **three** PoC paths, all restored: (a) an un-whitelisted transition, (b) a human move into
an agent column **during a live session** (anti-double-session), and (c) an `on_fail: rollback`
script/agent failure (§8.4).

#### 8.0.5 `kanban-move` refusal

`kanban-move` (the agent self-move shim) refuses to move a card into a **launch transition's
target** — the agent must never re-trigger its own stage. The refusal is keyed on the transition
whitelist (a launch target), NOT on a static column class. This preserves merge=human-only: the
`Review → Merge` row is a human-authorised script-gated launch, so an agent cannot self-advance
into it.

#### 8.0.6 Transitions-only model — the agent launches AT THE TRANSITION, never at a column (genesis phase 20 — supersedes the phase-12.6 HYBRID)

> **Operator decision (2026-06-09), revising 2026-06-06.** The PoC has **no** column-class model:
> the agent launches **at the transition** `(from, to)`, never at a column. The phase-12.6 "HYBRID"
> (a per-column `triggers_agent` autonomy gate) was a genesis bolt-on that diverged from the PoC —
> it silently dropped a freshly-init board into a destination-only column model and made the
> early-stage prompts _dormant_, which the PoC never did. It is **removed**. `transitions.yml` is the
> **sole** trigger model; `columns.yml` carries **no launch configuration**.

**The launch is a transition concern — full stop.** Everything that defines a launch lives on the
`(from, to)` entry in `transitions.yml`: `prompt`, `profile` (the permission profile), `permission_mode`,
`script`, `advance`, `on_fail` (§8.0.1). A whitelisted transition that has a `prompt` **always
LAUNCHes** an agent (an interactive, resumable tmux session — PoC parity: every stage launches; an
interactive stage like brainstorm is driven by attaching to its session). There is **no** per-column
autonomy gate, **no** dormant stage, and **no** destination-only column-class path.

**`columns.yml` is minimal — the board's column SET, nothing launch-related.** It declares the columns
(`key` / `name`) and the **non-launch** classification NEW's architecture still needs: `action: teardown`
(the reactive Cancel column — a mechanical raze, NOT an agent launch) and the inert/terminal markers used
to validate the board + resolve the Blocked-park / Backlog-reset targets. The fields `triggers_agent`,
`prompt`, `profile`, `permission_mode`, and `interactive_only` are **all removed** from `columns.yml`
(launch config moved entirely onto the transition, where the launch actually happens).

**`decide.py` is transitions-only.** A `(from, to)` move is resolved against the `transitions.yml`
whitelist (§8.0.2 precedence) and classified by `decide_transition` (§8.0.3): a prompt-bearing pair that
passes the BLOCK guards returns `LAUNCH` unconditionally — there is no destination-column-class check.
The legacy "no-whitelist → destination-only column-class" fallback is **removed**: when a board ships no
`transitions.yml`, the engine falls back to the built-in `DEFAULT_TRANSITIONS` (the shipped PoC flow),
**never** to a column model. This closes the silent-degradation footgun (a stale/missing `transitions.yml`
ran a non-PoC model unnoticed) and restores strict PoC fidelity.

### 8.1 Sticky comments per step (agent→ticket signalling)

`kanban-comment --sticky <step-key>` keeps **one comment per (ticket, step)** updated in place via
an HTML marker (`<!-- kanban:step=<column-key> -->`): list the issue's comments, match the marker,
**edit** the existing one or **create** it if absent. Append mode stays for free-form notes. Durable
progress surface that doesn't spam the timeline.

> **Operator decision — rich two-zone signalling, full PoC parity (genesis phase 8.1).** Beyond the
> in-place marker above, the shipped subsystem (ported from the PoC `engine/stage_comment.py` per the
> §11 source-of-truth clause) is **two-zone**: a HEADER zone owned by producers-with-proof and a
> `**Progress**` BODY zone the agent appends to; a header update preserves the body and vice-versa.
> The header carries a status **badge + English label** spanning the FULL lifecycle, with all FIVE
> producers wired: 🟡 `in progress` (launch) → ✅ `done` (forward advance) / ⚠️ `interrupted`
> (session-end without an advance breadcrumb) / ⛔ `blocked` (reaper) → ❌ `cancelled` (teardown).
> Badge labels are ENGLISH (NEW's English-only artifact rule), not the PoC's French. The advance
> breadcrumb (issue-keyed, written synchronously before the agent exits) is the ✅/⚠️ discriminator.

### 8.2 Cancel column — teardown + resume

A **`Cancel`** reactive column. A card moved into it triggers **full teardown** (`TeardownAction`),
sharing the teardown core with the `kanban cancel` CLI.

> **Operator decision — full PoC-parity teardown (genesis phase 8.2).** The shipped teardown follows
> the PoC `engine/teardown.py` (the §11 "PoC code is the source of truth for §8.1/§8.2" clause):
> kill the tmux session (guarded), `worktree remove` **with `--force`** (a cancelled worktree is
> almost always dirty), local `git branch -D <feat>` (the dispatcher is the ONE mechanical path
> allowed to delete — the agent deny-list still bans it), purge persisted state + the advance
> breadcrumb, flip every OPEN stage sticky to ❌ `cancelled`, and a recap comment; plus the remote
> step **close the open PR but KEEP the remote branch** (close ≠ merge; merge stays human-only). This
> supersedes the earlier sketch ("`worktree remove` (no `--force`)", no branch/PR step), which
> predated the PoC-parity decision.

**Resume**: a **Cancel → Backlog** transition (`ResetAction`) purges the ticket to a clean,
re-startable state (fresh uuid/worktree on a later move into an agent column). Both Cancel and Backlog
are non-agent, so neither move relaunches an agent; teardown keys on the destination (`Cancel`), reset
on the transition (`Cancel→Backlog`).

### 8.3 Agent liveness heartbeat (PoC #67 — shipped)

Two **distinct** heartbeats exist, do not conflate them:

- **Agent heartbeat** (this section) — proves the _agent_ is working.
- **Daemon heartbeat** (§5) — proves the _daemon_ is alive; `kanban doctor` checks it.

`LaunchAction` bakes a **PostToolUse hook with matcher `"*"`** into the worktree's
`.claude/settings.json` (alongside the H4 perms), so it fires after _every_ tool the agent uses.
Per the Claude Code hook schema the hook is a **command string with the issue baked in by the
dispatcher** (`kanban-heartbeat <issue>` — a command string, **not** exec-form args); the hook's
stdin JSON payload is ignored. Each firing calls `Store.touch_heartbeat(issue, now)` — an
**atomic** (temp + `os.replace`) write that refreshes `state[issue].heartbeat`. A working agent
therefore never stales; an agent that _stops emitting tools_ for the whole TTL goes silent and is reaped.

Hard contracts of the shim (`bin/kanban-heartbeat`):

- **Always exits 0** (non-blocking, zero influence on the agent); exit 2 would _block_ the agent and
  is never emitted. A bare `try/except` swallows any missed heartbeat.
- **Import-light**: argv is parsed to `int` _before_ importing `kanbanmate`, so a missing/non-int
  arg short-circuits to exit 0 without paying the package-import cost (it fires synchronously after
  every tool; cold start ~100 ms, negligible and never blocking).
- **No resurrection**: `touch_heartbeat` is a **no-op when `state/<issue>.json` is absent**, so a
  late hook firing _after a Cancel teardown_ (§8.2) never recreates a torn-down ticket's state.

The daemon's reap step (part of every `tick`) blocks a `running` ticket whose agent heartbeat is
older than `HEARTBEAT_TTL` (default 1800 s): comment + move to `Blocked` + kill the dead session +
release the slot. A retry refreshes the heartbeat so the next tick does not immediately re-block it.

### 8.4 Concurrency cap, queue, move rate-limit & fix-CI retry (restored from PoC)

These four runaway/workload guards were ported as primitives but left **unwired** (the cap slot is
dead code, the queue is a stub). They are restored as live behaviour.

#### 8.4.1 Concurrency CAP — reserve before launch (PoC `engine/cap.py`, `runner.py:706,756–770`)

Active sessions are markers under `~/.kanban/slots/`. **Before** every launch the runner calls
`reserve_slot(kanban_root, cap, ticket)`: count + reserve happen in **one critical section** under
`flock("cap")` (PoC `engine/locks.py`) so two simultaneous ticks can never both reserve the Nth
slot (TOCTOU-safe). Reservation is **idempotent per ticket** (a re-tick of an already-running ticket
returns `True` without consuming another slot). `cap` is `transitions.yml`'s `concurrency_cap`
(default 3). **On ANY `start_session` failure the reserved slot is released and the error re-raised**
— no slot leak (PoC `runner.py:756–770`). The success path does NOT release; the slot is released by
`kanban-session-end` when `claude` exits, by `TeardownAction`, and by `ResetAction`.

#### 8.4.2 QUEUE — defer on cap-full, drain on slot-free (PoC `runner.py:706–732`, `engine/reaper.py`)

When `reserve_slot` returns `False` (cap full) the runner persists a **self-contained relaunch
marker** `~/.kanban/queue/ticket-<n>` carrying EVERY input needed to relaunch later (it never
re-derives from config): the filled `prompt`, `profile`, target `column` + `to_option_id`, the
GitHub coordinates, `clone_dir`, `config_dir`, `dev_repo_path`, and `concurrency_cap`. It records
the column and returns a `queue` verdict. The **reap step drains the queue** (a `dequeue` action)
**only when a slot frees**: it reserves, relaunches **while the marker still exists**, unlinks only
on a confirmed start, and on empty/invalid inputs releases-the-slot-and-keeps-the-marker (no leak,
no silent drop). `queue_dir()` and the marker are purged by teardown.

#### 8.4.3 Per-item move RATE LIMIT — durable backstop (PoC `state.py:305–317`, `runner.py:504–518`)

A per-item move history persisted on disk (`moves/item_<item>.json`) over a 3600 s window backs the
§6 runaway-loop backstop: when an item has made `>= move_rate_limit_per_hour` **AUTO/bot** moves
within the hour, the runner **parks the card in the `Blocked` column** (a visible board move +
comment) instead of acting. Fed ONLY by auto/bot moves (`advance:auto`, `on_fail:move`, rollback
bookkeeping), **never** by human-paced launches. The cap is **configurable per deployment** via
`move_rate_limit_per_hour` (default 10). **Durability matters**: because the history is on disk, the
per-hour cap holds across daemon restarts/crashes — the in-memory `core/antiloop.py` shadow alone
resets to empty on restart and silently hard-pins the cap at 10, which this restore corrects (wire
the YAML knob; persist the history).

#### 8.4.4 Fix-CI RETRY (N=2) — bounded `on_fail:move` loop (PoC `runner.py:45–47,536–570`, `state.py:205–225`)

`on_fail: move:<col>` performs an AUTO bot move that **DOES re-trigger** the next transition (the
CI-fix loop, e.g. `PR Ready → Implement → PR Ready`), bounded by a per-loop budget `_FIXCI_CAP = 2`
keyed by destination column (`onfail:<col>`), backed by a persisted per-`(item,key)` retry ledger
(`retries/<safe-item>__<key>`, `bump_retry`/`reset_retry`). **Beyond the cap the ticket is parked in
`Blocked`** (`_park_blocked`: bookkeeping move + comment). `on_fail: rollback` / `""` rolls the card
back to `from` (guarded, §8.0.4). The reaper additionally relaunches a dead session at most
`RETRY_LIMIT = 1` time (refresh heartbeat + relaunch) before parking in `Blocked` (DESIGN §8.3 already
promises this; restore the implementation).

### 8.5 Per-repo clone bootstrap, worktree provisioning & launch argv (restored from PoC)

#### 8.5.1 `ensure_clone` — tokenless local clone with credential-helper isolation (PoC `engine/worktree.py:20–97`)

`kanban init` creates the per-repo **local git clone** at `<root>/clones/<name>` — the BASE of all
per-ticket worktrees. The clone is created idempotently and **NON-destructively** (`git init` in
place when a dir already exists, preserving any generated `transitions.yml`; never delete-and-reclone),
`origin` set/added idempotently, and `git fetch origin <base>` run (working tree stays empty; the
worktrees carry the checkouts). The launched agent therefore must NOT be assumed to operate against a
pre-existing operator clone (the over-simplification told the operator to `cd` into a clone manually).

**Token isolation (a SECURITY behaviour, security-tested in the PoC).** `origin` is kept **tokenless**.
When a `token_path` is given, `ensure_clone` installs a **git credential helper** that reads the PAT
from a 600-mode file **at fetch time** — the token is **never persisted in `<clone>/.git/config`**
(only the helper command + the file path are). An empty `""` helper entry is added FIRST to clear the
inherited helper chain for the host (so osxkeychain / git-credential-manager cannot shadow ours).
This raises the bar against an agent exfiltrating a long-lived credential from inside its worktree. (NOT
a sandbox: same-UID absolute-path access remains; true isolation needs a separate execution boundary.)

#### 8.5.2 Worktree skill provisioning (PoC `engine/perms.py:351–391`, `engine/launch.py:233`)

A worktree is a clone checkout where `.claude/` is **gitignored** — so a launched agent has **none**
of the `/implement:*` skills (they live in the project's config repo). Before each launch,
`provision_worktree_skills(worktree, config_dir)` **COPIES** the project's
`.claude/{skills,commands,agents}` into `<worktree>/.claude/` so the column prompt resolves. It
**copies, not symlinks** (a write the agent makes inside its worktree cannot propagate through a
symlink to mutate the shared config repo), and **REFRESHES** on every launch (current skills). The
registry persists this path as `ProjectEntry.config_dir` (computed at `init`, threaded into launch +
the queue marker). `ensure_manual_merge_mode(worktree)` additionally pins the worktree's
`IMPLEMENTATION.md` to `**PR merge**: manual` so an auto-triggered `/implement:pr-review` hands off to
a human instead of squash-merging unattended — **defense-in-depth alongside** the deny-list.

`provision_worktree_bin(worktree)` (phase 38) additionally SYMLINKS the engine's OWN `kanban-*`
helper console scripts into `<worktree>/.claude/kanban-bin/`, and the launch prefixes the composed
command with `export PATH=<quoted kanban-bin>:"$PATH"; ` so both `claude` and the trailing
`; kanban-session-end <issue>` resolve the helpers from **the interpreter actually running the
daemon**. An orchestrated agent's tmux session inherits the shell's `pyenv global` python, and pyenv
shims dispatch per ACTIVE version — so a helper entry point added after a stale global install (the
live `kanban-update-body` 127 case) would otherwise be unresolvable. The symlink targets are the
RESOLVED absolute scripts (`shutil.which` then the `sys.executable` scripts dir, via the shared
`_resolve_console_bin`); an unresolved helper is skipped fail-soft with a logged warning; each launch
refreshes the links (idempotent). The dir holds ONLY `kanban-*` symlinks, so it has zero impact on
the project's own python/pip. `doctor` gains an advisory `pyenv twin` check that WARNS (never blocks)
when `~/.pyenv/version` differs in MAJOR.MINOR from the engine interpreter.

#### 8.5.3 flock locks (PoC `engine/locks.py`)

Advisory `fcntl.flock` locks serialise clone mutations per repo (`flock(<repo>)` around
fetch/worktree-add/remove) and the cap count+reserve critical section (`flock("cap")`). Resource
names are sanitised (`[^A-Za-z0-9._-] → _`) so a name cannot escape the `locks/` dir.

#### 8.5.4 Launch argv (PoC `engine/launch.py:80–115`)

The launched session runs:
`claude --session-id <uuid> --permission-mode <mode> --add-dir <worktree>`.
`--session-id` is the single-source-of-truth uuid (resumable via `claude --resume <uuid>`),
`--permission-mode` is the **per-transition** mode (default `auto`; bypass rejected),
`--add-dir <worktree>` scopes the session. The command is suffixed with
`; kanban-session-end <issue>` (`;`, not `&&`, so the session-end finalizer ALWAYS fires and the
cap slot is always released). Each argv element is `shlex.quote`d (worktree paths may contain spaces).
Registry inputs `config_dir` / `dev_repo_path` are threaded into `start_session` and persisted into
state + the queue marker so the reaper can relaunch by reading them back.

### 8.6 Prompt routing — per-transition template (`placeholders.fill {{key}}`) (restored from PoC)

**The agent runs the per-transition prompt template — NOT a bare global `agent_command`.** The
over-simplification launched a single static `claude` (default `agent_command`) for every agent
column, with **zero ticket-context injection** — the agent received no slash-command and no ticket
body/comments. The PoC routes a **per-`(from,to)`-transition prompt** through `placeholders.fill`.

#### 8.6.1 `placeholders.fill(template, ctx)` (PoC `placeholders.py`)

A pure `{{key}}` / `{{a.b}}` substitutor with dotted-path resolution that **FAILS LOUD** (`KeyError`)
on any unknown key. At dispatch time the runner builds the launch context and substitutes it into the
matched transition's `prompt` **before** typing it into the session (PoC `runner.py:704`:
`decision.prompt = fill(decision.prompt, ctx)`).

#### 8.6.2 The fill context (PoC `runner.py:686–703`)

`ctx` is assembled live per launch from GraphQL + persisted state (both of which polling still has):
`code`, `title`, `branch`, `script_output` (the gate script's stdout, §8.0.3), `ticket_body`,
`issue_body` (the first cross-referenced/linked issue body), `comments` (up to 50 comment bodies),
`codename`, `design_path`, `plan_paths` (parsed from the ticket body), `base_clone`, `dev_repo_path`.
The `ticket_body`/`issue_body`/`comments` come from the GitHub adapter's **`issue_context`** query
(issue body + up to 50 comments + first linked issue), fail-soft — also restored.

#### 8.6.3 The shipped templates (PoC `cli/transitions_yaml.py:39–87`; brainstorming split — genesis phase 26)

Seven per-transition launch templates ship in the default `transitions.yml`:
`_BRAINSTORM_PROMPT` (`/implement:brainstorm`, Backlog → Brainstorming — the ONLY interactive one),
`_DESIGN_PROMPT` (autonomous design, Brainstorming → Spec), `_PLAN_PROMPT` (`/implement:plan`,
Spec → Plan), `_PREPARE_PROMPT` (`/implement:create-branch`), `_IMPLEMENT_PROMPT` (`/implement:phase`),
`_FIXCI_PROMPT` (CI-red fix), `_REVIEW_PROMPT` (`/implement:pr-review` — explicitly _without_ merging).
There is deliberately **no** `_MERGE_PROMPT` (merge stays human, §10): `Review → Merge` is a script gate.

> **Autonomy split (genesis phase 26, e2e-driven).** Only `_BRAINSTORM_PROMPT` is **interactive** — it
> tells the agent it MAY ask the user clarifying questions (the tmux session is resumable, so a human
> `tmux attach`es to answer) and to write the brainstorm OUTPUT + a `**codename**:` line into the ticket
> body, NOT the formal design. **Every other agent prompt** (the autonomous `_DESIGN_PROMPT`, `_PLAN_PROMPT`,
> `_PREPARE_PROMPT`, `_IMPLEMENT_PROMPT`, `_FIXCI_PROMPT`, `_REVIEW_PROMPT`) carries a shared `_AUTONOMY`
> instruction — _"Run fully autonomously — do NOT ask the user any questions; make reasonable
> assumptions for any gaps and proceed; do NOT invoke an interactive brainstorming Q&A."_ — so an
> unattended orchestrated session never hangs on a question (the first live e2e exposed exactly that
> hang; without this the reaper would churn the stalled session).

> **Language note.** The PoC templates are in **French**. NEW's English-only artifact rule governs
> docs and _user-facing GitHub stickies_ (§8.1). The launch _prompt_ is an internal instruction typed
> into the agent's session, not a published artifact; the shipped constants are translated to English
> for codebase consistency, but the **placeholders, slash-commands and routing are load-bearing and
> are ported faithfully**.

#### 8.6.4 Agent discipline — hardened-prompt constants (genesis phase 29)

Every launch prompt is assembled from a small set of shared **hardening constants** prepended to the
per-transition body (`core/transitions_defaults.py` `_SCOPE_GUARD` / `_IDENTITY_THEN_STATE` /
`_STATE_CHECK_LATE` / `_DESYNC` / `_AUTONOMY`). They encode the autonomous agent's operating
discipline so a launched session behaves predictably and idempotently:

- **Scope guard** — change ONLY what the transition asks for; never refactor beyond the task. Bounds
  the blast radius of an autonomous edit (the agent has push rights on its own branch).
- **Identity-then-state** — establish the ticket identity (`{{code}}`/`{{codename}}`) FIRST, then
  check the live state (the worktree, the open PR, the CI), because a re-entry (the diff re-fired the
  move) must VERIFY-and-finalize rather than redo work.
- **Late state-check + desync** — captured inputs (`{{script_output}}`) may be STALE by the time the
  agent runs; re-check the LIVE state before acting, with a fast path when it is already green.
- **Autonomy** — no clarifying questions except in the single interactive `Backlog → Brainstorming`
  step (the only place a human `tmux attach`es); every other prompt carries the autonomy clause.
- **Blocked-not-Cancel late exits** — a late-stage agent that recognises its feature is already
  shipped exits to `Blocked` (operator-visible, non-destructive), NOT `Cancel` (operator-only
  teardown). Early stages exit to `Done` (the skip-to-Done whitelist boundary, §9).
- **Binding move chain** — the agent's terminal `kanban-move` is the load-bearing advance: durable
  outputs (the pushed branch / open PR) MUST exist BEFORE the move, and the dual advance mechanism
  (the prompt move + `advance:auto:<col>`) is the engine's idempotence backstop.

> This subsection is the deferred phase-29.5 doc landed by phase 30 (#6) — the gate-checklist
> "DESIGN delta present" line exists precisely so a behaviour-changing phase no longer closes without
> it. The comprehensive §8.x re-sync (the WAITING 6th-state pass, §8.5.4 send-keys three-step) stays
> deferred to the operator-signalled doc pass.

### 8.7 Project status updates — rolling on-change orchestration dashboard (phase-24)

KanbanMate maintains ONE **rolling** status update in the GitHub Project's "Status updates" section
that surfaces live orchestration activity: the agents currently running (with each agent's latest
progress milestone), the launch-queue depth, the recent significant events, and an overall **health**
mapped onto GitHub's `ProjectV2StatusUpdateStatus` enum (`INACTIVE | ON_TRACK | AT_RISK | OFF_TRACK |
COMPLETE`). The user-facing strings are **French** (operator decision for the live dashboard) —
distinct from the ENGLISH issue-comment stickies of §8.1.

The work splits cleanly across the hexagon:

- **`core/status_update.py` (pure)** — the value objects (`RunningAgent`, `StatusEvent`,
  `OrchestrationState`) + a single PURE `render_status(state) -> StatusUpdateRender(body, status)`.
  `now` is injected, no clock/network — fully unit-testable.
- **`ports/board.py` `ProjectStatusReporter`** + the GitHub adapter — `create_status_update` /
  `update_status_update` / `delete_status_update` over `createProjectV2StatusUpdate` /
  `updateProjectV2StatusUpdate` / `deleteProjectV2StatusUpdate`, carrying the client's mandatory
  connect+read timeouts. The delete mutation selects **`deletedStatusUpdateId`** — the
  `DeleteProjectV2StatusUpdatePayload` type has **no** `statusUpdate` field, so the earlier
  `statusUpdate { id }` selection made GitHub reject every delete (orphans stacked up, observed live:
  52 on a retired board). **`ports/store.py`** persists the rolling update id, the last-posted body
  hash, **the last-posted status enum** (`status/last_status`, drives the re-create-on-enum-change
  below), and a bounded recent-events ring (≤10 newest) under `~/.kanban/status/`.
- **`app/status_reporter.py` `report_status(...)` (the imperative half, phase-24 §24.3)** — the
  tick's **fail-soft last step** (after reap + drain + heartbeat). It (1) appends THIS tick's executed
  actions to the events ring (translating each action → a coarse event kind: launch / teardown /
  gate_pass / gate_fail / auto / block / reap); (2) builds the `OrchestrationState` from the store's
  running tickets + the snapshot (titles + current columns) + the queue depth + the concurrency cap +
  the kill-switch flag, reading each running agent's latest progress off its issue sticky via the
  stage-comment marker/parse helpers (**individually fail-soft** — one bad sticky read degrades only
  that agent's progress to `None`, never the whole update); (3) renders, hashes the body, and posts
  **on change only** — an equal stored hash means the dashboard is unchanged, so NO API call. On a
  change it posts — choosing the mutation by whether the **health enum changed** (see the GitHub-pill
  note below): an enum change (or first post) **re-creates** the rolling update and deletes the
  superseded one; a body-only change (same enum) takes the cheap in-place `update` (with a fresh
  `create` + re-store as the **fail-soft fallback** when the stored id went stale/deleted). It then
  persists the new id + body hash + last-posted enum.

**GitHub pill quirk — why an enum change RE-CREATES (live-bug fix, 2026-06-13).** GitHub refreshes a
Project's denormalised "Status" PILL (the colour shown in the UI / project list) **only when a status
update is created**, never on an in-place `update`. An in-place `update` does change the record's body

- status fields the GraphQL API returns, but the project pill stays frozen at the value the rolling
  update had **at creation**. The original design edited ONE record in place forever, so a board created
  `OFF_TRACK` (a transient block at seed time) stayed visually `OFF_TRACK` for days while the API record
  read `ON_TRACK` — indistinguishable from a stuck orchestrator. The reporter therefore re-creates the
  rolling update whenever the enum changes (the only operation that moves the pill), tracking the
  last-posted enum in `status/last_status`; body-only churn still updates in place to avoid pill
  thrash/spam. The superseded record is best-effort deleted (now that `delete_status_update` works) so
  the board keeps a single rolling pill.

**Fail-soft everywhere (load-bearing):** the rolling status update is **observability, NEVER a launch
blocker**. `report_status` wraps its entire body so any exception (network, parse, missing data) is
logged at WARNING and swallowed — it can never raise into the tick or block a launch. The tick wiring
is therefore a thin, guarded call; all the gather/render/diff/post logic lives in the reporter module.

**Health mapping** (`compute_status`, first match wins): `paused` → `INACTIVE`; a blocking/failure
event (block / gate_fail) or an agent parked Blocked → `OFF_TRACK`; a degraded signal (a stale agent,
a reap/relaunch or rate-limit-park event, or queue > cap) → `AT_RISK`; fully idle (no agents, no
events) → `COMPLETE`; else `ON_TRACK`.

## 9. Default columns & default transition table

> **Transitions-only board, unified column KEYS (genesis phase 20, operator decision 2026-06-09 —
> supersedes the phase-12.6 hybrid; brainstorming split — genesis phase 26, e2e-driven).** The shipped
> defaults are keyed to NEW's **unified column key set** — the PoC's keys **plus** a `PrepareFeature`
> key (the create-branch stage NEW lacked) **plus** the two phase-26 columns `Brainstorming` (after
> Backlog) and `Plan` (after Spec) — for a total of **14 columns**. Phase 26 repurposes `Spec` to the
> autonomous **design** step and `Planned` to a **human checkpoint**. `DEFAULT_TRANSITIONS` and the
> prompt constants live in `core/transitions_defaults.py`; `columns.yml.tmpl` ships the matching 14
> columns as a **bare set** — `key`/`name` + `action: teardown` (Cancel) + inert/terminal markers
> only. **All launch config — `profile`, `prompt`, `permission_mode`, `script`, `advance`, `on_fail`
> — lives on the transition** (the table below: `profile` is a transition column), because the agent
> launches at the transition, never at a column. `columns.yml` carries **no** `triggers_agent` /
> `prompt` / `profile` / `permission_mode` / `interactive_only`.

**PoC display-name → NEW key map** (the renames; the rest are identical). Phase 26 adds two NEW keys
with no PoC ancestor — `Brainstorming` and `Plan` — and repurposes `Spec` (autonomous design) and
`Planned` (human checkpoint):

| PoC display name    | NEW key                                                        |
| ------------------- | -------------------------------------------------------------- |
| Design              | `Spec` (repurposed: autonomous design, Brainstorming → Spec)   |
| Plan                | `Planned` (repurposed: human checkpoint)                       |
| Ready to dev        | `ReadyToDev`                                                   |
| Prepare feature     | `PrepareFeature` (new — genesis)                               |
| Implement           | `InProgress`                                                   |
| PR Ready            | `PRCI`                                                         |
| _(no PoC ancestor)_ | `Brainstorming` (new — phase 26) · `Plan` (new — phase 26)     |
| _(identical)_       | `Backlog` · `Review` · `Merge` · `Done` · `Cancel` · `Blocked` |

The board provisions the canonical **14 columns**, display order:
`Backlog · Brainstorming · Spec · Plan · Planned · Ready to dev · Prepare feature · In Progress ·
PR/CI · Review · Merge · Cancel · Done · Blocked`.

The shipped **default transition table** (`DEFAULT_TRANSITIONS`) — each row is one whitelisted
`(from, to)` entry with its own action, **keyed to NEW's unified keys**. `defaults`:
`concurrency_cap: 3`, `move_rate_limit_per_hour: 10` (the loader fallbacks are 2 and 10).

| from                                                        | to               | profile | action                                                             | advance       | on_fail             | autonomy        |
| ----------------------------------------------------------- | ---------------- | ------- | ------------------------------------------------------------------ | ------------- | ------------------- | --------------- |
| `Backlog`                                                   | `Brainstorming`  | docs    | prompt `/implement:brainstorm` (`_BRAINSTORM_PROMPT`)              | stop          | —                   | **INTERACTIVE** |
| `Brainstorming`                                             | `Spec`           | docs    | prompt autonomous design (`_DESIGN_PROMPT`)                        | stop          | —                   | autonomous      |
| `Spec`                                                      | `Plan`           | docs    | prompt `/implement:plan` (`_PLAN_PROMPT`)                          | stop          | —                   | autonomous      |
| `Plan`                                                      | `Planned`        | —       | **allowed no-op** (lands in Planned for human review)              | —             | —                   | —               |
| `Planned`                                                   | `ReadyToDev`     | —       | **allowed no-op** (human gate)                                     | —             | —                   | —               |
| `ReadyToDev`                                                | `PrepareFeature` | prepare | prompt `/implement:create-branch` (`_PREPARE_PROMPT`)              | stop          | —                   | autonomous      |
| `PrepareFeature`                                            | `InProgress`     | dev     | prompt `/implement:phase` (`_IMPLEMENT_PROMPT`)                    | **auto:PRCI** | —                   | autonomous      |
| `InProgress`                                                | `PRCI`           | check   | **script** `bin/check-pr-ready.sh` (mechanical, `run_script`)      | —             | **move:InProgress** | —               |
| `PRCI`                                                      | `InProgress`     | dev     | prompt fix-CI (`_FIXCI_PROMPT`)                                    | **auto:PRCI** | —                   | autonomous      |
| `PRCI`                                                      | `Review`         | dev     | prompt `/implement:pr-review` (`_REVIEW_PROMPT`)                   | stop          | —                   | autonomous      |
| `Review`                                                    | `Merge`          | check   | **script gate** `bin/check-merge-ready.sh` (NO merge prompt — §10) | —             | **rollback**        | —               |
| `Merge`                                                     | `Done`           | —       | terminal no-op                                                     | —             | —                   | —               |
| `[Backlog, Brainstorming, Spec, Plan, Planned, ReadyToDev]` | `Done`           | —       | **allowed no-op** — early skip-to-Done whitelist (6 edges, below)  | —             | —                   | —               |
| `*`                                                         | `Blocked`        | —       | parking wildcard                                                   | —             | —                   | —               |
| `Blocked`                                                   | `*`              | —       | un-park wildcard                                                   | —             | —                   | —               |
| `*`                                                         | `Cancel`         | —       | teardown (reactive, §8.2)                                          | —             | —                   | —               |
| `Cancel`                                                    | `Backlog`        | —       | reset / resume (reactive, §8.2)                                    | —             | —                   | —               |

**Autonomy — only Backlog → Brainstorming is interactive (genesis phase 26, e2e-driven).** The
brainstorm is the one step where a human `tmux attach`es to answer the agent's clarifying questions;
EVERY other agent prompt carries the shared `_AUTONOMY` instruction (§8.6.3) — _do NOT ask the user any
questions; make reasonable assumptions and proceed_ — so an unattended orchestrated session never hangs
on a question. The first live e2e (#91) hung on exactly that interactive-brainstorm prompt; this split
fixes it.

**Early skip-to-Done whitelist (genesis phase 26).** A single list-expanded no-op entry
`{from: [Backlog, Brainstorming, Spec, Plan, Planned, ReadyToDev], to: Done}` cartesian-expands to six
explicit no-op edges (no prompt/script) so an agent/human can mark an ALREADY-DONE ticket `Done` without
a rollback — the e2e found an already-shipped ticket (#91) that could be recognised but not retired. It
is **bounded at ReadyToDev**: before `PrepareFeature` there is no worktree/branch, so a direct → `Done`
is safe; from `PrepareFeature` onward a worktree/branch exists, so retirement must go through `Cancel`
(teardown). `Done` is therefore deliberately **NOT** whitelisted from
`PrepareFeature`/`InProgress`/`PRCI`/`Review`/`Merge` — a direct → `Done` there rolls back.
**Done-arrival reclaims orphan worktrees (genesis phase 30, #9).** A card arriving in `Done`
WHILE a worktree still EXISTS for it triggers a DONE-flavoured teardown that reclaims the worktree
(kill session, remove worktree + branch, finalize ✅, purge state) — the card STAYS in `Done`. This
is **keyed on `workspace.worktree_exists(issue)`**, NOT on persisted state: the dominant orphan is a
worktree with NO state (`kanban session-end` purges the state but leaves the worktree, then a human
moves the card to `Done`), which a state-keyed trigger missed. **Unpushed-work guard:** before
destroying anything, `workspace.has_unpushed_work(issue)` is probed (dirty tree or commits ahead of
the remote); on unpushed work the reclaim DOWNGRADES to a loud `Blocked` sticky (the worktree is
KEPT, never silently destroyed) — the operator pushes/merges, then re-`Done`s to reclaim. This
SUPERSEDES the earlier "`Done` is inert — no teardown fires; a stray worktree is harmless residue"
acceptance: a skip-to-Done from `Spec`/`Plan` whose agent created a worktree now reclaims it rather
than leaking it.

**Two transitions land in the SAME destination column `InProgress` but carry DIFFERENT prompts** —
`PrepareFeature → InProgress` runs `_IMPLEMENT_PROMPT`, `PRCI → InProgress` runs `_FIXCI_PROMPT`.
This is the load-bearing reason the model is per-`(from,to)` and **not** per-column: a column reached
from two origins gets two prompts. The 3-class column model could not express this.

**Merge stays human (§10, ratified phase-17 #1).** There is deliberately **NO** autonomous merge
prompt — an `_MERGE_PROMPT` would violate the `gh pr merge` ban. `Review → Merge` ships as a
`bin/check-merge-ready.sh` **script gate only** (a mechanical mergeability check, `on_fail:
rollback` — phase-15.6 fix be5fe2f: a gate-fail must not re-fire; `rollback` is a bookkeeping
return that leaves the card in Review with `baseline=Review`, whereas the re-triggering
`move:<col>` would set `baseline=Merge` and falsely re-fire the gate); `Merge` stays an **inert**
column and a HUMAN performs the squash-merge. The
`bin/check-pr-ready.sh` / `bin/check-merge-ready.sh` helper scripts land in phase 15.

The `implement:*` prompt defaults live **only** in the `transitions.yml` template (per-repo,
user-editable) + the `core/transitions_defaults.py` source — the engine stays generic.

> **Deferred live-board step (post-merge, like §11.7).** An existing live Project v2 needs three columns
> **added** to match the 14-column key set — `PrepareFeature` ("Prepare feature"), and the phase-26
> pair `Brainstorming` and `Plan` (in flow order: Brainstorming after Backlog, Plan after Spec). This
> is a deferred operational step (genesis phase 26.2 performs it on the live board), not part of the
> engine cutover.

> **Note for the plan**: this restores `transitions.yml` as the per-clone whitelist file. The phase-8
> sticky-marker prefix (`<!-- kanban:step=<key> -->`) and the badge lifecycle (§8.1) are unaffected —
> the sticky stage key is the destination column key, which still exists.

## 10. Security & autonomy

Merge = human only (agents push + open PR, never merge); ban `gh pr merge` / `--force` / history
rewrite across all profiles. Four per-stage profiles `docs`/`prepare`/`dev`/`check`, each a
concrete `permissions.allow` + pinned `defaultMode`; `docs` is the minimal floor (the kill-switch
downgrades every profile to it, and an unknown profile name degrades to it). The PoC's fifth
`merge` profile is deliberately absent — there is no agent profile that may merge.
Token in `~/.kanban/token` (600, off-git); v1 = user PAT scoped **`project` + `repo`** (no
`admin:org_hook` — webhooks are gone; anti-loop is target-keyed, not identity-keyed). Kill-switch
(H5). Non-root daemon (tmux socket ownership; `bypassPermissions` refuses under root). GitHub App =
optional future upgrade (§13).

`permission_mode` is configured **per transition** (not pinned per static profile), validated against
`{default, acceptEdits, auto, dontAsk, plan}` with `bypassPermissions` **banned** at load (it would
skip the deny layer / break merge=human-only) and non-string YAML values failing loud. The clone is
**tokenless** with a credential-helper that keeps the PAT out of `<clone>/.git/config` (§8.5.1).
`ensure_manual_merge_mode` pins each worktree to manual merge (§8.5.2) — defense-in-depth alongside
the deny-list.

The launch **profile** resolves from the matched transition's `profile` (`transitions.yml`) **ONLY**
(genesis phase 20, superseding the phase-12.6 two-tier model — the agent launches at the transition, so
its profile is a transition concern; `columns.yml` carries no `permission_profile`). **No column default,
no global default** — a launch whose transition leaves `profile` empty **fails loud**, never falling back
to a column default or a single global profile.

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
- **P5** — sticky comments (§8.1) + Cancel column (§8.2) wired to the transition whitelist + the
  reactive (teardown) column class (Cancel is a REACTIVE column; sticky comments are agent→ticket
  signalling emitted on launch transitions — §8.0.6/§9); docs; cutover + decommission of the old
  location.
