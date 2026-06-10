# Implementation Progress — acquire-store

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP3 — acquire.db store + single deletion authority (minor)
**Version bump**: 0.25.0 → 0.26.0
**Branch**: feat/acquire-store
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/144
**Design**: docs/features/acquire-store/DESIGN.md
**Master plan**: docs/features/acquire-store/plan/INDEX.md

## Phases

| #   | Phase                                         | File                                | Status |
| --- | --------------------------------------------- | ----------------------------------- | ------ |
| 1   | core/sqlite extraction                        | phase-01-core-sqlite-extraction.md  | [x]    |
| 2   | core/identity + AcquireConfig + acquire.json5 | phase-02-identity-config.md         | [x]    |
| 3   | acquire/domain + schema + store               | phase-03-domain-schema-store.md     | [x]    |
| 4   | core/delete_permit + acquire/delete_authority | phase-04-delete-permit-authority.md | [x]    |
| 5   | Dispatch-time writer + per-site wiring        | phase-05-dispatch-wiring.md         | [x]    |
| 6   | Guardrails + docs + gate                      | phase-06-guardrails-docs-gate.md    | [x]    |
| 7   | PR review fixes — cycle 1                     | phase-07-pr-fixes-cycle-1.md        | [x]    |

## Review cycles

### Cycle 1

- Toolkit: 4 agents (silent-failure-hunter, code-reviewer, pr-test-analyzer, type-design-analyzer) on the feat/acquire-store diff (PR #144), focused on fail-open correctness, concurrency, real-API usage, layering. CI green at review time.
- Retained findings (all design-conformant — implementation did not match design intent; NO design contradiction):
  - **C1 (major)** `record_dispatch` correlates by `staging_source.stat().st_size`, but dispatch passes a directory → directory inode size never equals the torrent's `size_bytes` → no obligation ever written in production. Vacuous tests (single files, not dirs) masked it.
  - **C2 (major)** `library_clean` calls `clean_library(permit=…)` outside the `per_step_boundary` block → store closed before `may_delete` → swallowed → ALLOW → maintenance hard-skip can never fire.
  - **F1 (major)** `may_delete` path-exists guard (`Path(dp).exists()`) sits outside the fail-open `try/except` → can raise `OSError` (ENAMETOOLONG/EACCES) → fails CLOSED into the deleter.
  - **F2 (major)** permit consult sites (disk*cleaner `\_delete*\*`, dispatch `\_movie`/`\_tv`) unwrapped → a raising permit aborts cleanup/dispatch (DESIGN §7.3 requires the consult itself be fail-open).
  - **T1 (medium)** `SeedObligation.min_seed_time_s`/`min_ratio` have no `>= 0` guard; a negative value defeats the HnR comparison (`delete_authority.py:137`).
  - F3 (minor, folded in) `record_dispatch` correlation window (`is_seeding()`) unguarded vs the "never raises" contract.
- Decision: **Case B** (major/medium present). Fix phase 7 executed (2 Opus batches, 5 commits `b68855f5`→`eb9cbcf9`); regression test per bug (project rule).
- Fixes applied + independently re-verified:
  - **C1** `record_dispatch._staging_size` sums recursive file bytes for directory sources (stdlib `rglob`, no dispatch import) → matches the torrent `size_bytes`; verbatim-folder-torrent dispatch now records an obligation. Smoke: directory source → obligation row written.
  - **C2** `library_clean` runs `clean_library` + reporting **inside** the `per_step_boundary` block via `_run_and_report(permit)`; store stays open across `may_delete`; authority-build failure still fail-opens to `AllowAllPermit`; `clean_library`'s own errors re-raise. Smoke: descendant obligation → dir hard-skipped, `skipped_by_obligation=1`.
  - **F1** `may_delete` fail-open `try/except` widened over the whole obligation loop (`_evaluate_obligations`) → `Path.exists()` OSError → ALLOW (mutation-proven). **F3** correlation window (`_correlate_and_record`) made fully fail-soft (`is_seeding`/store-write errors → MISS, never raises).
  - **F2** every `permit.may_delete(...)` consult (disk*cleaner `\_delete*_`, dispatch `\_movie`/`\_tv`) wrapped → a raising permit → ALLOW + `_.permit_error` log, never aborts.
  - **T1** `SeedObligation.__post_init__` rejects negative `min_seed_time_s`/`min_ratio`; DB `CHECK` added to `001_init.sql`.
  - Closed the wiring test gaps that masked C2: DispatchStep authority forwarding (permit==recorder), factory economy-map construction.
- Gate: `make check` 6445 / `make test` 6603, 0 failed. Deleters still ⇏ acquire (layering green). Pushed; CI re-running. Merge = manual → operator squash-merges once CI green.

## Next action

Review cycle 1 fixes pushed + locally green. **Awaiting CI green on PR #144, then MANUAL squash merge** (`gh pr merge 144 --squash` or GitHub UI). After merge: next `/implement:feature` archives acquire-store.
