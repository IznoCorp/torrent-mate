"""Tests for personalscraper.library.analyzer — ffprobe deep scan."""

from personalscraper.library.analyzer import deduce_audio_profile


class TestDeduceAudioProfile:
    """Tests for audio profile detection logic."""

    def test_multi_two_languages(self) -> None:
        """Two different audio languages = multi."""
        tracks = [
            {"language": "fra", "is_default": True},
            {"language": "eng", "is_default": False},
        ]
        assert deduce_audio_profile(tracks, []) == "multi"

    def test_vf_single_french(self) -> None:
        """Single French audio = vf."""
        tracks = [{"language": "fra", "is_default": True}]
        assert deduce_audio_profile(tracks, []) == "vf"

    def test_vostfr_eng_audio_french_sub(self) -> None:
        """English audio + French subtitle = vostfr."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"

    def test_vostfr_japanese_audio_french_sub(self) -> None:
        """Japanese audio + French subtitle = vostfr (anime)."""
        audio = [{"language": "jpn", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"

    def test_vo_english_no_french_subs(self) -> None:
        """English audio without French subtitles = vo."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "eng"}]
        assert deduce_audio_profile(audio, subs) == "vo"

    def test_vo_no_tracks(self) -> None:
        """No audio tracks = vo (unknown)."""
        assert deduce_audio_profile([], []) == "vo"

    def test_multi_three_languages(self) -> None:
        """Three different languages = multi."""
        tracks = [
            {"language": "fra", "is_default": True},
            {"language": "eng", "is_default": False},
            {"language": "jpn", "is_default": False},
        ]
        assert deduce_audio_profile(tracks, []) == "multi"
