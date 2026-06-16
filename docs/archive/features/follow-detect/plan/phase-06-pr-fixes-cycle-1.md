# Phase 6 — PR fixes cycle 1

> Fixes from `/implement:pr-review` cycle 1 (PR #200, 5-lens review). All findings are coherent with DESIGN scope (the cadence subsystem is net-new in this PR). 0 critical, 0 major, 6 medium retained + minor doc touch-ups. Ignored: systemic-poll no-coverage signal (out of scope — needs RP9 contract change), redundant `store.follow.get` (pre-existing), `--series` numeric shadowing (documented UX), `db_path` WAL validator (pre-existing).

**Goal:** Close the config-reachable cadence **dead-band** (the convergent top finding), harden the `Cadence` VO so illegal states are unrepresentable, make `cadence_from_json` defensive, and pin the under-asserted cadence/validator/service branches with regression tests. Plus minor doc accuracy fixes.

---

## Gate

Phase 5 complete: `make check` green (6804 passed), PR #200 open, CI green.

---

## Sub-phase 6.1 — Fix the cadence dead-band + harden the `Cadence` VO

**Files:** `personalscraper/acquire/cadence.py`, `tests/acquire/test_cadence.py`.

### Task 1 — dead-band fix + VO invariant guard

- [ ] **F-A — dead-band fix (DESIGN §3 intent: keep searching until cutoff, then abandon).**
      In `is_due_by_cadence`, when no tier matches (`age >= tiers[-1].max_age_s`) but the item is **not** past cutoff, fall back to the **last** tier's interval instead of returning `False`. Replace:
      `python
    tier = next((t for t in cadence.tiers if age < t.max_age_s), None)
    if tier is None:
        return False
    `
      with:
      `python
    tier = next((t for t in cadence.tiers if age < t.max_age_s), cadence.tiers[-1])
    # age beyond the last tier but before cutoff → keep searching at the slowest
    # (last/Cold) cadence until is_past_cutoff fires. Prevents the dead-band freeze
    # when cutoff_s > tiers[-1].max_age_s (validator allows cutoff >= last tier).
    `
      Canonical config (cutoff == last tier) is unaffected: any `age >= cutoff_s` is caught by `is_past_cutoff` first, so the fallback only activates for custom configs with `cutoff_s > tiers[-1].max_age_s`.

- [ ] **F-B — `Cadence.__post_init__` invariant guard (illegal states unrepresentable).**
      Add a `__post_init__` to the frozen `Cadence` dataclass that raises `ValueError` when: `tiers` is empty; any `CadenceTier.max_age_s <= 0` or `interval_s <= 0`; `tiers` not strictly increasing by `max_age_s`; or `cutoff_s < tiers[-1].max_age_s`. This makes EVERY construction path (`cadence_from_config`, `cadence_from_json`, direct) self-validating, matching the `CadenceConfig` validator's contract at the VO level. Keep the predicates branch-free (the guard runs once at build, not on the hot path).

- [ ] **Tests (test_cadence.py):**
  - `test_is_due_dead_band_uses_last_tier_interval` — a cadence with `cutoff_s > tiers[-1].max_age_s` (e.g. tiers Cold max=720h, cutoff=960h); an item with `age` in `[720h, 960h)` and `last_search_at` one Cold interval back → `is_due_by_cadence(...) is True` (searches at Cold cadence, NOT frozen). And a sibling asserting a too-recent `last_search_at` in that window → `False`. **Mutation-proof:** these MUST fail against the pre-fix `return False`.
  - `test_cadence_post_init_rejects_*` — `pytest.raises(ValueError)` for empty tiers, a non-positive `max_age_s`/`interval_s`, non-monotonic tiers, and `cutoff_s < tiers[-1].max_age_s`. Plus a positive control: the canonical `Cadence(...)` builds without raising.
- [ ] **Gate 6.1:** `pytest tests/acquire/test_cadence.py -q` green; `ruff check` + `mypy personalscraper/acquire/cadence.py` clean.
- [ ] **Commit:** `fix(follow-detect): close cadence dead-band + add Cadence VO invariant guard`

---

## Sub-phase 6.2 — Defensive decode + pin under-asserted branches

**Files:** `personalscraper/acquire/desired.py`, `tests/acquire/test_cadence.py`, `tests/acquire/test_service_cadence.py`.

### Task 2 — defensive `cadence_from_json` + test strengthening

- [ ] **F-C — `cadence_from_json` defensive (latent unvalidated boundary; decode is wired into `service.py`).**
      Make `cadence_from_json` fail-soft on a malformed blob: wrap the `json.loads` + dict access in `try/except (json.JSONDecodeError, KeyError, TypeError, ValueError)`; on failure, log a `warning` (`acquire.cadence.bad_cadence_json`, via `get_logger`) and return `None` (→ caller falls back to the global default via `effective_cadence`). A structurally-valid-but-semantically-invalid blob now also raises via `Cadence.__post_init__` (F-B) and is caught here. (`desired.py` may need a module logger if it has none — use `personalscraper.logger.get_logger`, never structlog.) - Test `test_cadence_from_json_malformed_returns_none` — feed `"{not json"`, `'{"tiers": []}'` (missing cutoff / empty), `'{"tiers": [{"max_age_s": -1, "interval_s": 1}], "cutoff_s": 5}'` → each returns `None` (no crash).

- [ ] **F-D — not-due skip path must not mutate status (pr-test FD-01).**
      In `test_service_cadence.py::test_not_due_item_is_skipped_no_claim`, add `store.wanted.set_status.assert_not_called()` (a not-due item stays `pending`; mirrors what the cutoff test asserts). Mutation-proof: fails if the skip path ever writes status.

- [ ] **F-E — validator rejection completeness (pr-test FD-03, ACCEPTANCE crit 3).**
      In `test_cadence.py`, add `pytest.raises(ValidationError)` tests for `CadenceConfig(tiers=[])` and a tier with `max_age_hours=0` / `interval_minutes=0` (the validator already guards these; pin them).

- [ ] **F-F — per-series cadence override exercised through the service (pr-test FD-05 / type-design).**
      Add `test_service_cadence.py::test_per_series_cadence_override_abandons` — a `FollowedSeries` whose `cadence_json` encodes a **tight** cutoff (via `cadence_to_json`) that abandons an item the **global default** would keep; `store.follow.get` returns that series. Assert `WantedAbandoned(reason='cutoff_reached')` emitted (proves `service.py` consults `cadence_from_json(fs.cadence_json)` via `effective_cadence`, not just the global default). Mutation-proof: fails if the service drops the per-series override lookup.

- [ ] **Gate 6.2:** `pytest tests/acquire/test_cadence.py tests/acquire/test_service_cadence.py -q` green; `ruff` + `mypy personalscraper/acquire/desired.py` clean.
- [ ] **Commit:** `test(follow-detect): defensive cadence_from_json + pin not-due/validator/per-series-override branches`

---

## Sub-phase 6.3 — Doc accuracy + cadence purity test

**Files:** `personalscraper/acquire/desired.py` (module docstring), `personalscraper/commands/follow.py` (module docstring + one comment), `docs/reference/architecture.md`, `tests/acquire/test_cadence.py` (or a layering test).

### Task 3 — minor doc/comment fixes + purity pin

- [ ] **F-G — stale LOC figure (comment-analyzer FD-01).** In `desired.py` module docstring, replace the hard `684-LOC`/`store.py` budget figure with a ceiling-relative phrasing (e.g. "so `store.py` stays under the 1000-LOC module ceiling") so it stops rotting on every `store.py` edit.
- [ ] **F-H — `follow.py` module docstring (comment-analyzer FD-02).** Add a `detect` bullet to the "Sub-commands:" list (`follow detect [--dry-run] [--series]` — poll aired episodes for active series and enqueue them as wanted items).
- [ ] **F-I — `criteria_json` comment (code-reviewer FD-3).** Add a one-line comment at the `follow_detect` `WantedItem(...)` enqueue noting DESIGN §6's `criteria_json = source_criteria(...) or None` reduces to `None` at D2 (no per-series source-criteria field yet) — so a future reader doesn't think the mapping was dropped.
- [ ] **F-J — architecture.md tree alignment (comment-analyzer cosmetic).** Fix the `cadence.py` tree-entry indentation to match its siblings exactly (one column over).
- [ ] **F-K — cadence purity allowlist test (code-reviewer FD-5 / DESIGN crit 9).** Add `test_cadence_module_imports_are_pure` — AST-parse `personalscraper/acquire/cadence.py`, assert every import's module is in an allowlist of stdlib (`__future__`, `dataclasses`) — i.e. no `store`/`indexer`/`scraper`/`event_bus`/`conf`. Pins the DESIGN §11 criterion-9 purity invariant for cadence.py specifically.
- [ ] **Gate 6.3:** `pytest tests/acquire/test_cadence.py -q` green; `rg -n 'detect' -g '*.py' personalscraper/commands/follow.py` shows the docstring bullet.
- [ ] **Commit:** `docs(follow-detect): fix desired/follow docstrings + criteria_json note + architecture alignment + cadence purity test`

---

## Final gate (main session, phase 6 milestone)

`make check` green + `python -c "import personalscraper"` smoke. `docs/reference/architecture.md` changed → run `python3 scripts/audit_design_coverage.py --strict` + `python3 scripts/update_feature_map.py --check` (both EXIT 0). Then mark phase 6 `[x]`.
