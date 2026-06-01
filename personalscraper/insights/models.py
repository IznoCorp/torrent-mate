"""Dataclasses produced and consumed by the insights layer.

Routing (DESIGN §4.6): the analysis + recommender dataclasses live here;
scan-stage types live in ``indexer.scanner._modes._item_stage``; verify
types live in ``verify.library_checks``.

This module hosts:

* The ``analyze`` health-summary dataclasses (``NfoStatusCounts``,
  ``ArtworkCounts``, ``AnalysisResult``) — formerly in ``library/analyzer``.
* The ffprobe/stream analysis dataclasses (``VideoInfo``, ``AudioTrack``,
  ``SubtitleTrack``, ``MediaFileAnalysis``, ``LibraryAnalysisItem``,
  ``LibraryAnalysisResult``) — formerly in ``library/models``.
* The recommender dataclasses (``CurrentState``, ``TargetState``,
  ``Recommendation``, ``LibraryRecommendationResult``) and the priority
  constants — formerly in ``library/models``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Priority constants (consumed by Recommendation + recommender)
# ---------------------------------------------------------------------------

PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"


# ---------------------------------------------------------------------------
# AnalysisResult — DB-query health summary (formerly library/analyzer.py)
# ---------------------------------------------------------------------------


@dataclass
class NfoStatusCounts:
    """NFO status breakdown across the whole library.

    Attributes:
        valid: Number of items whose NFO is present and valid.
        invalid: Number of items with a present but invalid NFO.
        missing: Number of items with no NFO at all.
    """

    valid: int = 0
    invalid: int = 0
    missing: int = 0


@dataclass
class ArtworkCounts:
    """Artwork presence counts across the whole library.

    Attributes:
        poster_present: Items that have a poster.
        poster_missing: Items that have no poster.
    """

    poster_present: int = 0
    poster_missing: int = 0


@dataclass
class AnalysisResult:
    """Aggregate library health metrics queried from the indexer DB.

    Produced by :func:`personalscraper.insights.analytics.analyze`.  Consumed
    by ``insights/reporter.py`` and ``maintenance/rescraper.py``.

    Attributes:
        analyzed_at: ISO 8601 timestamp of analysis.
        total_items: Total ``media_item`` rows in the DB.
        total_size_gb: Total bytes of all ``media_file`` rows, expressed in GB.
        movies_count: Items with ``kind='movie'``.
        shows_count: Items with ``kind='show'``.
        nfo: NFO status breakdown (valid / invalid / missing).
        artwork: Poster presence breakdown.
        seasons_missing_poster: Total ``season`` rows with ``has_poster=0``.
        nfo_invalid_by_category: Count of invalid-NFO items per ``category_id``.
        poster_missing_by_category: Count of poster-missing items per ``category_id``.
        items_needing_rescrape: Items with ``nfo_status != 'valid'`` or
            ``date_metadata_refreshed IS NULL`` — candidates for rescraper.
        items_per_disk: Item count per ``disk.label`` (i.e. config disk ID).
        items_per_category: Item count per ``category_id``.
        size_per_disk_gb: Total ``media_file`` bytes per disk, in GB.
        top_largest: Top 20 ``(title, size_gb)`` ordered by descending size.
        scan_issues: Count of items per directory-hygiene issue type
            (``actors_dir_present``, ``junk_files``, ``bad_dir_naming``,
            ``release_group_artifact``, ``empty_subdir``, ``ntfs_unsafe_name``).
            Populated by the indexer via the ``item_issue`` table.
        actors_dir_count: Convenience accessor — items with at least one
            ``.actors/`` directory.  Equivalent to
            ``scan_issues.get('actors_dir_present', 0)``.
    """

    analyzed_at: str = ""
    total_items: int = 0
    total_size_gb: float = 0.0
    movies_count: int = 0
    shows_count: int = 0
    nfo: NfoStatusCounts = field(default_factory=NfoStatusCounts)
    artwork: ArtworkCounts = field(default_factory=ArtworkCounts)
    seasons_missing_poster: int = 0
    nfo_invalid_by_category: dict[str, int] = field(default_factory=dict)
    poster_missing_by_category: dict[str, int] = field(default_factory=dict)
    items_needing_rescrape: int = 0
    items_per_disk: dict[str, int] = field(default_factory=dict)
    items_per_category: dict[str, int] = field(default_factory=dict)
    size_per_disk_gb: dict[str, float] = field(default_factory=dict)
    top_largest: list[tuple[str, float]] = field(default_factory=list)
    scan_issues: dict[str, int] = field(default_factory=dict)
    actors_dir_count: int = 0


# ---------------------------------------------------------------------------
# Analysis models (formerly library/models.py)
# ---------------------------------------------------------------------------


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
    """In-memory container for index-backed analysis results.

    Returned by :func:`personalscraper.insights.analytics.analyze_from_index`
    and consumed inline by ``library-recommend``.
    """

    analyzed_at: str
    disk_filter: str | None
    category_filter: str | None
    item_count: int
    file_count: int
    items: list[LibraryAnalysisItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Recommendation models (formerly library/models.py)
# ---------------------------------------------------------------------------


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
