# ACCEPTANCE — airing (RP9)

Every criterion below is an **executable shell command** with a documented
expected output (SH-16 rule). Run from the repo root with the `personalscraper`
package installed (`pip install -e ".[dev]"`).

Re-exercise ALL criteria before squash merge.

---

## ACC-01 — AiredEpisode VO is importable and frozen

**Command:**

```bash
python -c "
from personalscraper.acquire.domain import AiredEpisode
from datetime import date
from personalscraper.core.identity import MediaRef
ep = AiredEpisode(media_ref=MediaRef(tvdb_id=81189), season=1, episode=1, air_date=date(2024,1,1))
try:
    ep.season = 2
    print('FAIL: frozen dataclass allows mutation')
except (AttributeError, TypeError):
    print('OK: AiredEpisode is frozen')
"
```

**Expected:** `OK: AiredEpisode is frozen`

---

## ACC-02 — Predicate tests (past / future / today / empty / malformed)

**Command:**

```bash
pytest tests/acquire/test_airing.py -v -k "parse_date or is_aired" --tb=short
```

**Expected:** `8 passed` (3 `_parse_date` + 5 `_is_aired` tests), `0 failed`

---

## ACC-03 — Golden test (assert WHICH episodes are surfaced)

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_golden -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-04 — Set-poll aggregate (2 series, each AiredEpisode carries its media_ref)

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_set_poll_aggregate -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-05 — Fail-soft (one series raises → others still polled)

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_fail_soft_one_series_raises -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-06 — Empty chain (chain() returns [] → empty result, no crash)

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_empty_chain_no_crash -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-07 — Season selection (season 0 excluded, seasons 1+ polled)

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_season_selection_excludes_season_zero -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-08 — NEGATIVE: no store.wanted.\* call

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_makes_no_store_wanted_calls -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-09 — NEGATIVE: no ownership.owns() call

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_makes_no_ownership_calls -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-10 — NEGATIVE: cadence_json not read

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_poll_aired_does_not_read_cadence_json -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-11 — Layering guard (no store/indexer import in airing.py)

**Command:**

```bash
pytest tests/acquire/test_airing.py::test_airing_module_has_no_store_or_indexer_import -v --tb=short
```

**Expected:** `1 passed`

---

## ACC-12 — No store/indexer import (rg cross-check)

**Command:**

```bash
rg "^from.*(indexer|acquire\.store|acquire\._ports)|^import.*(indexer|acquire\.store)" --type py personalscraper/acquire/airing.py
```

**Expected:** no output (exit code 1 = no match = correct)

---

## ACC-13 — Full test suite green

**Command:**

```bash
make check
```

**Expected:** `make check` exits 0 — `make lint` (ruff + mypy) + `make test` (all tests pass, 0 failed) + module-size guard green.

---

## ACC-14 — poll_aired signature matches DESIGN §3

**Command:**

```bash
python -c "
import inspect
from personalscraper.acquire.airing import poll_aired
sig = inspect.signature(poll_aired)
params = list(sig.parameters.keys())
assert params == ['series', 'registry', 'today'], f'Wrong params: {params}'
assert sig.parameters['today'].kind.name == 'KEYWORD_ONLY', 'today must be keyword-only'
print('OK:', params)
"
```

**Expected:** `OK: ['series', 'registry', 'today']`

---

## ACC-15 — AcquireContext unchanged (no airing field)

**Command:**

```bash
python -c "
from personalscraper.acquire.context import AcquireContext
import dataclasses
fields = [f.name for f in dataclasses.fields(AcquireContext)]
assert 'airing' not in fields, f'Unexpected field: {fields}'
print('OK — AcquireContext has no airing field')
"
```

**Expected:** `OK — AcquireContext has no airing field`
