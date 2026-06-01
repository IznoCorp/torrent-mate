"""Tests for personalscraper.insights.models — analysis + recommender dataclasses."""

import pytest

from personalscraper.insights.models import (
    PRIORITY_HIGH,
    AudioTrack,
    CurrentState,
    MediaFileAnalysis,
    Recommendation,
    TargetState,
    VideoInfo,
)


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
