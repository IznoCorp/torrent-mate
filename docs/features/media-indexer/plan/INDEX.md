# Media Indexer — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan phase-by-phase.

**Feature:** `media-indexer`
**Branch:** `feat/media-indexer`
**Version bump:** `0.7.0 → 0.8.0`
**Design:** `docs/features/media-indexer/DESIGN.md`

---

## Phases

| #   | Phase                                    | File                                                                         | Status |
| --- | ---------------------------------------- | ---------------------------------------------------------------------------- | ------ |
| 0   | Config Overhaul                          | [phase-00-config-overhaul.md](phase-00-config-overhaul.md)                   | [ ]    |
| 1   | Indexer Core: DB layer                   | [phase-01-db-layer.md](phase-01-db-layer.md)                                 | [ ]    |
| 2   | Indexer Core: Scanner (full + quick)     | [phase-02-scanner-full-quick.md](phase-02-scanner-full-quick.md)             | [ ]    |
| 3   | Indexer Core: Drift + Reconciliation     | [phase-03-drift-reconciliation.md](phase-03-drift-reconciliation.md)         | [ ]    |
| 4   | Performance + Incremental + Enrich modes | [phase-04-perf-incremental-enrich.md](phase-04-perf-incremental-enrich.md)   | [ ]    |
| 5   | Outbox + Write-through                   | [phase-05-outbox-writethrough.md](phase-05-outbox-writethrough.md)           | [ ]    |
| 6   | Consumer migration: dispatch             | [phase-06-migrate-dispatch.md](phase-06-migrate-dispatch.md)                 | [ ]    |
| 7   | Consumer migration: library + trailers   | [phase-07-migrate-library-trailers.md](phase-07-migrate-library-trailers.md) | [ ]    |
| 8   | CLI + cron + query language              | [phase-08-cli-cron-query.md](phase-08-cli-cron-query.md)                     | [ ]    |

---

## Execution order

Phases are **strictly sequential** — each phase's Gate must pass before the next phase begins. The gate for each phase is listed at the top of its file.

## Commit convention

All commits use scope `media-indexer`:

```
{type}(media-indexer): description
```

Types: `feat | fix | chore | refactor | docs | test | perf | build`

## Key invariants across all phases

- The **disks remain SSOT** — the indexer is a queryable mirror, never authoritative.
- **No coexistence period** — legacy JSON files (`media_index.json`, `library_scan.json`, `library_analysis.json`) are removed in Phases 6–7 with no grace period.
- **Outbox tests live in `tests/integration/`**, never in `tests/dispatch/` (preserves the test-realism trim from PR #14).
- **`library.db` must always live on the internal APFS disk** — loader rejects any `db_path` on a macFUSE-NTFS volume.
- **Spotlight is NOT used on macFUSE storage disks** — dir-mtime walk is always the storage-disk change-detection path.
