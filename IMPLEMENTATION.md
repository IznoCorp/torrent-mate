# Implementation Progress — multi-filesystem

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Multi-Filesystem Support (FilesystemCapability Layer) (minor)
**Version bump**: 0.17.0 → 0.18.0
**Branch**: feat/multi-filesystem
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/29
**Design**: docs/features/multi-filesystem/DESIGN.md
**Master plan**: docs/features/multi-filesystem/plan/INDEX.md

## Phases

| #   | Phase                                                       | File                            | Status |
| --- | ----------------------------------------------------------- | ------------------------------- | ------ |
| 1   | Consolidate 3 mount-parsers into one cached FsProbe         | phase-01-fs-probe.md            | [x]    |
| 2   | Define the FilesystemCapability strategy table              | phase-02-fs-capability.md       | [x]    |
| 3   | Make \_transfer rsync/rsync_merge consume the capability    | phase-03-transfer-capability.md | [x]    |
| 4   | Optional DiskConfig.fs_type override + plumb capabilities   | phase-04-diskconfig-override.md | [x]    |
| 5   | Make indexer tier-1 drift FS-aware (higher risk, deferable) | phase-05-drift-fs-aware.md      | [x]    |
| 6   | Multi-FS test harness + SH-16 ACCEPTANCE + docs             | phase-06-test-harness-docs.md   | [x]    |
| 7   | Feature PR + review                                         | phase-07-feature-pr.md          | [ ]    |

## Review cycles

### Cycle 1 (2026-05-29)

Reviewers: code-reviewer (no critical/major; re-verified NTFS byte-identical vs `main`), silent-failure-hunter, type-design-analyzer, pr-test-analyzer.

Retained + fixed:

- **MAJOR** — `DiskConfig.fs_type` had no validation; a typo (`"ntfs"`, `"APFS"`, `"apfs "`) silently degraded to NTFS-safe `unknown`. Fixed: `Literal[...] | None` → fails loud at config load (enforces the documented "must be a canonical key"). `[24367636]`
- **MEDIUM** — `_run_mount` swallowed all exceptions at DEBUG + `lru_cache`-poisoned a hung `mount`. Fixed: narrow to `(TimeoutExpired, OSError)`, WARNING on timeout/failure; unexpected errors propagate. `[24367636]`
- **MEDIUM (regression net)** — pinned the missed-drift coarse-FS limitation (same-size within-bucket content change), quick-mode paranoia coarse-FS coverage, size-trips-bucket unit, exFAT real-drift→repair, two-disk per-disk override, hash/set-collapse intent. `[4f4ae92b]`

Declined (with reason): `open_db` defense-in-depth no-op (pre-existing, not introduced here; conf validator is the real gate and covers it; FIX-2's WARNING now surfaces the probe failure); redundant boolean fields (over-engineering); `_NTFS_ILLEGAL` duplication (no defect); Optional-style cosmetics.

### Cycle 2 (2026-05-29) — CONVERGED

Adversarial verification of `24367636` + `4f4ae92b`: all fixes correct, complete, no regression. Missed-drift pin confirmed a true pin (real content change, real oshash, mtime truly in-bucket); per-disk override confirmed truly per-disk. No remaining critical/major/medium → loop exits.

Gate after fixes: `make check` exit 0 (5893 passed), `pytest -m multifs` 134 passed.

### Cycle 3 (2026-05-29) — adversarial retrospective + full remediation (phase 8)

A 5-lens adversarial retrospective (design / scope / tests / bugs / docs-process) found the cycle-1/2 review (and the orchestrator) had MISSED that the feature's headline objective was only half-delivered. Plan + execution at `docs/features/multi-filesystem/plan/phase-08-retro-fixes.md`. All fixed (10 commits `9d8c14cc`..`61b39b4f`):

- **(botched → fixed) Gating layer was NOT FS-aware.** merkle root, merkle delta (bulk-change freeze), and dir-mtime subtree skip all compared RAW mtime, so on a coarse FS the per-file FS-aware compare was never reached → perpetual rehash persisted + spurious `DiskBulkChangeDetected` freeze risk. Now `_build_disk_fingerprints`/`_sample_fresh_fingerprints` bucket mtime via the disk capability; root/delta/dir-mtime + the full-scan root store are all FS-aware. NTFS byte-identical (gran=1 identity), pinned by `test_merkle_fs_aware.py`. The quick-mode walk capability (phase-05 Task 2.3) was also finally threaded.
- **(botched → fixed) AC-05 not delivered end-to-end.** The illegal-name gate ran before disk selection with a hardcoded NTFS regex. Moved after dest resolution in `_movie.py`/`_tv.py`; uses the resolved `capability.illegal_name_regex`. Colon names now allowed on APFS, skipped on NTFS — proven end-to-end (`test_illegal_name_fs_aware.py`).
- **(botched → fixed) "never diverge" was false.** Override map was keyed on the mutable `disk.mount_path`. Re-keyed on the stable `DiskConfig.id` (== `DiskRow.label`) via `build_fs_type_overrides`; divergence test proves the override survives a mount_path change.
- **(botched → fixed) DESIGN.md lied** (never touched on the branch): described `reconcile_file` (dead code) as the drift target and version 0.17.0. Rewritten to the shipped reality (normalize_tier1 + FS-aware gating; reconcile_file = untouched dead code; 0.18.0). phase-05/06/07/INDEX + indexer.md + storage.md reconciled too.
- **(improvable → fixed)** dead `forbids_*` fields → derived `@property`; dispatcher resolve E2E test; canonical-fs_type boundary test; full→incremental no-op handoff test; AC-09 count refreshed (→150).

Gate: `make check` exit 0 (5751 passed cov-run), `pytest -m multifs` 150 passed, design-gaps AUDIT=0 FM=0, NTFS byte-identical re-verified (merkle + tier1 + rsync).

### Cycle 4 (2026-05-30) — re-review caught a phase-8 REGRESSION, fixed

A 4-lens adversarial re-review confirmed the phase-8 scanner fix is correct + NTFS byte-identical, but found phase-8 was **incomplete**: the merkle root is computed in FOUR places and phase-8 only bucketed two (scanner build + finalize). The other two stayed RAW → on an auto-detected coarse FS the bucketed-stored root permanently mismatched the raw-recomputed root (a regression vs pre-phase-8, where all four were raw and agreed):

- **(major regression → fixed)** `reconcile.detect_merkle_drift` → `library doctor` warned false merkle-drift after every clean scan on exFAT/HFS+. Now routes through the shared `_build_disk_fingerprints(conn, disk_id, capability)` with per-disk `resolve_capability`; override threaded from `doctor` (keyed on stable `DiskRow.label`).
- **(major regression → fixed)** `repair._refresh_disk_merkle` wrote a RAW root after repairs → defeated the next scan's short-circuit. Now FS-aware (auto-detect; the `drain` processor protocol has no override channel — documented, matches the scanner for the no-override case).
- **(should-fix → fixed)** docs over-claim corrected (all three consumers now named as co-bucketers); AC-05 skip-reason precedence pinned (disk-full beats illegal-name).

`8ed5f389`..`bb8a8e8e`. Gate: `make check` exit 0 (5918 passed), `pytest -m multifs` 159, design-gaps AUDIT=0 FM=0, NTFS byte-identical re-verified for both new consumers. The regression-guard tests fail without the fix (verified via git stash).

## Next action

Review converged after **3 cycles**; the retrospective remediation closed the half-delivered headline. **Merge is BLOCKED only by GitHub Actions billing** (spending limit): the `test`/`security`/`coverage-merge` jobs cannot start. Static CI (lint, typecheck, design-gaps, licenses, secrets) is green. Action for the operator: fix Settings → Billing & plans, then re-run CI (`gh run rerun <id> --failed`) → green → manual squash-merge of PR #29.

> Phase 2 note (for Phases 3–5): `FilesystemCapability.fs_type` is `field(compare=False)`
> so `capability_for("unknown") == capability_for("ntfs_macfuse")` is `True` (behavioral
> equality — the restrictive-superset invariant). Capabilities are looked up by string key,
> never by object identity. Other fs-types remain distinct.
