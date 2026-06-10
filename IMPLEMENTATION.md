# Implementation Progress — acquire-events

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP4 — acquisition event catalog + muted Telegram subscriber (minor)
**Version bump**: 0.26.0 → 0.27.0
**Branch**: feat/acquire-events
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/145
**Design**: docs/features/acquire-events/DESIGN.md
**Master plan**: docs/features/acquire-events/plan/INDEX.md

## Phases

| #   | Phase                                                            | File                   | Status |
| --- | ---------------------------------------------------------------- | ---------------------- | ------ |
| 1   | Event catalog (acquire/events.py) + hub registration + factories | phase-01-events.md     | [x]    |
| 2   | Muted Telegram subscriber + config flag + CLI wiring             | phase-02-subscriber.md | [x]    |
| 3   | Docs update + ACCEPTANCE.md + make check gate                    | phase-03-docs-gate.md  | [x]    |
| 4   | PR review fixes — cycle 1                                        | phase-04-pr-fixes-cycle-1.md | [x]    |

## Review cycles

### Cycle 1

- Toolkit: 3 agents (pr-test-analyzer, code-reviewer, silent-failure-hunter) on the PR #145 diff. Event-catalog + serialization core confirmed genuinely strong + non-vacuous (true equality round-trip, real MediaRef factories, real count-pin; fail-soft correctly implemented + logged). Findings concentrated on the subscriber/config surface (all design-conformant, NO design contradiction):
  - **#1 (medium)** WantedEnqueued handler formats S00E05 as `?` — `if event.season and event.episode` uses truthiness, but season/episode 0 (Plex Specials) are legitimate falsy ints. Display-only (muted) but a real logic bug for Follow D2.
  - **#2 (major)** `test_fail_soft_notifier_error_does_not_propagate` is VACUOUS — the send runs on a daemon thread so the exception can never reach `bus.emit` regardless of the production guard (mutation-proven: deleting the guard keeps the test green). The 3 real fail-soft WARNING branches (send→False, notifier=None, worker-crashed) are untested.
  - **#3 (major)** `acquire_notify_enabled` default-False (the production muted switch) asserted nowhere — flipping it to True would keep the whole suite green and silently start sending in prod.
  - **#4 (medium)** docstring advertises `acquire.notify.<event>` but the code logs a static `acquire.notify.event` key (per-event discriminator in the `acquire_event` field; dynamic name forbidden by check_logging). Doc/code drift.
  - #5/#6/#7 (minor) untested pipeline wiring; `time.sleep` daemon-join flake risk; stale `test_..._eighteen_v1_events` name pinning 33.
- Decision: **Case B**. Fix phase 4 executed (2 commits `1bf14c8b`,`6607c8c8`): #1 specials `is not None` (S00E05 verified), #2 non-vacuous fail-soft (3 branches MUTATION-PROVEN: guard removed→FAIL, restored→PASS), #3 default-False asserted, #4 docstring matched to the static-key reality, + deflake/rename minors. make check 6544 green. Cycle 2 not needed (fix diff = 1-line logic + tests + docstring, mutation-proven, minimal-risk). Merge = manual → operator squash-merges on CI green.

### Cycle 2

- Toolkit: 2 lenses (silent-failure-hunter, code-reviewer) on the cycle-1 fix diff (`2e9578b9..HEAD`). **APPROVE, zero findings.** silent-failure-hunter empirically re-mutated all 4 guards (each removed → its test FAILS, restored → PASS) confirming the replacement fail-soft tests are genuinely non-vacuous + no new over-swallow + muted contract holds; code-reviewer confirmed all 6 cycle-1 fixes correct + complete, audited all 10 handlers for the same truthiness-vs-None bug (none), no new convention violation.
- Decision: **Case A** (no critical/major/medium). Loop exits clean. Merge = manual → operator squash-merges.

## Next action

Review cycles 1+2 complete (cycle 2 = clean, zero findings). CI green on `31f12e1b`. **Awaiting MANUAL squash merge** (`gh pr merge 145 --squash`). After merge: next `/implement:feature` archives acquire-events.