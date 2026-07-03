# Phase 10 — PR fixes cycle 1

## Context

Fixes identified during PR #212 review cycle 1 (5 agents: code-reviewer, silent-failure-hunter,
pr-test-analyzer, comment-analyzer, type-design-analyzer). All retained findings are coherent
with DESIGN.md scope — every fix moves the implementation TOWARD the frozen design (D4, D6,
D10, W3, W6, W7). No design contradiction.

## Gate

- **Requires**: Phases 1–9 complete, PR #212 open, CI green at b0f29f39.
- **Produces**: all critical/major/medium review findings fixed, suite + gates green, ready for re-review cycle 2.

### Sub-phases (11 commits minimum)

| #     | Severity | Commit                                                                                       |
| ----- | -------- | -------------------------------------------------------------------------------------------- |
| 10.1  | critical | `fix(watch-seed): normalize path frames between qBit list_files and torrent parse`           |
| 10.2  | critical | `fix(watch-seed): guard against self-candidate injection`                                    |
| 10.3  | major    | `fix(watch-seed): fail-safe post-inject finalization + sweep isolation`                      |
| 10.4  | major    | `fix(watch-seed): repair W7 anti-storm — machine owns backoff resets`                        |
| 10.5  | major    | `fix(watch-seed): derive media_type from release name instead of hardcoded MOVIE`            |
| 10.6  | major    | `fix(watch-seed): make SIGTERM shutdown reachable under PM2`                                 |
| 10.7  | medium   | `fix(watch-seed): tracker-outage handling + sweep failure surfacing + verify timeout config` |
| 10.8  | medium   | `fix(watch-seed): watch loop hardening — corrupt tracker file + child timeout/retry`         |
| 10.9  | medium   | `fix(watch-seed): is_lock_held OSError logging + docstring + direct tests`                   |
| 10.10 | medium   | `test(watch-seed): golden equality pins + TorrentLayout validation + type hardening`         |
| 10.11 | medium   | `docs(watch-seed): correct lying docstrings and comments (review batch)`                     |

## Sub-phase 10.1 — Fix: path-frame mismatch (multi-file never matches)

**Finding**: qBittorrent `torrents/files` returns names that INCLUDE the torrent root folder for
multi-file torrents (`"Root/inner.mkv"`), while `parse_torrent_layout` yields paths relative to
`info.name` WITHOUT the root (`"inner.mkv"` / `"Season 01/ep1.mkv"`). `structural_match` compares
exact strings → every real multi-file torrent = `FILE_LIST_MISMATCH` → the feature silently never
injects multi-file cross-seeds. Tests never caught it because fakes used the same frame on both sides.
**Location**: `personalscraper/acquire/cross_seed.py:522` (`_build_local_layout`), `_layout.py:75-77`
**Severity**: critical

**Fix**: in `_build_local_layout`, normalize the qBit side to the candidate frame:

- If the torrent has > 1 file OR any entry contains `/`: compute the first path component of every
  entry; if ALL entries share the same first component, strip it (`root/`) and use that component as
  the layout `name` (more truthful than the qBit display name, which is renameable); if entries do
  NOT share a single root (rare, torrent with files at top level), leave paths as-is and use
  `item.name` as name.
- Single-file (one entry, no `/`): keep as-is (frames already agree), name = the entry name.
- Document the frame convention in `TorrentLayout.files` docstring (fix its `joined to name/` claim
  for single-file too — see 10.11 overlap; do the docstring here since it's the same file).

**Acceptance**: new regression test pairing a REAL root-prefixed qBit-style file list (e.g.
`[("Show.S01/Season 01/ep1.mkv", 1000), ("Show.S01/Season 01/ep2.mkv", 1200)]`) against a real
multi-file `.torrent` parse of the same tree → `structural_match` returns `MATCH`. A renamed-root
qBit list still yields the correct behavior (strip happens regardless; name check catches renames
only when display name is used — assert the documented outcome). All existing tests green.

## Sub-phase 10.2 — Fix: self-candidate injection guard

**Finding**: nothing compares the candidate's info-hash to the source's. When the origin tracker is
unresolvable (tag lost — logged only at debug), the search can return the SOURCE torrent itself;
`inject()` hits `Conflict409Error` → idempotent success returning the source's own hash → recheck of
the LIVE source; small torrent → source gets tagged SEED_PURE (never ingested again, silently);
large torrent → verify timeout → `delete(injected_hash)` DELETES THE SOURCE from qBittorrent.
**Location**: `personalscraper/acquire/cross_seed.py:584-589`, `:327`, `:365`
**Severity**: critical

**Fix**:

1. After fetching + parsing a candidate, compute its v1 info-hash (`_bencode_info_hash(candidate_bytes)`,
   fail-soft) and reject with reason `"self_candidate"` when it equals `info_hash` (also covers
   byte-identical same-hash releases cross-posted on other trackers — injecting the same hash is
   always a no-op at best and a recheck/delete hazard at worst).
2. Additionally guard the delete path: `_verify_injection` failure must NEVER delete when
   `injected_hash == info_hash` (belt-and-braces).
3. Promote the `origin_unresolved` log from debug to warning (operator must know exclusion is off).

**Acceptance**: test: candidate whose bytes hash to the source's `info_hash` → rejected
`self_candidate`, NO inject call, NO delete call; test: origin unresolved logs at warning. Existing
tests green.

## Sub-phase 10.3 — Fix: fail-safe post-inject finalization + sweep isolation

**Findings** (aggregate):
(a) `resume()` (cross_seed.py:336) and `delete()` (:365) are unguarded; QBitClient `resume`/`delete`/
`list_files`/`properties`/recheck-inside-`inject` have no/partial qbittorrentapi→ApiError mapping —
one transient auth/network error aborts `check()` mid-finalization leaving the injection paused
forever with no tag/obligation/event, and kills the whole `sweep()`.
(b) Emit-after-persist violated: `_write_obligation` swallows store errors but `CrossSeedInjected`
is emitted anyway; the torrent seeds with no obligation row (hit-and-run risk).
(c) Tag failure warning doesn't state the consequence (duplicate re-ingestion path).
**Location**: `personalscraper/acquire/cross_seed.py:327-381,685-693`, `personalscraper/api/torrent/qbittorrent.py:214-229,168-202,390,425`
**Severity**: major

**Fix**:

1. `qbittorrent.py`: map qbittorrentapi/auth/connection errors to `ApiError` on `resume`, `delete`,
   `list_files`, `properties`, and the `torrents_recheck` calls inside `inject` (mirror `add()`'s
   mapping style; recheck failure after successful add must NOT report the injection as failed —
   log and continue, the caller's verify poll is the arbiter).
2. `cross_seed.py` finalization ordering (D10-conform, write-then-resume): after verify OK →
   (i) write obligation; if the write FAILS → log at ERROR with the H&R consequence, do NOT resume,
   `delete(injected, delete_files=False)` (no obligation = do not seed), rejected reason
   `"obligation_write_failed"`; (ii) resume — on failure log ERROR `"stranded_paused_injection"`
   with hash + save_path + "manual resume required" but KEEP obligation + tag attempt + event
   (state is recoverable manually); (iii) tag — on failure log WARNING stating "will be re-processed
   as new work until tagged"; (iv) emit `CrossSeedInjected` only after obligation persisted.
3. `sweep()`: wrap the per-item `self.check(h)` in try/except Exception → log `sweep_item_error`
   with hash + continue (per-item isolation); the guard on `get_completed` stays.

**Acceptance**: tests: (a) injector.inject raising ApiError mid-sweep → sweep continues to next item
and returns a result; (b) obligation store write raises → no CrossSeedInjected emitted, injection
deleted, reason `obligation_write_failed`; (c) resume raises → obligation kept, ERROR logged, check()
returns with the injection counted + concern logged. Existing tests green (update the happy-path
ordering assertions if they pinned resume-before-obligation).

## Sub-phase 10.4 — Fix: W7 anti-storm — the machine owns backoff resets

**Findings** (aggregate):
(a) The loop unconditionally resets `debounce_until=None, backoff_multiplier=0` on any exit-0 run
(watch.py:206-211) — defeats W7 in its exact target scenario (item repeatedly failing ingest:
pipeline exits 0, predicate stays true → reset every run → re-fire every 15 min forever).
(b) Backoff `2**multiplier` unbounded; safety net unreachable while work exists.
(c) Safety-net cooldown dead: branch 4 (stale-window clear) wipes the window the safety-net branch
just set → persistent-failure serial storm at poll cadence.
**Location**: `personalscraper/acquire/watcher.py:116-119,157-215`, `personalscraper/commands/watch.py:198-211`
**Severity**: major

**Fix** (machine-owned invariants):

1. `WatcherState` gains `debounce_origin: str | None = None` (`"completion" | "safety_net" | None`).
2. Branch 3b (completion fire): clamp the next window — `delay = min(debounce_s * 2**multiplier,
safety_net_hours * 3600)`; set origin `"completion"`.
3. Branch 4 (work vanished): clear the window ONLY when `debounce_origin == "completion"` (or None);
   a `safety_net`-origin window survives (it IS the pacing for persistent failure).
4. Branch 5 (safety net): fire only when `debounce_until is None or now >= debounce_until`; on fire
   set `debounce_until = now + min(debounce_s * 2**multiplier, safety_net_hours * 3600)`,
   `backoff_multiplier += 1` (NOT reset to 0), origin `"safety_net"`.
5. Sentinel/manual fire keeps clearing everything (explicit operator reset) — origin None.
6. The LOOP: remove the unconditional debounce/backoff reset on exit-0; keep only
   `last_successful_run_at` persist + `state = replace(state, last_successful_run_at=now)`.
   The machine's branch 4 clears completion windows when work vanishes (success case), and keeps
   pacing when it doesn't (W7 case).
7. Rewrite `evaluate()`'s docstring: no caller-side reset contract; document origins + clamps.

**Acceptance**: unit tests: (a) repeated completion fires with predicate stuck true → delays
900, 1800, 3600, ... clamped at safety_net_hours*3600; (b) after a fire, work vanishes → next cycle
clears window + backoff (success path); (c) persistent failure with NO work: safety-net fires, then
does NOT re-fire until its window expires; consecutive safety-net fires space out exponentially
(clamped); (d) `cross_seed_dispatched` survives every FIRE_RUN transition (explicit asserts on the
manual/completion/safety-net paths); (e) loop test: run exit != 0 → `last_successful_run_at` NOT
persisted, machine state untouched by the loop. Full watcher suite green.

## Sub-phase 10.5 — Fix: media_type derived from release name

**Finding**: `search_candidates(item.name, MediaType.MOVIE)` hardcoded — c411 picks its endpoint by
media_type, so TV/anime completions search the movies category and miss candidates (violates D6
"ALL completed torrents").
**Location**: `personalscraper/acquire/cross_seed.py:224`
**Severity**: major

**Fix**: derive the media type from the release name with guessit (already a project dependency;
check how triage calls it — `guessit(item.name)` `type` field: `"episode"` → the registry's TV media
type, else MOVIE; wrap in try/except with MOVIE fallback + debug log). Verify what MediaType members
exist (`rg -n --type py "class MediaType" personalscraper/`) and what c411 expects. Small pure helper
`_media_type_for(name)` in cross_seed.py + Google docstring.

**Acceptance**: tests: `"Show.S01E01.1080p..."` → TV type; `"Movie.2024.1080p..."` → MOVIE;
guessit exception → MOVIE fallback. Existing tests green.

## Sub-phase 10.6 — Fix: SIGTERM shutdown reachable under PM2

**Finding**: `time.sleep(60)` resumes after the handler (PEP 475) and PM2's default kill timeout
(~1.6 s) SIGKILLs long before the cycle ends — the finally block (context close, shutdown log) is
dead code in production.
**Location**: `personalscraper/commands/watch.py:218`, `ecosystem.config.js`
**Severity**: major

**Fix**: (1) replace the single sleep with 1 s slices checking `_shutdown_requested` (extract
`_interruptible_sleep(seconds)` helper); (2) `ecosystem.config.js`: add `kill_timeout: 30000` to the
watch app (covers slice granularity + context close; document the choice in a comment).

**Acceptance**: loop test: SIGTERM flag set mid-sleep → loop exits within ~1 simulated slice (patch
time.sleep, count calls), finally runs (closes called). Ecosystem guard test updated for kill_timeout.

## Sub-phase 10.7 — Fix: tracker-outage handling + sweep failure surfacing + verify timeout

**Findings** (aggregate):
(a) `check()` ignores `search_candidates`' `trackers_errored` and records search history BEFORE the
outcome — a tracker outage suppresses retries for `exclude_recent_search_days` (3 d) silently.
(b) `sweep()` returns an empty SweepResult when `get_completed()` fails; CLI prints a green
"0 checked, 0 injected" success banner for a total failure (exit 0 — PM2 cron can't tell).
(c) Verify timeout: fixed 120 s is unrealistic for large media over macFUSE/NTFS; timeout, poll
lister failure, and true mismatch all collapse into reason `recheck_failed`.
**Location**: `cross_seed.py:224-232,430-437,40,363-381,632-640`, `commands/cross_seed.py:101-107`, `conf/models/watch_seed.py`
**Severity**: medium

**Fix**:

1. Consume the search outcome: only `record_search(hash, tracker)` for trackers in
   `trackers_queried` minus `trackers_errored`; log `search_partial_outage` (warning) with the
   errored list when non-empty.
2. `SweepResult` gains `lister_failed: bool = False`; sweep sets it on the get_completed guard;
   the CLI prints a red error + exits 1 when set.
3. `CrossSeedConfig` gains `verify_timeout_s: int = Field(default=900, ge=30, le=7200)`; service
   uses it (replaces the module constant); BOTH config overlays get the commented default
   (anti-drift). Distinct rejected reason: `"verify_timeout"` when the deadline passed without a
   definitive verdict vs `"recheck_failed"` reserved for a definitive failed verification
   (delete still happens in both — D10 — but the reason + event now tell the operator which).

**Acceptance**: tests: errored tracker not recorded in history (retry possible next check); sweep
lister failure → CLI exit 1 + red message; verify_timeout config default 900 exposed + both overlay
files contain the key; timeout emits reason verify_timeout. Existing tests updated (constant → config).

## Sub-phase 10.8 — Fix: watch loop hardening — corrupt tracker file + child timeout/retry

**Findings** (aggregate):
(a) Corrupt/unreadable `ingested_torrents.json` degrades to `{}` = "nothing ingested" → mass
cross-seed dispatch + run trigger.
(b) Cross-seed children: `subprocess.run` without timeout (one hung child freezes the daemon —
same hazard class as the project's network-timeout rule); failed children are never retried
(hash stays in `cross_seed_dispatched` for the daemon's lifetime).
**Location**: `personalscraper/commands/watch.py:110-111,167-184`
**Severity**: medium

**Fix**:

1. Cycle guard: if the tracker file exists AND is non-empty AND `load()` returned `{}` → log
   `watcher_tracker_unreadable` (warning) + skip the cycle (do not treat as fresh library).
2. `subprocess.run(..., timeout=1800)`; on `TimeoutExpired` or `returncode != 0`: log (include
   returncode; capture_output=True and log stderr tail ~500 chars) AND remove the hash from
   `state.cross_seed_dispatched` (bounded natural retry next cycle; the acquire.db
   exclude-recent guard prevents tracker hammering).

**Acceptance**: loop tests: corrupt-file cycle skipped (no spawns); child failure → hash removed
from dispatched set (retried next cycle) + stderr logged; child timeout handled without daemon
crash. Existing loop tests green.

## Sub-phase 10.9 — Fix: is_lock_held contract + real _WatchSubStore tests

**Findings** (aggregate):
(a) `is_lock_held` docstring says PermissionError → False while the code (correctly) returns True;
`OSError` reads swallowed silently; ZERO direct tests for the daemon's most safety-critical probe.
(b) `_WatchSubStore` get/set never executed against a real store by any test (both call-sites are
fail-soft — a SQL typo would be permanently silent: safety-net fires after every PM2 restart).
**Location**: `personalscraper/lock.py:89-119`, `personalscraper/acquire/_watch_store.py`
**Severity**: medium

**Fix**: correct the docstring (PermissionError = held); add a warning log (path + errno) on the
OSError branch before returning False; add tests/test_lock.py cases: missing file / corrupt PID /
stale dead PID / live PID (own pid) / PermissionError (monkeypatch os.kill) — 5 direct tests.
Add a real-store round-trip test (tmp acquire.db): get→None, set, get→value, set again (upsert),
get→new value.

**Acceptance**: the 7+ new tests pass; full make lint green.

## Sub-phase 10.10 — Test + type hardening batch

**Findings** (aggregate):
(a) Golden .torrent fixture tests assert shape only (name non-empty, sizes positive) — a byte-offset
drift yielding wrong-but-positive values passes; pin EXACT name, piece_length, file count,
total_size for each of the 3 committed fixtures.
(b) qBit `inject()` mapping tests cover only Conflict409 — add "Fails." → ApiError and one
typed-error mapping test (from the 10.3 mappings).
(c) `TorrentLayout` unvalidated: add `__post_init__` (files non-empty, piece_length > 0, sizes >= 0),
`files: tuple[tuple[str, int], ...]` (update producers/tests), `total_size` verified (keep the field
— frozen dataclass — but validate it equals the sum in `__post_init__`; fix producers to always
compute it); v2 gates flip to `meta_version != 1` (both `_layout.py` structural_match and
`cross_seed.py` local check).
(d) `check()` refuses to inject when `item.save_path` is empty (skip with reason `no_save_path`).
(e) `WatcherOutput.new_state` becomes required (no default_factory reset-magnet).
(f) `CrossSeedRejected.reason` docstring lists the REAL closed reason set (incl. the new
self_candidate / obligation_write_failed / verify_timeout / no_save_path).
(g) Fix the weak `TestCheckOriginExcluded` (construct the promised scenario: origin candidates +
one eligible other tracker → only non-origin fetched) and remove the dead fake_clock/fake_sleep
fixtures in test_cross_seed_service.py.
**Severity**: medium

**Acceptance**: all listed tests exist and pass; mypy strict green; `structural_match` rejects
`meta_version=3`; TorrentLayout(files=[]) raises ValueError.

## Sub-phase 10.11 — Docs: correct lying docstrings/comments (review batch)

**Findings** (comment-analyzer, remaining after 10.1/10.4/10.9/10.10 overlaps):

1. `store.py:980-982` `increment_daily_count` docstring instructs wrapping in a transaction that
   the method already opens (following it → "cannot start a transaction within a transaction").
   State the truth: self-contained upsert, call bare.
2. `_base.py:41-44` `TorrentItem.save_path` claim about Transmission is stale — the mapper DOES set
   it from `download_dir`.
3. `_contracts.py:223-224` `TorrentInjector` justification wrong (Transmission has download_dir +
   verify_torrent; real reason = RP10b scopes qBit only per DESIGN D2 seed-source) + wrong "(D2)"
   code collision with the module's own header table. Rewrite honestly.
4. `cross_seed.py:401-403,428,469` sweep sleep comments: describe the REAL behavior (once a counted
   check sets need_sleep it stays; a skipped item between two counted ones does not suppress the
   sleep) or simplify the flag logic to match the comment — pick one, keep code+comment agreeing.
5. `watcher.py:61` `pipeline_lock_held`: "exists" → "held by a live process (is_lock_held probe)".
6. `watch.py:65-66` "(W5)" → "(W6)" for the lock discipline sentence.
7. `cross_seed.py:231-232` "per DESIGN §Config" → cite CrossSeedConfig docstring instead.
8. `cross_seed.py:234,326` step-number comments beyond the documented list — renumber docstring
   - comments consistently.
     **Severity**: medium (docs-only)

**Acceptance**: each item verifiably corrected; `make lint` green; no behavior change
(`git diff` shows only comments/docstrings except where 10.11.4 chooses the code-simplification arm).

## Gate check (before re-review cycle 2)

- [ ] `make check` — all green.
- [ ] New regression tests from 10.1–10.10 all pass.
- [ ] `make test 2>&1 | tail -1` — 0 failed.
- [ ] Layering + boundary + module-size guards green (`cross_seed.py` may need splitting if it
      exceeds 800 LOC after 10.3/10.7 — watch it).
