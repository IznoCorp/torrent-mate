# Design — YoutubeTrailerScraper Integration

**Date**: 2026-04-23
**Codename**: `trailer`
**Type**: minor (feat)
**Version bump**: 0.6.0 → 0.7.0 (applied at branch creation on 2026-04-24)
**Branch**: `feat/trailer`

## Context

`/opt/YoutubeTrailerScraper/` (YTS) is a standalone Python project by the same author that scans media directories, finds movies/TV shows without trailers, queries TMDB for official trailer URLs, falls back to direct YouTube search when TMDB has none, and downloads the result with `yt-dlp` using cookie authentication to bypass bot detection. It currently runs successfully on cron at night.

`personalscraper` handles the upstream half of the media lifecycle: ingest, sort, metadata scraping, NFO generation, artwork download, dispatch to 4 storage disks. It has its own mature TMDB integration inside `scraper/`, HTTP retry utilities (`http_retry.py`), circuit breaker (`circuit_breaker.py`), and a keywords cache. It lacks trailer handling entirely.

Rather than run YTS as a separate cron next to `personalscraper`, this feature **integrates trailer discovery/download into `personalscraper`** so trailers land alongside their media during the same pipeline pass (for staging items) and can be back-filled across the library (for existing media on disk). YTS's domain logic (Plex file-naming convention, FR→EN language fallback, two-tier TMDB→YouTube strategy, yt-dlp+cookie handling) is inherited unchanged. Only the integration surface — config, pipeline wiring, CLI, shared infrastructure — is designed here.

## Goals

1. Download missing trailers for media currently in the staging area, as a non-blocking pipeline step running after `verify` and before `dispatch`.
2. Provide a standalone CLI to back-fill trailers across the existing library on the 4 storage disks, using the same discovery/download logic.
3. Extend the existing `scraper/tmdb_client.TMDBClient` with video endpoints (`fetch_movie_videos` / `fetch_tv_videos`) so trailer discovery reuses the shared client — no new TMDB code path, no duplication.
4. Factor a generic `scraper/json_ttl_cache.JsonTTLCache` out of the current `scraper/keywords_cache.py` so TMDB video responses, YouTube searches, and future cached data all share a tested caching primitive.
5. Respect disks-as-source-of-truth: every "does this trailer already exist?" check hits the filesystem, never a cached scan.
6. Track failed/no-trailer-available lookups with a progressive retry-after policy so cron runs do not spam TMDB/YouTube for items that will never have a trailer.
7. Work on a headless server (cron at 03:00) without a live browser — cookies handled via static file or browser-profile extraction.

## Non-Goals

- Multi-language trailer support (only one trailer per media; language order falls back via the YTS-style list). A future feature can migrate to per-language trailers.
- Trailer transcoding or quality normalization (whatever yt-dlp delivers is kept).
- Re-implementing YTS's discovery algorithm — the two-tier TMDB→YouTube strategy is inherited as-is.
- Building an upstream library improvement / PR back to YTS. This is a downstream integration.
- UI / notifications beyond existing `notifier.py` Telegram hooks.

## Architecture

Layered, mirrors the existing `scraper/` (toolkit) + top-level pipeline step (`process/`, `dispatch/`, …) pattern.

```
personalscraper/
  scraper/                     # existing toolkit (metadata scraping + infra)
    tmdb_client.py             # EXISTING — extended with fetch_movie_videos / fetch_tv_videos
    artwork.py                 # EXISTING — unchanged (does not use TMDB HTTP; it downloads images)
    json_ttl_cache.py          # NEW — generic JSON+TTL cache extracted from keywords_cache
    keywords_cache.py          # EXISTING — migrated to use JsonTTLCache internally (same on-disk format)
    trailer_finder.py          # NEW — (tmdb_id, media_type) → YouTube URL
                               #   TMDB-first (via TMDBClient), YouTube-search fallback (YTS strategy)
    youtube_search.py          # NEW — direct YouTube search layer
    ytdlp_downloader.py        # NEW — yt-dlp wrapper with cookies handling
    trailers_cache.py          # NEW — TMDB video responses + YouTube search results (JsonTTLCache)
    http_retry.py              # existing (reused)
    circuit_breaker.py         # existing (reused)
    nfo_generator.py           # existing
    ...

  trailers/                    # NEW pipeline step + CLI (feature-level orchestration)
    __init__.py
    cli.py                     # `personalscraper trailers scan|download|verify|purge`
    step.py                    # pipeline step wiring (between process and dispatch)
    scanner.py                 # "media without trailer" detection — walks staging OR library
    placement.py               # Plex/Kodi naming convention (movie-trailer.mp4, trailers/trailer.mp4)
    state.py                   # persistent failure tracking (retry-after policy)
    orchestrator.py            # glue: scanner → trailer_finder → ytdlp_downloader → placement → state

  library/                     # existing — reused by `trailers scan` for cross-disk iteration
    ...

tests/
  scraper/test_tmdb_client_videos.py        # NEW — new fetch_movie_videos / fetch_tv_videos
  scraper/test_json_ttl_cache.py            # NEW — generic cache primitive
  scraper/test_keywords_cache.py            # EXISTING — must still pass after migration to JsonTTLCache
  scraper/test_trailer_finder.py            # NEW
  scraper/test_youtube_search.py            # NEW
  scraper/test_ytdlp_downloader.py          # NEW (yt-dlp fully mocked)
  scraper/test_trailers_cache.py            # NEW
  trailers/test_cli.py                      # NEW
  trailers/test_step.py                     # NEW
  trailers/test_scanner.py                  # NEW
  trailers/test_placement.py                # NEW
  trailers/test_state.py                    # NEW
  trailers/test_orchestrator.py             # NEW
  trailers/test_integration.py              # NEW — @pytest.mark.network E2E (Big Buck Bunny trailer)
```

### Why this split

- `scraper/` is the reusable metadata-scraping toolkit. `trailer_finder.py` joins it as a new TMDB consumer alongside existing callers of `TMDBClient`. It does NOT mirror `artwork.py` (artwork.py is an image downloader, not a metadata fetcher — that was a misread in an earlier draft).
- `trailers/` is a feature-level module (pipeline step + CLI + state) at the same architectural layer as `ingest/`, `sort/`, `process/`, `dispatch/`, `verify/`. Archivable / removable as a unit.
- Two small toolkit additions land before feature work: Phase 1 extends `TMDBClient` with video endpoints (purely additive); Phase 2 extracts `JsonTTLCache` from `keywords_cache.py` (behavior-preserving refactor, on-disk format unchanged).

## Key Design Decisions

### 1. Integration mode: targeted rewrite sharing project infrastructure

The YTS domain logic (two-tier discovery, flat file naming, FR→EN language fallback, yt-dlp download patterns, cookie-auth strategy) is **inherited as algorithmic inspiration, not verbatim**. The implementation shares personalscraper's infrastructure (`http_retry`, `circuit_breaker`, `keywords_cache`, logger, config, TMDB client) rather than importing YTS as a dependency or duplicating its code verbatim.

**Rationale**: YTS's value is its domain knowledge, not its infrastructure. personalscraper already has battle-tested HTTP/retry/breaker utilities — introducing pydevmate (CacheIt/LogIt) and a different logging/config ecosystem would double the maintenance surface. Sharing infra means a single source of truth for retry policy, a single TMDB client, and one coherent logging story.

**Two independent `CircuitBreaker` instances** (closes the "shared TMDB breaker tripped by YouTube errors" hole): the feature creates a dedicated `CircuitBreaker(name="youtube", …)` for YouTube operations (Data API v3 search AND yt-dlp downloads) and reuses / configures a `CircuitBreaker(name="tmdb_videos", …)` distinct from the scraper-wide `tmdb` breaker. This prevents YouTube saturation from tripping metadata scraping and vice-versa. Configuration lives in `config.trailers.circuit_breakers.{tmdb_videos,youtube}` (see §9).

**YouTube search primary path = YouTube Data API v3** (keyed via `YOUTUBE_API_KEY` in `.env`), with **yt-dlp `ytsearch1` as fallback** when the key is absent or quota is exhausted (HTTP 403). See §9 for quota accounting and fallback triggers. This closes the "calling googleapis search endpoint without `key=` returns 403 every time" hole from plan review.

### 2. Pipeline position: new step `trailers` between `verify` and `dispatch`, non-blocking

The actual pipeline today is 8 steps (from `pipeline.py`):
`ingest → sort → clean → scrape → cleanup → enforce → verify → dispatch`.

After this feature lands it becomes 9 steps:
`ingest → sort → clean → scrape → cleanup → enforce → verify → trailers → dispatch`.

- `scrape` has already generated NFOs, so `trailer_finder` reads `tmdbid`/`tvdbid` straight from them — no duplicate TMDB search.
- `verify` has validated media structure before we spend bandwidth on trailers — items that would fail dispatch anyway never trigger downloads.
- A YouTube outage or yt-dlp failure logs a warning and continues; dispatch proceeds without the trailer. The media is never blocked from reaching its final disk.
- Media still sits in staging during this step, so a successfully downloaded trailer is placed next to the media and is dispatched together in one move.
- Controlled by `config.json5 › trailers.enabled` and CLI flag `--skip-trailers`.

**Rationale**: trailers are a nice-to-have. Coupling them into `scrape` would slow metadata writing and introduce bot-detection failure modes that abort NFO generation. Decoupling into its own step gives a clean skip-lane and a natural retry point. Position after `verify` ensures we only attempt trailers for items that are structurally correct.

**Implementation note for Phase 5**: `pipeline.py` wires `_run_step("verify", …)` then conditionally `_run_step("dispatch", …)` only if `verified` items exist. The `trailers` step must be inserted between these two calls — before the `if verified:` branch, with its own short-circuit when `verified` is empty (skipped with `status=skipped`, same pattern as dispatch's empty-verified skip).

### 3. Standalone CLI: `personalscraper trailers <subcommand>` with full filter set

```
personalscraper trailers scan      [filters]            # dry-run: list missing trailers
personalscraper trailers download  [filters]            # scan + download
personalscraper trailers verify    [filters] [--deep]   # audit existing trailers (see expanded bullet below)
personalscraper trailers purge     [filters] [--dry-run]  # remove orphan trailers (media parent absent)
```

`personalscraper trailers verify [filters] [--deep]` — audit existing trailers:

- **Existence**: trailer file present at the expected placement path
- **Size**: file size ≥ `config.trailers.filters.min_file_size_bytes` (default 100 KiB)
- **Extension**: file suffix in `{mp4, mkv, webm}` (configurable via `config.trailers.filters.allowed_extensions`)
- **Playable** (opt-in, `--deep` flag): ffprobe returns non-zero duration for the file (expensive — disabled by default)

Report each failing check with its category (`missing`, `undersized`, `wrong_extension`, `unplayable`). Exit code: 0 if all pass, 2 if any fail (4 for `--deep` probe errors).

Filters (shared across subcommands):

- `--disk DISK_N` — restrict to one of the 4 storage disks
- `--category movies|tv_shows|movies_animation|tv_shows_animation|...` — category ID from config
- `--since YYYY-MM-DD` — media added/modified after a date
- `--limit N` — cap items processed per run
- `--dry-run` — implied for `scan`, opt-in for `download`/`purge`

Idempotent: re-running `download` on a clean library is a no-op. Skip rule: trailer file exists AND size ≥ `config.trailers.filters.min_file_size_bytes` (default 100 KiB).

### 4. Trailer placement, language, search strategy

- **Movie**: `{movie_folder}/{movie_name}-trailer.{ext}`
- **TV show**: `{tvshow_folder}/{show_name}-trailer.{ext}` (flat, same convention as movies)
- **Extension** `{ext}`: whatever yt-dlp delivers (mp4 in practice with the `best[ext=mp4]/best` format hint, may be `mkv`/`webm` in edge cases). The filename suffix is dynamic, not hardcoded.
- **Language fallback**: ordered list, default `["fr-FR", "en-US"]`.
- **Discovery**: TMDB primary (per language), YouTube direct search fallback with query format `{title} {year} bande annonce`.
- **NFO**: in addition to the file on disk, the NFO `<trailer>` tag (currently emitted empty by `nfo_generator.py` lines 181, 290 — line numbers current as of commit 6bd2b66) is populated with the YouTube URL — Plex uses this as a remote-trailer fallback when Local Media Assets doesn't pick up the file, Kodi ignores it but it costs nothing to write.

**Why flat `{name}-trailer.{ext}` for both movies and TV** (deviates from YTS's `{tvshow}/trailers/trailer.mp4`):

- **Plex priority** (user preference): the "Local Media Assets" agent recognizes `{name}-trailer.ext` next to the media for both movies and TV shows. The `Trailers/` subfolder is Plex-only for the "Local Trailers" agent and has no TV-show support.
- **Kodi compatibility**: `{name}-trailer.ext` is the documented Kodi convention for both types.
- **Jellyfin/Emby**: same flat convention works out of the box.
- Result: one convention, maximum compatibility, no special-case code.

These placements are canonical and not re-opened downstream. `docs/reference/naming.md` is updated in Phase 9 to document them alongside the existing movie/TV naming rules.

### 5. Cookie authentication on a headless server

Hybrid configuration — either or both can be set in `.env`:

```
YOUTUBE_COOKIES_FILE=/absolute/path/to/cookies.txt         # option A — static export
YOUTUBE_COOKIES_FROM_BROWSER=firefox                       # option B — live extraction
```

Priority: `YOUTUBE_COOKIES_FILE` > `YOUTUBE_COOKIES_FROM_BROWSER` > no cookies.

Failure policy when cookies absent/expired and yt-dlp reports bot-detection: **retry once without cookies** (public videos sometimes pass) → if still fails, log warning, mark the item in the state file with `status=bot_detected`, continue to next. Never abort the pipeline step.

**Bounded retry for `bot_detected`** (closes the "always retry → infinite YouTube spam on age-restricted content" hole): while `bot_detected` is normally exempt from the retry-after progression (user-fixable), we cap the consecutive `bot_detected` attempts per key. After `config.trailers.bot_detected_max_consecutive_attempts` (default `5`) without a successful download, the entry transitions into the standard retry-after progression and `bot_detected_consecutive_attempts` is reset the next time a non-`bot_detected` outcome is observed. This prevents the "age-restricted → retry forever → rate-limit ban" failure mode while still letting the user fix cookies and have work resume immediately after the next success.

**Counter semantics (explicit)**:

- A dedicated field `bot_detected_consecutive_attempts: int` (default 0) is persisted on each state entry.
- **Increment**: every time an attempt produces `status=bot_detected`.
- **Reset**: on **any** non-`bot_detected` outcome (success, http_error, ytdlp_error, no_trailer_available). Reset happens BEFORE the new status is written.
- **Scope**: per state entry. Two different movies each tracked independently; no global counter.
- **Threshold behavior**: once the counter reaches `bot_detected_max_consecutive_attempts`, the entry transitions to the standard retry-after progression (`status=http_error` for conservative exponential backoff) AND `bot_detected_consecutive_attempts` is NOT reset. A subsequent successful run resets both `attempts` (to 1) and `bot_detected_consecutive_attempts` (to 0).

### 6. Toolkit additions: extend `TMDBClient`, extract `JsonTTLCache`

`scraper/tmdb_client.py` already exists with `TMDBClient` (uses `http_retry`, `circuit_breaker`, implements `MetadataProvider`). No extraction work is needed. The feature adds two methods:

- `TMDBClient.fetch_movie_videos(tmdb_id: int, language: str) -> list[Video]`
- `TMDBClient.fetch_tv_videos(tmdb_id: int, language: str) -> list[Video]`

Both return typed results (lightweight dataclass wrapping the TMDB `/videos` response: `id`, `site`, `key`, `type`, `official`, `size`, `iso_639_1`). Unit-tested with golden fixtures. **Phase 1** is this additive API change plus its tests — small, merge-on-its-own safe.

`scraper/keywords_cache.py` is not a reusable pattern as-is (hard-coded filename, keys, payload shape). **Phase 2** extracts a generic `scraper/json_ttl_cache.JsonTTLCache` with a clean interface (`get(key) -> T | None`, `set(key, value, ttl_seconds)`, `invalidate(key)`, `compact()`). The new `trailers_cache.py` in Phase 3 uses `JsonTTLCache` directly for TMDB video responses and YouTube search results.

**Shared TTL helper between `KeywordsCache` and `JsonTTLCache`** (closes the "refactor promise not honoured" hole reported by plan review):

The on-disk format of `tmdb_keywords_cache.json` must stay unchanged (it is read/written in production), so `KeywordsCache` cannot wholesale delegate to `JsonTTLCache`. Instead, a pure-function helper is factored and shared:

```python
# scraper/json_ttl_cache.py
def check_ttl(cached_at: datetime, ttl_seconds: int, *, now: datetime | None = None) -> bool:
    """Return True if the cached_at timestamp is still within ttl_seconds."""
    current = now or datetime.now(UTC)
    return (current - cached_at).total_seconds() < ttl_seconds
```

Both `KeywordsCache._is_expired()` and `JsonTTLCache._is_expired()` call `check_ttl()`. The shared helper lives in `json_ttl_cache.py` and is imported by `keywords_cache.py`. This honours the DESIGN promise ("Both toolkit changes are behavior-preserving" / "single source of truth for TTL logic") without breaking the on-disk schema. `test_keywords_cache.py` must still pass after the migration; `test_json_ttl_cache.py` adds targeted tests for `check_ttl()` covering boundary (`ttl_seconds == 0`), past/future, and timezone-naïve input rejection.

Both toolkit changes are behavior-preserving for existing code paths — they enable feature work without introducing incidental complexity in the feature phases.

### 7. State tracking (`trailers/state.py`)

Persistent JSON at `.data/trailers_state.json` (gitignored, under the `.data/` directory already in use).

**Key scheme (composite, precedence-ordered)**:

```
movie:tmdb:{id}                    # primary: media has a valid TMDB id
movie:tvdb:{id}                    # TMDB miss, TVDB fallback (movies rarely — but possible via imdb→tvdb chain)
tv:tmdb:{id}                       # primary for TV
tv:tvdb:{id}                       # TV with TVDB-only metadata
manual:{sha256(title|year|type)}   # no external ID — stable hash of normalized (title, year, media_type)
```

The orchestrator picks the key based on the NFO it reads for the media; it never invents an ID. When multiple IDs exist, `tmdb` is preferred (matches the discovery path).

**Why `sha256(title|year|type)` rather than `sha1(absolute_path)`** (closes the "rename/move breaks state key" hole): absolute paths change frequently for NTFS media (merge/replace rules from `dispatch` move media between disks; re-scrape may rename folders to canonical titles). Hashing `(title, year, media_type)` after NFC-normalization + casefolding yields a stable key as long as the scraper converges on the same title/year — which is exactly what scrape is already tasked with. The path is still stored as `media_path` on the entry for auto-GC lifecycle check #2 (detect missing media), but it is not part of the identity.

**Entry shape**:

```json
{
  "version": 1,
  "entries": {
    "movie:tmdb:550": {
      "last_attempt": "2026-04-23T03:12:04Z",
      "attempts": 3,
      "status": "no_trailer_available",
      "next_retry_at": "2026-05-23T00:00:00Z",
      "media_path": "/Volumes/DISK_A/001-MOVIES/Fight Club (1999)",
      "notes": "TMDB returned 0 videos, YouTube search top 5 irrelevant"
    },
    "tv:tmdb:1399": {
      "last_attempt": "2026-04-23T03:14:11Z",
      "attempts": 1,
      "status": "downloaded",
      "media_path": "/Volumes/DISK_B/002-TVSHOWS/Game of Thrones",
      "trailer_path": "/Volumes/DISK_B/002-TVSHOWS/Game of Thrones/Game of Thrones-trailer.mp4",
      "source": "tmdb",
      "youtube_url": "https://www.youtube.com/watch?v=..."
    },
    "movie:tmdb:99999": {
      "last_attempt": "2026-04-23T03:18:02Z",
      "attempts": 2,
      "status": "bot_detected",
      "media_path": "/Volumes/DISK_C/001-MOVIES/Obscure (2017)"
    }
  }
}
```

**Status enum** (complete): `downloaded | no_trailer_available | bot_detected | http_error | ytdlp_error | skipped_by_filter | orphan`.

**Retry-after policy (explicit)**:

- `config.trailers.retry_after_days: [1, 7, 30]` — progression array.
- Attempt `N` → retry after `retry_after_days[min(N-1, len-1)]` days. The last element repeats indefinitely for any further attempt. Documented invariant.
- **Clock reference**: `next_retry_at` is computed as `last_attempt + timedelta(days=retry_after_days[min(N-1, len-1)])` — **always measured from the last attempt, never from the first failure**. This means a stuck entry keeps pushing its retry forward; a recovered entry resets `attempts=1` on its next successful result.
- `bot_detected`: **exempt from the progression** — always retry on the next run (cookies issue is user-fixable).
- Timestamps are UTC ISO 8601. Schedule robustness relies on `datetime.now(UTC)`; a backwards clock reset will compress the effective schedule (accepted — system time is the user's responsibility).

**Lookup logic** (before any network call): if an entry exists AND `status ∈ {no_trailer_available, http_error, ytdlp_error}` AND `next_retry_at > now` → skip, don't contact TMDB/YouTube.

**Lifecycle / auto-GC** (runs at the start of every `trailers` step and every `trailers *` subcommand):

1. For each `downloaded` entry, check that `trailer_path` exists on disk. If missing, remove the entry (trailer was manually deleted or media moved — let it be re-downloaded).
2. For each entry with a `media_path`, check that path still exists. If not, flip `status` to `orphan`.
3. `trailers purge --include-state` wipes `orphan` entries (after optional `--dry-run`).

No separate remap-detection for TMDB ID changes: if a re-scrape changes `tmdbid` in the NFO, the new key has no state entry → discovery runs → the Plex-convention trailer path already exists on disk → idempotent skip via the size-based "already present" rule. The old key lingers until lifecycle check #2 flips it to `orphan` (happens when the original `media_path` no longer exists, i.e. when the media itself moved).

### 8. Source of Truth: disks

`personalscraper/library/scanner.py` exposes `scan_library()`, `scan_movie_dir()`, `scan_tvshow_dir()` and caches results. The cache can be stale. Design rules:

1. **Presence check goes to the filesystem.** Before `download`, re-verify the trailer file is still absent at the expected path. Before `purge`, re-verify the media is actually missing from disk.
2. **Desync detection.** If a state entry references a `media_path` that no longer exists, flip `status=orphan` and move on. `trailers purge --include-state` uses these markers to clean up.
3. **No write without filesystem-verified intent.** Do not delete trailers based on library cache stating "media missing" — re-check the disk first.

**Fresh-scan policy for back-fill CLI** (addresses the "media on disk but absent from cache" hole):

- `trailers download` and `trailers scan` default to refreshing the library if the last scan is older than 24 hours (threshold configurable via `config.trailers.library_scan_max_age_hours`, default 24).
- `--no-refresh` flag overrides: always use the cache, even if stale. Intended for ad-hoc debugging or repeated runs within a short window.
- The pipeline `trailers` step (not the CLI) does NOT refresh — it scans only staging items, where library cache is irrelevant.

This keeps the SOT guarantee practical: the cache is only as stale as the user's configured threshold allows, and fresh-scan is opt-out rather than opt-in for destructive paths.

### 9. Configuration split

**`.env`** (secrets, machine-local, already supported by personalscraper's settings layer):

```
TMDB_API_KEY=...
TMDB_READ_ACCESS_TOKEN=...
YOUTUBE_API_KEY=...                                       # YouTube Data API v3 key (primary search path)
YOUTUBE_COOKIES_FILE=/absolute/path/cookies.txt           # optional
YOUTUBE_COOKIES_FROM_BROWSER=firefox                      # optional, one of: firefox, chrome, chromium, edge, opera, brave, safari
```

**YouTube search strategy — two tiers**:

1. **Primary: YouTube Data API v3 `/search`** with `key={YOUTUBE_API_KEY}`. Quota-tracked (10 000 units/day default, 100 search calls/day since each `search.list` costs 100 units). All responses cached via `JsonTTLCache` with a long TTL (7 days) to stretch the quota across runs.
2. **Fallback: yt-dlp `ytsearch1`** (`yt_dlp.YoutubeDL({'default_search': 'ytsearch1', 'noplaylist': True}).extract_info(query, download=False)`). Used automatically when (a) `YOUTUBE_API_KEY` is unset in `.env`, or (b) the primary call returns HTTP 403 (quota exceeded) or a retriable 5xx after the HTTP retry budget is exhausted.

The YouTube breaker (see below) tracks only primary-path errors; fallback failures trip yt-dlp's own `circuit_breaker` state (shared with download errors) since they exercise yt-dlp. The fallback logs at INFO ("primary YouTube search unavailable, falling back to yt-dlp ytsearch") so the operator knows quota is burning or the key is missing.

**`config.json5`** (patterns, policy, portable):

```json5
{
  trailers: {
    enabled: true,

    languages: ["fr-FR", "en-US"],
    fallback_youtube_search: true,
    search_query_format: "{title} {year} bande annonce",

    placement: {
      // Flat convention for both movies and TV shows — Plex Local Media Assets + Kodi + Jellyfin all recognize it.
      movie_pattern: "{folder}/{name}-trailer.{ext}",
      tvshow_pattern: "{folder}/{name}-trailer.{ext}",
    },

    filters: {
      min_duration_sec: 30,
      max_duration_sec: 600,
      min_file_size_bytes: 102400,
      max_resolution: 1080, // cap to avoid 4K/2 GB downloads
      max_filesize_mb: 500, // hard cap for yt-dlp
      prefer_official_channels: true,
      // TMDB video filtering (applied to /videos responses before YouTube URL construction).
      tmdb_video_filters: {
        require_youtube_site: true, // drop Vimeo/DailyMotion entries (URL construction assumes YouTube)
        prefer_official: true, // prefer v.official == true
        allowed_types: ["Trailer", "Teaser"],
      },
    },

    state_file: ".data/trailers_state.json",
    retry_after_days: [1, 7, 30],
    bot_detected_max_consecutive_attempts: 5, // bounded retry before entering progression (see §5)

    // Two independent circuit breakers, one per external service.
    // A YouTube outage must NOT trip the TMDB breaker used by the rest of the scraper.
    circuit_breakers: {
      tmdb_videos: {
        // Name matches the scraper-wide `tmdb` breaker conceptually but uses a distinct instance
        // keyed on "tmdb_videos" so /videos 5xx storms don't poison /movie /tv calls.
        errors_threshold: 5,
        cooldown_sec: 1800,
      },
      youtube: {
        errors_threshold: 5,
        cooldown_sec: 3600,
      },
    },

    // YouTube Data API v3 quota tracking (primary search). Fallback kicks in when exhausted or on 403.
    youtube_api: {
      daily_quota_units: 10000, // default YouTube Data API v3 daily quota
      search_list_cost_units: 100, // each search.list costs 100 quota units
      cache_ttl_days: 7, // long TTL to stretch quota across runs
    },

    ytdlp: {
      // 1080p max, mp4 preferred, caps filesize. Extension suffix of the final file is dynamic.
      format: "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
      socket_timeout_sec: 30,
      retries: 3,
      default_search: "ytsearch1", // used by the yt-dlp fallback search path
    },

    library_scan_max_age_hours: 24, // refresh threshold for `trailers scan/download` (see §8)
  },
}
```

`personalscraper/commands/init_config.py` (or equivalent) does NOT currently emit feature-specific config blocks — it generates the base structural sections (disks, categories, paths, genres). Rather than extending it, the `trailers` section uses Pydantic `Field(default_factory=...)` in the `conf/` settings model so that **omitting `trailers` from `config.json5` yields sensible defaults with `enabled: false`**. The feature auto-enables if `TMDB_API_KEY` is detected in `.env` AND the user explicitly flips `trailers.enabled: true` in `config.json5`. No migration step required.

### 10. Testing strategy

- `yt-dlp`: fully mocked. `tests/scraper/test_ytdlp_downloader.py` patches `yt_dlp.YoutubeDL` and asserts the options dict (format, cookies path, retries, output template).
- `TMDB`: golden fixtures stored under `tests/fixtures/tmdb/`, loaded by a mock HTTP transport. No network calls in the unit test suite.
- `YouTube search`: HTTP layer mocked; response fixtures in `tests/fixtures/youtube/`.
- `Scanner` / `placement` / `state`: tmpdir-based fixtures producing fake media trees (movie folders with/without trailers, TV show folders with `trailers/` subdir).
- **One end-to-end integration test** behind `@pytest.mark.network`, opt-in (skipped in CI by default), downloading a stable public trailer (e.g. Big Buck Bunny via a known TMDB entry) to a tmpdir. Guarded by an env var to keep CI fast and deterministic.
- Coverage target: match project baseline; no regression in overall coverage after this feature lands.

### 11. Observability

- `logger.py` is the project logger — every major step (scan, discover, download, place, state update) logs at INFO with the `tmdb_id`/`tvdbid` and media title.
- Failures log at WARNING with a reason code matching the state status.
- `notifier.py` (Telegram) receives a pipeline summary: "N trailers downloaded, M skipped, K failed" at the end of the `trailers` step.

### 12. Operational Safeguards

Production hardening. Every item here closes a specific risk surfaced during plan review.

#### Timeouts

- **Per-item yt-dlp wall-clock**: `config.trailers.ytdlp.max_wall_clock_sec` (default **180 s**). Implemented via `signal.SIGALRM` in `YtdlpDownloader.download()` (Unix-only; on non-Unix platforms the timeout is best-effort via `socket_timeout`). Exceeding this timeout produces `status=ytdlp_error` with `notes="wall-clock timeout"`.
- **Per-step global budget**: `config.trailers.step.max_duration_sec` (default **1800 s** = 30 minutes). When exceeded, the orchestrator stops pulling new items, logs `trailers_step_budget_exceeded`, and returns a partial StepReport. Already-downloaded trailers are kept.

#### Disk space

- Before each download: `shutil.disk_usage(staging_dir)` must report ≥ `config.trailers.filters.max_filesize_mb * 1024 * 1024 * 1.5` (50% safety margin) free. If not, skip the item with `status=skipped_by_filter`, `notes="disk_space_low"`. Log event `trailers_disk_space_low` with bytes free. Implemented in the orchestrator, not the downloader (so the check happens once per item before yt-dlp spins up).

#### Concurrency

- `.data/trailers_state.json` writes use `fcntl.flock(LOCK_EX)` on the state file's directory-level lockfile `.data/trailers_state.lock`. Read-then-write cycles are atomic under the lock.
- `.data/youtube_quota_cache.json` (used for YouTube Data API v3 quota accounting) uses the same lock strategy on `.data/youtube_quota.lock`.
- Pipeline-level coordination: the existing `pipeline.lock` (see `personalscraper/lock.py`) covers the `trailers` pipeline step automatically. Standalone CLI invocations (`personalscraper trailers download`) acquire the state lock only — they do NOT take `pipeline.lock` (intentional: a user-driven back-fill should not block a scheduled pipeline run or vice-versa). Document this asymmetry in `docs/reference/pipeline-internals.md`.

#### Log redaction

- **YOUTUBE_API_KEY must never appear in logs**. Enforcement:
  - HTTP requests to the YouTube Data API v3 strip the `key=` query parameter before logging any URL (`youtube_search.py`).
  - A structlog processor `redact_secrets` is added to `personalscraper/logger.py` that recursively redacts any dict key matching `/^(api[_-]?key|authorization|cookie|key)$/i` anywhere in the event dict, replacing values with `"***REDACTED***"`.
  - Cookie file contents are never logged (only the file path is logged, at INFO level).
- **Verification**: `tests/trailers/test_security.py` with tests asserting that `logger.warning("fake_event", url="https://example.com?key=secret123")` does not emit `secret123` in the captured output. Same for `api_key=`, `authorization=`, etc.

#### yt-dlp version pin

- `pyproject.toml` pins `yt-dlp>=2026.1.1,<2027` (major+minor floor, major ceiling). Rationale: yt-dlp is broken by YouTube changes every 2–6 weeks; an unpinned install silently ships a broken extractor. The major-version ceiling prevents accidental breakage on `pip install --upgrade`.
- A `make update-ytdlp` target bumps the pin and runs the integration test, giving maintainers a one-shot refresh path.

#### ffmpeg dependency

- `YtdlpDownloader.__init__` runs `shutil.which("ffmpeg")` once. If absent, logs `ytdlp_ffmpeg_missing` at WARN level; downloads still proceed for single-stream formats but multi-stream merges fail with `status=ytdlp_error`, `notes="ffmpeg_required"`.
- Installation guidance in `docs/reference/libraries.md`: `brew install ffmpeg` (macOS), `apt-get install ffmpeg` (Debian/Ubuntu).

#### Circuit breaker tuning for YouTube

- The default `cooldown_sec=3600` (1 h) for the YouTube breaker is aggressive — a 1-minute YouTube blip during cron would skip an entire night's trailer batch. For v0.7.0 keep this conservative default (cron runs once per night; a 1-h cooldown costs at most one night). Future tuning proposal: migrate to a sliding-window breaker that counts failures in the last N seconds rather than consecutive failures. Tracked as ROADMAP follow-up.

### 13. Security

- `.env` is already gitignored; no new credential surface is committed.
- Cookie files (`YOUTUBE_COOKIES_FILE`) should have mode `600`. The loader emits a WARNING if stricter mode is not set on POSIX filesystems. On macFUSE/NTFS-mounted volumes the permission bits are not reliable — the loader detects the mount type and skips the check silently (documented as intentional).
- `.env` and `YOUTUBE_COOKIES_FILE` are expected on **APFS-native storage only** (e.g. `~/`, `/opt/`, `/path/to/staging/`). Cookie files on NTFS/macFUSE disks are rejected at load time with a clear error — the filesystem can leak the file on sharing and the permission model doesn't protect it.
- `yt-dlp` is invoked via its Python API (`yt_dlp.YoutubeDL(opts).download([url])`), never shell-interpolated user input — no command-injection surface.
- TMDB keys reuse the existing personalscraper key; do not duplicate in `/opt/YoutubeTrailerScraper/.env`.

### 14. Pipeline step contract (non-blocking semantics)

The `trailers` step follows the existing pipeline `StepReport` pattern (same as `process/`, `dispatch/`, `verify/`). It returns a report with:

- `status`: one of `success` (all items had a trailer or got one), `partial` (some items failed/skipped, pipeline continues), `skipped` (`config.trailers.enabled=false` or `--skip-trailers`), `error` (step itself crashed — unusual, e.g. bug in scanner).
- `counts`: `{"downloaded": N, "already_present": M, "no_trailer": K, "bot_detected": L, "error": X, "skipped_by_state": Y}`.
- `failed_items`: list of `(key, status, reason)` for each item that did not land a trailer, used by `notifier.py` for the Telegram summary.

**Non-blocking semantics**:

- `status=partial` **does NOT block `dispatch`**. The pipeline reads `status ∈ {success, partial, skipped}` as "proceed".
- Only `status=error` pauses the pipeline — and even then, a CLI flag `--continue-on-trailer-error` can override (default: off, so the user notices a real bug).
- `verify` (the step after `dispatch`) asserts nothing about trailer presence — trailers are bonus content, not part of media correctness.

## Phase Breakdown

Intended plan structure (owned by `/implement:plan` later, but listed here for reviewer sanity):

| #   | Phase                                                                        | Goal                                                                                                                                                                                                                                                                                             |
| --- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Extend `TMDBClient` with video endpoints**                                 | Additive API: `fetch_movie_videos()`, `fetch_tv_videos()` + `Video` dataclass. Golden fixtures, unit tests. Existing tests unchanged. Merge-on-its-own safe.                                                                                                                                     |
| 2   | **Extract `JsonTTLCache` primitive + shared `check_ttl()` helper**           | Factor generic `scraper/json_ttl_cache.py` (new class + pure `check_ttl()` helper). Refactor `keywords_cache.py` to call the shared `check_ttl()` (on-disk format unchanged — single source of truth for TTL logic). `test_keywords_cache.py` must still pass. Add `test_json_ttl_cache.py`.     |
| 3a  | **Trailer discovery (`trailer_finder`, `youtube_search`, `trailers_cache`)** | TMDB-first via extended `TMDBClient` (with required `v.site=='YouTube'` filter); YouTube Data API v3 primary + yt-dlp `ytsearch1` fallback; quota tracking; caching via `JsonTTLCache`. Unit-tested with mocks and golden fixtures. No download yet.                                             |
| 3b  | **Download wrapper (`ytdlp_downloader`)**                                    | yt-dlp Python API wrapper + cookies handling (file or browser) + retry-without-cookies fallback (bounded by `bot_detected_max_consecutive_attempts`) + resolution/filesize caps. Fully mocked tests asserting opts dict + one `@pytest.mark.network` E2E against a CC-licensed clip.             |
| 3c  | **Placement (`placement.py`)**                                               | Flat `{folder}/{name}-trailer.{ext}` convention for both movies and TV. Populates NFO `<trailer>` tag with YouTube URL. FS permission checks, cross-disk considerations. Tmpdir tests.                                                                                                           |
| 4   | **State tracking (`state.py`)**                                              | JSON state file with composite keys (`{media_type}:{id_kind}:{id}` / `manual:{sha256(title                                                                                                                                                                                                       | year | type)}`), retry-after policy with explicit progression invariant, bounded `bot_detected`retries, status enum (incl.`orphan`), auto-GC lifecycle, lookup helper. All timestamps UTC. |
| 5   | **Pipeline step (`trailers/step.py`)**                                       | Wire `trailers` step between `verify` and `dispatch` (before the existing `if verified:` branch). `config.trailers.enabled` gate + `--skip-trailers` flag. `StepReport` extended with `status`/`counts`/`failed_items` after an audit of existing `StepReport(…)` call-sites. Non-blocking.      |
| 6   | **Scanner + orchestrator**                                                   | Staging vs. library iteration paths; SOT disk verification at every decision point; integration with `library.scanner.scan_library()` (+ `scan_movie_dir`, `scan_tvshow_dir`); fresh-scan threshold (24h default) + `--no-refresh`.                                                              |
| 7   | **Config schema via Pydantic defaults**                                      | `TrailersConfig` with `Field(default_factory=...)` in `conf/`. Sensible defaults produce `enabled: false`. `.env.example` updated (`YOUTUBE_API_KEY`). No `init-config` migration (omission-friendly). Schema is finalized BEFORE the CLI so CLI can consume it without mocks in runtime.        |
| 8   | **CLI (`personalscraper trailers …`)**                                       | Subcommands `scan`, `download`, `verify`, `purge`; full filter set (`--disk DISK_N` matching existing `Disk1-4` style, `--category`, `--since`, `--limit`, `--dry-run`, `--no-refresh`, `--include-state` for purge). Consumes `TrailersConfig` from Phase 7. Uses `rich.Progress` + structlog.  |
| 9   | **E2E + docs + gate**                                                        | End-to-end run on staged items (one hermetic test with fixture `.mp4` + mock HTTP; one opt-in `@pytest.mark.network` E2E); coverage audit; `docs/reference/trailers.md` (new) + updates to `architecture.md` / `commands.md` / `testing.md` / `naming.md` + CLAUDE.md trigger table; final gate. |

Phases 1 and 2 are behavior-preserving — each mergeable on its own if the feature ever aborts. Phase 3 splits into 3a/3b/3c to match the sub-phase discipline (scoped commits per concern).

**Phase 7 / 8 ordering note** (reviewer-flagged fix): the original draft placed CLI before Config, but the CLI consumes `cfg.trailers.*` defined by the Pydantic model — running the CLI without the config model in place only works when the consumer is mocked. Moving Config to Phase 7 and CLI to Phase 8 makes each phase independently runnable and keeps tests hermetic.

## Out of Scope

- Multi-language trailers (one trailer per media).
- Downloading anything other than trailers (behind-the-scenes, featurettes, clips).
- Automatic cookie refresh (manual re-export if `cookies.txt` expires).
- Transcoding to a uniform codec/bitrate.
- TMDB ID remap detection (accepted as orphan; no migration code).
- Extending `init-config` to generate feature-specific blocks (Pydantic defaults handle it).
- Integration with the future Library Indexer feature (ROADMAP item) — `trailers` uses `library.scanner` directly; a later optimization may switch to the indexer once available.

## Open Questions

- Pipeline E2E fixture existence — Phase 9 must first check whether `tests/` already has a full `ingest → ... → dispatch` fixture. If none, a fixture-creation sub-phase is added inside Phase 9. Not a design blocker.

## References

- Upstream: `/opt/YoutubeTrailerScraper/` (README, DEVELOPMENT_PLAN.md, `src/youtubetrailerscraper/`).
- Existing personalscraper scraping toolkit: `personalscraper/scraper/`.
- Pipeline orchestration: `personalscraper/pipeline.py`.
- Config layer: `personalscraper/conf/`.
- yt-dlp documentation: https://github.com/yt-dlp/yt-dlp#readme
- TMDB API v3: https://developer.themoviedb.org/reference/intro/getting-started
