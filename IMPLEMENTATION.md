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
| 9   | PR fixes cycle 1                         | [phase-09-pr-fixes-cycle-1.md](docs/features/media-indexer/plan/phase-09-pr-fixes-cycle-1.md)                 | [ ]    |

## Review cycles

### Cycle 1

- Findings received: ~80 raw (5 review agents)
- Retained: 6 (2 critical, 4 major, 0 medium, ~20 reclassified to minor / deferred)
- Ignored: many out-of-scope (style preferences not codified, pre-existing items on main)
- Fix phase created: phase-09-pr-fixes-cycle-1.md
- Status: fix phase dispatched → awaiting /implement:phase

**Critical**:

- C1: `outbox.publish_event`/`disk_id_for_path` ignore configured `db_path` (DESIGN §9.4)
- C2: `library/scanner.scan_library` hardcodes `generation=1` (DESIGN §8.1)

**Major**:

- M1: SQL f-string interpolation in `_apply_artwork_write` without kind whitelist
- M2: `MediaIndex` sqlite connection leak (no close/`__exit__`)
- M3: `_inventory_artwork`/`_check_nfo_status` overwrite valid data on transient OSError
- M4: `scan()` swallows exceptions, contradicting documented re-raise contract

**Deferred to follow-up PR** (~30 items): type-design tightening (Literal aliases / bool conversions / frozen dataclasses), observability gaps (log level / `exc_info=True` / `error_type`), comment sweep (orphan plan refs / outdated docstrings), CLI cosmetic fixes, test-coverage suggestions.

## Next action

All phases complete — run `/implement:feature-pr`.
