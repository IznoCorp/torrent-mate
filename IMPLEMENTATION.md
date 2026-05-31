# Implementation Progress — lib-fold

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Library / Indexer Consolidation (minor)
**Version bump**: 0.18.0 → 0.19.0
**Branch**: feat/lib-fold
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/lib-fold/DESIGN.md
**Master plan**: docs/features/lib-fold/plan/INDEX.md

## Phases

| #   | Phase                                                            | File                                  | Status |
| --- | ---------------------------------------------------------------- | ------------------------------------- | ------ |
| 0   | Season-dir SSOT (widen-first) + VIDEO_EXTENSIONS                 | phase-00-season-ssot.md               | [x]    |
| 1   | Extract NFO helpers → nfo_utils                                  | phase-01-nfo-helpers.md               | [x]    |
| 2   | Build \_item_stage + \_canonical; rewire scan_library (parallel) | phase-02-item-stage.md                | [x]    |
| 3   | Single-creator cutover: dispatch + alias + delete scanner.py     | phase-03-single-creator-cutover.md    | [x]    |
| 4   | ffprobe fold + insights/                                         | phase-04-ffprobe-insights.md          | [ ]    |
| 5   | verify/maintenance re-home + no-NFO + delete library/            | phase-05-verify-maintenance-delete.md | [ ]    |
| 6   | Feature PR + review (auto-invoked)                               | phase-06-feature-pr.md                | [ ]    |

## Design & plan review (2026-05-31, pre-implementation)

Design + plan were reviewed collaboratively before Phase 0 — more rigorous than the default flow.

**DESIGN review:**

- Interactive brainstorm → **8 decisions** resolved, each user-approved: single `media_item` creator; kind-deterministic canonical SSOT; NFO-less dirs indexed (folder-name fallback) + flagged (`item_issue`/`nfo_missing`) + proactive `doctor`/`audit` visibility; HDR/Atmos via the **existing** `media_stream` columns; `insights/` move-only; `maintenance/` = `disk_cleaner` + `rescraper`; `library-scan` visible re-pointed alias; `models.py` split by producer/consumer.
- **Adversarial self-review** (3 lenses: grounding / consistency / ACC executability) caught **2 real errors** + 8 grounding fixes:
  - HDR/Atmos columns (`hdr_format`/`is_atmos`) **already exist** (migration 004, populated by `enrich`) → decision reframed from "add columns" to "ensure enrich parity with the dropped ffprobe granularity".
  - Canonical `SEASON_DIR_RE` is **French-only** `^Saison (\d+)$`; three ad-hoc copies also match English `Season N` + `Specials` → **Phase 0 must widen before replacing** (silent-regression trap).
  - Also: `load_config` import path (`conf.loader`), `incremental.py:667` anchor, canonical trigger = manual `library-init-canonical` (not a scheduled job), completed `models.py` routing, existing `nfo_utils.py` path.
- Merged the pre-existing 619-line draft (committed in #27, v0.16→0.17, which carried the same HDR/regex errors) — best of both: its implementation-grade detail + the validated corrections.

**PLAN review:**

- 7 phases (0→6) generated, then verified for fidelity: strict 0→6 order; Phase 0 widen-first; Phase 2 parallel + characterization golden (no deletion); Phase 3 cutover (single creator, visible alias, delete `scanner.py`); Phase 4 no-new-columns + `hdr_format` parity; every phase opens with a Gate. All 16 ACC mapped.

**Outcome:** design + plan **approved**, ready for implementation. Invariants carried forward: DB end-state equality vs `library-scan` (Phase 2), 194-show + DEV#50 guards verbatim, residual-import grep = 0, `make check` per gate.

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

**Phase 4** (ffprobe fold + `insights/`). Start at `docs/features/lib-fold/plan/phase-04-ffprobe-insights.md`.

### Phase 3 — DONE (2026-05-31, single-creator cutover; independently verified at HEAD)

All five tasks complete; each sub-dispatch was verified against DESIGN + plan by the main session (git range, scope, quality gate re-run, honesty audit of every migrated/weakened assertion) before proceeding.

- ✅ **Task 1+2** (pre-existing): dispatch `rebuild()`/`add()` delegate to the shared `upsert_item_with_attrs` (rich rows; `canonical_provider=None` eliminated — ACC-04b ✓). Regression test `tests/dispatch/test_media_index_rich_rows.py`. Commits `3d54ba8c`/`b73a141c`/`0784850d`.
- ✅ **Task 3** — `library-scan` is now a **visible alias** of `library-index --mode full`, delegating to the shared `library_index_command(mode="full", …)` (NOT the stale plan's `commands/library/index.py` import nor a direct decorated-function call — that was a Typer `OptionInfo` trap). `tests/commands/test_library_scan.py` + `_e2e.py` rewritten to the delegation contract. Commit `5731e398`.
- ✅ **Task 4** (irreversible) — `personalscraper/library/scanner.py` **deleted** (`a487fd88`), in three verified steps: (4a) golden `test_item_stage_golden.py` **decoupled** from the live `scan_library` by freezing a verbatim-captured legacy baseline snapshot (`89267d1e`); (4b) unique scanner coverage **migrated** to `tests/indexer/scanner/_modes/test_item_stage.py` (+24 tests against `stage_library_items`/`scan_and_stage_dir`/`_detect_issues`/`_ensure_disk_row`) and `tests/test_nfo_utils.py` (+12) — full coverage-mapping table audited, `_item_stage.py` at 92.81% (`09aef064`); (4c) `test_integration.py` re-pointed to `stage_library_items`, arch `test_event_bus_required_signatures.py` entry removed, `test_scanner.py` deleted.
- ✅ **Task 5 gate (independently re-run by main session):** `make lint` clean · `make test` **5972 passed, 0 failed, 0 errors** · `make check` rc=0, **coverage 91.74%** (≥90). Module-size: only the pre-existing `movie_service.py` (975) WARN remains (out of lib-fold scope).

**Two documented incoherence-fixes (the only deviations from literal plan/DESIGN text, both signed off):**

1. **ACC-04 re-scoped** (operator sign-off — same precedent as the ACC-02 fix): the broad `rg 'library.scanner|scan_library'` → rc=1 form is **unsatisfiable** (the `trailers` subsystem has its own unrelated `Scanner.scan_library` method; `library/analyzer.py` keeps `:func:` docstrings until Phase 4; `.` is a regex wildcard). Re-scoped to the satisfiable, intent-preserving form: **file gone + no LIVE import of the deleted module** (`rg 'from personalscraper\.library\.scanner|import personalscraper\.library\.scanner'` → rc=1, verified). DESIGN.md + plan-03 synced.
2. **`library-scan --disk X` semantic shift** (DESIGN-conformant consequence of OQ-4, not a regression): the legacy alias filtered `cfg.disks` so `--disk` restricted `media_item` creation; the delegated `library-index --mode full` runs its item stage (pass 1) **library-wide** (DESIGN §4.1/§5 — `stage_items_pass1` has no `disk_filter`), so `--disk` now restricts only the file-level walk (`path`/`media_file`). No cron/launchd job uses `library-scan --disk` (DESIGN §3.6); pre-1.0, no back-compat.

## Phase 0/1/2 — corrective closure (2026-05-31, post-audit, NO DEFERRAL)

An independent adversarial audit found the original phase 0/1/2 gate commits had been stamped **before** some planned objectives/ACC were complete (false-greens at the time). Per the user's directive ("respecter le design — Option A; sans déférer"), **every gap was closed at HEAD by building exactly what DESIGN+plan specify** (not by amending the design away), then re-verified COMPLETE by a fresh independent audit (all P0/P1/P2 objectives DONE + all ACC PASS at HEAD).

| Gap (audit)                                                                                                          | Sev         | Closure                                                                                                                                                                                                | Commit     |
| -------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| P0 `SEASON_DIR_RE` shipped `\s+`, narrowing out no-space forms the ad-hoc copies matched (DESIGN §3.4 parity broken) | minor       | restored `\s*` + no-space test cases                                                                                                                                                                   | `3b98290e` |
| P1 scanner.py still **defined** the 3 NFO helpers (duplication, not SSOT)                                            | blocker     | helpers now **import** from `nfo_utils` (SSOT); `test_scanner.py` repointed                                                                                                                            | `0b975e51` |
| P1 ACC-02 broad form unsatisfiable / failing                                                                         | blocker     | rescoped to NFO-helpers (incoherence) + `validator.py` inventory + DESIGN.md ACC-02 synced                                                                                                             | `b80d1725` |
| P2 obj #5 — `scan_library` not single-writer                                                                         | blocker     | `_upsert_media_item` **delegates** to shared `upsert_item_with_attrs`; dead `_normalize_canonical_provider` removed                                                                                    | `a01bc3a0` |
| P2 `full.py` unmodified (pass-1 in command layer, diverged from DESIGN §4.1/§5)                                      | blocker     | pass-1 → `full.stage_items_pass1`, invoked **once** by `scan()` via new optional `config` param                                                                                                        | `f73abf1c` |
| P2 no end-to-end pass-1 test (MAJOR) + golden weaker than DESIGN §4.3 + marker unregistered                          | major/minor | `test_full_pass1_integration.py` (real `scan(mode=full, config=cfg)`); golden → **real** `scan_library` baseline (monkeypatched `_indexer_scan`) + full §4.3 snapshot; `integration` marker registered | `8df8828c` |

**Two authorized incoherence-fixes** (the only deviations from literal DESIGN text, both documented): ACC-02 rescope (the broad form is unsatisfiable while `scan_library` lives) and the golden's **bounded** `item_issue` superset (DESIGN decision #3 mandates the new path _adds_ `nfo_missing` for NFO-less dirs — surfaced honestly by the hardened test, every other field asserted byte-identical).

**Re-gate after corrections:** `make lint` clean · `make test` **5986 passed, 0 failed** · `make check` (coverage ≥ 90 %; module-size OK <1000 — `scanner.py` dropped below 800 after the helper/`_normalize_canonical_provider` removal; registry/typed-api/pragma/CLI guardrails OK). Pre-existing `movie_service.py` (975) WARN remains (out of lib-fold scope).
