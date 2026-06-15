# Phase 7 — PR fixes cycle 2

> Fixes from `/implement:pr-review` cycle 2 (PR #200, 4-lens re-review of the cycle-1 delta). Cycle-1 fixes verified correct + complete (code-reviewer CLEAN; type-design FD-01/02 resolved 9/10; silent-failure fail-soft "correct and complete"). 1 medium (observability) + minor test/type hardening retained. Ignored: float-vs-int strictness (pre-existing leniency, reviewers said don't gate), single-tier dead-band (informational, no missed path).

**Goal:** Make a dropped per-series cadence override **actionable** (log the owning series), close the last representable-illegal-state (`CadenceTier` leaf guard), and tighten the cadence test suite (untested `TypeError` decode branch + misleading docstring + `match=` durability + a stronger dead-band negative control).

---

## Gate

Phase 6 complete: `make check` green (6815 passed), cycle-1 fixes pushed, CI green on PR #200.

---

## Sub-phase 7.1 — Actionable dropped-override + CadenceTier leaf guard

**Files:** `personalscraper/acquire/service.py`, `personalscraper/acquire/cadence.py`, `tests/acquire/test_service_cadence.py`, `tests/acquire/test_cadence.py`.

### Task 1 — observability + leaf guard

- [x] **F-L — actionable dropped per-series cadence override (silent-failure FINDING 1).**
      In `AcquisitionService.run()` (the cadence resolution at ~`service.py:216-220`), replace the inline `cadence = effective_cadence(cadence_from_json(fs.cadence_json) if fs else None, global_cadence)` with a form that distinguishes "no override" from "override present but rejected", and logs the latter with the owning series identity:
      `python
override = None
if fs is not None and fs.cadence_json is not None:
    override = cadence_from_json(fs.cadence_json)
    if override is None:
        log.warning(
            "acquire.service.cadence_override_dropped",
            followed_id=fs.id,
            title=fs.title,
        )  # malformed per-series cadence_json → fell back to the global default
cadence = effective_cadence(override, global_cadence)
`
      `cadence_from_json` keeps its own `acquire.cadence.bad_cadence_json` warning (the parse-level detail); this adds the series-level breadcrumb at the call site where `fs` is known. (`cadence_from_json` signature unchanged — the call site owns the identity.)
  - Test `test_service_cadence.py::test_malformed_per_series_cadence_logs_series_and_uses_default`: a `FollowedSeries` with `cadence_json='{"broken'` (or an empty-tiers blob), `store.follow.get` returns it; assert (via `caplog`) a `WARNING` carrying the event `acquire.service.cadence_override_dropped` AND that the item is still processed under the **global** default (e.g. a recent item proceeds to claim, not abandoned). Use the repo's structlog→caplog bridge (see `tests/conftest.py`; precedent `tests/acquire/test_delete_authority.py`). Mutation-proof: fails if the call site doesn't log the drop.

- [x] **F-M — `CadenceTier` leaf guard (type-design residual → 10/10).**
      Add a `__post_init__` to the frozen `CadenceTier` dataclass raising `ValueError` when `max_age_s <= 0` or `interval_s <= 0`, so the leaf type is independently sound (not only validated inside `Cadence`). cadence.py stays pure (stdlib only). Confirm `Cadence.__post_init__` still works (it iterates already-constructed tiers — leaf guard fires first on a bad tier, which is fine).
  - Tests (test_cadence.py): `test_cadence_tier_rejects_nonpositive` — `pytest.raises(ValueError, match=...)` for `CadenceTier(max_age_s=0, ...)` and `CadenceTier(max_age_s=1, interval_s=-1)`. Positive control: a valid `CadenceTier` builds.

- [x] **Gate 7.1:** `pytest tests/acquire/test_service_cadence.py tests/acquire/test_cadence.py -q` green; `ruff` + `mypy personalscraper/acquire/service.py personalscraper/acquire/cadence.py` clean.
- [x] **Commit:** `fix(follow-detect): log dropped per-series cadence override + CadenceTier leaf guard`

---

## Sub-phase 7.2 — Test completeness + durability

**Files:** `tests/acquire/test_cadence.py`.

### Task 2 — close the test gaps (pr-test F1/F2/F3)

- [ ] **F-N — untested `TypeError` decode branch + misleading docstring (pr-test F1).**
      `cadence_from_json`'s `except` is `(json.JSONDecodeError, KeyError, TypeError, ValueError)` but the existing `test_cadence_from_json_malformed_returns_none` exercises only 3 branches. Add a `TypeError` case: `assert cadence_from_json('{"tiers": 5, "cutoff_s": 10}') is None` ("'int' object is not iterable"). Also fix the test's docstring/comment: the `'{"tiers": []}'` case actually fails at `KeyError: 'cutoff_s'` (it never reaches the empty-tiers `ValueError`); the `ValueError`/`__post_init__` branch is covered by the negative-duration case. Reword so the comment matches reality.

- [ ] **F-O — `match=` on the `__post_init__` rejection tests (pr-test F2).**
      Add a `match=` regex to each `pytest.raises(ValueError)` in the `test_cadence_post_init_rejects_*` suite (e.g. `match="empty"`, `match="must be positive"`, `match="strictly increasing"`, `match="cutoff"`) so a future guard-reorder or merged error path is caught as a regression. (Align the `match=` strings with the actual `ValueError` messages — read them from `cadence.py`.)

- [ ] **F-P — strengthen the dead-band negative control (pr-test F3).**
      `test_is_due_dead_band_too_recent_not_due` passes even against the pre-fix `return False`, so it adds little. Make it independently load-bearing: in the SAME `[last_tier, cutoff)` window, assert that an item with `last_search_at` **older** than the Cold interval is due (True) AND one with a **recent** `last_search_at` is not due (False) — anchoring the not-due to the interval, not a blanket freeze. (The True half already lives in `test_is_due_dead_band_uses_last_tier_interval`; ensure the pair pins "interval-gated within the dead-band", and that the not-due half would FAIL if the fallback used a zero/Hot interval.)

- [ ] **Gate 7.2:** `pytest tests/acquire/test_cadence.py -q` green; assertions name WHICH (never bare `raises` without `match` for the guard suite).
- [ ] **Commit:** `test(follow-detect): cover TypeError decode branch + match= guard messages + stronger dead-band control`

---

## Final gate (main session, phase 7 milestone)

`make check` green + `python -c "import personalscraper"` smoke (no docs/feature_map change → design-gaps unchanged). Then mark phase 7 `[x]`.
