# Phase 10 — PR fixes cycle 3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

Fixes identified during the third PR-review pass on `feat/trailer` (post-cycle-2,
post-`28d9f75`/`3792ea9` placement and scanner fixes). Four specialized reviewers
(code-reviewer, pr-test-analyzer, silent-failure-hunter, comment-analyzer) flagged
a fresh batch of findings beyond what cycles 1 and 2 addressed.

Total retained: **40 findings** (10 critical, 20 important, 10 suggestions).
Ignored: a few cosmetics already accepted in earlier cycles or out of scope (see
"Out of scope" at the bottom).

The critical findings cluster around two pathologies that survived the first two
cycles:

1. **Silent persistence of broken state.** Failure modes (TMDB outage, missing
   ffmpeg, finder import error, partial yt-dlp output) get cached or written to
   the state JSON as `NO_TRAILER_AVAILABLE` / `__no_result__` / `DOWNLOADED`,
   then poison the next 1-7 days of runs.
2. **Test fixtures that route MagicMock strings through real filesystem code.**
   A pipeline fixture forgot `enabled=False`; the orchestrator's
   `Path(str(config.trailers.state_file))` produces a literal
   `<MagicMock name='mock.trailers.lock` file at the repo root.

Sub-phases are organized by code area, not by severity, so each commit lands a
coherent slice. Each sub-phase ends with a `fix(trailer): …` commit; the final
milestone commit closes Phase 10.

## Sub-phases

### 10.1 — Downloader & state-store correctness (4 findings)

**Findings**:

1. **C3** `personalscraper/scraper/ytdlp_downloader.py:389-392` —
   `download()` returns `DownloadStatus.SUCCESS` without verifying the output
   file exists or has size. ffmpeg-merge failure (e.g. `ytdlp_ffmpeg_missing`
   warned at construction) lands the file at `.webm` while
   `result.output_path` claims `.mp4`. Orchestrator records `DOWNLOADED`, SOT
   recheck on next run sees nothing at the expected path, retries indefinitely.
2. **C4** `personalscraper/scraper/ytdlp_downloader.py:374-441` — yt-dlp
   partial files (`.part`, `.frag*`, `.temp.*`) never cleaned up on failure.
   No `finally`-block sweep. Disk leak compounds over time.
3. **I3** `personalscraper/scraper/ytdlp_downloader.py:435-441` —
   retry-without-cookies path classifies _every_ exception as `BOT_DETECTED`.
   Bot-detected entries are exempt from `next_retry_at` (`state.py:416-417`),
   so a real transport error during the retry triggers infinite re-attempts
   on every run.
4. **C7** `personalscraper/trailers/state.py:380-394, 476-505` —
   `fcntl.flock(LOCK_EX)` without `LOCK_NB` and no timeout. Two concurrent
   processes (cron + manual CLI) deadlock with no log, no progress.

**Acceptance**:

- `ytdlp_downloader.download()`, after `_attempt_download` returns, stats the
  expected `output_path`. If absent, glob the parent for `<stem>.*` (excluding
  the suffix) — if a sibling like `.webm` exists, return
  `DownloadStatus.YTDLP_ERROR` with `error_message="downloaded file extension
mismatch (got .webm, expected .mp4); ffmpeg merge failed"`. If no sibling,
  return `YTDLP_ERROR` with `error_message="downloaded file missing"`. Verify
  size > `min_size_bytes` before declaring success.
- Every non-success path in `download()` (timeout, generic exception,
  retry-without-cookies failure) ends with a `finally` block that enumerates
  `output_path.parent.glob(output_path.with_suffix('').name + '.*')`,
  unlinks anything not matching `output_path.suffix`, and emits
  `log.info("ytdlp_partial_cleanup", url=url, removed=count)`.
- Retry-without-cookies path re-applies `_is_bot_detection_error(retry_exc)`.
  If True, return `BOT_DETECTED`. If False, return `YTDLP_ERROR` with the
  retry exception's message — consumers then get normal retry semantics.
- `TrailerStateStore` lock acquisition switches to `LOCK_EX | LOCK_NB` inside
  a bounded loop (3 attempts, 0.5s sleep between attempts). After the budget
  is exhausted, raise a new exception class
  `TrailerStateLocked(Exception)` with the lock-file path and the holder's PID
  if resolvable (best-effort `lsof` — degrade gracefully if unavailable).
  `step.py:run_trailers` catches `TrailerStateLocked` and emits a `StepReport`
  with `status="error"` and a clear log event `trailers_state_locked`.

**Tests**:

- `tests/scraper/test_ytdlp_downloader.py`:
  - `test_download_returns_ytdlp_error_when_output_extension_mismatch` —
    monkeypatch `_attempt_download` to write `name.webm` while
    `output_path=name.mp4`; assert `DownloadStatus.YTDLP_ERROR`.
  - `test_download_returns_ytdlp_error_when_output_missing` — monkeypatch
    `_attempt_download` to write nothing; assert `YTDLP_ERROR`.
  - `test_download_cleans_up_partial_files_on_exception` — write
    `name.part` and `name.frag1` before raising; assert both unlinked,
    final `mp4` not created.
  - `test_retry_without_cookies_classifies_transport_error_as_ytdlp_error` —
    second attempt raises `requests.ConnectionError`; assert `YTDLP_ERROR`,
    not `BOT_DETECTED`.
- `tests/trailers/test_state.py`:
  - `test_lock_contention_raises_trailer_state_locked` — open the lock file
    in a child process, hold for the full retry budget, assert parent
    raises `TrailerStateLocked` with the child's PID.

### 10.2 — Cache integrity (4 findings)

**Findings**:

1. **C5** `personalscraper/scraper/trailer_finder.py:178-182` — TMDB cache
   poisoning. `_fetch_videos` returns `[]` on `CircuitOpenError`, transport
   errors, JSON decode errors. Caller writes `[]` to `TrailersCache` for
   7 days. One 30-second TMDB blip pins empty for a week.
2. **C5** (same) `personalscraper/scraper/trailer_finder.py:213-214` — same
   defect on YouTube fallback path: writes `__no_result__` for transport
   errors / breaker-open / missing API key for 7 days.
3. **C6** `personalscraper/scraper/trailer_finder.py:200-210` plus
   `personalscraper/scraper/trailers_cache.py:169-187` — TTL bypass.
   `has_cached_search()` deliberately reaches into `JsonTTLCache._load()`
   (private), bypassing TTL. After 7 days `has_cached_search` is True, but
   `get_youtube_search` returns None for expiry, finder treats as
   `__no_result__` and exits without re-querying. Permanent silent None.
4. **I7** `personalscraper/scraper/json_ttl_cache.py:132-146, 211-239` —
   `JsonTTLCache.set` has no inter-process locking. Read-modify-write
   from concurrent processes (CLI + scheduled pipeline) drops entries.
5. **I8** `personalscraper/scraper/keywords_cache.py:166-168` — `_load`
   returns `{}` on parse error without backing up the corrupt file. Next
   `set()` overwrites; cache irrecoverably lost.

**Acceptance**:

- `tmdb_client._fetch_videos` is split into two return shapes: keep the
  fail-soft public methods (`fetch_movie_videos`, `fetch_tv_videos`,
  `fetch_tv_season_videos`) but introduce an internal
  `_fetch_videos_strict(...) -> list[Video]` that raises on transport /
  circuit-open / JSON decode errors. The public methods catch and return `[]`;
  the new internal method is the one `trailer_finder.py` calls so it can
  distinguish "real empty" from "error". On error, `trailer_finder.py` skips
  the cache write entirely (just returns None / falls through to YouTube).
- `trailer_finder._youtube_fallback`: same separation. Transport errors,
  breaker-open, `KeyError`/`AttributeError` from yt-dlp parser bugs are
  re-raised internally so `find()` can skip caching. Only a successful query
  with no results is cached as `__no_result__`.
- `trailers_cache.TrailersCache` gains a public TTL-aware `contains_search`
  method (uses `JsonTTLCache.get` internally). `has_cached_search` is removed
  (or kept as a thin alias of `contains_search`); the private `_load` access
  is deleted. `trailer_finder.py` calls only `contains_search` /
  `get_youtube_search` and trusts the TTL.
- `JsonTTLCache._atomic_save` acquires a sibling `.lock` file via
  `fcntl.flock(LOCK_EX | LOCK_NB)` with the same bounded-retry pattern as
  state.py (sub-phase 10.1). Read-modify-write helpers (`set`, `delete`,
  `compact`) hold the lock across the read and the write so concurrent
  writers cannot drop entries.
- `keywords_cache._load` adopts the `_backup_corrupt` pattern from
  `state.py:544-571`: rename the corrupt file to
  `keywords_cache.corrupt-{ts}.json` before returning `{}`, log at WARNING
  with the backup path. Same for `json_ttl_cache._load` (sub-phase 10.2 catch
  is consistent across both caches).

**Tests**:

- `tests/scraper/test_trailers_cache.py`:
  - `test_contains_search_returns_false_after_ttl_expiry` — write entry,
    monkeypatch time forward beyond TTL, assert `contains_search` is False
    even though the file still has the key.
  - `test_set_does_not_drop_concurrent_writes` — two threads / processes
    set distinct keys at the same time; assert both keys survive.
- `tests/scraper/test_trailer_finder.py`:
  - `test_tmdb_outage_does_not_cache_empty_for_a_week` — patch the TMDB
    fetch to raise `CircuitOpenError`; assert no entry written to the
    `TrailersCache`. Patch the next call to return a real movie; assert
    the trailer is found (not blocked by cached `[]`).
  - `test_youtube_fallback_transport_error_does_not_cache_no_result` —
    parallel test for the YouTube fallback path.
- `tests/scraper/test_keywords_cache.py`:
  - `test_corrupt_file_is_backed_up_before_reset` — write garbage to the
    cache file; call `get`; assert the corrupt file was renamed to
    `keywords_cache.corrupt-*.json` and the active file now has empty `{}`.

### 10.3 — Orchestrator status taxonomy & flag wiring (6 findings)

**Findings**:

1. **C2** `personalscraper/pipeline.py:291-299` —
   `--continue-on-trailer-error` is a no-op. Both branches log and continue
   to dispatch. The hint message is misleading. CLAUDE.md docs the flag as
   functional.
2. **C8** `personalscraper/trailers/step.py:25-44` — `verified` parameter
   advertised as "items absent from this list are skipped" but the
   orchestrator is called with no `items` argument, so the list is dropped.
   Items that failed `verify` still get trailer processing.
3. **C10** `personalscraper/trailers/orchestrator.py:291-347, 469-539` —
   three "no URL" outcomes collapse into `NO_TRAILER_AVAILABLE`:
   `_finder is None` (import / init error), TMDB+YouTube outage, and
   genuine "no trailer". Run summary lies: "no_trailer: 47" hides outages.
4. **I5** `personalscraper/trailers/orchestrator.py:303-328` — finder
   exceptions (TMDB outage, JSON decode, bad API key) get persisted as
   `TrailerStatus.SKIPPED_BY_FILTER` — the same status used at line 279
   for "disk-space precheck refused". State taxonomy is corrupted; downstream
   queries that filter `status==skipped_by_filter` get junk.
5. **I6** `personalscraper/trailers/placement.py:106-133` — after the
   `28d9f75` migration, `find_existing_trailer(media_type="tvshow", ...)`
   only checks the new `Trailers/{name}.{ext}` subfolder. TV-show trailers
   downloaded by an earlier commit on this branch at the legacy flat path
   (`{show_dir}/{show_name}-trailer.mp4`) are invisible — re-download
   creates duplicates.
6. **I4** `personalscraper/scraper/trailer_finder.py:289-298` — season
   YouTube fallback constructs `YoutubeSearch(...)` without
   `daily_quota_units` / `search_list_cost_units`, falling back to
   `_DEFAULT_DAILY_QUOTA_UNITS=10_000` regardless of config. Also reaches
   into `self._youtube_search._api_key` / `_quota` / `_breaker` — fragile.

**Acceptance**:

- **C2**: Decision is to **implement** the flag (not document-as-advisory).
  When `trailers_step.status == "error"` and `not continue_on_trailer_error`,
  the pipeline raises `TrailerStepFailed(Exception)` (new) and dispatch is
  skipped. CLI catches it and exits with code `2`. The error log keeps the
  hint text, but it now reflects reality. DESIGN §2 ("trailers are
  non-blocking") is updated: trailers are non-blocking _by default_ and the
  flag opts into hard-fail; that matches the user-facing CLI semantics.
- **C8**: `step.py:run_trailers` builds an `allowed_paths` set from
  `verified` (extracting `Path(item.path)` for items with status
  `success`/`pass`) and passes `items=[scan_item for scan_item in
scanner.scan(...) if scan_item.path in allowed_paths]` to
  `orchestrator.run()`. The "verified absent → skipped" promise is restored.
  If `verified is None` (unit-test or CLI direct invocation) the orchestrator
  falls back to a full staging scan as today.
- **C10 + I5**: Add `TrailerStatus.FINDER_UNAVAILABLE` and
  `TrailerStatus.HTTP_ERROR` (if not already present — `tmdb_client` already
  imports `HTTP_ERROR` per the doc grep, so wire it consistently). New
  orchestrator behaviour:
  - At `run()` entry: if `self._finder is None`, raise
    `RuntimeError("trailers finder unavailable")`. `step.py` catches this
    and reports `status="error"`. **Do not** persist `NO_TRAILER_AVAILABLE`
    for items the orchestrator never inspected.
  - When `find()` raises an exception: persist
    `TrailerStatus.HTTP_ERROR` (or new `FINDER_ERROR` if a more specific
    bucket is wanted) with `next_retry_at` per `retry_policy`. Increment
    `counts["error"]`. Do **not** reuse `SKIPPED_BY_FILTER`.
- **I6**: `find_existing_trailer(media_type="tvshow", ...)` probes the legacy
  flat path BEFORE returning None. If the legacy file exists, log
  `placement.legacy_tvshow_trailer_found` at WARNING with the path and
  return it — the orchestrator's "already present" check skips re-download.
  Add a one-paragraph migration note to `docs/reference/trailers.md`
  pointing operators at a `personalscraper trailers purge --legacy-paths`
  helper if the volume of stranded files becomes a problem (the actual
  helper is out of scope for Phase 10; mention as future work).
- **I4**: Make `daily_quota_units` and `search_list_cost_units` public
  attributes of `YoutubeSearch` (or expose via a `clone(query_format=...)`
  factory). `_youtube_fallback` constructs the new searcher with all
  parameters explicit, no private-attribute reads.

**Tests**:

- `tests/test_pipeline_orchestration.py`:
  - `test_pipeline_aborts_when_trailers_error_and_continue_on_error_false`
    — trailers step returns `StepReport(status="error")`,
    `continue_on_trailer_error=False`; assert `dispatch_recorder` is NOT
    in `order` and a `TrailerStepFailed` was raised.
  - `test_pipeline_continues_when_continue_on_trailer_error_true` —
    same scaffold, opposite flag; assert dispatch ran.
- `tests/trailers/test_step.py`:
  - `test_run_trailers_filters_orchestrator_items_to_verified_paths`
    — pass a `verified` list with one item; assert the orchestrator was
    called with `items=[only the verified one]`.
- `tests/trailers/test_orchestrator.py`:
  - `test_run_raises_when_finder_unavailable` — construct orchestrator
    with `_finder=None`; assert `run()` raises `RuntimeError`.
  - `test_finder_exception_persisted_as_http_error_not_skipped_by_filter`
    — make `_finder.find` raise; assert
    `state[key].status == TrailerStatus.HTTP_ERROR` and `counts["error"]`
    incremented.
- `tests/trailers/test_placement.py`:
  - `test_find_existing_trailer_finds_legacy_flat_tvshow_path` — write a
    legacy `{show_dir}/{name}-trailer.mp4`; assert
    `find_existing_trailer(media_type="tvshow")` returns it (and a WARNING
    is logged).
- `tests/scraper/test_trailer_finder.py`:
  - `test_season_fallback_respects_configured_quota` — construct finder
    with `daily_quota_units=500`; trigger season fallback; assert the new
    `YoutubeSearch` was constructed with `daily_quota_units=500`.

### 10.4 — Error-handling hardening (6 findings)

**Findings**:

1. **I2** `personalscraper/scraper/youtube_search.py:110-115`,
   `tmdb_client.py:639-649` — circuit-breaker open is logged at INFO/warning
   without bubbling up a counter. Long-running outages are buried in
   `youtube_fallback_invoked` events.
2. **I4** `personalscraper/scraper/youtube_search.py:237-252` —
   `_fallback_search` synthesises a `requests.ConnectionError` for _every_
   exception type, including `KeyError`/`AttributeError` from yt-dlp parser
   drift. Pushes the breaker toward open on parser bugs.
3. **I6** `personalscraper/scraper/youtube_search.py:132-142` —
   `_primary_search` has no transport-error retry. A single DNS hiccup is a
   breaker failure (TMDB has tenacity; YouTube doesn't).
4. **I8** `personalscraper/trailers/placement.py:159-200` —
   `write_trailer_url_to_nfo` writes back without atomic temp-file swap.
   SIGINT mid-write truncates the NFO.
5. **I8** (state) `personalscraper/trailers/state.py:511-542, 370-394` —
   `_load` returns `{}` on parse error after a backup; the next `set()`
   writes a 1-entry dict. Backup preserves data, but the WARNING is easy to
   miss. Need a louder error log naming the backup path and the entry-count
   delta.
6. **S1** Inconsistent `exc_info=True` use across error logs in
   `youtube_search.py`, `ytdlp_downloader.py`, `json_ttl_cache.py`,
   `trailers_cache.py`, `state.py`. Picking one rule.
7. **I-extra** `personalscraper/logger.py:13` — redaction regex is exact-match
   (`^(api[_-]?key|...|password)$`). Field names like `youtube_api_key`,
   `tmdb_api_key`, `cookies_file` will NOT match. Secrets leak.

**Acceptance**:

- New `counts["circuit_open"]` bucket in the orchestrator counts dict,
  incremented when `youtube_search` or `tmdb_client` raises / signals
  breaker-open. Surfaced separately in `StepReport`.
- `_fallback_search` exception split: `(KeyError, AttributeError, TypeError)`
  → log at ERROR with `exc_info=True`, do NOT push the breaker (these are
  parser bugs, not network). `(requests.RequestException, OSError,
yt_dlp.utils.DownloadError)` → push breaker as today, also with
  `exc_info=True`.
- `_primary_search` is wrapped in tenacity with
  `make_retryable_predicate` (already exists per `tmdb_client.py`). At
  minimum, mount an `HTTPAdapter` with the same `Retry` strategy as TMDB.
- `placement.write_trailer_url_to_nfo` writes to a sibling temp file
  (`{path}.tmp-{pid}`), `os.replace` to the final path. Mirrors
  `state.py:_save` and `json_ttl_cache._atomic_save`.
- `state.py:_load` post-backup logs at ERROR (not WARNING):
  `trailer_state.data_loss_started` with fields `backup_path=...,
entries_lost=N`. The first subsequent `set()` ALSO logs
  `trailer_state.recovering_from_corrupt` at WARNING with the new
  entry-count.
- One-pass cleanup: every `log.error`/`log.warning` taking an exception
  argument adds `exc_info=True`. Affected lines listed in the review:
  `youtube_search.py:135-141, 159-164, 175, 189, 230-235, 243-248, 261-266`,
  `ytdlp_downloader.py:403-408, 437`, `json_ttl_cache.py:202-208`,
  `trailers_cache.py:103`, `state.py:451, 536, 541, 598-602, 604-609`.
- `personalscraper/logger.py` redaction regex broadens to
  `(?i).*\b(api[_-]?key|authorization|cookie|secret|token|password|cookies?_file)\b.*`
  (or splits into two regexes — one exact-match for top-level keys, one
  substring-match for compound names). New tests cover
  `youtube_api_key`, `tmdb_api_key`, `tvdb_api_key`, `cookies_file`,
  `cookie_file`.

**Tests**:

- `tests/scraper/test_youtube_search.py`:
  - `test_fallback_keyerror_does_not_push_breaker` — patch yt-dlp to raise
    `KeyError`; assert `breaker.failure_count` unchanged, log at ERROR with
    `exc_info`.
  - `test_primary_search_retries_transport_errors` — first two HTTP calls
    raise `requests.ConnectionError`, third succeeds; assert search returns
    a result and breaker not triggered.
- `tests/trailers/test_placement.py`:
  - `test_write_trailer_url_to_nfo_is_atomic_under_simulated_crash` —
    monkeypatch `tree.write` to raise mid-write; assert the original NFO
    file is unchanged on disk.
- `tests/trailers/test_state.py`:
  - `test_corrupt_state_emits_data_loss_error_log` — write garbage to the
    state file, instantiate the store, capture logs; assert
    `trailer_state.data_loss_started` at ERROR with `backup_path` and
    `entries_lost` fields.
- `tests/test_log_redaction.py`:
  - `test_redacts_youtube_api_key_field` — log with `youtube_api_key="..."`;
    assert redacted.
  - `test_redacts_tmdb_api_key_field` — same for TMDB.
  - `test_redacts_cookies_file_path` — log with
    `cookies_file="/Users/foo/.config/youtube_cookies.txt"`; assert path
    redacted (or at least the field name is allowlisted to omit).

### 10.5 — Test gaps (8 findings)

**Findings**:

1. **Critical #1** `tests/resilience/test_pipeline_double_run.py:49`,
   `tests/test_pipeline.py` — bare `MagicMock()` config without
   `config.trailers.enabled = False`, without stubbing `run_trailers`, and
   without setting `state_file`. Real orchestrator runs against MagicMock
   strings → leaks `<MagicMock name='mock.trailers.lock` at repo root.
2. `tests/trailers/test_integration_network.py:62` — uses old
   `CircuitBreaker(errors_threshold=…, cooldown_sec=…)` signature; real one
   is `CircuitBreaker(name, failure_threshold, cooldown_seconds)`. The only
   `@pytest.mark.network` test will TypeError before any network call.
3. `tests/resilience/test_pipeline_double_run.py` — docstring claims
   "9-step pipeline" idempotence but trailers step is unstubbed and trailer
   counts are never asserted. Idempotence of the trailers step is NOT
   actually verified.
4. `tests/test_cli.py:281-300` — `--continue-on-trailer-error` and
   `--skip-trailers` only tested at CLI plumbing layer, not at the
   pipeline-orchestration decision layer.
5. yt-dlp retry contract — pieces tested individually
   (`compute_next_retry_at`, `should_skip` honouring `next_retry_at`,
   counter increments on YTDLP_ERROR) but no end-to-end test asserts
   "run #1 errors → run #2 skips honour the cool-down → run #3 (after
   cool-down) re-attempts".
6. `tests/trailers/test_cli.py:274-298` — `verify --deep` covers happy
   path only. ffprobe non-zero exit, zero-duration output, FileNotFoundError
   for missing ffprobe — all uncovered.
7. `tests/scraper/test_trailers_cache.py` — TTL invalidation at the
   `TrailersCache` layer (vs the underlying generic `JsonTTLCache`) not
   asserted. If `TrailersCache` ever derives its own TTL math, the
   regression net is missing.
8. `tests/trailers/test_orchestrator.py:303-308` and
   `test_integration_hermetic.py:361-369` — `lib_item` is bare `MagicMock()`
   with `.path`, `.category`, `.nfo.tmdb_id`, `.nfo.imdb_id`. If the
   orchestrator starts reading another field, MagicMock auto-attributes
   silently. Switch to `MagicMock(spec=LibraryScanItem)` or real instances.

**Acceptance**:

- `tests/conftest.py`: a session-scoped autouse fixture
  `_no_magicmock_files_leaked` that snapshots cwd at session start, then
  fails (with the offending paths listed) at session end if any files
  matching `<MagicMock*` exist.
- `tests/resilience/test_pipeline_double_run.py`: fixture sets
  `config.trailers.enabled = False` AND patches `run_trailers` (defence in
  depth). Two new assertions on `report2`:
  `report2.steps["trailers"].status in {"skipped", "success"}` and
  `report2.steps["trailers"].counts.get("downloaded", 0) == 0`.
- `tests/test_pipeline.py`: same fixture fix; tests
  `test_dispatch_skipped_when_no_verified`,
  `test_dispatch_skipped_when_verify_crashes`,
  `test_gate_warning_does_not_block` updated.
- `tests/trailers/test_integration_network.py:62`: `CircuitBreaker` call
  fixed to `CircuitBreaker(name="youtube-network-test",
failure_threshold=5, cooldown_seconds=60)`.
- `tests/trailers/test_orchestrator.py`:
  - `test_ytdlp_failure_round_trip_persists_retry_then_skips_then_retries`:
    run 1 hits `YTDLP_ERROR`, run 2 (within cool-down) skips, run 3
    (with `last_attempt` mocked into the past) re-attempts.
  - LibraryScanItem mocks switched to `MagicMock(spec=LibraryScanItem)`
    or real instances.
- `tests/trailers/test_cli.py`:
  - `test_verify_deep_flags_corrupt_trailer` (ffprobe exit != 0).
  - `test_verify_deep_flags_zero_duration_trailer` (stdout `"0.0"`).
  - `test_verify_deep_handles_missing_ffprobe` (FileNotFoundError →
    warn-and-treat-as-shallow, no crash).
- `tests/scraper/test_trailers_cache.py`:
  - `test_get_youtube_search_returns_none_after_ttl_expiry` (covers the
    facade layer, not just the underlying cache).

### 10.6 — Documentation refresh (10 findings)

**Findings**:

1. `docs/reference/trailers.md:186-199` — describes the OLD flat TV-show
   placement (`Breaking Bad (2008)/Breaking Bad (2008)-trailer.mp4`). After
   `28d9f75`, TV shows live in `Trailers/{name}.{ext}` subfolder.
2. `docs/reference/naming.md:51-71` — same: `## Trailer File Naming`
   section presents flat naming for movies AND TV shows AND seasons.
3. `CLAUDE.md:121` — Reference Index trigger row says "flat
   `{name}-trailer.{ext}` placement" — false for TV shows now.
4. `personalscraper/trailers/step.py:30-32` — docstring says "places files
   next to media". Only true for movies.
5. `personalscraper/pipeline.py:271` — same "next to media" misleading
   phrasing.
6. `docs/reference/trailers.md:165` — composite key table shows
   `manual:sha256:{hash}` but actual code at `state.py:279` is
   `f"manual:{digest}"` (no `:sha256:` segment).
7. `docs/reference/architecture.md:57` — "8-step pipeline" (now 9, line 19
   already correct).
8. `docs/reference/architecture.md:47-51` — trailer module bullets missing
   `│` tree prefix; visual inconsistency.
9. `personalscraper/scraper/json_ttl_cache.py:93-94` and
   `keywords_cache.py:60-63` — docstrings claim parent dir "must exist; not
   created automatically" but `_atomic_save` does
   `mkdir(parents=True, exist_ok=True)`.
10. `personalscraper/trailers/placement.py:162-163` — stale line refs
    (160/269 → actual 181/290).
11. `personalscraper/scraper/ytdlp_downloader.py:209-215` —
    `DownloadStatus.HTTP_ERROR` enum member is dead code (orchestrator has
    a branch for it that can never fire because `download()` never returns
    it). Either wire it (Phase 10.1 may already touch this) or remove the
    enum + orchestrator branch.
12. `personalscraper/scraper/ytdlp_downloader.py:326-327` — comment says
    "Suppress yt-dlp's own progress output" but `no_warnings: False` does
    the opposite. Either flip to `True` or rewrite the comment.
13. `personalscraper/scraper/tmdb_client.py:601-604` —
    `fetch_tv_season_videos` documents `Raises:` "propagates circuit-breaker
    open" — but `_fetch_videos` is fail-soft and never re-raises.
14. `personalscraper/trailers/orchestrator.py:108-138` — step labels
    `1, 2, 2bis, 3a, b, b-new, c, d, e, f, g, h, 4`. Renumber straight 1..N.
15. `personalscraper/trailers/state.py:233-234` — hardcodes "v0.7.0" in
    a comment; will rot at 0.8.0. Rephrase generically.
16. `personalscraper/trailers/cli.py:1-20` — module docstring lists
    `--dry-run` as common to all subcommands but `scan` and `verify` lack it.
17. `personalscraper/trailers/state.py:5-6` — claims state file is at
    `.data/trailers_state.json` "relative to the project root" without
    noting it's actually `config.trailers.state_file` (configurable).
18. "2026-04-25 incident" annotations in `orchestrator.py:131`,
    `cli.py:274`, `scanner.py:97-99` — opaque to future maintainers.
    Replace with commit/PR refs (`see commit 3792ea9`).

**Acceptance**:

- `docs/reference/trailers.md`:
  - Rewrite the placement section (currently 186-199) to describe the
    actual conventions per `placement.py`:
    - Movies: `{media_dir}/{name}-trailer.{ext}` (flat).
    - TV shows: `{media_dir}/Trailers/{name}.{ext}` (subfolder).
    - Seasons: `{show_dir}/Saison {NN}/Trailers/{show_dir.name} - Saison {NN}.{ext}`.
  - Fix the composite-key example to `manual:{hash}`.
  - Add a one-paragraph migration note for users with stranded
    legacy-flat-path TV-show trailers (Phase 10.3 finding I6).
- `docs/reference/naming.md`: rewrite `## Trailer File Naming` section to
  match the same contract.
- `CLAUDE.md:121`: replace "flat `{name}-trailer.{ext}` placement" with
  "Plex-conformant placement (movies flat, TV shows in `Trailers/`
  subfolder)".
- `personalscraper/trailers/step.py:30-32` and `pipeline.py:271`: replace
  "places files next to media" with "places files using the per-type Plex
  placement convention (see `trailers.placement`)".
- `docs/reference/architecture.md:57` → "9-step pipeline orchestrator".
  Lines 47-51: add `│` prefix to trailer module bullets to match the rest
  of the tree.
- `personalscraper/scraper/json_ttl_cache.py:93-94` and
  `keywords_cache.py:60-63`: drop the false "parent must exist" claim;
  document that the parent directory is created on first write.
- `personalscraper/trailers/placement.py:162-163`: drop the parenthetical
  line numbers (or replace with `_build_movie_nfo` / `_build_tv_nfo`).
- `personalscraper/scraper/ytdlp_downloader.py:209-215`: if Sub-phase 10.1's
  output-verification path emits `HTTP_ERROR` for some HTTP failures, leave
  the enum and document the new producer. Otherwise, remove the enum AND the
  orchestrator branch handling it (`orchestrator.py:406-424`).
- `personalscraper/scraper/ytdlp_downloader.py:326-327`: choose one — set
  `no_warnings: True` (matches comment) OR rewrite the comment ("Forward
  yt-dlp warnings; we already silence the progress bar via `quiet`"). Pick
  whichever matches the desired log volume.
- `personalscraper/scraper/tmdb_client.py:601-604`: drop the `Raises:`
  section in `fetch_tv_season_videos`'s docstring.
- `personalscraper/trailers/orchestrator.py:108-138`: renumber `run()`
  step labels 1..N straight; drop "2bis" / "b-new" / suffixes.
- `personalscraper/trailers/state.py:233-234`: replace "for v0.7.0" with
  "in this initial trailer feature release".
- `personalscraper/trailers/cli.py:1-20`: move `--dry-run` out of "common
  filters" and document it per-subcommand (only `download` and `purge`
  have it).
- `personalscraper/trailers/state.py:5-6`: append "(default; configurable
  via `config.trailers.state_file`)".
- `2026-04-25 incident` annotations: replace with `see commit 3792ea9`
  / `see commit 28d9f75` as applicable. Keep the prose context.

### 10.7 — Quality gate + milestone commit

**Acceptance**:

- All sub-phase 10.1–10.6 tests pass: `make test`.
- Lint: `make lint` clean.
- Type: `python -m mypy personalscraper/trailers/ personalscraper/scraper/trailer_finder.py personalscraper/scraper/json_ttl_cache.py personalscraper/scraper/trailers_cache.py personalscraper/scraper/youtube_search.py personalscraper/scraper/ytdlp_downloader.py personalscraper/scraper/tmdb_client.py personalscraper/scraper/keywords_cache.py personalscraper/pipeline.py personalscraper/logger.py` — `Success: no issues found`.
- Coverage: trailer module suite still ≥ the post-Phase 9 baseline
  (orchestrator ≥ 93%, scanner ≥ 98%, downloader unchanged).
- Repo cleanliness: `git status` shows no `<MagicMock*` artefacts after a
  full `make test`.
- Manual smoke: `python -m personalscraper trailers --help` and each
  subcommand `--help` print without error.
- Update `IMPLEMENTATION.md` "Review cycles" section: add Cycle 3 record
  (40 retained, breakdown by severity).

**Milestone commit**:

```bash
git commit --allow-empty -m "chore(trailer): phase 10 gate — pr-review cycle 3 — 40 retained findings + new tests"
```

## Quality gates (after all sub-phases)

- `ruff check personalscraper/ tests/`
- `ruff format --check personalscraper/ tests/`
- `python -m mypy ...` (full module list per Sub-phase 10.7)
- `make test` — full suite green; expected delta: +~25 new tests across
  all sub-phases.
- `git status` clean (no `<MagicMock*` files, no `*.lock` leftovers).

## Out of scope for this cycle

- **`personalscraper trailers purge --legacy-paths` helper** for stranded
  TV-show trailer files at the flat path. The doc reference in 10.3/I6
  forward-references a follow-up PR; the helper itself is not implemented
  here. (Volume of stranded files is likely small — branch lifetime is short.)
- **Refactor of `_lookup_library_item` data structure** (review S10) —
  O(n) lookup against a `(category, id)` index that ignores the category
  dimension. The docstring already acknowledges this is intentional; flat
  index would be clearer but the perf cost is negligible at current
  library sizes.
- **`Scanner._is_scan_fresh` cross-process cache** (review S4) — the in-memory
  freshness gate is per-instance only; a process-level cache would help
  CLI invocations but the current daily-pipeline flow already creates the
  scanner once. Documented as in-memory-only in Sub-phase 10.6 if not
  already.
- **Retry-budget regression assertions for season-level YouTube fallbacks**
  beyond the new quota-forwarding test — covered indirectly by the existing
  fallback test.
- **`continue_on_trailer_error` UX rename** — the flag stays as-is once
  Sub-phase 10.3 wires it correctly.
- **Cosmetic: `noqa: BLE001` audit across the codebase** — left to a
  follow-up cleanup PR; this cycle only touches `BLE001` sites where the
  catch is a real defect (10.4).
