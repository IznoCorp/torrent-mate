"""Data models for library maintenance commands.

Result models use @dataclass (V0-V13 convention). Path fields use str
for JSON serialization compatibility (matching IndexEntry pattern).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path as PathLib


@dataclass
class NfoStatus:
    """NFO file presence and validity status.

    Invariant: if present is False, valid is False and IDs are None.

    Attributes:
        present: Whether the NFO file exists on disk.
        valid: Whether the NFO is parsable XML with at least one uniqueid.
        tmdb_id: TMDB ID extracted from NFO, if valid.
        imdb_id: IMDB ID extracted from NFO, if valid.
    """

    present: bool
    valid: bool
    tmdb_id: str | None
    imdb_id: str | None

    def __post_init__(self) -> None:
        """Enforce invariant: absent NFO cannot be valid or have IDs."""
        if not self.present:
            self.valid = False
            self.tmdb_id = None
            self.imdb_id = None


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
        disk: Disk name ("Disk1" through "Disk4").
        category: Disk category name (e.g. "films", "series").
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


@dataclass
class LibraryScanResult:
    """Top-level container for library_scan.json.

    Attributes:
        scanned_at: ISO 8601 timestamp of scan start.
        disk_filter: Disk filter applied (None = all disks).
        category_filter: Category filter applied (None = all).
        item_count: Total items scanned.
        items: List of scan results.
    """

    scanned_at: str
    disk_filter: str | None
    category_filter: str | None
    item_count: int
    items: list[LibraryScanItem] = field(default_factory=list)


# --- Priority constants ---

PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"


# --- Analysis models ---


@dataclass
class VideoInfo:
    """Video stream information extracted by ffprobe.

    Resolution is a computed property derived from height to prevent
    inconsistency between stored resolution and actual dimensions.

    Attributes:
        codec: Video codec name ("hevc", "h264", "av1", etc.).
        width: Frame width in pixels.
        height: Frame height in pixels.
        bitrate_kbps: Video bitrate in kbps (None if unavailable).
        hdr: Whether the video is HDR.
        hdr_type: HDR standard (only set when hdr=True).
    """

    codec: str
    width: int
    height: int
    bitrate_kbps: int | None
    hdr: bool
    hdr_type: str | None

    @property
    def resolution(self) -> str:
        """Derive resolution label from height."""
        return f"{self.height}p"


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
    """Top-level container for library_analysis.json."""

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


@dataclass
class LibraryRecommendationResult:
    """Top-level container for library_recommendations.json."""

    generated_at: str
    total_recommendations: int
    estimated_total_savings_gb: float
    items: list[Recommendation] = field(default_factory=list)


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
    return json.dumps(asdict(obj), default=_json_default, indent=2, ensure_ascii=False)


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


def read_json(path: PathLib) -> dict:
    """Read a JSON file and return parsed dict.

    Args:
        path: Path to JSON file.

    Returns:
        Parsed dictionary.
    """
    return json.loads(path.read_text(encoding="utf-8"))
