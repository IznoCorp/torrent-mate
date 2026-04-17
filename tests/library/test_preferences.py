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
