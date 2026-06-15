# How it works

KanbanMate is a **polling-based Kanban orchestrator**. There is no webhook, no n8n, no
public endpoint — just a single daemon that polls the board and reconciles it against
persisted state.

## The polling loop (`tick`)

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

Each tick is **idempotent** — on restart the daemon rebuilds from persisted state + a fresh
snapshot, and the diff naturally recovers any moves made during downtime.

### Steps in detail

1. **cheap_probe** — fetch the 5 most recently updated project items. If unchanged from last
   poll, skip the full snapshot (saves GraphQL rate limit).
2. **snapshot** — cursor-paginated full board read. Only runs when the probe detected a change.
3. **diff** — compare the fresh snapshot against the persisted state from the last tick.
   Produces zero or more `Transition` objects (ticket + from_column + to_column).
4. **decide** — for each transition, determine what action (if any) to take based on the
   column classes of `from` and `to`.
5. **execute** — run the action (launch agent, teardown session, reset state, or block).
6. **reap** — detect agents whose heartbeat has gone stale and move them to Blocked.
7. **drain queue** — process any deferred actions.
8. **heartbeat** — write the daemon's own liveness heartbeat so `kanban doctor` can detect a
   wedged daemon.

## Column classes

Every column on the board falls into one of three classes, resolved from the per-repo
`columns.yml`:

| Class        | Config                 | Behaviour                                                          |
| ------------ | ---------------------- | ------------------------------------------------------------------ |
| **Agent**    | `triggers_agent: true` | Moving a card here fires a Claude Code agent (`LaunchAction`)      |
| **Reactive** | `action: teardown`     | Moving a card here runs a side-effect (e.g. Cancel → kill session) |
| **Inert**    | neither flag           | Human gate or terminal column; no automatic action                 |

`kanban-move` (the agent helper) refuses agent-column targets — this is the anti-loop guard
(DESIGN §8).

## Action model

The daemon decides on one of four action kinds per transition:

| Action           | Kind     | When                                                                    |
| ---------------- | -------- | ----------------------------------------------------------------------- |
| `LaunchAction`   | LAUNCH   | Ticket enters an agent column → spawn tmux + worktree + claude session  |
| `TeardownAction` | TEARDOWN | Ticket lands in Cancel → kill tmux session, remove worktree, post recap |
| `ResetAction`    | RESET    | Ticket moves Cancel → Backlog → purge state so it can restart fresh     |
| `BlockAction`    | BLOCK    | Dependency gate not satisfied, rate limit hit, or kill-switch active    |

Agents can push commits and open PRs, but **never merge** — `gh pr merge`, `git push --force`,
and history rewrite are banned across all permission profiles (DESIGN §10).

## Agent liveness — heartbeat (#67)

Two distinct heartbeats coexist (do not conflate them):

### Agent heartbeat (per-tool)

`LaunchAction` bakes a **PostToolUse hook** (matcher `"*"`) into the worktree's
`.claude/settings.json`. The hook runs `kanban-heartbeat <issue>` after every tool the agent
uses, which calls `Store.touch_heartbeat(issue, now)`. Contracts:

- **Always exits 0** — exit 2 would block the agent; never emitted.
- **Import-light** — parses `argv[1]` to `int` before importing `kanbanmate`. Bad/missing arg
  → exit 0 silently.
- **No resurrection** — `touch_heartbeat` is a no-op when state for that issue is absent
  (so a late hook after Cancel teardown never recreates torn-down state).

### Reaper (daemon-side)

Every `tick`, the daemon's reap step checks every `running` ticket: if its agent heartbeat is
older than `HEARTBEAT_TTL` (default 1800 s), the daemon posts a sticky comment, moves the card
to Blocked, kills the dead tmux session, and releases the slot.

### Daemon heartbeat (per-tick)

The daemon writes its own heartbeat each tick. `kanban doctor` checks it to detect a wedged
daemon (one that is alive but not processing ticks — e.g. hung on a network call despite
timeouts).

## Kill-switch

`~/.kanban/PAUSE` — if this file exists, all permission profiles are downgraded to `safe` and
**zero agent launches** occur. The daemon still polls and can still reap/block/drain, but it
will not start new agents. Combined with the **unattended-hours** window (configurable in
`~/.kanban/config.yml`), this ensures agents don't fire while you're asleep or away.

Delete the file to resume normal operation:

```bash
rm ~/.kanban/PAUSE
```

## Resumability

Agent sessions run in named tmux windows (`ticket-<n>`). You can attach, watch, or interact:

```bash
tmux attach -t ticket-42
claude --resume <uuid>              # resume a specific session
kanban sessions                     # list live sessions + flag DEAD ones
kanban cancel 42                    # manually tear down a ticket's agent
```

## Adaptive poll interval

When the board is idle (no transitions for several ticks), the daemon backs off to a longer
poll interval to conserve GraphQL rate limit. The first change on the board (detected by
`cheap_probe`) resets the interval to the configured minimum.

## No webhook, no n8n

Polling is the only ingress model in v1. The `diff`-against-persisted-state approach
naturally handles every webhook use case (new card, column move, field change) without a
public endpoint, HMAC verification, or an external automation platform. Webhook ingress is
a deferred optional adapter — see [ROADMAP.md](../ROADMAP.md).
