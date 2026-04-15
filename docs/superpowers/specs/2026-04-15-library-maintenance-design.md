# V14 — LIBRARY MAINTENANCE — Design Spec

> **Version:** v14
> **Date:** 2026-04-15
> **Status:** Approved
> **Scope:** Scan, clean, validate, analyze, and report on the existing media library across 4 NTFS storage disks.

## 1. Purpose

The pipeline (V0-V13) handles **new** media from torrent download to storage dispatch. V14 addresses the **existing** library: years of accumulated inconsistencies from manual management and older scraping tools (MediaElch). Goals:

- Clean dead weight (.actors/, empty dirs, junk files)
- Validate NFO/artwork/naming conformity
- Analyze encoding quality (codec, audio, subtitles)
- Produce actionable re-download recommendations
- Report library health statistics

## 2. Approach

**Modular CLI commands** — 6 independent commands, each planifiable via cron, each producing JSON intermediate files consumed by downstream commands. Dry-run by default for any destructive action.

## 3. Architecture

### 3.1 Module structure

```
personalscraper/library/
├── __init__.py
├── scanner.py         # Lightweight scan: structure, NFO, artwork → library_scan.json
├── cleaner.py         # Cleanup: .actors, empty dirs, junk — dry-run by default
├── validator.py       # NFO/artwork/naming validation → library_validation.json
├── analyzer.py        # Deep ffprobe scan: codec, audio, subs → library_analysis.json
├── recommender.py     # Cross analysis + preferences → library_recommendations.json
├── reporter.py        # Global stats from all JSON files
├── preferences.py     # Pydantic models for encoding/audio/subtitle preferences
└── models.py          # Data models for scan, analysis, recommendation results
```

### 3.2 Intermediate data files

All stored in `.personalscraper/` (same directory as `media_index.json`):

```
.personalscraper/
├── library_scan.json           # Lightweight inventory (~2000 entries)
├── library_analysis.json       # ffprobe details per video file
├── library_validation.json     # Validation results per item
├── library_recommendations.json # Prioritized re-download list
└── library_report.json         # Aggregated statistics
```

Each file is idempotent: re-running updates in place (no duplicates). Atomic write pattern: write to `.tmp` then rename.

### 3.3 Data flow

```
library-scan ──→ library_scan.json ──→ library-validate
                                   ──→ library-clean
library-analyze ──→ library_analysis.json ──→ library-recommend
library-report ◄── all JSON files above
```

`library-scan` and `library-analyze` are independent (schedulable separately). `library-validate` and `library-clean` consume the scan. `library-recommend` consumes the analysis.

## 4. CLI Commands

### 4.1 `personalscraper library-scan`

Lightweight scan — reads directories and NFOs, no ffprobe. Fast, minimal I/O.

```
personalscraper library-scan                    # Scan all mounted disks
personalscraper library-scan --disk Disk1       # Single disk
personalscraper library-scan --category films   # Single category
personalscraper library-scan --dry-run          # Show what would be scanned
```

**Collected per item:**

- Path, type (movie/tvshow), title, year
- NFO: present? valid? IDs (TMDB/IMDB)?
- Artwork: which files exist (poster, fanart, landscape, etc.)
- Structure: seasons (for TV), episodes, .actors/ present?
- Total folder size
- Detected issues (empty subdirs, junk, incorrect naming, NTFS-unsafe)

**Reuses:** `MediaIndex.rebuild()`, `_is_nfo_complete()`, `PATTERNS`, `SEASON_DIR_RE`, `DiskConfig`, `DiskStatus`.

### 4.2 `personalscraper library-clean`

Non-destructive cleanup. **Dry-run by default** — requires `--apply` to execute.

```
personalscraper library-clean                    # Dry-run on everything
personalscraper library-clean --apply            # Execute cleanup
personalscraper library-clean --disk Disk1       # Single disk
personalscraper library-clean --only actors      # Only .actors/ directories
personalscraper library-clean --only empty       # Only empty directories
personalscraper library-clean --only junk        # Only .DS_Store, Thumbs.db, desktop.ini
personalscraper library-clean --only release     # Only empty release-group artifact dirs
```

**Cleanup actions:**

| Action                         | Target                                  |         Safe?         |
| ------------------------------ | --------------------------------------- | :-------------------: |
| Remove `.actors/`              | ~1,792 directories                      | Yes — unused by Plex  |
| Remove empty dirs              | ~104 directories                        | Yes — no content loss |
| Remove junk files              | `.DS_Store`, `Thumbs.db`, `desktop.ini` |   Yes — OS metadata   |
| Remove release-group artifacts | Empty dirs with torrent-style names     |      Yes — empty      |

No media file is ever touched. Dry-run shows exactly what would be deleted with sizes.

### 4.3 `personalscraper library-validate`

Validates conformity of each library item. Reuses `verify/checker.py` logic.

```
personalscraper library-validate                        # Validate everything
personalscraper library-validate --disk Disk1           # Single disk
personalscraper library-validate --level quick           # NFO + poster only
personalscraper library-validate --level full            # All checks (default)
personalscraper library-validate --fix --dry-run         # Show possible fixes
personalscraper library-validate --fix --apply           # Apply fixes
```

**Checks:**

- NFO valid (parsable XML, uniqueid present)
- Directory naming conforms to `Title (Year)`
- Minimum artwork (poster + landscape)
- Season structure (TV shows)
- NTFS-safe filenames
- No orphaned files
- Category/disk coherence (via GenreMapper)

**Automatic fixes (with `--fix --apply`):**

- Rename directories from NFO data
- Sanitize NTFS-unsafe names
- Remove corrupt NFOs (unparsable XML) to force future re-scrape

### 4.4 `personalscraper library-analyze`

Deep scan with ffprobe — **most I/O-intensive**. Schedule during off-peak hours.

```
personalscraper library-analyze                         # Analyze everything
personalscraper library-analyze --disk Disk2            # Single disk
personalscraper library-analyze --category series       # Single category
personalscraper library-analyze --incremental           # Skip already-analyzed
personalscraper library-analyze --max-items 100         # Limit items
```

**Extracted per video file (ffprobe):**

- Video: codec, resolution, width, height, bitrate, HDR, HDR type
- Audio tracks: codec, language, channels, Atmos detection
- Subtitle tracks: language, format (SRT/PGS/ASS), forced flag
- File size, duration

**`--incremental` flag:** Skips files already in `library_analysis.json` whose size hasn't changed. Essential for avoiding full rescan.

**Reuses:** `scraper/mediainfo.py` → `extract_stream_info()`, extended with bitrate extraction.

### 4.5 `personalscraper library-recommend`

Crosses analysis with preferences to produce the re-download recommendation list.

```
personalscraper library-recommend                       # Generate recommendations
personalscraper library-recommend --sort size            # Sort by potential savings
personalscraper library-recommend --sort codec           # Sort by current codec
personalscraper library-recommend --export csv           # Export to CSV
```

**Recommendation criteria:**

- Non-optimal codec (H.264 when H.265 preferred)
- Excessive size (movie > `max_size_movie_gb`, episode > `max_size_episode_gb`)
- Non-conforming audio (no MULTI or VF when preferred)
- Missing subtitles (no FR when required)
- Override rules (`encoding_rules.json`) not met
- Disparate series (mixed H.264/H.265 episodes in same show)

**Priority levels:**

- **high**: rejected codec (mpeg2/mpeg4) OR size > 2× max OR override rule not met
- **medium**: non-preferred codec (h264→hevc) OR size > max OR missing audio
- **low**: missing subtitles OR incomplete artwork

**Output format designed for future auto-download integration** — each recommendation includes IMDB/TMDB IDs, current state, target state, and reasons.

### 4.6 `personalscraper library-report`

Human-readable library statistics.

```
personalscraper library-report                          # Full report
personalscraper library-report --format json            # JSON export
```

**Contents:**

- Total / used / free space per disk
- Item counts per category per disk
- Codec distribution (H.264 vs H.265 vs other)
- Audio distribution (MULTI vs VF vs VOSTFR vs VO)
- Top 20 largest items
- Validation summary (% conforming, % fixable, % blocked)
- Estimated savings if all recommendations followed

## 5. Data Models

### 5.1 Preferences

```python
class VideoPreferences(BaseModel):
    preferred_codec: str = "hevc"
    fallback_codecs: list[str] = ["av1"]
    rejected_codecs: list[str] = ["mpeg2", "mpeg4"]
    preferred_resolution: str = "1080p"
    max_size_movie_gb: float = 4.0
    max_size_episode_gb: float = 2.0

class AudioPreferences(BaseModel):
    language_priority: list[str] = ["multi", "vf", "vostfr", "vo"]
    min_channels: int = 2
    preferred_codec: str | None = None

class SubtitlePreferences(BaseModel):
    required_languages: list[str] = ["fre"]
    preferred_languages: list[str] = ["fre", "eng"]
    warn_if_missing: bool = True

class EncodingRule(BaseModel):
    criteria: dict[str, str]    # {"franchise": "Marvel", "studio": "A24", "imdb_id": "tt..."}
    resolution: str | None = None
    codec: str | None = None
    max_size_gb: float | None = None

class LibraryPreferences(BaseModel):
    video: VideoPreferences = VideoPreferences()
    audio: AudioPreferences = AudioPreferences()
    subtitles: SubtitlePreferences = SubtitlePreferences()
    encoding_rules: list[EncodingRule] = []
```

### 5.2 Scan results

```python
class NfoStatus(BaseModel):
    present: bool
    valid: bool
    tmdb_id: str | None
    imdb_id: str | None

class SeasonInfo(BaseModel):
    number: int
    episode_count: int
    has_poster: bool

class LibraryScanItem(BaseModel):
    path: Path
    disk: str
    category: str
    media_type: str             # "movie" | "tvshow"
    title: str
    year: int | None
    folder_size_mb: float
    nfo: NfoStatus
    artwork: dict[str, bool]    # {"poster": True, "landscape": False, ...}
    actors_dir: bool
    issues: list[str]
    seasons: list[SeasonInfo] | None
```

### 5.3 Analysis results

```python
class VideoInfo(BaseModel):
    codec: str
    resolution: str
    width: int
    height: int
    bitrate_kbps: int | None
    hdr: bool
    hdr_type: str | None

class AudioTrack(BaseModel):
    codec: str
    language: str               # ISO 639-2/T
    channels: int
    is_atmos: bool

class SubtitleTrack(BaseModel):
    language: str
    format: str                 # "srt", "pgs", "ass"
    forced: bool

class MediaFileAnalysis(BaseModel):
    path: Path
    filename: str
    size_mb: float
    duration_seconds: float | None
    video: VideoInfo
    audio_tracks: list[AudioTrack]
    subtitle_tracks: list[SubtitleTrack]

class LibraryAnalysisItem(BaseModel):
    path: Path
    media_type: str
    files: list[MediaFileAnalysis]
    audio_profile: str          # "multi", "vf", "vostfr", "vo" (deduced)
    subtitle_profile: str       # "fre+eng", "fre", "none"
```

### 5.4 Recommendation results

```python
class CurrentState(BaseModel):
    codec: str
    resolution: str
    size_gb: float
    audio_profile: str
    subtitle_languages: list[str]

class TargetState(BaseModel):
    codec: str | None
    resolution: str | None
    max_size_gb: float | None

class Recommendation(BaseModel):
    path: Path
    title: str
    media_type: str
    disk: str
    tmdb_id: str | None
    imdb_id: str | None
    current: CurrentState
    target: TargetState
    reasons: list[str]
    priority: str               # "high", "medium", "low"
    estimated_savings_gb: float | None
    matched_rule: str | None
```

## 6. Audio Profile Detection

Audio profile is deduced from ffprobe audio tracks:

| Profile  | Condition                                                    |
| -------- | ------------------------------------------------------------ |
| `multi`  | ≥2 audio tracks with different languages                     |
| `vf`     | Single audio track in `fra`/`fre`                            |
| `vostfr` | Audio in non-French language + subtitle track in `fra`/`fre` |
| `vo`     | Audio in non-French language without French subtitles        |

Priority order for recommendation matching: `multi` > `vf` > `vostfr` > `vo` (configurable).

## 7. Existing Code Reuse

| Existing module                                                | Used in V14                  | How                                        |
| -------------------------------------------------------------- | ---------------------------- | ------------------------------------------ |
| `dispatch/media_index.py` → `MediaIndex`                       | `scanner.py`                 | Rebuild index for complete disk inventory  |
| `dispatch/disk_scanner.py` → `DiskConfig`, `DiskStatus`        | `scanner.py`, `reporter.py`  | Disk config, free space, mount status      |
| `scraper/mediainfo.py` → `extract_stream_info()`               | `analyzer.py`                | ffprobe extraction — extended with bitrate |
| `scraper/scraper.py` → `_is_nfo_complete()`                    | `scanner.py`                 | Quick NFO validation                       |
| `verify/checker.py` → `check_movie()`, `check_tvshow()`        | `validator.py`               | 12+ existing checks                        |
| `verify/fixer.py` → `MediaFixer`                               | `validator.py --fix`         | Directory rename from NFO                  |
| `text_utils.py` → `sanitize_filename()`, `fuzzy_match_score()` | `validator.py`, `scanner.py` | NTFS-safe naming, duplicate detection      |
| `genre_mapper.py` → `categorize_from_nfo()`                    | `scanner.py`                 | Category/disk coherence check              |
| `naming_patterns.py` → `PATTERNS`, `SEASON_DIR_RE`             | `scanner.py`, `validator.py` | Expected artwork patterns, season regex    |
| `config.py` → `Settings`                                       | All commands                 | Extended with `LibraryPreferences`         |

**Only change to existing code:** Add `bitrate_kbps` extraction to `scraper/mediainfo.py`.

**Pipeline code (V0-V13) is NOT modified.** All new code lives in `personalscraper/library/`.

## 8. Configuration

New entries in `config.py` / `.env`:

```ini
# Video preferences
LIBRARY_PREFERRED_CODEC=hevc
LIBRARY_PREFERRED_RESOLUTION=1080p
LIBRARY_MAX_SIZE_MOVIE_GB=4.0
LIBRARY_MAX_SIZE_EPISODE_GB=2.0

# Audio preferences
LIBRARY_AUDIO_PRIORITY=multi,vf,vostfr,vo

# Subtitle preferences
LIBRARY_SUBTITLE_REQUIRED=fre
LIBRARY_SUBTITLE_PREFERRED=fre,eng

# Override rules (separate JSON file)
LIBRARY_ENCODING_RULES_FILE=encoding_rules.json
```

The `encoding_rules.json` file lives in `.personalscraper/`:

```json
[
  {
    "criteria": { "franchise": "Marvel" },
    "resolution": "2160p",
    "codec": "hevc"
  },
  { "criteria": { "studio": "A24" }, "resolution": "1080p", "codec": "hevc" },
  { "criteria": { "imdb_id": "tt1234567" }, "resolution": "2160p" }
]
```

Criteria keys: `franchise`, `studio`, `director`, `genre`, `title`, `imdb_id`, `tmdb_id`.
Matching is case-insensitive substring for string fields, exact match for IDs.

## 9. Documentation Deliverables

| File                     | Update                                                                                               |
| ------------------------ | ---------------------------------------------------------------------------------------------------- |
| `CLAUDE.md`              | Add 6 library-\* commands, config section, V14 in version table                                      |
| `MANUAL.md`              | New section "Maintenance médiathèque" (French) with examples                                         |
| `ROADMAP.md`             | **New file** — future versions (auto-download, watcher, config overhaul, staging decouple, trailers) |
| `docs/IMPLEMENTATION.md` | V14 phase tracking                                                                                   |
| CLI `--help`             | All commands with Rich formatting, examples, grouped by Pipeline/Library                             |

## 10. Acceptance Criteria

V14 is done when:

1. The 6 `library-*` commands work with detailed `--help` and examples
2. `library-scan` produces a complete inventory of all 4 disks in < 5 minutes
3. `library-clean --apply` removes .actors/, empty dirs, junk without touching media files
4. `library-validate` detects invalid NFOs, missing artwork, incorrect naming
5. `library-analyze --incremental` scans video files with ffprobe without re-scanning already-analyzed files
6. `library-recommend` produces a prioritized list with estimated savings, based on configurable preferences
7. `library-report` displays readable stats (space, codecs, audio, health)
8. All preferences (codec, audio, subs, sizes, rules) are in config, nothing hardcoded
9. Dry-run by default for any destructive action (`library-clean`, `library-validate --fix`)
10. `--disk` and `--category` filters on all commands
11. Documentation up to date: CLAUDE.md, MANUAL.md, `--help` complete
12. ROADMAP.md created with documented future versions
13. Unit tests for each module + integration tests
14. Each command schedulable via cron independently (exit code 0/1, no interactivity)
