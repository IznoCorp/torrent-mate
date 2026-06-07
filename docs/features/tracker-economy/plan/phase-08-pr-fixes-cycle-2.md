# Phase 8 — PR fixes cycle 2 (minor polish, user-elected)

## Context

PR #141 review cycle 2 was **clean (Case A — 0 blocking findings)**; all 5 cycle-1
findings were confirmed resolved. This phase is a **discretionary, user-elected
polish** of the 4 _minor_ cycle-2 findings (the review loop did not require it).
All changes are test additions/tightenings + one cosmetic error-message
improvement — no behavioural change to valid inputs.

Findings addressed: SF2-1, TEST2-2, TEST2-1, SF2-2 (see IMPLEMENTATION.md cycle-2 record).

## Sub-phases

### 8.1 — SF2-2 (clearer missing-unit message) + TEST2-2 (direct parser `-3h` test)

**Findings**: SF2-2 (`"72"`/`"3.0"` raise as "unknown duration unit '2'/'0'", misdirecting —
the real issue is a missing unit), TEST2-2 (no direct parser-layer test for a leading `-`).
**Location**: `personalscraper/conf/models/_duration.py`, `tests/unit/test_duration.py`
**Severity**: minor

**Implementation constraints**:

- In `parse_duration`, when `raw[-1]` is an **ASCII digit** (the user likely forgot the
  unit), raise a clearer message instead of "unknown duration unit", e.g.
  `f"missing duration unit in {raw!r}; append one of {', '.join(_UNIT_SECONDS)} (e.g. '72h') or pass a bare int for seconds"`.
  Guard with `raw[-1].isascii() and raw[-1].isdigit()` so unicode digits stay on the
  "unknown duration unit" path. Keep "unknown duration unit" for genuine non-digit
  unknown units (e.g. `"3x"`).
- Update the docstring `Raises:` to mention the missing-unit case.
- **Existing test churn**: `test_malformed_no_unit` uses `"3600"` (digit last char) and
  asserts `match="unknown duration unit"` — update it to `match="missing duration unit"`
  (same commit). `test_malformed_unknown_unit` (`"3x"`) stays on "unknown duration unit".
- Add `test_minus_sign_magnitude_rejected`: `parse_duration("-3h")` raises `ValueError`,
  `match="non-integer magnitude"` (mirrors the existing `+5h` test at the parser's own layer).

**Acceptance**:

- `parse_duration("72")` and `parse_duration("3.0")` raise `ValueError` matching `"missing duration unit"`.
- `parse_duration("3x")` still raises `ValueError` matching `"unknown duration unit"`.
- `parse_duration("-3h")` raises `ValueError` matching `"non-integer magnitude"`.
- **No regression**: `"72h"`/`"3d"`/`"2w"`/`"24H"`/`"0h"`/bare-int all still parse correctly.
- `make lint` clean; updated `test_malformed_no_unit` passes with the new match.

### 8.2 — SF2-1 (`min_ratio` non-finite regression tests) + TEST2-1 (tighten `-3h` match)

**Findings**: SF2-1 (`min_ratio` non-finite is guarded in code — verified live — but only
`target_ratio` has a NaN/inf regression test; a future loop-tuple narrowing could silently
reopen the `min_ratio` hole), TEST2-1 (`test_negative_humanized_duration_rejected` uses
`match="min_seed_time"` but the docstring claims parser sign-rejection — over-broad).
**Location**: `tests/unit/test_tracker_economy_schema.py`
**Severity**: minor

**Implementation constraints**:

- Add `test_nan_min_ratio_rejected`: `TrackerEconomyConfig(target_ratio=2.0, min_ratio=float("nan"), min_seed_time=0)`
  → `ValidationError`, `match="finite"`. Pins the `min_ratio` branch of the `math.isfinite` loop.
- Add `test_inf_min_ratio_rejected`: same with `float("inf")` → `ValidationError`, `match="finite"`.
- Tighten `test_negative_humanized_duration_rejected` to `match="non-integer magnitude"` (the
  actual parser-layer rejection path for `"-3h"`), so the test pins the documented mechanism,
  not just the field-name location.

**Acceptance**:

- `min_ratio=float("nan")` and `min_ratio=float("inf")` each raise `ValidationError` matching `"finite"`.
- `test_negative_humanized_duration_rejected` passes with `match="non-integer magnitude"`.
- **No regression**: all existing `test_tracker_economy_schema.py` tests still pass.

## Phase gate

After 8.1–8.2: full `make check` + smoke import + **mutation check** on the 2 new
`min_ratio` NaN/inf tests (revert the `isfinite` guard, confirm they fail, restore) — proving
they genuinely pin the `min_ratio` branch. Push + CI green, then hand off PR #141 for the
**manual** squash merge (the review loop already exited at cycle 2; this is verified
remediation, not a new review cycle).
