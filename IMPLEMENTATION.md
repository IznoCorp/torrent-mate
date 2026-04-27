# Implementation Progress — media-indexer

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Media Indexer + Config Overhaul (minor)
**Version bump**: 0.7.0 → 0.8.0
**Branch**: feat/media-indexer
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/media-indexer/DESIGN.md
**Master plan**: docs/features/media-indexer/plan/INDEX.md

## Phases

| #   | Phase                                    | File                                                                                                          | Status |
| --- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------ |
| 0   | Config Overhaul                          | [phase-00-config-overhaul.md](docs/features/media-indexer/plan/phase-00-config-overhaul.md)                   | [x]    |
| 1   | Indexer Core: DB layer                   | [phase-01-db-layer.md](docs/features/media-indexer/plan/phase-01-db-layer.md)                                 | [x]    |
| 2   | Indexer Core: Scanner (full + quick)     | [phase-02-scanner-full-quick.md](docs/features/media-indexer/plan/phase-02-scanner-full-quick.md)             | [x]    |
| 3   | Indexer Core: Drift + Reconciliation     | [phase-03-drift-reconciliation.md](docs/features/media-indexer/plan/phase-03-drift-reconciliation.md)         | [x]    |
| 4   | Performance + Incremental + Enrich modes | [phase-04-perf-incremental-enrich.md](docs/features/media-indexer/plan/phase-04-perf-incremental-enrich.md)   | [ ]    |
| 5   | Outbox + Write-through                   | [phase-05-outbox-writethrough.md](docs/features/media-indexer/plan/phase-05-outbox-writethrough.md)           | [ ]    |
| 6   | Consumer migration: dispatch             | [phase-06-migrate-dispatch.md](docs/features/media-indexer/plan/phase-06-migrate-dispatch.md)                 | [ ]    |
| 7   | Consumer migration: library + trailers   | [phase-07-migrate-library-trailers.md](docs/features/media-indexer/plan/phase-07-migrate-library-trailers.md) | [ ]    |
| 8   | CLI + cron + query language              | [phase-08-cli-cron-query.md](docs/features/media-indexer/plan/phase-08-cli-cron-query.md)                     | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 4 (Performance + Incremental + Enrich modes).
