# Implementation Progress — media-indexer

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Media Indexer + Config Overhaul (minor)
**Version bump**: 0.7.0 → 0.8.0
**Branch**: feat/media-indexer
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/16
**Design**: docs/features/media-indexer/DESIGN.md
**Master plan**: docs/features/media-indexer/plan/INDEX.md

## Phases

| #   | Phase                                    | File                                                                                                          | Status |
| --- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------ |
| 0   | Config Overhaul                          | [phase-00-config-overhaul.md](docs/features/media-indexer/plan/phase-00-config-overhaul.md)                   | [x]    |
| 1   | Indexer Core: DB layer                   | [phase-01-db-layer.md](docs/features/media-indexer/plan/phase-01-db-layer.md)                                 | [x]    |
| 2   | Indexer Core: Scanner (full + quick)     | [phase-02-scanner-full-quick.md](docs/features/media-indexer/plan/phase-02-scanner-full-quick.md)             | [x]    |
| 3   | Indexer Core: Drift + Reconciliation     | [phase-03-drift-reconciliation.md](docs/features/media-indexer/plan/phase-03-drift-reconciliation.md)         | [x]    |
| 4   | Performance + Incremental + Enrich modes | [phase-04-perf-incremental-enrich.md](docs/features/media-indexer/plan/phase-04-perf-incremental-enrich.md)   | [x]    |
| 5   | Outbox + Write-through                   | [phase-05-outbox-writethrough.md](docs/features/media-indexer/plan/phase-05-outbox-writethrough.md)           | [x]    |
| 6   | Consumer migration: dispatch             | [phase-06-migrate-dispatch.md](docs/features/media-indexer/plan/phase-06-migrate-dispatch.md)                 | [x]    |
| 7   | Consumer migration: library + trailers   | [phase-07-migrate-library-trailers.md](docs/features/media-indexer/plan/phase-07-migrate-library-trailers.md) | [x]    |
| 8   | CLI + cron + query language              | [phase-08-cli-cron-query.md](docs/features/media-indexer/plan/phase-08-cli-cron-query.md)                     | [x]    |
| 9   | PR fixes cycle 1                         | [phase-09-pr-fixes-cycle-1.md](docs/features/media-indexer/plan/phase-09-pr-fixes-cycle-1.md)                 | [x]    |
| 10  | PR fixes cycle 2 (smoke-test bugs)       | [phase-10-pr-fixes-cycle-2.md](docs/features/media-indexer/plan/phase-10-pr-fixes-cycle-2.md)                 | [x]    |

## Review cycles

### Cycle 1

- Findings received: ~80 raw (5 review agents)
- Retained: 6 (2 critical, 4 major, 0 medium, ~20 reclassified to minor / deferred)
- Ignored: many out-of-scope (style preferences not codified, pre-existing items on main)
- Fix phase created: phase-09-pr-fixes-cycle-1.md
- Status: fix phase complete → /implement:feature-pr re-running for cycle 2

**Critical**:

- C1: `outbox.publish_event`/`disk_id_for_path` ignore configured `db_path` (DESIGN §9.4)
- C2: `library/scanner.scan_library` hardcodes `generation=1` (DESIGN §8.1)

**Major**:

- M1: SQL f-string interpolation in `_apply_artwork_write` without kind whitelist
- M2: `MediaIndex` sqlite connection leak (no close/`__exit__`)
- M3: `_inventory_artwork`/`_check_nfo_status` overwrite valid data on transient OSError
- M4: `scan()` swallows exceptions, contradicting documented re-raise contract

**Deferred to follow-up PR** (~30 items): type-design tightening (Literal aliases / bool conversions / frozen dataclasses), observability gaps (log level / `exc_info=True` / `error_type`), comment sweep (orphan plan refs / outdated docstrings), CLI cosmetic fixes, test-coverage suggestions.

### Cycle 2

- Findings received: focused review of cycle 1 fix commits (f10100d..51f32e1)
- Retained: 0 (0 critical, 0 major, 0 medium, 1 reclassified to minor)
- Reclassified to minor / deferred: 1 — `scraper/artwork.py` publishes `kind="thumb"` / `kind="unknown"` for unmatched filename stems; after M1's whitelist these now produce permanent `status='failed'` outbox rows instead of silent JSON garbage. Producer bug pre-dates cycle 1. Recommendation: whitelist at publisher (skip `publish_event` when kind unrecognised) or normalise stems before publishing. Does not block merge.
- Cycle 1 fixes verified: all 6 (C1, C2, M1, M2, M3, M4) plus the regression guard correctly resolve the cycle 1 findings with adequate test coverage.
- Status: clean — proceeding to merge handoff (manual mode)

### Cycle 3

- Findings received: focused review of phase-10 commits (51f32e1..8ae99c2)
- Retained: 0 (0 critical, 0 major, 0 medium)
- Reclassified to minor / deferred: 3 — (a) false positive on `_resolve_volume_root` "duplication" (it's imported from merkle in cli.py:33); (b) `mount_path` stored as configured subdir while sentinel lives at volume root — intentional design decision in 10.4, doc could clarify; (c) `[unmatched] <name>` detail string parsing is brittle — future refactor target (typed `StepReport.unmatched_paths` field) but not a current bug.
- Phase 10 fixes verified: 5 sub-phases (10.1–10.5) all solve their stated problems with adequate test coverage. No regressions introduced.
- Status: clean — proceeding to merge handoff (manual mode)

### Cycle 4 — deferred-items follow-up (2026-04-30)

Cleanup of all minor / deferred items rolled up across cycles 1–3 (≈30 items).
Single non-milestone working session, full test suite green (2373 passed, 17 skipped, 0 failed).

- **Cycle 2 producer guard** — `scraper/artwork.py` now resolves `kind` via a stem→whitelisted-kind table (`poster`, `landscape`, `fanart`, `backdrop`, `banner`, `clearlogo`, `clearart`, `discart`, `characterart`) and skips `publish_event` when the stem matches none. Eliminates the permanent-`failed` outbox rows for `thumb`/`unknown` previously emitted at the producer side. Test `tests/integration/test_outbox_writethrough_artwork.py::test_kind_derivation` rewritten to assert both whitelisted kinds and unrecognised-skip behaviour.
- **Cycle 3 — mount_path doc clarification** — `DiskRow.mount_path` and the DESIGN §6.2 schema comment now explicitly document the two-level model (`mount_path` = configured scan root, sentinel/diskutil resolve volume root via `_resolve_volume_root`).
- **Cycle 3 — typed `StepReport.unmatched_paths`** — new typed field on `StepReport`, populated in `scraper/run.py::_to_step_report`, consumed directly by `process/run.py` instead of grepping the `[unmatched] <name>` detail strings. Detail strings kept for human reporting.
- **Type design tightening** — added `Literal` aliases in `indexer/schema.py` (`MediaItemKind`, `NfoStatus`, `OutboxSource`, `OutboxOp`, `OutboxStatus`, `ScanMode`, `ScanStatus`, `RepairScope`, `RepairQueueStatus`, `DeletedKind`, `StreamKind`) and applied them on the corresponding row dataclass fields. Marked `ScanRunResult` `frozen=True` (no mutation observed at any call site).
- **Observability gaps** — added `error_type=type(exc).__name__` and `exc_info=True` on the `log.warning` / `log.error` sites in `outbox.py`, `db.py`, `drift.py`, `scanner/_db_writes.py`. The structured event names were already in place; this completes the payload.
- **Comment sweep** — removed orphan plan-phase markers in `scanner/_types.py::ScanMode` and `scanner/_walker.py`; updated the `F_RDADVISE` references in `conf/models.py` and `indexer/mediainfo.py` to point at the actual `mmap+madvise(MADV_SEQUENTIAL)` implementation in `_macos_io.sequential_hint`.
- **`library_search` CLI fix** — header dropped the bogus `TRAILER` column and re-aligned widths so they match the data row in a fixed-width terminal; docstring updated to reflect the actual 4 columns (`id | title | year | nfo`).
- **`apply_migrations` closed-connection invariant** — `Raises:` section now spells out that the connection is `.close()`-d before re-raising `IndexerMigrationError`, so callers must re-open via `open_db` (matching the inline comment that was already at the failure path).

Verification: `ruff check personalscraper/` clean; full non-e2e pytest suite green.

## Next action

All phases complete — run `/implement:feature-pr`.
