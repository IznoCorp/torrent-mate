"""Tests for personalscraper.library.recommender — re-download recommendations."""

import pytest

from personalscraper.library.models import (
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    AudioTrack,
    LibraryAnalysisItem,
    MediaFileAnalysis,
    SubtitleTrack,
    VideoInfo,
)
from personalscraper.library.preferences import (
    EncodingRule,
    LibraryPreferences,
    RuleCriteria,
    VideoPreferences,
)
from personalscraper.library.recommender import generate_recommendations


def _make_movie(
    codec: str = "hevc",
    height: int = 1080,
    size_gb: float = 2.0,
    audio_lang: str = "fra",
    audio_profile: str = "vf",
    sub_languages: list[str] | None = None,
    title: str = "Movie",
    tmdb_id: str | None = "1",
    imdb_id: str | None = None,
) -> LibraryAnalysisItem:
    """Helper to build a movie analysis item."""
    return LibraryAnalysisItem(
        path=f"/Volumes/Disk1/medias/films/{title} (2024)",
        disk="Disk1", category="films", media_type="movie",
        title=title, year=2024,
        files=[MediaFileAnalysis(
            path=f"/Volumes/Disk1/medias/films/{title} (2024)/{title}.mkv",
            size_gb=size_gb, duration_seconds=7200,
            video=VideoInfo(codec=codec, width=int(height * 16 / 9),
                            height=height, bitrate_kbps=5000,
                            hdr=False, hdr_type=None),
            audio_tracks=[AudioTrack(codec="eac3", language=audio_lang,
                                     channels=6, is_atmos=False, is_default=True)],
            subtitle_tracks=[SubtitleTrack(language=lang, format="srt",
                                           forced=False, is_default=False)
                             for lang in (sub_languages or [])],
            audio_profile=audio_profile,
            subtitle_languages=sorted(sub_languages or []),
            analyzed_at="2026-04-15T12:00:00",
        )],
    )


class TestRecommendCodec:
    """Tests for codec-based recommendations."""

    def test_preferred_codec_no_recommendation(self) -> None:
        """Movie with preferred codec should not be recommended."""
        items = [_make_movie(codec="hevc", audio_profile="multi", sub_languages=["fra"])]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0

    def test_rejected_codec_high_priority(self) -> None:
        """Movie with rejected codec should be high priority."""
        items = [_make_movie(codec="mpeg2")]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_HIGH
        assert "rejected codec" in result.items[0].reasons[0].lower()

    def test_non_preferred_codec_medium_priority(self) -> None:
        """Movie with non-preferred, non-rejected codec should be medium."""
        items = [_make_movie(codec="h264")]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_MEDIUM

    def test_fallback_codec_no_recommendation(self) -> None:
        """Movie with fallback codec (av1) should not be recommended."""
        items = [_make_movie(codec="av1", audio_profile="multi", sub_languages=["fra"])]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0


class TestRecommendSize:
    """Tests for size-based recommendations."""

    def test_oversized_movie_medium(self) -> None:
        """Movie exceeding max_size should be medium priority."""
        items = [_make_movie(codec="hevc", size_gb=6.0)]
        prefs = LibraryPreferences(video=VideoPreferences(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_MEDIUM

    def test_very_oversized_movie_high(self) -> None:
        """Movie exceeding 2x max should be high priority."""
        items = [_make_movie(codec="hevc", size_gb=9.0)]
        prefs = LibraryPreferences(video=VideoPreferences(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.items[0].priority == PRIORITY_HIGH

    def test_savings_estimated(self) -> None:
        """Estimated savings should be current_size - max_size."""
        items = [_make_movie(codec="hevc", size_gb=6.0)]
        prefs = LibraryPreferences(video=VideoPreferences(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.items[0].estimated_savings_gb == pytest.approx(2.0, abs=0.1)


class TestRecommendAudio:
    """Tests for audio-based recommendations."""

    def test_vo_when_multi_preferred(self) -> None:
        """VO movie when multi preferred should be recommended."""
        items = [_make_movie(audio_lang="eng", audio_profile="vo")]
        prefs = LibraryPreferences()  # default: multi > vf > vostfr > vo
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert "audio" in result.items[0].reasons[0].lower()

    def test_multi_audio_no_recommendation(self) -> None:
        """MULTI movie should not be recommended for audio."""
        items = [_make_movie(audio_profile="multi", sub_languages=["fra"])]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0


class TestRecommendSubtitles:
    """Tests for subtitle-based recommendations."""

    def test_missing_required_subtitle_flagged(self) -> None:
        """Movie without required French subtitles should be recommended."""
        items = [_make_movie(audio_profile="multi", sub_languages=["eng"])]
        prefs = LibraryPreferences()  # default: required=["fra"]
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert any("subtitle" in r.lower() for r in result.items[0].reasons)


class TestEncodingRules:
    """Tests for override rule matching."""

    def test_rule_by_imdb_id(self) -> None:
        """Rule matching IMDB ID should override target."""
        items = [_make_movie(codec="hevc", imdb_id="tt4154796")]
        prefs = LibraryPreferences(encoding_rules=[
            EncodingRule(
                criteria=RuleCriteria(imdb_id="tt4154796"),
                resolution="2160p",
            ),
        ])
        id_lookup = {items[0].path: ("1", "tt4154796")}
        result = generate_recommendations(items, prefs, id_lookup=id_lookup)
        assert result.total_recommendations == 1
        assert result.items[0].target.resolution == "2160p"
        assert result.items[0].priority == PRIORITY_HIGH
        assert result.items[0].matched_rule_index == 0

    def test_rule_by_title_substring(self) -> None:
        """Rule matching title substring should apply."""
        items = [_make_movie(codec="hevc", title="Animation Movie", size_gb=3.0)]
        prefs = LibraryPreferences(encoding_rules=[
            EncodingRule(
                criteria=RuleCriteria(title="Animation"),
                max_size_gb=2.0,
            ),
        ])
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].matched_rule_index == 0


class TestDisparateSeries:
    """Tests for mixed-codec series detection."""

    def test_mixed_codec_series(self) -> None:
        """Series with mixed h264/hevc episodes should be flagged."""
        item = LibraryAnalysisItem(
            path="/tmp/Show (2024)", disk="Disk1", category="series",
            media_type="tvshow", title="Show", year=2024,
            files=[
                MediaFileAnalysis(
                    path="/tmp/Show (2024)/Saison 01/S01E01.mkv",
                    size_gb=1.0, duration_seconds=3600,
                    video=VideoInfo(codec="h264", width=1920, height=1080,
                                    bitrate_kbps=5000, hdr=False, hdr_type=None),
                    audio_tracks=[], subtitle_tracks=[],
                    audio_profile="vf", subtitle_languages=[],
                    analyzed_at="2026-04-15T12:00:00",
                ),
                MediaFileAnalysis(
                    path="/tmp/Show (2024)/Saison 01/S01E02.mkv",
                    size_gb=0.5, duration_seconds=3600,
                    video=VideoInfo(codec="hevc", width=1920, height=1080,
                                    bitrate_kbps=3000, hdr=False, hdr_type=None),
                    audio_tracks=[], subtitle_tracks=[],
                    audio_profile="vf", subtitle_languages=[],
                    analyzed_at="2026-04-15T12:00:00",
                ),
            ],
        )
        prefs = LibraryPreferences()
        result = generate_recommendations([item], prefs)
        assert result.total_recommendations == 1
        assert any("disparate" in r.lower() or "mixed" in r.lower()
                    for r in result.items[0].reasons)
