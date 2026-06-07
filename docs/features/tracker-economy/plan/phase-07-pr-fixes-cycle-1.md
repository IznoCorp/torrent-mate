# Phase 7 — PR fixes cycle 1

## Context

Fixes identified during PR #141 review cycle 1 (`/implement:pr-review`). All
findings are **coherent with DESIGN.md scope** — they close silent-acceptance
gaps against the DESIGN's own stated contract:

- §"Validation rules (boot-time, fail-loud)": _"Durations: humanized parse or
  bare int; malformed → ValueError."_
- §Components.2: _"Accepts `<int><unit>` … Rejects malformed input with a clear
  `ValueError` (surfaced at config-load)."_

No design contradiction: the implementation already matches DESIGN; these
sub-phases harden the parser/validator to actually honour the fail-loud promise,
add the mandatory `Raises:` docstring (CLAUDE.md convention), and pin the
DESIGN-mandated behaviours with adversarial/boundary tests
(regression-test-per-bug rule). All edge cases below were **reproduced live**
during review against the current `feat/tracker-economy` HEAD.

**Out of scope (recorded, not actioned this cycle):** global `_StrictModel`
`strict=True` (cross-cutting; would reject legit int-for-float JSON5), `frozen=True`
on the shared base model (no consumer yet, touches all config models). These are
deferred to the first real consumer PR (Vague 5 — Ratio C1 / Seed-Safety O2).

## Sub-phases

### 7.1 — Fix: `parse_duration` silently accepts `bool` and malformed magnitudes

**Findings**: M1 (bool→1/0 s), M2 (interior whitespace / `+` / `_` magnitudes).
**Location**: `personalscraper/conf/models/_duration.py:25-37`
**Severity**: medium

Live-reproduced silent acceptances that must instead raise `ValueError`:

| Input                         | Current (silent)             | Required     |
| ----------------------------- | ---------------------------- | ------------ |
| `True` / `False`              | `True` / `False` (→ 1 / 0 s) | `ValueError` |
| `"72 h"` (interior space)     | `259200`                     | `ValueError` |
| `"+5h"`                       | `18000`                      | `ValueError` |
| `"1_0h"` (PEP-515 underscore) | `36000`                      | `ValueError` |

**Implementation constraints**:

- Reject `bool` **explicitly and first**: `isinstance(value, bool)` → `ValueError`
  (must precede the `isinstance(value, int)` bare-int passthrough, because
  `bool` is a subclass of `int`).
- Keep the bare-`int` passthrough for genuine ints (DESIGN: "Accepts a bare int").
- Tighten the magnitude grammar to **ASCII digits only**: validate `raw[:-1]`
  against `^[0-9]+$` (e.g. `re.fullmatch(r"[0-9]+", magnitude_str)` or an
  equivalent ASCII-digit check) **before** `int()`. This rejects interior
  whitespace, `+`/`-` signs, underscores, and unicode digits.
- **Preserve the existing granular, clear messages** (`"must not be empty"`,
  `"unknown duration unit …"`, `"non-integer magnitude …"`). Do not collapse to
  one generic message.

**Acceptance**:

- `parse_duration(True)` and `parse_duration(False)` each raise `ValueError`.
- `parse_duration("72 h")`, `parse_duration("+5h")`, `parse_duration("1_0h")`
  each raise `ValueError`.
- **No regression**: `parse_duration("90s")==90`, `"90m"==5400`, `"72h"==259200`,
  `"3d"==259200`, `"2w"==1209600`, `"24H"==86400`, `"0h"==0`, and
  `parse_duration(3600)==3600` all still pass.
- `make lint` clean (new `import re` if used; no unused imports).

### 7.2 — Fix: `NaN`/`inf` ratios pass both validation guards

**Finding**: M3 — `target_ratio=float('nan')` / `float('inf')` construct cleanly
(NaN comparisons are always `False`, so both the ordering check and the `>= 0`
loop are defeated). Live-reproduced.
**Location**: `personalscraper/conf/models/api_config.py:200-207` (`_validate_ratio_ordering`)
**Severity**: medium

**Implementation constraints**:

- Add `import math` and a finiteness guard for the float ratio fields
  (`target_ratio`, `min_ratio`) at the **top** of `_validate_ratio_ordering`,
  **before** the ordering comparison (so NaN is caught rather than slipping
  through the always-`False` comparison).
- Clear message, e.g. `f"{name} must be finite, got {value}"`.
- Do not apply `isfinite` to the int fields (`min_seed_time`, `hit_and_run_grace`);
  they are already ints post-coercion.

**Acceptance**:

- `TrackerEconomyConfig(target_ratio=float('nan'), min_seed_time=0)` raises `ValidationError`.
- `TrackerEconomyConfig(target_ratio=float('inf'), min_seed_time=0)` raises `ValidationError`.
- `TrackerEconomyConfig(min_ratio=float('nan'), target_ratio=2.0, min_seed_time=0)` raises `ValidationError`.
- **No regression**: all existing `test_tracker_economy_schema.py` tests still pass.

### 7.3 — Fix: missing `Raises:` docstring + self-contradictory attribute doc

**Findings**: M4 (DOC-1, missing `Raises:` — CLAUDE.md mandatory convention,
inconsistent with the sibling validator), DOC-2 (`min_seed_time` Attributes line
says "in seconds" _and_ "Accepts humanized string").
**Location**: `personalscraper/conf/models/api_config.py:171, 180-191`
**Severity**: medium (M4 = convention violation), minor (DOC-2)

**Implementation constraints**:

- Add a `Raises:` clause to `_parse_duration_field` documenting the `ValueError`
  it propagates from `parse_duration` (malformed string: unknown unit,
  non-integer magnitude, empty, or non-int/`bool` type) — mirror the sibling
  `_validate_ratio_ordering` docstring which already has `Raises:`.
- Update `parse_duration`'s own `Raises:` to mention the `bool`/non-int rejection
  added in 7.1.
- Rewrite the `min_seed_time` Attributes line to remove the contradiction, e.g.
  _"Minimum seed obligation, stored as integer seconds. Accepts a humanized
  string (e.g. `"72h"`) or a bare int at config load."_ (align with DESIGN.md:59).

**Acceptance**:

- `_parse_duration_field`, `parse_duration`, and `_validate_ratio_ordering` all
  carry a `Raises:` clause consistent with their behaviour.
- `min_seed_time` docstring no longer self-contradicts (single, accurate sentence).
- Google-style docstring convention satisfied; `make lint` clean.

### 7.4 — Test: adversarial parser cases + boundary/negative validation

**Finding**: M5 — DESIGN-mandated behaviours unpinned (negative _humanized_
duration end-to-end, negative `min_seed_time`/`hit_and_run_grace`, inclusive
equal-ratio boundary, parser adversarial inputs). Project rule: parser code
needs adversarial/golden coverage, and every fixed bug needs a reproducing test.
**Location**: `tests/unit/test_duration.py`, `tests/unit/test_tracker_economy_schema.py`
**Severity**: medium

**Add to `tests/unit/test_duration.py` (`TestParseDuration`)** — these MUST fail
against the pre-7.1 code and pass after:

- `parse_duration(True)` raises `ValueError`.
- `parse_duration(False)` raises `ValueError`.
- `parse_duration("72 h")` raises `ValueError`.
- `parse_duration("+5h")` raises `ValueError`.
- `parse_duration("1_0h")` raises `ValueError`.
- `parse_duration("h")` raises `ValueError` (bare unit, empty magnitude).

**Add to `tests/unit/test_tracker_economy_schema.py` (`TestTrackerEconomyConfig`)**:

- `test_equal_ratios_accepted`: `TrackerEconomyConfig(target_ratio=1.0, min_ratio=1.0, min_seed_time=0)`
  constructs successfully (pins the inclusive `>=` boundary; a `<`→`<=` regression must fail).
- `test_negative_min_seed_time_rejected`: bare-int `min_seed_time=-1` → `ValidationError` matching `min_seed_time`.
- `test_negative_hit_and_run_grace_rejected`: `hit_and_run_grace=-5` → `ValidationError` matching `hit_and_run_grace`.
- `test_negative_humanized_duration_rejected`: `min_seed_time="-3h"` → `ValidationError`
  matching `min_seed_time` (crosses the parse→validate seam; after 7.1 the parser
  rejects `"-3h"` directly — assert it surfaces as a `ValidationError` either way).
- `test_nan_target_ratio_rejected` / `test_inf_target_ratio_rejected`: from 7.2.

**Acceptance**:

- All new tests present and passing **after** 7.1–7.2; each negative/adversarial
  case asserts a specific `match=` where a message exists.
- The duration-string regression set (clean `<int><unit>` forms) still passes.

### 7.5 — Minor polish (bundled per user election)

**Findings**: CR-1/SF-7 (env default idiom), CR-2/SF-6 (empty-string passkey
doc + pin), TEST-5 (integration `match=`), TEST-6 (empty-string passkey test),
DOC-5 (positional `§Components.2` ref).
**Severity**: minor

**Implementation constraints**:

- `personalscraper/api/_activation.py` `resolve_optional_secret`: change signature
  to `env: Mapping[str, str] | None = None` and resolve `if env is None: env = os.environ`
  **inside the body** — match the sibling `resolve_active` idiom (avoids the
  import-time mutable-default binding). Behaviour identical.
- Document in that docstring that a **blank/empty-string** value is normalized to
  `None` (the load-bearing `env.get(k) or None`), so a Vague-5 consumer is not surprised.
- `tests/unit/test_activation.py` (`TestResolveOptionalSecret`): add
  `test_empty_string_passkey_returns_none` — `resolve_optional_secret("c411", env={"C411_PASSKEY": ""}) == {"C411_PASSKEY": None}`.
- `tests/conf/test_tracker_economy_integration.py` `test_malformed_duration_rejected_at_load`:
  tighten to `pytest.raises(ConfigValidationError, match="min_seed_time")` (or `match="duration"`).
- `personalscraper/conf/models/_duration.py` module docstring: replace the
  positional `Design: tracker-economy §Components.2.` with a durable reference,
  e.g. `Design: docs/features/tracker-economy/DESIGN.md ("Components → Duration parser").`

**Acceptance**:

- `resolve_optional_secret(env=None)` reads `os.environ` lazily; existing
  activation tests (incl. the non-gating proof) still pass.
- New empty-string passkey test passes; integration test now matches the specific cause.
- `make check` green overall (ruff + mypy + tests + module-size + typed-api).

## Phase gate

After 7.1–7.5: run the full mandatory phase-gate checklist (`make lint`,
`make test`, `make check`, smoke import) and **re-reproduce the entire
edge-case matrix** from this phase against the patched code (Opus main-session
verification, per the parser-code adversarial-review rule) before declaring green.
