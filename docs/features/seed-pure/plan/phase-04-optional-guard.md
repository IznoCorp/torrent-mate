# Phase 4 — Opt-in sort-side guard (real exclusion)

> **Re-scoped during implementation (operator-approved):** the original plan's guard _counted_ seed-pure items but
> still passed them to the sorter (vacuous — they still land in the library). This phase implements a **genuine
> exclusion on the sort side only** (where name-matching is reliable). The **clean-side guard is dropped** (post-sort
> items are renamed → unreliable matching); a `process_clean.verify_seed_pure` flag is added for config symmetry but
> is **reserved / not enforced**. The always-on **ingest skip (phase 3) is the real guardrail**.

**Goal:** Add `verify_seed_pure` flags to new `SortConfig` + `ProcessCleanConfig` models (default `False`); give
`Sorter.process` a `skip_names` parameter that genuinely excludes matching items (→ `skipped` `SortResult`); have
`run_sort` build the seed-pure name set from the torrent client and thread it; wire `SortStep`. Tests (criterion 7)
prove **real exclusion** (not a vacuous count).

**Tech Stack:** Python 3.11+, `pydantic`, `pytest`, `unittest.mock`

---

## Gate

Phase 3 produced the always-on ingest skip; `pytest tests/ingest/test_ingest_seed_pure.py` passes.

---

## Sub-phase 4.1 — Config models (`SortConfig`, `ProcessCleanConfig`)

**Files:** `personalscraper/conf/models/scraper.py`, `personalscraper/conf/models/config.py`.

- [ ] **Add `SortConfig` + `ProcessCleanConfig` to `conf/models/scraper.py`** (both extend `_StrictModel`, mirror the
      `IngestConfig` style). `SortConfig.verify_seed_pure: bool = Field(default=False, ...)` — **enforced** (sort guard).
      `ProcessCleanConfig.verify_seed_pure: bool = Field(default=False, ...)` — docstring MUST state **"reserved — not
      yet enforced; the clean-side guard is intentionally not implemented (post-sort name-matching is unreliable).
      The active guardrails are the always-on ingest skip + the opt-in sort guard."** Update `scraper.py` `__all__`
      (alphabetical) to add `ProcessCleanConfig`, `SortConfig`.
- [ ] **Wire onto `Config` (`conf/models/config.py`)**: extend the `scraper` import; add fields after `ingest`
      (~line 87): `sort: SortConfig = Field(default_factory=SortConfig)` and
      `process_clean: ProcessCleanConfig = Field(default_factory=ProcessCleanConfig)`; document both in the `Config`
      docstring Attributes (note `process_clean.verify_seed_pure` is reserved).
- [ ] **Smoke:** `python -c "from personalscraper.conf.models.scraper import SortConfig, ProcessCleanConfig; assert SortConfig().verify_seed_pure is False and ProcessCleanConfig().verify_seed_pure is False; print('OK')"`.
      Also `python -c "import personalscraper"` (the real config loader must still validate — no required field added).
- [ ] **Gate 4.1:** ruff + `mypy personalscraper/conf/models/scraper.py personalscraper/conf/models/config.py` clean; a
      tiny test in `tests/conf/` (or inline) pinning the two defaults are `False`.
- [ ] **Commit:** `feat(seed-pure): add SortConfig + ProcessCleanConfig verify_seed_pure flags (default off; clean reserved)`

---

## Sub-phase 4.2 — `Sorter.process` skip_names + `run_sort` guard + `SortStep` (real exclusion)

**Files:** `personalscraper/sorter/sorter.py`, `personalscraper/sorter/run.py`, `personalscraper/pipeline_steps.py`,
`tests/sorter/test_sort_seed_pure_guard.py`.

### Task 1 — genuine exclusion in `Sorter.process`

- [ ] **`Sorter.process(source_dir, dest_root=None, *, skip_names: frozenset[str] = frozenset())`.** In the existing
      item loop (`sorter.py` ~line 108, after the `skip_dirs`/hidden-file `continue`), add:
      `python
    if item.name in skip_names:
        log.info("sort.seed_pure_skipped", name=item.name)
        results.append(
            SortResult(
                source=item, destination=item, media_type="", title=item.name,
                year=None, season=None, episode=None, status="skipped", message="seed_pure",
            )
        )
        continue
    `
      This is a **genuine exclusion** — `sort_item` is never called for the item, so it is NOT moved; it is reported as
      a `skipped` `SortResult` (`message="seed_pure"`). Default `skip_names=frozenset()` → byte-identical behavior for
      every existing caller. Update the `process` docstring `Args:` with `skip_names`.

### Task 2 — `run_sort` builds the set + threads it

- [ ] **`run_sort(..., *, event_bus, torrent_client: object | None = None)`** + `from personalscraper.core.tags import SEED_PURE`.
      After the fast-skip and before `sorter.process`, build the set (guarded + fail-soft):
      `python
    skip_names: frozenset[str] = frozenset()
    if getattr(config, "sort", None) is not None and config.sort.verify_seed_pure and torrent_client is not None:
        try:
            completed = torrent_client.get_completed()
            skip_names = frozenset(t.name for t in completed if SEED_PURE in getattr(t, "tags", []) )
            if skip_names:
                log.info("sort.seed_pure_guard_active", skipping=sorted(skip_names))
        except Exception as exc:  # noqa: BLE001 — guard must never abort the sort
            log.warning("sort.seed_pure_guard_failed", error=str(exc))
    results = sorter.process(ingest_dir, dest_root=staging_dir, skip_names=skip_names)
    `
      The **existing result-loop** already maps `r.status == "skipped"` → `report.skip_count += 1` +
      `ItemProgressed(step="sort", status="skipped", details={"reason": r.message or ""})`, so the seed-pure skip flows
      through with `reason="seed_pure"` automatically — no new emit code. Document the `torrent_client` arg.

### Task 3 — `SortStep` wiring

- [ ] **`SortStep.__call__`** passes `torrent_client=ctx.app.torrent_client` **only** when
      `getattr(ctx.app.config, "sort", None) is not None and ctx.app.config.sort.verify_seed_pure`, else `None`.

### Task 4 — NON-VACUOUS tests (`tests/sorter/test_sort_seed_pure_guard.py`)

- [ ] **`test_sort_process_excludes_skip_names` (the load-bearing real-exclusion test — uses the REAL Sorter):**
      create a real `tmp_path` ingest dir with TWO real items (`Seed.Movie.2024/` and `Keep.Show.2024/`); a real
      `Sorter(config=<real-ish config with staging_dirs>, ...)`; call `sorter.process(tmp_path, dest_root=tmp_path2,
    skip_names=frozenset({"Seed.Movie.2024"}))`. Assert: the `Seed.Movie.2024` result has `status=="skipped"` &
      `message=="seed_pure"`; the `Keep.Show.2024` item was processed (its result is present and NOT the seed-pure
      skip). **Mutation-proof:** this fails if `skip_names` is ignored (the seed item would be sort_item'd, not a
      seed_pure skip). (Stub `sort_item` if needed to avoid real moves, but assert it was NOT called for the skipped
      name and WAS called for the kept name — that proves genuine exclusion.)
- [ ] **`test_run_sort_guard_off_no_client_query`:** flag off → `run_sort(..., torrent_client=mock_client)` never calls
      `mock_client.get_completed` and calls `sorter.process` with `skip_names=frozenset()` (mock Sorter; assert the
      kwarg).
- [ ] **`test_run_sort_guard_on_threads_skip_names`:** flag on + `mock_client.get_completed` returns a seed-pure
      `TorrentItem` named `Seed.Movie.2024` → `run_sort` calls `get_completed` once AND calls `sorter.process` with
      `skip_names` containing `"Seed.Movie.2024"` (assert the kwarg). Mutation-proof: fails if run_sort doesn't thread
      the set.
- [ ] **`test_run_sort_guard_on_no_client_inert`:** flag on but `torrent_client=None` → no crash, `skip_names` empty,
      `error_count == 0`.
- [ ] **Gate 4.2:** ruff + `mypy` on sorter.py/run.py/pipeline_steps.py; `pytest tests/sorter/ -q` (new + no
      regression); residual `rg '"seed-pure"' --type py personalscraper/sorter/` returns nothing (constant only).
- [ ] **Commit:** `feat(seed-pure): real sort-side seed-pure exclusion via Sorter.process skip_names + run_sort guard + SortStep + tests`

---

## Phase 4 Gate

- [ ] `make check` exit 0; `python -c "import personalscraper"` smoke.
- [ ] Config smoke: both flags default `False`.
- [ ] Residual: `rg '"seed-pure"' --type py personalscraper/sorter/ personalscraper/conf/` returns nothing (constant only).
- [ ] (No clean-side code — `process/run.py` is intentionally untouched; the `process_clean.verify_seed_pure` flag is reserved.)
