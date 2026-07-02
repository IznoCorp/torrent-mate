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
| 10  | PR fixes cycle 1                                     | phase-10-pr-fixes-cycle-1.md            | [x]    |
| 11  | PR fixes cycle 2                                     | phase-11-pr-fixes-cycle-2.md            | [x]    |
| 12  | PR fixes cycle 3                                     | phase-12-pr-fixes-cycle-3.md            | [x]    |

## Review cycles

### Cycle 1

- Findings received: 47 (5 agents: code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer, type-design-analyzer)
- Retained: 18 grouped findings (2 critical, 5 major, 11 medium) → consolidated into 11 fix sub-phases
  - CRITICAL: path-frame mismatch (multi-file never matches, D4); self-candidate injection (source deletable via Conflict409+recheck-timeout)
  - MAJOR: post-inject finalization not fail-safe; W7 anti-storm defeated by loop reset; backoff uncapped/safety-net pacing dead; MediaType.MOVIE hardcoded (D6); SIGTERM dead under PM2
- Ignored (open items, operator sign-off pending): TorrentLayoutReader protocol split, typed properties() return, run_in_flight machine input, LOW polish (completion_on consumption, CrossSeedResult NamedTuple)
- Design contradictions: none (all fixes move toward the frozen DESIGN)
- Fix phase created: phase-10-pr-fixes-cycle-1.md
- Status: fix phase COMPLETE (18 commits, 2 wrapper-timeout continuations recovered, 2 in-flight corrections: valid-empty tracker freeze, format stragglers) — make check green → pushed for re-review cycle 2

### Cycle 2

- Findings received: 16 (2 agents: code-reviewer verification pass + silent-failure-hunter)
- Cycle-1 fixes verdict: ALL 11 areas confirmed SOUND by both agents (non-vacuous tests, no regression from finalization reordering / debounce_origin / module split)
- Retained: 9 grouped (0 critical, 2 major, 7 medium) → 4 fix sub-phases
  - MAJOR: whitespace-only tracker file bypasses the corrupt-file guard (mass-dispatch path); hardcoded child timeout 1800s vs verify_timeout_s ≤7200 (stranded paused injection on SIGKILL) + shutdown-blind spawn loop
  - MEDIUM: inject/local-layout unguarded in check(); self-delete guard asymmetry (comment lies); never-queried trackers recorded as searched; sweep item-errors invisible (fabricated green one level down) + throttle bypass on error; exc_info missing on 5 catch-alls; guessit fallback at DEBUG; lister_error severity; qbittorrentapi terminal mapping
- Ignored (informational): backoff growth under safety-net-only operation (clamped, by design); SIGTERM-during-child residual (design-inherent W5, acknowledged in comment)
- Design contradictions: none
- Fix phase created: phase-11-pr-fixes-cycle-2.md
- Status: fix phase COMPLETE (12 commits across 4 sub-phases; 1 wrapper-timeout continuation on 11.3, 2 in-flight corrections: mypy import from real module, ruff format stragglers) — make check green (91.03% cov) → pushed for re-review cycle 3

### Cycle 3

- Findings received: cycle-2 fixes verified by 2 agents (code-reviewer + silent-failure-hunter)
- Cycle-2 fixes verdict: ALL 9 findings confirmed genuinely closed, non-vacuous, no regression; both agents recommend merge in default config
- Retained: 2 medium (0 critical, 0 major) → 2 fix sub-phases
  - MEDIUM F1: re-search storm — my 11.3 queried_names filter regresses under a subset priority_by_media_type override (eligible-but-not-queried tracker never recorded → all_excluded_recent never fires → full search every check() forever, quota drain). Non-default config trigger.
  - MEDIUM F2: my 11.1 tracker-file guard restructure lets UnicodeDecodeError (ValueError subclass, not OSError) escape → daemon crash on invalid-UTF-8 tracker file (breaks the fail-closed contract).
- Ignored (informational, non-blocking): shutdown-removal no-op vs restart-clears-set (correct outcome, redundant code); timeout heuristic ≤2 verify polls; _cross_seed_failures unbounded growth (reset on restart); double-read TOCTOU (atomic writer mitigates)
- Design contradictions: none
- Fix phase created: phase-12-pr-fixes-cycle-3.md
- Status: fix phase COMPLETE (2 sub-phases, 2 commits, no timeout) — make check green (91.02% cov) → pushed for re-review cycle 4

## Next action

All phases complete — run /implement:feature-pr (gate + push + PR + CI; merge manual).
