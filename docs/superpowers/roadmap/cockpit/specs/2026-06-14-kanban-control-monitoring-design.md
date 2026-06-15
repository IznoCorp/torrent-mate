# Kanban Control & Monitoring Skill — Design

> **Codename:** `cockpit` (provisional — control + monitoring panel for the board)
> **Status:** Brainstormed 2026-06-14, **adversarially hardened** via an 11-agent design-review
> workflow (7 codebase-verifiers + 4 adversarial critics). On branch `feat/cockpit` (off
> `feat/genesis` — NOT part of the in-flight `genesis` PR).
> **Implementation (2026-06-14 → 15):** PR1 (read-only `kanban state`), PR2 (intent queue +
> `kanban move`), PR3 (`kanban ticket create/edit/close` + `kanban pill set-health/note/clear`) all
> **SHIPPED, gated (1518 tests), pushed, and live-verified** on the daemon. Deferred (documented in
> §7/§12): the sleep-interrupt nudge (10s cadence suffices), result-file GC (TTL sweep), agent
> move-unification.
> **Type:** minor feature (new skill + engine surface), shipped via the KanbanMate plugin marketplace.

## 1. Purpose & vision

A first-class way to **control and monitor** the KanbanMate board (GitHub Projects v2) from Claude
Code, distributed via the plugin marketplace and auto-installed on projects. It surfaces live board +
agent state, and lets callers mutate the board (move tickets, CRUD tickets, drive the status pill) —
**without racing the polling daemon** and **without weakening the autonomy guardrails**.

Two callers, one surface:

- **Operator** (you, interactive in your own Claude session) — broad authority.
- **Autonomous agents** (in their worktrees) — strictly bounded authority.

The `/kanban` skill stays a **thin wrapper** over the `kanban` CLI; all logic lives in the engine
(hexagonal, functional-core / imperative-shell). This design adds engine surface, not skill logic.

## 2. Scope (v1) & non-goals

**In scope (v1, delivered across 3 PRs — see §3):**

- Read/monitoring: an aggregated `kanban state` (board columns + WIP, agent states, queue, recent
  events, health pill), JSON + human render.
- Move tickets between columns (**operator-only in v1** — see §12).
- Ticket CRUD: create / edit / close issues on the board.
- Status pill: operator **override** of the rolling pill + operator notes (NOT arbitrary status-update
  CRUD — preserves the single-rolling-pill invariant of DESIGN §8.7).

**Non-goals (v1):**

- Multi-project / multi-board in one command (the daemon is single-project per `--root`; managing N
  projects = N roots + N daemons today — see §12).
- Unifying the agent `kanban-move` path into the intent queue (deferred — see §12).
- Arbitrary creation/deletion of _separate_ status updates (would break the single-pill invariant).

## 3. Decomposition / roadmap

The full surface is **too large for one plan** (it touches the entire hexagon and several load-bearing
invariants: rolling-pill markers, anti-loop, move rate-limit, diff baseline). It is sliced into three
independently-shippable PRs, each with a green phase gate:

- **PR1 — Read-only `kanban state`.** No writes, no intents, no daemon changes. Pure aggregation +
  JSON/human render. Lowest risk, immediate operator value, and it exposes the marker IDs / shapes
  PR2–PR3 reuse. **This is the first sub-project to plan & implement.**
- **PR2 — Intent spine + operator move.** The `~/.kanban/intents/` queue, the `nudge` wake, the
  `drain_intents` tick step, the **daemon-derived authority model** (§5), and `kanban move`
  (operator). Exercises the full enqueue → nudge → drain → result loop on the simplest mutation.
- **PR3 — Ticket CRUD + status/pill CRUD.** `ticket create/edit/close` (idempotent, anti-trigger
  column) + `pill set-health/note/clear` (single-pill coordination).

Each PR gets its own `/implement` spec → plan → implementation cycle. This document is the **umbrella
design**; PR1 is specified in full (§6); PR2/PR3 are design sketches (§7–§8) refined when they start.

## 4. Architecture

Hexagonal, downward-only imports. New/changed modules:

```
cli/ (state, move, ticket, pill)        skill /kanban (thin wrapper, +commands)
  │
app/ (read aggregation · drain_intents · per-kind executors)
  │
core/ (read_model — pure · intent — pure VO + validate_intent)
  │
ports/ (StateStore +intent methods · Nudge)
  ▲
adapters/ (fs_intents mixin · wake · GitHub adapter [reused as-is])
```

**Write model (PR2+):** a file-backed **intent queue**, with the **daemon as the sole board writer**
(eliminates the daemon-vs-agent `move_card` race that exists today). CLI enqueues an intent + nudges
the daemon; the daemon drains it on its tick; the CLI `--wait` polls the result.

```
CLI (move/ticket/pill) → enqueue_intent(intents/<id>.json) → nudge() → --wait polls intents/<id>.result.json
DAEMON tick: 4a reap → 4b drain_queue → 4c drain_intents → 4d report_status
  drain_intents: load → re-derive authority → validate → execute (GitHub adapter) → result → clear
```

**Read model (PR1):** a **direct read-only** path (no intent), aggregating the same state the
`status_reporter` already gathers. Aggregation lives in **`core/read_model.py` (pure)** fed by an
**`app/`** gather that does the I/O — `core` never imports `cli`/`adapters` (see §6, layering fix).

## 5. Security & authority model (the central reshape)

> The naive approach — a `caller: operator|agent` field set at the CLI boundary and trusted by the
> daemon — is **insecure** and is explicitly rejected. Agents run **non-root as the same UID** as the
> daemon and can write `~/.kanban/intents/`, so they could forge `caller=operator` and bypass every
> guardrail. **The `caller` field is advisory only; it is NEVER the security decision.**

**Authority is re-derived by the daemon at execution time, from state the daemon owns:**

1. **Agent identity = the daemon's launch bookkeeping.** The daemon knows the
   `issue ↔ session ↔ worktree` mapping for every agent it launched. Any intent whose `issue` is a
   **daemon-tracked in-flight agent ticket** is treated as **agent-authority**, regardless of the
   file's `caller` field.
2. **Operator authority = a non-spoofable marker** agents cannot produce (e.g. a file/token under
   `~/.kanban/` whose path agent worktree perms cannot read/write, or the fact that the operator's
   `kanban` invocation is itself denied to agents by the Bash deny-list). Operator-only kinds
   (`ticket_create`, `pill *`, arbitrary moves) are gated on this marker, never on `caller`.
3. **R1 ("touch only your own ticket") is enforced daemon-side**, not via the worktree pin (which may
   be gone after reaper cleanup): an agent-authority intent is bound to the **launching issue** in the
   daemon's bookkeeping; `intent.issue != launching_issue` → **reject**.
4. **Launch re-fire guard uses the resolved transition, not the static column set.** Agent `move`
   validation must reject when `transitions.get(from_col, to_col)` resolves to a **prompt-bearing**
   transition (honouring `(from,*)`/`(*,to)` wildcards) — NOT mere membership in
   `launch_target_columns()`, which deliberately excludes `to='*'` wildcards (a real escalation hole).
5. **Universal deny re-applied daemon-side.** The agent Bash deny-list (`gh pr merge`, force-push,
   history rewrite — `adapters/perms.py`) does **not** cover a daemon-executed intent. The daemon
   executor must independently forbid any intent (or triggered script) that causes merge / force-push /
   branch deletion / history rewrite — incl. an agent `move` into `Merge`.
6. **PAUSE matrix.** Under `~/.kanban/PAUSE`: **hold** (leave pending, don't reject) any
   **agent-authority** intent that could trigger a launch; **allow** operator intents (the operator is
   who acts during a pause). Write an interim result note (`held: board paused`) so `--wait` surfaces
   the reason instead of hanging.

`validate_intent(intent, transitions, columns, authority)` is **pure** and lives in `core/intent.py`;
the **authority** is computed by the daemon (app layer) from its bookkeeping and passed in — the pure
validator never reads the spoofable `caller` field for security decisions.

Cited: `core/transitions.py:183-244` (`get` wildcard resolution, `launch_target_columns` exclusion),
`adapters/perms.py:1-44,313-343` (deny-list, profiles), `bin/_pin.py:50-105` (pin, now advisory).

## 6. PR1 — Read-only `kanban state` (full design)

**Goal:** one command, zero writes, that answers "what is the board + the agents doing right now?"
for both an operator (human render) and agents/scripts (`--json`).

**CLI:** `kanban state [--json]` (the existing `kanban status` board summary stays; `state` is the
richer unified view). Skill: `/kanban state [...]` → `kanban state [...]`.

**Layering fix (blocker from review):** the read-model must **not** import `cli/` types into `core/`
(`tests/test_layering.py` forbids `core → cli`). Resolution:

- `core/read_model.py` (**pure**) defines the frozen value object `KanbanState` and the **renderers**
  `render_state_json(state) -> dict` and `render_state_human(state) -> str`. It reuses the existing
  pure `core/status_update.py` types (`RunningAgent`, `StatusEvent`, `OrchestrationState`,
  `compute_status`, `render_status`). Any value objects currently in `cli/status.py` that `core` needs
  (`QueuedRow`, `DaemonHealth`) are **moved down into `core/`** (cli imports them upward — legal), OR
  re-expressed as plain fields. No `core → cli` edge.
- `app/` owns the **gather** (the I/O): `gather_kanban_state(deps, config, running, snapshot, now) ->
KanbanState`, reusing the `status_reporter` assembly. Extract the existing
  `status_reporter._running_agent(...)` into a shared helper both call (no duplication).

**`KanbanState` (frozen):** `board_snapshot`, `agents`, `queue_depth`, `queue_items`, `events`,
`health` (via `compute_status`), `paused`, `daemon_health`, `now`.

**JSON shape (agent/script API):** `{ board:{columns:{key:count}, total}, agents:[{issue, code,
title, from_col, to_col, profile, launched_at, heartbeat_age, progress, waiting}], queue:{depth, cap,
items:[{issue, stage, age}]}, events:[{ts, kind, issue, detail}], health:{enum, paused, daemon:{ok,
age, failures}} }`.

**Human render:** Markdown, reusing `render_status` body + the health enum (consistent with the live
dashboard).

**No daemon changes, no new persistence.** Pure reads off the board snapshot + store (running tickets,
queue, events ring) + `daemon.heartbeat`. Fail-soft: a missing piece degrades that section, never the
whole view.

Cited: `core/status_update.py:200-227,299-356,419-462`, `app/status_reporter.py:177-242`,
`cli/status.py:65-108,134-187,416-437`, `ports/store.py:588-638,758-780`.

## 7. PR2 — Intent spine + operator move (sketch)

- **Store (adapters):** new `adapters/store/fs_intents.py` `IntentsStateMixin` (mirrors
  `StatusUpdateStateMixin`): `enqueue_intent / load_intent / clear_intent / list_pending_intents /
save_intent_result / load_intent_result`, atomic-write + poison-tolerant. Port: add the 6 methods,
  **typed in terms of the `core/intent.py` `Intent`/`IntentResult` value objects** (not bare dicts).
  - **Prep blocker:** `fs_store.py` is at **998/1000 LOC** → first extract a cohesive block (e.g. the
    `queue/` methods or the move-rate-limit methods) into its own mixin to reclaim headroom; only then
    add the 2-line intents wiring. Post-change LOC is a phase-gate item.
- **Tick step:** `app/intents.py` `drain_intents(deps, config, executor, next_columns, now, *,
kill_switch)` inserted as **4c** (after `drain_queue`, before `report_status`) — placing it _after_
  drain*queue ensures a pathological intent can never starve launches; \_before* report_status ensures
  status/board mutations are reflected in the pill render. **Never raises** (wrapped like
  `report_status`); **per-intent try/except** (one bad intent → log + result + continue).
- **Nudge:** `ports/Nudge` + an adapter. The wake only **shortens sleep** — `drain_intents` ALWAYS
  globs `intents/` regardless of the wake file (a missed wake delays drain by one poll, never loses an
  intent). Reset `last_activity` on drain so idle back-off doesn't stretch latency to 300s. Mechanism
  (signal-to-PID vs wake-file) chosen in PR2 planning; must be PM2 + non-root safe.
- **`kanban move <issue> <column> [--wait]`** — operator move intent. `--wait` has a **bounded
  timeout** + a **daemon-liveness precheck** (`daemon.heartbeat` freshness) → fails fast with
  "daemon may be down — check `kanban doctor`" instead of hanging. An intermediate `claimed` result
  state distinguishes "daemon saw it, working" from "never picked up".

## 8. PR3 — Ticket CRUD + status/pill CRUD (sketch)

- **`kanban ticket create/edit/close`.** `create` is **multi-step** (create_issue + add_to_project +
  set-column are separate GraphQL mutations) → **checkpoint-then-result** idempotency: persist a
  progress checkpoint (`created_issue_number`, `item_id`) in the intent BEFORE the terminal result; on
  failure write `pending` and KEEP the intent to resume; use an idempotency key so a retry never
  duplicates the issue. **Reject (or normalize to Backlog)** a `create` whose initial column is a
  triggering column unless an explicit operator-confirm flag is set.
- **`kanban pill set-health <enum> [--note]` / `pill note <text>` / `pill clear`.** Operator
  **override** of the rolling pill, never a separate status update (single-pill invariant). The daemon
  performs the GitHub mutation AND updates the markers (`update_id/last_status/body_hash`) in one
  critical section; on partial failure write `pending` (not `done`) and let the existing self-heal own
  recovery. `report_status` must respect a **suppression marker** so it does not re-create the pill in
  the same tick merely because the computed enum differs from the operator override (override wins
  until orchestration state changes naturally). Reuses the phase-8.7 re-create-on-enum-change machine.

## 9. Correctness invariants (intent executor, PR2+)

1. **Baseline advance:** after a successful move, set `next_columns[item_id] = to_column` (thread the
   in-memory baseline into `drain_intents`) so a move into a triggering column does **not** re-fire a
   launch next tick. (Intent moves are first-class baseline mutations, not Step-4 side effects.)
2. **Ordering & concurrency:** sort pending intents by `requested_at` (tie-break by id), not glob
   order. For the same issue: process in order with fresh state, or reject all but the earliest
   (`rejected: conflicting intent for issue N`). Move executor re-reads the card's current column and
   rejects on from-state mismatch (**optimistic concurrency**) — no silent clobber.
3. **Intra-tick collision:** if Step 3 (`advance:auto`) already moved an item this tick, defer an
   intent move for the same item to the next tick (`deferred: moved by orchestrator this tick`).
4. **Idempotency / crash-safety:** write a `claimed` marker (or move to `intents/processing/`) BEFORE
   the mutation; write result BEFORE clearing the intent. On restart, a `processing` intent triggers a
   reconcile-not-replay path (check whether the effect already happened).
5. **Single-writer by construction:** ONLY the daemon (holding `daemon.lock`) drains intents; the CLI
   only enqueues + polls. Document + guard this.

## 10. Error handling & fail-soft

- `drain_intents` never raises into the tick; each intent isolated.
- Poison intent (`load_intent → None`): write a `rejected` result ("corrupt/unparseable"), clear the
  marker, log ONE warning (mirrors `drain.py:130-135`) — unblocks the caller's `--wait`.
- **Result GC:** results are removed after a successful terminal read by `--wait`, or TTL-expired by a
  cheap housekeeping pass in `drain_intents` — `intents/` must not grow unbounded.
- Daemon down: `--wait` detects stale `daemon.heartbeat` and fails fast; intents persist and apply on
  the next healthy tick.

## 11. Testing strategy

- **core (pure):** `validate_intent` table tests (operator vs agent × every kind; wildcard
  `to='*'` prompt transition → agent move rejected; agent move into `Merge` rejected; cross-issue
  agent intent rejected). `read_model` render tests (JSON shape + human) from fixed `KanbanState`.
- **app:** `drain_intents` with fakes — ordering, optimistic-concurrency reject, baseline advance,
  per-intent isolation, never-raises, PAUSE matrix, checkpoint-resume for `ticket_create`, status
  suppression marker vs `report_status`.
- **adapters:** `fs_intents` round-trip / poison / atomic-no-residue (mirrors `fs_status_state` tests).
- **cli:** `kanban state --json` shape; `move/ticket/pill` enqueue + `--wait` timeout + daemon-down
  message.
- **layering/size gates:** no `core → cli`; `fs_store.py` under ceiling post-extraction.

## 12. Deferred / out of scope

- **Multi-project on one machine:** today = N `--root`s + N `kanban run` PM2 processes (single-project
  per daemon, `loop.py` "v1 drives exactly one"). A unified multi-board daemon / a cockpit that lists &
  targets multiple roots is a strong **future** candidate (this skill is the natural home).
- **Move-unification:** keep the synchronous agent `kanban-move` (fail-fast, exit-code, breadcrumb, no
  rate-limit) **as-is**; v1 `move` intent is **operator-only** (operators have no move mechanism
  today). Full unification — factoring the move side-effect bookkeeping (rate-limit + breadcrumb) into
  one app-level helper both call — is a separate follow-up once the spine is proven. If/when agent
  moves route through the queue, feed the per-issue move rate-limiter (runaway backstop).
- **Arbitrary separate status updates** (`post/edit/delete` of non-rolling updates): rejected — breaks
  the single-pill invariant.

## 13. Open questions / risks

- **Operator non-spoofable marker (§5.2):** exact mechanism (a `~/.kanban/operator.token` agents can't
  read, vs relying on the Bash deny-list denying `kanban` to agents) — to settle in PR2 planning.
- **Nudge mechanism (§7):** signal-to-PID vs wake-file — to settle in PR2 planning (PM2/non-root).
- **`QueuedRow`/`DaemonHealth` ownership (§6):** move down to `core` vs re-express — settle in PR1
  planning (it's the layering blocker).
- **`fs_store.py` extraction target (§7):** which cohesive block to extract for LOC headroom — settle
  in PR2 planning.
