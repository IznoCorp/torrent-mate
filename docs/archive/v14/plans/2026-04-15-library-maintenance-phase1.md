# Phase 1: Foundation — Models, Preferences, Config, Refactoring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Create the data models, preference system, and shared utilities that all 6 library commands depend on.

**Architecture:** `@dataclass` for result models (matching V0-V13 convention), pydantic `BaseModel` for preferences (config-adjacent). Refactor `_is_nfo_complete()` to a shared module. Extend `Settings` with preferences file path.

**Tech Stack:** Python, pydantic, dataclasses, pytest

---

## Task 1: Create library package and result models

**Files:**

- Create: `personalscraper/library/__init__.py`
- Create: `personalscraper/library/models.py`
- Create: `tests/library/__init__.py`
- Create: `tests/library/test_models.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p personalscraper/library tests/library
touch personalscraper/library/__init__.py tests/library/__init__.py
```

- [ ] **Step 2: Write failing tests for NfoStatus**

```python
# tests/library/test_models.py
"""Tests for personalscraper.library.models — library result dataclasses."""

from personalscraper.library.models import NfoStatus


class TestNfoStatus:
    """Tests for NfoStatus invariant enforcement."""

    def test_present_and_valid(self) -> None:
        """Valid NFO with IDs should store all fields."""
        nfo = NfoStatus(present=True, valid=True, tmdb_id="12345", imdb_id="tt999")
        assert nfo.present is True
        assert nfo.valid is True
        assert nfo.tmdb_id == "12345"
        assert nfo.imdb_id == "tt999"

    def test_absent_forces_invalid_and_no_ids(self) -> None:
        """Absent NFO must force valid=False and clear IDs."""
        nfo = NfoStatus(present=False, valid=True, tmdb_id="12345", imdb_id="tt999")
        assert nfo.present is False
        assert nfo.valid is False
        assert nfo.tmdb_id is None
        assert nfo.imdb_id is None

    def test_present_but_invalid(self) -> None:
        """Present but invalid NFO (corrupt XML) should clear IDs."""
        nfo = NfoStatus(present=True, valid=False, tmdb_id=None, imdb_id=None)
        assert nfo.present is True
        assert nfo.valid is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_models.py::TestNfoStatus -v`
Expected: FAIL — `personalscraper.library.models` does not exist

- [ ] **Step 4: Implement NfoStatus**

```python
# personalscraper/library/models.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/library/test_models.py::TestNfoStatus -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Add ArtworkStatus, SeasonInfo, issue constants, and scan models**

Add to `tests/library/test_models.py`:

```python
from personalscraper.library.models import (
    ArtworkStatus,
    LibraryScanItem,
    LibraryScanResult,
    NfoStatus,
    SeasonInfo,
    ISSUE_ACTORS_DIR,
    ISSUE_EMPTY_SUBDIR,
)


class TestArtworkStatus:
    """Tests for ArtworkStatus defaults."""

    def test_all_false_by_default(self) -> None:
        """All artwork types default to False (not present)."""
        art = ArtworkStatus()
        assert art.poster is False
        assert art.fanart is False
        assert art.landscape is False
        assert art.banner is False
        assert art.clearlogo is False
        assert art.clearart is False
        assert art.discart is False
        assert art.characterart is False


class TestSeasonInfo:
    """Tests for SeasonInfo."""

    def test_basic_season(self) -> None:
        """Season with basic info."""
        s = SeasonInfo(number=1, path="/tmp/Saison 01", episode_count=8,
                       has_poster=True, episodes_with_nfo=6)
        assert s.number == 1
        assert s.episode_count == 8
        assert s.episodes_with_nfo == 6


class TestLibraryScanItem:
    """Tests for LibraryScanItem."""

    def test_movie_has_no_seasons(self) -> None:
        """Movie scan item should have seasons=None."""
        item = LibraryScanItem(
            path="/Volumes/Disk1/medias/films/Movie (2024)",
            disk="Disk1", category="films", media_type="movie",
            title="Movie", year=2024, folder_size_gb=2.5,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="1", imdb_id=None),
            artwork=ArtworkStatus(poster=True, landscape=True),
            actors_dir=False, issues=[], seasons=None,
            scanned_at="2026-04-15T12:00:00",
        )
        assert item.seasons is None
        assert item.media_type == "movie"

    def test_tvshow_with_seasons(self) -> None:
        """TV show scan item should have populated seasons list."""
        item = LibraryScanItem(
            path="/Volumes/Disk1/medias/series/Show (2024)",
            disk="Disk1", category="series", media_type="tvshow",
            title="Show", year=2024, folder_size_gb=15.0,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="1", imdb_id=None),
            artwork=ArtworkStatus(poster=True),
            actors_dir=True,
            issues=[ISSUE_ACTORS_DIR, ISSUE_EMPTY_SUBDIR],
            seasons=[SeasonInfo(number=1, path="/tmp/Saison 01",
                                episode_count=10, has_poster=True,
                                episodes_with_nfo=10)],
            scanned_at="2026-04-15T12:00:00",
        )
        assert len(item.seasons) == 1
        assert ISSUE_ACTORS_DIR in item.issues


class TestLibraryScanResult:
    """Tests for LibraryScanResult container."""

    def test_empty_result(self) -> None:
        """Empty scan result."""
        result = LibraryScanResult(
            scanned_at="2026-04-15T12:00:00",
            disk_filter=None, category_filter=None,
            item_count=0, items=[],
        )
        assert result.item_count == 0
```

- [ ] **Step 7: Implement remaining scan models**

Add to `personalscraper/library/models.py`:

```python
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
```

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/library/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add personalscraper/library/ tests/library/
git commit -m "v14.1.1: Add library scan result models (@dataclass)"
```

---

## Task 2: Add analysis and recommendation models

**Files:**

- Modify: `personalscraper/library/models.py`
- Modify: `tests/library/test_models.py`

- [ ] **Step 1: Write failing tests for analysis models**

Add to `tests/library/test_models.py`:

```python
from personalscraper.library.models import (
    AudioTrack,
    CurrentState,
    LibraryAnalysisItem,
    LibraryAnalysisResult,
    LibraryRecommendationResult,
    MediaFileAnalysis,
    Recommendation,
    SubtitleTrack,
    TargetState,
    VideoInfo,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_LOW,
)
import pytest


class TestVideoInfo:
    """Tests for VideoInfo with computed resolution."""

    def test_resolution_1080p(self) -> None:
        """1080 height should give '1080p' resolution."""
        v = VideoInfo(codec="hevc", width=1920, height=1080,
                      bitrate_kbps=5000, hdr=False, hdr_type=None)
        assert v.resolution == "1080p"

    def test_resolution_2160p(self) -> None:
        """2160 height should give '2160p' (4K)."""
        v = VideoInfo(codec="hevc", width=3840, height=2160,
                      bitrate_kbps=15000, hdr=True, hdr_type="hdr10")
        assert v.resolution == "2160p"

    def test_resolution_720p(self) -> None:
        """720 height should give '720p'."""
        v = VideoInfo(codec="h264", width=1280, height=720,
                      bitrate_kbps=3000, hdr=False, hdr_type=None)
        assert v.resolution == "720p"

    def test_resolution_non_standard(self) -> None:
        """Non-standard height should still produce '{height}p'."""
        v = VideoInfo(codec="h264", width=1920, height=800,
                      bitrate_kbps=4000, hdr=False, hdr_type=None)
        assert v.resolution == "800p"


class TestMediaFileAnalysis:
    """Tests for per-file analysis model."""

    def test_multi_audio_profile(self) -> None:
        """File with 2 languages should be 'multi'."""
        f = MediaFileAnalysis(
            path="/tmp/movie.mkv", size_gb=2.5, duration_seconds=7200,
            video=VideoInfo(codec="hevc", width=1920, height=1080,
                            bitrate_kbps=5000, hdr=False, hdr_type=None),
            audio_tracks=[
                AudioTrack(codec="eac3", language="fra", channels=6,
                           is_atmos=False, is_default=True),
                AudioTrack(codec="eac3", language="eng", channels=6,
                           is_atmos=False, is_default=False),
            ],
            subtitle_tracks=[],
            audio_profile="multi",
            subtitle_languages=["eng", "fra"],
            analyzed_at="2026-04-15T12:00:00",
        )
        assert f.audio_profile == "multi"
        assert f.subtitle_languages == ["eng", "fra"]


class TestTargetState:
    """Tests for TargetState validation."""

    def test_all_none_raises(self) -> None:
        """TargetState with all None fields should raise ValueError."""
        with pytest.raises(ValueError, match="at least one non-None"):
            TargetState(codec=None, resolution=None, max_size_gb=None)

    def test_valid_target(self) -> None:
        """TargetState with at least one field set should work."""
        t = TargetState(codec="hevc", resolution=None, max_size_gb=None)
        assert t.codec == "hevc"


class TestRecommendation:
    """Tests for Recommendation model."""

    def test_high_priority(self) -> None:
        """High priority recommendation."""
        r = Recommendation(
            path="/tmp/movie", title="Movie", media_type="movie",
            disk="Disk1", category="films",
            tmdb_id="123", imdb_id="tt123",
            current=CurrentState(codec="mpeg2", resolution="1080p",
                                 size_gb=8.0, audio_profile="vf",
                                 subtitle_languages=["fra"]),
            target=TargetState(codec="hevc", resolution=None, max_size_gb=4.0),
            reasons=["rejected codec mpeg2", "oversized 8.0 GB > 4.0 GB"],
            priority=PRIORITY_HIGH,
            estimated_savings_gb=4.0,
            matched_rule_index=None,
        )
        assert r.priority == PRIORITY_HIGH
        assert len(r.reasons) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_models.py -k "VideoInfo or MediaFile or TargetState or Recommendation" -v`
Expected: FAIL — classes not yet defined

- [ ] **Step 3: Implement analysis and recommendation models**

Add to `personalscraper/library/models.py`:

```python
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
```

- [ ] **Step 4: Run all model tests**

Run: `python -m pytest tests/library/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/models.py tests/library/test_models.py
git commit -m "v14.1.2: Add analysis and recommendation models"
```

---

## Task 3: Create preferences models

**Files:**

- Create: `personalscraper/library/preferences.py`
- Create: `tests/library/test_preferences.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_preferences.py
"""Tests for personalscraper.library.preferences — pydantic config models."""

import json

import pytest

from personalscraper.library.preferences import (
    AudioPreferences,
    EncodingRule,
    LibraryPreferences,
    RuleCriteria,
    SubtitlePreferences,
    VideoPreferences,
)


class TestVideoPreferences:
    """Tests for VideoPreferences validation."""

    def test_defaults(self) -> None:
        """Default preferences should be sensible."""
        v = VideoPreferences()
        assert v.preferred_codec == "hevc"
        assert v.preferred_resolution == "1080p"
        assert v.max_size_movie_gb == 4.0

    def test_disjoint_codecs_valid(self) -> None:
        """Non-overlapping codec sets should pass."""
        v = VideoPreferences(
            preferred_codec="hevc",
            fallback_codecs=["av1"],
            rejected_codecs=["mpeg2"],
        )
        assert v.preferred_codec == "hevc"

    def test_preferred_in_rejected_raises(self) -> None:
        """Preferred codec in rejected set should fail validation."""
        with pytest.raises(ValueError, match="overlap"):
            VideoPreferences(
                preferred_codec="hevc",
                fallback_codecs=[],
                rejected_codecs=["hevc", "mpeg2"],
            )

    def test_fallback_in_rejected_raises(self) -> None:
        """Fallback codec in rejected set should fail validation."""
        with pytest.raises(ValueError, match="overlap"):
            VideoPreferences(
                preferred_codec="hevc",
                fallback_codecs=["av1"],
                rejected_codecs=["av1"],
            )


class TestAudioPreferences:
    """Tests for AudioPreferences."""

    def test_defaults(self) -> None:
        """Default audio profile priority."""
        a = AudioPreferences()
        assert a.profile_priority == ["multi", "vf", "vostfr", "vo"]

    def test_min_channels_positive(self) -> None:
        """min_channels must be >= 1."""
        with pytest.raises(ValueError):
            AudioPreferences(min_channels=0)


class TestSubtitlePreferences:
    """Tests for SubtitlePreferences validation."""

    def test_defaults_use_639_2_t(self) -> None:
        """Default languages should be ISO 639-2/T (fra, not fre)."""
        s = SubtitlePreferences()
        assert s.required_languages == ["fra"]
        assert "fra" in s.preferred_languages

    def test_required_subset_of_preferred(self) -> None:
        """Required languages must be a subset of preferred."""
        with pytest.raises(ValueError, match="subset"):
            SubtitlePreferences(
                required_languages=["jpn"],
                preferred_languages=["fra", "eng"],
            )


class TestRuleCriteria:
    """Tests for RuleCriteria."""

    def test_valid_criteria(self) -> None:
        """Criteria with at least one field set."""
        c = RuleCriteria(genre="Animation")
        assert c.genre == "Animation"
        assert c.title is None

    def test_all_none_raises(self) -> None:
        """Criteria with all None fields should fail."""
        with pytest.raises(ValueError, match="at least one"):
            RuleCriteria()


class TestEncodingRule:
    """Tests for EncodingRule."""

    def test_valid_rule(self) -> None:
        """Rule with criteria and at least one target."""
        r = EncodingRule(
            criteria=RuleCriteria(imdb_id="tt4154796"),
            resolution="2160p",
        )
        assert r.resolution == "2160p"
        assert r.codec is None

    def test_no_target_raises(self) -> None:
        """Rule with no resolution/codec/max_size should fail."""
        with pytest.raises(ValueError, match="at least one"):
            EncodingRule(criteria=RuleCriteria(genre="Action"))


class TestLibraryPreferences:
    """Tests for full preferences loading."""

    def test_defaults(self) -> None:
        """Default preferences should be valid."""
        p = LibraryPreferences()
        assert p.video.preferred_codec == "hevc"
        assert p.audio.profile_priority[0] == "multi"
        assert p.subtitles.required_languages == ["fra"]

    def test_from_json(self, tmp_path) -> None:
        """Preferences should load from a JSON file."""
        data = {
            "video": {"preferred_codec": "av1", "max_size_movie_gb": 3.0},
            "audio": {"profile_priority": ["vf", "multi"]},
            "subtitles": {"required_languages": ["fra"]},
            "encoding_rules": [
                {
                    "criteria": {"imdb_id": "tt4154796"},
                    "resolution": "2160p",
                }
            ],
        }
        json_file = tmp_path / "prefs.json"
        json_file.write_text(json.dumps(data))

        p = LibraryPreferences.model_validate_json(json_file.read_text())
        assert p.video.preferred_codec == "av1"
        assert p.video.max_size_movie_gb == 3.0
        assert len(p.encoding_rules) == 1
        assert p.encoding_rules[0].criteria.imdb_id == "tt4154796"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_preferences.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement preferences models**

```python
# personalscraper/library/preferences.py
"""Pydantic models for library maintenance preferences.

Loaded from a JSON file (library_preferences.json in .personalscraper/).
Uses pydantic BaseModel (not @dataclass) because these are user-facing
configuration that benefits from validation.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class VideoPreferences(BaseModel):
    """Video encoding preferences.

    Attributes:
        preferred_codec: Target codec for recommendations.
        fallback_codecs: Acceptable codecs (not flagged).
        rejected_codecs: Always-flagged codecs.
        preferred_resolution: Target resolution label.
        max_size_movie_gb: Maximum movie file size in GB.
        max_size_episode_gb: Maximum episode file size in GB.
    """

    preferred_codec: str = "hevc"
    fallback_codecs: list[str] = Field(default_factory=lambda: ["av1"])
    rejected_codecs: list[str] = Field(default_factory=lambda: ["mpeg2", "mpeg4"])
    preferred_resolution: str = "1080p"
    max_size_movie_gb: float = 4.0
    max_size_episode_gb: float = 2.0

    @model_validator(mode="after")
    def codecs_are_disjoint(self) -> Self:
        """Ensure preferred, fallback, and rejected codec sets don't overlap."""
        all_codecs = {self.preferred_codec} | set(self.fallback_codecs)
        rejected = set(self.rejected_codecs)
        overlap = all_codecs & rejected
        if overlap:
            msg = f"Codec sets overlap: {overlap}"
            raise ValueError(msg)
        return self


class AudioPreferences(BaseModel):
    """Audio track preferences.

    Attributes:
        profile_priority: Ordered preference for audio profiles.
        min_channels: Minimum channel count (flags mono as suspect).
        preferred_codec: Preferred audio codec (None = no preference).
    """

    profile_priority: list[str] = Field(
        default_factory=lambda: ["multi", "vf", "vostfr", "vo"],
    )
    min_channels: int = Field(default=2, ge=1)
    preferred_codec: str | None = None


class SubtitlePreferences(BaseModel):
    """Subtitle track preferences.

    Language codes use ISO 639-2/T (fra, eng, jpn — NOT fre).

    Attributes:
        required_languages: Languages that must be present (ERROR if missing).
        preferred_languages: Languages that should be present (WARNING if missing).
        warn_if_missing: Whether missing subtitles produce warnings.
    """

    required_languages: list[str] = Field(default_factory=lambda: ["fra"])
    preferred_languages: list[str] = Field(default_factory=lambda: ["fra", "eng"])
    warn_if_missing: bool = True

    @model_validator(mode="after")
    def required_subset_of_preferred(self) -> Self:
        """Ensure required_languages is a subset of preferred_languages."""
        required = set(self.required_languages)
        preferred = set(self.preferred_languages)
        if not required.issubset(preferred):
            diff = required - preferred
            msg = f"required_languages must be a subset of preferred_languages, extra: {diff}"
            raise ValueError(msg)
        return self


class RuleCriteria(BaseModel):
    """Structured criteria for encoding override rules.

    String fields use case-insensitive substring matching.
    ID fields use exact matching.
    At least one field must be non-None.

    Attributes:
        genre: Genre substring to match (e.g. "Animation").
        title: Title substring to match.
        imdb_id: Exact IMDB ID (e.g. "tt4154796").
        tmdb_id: Exact TMDB ID (e.g. "12345").
    """

    genre: str | None = None
    title: str | None = None
    imdb_id: str | None = None
    tmdb_id: str | None = None

    @model_validator(mode="after")
    def has_at_least_one_criterion(self) -> Self:
        """At least one criterion must be set."""
        if all(v is None for v in (self.genre, self.title, self.imdb_id, self.tmdb_id)):
            msg = "RuleCriteria must have at least one non-None field"
            raise ValueError(msg)
        return self


class EncodingRule(BaseModel):
    """Override rule for specific media matching criteria.

    Attributes:
        criteria: What to match against.
        resolution: Override resolution (None = no override).
        codec: Override codec (None = no override).
        max_size_gb: Override max size in GB (None = no override).
    """

    criteria: RuleCriteria
    resolution: str | None = None
    codec: str | None = None
    max_size_gb: float | None = None

    @model_validator(mode="after")
    def has_at_least_one_target(self) -> Self:
        """At least one of resolution, codec, max_size_gb must be set."""
        if self.resolution is None and self.codec is None and self.max_size_gb is None:
            msg = "EncodingRule must have at least one target (resolution, codec, or max_size_gb)"
            raise ValueError(msg)
        return self


class LibraryPreferences(BaseModel):
    """Root preferences model for library maintenance.

    Loaded from library_preferences.json in .personalscraper/.

    Attributes:
        video: Video encoding preferences.
        audio: Audio track preferences.
        subtitles: Subtitle track preferences.
        encoding_rules: Override rules for specific media.
    """

    video: VideoPreferences = Field(default_factory=VideoPreferences)
    audio: AudioPreferences = Field(default_factory=AudioPreferences)
    subtitles: SubtitlePreferences = Field(default_factory=SubtitlePreferences)
    encoding_rules: list[EncodingRule] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_preferences.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest tests/ -x -q`
Expected: All pass, 0 regressions

- [ ] **Step 6: Commit**

```bash
git add personalscraper/library/preferences.py tests/library/test_preferences.py
git commit -m "v14.1.3: Add library preferences models (pydantic)"
```

---

## Task 4: Extend Settings with library_preferences_file

**Files:**

- Modify: `personalscraper/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_config.py`:

```python
def test_library_preferences_file_default(monkeypatch):
    """library_preferences_file should default to 'library_preferences.json'."""
    # Provide minimum required env vars
    monkeypatch.setenv("STAGING_DIR", "/tmp/staging")
    from personalscraper.config import Settings
    settings = Settings(_env_file=None)
    assert settings.library_preferences_file == "library_preferences.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py::test_library_preferences_file_default -v`
Expected: FAIL — `Settings` has no attribute `library_preferences_file`

- [ ] **Step 3: Add field to Settings**

In `personalscraper/config.py`, add after the `data_dir_name` field (around line 102):

```python
    # Library maintenance preferences
    library_preferences_file: str = "library_preferences.json"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py::test_library_preferences_file_default -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/config.py tests/test_config.py
git commit -m "v14.1.4: Add library_preferences_file to Settings"
```

---

## Task 5: Refactor \_is_nfo_complete to shared module

**Files:**

- Create: `personalscraper/nfo_utils.py`
- Modify: `personalscraper/scraper/scraper.py`
- Modify: `tests/scraper/test_scraper.py` (if imports change)

- [ ] **Step 1: Write test for new shared module**

```python
# tests/test_nfo_utils.py
"""Tests for personalscraper.nfo_utils — shared NFO validation."""

from pathlib import Path

from personalscraper.nfo_utils import is_nfo_complete


class TestIsNfoComplete:
    """Tests for is_nfo_complete shared function."""

    def test_valid_nfo(self, tmp_path: Path) -> None:
        """NFO with uniqueid should be complete."""
        nfo = tmp_path / "movie.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb">123</uniqueid></movie>')
        assert is_nfo_complete(nfo) is True

    def test_missing_nfo(self, tmp_path: Path) -> None:
        """Non-existent NFO should be incomplete."""
        assert is_nfo_complete(tmp_path / "missing.nfo") is False

    def test_empty_nfo(self, tmp_path: Path) -> None:
        """Empty file should be incomplete."""
        nfo = tmp_path / "empty.nfo"
        nfo.write_text("")
        assert is_nfo_complete(nfo) is False

    def test_no_uniqueid(self, tmp_path: Path) -> None:
        """NFO without uniqueid should be incomplete."""
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<movie><title>Test</title></movie>")
        assert is_nfo_complete(nfo) is False

    def test_corrupt_xml(self, tmp_path: Path) -> None:
        """Non-parsable XML should be incomplete."""
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<movie><title>broken")
        assert is_nfo_complete(nfo) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_nfo_utils.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Create nfo_utils.py with the function**

```python
# personalscraper/nfo_utils.py
"""Shared NFO file validation utilities.

Provides is_nfo_complete() for checking NFO validity across the
pipeline (scraper, library scanner, verify). Moved from
scraper/scraper.py to enable cross-module access.
"""

from pathlib import Path
from xml.etree import ElementTree as ET


def is_nfo_complete(nfo_path: Path) -> bool:
    """Check if an NFO file is complete and valid.

    A complete NFO must:
    1. Exist on disk
    2. Be parsable as XML
    3. Contain at least one <uniqueid> element with non-empty text

    Used to distinguish valid NFOs from crash-truncated or incomplete
    ones that should be re-scraped.

    Args:
        nfo_path: Path to the .nfo file.

    Returns:
        True if the NFO is complete and valid.
    """
    if not nfo_path.exists():
        return False
    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        root = tree.getroot()
        for uid in root.iter("uniqueid"):
            if uid.text and uid.text.strip():
                return True
        return False
    except ET.ParseError:
        return False
    except OSError:
        return False
```

- [ ] **Step 4: Run new tests**

Run: `python -m pytest tests/test_nfo_utils.py -v`
Expected: ALL PASS (5 tests)

- [ ] **Step 5: Update scraper.py to import from shared module**

In `personalscraper/scraper/scraper.py`, replace the `_is_nfo_complete` function (around line 100-130) with an import:

```python
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
```

Remove the old function body. Keep the local alias `_is_nfo_complete` so all internal references remain unchanged.

- [ ] **Step 6: Run scraper tests to verify no regressions**

Run: `python -m pytest tests/scraper/ -x -q`
Expected: All pass

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add personalscraper/nfo_utils.py personalscraper/scraper/scraper.py tests/test_nfo_utils.py
git commit -m "v14.1.5: Extract is_nfo_complete to shared nfo_utils module"
```

---

## Task 6: Add JSON serialization helper

**Files:**

- Modify: `personalscraper/library/models.py`
- Modify: `tests/library/test_models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/library/test_models.py`:

```python
import json

from personalscraper.library.models import (
    LibraryScanResult,
    serialize_to_json,
    deserialize_scan_result,
)


class TestJsonSerialization:
    """Tests for JSON serialization helpers."""

    def test_roundtrip_scan_result(self) -> None:
        """Serialize and deserialize a scan result."""
        result = LibraryScanResult(
            scanned_at="2026-04-15T12:00:00",
            disk_filter=None, category_filter=None,
            item_count=0, items=[],
        )
        json_str = serialize_to_json(result)
        parsed = json.loads(json_str)
        assert parsed["scanned_at"] == "2026-04-15T12:00:00"
        assert parsed["item_count"] == 0

    def test_atomic_write_and_read(self, tmp_path) -> None:
        """Write to file atomically and read back."""
        from personalscraper.library.models import write_json, read_json
        result = LibraryScanResult(
            scanned_at="2026-04-15T12:00:00",
            disk_filter="Disk1", category_filter=None,
            item_count=0, items=[],
        )
        path = tmp_path / "test.json"
        write_json(result, path)
        assert path.exists()

        data = read_json(path)
        assert data["scanned_at"] == "2026-04-15T12:00:00"
        assert data["disk_filter"] == "Disk1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/library/test_models.py::TestJsonSerialization -v`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement serialization helpers**

Add to `personalscraper/library/models.py`:

```python
import json
from pathlib import Path as PathLib


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
    from dataclasses import asdict
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_models.py::TestJsonSerialization -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/library/models.py tests/library/test_models.py
git commit -m "v14.1.6: Add JSON serialization helpers (atomic write, Path-safe)"
```

---

## Acceptance Criteria — Phase 1

Before moving to Phase 2, verify:

- [ ] `personalscraper/library/` package exists with `models.py` and `preferences.py`
- [ ] All scan, analysis, and recommendation dataclasses are defined with proper invariants
- [ ] `LibraryPreferences` loads from JSON with full validation
- [ ] `Settings.library_preferences_file` is available
- [ ] `is_nfo_complete()` lives in `nfo_utils.py` (shared)
- [ ] Scraper tests still pass after refactoring
- [ ] JSON serialization helpers work with atomic writes
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
