# ACCEPTANCE — follow-detect (Follow D2)

Every criterion below is an **executable shell command** with a documented
expected output (SH-16 rule). Run from the repo root with the `personalscraper`
package installed (`pip install -e ".[dev]"`).

Re-exercise ALL criteria before squash merge.

---

## ACC-01 — Cadence predicate: all tier boundaries + cutoff

**Command:**

```bash
pytest tests/acquire/test_cadence.py -k "is_due or is_past_cutoff" --tb=short
```

**Expected:** `11 passed, 9 deselected`, `0 failed` — all `is_due_by_cadence` /
`is_past_cutoff` tier-boundary and cutoff tests pass.

---

## ACC-02 — `effective_cadence`: series override wins; None → global default

**Command:**

```bash
pytest tests/acquire/test_cadence.py -k "effective_cadence" --tb=short
```

**Expected:** `2 passed, 18 deselected`, `0 failed`.

---

## ACC-03 — Config: `CadenceConfig` default reproduces Hot/Warm/Cold/30d; validators reject bad tiers/cutoff; unit conversion

**Command:**

```bash
pytest tests/acquire/test_cadence.py -k "config" --tb=short
```

**Expected:** `5 passed, 15 deselected`, `0 failed`. The broad `-k config`
selector matches the 5 config-related tests:
`test_cadence_config_default_reproduces_hot_warm_cold`,
`test_acquire_config_has_cadence_field`,
`test_cadence_config_rejects_non_monotonic_tiers`,
`test_cadence_config_rejects_cutoff_below_last_tier`,
`test_cadence_from_config_converts_units` (the two `rejects_*` validator tests
are matched as well, so the count is 5 — not 2).

---

## ACC-04 — `store.wanted.find`: returns row for known key, None otherwise; round-trips through `add`

**Command:**

```bash
pytest tests/acquire/test_store_wanted_find.py --tb=short
```

**Expected:** `5 passed`, `0 failed`.

---

## ACC-05 — DETECT golden: correct which episodes enqueued vs skipped-owned vs skipped-dup; `WantedEnqueued` emitted once per enqueue with correct fields

**Command:**

```bash
pytest tests/commands/test_follow_detect.py -k "golden or skips_owned or skips_duplicate" --tb=short
```

**Expected:** `3 passed, 5 deselected`, `0 failed`.

---

## ACC-06 — DETECT `--dry-run`: zero `store.wanted.add` calls, zero emits

**Command:**

```bash
pytest tests/commands/test_follow_detect.py::test_detect_dry_run_no_writes_no_emits --tb=short
```

**Expected:** `1 passed`, `0 failed`.

---

## ACC-07 — Cadence-aware `run()`: not-due → skipped (no claim, attempts unchanged); due → claim called; past-cutoff → abandoned + `WantedAbandoned(reason='cutoff_reached')` emitted before any grab

**Command:**

```bash
pytest tests/acquire/test_service_cadence.py --tb=short
```

**Expected:** `4 passed`, `0 failed`.

---

## ACC-08 — Boundary preserved: DETECT makes zero grab calls; `poll_aired` (RP9) tests still pass

**Command:**

```bash
pytest tests/commands/test_follow_detect.py::test_detect_boundary_no_grab_calls tests/acquire/test_airing.py --tb=short
```

**Expected:** `25 passed`, `0 failed` (the DETECT boundary test plus the full
`tests/acquire/test_airing.py` RP9 suite).

---

## ACC-09 — Layering guard: `acquire/cadence.py` imports no `indexer`/`store`/`scraper`/event-bus; `commands/follow.py` imports no `indexer`/`pipeline`

**Command:**

```bash
rg "^from .*(indexer|acquire\.store|acquire\._ports|scraper|event_bus)|^import .*(indexer|acquire\.store|scraper)" --type py personalscraper/acquire/cadence.py
pytest tests/commands/test_follow_detect.py::test_detect_layering_no_indexer_import --tb=short
```

**Expected:** First command produces **no output** (exit code 1 = no match =
correct). The patterns are anchored with a literal space after `from`/`import`
(`^from ` / `^import `) so they match real import statements only and do NOT
false-match the `cadence.py` module docstring prose, which lists the forbidden
module names (`scraper`, `indexer`, `store`) as words. Second command: `1 passed`.

---

## ACC-10 — `make check` green; `python -c "import personalscraper"` smoke; design-gaps + feature-map scripts exit 0

**Command:**

```bash
make check
python -c "import personalscraper; print('OK')"
python3 scripts/audit_design_coverage.py --strict
python3 scripts/update_feature_map.py --check
```

**Expected:** All four commands exit 0. `make check` summary shows 0 failed /
0 errors. `python -c` prints `OK`. `audit_design_coverage.py --strict` prints
`audit: 0 finding(s), 0 error(s).` and exits 0. `update_feature_map.py --check`
exits 0 with no output.
