"""Data models for library maintenance commands.

Result models use @dataclass (V0-V13 convention). Path fields use str
for JSON serialization compatibility (matching IndexEntry pattern).
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
