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
| 0   | Baseline golden capture | phase-00-baseline-golden.md        | [ ]    |
| 1   | Core framework          | phase-01-core-framework.md         | [ ]    |
| 2   | Migrate DISPATCH checks | phase-02-migrate-dispatch.md       | [ ]    |
| 3   | Consolidate fixes       | phase-03-consolidate-fixes.md      | [ ]    |
| 4   | DB-mode unification     | phase-04-db-mode.md                | [ ]    |
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

**Ready for implementation in a fresh session.** Run `/implement:phase` — it starts at **Phase 0** (baseline golden capture of all 7 entry points; the parity spine). Strict 0→9 order; each phase opens with a Gate and ends with `make check`. Plan: `docs/features/check-plugins/plan/INDEX.md`.

> **PR #33 is already created** (https://github.com/LounisBou/personal-scraper/pull/33, WIP). The branch is pushed to `origin/feat/check-plugins`. When the lifecycle reaches Phase 9 (`/implement:feature-pr`), it must **push onto the existing branch and reuse PR #33** (detect-existing, do not create a duplicate) — then `/implement:pr-review` → **manual squash merge**. Each implementation commit pushed to the branch updates PR #33 in place.
