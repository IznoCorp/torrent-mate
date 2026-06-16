# Implementation Progress — zero-deferrals (robustness batch 3)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: zero-deferrals — clear EVERY remaining deferred / minor / nit from the lifecycle audit
+ the 6 PR reviews, with zero new deferrals. Lands FIX 5 (body-top status header) + Candidates 1–5
+ the cockpit result-file GC. Built in an isolated worktree + venv; the live PM2 daemons (editable
install from the MAIN worktree) were never touched.
**Version bump**: minor (Y+1) — 0.2.0 → 0.3.0 (new body-status capability)
**Branch**: `feat/zero-deferrals`
**PR merge**: manual (human-only)
**PR**: _(created after the gate)_
**Design**: `docs/features/zero-deferrals/DESIGN.md` (+ `docs/features/clean-termination/DESIGN.md`
"FIX 5 — DONE")
**Master plan**: _(single feature branch — sub-phases below)_

## Phases

| Phase | Scope | Status | Commit |
|-------|-------|--------|--------|
| 1 | FIX 5 body-top status header: pure `core/body_edit.set_status_header` + delimiters; fail-soft `app/body_status.update_body_status`; call sites (launch/advance/done/block/waiting via `transition_step`/`tick`/`reaper`/`kanban_session_end`); adversarial roundtrip + fail-soft tests | DONE | `feat(zero-deferrals): body-top current-status header (FIX 5)` |
| 2 | Candidate 1: reaper Blocked-park no longer feeds the forward-advance budget (`record_move_for_item` dropped, anti-loop `record_move` kept; `_rate_limited` removed); docstrings in `ports/store` + `core/antiloop` + `script_route` + `kanban_session_end`; regression tests | DONE | `fix(zero-deferrals): reaper park excluded from the forward-advance rate-limit budget` |
| 3 | Candidate 2: `Sessions.repl_alive` port + adapter impl (comm-verified); `reaper._end_done_session` short-circuits when the REPL already exited; fakes + adapter + reaper tests | DONE | `fix(zero-deferrals): skip done-exit keystrokes when the REPL already exited` |
| 4 | Candidate 3 + result-GC: extract `ports/store_health.py` (`HealthStateStore` + `prune_item_health`) and `ports/store_intents.py` (`IntentStore` + `gc_intent_results`); `StateStore` composes both; adapter impls; wire `apply_health` prune + `drain_intents` GC; tests | DONE | `feat(zero-deferrals): GC health markers + cockpit result files (Protocol extraction)` |
| 5 | Candidate 4: `_auto_advance` returns its outcome; session-end done branch finalizes ⛔ on a rate-limited park (sticky + body-status reflect Blocked); tests | DONE | `fix(zero-deferrals): session-end sticky reflects the Blocked outcome on a rate-limited park` |
| 6 | Candidate 5: `cli/doctor_health.py` advisory Health-field check + ~6-line wire into `doctor.py` (kept ≤1000 LOC); tests | DONE | `feat(zero-deferrals): advisory kanban doctor Health-field check` |
| 7 | Docs + version: `docs/features/zero-deferrals/DESIGN.md`, clean-termination FIX-5 → DONE, this tracker, version bump 0.2.0 → 0.3.0 across all 5 pins | DONE | `docs(zero-deferrals): DESIGN + IMPLEMENTATION + version bump 0.3.0` |

## Behaviour deltas (gate requirement)

- **FIX 5 — body-top status header.** A delimited `<!-- kanban:status:begin -->…:end` block at the
  TOP of the issue body now mirrors the current stage + state (running/done/blocked/waiting/
  interrupted) + a short summary + timestamp, updated at every stage transition the engine finalizes
  a sticky for. Pure transform (`core/body_edit.set_status_header`, region-disjoint from the
  `**key**:` markers + `## Brainstorm`, idempotent, replace-in-place), fail-soft orchestrator
  (`app/body_status.update_body_status`, body-diff-gated, never raises into the tick), reuses the
  existing `Seeder` surface + wired `Deps.seeder`.
- **Candidate 1 — rate-limit conflation fixed.** The reaper park-in-Blocked no longer consumes the
  per-issue forward-advance budget (`moves/<issue>.json`) — it feeds ONLY the in-memory anti-loop
  runaway backstop. A busy ticket's genuine forward moves and the reaper's bookkeeping parks no
  longer share one cap, so a busy ticket is not parked mid-flow needing manual intervention.
- **Candidate 2 — done-exit idempotency.** New `Sessions.repl_alive`; the reaper skips re-sending
  `end_session` keystrokes (and the WAITING-park) when a daemon restart raced the wrapper and the
  `claude` REPL already exited.
- **Candidate 3 — health markers GC.** `apply_health` now prunes `health/last/<item>` markers for
  cards no longer on the board (bounded, fail-soft) — the directory stays proportional to the live
  board instead of growing forever.
- **Candidate 4 — Blocked-outcome sticky.** On a rate-limited runaway, the session-end stage sticky
  (and the body-status header) is finalized ⛔ blocked, not a misleading ✅ done on a now-Blocked card.
- **Candidate 5 — doctor Health check.** `kanban doctor` gained an ADVISORY Health-field check (PASS
  with all 5 options; WARN when an option is missing / unreadable; advisory skip with no project).
- **Result-file GC.** `drain_intents` now TTL-expires `intents/<id>.result.json` (1h) so the
  `intents/` directory no longer grows unbounded (cockpit DESIGN §10 promise honoured).
- **Protocol extractions (LOC ceiling).** `ports/store_health.py` (`HealthStateStore`) and
  `ports/store_intents.py` (`IntentStore`) were lifted out of `ports/store.py` (996 → 893);
  `StateStore` composes both. `cli/doctor_health.py` holds the Health check (`doctor.py` kept at
  1000). No module exceeds the 1000-LOC hard ceiling.

## Deferred

- **No robustness fixes deferred.** Per the operator directive, every remaining deferred / minor /
  nit robustness item from the audit + the 6 PR reviews was fixed in this batch (zero new robustness
  deferrals).
- **Out-of-scope future features (reported honestly, NOT deferred robustness bugs).** The collate
  classified four items as net-new feature scope, listed for visibility per the
  "nothing deferred without explicit authorization" directive (full reasons in DESIGN §8):
  1. Webhook ingress adapter / GitHub-App upgrade / multi-org / multi-project unified board —
     net-new feature scope (the polling diff stays the only ingress, §3.1).
  2. Cockpit agent `kanban-move` unification into the intent queue — net-new feature scope.
  3. Cockpit sleep-interrupt nudge mechanism — net-new feature scope.
  4. Post-merge cutover / engine PoC-conformance — net-new feature scope / separate effort.
- (Out of engine scope, unchanged) The `.claude/` portable-config edits documented in earlier
  DESIGNs (hybrid-flow §6 create-branch SKILL.md, clean-termination §6) live in the SEPARATE
  gitignored `.claude/` repo and were already done per the task brief; not engine code, not touched.
