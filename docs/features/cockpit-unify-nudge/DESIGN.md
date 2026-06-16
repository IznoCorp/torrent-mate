# DESIGN — cockpit-unify-nudge (0.3.0 → 0.4.0)

Two contained engine features, one minor bump. Grounded against HEAD `f308a02`. Both built in an
isolated worktree + isolated venv; the live PM2 daemons (editable install from the MAIN worktree)
were never touched.

* **ITEM 2 — Cockpit move-unification.** Route the agent's `kanban-move` through the SAME intent
  queue the operator uses, so there is ONE audited board-write path with uniform daemon-derived
  authority.
* **ITEM 3 — Daemon sleep-interrupt nudge.** Wake the daemon's inter-tick sleep immediately when an
  intent is enqueued, without lowering the poll interval (no API-quota cost).

---

## ITEM 2 — Cockpit move-unification

### Before (two board-write paths)

1. **Operator move** — `cli/move.py:move()` enqueues an intent file `~/.kanban/intents/<id>.json`
   with `caller="operator"`; the daemon's `app/intents.py:drain_intents` (tick step 4c) is the SOLE
   executor (derives authority, validates, `move_card` + baseline-advance). The audited path.
2. **Agent move** — `bin/kanban_move.py:main()` resolved columns/transitions, checked the worktree
   pin, then called `GithubClient.move_card(...)` **directly** — a SECOND write path bypassing the
   queue — and wrote the advance breadcrumb synchronously.

The daemon side was already built for the agent path: `core/intent.py` has the full bridled-agent
guardrail set (`AGENT_ALLOWED_KINDS={"move"}`, R1 `launching_issue` binding, `_MERGE_COLUMN` deny,
wildcard-aware re-fire guard via `transitions.get(from, to).prompt`), and `app/intents.py:_process_intent`
already derived `authority = "agent" if intent.issue in running_issues else "operator"` (NEVER from the
spoofable `caller` field), passing `launching_issue=intent.issue` into `validate_intent`. Only the agent
helper still wrote the board directly.

### After (one write path)

`bin/kanban_move.py:main()` now ENQUEUES a `move` intent into the SAME `intents/` queue:

```python
store.enqueue_intent(intent_id, {
    "kind": "move", "issue": issue, "args": {"to_col": column.key},
    "requested_at": time.time(), "caller": "agent",   # ADVISORY only
})
store.nudge_daemon()                                  # ITEM 3 integration
```

The daemon's `drain_intents` drains it, derives **agent-authority from the running set** (the agent's
own in-flight ticket → `"agent"` automatically — no new authority code), re-validates the
authoritative guardrails, `move_card`s, and baseline-advances `next_columns[item_id]=to_col` (so the
move never re-fires a launch — anti-double-session preserved). The helper is now **network-free**
(`GithubClient` / `load_token` imports dropped — a layering simplification).

### Preserved guardrails (load-bearing)

* **Daemon-derived authority.** The enqueued `caller="agent"` is advisory ONLY. `_process_intent`
  derives authority from `intent.issue in running_issues`, NEVER from `caller`. A `caller="agent"`
  intent for a NON-running issue resolves to `"operator"` (broad) — the security-heart regression
  test asserts this.
* **R1 own-ticket, two layers.** (a) The helper still calls `check_pin(issue)` at enqueue time
  (refuses a worktree pinned to a different issue, BEFORE any write); (b) the daemon's
  `validate_intent(..., launching_issue=intent.issue)` re-enforces R1.
* **Non-triggering destination / re-fire guard.** The helper keeps a cheap pre-flight launch-target
  refusal (fast UX), but the daemon's wildcard-aware `validate_intent` re-fire check is
  AUTHORITATIVE (it also catches `(*, to)` wildcards the static `launch_target_columns()` set
  misses).
* **Merge deny.** `validate_intent` rejects an agent move into `Merge` (merge=human-only). The
  operator path is unaffected.
* **Anti-double-session.** The agent move never spawns a session; the daemon's drain `move_card` +
  baseline-advance means the next diff does NOT re-fire a launch, so no duplicate `ticket-<n>`
  session is ever created.

### Advance breadcrumb — promise-vs-land semantic shift (DESIGN delta)

The breadcrumb MUST stay written **synchronously by the agent helper** BEFORE `claude` exits — NOT by
the daemon drain. `bin/kanban_session_end.py` reads `recent_agent_advance(issue)` to choose the
✅ (advanced → daemon finalizes) vs ⚠️ (died-without-advancing) split, and it RACES the asynchronous
daemon poll. A daemon-written breadcrumb could land AFTER the agent's REPL already exited →
session-end would see "absent" and mis-finalize ⚠️.

So the helper writes the breadcrumb at enqueue time. **The breadcrumb meaning shifts** from
"the GitHub move LANDED" to "the agent REQUESTED its own advance" — which is exactly what the ✅/⚠️
split needs (it distinguishes "agent intended to advance & finished" from "agent died mid-stage").
The breadcrumb TTL (300 s) comfortably covers the drain latency (near-instant with the ITEM 3 nudge).

To avoid a refused move leaving a false ✅-signal, `kanban-move` defaults to `--wait`: it polls the
daemon's terminal result (15 s budget) and on a `rejected` outcome CLEARS the breadcrumb
(`clear_agent_advance(issue)`), prints the reason, and exits 1. A `--no-wait` escape hatch is exposed.

### Interaction with the operator-move drain

The agent intent is a normal `move` intent in the SAME queue. `drain_intents` already orders by
`requested_at` (an agent move and a concurrent operator move on the same issue → the earlier runs, the
later is DEFERRED), derives authority per-intent, and applies the PAUSE matrix (an agent move now
correctly HELDs under PAUSE — a small safety improvement over the old direct helper, which moved
regardless). No new ordering or locking is required.

---

## ITEM 3 — Daemon sleep-interrupt nudge

### Mechanism (chosen): file-mtime-polled interruptible sleep

The enqueue side and the daemon are **separate processes**, so a `threading.Event` cannot bridge them
(rejected). A self-pipe/FIFO + `select` is POSIX-only and adds FD lifecycle complexity (rejected). The
simplest correct cross-process mechanism for a single-host PM2 daemon is a **nudge sentinel file** the
enqueue side touches and the daemon's sleep polls in short slices:

* **Enqueue side** (`store.nudge_daemon()`): atomically bump the mtime of `<root>/intents/.nudge`
  (create-or-touch via the existing atomic temp-file + `os.replace`). Best-effort — swallows ALL
  errors → degrades to a normal full-interval sleep (fail-soft).
* **Daemon side** (`daemon/loop.py:_interruptible_sleep`): replaces the single `sleep(delay)`. It
  captures the sentinel mtime at sleep entry (`baseline`), then sleeps in fixed `0.5 s` slices,
  re-reading the mtime after each slice and returning EARLY the moment it advances past `baseline`.
  No nudge → it sleeps the full `delay` (slice-summed). NOT a busy-loop (each slice is a real
  `sleep`; ~20 cheap `stat()` calls per 10 s gap). Tick semantics untouched — still exactly one tick
  then a sleep; only the sleep DURATION can shrink.

Worst-case wake latency = one slice (0.5 s) vs the prior ~10 s, with zero interval reduction (no API
cost). The daemon reads the sentinel via a path-local closure (`_make_nudge_reader`, mirroring its
existing direct PAUSE/DEGRADED sentinel reads) so it needs no store construction; the store's
`nudge_mtime()` is the canonical reader for tests + agent/CLI symmetry.

### Consume-on-read (mtime monotonicity)

The baseline is re-read at the NEXT sleep entry (AFTER the tick that drained the nudged intent), so a
single nudge wakes exactly one sleep — a nudge during a tick is caught at the next baseline read (the
tick drained it already); a nudge during a sleep advances past the captured baseline → early wake. No
missed/repeated nudges, no explicit clear needed.

### Fail-soft + bonuses

* Every sentinel read is guarded — a `stat` that raises is treated as "no nudge" → full sleep.
* `_interruptible_sleep` also checks `flag.requested` between slices, so a SIGTERM during the
  inter-tick sleep exits within ≤0.5 s (was up to 10 s) — without changing the finish-tick-then-exit
  guarantee (the current tick already completed).
* The nudge interrupts the geometric failure back-off sleep too (an operator intent wakes a
  backed-off daemon within a slice — desirable). The back-off `delay` computation is unchanged; only
  the sleep is interruptible.

### Convention

**Every `enqueue_intent()` pairs with `nudge_daemon()`** — wired in `cli/move.py:move()` and
`bin/kanban_move.py:main()`; any future intent enqueuer (PR3 ticket/pill CRUD) should follow. Folding
the nudge INTO `enqueue_intent` was considered and REJECTED (it would couple every test's enqueue to a
filesystem touch and remove the fail-soft separation).

### The `.nudge` dotfile is invisible to the existing queue surface

`list_pending_intents` globs `*.json` (the dotfile `.nudge` is excluded) and the result GC globs
`*.result.json` only — so no glob change was needed.

---

## File-by-file summary

| File | Change |
|---|---|
| `bin/kanban_move.py` | Rewrite `main()` → enqueue intent + nudge + sync breadcrumb + `--wait`/`--no-wait`; network-free (drop `GithubClient`/`load_token`). |
| `core/intent.py` | Docstring-only: agent-move is LIVE (0.4.0), no longer "deferred". |
| `app/intents.py` | Docstring-only: `move` executes for both operator and agent now. |
| `cli/move.py` | +1 `store.nudge_daemon()` after enqueue (operator path otherwise unchanged). |
| `ports/store_intents.py` | +2 Protocol stubs: `nudge_daemon` / `nudge_mtime`. |
| `adapters/store/fs_intents.py` | Implement `nudge_daemon` (atomic touch) + `nudge_mtime` (fail-soft stat); `.nudge` sentinel. |
| `daemon/loop.py` | `_interruptible_sleep` + `_make_nudge_reader`; replace the tail `sleep(delay)`. |

All touched files stay well under the 1000-LOC hard ceiling (largest: `loop.py` at 689).
