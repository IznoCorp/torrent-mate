"""Stream details extraction via ffprobe for Kodi NFO generation.

Extracts video codec, resolution, aspect ratio, audio tracks (with Dolby
Atmos detection), subtitles, and duration from media files. All language
codes are converted from ISO 639-2/B (ffprobe) to ISO 639-2/T (Kodi).

Uses subprocess to call ffprobe (reads headers only, ~65ms per file).
Returns None gracefully if ffprobe is absent or the file is unreadable.

See docs/ffprobe-reference.md for the full specification.
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

FFPROBE_TIMEOUT = 30  # seconds — generous; ffprobe reads only headers

# ---------------------------------------------------------------------------
# Codec mapping tables
# ---------------------------------------------------------------------------

VIDEO_CODEC_MAP: dict[str, str] = {
    "mpeg2video": "mpeg2",
}

SUBTITLE_CODEC_MAP: dict[str, str] = {
    "subrip": "srt",
    "hdmv_pgs_subtitle": "pgs",
    "dvd_subtitle": "vobsub",
    "mov_text": "tx3g",
    "ass": "ass",
}

# ISO 639-2/B (ffprobe/MKV) -> ISO 639-2/T (Kodi) — only codes that differ
ISO_639_2_B_TO_T: dict[str, str] = {
    "fre": "fra", "ger": "deu", "dut": "nld", "chi": "zho",
    "cze": "ces", "gre": "ell", "rum": "ron", "slo": "slk",
    "per": "fas", "arm": "hye", "geo": "kat", "ice": "isl",
    "mac": "mkd", "may": "msa", "baq": "eus", "bur": "mya",
    "tib": "bod", "wel": "cym", "alb": "sqi", "mao": "mri",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lang_to_kodi(code: str) -> str:
    """Convert ISO 639-2/B language code (ffprobe) to ISO 639-2/T (Kodi).

    Args:
        code: ISO 639-2/B language code (e.g. "fre").

    Returns:
        ISO 639-2/T equivalent (e.g. "fra"). Returns input unchanged
        if no mapping exists (most codes are identical).
    """
    return ISO_639_2_B_TO_T.get(code, code)


def _map_video_codec(codec_name: str) -> str:
    """Map ffprobe video codec name to Kodi NFO name.

    Args:
        codec_name: Raw ffprobe codec name (e.g. "mpeg2video").

    Returns:
        Kodi-compatible codec name (e.g. "mpeg2").
    """
    return VIDEO_CODEC_MAP.get(codec_name, codec_name)


def _map_audio_codec(codec_name: str, profile: str = "") -> str:
    """Map ffprobe audio codec name to Kodi NFO name.

    Dolby Atmos returns "atmos" for Kodi NFO compatibility.
    DTS-HD variants are also detected. The separate is_atmos field
    on audio tracks preserves the underlying codec for analysis.

    Args:
        codec_name: Raw ffprobe codec name (e.g. "eac3").
        profile: ffprobe profile string (e.g. "Dolby Digital Plus + Dolby Atmos").

    Returns:
        Kodi-compatible codec name ("atmos", "dtshd_ma", or raw codec).
    """
    if "Atmos" in profile:
        return "atmos"
    if codec_name == "dts" and profile:
        if "DTS-HD MA" in profile:
            return "dtshd_ma"
        if "DTS-HD HRA" in profile or "DTS-HD HR" in profile:
            return "dtshd_hra"
    return codec_name


def _parse_aspect_ratio(dar_str: str | None, width: int, height: int) -> float:
    """Convert ffprobe display_aspect_ratio to decimal.

    Args:
        dar_str: Display aspect ratio string (e.g. "16:9"), or None.
        width: Video width in pixels.
        height: Video height in pixels.

    Returns:
        Decimal aspect ratio (e.g. 1.778). Falls back to width/height.
    """
    if dar_str and ":" in dar_str:
        parts = dar_str.split(":")
        try:
            return round(int(parts[0]) / int(parts[1]), 3)
        except (ValueError, ZeroDivisionError):
            pass
    if width and height:
        return round(width / height, 3)
    return 0.0


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def extract_stream_info(video_path: Path) -> dict | None:
    """Extract stream details from a video file using ffprobe.

    Returns a dict ready for Kodi NFO <streamdetails> generation::

        {
            "duration_seconds": 7627,
            "video": {
                "codec": "hevc",
                "width": 3840,
                "height": 2160,
                "aspect": 1.778,
                "scantype": "progressive",
                "hdr": {"is_hdr": True, "hdr_type": "hdr10"},
                "bitrate_kbps": 15000,
            },
            "audio": [
                {"codec": "eac3", "channels": 6, "language": "fra",
                 "is_atmos": False, "is_default": True},
            ],
            "subtitle": [
                {"language": "fra", "format": "srt",
                 "forced": False, "is_default": True},
            ],
        }

    Args:
        video_path: Path to the video file.

    Returns:
        Stream details dict, or None if ffprobe is absent, the file is
        unreadable, or no video streams are found.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT)
    except FileNotFoundError:
        logger.warning("ffprobe not found — install ffmpeg: brew install ffmpeg")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ffprobe timed out after %ds on: %s", FFPROBE_TIMEOUT, video_path)
        return None

    if result.returncode != 0:
        logger.warning("ffprobe failed (exit %d) on: %s", result.returncode, video_path)
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("ffprobe returned invalid JSON for: %s", video_path)
        return None

    streams = data.get("streams", [])
    fmt = data.get("format", {})

    if not streams:
        logger.warning("ffprobe returned no streams for: %s", video_path)
        return None

    # --- Parse duration ---
    duration_str = fmt.get("duration", "0")
    try:
        duration_seconds = round(float(duration_str))
    except (ValueError, OverflowError):
        duration_seconds = 0

    # --- Parse video stream (first real one, skip attached pics) ---
    video_info = None
    for s in streams:
        if s.get("codec_type") != "video":
            continue
        # Skip embedded thumbnails/posters (attached as video streams)
        if s.get("disposition", {}).get("attached_pic", 0):
            continue

        codec = _map_video_codec(s.get("codec_name", ""))
        width = s.get("width", 0)
        height = s.get("height", 0)
        aspect = _parse_aspect_ratio(s.get("display_aspect_ratio"), width, height)

        # HDR detection via color_transfer and side_data
        color_transfer = s.get("color_transfer", "")
        side_data = s.get("side_data_list", [])
        side_data_types = {sd.get("side_data_type", "") for sd in side_data}

        is_hdr = color_transfer in ("smpte2084", "arib-std-b67")
        hdr_type = None
        if color_transfer == "smpte2084":
            if "DOVI configuration record" in side_data_types:
                hdr_type = "dolby_vision"
            elif "HDR dynamic metadata" in side_data_types:
                hdr_type = "hdr10plus"
            else:
                hdr_type = "hdr10"
        elif color_transfer == "arib-std-b67":
            hdr_type = "hlg"

        # Scan type: interlaced detection via field_order
        field_order = s.get("field_order", "progressive")
        scantype = "interlaced" if field_order in ("tt", "bb", "tb", "bt") else "progressive"

        # Bitrate extraction (V14)
        bitrate_raw = s.get("bit_rate", "")
        bitrate_kbps = int(int(bitrate_raw) / 1000) if bitrate_raw and str(bitrate_raw).isdigit() else None

        video_info = {
            "codec": codec,
            "width": width,
            "height": height,
            "aspect": aspect,
            "scantype": scantype,
            "hdr": {"is_hdr": is_hdr, "hdr_type": hdr_type},
            "bitrate_kbps": bitrate_kbps,
        }
        break  # First real video stream only

    if video_info is None:
        logger.warning("No video stream found in: %s", video_path)
        return None

    # --- Parse audio streams (all) ---
    audio_tracks = []
    for s in streams:
        if s.get("codec_type") != "audio":
            continue
        codec_name = s.get("codec_name", "")
        profile = s.get("profile", "")
        codec = _map_audio_codec(codec_name, profile)
        channels = s.get("channels", 0)
        language = _lang_to_kodi(s.get("tags", {}).get("language", "und"))
        # Atmos detection (separate from codec for analysis) and default flag
        is_atmos = "atmos" in profile.lower() if profile else False
        disposition = s.get("disposition", {})
        is_default = bool(disposition.get("default", 0))
        audio_tracks.append({
            "codec": codec, "channels": channels, "language": language,
            "is_atmos": is_atmos, "is_default": is_default,
        })

    # --- Parse subtitle streams (all) ---
    subtitle_tracks = []
    for s in streams:
        if s.get("codec_type") != "subtitle":
            continue
        language = _lang_to_kodi(s.get("tags", {}).get("language", "und"))
        sub_codec_name = s.get("codec_name", "unknown")
        sub_format = SUBTITLE_CODEC_MAP.get(sub_codec_name, sub_codec_name)
        disposition = s.get("disposition", {})
        forced = bool(disposition.get("forced", 0))
        is_default = bool(disposition.get("default", 0))
        subtitle_tracks.append({
            "language": language, "format": sub_format,
            "forced": forced, "is_default": is_default,
        })

    return {
        "duration_seconds": duration_seconds,
        "video": video_info,
        "audio": audio_tracks,
        "subtitle": subtitle_tracks,
    }
