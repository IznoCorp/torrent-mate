# How it works

KanbanMate is a **polling reconciler with a local source of truth**. Each project's placement
authority is a per-project **`board.json`** on disk (codename **keel**) — _not_ GitHub. GitHub
Projects v2 is a **one-way mirror** of that local board: a move is written to `board.json` first,
then mirrored out to GitHub's Status field. A single background daemon (`kanban run`, PM2-supervised)
polls and reconciles `board.json` against persisted state, fires Claude Code agents, and drives the
board column by column.

> **What changed vs the old model.** Earlier KanbanMate treated GitHub's Status as the source of
> truth and polled it directly ("no webhook, no public endpoint"). That is **stale** for the default
> **native** backend. Today the local `board.json` is authoritative, GitHub is mirrored to (not read
> for placement), monitoring + board views read `board.json` (sub-second, immune to GitHub latency),
> and a secondary drag made _on the GitHub board_ is fed back through a small **webhook receiver**
> (`kanban serve`). Polling is still the reconciliation engine; the webhook only nudges it awake fast.

## Board backends

The placement authority is selected per project (`board_backend` in `~/.kanban-km/projects.json`):

| Backend              | Placement authority | GitHub direction                                | When                                |
| -------------------- | ------------------- | ----------------------------------------------- | ----------------------------------- |
| **native** (default) | local `board.json`  | one-way mirror **out** (native → GitHub Status) | the normal KanbanMateUI-first model |
| **hybrid** (legacy)  | local `board.json`  | mirror out **+** reconcile GitHub drags back in | being retired (ticket #112)         |
| **github**           | GitHub Status       | read + write GitHub directly                    | pure-GitHub boards, no local store  |

A `WiringConfig` built without an explicit value defaults to `native` (`board_mirror=True`), so a
fresh board is on the new one-way system. The backend is the **only** place a concrete board adapter
is named — `NativeBoardBackend` decorates the GitHub client: it overrides `cheap_probe`, `snapshot`,
and `move_card` to use the local store, and delegates every other forge op (issue open/closed,
comments, PRs) straight to GitHub.

## The native one-way model

```
                                  ┌───────────────────────────────────────────────┐
  PM2 supervises  ───────────────▶│  kanban run  (daemon, non-root user)          │
  (restart/boot)                  │  loop:  reload config if changed              │
                                  │         → tick()  per enabled project         │
                                  │         → interruptible sleep (nudge-aware)   │
                                  └───────────────────┬───────────────────────────┘
                                                      ▼  one tick =
  cheap_probe = "{board.json version}:{forge issue probe}"
        │            (changed?  →  full snapshot, else skip)
        ▼
  snapshot = JOIN( GitHub issue set [identity, open/closed]  ✕  board.json [placement] )
        │
  diff(persisted_state, snapshot) → [Transition]
        │
  ∀ transition: decide() → Action ──┬─ LaunchAction   (agent column)
                                    ├─ TeardownAction (Cancel / skip-to-Done)
                                    ├─ ResetAction    (Cancel → Backlog)
                                    ├─ BlockAction    (dep gate / rate / kill-switch)
                                    ├─ RollbackAction (un-whitelisted move bounced back)
                                    ├─ RunScriptAction(mechanical, no-LLM transition)
                                    └─ noop
        │
  then: reap stale agents · drain concurrency queue · drain intent queue · heartbeat
        │
  move_card(item, col):  write board.json (AUTHORITY)  ──▶  mirror to GitHub Status (one-way)
        ▲                                                            │
        │  webhook ingest (a drag made ON GitHub)                    ▼
  kanban serve  ◀── POST /webhook (HMAC) ── GitHub projects_v2_item ── GitHub Projects v2 board
        │  ingest_external_move → board.json → nudge daemon
        ▼
  Agent (claude · tmux · git worktree): works · kanban-comment (sticky) · kanban-move (push/PR, NEVER merge)
        ▲
  You: KanbanMateUI (board + Monitoring, reads board.json) · ssh + tmux attach -t ticket-<n> · claude --resume <uuid> · /kanban
```

### Placement authority — `board.json`

`board.json` (an `FsBoardStateStore`) holds the column each card sits in and the order within each
column. Every write goes through `place_card` / `reorder_column` under an exclusive advisory
`flock`, bumps a monotonic `version`, and is atomic. It is written by:

- the daemon's own `move_card` (auto-advance, reaps, intent drains),
- an operator action in **KanbanMateUI** (board drag / Status change → local write),
- the webhook receiver, when it ingests a drag made directly on the GitHub board.

### One-way mirror to GitHub

`NativeBoardBackend.move_card` writes the native placement **first** (the authority), then mirrors to
GitHub by calling the forge client's `move_card` with the column's **display name** (the GitHub
Status option). A mirror failure is logged and **swallowed** — the local board is already correct, so
a GitHub outage never blocks a move; the next reconcile re-mirrors. GitHub thus keeps showing the
right Status pill + Health chips, but it is a projection, not the truth.

### Reading back a drag made on GitHub

The GitHub board is a secondary surface. A drag there does **not** change `board.json` by itself —
the native snapshot reads placement from the local store, not from GitHub's Status. The
`kanban serve` receiver closes that gap:

1. GitHub fires a `projects_v2_item` event to `POST /webhook`.
2. The receiver verifies the HMAC on the **raw bytes first**, resolves which registered project the
   event hit (`project_node_id`), then calls `ingest_external_move`.
3. Ingestion parses the new Status option name, maps it to a native column key, and — **unless it
   equals the current native placement** (that would be the daemon's own mirror echo) — writes it
   into `board.json` and bumps the version. The "own-writes ledger" is simply the current placement:
   an incoming Status equal to it is a self-echo and is dropped (a single-tick, no-debounce decision).
4. The receiver **nudges** the daemon (the same sentinel the intent queue uses). The next tick's
   `cheap_probe` sees the bumped version, re-snapshots, the `diff` sees the move, and the launch fires.

The receiver never synthesises a transition or a fake snapshot — it only updates `board.json` and
nudges. Reconciliation stays the daemon's single, authoritative computation, so the webhook fast-path
and the slow safety sweep converge on the same `diff` (idempotent by construction). It is hardened
(bounded body read, per-connection slow-loris timeout, method/path allow-list, loopback bind behind
your TLS proxy, refuse-to-start on a missing/placeholder secret, non-root + unprivileged port).

### Monitoring + board views read the local store

KanbanMateUI's board view and the **Monitoring** tab read placement straight from `board.json`, so a
card's column reflects an auto-advance or an operator drag within a single tick (sub-millisecond),
instead of waiting on a GitHub snapshot's TTL (the historical ~22.5 s placement lag is gone). GitHub
is consulted only for ticket **identity** (issue number, title, open/closed), under a separate
5-minute identity-only cache that degrades to last-known values during a GitHub blip — so the board
renders columns + per-card state even while GitHub is unreachable.

## The poll loop (`tick`)

One tick is exactly one reconciliation pass and is the only place the pure core meets live I/O. It is
**idempotent**: re-running with an unchanged probe does no work, and even a forced re-snapshot
produces no duplicate launches (the `diff` compares against persisted state and the anti-loop guard
suppresses re-reactions). On restart the in-memory diff baseline is empty, so the first tick re-syncs
silently from the live board as first-contact — downtime moves are naturally recovered.

1. **cheap_probe** — a combined change-detection token `"{board.json version}:{forge probe}"`. It
   changes when the local store is mutated (any move / reorder / import / webhook ingest) **or** when
   GitHub's newest-items `updatedAt` probe moves (an issue created, closed, edited). A forge-probe
   failure degrades to a native-only token, so a local move still wakes the tick during a GitHub
   outage. If the token equals the previous one, the snapshot is skipped (saves GraphQL budget) —
   unless a nudge opened the fast-poll window, which forces a re-snapshot.
2. **snapshot** — JOIN the GitHub issue set (identity, open/closed) with `board.json` placement.
   First-seen issues are registered at the entry column; an item in the store but absent from the
   forge read is omitted this tick (placement retained) and logged. The result is structurally
   identical to the legacy GitHub path, so `diff` / `decide` consume it unchanged.
3. **diff** — compare the snapshot against the persisted baseline → zero or more `Transition`s.
4. **decide** — classify each transition against the `transitions.yml` whitelist into one Action.
5. **execute** — run the action under a per-action watchdog (a hung `git`/`tmux`/network call aborts
   that action, the tick continues; one bad ticket never aborts the cycle).
6. **reap** — relaunch or park stale agents (heartbeat-based, below).
7. **drain queues** — the concurrency-cap launch queue, then the cockpit **intent queue** (the
   daemon is the _sole_ board writer; operator/CLI moves are enqueued and drained here with authority
   derived from the running set, never a spoofable caller field).
8. **heartbeat / dashboards** — write the daemon's own liveness marker, refresh the rolling Status
   pill, and apply per-card Health chips. All dashboard steps are wholly fail-soft.

### Action model

| Action            | Kind       | When                                                                       |
| ----------------- | ---------- | -------------------------------------------------------------------------- |
| `LaunchAction`    | LAUNCH     | Ticket enters an agent transition → spawn tmux + worktree + claude session |
| `TeardownAction`  | TEARDOWN   | Cancel teardown, or a live agent's card dragged straight to Done           |
| `ResetAction`     | RESET      | Cancel → Backlog → purge state so the ticket can restart fresh             |
| `BlockAction`     | BLOCK      | Dependency gate unmet, move-rate limit hit, or kill-switch active          |
| `RollbackAction`  | ROLLBACK   | An un-whitelisted move is bounced back to its origin column                |
| `RunScriptAction` | RUN_SCRIPT | A mechanical (no-LLM) script transition (e.g. the CI gate)                 |

The launch profile, prompt, `permission_mode`, `advance`, and `on_fail` all come from the matched
`(from, to)` entry in `transitions.yml` — the agent launches **at the transition**, not at a column.

## The nudge + poll cadence

The daemon runs one inter-tick sleep after sweeping all enabled projects, so its base cadence is the
**tightest any project needs**:

- **polling** ingress → tight base cadence (default **~10 s**, a flat fixed poll — the idle back-off
  is disabled by default and only re-engages if you set `idle_max > base`).
- **webhook** ingress → slow safety-sweep fallback (**~120 s**); the webhook nudge collapses the wait
  to one slice for fast reaction.

A native board's primary input is local (KanbanMateUI writes `board.json`; no webhook fires for a
local drag), so a blank ingress on a native/hybrid board resolves to **polling** — i.e. **polling is
the recommended ingress for native boards** so an operator action reacts at the tight cadence out of
the box. (`github`-backed boards keep the `webhook` default.)

### The `.nudge` sentinel

The inter-tick sleep is **interruptible**: it sleeps in ~0.5 s slices and returns early the moment the
daemon-level nudge sentinel `intents/.nudge`'s mtime advances. Anything that wants the daemon awake
**now** bumps it: the CLI `kanban move`, `kanban ticket create`, a KanbanMateUI action (via the intent
queue), and the webhook receiver. So an operator action is drained within one slice (**<1 s**) without
lowering the poll interval (no API-quota cost). A nudge wake also opens a short fast-poll window
(~8 ticks) that forces re-snapshots at the tight base — covering a self-initiated auto-advance whose
mirror lags GitHub's eventual-consistent API, and a `kanban-done` finish where the agent is still
running its final turn. The mechanism is fail-soft (a read failure degrades to the full-interval
sleep) and cross-process (a file sentinel, not an in-memory event, bridges the separate enqueuer and
daemon processes).

A sustained run of tick failures (a dead token's 401-loop, a GitHub outage) trips a geometric
circuit-breaker back-off (capped 300 s) so the daemon stops re-hammering GitHub, snapping back to the
tight cadence on the first clean tick. An auth failure also drops a `DEGRADED` breadcrumb `kanban
doctor` / `kanban status` surface.

## Fast-track lanes (skiff)

Moving a card into **Triage** fires a cheap classifier agent that routes the ticket onto one of three
lanes, by having the engine move the card to the lane's entry column:

```
Backlog ─▶ Triage ─┬─(full)────▶ Brainstorming ▶ Spec ▶ Plan ▶ [Ready to dev = HUMAN GATE] ▶ Prepare feature ▶ In Progress ▶ …
                   ├─(lite)─────▶ Scope (design+plan in ONE pass, no human gate) ▶ Prepare feature ▶ In Progress ▶ …
                   └─(express)──▶ Prepare feature (straight to build) ▶ In Progress ▶ …
```

| Lane        | Entry column    | Design/plan effort                    | Pre-build human gate |
| ----------- | --------------- | ------------------------------------- | -------------------- |
| **full**    | Brainstorming   | brainstorm → DESIGN.md → phased plan  | Ready to dev (yes)   |
| **lite**    | Scope           | compressed mini-design + mini-plan    | none                 |
| **express** | Prepare feature | none (rationale lives in the PR body) | none                 |

The classifier sizes the ticket by **novel design decisions / unknowns / irreversible-or-risky
choices** (not files-touched), checks `sensitive.yml` (any path/keyword/label match forces **full**),
and applies the decision tree: sensitive or un-assessable → full; substantial → full; an explicit
`track:full|lite|express` label overrides only a non-sensitive, non-substantial ticket; small → lite;
trivial → express. The lane map is `TRACK_ENTRY = {full: Brainstorming, lite: Scope, express:
PrepareFeature}`.

After Triage the lifecycle is autonomous: `advance:auto:<col>` on a transition means the engine
auto-moves the card after that stage's agent finishes with a clean `kanban-done`. The **full** lane
auto-advances through Brainstorming → Spec → Plan, then **stops** at _Ready to dev_ (the single
pre-build human gate); the human drags _Ready to dev → Prepare feature_ to start the build. The
_In Progress → PR/CI_ edge is a script gate the engine owns (it auto-advances on green CI to Review).
The review agent auto-advances a card to _Ready to merge_; the **merge is a human drag** (_Ready to
merge → Merge_) in **all three lanes** — agents push and open PRs but never merge.

## How an agent runs

A `LaunchAction` spawns a Claude Code session in a **named tmux window** (`ticket-<n>`) on an
**isolated git worktree** (the per-ticket WIP branch `kanban/ticket-<n>`, so cross-stage artifacts —
DESIGN.md, plan, SCOPE.md — committed by one stage are visible to the next without a push). The
transition's permission **profile** (`docs` / `prepare` / `dev` / `check`) is materialised into the
worktree's `.claude/settings.json` with a pinned `defaultMode`, plus the PostToolUse heartbeat hook.
The agent then:

- runs the transition's filled `/implement:*` (or `/kanban`) prompt;
- posts progress via `kanban-comment` / `kanban-progress` — a **sticky** per-stage comment that the
  daemon flips 🟡 running → ✅ done (or ⚠️) as the stage completes;
- may **re-move its own card** via `kanban-move`, but only to non-triggering columns (the anti-loop
  guard refuses agent-column targets);
- pushes commits and opens PRs but **NEVER merges** — `gh pr merge`, `git push --force`, and history
  rewrite are banned across every permission profile;
- signals completion with `kanban-done`, which clears the done breadcrumb so the engine can
  auto-advance the card on the next tick.

Sessions are **resumable**:

```bash
tmux attach -t ticket-42          # watch / answer a full-lane brainstorm's questions
claude --resume <uuid>            # resume a specific session
kanban sessions                   # list live sessions, flag DEAD ones
kanban cancel 42                  # tear down a ticket's agent (preserves the WIP branch)
```

## Agent liveness — heartbeat

Two distinct heartbeats coexist (do not conflate them):

- **Agent heartbeat (per-tool)** — the launch bakes a PostToolUse hook into the worktree's
  `.claude/settings.json`; it runs `kanban-heartbeat <issue>` after every tool the agent uses. The
  hook always exits 0 (never blocks the agent), is import-light, and is no-op when state is absent
  (a late hook after Cancel teardown never resurrects torn-down state).
- **Reaper (daemon-side)** — every tick checks each `running` ticket. Past a short silence
  (~180 s) it probes the pane for a pending human prompt and flips the card to **WAITING**; past the
  full TTL (default 1800 s) it relaunches the session once, then parks the card in **Blocked**, kills
  the dead tmux session, and releases the slot. A finished-but-idle agent's session-end is **deferred
  until its final turn goes idle**, so the reaper never cuts a mid-turn agent.
- **Daemon heartbeat (per-tick)** — the daemon writes `daemon.heartbeat` each tick (timestamp +
  `last_tick_ok` + consecutive-failure count) so `kanban doctor` can detect a wedged or persistently
  failing daemon, not just a dead one.

## Kill-switch

`~/.kanban/PAUSE` (read fresh every tick) downgrades all permission profiles to the `docs` floor and
performs **zero agent launches**. The daemon still polls, reaps, blocks, and drains queues — it just
will not start new agents. Combined with an optional unattended-hours window, this keeps agents from
firing while you are away.

```bash
rm ~/.kanban/PAUSE                # resume normal operation
# (or: kanban resume)
```

## A gotcha: re-import after a column change

`board.json` keeps its own copy of the column set. After you **add or rename a column on the GitHub
board**, run:

```bash
kanban board import               # re-sync board.json's columns + placement from GitHub
```

Native placement can only reconcile a column it knows about. Without a re-import, a card dragged into
the new column maps to no native column key — the daemon logs the drift and skips the move, so the
launch never fires. Run `kanban board import` whenever the board's column structure changes.

---

For the full picture: [install.md](install.md) · [columns.md](columns.md) ·
[reference/deployment.md](reference/deployment.md) · [../ROADMAP.md](../ROADMAP.md).
