# Insights Reference

Read-only analytics, reporting, and recommendation layer over the indexer SQLite DB.

## Overview

The `insights/` package (`personalscraper/insights/`) provides the analysis,
reporting, and recommendation functions that power the `library-analyze`,
`library-recommend`, and `library-report` CLI commands. It consumes the rows the
indexer wrote into the SQLite DB and turns them into health summaries, per-file
codec/audio/subtitle analysis, re-download recommendations, and a human-readable
report.

The package is strictly **read-only**: it never walks the filesystem, never runs
ffprobe, and never writes to the indexer DB. Every figure it surfaces comes from
rows the indexer scan and enrich passes already persisted (see
`docs/reference/indexer.md`). The stream-level data (codec / audio / subtitle /
HDR / Atmos) is read exclusively from the `media_stream` rows that
`indexer.scanner._modes.enrich` populated — `insights` is the sole reader of
that table and has no ffprobe successor to the deleted `analyzer.analyze_library`
re-scan. Side outputs (`library_recommendations.json`, the report) are written by
the CLI command layer, not by the package itself.

## Package layout

| Module           | Purpose                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| `analytics.py`   | DB-backed aggregate health summary and per-file stream analysis.        |
| `reporter.py`    | Aggregates the analysis plus command JSON outputs into a health report. |
| `recommender.py` | Crosses analysis with user preferences to produce re-download recs.     |
| `models.py`      | Dataclasses produced and consumed across the three modules.             |

## Data sources

`insights` reads the indexer schema (see `docs/reference/indexer.md` and
`docs/reference/indexer-json-shapes.md` for the column shapes):

| Table            | What is read                                                                                                                                  |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `media_item`     | Totals, `kind`, `title`, `year`, `category_id`, `nfo_status`, `artwork_json`, `date_metadata_refreshed`.                                      |
| `media_stream`   | Per-file `codec`, `lang`, `channels`, `width`/`height`, `duration_ms`, `bitrate`, `hdr_format`, `is_atmos`, `is_default`, `forced`, `format`. |
| `media_file`     | `filename`, `size_bytes`, `path_id`, `release_id` (size aggregation, soft-delete filter).                                                     |
| `media_release`  | Links a file to its owning movie item or episode.                                                                                             |
| `season`         | `has_poster` (season poster gaps), `item_id` (joins episode files to the show).                                                               |
| `episode`        | `season_id` / `id` — joins episode-level `media_release` rows back to the show item.                                                          |
| `item_attribute` | `dispatch_disk` / `dispatch_path` (per-disk distribution, item paths, disk/path filters).                                                     |
| `item_issue`     | Directory-hygiene issue tags (`actors_dir_present`, `junk_files`, etc.) for the report.                                                       |
| `path` / `disk`  | Path → disk joins for per-disk size aggregation and absolute path reconstruction.                                                             |

All of these must already be populated. `analyze` requires a completed scan;
`analyze_from_index` requires a completed enrich pass (`library-index --mode
enrich`) — items with no `media_stream` rows are silently skipped.

## analytics.py

Two public functions, both read-only DB queries.

### `analyze(conn) -> AnalysisResult`

Aggregate library health summary, queried entirely from the DB. Computes:

- Totals: `total_items`, `movies_count` (`kind='movie'`), `shows_count`
  (`kind='show'`), `total_size_gb`.
- NFO breakdown (`NfoStatusCounts`): `valid` / `invalid` / `missing` (missing
  also counts `nfo_status IS NULL`).
- Poster coverage (`ArtworkCounts`): present / missing, via
  `json_extract(artwork_json, '$.poster')`.
- `seasons_missing_poster` from `season.has_poster = 0`.
- Per-category breakdowns: `items_per_category`, `nfo_invalid_by_category`,
  `poster_missing_by_category`.
- `items_needing_rescrape`: items with `nfo_status != 'valid'` **or**
  `date_metadata_refreshed IS NULL` (rescraper candidates).
- Per-disk distribution: `items_per_disk` (from `item_attribute.dispatch_disk`)
  and `size_per_disk_gb` (sum of `media_file.size_bytes` joined to disk).
- `top_largest`: top-20 `(title, size_gb)` by descending size, resolved either
  via `media_release` linkage (post-enrich, exact) or a `dispatch_path` fallback.
- `scan_issues` / `actors_dir_count`: directory-hygiene issue counts from
  `item_issue` (so the report can flag dirty directories without re-walking disks).

Returns an `AnalysisResult`. Consumed by `reporter.generate_report` and by
`maintenance/rescraper.py`.

### `analyze_from_index(conn, disk_filter=None, category_filter=None, max_items=None) -> LibraryAnalysisResult`

Per-file codec/audio/subtitle/HDR/Atmos analysis built from `media_stream`
rows (the sole stream reader). For each `media_item`, it collects the video
files reachable through `media_release` (movie releases and episode releases),
filters non-video extensions and soft-deleted files, then builds one
`MediaFileAnalysis` per file:

- HDR detection comes from `media_stream.hdr_format` (`VideoInfo.hdr` is `True`
  only when that column is set).
- Dolby Atmos comes from `media_stream.is_atmos`, with a codec + channel-count
  fallback (`eac3` with ≥ 8 channels) for rows enriched before migration 004.
- Subtitle `format` / `forced` / `is_default` and `AudioTrack.is_default` fall
  back to conservative defaults (`"unknown"` / `False`) when absent.
- The audio profile (`multi` / `vf` / `vostfr` / `vo`) is deduced from the track
  languages by `deduce_audio_profile` (see below).

Optional filters narrow the result: `disk_filter` (matches
`item_attribute.dispatch_disk`), `category_filter` (matches
`media_item.category_id`), and `max_items` (cap in title-sort order). Items with
no `media_stream` rows are skipped. Returns a `LibraryAnalysisResult`, consumed
inline by `library-recommend`.

### `deduce_audio_profile(audio_tracks, subtitle_tracks) -> str`

Helper used by `analyze_from_index`. Rules:

- `multi` — ≥ 2 audio tracks with different languages.
- `vf` — a single French audio track (`fra` / `fre`).
- `vostfr` — non-French audio with a French subtitle track.
- `vo` — non-French audio without French subtitles (also the empty-track default).

## reporter.py

Aggregates the DB analysis and supplementary command JSON outputs into a single
`LibraryReport` dataclass.

### `generate_report(analysis_result=None, validation_data=None, recommendation_data=None, disk_statuses=None, rescrape_data=None) -> LibraryReport`

Every argument is optional — the report includes whatever data is present.
`analysis_result` (from `analytics.analyze`) is the single source of truth for
totals, NFO / artwork status, disk distribution, top-largest items, and
scan-issue counts. The supplementary JSON inputs are individual command outputs
this report folds in when present:

- `validation_data` — `library_validation.json` (from `library-validate`):
  valid / fixable / issue counts and per-item error/warning tallies.
- `recommendation_data` — `library_recommendations.json` (from
  `library-recommend`): recommendation count, estimated savings, per-priority
  breakdown, and top recommendation details.
- `disk_statuses` — live `DiskStatus` objects for free-space per disk.
- `rescrape_data` — `library_rescrape.json` (from `library-rescrape`): fixed /
  skipped / error counts and per-action tallies.

### `format_report_text(report) -> str`

Renders a `LibraryReport` as a detailed multi-line human-readable report
(sectioned: overview, disks, categories, scan issues, validation,
recommendations). The text includes per-issue explanations and suggested
remediation commands (e.g. `library-clean --only junk --apply`,
`library-rescrape --only nfo`). User-facing report strings are in French; the
JSON form (`--format json`) emits the raw `LibraryReport` fields.

## recommender.py

### `generate_recommendations(items, prefs, id_lookup=None) -> LibraryRecommendationResult`

Crosses the per-file analysis (`LibraryAnalysisItem` list) with the user's
`LibraryPrefs` (from `config.library`) to produce a prioritized list of
re-download recommendations. The output format is the contract for future
auto-download integration. Movies and TV shows are evaluated by separate
internal helpers.

**Inputs (from `LibraryPrefs` — the `library` block, `config/encoding.json5`):**

- `video.preferred_codec` (default `hevc`), `video.fallback_codecs`
  (default `["av1"]`), `video.rejected_codecs` (default `["mpeg2", "mpeg4"]`).
- `video.preferred_resolution` (default `1080p`),
  `video.max_size_movie_gb` (default `4.0`),
  `video.max_size_episode_gb` (default `2.0`).
- `audio.profile_priority` (default `["multi", "vf", "vostfr", "vo"]`).
- `subtitles.required_languages` (default `["fra"]`).
- `encoding_rules` — override rules matched per item. Each rule has
  `criteria` (`tmdb_id` exact, `title` case-insensitive substring, or `genre`)
  plus at least one target (`resolution`, `codec`, `max_size_gb`). The first
  matching rule wins and forces `high` priority. Note: `genre` matching is
  currently deferred (requires NFO genre data), and the legacy `imdb_id`
  criterion was dropped — rules key by `tmdb_id` / `title` / `genre` only.

**Recommendation logic:**

- **Movies** — checks (in order) encoding-rule overrides, rejected/non-preferred
  codec, oversize (vs `max_size_movie_gb`, escalated to `high` above 2×), audio
  profile rank, and missing required subtitles. Estimated savings are computed
  from the target size, or roughly from a codec downgrade (HEVC ≈ 40 % smaller).
- **TV shows** — flags disparate codecs across episodes, rejected / non-preferred
  per-episode codecs, and oversized episodes (vs `max_size_episode_gb`). Savings
  are estimated from total vs target episode size.

Conforming items (no reasons) yield no recommendation. Priority is one of
`high` / `medium` / `low` (`PRIORITY_*` constants).

**Output (`LibraryRecommendationResult`):** `generated_at`,
`total_recommendations`, `estimated_total_savings_gb`, and an `items` list of
`Recommendation` objects. Each `Recommendation` carries `current` /`target`
encoding states, human-readable `reasons` (always non-empty), `priority`,
`estimated_savings_gb`, `tmdb_id` / `imdb_id` (for future auto-download), and
`matched_rule_index`.

## models.py

Dataclasses shared across the package:

| Dataclass                      | Role                                                                       |
| ------------------------------ | -------------------------------------------------------------------------- |
| `NfoStatusCounts`              | NFO valid / invalid / missing breakdown.                                   |
| `ArtworkCounts`                | Poster present / missing counts.                                           |
| `AnalysisResult`               | Aggregate health summary returned by `analyze`.                            |
| `VideoInfo`                    | Per-file video stream (codec, dimensions, bitrate, HDR).                   |
| `AudioTrack`                   | One audio track (codec, language, channels, Atmos, default).               |
| `SubtitleTrack`                | One subtitle track (language, format, forced, default).                    |
| `MediaFileAnalysis`            | One video file with its video/audio/subtitle profile.                      |
| `LibraryAnalysisItem`          | One movie/show with all analyzed files.                                    |
| `LibraryAnalysisResult`        | Result of `analyze_from_index`.                                            |
| `CurrentState` / `TargetState` | Current vs desired encoding state for a recommendation.                    |
| `Recommendation`               | One re-download recommendation.                                            |
| `LibraryRecommendationResult`  | Top-level recommendations container (also `library_recommendations.json`). |

Priority constants: `PRIORITY_HIGH` (`"high"`), `PRIORITY_MEDIUM` (`"medium"`),
`PRIORITY_LOW` (`"low"`).

## CLI commands

The package is surfaced by three Typer commands in
`personalscraper/commands/library/analyze.py` (Typer maps the function name's
underscores to hyphens):

| Command             | Reads via                                            | Writes                                                                     |
| ------------------- | ---------------------------------------------------- | -------------------------------------------------------------------------- |
| `library-analyze`   | `analyze_from_index`                                 | Nothing — prints codec/audio summary.                                      |
| `library-recommend` | `analyze_from_index` → `generate_recommendations`    | `library_recommendations.json` (+ optional `library_recommendations.csv`). |
| `library-report`    | `analyze` + `generate_report` → `format_report_text` | Nothing — prints/emits the report.                                         |

- `library-analyze` summarizes codec / audio-profile distributions read from the
  enrich-populated `media_stream` rows. The result is **not** persisted —
  `library-recommend` re-runs the analysis inline. Options: `--disk`,
  `--category`, `--max-items`. (`--from-index` is a deprecated no-op kept for
  back-compat; the DB is always the source.)
- `library-recommend` feeds the inline analysis to the recommender using
  preferences from `config.library`, sorts by `--sort` (`priority` / `size` /
  `codec`), and writes `library_recommendations.json` to `paths.data_dir`.
  Options: `--sort`, `--export csv`, `--disk`, `--category`, `--from-index`
  (deprecated no-op).
- `library-report` queries the DB via `analyze` and folds in the
  `library_validation.json` / `library_recommendations.json` /
  `library_rescrape.json` outputs plus live disk free space, then renders with
  `format_report_text` (or raw JSON under `--format json`).

Both `library-analyze` and `library-recommend` require a prior
`library-index --mode enrich` run; when no `media_stream` rows exist they print
an explicit hint to run enrich first. See `docs/reference/commands.md` for the
full command catalog and `docs/reference/indexer.md` for the indexer/enrich
pipeline.
