# Design — Trailer download-failure → YouTube-search fallback

**Codename**: trailer-fallback
**Type**: minor (0.34.1 → 0.35.0)
**Origin**: real pipeline run 2026-06-16-18h28 — 25/30 trailers downloaded; the 2 misses ("Super Mario Galaxy" → YouTube "video not available", "FROM" → geo-blocked to US) were download-stage failures on a TMDB-found URL with no second-source attempt. Root cause adversarially verified (study `tasks/w6kopxoam.output`, 9 agents + 3 verifiers).

## Problem

TMDB discovery found a trailer URL for ALL items (`No trailer: 0`), but the per-item flow downloads exactly ONE URL (`orchestrator.py:494`) and, on any non-SUCCESS status, writes a terminal failure state (`else/YTDLP_ERROR` branch, `orchestrator.py:615-637`) with **no alternative-source attempt**. The existing TrailerFinder "TMDB-first / YouTube-fallback" (`trailer_finder.py`) only fires its YouTube tier when TMDB returns NO video — not when a found URL fails to download. So a dead/geo-blocked TMDB URL is a hard miss.

## Design — same-run, in-loop fallback

When the (first) download fails, attempt the YouTube **search** engine once for an alternative upload, then re-download. One extra attempt; structurally minimal.

### Hook point

`personalscraper/trailers/orchestrator.py:494`, immediately after `result = self._downloader.download(url, expected_path)` and BEFORE the status-dispatch block (`497-637`, left structurally untouched). Insert:

- if `result.status != DownloadStatus.SUCCESS` AND `cfg.trailers.fallback_youtube_search` AND fallback not yet tried:
  - `alt = self._youtube_search_fallback(item)`
  - if `alt and alt not in tried`: `tried.add(alt)`, `url = alt` (so state/NFO/event record the URL actually used), `result = self._downloader.download(url, expected_path)` — exactly once.
- Then fall into the EXISTING unchanged SUCCESS/BOT_DETECTED/HTTP_ERROR/else dispatch (it simply sees the second `result` + updated `url`).

### New helper

`TrailersOrchestrator._youtube_search_fallback(item) -> str | None` (near `_build_finder`, `orchestrator.py:655`) → delegates to `self._finder._youtube_search.search(item.title, item.year)` (real `YoutubeSearch`, `youtube_search.py:124` `search(self, title: str, year: int|None) -> str|None`, fail-soft). Wrap in `CircuitOpenError` handling (mirror `orchestrator.py:415-417`) so a tripped YouTube breaker is a clean no-fallback, not a crash. **Do NOT call `finder.find()`** (would re-hit the dead TMDB tier + risk writing the `__no_result__` cache sentinel). Uses `personalscraper.logger.get_logger`.

### Why same-run (not cross-run)

On failure the else branch writes `next_retry_at = +1 day`; `should_skip()` (`state.py:573`) then skips the item at the loop-entry gate (`orchestrator.py:295`) on the NEXT run before `find()`/`download` — a cross-run fallback could never fire. So the fallback MUST run in the same item-iteration, before the terminal failure state is written.

### State / idempotence (preserved byte-for-byte)

State is written exactly ONCE, after the (possibly second) download, by the unchanged dispatch block. `attempts` stays 1 (one logical item-attempt, internally up to 2 URLs). The `tried`-set makes a self-returning YouTube URL a no-op (no double-download/charge). When the fallback ALSO fails → identical terminal `YTDLP_ERROR`/`HTTP_ERROR` state + `next_retry_at` + counters as today.

### Config

New field `TrailersConfig.fallback_youtube_search: bool = True` (`conf/models/trailers.py`). Already set on MagicMock cfgs in 5 test files but NOT a real model field — wire it; read once in `run()` near `orchestrator.py:264`. Pre-1.0 → add in place, no migration; update the `config.example` trailers overlay in lock-step.

### Cost / safety

Uses the SAME YouTube circuit breaker + quota cache as the finder Tier-2 (~100 quota units per failed item, out of 10k/day — negligible at 30 items/run). Bypasses `find()` → does NOT write the finder's `__no_result__` cache sentinel → no cache poisoning.

## Non-goals / out of scope

- The SUCCESS branch hardcodes `source="youtube"` even for TMDB URLs (`orchestrator.py:534`) — pre-existing minor inaccuracy, NOT fixed here.
- No multi-N retry loop (one fallback attempt for v1; `_best_video` already discards N>1 TMDB videos so there is no cheap 2nd-TMDB candidate).
- No proxy/VPN for geo-blocks (a future option).

## Acceptance (executable — TDD, "un test par bug")

Tests under `tests/trailers/`, run in `make check`. Mutation-proof.

- **AC-1**: `test_ytdlp_failure_triggers_youtube_fallback_and_succeeds` — TMDB url → YTDLP_ERROR, search → ALT_URL → SUCCESS. Assert download called twice, `downloaded==1`, `ytdlp_error==0`, state `DOWNLOADED`, `source=="youtube"`, `youtube_url==ALT_URL`. (Reproduces the SMG/FROM miss; fails on current code.)
- **AC-2**: `test_ytdlp_failure_fallback_also_fails_keeps_terminal_state` — both fail → download×2, `ytdlp_error==1`, terminal state + `next_retry_at` unchanged.
- **AC-3**: `test_ytdlp_failure_fallback_returns_none_no_second_download` — search None → download×1, terminal.
- **AC-4**: `test_ytdlp_failure_fallback_returns_same_url_no_double_download` — search returns the failed URL → tried-set blocks 2nd download (download×1).
- **AC-5**: `test_fallback_disabled_by_config` — `fallback_youtube_search=False` → search NOT called, download×1, terminal.
- **AC-6**: `test_fallback_youtube_circuit_open_is_clean` — search raises `CircuitOpenError` → no crash, no 2nd download, terminal.
- **AC-7**: `test_http_error_also_triggers_fallback` — HTTP_ERROR also falls back (cover all non-SUCCESS). Decide+document BOT_DETECTED (recommend: fall back, but must not corrupt `bot_detected_consecutive_attempts`).
- **AC-8 (back-compat, MANDATORY)**: amend existing `test_run_ytdlp_error_increments_counter` (`test_orchestrator.py:708`) to also patch `_finder._youtube_search.search→None` (else it may make a live call / flake).
- **AC-9**: `TrailersConfig().fallback_youtube_search` defaults `True` + round-trips the JSON5 overlay loader; no exhaustive-field/golden snapshot test breaks.
- **AC-10**: `make check` green (ruff + mypy + check_logging + full suite, 0 failed/errors).

## SemVer

minor → Y+1: **0.34.1 → 0.35.0**, branch `feat/trailer-fallback` (new code path + new public config field; backward-compatible default-on).
