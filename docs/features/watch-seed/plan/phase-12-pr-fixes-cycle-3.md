# Phase 12 — PR fixes cycle 3

## Context

Cycle-3 review (2 agents) confirmed ALL cycle-2 fixes sound, non-vacuous, no regression — both
agents recommend merge in default config. The silent-failure-hunter found 2 new MEDIUM issues, both
introduced by cycle-2 fix commits (11.1 restructure, 11.3 queried_names filter). 0 critical, 0 major,
2 medium retained. No design contradiction. Fixing both per operator "nothing deferred without
sign-off" + "continue to merge" directive.

## Gate

- **Requires**: Phase 11 complete, CI green at 1f371b1a.
- **Produces**: 2 cycle-3 mediums fixed, gates green, ready for re-review cycle 4.

### Sub-phases (2 commits minimum)

| #    | Severity | Commit                                                                       |
| ---- | -------- | ---------------------------------------------------------------------------- |
| 12.1 | medium   | `fix(watch-seed): scope cross-seed targets to media-type-queryable trackers` |
| 12.2 | medium   | `fix(watch-seed): tracker-file guard must not crash on invalid UTF-8`        |

## Sub-phase 12.1 — media-type-scoped eligible trackers (re-search storm)

**Finding (F1, medium — borderline major under subset override config)**: `remaining` in `check()`
is derived from `_eligible_trackers()` which uses the flat media-type-AGNOSTIC `tracker.priority`,
but `search_candidates()` only queries `_priority_for(media_type)` which honors a
`priority_by_media_type` override. When an override is a strict subset (permitted by the
`api_config.py` validator), a tracker `T` that is enabled + `cross_seed=True` (so in `remaining`)
but absent from the movie/tv override is NEVER in `queried_names` → the 11.3 filter never records it
→ `was_searched_recently(T)` stays False → `remaining` never empties → the `all_excluded_recent`
short-circuit never fires → `check()` runs a full network search on EVERY call forever for every
affected info-hash, burning the daily quota on `--sweep` (premature `quota_exhausted`, sweep never
progresses). No log connects the perpetual re-search to the config mismatch. Default config (no
override, or a full-set override) is unaffected.
**Location**: `personalscraper/acquire/cross_seed.py:187-222` (`check()` remaining/record loop),
`_eligible_trackers` (`cross_seed.py:779-805`), `api/tracker/_registry.py:70-79` (`_priority_for`).
**Severity**: medium (this is a regression in the 11.3 queried_names fix — the filter that prevents
a _false_ lockout created a case where an eligible-but-not-queried tracker is never recorded,
producing an infinite re-search).

**Fix (make `remaining` media-type aware so an override-excluded tracker is simply not a target)**:

1. Expose the media-type-scoped queryable tracker set from the registry: add a small method
   `TrackerRegistry.queryable_for(media_type) -> set[str]` (or `list`) that returns
   `_priority_for(str(media_type))` filtered to trackers actually present in `self._trackers`
   (the same set `search_candidates` would iterate, minus client-None). Google docstring.
2. In `check()`, intersect `remaining` (eligible: enabled + cross_seed + not-origin) with
   `registry.queryable_for(media_type)` BEFORE the `all_excluded_recent` short-circuit. A tracker
   the operator excluded from this media type's priority is thereby correctly NOT a cross-seed
   target for this media type — no search, no storm, no false lockout. This is the operator's
   explicit intent when they set a subset override.
3. If the intersection drops any eligible tracker for this media type, log ONCE per check at debug
   `cross_seed_tracker_not_queryable_for_type` (tracker, media_type) so the config choice is
   observable without noise.
4. Keep the 11.3 `queried_names ∩ not-errored` record filter (still correct — it now operates on a
   `remaining` that is already media-type-scoped, so queried_names and remaining agree in the happy
   path; the record filter remains the guard against a tracker that errored mid-search).

**Acceptance**: test — a tracker enabled+cross_seed but excluded from a `priority_by_media_type`
subset override is NOT searched, NOT recorded, and (critically) a second `check()` on the same hash
with all real targets excluded-recent → `all_excluded_recent` short-circuit fires (skipped, NO
network search) instead of re-searching. Existing cross_seed tests green (default config path
unchanged — with no override, `queryable_for` returns the full eligible set).

## Sub-phase 12.2 — tracker-file guard: UnicodeDecodeError must not crash the daemon

**Finding (F2, medium)**: the cycle-2 tracker-file guard reads
`tracker_path.read_text(encoding="utf-8")` wrapped only in `except OSError`. A file with invalid
UTF-8 bytes raises `UnicodeDecodeError` (a `ValueError` subclass, NOT `OSError`), which escapes
every guard case, propagates out of the `while` loop (the outer block has only `finally`, no
`except`), and kills the watcher daemon → PM2 crash-loop. The guard's whole purpose is to fail
CLOSED on degraded data before `load()` (which would degrade to `{}` → mass dispatch), so leaving
one corruption mode as an uncaught crash breaks the fail-closed contract. Untested (guard tests
cover OSError/whitespace/non-dict/invalid-json only).
**Location**: `personalscraper/commands/watch.py:150-155`.
**Severity**: medium (crash hole directly inside the 11.1 restructure — loud, not silent, but a
real availability regression on a corrupt-write).

**Fix**: broaden the raw-read guard to `except (OSError, UnicodeDecodeError)` (treat undecodable
bytes like `io_error`/`invalid_json` — skip the cycle with a distinct `cause="undecodable"` +
`_interruptible_sleep` + continue). A one-line broadening; keep the warning event name
`watcher_tracker_unreadable` with the new cause value.

**Acceptance**: test — a tracker file containing invalid UTF-8 bytes (`b"\xff\xfe"`) makes the loop
SKIP the cycle (no crash, no mass dispatch, warning logged with cause=undecodable). Existing guard
tests green.

## Gate check (before re-review cycle 4)

- [ ] `make check` — all green.
- [ ] Both 12.x acceptance tests pass.
- [ ] Default-config cross_seed path unchanged (regression-free).
