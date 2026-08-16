# Registry Merge Readiness — feat/registry → main (PR #27)

> STATUS: SHIPPED (registry, #27). Live docs archived under docs/archive/features/registry/. Historical analysis.

> **Date**: 2026-05-28 · **Version**: 0.16.0 · **Branch**: `feat/registry` (HEAD `c40015f7`) · **Project status**: pre-1.0, single mono-user instance, NOT in production · **Report scope**: merge-readiness of the Provider Registry feature (PR #27), the open Phase 30, the documentation/acceptance drift, and the squash/archival decisions · **Confidence**: high (every load-bearing claim re-verified live at HEAD `c40015f7`; earlier passes anchored at the stale snapshot `348e4ed9` and their "merge-ready" framing is corrected here).

---

## 1. Executive summary (TL;DR)

- **PR #27 is NOT merge-ready.** A new **Phase 30** (scraper same-TMDB multi-source dedup fix) is open: `IMPLEMENTATION.md:47` marks it `[ ]`. Only sub-phase **30.1** is committed (`c40015f7`); sub-phases **30.2 → 30.5** are unimplemented (verified: 0 `movie_video_orphan` occurrences in `movie_service.py`, no `_check_no_duplicate_videos` in `verify/checker.py`, no E2E test, matrix still `2.4`).
- **The branch is not even pushed.** Local `feat/registry` is **3 commits ahead** of `origin/feat/registry`. `gh pr view 27` reports `headRefOid` = `348e4ed9` — the green CI (9/9 checks) was computed for the Phase-29 gate and **does NOT cover the new code fix `c40015f7`**. CI-at-true-HEAD is unknown.
- **The feature tracker contradicts itself.** `IMPLEMENTATION.md:57` says "Execute phase 30 … then squash-merge", while a stale block at `IMPLEMENTATION.md:190-192` says "**MERGE READY** — squash now". Two opposite "Next action" directives in one live file.
- **The registry framework itself is sound and genuinely consumed** (re-confirmed): `registry/__init__.py` = 689 non-blank LOC, all 6 modules under the 800 soft ceiling, all 5 v1 events emitted in production, `fan_out(RatingProvider)` has a real consumer at `backfill_ids.py:637`, zero `DEFER/TODO(registry)/FIXME` markers, `make check` guards exit 0.
- **Three pre-merge documentation defects remain** (independent of Phase 30): ACC-09 + `BASELINE_PASS_COUNT` pinned at `342` but live count is `344`; ACC-04b is environment-dependent; DESIGN claims the indexer fan_out migration is deferred in **three** places (`:605`, `:607`, `:1018`) while `:1091` and the shipped code say it was delivered in Phase 11.

**Verdict: CONDITIONAL — DO NOT MERGE YET.** Close Phase 30 (5 sub-phases, includes a functional scraper code change + its E2E regression test), then re-pin ACC counts to the post-Phase-30 value, reconcile the DESIGN contradiction, fix ACC-04b, resolve the duplicate "Next action" block, push, confirm CI green at the real HEAD, then squash.

---

## 2. Current state (evidence-backed)

### 2.1 Branch / PR mechanics (live at `c40015f7`)

| Fact                         | Command                                                    | Observed                                      |
| ---------------------------- | ---------------------------------------------------------- | --------------------------------------------- |
| Commits ahead of `main`      | `git rev-list --count main..feat/registry`                 | **203** (was 200 at the `348e4ed9` snapshot)  |
| Local diff vs main           | `git diff --stat main..feat/registry \| tail -1`           | **200 files, +21823 / −2261**                 |
| PR API diff (STALE)          | `gh pr view 27 --json additions,deletions,changedFiles`    | 196 files, +21115 / −2256                     |
| PR head (STALE)              | `gh pr view 27 --json headRefOid`                          | `348e4ed9` (NOT current `c40015f7`)           |
| Local ahead of remote branch | `git rev-list --count origin/feat/registry..feat/registry` | **3** (branch not pushed)                     |
| PR state                     | `gh pr view 27 --json state,mergeable,mergeStateStatus`    | OPEN / MERGEABLE / CLEAN                      |
| Squash conflict-free         | `git merge-base --is-ancestor main feat/registry`          | exit 0 (main 0 ahead)                         |
| CI at PR head                | `gh pr checks 27`                                          | 9/9 pass — but for `348e4ed9`, not `c40015f7` |

The +21115/−2256/196-files figures in earlier passes are the **GitHub PR API view of the un-pushed older head** and must not be used for merge planning. The squash will collapse **200 local-diff files**, not 196.

### 2.2 Phase 30 status (the merge blocker)

`IMPLEMENTATION.md:47`: `| 30 | Scraper same-TMDB multi-source dedup fix | phase-30-scrape-dedup-gap-fix.md | [ ] |`. Plan at `docs/features/registry/plan/phase-30-scrape-dedup-gap-fix.md` defines 5 sub-phases:

| Sub-phase | Deliverable                                                                                           | Status (verified)                                                                                                                                         |
| --------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 30.1      | `_find_video_file` mtime-first selection + `tests/scraper/test_find_video_file.py`                    | **DONE** (`c40015f7`): `_shared.py:81` now `max(candidates, key=lambda f: (f.stat().st_mtime, f.stat().st_size))`; 81-line test file added                |
| 30.2      | Post-rename orphan unlink in `movie_service.py` + `movie_video_orphan_*` events + tests               | **NOT DONE**: `grep -c movie_video_orphan personalscraper/scraper/movie_service.py` = 0; `tests/unit/scraper/test_movie_service_orphan_cleanup.py` absent |
| 30.3      | `_check_no_duplicate_videos` in `verify/checker.py` (movie scope, 12→13 checks) + tests               | **NOT DONE**: no `_check_no_duplicate_videos`; `tests/unit/verify/test_no_duplicate_videos.py` absent                                                     |
| 30.4      | `tests/e2e/test_scrape_same_tmdb_multi_source.py` (Gourou regression)                                 | **NOT DONE**: file absent                                                                                                                                 |
| 30.5      | Matrix v2.4 → v2.5 bump (`design-conformity-matrix.md` + `SKILL.md` `MATRIX_VERSION`) + agent prompts | **NOT DONE**: matrix header still `2.4` (`design-conformity-matrix.md:3`), `SKILL.md:28` still `MATRIX_VERSION = "2.4"`                                   |

Phase 30 is a **functional scraper behaviour change** (root-cause fix + automatic orphan cleanup + VERIFY safety net), not a docs cleanup. It addresses a MAJEUR pipeline-monitor v2.4 deviation: same-TMDB merges leave orphan `.mkv` files that no pipeline step catches (Gourou scenario: 22 GB HDR + 2.9 GB 1080p resolving to the same TMDB id). Operator spec (`phase-30…:29-32`): the most recently downloaded video must be the one kept; no orphan may remain.

### 2.3 Registry framework (sound — re-confirmed)

- **Module sizes (non-blank LOC, all < 800 soft ceiling)**: `__init__.py` 689, `_validation.py` 313, `_factory.py` 225, `_semantics.py` 82, `_events.py` 76, `_errors.py` 75. `python scripts/check-module-size.py` exits 0.
- **5 v1 events all emitted in production** (`registry/__init__.py`): `RegistryBootValidated:394`, `RegistryFanOutCompleted:496`, `LockedCapabilityUnresolved:583`, `ProviderFallbackTriggered:640` and `:759` (via `_emit_fallback`), `ProviderExhaustedEvent:792` (via `_emit_exhausted`). `def fan_out` at `:447`.
- **fan_out has a real consumer**: `personalscraper/indexer/scanner/_modes/backfill_ids.py:637` calls `registry.fan_out(RatingProvider)` and iterates `.values` at `:645`. It is the **only** non-doc/non-registry call site (concentration risk, §3).
- **Empty config sections are intentional and inline-documented**: `config.example/providers.json5` `RatingProvider:{}` (`:32`), `KeywordProvider:{}` (`:44`), `IDValidator:{}` (`:55`), `IDCrossRef:{}` (`:56`), each with a rationale comment. Local `config/providers.json5` mirrors the template (no overlay drift).
- **Zero deferral markers**: `grep -rn "DEFER\|FIXME" personalscraper/ --include="*.py"` exit 1; `grep -rn "TODO(registry)"` exit 1.
- **`make check` guards pass live**: ruff clean, `check-module-size` 0, `check-no-broad-registry-catch` 0, `check-typed-api` 0, `check-pragma-discipline` 0, `audit-cli-coverage` 0, `check_logging` 0.
- **CHANGELOG 0.16.0 present**: `CHANGELOG.md:8` `## [0.16.0] — 2026-05-27`, registry entries at `:12`, `:19`.

### 2.4 Acceptance / documentation drift

- **ACC-09 + baseline STALE**: `ACCEPTANCE.md:11` `BASELINE_PASS_COUNT = 342`; `ACCEPTANCE.md:28` ACC-09 expected stdout `342`; `IMPLEMENTATION.md:87` `BASELINE_PASS_COUNT = 342`. Live run `pytest tests/e2e/ tests/integration/ -q` → **344 passed, 22 deselected, 1 xfailed** (11.13s). Phases 27–29 added regression tests after the Phase-26 re-pin, drifting +2.
- **ACC-04b env-dependent**: `ACCEPTANCE.md:22` expects `personalscraper info providers 2>&1 | grep -c 'RegistryConfigError'` = `1`. In this clone (which has `config/providers.json5`) it returns `0`. The criterion only holds on a config-less clone.
- **DESIGN contradiction (3 vs 1)**: `DESIGN.md:605` ("outside the Big Bang scope of this feature"), `:607` ("a deliberate follow-up feature"), and `:1018` ("No real consumer is migrated here — the only candidate `indexer/backfill_ids.py` stays on its current code path") all say the indexer migration is deferred. But `DESIGN.md:1091` (§11) says it "is delivered in **Phase 11 of this feature plan**", and `backfill_ids.py:637` proves it. **Three** stale assertions, not one — earlier passes flagged only `:1018`.
- **Duplicate "Next action"**: `IMPLEMENTATION.md:57` (execute Phase 30 first) vs `IMPLEMENTATION.md:190-192` (MERGE READY, "CI green on `ccb8ba9b`" — a SHA not in the recent log).

### 2.5 History context (RETROSPECTIVE)

`RETROSPECTIVE.md:4` records a **prior merge of PR #27 on 2026-05-26** (framework-only, graded "Production migration: D — Framework is unused in production", `RETROSPECTIVE.md:196`), then a reopen. `IMPLEMENTATION.md:49` confirms Phases 7–13 are "Post-merge remediation phases generated by the 2026-05-27 retrospective". The current OPEN PR re-presents framework + all remediation; the production-consumer gap the retrospective flagged is now closed (chain in production via Phase 7, indexer fan_out via Phase 11). RETROSPECTIVE Item #3 (DESIGN amended mid-execution) and Item #11 (no end-to-end pipeline run validated registry) remain relevant to §3.

---

## 3. Problems & risks

| #   | Severity     | Problem                                                                                                                                                                 | Evidence                                                                                                                               |
| --- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | **CRITICAL** | Phase 30 open — 4 of 5 sub-phases unimplemented (functional scraper change, not docs)                                                                                   | `IMPLEMENTATION.md:47` `[ ]`; `grep -c movie_video_orphan movie_service.py` = 0; no `_check_no_duplicate_videos`; no E2E; matrix `2.4` |
| P2  | **CRITICAL** | Branch not pushed; PR CI green only for the stale head `348e4ed9`, not the code fix `c40015f7`                                                                          | `git rev-list --count origin/feat/registry..feat/registry` = 3; `gh pr view 27` headRefOid `348e4ed9`                                  |
| P3  | **HIGH**     | ACC-09 + `BASELINE_PASS_COUNT` = 342 but live count is 344 — SH-16 criterion fails its documented output                                                                | `ACCEPTANCE.md:11,:28`, `IMPLEMENTATION.md:87`; live `344 passed`                                                                      |
| P4  | **HIGH**     | `IMPLEMENTATION.md` self-contradicts on merge-readiness (line 57 vs 190-192)                                                                                            | both blocks live in the same tracked file                                                                                              |
| P5  | MEDIUM       | DESIGN says fan_out indexer migration is deferred in 3 places (`:605/:607/:1018`), contradicting `:1091` + shipped code — about to be frozen into the archived contract | `DESIGN.md` lines + `backfill_ids.py:637`                                                                                              |
| P6  | MEDIUM       | ACC-04b passes only on a config-less clone (non-deterministic across dev environments)                                                                                  | `ACCEPTANCE.md:22`; live returns `0` not `1`                                                                                           |
| P7  | MEDIUM       | Squash collapses 203 commits (34 fix + 24 refactor + 29 test) → one; permanent loss of sub-feature bisectability on main                                                | `git log main..feat/registry --pretty=%s` type-bucketed                                                                                |
| P8  | MEDIUM       | Post-merge, main holds the live `IMPLEMENTATION.md` + 39-file `docs/features/registry/` tree un-archived until a manual `/implement:archive` step                       | `git ls-files`; `docs/archive/features/` has 14 prior features, not registry                                                           |
| P9  | LOW          | `fan_out` has exactly one consumer (`backfill_ids.py`), OMDB-gated, never exercised in the default 2-provider config — test-covered but not smoke-tested live           | `RatingProvider:{}` at `providers.json5:32`; RETROSPECTIVE Item #11                                                                    |

**Sequencing note on P3**: do NOT re-pin to 344 now. Phase 30 sub-phases 30.3/30.4 add tests under `tests/verify/`/`tests/e2e/` (the ACC-09 selector globs `tests/e2e/ tests/integration/`), so the count will drift again. Re-pin **after** Phase 30 closes, to whatever the post-Phase-30 measurement yields — this is the exact drift mechanism that caused 342→344.

---

## 4. Implementation plan

This work continues the **existing** `feat/registry` branch — it is in-flight, not a new feature. The `/implement:phase` lifecycle drives Phase 30; the doc/acceptance fixes ride as a trailing cleanup commit so they fold into the squash. No new codename, no SemVer re-bump (already `0.15.1 → 0.16.0` at create-branch). Conventional Commits with `(scraper)` / `(verify)` / `(pipeline-monitor)` / `(registry)` scopes. **No migration scripts** (pre-1.0). Module-size hard ceiling 1000 LOC respected. Regression-test-per-bug enforced (Phase 30.4 is the Gourou regression).

> Branch: `feat/registry` (existing). Commits: see per-sub-phase. SemVer: unchanged (0.16.0).

### Phase A — Finish Phase 30 (the merge blocker)

**Objective**: close the open MAJEUR same-TMDB dedup deviation end-to-end (root cause + auto-cleanup + safety net + regression + matrix). Follow `phase-30-scrape-dedup-gap-fix.md` verbatim. Public import paths to preserve: `personalscraper.scraper._shared._find_video_file`, `personalscraper.verify.checker` check entry points (no rename of existing checks).

- **A.2 (= plan 30.2)** — _Modify_ `personalscraper/scraper/movie_service.py`: after the canonical rename succeeds (after the `log.info("movie_video_renamed", ...)` site, plan cites ~line 982), iterate the movie dir and `unlink` any other `VIDEO_EXTENSIONS` file that is not the canonical path. Emit `movie_video_orphan_removed` per removal (`filename`, `parent` fields); wrap each `unlink` in `try/except OSError` emitting `movie_video_orphan_remove_failed` and continue (one failure must not abort the others); guard behind the non-dry-run branch and emit `movie_video_orphan_would_remove` in dry-run. _Create_ `tests/unit/scraper/test_movie_service_orphan_cleanup.py` (3 cases: real cleanup leaves only canonical + emits `movie_video_orphan_removed` once; dry-run preserves both + emits `movie_video_orphan_would_remove`, no `unlink`; mocked `OSError` → `movie_video_orphan_remove_failed` logged, canonical untouched, no raise). Commit `fix(scraper): unlink non-canonical video files after movie rename`. Effort **M**, risk **medium** (live move/rename path), deps: 30.1 (done).
- **A.3 (= plan 30.3)** — _Modify_ `personalscraper/verify/checker.py`: add `_check_no_duplicate_videos` (movie scope only — TV shows have multi-file seasons by design), non-recursive count of `VIDEO_EXTENSIONS` files at the movie root; `> 1` → `CheckResult(passed=False, error="Multiple video files at root: {sorted(filenames)}")`. Wire into the movie checks so the denominator becomes 13/13. _Create_ `tests/unit/verify/test_no_duplicate_videos.py` (1 video passes; 2 videos fail with the exact error string; 1 root + 1 in `Extras/` passes — sub-dir ignored). Commit `feat(verify): block movies with multiple video files at root`. Effort **M**, risk **low**.
- **A.4 (= plan 30.4)** — _Create_ `tests/e2e/test_scrape_same_tmdb_multi_source.py`: two staged movie dirs (`Gourou (2025)/A.mkv` older mtime, `Gourou (2026)/B.mkv` newer), mocked TMDB returning the same id for both probes; assert only `Gourou (2026)/Gourou.mkv` (content of `B.mkv`) survives, `Gourou (2025)/` removed, NFO+poster+landscape present, no orphan; assert log events `movie_folder_merged`, `movie_video_renamed`, `movie_video_orphan_removed` (×1), no `movie_video_orphan_remove_failed`; assert VERIFY `status=valid checks_passed=13 checks_total=13`. Apply `@pytest.mark.e2e` per `tests/e2e/conftest.py`. Commit `test(scraper): e2e regression for same-TMDB multi-source dedup`. Effort **M**, risk **low**, deps: A.2, A.3.
- **A.5 (= plan 30.5)** — _Modify_ `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md` (header `2.4`→`2.5` at `:3`, new PROCESS:scrape DESIGN_CONFORM row for `movie_video_orphan_removed`, VERIFY denominator `12/12`→`13/13`, changelog footer line). _Modify_ `.claude/skills/pipeline-monitor/SKILL.md` `MATRIX_VERSION = "2.4"`→`"2.5"` at `:28` (+ the assertion text at `:30,:32`). _Modify_ `.claude/agents/pipeline-output-analyzer.md` and `.claude/agents/pipeline-scrape-checker.md` per plan. Commit `docs(pipeline-monitor): matrix v2.5 — movie dedup contract`. Effort **S**, risk **low**, deps: A.2 (event names must match emitted ones).
- **Phase 30 gate**: `make lint` 0, `make test` all green (incl. new unit + E2E), `make check` exit 0, `python -c "import personalscraper"` exit 0. Flip `IMPLEMENTATION.md:47` to `[x]`.

### Phase B — Pre-merge documentation & acceptance fixes

**Objective**: make the archived contract internally consistent and SH-16-clean. Single `docs(registry): …` commit (folds into squash). Effort **S** total, risk **low**, deps: **must run AFTER Phase A** (so the ACC re-pin includes Phase 30 tests).

- **B.1 Re-pin ACC counts** — _Modify_ `docs/features/registry/ACCEPTANCE.md:11` and `:28`, and `IMPLEMENTATION.md:87`: set `BASELINE_PASS_COUNT` / ACC-09 expected to the live post-Phase-30 value of `pytest tests/e2e/ tests/integration/ -q | tail -1 | grep -oE '[0-9]+ passed' | awk '{print $1}'`. (At current HEAD that is `344`; it will be higher once A.4 adds the E2E test — measure, do not assume.) Re-run ACC-09 to confirm stdout matches.
- **B.2 Fix ACC-04b determinism** — _Modify_ `docs/features/registry/ACCEPTANCE.md:22`: change the command to point at a guaranteed-absent config, `personalscraper info providers --config /nonexistent/providers.json5 2>&1 | grep -c 'RegistryConfigError'` (first verify `--config` is a real flag via `personalscraper info providers --help`; if not, document the precondition "run from a clone without config/"). Re-run to confirm it returns `1` regardless of local `config/`.
- **B.3 Reconcile DESIGN** — _Modify_ `DESIGN.md:605`, `:607`, and `:1018`: state the indexer fan_out consumer **was migrated in Phase 11** (matching `:1091` + `backfill_ids.py:637`). Optionally add the `## Revision history` section RETROSPECTIVE Item #3 recommends. Do not touch the §11 paragraph at `:1091` (already correct).
- **B.4 Resolve duplicate "Next action"** — _Modify_ `IMPLEMENTATION.md`: delete the stale `## Next action` block at `:190-192` (the "MERGE READY / CI green on ccb8ba9b" one) and keep `:57` as the single source of truth, updated to reflect Phase 30 closure.

### Phase C — Final gate, push, CI, merge decision

**Objective**: green CI at the real HEAD, deliberate squash decision, merge. Effort **M** (full suite ~5–6 min), risk **low**, deps: Phases A + B complete.

- **C.1** Run the full `make check` once at the merged HEAD (lint + test-cov branch-coverage ≥90% + module-size + typed-api + pragma + cli-coverage + no-broad-registry-catch). Earlier passes verified ruff + the 6 guards + the e2e/integration anchor + registry units, but **not** the full 5657-test suite or the coverage gate.
- **C.2** `git push origin feat/registry`; then `gh pr checks 27` must be green **at the new headRefOid** (which becomes the Phase-A/B HEAD, not `348e4ed9`).
- **C.3** Record a deliberate squash-vs-`--no-ff` decision in the PR description (§6). Default = manual squash (chosen at feature start). Then squash-merge.
- **C.4** (post-merge) decide archival: run `/implement:archive` immediately (on a non-main branch), OR let the next feature's `/implement:create-branch` fold it in. Either way the stale `IMPLEMENTATION.md` already on main must be replaced. Defer ROADMAP P2 (Web UI Consumer, `ROADMAP.md:132`) / P3 (Active Health Scoring `:256`, Hot-Swap `:284`) — net-new features, not blockers.

---

## 5. Acceptance criteria

SH-16 — every criterion is an executable command with documented expected output. Run from repo root after Phases A + B at the merged HEAD.

```bash
# AC-1 — Phase 30 closed in the tracker
grep -E '^\| 30 ' IMPLEMENTATION.md | grep -c '\[x\]'
# expected stdout: 1

# AC-2 — 30.1 root-cause fix present (mtime drives _find_video_file)
grep -c 'st_mtime' personalscraper/scraper/_shared.py
# expected: >= 1

# AC-3 — 30.2 orphan cleanup wired with events
grep -c 'movie_video_orphan_removed' personalscraper/scraper/movie_service.py
# expected: >= 1

# AC-4 — 30.3 verify safety net present
grep -c '_check_no_duplicate_videos' personalscraper/verify/checker.py
# expected: >= 1

# AC-5 — 30.4 E2E regression exists and passes
test -f tests/e2e/test_scrape_same_tmdb_multi_source.py && echo PRESENT
# expected stdout: PRESENT
python -m pytest tests/e2e/test_scrape_same_tmdb_multi_source.py -q | tail -1 | grep -c 'passed'
# expected: 1

# AC-6 — 30.5 matrix bumped to 2.5 in both files
grep -c 'Matrix version.*2.5' .claude/skills/pipeline-monitor/references/design-conformity-matrix.md
# expected: 1
grep -c 'MATRIX_VERSION = "2.5"' .claude/skills/pipeline-monitor/SKILL.md
# expected: 1

# AC-7 — ACC-09 / BASELINE re-pinned to the LIVE post-Phase-30 count (compute, then assert equality)
N=$(python -m pytest tests/e2e/ tests/integration/ -q 2>&1 | tail -1 | grep -oE '[0-9]+ passed' | awk '{print $1}')
grep -c "BASELINE_PASS_COUNT.*\*\*${N}\*\*" docs/features/registry/ACCEPTANCE.md
# expected: 1   (pinned value equals the live measurement)

# AC-8 — ACC-04b is environment-independent (returns 1 even with local config/ present)
personalscraper info providers --config /nonexistent/providers.json5 2>&1 | grep -c 'RegistryConfigError'
# expected stdout: 1

# AC-9 — DESIGN no longer claims the fan_out indexer migration is unmigrated
grep -c 'stays on its current code path' docs/features/registry/DESIGN.md
# expected: 0

# AC-10 — IMPLEMENTATION.md has exactly ONE Next-action block
grep -c '^## Next action' IMPLEMENTATION.md
# expected: 1

# AC-11 — branch pushed; PR head equals local HEAD
test "$(git rev-parse feat/registry)" = "$(gh pr view 27 --json headRefOid -q .headRefOid)" && echo SYNCED
# expected stdout: SYNCED

# AC-12 — full quality gate green at the merged HEAD
make check >/dev/null 2>&1 && echo CHECK_OK
# expected stdout: CHECK_OK

# AC-13 — registry framework unchanged & under ceilings (regression guard)
python scripts/check-module-size.py >/dev/null 2>&1 && echo SIZE_OK
# expected stdout: SIZE_OK
python -c "import personalscraper" && echo IMPORT_OK
# expected stdout: IMPORT_OK
```

---

## 6. Trade-offs & alternatives

- **Ship Phase 30 in this PR vs a separate PR.** Operator already elected in-PR (`phase-30…:6-7`). _Pro_: the dedup bug never reaches main even transiently; one squash. _Con_: the PR identity blurs (registry + an unrelated scraper fix). _Rejected_: split into PR #28 — would force re-pinning ACC twice and delay the registry merge for a small scraper change. In-PR is right for a mono-user pre-1.0 repo.
- **Manual squash vs `--no-ff` merge commit.** Squash collapses 203 commits (34 fix / 24 refactor / 29 test) → one; `git bisect` on main can only land on the squash commit. _Mitigation_: per-phase plan files + the IMPLEMENTATION.md review-cycle log preserve the narrative. _Alternative_: `--no-ff` retains the graph for future registry-internals bisection at the cost of 203 noisy commits on main. Default (squash) is defensible; make it a deliberate, recorded decision.
- **Re-pin ACC now vs after Phase 30.** Re-pinning to 344 now (as the stale pass recommended) would drift again the moment A.4 adds an E2E test under `tests/e2e/`. _Decision_: re-pin once, after Phase 30, to the measured value.
- **Fix ACC-04b via `--config /nonexistent` vs documenting a precondition.** The flag approach keeps the criterion a single deterministic command (SH-16 ideal); the precondition-note approach is weaker (depends on the runner reading prose). Prefer the flag if `personalscraper info providers --config` exists.
- **Archive immediately post-merge vs defer to next feature.** Documented default is to fold the archive into the next feature's `/implement:create-branch` (via `prev_codename`). If no next feature starts soon, main sits with a live feature tracker. Immediate `/implement:archive` is cleaner but needs a non-main branch. Either is valid; pick one explicitly.

---

## 7. Effort & sequencing

**Overall: M–L.** The blocker is Phase 30 (real code across 3 production modules + 3 test files + matrix/agent docs), then trivial doc fixes, then the full-suite gate.

**Recommended order:**

1. **Phase A (Phase 30)** — heavy lift. A.2 → A.3 → A.4 → A.5 (A.4 depends on A.2/A.3; A.5 depends on A.2 for event names). One commit per sub-phase. **Run `make test` after each** — A.2 touches the live move path (highest regression risk).
2. **Phase B (doc fixes)** — quick wins, single commit, **after** Phase A so the ACC re-pin is correct (B.1 last within B).
3. **Phase C (gate + push + merge)** — `make check` once, push, confirm CI green at the real head, record the squash decision, squash-merge. Post-merge archival is a separate ≤S step.

**Quick wins** (≤S each): B.2 (ACC-04b), B.3 (DESIGN reconcile), B.4 (dedup Next-action), A.5 (matrix bump). **Heavy lifts**: A.2 (orphan unlink on the live path), A.4 (E2E harness), C.1 (full 5657-test + coverage gate, ~5–6 min).

---

## 8. Open questions

1. **CI at the real HEAD** — the green `gh pr checks 27` is for `348e4ed9` (Phase-29 gate). After Phase A + B + push, is CI green at the new head (with the scraper code change)? This is the gating signal, not the stale PR-API status.
2. **Full suite + coverage** — has `make test` (5657 tests) + `test-cov` branch-coverage ≥90% been confirmed green at the exact merged HEAD? Only ruff + 6 guards + the e2e/integration anchor (344) + registry units (59) were verified read-only.
3. **`--config` flag for ACC-04b** — does `personalscraper info providers` accept `--config`? If not, ACC-04b must document the "config-less clone" precondition instead.
4. **Squash vs `--no-ff`** — manual squash (default) or a merge commit to preserve the 203-commit graph (34 fix / 24 refactor / 29 test) for future bisection on main?
5. **Archival timing** — run `/implement:archive` immediately post-merge, or defer to the next feature's `create-branch`? Either way the stale `IMPLEMENTATION.md` already on main must be replaced.
6. **Dormant fan_out smoke test** — should the OMDB-gated `backfill_ids.py:637` fan_out path (never exercised in the default 2-provider config) get a smoke/integration test before P2/health work relies on it (RETROSPECTIVE Item #11)?
