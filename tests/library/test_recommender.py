"""Tests for personalscraper.library.recommender — re-download recommendations."""

import pytest

from personalscraper.conf.models.preferences import (
    EncodingRule,
    LibraryPrefs,
    RuleCriteria,
    VideoPrefs,
)
from personalscraper.library.models import (
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    AudioTrack,
    LibraryAnalysisItem,
    MediaFileAnalysis,
    SubtitleTrack,
    VideoInfo,
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
        disk="Disk1",
        category="films",
        media_type="movie",
        title=title,
        year=2024,
        files=[
            MediaFileAnalysis(
                path=f"/Volumes/Disk1/medias/films/{title} (2024)/{title}.mkv",
                size_gb=size_gb,
                duration_seconds=7200,
                video=VideoInfo(
                    codec=codec, width=int(height * 16 / 9), height=height, bitrate_kbps=5000, hdr=False, hdr_type=None
                ),
                audio_tracks=[
                    AudioTrack(codec="eac3", language=audio_lang, channels=6, is_atmos=False, is_default=True)
                ],
                subtitle_tracks=[
                    SubtitleTrack(language=lang, format="srt", forced=False, is_default=False)
                    for lang in (sub_languages or [])
                ],
                audio_profile=audio_profile,
                subtitle_languages=sorted(sub_languages or []),
                analyzed_at="2026-04-15T12:00:00",
            )
        ],
    )


class TestRecommendCodec:
    """Tests for codec-based recommendations."""

    def test_preferred_codec_no_recommendation(self) -> None:
        """Movie with preferred codec should not be recommended."""
        items = [_make_movie(codec="hevc", audio_profile="multi", sub_languages=["fra"])]
        prefs = LibraryPrefs()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0

    def test_rejected_codec_high_priority(self) -> None:
        """Movie with rejected codec should be high priority."""
        items = [_make_movie(codec="mpeg2")]
        prefs = LibraryPrefs()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_HIGH
        assert "rejected codec" in result.items[0].reasons[0].lower()

    def test_non_preferred_codec_medium_priority(self) -> None:
        """Movie with non-preferred, non-rejected codec should be medium."""
        items = [_make_movie(codec="h264")]
        prefs = LibraryPrefs()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_MEDIUM

    def test_fallback_codec_no_recommendation(self) -> None:
        """Movie with fallback codec (av1) should not be recommended."""
        items = [_make_movie(codec="av1", audio_profile="multi", sub_languages=["fra"])]
        prefs = LibraryPrefs()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0


class TestRecommendSize:
    """Tests for size-based recommendations."""

    def test_oversized_movie_medium(self) -> None:
        """Movie exceeding max_size should be medium priority."""
        items = [_make_movie(codec="hevc", size_gb=6.0)]
        prefs = LibraryPrefs(video=VideoPrefs(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_MEDIUM

    def test_very_oversized_movie_high(self) -> None:
        """Movie exceeding 2x max should be high priority."""
        items = [_make_movie(codec="hevc", size_gb=9.0)]
        prefs = LibraryPrefs(video=VideoPrefs(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.items[0].priority == PRIORITY_HIGH

    def test_savings_estimated(self) -> None:
        """Estimated savings should be current_size - max_size."""
        items = [_make_movie(codec="hevc", size_gb=6.0)]
        prefs = LibraryPrefs(video=VideoPrefs(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.items[0].estimated_savings_gb == pytest.approx(2.0, abs=0.1)


class TestRecommendAudio:
    """Tests for audio-based recommendations."""

    def test_vo_when_multi_preferred(self) -> None:
        """VO movie when multi preferred should be recommended."""
        items = [_make_movie(audio_lang="eng", audio_profile="vo")]
        prefs = LibraryPrefs()  # default: multi > vf > vostfr > vo
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert "audio" in result.items[0].reasons[0].lower()

    def test_multi_audio_no_recommendation(self) -> None:
        """MULTI movie should not be recommended for audio."""
        items = [_make_movie(audio_profile="multi", sub_languages=["fra"])]
        prefs = LibraryPrefs()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0


class TestRecommendSubtitles:
    """Tests for subtitle-based recommendations."""

    def test_missing_required_subtitle_flagged(self) -> None:
        """Movie without required French subtitles should be recommended."""
        items = [_make_movie(audio_profile="multi", sub_languages=["eng"])]
        prefs = LibraryPrefs()  # default: required=["fra"]
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert any("subtitle" in r.lower() for r in result.items[0].reasons)


class TestEncodingRules:
    """Tests for override rule matching."""

    def test_rule_by_tmdb_id(self) -> None:
        """Rule matching TMDB ID should override target.

        Replaces the legacy ``test_rule_by_imdb_id`` — provider-ids
        sub-phase 10.3 dropped the ``imdb_id`` criterion (IMDb is no
        longer a primary scrape anchor under DESIGN §3).
        """
        items = [_make_movie(codec="hevc", tmdb_id="12345")]
        prefs = LibraryPrefs(
            encoding_rules=[
                EncodingRule(
                    criteria=RuleCriteria(tmdb_id="12345"),
                    resolution="2160p",
                ),
            ]
        )
        id_lookup: dict[str, tuple[str | None, str | None]] = {items[0].path: ("12345", None)}
        result = generate_recommendations(items, prefs, id_lookup=id_lookup)
        assert result.total_recommendations == 1
        assert result.items[0].target.resolution == "2160p"
        assert result.items[0].priority == PRIORITY_HIGH
        assert result.items[0].matched_rule_index == 0

    def test_rule_by_title_substring(self) -> None:
        """Rule matching title substring should apply."""
        items = [_make_movie(codec="hevc", title="Animation Movie", size_gb=3.0)]
        prefs = LibraryPrefs(
            encoding_rules=[
                EncodingRule(
                    criteria=RuleCriteria(title="Animation"),
                    max_size_gb=2.0,
                ),
            ]
        )
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].matched_rule_index == 0


class TestDisparateSeries:
    """Tests for mixed-codec series detection."""

    def test_mixed_codec_series(self) -> None:
        """Series with mixed h264/hevc episodes should be flagged."""
        item = LibraryAnalysisItem(
            path="/tmp/Show (2024)",
            disk="Disk1",
            category="series",
            media_type="tvshow",
            title="Show",
            year=2024,
            files=[
                MediaFileAnalysis(
                    path="/tmp/Show (2024)/Saison 01/S01E01.mkv",
                    size_gb=1.0,
                    duration_seconds=3600,
                    video=VideoInfo(codec="h264", width=1920, height=1080, bitrate_kbps=5000, hdr=False, hdr_type=None),
                    audio_tracks=[],
                    subtitle_tracks=[],
                    audio_profile="vf",
                    subtitle_languages=[],
                    analyzed_at="2026-04-15T12:00:00",
                ),
                MediaFileAnalysis(
                    path="/tmp/Show (2024)/Saison 01/S01E02.mkv",
                    size_gb=0.5,
                    duration_seconds=3600,
                    video=VideoInfo(codec="hevc", width=1920, height=1080, bitrate_kbps=3000, hdr=False, hdr_type=None),
                    audio_tracks=[],
                    subtitle_tracks=[],
                    audio_profile="vf",
                    subtitle_languages=[],
                    analyzed_at="2026-04-15T12:00:00",
                ),
            ],
        )
        prefs = LibraryPrefs()
        result = generate_recommendations([item], prefs)
        assert result.total_recommendations == 1
        assert any("disparate" in r.lower() or "mixed" in r.lower() for r in result.items[0].reasons)


# ---------------------------------------------------------------------------
# Branch-coverage tests for unreached corners of recommender
# ---------------------------------------------------------------------------


def _make_empty_movie(title: str = "Empty") -> LibraryAnalysisItem:
    """Return a movie analysis item with an empty ``files`` list."""
    return LibraryAnalysisItem(
        path=f"/tmp/{title}",
        disk="Disk1",
        category="films",
        media_type="movie",
        title=title,
        year=2024,
        files=[],
    )


def _make_empty_tvshow(title: str = "EmptyShow") -> LibraryAnalysisItem:
    """Return a TV show analysis item with an empty ``files`` list."""
    return LibraryAnalysisItem(
        path=f"/tmp/{title}",
        disk="Disk1",
        category="series",
        media_type="tvshow",
        title=title,
        year=2024,
        files=[],
    )


def _make_episode(
    codec: str = "hevc",
    size_gb: float = 1.0,
    audio_profile: str = "vf",
    sub_languages: list[str] | None = None,
    path: str = "/tmp/show/S01E01.mkv",
) -> MediaFileAnalysis:
    """Return a single episode MediaFileAnalysis for TV show construction."""
    return MediaFileAnalysis(
        path=path,
        size_gb=size_gb,
        duration_seconds=3600,
        video=VideoInfo(codec=codec, width=1920, height=1080, bitrate_kbps=3000, hdr=False, hdr_type=None),
        audio_tracks=[AudioTrack(codec="aac", language="fra", channels=2, is_atmos=False, is_default=True)],
        subtitle_tracks=[
            SubtitleTrack(language=lang, format="srt", forced=False, is_default=False)
            for lang in (sub_languages or ["fra"])
        ],
        audio_profile=audio_profile,
        subtitle_languages=sorted(sub_languages or ["fra"]),
        analyzed_at="2026-04-15T12:00:00",
    )


class TestEmptyFilesGuards:
    """Tests covering the early-return guards when ``item.files`` is empty."""

    def test_movie_with_no_files_returns_no_recommendation(self) -> None:
        """Empty-files movie skipped early (covers line 50)."""
        result = generate_recommendations([_make_empty_movie()], LibraryPrefs())
        assert result.total_recommendations == 0

    def test_tvshow_with_no_files_returns_no_recommendation(self) -> None:
        """Empty-files TV show skipped early (covers line 190)."""
        result = generate_recommendations([_make_empty_tvshow()], LibraryPrefs())
        assert result.total_recommendations == 0


class TestEncodingRulesExtraBranches:
    """Branches not yet exercised in the encoding-rule loop."""

    def test_rule_by_title_substring_no_id_in_lookup(self) -> None:
        """Rule matched by title substring (covers line 70 + 71 match branch)."""
        items = [_make_movie(codec="hevc", title="Special Movie")]
        prefs = LibraryPrefs(
            encoding_rules=[
                EncodingRule(
                    criteria=RuleCriteria(title="special"),
                    codec="av1",
                ),
            ]
        )
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].matched_rule_index == 0
        assert result.items[0].target.codec == "av1"

    def test_rule_with_genre_only_does_not_match(self) -> None:
        """Genre-only criteria currently ``pass`` — not enough to flag a recommendation.

        Covers lines 73-74 (the ``pass`` branch for genre criteria).
        """
        items = [_make_movie(codec="hevc", audio_profile="multi", sub_languages=["fra"])]
        prefs = LibraryPrefs(
            encoding_rules=[
                EncodingRule(
                    criteria=RuleCriteria(genre="Animation"),
                    resolution="2160p",
                ),
            ]
        )
        result = generate_recommendations(items, prefs)
        # Genre-only rule doesn't match → conforming movie stays unflagged.
        assert result.total_recommendations == 0

    def test_rule_codec_override_high_priority(self) -> None:
        """A matched rule with a different codec emits a HIGH-priority override.

        Covers lines 82-86 (the ``rule.codec`` branch inside the matched
        rule block) when the current codec differs from the rule codec.
        """
        items = [_make_movie(codec="h264", title="Action Flick")]
        prefs = LibraryPrefs(
            encoding_rules=[
                EncodingRule(
                    criteria=RuleCriteria(title="Action"),
                    codec="av1",
                ),
            ]
        )
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        rec = result.items[0]
        assert rec.matched_rule_index == 0
        assert rec.target.codec == "av1"
        assert rec.priority == PRIORITY_HIGH
        assert any("Override rule" in r and "av1" in r for r in rec.reasons)


class TestTvShowExtraBranches:
    """TV show evaluation branches missed by existing tests."""

    def test_tvshow_with_rejected_codec_high_priority(self) -> None:
        """Episodes with rejected codec emit a HIGH priority recommendation.

        Covers lines 210-211 (``rejected`` branch inside _evaluate_tvshow).
        """
        item = LibraryAnalysisItem(
            path="/tmp/Show",
            disk="Disk1",
            category="series",
            media_type="tvshow",
            title="Show",
            year=2024,
            files=[
                _make_episode(codec="mpeg2", path="/tmp/Show/S01E01.mkv"),
                _make_episode(codec="mpeg2", path="/tmp/Show/S01E02.mkv"),
            ],
        )
        result = generate_recommendations([item], LibraryPrefs())
        assert result.total_recommendations == 1
        rec = result.items[0]
        assert rec.priority == PRIORITY_HIGH
        assert any("rejected codec" in r.lower() for r in rec.reasons)

    def test_tvshow_oversized_episodes_medium_priority(self) -> None:
        """Episodes exceeding ``max_size_episode_gb`` are flagged as medium.

        Covers lines 217-218 (the ``oversized`` branch).
        """
        item = LibraryAnalysisItem(
            path="/tmp/Show",
            disk="Disk1",
            category="series",
            media_type="tvshow",
            title="Show",
            year=2024,
            files=[
                _make_episode(codec="hevc", size_gb=5.0, path="/tmp/Show/S01E01.mkv"),
                _make_episode(codec="hevc", size_gb=5.0, path="/tmp/Show/S01E02.mkv"),
            ],
        )
        prefs = LibraryPrefs(video=VideoPrefs(max_size_episode_gb=2.0))
        result = generate_recommendations([item], prefs)
        assert result.total_recommendations == 1
        rec = result.items[0]
        assert any("oversized" in r.lower() for r in rec.reasons)
        # Estimated savings positive when total > target
        assert rec.estimated_savings_gb is not None
        assert rec.estimated_savings_gb > 0

    def test_tvshow_conforming_returns_no_recommendation(self) -> None:
        """A TV show whose episodes all match preferences returns None.

        Covers line 221 (``if not reasons: return None``) inside
        ``_evaluate_tvshow``.
        """
        item = LibraryAnalysisItem(
            path="/tmp/Show",
            disk="Disk1",
            category="series",
            media_type="tvshow",
            title="Show",
            year=2024,
            files=[
                _make_episode(codec="hevc", size_gb=1.0, path="/tmp/Show/S01E01.mkv"),
                _make_episode(codec="hevc", size_gb=1.0, path="/tmp/Show/S01E02.mkv"),
            ],
        )
        result = generate_recommendations([item], LibraryPrefs())
        assert result.total_recommendations == 0


class TestAudioSubtitleSkippedBranches:
    """Branches that skip the audio/subtitle reason addition."""

    def test_unknown_audio_profile_skips_audio_reason(self) -> None:
        """``audio_profile`` outside the prefs priority list does not add an audio reason.

        Covers branch 117->124 (the ``rank > 0`` guard skipped because the
        profile is not in ``profile_priority``).
        """
        items = [_make_movie(codec="hevc", audio_profile="weird", sub_languages=["fra"])]
        prefs = LibraryPrefs()
        result = generate_recommendations(items, prefs)
        # Audio profile not in priority → no audio reason. Subs ok → no
        # subtitle reason. Codec ok → conforming.
        assert result.total_recommendations == 0

    def test_no_required_subtitles_pref_skips_subtitle_reason(self) -> None:
        """Empty ``required_languages`` skips the subtitle check (covers 124->130)."""
        from personalscraper.conf.models.preferences import SubtitlePrefs

        items = [_make_movie(codec="h264", audio_profile="multi", sub_languages=[])]
        prefs = LibraryPrefs(subtitles=SubtitlePrefs(required_languages=[]))
        result = generate_recommendations(items, prefs)
        # Codec h264 is non-preferred → recommended, but no subtitle reason.
        assert result.total_recommendations == 1
        rec = result.items[0]
        assert all("subtitle" not in r.lower() for r in rec.reasons)
