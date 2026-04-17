"""Tests for extract_stream_info V14 extensions — bitrate, is_atmos, forced, format, is_default."""

import json
from pathlib import Path
from unittest.mock import patch

from personalscraper.scraper.mediainfo import extract_stream_info


def _mock_ffprobe_output(
    video_bitrate: str = "5000000",
    audio_profile: str = "",
    sub_codec: str = "subrip",
    sub_forced: int = 0,
    audio_default: int = 1,
    sub_default: int = 0,
) -> str:
    """Build a realistic ffprobe JSON output with V14 fields."""
    return json.dumps({
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 1920,
                "height": 1080,
                "display_aspect_ratio": "16:9",
                "field_order": "progressive",
                "bit_rate": video_bitrate,
                "color_transfer": "bt709",
                "color_primaries": "bt709",
                "side_data_list": [],
            },
            {
                "codec_type": "audio",
                "codec_name": "eac3",
                "channels": 6,
                "tags": {"language": "fre"},
                "profile": audio_profile,
                "disposition": {"default": audio_default},
            },
            {
                "codec_type": "subtitle",
                "codec_name": sub_codec,
                "tags": {"language": "fre"},
                "disposition": {"default": sub_default, "forced": sub_forced},
            },
        ],
        "format": {"duration": "7200.000"},
    })


class TestBitrateExtraction:
    """Tests for video bitrate extraction."""

    def test_bitrate_from_stream(self, tmp_path: Path) -> None:
        """Video bitrate should be extracted from stream bit_rate."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(video_bitrate="5000000")
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result is not None
        assert result["video"]["bitrate_kbps"] == 5000

    def test_bitrate_missing_returns_none(self, tmp_path: Path) -> None:
        """Missing bit_rate should return None."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(video_bitrate="")
        # Remove bit_rate from the stream
        data = json.loads(output)
        del data["streams"][0]["bit_rate"]
        output = json.dumps(data)

        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result is not None
        assert result["video"]["bitrate_kbps"] is None


class TestAtmosDetection:
    """Tests for Dolby Atmos boolean flag."""

    def test_atmos_detected(self, tmp_path: Path) -> None:
        """Audio with Dolby Atmos profile should set is_atmos=True."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(audio_profile="Dolby Digital Plus + Dolby Atmos")
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result["audio"][0]["is_atmos"] is True
        # Underlying codec preserved (not "atmos")
        assert result["audio"][0]["codec"] == "eac3"

    def test_no_atmos(self, tmp_path: Path) -> None:
        """Regular audio should set is_atmos=False."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(audio_profile="")
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result["audio"][0]["is_atmos"] is False


class TestSubtitleExtensions:
    """Tests for subtitle format, forced, and is_default fields."""

    def test_subtitle_format_normalized(self, tmp_path: Path) -> None:
        """Subtitle codec_name should be normalized (subrip -> srt)."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(sub_codec="subrip")
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result["subtitle"][0]["format"] == "srt"

    def test_subtitle_pgs_normalized(self, tmp_path: Path) -> None:
        """hdmv_pgs_subtitle should normalize to pgs."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(sub_codec="hdmv_pgs_subtitle")
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result["subtitle"][0]["format"] == "pgs"

    def test_forced_subtitle(self, tmp_path: Path) -> None:
        """Forced subtitle flag should be extracted."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(sub_forced=1)
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result["subtitle"][0]["forced"] is True

    def test_default_flags(self, tmp_path: Path) -> None:
        """is_default should be extracted for audio and subtitle tracks."""
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"\x00")

        output = _mock_ffprobe_output(audio_default=1, sub_default=0)
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result["audio"][0]["is_default"] is True
        assert result["subtitle"][0]["is_default"] is False
