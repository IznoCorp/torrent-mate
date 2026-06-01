# God-Modules & Module-Size Debt Audit

> STATUS: PARTIALLY ADDRESSED. library/scanner.py removed by lib-fold (0.19.0); the remaining god-module is scraper/movie_service.py (~975 non-blank LOC, sole file over the 800 WARN ceiling). Point-in-time audit; see current code.

> **Metadata** — Date: 2026-05-28 · Version: 0.16.0 · Branch: `feat/registry` ·
> Project status: pre-1.0, single mono-user instance, **not in production** (no back-compat / no migration scripts) ·
> Report scope: module-size guardrail (`scripts/check-module-size.py`), the "god-module" inventory in `ROADMAP.md` P3, and concrete decomposition seams for the real offenders ·
> Confidence: **High** (fact-check overall_confidence = high; every LOC count and seam line-reference reproduced against the working tree on this branch).

---

## 1. Executive summary (TL;DR)

- **The crisis described by the brief and `ROADMAP.md` P3 no longer exists.** Ground truth from `python3 scripts/check-module-size.py` (exit code **0**, `make check` module-size step is **GREEN**): exactly **two** files exceed the 800 non-blank soft-warn ceiling and **zero** files breach the 1000 hard-block ceiling.
- The two WARN files are `personalscraper/scraper/movie_service.py` (**927** non-blank) and `personalscraper/library/scanner.py` (**855** non-blank). Both are advisory-only and do **not** block the gate. There is **no allowlist, no grandfathering, no pragma escape** in the checker — these pass because they are genuinely under 1000.
- `ROADMAP.md:180-214` is **materially stale**: it claims `indexer/scanner/__init__.py`=1056 (actual 621), `trailers/state.py`=950 (actual 767), `trailers/cli.py`=752 (actual 698), `indexer/db.py`=604 (actual 588), and lists `scraper/tmdb_client.py`=770 — **a file that no longer exists** (split into `api/metadata/tmdb.py` + `api/metadata/_tmdb_parsers.py`). The decomposition P3 prescribes has **already largely landed**.
- The **real blind spot** is the checker's blanket `__init__.py` exclusion (`check-module-size.py:22,37`). Two facade modules carry heavy logic invisible to the guardrail: `api/metadata/registry/__init__.py` (**689** non-blank — the largest module in the package by this metric, holding `ProviderRegistry`/`Mode`/`ProviderMatch`) and `indexer/scanner/__init__.py` (**621** non-blank, holding `scan()`/`filter_disks()`/`_finalize_disk_after_walk()`).
- **Verdict:** This is **debt-monitoring**, not an emergency. The single highest-value action is **documentation hygiene** (re-baseline `ROADMAP.md` P3). The two WARN files have clean extraction seams worth doing. The `__init__.py` policy is a real decision the owner must make. Everything else stays as monitored debt.

---

## 2. Current state (evidence-backed)

### 2.1 The guardrail mechanics (`scripts/check-module-size.py`)

- Metric: **non-blank lines**, `check-module-size.py:30` → `sum(1 for line in fh if line.strip())`.
- Thresholds: `WARN_LOC = 800`, `BLOCK_LOC = 1000` (`check-module-size.py:19-20`).
- Exclusions: `EXCLUDED_FILENAMES = {"__init__.py"}` and `EXCLUDED_DIR_PARTS = {"tests", "migrations"}` (`check-module-size.py:22-23`), applied in `_is_excluded` (`check-module-size.py:35-39`).
- Exit code: **1 only** when a REPORT-level (≥1000) finding exists; WARN-only is exit **0** (`check-module-size.py:58-74`). REPORT lines go to stdout, WARN lines to stderr (line 69).
- **No allowlist, no grandfathering, no per-file pragma** anywhere in the file.

### 2.2 Tool output today (verbatim, branch `feat/registry`)

```
  [WARN] personalscraper/library/scanner.py: 855 non-blank lines
  [WARN] personalscraper/scraper/movie_service.py: 927 non-blank lines
check-module-size: 2 finding(s) (root=personalscraper)
```

Exit code: **0**. Companion `make check` guardrails verified PASS: `check-no-broad-registry-catch`, `check-typed-api`, `check-pragma-discipline`.

### 2.3 The full `make check` chain (Makefile:62-68)

The investigation under-enumerated this. The complete `check` target is:

```makefile
check: lint test-cov
	python3 scripts/check-module-size.py
	python3 scripts/check-no-broad-registry-catch.py
	python3 scripts/check-typed-api.py
	python3 scripts/check-pragma-discipline.py
	python3 scripts/audit-cli-coverage.py
	$(MAKE) cli-coverage-check          # -> python3 scripts/cli-coverage-report.py --check
```

None of the CLI-coverage steps affect god-module conclusions, but any plan touching CLI-bearing modules (e.g. relocating `trailers/cli.py`) must keep `audit-cli-coverage.py` and `cli-coverage-report.py --check` green.

### 2.4 Real offenders by the checker metric (non-blank LOC, verified)

| Module                                   | Non-blank | Vs ceiling    | Status               |
| ---------------------------------------- | --------- | ------------- | -------------------- |
| `scraper/movie_service.py`               | 927       | > 800 WARN    | **flagged**          |
| `library/scanner.py`                     | 855       | > 800 WARN    | **flagged**          |
| `scraper/tv_service.py`                  | 797       | 3 below WARN  | monitor (razor-thin) |
| `trailers/state.py`                      | 767       | 33 below WARN | monitor              |
| `trailers/orchestrator.py`               | 734       | below WARN    | monitor              |
| `indexer/scanner/_modes/backfill_ids.py` | 728       | below WARN    | monitor              |
| `scraper/nfo_generator.py`               | 723       | below WARN    | monitor              |
| `trailers/cli.py`                        | 698       | below WARN    | monitor              |
| `scraper/existing_validator.py`          | 642       | below WARN    | monitor              |
| `indexer/db.py`                          | 588       | below WARN    | OK                   |

### 2.5 The `__init__.py` blind spot (excluded, therefore invisible)

| Excluded module                     | Non-blank | Logic it holds (verified line anchors)                               |
| ----------------------------------- | --------- | -------------------------------------------------------------------- |
| `api/metadata/registry/__init__.py` | **689**   | `Mode` (line 134), `ProviderMatch` (164), `ProviderRegistry` (316)   |
| `indexer/scanner/__init__.py`       | **621**   | `_finalize_disk_after_walk` (98), `filter_disks` (308), `scan` (338) |

`registry/__init__.py` at 689 is the **single largest module** in the package by the checker metric, yet it never appears in any report.

### 2.6 Consumer counts (verified — corrects the investigation)

`rg -t py -l` over `personalscraper/` + `tests/`:

| Module            | Consumers | Note                                  |
| ----------------- | --------- | ------------------------------------- |
| `indexer.scanner` | **59**    | confirmed                             |
| `tv_service`      | **27**    | (investigation said 29)               |
| `trailers.state`  | **22**    | **corrected** (investigation said 25) |
| `movie_service`   | **16**    | (investigation said 18)               |
| `library.scanner` | **11**    | **corrected** (investigation said 18) |

### 2.7 `feature_map` contracts do not pin module paths

`tests/feature_map/scraper.json` leaf values are pytest node-ids / doc paths (e.g. `scraper`, `docs/reference/scraping.md`), never `personalscraper/...` module paths. `rg -g '*.json' 'movie_service|tv_service|library/scanner' tests/feature_map/` returns **nothing**. Behaviour-preserving splits that keep test names stable will **not** trip `update_feature_map.py --check`. The pre-commit hook only regenerates feature*map when a `test_design*\*.py` is staged.

### 2.8 Namespace is free for proposed module names

`ls` confirmed none of these exist: `scraper/_movie_restore.py`, `library/_scanner_upsert.py`, `api/metadata/registry/_registry.py`. **Caveat:** `indexer/scanner/_scan_orchestrator.py` **already exists** — do **not** name a new scanner module `_orchestrator.py` (the ROADMAP's own P3 suggestion would collide). Existing privates: `scraper/{_drift_persistence,_shared,_tvdb_convert,_xref}.py`; `indexer/scanner/{_checkpoint,_concurrency,_db_writes,_exclusions,_index_ddl,_scan_orchestrator,_shutdown,_spotlight,_types,_walker}.py`; `api/metadata/registry/{_errors,_events,_factory,_semantics,_validation}.py`.

---

## 3. Problems & risks (prioritised)

| #   | Severity | Problem                                                                                                                                                                                                     | Evidence                                                                                                                                                                                                                          |
| --- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | **High** | `ROADMAP.md:180-214` god-module table is stale; numbers are 1.3-1.7× current reality and reference a deleted file (`tmdb_client.py`, ROADMAP line 207). A future agent reading it would chase phantom work. | `ROADMAP.md:186` (1056 vs 621), `:187` (950 vs 767), `:188` (752 vs 698), `:189` (604 vs 588), `:207` (`tmdb_client.py` 770 — absent).                                                                                            |
| P2  | **High** | `__init__.py` blanket exclusion lets `registry/__init__.py` (689) and `indexer/scanner/__init__.py` (621) accrete unbounded, defeating cognitive-load control for facade modules.                           | `check-module-size.py:22,37`; logic anchors §2.5.                                                                                                                                                                                 |
| P3  | Medium   | `movie_service.py` (927) mixes two cohesive concerns: DB-restore (8 `RestoreOutcome` dataclasses + `_restore_from_db`) and scrape (`MovieServiceMixin`).                                                    | `movie_service.py:168-227` (dataclasses), `:227` (`_restore_from_db`), `:422` (`MovieServiceMixin`).                                                                                                                              |
| P4  | Medium   | `library/scanner.py` (855) is a flat module mixing NFO-parse, DB-upsert, and disk-scan concerns.                                                                                                            | `scanner.py:562` (`_nfo_status_string`), `:579` (`_artwork_inventory`), `:600` (`_upsert_media_item`), `:726` (`_upsert_seasons_and_episodes`), `:826` (`_build_disk_row`), `:851` (`_ensure_disk_row`), `:902` (`scan_library`). |
| P5  | Low      | `tv_service.py` (797) sits **3 non-blank lines** below the WARN ceiling — a single trivial edit flips it red.                                                                                               | §2.4.                                                                                                                                                                                                                             |
| P6  | Low      | `ROADMAP.md` "move `trailers/cli.py` to `commands/trailers/`" is a consistency argument, not a size one — cli is 698 (below WARN) with only 4 `@app.command`.                                               | ROADMAP line ~190 + §2.4.                                                                                                                                                                                                         |

**Cross-cutting risk:** splits touch heavily-imported modules. Public import paths **must** be preserved via re-exports, else a wave of test-import updates is needed. The breakage surface is **`tests/`**, not `feature_map` JSONs — tests import private symbols directly (e.g. `tests/library/test_scanner.py:1190` imports `_ensure_disk_row`; `tests/integration/test_bdd_restore.py` references the restore symbols). Mandatory phase-gate residual-import grep on every moved symbol.

---

## 4. Implementation plan

> **Codename:** `module-trim` · **SemVer bump:** **Z+1** (0.16.0 → 0.16.1; behaviour-preserving structural + docs, no public-API change) · **Branch:** `fix/module-trim` (structural debt remediation, no feature). Conventional Commits scoped `(module-trim)`. Phase gates require `make lint` + `make test` + `make check` all green and a residual-import grep per moved symbol. **No migration scripts** (pre-1.0). **No new abstractions** (ROADMAP P3 non-goal — preserve it). **Regression-test-per-bug:** these are behaviour-preserving moves, so no new reproduction tests are required, but full `make test` re-run is mandatory after each phase.

### Phase 1 — Re-baseline `ROADMAP.md` P3 (docs only)

- **Objective:** stop future agents chasing phantom debt; record verified reality.
- **Modify:** `ROADMAP.md:180-214`.
- **Sub-tasks (agent-executable):**
  1. Replace the P3 table LOC column with verified non-blank counts: `indexer/scanner/__init__.py` 621, `trailers/state.py` 767, `trailers/cli.py` 698, `indexer/db.py` 588.
  2. Mark the `_modes/`/`_walker.py`/`_scan_orchestrator.py` scanner split, the `indexer/db.py` `_migrations`/`_disk_guard` extraction, and the `tmdb_client.py` → `api/metadata/tmdb.py` + `api/metadata/_tmdb_parsers.py` split as **DONE** (they have landed).
  3. Delete the `scraper/tmdb_client.py` row from the "Also monitor" table (file no longer exists); replace with verified successors and current counts: `existing_validator.py` 642, `tv_service.py` 797, `nfo_generator.py` 723.
  4. Add a **monitored-debt** subsection listing `movie_service.py` 927, `library/scanner.py` 855, `tv_service.py` 797 (flag the 3-line margin), `trailers/state.py` 767, plus the two excluded facades `registry/__init__.py` 689 and `indexer/scanner/__init__.py` 621 with the explicit note "invisible to `check-module-size.py` (`__init__.py` exclusion)".
  5. Replace the P3 `_orchestrator.py` goal text — that name **collides** with the existing `indexer/scanner/_scan_orchestrator.py`; if a future split happens, name the new module distinctly (e.g. `_scan_facade.py`).
- **Commit:** `docs(module-trim): re-baseline ROADMAP P3 god-module inventory`. Use `git add -f ROADMAP.md` only if blocked by the global `docs/` gitignore rule (ROADMAP.md is at repo root; verify it is tracked first).
- **Effort:** S · **Risk:** low · **Dependencies:** none (do first).

### Phase 2 — Split `movie_service.py` (927 → ~722): extract DB-restore concern

- **Objective:** clear the WARN by moving a self-contained block; no logic change.
- **Create:** `personalscraper/scraper/_movie_restore.py`.
- **Modify:** `personalscraper/scraper/movie_service.py`; any test importing the moved private symbols.
- **What moves** (`movie_service.py:167-421`, **205 non-blank lines** measured): the base `RestoreOutcome` (167) + `Restored`/`NoDb`/`NoMatch`/`NoDispatchPath`/`NoNfoAtDispatch`/`AmbiguousNfo`/`CopyFailed` (175-220) + `_restore_from_db` (227). After extraction, movie_service drops to **~722 non-blank** (927 − 205, plus a re-import line), clearing the 800 WARN with ~78 lines of margin.
- **Preserve:** the `MovieServiceMixin` public path (`scraper.movie_service.MovieServiceMixin`, 16 consumers). Re-export the restore symbols from `movie_service` (`from personalscraper.scraper._movie_restore import RestoreOutcome, Restored, NoDb, NoMatch, NoDispatchPath, NoNfoAtDispatch, AmbiguousNfo, CopyFailed, _restore_from_db`) so existing imports keep working.
- **Move helper deps too:** check whether `_media_details_to_movie_data` (40), `_coerce_to_movie_data` (119) etc. are used by `_restore_from_db`; if so, leave them in `movie_service.py` and import into `_movie_restore.py`, or move them — decide by following the call graph (no duplication).
- **Tests to update:** `tests/integration/test_bdd_restore.py` references the restore symbols. If it imports from `personalscraper.scraper.movie_service`, the re-export keeps it green; verify and, if it imports the new private module path, update.
- **Effort:** M · **Risk:** low · **Dependencies:** after Phase 1.

### Phase 3 — Split `library/scanner.py` (855 → ~600): extract DB-upsert helpers

- **Objective:** clear the WARN; isolate the persistence concern.
- **Create:** `personalscraper/library/_scanner_upsert.py`.
- **Modify:** `personalscraper/library/scanner.py`; tests importing the moved privates.
- **What moves** (`scanner.py:562-901`, ~290 lines): `_nfo_status_string` (562), `_artwork_inventory` (579), `_upsert_media_item` (600), `_upsert_seasons_and_episodes` (726), `_read_episode_titles` (773, if only used by upsert), `_build_disk_row` (826), `_ensure_disk_row` (851). Target ~600 non-blank.
- **Preserve public surface** (importable from `library.scanner`, 11 consumers): `parse_title_year`, `extract_nfo_ids`, `extract_nfo_metadata`, `scan_movie_dir`, `scan_tvshow_dir`, `scan_library`. Re-export the moved privates from `scanner` since tests import them directly — e.g. `tests/library/test_scanner.py:1190,1224,1244` do `from personalscraper.library.scanner import _ensure_disk_row`.
- **Tests to update:** `tests/library/test_scanner.py`, `tests/indexer/test_upsert_media_item_dedup.py` import `_upsert_media_item`/`_ensure_disk_row` from `library.scanner`. Re-export keeps them green; verify with grep.
- **Effort:** M · **Risk:** low · **Dependencies:** independent of Phase 2 (can share the same phase commit set).

### Phase 4 — Decide & enforce the `__init__.py` policy (owner decision required)

- **Objective:** close the blind spot for `registry/__init__.py` (689) and `indexer/scanner/__init__.py` (621).
- **Option A (refactor facades to shims — preferred):**
  - `api/metadata/registry/__init__.py` → move `Mode`/`ProviderMatch`/`ProviderRegistry` (134-316) into `api/metadata/registry/_registry.py`; `__init__.py` becomes a re-export shim. Preserves the public import surface (the registry package is the capability-keyed dispatch core).
  - `indexer/scanner/__init__.py` → move `scan`/`filter_disks`/`_finalize_disk_after_walk` (98-338) into `indexer/scanner/_scan_facade.py` (**not** `_orchestrator.py` — collides with existing `_scan_orchestrator.py`); `__init__.py` re-exports. Preserves `indexer.scanner` (**59 importers**).
- **Option B (tighten the checker):** change `check-module-size.py:22,37` to apply the threshold to `__init__.py` above some floor (e.g. 400 non-blank) instead of blanket-excluding. **Sequencing hazard:** flipping the rule first turns `make check` RED immediately (both facades WARN; if either had a path ≥1000 it would block). The refactors (Option A) **must land first or in the same phase**.
- **Recommendation:** do Option A for `indexer/scanner` (matches the existing `_modes/`/`_walker.py` pattern), and at minimum document `registry/__init__.py` in ROADMAP. Treat Option B as a follow-on once the two facades are shims.
- **Effort:** L · **Risk:** medium · **Dependencies:** after Phase 1; if Option B, refactor must precede the rule flip.

### Phase 5 — Monitored-debt list (no code)

- `tv_service.py` (797 — **3 lines from WARN**), `trailers/state.py` (767), `trailers/cli.py` (698), `nfo_generator.py` (723), `trailers/orchestrator.py` (734) stay as monitored debt in ROADMAP. **Trigger rule:** split only when a feature touches them and pushes them past 800, folding the split into that feature's phase. This avoids churn-for-churn and keeps the 22/27/59 consumer import paths stable. (This is part of the Phase 1 doc edit.)

---

## 5. Acceptance criteria (SH-16 — executable, with expected output)

Run from repo root on `fix/module-trim`.

**Phase 1 (re-baseline):**

```bash
rg -c '1056|950|752|604|tmdb_client' ROADMAP.md || echo 0
# expected: 0   (no stale LOC figures and no reference to the deleted tmdb_client.py remain)
```

> **CRITICAL — capture stderr.** WARN findings print to **stderr** (`check-module-size.py:69`: `dest = sys.stderr if level == "WARN" else sys.stdout`). A criterion that pipes only stdout is **tautological**: `python3 scripts/check-module-size.py | grep -c movie_service` returns `0` **today** while `movie_service` is still a 927-LOC WARN, so it would "pass" before and after the split, proving nothing. Every module-grep criterion below uses `2>&1`.

**Phase 2 (movie_service split):**

```bash
python3 scripts/check-module-size.py 2>&1 | grep -c movie_service
# expected: 0   (NOTE: 2>&1 is mandatory — WARN goes to stderr; without it this returns 0 even pre-split)
test -f personalscraper/scraper/_movie_restore.py && echo PRESENT
# expected: PRESENT
python3 -c "from personalscraper.scraper.movie_service import RestoreOutcome, _restore_from_db; print('ok')"
# expected: ok
awk 'NF{c++} END{print (c < 800) ? "PASS" : "FAIL ("c")"}' personalscraper/scraper/movie_service.py
# expected: PASS
```

**Phase 3 (scanner split):**

```bash
python3 scripts/check-module-size.py 2>&1 | grep -c 'library/scanner.py'
# expected: 0   (2>&1 mandatory — same stderr caveat as Phase 2)
test -f personalscraper/library/_scanner_upsert.py && echo PRESENT
# expected: PRESENT
python3 -c "from personalscraper.library.scanner import scan_library, _ensure_disk_row, _upsert_media_item; print('ok')"
# expected: ok
awk 'NF{c++} END{print (c < 800) ? "PASS" : "FAIL ("c")"}' personalscraper/library/scanner.py
# expected: PASS
```

**Phase 4 (facade policy — if Option A executed):**

```bash
python3 -c "from personalscraper.api.metadata.registry import ProviderRegistry, Mode, ProviderMatch; print('ok')"
# expected: ok
python3 -c "from personalscraper.indexer.scanner import scan, filter_disks; print('ok')"
# expected: ok
test -f personalscraper/indexer/scanner/_scan_facade.py && echo PRESENT
# expected: PRESENT
```

**Whole-feature gate (every phase):**

```bash
python3 scripts/check-module-size.py; echo "EXIT:$?"
# expected: "check-module-size: clean (root=personalscraper)" then EXIT:0
#           (after Phases 2+3; before them, EXIT:0 with the 2 WARNs is acceptable)
make lint && make test && make check && echo GATE_GREEN
# expected: ... GATE_GREEN
python -c "import personalscraper" && echo IMPORT_OK
# expected: IMPORT_OK
```

> **Coverage caveat (do not skip).** `make check` runs `test-cov` with `--cov-fail-under=$(THRESHOLD)` (`Makefile:49`, branch coverage ≥90%). Extracting code to a new module re-attributes branch coverage; a moved private helper can fall below threshold in its new file. After each extraction, run `make test-cov` and confirm the reported `NN%` line stays ≥90. If it drops, add the missing branch test in the new module **before** the phase gate (regression-test discipline applies to the extracted branches even though no bug was fixed).

**Residual-import safety (run per moved symbol, e.g.):**

```bash
rg -t py 'from personalscraper.scraper._movie_restore import' personalscraper/ | wc -l
# expected: >= 1  (movie_service re-exports; consumers untouched)
rg -t py '_restore_from_db|_upsert_media_item|_ensure_disk_row' tests/ -l | wc -l
# expected: matches the pre-split count (no test left importing a now-broken path)
```

---

## 6. Trade-offs & alternatives

- **Do-nothing on the WARN files.** Defensible — they don't block the gate. Rejected for Phases 2-3 only because both have a clean, zero-risk seam and clearing the WARN reduces cognitive load with minimal churn. If owner prefers zero churn, Phase 1 (docs) alone is a complete and valid deliverable.
- **Split by line-budget vs by concern.** Splitting purely to hit a number invites artificial seams. Both proposed splits follow **concern boundaries** (restore-vs-scrape; upsert-vs-parse-vs-scan) that happen to clear the threshold — concern-driven, not number-driven.
- **Option B (tighten checker) before Option A (refactor).** Rejected: flipping the rule first makes `make check` red and blocks all other work. Refactor-then-rule is the only safe order.
- **Switch the metric to cyclomatic complexity / function count.** Tempting, since non-blank LOC is a crude proxy that let two 600-689-line facades hide. But this cycle the proxy missed nothing actionable except via the `__init__.py` exclusion — which is an exclusion bug, not a metric bug. Fix the exclusion (Phase 4) before re-litigating the metric. Logged as an open question.
- **Naming `_orchestrator.py` for the scanner facade** (as ROADMAP P3 literally says): rejected — collides with existing `indexer/scanner/_scan_orchestrator.py`. Use `_scan_facade.py`.

---

## 7. Effort & sequencing

- **Quick win (do first):** Phase 1 — S, low-risk docs edit. Stops phantom-work risk immediately; no SemVer concern if done as a standalone `docs:` commit, or fold into the `fix/module-trim` branch.
- **Heavy-ish but low-risk:** Phases 2 + 3 — M each, can share one phase/commit set. Both are behaviour-preserving extractions guarded by re-exports + residual-import grep. Together they take the package to **zero WARN**.
- **Heaviest / needs a decision:** Phase 4 — L, medium-risk, gated on owner choice (A/B). Defer until Phases 1-3 are merged.
- **Recommended order:** 1 → (2 ∥ 3) → 5 (folded into 1) → 4. Phases 2 and 3 are independent and parallelisable.
- **Total:** if the owner stops after Phase 3, the deliverable is a green, WARN-free `make check` plus accurate roadmap — a complete and defensible outcome. Phase 4 is optional hardening.

---

## 8. Open questions (owner decisions)

1. **Is the `__init__.py` exclusion deliberate** (a facade allowance) **or an oversight?** It currently lets `registry/__init__.py` (689) and `indexer/scanner/__init__.py` (621) grow unbounded and invisible. Phase 4 cannot start without this answer.
2. **Is the DESIGN target of ≤700 LOC still active**, or superseded by the 800/1000 guardrail? `tv_service.py` (797) and `trailers/state.py` (767) sit between the two targets — they are "debt" under the old target but "fine" under the current rule.
3. **Should the size metric move from non-blank LOC to a cognitive metric** (cyclomatic complexity / function count)? Not urgent — the only thing the LOC proxy missed this cycle was hidden via the `__init__.py` exclusion (question 1), so fix that first.
4. **Do Phases 2-3 ship as one `fix/module-trim` feature, or should Phase 1 be a separate `docs:` commit on `main`?** Affects whether the docs re-baseline lands immediately or waits for the structural PR.
