# Phase 6 — PR fixes cycle 1

## Context

Fixes identified during PR #14 review cycle 1. All findings are coherent with DESIGN.md scope. Total retained: 12 (5 major + 3 medium + 4 minor). Ignored: 4 (out of scope).

Design rationale for retaining the majors: DESIGN §1 explicitly lists "tests verify the mocks, not the code" as the core pathology being fixed. Tests that don't assert observable effects (tautological, pre-seeded-state-accepted, or missing count assertions) recreate that exact pathology.

## Sub-phases

### 6.1 — Fix tautological + pre-seeded assertions (majors, 3 tests)

**Findings**:

1. `tests/integration/test_verify.py:108` — `assert results or True` is always truthy; the `or` fallback accepts `[valid]` in report details even if the check never ran.
2. `tests/integration/test_full_pipeline.py:82-195` — no `report.steps["ingest"].success_count >= 1` assertion; a broken ingest that processes 0 torrents passes. Docstring promised "expected counts".
3. `tests/integration/test_dispatch_merge.py:201-204` — `any(folder.lower() in k for k in updated_index)` accepts the pre-seeded index key; a regression where the index is never re-written after merge passes.

**Acceptance**:

- `test_verify.py`: positive-case assertion checks the result object state (not the report string), and the `or True` fallback is removed.
- `test_full_pipeline.py`: at least one `assert report.steps[<name>].success_count == expected_int` per pipeline step is present, with concrete integer expectations matching the 3-torrent seed.
- `test_dispatch_merge.py`: either assert `last_updated` changed OR assert the entry's `path` matches the post-merge on-disk path (not the pre-seeded one).

### 6.2 — Fix under-tested CLI wiring + catalogue #6 gap (majors, 2 areas)

**Findings**: 4. `tests/test_cli.py:138-143, 170-177` — `test_sort_dry_run` / `test_scrape_dry_run` assert only `call_args is not None`, never `kwargs["dry_run"] is True`. The flag-forwarding invariant these tests claim is unverified. 5. DESIGN §4 catalogue #6 explicitly says "`The Matrix (1999)` + `The Matrix (2003)` → not merged" (fuzzy guards). Only the positive merge is tested in `tests/integration/test_process.py`; the negative year-guard is absent.

**Acceptance**:

- Each `*_dry_run` wiring test asserts `kwargs.get("dry_run") is True`.
- `test_process.py` gains `test_dedup_preserves_distinct_years` covering the Matrix-year-guard case; after dedup, both `The Matrix (1999)/` and `The Matrix (2003)/` still exist.

### 6.3 — Logging + warnings hygiene on new production seams (mediums, 3 fixes)

**Findings**: 6. `personalscraper/ingest/ingest.py:249-251` — ratio guard: `getattr(torrent, "ratio", 0.0)` silently defaults to 0.0 when the attr is missing, and `log.debug` is invisible at default log level. Users with `min_ratio > 0.0` get silent skips. 7. `personalscraper/enforce/structure_validator.py:184` — files without `SxxEyy` pattern are silently `continue`'d with no log event. 8. `personalscraper/enforce/structure_validator.py:187` — `OSError` on rename is caught but not appended to `result.warnings`; the enforce report shows success while a file remains at root.

**Acceptance**:

- ingest: the ratio-below-threshold event is logged at `log.info` (matches `already_in_staging` / `already_exists` convention). When `ratio` attribute is absent, a distinct `log.warning("ingest.torrent_ratio_missing", hash=...)` event is emitted. Comment documents the `missing → skip` semantics.
- structure_validator orphan skip: `log.info("enforce.orphan_episode_no_season", path=str(f))` emitted when the regex doesn't match.
- structure_validator OSError branch: `result.warnings.append(...)` call added alongside the existing `log.warning` so operators see the failure in the structure report.

### 6.4 — Doc accuracy fixes (mediums + minors, 5 small edits)

**Findings**: 9. `docs/reference/testing.md:40-44` — claims `pytest-timeout` enforces tier budgets, but the package is not installed and no `timeout=` is in pyproject. False. 10. `docs/reference/testing.md:34` — rule "mock network **and subprocess** → integration" contradicts the taxonomy table ("real subprocesses" at integration). 11. `personalscraper/pipeline.py` — `step_overrides` docstring omits the `"dispatch"` key (supported at line 261). 12. `personalscraper/pipeline.py:383` — `_step_icon` docstring example `[cyan]1/7[/cyan]` stale; pipeline is 8-step. 13. `.github/workflows/ci.yml:125` — the `--ignore-vuln CVE-2026-3219` lacks an expiry/revisit comment. 14. `tests/integration/conftest.py:42-45` — tier isolation uses `assert` which is stripped under `python -O`.

**Acceptance**:

- testing.md: "Enforced by pytest-timeout" replaced with "Budget (advisory)". The rule of thumb says "mock network → integration" (no "and subprocess").
- pipeline.py: `step_overrides` docstring lists all 8 keys including `"dispatch"`. `_step_icon` example updated to `[cyan]1/8[/cyan]`.
- ci.yml: comment updated with "TODO(security): remove --ignore-vuln once pip > 26.0.1 is released with a fix (track https://github.com/pypa/pip/issues/…)". Acceptable if a specific tracking URL is unavailable; the TODO itself must exist.
- conftest.py: `assert` replaced with `if "tests.e2e" in sys.modules: raise RuntimeError(...)` so the guard survives `python -O`.

## Quality gates (after all sub-phases)

- `ruff check personalscraper/ tests/`
- `ruff format --check personalscraper/ tests/`
- `python -m mypy personalscraper/pipeline.py personalscraper/ingest/ingest.py personalscraper/enforce/structure_validator.py`
- `make test` — full suite green; expected test count: 1636 + 1 new dedup negative case = 1637 (+1) unless some existing test changes count.

## Out of scope for this cycle

- Regex deduplication between `structure_validator.py` / `episode_manager.py` / `verify/checker.py` (suggestion only; follow-up PR).
- `test_dispatch_new` ineligible-disk negative case (not in DESIGN §4 catalogue).
- TVDB miss path in `test_scrape` (DESIGN §4 catalogue #8 only specifies TMDB).
- `season_dir.mkdir` edge case with file-at-path (pathological; existing `except OSError` covers it).
