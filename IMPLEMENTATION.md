# Implementation Progress — watch-seed

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Watcher Service + native cross-seeding for managed trackers
**Type**: feat
**Version bump**: 0.38.0 → 0.39.0 (minor)
**Branch**: feat/watch-seed
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/212
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
| 6   | WatcherService pure state machine                    | phase-06-watcher-state-machine.md       | [x]    |
| 7   | Watch command loop + watch-now + run flags           | phase-07-watch-loop.md                  | [x]    |
| 8   | PM2 ecosystem + launchd decommission                 | phase-08-pm2-launchd-cutover.md         | [x]    |
| 9   | E2E roundtrip + ACCEPTANCE gate                      | phase-09-e2e-acceptance-gate.md         | [x]    |
| 10  | PR fixes cycle 1                                     | phase-10-pr-fixes-cycle-1.md            | [ ]    |

## Review cycles

### Cycle 1

- Findings received: 47 (5 agents: code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer, type-design-analyzer)
- Retained: 18 grouped findings (2 critical, 5 major, 11 medium) → consolidated into 11 fix sub-phases
  - CRITICAL: path-frame mismatch (multi-file never matches, D4); self-candidate injection (source deletable via Conflict409+recheck-timeout)
  - MAJOR: post-inject finalization not fail-safe; W7 anti-storm defeated by loop reset; backoff uncapped/safety-net pacing dead; MediaType.MOVIE hardcoded (D6); SIGTERM dead under PM2
- Ignored (open items, operator sign-off pending): TorrentLayoutReader protocol split, typed properties() return, run_in_flight machine input, LOW polish (completion_on consumption, CrossSeedResult NamedTuple)
- Design contradictions: none (all fixes move toward the frozen DESIGN)
- Fix phase created: phase-10-pr-fixes-cycle-1.md
- Status: fix phase dispatched → awaiting /implement:phase

## Next action

All phases complete — run /implement:feature-pr (gate + push + PR + CI; merge manual).
