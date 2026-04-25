# Phase 11 — PR fixes cycle 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

Fixes identified during PR review cycle 4 — the post-cycle-3 review pass run by
`/implement:pr-review` after CI green on commit `918e070`. Four reviewers
(code, tests, errors, comments) returned a fresh batch.

Total retained: **22 findings** (7 critical, 8 major, 7 medium).
Ignored: design-coherent suggestions and minor polish (see "Out of scope" at the
bottom).

The critical findings cluster around three pathologies introduced or unfixed
by cycle 3:

1. **`TrailerStateLocked` only caught in `step.py`** — the bounded-retry lock
   was supposed to prevent silent deadlock, but every other call site in the
   orchestrator and CLI leaks the exception unprotected.
2. **Cache poisoning prevention is half-done** — the strict TMDB/YouTube
   variants were supposed to skip caching `__no_result__` on outage, but
   parser-drift `TypeError` from yt-dlp and transport errors still slip
   through `_fallback_search`'s fail-soft contract → cached for 7d.
3. **Cycle 3's claimed test work was partial** — `MagicMock(spec=…)`
   tightening was advertised but never landed; `verify --deep` error paths
   were listed in the plan but only the happy path was delivered; a comment
   at `test_orchestrator.py:17` actively misleads.

Sub-phases are organized by code area, not by severity, so each commit lands a
coherent slice.

## Sub-phases

### 11.1 — Lock-contention defence in depth (4 findings)

**Findings**:

1. **C1 silent-failure-hunter** — `TrailerStateLocked` unhandled outside
   `step.py:124`:
   - `personalscraper/trailers/orchestrator.py:163` — `auto_gc()` is the
     orchestrator's first call. Bubbles through `step.py`'s catch (fine for
     pipeline) but also through `cli.py` `download` (raw traceback to user).
   - `personalscraper/trailers/orchestrator.py:227, 342, 362, 397, 420, 438, 458`
     — every per-item `_state_store.set(...)` call is unprotected. A peer
     process holding the lock for >1.5s aborts the whole orchestrator mid-loop.
   - `personalscraper/trailers/cli.py:732` — `state_store.purge_orphans()` raw
     traceback path.
2. **C2 silent-failure-hunter** — `state.py:_acquire_lock` catches every
   `OSError` as "contention". `EBADF` (closed fh), `EINVAL` (bad operation),
   NFS lock-not-supported all silently retry. Real bugs hidden behind
   "couldn't acquire lock".

**Acceptance**:

- `state.py:_acquire_lock` inspects `errno`. Only `EAGAIN`/`EWOULDBLOCK` map
  to retry; other `OSError` instances log `trailer_state_lock_unexpected_oserror`
  at ERROR with `errno`, `exc_info=True`, and re-raise the original exception
  unchanged.
- New helper `_with_lock_retry` (or inline pattern) in `orchestrator.py` wraps
  per-item `state_store.set(...)` so a `TrailerStateLocked` for one item logs
  `trailers_state_locked_for_item` and increments `counts["error"]`, then
  continues to the next item rather than aborting the whole loop. The
  orchestrator-wide `auto_gc()` at entry stays unprotected (a contended GC
  is a real failure that should propagate).
- `cli.py:732` (`purge_orphans` site) wraps in `try/except TrailerStateLocked`
  and emits `[red]Another trailers process is running; try again later.[/red]`
  - `raise typer.Exit(1)`.
- Same pattern at any other CLI subcommand that calls `state_store.set()` or
  `purge_orphans` directly — audit `cli.py` for missing handlers.

**Tests**:

- `tests/trailers/test_state.py`:
  - `test_acquire_lock_re_raises_unexpected_oserror` — patch `_fcntl.flock` to
    raise `OSError(errno.EBADF, "bad fd")`; assert raised exception is the
    original OSError, log event `trailer_state_lock_unexpected_oserror` at
    ERROR.
- `tests/trailers/test_orchestrator.py`:
  - `test_per_item_lock_contention_continues_loop` — mock state_store.set to
    raise `TrailerStateLocked` for one item only; assert orchestrator
    completes the rest of the loop, `counts["error"] == 1`, log event
    `trailers_state_locked_for_item`.
- `tests/trailers/test_cli.py`:
  - `test_purge_orphans_handles_lock_contention` — patch `state_store.purge_orphans`
    to raise `TrailerStateLocked`; assert exit code 1 and the "Another
    trailers process is running" message.

### 11.2 — Cache-poisoning closure (3 findings)

**Findings**:

1. **I1 code-reviewer + I1 silent-failure-hunter** — YouTube fallback
   cache-poisoning prevention is half-done. `_youtube_fallback_strict`
   (`trailer_finder.py:251`) re-raises `(CircuitOpenError, RequestException,
KeyError, AttributeError)` from `_call_youtube_search`, but
   `_fallback_search` in `youtube_search.py:292` catches `(KeyError,
AttributeError, TypeError)` internally and returns None — cached as
   `__no_result__` for 7d. Asymmetry: `TypeError` is only swallowed at the
   inner layer.
2. **I2 silent-failure-hunter** — Same gap on the breaker-just-opened-during-
   this-call path: `searcher.search()` returns None on a fresh transport
   failure that records the breaker.
3. **I11 silent-failure-hunter** — non-dict TMDB JSON: `_fetch_videos_strict`
   calls `data.get("results")` without verifying `data` is a dict.
   `AttributeError` leaks past `find()`'s `except (TMDBError, CircuitOpenError,
requests.RequestException, json.JSONDecodeError)`.

**Acceptance**:

- `youtube_search.py:_fallback_search` exception split is rebalanced:
  - `(KeyError, AttributeError, TypeError)` are re-raised (NOT caught) so
    `_youtube_fallback_strict` can decide caching policy uniformly. The
    project's other error-class handling (breaker push) is moved to the
    re-raise path: log at ERROR with `exc_info=True`, do NOT push the breaker
    for parser drift, then re-raise.
  - `(requests.RequestException, OSError, yt_dlp.utils.DownloadError)` →
    log at WARNING, push breaker, re-raise (cycle 3 was supposed to push +
    return None; raise instead so the strict layer skips caching).
- `_call_youtube_search` (`trailer_finder.py`) snapshots
  `searcher._breaker.is_open` before and after; if it transitioned closed → open,
  raise `CircuitOpenError("breaker opened during call")` post-hoc to skip
  cache write.
- `tmdb_client.py:_fetch_videos_strict` validates `isinstance(data, dict)`
  before `data.get("results")`. Non-dict JSON raises `TMDBError("malformed
response: expected object, got <type>")` (or a new `TMDBSchemaError`).
- `trailer_finder.py:find()` widens its `except` to include
  `(AttributeError, TypeError)` defensively (not the primary fix — the
  primary fix is at the validation boundary in `tmdb_client`).

**Tests**:

- `tests/scraper/test_trailer_finder.py`:
  - `test_youtube_fallback_typeerror_does_not_cache_no_result` — patch
    `YoutubeSearch._fallback_search` to raise `TypeError`; assert no
    `__no_result__` entry written to cache.
  - `test_breaker_just_opened_during_call_does_not_cache` — manipulate the
    breaker state during a call so it transitions closed → open;
    assert no cache write.
- `tests/scraper/test_tmdb_client_videos.py`:
  - `test_fetch_videos_strict_raises_on_non_dict_response` — patch
    `_get` to return `["not", "a", "dict"]`; assert
    `TMDBError`/`TMDBSchemaError` raised.

### 11.3 — Cache hygiene (3 findings)

**Findings**:

1. **I2 code-reviewer** — `JsonTTLCache._load` (line ~365) and
   `keywords_cache._load` (line ~209) catch `OSError` and call `_backup_corrupt`.
   A flaky NFS / EBUSY / stale-handle on a network share creates a `.corrupt-*`
   file flood despite the original being healthy. Compare `state.py:_load`
   which already splits the two cases.
2. **I3 code-reviewer / 2 comment-analyzer** — `trailers_cache.has_cached_search`
   docstring still claims TTL-bypassing behavior; body delegates to
   `contains_search` (TTL-aware). Misleading.
3. **I8 silent-failure-hunter** — `youtube_search.py:_build_youtube_session`
   `Urllib3Retry(status_forcelist=[500, 502, 503, 504])` is missing 429.
   YouTube quota/rate-limit responses are sometimes 429 and should be retried
   with backoff at the transport layer.

**Acceptance**:

- `JsonTTLCache._load` and `keywords_cache._load` mirror `state.py:_load`
  asymmetry: `OSError` → log at WARNING + return `{}` (no backup);
  `(json.JSONDecodeError, ValueError)` → backup + log at ERROR.
- `trailers_cache.has_cached_search` docstring rewrites: "Deprecated alias for
  `contains_search`. Originally TTL-unaware, now delegates to the TTL-aware
  variant; new code should use `contains_search`. The legacy TTL-bypassing
  behavior is gone."
- `youtube_search.py:_build_youtube_session` adds `429` to `status_forcelist`.

**Tests**:

- `tests/scraper/test_json_ttl_cache.py`:
  - `test_oserror_during_load_does_not_create_backup` — patch `Path.read_text`
    to raise `OSError(errno.EBUSY, ...)`; assert no `.corrupt-*` sibling.
- `tests/scraper/test_keywords_cache.py`:
  - Parallel `test_oserror_during_load_does_not_create_backup`.
- `tests/scraper/test_youtube_search.py`:
  - `test_primary_search_retries_on_429` — first response 429, second 200;
    assert single returned result via session retry.

### 11.4 — Atomic write + redaction correctness (2 findings)

**Findings**:

1. **I7 silent-failure-hunter** — `placement.write_trailer_url_to_nfo`:
   - Cleanup is in `OSError` only; `tree.write()` may raise
     `xml.etree.ElementTree.ParseError`-adjacent errors,
     `UnicodeEncodeError`, `TypeError` for non-encodable URLs. None of
     these trigger cleanup → orphan `.tmp-{pid}` files.
   - Function returns silently after logging — caller never knows whether
     NFO update succeeded. Plex's `<trailer>` tag stays empty even though
     the trailer is on disk.
   - Inner `except OSError: pass` (line 229) is the empty-pass anti-pattern.
2. **I10 silent-failure-hunter** — `logger.py:_SECRET_KEY_COMPOUND_RE`
   over-matches `cookie_count`, `token_count`, `secret_count`,
   `password_count`. The compound alternation includes bare `cookie|secret|
token|password`, which match against compound names where the secret
   word is just a prefix segment. Integer counters get redacted as
   `***REDACTED***`.

**Acceptance**:

- `placement.write_trailer_url_to_nfo`:
  - Wrap `tree.write` + `os.replace` in `try` / `finally:
tmp_path.unlink(missing_ok=True)` so cleanup runs on every error path
    regardless of exception type.
  - Return `bool` (success/failure) so the caller can branch. Update the
    one call site in `orchestrator.py` to log `placement.nfo_update_failed`
    when False is returned.
  - Replace inner `except OSError: pass` with `except OSError as exc:
log.debug("placement.tmp_cleanup_failed", path=str(tmp_path),
error=str(exc))`.
- `logger.py:_SECRET_KEY_COMPOUND_RE` tightens: drop the bare
  `cookie|secret|token|password` alternation and only keep the compound
  forms (`api[_-]?key`, `cookies?[_-]file`, `authorization`). The exact-match
  regex `_SECRET_KEY_RE` already covers bare `cookie`/`secret`/`token`/
  `password` field names.

**Tests**:

- `tests/trailers/test_placement.py`:
  - `test_write_trailer_url_to_nfo_cleans_up_tmp_on_unicode_error` —
    monkeypatch `tree.write` to raise `UnicodeEncodeError`; assert no
    `.tmp-*` left behind, function returns False.
  - `test_write_trailer_url_to_nfo_returns_false_on_failure` — generic
    error path; assert return type and value.
- `tests/test_log_redaction.py`:
  - `test_does_not_redact_cookie_count_field` — log with `cookie_count=42`;
    assert `42` (or stringified int) appears in output, not `***REDACTED***`.
  - Same pattern for `token_count`, `secret_count`, `password_count`.

### 11.5 — Doc + comment correctness (5 findings)

**Findings**:

1. **1 comment-analyzer** — `pipeline.py:86-88` (`__init__` docstring) says
   "trailers is always non-blocking". The new `TrailerStepFailed` raise
   contradicts this.
2. **3 comment-analyzer** — `pipeline.py:182` `run()` docstring still labels
   trailers as "Phase 5bis". Sub-phase 8a99320 renumbered orchestrator step
   labels but missed pipeline-level.
3. **6 comment-analyzer** — `docs/reference/architecture.md:78` `resilience/`
   tree row is missing the `│` prefix. caf4665 only fixed lines 47-51.
4. **4 comment-analyzer** — `_youtube_fallback_strict` (`trailer_finder.py`)
   `Raises:` block lists exception types it cannot raise. Tighten to
   `CircuitOpenError` plus the new types from sub-phase 11.2.
5. **5 comment-analyzer** — `_verify_output` (`ytdlp_downloader.py:374`)
   docstring says "minimum size" / "large enough"; the check is `<= 0`.
   Misleading.

**Acceptance**:

- `pipeline.py:86-88`: rewrite to "non-blocking by default; per-item failures
  are logged and dispatch proceeds. `continue_on_trailer_error=False` (the
  default) aborts dispatch when the trailers step returns
  `status='error'` — typically only on lock contention or unexpected crash."
- `pipeline.py:182`: rename "Phase 5bis" to "Phase 6 — TRAILERS" and
  renumber DISPATCH to "Phase 7" (assuming current docstring reads
  "Phase 6: DISPATCH"; verify the actual sequence).
- `architecture.md:78`: add `│` prefix to the `resilience/` line so it
  matches the rest of the `tests/` subtree.
- `trailer_finder.py:_youtube_fallback_strict`: `Raises:` lists only the
  exceptions actually produced after sub-phase 11.2's rebalancing.
- `ytdlp_downloader.py:_verify_output` docstring rewrites: "Verify the
  expected output file exists and is non-empty. Also probes the parent
  directory for a sibling with a different extension (diagnostic only —
  indicates ffmpeg-merge failure). The configurable size threshold is
  enforced separately by `placement.trailer_exists()`."

**Tests**: doc-only changes; no new tests required. Verify by `Read`-ing
each modified region.

### 11.6 — State-store error semantics (3 findings)

**Findings**:

1. **I4 silent-failure-hunter** — `state.py:_count_entries_lost` re-parses
   the corrupt file with the same `json.loads`; on `JSONDecodeError`,
   `entries_lost` is always 0. Operator reads `entries_lost=0` and assumes
   nothing was lost, when in fact the file may have contained 1000 entries.
2. **I6 silent-failure-hunter** — `_save` raises `OSError` (disk full,
   read-only fs, NFS stale handle). `set()` callers don't catch distinctly;
   `step.py`'s blanket catch produces `trailers_step_crashed` event,
   conflating ops-transient errors with logic bugs.
3. **I3 pr-test-analyzer** — `continue_on_trailer_error` E2E coverage is
   shallow. Both branches tested but `run_trailers` is stubbed; the bridge
   "real orchestrator → StepReport.status='error' → pipeline raises
   TrailerStepFailed" is never tested in one chain.

**Acceptance**:

- `state.py:_count_entries_lost` adds a heuristic: count occurrences of
  `"status":` substrings in the raw text as a lower-bound estimate. Rename
  the log field from `entries_lost` to `min_entries_lost` and document the
  field is best-effort.
- `step.py` adds `except OSError as exc:` ahead of the generic catch.
  Distinct event name `trailers_state_write_failed` with `errno=exc.errno`,
  `path=...`, `exc_info=True`. Returns `StepReport(status="error",
notes=f"state write failed: {exc.strerror}")`.
- `tests/test_pipeline_orchestration.py` adds:
  - `test_real_run_trailers_failure_propagates_TrailerStepFailed_to_pipeline`
    — wire a real `run_trailers` with a `TrailersOrchestrator` whose
    `_state_store.set` raises `TrailerStateLocked`; run pipeline with
    `continue_on_trailer_error=False`; assert `TrailerStepFailed` raised
    and dispatch did NOT execute.

**Tests**:

- `tests/trailers/test_state.py`:
  - `test_count_entries_lost_returns_lower_bound_on_corrupt_json` —
    write file with 5 truncated entries; assert `_count_entries_lost`
    returns 5 (or close), not 0.
- `tests/trailers/test_step.py`:
  - `test_state_write_failure_returns_status_error_distinct_event` —
    patch `state_store.set` to raise `OSError(errno.ENOSPC, ...)`; assert
    `StepReport(status="error")` and log event
    `trailers_state_write_failed`.
- `tests/test_pipeline_orchestration.py`:
  - The end-to-end `TrailerStepFailed` propagation test as above.

### 11.7 — Test sentinel + coverage gaps (4 findings)

**Findings**:

1. **C1 pr-test-analyzer** — `tests/trailers/test_orchestrator.py:17`
   comment claims `MagicMock(spec=…)` was applied; in fact zero specs are
   used. 8 bare `MagicMock()` spots remain (lines 30, 307, 350, 355, 402,
   545, 580, 624).
2. **C2 pr-test-analyzer** — `verify --deep` error-path tests claimed in
   sub-phase 10.5's plan never landed. `tests/trailers/test_cli.py:272-296`
   has only the happy path.
3. **I1 pr-test-analyzer** — `_no_magicmock_files_leaked` (sentinel) only
   globs root cwd; misses subdirs like `cwd/.data/`.
4. **I2 pr-test-analyzer** — round-trip retry test
   (`test_ytdlp_failure_round_trip_persists_retry_then_skips_then_retries`)
   doesn't independently re-read state file from disk between runs;
   regression to in-memory class-level cache would silently pass.

**Acceptance**:

- `tests/trailers/test_orchestrator.py`: tighten 6+ bare MagicMock spots to
  `MagicMock(spec=LibraryScanItem)` (or real `LibraryScanItem` instances).
  Specifically the `_make_lib_item` helper around line 30 and the inline
  `lib_item = MagicMock()` blocks at the tagged lines. The misleading
  comment at line 17 either gets accurate (specs now used) or is removed.
- `tests/trailers/test_cli.py`: add the three missing tests from
  sub-phase 10.5's plan:
  - `test_verify_deep_flags_corrupt_trailer` — ffprobe returncode != 0.
  - `test_verify_deep_flags_zero_duration_trailer` — stdout `"0.0\n"`.
  - `test_verify_deep_handles_missing_ffprobe` — subprocess raises
    `FileNotFoundError`.
- `tests/conftest.py:_no_magicmock_files_leaked`: replace `glob` with
  `Path.cwd().rglob("<MagicMock*")`. Anchor depth (e.g. exclude common
  cache dirs) so the assertion stays fast.
- `tests/trailers/test_orchestrator.py`: round-trip retry test adds an
  intermediate disk read between runs:
  `assert (tmp_path / ".data/trailers_state.json").read_text()` contains
  the expected entry shape.

**Tests**: the acceptance items ARE the tests. Plus:

- `tests/conftest.py`:
  - `test_sentinel_catches_magicmock_in_subdir` (in a separate test file
    like `tests/test_conftest_sentinel.py`) — write a `<MagicMock*` file
    inside `cwd/.data/` and verify the sentinel detects it on next teardown.

### 11.8 — Quality gate + milestone commit

**Acceptance**:

- All sub-phase 11.1–11.7 tests pass: `make test`.
- Lint: `make lint` clean.
- Type: full mypy pass.
- Coverage: orchestrator coverage back to ≥ 93% (cycle-3 baseline).
- Repo cleanliness: `git status` clean.
- Update `IMPLEMENTATION.md` "Review cycles" — record Cycle 4 outcome.

**Milestone commit**:

```bash
git commit --allow-empty -m "chore(trailer): phase 11 gate — pr-review cycle 4 — 22 retained findings"
```

## Quality gates (after all sub-phases)

- `ruff check personalscraper/ tests/`
- `ruff format --check personalscraper/ tests/`
- `python -m mypy personalscraper/`
- `make test` — full suite green; expected delta: +~15 new tests across
  all sub-phases.

## Out of scope for this cycle

- **`silent-failure-hunter C3`** — `_resolve_lock_holder_pid` blanket
  `except Exception` is acceptably defensive (best-effort PID resolution,
  errors don't matter). The 2s `lsof` timeout is fine in practice.
- **`silent-failure-hunter I3`** — defensive `pipeline._run_step`
  hardening for hypothetical future re-routing of `TrailerStepFailed`.
  Today's path is correct; defensive `except TrailerStepFailed: raise`
  is clutter without an active threat.
- **`silent-failure-hunter I5`** — duplicate-corruption silent skip in
  `_backup_corrupt_with_data_loss`. Edge case; the recovery flag is the
  right primary mechanism.
- **`silent-failure-hunter I9`** — `circuit_open` counter only increments
  at the orchestrator. This is a reporting-granularity choice, not a
  correctness bug. Document the metric semantics elsewhere.
- **`comment-analyzer 7-13`** — various polish (Windows fallback wording,
  cross-file rationale duplication, legacy-path TODO consolidation, stale
  `2026-04-25` annotations in some test files, etc.). These can wait for a
  next-PR cleanup.
- **Procedural drift in cycle-3 commits `1f2dc6d`** — already accepted in
  cycle 3; not worth a history rewrite at this depth.
- **`code-reviewer S5` stale `2026-04-25` annotations** — incomplete
  sweep, but the remaining instances are descriptive context, not
  misleading. Polish for a future cleanup.
