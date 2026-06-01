# check-plugins Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `verify/checker.py` monolith and `enforce/coherence_checker.py` duplicate with a single unified Check plugin framework: one `Check` Protocol, a `CheckRegistry`, per-group plugin modules under `verify/checks/`, and registry-driven orchestrator loops — all proven no-behavior-change by a characterization golden over all 6 public entry points.

**Architecture:** Each existing check becomes its own plugin class in `verify/checks/<group>.py` registered via `@register_check`. Four orchestrators (`MediaChecker`, `Verifier`, `validate_library`, `validate_from_index`, `check_coherence`) become thin registry-driven loops with unchanged public signatures. Fix logic moves to co-located `fix()` methods; `MediaFixer` is deleted. A final deliberate phase unifies verify's fix policy to the 3-check set already used by library validate.

**Tech Stack:** Python 3.11, `dataclasses`, `xml.etree.ElementTree`, `pytest`, `make lint/test/check`

---

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

---

## ACCEPTANCE Criteria Mapping

Every criterion is an executable shell command with documented expected output (per project convention — prose criteria are invalid).

| ACC     | Command                                                                                                                                                                                                                       | Expected output                                                                        | Phase                                                      |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| ACC-01  | `pytest tests/verify/test_characterization_golden.py -q`                                                                                                                                                                      | All pass, 0 failed                                                                     | Phase 0 (captured), asserted from Phase 2 onward           |
| ACC-02  | `pytest tests/verify tests/enforce -q`                                                                                                                                                                                        | All pass, 0 failed                                                                     | Asserted each phase gate Phase 1–7                         |
| ACC-03  | `python -c "from personalscraper.verify.checks.catalog import list_checks; s=list_checks(); print(len(s))"`                                                                                                                   | Prints integer ≥ 23                                                                    | Phase 1 (catalog created), Phase 2 + 5 (checks registered) |
| ACC-04a | `personalscraper verify --list-checks`                                                                                                                                                                                        | Prints DISPATCH check specs, exits 0                                                   | Phase 6                                                    |
| ACC-04b | `personalscraper verify --check nfo_present` (operates on the configured staging dirs — no positional path)                                                                                                                   | Runs only the nfo_present check; prints "N OK, M blocked", exits 0                     | Phase 6                                                    |
| ACC-05  | `python -c "from personalscraper.verify.checks.base import CheckStage as S; from personalscraper.verify.checks.registry import registry; print(registry.get(S.DISPATCH,'nfo_ids') is not registry.get(S.STAGING,'nfo_ids'))"` | `True`                                                                                 | Phase 5                                                    |
| ACC-06a | `rg -t py 'MediaFixer' personalscraper/ tests/`                                                                                                                                                                               | rc=1 (no matches)                                                                      | Phase 3                                                    |
| ACC-06b | `rg -t py 'from personalscraper\.verify\.checker import.*\b(Severity\|CheckResult)\b' personalscraper/ tests/`                                                                                                                | rc=1 (no matches)                                                                      | Phase 3                                                    |
| ACC-07  | `python3 scripts/check-module-size.py`                                                                                                                                                                                        | rc=0; all modules under 800 LOC                                                        | Each gate Phase 1–7                                        |
| ACC-08  | `make check`                                                                                                                                                                                                                  | rc=0, coverage ≥ 90%                                                                   | Each gate Phase 1–7                                        |
| ACC-09  | `pytest tests/verify/checks/test_fix_policy.py -q`                                                                                                                                                                            | All pass — verify pipeline auto-fixes `no_empty_dirs` + `ntfs_safe_names`              | Phase 7                                                    |
| ACC-10  | `pytest tests/indexer/test_external_ids_models.py::test_extract_nfo_metadata_rating_source_validates_against_model -q`                                                                                                        | Pass — stored `source="tmdb"` validates against the `Ratings` model (Bug 1)            | Phase 8                                                    |
| ACC-11  | `pytest tests/event_bus/test_verify_item_done_catalog.py -q`                                                                                                                                                                  | Pass — `VerifyItemDone` resolves from the eager catalog in a fresh interpreter (Bug 2) | Phase 8                                                    |

---

## Running parity guard

The **characterization golden** captured in Phase 0 (`tests/verify/golden/*.json`) is re-asserted green at every gate from Phase 2 through Phase 6. Phase 7 deliberately updates it (explicit golden update + dedicated tests). This is the formal proof of "no behavior change" for the structural refactor.

---

## Per-gate quality checklist (CLAUDE.md §Phase Gate)

Each phase gate MUST pass all of:

1. `make lint` → 0 errors (ruff + mypy)
2. `make test` → all pass, 0 collection ERROR
3. `make check` → rc=0, coverage ≥ 90%, module-size each plugin << 800 LOC
4. Residual-import grep (where modules move/delete) → 0 matches
5. `python -c "import personalscraper"` → exits 0

---

## Key code anchors (DESIGN §5, §8)

- **6 public entry points**: `MediaChecker.check_movie/check_tvshow`, `Verifier.verify_movie/verify_tvshow`, `validate_library`, `validate_from_index`, `check_coherence`
- **`_ORDER` table** (DESIGN §8): deterministic per `(stage, media_type)` key; `checks_for()` respects it
- **Fix-policy asymmetry** (DESIGN §6.3): verify = `{"dir_naming"}`, library = `{"dir_naming","no_empty_dirs","ntfs_safe_names"}` — PRESERVED through Phase 6, unified in Phase 7
- **`(stage, name)` registry key** (DESIGN §6.1): `nfo_ids` exists on both DISPATCH and STAGING as genuinely different checks
