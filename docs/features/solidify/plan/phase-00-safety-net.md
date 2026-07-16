# Phase 0 — Worktree safety net + gate parity

## Gate

All of the following must pass before the phase-0 gate commit:

```bash
# Full local gate (unchanged commands; this phase makes them a superset of CI)
make lint && make test && make check

# New characterization tests pass and are wired into the suite
command python -m pytest tests -k "characterization or golden" -q --no-header | grep -E "passed"

# Gate-parity: the previously-broken rg flag no longer aborts the gate audit
grep -n "rg -l" Makefile          # confirm no `--include=` (invalid rg flag) remains
make gate                          # residual-import audit runs clean

# CI-only gates are now reachable locally (make == CI parity, DESIGN T10/P0)
python3 scripts/update_feature_map.py --check
python3 scripts/audit_design_coverage.py --strict

# Smoke import
python -c "import personalscraper" && echo IMPORT-OK

# ACC hooks introduced by this phase (DESIGN §10)
make check && echo ACC-01-OK
```

No modules are moved or deleted in P0, so there are no residual-import greps for
deletions; the residual-import audit that runs is the existing `make gate` block, whose
broken `rg --include='*.py'` flag (Makefile line ~82) this phase repairs.

## Objective

Install the behavioural safety net and gate parity that every later phase depends on
(DESIGN §7 P0, seam T10-gates). Pin current behaviour with characterization/golden tests
on the thin refactor targets (dispatch template, scrape write-back, trailer outcomes)
before any code moves; make `make check` a superset of CI so local-green == CI-green
(fold in the openapi-drift, version-bump, feature-map and design-coverage gates and fix
the invalid `rg` flag in the make gate); and capture a memtrace `get_impact` snapshot of
the bridge symbols so blast-radius regressions are detectable. This phase changes zero
production code paths.

## Findings addressed

- Groundwork for all phases; directly seeds DOCS-ARCH-DRIFT gate items and MEMTRACE-GRAPH-05
  (gate parity + impact snapshot). No functional finding is *resolved* here — P0 only
  builds the net that guards the resolutions in P1–P13.

## Code anchors (verified)

- **Broken gate flag**: `Makefile` line ~82 — `@! rg -l "TMDBError|TVDBError" personalscraper/ --include='*.py' ...`. Verified `rg --include` is an invalid flag (`rg: unrecognized flag --include`); the correct form is `-g '*.py'`. This is the "broken rg flag in the make gate" (DESIGN §5 T10).
- **`make check` composition**: `Makefile` `check:` target = `lint test-cov` + `check-module-size.py` + `check-no-broad-registry-catch.py` + `check-typed-api.py` + `check-pragma-discipline.py` + `audit-cli-coverage.py` + `cli-coverage-check`. Verified these CI-only gates are **absent** from the Makefile: `scripts/update_feature_map.py --check` and `scripts/audit_design_coverage.py --strict` (present only in `.github/workflows/ci.yml` lines 287 and 292).
- **CI job set** (`.github/workflows/ci.yml`): lint (ruff + `check_logging.py`), typecheck (mypy), test (pytest `-n auto` + coverage, needs `unar`), frontend (`tsc -b --noEmit`, `npm run lint`, `npm run lint:ds`, `npm run test -- --run`, `npm run build`), openapi (`make openapi` + `git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts`), coverage-merge (threshold monotonic vs base), version-bump (assert bumped vs base). These enumerate the "CI-only gates" P0 mirrors locally.
- **Bridge symbols for the impact snapshot** (DESIGN §4 constraint): `_StrictModel` (`personalscraper/conf/models/_base.py:10`), `run_enforce` (`personalscraper/enforce/run.py:24`), `TransportPolicy` (`personalscraper/api/transport/_policy.py:76`), `_build_app_context` (`personalscraper/cli_helpers/__init__.py:29`), `extract_stream_info` (`personalscraper/scraper/mediainfo.py:146`), `classify` (`personalscraper/conf/classifier.py:30`). All six verified present.
- **Characterization targets** (thin refactor targets lacking behavioural pins):
  - dispatch template: `personalscraper/dispatch/_movie.py::dispatch_movie` (:29) and `personalscraper/dispatch/_tv.py::dispatch_tvshow` (:27).
  - scrape write-back: `personalscraper/scraper/tv_service_write.py` (389 LOC) and the `_write_confirmed_*` extraction referenced by both services.
  - trailer outcomes: `personalscraper/trailers/orchestrator.py::TrailersOrchestrator.run` (:200).
- **Existing golden home**: `tests/verify/golden/` exists; `tests/scraper/test_nfo_golden_multi_source.py` shows the in-repo golden style. New characterization tests follow the unit/integration split in `docs/reference/testing.md`.
- **Version anchor**: `personalscraper/__init__.py:17` `__version__ = "0.50.0"` (already bumped by create-branch); `scripts/check_version_bump.py` present. `make check` parity must not duplicate the version-bump job in a way that fails on the branch (base is `origin/main`).

Discrepancy note: DESIGN §5 T10 says "make check gains the CI-only gates … frontend
lint/typecheck/test". Adding the frontend gates directly into `make check` would force an
`npm` toolchain run on every backend phase gate. Resolution (executor re-verifies): wire
the **backend** CI-only gates (`update_feature_map --check`, `audit_design_coverage
--strict`, openapi-drift check, version-bump-vs-main) into `make check`, and expose the
frontend gates through a dedicated `make check-frontend` target that `make check` invokes
**only when `frontend/node_modules` is present** (skips cleanly on CI-parity backend
runs, runs in full on frontend phases P10/P11 and in P13). This preserves "local green ==
CI green" without making every backend gate depend on Node.

## Tasks

1. **P0.1 — Fix the broken gate flag.** Edit `Makefile`: replace `rg -l "TMDBError|TVDBError" personalscraper/ --include='*.py'` with `rg -l "TMDBError|TVDBError" -g '*.py' personalscraper/`. Verify: `make gate` runs the residual-import audit without an `unrecognized flag` error, and the audit still passes (`echo $?` == 0).
2. **P0.2 — Fold backend CI-only gates into `make check`.** Add to the `check:` target (after the existing gate scripts): `python3 scripts/update_feature_map.py --check`, `python3 scripts/audit_design_coverage.py --strict`, an openapi-drift check (`make openapi` then `git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts` — guarded to no-op when `frontend/node_modules` absent), and a version-bump check against `origin/main` (`python3 scripts/check_version_bump.py --base origin/main`). Verify: `make check` runs each new gate; on a clean branch all pass. Keep each new line individually runnable.
3. **P0.3 — Add `make check-frontend` parity target.** New Makefile target running `cd frontend && npm run lint && npm run typecheck && npx vitest run`; `make check` invokes it conditionally on `frontend/node_modules` existing. Verify: with `node_modules` present, `make check-frontend` mirrors the CI frontend job (lint, typecheck, vitest); document `lint:ds` as part of P10/P11 gates (not forced on backend phases).
4. **P0.4 — Characterization: dispatch template.** Create `tests/dispatch/test_dispatch_characterization.py` pinning current `dispatch_movie` (replace) and `dispatch_tvshow` (merge-overwrite) behaviour: destination path, `existing_action`, journal side-effects (movie journals, TV does NOT yet — this pins the pre-F1 state), orphan-temp cleanup. Cover BOTH entry points; normalize non-deterministic fields (timestamps, tmp suffixes) per the complete-golden rule. Verify: `pytest tests/dispatch/test_dispatch_characterization.py -q` green; deliberately mutate a destination in a scratch run to confirm the test fails (proves it is load-bearing), then revert.
5. **P0.5 — Characterization: scrape write-back.** Create `tests/scraper/test_writeback_characterization.py` pinning the folder rename/merge + NFO id/title + artwork-recovery outcomes for a movie dir and a TV-show dir against goldens. Cover the forced-resolve path too (must match automatic scrape — a hard product invariant). Verify: `pytest tests/scraper/test_writeback_characterization.py -q` green; fail-on-missing golden asserted.
6. **P0.6 — Characterization: trailer outcomes.** Create `tests/trailers/test_orchestrator_characterization.py` pinning the six current `TrailersOrchestrator.run()` outcomes (found/placed/skipped/failed/cooldown/no-match) as a status map, normalizing paths/timestamps. Verify: `pytest tests/trailers/test_orchestrator_characterization.py -q` green.
7. **P0.7 — Memtrace bridge-symbol impact snapshot.** Run `get_impact` on each bridge symbol (`_StrictModel`, `run_enforce`, `TransportPolicy`, `_build_app_context`, `extract_stream_info`, `classify`) and record the blast-radius (caller sets, communities) into `docs/analysis/2026-07-16-solidify-impact-baseline.md` (untracked analysis file per repo convention, English). Verify: file exists and lists a non-empty caller set per symbol; this is the baseline later phases diff against before touching a bridge symbol.
8. **P0.8 — Green the superset gate.** Run `make lint && make test && make check` end to end; fix any newly-surfaced parity failure (e.g. a stale feature_map or design-coverage gap) by regenerating the artifact, not by weakening the gate. Verify: all commands exit 0.

## Non-goals

- No production-code behaviour change of any kind (P0 is net-only). The characterization
  tests pin the PRE-fix state — F1's "TV merge journaled" assertion is written in P2, not
  here.
- Do not touch the dispatch/scrape/trailer *implementations* (P2/P4/P6 own those).
- Do not add the six conformity-fix regression tests here; each lands in its seam's phase.
- Do not modify `origin/main` reintegration state — the first merge-of-main happens at the
  P0→P1 boundary only if main actually moved.

## Commit

Intermediate commits (optional, per task):

```
test(solidify): characterization goldens for dispatch/scrape/trailer targets
ci(solidify): fix invalid rg flag in make gate; add CI-only gates to make check
```

Phase-gate commit:

```
chore(solidify): phase 0 gate — safety net, gate parity, bridge-symbol impact baseline
```
