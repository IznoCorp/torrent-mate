# Phase 04 — PR fixes cycle 1

**PR**: [#145](https://github.com/user/personalscraper/pull/145)
**Branch**: `feat/acquire-events`
**Date**: 2026-06-10
**Agent**: DeepSeek v4 Pro

## Fixes applied

| #   | Severity | Description                                                                                        | Commit     |
| --- | -------- | -------------------------------------------------------------------------------------------------- | ---------- |
| 1   | MEDIUM   | WantedEnqueued season=0/episode=0 (Plex Specials) rendered "?" — truthiness bug                    | `1bf14c8b` |
| 2   | MAJOR    | Vacuous fail-soft test replaced with 3 non-vacuous sync tests (mutation-proof)                     | `6607c8c8` |
| 3   | MAJOR    | `acquire_notify_enabled` default `False` untested — assertion added                                | `6607c8c8` |
| 4   | MEDIUM   | Docstring drift: `acquire.notify.<event>` → `acquire.notify.event` + `acquire_event` field         | `1bf14c8b` |
| 6   | MINOR    | `time.sleep(0.05)` daemon-join waits replaced with deterministic `_wait_for()` poll                | `6607c8c8` |
| 7   | MINOR    | `test_event_registry_has_eighteen_v1_events` → `test_event_registry_has_all_v1_events` (33 events) | `6607c8c8` |
| 5   | —        | Wiring test — skipped (needs heavy harness)                                                        | —          |

## Commits

```
6607c8c8 test(acquire-events): non-vacuous fail-soft + notify-default-False + deflake
1bf14c8b fix(acquire-events): WantedEnqueued specials S00E0x (is-not-None) + subscriber docstring
```

## Files changed

4 files:

- `personalscraper/subscribers/acquire.py` — Fix #1 (is-not-None), Fix #4 (docstrings)
- `tests/subscribers/test_acquire_subscriber.py` — Fix #2 (non-vacuous fail-soft × 3), Fix #1 regression (S00E05), Fix #6 (\_wait_for helper)
- `tests/unit/test_api_config_models.py` — Fix #3 (default-False assertion)
- `tests/event_bus/test_pipeline_events.py` — Fix #7 (test rename)

## Mutation proof (Fix #2)

All three new fail-soft tests verified empirically:

| Test                                                      | Guard removed                                                       | Result                                                                   | Guard restored |
| --------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------ | -------------- |
| `test_fail_soft_notifier_send_returns_false_logs_warning` | `if not self._notifier.send(...)` → bare `self._notifier.send(...)` | **FAILED** — no WARNING logged                                           | **PASSED**     |
| `test_fail_soft_no_notifier_logs_warning`                 | `if self._notifier is None:` guard removed                          | **FAILED** — `AttributeError: 'NoneType' object has no attribute 'send'` | **PASSED**     |
| `test_fail_soft_worker_crashed_logged`                    | try/except in `_runner` removed                                     | **FAILED** — `TimeoutError` (no WARNING logged)                          | **PASSED**     |

## Regression tests (Fix #1)

- `test_wanted_enqueued_specials_format_s00e05` — season=0, episode=5 → `"S00E05"` in message (not `"?"`)
- `test_wanted_enqueued_movie_no_season_placeholder` — movie kind → no season placeholder

## Quality gates

```
make lint    → All checks passed (ruff + mypy + check_logging 0 findings)
make test    → 540 passed, 1 skipped (targeted)
make check   → 6544 passed, 3 skipped, 2 xfailed in 61.82s
               Coverage: 91.38% (threshold 90%)
               module-size: 1 pre-existing WARN (movie_service.py, not our change)
               CLI coverage: OK — 0 ❌
```
