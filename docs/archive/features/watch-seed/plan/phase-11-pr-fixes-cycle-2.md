# Phase 11 — PR fixes cycle 2

## Context

Cycle-2 review (2 agents) confirmed ALL cycle-1 fixes sound, and found a smaller set of holes in
and around the fixes themselves. 0 critical, 2 major, ~7 medium retained. No design contradiction.

## Gate

- **Requires**: Phase 10 complete, CI green at 6db09e90.
- **Produces**: cycle-2 findings fixed, gates green, ready for re-review cycle 3.

### Sub-phases (4 commits minimum)

| #    | Severity | Commit                                                                              |
| ---- | -------- | ----------------------------------------------------------------------------------- |
| 11.1 | major    | `fix(watch-seed): close tracker-file guard holes (whitespace, non-dict, TOCTOU)`    |
| 11.2 | major    | `fix(watch-seed): config-derived child timeout + shutdown-aware cross-seed loop`    |
| 11.3 | medium   | `fix(watch-seed): guard inject/layout paths + self-delete symmetry + queried_names` |
| 11.4 | medium   | `fix(watch-seed): sweep item-error accounting + logging polish`                     |

## Sub-phase 11.1 — tracker-file guard holes

**Findings**: (a) whitespace-only file (`"\n"`, truncated write) has st_size>0, fails json.loads
inside IngestTracker.load() (→ {}), but the guard's `if raw.strip():` skips the re-check → cycle
proceeds with empty ingested set → mass dispatch (the exact failure the guard exists to prevent);
(b) valid-JSON non-dict file (`[1,2,3]`) → `load()` returns a list → `.keys()` at watch.py:136
raises AttributeError BEFORE the guard → daemon crash loop; (c) `tracker_path.stat()` at :146 sits
outside the try — TOCTOU OSError kills the daemon.
**Location**: `personalscraper/commands/watch.py:130-161`, and note `ingest/tracker.py` load() shape
**Severity**: major

**Fix**: restructure the cycle-top tracker read into one guarded block: read raw text (OSError →
unreadable-skip); `raw.strip() == ""` with st_size>0 → unreadable-skip; json.loads fails →
unreadable-skip; parsed is not a dict → unreadable-skip (distinct log detail); else proceed and
build the frozenset from load() (which may still normalize). Each skip path: one warning
`watcher_tracker_unreadable` with a `cause` field (empty|invalid_json|not_a_dict|io_error) +
_interruptible_sleep + continue. Also add the is_lock_held OSError regression test (monkeypatch
read_text → OSError; assert False + lock_read_failed warning) — regression-test-per-bug rule,
missed in 10.9.

**Acceptance**: 4 new loop tests (whitespace-only skip; non-dict skip without crash; io-error skip;
valid dict proceeds) + the lock OSError test; existing loop tests green.

## Sub-phase 11.2 — config-derived child timeout + shutdown-aware loop

**Findings**: (a) hardcoded `timeout=1800` conflicts with `verify_timeout_s` (≤7200): SIGKILL can
land mid-verify → stranded paused injection with no tag/obligation and no heal path (history
already recorded → all_excluded_recent skips; hash re-added to dispatched set); (b) the
`for h in out.cross_seed_hashes` loop never checks `_shutdown_requested` between hashes — N hung
children stall SIGTERM far past kill_timeout → SIGKILL skips finally; (c) TimeoutExpired handler
discards exc.stderr; (d) retry-on-failure is unbounded for pre-search failures (auth/config error →
respawn every cycle forever).
**Location**: `personalscraper/commands/watch.py:220-231`
**Severity**: major

**Fix**: (1) child timeout = `max(1800, 2 * config.cross_seed.verify_timeout_s + 300)` computed
once per loop iteration (comment explaining the 2× + margin: up to two sequential verify polls per
check); mention the possible stranded injection in the timeout warning text. (2) `break` out of the
cross-seed spawn loop when `_shutdown_requested` is set (unspawned hashes: remove from
`cross_seed_dispatched` so the next daemon boot retries them). (3) log `stderr_tail` (≤500 chars,
from exc.stderr) in the TimeoutExpired path too. (4) bounded retry: in-memory per-hash failure
counter (dict on the loop, not the pure machine); after 3 failed/timeout attempts, STOP removing
the hash from dispatched (leave it dispatched = no more retries this daemon lifetime) and log
`watcher_cross_seed_gave_up` (warning, with attempts=3). Acknowledge in the 10.6 comment that a
running child still blocks SIGTERM for up to the child timeout (design-inherent, W5 serial spawns).

**Acceptance**: tests: child timeout value derives from config (assert the computed arg);
shutdown flag mid-list stops remaining spawns + removes unspawned hashes; third failure stops
retrying + logs gave_up; TimeoutExpired logs stderr_tail. Existing loop tests green.

## Sub-phase 11.3 — check() guards + self-delete symmetry + queried_names

**Findings**: (a) `injector.inject()` unguarded in check(): a hash_uncomputable candidate raises
ValueError from `_bencode_info_hash` INSIDE inject; ApiError aborts the item (remaining
candidates/trackers skipped, per-completion CLI dies raw); (b) `_build_local_layout` can now raise
ValueError via TorrentLayout.**post_init** (empty file list / piece_size<=0) where it used to
degrade — unguarded in check(); its docstring still documents only the None-on-missing-piece_size
contract; (c) the `obligation_write_failed` delete site lacks the `injected_hash == info_hash`
self-delete guard the nearby comment PROMISES (comment lies; guard exists only in the
verify-failure branch); (d) never-queried trackers (absent from a priority_by_media_type override,
or client None) are still recorded as searched → 3-day silent lockout; the registry's client-None
skip has no log.
**Location**: `personalscraper/acquire/cross_seed.py:157,357,381,451`, `api/tracker/_registry.py:163-166`, `acquire/_dedup.py`
**Severity**: medium

**Fix**: (1) wrap the inject call: ValueError/ApiError → rejected reason `"inject_failed"` +
CrossSeedRejected + warning log + continue to next candidate (add `inject_failed` to the
documented reason set in events.py). (2) wrap the TorrentLayout construction in
`_build_local_layout` with try/except ValueError → return None (existing skip path) + docstring
updated. (3) add the self-delete guard to the obligation_write_failed delete site (log
self_delete_averted, skip delete) and make the 10.2 comment truthful. (4) `SearchOutcome` gains
`queried_names: list[str]`; registry populates it and logs `tracker_unavailable` (warning) on the
client-None skip; check() records history only for `remaining ∩ queried_names − errored_names`.

**Acceptance**: tests: inject raising ApiError → item continues with rejected inject_failed;
inject raising ValueError (uncomputable candidate) → same; empty list_files → check skips (no
raise); obligation-write-fail with self-hash → NO delete + averted log; tracker absent from the
media-type priority → NOT recorded as searched. Existing green.

## Sub-phase 11.4 — sweep item-error accounting + logging polish

**Findings**: (a) per-item sweep errors invisible: SweepResult has no error count, CLI prints
green/exit 0 even if every item raised; error path bypasses quota + need_sleep accounting
(throttle hole); (b) five new broad except blocks log error=str(exc) WITHOUT exc_info=True
(obligation_write_failed, obligation_delete_failed, stranded_paused_injection,
recheck_failed_delete_error, sweep_item_error) — tracebacks lost where they matter most;
(c) `_media_type_for` guessit fallback logs at DEBUG with no error field (category mis-route =
silent 3-day lockout window); (d) `sweep.lister_error` logged WARNING while the CLI treats it
as fatal (exit 1) — should be ERROR; (e) qBit resume/delete/list_files/properties mappings lack
a terminal `qbittorrentapi APIError` catch (500-class escapes raw).
**Location**: `cross_seed.py`, `_cross_seed_support.py:94-100`, `commands/cross_seed.py`, `qbittorrent.py`
**Severity**: medium

**Fix**: (1) `SweepResult.item_errors: int = 0`; sweep counts them; quota increment + need_sleep
set in a finally (or before the risky section) so the throttle holds on error paths; CLI: yellow
warning line when item_errors>0 and exit 1 when item_errors == checked+item_errors > 0 (total
failure) — document the chosen threshold honestly in --help/docstring. (2) add exc_info=True to
the five catch-alls. (3) guessit fallback → warning + error=str(exc). (4) lister_error → ERROR.
(5) add terminal `except qbittorrentapi.exceptions.APIError → ApiError(502)` to the four mapped
methods (mirror add_tags' style).

**Acceptance**: tests: sweep with one raising item reports item_errors=1 + CLI yellow (exit per
threshold); quota consumed despite the error; existing tests green; make lint green.

## Gate check (before re-review cycle 3)

- [ ] `make check` — all green.
- [ ] All 11.x acceptance tests pass.
- [ ] Module sizes: no file > 1000 (watch check-module-size).
