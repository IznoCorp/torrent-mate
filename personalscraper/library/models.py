"""Data models for library maintenance commands.

Result models use @dataclass. Path fields use str
for JSON serialization compatibility (matching IndexEntry pattern).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path as PathLib
from typing import Any, cast


@dataclass
class NfoStatus:
    """NFO file presence and validity status.

    Invariant: if present is False, valid is False and IDs are None.

    Attributes:
        present: Whether the NFO file exists on disk.
        valid: Whether the NFO is parsable XML with at least one uniqueid.
        tmdb_id: TMDB ID extracted from NFO, if valid.
        imdb_id: IMDB ID extracted from NFO, if valid.
        tvdb_id: TVDB ID extracted from NFO, if valid. Provider-ids
            feature: indexer must persist all 3 families separately so
            queries can resolve a show by any of its uniqueids.
        canonical_provider: ``"tvdb"`` / ``"tmdb"`` when the NFO has a
            ``<uniqueid default="true">`` of that family. ``None``
            otherwise (legacy NFO without default attr or unrecognised
            family).
        ratings: List of ``{source, score, votes}`` dicts parsed from
            the ``<ratings>`` block. Empty when the NFO has no ratings
            or is invalid. ``source`` uses the canonical
            internal name (``"imdb"``, ``"tmdb"``,
            ``"rotten_tomatoes"``, ``"metacritic"``, ``"trakt"``) —
            the NFO display name (e.g. ``themoviedb``) is mapped back
            at extraction time so the indexer's ``ratings_json``
            stays uniform with what the scraper writes.
    """

    present: bool
    valid: bool
    tmdb_id: str | None
    imdb_id: str | None
    tvdb_id: str | None = None
    canonical_provider: str | None = None
    ratings: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Enforce invariant: absent NFO cannot be valid or have IDs."""
        if not self.present:
            self.valid = False
            self.tmdb_id = None
            self.imdb_id = None
            self.tvdb_id = None
            self.canonical_provider = None
            self.ratings = []


# --- Issue constants for programmatic filtering ---

ISSUE_EMPTY_SUBDIR = "empty_subdir"
ISSUE_JUNK_FILES = "junk_files"
ISSUE_NTFS_UNSAFE = "ntfs_unsafe_name"
ISSUE_BAD_DIR_NAME = "bad_dir_naming"
ISSUE_ACTORS_DIR = "actors_dir_present"
ISSUE_RELEASE_ARTIFACT = "release_group_artifact"


@dataclass
class ArtworkStatus:
    """Artwork presence for known types.

    Named fields prevent typos (vs dict[str, bool]).
    Matches artwork types from naming_patterns.py.

    Attributes:
        poster: Movie poster or tvshow poster.
        fanart: Background fanart image.
        landscape: Landscape/thumb image.
        banner: Banner image.
        clearlogo: Transparent logo.
        clearart: Transparent character art.
        discart: Disc artwork (movies only).
        characterart: Character art (tvshows only).
    """

    poster: bool = False
    fanart: bool = False
    landscape: bool = False
    banner: bool = False
    clearlogo: bool = False
    clearart: bool = False
    discart: bool = False
    characterart: bool = False


@dataclass
class SeasonInfo:
    """TV show season metadata.

    Attributes:
        number: Season number (1-based).
        path: Absolute path to season directory (str for JSON).
        episode_count: Number of video files in season dir.
        has_poster: Whether season poster exists.
        episodes_with_nfo: Count of episodes that have .nfo files.
    """

    number: int
    path: str
    episode_count: int
    has_poster: bool
    episodes_with_nfo: int


@dataclass
class LibraryScanItem:
    """Single library item from a lightweight scan.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        disk: Disk ID from config (e.g. "disk_1", "drive_a").
        category: Category ID from config (e.g. "movies", "tv_shows").
        media_type: "movie" or "tvshow".
        title: Parsed title from directory name.
        year: Parsed year from directory name, if present.
        folder_size_gb: Total directory size in GB.
        nfo: NFO file status.
        artwork: Artwork presence per type.
        actors_dir: Whether .actors/ directory exists.
        issues: List of issue constants detected.
        seasons: Season info list (None for movies).
        scanned_at: ISO 8601 timestamp of this scan.
    """

    path: str
    disk: str
    category: str
    media_type: str
    title: str
    year: int | None
    folder_size_gb: float
    nfo: NfoStatus
    artwork: ArtworkStatus
    actors_dir: bool
    issues: list[str] = field(default_factory=list)
    seasons: list[SeasonInfo] | None = None
    scanned_at: str = ""


# --- Validation models ---

_VALID_VALIDATION_STATUSES = {"valid", "fixed", "issues"}


@dataclass
class ValidationItem:
    """Validation result for a single library item.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        disk: Disk name.
        category: Category name.
        media_type: "movie" or "tvshow".
        title: Media title.
        year: Release year.
        status: "valid", "fixed", or "issues" (has quality problems).
        errors: List of error check names that failed.
        warnings: List of warning check names that failed.
        fixes_applied: List of fixes that were applied (if --fix --apply).
    """

    path: str
    disk: str
    category: str
    media_type: str
    title: str
    year: int | None
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Enforce status/errors/fixes_applied consistency."""
        if self.status not in _VALID_VALIDATION_STATUSES:
            raise ValueError(f"status must be one of {_VALID_VALIDATION_STATUSES}, got '{self.status}'")
        if self.status == "fixed" and not self.fixes_applied:
            raise ValueError("status='fixed' requires non-empty fixes_applied")
        if self.status == "valid" and (self.errors or self.fixes_applied):
            raise ValueError("status='valid' must have empty errors and fixes_applied")
        if self.status == "issues" and not (self.errors or self.warnings):
            raise ValueError("status='issues' requires non-empty errors or warnings")


@dataclass
class LibraryValidationResult:
    """Top-level container for library_validation.json."""

    validated_at: str
    disk_filter: str | None
    category_filter: str | None
    total_items: int
    valid_count: int
    fixed_count: int
    issues_count: int
    items: list[ValidationItem] = field(default_factory=list)


# --- Priority constants ---

PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"


# --- Analysis models ---


@dataclass
class VideoInfo:
    """Video stream information extracted by ffprobe.

    Resolution is derived from height in __post_init__ to ensure it is
    included in JSON serialization via asdict() while preventing
    inconsistency with actual dimensions.

    Attributes:
        codec: Video codec name ("hevc", "h264", "av1", etc.).
        width: Frame width in pixels.
        height: Frame height in pixels.
        bitrate_kbps: Video bitrate in kbps (None if unavailable).
        hdr: Whether the video is HDR.
        hdr_type: HDR standard (only set when hdr=True).
        resolution: Derived from height (e.g. "1080p"). Set automatically.
    """

    codec: str
    width: int
    height: int
    bitrate_kbps: int | None
    hdr: bool
    hdr_type: str | None
    resolution: str = ""

    def __post_init__(self) -> None:
        """Derive resolution from height and enforce hdr/hdr_type consistency."""
        self.resolution = f"{self.height}p"
        if not self.hdr:
            self.hdr_type = None


@dataclass
class AudioTrack:
    """Single audio track from ffprobe.

    Attributes:
        codec: Audio codec ("aac", "ac3", "eac3", "dts").
        language: ISO 639-2/T code ("fra", "eng", "jpn").
        channels: Number of audio channels.
        is_atmos: Whether Dolby Atmos is detected.
        is_default: Whether this is the default audio track.
    """

    codec: str
    language: str
    channels: int
    is_atmos: bool
    is_default: bool


@dataclass
class SubtitleTrack:
    """Single subtitle track from ffprobe.

    Attributes:
        language: ISO 639-2/T code.
        format: Normalized format ("srt", "pgs", "ass", "dvd_subtitle").
        forced: Whether subtitle is flagged as forced.
        is_default: Whether this is the default subtitle track.
    """

    language: str
    format: str
    forced: bool
    is_default: bool


@dataclass
class MediaFileAnalysis:
    """Analysis results for a single video file.

    Audio profile is per-file (not per-show) because episodes in a series
    can have different audio configurations.

    Attributes:
        path: Absolute path to the video file (str for JSON).
        size_gb: File size in GB (standardized unit).
        duration_seconds: Duration in seconds (None if unavailable).
        video: Video stream info.
        audio_tracks: All audio tracks.
        subtitle_tracks: All subtitle tracks.
        audio_profile: Deduced profile ("multi", "vf", "vostfr", "vo").
        subtitle_languages: Sorted list of subtitle language codes.
        analyzed_at: ISO 8601 timestamp.
    """

    path: str
    size_gb: float
    duration_seconds: float | None
    video: VideoInfo
    audio_tracks: list[AudioTrack]
    subtitle_tracks: list[SubtitleTrack]
    audio_profile: str
    subtitle_languages: list[str] = field(default_factory=list)
    analyzed_at: str = ""


@dataclass
class LibraryAnalysisItem:
    """One library item (movie or show) with all analyzed video files.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        disk: Disk name.
        category: Disk category name.
        media_type: "movie" or "tvshow".
        title: Media title.
        year: Release year.
        files: Analysis results per video file.
    """

    path: str
    disk: str
    category: str
    media_type: str
    title: str
    year: int | None
    files: list[MediaFileAnalysis] = field(default_factory=list)


@dataclass
class LibraryAnalysisResult:
    """In-memory container for ``analyze_library`` ffprobe results.

    Returned by :func:`personalscraper.library.analyzer.analyze_library`
    and consumed inline by ``library-recommend``.
    """

    analyzed_at: str
    disk_filter: str | None
    category_filter: str | None
    item_count: int
    file_count: int
    items: list[LibraryAnalysisItem] = field(default_factory=list)


# --- Recommendation models ---


@dataclass
class CurrentState:
    """Current encoding state of a media item.

    Attributes:
        codec: Current video codec.
        resolution: Current resolution label.
        size_gb: Current file/folder size in GB.
        audio_profile: Deduced audio profile.
        subtitle_languages: Available subtitle languages.
    """

    codec: str
    resolution: str
    size_gb: float
    audio_profile: str
    subtitle_languages: list[str] = field(default_factory=list)


@dataclass
class TargetState:
    """Desired encoding state for a recommendation.

    At least one field must be non-None.

    Attributes:
        codec: Target video codec (None = no change).
        resolution: Target resolution (None = no change).
        max_size_gb: Maximum acceptable size in GB (None = no change).
    """

    codec: str | None
    resolution: str | None
    max_size_gb: float | None

    def __post_init__(self) -> None:
        """Reject empty targets — a recommendation must change something."""
        if self.codec is None and self.resolution is None and self.max_size_gb is None:
            raise ValueError("TargetState must have at least one non-None field")


@dataclass
class Recommendation:
    """Single re-download recommendation.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        title: Media title.
        media_type: "movie" or "tvshow".
        disk: Disk where the item lives.
        category: Disk category name.
        tmdb_id: TMDB ID for future auto-download integration.
        imdb_id: IMDB ID for future auto-download integration.
        current: Current encoding state.
        target: Desired encoding state.
        reasons: Human-readable list of reasons (always non-empty).
        priority: PRIORITY_HIGH, PRIORITY_MEDIUM, or PRIORITY_LOW.
        estimated_savings_gb: Estimated space savings (None if unknown).
        matched_rule_index: Index into encoding_rules list (None if default).
    """

    path: str
    title: str
    media_type: str
    disk: str
    category: str
    tmdb_id: str | None
    imdb_id: str | None
    current: CurrentState
    target: TargetState
    reasons: list[str] = field(default_factory=list)
    priority: str = PRIORITY_MEDIUM
    estimated_savings_gb: float | None = None
    matched_rule_index: int | None = None

    def __post_init__(self) -> None:
        """Validate that reasons is non-empty and priority is valid."""
        if not self.reasons:
            raise ValueError("Recommendation must have at least one reason")
        valid = {PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW}
        if self.priority not in valid:
            raise ValueError(f"Invalid priority '{self.priority}', must be one of {valid}")


@dataclass
class LibraryRecommendationResult:
    """Top-level container for library_recommendations.json."""

    generated_at: str
    total_recommendations: int
    estimated_total_savings_gb: float
    items: list[Recommendation] = field(default_factory=list)


# --- Rescrape action constants ---

ACTION_NFO_REGENERATED = "nfo_regenerated"
ACTION_ARTWORK_DOWNLOADED = "artwork_downloaded"
ACTION_EPISODES_RENAMED = "episodes_renamed"
SKIP_LOW_CONFIDENCE = "low_confidence_match"
SKIP_NO_MATCH = "no_match"
SKIP_ALREADY_OK = "already_conforming"

_VALID_ONLY_FILTERS = {"nfo", "artwork", "episodes"}
_VALID_ID_SOURCES = {"nfo", "api_match"}


@dataclass
class RescrapeAction:
    """Single repair action taken on a media item.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        title: Media title.
        media_type: "movie" or "tvshow".
        disk: Disk name.
        category: Category name.
        actions_taken: List of action constants performed.
        actions_skipped: List of skip reason constants.
        errors: Per-item errors (API failure, NTFS write error, etc.).
        tmdb_id: TMDB ID used for API calls (str for JSON, converted from int).
        id_source: How the ID was obtained: "nfo" or "api_match".
        match_confidence: Match confidence 0.0-1.0 (None if ID from NFO).
        rescraped_at: ISO 8601 timestamp of this action.
    """

    path: str
    title: str
    media_type: str
    disk: str
    category: str
    actions_taken: list[str]
    actions_skipped: list[str]
    errors: list[str]
    tmdb_id: str | None
    id_source: str | None
    match_confidence: float | None
    rescraped_at: str = ""

    def __post_init__(self) -> None:
        """Enforce media_type and confidence constraints."""
        if self.media_type not in ("movie", "tvshow"):
            raise ValueError(f"media_type must be 'movie' or 'tvshow', got '{self.media_type}'")
        if self.match_confidence is not None and not (0.0 <= self.match_confidence <= 1.0):
            raise ValueError(f"match_confidence must be 0.0-1.0, got {self.match_confidence}")
        if self.id_source is not None and self.id_source not in _VALID_ID_SOURCES:
            raise ValueError(f"id_source must be one of {_VALID_ID_SOURCES} or None, got '{self.id_source}'")
        if self.tmdb_id is None and self.match_confidence is not None:
            self.match_confidence = None


@dataclass
class LibraryRescrapeResult:
    """Top-level container for library_rescrape.json.

    Attributes:
        rescraped_at: ISO 8601 timestamp of rescrape start.
        disk_filter: Disk filter applied (None = all disks).
        category_filter: Category filter applied (None = all).
        only_filter: Action filter ("nfo", "artwork", "episodes", or None = all).
        dry_run: Whether this was a dry-run (no actual changes).
        fixed_count: Items successfully repaired.
        skipped_count: Items skipped (low confidence, already OK, etc.).
        error_count: Items with errors.
        items: List of per-item rescrape actions.
    """

    rescraped_at: str
    disk_filter: str | None
    category_filter: str | None
    only_filter: str | None
    dry_run: bool
    fixed_count: int
    skipped_count: int
    error_count: int
    items: list[RescrapeAction] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate only_filter."""
        if self.only_filter is not None and self.only_filter not in _VALID_ONLY_FILTERS:
            raise ValueError(f"only_filter must be one of {_VALID_ONLY_FILTERS} or None")


# --- JSON serialization helpers ---


def _json_default(obj: object) -> str:
    """JSON encoder fallback for Path and other non-serializable types."""
    if isinstance(obj, PathLib):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def serialize_to_json(obj: object) -> str:
    """Serialize a dataclass instance to JSON string.

    Handles Path objects via custom encoder. Uses dataclasses.asdict()
    for conversion, matching the IndexEntry serialization pattern.

    Args:
        obj: A dataclass instance.

    Returns:
        JSON string with 2-space indentation.
    """
    # mypy: asdict requires DataclassInstance; callers always pass a dataclass instance.
    return json.dumps(asdict(obj), default=_json_default, indent=2, ensure_ascii=False)  # type: ignore[call-overload]


def write_json(obj: object, path: PathLib) -> None:
    """Atomically write a dataclass to a JSON file.

    Writes to a .tmp file first, then renames to target path.
    Prevents corruption from interrupted writes.

    Args:
        obj: A dataclass instance.
        path: Target file path.
    """
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(serialize_to_json(obj), encoding="utf-8")
    tmp_path.rename(path)


def read_json(path: PathLib) -> dict[str, Any]:
    """Read a JSON file and return parsed dict.

    Args:
        path: Path to JSON file.

    Returns:
        Parsed dictionary.
    """
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
