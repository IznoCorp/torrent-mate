# Phase 13 — Concurrency cap + queue + move rate-limit + fix-CI retry (PoC parity port)

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §3.1 (the tick post-steps list "drain queue"), §6 (the §6 runaway-loop
> backstops — durable per-item rate-limit + bounded fix-CI loop), §7 (atomic concurrency cap),
> §11 (port-from-PoC; the PoC is the source of truth).
> PoC source of truth (ABSOLUTE OLD root —
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`):
> `<OLD>/engine/cap.py` (`reserve_slot`/`release_slot`/`active_count` — the flock("cap") + slots/
> machinery, already ported faithfully into `fs_store.reserve_slot`/`release_slot`) ·
> `<OLD>/state.py`
> `record_move_for_item`/`move_count_for_item_last_hour` (L305-317, durable `moves/item_<item>.json`
> history over `_RATE_WINDOW = 3600.0`, L38) ·
> `bump_retry`/`reset_retry`/`_retry_path` (L205-225, `retries/<safe-item>__<key> = {"n": n}`) ·
> `queue_dir` (L389-393, `<root>/queue`) ·
> `purge_ticket` (L427-479, the exhaustive idempotent purge of `queue/ticket-<issue>`,
> `moves/<issue>.json`, `moves/item_<item>.json`, `retries/<safe-item>__*`) ·
> `<OLD>/runner.py` the launch-path cap gate + queue divert (L706-733) and the per-item
> move-rate-limit park (L504-518), plus `_park_blocked` (L212-227) and `_auto_move`'s
> single `record_move_for_item` call-site (L230-250) ·
> `<OLD>/engine/reaper.py` the `dequeue` sweep + drain (L44-63 sweep, L185-233 apply). NEW root:
> `/Users/izno/dev/KanbanMate/src/kanbanmate/`.

**Goal**: restore the four workload-management / runaway-loop capabilities the parity audit confirms
were dropped or left inert in NEW — all orthogonal to the n8n→polling pivot, all DESIGN-promised:

| Capability                  | Audit verdict                                                                            | PoC source                          |
| --------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------- |
| Concurrency CAP at launch   | [HIGH] `reserve_slot` ported into `fs_store` but **NEVER CALLED** — unbounded launches   | `runner.py:706-733`; `cap.py:26-40` |
| QUEUE on cap-full + drain   | [HIGH] `_drain_queue` is an explicit Phase-1 stub; nothing writes a queue marker         | `runner.py:706-732`; `reaper.py`    |
| Per-item move RATE-LIMIT    | [HIGH] survives only as a VOLATILE in-memory counter (`antiloop`), lost on every restart | `state.py:305-317`; `runner.py:511` |
| Per-(item,key) fix-CI RETRY | [MEDIUM] `bump_retry`/`reset_retry` + `retries/` dir entirely ABSENT                     | `state.py:205-225`                  |

**Design boundaries (operator decisions baked into this plan).**

1. **The slot/queue/moves/retries primitives are I/O — they live in `fs_store` (the adapter) +
   the `StateStore` port, NEVER in `core/`.** `core/` imports nothing with I/O (the layering guard).
   The cap/rate-limit _policy gate_ runs in `app/tick.py` (the imperative shell) where the live
   `store` port + the `TickConfig` knobs are in scope.
2. **Issue-keying throughout.** OLD keyed `moves/item_<item>.json` and `retries/<safe-item>__<key>`
   by the **content node id**; NEW keys every per-ticket marker by the **issue number** (the same
   deliberate divergence 8.1.d made for the advance breadcrumb). The slot marker is already
   `slots/ticket-<issue>` and the queue marker is `queue/ticket-<issue>` — issue-keyed. So this is
   NOT a verbatim port: the rate-limit history becomes `moves/<issue>.json` and the retry counter
   becomes `retries/<issue>__<key>`, issue-keyed. State the keying invariant in each docstring.
3. **Durability restored.** The §6 rate-limit history is restored to ON-DISK persistence
   (`moves/<issue>.json`) so the per-hour cap holds across a daemon restart/crash — NOT the volatile
   `PersistedState.antiloop` counter. The in-memory `antiloop` guard STAYS as defense-in-depth (it
   is a different, target-keyed dedup net, DESIGN §6); this phase adds the durable backstop ALONGSIDE
   it, it does not replace it.
4. **What feeds the rate-limit counter.** Port OLD's exact semantics: the per-item move counter is
   fed **ONLY by AUTO/bot moves the daemon itself issues** (the reaper's move-to-Blocked is the only
   such move in NEW today), NEVER by human launches or the agent's own forward `kanban-move`. The
   limit guards the bot loop, not the human workflow (`runner.py:504-510`, `_auto_move` L248).
5. **The transitions defaults block.** OLD's `concurrency_cap` + `move_rate_limit_per_hour` lived on
   the per-transition `TransitionConfig` (`transitions.py:57,97`, YAML-overridable). NEW has no
   `transitions.yml` whitelist (a deliberate pivot to the per-column-class model). So the two knobs
   are surfaced as a SMALL board-level `defaults:` block parsed from the SAME `columns.yml` document
   the column model already loads (no second config file), threaded onto `TickConfig`. Defaults
   mirror OLD: `concurrency_cap` (no OLD literal default — REQUIRED on the transition; NEW picks a
   conservative `3`), `move_rate_limit_per_hour: 10` (`transitions.py:97`).

---

## Gate

Phases 1–12 complete; PR open + CI green; branch `feat/genesis`; `make check` green at start. The
advance breadcrumb (8.1.d), the widened `TicketState`, `reserve_slot`/`release_slot`, and the
in-memory `antiloop` guard are all present and read for this port. **Clear `.mypy_cache` before the
authoritative gate check** (its incremental cache has masked real errors in this repo).

---

## 13.1 — fs-store: durable per-issue move rate-limit history (`record_move`/`move_count`)

> **The gap.** [HIGH] The §6 per-item move rate-limit survives in NEW only as a PURE in-memory
> counter (`core/antiloop.py` `move_times`, `rate_window=3600.0`), threaded through
> `PersistedState.antiloop`, which `daemon/loop.py` initialises EMPTY at every startup and NEVER
> writes to disk. So the per-hour cap does NOT survive a daemon restart/crash, whereas OLD persisted
> `moves/item_<item>.json` on disk. This sub-phase restores the durable on-disk history (issue-keyed),
> a faithful port of `state.py:305-317`.

**Layer**: `ports/` (extend the `StateStore` Protocol — pure) · `adapters/store/` (fs history,
mirrors the PoC `record_move_for_item`/`move_count_for_item_last_hour`).

**Files**: `src/kanbanmate/ports/store.py` (extend the Protocol),
`src/kanbanmate/adapters/store/fs_store.py` (add the two methods + the `moves/` dir + `_moves_path`),
`tests/adapters/test_fs_store.py` (extend — the test lives at `tests/adapters/test_fs_store.py`, NOT
`tests/adapters/store/test_fs_store.py`).

- [ ] Add `_RATE_WINDOW = 3600.0` module constant to `fs_store.py` (port of `state.py:38`,
      the rate-limit sliding-window width in seconds). Document it is DISTINCT from `_ADVANCE_TTL`
      (300 s breadcrumb recency) and `HEARTBEAT_TTL` (1800 s reap window) — three separate knobs.
- [ ] In `FsStateStore.__init__` create `(self.root / "moves").mkdir(parents=True, exist_ok=True)`
      alongside the existing `state/`, `slots/`, `advances/` dirs.
- [ ] Add `_moves_path(self, issue_number: int) -> Path` → `<root>/moves/<issue>.json`. **Issue-keyed**
      (boundary 2): OLD used `moves/item_<item>.json` keyed by content node id; NEW keys by issue
      number, like the slot/queue/advance markers. Document the divergence.
- [ ] `record_move_for_item(self, issue_number: int, *, now: float) -> None` — append `now` to the
      `<root>/moves/<issue>.json` JSON list (read-or-`[]`, append, write). Port of `state.py:306-310`.
      English docstring: this is fed ONLY by an AUTO/bot move the daemon itself issues (the reaper's
      move-to-Blocked) — NEVER a human launch or the agent's own `kanban-move` (the §6 limit guards
      the bot loop, not the human workflow). Keep the method name `record_move_for_item` for a
      faithful port even though it is now issue-keyed.
- [ ] `move_count_for_item_last_hour(self, issue_number: int, *, now: float) -> int` — return
      `sum(1 for t in hist if (now - t) <= _RATE_WINDOW)`, `0` when the file is absent. Port of
      `state.py:312-317`. Tolerate a corrupt/unreadable file by returning `0` (degrade like `load`'s
      poison-file path) so a bad `moves/` file cannot wedge the launch gate.
- [ ] Add both methods to the `StateStore` Protocol (`ports/store.py`) with the issue-keying
      invariant + the "fed only by bot moves" note in the docstrings. Keep the Protocol I/O-free
      (signatures only).
- [ ] Tests (`tests/adapters/test_fs_store.py`): `record_move_for_item` then
      `move_count_for_item_last_hour` counts entries within the window and DROPS entries older than
      `_RATE_WINDOW` (set `now` past the window); count is `0` for an issue with no history; a corrupt
      `moves/<issue>.json` → `move_count_for_item_last_hour` returns `0` (no raise); the history is
      keyed by issue number (`moves/<issue>.json` exists, NOT `moves/item_<node>.json`); the history
      survives a fresh `FsStateStore(root)` instance over the same root (durability — the whole point).
- [ ] Verify: `make check` green; layering guard sees the new methods stay within
      `ports/` + `adapters/store/` (no upward import).

```bash
git commit -m "feat(genesis): durable per-issue move rate-limit history in fs-store (port record_move_for_item)"
```

---

## 13.2 — fs-store: per-(issue,key) fix-CI retry counter (`bump_retry`/`reset_retry`)

> **The gap.** [MEDIUM] OLD's `state.py:205-225` persisted a per-(item,key) retry ledger
> (`retries/<safe-item>__<key> = {"n": count}`, `bump_retry` increments starting at 1, `reset_retry`
> zeroes) backing the bounded fix-CI loop cap (§6, N=2 → park in Blocked). NEW has NO `bump_retry`/
> `reset_retry` and NO `retries/` dir (the constructor creates only `state/`, `slots/`, `advances/`).
> This sub-phase ports the ledger (issue-keyed). The fix-CI _loop policy_ that consumes it (on_fail →
> auto-retry → park-in-Blocked after N) belongs to the dropped script-transition feature (a separate,
> larger gap not in this phase's scope); this sub-phase restores the persistence primitive + a focused
> consumer seam so the counter is real and tested, ready for a future on_fail port.

**Layer**: `ports/` (extend the `StateStore` Protocol) · `adapters/store/` (the `retries/` ledger).

**Files**: `src/kanbanmate/ports/store.py` (extend the Protocol),
`src/kanbanmate/adapters/store/fs_store.py` (add `_retry_path` + the two methods + the `retries/`
dir), `tests/adapters/test_fs_store.py` (extend).

- [ ] In `FsStateStore.__init__` create `(self.root / "retries").mkdir(parents=True, exist_ok=True)`.
- [ ] Add `_retry_path(self, issue_number: int, key: str) -> Path` →
      `<root>/retries/<issue>__<safe-key>`. **Issue-keyed** (boundary 2): OLD keyed by the safe
      content node id; NEW keys by issue number. Sanitise `key` with the same alnum/`._-` filter
      the `_lock` helper uses (replace any other char) so a column name with a space/slash (e.g.
      `"PR Ready"`) cannot escape the `retries/` dir. Default an empty key to `"_"` (OLD did the
      same via `_INFLIGHT_SAFE`).
- [ ] `bump_retry(self, issue_number: int, key: str) -> int` — read `{"n": n}` (or `0` when absent),
      increment, write back, return the new count (starts at 1). Port of `state.py:212-221`. English
      docstring: backs the bounded fix-CI loop (§6, N=2) — the consumer bumps on each auto-retry and
      parks the ticket in Blocked once the count exceeds the cap.
- [ ] `reset_retry(self, issue_number: int, key: str) -> None` — write `{"n": 0}` (the loop succeeded
      / left the cycle). Port of `state.py:223-225`.
- [ ] Add both methods to the `StateStore` Protocol with the issue-keying + sanitisation invariant
      in the docstrings.
- [ ] Tests (`tests/adapters/test_fs_store.py`): `bump_retry` returns 1 then 2 then 3 across calls;
      `reset_retry` zeroes it (next `bump_retry` returns 1); two DISTINCT `key`s on the same issue keep
      independent counters (per-loop budget keyed by destination — port of OLD's `onfail:<to>`
      semantics); a `key` containing a space/slash is sanitised to a single `retries/` file (assert the
      marker path stays under `retries/`, no dir escape); the counter survives a fresh
      `FsStateStore(root)` over the same root.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): per-(issue,key) fix-CI retry counter in fs-store (port bump_retry/reset_retry)"
```

---

## 13.3 — fs-store: queue persistence + `release_slot`/purge widening

> **The gap.** [HIGH] [LOW] OLD's `queue_dir()` (`state.py:389-393`) backs a real concurrency-cap
> queue: on a triggering move at cap, `runner.py:706-732` writes `queue/ticket-<n>` carrying every
> relaunch input; the reaper later drains it (`reaper.py:185-233`). NEW has NO queue dir, NO accessor,
> and `_drain_queue` is an explicit Phase-1 stub. Additionally, OLD's `purge_ticket` (`state.py:462-466`)
> exhaustively removed `queue/ticket-<issue>`, `moves/<issue>.json`, `moves/item_<item>.json`, and
> `retries/<safe-item>__*` on teardown; NEW's `release_slot` only unlinks `state/`, `slots/`, and
> `advances/` — so a cancelled ticket leaves stale rate-limit history, retry counters, and a queue
> marker behind. This sub-phase ports the queue persistence primitives + extends the purge.

**Layer**: `ports/` (extend the `StateStore` Protocol) · `adapters/store/` (queue dir + markers +
the widened purge).

**Files**: `src/kanbanmate/ports/store.py` (extend the Protocol),
`src/kanbanmate/adapters/store/fs_store.py` (add `_queue_path` + queue accessors + extend
`release_slot`), `tests/adapters/test_fs_store.py` (extend).

- [ ] In `FsStateStore.__init__` create `(self.root / "queue").mkdir(parents=True, exist_ok=True)`.
- [ ] Add `_queue_path(self, issue_number: int) -> Path` → `<root>/queue/ticket-<issue>`. Issue-keyed
      (matches OLD's `queue/ticket-<issue>`, which was already issue-keyed even in OLD).
- [ ] `enqueue_launch(self, issue_number: int, payload: Mapping[str, object]) -> None` — write the
      relaunch `payload` as JSON to `<root>/queue/ticket-<issue>`. Port of OLD's queue-marker write
      (`runner.py:711-728`), but NEW's relaunch payload is minimal: NEW's `LaunchAction` re-derives
      its worktree/profile/agent_command from `Deps` + the snapshot, so the marker only needs enough
      to RE-IDENTIFY the ticket (`item_id`, `column_key`/stage) for the drain — store `{"item_id":…,
"stage":…, "enqueued_at": now}`. Document that NEW's payload is intentionally thinner than OLD's
      (OLD persisted the FULLY-FILLED prompt + GH coords because its launcher re-read the marker; NEW's
      `LaunchAction` is self-contained).
- [ ] `dequeue_pending(self) -> tuple[int, ...]` — return the issue numbers of every queued ticket,
      sorted (mirror OLD's `sorted(store.queue_dir().glob("ticket-*"))`, `reaper.py:58`). Skip a
      marker whose name does not parse to an int (port OLD's `try/except (IndexError, ValueError)`).
- [ ] `load_queued(self, issue_number: int) -> dict | None` — read+parse the marker payload, or `None`
      when absent/corrupt (so the drain can re-identify the ticket; degrades like `load`).
- [ ] `clear_queued(self, issue_number: int) -> None` — unlink `<root>/queue/ticket-<issue>`, no-op
      when absent (unlink-if-exists / no-raise, like the other purges). Called by the drain AFTER a
      confirmed launch.
- [ ] **Widen `release_slot`** to the exhaustive purge (port `purge_ticket`'s issue-keyed targets):
      in addition to `state/<issue>.json`, `slots/ticket-<issue>`, and `advances/<issue>` (already
      unlinked), ALSO unlink `queue/ticket-<issue>`, `moves/<issue>.json`, and EVERY
      `retries/<issue>__*` (glob the issue prefix; `glob.escape` the interpolated issue so a metachar
      can never widen the pattern — port OLD's over-match defence note at `state.py:467-469`). Each
      removal independently guarded (no-raise on absent) so a teardown→reset double-purge never raises
      (idempotent — OLD's `purge_ticket` contract). Update the `release_slot` docstring to enumerate
      EVERY purged marker.
- [ ] Add the four queue methods to the `StateStore` Protocol (signatures + docstrings); document the
      thinner-payload divergence and the issue-keying. Keep the Protocol I/O-free.
- [ ] Tests (`tests/adapters/test_fs_store.py`): `enqueue_launch` then `dequeue_pending` returns the
      issue; `load_queued` round-trips the payload; `clear_queued` removes it (no-op when absent);
      `dequeue_pending` returns issues SORTED and SKIPS a non-`ticket-<int>` file; **`release_slot`
      now ALSO purges** `queue/ticket-<n>`, `moves/<n>.json`, and `retries/<n>__*` (seed all three,
      call `release_slot`, assert all gone) AND is idempotent (a second `release_slot` raises nothing);
      a `retries/<n>__*` glob with a metachar in a sibling issue is NOT collaterally deleted
      (over-match defence).
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): fs-store queue persistence + exhaustive release_slot purge (port queue_dir/purge_ticket)"
```

---

## 13.4 — `transitions.yml` defaults block: `concurrency_cap` + `move_rate_limit_per_hour`

> **The gap.** OLD carried `concurrency_cap` + `move_rate_limit_per_hour` on the per-transition
> `TransitionConfig` (`transitions.py:57,97`, YAML-overridable; e2e tests set `6`). NEW dropped the
> `transitions.yml` whitelist for the per-column-class model, so the two knobs have NO home. They are
> the inputs the cap gate (13.5) and the rate-limit gate (13.6) consume, so they must be configurable.
> Surface them as a small board-level `defaults:` block parsed from the SAME `columns.yml` document
> the column model already loads — no second config file, no `transitions.yml` resurrection.

**Layer**: `core/` (pure YAML→value-object parse) · `app/` (thread the defaults onto `TickConfig`).

**Files**: `src/kanbanmate/core/columns.py` (add a `load_board_defaults(yaml_text) -> BoardDefaults`
parser + a `@dataclass(frozen=True) BoardDefaults`), `src/kanbanmate/app/tick.py` (`TickConfig` gains
`concurrency_cap` + `move_rate_limit_per_hour`), `src/kanbanmate/app/wiring.py`
(`build_tick_config` parses the defaults block onto `TickConfig`),
`src/kanbanmate/assets/columns.yml.tmpl` (add the documented `defaults:` block),
`tests/core/test_columns.py` (extend), `tests/app/test_wiring.py` (extend).

- [ ] `core/columns.py`: add `@dataclass(frozen=True) BoardDefaults` with English-docstringed fields:
  - `concurrency_cap: int = 3` — max concurrent agent sessions before a launch diverts to the queue
    (DESIGN §7; OLD had no literal default — the transition REQUIRED it; NEW picks a conservative 3).
  - `move_rate_limit_per_hour: int = 10` — max AUTO/bot moves per ticket within the hour before it is
    parked in Blocked (port of `transitions.py:97` default 10).
- [ ] Add `load_board_defaults(yaml_text: str) -> BoardDefaults` — parse a top-level optional
      `defaults:` mapping from the SAME `columns.yml` document; read `concurrency_cap` /
      `move_rate_limit_per_hour` with the dataclass defaults as fallbacks. Coerce to `int` and FAIL
      LOUD (`ValueError`) on a non-int / non-positive value (port OLD's validation spirit — a runaway
      backstop must not silently accept `0` or a YAML `no`/`yes` footgun). An ABSENT `defaults:` block
      → all defaults (so existing `columns.yml` files without the block still load). Keep it pure
      (string in, value object out; no I/O).
- [ ] `app/tick.py` `TickConfig`: add `concurrency_cap: int = 3` and `move_rate_limit_per_hour: int = 10`
      fields (defaults matching `BoardDefaults`), with English docstrings tying each to its gate
      (13.5 cap / 13.6 rate-limit). Keep `TickConfig` frozen.
- [ ] `app/wiring.py` `build_tick_config`: call `load_board_defaults(config.columns_yaml)` and pass
      `concurrency_cap=…` + `move_rate_limit_per_hour=…` into the constructed `TickConfig` (alongside
      the existing `columns=` + `kill_switch=`).
- [ ] `assets/columns.yml.tmpl`: add a documented top-level `defaults:` block at the head (above
      `columns:`), e.g.:
      `yaml
defaults:
  concurrency_cap: 3            # max concurrent agent sessions; over-cap launches queue (§7)
  move_rate_limit_per_hour: 10  # max AUTO/bot moves per ticket per hour; over-limit parks Blocked (§6)
`
      Document that these are board-wide knobs (OLD carried them per-transition; NEW's per-column-class
      model surfaces them once at board level).
- [ ] Tests: `load_board_defaults` reads an explicit `defaults:` block; an ABSENT block yields the
      dataclass defaults (3 / 10); a non-int or `<= 0` value raises `ValueError`; `build_tick_config`
      threads the parsed defaults onto `TickConfig` (assert both fields land); the shipped
      `columns.yml.tmpl` parses to the documented values (round-trip the template through
      `load_board_defaults`).
- [ ] Verify: `make check` green; the new `BoardDefaults`/`load_board_defaults` import nothing with
      I/O (layering guard — `core/columns.py` stays pure).

```bash
git commit -m "feat(genesis): board-level concurrency_cap + move_rate_limit_per_hour defaults (transitions knobs)"
```

---

## 13.5 — `app/tick.py`: enforce the concurrency cap BEFORE launch + drain the queue when a slot frees

> **The gap.** [HIGH] `fs_store.reserve_slot(issue, cap)` is ported faithfully but `rg 'reserve_slot'
src/kanbanmate/app src/kanbanmate/daemon` → ZERO hits in the launch path: `LaunchAction.execute`
> never reserves, `tick.py` never consults the cap, so the daemon launches one agent per agent-bound
> transition every snapshot with NO upper bound. And [HIGH] `_drain_queue` is an explicit empty stub.
> This sub-phase ports OLD's launch-path cap gate (`runner.py:706-733`) + the reaper's `dequeue` drain
> (`reaper.py:185-233`) onto NEW's tick: reserve a slot BEFORE dispatching `LaunchAction`; on cap-full
> divert to the queue (no launch); after the reap step, drain the queue WHILE slots are free.

**Layer**: `app/` (the imperative shell — needs the live `store` port + the `TickConfig` cap +
the snapshot). **Files**: `src/kanbanmate/app/tick.py` (the LAUNCH branch reserves; `_drain_queue`
becomes real), `tests/app/test_tick.py` (extend).

> **Operator decision 2026-06-06 — RICH queue payload (parity over thinness).** The original plan
> stored a THIN marker (`{item_id, stage, enqueued_at}`) and rebuilt a BARE `LaunchAction(ticket=…)`
> at drain. Verified against the code, a bare `LaunchAction` has `prompt is None` → it falls back to
> the generic `Deps.agent_command` (`actions.py:245`), so a queue-diverted ticket would LOSE the
> filled per-transition `/implement:*` prompt the phase-12 whitelist just restored. The PoC persisted
> the FULL filled prompt in its queue marker (`runner.py:711-728`) precisely to preserve it on drain;
> dropping it leaves a PoC capability behind, which the restoration directive forbids. So the marker
> now carries the FULL launch routing + ticket identity, and the drain rebuilds a `LaunchAction`
> BYTE-IDENTICAL to a direct launch (filled prompt preserved). `enqueue_launch(payload: Mapping)`
> (13.3, already shipped) accepts any mapping, so this needs NO 13.3 code change — only this richer
> payload at the enqueue call-site + the faithful rebuild at drain.

- [ ] **Cap gate on the LAUNCH branch.** In the decided-action loop, when
      `action.kind is ActionKind.LAUNCH` (after the `_build_action` dependency gate already
      produced a `LaunchAction`, NOT a `BlockAction` — guard with `isinstance(command, LaunchAction)`),
      BEFORE running the command:
  - `if not deps.store.reserve_slot(issue, config.concurrency_cap):` → the cap is full. Do NOT
    dispatch `LaunchAction`. Instead enqueue the FULL launch routing so the drain rebuilds a faithful
    launch (operator decision above) — read the fields off the already-built `command` (the
    `LaunchAction`):
    `deps.store.enqueue_launch(issue, {"item_id": ticket.item_id, "stage": transition.to_column,
"title": ticket.title, "body": ticket.body, "prompt": command.prompt, "script": command.script,
"profile": command.profile, "permission_mode": command.permission_mode, "on_fail": command.on_fail,
"advance": command.advance, "enqueued_at": now})` (13.3). Then advance the diff baseline
    (`next_columns[item_id] = to_column` — the card IS in the agent column on the board, so the next
    diff must not re-fire it), and `continue`.
    Mirror OLD's "cap full → QUEUE, record column, return Decision('queue')" (`runner.py:706-732`).
    `reserve_slot` is idempotent per ticket, so a re-queued ticket already holding a slot reserves
    nothing extra.
  - on a successful reserve, dispatch `LaunchAction` as today. **Leak-safety (port OLD's
    `try/except BaseException: release_slot; raise`, `runner.py:756-770`):** if the `LaunchAction`
    watchdog returns `False` (the launch timed out or raised — `_run_with_watchdog` already swallows
    - logs), the reserved slot would otherwise LEAK forever (no running-state, no queue marker, so the
      reaper never reclaims it). After a failed `LaunchAction` (`ok is False` on a LAUNCH transition),
      call `deps.store.release_slot(issue)` to release the just-reserved slot. Document this mirrors
      OLD's release-on-launch-failure (the success path must NOT release — the slot backs the now-running
      session and is released by `kanban session-end`). NB `release_slot` also purges state/breadcrumb,
      but on a failed launch there is no state to purge yet (the save is `LaunchAction` step 4), so the
      purge is a harmless no-op — the slot release is the load-bearing part.
  - The `✅ left-stage finalize` (8.1.e) on the LAUNCH branch still runs from the PRE-READ `left_state`;
    keep that ordering (pre-read → reserve → dispatch → finalize). On the queue-divert path the agent
    never launched, so do NOT finalize the left stage (nothing advanced) — just enqueue + advance the
    baseline + continue.
- [ ] **`_drain_queue` becomes real** (port `reaper.py:185-233`). Replace the stub with: for each
      `issue in deps.store.dequeue_pending()`:
  - `if not deps.store.reserve_slot(issue, config.concurrency_cap): continue` — only drain when a slot
    is ACTUALLY free; never exceed the cap. Leave the marker for the next sweep (OLD's
    `reaper.py:193-195`).
  - load the queued payload (`deps.store.load_queued(issue)`); if `None`/missing `item_id` → release
    the just-reserved slot + clear the marker (it is unlaunchable — port OLD's empty/invalid-inputs
    diagnostic at `reaper.py:221-233`, logging ONE warning via the module logger so a wedged ticket is
    visible, NOT a silent drop) and continue.
  - rebuild a FAITHFUL launch from the RICH payload (operator decision — parity over thinness):
    `Ticket(item_id=str(payload["item_id"]), issue_number=issue, title=str(payload.get("title") or
f"ticket-{issue}"), column_key=str(payload.get("stage") or ""), body=str(payload.get("body") or ""))`,
    then `LaunchAction(ticket=…, prompt=payload.get("prompt"), script=payload.get("script"),
profile=str(payload.get("profile") or ""), permission_mode=str(payload.get("permission_mode") or
"auto"), on_fail=str(payload.get("on_fail") or ""), advance=str(payload.get("advance") or "stop"))`,
    and dispatch it under the watchdog. The rebuilt `LaunchAction` is byte-identical to the one the
    cap-gate would have dispatched directly, so the drained agent runs the SAME filled `/implement:*`
    prompt (the whole point of the rich payload). **mypy note:** `load_queued` returns
    `dict[str, object] | None`, so each `payload[...]` is typed `object`; coerce explicitly
    (`str(...)`, and for the `str | None` prompt/script use a small `cast`/`isinstance` narrowing) to
    satisfy mypy strict — mirror `load_queued`'s own `cast` pattern.
  - **Launch WHILE the marker still exists** (OLD's race-closing rule): only `clear_queued(issue)`
    AFTER a confirmed successful launch (`ok is True`). On a failed launch, `release_slot(issue)` (so
    the slot does not leak) and KEEP the marker for a later sweep (no leak, no drop — OLD
    `reaper.py:209-220`). Wrap the dispatch so an exception releases the slot before propagating
    isolation (the watchdog already isolates exceptions, so in practice `ok is False` covers it).
  - `_drain_queue` needs `config` (the cap) + `executor` (the watchdog) + `now`: change its signature
    to `_drain_queue(deps, config, executor, now)` and update the call-site in `tick`. Keep the call
    AFTER `_reap_stale_agents` (a reap frees slots first, so the drain sees them — DESIGN §3.1 tick
    post-step order: reap → drain).
- [ ] Tests (`tests/app/test_tick.py`): with `concurrency_cap=1` and one slot already reserved, a
      LAUNCH transition does NOT dispatch `LaunchAction` (assert the sessions adapter `launch` is NOT
      called) and instead enqueues the ticket (`dequeue_pending()` returns it) + advances the baseline
      (the move is not re-fired next tick); under the cap, a LAUNCH reserves a slot then dispatches; a
      LAUNCH whose `LaunchAction` raises/timeouts RELEASES the reserved slot (no leak — assert
      `reserve_slot` can succeed again afterward); `_drain_queue` launches a queued ticket WHEN a slot
      is free, clears its marker on success, and leaves the marker + releases the slot when the launch
      fails; `_drain_queue` does NOT exceed the cap (with no free slot it drains nothing, marker kept);
      a queued marker with no `item_id` is cleared + logged, never launched. **Rich-payload parity
      (operator decision):** the cap-gate enqueues the FULL routing (assert the persisted payload
      carries `prompt`/`profile`/`permission_mode`/`title`/`body`, not just `item_id`/`stage`), and a
      drained launch rebuilds a `LaunchAction` carrying the SAME filled `prompt` (assert the drained
      `LaunchAction.prompt` equals the originally-queued transition prompt, NOT `None` — i.e. the
      drained agent does not regress to the bare `agent_command`). Use a fake store recording
      `reserve_slot`/`release_slot`/`enqueue_launch`/`dequeue_pending`/`load_queued`/`clear_queued`
      calls (extend the existing tick fakes; mind the Drift note below).
- [ ] Verify: `make check` green. Residual grep — the cap is now enforced:
      `rg --type py "Intentionally empty: no queue backlog" src` → ZERO matches (the stub text is gone).

> **Drift note (13.5 execution).** Making `reserve_slot`/`enqueue_launch`/`dequeue_pending`/
> `load_queued`/`clear_queued`/`record_move_for_item`/`move_count_for_item_last_hour`/`bump_retry`/
> `reset_retry` part of the `StateStore` Protocol (13.1–13.3) fans out to EVERY test fake that
> implements `StateStore`: `tests/app/test_tick.py`, `tests/app/test_actions.py`,
> `tests/cli/test_status.py` (`_FakeStore`), `tests/integration/test_poll_real_board.py`,
> `tests/local_real/test_tick_local.py`. Each fake gains the new methods (a recording stub or a
> tiny in-memory dict suffices). Clear `.mypy_cache` and run `mypy src tests` to surface EVERY
> unimplemented-Protocol-method error before the gate — the incremental cache has masked these before.

```bash
git commit -m "feat(genesis): enforce concurrency cap before launch + real queue drain (port reserve_slot gate + dequeue)"
```

---

## 13.6 — `app/tick.py`: durable per-item move rate-limit gate (park AUTO/bot over-moves in Blocked)

> **The gap.** [HIGH] OLD's `runner.py:504-518` parked a card in the Blocked COLUMN (a visible board
> move + comment) when an item had made `>= move_rate_limit_per_hour` AUTO/bot moves within the hour,
> fed ONLY by `_auto_move`'s single `record_move_for_item` call (`runner.py:248`). NEW's in-memory
> `antiloop` guard yields a `BlockAction` COMMENT, not a board park, counts a different set of moves,
> and is lost on restart. This sub-phase ports the DURABLE rate-limit gate: record each AUTO/bot move
> the daemon issues into the on-disk history (13.1), and when the per-hour count trips the cap, park
> the card in the Blocked COLUMN (not just comment) — OLD's exact §6 backstop.

**Layer**: `app/` (the imperative shell — the daemon's own move-record + the park-in-Blocked board
write). **Files**: `src/kanbanmate/app/tick.py` (`_reap_stale_agents` records its move into the
durable history; a new `_rate_limited` pre-check parks an over-limit ticket), `tests/app/test_tick.py`
(extend).

- [ ] **Record the daemon's own AUTO/bot moves into the DURABLE history.** Today `_reap_stale_agents`
      records its move-to-Blocked ONLY into the volatile in-memory `antiloop` (`record_move`,
      `tick.py:389`). Port OLD's `_auto_move` semantics: after a SUCCESSFUL reaper move (`ok_move` is
      `True`), ALSO call `deps.store.record_move_for_item(state.issue_number, now=now)` so the move
      feeds the DURABLE per-hour counter (13.1). Keep the existing `record_move(antiloop, …)` call too
      (the in-memory target-keyed dedup is a different, complementary guard — DESIGN §6 defense-in-depth).
      **The reaper's move-to-Blocked is the ONLY daemon-issued AUTO/bot move in NEW today** — there is
      no auto-advance — so it is the only `record_move_for_item` call-site. Document that any FUTURE
      daemon-issued bot move (e.g. a ported on_fail auto-move) MUST likewise call
      `record_move_for_item` here, exactly as OLD fed the counter ONLY from `_auto_move`.
- [ ] **Durable rate-limit gate before a daemon-issued AUTO move parks past the cap.** Add a small
      helper `_rate_limited(deps, issue, cap, now) -> bool` →
      `deps.store.move_count_for_item_last_hour(issue, now=now) >= cap`. Port of OLD's
      `runner.py:511-512` check (`>= cap → park`). The gate's CONSUMER is the daemon's own AUTO/bot
      move path: before the daemon issues a move that would itself be recorded (the reaper's
      move-to-Blocked is already going TO Blocked, so it cannot over-park — but the gate is the seam a
      future on_fail/auto-advance move uses). For NEW today, wire the gate as a guard on the reaper's
      move: when `_rate_limited(deps, state.issue_number, config.move_rate_limit_per_hour, now)` is
      already `True` BEFORE recording this move, the ticket is already at/over its hourly AUTO-move
      budget — the move-to-Blocked still proceeds (parking in Blocked IS the §6 remedy), but do NOT
      double-record it (skip the `record_move_for_item` so the counter cannot run away past the cap —
      port OLD's "park instead of acting + mark_processed" which stopped feeding the loop). State that
      the gate uses `config.move_rate_limit_per_hour` (13.4), so a board that set `6` gets `6`, not the
      hard-pinned in-core `10` (Delta 2 the audit flagged — the cap is now tunable again).
- [ ] **Reuse the Blocked-column park.** The §6 remedy is "park the card in the Blocked COLUMN", which
      NEW's `_ReapMove(item_id, config.blocked_column)` + the ⛔ sticky flip already perform on the reap
      path — so an over-rate ticket reaped here lands in Blocked exactly as OLD's `_park_blocked`
      (`runner.py:212-227`: bookkeeping move + comment). Confirm the reaper's existing
      move-to-Blocked + `record_move(antiloop, …)` + ⛔ flip is the parity equivalent of OLD's
      `_park_blocked`; do not duplicate a second board move.
- [ ] Tests (`tests/app/test_tick.py`): after a reaper move-to-Blocked the DURABLE
      `move_count_for_item_last_hour` for that issue INCREASES by 1 (the move was recorded on disk, not
      just in `antiloop`); a ticket already at `move_rate_limit_per_hour` durable AUTO-moves is NOT
      double-recorded by a further reaper move (the counter does not exceed the cap); the gate reads
      `config.move_rate_limit_per_hour` (set it to `2` in the test, assert the trip at 2 not 10); the
      durable count survives a fresh store instance (restart durability — the headline §6 fix).
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): durable per-item move rate-limit gate feeds the §6 park-in-Blocked backstop"
```

---

## 13.7 — corrective: restore the PoC slot-only/purge split + close drain & cap-gate marker bugs

> **Why this exists (adversarial verification 2026-06-06).** A four-lens adversarial review of the
> 13.5 keystone (run after 13.5 landed) found a **CRITICAL** defect that two independent lenses
> reproduced end-to-end on the REAL `FsStateStore`, plus several real-but-minor ones. Root cause: 13.3
> WIDENED `release_slot` into the exhaustive purge (it now also unlinks `queue/ticket-<n>` + `moves/`
>
> - `retries/`), but the PoC deliberately kept TWO functions — `cap.py:release_slot` (slot-only) and
>   `purge_ticket` (exhaustive) — precisely so the launch-failure / drain paths could free a slot WHILE
>   KEEPING the queue marker for retry. NEW's merge silently broke that invariant. Restoring the PoC
>   split is the faithful fix (directive: nothing left behind).

**The confirmed defects:**

1. **[CRITICAL] Failed drained launch DROPS the queued ticket.** `_drain_queue`'s failed-launch path
   (13.5) calls `release_slot(issue)` with the explicit contract "release the slot, KEEP the marker so
   a later sweep retries". On the real adapter `release_slot` DELETES `queue/ticket-<issue>` → the
   ticket is silently dropped, never retried (its card sits in the agent column so the diff emits no
   transition and nothing re-enqueues it). Reproduced: `dequeue_pending()==(7,)` before → `()` after.
   The unit test `test_drain_keeps_marker_and_releases_slot_on_failed_launch` uses a **MagicMock** store
   (release_slot is a no-op recorder), so it passes — **false confidence**.
2. **[MINOR→real once 13.6 lands] Cap-gate leak-safety wipes rate-limit/retry history.** The failed
   DIRECT-launch leak-safety (13.5 tick.py:670) also calls the exhaustive `release_slot`, wiping
   `moves/<issue>.json` + `retries/<issue>__*` on a transient launch failure — destroying the durable
   counters 13.1/13.2/13.6 maintain.
3. **[MAJOR] Watchdog-timeout race.** On a launch TIMEOUT (`_run_with_watchdog` returns `False` but the
   worker thread keeps running), the leak-safety `release_slot` races the abandoned worker's late
   `LaunchAction.save` → either a live agent with no slot (cap undercount) or a purged RUNNING state
   (orphan the reaper never sees). The worst case (double-launch) is already defended by tmux
   `new-session check=True` (duplicate-name fails cleanly).
4. **[MINOR] Latent double-launch window** once #1 is fixed: a fresh successful DIRECT launch does not
   clear a coexisting stale queue marker → the same-tick drain could re-dispatch it.
5. **[MINOR] Operator pull-back**: a queued card dragged to an inert column (NOOP) leaves its queue
   marker, so the drain later resurrects a withdrawn ticket.
6. **[MINOR/doc] `dequeue_pending` order** is lexicographic, not numeric — docstrings overstate
   "ascending / oldest first".

**Layer**: `ports/` (split the Protocol) · `adapters/store/` (split the impl) · `app/` (route each
caller to the right method + close the marker bugs). **Files**: `src/kanbanmate/ports/store.py`,
`src/kanbanmate/adapters/store/fs_store.py`, `src/kanbanmate/app/tick.py`,
`src/kanbanmate/app/actions.py` (Teardown/Reset → `purge_ticket`),
`src/kanbanmate/bin/kanban_session_end.py` (→ `purge_ticket`), `tests/adapters/test_fs_store.py`,
`tests/app/test_tick.py`, `tests/bin/test_kanban_session_end.py`, and any StateStore fake mypy flags.

- [ ] **Split the store API (restore the PoC two-function design).** In `fs_store.py`: RENAME the
      current exhaustive `release_slot` body to `purge_ticket(self, issue_number: int) -> None` (keep
      its full enumerated purge: state + slots + advances + queue + moves + retries, `glob.escape`
      defence, idempotent). Add a NEW slot-only `release_slot(self, issue_number: int) -> None` that
      unlinks ONLY `slots/ticket-<issue>` (no-raise, idempotent) — a faithful port of PoC
      `engine/cap.py:43-49`. Update `ports/store.py`: `release_slot` docstring → "frees ONLY the
      concurrency-cap slot marker; does NOT purge state/queue/moves/retries (used by launch-failure
      leak-safety + the drain so a kept queue marker survives a retry)"; ADD `purge_ticket` → the
      exhaustive teardown contract (enumerate every marker).
- [ ] **Route every caller to the correct method.**
  - EXHAUSTIVE `purge_ticket`: `TeardownAction` (actions.py:379), `ResetAction` (actions.py:442),
    `kanban_session_end.py` (117, 129 — the session is over, tear the runtime state down; keeps the
    "breadcrumb read BEFORE the purge" ordering — it is `purge_ticket` that now purges the breadcrumb).
  - SLOT-ONLY `release_slot`: the cap-gate failed-DIRECT-launch leak-safety (tick.py:670) and the
    drain failed-launch path (tick.py:826 — this is the CRITICAL fix: free the slot, KEEP the marker).
    The drain invalid-payload path (tick.py:785) stays "slot-only release + explicit `clear_queued`".
- [ ] **Close the drain already-running guard (timeout mitigation).** In `_drain_queue`, after a
      successful `reserve_slot` and BEFORE re-dispatch, if `deps.store.load(issue)` is a RUNNING state
      the ticket is already live (e.g. a timed-out launch that completed late) → `clear_queued(issue)` +
      slot-only `release_slot(issue)` + continue (do NOT re-dispatch → no tmux duplicate-name churn).
- [ ] **Clear a stale marker on a fresh direct launch.** On the cap-gate DIRECT-launch SUCCESS path
      (`ok is True` for a LAUNCH), `deps.store.clear_queued(issue)` (idempotent no-op when absent) so a
      fresh launch supersedes any stale queue marker — closes the #4 double-launch window.
- [ ] **Clear the marker on an operator pull-back.** In the NOOP-forward branch (agent→inert), call
      `deps.store.clear_queued(transition.ticket.issue_number)` (idempotent) so a queued card the
      operator withdrew to an inert column is not later resurrected by the drain (#5).
- [ ] **Fix `dequeue_pending` docstrings** (fs_store + the `_drain_queue` docstring): say "lexicographic
      by marker name" not "ascending / oldest first" (#6 — behaviour is a faithful PoC port; only the
      wording was wrong).
- [ ] **Tests — replace the false-confidence mock test with REAL-fs integration tests.**
  - `tests/app/test_tick.py`: REWRITE `test_drain_keeps_marker_and_releases_slot_on_failed_launch` to
    use a REAL `FsStateStore(tmp_path)` and assert `dequeue_pending() == (issue,)` (marker KEPT) +
    the slot is freed after a failed drained launch. Add: a failed DIRECT launch preserves
    `moves/<issue>` + `retries/<issue>__*` (real fs); the drain already-running guard clears the marker
    - does not re-dispatch when a RUNNING state exists; a fresh direct-launch SUCCESS clears a
      pre-seeded queue marker; a NOOP agent→inert move clears the queue marker.
  - `tests/adapters/test_fs_store.py`: re-target the exhaustive-purge tests (queue/moves/retries +
    breadcrumb + state + no-resurrection) to `purge_ticket`; add slot-only `release_slot` tests
    (unlinks ONLY the slot; leaves state/queue/moves/retries intact; idempotent).
  - `tests/bin/test_kanban_session_end.py`: update the `release_slot` assertions to `purge_ticket`
    (incl. the "breadcrumb read before the purge" regression test).
- [ ] **Known residual (documented, not fixed here):** the cap-gate DIRECT-launch timeout can still
      transiently run an agent without a slot (cap+1) until the reaper reconciles via the late-saved
      RUNNING state. A full fix needs a tri-state `_run_with_watchdog` (OK / FAILED / TIMED_OUT); that
      is a broader shared-helper change deferred to a follow-up. Note it in the report.
- [ ] Verify: `rm -rf .mypy_cache && make check` green; residual greps (below) updated for the split.

```bash
git commit -m "fix(genesis): restore PoC slot-only release_slot vs exhaustive purge_ticket (drain keep-marker invariant + cap-gate leak-safety)"
```

---

## 13.8 — corrective: per-issue budgets (moves/ + retries/) survive reaps & session-ends

> **Why this exists (re-verification 2026-06-06).** A regression re-check of the 13.7 split found two
> real-but-DORMANT defects (no live consumer trips them today, but they make 13.6's durability claim
> hollow and the tests INVALID): (1) the reaper's `TeardownAction → purge_ticket` wipes
> `moves/<issue>.json` one step BEFORE the SAME reap reads it for the rate-limit gate, so the durable
> §6 per-hour counter perpetually resets to 1 and `_rate_limited` can NEVER observe `>= cap`; (2)
> `kanban session-end` routes through `purge_ticket`, wiping `moves/` + `retries/` on EVERY normal
> session exit, resetting the per-issue rate-limit + (future) fix-CI retry budget per session. The PoC
> kept these per-issue budgets across reaps/sessions (reaper `_move_to_blocked` used slot-only
> `release_slot`; `end_session` set status=idle + slot-only release) and purged them ONLY on the
> deliberate Cancel / reset. **Operator decision 2026-06-06 — Option A:** make the reaper PRESERVE the
> budgets so 13.6's durable rate-limit actually accumulates and works (adapting the feeder to NEW's
> reality — NEW has no `_auto_move` yet — rather than removing it). The DAMNING evidence the fix is
> needed: `test_rate_limited_ticket_not_double_recorded` only passes because it STUBS
> `store.purge_ticket = lambda …: None` to stop the production purge — a test that disables production
> behaviour to assert a claim production cannot exhibit.

**The principle:** `moves/<issue>.json` (per-hour rate-limit) and `retries/<issue>__*` (fix-CI loop
budget) are **per-issue budgets** that must persist across the ticket's lifecycle (sessions, reaps)
and be torn down ONLY when the ticket is truly abandoned (**Cancel**) or **reset**.

**Layer**: `ports/` (purge_ticket signature) · `adapters/store/` (the conditional purge) · `app/` +
`bin/` (the reaper + session-end pass the flag). **Files**: `src/kanbanmate/ports/store.py`,
`src/kanbanmate/adapters/store/fs_store.py`, `src/kanbanmate/app/actions.py` (TeardownAction gains the
flag), `src/kanbanmate/app/tick.py` (the reaper constructs `TeardownAction(keep_budgets=True)`),
`src/kanbanmate/bin/kanban_session_end.py` (pass `keep_budgets=True` + fix the misleading messages),
`tests/app/test_tick.py`, `tests/app/test_actions.py`, `tests/bin/test_kanban_session_end.py`.

- [ ] **`purge_ticket(issue, *, keep_budgets: bool = False)`** (fs_store + Protocol). When
      `keep_budgets` is `True`, purge state + slot + advance breadcrumb + queue, but SKIP the
      `moves/<issue>.json` + every `retries/<issue>__*` unlink (preserve the per-issue budgets). Default
      `False` = the full exhaustive teardown (Cancel / reset). English docstrings stating WHICH callers
      pass `True` (reaper stale-agent teardown + session-end — the ticket may continue) and `False`
      (Cancel / reset — the ticket is abandoned).
- [ ] **`TeardownAction(keep_budgets: bool = False)`** (actions.py): a defaulted frozen-dataclass
      field; `execute` calls `deps.store.purge_ticket(issue, keep_budgets=self.keep_budgets)`. Cancel
      (cli/cancel) constructs the default (`False` → full purge); the reaper constructs
      `TeardownAction(ticket=…, keep_budgets=True)` in `_reap_stale_agents` so a reaped stale agent
      keeps its rate-limit/retry budgets while everything else is torn down. `ResetAction` stays the
      full purge (`purge_ticket(issue)` default `False`).
- [ ] **session-end** (kanban_session_end.py): both `purge_ticket(issue)` call-sites →
      `purge_ticket(issue, keep_budgets=True)` (an inter-session idle, not an abandonment — preserve
      the §6 + fix-CI budgets, PoC `end_session` fidelity). FIX the misleading messages: the early
      no-resurrection branch's "cap slot released" and the success "ticket #N marked idle" must reflect
      that the state record is removed but the per-issue budgets are preserved.
- [ ] **Fix the INVALID tests** (the headline — they assert behaviour production cannot exhibit):
  - `tests/app/test_tick.py::test_reap_records_move_into_durable_history` — REMOVE the reliance on the
    broken reset; with the reaper now preserving `moves/`, assert REAL accumulation: two reaps within
    the hour → `move_count_for_item_last_hour == 2` (not perpetually 1).
  - `tests/app/test_tick.py::test_rate_limited_ticket_not_double_recorded` — DELETE the
    `store.purge_ticket = lambda …: None` stub; with the reaper now keep_budgets=True the seeded
    history survives the REAL purge, so seed 3 → reap → gate sees `3 >= cap` → skips record → count
    stays 3 (asserted against the un-stubbed production path).
  - ADD: a reaper teardown PRESERVES `moves/` + `retries/` (real fs); a Cancel teardown PURGES them
    (real fs — `keep_budgets=False`); a normal session-end PRESERVES `moves/` + `retries/` (real fs).
  - `tests/app/test_actions.py`: a `TeardownAction(keep_budgets=True)` calls
    `purge_ticket(issue, keep_budgets=True)`; the default Cancel `TeardownAction` calls it with
    `keep_budgets=False`.
- [ ] Any StateStore fake mypy flags (the `purge_ticket` signature gained a kwarg): update the
      `_FakeStore` stub in `tests/cli/test_status.py` to `def purge_ticket(self, issue_number, *, keep_budgets=False)`.
- [ ] Verify: `rm -rf .mypy_cache && make check` green; no test stubs out `purge_ticket` to pass
      (`rg --type py "purge_ticket = lambda" tests` → ZERO matches).

```bash
git commit -m "fix(genesis): per-issue budgets survive reaps & session-ends (keep_budgets) — durable rate-limit accumulates"
```

---

### Phase 13 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`). **Clear `.mypy_cache` first** (incremental
   cache has masked real Protocol-conformance errors here — the 13.5 Drift note fans the new
   `StateStore` methods out to every test fake).
2. `make test` — all pass (check the summary line; any ERROR = collection crash, fix imports first).
3. `make check` — clean (lint + test + module-size guards; `fs_store.py` + `tick.py` stay under the
   ~800 LOC soft cap — if either crosses it, note it, do not refactor blindly).
4. Residual grep (split — audit fix):
   - `rg --type py "reserve_slot" src/kanbanmate/app src/kanbanmate/daemon` → the cap is now ENFORCED
     in the launch path (`tick.py` reserves before dispatch + the drain reserves) — NON-zero matches
     (the audit's "ZERO hits in the launch path" gap is closed).
   - `rg --type py "Intentionally empty: no queue backlog" src` → ZERO matches (the `_drain_queue`
     stub is gone).
   - `rg --type py "record_move_for_item|move_count_for_item_last_hour|bump_retry|reset_retry|queue_dir|enqueue_launch|dequeue_pending" src` →
     the four primitives are present in `ports/store.py` + `adapters/store/fs_store.py` (and called
     from `app/tick.py`).
5. Parity check — exercised in tests: the concurrency cap diverts an over-cap launch to the queue and
   the drain re-launches it when a slot frees WITHOUT exceeding the cap; a failed launch never leaks a
   slot; the per-item move rate-limit history is DURABLE (survives a fresh store) and tunable via
   `config.move_rate_limit_per_hour`; the fix-CI retry counter increments/resets per-(issue,key) and
   survives a restart. **Post-13.7 store split:** slot-only `release_slot` frees ONLY the slot (the
   drain's failed-launch path KEEPS the queue marker for retry — the CRITICAL fix, asserted on a REAL
   `FsStateStore`, not a mock); exhaustive `purge_ticket` purges `queue/`, `moves/`, and `retries/` on
   teardown / cancel / reset / session-end.
6. Residual grep (13.7 split): `rg --type py "def purge_ticket|def release_slot" src/kanbanmate` →
   BOTH methods exist in `ports/store.py` + `adapters/store/fs_store.py`; `rg --type py "release_slot"
tests/app/test_tick.py` → the drain failed-launch test uses a REAL `FsStateStore` (no MagicMock
   masking the marker purge).
7. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 13 gate — concurrency cap + queue + move rate-limit + fix-CI retry"
```
