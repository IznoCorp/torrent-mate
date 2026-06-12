# Phase 08 — PR-review fixes, cycle 1 (PR #196)

**Goal:** Resolve the concurrency/recovery-correctness findings from the PR #196
review: the hash-guard was persisted but never consulted (C1) and the service
batch loop had zero per-item error isolation (C2), plus an untested
profile-overlay handoff (M1) and two minors. A regression test accompanies every
finding (project rule: "regression test per bug").

**Branch:** `feat/grab-core` · **Baseline:** `95e1ec2b`

---

## Findings addressed

### C1 (MAJOR) — hash-guard consultation missing + add→mark_grabbed double-emit window (§11(d))

`grabbed_hash` was persisted by `mark_grabbed` but never **consulted**, and the
orchestrator emitted `GrabSucceeded` **before** the service persisted — so a
`mark_grabbed` crash left the row `'searching'` and the stale-recovery re-grab
emitted a **second** `GrabSucceeded`.

**Approach chosen: emit-after-persist (PREFERRED, not the pragmatic retry fallback).**

- `acquire/orchestrator.py` — `grab()` no longer emits `GrabSucceeded`; it returns the
  success payload on `GrabOutcome` (new `category` / `tags` fields alongside `info_hash`
  / `chosen`). The FAILURE events (`GrabFailed` / `WantedAbandoned`) are still emitted by
  the orchestrator — no irreversible side-effect precedes them, so they have no
  persist-then-crash window. **Success is special** (the torrent `add()` is the only
  irreversible side-effect that precedes persistence), so its emit moves to follow
  persistence. Documented in DESIGN §15 + module/`GrabOutcome` docstrings.
- `acquire/service.py` — new `_persist_success()` runs `mark_grabbed` FIRST then emits
  `GrabSucceeded`. A `mark_grabbed` crash → NO emit → the single re-grab emits exactly
  once. Added a **hash-guard consultation** short-circuit: a re-fetched row already
  carrying `grabbed_hash` (or `status='grabbed'`) is skipped (no re-grab / re-emit) as
  belt-and-suspenders over the `claim_for_search` `WHERE status='pending'` guard.

**Regression:** `test_section_11d_crash_window_emits_grab_succeeded_exactly_once` —
`add()` succeeds → `mark_grabbed` raises `OperationalError` once → stale-recovery
re-grabs → asserts exactly ONE `GrabSucceeded` across both runs AND an idempotent
double-`add` (same `info_hash`). Plus
`test_service_emits_grab_succeeded_after_persist_exact_payload` (the service now owns
the emit, persist-before-emit ordering + exact payload).

### C2 (MAJOR) — service batch loop has zero error isolation

`acquire/service.py` — the per-item body (`_process_item`) is wrapped in a narrow
try/except in `run()`:

- `sqlite3.OperationalError` (DB lock, RETRYABLE §6.2) → log `acquire.service.item_db_locked`,
  count skipped, leave the row `'searching'` for the stale-searching sweep, `continue`.
- `json.JSONDecodeError` (corrupt `criteria_json`/`quality_profile_json`) → set that row
  `'abandoned'` (guarded) + log `acquire.service.item_bad_criteria_json`, `continue`.
- NO bare `except Exception` — a genuine programming bug still surfaces and crashes loudly.

ONE bad row never aborts the batch; `run_complete` always fires.

**Regression:** `test_run_isolates_db_lock_and_continues_batch` (item 1's `mark_grabbed`
raises `OperationalError` → item 2 still grabbed, run completes, counts sane) +
`test_run_isolates_corrupt_criteria_json_abandons_only_that_row`.

### M1 (MEDIUM) — profile-overlay branch untested

**Regression:** `test_resolve_profile_follow_lookup_passes_floor_to_orchestrator` — seeds a
`FollowedSeries` with a non-permissive `quality_profile_json` (min_resolution 1080p) + a
`WantedItem` bound via `followed_id`; a mock orchestrator captures the `profile` arg and
asserts it carries `Resolution.R1080P` (proves the live follow-lookup + overlay handoff,
not just unit-level `effective_quality`).

### Minors

- **m1** — `tests/acquire/test_orchestrator.py`: trimmed the 3 vacuous `seed_spy.*`
  assertions on the unwired mock (a mock passed nowhere can never be touched); kept the
  load-bearing belt-and-suspenders dep-scan the NEGATIVE guarantee rests on.
- **m3** — `acquire/service.py`: on a `success` disposition with a falsy `info_hash`, log
  `acquire.service.success_without_hash` instead of silently coercing to `""`.
- m2 (silverleech dedup tier test) — NOT done (optional, out of scope this cycle).

---

## Files changed

- `personalscraper/acquire/orchestrator.py` — emit-after-persist (no `GrabSucceeded` emit;
  carry `category`/`tags` on `GrabOutcome`); docstrings.
- `personalscraper/acquire/service.py` — `_process_item` + `_persist_success` + error
  isolation + hash-guard consultation + m3 log.
- `tests/acquire/test_service.py` — C1/C2/M1 regression tests; emit-after-persist updates.
- `tests/acquire/test_orchestrator.py` — emit-after-persist test updates; m1 trim.
- `docs/features/grab-core/DESIGN.md` — §15 PR-fixes-cycle-1 note (emit-ordering decision).

---

## Quality gate

- `pytest tests/acquire/ tests/commands/test_grab.py tests/architecture/` — 0 failures.
- `mypy personalscraper/acquire/` — 0 errors.
- `make check` — green.
- `git status --short` — clean after each commit (commit any ruff reformat).
