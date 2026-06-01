"""Dataclasses and issue constants produced by the item-stage scan pass.

These types describe the lightweight library scan result shape. They live
with their producer (the item stage) rather than in a standalone models
module, per DESIGN §4.6. ``NfoStatus`` and ``ArtworkStatus`` are
cross-consumer (also read by :mod:`personalscraper.verify.library_checks`),
so they live with the producer here and the verify module imports them
from this sibling.

Kept in a sibling module (not inlined into ``_item_stage.py``) to keep that
module under the 1000-LOC hard ceiling.

Moved from the legacy library models module during lib-fold Phase 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- Issue constants for programmatic filtering ---

ISSUE_EMPTY_SUBDIR = "empty_subdir"
ISSUE_JUNK_FILES = "junk_files"
ISSUE_NTFS_UNSAFE = "ntfs_unsafe_name"
ISSUE_BAD_DIR_NAME = "bad_dir_naming"
ISSUE_ACTORS_DIR = "actors_dir_present"
ISSUE_RELEASE_ARTIFACT = "release_group_artifact"


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
