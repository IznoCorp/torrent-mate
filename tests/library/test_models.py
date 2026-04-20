"""Tests for personalscraper.library.models — library result dataclasses."""

import json

import pytest

from personalscraper.library.models import (
    ACTION_ARTWORK_DOWNLOADED,
    ACTION_EPISODES_RENAMED,
    ACTION_NFO_REGENERATED,
    ISSUE_ACTORS_DIR,
    ISSUE_EMPTY_SUBDIR,
    PRIORITY_HIGH,
    SKIP_NO_MATCH,
    ArtworkStatus,
    AudioTrack,
    CurrentState,
    LibraryRescrapeResult,
    LibraryScanItem,
    LibraryScanResult,
    MediaFileAnalysis,
    NfoStatus,
    Recommendation,
    RescrapeAction,
    SeasonInfo,
    TargetState,
    ValidationItem,
    VideoInfo,
    read_json,
    serialize_to_json,
    write_json,
)


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
        s = SeasonInfo(number=1, path="/tmp/Saison 01", episode_count=8, has_poster=True, episodes_with_nfo=6)
        assert s.number == 1
        assert s.episode_count == 8
        assert s.episodes_with_nfo == 6


class TestLibraryScanItem:
    """Tests for LibraryScanItem."""

    def test_movie_has_no_seasons(self) -> None:
        """Movie scan item should have seasons=None."""
        item = LibraryScanItem(
            path="/Volumes/Disk1/medias/films/Movie (2024)",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="Movie",
            year=2024,
            folder_size_gb=2.5,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="1", imdb_id=None),
            artwork=ArtworkStatus(poster=True, landscape=True),
            actors_dir=False,
            issues=[],
            seasons=None,
            scanned_at="2026-04-15T12:00:00",
        )
        assert item.seasons is None
        assert item.media_type == "movie"

    def test_tvshow_with_seasons(self) -> None:
        """TV show scan item should have populated seasons list."""
        item = LibraryScanItem(
            path="/Volumes/Disk1/medias/series/Show (2024)",
            disk="Disk1",
            category="series",
            media_type="tvshow",
            title="Show",
            year=2024,
            folder_size_gb=15.0,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="1", imdb_id=None),
            artwork=ArtworkStatus(poster=True),
            actors_dir=True,
            issues=[ISSUE_ACTORS_DIR, ISSUE_EMPTY_SUBDIR],
            seasons=[
                SeasonInfo(number=1, path="/tmp/Saison 01", episode_count=10, has_poster=True, episodes_with_nfo=10)
            ],
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
            disk_filter=None,
            category_filter=None,
            item_count=0,
            items=[],
        )
        assert result.item_count == 0


class TestVideoInfo:
    """Tests for VideoInfo with computed resolution."""

    def test_resolution_1080p(self) -> None:
        """1080 height should give '1080p' resolution."""
        v = VideoInfo(codec="hevc", width=1920, height=1080, bitrate_kbps=5000, hdr=False, hdr_type=None)
        assert v.resolution == "1080p"

    def test_resolution_2160p(self) -> None:
        """2160 height should give '2160p' (4K)."""
        v = VideoInfo(codec="hevc", width=3840, height=2160, bitrate_kbps=15000, hdr=True, hdr_type="hdr10")
        assert v.resolution == "2160p"

    def test_resolution_720p(self) -> None:
        """720 height should give '720p'."""
        v = VideoInfo(codec="h264", width=1280, height=720, bitrate_kbps=3000, hdr=False, hdr_type=None)
        assert v.resolution == "720p"

    def test_resolution_non_standard(self) -> None:
        """Non-standard height should still produce '{height}p'."""
        v = VideoInfo(codec="h264", width=1920, height=800, bitrate_kbps=4000, hdr=False, hdr_type=None)
        assert v.resolution == "800p"


class TestMediaFileAnalysis:
    """Tests for per-file analysis model."""

    def test_multi_audio_profile(self) -> None:
        """File with 2 languages should be 'multi'."""
        f = MediaFileAnalysis(
            path="/tmp/movie.mkv",
            size_gb=2.5,
            duration_seconds=7200,
            video=VideoInfo(codec="hevc", width=1920, height=1080, bitrate_kbps=5000, hdr=False, hdr_type=None),
            audio_tracks=[
                AudioTrack(codec="eac3", language="fra", channels=6, is_atmos=False, is_default=True),
                AudioTrack(codec="eac3", language="eng", channels=6, is_atmos=False, is_default=False),
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
            path="/tmp/movie",
            title="Movie",
            media_type="movie",
            disk="Disk1",
            category="films",
            tmdb_id="123",
            imdb_id="tt123",
            current=CurrentState(
                codec="mpeg2", resolution="1080p", size_gb=8.0, audio_profile="vf", subtitle_languages=["fra"]
            ),
            target=TargetState(codec="hevc", resolution=None, max_size_gb=4.0),
            reasons=["rejected codec mpeg2", "oversized 8.0 GB > 4.0 GB"],
            priority=PRIORITY_HIGH,
            estimated_savings_gb=4.0,
            matched_rule_index=None,
        )
        assert r.priority == PRIORITY_HIGH
        assert len(r.reasons) == 2


class TestValidationItem:
    """Tests for ValidationItem model."""

    def test_valid_item(self) -> None:
        """Item with all checks passed."""
        item = ValidationItem(
            path="/tmp/Movie (2024)",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="Movie",
            year=2024,
            status="valid",
            errors=[],
            warnings=[],
            fixes_applied=[],
        )
        assert item.status == "valid"

    def test_item_with_issues(self) -> None:
        """Item with errors should have 'issues' status."""
        item = ValidationItem(
            path="/tmp/Movie",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="Movie",
            year=None,
            status="issues",
            errors=["nfo_missing", "bad_dir_naming"],
            warnings=["no_landscape"],
            fixes_applied=[],
        )
        assert item.status == "issues"
        assert len(item.errors) == 2


class TestJsonSerialization:
    """Tests for JSON serialization helpers."""

    def test_roundtrip_scan_result(self) -> None:
        """Serialize and deserialize a scan result."""
        result = LibraryScanResult(
            scanned_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            item_count=0,
            items=[],
        )
        json_str = serialize_to_json(result)
        parsed = json.loads(json_str)
        assert parsed["scanned_at"] == "2026-04-15T12:00:00"
        assert parsed["item_count"] == 0

    def test_atomic_write_and_read(self, tmp_path) -> None:
        """Write to file atomically and read back."""
        result = LibraryScanResult(
            scanned_at="2026-04-15T12:00:00",
            disk_filter="Disk1",
            category_filter=None,
            item_count=0,
            items=[],
        )
        path = tmp_path / "test.json"
        write_json(result, path)
        assert path.exists()

        data = read_json(path)
        assert data["scanned_at"] == "2026-04-15T12:00:00"
        assert data["disk_filter"] == "Disk1"


class TestValidationItemInvariant:
    """Tests for ValidationItem.__post_init__ enforcement."""

    def test_valid_status_accepted(self) -> None:
        """Valid status values should be accepted."""
        for status in ("valid", "fixed", "issues"):
            item = ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status=status,
                errors=["err"] if status == "issues" else [],
                fixes_applied=["fix"] if status == "fixed" else [],
            )
            assert item.status == status

    def test_invalid_status_raises(self) -> None:
        """Unknown status should raise ValueError."""
        with pytest.raises(ValueError, match="status"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="blocked",
            )

    def test_fixed_without_fixes_raises(self) -> None:
        """status='fixed' with empty fixes_applied should raise."""
        with pytest.raises(ValueError, match="fixes_applied"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="fixed",
                fixes_applied=[],
            )

    def test_valid_with_errors_raises(self) -> None:
        """status='valid' with errors should raise."""
        with pytest.raises(ValueError, match="valid"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="valid",
                errors=["nfo_present"],
            )

    def test_issues_without_errors_or_warnings_raises(self) -> None:
        """status='issues' with no errors and no warnings should raise."""
        with pytest.raises(ValueError, match="issues"):
            ValidationItem(
                path="/tmp/X",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="X",
                year=2024,
                status="issues",
                errors=[],
                warnings=[],
            )

    def test_issues_with_only_warnings_accepted(self) -> None:
        """status='issues' with only warnings should be accepted."""
        item = ValidationItem(
            path="/tmp/X",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="X",
            year=2024,
            status="issues",
            errors=[],
            warnings=["no_landscape"],
        )
        assert item.status == "issues"


class TestRescrapeAction:
    """Tests for RescrapeAction model."""

    def test_valid_action(self) -> None:
        """Action with valid fields should work."""
        action = RescrapeAction(
            path="/tmp/Movie (2024)",
            title="Movie",
            media_type="movie",
            disk="Disk1",
            category="films",
            actions_taken=[ACTION_NFO_REGENERATED],
            actions_skipped=[],
            errors=[],
            tmdb_id="123",
            id_source="nfo",
            match_confidence=None,
            rescraped_at="2026-04-17T12:00:00",
        )
        assert action.tmdb_id == "123"
        assert action.id_source == "nfo"

    def test_invalid_media_type_raises(self) -> None:
        """Invalid media_type should raise ValueError."""
        with pytest.raises(ValueError, match="media_type"):
            RescrapeAction(
                path="/tmp/X",
                title="X",
                media_type="audiobook",
                disk="Disk1",
                category="films",
                actions_taken=["test"],
                actions_skipped=[],
                errors=[],
                tmdb_id=None,
                id_source=None,
                match_confidence=None,
            )

    def test_confidence_out_of_range_raises(self) -> None:
        """Confidence > 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="match_confidence"):
            RescrapeAction(
                path="/tmp/X",
                title="X",
                media_type="movie",
                disk="Disk1",
                category="films",
                actions_taken=["test"],
                actions_skipped=[],
                errors=[],
                tmdb_id="1",
                id_source="api_match",
                match_confidence=95.0,
            )

    def test_no_tmdb_clears_confidence(self) -> None:
        """If tmdb_id is None, confidence should be cleared."""
        action = RescrapeAction(
            path="/tmp/X",
            title="X",
            media_type="movie",
            disk="Disk1",
            category="films",
            actions_taken=[],
            actions_skipped=[SKIP_NO_MATCH],
            errors=[],
            tmdb_id=None,
            id_source=None,
            match_confidence=0.5,
        )
        assert action.match_confidence is None

    def test_artwork_action_constant(self) -> None:
        """ACTION_ARTWORK_DOWNLOADED and ACTION_EPISODES_RENAMED should be usable."""
        action = RescrapeAction(
            path="/tmp/X",
            title="X",
            media_type="tvshow",
            disk="Disk1",
            category="series",
            actions_taken=[ACTION_ARTWORK_DOWNLOADED, ACTION_EPISODES_RENAMED],
            actions_skipped=[],
            errors=[],
            tmdb_id="1",
            id_source="nfo",
            match_confidence=None,
        )
        assert ACTION_ARTWORK_DOWNLOADED in action.actions_taken
        assert ACTION_EPISODES_RENAMED in action.actions_taken

    def test_invalid_id_source_raises(self) -> None:
        """Invalid id_source should raise ValueError."""
        with pytest.raises(ValueError, match="id_source"):
            RescrapeAction(
                path="/tmp/X",
                title="X",
                media_type="movie",
                disk="Disk1",
                category="films",
                actions_taken=[],
                actions_skipped=[],
                errors=[],
                tmdb_id="1",
                id_source="api",
                match_confidence=0.9,
            )

    def test_none_id_source_accepted(self) -> None:
        """id_source=None should be accepted."""
        action = RescrapeAction(
            path="/tmp/X",
            title="X",
            media_type="movie",
            disk="Disk1",
            category="films",
            actions_taken=[],
            actions_skipped=[SKIP_NO_MATCH],
            errors=[],
            tmdb_id=None,
            id_source=None,
            match_confidence=None,
        )
        assert action.id_source is None


class TestLibraryRescrapeResult:
    """Tests for LibraryRescrapeResult container."""

    def test_valid_result(self) -> None:
        """Result with valid fields."""
        result = LibraryRescrapeResult(
            rescraped_at="2026-04-17T12:00:00",
            disk_filter=None,
            category_filter=None,
            only_filter=None,
            dry_run=True,
            fixed_count=0,
            skipped_count=0,
            error_count=0,
        )
        assert result.dry_run is True

    def test_invalid_only_filter_raises(self) -> None:
        """Invalid only_filter should raise ValueError."""
        with pytest.raises(ValueError, match="only_filter"):
            LibraryRescrapeResult(
                rescraped_at="2026-04-17T12:00:00",
                disk_filter=None,
                category_filter=None,
                only_filter="invalid",
                dry_run=True,
                fixed_count=0,
                skipped_count=0,
                error_count=0,
            )

    def test_valid_only_filters(self) -> None:
        """Valid only_filter values should be accepted."""
        for val in ("nfo", "artwork", "episodes"):
            result = LibraryRescrapeResult(
                rescraped_at="2026-04-17T12:00:00",
                disk_filter=None,
                category_filter=None,
                only_filter=val,
                dry_run=False,
                fixed_count=0,
                skipped_count=0,
                error_count=0,
            )
            assert result.only_filter == val
