# Implementation Progress — check-plugins

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Unified Check Plugin Framework (verify + enforce) (minor)
**Version bump**: 0.19.0 → 0.20.0
**Branch**: feat/check-plugins
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/33 (pre-created, WIP — **update in place, do NOT create a new one**)
**Design**: docs/features/check-plugins/DESIGN.md
**Master plan**: docs/features/check-plugins/plan/INDEX.md

## Phases

| #   | Phase                   | File                               | Status |
| --- | ----------------------- | ---------------------------------- | ------ |
| 0   | Baseline golden capture | phase-00-baseline-golden.md        | [x]    |
| 1   | Core framework          | phase-01-core-framework.md         | [x]    |
| 2   | Migrate DISPATCH checks | phase-02-migrate-dispatch.md       | [x]    |
| 3   | Consolidate fixes       | phase-03-consolidate-fixes.md      | [x]    |
| 4   | DB-mode unification     | phase-04-db-mode.md                | [x]    |
| 5   | Migrate STAGING checks  | phase-05-migrate-staging.md        | [ ]    |
| 6   | Granular CLI            | phase-06-granular-cli.md           | [ ]    |
| 7   | Fix-policy unification  | phase-07-fix-policy-unification.md | [ ]    |
| 8   | Latent bug fixes        | phase-08-latent-bug-fixes.md       | [ ]    |
| 9   | Feature PR + review     | phase-09-feature-pr.md             | [ ]    |

## Design & plan review (2026-06-01, pre-implementation)

Design + plan were brainstormed, then verified **three times** before any code — more rigorous than the default flow. **Read this before starting Phase 0.**

**Brainstorm decisions (operator-confirmed):**

- **Scope = maximal**: one unified Check plugin framework spanning **verify (DISPATCH)** + **enforce (STAGING coherence)**; covers FS checks + DB-mode (`from_index`) + co-located fixes.
- **Approach A1 (fully unified)**: one `Check` Protocol, one `CheckResult`, one `CheckRegistry` keyed by **`(stage, name)`** (the `nfo_ids` collision), a shared `CheckContext` with a **parse-once NFO cache**.
- **Fix-policy asymmetry preserved** through Phases 0–6 (verify auto-fixes only `dir_naming`; library validate fixes 3), then **deliberately unified** in Phase 7 — `_VERIFY_FIX_POLICY` is a **module-level** constant so Phase 7 flips it in one place.
- **Phase 8 = operator-added adjacent scope** (not derived from the framework goals): Bug 1 `RatingSource` Literal `themoviedb`→`tmdb` (`indexer/external_ids.py`), Bug 2 eager-register `VerifyItemDone` (`events/__init__.py`). Bug 3 (trailers AppContext allowlist) = **verified false positive — no action**. See DESIGN §12.

**Three verification passes (all findings closed):**

1. **Full design+plan verification** (7 dimensions, adversarial): 64 findings, **15 confirmed**. Central one: the characterization golden covered only **2 of 7** entry points and the test was a stub → **vacuous parity proof**. Phase 0 was rewritten to capture **all 7** entry points pre-refactor, **real equality**, **fail-on-missing**, normalize `validated_at`, correct per-entry-point harnesses (staging corpus for coherence, in-memory DB for `from_index`, fresh copy for mutating fix paths).
2. **Lean coherence re-check**: caught that the first remediation was **banner-only** (banner said "do Y", phase body still showed "X") → fixed the **bodies** + cross-doc `6→7` count + removed a dangling `capture_golden.py` (the test is env-driven: `CAPTURE_GOLDEN=1` / `GOLDEN_ONLY`).
3. **Confirmation pass**: FINDING-CLOSURE clean; 3 residuals fixed (`_VERIFY_FIX_POLICY` module-level, phase-00 count, ACC-06b mapping).

**Invariants carried into implementation:**

- **No behavior change (Phases 0–6)**: all 7 entry points byte-identical vs the Phase-0 golden — it is the running parity guard, re-asserted every gate; Phase 7 updates `verifier_*` only, deliberately + isolated.
- **Public signatures unchanged** → existing `tests/verify` + `tests/enforce` keep passing as the second proof.
- **Single source**: `Severity`/`CheckResult`/`FixAction` in `verify/checks/base.py` (moved + importers repointed in **sub-phase 2.0**, FIRST); `MediaFixer` deleted (Phase 3); residual-import grep = 0.
- **Per-gate**: `make lint` · `make test` (0 ERROR) · `make check` (≥90 % cov, each plugin << 800 LOC) · residual greps · `python -c "import personalscraper"`. Regression-test-per-bug.
- 11 ACC criteria (INDEX) — every one an executable command; re-exercise all before squash merge.

**Git state:** branch `feat/check-plugins` **rebased on `origin/main` = #32** (docs overhaul) — 0 conflicts; VERSION + `personalscraper/__init__` = `0.20.0`; lib-fold archived. ⚠️ The branch also carries interleaved `docs(roadmap): …` commits from a **parallel agent** — leave `ROADMAP.md` untouched; those commits ride in this PR by the operator's choice.

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

**Phase 4 DONE (gate green).** Proceed to **Phase 5 — Migrate STAGING checks** (`docs/features/check-plugins/plan/phase-05-migrate-staging.md`): migrate the enforce (STAGING coherence) checks — `check_coherence` — onto the framework via STAGING-stage plugins (the `(stage, name)` collision case: `nfo_ids` exists on both DISPATCH and STAGING). Strict 0→9 order; each phase ends with `make check`. The Phase-0 golden (esp. `coherence`) + `test_dispatch_parity` are the running parity guards.

### Phase 0 gate record (2026-06-02)

- Sub-phases: `0.1` corpus builders (`175bf4a1`), `0.2` characterization test + 7 goldens (`71e7b4e3`).
- Gate caught a real defect: the tmp-path normalization regex was not robust to the pytest-xdist worker segment (`popen-gwN/`) nor to non-macOS tmp prefixes — 4 path-bearing tests passed in isolation but failed under full `make check`. Fixed in `c0b6c602` (prefix-agnostic + worker-aware regex; goldens unchanged, no re-capture).
- Gate green: `make lint` ✓, `make check` ✓ (5845 passed, 3 skipped, 2 xfailed, 0 failed; coverage 91.7%), 7 goldens, `import personalscraper` ✓, characterization test deterministic across serial + xdist runs.
- Note: a parallel `docs(roadmap)` commit (`0d231b88`, ROADMAP.md only) rides in this branch range per the operator's choice (IMPLEMENTATION.md design note).

### Phase 1 gate record (2026-06-02)

- Sub-phases: `1.1` `verify/checks/base.py` — types + 3 Protocols + `CheckContext` (parse-once NFO cache) (`2caab076`); `1.2` `registry.py` (`CheckRegistry` + `_ORDER` + `apply_fixes`) + `catalog.py` (`e4fff6ce`). Framework skeleton only — **0 production code changed**; `checker.py` keeps its own `Severity`/`CheckResult` until 2.0 (MOVE-1).
- Mechanical drift handled by sub-agents: `typing.Mapping` → `Mapping[str, Any]` (mypy strict), removed 2 stale `# type: ignore`, D103 test docstrings. No public shape changed; `_ORDER` table preserved verbatim.
- Gate green: `make check` ✓ (5859 passed, 0 failed; coverage ≥90%; base/registry/catalog all << 800 LOC), `import personalscraper` ✓, ACC-02 `tests/verify tests/enforce` 160 passed.

### Phase 2 gate record (2026-06-02)

- Sub-phases: `2.0` move `Severity`/`CheckResult` → base.py + repoint 8 importers, no shim (`27cebac6`); `2.1` extract all DISPATCH checks into **9 plugin modules / 22 `@register_check` classes** (`bdfacd85`); `2.2` `MediaChecker.check_movie/check_tvshow` become registry-driven loops (`8fa2bfa0`, checker.py 793→450 LOC; helper methods kept as dead code until Phase 3).
- **Parity proof strengthened**: added `tests/verify/checks/test_dispatch_parity.py` asserting `registry.checks_for(DISPATCH, mt)` loop output == `MediaChecker` output over the Phase-0 corpus (movie+tvshow). It passed in 2.1 (when MediaChecker still used inline logic) — proving the extraction is byte-faithful BEFORE 2.2 switched the bodies. `_ORDER` verified against the real append sequence (movie=13, tvshow=18).
- DeepSeek 2.2 dispatch hit one Category-B socket error; health-probe PASS → retried once → clean (per subagent:deepseek policy).
- Gate green: `make check` ✓ (5876 passed, 0 failed), ACC-01 golden 7 passed, ACC-02 168 passed, **ACC-06b grep rc=1**, `import personalscraper` ✓. ACC-07 module-size: all check-plugins modules << 800; 1 **pre-existing** advisory WARN on `scraper/movie_service.py` (975 LOC, untouched by this feature, under the 1000 hard ceiling) — out of scope.

### Phase 3 gate record (2026-06-02)

- Sub-phases: `3.1` co-locate real `fix()` on `DirNaming`/`NoEmptyDirs`/`NtfsSafeNames` (`fce87f94`); `3.2` delete `MediaFixer`, wire `Verifier` + `validate_library` to `apply_fixes()`, `_classify` reuses `ctx.resolved_category` (`0504c10` + `1d41ca`). `fixer.py` deleted.
- **Fix-policy asymmetry preserved** as module-level constants for Phase 7's single-flip: `_VERIFY_FIX_POLICY = frozenset({"dir_naming"})` (verifier.py), `_LIBRARY_FIX_POLICY = frozenset({"dir_naming","no_empty_dirs","ntfs_safe_names"})` (library_checks.py).
- **CMP-3**: verify_movie/verify_tvshow now run the registry loop on verify's OWN ctx (NOT `self._checker.check_movie`, which used a throwaway ctx — a latent plan inconsistency the Opus sub-agent corrected) so the `category` plugin's `resolved_category` propagates to `_classify`. `classify_from_nfo` calls per verify: 2 → 1 (pinned by `tests/verify/test_verifier_classify.py`).
- **Plan-literal bug caught + fixed by sub-agent**: the plan's `fixed_error_names = {a.old_path.name …}` captured path basenames, but the downstream `remaining_errors` filter compares check NAMES — would have silently broken the filter. Replaced with a per-failed-check `apply_fixes` loop tagging the check NAME.
- Gate green: `make check` ✓ (5864 passed, 0 failed, **coverage 91.12%** — no regression despite deleting MediaFixer tests; branch coverage migrated to `test_fixes.py`), ACC-01 golden 7 byte-identical, ACC-02 157 passed, **ACC-06a `MediaFixer` rc=1**, **ACC-06b rc=1**, `from …verify.fixer` rc=1, `import personalscraper` ✓.
- ⚠️ **BEHAVIOR NOTE (awaiting operator sign-off)**: the consolidated `NoEmptyDirs.fix()` (from the plan's 3.1 body) walks `rglob("*")` (recursive) whereas the legacy `library_checks._fix_empty_dirs` walked `iterdir()` (top-level only). The `library_validate` golden is byte-identical (corpus has no NESTED empty dirs, so the divergence is uncovered). This is a deliberate plan choice (more thorough cleaning) but IS a behavior change in the library empty-dir fix for nested cases. If strict legacy parity is required, revert `NoEmptyDirs.fix` to top-level `iterdir`. Otherwise no action.
- ⚠️ **Minor plan gap**: Phase 2.2 said checker.py's dead helper methods would be "deleted in Phase 3", but the Phase 3 plan never removes them. They remain as dead code (checker.py 450 LOC < 800). Candidate for a later cleanup; not blocking.

### Phase 4 gate record (2026-06-02)

- Sub-phases: `4.1` add `from_index()` to NfoPresent/NfoValid (nfo.py) + PosterPresent/ArtworkLandscape (artwork.py) — DB-mode IndexableCheck capability (`9a91a3d`); `4.2` `validate_from_index` becomes an `IndexableCheck` registry loop, replacing the inline `nfo_status`/`artwork_json` field-inspection (`09bc3148`).
- Parity: `library_from_index` golden byte-identical. Verified the from_index methods reproduce the OLD inline logic exactly — incl. the **movie-only landscape gate** (`if media_type == "movie"` in legacy ⇄ `ArtworkLandscape.from_index` returns None for tvshow), `nfo_status` NULL→unflagged, and the nfo-before-artwork order (= `_ORDER`).
- Gate green: `make check` ✓ (5875 passed, 0 failed, coverage 91.14%), ACC-01 golden 7 passed, ACC-02 168 passed, ACC-07 module-size (only the pre-existing movie_service.py WARN), `import personalscraper` ✓.

> **PR #33 is already created** (https://github.com/LounisBou/personal-scraper/pull/33, WIP). The branch is pushed to `origin/feat/check-plugins`. When the lifecycle reaches Phase 9 (`/implement:feature-pr`), it must **push onto the existing branch and reuse PR #33** (detect-existing, do not create a duplicate) — then `/implement:pr-review` → **manual squash merge**. Each implementation commit pushed to the branch updates PR #33 in place.
