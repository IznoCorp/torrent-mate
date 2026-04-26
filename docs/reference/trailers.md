# Trailers Reference

Trailer discovery, download, placement, state, and CLI commands.

## Overview

The trailers feature discovers and downloads trailers for media in the staging area.
It runs as step 8 of 9 in the pipeline (between verify and dispatch).

Disabled by default (trailers.enabled = false). Enable and set YOUTUBE_API_KEY for
two-tier search: TMDB /videos -> YouTube API v3 -> yt-dlp fallback.

## Configuration

All keys under the trailers block in config.json5.

### Top-level keys

| Key                                   | Type | Default                        | Description                    |
| ------------------------------------- | ---- | ------------------------------ | ------------------------------ |
| enabled                               | bool | false                          | Master switch                  |
| languages                             | list | ["fr-FR","en-US"]              | TMDB video language codes      |
| search_query_format                   | str  | "{title} {year} bande annonce" | YouTube fallback query         |
| state_file                            | str  | ".data/trailers_state.json"    | State JSON path                |
| retry_after_days                      | list | [1,7,30]                       | Days before retry              |
| bot_detected_max_consecutive_attempts | int  | 5                              | Max consecutive BOT_DETECTED   |
| library_scan_max_age_hours            | int  | 24                             | Max age of cached library scan |

### trailers.filters

| Key                 | Type | Default              | Description                           |
| ------------------- | ---- | -------------------- | ------------------------------------- |
| min_file_size_bytes | int  | 102400               | Min bytes for valid trailer (100 KiB) |
| max_filesize_mb     | int  | 500                  | Hard cap passed to yt-dlp             |
| allowed_extensions  | list | ["mp4","mkv","webm"] | Extensions for trailers verify        |

### trailers.ytdlp

| Key                | Type | Default                                | Description            |
| ------------------ | ---- | -------------------------------------- | ---------------------- |
| format             | str  | bestvideo[height<=1080]+bestaudio/best | yt-dlp format selector |
| socket_timeout_sec | int  | 30                                     | Socket timeout         |
| retries            | int  | 3                                      | Retry count            |
| default_search     | str  | ytsearch1                              | Search prefix fallback |

### trailers.step

| Key              | Type | Default | Description                          |
| ---------------- | ---- | ------- | ------------------------------------ |
| max_duration_sec | int  | 1800    | Step time budget in seconds (30 min) |

### trailers.circuit_breakers

Two independent circuit breakers.

| Service | errors_threshold | cooldown_sec  |
| ------- | ---------------- | ------------- |
| tmdb    | 5                | 1800 (30 min) |
| youtube | 5                | 3600 (60 min) |

### trailers.youtube_api

| Key                    | Type | Default | Description                |
| ---------------------- | ---- | ------- | -------------------------- |
| daily_quota_units      | int  | 10000   | Google daily quota         |
| search_list_cost_units | int  | 100     | Quota per search.list call |
| cache_ttl_days         | int  | 7       | YouTube search result TTL  |

### trailers.seasons

Opt-in per-season discovery. Disabled by default.

| Key                 | Type | Default                                        | Description                                |
| ------------------- | ---- | ---------------------------------------------- | ------------------------------------------ |
| enabled             | bool | false                                          | Enable per-season download                 |
| language_fallback   | list | null                                           | Override languages for season TMDB lookups |
| search_query_format | str  | "{title} {year} saison {season} bande annonce" | Season YouTube query                       |

### trailers.library_check

Per-type library-aware idempotence toggles.

| Key      | Type | Default | Description                            |
| -------- | ---- | ------- | -------------------------------------- |
| movies   | bool | false   | Library scan for movies (default OFF)  |
| tv_shows | bool | true    | Library scan for TV shows (default ON) |

### trailers.pipeline

| Key               | Type | Default | Description                   |
| ----------------- | ---- | ------- | ----------------------------- |
| skip              | bool | false   | Equivalent to --skip-trailers |
| continue_on_error | bool | false   | Continue to dispatch on error |

## Environment Variables

| Variable                     | Required | Description                                                     |
| ---------------------------- | -------- | --------------------------------------------------------------- |
| YOUTUBE_API_KEY              | Optional | YouTube Data API v3 key. Without it only yt-dlp search is used. |
| YOUTUBE_COOKIES_FILE         | Optional | Netscape cookies file path (mode 600 on APFS).                  |
| YOUTUBE_COOKIES_FROM_BROWSER | Optional | Browser name for --cookies-from-browser (e.g. chrome).          |

Never put API keys in config.json5 -- use .env (gitignored).

## Pipeline Step

Step **8** of 9, between verify and dispatch.
Non-blocking by default.

- --skip-trailers : skip for this run.
- --continue-on-trailer-error : continue to dispatch on errors.

Time budget: trailers.step.max_duration_sec (default 1800 s).

## CLI Commands

All subcommands mounted at `personalscraper trailers`.

### trailers scan

Dry-run: list media items missing trailers.

Options: --disk, --category, --since YYYY-MM-DD, --limit N, --level show|season|both, --season N, --no-refresh.
Exit codes: 0 (ok), 2 (bad --since date).

### trailers download

Discover and download missing trailers.

Options: --dry-run, --disk, --category, --since, --limit, --level, --season.
Exit codes: 0 (ok or zero errors), 1 (download error).

### trailers verify

Audit existing trailer files (size, extension, optional ffprobe).

Options: --disk, --category, --deep, --no-refresh.
Exit codes: 0 (all valid), 1 (invalid trailer found).

### trailers purge

Remove orphan trailer files.

Options: --dry-run, --disk.
Exit codes: 0 (ok), 1 (error).

### personalscraper run flags

| Flag                        | Description                                             |
| --------------------------- | ------------------------------------------------------- |
| --skip-trailers             | Skip the trailers step entirely                         |
| --continue-on-trailer-error | Continue to dispatch even when trailers step has errors |

## State File

Location: .data/trailers_state.json (via trailers.state_file).

### Composite key format

| Pattern                 | Example               | When                                      |
| ----------------------- | --------------------- | ----------------------------------------- |
| movie:tmdb:{id}         | movie:tmdb:550        | Movie with TMDB ID                        |
| tv:tmdb:{id}            | tv:tmdb:1396          | TV show trailer                           |
| tv:tmdb:{id}:season:{N} | tv:tmdb:1396:season:2 | Season-level trailer                      |
| manual:{hash}           | manual:abcd1234       | No TMDB ID (SHA-256 of title\|year\|type) |

### TrailerStatus values

| Value                   | Meaning                                           |
| ----------------------- | ------------------------------------------------- |
| downloaded              | Trailer placed successfully                       |
| no_trailer_available    | No usable URL found                               |
| bot_detected            | Bot-detection response; retried next run          |
| http_error              | HTTP error (403, 404); respects retry_after_days  |
| ytdlp_error             | Generic yt-dlp failure; respects retry_after_days |
| skipped_by_filter       | Excluded by config filter                         |
| orphan                  | Media directory gone; set by trailers purge       |
| already_present_on_disk | Valid trailer on storage disk (library scan)      |

### Retry policy

- Items with next_retry_at in the future are skipped.
- BOT_DETECTED is exempt from retry-after (retried each run).
- After bot_detected_max_consecutive_attempts consecutive BOT_DETECTED: permanent skip.

## Placement Convention

Plex-conformant naming — placement depends on media type:

**Movies** (Plex Local Media Assets — flat):
{media_dir}/{media_name}-trailer.{ext}
Example: Fight Club (1999)/Fight Club (1999)-trailer.mp4

**TV shows — show level** (Plex TV Series agent extras — subfolder only):
{show_dir}/Trailers/{show_name}.{ext}
Example: Breaking Bad (2008)/Trailers/Breaking Bad (2008).mp4

**TV shows — season level** (opt-in via trailers.seasons.enabled):
{show_dir}/Saison {NN}/Trailers/{show_name} - Saison {NN}.{ext}
Example: Breaking Bad (2008)/Saison 01/Trailers/Breaking Bad (2008) - Saison 01.mp4

The Plex TV Series agent requires the `Trailers/` subfolder for show-level and
season-level extras. Using the flat `{show}-trailer.{ext}` convention at show or
season level produces an unrecognised orphan video in Plex.

Accepted extensions: .mp4, .mkv, .webm (priority order).

NFO <trailer> tag: populated with YouTube URL for Plex/Kodi remote-trailer fallback.

### Legacy TV-show flat paths

Prior to the 2026-04-25 pipeline fix, TV show trailers were placed using the same
flat `{show}-trailer.{ext}` convention as movies. This produces unrecognised orphan
videos in Plex's TV Series agent. The correct convention is the subfolder path
`Trailers/{show}.{ext}` (or `Saison NN/Trailers/{show} - Saison NN.{ext}` for
season-level).

`find_existing_trailer()` probes the legacy flat path as a fallback so existing
files are detected as already-present rather than silently re-downloaded alongside
the correct new path. A `placement.legacy_tvshow_trailer_found` WARNING is emitted
when a legacy file is found.

To migrate legacy files to the correct location, run:

```
personalscraper trailers purge --legacy-paths
```

This helper is **not yet implemented**. Until it is, the legacy files remain in
place and are reported as already-present on each pipeline run.

### Library-aware idempotence (DESIGN section 8)

When trailers.library_check.tv_shows = true (default), the orchestrator calls
library.scanner.scan_library() once before processing TV show items.
If the show exists on a storage disk with a valid trailer, the entry is marked
already_present_on_disk and no network call is made.

- movies = false (films rarely re-ingested)
- tv_shows = true (new episodes arrive frequently)

## Security

- Cookie files: mode 600 required on APFS. yt-dlp rejects looser permissions.
- .env is gitignored. Never commit it.
- YOUTUBE_API_KEY and TMDB_READ_ACCESS_TOKEN belong in .env only.

## ToS Note

Downloading YouTube content is grey-area under YouTube ToS (section 5).
Personal offline viewing only. Do not redistribute downloaded trailers.

## Troubleshooting

| Symptom                              | Cause                            | Fix                                             |
| ------------------------------------ | -------------------------------- | ----------------------------------------------- |
| Many bot_detected items              | Rate-limiting or expired cookies | Refresh YOUTUBE_COOKIES_FILE                    |
| Items never retry after bot_detected | Max attempts reached             | Delete key from state JSON                      |
| NTFS trailer placement failure       | Long filename                    | Folder name <=255 chars; macFUSE required       |
| Quota exhausted                      | Daily API limit                  | Wait 24h or raise youtube_api.daily_quota_units |
| yt-dlp format errors                 | Outdated yt-dlp                  | pip install --upgrade yt-dlp                    |
| ffmpeg not found                     | Missing dependency               | brew install ffmpeg                             |
| State file locked                    | Concurrent process               | Wait for process to finish                      |
