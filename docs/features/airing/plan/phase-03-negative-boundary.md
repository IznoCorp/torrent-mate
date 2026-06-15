# Phase 3 — Negative-boundary tests + wiring touchpoint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the three NEGATIVE boundary tests (DESIGN §1/§8) that encode the RP9↔D2 boundary, confirm `poll_aired` is a callable free function (no `AcquireContext` change needed), and add an import-layering test asserting `acquire/airing.py` never imports store or indexer.

**Architecture:** Three spy-based tests assert that `poll_aired` makes zero `store.wanted.*` calls, zero `ownership.owns` calls, and does not read `cadence_json`. A `test_airing_layering` test uses `ast.parse` / `importlib` to verify the import graph stays downward-only. No source code changes — only tests.

**Tech Stack:** Python 3.11+, `unittest.mock.MagicMock`, `ast`, `pytest`

---

## Gate

Phase 2 must have produced:

- `personalscraper/acquire/airing.py` — `poll_aired` fully implemented and exported.
- `tests/acquire/test_airing.py` — all service tests passing (golden, set-poll, fail-soft, empty-chain, season-selection).

Verify before starting:

```bash
pytest tests/acquire/test_airing.py -v --tb=short 2>&1 | tail -5
python -c "from personalscraper.acquire.airing import poll_aired; print('OK')"
```

---

## Sub-phase 3.1 — Negative-boundary tests (DESIGN §1/§8 — LOAD-BEARING)

**Files:**

- Modify: `tests/acquire/test_airing.py` (append three negative test functions)

### Task 1: Add the three negative tests

- [ ] **Step 1: Append to `tests/acquire/test_airing.py`**

  ```python
  # ---------------------------------------------------------------------------
  # NEGATIVE boundary (DESIGN §1 / §8 — LOAD-BEARING)
  # These tests encode the RP9↔D2 boundary as executable assertions.
  # A future refactor that folds D2 logic into RP9 will fail here.
  # ---------------------------------------------------------------------------


  def test_poll_aired_makes_no_store_wanted_calls() -> None:
      """LOAD-BEARING (DESIGN §1): poll_aired must NEVER call store.wanted.* (D2's job)."""
      from datetime import date
      from unittest.mock import MagicMock

      from personalscraper.acquire.airing import poll_aired

      registry = MagicMock()
      registry.chain.return_value = []  # empty chain → no network calls

      store_spy = MagicMock()
      wanted_spy = MagicMock()
      store_spy.wanted = wanted_spy

      series = [_make_series(81189, "Test Show")]

      # poll_aired does NOT accept a store argument — we are verifying it is never
      # called at all (it has no store parameter by design).
      poll_aired(series, registry, today=date(2024, 6, 15))

      # The store spy was never passed in, so wanted_spy must have zero calls.
      # This confirms poll_aired's signature has no store parameter (DESIGN §2).
      assert wanted_spy.add.call_count == 0, "poll_aired must not call store.wanted.add"
      assert wanted_spy.enqueue.call_count == 0, "poll_aired must not call store.wanted.enqueue"
      assert store_spy.call_count == 0, "poll_aired must not call the store at all"


  def test_poll_aired_makes_no_ownership_calls() -> None:
      """LOAD-BEARING (DESIGN §1): poll_aired must NEVER call ownership.owns() (D2's job)."""
      from datetime import date
      from unittest.mock import MagicMock, patch

      from personalscraper.acquire.airing import poll_aired

      registry = MagicMock()
      registry.chain.return_value = []

      ownership_spy = MagicMock()

      with patch("personalscraper.acquire.airing.ownership", ownership_spy, create=True):
          # Even if an 'ownership' symbol existed in the module namespace, it must
          # never be called. create=True so the patch installs it without import error.
          series = [_make_series(81189, "Test Show")]
          poll_aired(series, registry, today=date(2024, 6, 15))

      assert ownership_spy.owns.call_count == 0, "poll_aired must not call ownership.owns()"


  def test_poll_aired_does_not_read_cadence_json() -> None:
      """LOAD-BEARING (DESIGN §1): poll_aired must NOT access cadence_json on FollowedSeries."""
      from datetime import date
      from unittest.mock import MagicMock, PropertyMock

      from personalscraper.acquire.airing import poll_aired
      from personalscraper.core.identity import MediaRef

      registry = MagicMock()
      registry.chain.return_value = []

      # Build a FollowedSeries mock that records cadence_json access.
      fs = MagicMock()
      fs.title = "Test Show"
      fs.media_ref = MediaRef(tvdb_id=81189)
      cadence_spy = PropertyMock(return_value=None)
      type(fs).cadence_json = cadence_spy

      poll_aired([fs], registry, today=date(2024, 6, 15))

      assert cadence_spy.call_count == 0, (
          f"poll_aired must not read cadence_json (accessed {cadence_spy.call_count} time(s))"
      )
  ```

- [ ] **Step 2: Run only the negative tests to confirm they PASS**

  ```bash
  pytest tests/acquire/test_airing.py -v -k "negative or no_store or no_ownership or cadence"
  ```

  Expected: `3 passed`

---

## Sub-phase 3.2 — Import-layering test

**Files:**

- Modify: `tests/acquire/test_airing.py` (append one layering test)

### Task 2: Add the import-layering assertion

- [ ] **Step 3: Append the layering test to `tests/acquire/test_airing.py`**

  ```python
  # ---------------------------------------------------------------------------
  # Layering guard (DESIGN §7)
  # acquire/airing.py must import downward only:
  #   api/metadata + acquire.domain + core.identity + stdlib datetime
  # Never store, indexer, or any triage package.
  # ---------------------------------------------------------------------------


  def test_airing_module_has_no_store_or_indexer_import() -> None:
      """DESIGN §7: acquire/airing.py must not import store or indexer packages."""
      import ast
      from pathlib import Path

      source = (Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "airing.py").read_text()
      tree = ast.parse(source)

      forbidden_prefixes = (
          "personalscraper.indexer",
          "personalscraper.acquire.store",
          "personalscraper.acquire._ports",
          "personalscraper.scraper",
          "personalscraper.ingest",
          "personalscraper.commands",
          "personalscraper.pipeline",
      )

      for node in ast.walk(tree):
          if isinstance(node, (ast.Import, ast.ImportFrom)):
              module = ""
              if isinstance(node, ast.ImportFrom) and node.module:
                  module = node.module
              elif isinstance(node, ast.Import):
                  for alias in node.names:
                      module = alias.name
              for prefix in forbidden_prefixes:
                  assert not module.startswith(prefix), (
                      f"acquire/airing.py imports forbidden module '{module}' "
                      f"(violates DESIGN §7 layering invariant)"
                  )
  ```

- [ ] **Step 4: Run the layering test**

  ```bash
  pytest tests/acquire/test_airing.py::test_airing_module_has_no_store_or_indexer_import -v
  ```

  Expected: `1 passed`

---

## Sub-phase 3.3 — Wiring touchpoint confirmation

**Files:** None (read-only verification — no source changes)

### Task 3: Confirm `poll_aired` is a free function callable by a future D2

- [ ] **Step 5: Verify the public API — `poll_aired` importable with correct signature**

  ```bash
  python -c "
  import inspect
  from personalscraper.acquire.airing import poll_aired
  sig = inspect.signature(poll_aired)
  print('Parameters:', list(sig.parameters.keys()))
  assert 'series' in sig.parameters
  assert 'registry' in sig.parameters
  assert 'today' in sig.parameters
  assert sig.parameters['today'].kind.name == 'KEYWORD_ONLY'
  print('Signature OK — D2 can call poll_aired(series, registry, today=date.today())')
  "
  ```

  Expected output:

  ```
  Parameters: ['series', 'registry', 'today']
  Signature OK — D2 can call poll_aired(series, registry, today=date.today())
  ```

- [ ] **Step 6: Confirm AcquireContext is unchanged — no airing field added**

  ```bash
  python -c "
  from personalscraper.acquire.context import AcquireContext
  import dataclasses
  fields = [f.name for f in dataclasses.fields(AcquireContext)]
  assert 'airing' not in fields, f'AcquireContext must not have an airing field, got: {fields}'
  print('AcquireContext unchanged — OK')
  "
  ```

  Expected: `AcquireContext unchanged — OK`

- [ ] **Step 7: Run all airing tests to confirm full suite passes**

  ```bash
  pytest tests/acquire/test_airing.py -v
  ```

  Expected: all tests pass (predicate + service + negative + layering).

- [ ] **Step 8: Commit**

  ```bash
  git add tests/acquire/test_airing.py
  git commit -m "test(airing): negative-boundary tests (no wanted/ownership/cadence) + layering guard"
  ```
