# DESIGN — zero-deferrals (robustness batch 3, v0.3.0)

> Clear every remaining deferred / minor / nit from the lifecycle audit + the 6 PR reviews, with
> **zero new deferrals**. Built in an isolated worktree + venv; the live PM2 daemons (editable
> install from the MAIN worktree) were never touched.

Grounded against `main` (HEAD `6dc36aa`, v0.2.0). The full 2026-06-16 robustness arc (#18–#24) is
already merged + deployed; this batch is the follow-up that lands FIX 5 and every other outstanding
real-fix item.

## 1. FIX 5 — body-top status header (was the big deferral)

See `docs/features/clean-termination/DESIGN.md` → "FIX 5 — DONE" for the full as-built design. In
short: a pure `core/body_edit.set_status_header` inserts/replaces a delimited
`<!-- kanban:status:begin -->…<!-- kanban:status:end -->` block at the TOP of the issue body; a
fail-soft `app/body_status.update_body_status` orchestrates it on the existing `Seeder` surface,
body-diff-gated and region-disjoint from the `**key**:` markers + `## Brainstorm` section; it is
called at every stage transition the engine finalizes a sticky for — launch (`running`), advance
(`done`), waiting/blocked (reaper), AND the TERMINAL transitions (Done-arrival → `done`, Cancel →
`cancelled`, via `TeardownAction.execute`; the `reap` flavour is excluded — the reaper writes
`blocked` itself). Each call has its own try/except so it can never break the producer. On a LAUNCH
tick the header is written EXACTLY once — the new stage's `running`; the LEFT stage's `done`
body-status is suppressed in `_finalize_left_stage` (the ✅ sticky flip still runs) so the single
end-of-tick header shows the new stage, with no same-tick double write.

## 2. Candidate 1 — rate-limit conflation (reaper park vs forward-advance budget)

The reaper's park-in-Blocked is a TERMINAL bookkeeping move; it must NOT consume the per-issue
FORWARD-ADVANCE budget (`moves/<issue>.json`) the fix-CI / rework / session-end auto-advance loops
gate on. **Fix:** drop the `record_move_for_item` call at the reaper Blocked-park (`app/reaper`),
keeping ONLY the in-memory anti-loop `record_move` (the runaway backstop's feeder). The
script-route cap-park (`_park_runaway`) was already correct. Docstrings updated in `ports/store`
(`record_move_for_item` feeder list) and `core/antiloop` (canonical feeder list) to exclude the
reaper park; the now-dead `reaper._rate_limited` helper was removed and its cross-references
de-pointed.

## 3. Candidate 2 — daemon-restart mid-done-exit idempotency

Before re-dispatching `end_session` keystrokes for a still-present done breadcrumb, the reaper now
confirms the pane still hosts a live comm-verified `claude` child. **Fix:** new
`Sessions.repl_alive(name) -> bool` port (impl in `adapters/workspace/sessions` reusing
`_pane_pid` + `_child_pid`, fail-soft → `False`); `reaper._end_done_session` short-circuits
(consumes the branch, no keystrokes, no WAITING-park) when `repl_alive` is `False`. A probe error
falls through to the normal graceful dispatch (no regression).

## 4. Candidate 3 — health-field markers GC

`health/last/<item>` markers were never removed when a card left the board (only a project rebind
cleared them all). **Fix:** new `HealthStateStore.prune_item_health(live_item_ids)` (impl in
`adapters/store/fs_health_state` reusing the SAME sanitiser the marker write uses) unlinks any
marker not in the live snapshot; called from `app/health_reporter.apply_health` after the per-card
loop, fail-soft. **LOC-ceiling extraction:** `ports/store.py` was at 996/1000, so the 9 Health
Protocol stubs were lifted into a new `ports/store_health.py` (`class HealthStateStore(Protocol)`,
+ `prune_item_health`), composed via `class StateStore(HealthStateStore, IntentStore, Protocol)`.

## 5. Candidate 4 — session-end runaway sticky reflects the Blocked outcome

On a rate-limited runaway, `_auto_advance` parks the card in Blocked but the sticky was finalized
✅ done first (misleading). **Fix:** `_auto_advance` now RETURNS its outcome
(`advanced` | `stopped` | `parked_blocked`); the done branch runs it FIRST, then finalizes the
sticky ⛔ blocked (+ a `rate-limited — parked in Blocked` note + the FIX-5 body-status `blocked`)
on `parked_blocked`, else ✅ done.

## 6. Candidate 5 — `kanban doctor` Health-field advisory check

`doctor.py` gained no Health-field check. **Fix:** new `cli/doctor_health.py`
(`_check_health_field` + `_resolve_health_check`, mirroring the board-probe pattern) — an ADVISORY
check (always `ok=True`; `WARNING:` detail when an option is missing / the field is unreadable;
advisory skip with no project). `doctor.py` gained only the import + a resolver call + one check
tuple (kept at exactly 1000 LOC, under the hard ceiling).

## 7. Additional — cockpit result-file GC

`intents/<id>.result.json` files were never deleted (the cockpit DESIGN §10 "Result GC" promise).
**Fix:** new `IntentStore.gc_intent_results(*, now, ttl)` (impl in `adapters/store/fs_intents`)
TTL-expires `*.result.json` older than 1h; called once per `drain_intents` (BEFORE the
empty-pending early return, since results outlive their pending markers), fail-soft.
**LOC-ceiling extraction:** the intent Protocol stubs were lifted into a new
`ports/store_intents.py` (`class IntentStore(Protocol)` + `gc_intent_results`), composed into
`StateStore` alongside `HealthStateStore`.

## 8. Proposed no-fix (out-of-scope future features)

Every discovered **robustness bug / deferred / minor / nit** from the lifecycle audit + the 6 PR
reviews was fixed in this batch (zero new robustness deferrals). The collate ALSO surfaced four
items it classified as **not-a-bug / out-of-scope future features** — net-new feature scope, NOT
deferred robustness fixes. Per the operator directive ("nothing deferred without explicit
authorization"), they are listed honestly here rather than implemented or silently dropped:

1. **Webhook ingress adapter / GitHub-App upgrade / multi-org / multi-project unified board.** A new
   ingress + auth + cross-board model — a major architectural feature, not a robustness fix. The
   polling diff remains the only ingress (DESIGN §3.1). _No-fix reason: net-new feature scope._
2. **Cockpit agent `kanban-move` unification into the intent queue.** Routing an agent's own
   `kanban-move` through the cockpit intent queue is a new design surface (a behaviour change to the
   agent helpers), not a fix to existing behaviour. _No-fix reason: net-new feature scope._
3. **Cockpit sleep-interrupt nudge mechanism.** A new mechanism to interrupt the daemon's poll sleep
   on an operator nudge — a new feature, not a correctness fix. _No-fix reason: net-new feature
   scope._
4. **Post-merge cutover / engine PoC-conformance.** A larger conformance/migration effort (the
   docs-effort-paused track), not a contained robustness fix. _No-fix reason: net-new feature scope
   / separate effort._

These are reported for visibility and remain unauthorised feature work; none is a robustness bug
left unfixed in this batch.

## 9. LOC-ceiling discipline (load-bearing constraints honoured)

- `ports/store.py` 996 → 893 (two Protocol extractions: `store_health.py`, `store_intents.py`).
- `cli/doctor.py` 988 → 1000 (Health check extracted to `doctor_health.py`; only import + call +
  one tuple added inline).
- `app/actions.py` left byte-neutral (999) — the launch `running` body-status is emitted from
  `app/transition_step` (ample headroom), not inlined in `actions.py`.
- No module exceeds 1000 LOC after this batch (`make check` size guard green).
