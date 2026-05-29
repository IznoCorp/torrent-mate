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

## Next action

Review converged (2 cycles). **Merge is BLOCKED only by GitHub Actions billing** (spending limit): the `test`/`security`/`coverage-merge` jobs cannot start. Static CI (lint, typecheck, design-gaps, licenses, secrets) is green. Action for the operator: fix Settings → Billing & plans, then re-run CI (`gh run rerun <id> --failed`) → green → manual squash-merge of PR #29.

> Phase 2 note (for Phases 3–5): `FilesystemCapability.fs_type` is `field(compare=False)`
> so `capability_for("unknown") == capability_for("ntfs_macfuse")` is `True` (behavioral
> equality — the restrictive-superset invariant). Capabilities are looked up by string key,
> never by object identity. Other fs-types remain distinct.
