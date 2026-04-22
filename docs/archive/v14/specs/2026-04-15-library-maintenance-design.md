# V14 — LIBRARY MAINTENANCE — Design Spec

> **Version:** v14
> **Date:** 2026-04-15
> **Status:** Approved (revised after review)
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
├── disk_cleaner.py    # Cleanup: .actors, empty dirs, junk — dry-run by default
├── validator.py       # NFO/artwork/naming validation → library_validation.json
├── analyzer.py        # Deep ffprobe scan: codec, audio, subs → library_analysis.json
├── recommender.py     # Cross analysis + preferences → library_recommendations.json
├── reporter.py        # Global stats from all JSON files
├── preferences.py     # Pydantic models for encoding/audio/subtitle preferences (config)
└── models.py          # @dataclass result models for scan, analysis, recommendation
```

**Note:** Module is named `disk_cleaner.py` (not `cleaner.py`) to avoid confusion with `sorter/cleaner.py` which handles filename cleaning.

### 3.2 Model convention

Following the established codebase pattern (V0-V13):

- **`@dataclass`** for all result/data models (scan items, analysis items, recommendations)
- **`pydantic BaseModel`** only for preference/configuration models (loaded from config)
- **`str`** for path fields in models serialized to JSON (matching `IndexEntry.path: str`)
- **`dataclasses.asdict()` + `json.dumps()`** for JSON serialization (with shared `Path`-safe encoder)
- **`media_type: str`** kept as bare string (`"movie"` | `"tvshow"`) — matching V0-V13 convention

### 3.3 Intermediate data files

All stored in `.personalscraper/` (same directory as `media_index.json`):

```
.personalscraper/
├── library_scan.json           # Lightweight inventory (~2000 entries)
├── library_analysis.json       # ffprobe details per video file
├── library_validation.json     # Validation results per item
├── library_recommendations.json # Prioritized re-download list
└── library_report.json         # Aggregated statistics
```

Each file is idempotent: re-running updates in place (no duplicates). Atomic write pattern: write to `.tmp` then rename. Each file wraps items in a container with metadata (scan date, filters used, schema version).

### 3.4 Data flow

```
library-scan ──→ library_scan.json ──→ library-validate
                                   ──→ library-clean
library-analyze ──→ library_analysis.json ──→ library-recommend
library-report ◄── all JSON files above
```

`library-scan` and `library-analyze` are independent (schedulable separately). `library-validate` and `library-clean` consume the scan. `library-recommend` consumes the analysis.

### 3.5 Lock policy

| Command                          |   Modifies disks?   |        Lock required?        |
| -------------------------------- | :-----------------: | :--------------------------: |
| `library-scan`                   |   No (read-only)    |              No              |
| `library-clean --apply`          | Yes (deletes files) | Yes — acquires pipeline lock |
| `library-validate`               |   No (read-only)    |              No              |
| `library-validate --fix --apply` | Yes (renames files) | Yes — acquires pipeline lock |
| `library-analyze`                |   No (read-only)    |              No              |
| `library-recommend`              |   No (read-only)    |              No              |
| `library-report`                 |   No (read-only)    |              No              |

Write commands acquire the existing pipeline lock (`lock.py`) to prevent conflict with a running pipeline.

## 4. CLI Commands

### 4.1 `personalscraper library-scan`

Lightweight scan — reads directories and NFOs, no ffprobe. Fast, minimal I/O.

```
personalscraper library-scan                    # Scan all mounted disks
personalscraper library-scan --disk Disk1       # Single disk
personalscraper library-scan --category films   # Single category (disk category name)
```

**Note on `--category`:** Uses disk-side category names (`films`, `series`, `films animations`, etc. — as defined in `DiskConfig`), NOT staging names (`001-MOVIES`, `002-TVSHOWS`).

**Collected per item:**

- Path, type (movie/tvshow), title, year
- NFO: present? valid? IDs (TMDB/IMDB)?
- Artwork: which files exist (poster, fanart, landscape, etc.)
- Structure: seasons (for TV), episodes, .actors/ present?
- Total folder size
- Detected issues (empty subdirs, junk, incorrect naming, NTFS-unsafe)
- Scan timestamp for incremental updates

**Reuses:**

- `MediaIndex.rebuild()` — provides the list of paths to iterate over (disk/category/item enumeration only). Scanner implements its own collection logic on top.
- `is_nfo_complete()` — quick NFO validation (see section 7 for refactoring note)
- `PATTERNS`, `SEASON_DIR_RE`, `DiskConfig`, `DiskStatus`

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

**NTFS deletion error handling:** Disks are NTFS via macFUSE. `os.chmod()` has no effect on NTFS, so `shutil.rmtree` may fail on `.actors/` or other directories with NTFS metadata issues. The cleaner must:

1. Catch `OSError` per-item and continue (never crash on a single deletion failure)
2. Report `"X deleted, Y failed (NTFS)"` — not a misleading global success
3. Log each failure with the specific path and error for debugging

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

**Distinction with `personalscraper enforce`:** `enforce` operates on the **staging area** (A TRIER/) for new media before dispatch. `library-validate` operates on the **storage disks** (Disk1-4) for existing library items. They share checker logic but have different scopes and entry points.

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
- Audio tracks: codec, language, channels, Atmos detection, default track flag
- Subtitle tracks: language, format (normalized: subrip→srt, hdmv_pgs_subtitle→pgs), forced flag, default flag
- File size, duration

**`--incremental` flag:** Skips files already in `library_analysis.json` whose size AND mtime haven't changed. Using both size and mtime reduces risk of missing re-encoded files with similar sizes.

**Reuses:** `scraper/mediainfo.py` → `extract_stream_info()` (see section 7 for required extensions).

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

**Output format designed for future auto-download integration** — each recommendation includes IMDB/TMDB IDs, current state, target state, and reasons. The `library_recommendations.json` format is the contract between V14 and the future auto-download system — treat it as a stable API.

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

### 5.1 Preferences (pydantic BaseModel — loaded from config)

```python
class VideoPreferences(BaseModel):
    preferred_codec: str = "hevc"
    fallback_codecs: list[str] = ["av1"]
    rejected_codecs: list[str] = ["mpeg2", "mpeg4"]
    preferred_resolution: str = "1080p"
    max_size_movie_gb: float = 4.0
    max_size_episode_gb: float = 2.0

    @model_validator(mode="after")
    def codecs_are_disjoint(self) -> Self:
        """Ensure preferred, fallback, and rejected codec sets don't overlap."""
        ...

class AudioPreferences(BaseModel):
    profile_priority: list[str] = ["multi", "vf", "vostfr", "vo"]
    min_channels: int = Field(default=2, ge=1)
    preferred_codec: str | None = None

class SubtitlePreferences(BaseModel):
    required_languages: list[str] = ["fra"]     # ISO 639-2/T (NOT "fre")
    preferred_languages: list[str] = ["fra", "eng"]
    warn_if_missing: bool = True

    @model_validator(mode="after")
    def required_subset_of_preferred(self) -> Self:
        """Ensure required_languages ⊆ preferred_languages."""
        ...

class RuleCriteria(BaseModel):
    """Structured criteria for encoding override rules.

    String fields use case-insensitive substring matching.
    ID fields use exact matching.
    At least one field must be non-None.
    """
    genre: str | None = None
    title: str | None = None
    imdb_id: str | None = None
    tmdb_id: str | None = None

class EncodingRule(BaseModel):
    criteria: RuleCriteria
    resolution: str | None = None
    codec: str | None = None
    max_size_gb: float | None = None

    @model_validator(mode="after")
    def has_at_least_one_target(self) -> Self:
        """At least one of resolution, codec, max_size_gb must be set."""
        ...

class LibraryPreferences(BaseModel):
    video: VideoPreferences = VideoPreferences()
    audio: AudioPreferences = AudioPreferences()
    subtitles: SubtitlePreferences = SubtitlePreferences()
    encoding_rules: list[EncodingRule] = []
```

**Note on `RuleCriteria`:** V14 restricts criteria to fields available in local NFOs: `genre`, `title`, `imdb_id`, `tmdb_id`. Fields like `franchise`, `studio`, `director` require TMDB API lookups and are deferred to a future version when the data source is defined.

**Configuration approach:** All library preferences live in a single `library_preferences.json` file in `.personalscraper/`. A single `.env` entry points to it:

```ini
LIBRARY_PREFERENCES_FILE=library_preferences.json
```

This avoids mixing flat `.env` scalars with complex nested structures, and serves as a prototype for the future config system overhaul (see ROADMAP.md).

### 5.2 Scan results (@dataclass — serialized to JSON)

```python
@dataclass
class NfoStatus:
    present: bool
    valid: bool                     # True only if present is True
    tmdb_id: str | None
    imdb_id: str | None

    def __post_init__(self) -> None:
        if not self.present:
            # NFO absent implies not valid and no IDs
            self.valid = False
            self.tmdb_id = None
            self.imdb_id = None

@dataclass
class SeasonInfo:
    number: int
    path: str                       # absolute path to season directory
    episode_count: int
    has_poster: bool
    episodes_with_nfo: int          # count of episodes that have .nfo files

@dataclass
class ArtworkStatus:
    """Artwork presence for known types. Named fields prevent typos."""
    poster: bool = False
    fanart: bool = False
    landscape: bool = False
    banner: bool = False
    clearlogo: bool = False
    clearart: bool = False
    discart: bool = False           # movies only
    characterart: bool = False      # tvshows only

@dataclass
class LibraryScanItem:
    path: str                       # absolute path (str for JSON serialization)
    disk: str                       # "Disk1", "Disk2", "Disk3", "Disk4"
    category: str                   # disk category name (e.g. "films", "series")
    media_type: str                 # "movie" | "tvshow"
    title: str
    year: int | None
    folder_size_gb: float           # standardized to GB everywhere
    nfo: NfoStatus
    artwork: ArtworkStatus
    actors_dir: bool                # .actors/ present?
    issues: list[str]               # structured issue strings (see Issue Constants)
    seasons: list[SeasonInfo] | None  # None for movies, list for tvshows
    scanned_at: str                 # ISO 8601 timestamp

@dataclass
class LibraryScanResult:
    """Top-level container for library_scan.json."""
    scanned_at: str
    disk_filter: str | None
    category_filter: str | None
    item_count: int
    items: list[LibraryScanItem]
```

**Issue constants** (used in `issues: list[str]`):

```python
ISSUE_EMPTY_SUBDIR = "empty_subdir"
ISSUE_JUNK_FILES = "junk_files"
ISSUE_NTFS_UNSAFE = "ntfs_unsafe_name"
ISSUE_BAD_DIR_NAME = "bad_dir_naming"
ISSUE_ACTORS_DIR = "actors_dir_present"
ISSUE_RELEASE_ARTIFACT = "release_group_artifact"
```

Using constants enables programmatic filtering by downstream consumers.

### 5.3 Analysis results (@dataclass — serialized to JSON)

```python
@dataclass
class VideoInfo:
    codec: str                      # "hevc", "h264", "av1", "mpeg2"...
    width: int
    height: int
    bitrate_kbps: int | None
    hdr: bool
    hdr_type: str | None            # only set when hdr=True: "hdr10", "dolby_vision"...

    @property
    def resolution(self) -> str:
        """Derive resolution label from height: 2160→'2160p', 1080→'1080p', etc."""
        ...

@dataclass
class AudioTrack:
    codec: str                      # "aac", "ac3", "eac3", "dts"
    language: str                   # ISO 639-2/T: "fra", "eng", "jpn"
    channels: int
    is_atmos: bool
    is_default: bool                # ffprobe default track flag

@dataclass
class SubtitleTrack:
    language: str                   # ISO 639-2/T
    format: str                     # normalized: "srt", "pgs", "ass", "dvd_subtitle"
    forced: bool
    is_default: bool

@dataclass
class MediaFileAnalysis:
    path: str                       # absolute path (str for JSON)
    size_gb: float                  # standardized to GB everywhere
    duration_seconds: float | None
    video: VideoInfo
    audio_tracks: list[AudioTrack]
    subtitle_tracks: list[SubtitleTrack]
    audio_profile: str              # "multi", "vf", "vostfr", "vo" — per FILE, not per show
    subtitle_languages: list[str]   # sorted list: ["eng", "fra"] — no fragile joined strings
    analyzed_at: str                # ISO 8601 timestamp

@dataclass
class LibraryAnalysisItem:
    """One library item (movie or show) with all its analyzed video files."""
    path: str                       # absolute path (str for JSON)
    disk: str
    category: str
    media_type: str                 # "movie" | "tvshow"
    title: str
    year: int | None
    files: list[MediaFileAnalysis]

@dataclass
class LibraryAnalysisResult:
    """Top-level container for library_analysis.json."""
    analyzed_at: str
    disk_filter: str | None
    category_filter: str | None
    item_count: int
    file_count: int
    items: list[LibraryAnalysisItem]
```

**Key design decisions:**

- `audio_profile` is per **file**, not per show — a series can have S1 in MULTI and S2 in VF. The recommender aggregates per-file profiles to detect disparate series.
- `subtitle_languages` is a sorted `list[str]` instead of a joined string like `"fra+eng"` — avoids ordering ambiguity and enables programmatic comparison.
- `resolution` is a computed property derived from `height`, not a stored field — prevents inconsistency between `resolution="1080p"` and `height=720`.
- `filename` field removed — redundant with `Path(path).name`, derivable when needed.

### 5.4 Recommendation results (@dataclass — serialized to JSON)

```python
@dataclass
class CurrentState:
    codec: str
    resolution: str
    size_gb: float                  # GB everywhere
    audio_profile: str
    subtitle_languages: list[str]

@dataclass
class TargetState:
    codec: str | None
    resolution: str | None
    max_size_gb: float | None

    def __post_init__(self) -> None:
        if self.codec is None and self.resolution is None and self.max_size_gb is None:
            raise ValueError("TargetState must have at least one non-None field")

PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"

@dataclass
class Recommendation:
    path: str                       # absolute path (str for JSON)
    title: str
    media_type: str                 # "movie" | "tvshow"
    disk: str
    category: str                   # needed for report aggregation
    tmdb_id: str | None
    imdb_id: str | None
    current: CurrentState
    target: TargetState
    reasons: list[str]              # human-readable, always non-empty
    priority: str                   # PRIORITY_HIGH | PRIORITY_MEDIUM | PRIORITY_LOW
    estimated_savings_gb: float | None
    matched_rule_index: int | None  # index into encoding_rules list, or None

@dataclass
class LibraryRecommendationResult:
    """Top-level container for library_recommendations.json."""
    generated_at: str
    total_recommendations: int
    estimated_total_savings_gb: float
    items: list[Recommendation]
```

## 6. Audio Profile Detection

Audio profile is deduced from ffprobe audio tracks per video file:

| Profile  | Condition                                              |
| -------- | ------------------------------------------------------ |
| `multi`  | ≥2 audio tracks with different languages               |
| `vf`     | Single audio track in `fra`                            |
| `vostfr` | Audio in non-French language + subtitle track in `fra` |
| `vo`     | Audio in non-French language without French subtitles  |

Priority order for recommendation matching: `multi` > `vf` > `vostfr` > `vo` (configurable via `AudioPreferences.profile_priority`).

**Edge cases:**

- Audio `fra` + audio `eng` = `multi` (not `vf`, because multiple languages present)
- Audio `jpn` + subtitle `fra` = `vostfr` (covers anime, not just English content)
- Detection uses `is_default` flag to identify primary audio track when multiple exist

## 7. Existing Code Reuse

| Existing module                                                | Used in V14                  | How                                                                                                |
| -------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------- |
| `dispatch/media_index.py` → `MediaIndex`                       | `scanner.py`                 | Provides path enumeration (disk → category → items). Scanner adds its own collection logic on top. |
| `dispatch/disk_scanner.py` → `DiskConfig`, `DiskStatus`        | `scanner.py`, `reporter.py`  | Disk config, free space, mount status                                                              |
| `scraper/mediainfo.py` → `extract_stream_info()`               | `analyzer.py`                | ffprobe extraction — extended (see below)                                                          |
| `is_nfo_complete()` (refactored)                               | `scanner.py`                 | Quick NFO validation (see below)                                                                   |
| `verify/checker.py` → `check_movie()`, `check_tvshow()`        | `validator.py`               | 12+ existing checks                                                                                |
| `verify/fixer.py` → `MediaFixer`                               | `validator.py --fix`         | Directory rename from NFO                                                                          |
| `text_utils.py` → `sanitize_filename()`, `fuzzy_match_score()` | `validator.py`, `scanner.py` | NTFS-safe naming, duplicate detection                                                              |
| `genre_mapper.py` → `categorize_from_nfo()`                    | `scanner.py`                 | Category/disk coherence check                                                                      |
| `naming_patterns.py` → `PATTERNS`, `SEASON_DIR_RE`             | `scanner.py`, `validator.py` | Expected artwork patterns, season regex                                                            |
| `config.py` → `Settings`                                       | All commands                 | Extended with `library_preferences_file` path                                                      |

### 7.1 Refactoring: `_is_nfo_complete()`

Currently a private function in `scraper/scraper.py`. Must be made public and moved to a shared location for V14 access. Options:

- Move to `text_utils.py` (existing shared module)
- Create `personalscraper/nfo_utils.py` (new shared module)

Decision at implementation time. The function signature and behavior remain unchanged.

### 7.2 Extensions to `extract_stream_info()`

The spec requires **4 new fields** beyond what `extract_stream_info()` currently returns:

| Field                         | Source                                                | Current state                               |
| ----------------------------- | ----------------------------------------------------- | ------------------------------------------- |
| `bitrate_kbps` (video)        | ffprobe `bit_rate` or computed `file_size / duration` | Not extracted                               |
| `is_atmos` (audio)            | Currently encoded as `codec = "atmos"` string         | Needs transformation to separate bool field |
| `forced` (subtitle)           | ffprobe `disposition.forced`                          | Not extracted                               |
| `format` (subtitle)           | ffprobe `codec_name` (needs normalization)            | Only `language` currently extracted         |
| `is_default` (audio/subtitle) | ffprobe `disposition.default`                         | Not extracted                               |

Implementation approach: extend `extract_stream_info()` to return these fields. The existing callers (scraper) will ignore the new fields — backwards compatible.

### 7.3 Pipeline code untouched

Pipeline code (V0-V13) is NOT modified. All new code lives in `personalscraper/library/`. The only changes to existing code are:

1. Move `_is_nfo_complete()` to shared location (section 7.1)
2. Extend `extract_stream_info()` with new fields (section 7.2)

## 8. Configuration

Single entry in `.env`:

```ini
# Path to library preferences JSON (relative to .personalscraper/)
LIBRARY_PREFERENCES_FILE=library_preferences.json
```

The `library_preferences.json` file lives in `.personalscraper/`:

```json
{
  "video": {
    "preferred_codec": "hevc",
    "fallback_codecs": ["av1"],
    "rejected_codecs": ["mpeg2", "mpeg4"],
    "preferred_resolution": "1080p",
    "max_size_movie_gb": 4.0,
    "max_size_episode_gb": 2.0
  },
  "audio": {
    "profile_priority": ["multi", "vf", "vostfr", "vo"],
    "min_channels": 2,
    "preferred_codec": null
  },
  "subtitles": {
    "required_languages": ["fra"],
    "preferred_languages": ["fra", "eng"],
    "warn_if_missing": true
  },
  "encoding_rules": [
    {
      "criteria": {
        "genre": "Animation",
        "tmdb_id": null,
        "imdb_id": null,
        "title": null
      },
      "resolution": null,
      "codec": "hevc",
      "max_size_gb": 2.0
    },
    {
      "criteria": { "imdb_id": "tt4154796" },
      "resolution": "2160p",
      "codec": "hevc",
      "max_size_gb": null
    }
  ]
}
```

**Design rationale:** All preferences in a single structured JSON file rather than scattered across `.env` variables. This avoids the tension between flat `.env` scalars and complex nested structures, and serves as a prototype for the future config system overhaul (see ROADMAP.md). The pydantic `LibraryPreferences` model validates the JSON on load with clear error messages.

**Language codes:** All language codes use **ISO 639-2/T** (`fra`, `eng`, `jpn`) — matching the convention established in `scraper/mediainfo.py` which converts ffprobe's 639-2/B codes (`fre`) to T codes (`fra`).

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
3. `library-clean --apply` removes .actors/, empty dirs, junk without touching media files — reports NTFS failures gracefully
4. `library-validate` detects invalid NFOs, missing artwork, incorrect naming
5. `library-analyze --incremental` scans video files with ffprobe without re-scanning unchanged files (size + mtime check)
6. `library-recommend` produces a prioritized list with estimated savings, based on configurable preferences loaded from JSON
7. `library-report` displays readable stats (space, codecs, audio, health)
8. All preferences (codec, audio, subs, sizes, rules) are in `library_preferences.json`, nothing hardcoded
9. Dry-run by default for any destructive action (`library-clean`, `library-validate --fix`)
10. `--disk` and `--category` filters on all commands
11. Write commands acquire pipeline lock, read commands don't
12. Documentation up to date: CLAUDE.md, MANUAL.md, `--help` complete
13. ROADMAP.md created with documented future versions
14. Unit tests for each module + integration tests
15. Each command schedulable via cron independently (exit code 0/1, no interactivity)
