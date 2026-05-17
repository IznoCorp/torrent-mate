# Implementation Progress — provider-ids

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `provider-ids`
**Feature**: Multi-Provider IDs Propagation + Capabilities Refactor (type: minor)
**Version bump**: 0.14.0 → 0.15.0
**Branch**: feat/provider-ids
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/provider-ids/DESIGN.md
**Master plan**: docs/features/provider-ids/plan/INDEX.md

## Phases

| #   | Phase                                                         | File                                  | Status |
| --- | ------------------------------------------------------------- | ------------------------------------- | ------ |
| 1   | Capabilities Protocols (api/\_contracts.py + per-domain)      | phase-01-capabilities-protocols.md    | [ ]    |
| 2   | Fix DEV #2 — IDs propagation (regression tests first)         | phase-02-fix-dev2-ids-propagation.md  | [ ]    |
| 3   | Façades IMDb + RottenTomatoes (sur OMDbAdapter)               | phase-03-imdb-rt-facades.md           | [ ]    |
| 4   | Drift validator renforcé (canonical uniqueid required)        | phase-04-drift-validator-hardening.md | [ ]    |
| 5   | Xref enrichment sequential + \_resolve_external_ids           | phase-05-xref-enrichment.md           | [ ]    |
| 6   | NFO ratings multi-source + uniqueid default canonical         | phase-06-nfo-ratings-multisource.md   | [ ]    |
| 7   | DB schema — external_ids_json + ratings_json + canonical_prov | phase-07-db-schema-external-ids.md    | [ ]    |
| 8   | Backfill mode + CLI + auto-trigger post-scrape                | phase-08-backfill-mode.md             | [ ]    |
| 9   | Verify checker — 3 nouveaux checks                            | phase-09-verify-checker-extensions.md | [ ]    |
| 10  | Consommateurs library/conf/trailers refactor                  | phase-10-consumers-refactor.md        | [ ]    |
| 11  | Tracker capabilities + LaCale/C411 refactor                   | phase-11-tracker-capabilities.md      | [ ]    |
| 12  | Tracker registry priority-aware par type de média             | phase-12-tracker-registry-priority.md | [ ]    |
| 13  | Torrent capabilities + QBit/Transmission refactor             | phase-13-torrent-capabilities.md      | [ ]    |
| 14  | Notify capabilities + Telegram/Healthchecks refactor          | phase-14-notify-capabilities.md       | [ ]    |
| 15  | Integration + E2E + final wire                                | phase-15-integration-e2e.md           | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 1.
