# Implementation Progress — watch-seed

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Watcher Service + native cross-seeding for managed trackers
**Type**: feat
**Version bump**: 0.38.0 → 0.39.0 (minor)
**Branch**: feat/watch-seed
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/watch-seed/DESIGN.md
**Master plan**: docs/features/watch-seed/plan/INDEX.md

## Phases

| #   | Phase                                                | File                                    | Status |
| --- | ---------------------------------------------------- | --------------------------------------- | ------ |
| 1   | RP10a — TorrentLayout parser + structural match      | phase-01-rp10a-torrent-layout-parser.md | [x]    |
| 2   | RP10b — TorrentInjector protocol + QBitClient inject | phase-02-rp10b-torrent-injector.md      | [x]    |
| 3   | Cross-seed + watch configuration                     | phase-03-cross-seed-config.md           | [x]    |
| 4   | CrossSeedService — X1 core + X2 sweep                | phase-04-cross-seed-service.md          | [x]    |
| 5   | Cross-seed CLI + events                              | phase-05-cross-seed-cli-events.md       | [x]    |
| 6   | WatcherService pure state machine                    | phase-06-watcher-state-machine.md       | [ ]    |
| 7   | Watch command loop + watch-now + run flags           | phase-07-watch-loop.md                  | [ ]    |
| 8   | PM2 ecosystem + launchd decommission                 | phase-08-pm2-launchd-cutover.md         | [ ]    |
| 9   | E2E roundtrip + ACCEPTANCE gate                      | phase-09-e2e-acceptance-gate.md         | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Phase 6 (WatcherService state machine) is next — continue via `/implement:phase`.
