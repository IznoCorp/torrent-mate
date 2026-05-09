"""Tests for personalscraper.scraper.mediainfo — ffprobe stream extraction."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.scraper.mediainfo import (
    ISO_639_2_B_TO_T,
    _lang_to_kodi,
    _map_audio_codec,
    _map_video_codec,
    _parse_aspect_ratio,
    extract_stream_info,
)

# --- Helper: mock ffprobe output ---


def _mock_ffprobe_output(
    video_codec="hevc",
    width=1920,
    height=1080,
    dar="16:9",
    audio_codec="eac3",
    audio_profile="",
    audio_channels=6,
    audio_lang="fre",
    subtitle_lang="fre",
    duration="7627.5",
    field_order="progressive",
    color_transfer="",
):
    """Build a mock ffprobe JSON output."""
    data = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": video_codec,
                "width": width,
                "height": height,
                "display_aspect_ratio": dar,
                "field_order": field_order,
                "color_transfer": color_transfer,
                "disposition": {"attached_pic": 0},
            },
            {
                "codec_type": "audio",
                "codec_name": audio_codec,
                "profile": audio_profile,
                "channels": audio_channels,
                "tags": {"language": audio_lang},
            },
            {
                "codec_type": "subtitle",
                "tags": {"language": subtitle_lang},
            },
        ],
        "format": {"duration": duration},
    }
    return json.dumps(data)


def _mock_run(stdout, returncode=0):
    """Create a mock subprocess.run result."""
    result = subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")
    return result


# --- Language mapping ---


class TestLangToKodi:
    """ISO 639-2/B to 639-2/T conversion."""

    @pytest.mark.parametrize(
        "b_code,t_code",
        [
            ("fre", "fra"),
            ("ger", "deu"),
            ("dut", "nld"),
            ("chi", "zho"),
        ],
    )
    def test_codes_that_differ(self, b_code, t_code):
        """Codes that differ between B and T are converted."""
        assert _lang_to_kodi(b_code) == t_code

    @pytest.mark.parametrize("code", ["eng", "spa", "ita", "por", "jpn", "kor"])
    def test_codes_that_match(self, code):
        """Codes identical in both standards pass through unchanged."""
        assert _lang_to_kodi(code) == code

    def test_unknown_code_passes_through(self):
        """Unknown codes pass through unchanged."""
        assert _lang_to_kodi("xyz") == "xyz"

    def test_mapping_has_20_entries(self):
        """The mapping table has exactly 20 entries."""
        assert len(ISO_639_2_B_TO_T) == 20


# --- Codec mapping ---


class TestMapVideoCodec:
    """Video codec name mapping."""

    def test_mpeg2video_to_mpeg2(self):
        """mpeg2video maps to mpeg2."""
        assert _map_video_codec("mpeg2video") == "mpeg2"

    def test_hevc_passthrough(self):
        """Unknown codecs pass through."""
        assert _map_video_codec("hevc") == "hevc"


class TestMapAudioCodec:
    """Audio codec mapping with Atmos detection."""

    def test_atmos_detection(self):
        """EAC3 with Atmos profile returns 'atmos' for Kodi NFO compat."""
        assert _map_audio_codec("eac3", "Dolby Digital Plus + Dolby Atmos") == "atmos"

    def test_dts_hd_ma(self):
        """DTS with DTS-HD MA profile."""
        assert _map_audio_codec("dts", "DTS-HD MA") == "dtshd_ma"

    def test_plain_eac3(self):
        """Plain EAC3 without Atmos."""
        assert _map_audio_codec("eac3", "") == "eac3"

    def test_plain_aac(self):
        """AAC passthrough."""
        assert _map_audio_codec("aac") == "aac"


# --- Aspect ratio ---


class TestParseAspectRatio:
    """Aspect ratio conversion."""

    def test_16_9(self):
        """16:9 converts to 1.778."""
        assert _parse_aspect_ratio("16:9", 1920, 1080) == 1.778

    def test_4_3(self):
        """4:3 converts to 1.333."""
        assert _parse_aspect_ratio("4:3", 720, 480) == 1.333

    def test_fallback_to_dimensions(self):
        """Falls back to width/height when DAR is None."""
        assert _parse_aspect_ratio(None, 1920, 1080) == 1.778

    def test_zero_height(self):
        """Returns 0.0 for zero dimensions."""
        assert _parse_aspect_ratio(None, 0, 0) == 0.0


# --- extract_stream_info with mocked subprocess ---


class TestExtractStreamInfo:
    """extract_stream_info() — main function with mocked ffprobe."""

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_basic_extraction(self, mock_run):
        """Extracts video, audio, subtitle, and duration."""
        mock_run.return_value = _mock_run(_mock_ffprobe_output())
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None

        assert info is not None
        assert info["duration_seconds"] == 7628  # round(7627.5)
        assert info["video"]["codec"] == "hevc"
        assert info["video"]["width"] == 1920
        assert info["video"]["height"] == 1080
        assert info["video"]["aspect"] == 1.778
        assert info["video"]["scantype"] == "progressive"
        assert len(info["audio"]) == 1
        assert info["audio"][0]["codec"] == "eac3"
        assert info["audio"][0]["language"] == "fra"  # fre -> fra
        assert len(info["subtitle"]) == 1
        assert info["subtitle"][0]["language"] == "fra"

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_atmos_detected(self, mock_run):
        """Detects Dolby Atmos: codec='atmos' for NFO, is_atmos=True for analysis."""
        mock_run.return_value = _mock_run(_mock_ffprobe_output(audio_profile="Dolby Digital Plus + Dolby Atmos"))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["audio"][0]["codec"] == "atmos"
        assert info["audio"][0]["is_atmos"] is True

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_hdr10_detected(self, mock_run):
        """Detects HDR10 via color_transfer."""
        mock_run.return_value = _mock_run(_mock_ffprobe_output(color_transfer="smpte2084"))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["video"]["hdr"]["is_hdr"] is True
        assert info["video"]["hdr"]["hdr_type"] == "hdr10"

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_sdr_no_hdr(self, mock_run):
        """SDR content has no HDR info."""
        mock_run.return_value = _mock_run(_mock_ffprobe_output())
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["video"]["hdr"]["is_hdr"] is False

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_interlaced_detected(self, mock_run):
        """Interlaced content detected via field_order."""
        mock_run.return_value = _mock_run(_mock_ffprobe_output(field_order="tt"))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["video"]["scantype"] == "interlaced"


# --- Graceful fallbacks ---


class TestGracefulFallbacks:
    """Graceful error handling when ffprobe fails."""

    @patch("personalscraper.scraper.mediainfo.subprocess.run", side_effect=FileNotFoundError)
    def test_ffprobe_not_installed(self, mock_run):
        """Returns None if ffprobe is not found."""
        assert extract_stream_info(Path("test.mkv")) is None

    @patch(
        "personalscraper.scraper.mediainfo.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=30),
    )
    def test_ffprobe_timeout(self, mock_run):
        """Returns None on timeout."""
        assert extract_stream_info(Path("test.mkv")) is None

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_ffprobe_nonzero_exit(self, mock_run):
        """Returns None on non-zero exit code."""
        mock_run.return_value = _mock_run("", returncode=1)
        assert extract_stream_info(Path("test.mkv")) is None

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_invalid_json(self, mock_run):
        """Returns None on invalid JSON output."""
        mock_run.return_value = _mock_run("not json")
        assert extract_stream_info(Path("test.mkv")) is None

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_no_streams(self, mock_run):
        """Returns None when ffprobe reports no streams."""
        mock_run.return_value = _mock_run(json.dumps({"streams": [], "format": {}}))
        assert extract_stream_info(Path("test.mkv")) is None

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_no_video_stream(self, mock_run):
        """Returns None when only audio/subtitle streams exist."""
        data = {
            "streams": [
                {"codec_type": "audio", "codec_name": "aac", "channels": 2, "tags": {"language": "eng"}},
            ],
            "format": {"duration": "100"},
        }
        mock_run.return_value = _mock_run(json.dumps(data))
        assert extract_stream_info(Path("test.mkv")) is None


# --- Additional codec / aspect / HDR / duration edge branches ---


class TestAudioCodecExtras:
    """Edge branches for _map_audio_codec."""

    def test_dts_hd_hra(self):
        """DTS with DTS-HD HRA profile maps to dtshd_hra."""
        assert _map_audio_codec("dts", "DTS-HD HRA") == "dtshd_hra"

    def test_dts_hd_hr(self):
        """DTS with DTS-HD HR profile also maps to dtshd_hra."""
        assert _map_audio_codec("dts", "DTS-HD HR") == "dtshd_hra"

    def test_plain_dts_with_other_profile(self):
        """DTS codec with a non-HD profile passes through unchanged."""
        assert _map_audio_codec("dts", "DTS Core") == "dts"


class TestParseAspectRatioErrors:
    """Edge branches for _parse_aspect_ratio."""

    def test_division_by_zero_falls_back(self):
        """ZeroDivisionError on '16:0' falls back to width/height."""
        assert _parse_aspect_ratio("16:0", 1920, 1080) == 1.778

    def test_invalid_dar_string_falls_back(self):
        """Invalid (non-int) DAR string falls back to width/height."""
        assert _parse_aspect_ratio("a:b", 1920, 1080) == 1.778


class TestExtractStreamInfoBranches:
    """Branch coverage: attached_pic, HDR variants, malformed duration."""

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_invalid_duration_falls_back_to_zero(self, mock_run):
        """Non-numeric duration string yields duration_seconds=0."""
        data = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "display_aspect_ratio": "16:9",
                    "field_order": "progressive",
                    "color_transfer": "",
                    "disposition": {"attached_pic": 0},
                },
            ],
            "format": {"duration": "not-a-number"},
        }
        mock_run.return_value = _mock_run(json.dumps(data))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["duration_seconds"] == 0

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_attached_pic_skipped(self, mock_run):
        """Attached cover-art video streams are skipped; second real video stream wins."""
        data = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "mjpeg",
                    "width": 600,
                    "height": 900,
                    "display_aspect_ratio": "2:3",
                    "field_order": "progressive",
                    "color_transfer": "",
                    "disposition": {"attached_pic": 1},
                },
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "display_aspect_ratio": "16:9",
                    "field_order": "progressive",
                    "color_transfer": "",
                    "disposition": {"attached_pic": 0},
                },
            ],
            "format": {"duration": "120"},
        }
        mock_run.return_value = _mock_run(json.dumps(data))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["video"]["codec"] == "h264"
        assert info["video"]["width"] == 1920

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_dolby_vision_detected(self, mock_run):
        """smpte2084 + DOVI configuration record side data → dolby_vision."""
        data = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 3840,
                    "height": 2160,
                    "display_aspect_ratio": "16:9",
                    "field_order": "progressive",
                    "color_transfer": "smpte2084",
                    "side_data_list": [{"side_data_type": "DOVI configuration record"}],
                    "disposition": {"attached_pic": 0},
                },
            ],
            "format": {"duration": "100"},
        }
        mock_run.return_value = _mock_run(json.dumps(data))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["video"]["hdr"]["hdr_type"] == "dolby_vision"

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_hdr10plus_detected(self, mock_run):
        """smpte2084 + HDR dynamic metadata side data → hdr10plus."""
        data = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 3840,
                    "height": 2160,
                    "display_aspect_ratio": "16:9",
                    "field_order": "progressive",
                    "color_transfer": "smpte2084",
                    "side_data_list": [{"side_data_type": "HDR dynamic metadata"}],
                    "disposition": {"attached_pic": 0},
                },
            ],
            "format": {"duration": "100"},
        }
        mock_run.return_value = _mock_run(json.dumps(data))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["video"]["hdr"]["hdr_type"] == "hdr10plus"

    @patch("personalscraper.scraper.mediainfo.subprocess.run")
    def test_hlg_detected(self, mock_run):
        """arib-std-b67 transfer → hlg HDR type."""
        data = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 3840,
                    "height": 2160,
                    "display_aspect_ratio": "16:9",
                    "field_order": "progressive",
                    "color_transfer": "arib-std-b67",
                    "disposition": {"attached_pic": 0},
                },
            ],
            "format": {"duration": "100"},
        }
        mock_run.return_value = _mock_run(json.dumps(data))
        info = extract_stream_info(Path("test.mkv"))
        assert info is not None
        assert info["video"]["hdr"]["is_hdr"] is True
        assert info["video"]["hdr"]["hdr_type"] == "hlg"
