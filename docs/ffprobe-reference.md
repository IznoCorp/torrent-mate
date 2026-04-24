# ffprobe Reference for Media Pipeline

Complete reference for using `ffprobe` from Python via subprocess to extract video/audio/subtitle stream details from `.mkv` files and generate Kodi-compatible NFO XML.

---

## Table of Contents

1. [Installation](#1-installation)
2. [JSON Output Mode](#2-json-output-mode)
3. [Output Structure](#3-output-structure)
4. [Extracting Video Info](#4-extracting-video-info)
5. [Extracting Audio Info](#5-extracting-audio-info)
6. [Extracting Subtitle Info](#6-extracting-subtitle-info)
7. [Python Wrapper Pattern](#7-python-wrapper-pattern)
8. [Kodi NFO streamdetails Format](#8-kodi-nfo-streamdetails-format)
9. [Codec Name Mapping](#9-codec-name-mapping)
10. [Common Flags](#10-common-flags)
11. [Performance](#11-performance)
12. [Edge Cases](#12-edge-cases)
13. [Complete Implementation](#13-complete-implementation)

---

## 1. Installation

### macOS (Homebrew)

```bash
brew install ffmpeg
```

This installs both `ffmpeg` and `ffprobe`. Homebrew ffmpeg 8.0 includes support for all common codecs (x264, x265/HEVC, AV1, AAC, EAC3, DTS, etc.).

### Verify Installation

```bash
ffprobe -version
# ffprobe version 8.0 Copyright (c) 2007-2025 the FFmpeg developers
# built with Apple clang version 16.0.0 (clang-1600.0.26.6)
# ...
```

### Check Available in Python

```python
import shutil
ffprobe_path = shutil.which("ffprobe")
# Returns path like '/opt/homebrew/bin/ffprobe' or None if not found
```

---

## 2. JSON Output Mode

### The Command

```bash
ffprobe -v quiet -print_format json -show_streams -show_format <file>
```

| Flag                 | Purpose                                                  |
| -------------------- | -------------------------------------------------------- |
| `-v quiet`           | Suppress all stderr diagnostic output (banner, warnings) |
| `-print_format json` | Output as JSON (alias: `-of json`)                       |
| `-show_streams`      | Include per-stream info (video, audio, subtitle tracks)  |
| `-show_format`       | Include container-level info (duration, size, bitrate)   |

### Equivalent Aliases

```bash
# These are all equivalent:
-print_format json
-of json
-output_format json
```

### Compact JSON

```bash
# Single-line JSON (useful for piping):
-print_format json=compact=1
```

---

## 3. Output Structure

The JSON output has two top-level objects: `streams` (array) and `format` (object).

### `format` Object

Contains container-level metadata.

```json
{
  "format": {
    "filename": "/path/to/file.mkv",
    "nb_streams": 7,
    "nb_programs": 0,
    "format_name": "matroska,webm",
    "format_long_name": "Matroska / WebM",
    "start_time": "0.000000",
    "duration": "7626.560000",
    "size": "4939499917",
    "bit_rate": "5181366",
    "probe_score": 100,
    "tags": {
      "title": "The.Piano.Lesson.2024.MULTI.2160p.WEBRip.HDR.x265.EAC3.5.1.Atmos",
      "encoder": "libebml v1.4.5 + libmatroska v1.7.1",
      "creation_time": "2025-07-22T12:53:18.000000Z"
    }
  }
}
```

Key fields:

- **`duration`**: Duration in seconds as a string (e.g., `"7626.560000"` = 2h07m06s)
- **`size`**: File size in bytes as a string
- **`bit_rate`**: Overall bitrate in bits/sec as a string
- **`format_name`**: Container format (`"matroska,webm"` for .mkv)
- **`nb_streams`**: Total number of streams (video + audio + subtitle)

### `streams` Array

Each element represents one stream (track). Every stream has:

- **`index`**: Stream index (0-based)
- **`codec_type`**: One of `"video"`, `"audio"`, `"subtitle"`, `"data"`, `"attachment"`
- **`codec_name`**: Short codec name (e.g., `"hevc"`, `"eac3"`, `"subrip"`)
- **`codec_long_name`**: Human-readable name
- **`disposition`**: Object with boolean flags (`default`, `forced`, `hearing_impaired`, etc.)
- **`tags`**: Object with metadata (may include `language`, `title`, etc.)

---

## 4. Extracting Video Info

### Video Stream Fields

```json
{
  "index": 0,
  "codec_name": "hevc",
  "codec_long_name": "H.265 / HEVC (High Efficiency Video Coding)",
  "profile": "Main 10",
  "codec_type": "video",
  "width": 3840,
  "height": 2160,
  "coded_width": 3840,
  "coded_height": 2160,
  "sample_aspect_ratio": "1:1",
  "display_aspect_ratio": "16:9",
  "pix_fmt": "yuv420p10le",
  "level": 150,
  "color_range": "tv",
  "color_space": "bt2020nc",
  "color_transfer": "smpte2084",
  "color_primaries": "bt2020",
  "r_frame_rate": "24/1",
  "avg_frame_rate": "24/1",
  "side_data_list": [
    {
      "side_data_type": "Content light level metadata",
      "max_content": 86,
      "max_average": 80
    },
    {
      "side_data_type": "Mastering display metadata",
      "red_x": "11408507/16777216",
      "red_y": "5368709/16777216",
      "...": "..."
    }
  ]
}
```

### Common Video Codecs (codec_name values)

| codec_name      | Description | Typical files                 |
| --------------- | ----------- | ----------------------------- |
| `hevc` / `h265` | H.265 HEVC  | Most 4K content, modern 1080p |
| `h264`          | H.264 AVC   | Older 1080p/720p content      |
| `av1`           | AV1         | Newer streaming content       |
| `vc1`           | VC-1        | Older Blu-ray rips            |
| `mpeg2video`    | MPEG-2      | DVDs                          |
| `vp9`           | VP9         | YouTube downloads             |

### Aspect Ratio

ffprobe reports `display_aspect_ratio` as a ratio string (e.g., `"16:9"`, `"12:5"`, `"768:349"`).

Kodi NFO expects a decimal value (e.g., `1.778`, `2.400`, `2.201`).

Conversion:

```python
def parse_aspect_ratio(dar_str: str, width: int, height: int) -> float:
    """Convert ffprobe display_aspect_ratio to decimal for Kodi NFO."""
    if dar_str and ":" in dar_str:
        num, den = dar_str.split(":")
        try:
            return round(int(num) / int(den), 3)
        except (ValueError, ZeroDivisionError):
            pass
    # Fallback: compute from dimensions
    if width and height:
        return round(width / height, 3)
    return 0.0
```

Real examples from MKV files:

| display_aspect_ratio | Decimal | Meaning             |
| -------------------- | ------- | ------------------- |
| `16:9`               | 1.778   | Standard widescreen |
| `4:3`                | 1.333   | Classic TV          |
| `40:21`              | 1.905   | Near 1.9:1          |
| `12:5`               | 2.400   | Cinema scope 2.4:1  |
| `768:349`            | 2.201   | ~2.2:1              |
| `320:133`            | 2.406   | ~2.4:1 scope        |

### HDR Detection

HDR is determined by analyzing multiple fields on the video stream:

```python
def detect_hdr(stream: dict) -> dict:
    """Detect HDR format from video stream fields."""
    color_transfer = stream.get("color_transfer", "")
    color_primaries = stream.get("color_primaries", "")
    pix_fmt = stream.get("pix_fmt", "")
    side_data = stream.get("side_data_list", [])

    side_data_types = {sd.get("side_data_type", "") for sd in side_data}

    is_hdr = color_transfer in ("smpte2084", "arib-std-b67")
    is_10bit = "10" in pix_fmt  # yuv420p10le, yuv420p10be

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

    return {
        "is_hdr": is_hdr,
        "hdr_type": hdr_type,         # hdr10, hdr10plus, dolby_vision, hlg, None
        "is_10bit": is_10bit,
        "color_space": stream.get("color_space"),
        "color_transfer": color_transfer,
        "color_primaries": color_primaries,
    }
```

| color_transfer | color_primaries | Meaning                   |
| -------------- | --------------- | ------------------------- |
| `smpte2084`    | `bt2020`        | HDR10 (PQ transfer curve) |
| `arib-std-b67` | `bt2020`        | HLG (Hybrid Log-Gamma)    |
| `bt709`        | `bt709`         | SDR                       |
| `smpte170m`    | `smpte170m`     | SDR (NTSC)                |

| side_data_type                 | Meaning                              |
| ------------------------------ | ------------------------------------ |
| `Content light level metadata` | HDR10 MaxCLL/MaxFALL values          |
| `Mastering display metadata`   | HDR10 mastering display color volume |
| `DOVI configuration record`    | Dolby Vision                         |
| `HDR dynamic metadata`         | HDR10+ dynamic metadata              |

---

## 5. Extracting Audio Info

### Audio Stream Fields

```json
{
  "index": 1,
  "codec_name": "eac3",
  "codec_long_name": "ATSC A/52B (AC-3, E-AC-3)",
  "profile": "Dolby Digital Plus + Dolby Atmos",
  "codec_type": "audio",
  "sample_fmt": "fltp",
  "sample_rate": "48000",
  "channels": 6,
  "channel_layout": "5.1(side)",
  "bit_rate": "768000",
  "disposition": {
    "default": 1,
    "hearing_impaired": 0
  },
  "tags": {
    "language": "fre",
    "title": "French"
  }
}
```

### Common Audio Codecs

| codec_name  | Description                 | profile (if relevant)                                 |
| ----------- | --------------------------- | ----------------------------------------------------- |
| `eac3`      | Dolby Digital Plus (E-AC-3) | `"Dolby Digital Plus + Dolby Atmos"` for Atmos tracks |
| `ac3`       | Dolby Digital (AC-3)        |                                                       |
| `aac`       | AAC                         | `"LC"`, `"HE-AAC"`, `"HE-AACv2"`                      |
| `dts`       | DTS                         |                                                       |
| `truehd`    | Dolby TrueHD                | May include Atmos                                     |
| `flac`      | FLAC lossless               |                                                       |
| `opus`      | Opus                        |                                                       |
| `mp3`       | MP3                         |                                                       |
| `pcm_s16le` | PCM 16-bit                  |                                                       |
| `vorbis`    | Vorbis                      |                                                       |

### Channels and Channel Layout

| channels | channel_layout       | Meaning      |
| -------- | -------------------- | ------------ |
| 1        | `mono`               | Mono         |
| 2        | `stereo`             | Stereo       |
| 6        | `5.1` or `5.1(side)` | 5.1 surround |
| 8        | `7.1`                | 7.1 surround |

The `channels` field is an integer -- this is what Kodi NFO uses directly.

### Dolby Atmos Detection

Dolby Atmos is NOT a separate codec. It is metadata layered on top of EAC3 or TrueHD. ffprobe exposes it via the `profile` field:

```python
def is_atmos(stream: dict) -> bool:
    """Check if an audio stream carries Dolby Atmos metadata."""
    profile = stream.get("profile", "")
    return "Atmos" in profile
```

Profile values seen in practice:

- `"Dolby Digital Plus + Dolby Atmos"` -- EAC3 with Atmos
- `""` or missing -- standard EAC3/TrueHD without Atmos

### Language Tags

**Critical:** ffprobe uses **ISO 639-2/B** (bibliographic) codes, while Kodi NFO uses **ISO 639-2/T** (terminology) codes. Most codes are identical, but ~20 languages differ:

| ffprobe (639-2/B) | Kodi NFO (639-2/T) | Language   |
| ----------------- | ------------------ | ---------- |
| `fre`             | `fra`              | French     |
| `ger`             | `deu`              | German     |
| `dut`             | `nld`              | Dutch      |
| `chi`             | `zho`              | Chinese    |
| `cze`             | `ces`              | Czech      |
| `gre`             | `ell`              | Greek      |
| `rum`             | `ron`              | Romanian   |
| `slo`             | `slk`              | Slovak     |
| `per`             | `fas`              | Persian    |
| `arm`             | `hye`              | Armenian   |
| `geo`             | `kat`              | Georgian   |
| `ice`             | `isl`              | Icelandic  |
| `mac`             | `mkd`              | Macedonian |
| `may`             | `msa`              | Malay      |
| `baq`             | `eus`              | Basque     |
| `bur`             | `mya`              | Burmese    |
| `tib`             | `bod`              | Tibetan    |
| `wel`             | `cym`              | Welsh      |
| `alb`             | `sqi`              | Albanian   |
| `mao`             | `mri`              | Maori      |

Codes that are **identical** in both standards: `eng`, `spa`, `ita`, `por`, `jpn`, `kor`, `ara`, `hin`, `rus`, `pol`, `tur`, `swe`, `nor`, `dan`, `fin`, and hundreds more.

```python
# ISO 639-2/B -> ISO 639-2/T mapping (only codes that differ)
ISO_639_2_B_TO_T: dict[str, str] = {
    "fre": "fra", "ger": "deu", "dut": "nld", "chi": "zho",
    "cze": "ces", "gre": "ell", "rum": "ron", "slo": "slk",
    "per": "fas", "arm": "hye", "geo": "kat", "ice": "isl",
    "mac": "mkd", "may": "msa", "baq": "eus", "bur": "mya",
    "tib": "bod", "wel": "cym", "alb": "sqi", "mao": "mri",
}

def lang_b_to_t(code: str) -> str:
    """Convert ISO 639-2/B code to ISO 639-2/T (Kodi format)."""
    return ISO_639_2_B_TO_T.get(code, code)
```

---

## 6. Extracting Subtitle Info

### Subtitle Stream Fields

```json
{
  "index": 4,
  "codec_name": "subrip",
  "codec_long_name": "SubRip subtitle",
  "codec_type": "subtitle",
  "disposition": {
    "default": 0,
    "forced": 0,
    "hearing_impaired": 0
  },
  "tags": {
    "language": "fre",
    "title": "French Full"
  }
}
```

### Common Subtitle Codecs

| codec_name          | Description                | Kodi NFO codec  |
| ------------------- | -------------------------- | --------------- |
| `subrip`            | SubRip (.srt)              | `srt`           |
| `ass`               | Advanced SubStation Alpha  | `ass`           |
| `hdmv_pgs_subtitle` | PGS Blu-ray bitmap subs    | `pgs`           |
| `dvd_subtitle`      | DVD VobSub bitmap subs     | `vobsub`        |
| `mov_text`          | MP4 text subs              | `tx3g`          |
| `webvtt`            | WebVTT                     | `webvtt`        |
| (None/missing)      | Unknown/unrecognized codec | (skip or empty) |

**Edge case:** Some MKV files contain subtitle streams where `codec_name` is `None` or missing entirely. This can happen with unusual or malformed subtitle tracks. The code must handle this gracefully.

### Disposition Flags

Useful subtitle disposition flags:

- `forced`: Forced subtitles (foreign language dialog only)
- `hearing_impaired`: SDH subtitles
- `default`: Default track

---

## 7. Python Wrapper Pattern

### Basic Subprocess Call

```python
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

FFPROBE_TIMEOUT = 30  # seconds

def run_ffprobe(video_path: Path) -> dict | None:
    """
    Run ffprobe on a video file and return parsed JSON.

    Returns None if ffprobe is not installed, the file is unreadable,
    or the output cannot be parsed.
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
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT,
        )
    except FileNotFoundError:
        logger.warning("ffprobe not found — install ffmpeg (`brew install ffmpeg`)")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ffprobe timed out after %ds on %s", FFPROBE_TIMEOUT, video_path)
        return None

    if result.returncode != 0:
        # ffprobe exits 1 for missing files, corrupt files, non-media files
        logger.warning("ffprobe failed (exit %d) on %s", result.returncode, video_path)
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("ffprobe output is not valid JSON for %s", video_path)
        return None

    # Sanity check: must have at least one stream
    if not data.get("streams"):
        logger.warning("ffprobe returned no streams for %s", video_path)
        return None

    return data
```

### Key Error Scenarios

| Scenario                 | Behavior                                                          |
| ------------------------ | ----------------------------------------------------------------- |
| ffprobe not installed    | `FileNotFoundError` -- subprocess cannot find the binary          |
| File does not exist      | `returncode=1`, stdout is `{}` (empty JSON object)                |
| File is not a media file | `returncode=1`, stdout is `{}`                                    |
| Corrupted media file     | `returncode=1` or partial JSON with missing streams               |
| Very large file          | No issue -- ffprobe reads only headers/metadata (see Performance) |
| Timeout                  | `subprocess.TimeoutExpired` after 30s                             |

---

## 8. Kodi NFO streamdetails Format

### XML Structure

The `<streamdetails>` block lives inside `<fileinfo>` in the NFO:

```xml
<fileinfo>
    <streamdetails>
        <video>
            <durationinseconds>7627</durationinseconds>
            <codec>hevc</codec>
            <aspect>1.778</aspect>
            <width>3840</width>
            <height>2160</height>
            <scantype>progressive</scantype>
        </video>
        <audio>
            <language>fra</language>
            <codec>eac3</codec>
            <channels>6</channels>
        </audio>
        <audio>
            <language>eng</language>
            <codec>atmos</codec>
            <channels>6</channels>
        </audio>
        <subtitle>
            <language>fra</language>
        </subtitle>
        <subtitle>
            <language>eng</language>
        </subtitle>
    </streamdetails>
</fileinfo>
```

### Video Element

| Tag                   | Type   | Description                    | Example                     |
| --------------------- | ------ | ------------------------------ | --------------------------- |
| `<codec>`             | string | Video codec name               | `hevc`, `h264`, `av1`       |
| `<aspect>`            | float  | Display aspect ratio (decimal) | `1.778`, `2.400`            |
| `<width>`             | int    | Video width in pixels          | `3840`, `1920`              |
| `<height>`            | int    | Video height in pixels         | `2160`, `1080`              |
| `<durationinseconds>` | int    | Duration in whole seconds      | `7627`                      |
| `<scantype>`          | string | Scan type (optional)           | `progressive`, `interlaced` |
| `<stereomode>`        | string | 3D mode (optional, rare)       | `left_right`, `top_bottom`  |

### Audio Element (one per audio track)

| Tag          | Type   | Description               | Example                              |
| ------------ | ------ | ------------------------- | ------------------------------------ |
| `<codec>`    | string | Audio codec name          | `eac3`, `aac`, `ac3`, `dts`, `atmos` |
| `<language>` | string | ISO 639-2/T language code | `fra`, `eng`, `deu`                  |
| `<channels>` | int    | Number of audio channels  | `2`, `6`, `8`                        |

### Subtitle Element (one per subtitle track)

| Tag          | Type   | Description               | Example      |
| ------------ | ------ | ------------------------- | ------------ |
| `<language>` | string | ISO 639-2/T language code | `fra`, `eng` |

---

## 9. Codec Name Mapping

### ffprobe to Kodi Video Codec Mapping

Most video codec names pass through unchanged:

| ffprobe codec_name | Kodi NFO codec | Notes   |
| ------------------ | -------------- | ------- |
| `hevc`             | `hevc`         | Same    |
| `h264`             | `h264`         | Same    |
| `av1`              | `av1`          | Same    |
| `vc1`              | `vc1`          | Same    |
| `mpeg2video`       | `mpeg2`        | Shorten |
| `mpeg4`            | `mpeg4`        | Same    |
| `vp9`              | `vp9`          | Same    |
| `vp8`              | `vp8`          | Same    |
| `theora`           | `theora`       | Same    |

### ffprobe to Kodi Audio Codec Mapping

| ffprobe codec_name | ffprobe profile                    | Kodi NFO codec | Notes                         |
| ------------------ | ---------------------------------- | -------------- | ----------------------------- |
| `eac3`             | (none)                             | `eac3`         | Dolby Digital Plus            |
| `eac3`             | `Dolby Digital Plus + Dolby Atmos` | `atmos`        | Atmos via profile detection   |
| `ac3`              |                                    | `ac3`          | Dolby Digital                 |
| `aac`              |                                    | `aac`          | AAC                           |
| `dts`              |                                    | `dts`          | DTS                           |
| `dts`              | `DTS-HD MA`                        | `dtshd_ma`     | DTS-HD Master Audio           |
| `dts`              | `DTS-HD HRA`                       | `dtshd_hra`    | DTS-HD High Resolution        |
| `truehd`           |                                    | `truehd`       | Dolby TrueHD                  |
| `truehd`           | (with Atmos)                       | `truehd`       | TrueHD+Atmos (keep as truehd) |
| `flac`             |                                    | `flac`         | FLAC lossless                 |
| `opus`             |                                    | `opus`         | Opus                          |
| `mp3`              |                                    | `mp3`          | MP3                           |
| `vorbis`           |                                    | `vorbis`       | Vorbis                        |
| `pcm_s16le`        |                                    | `pcm`          | PCM (any variant)             |

### ffprobe to Kodi Subtitle Codec Mapping

| ffprobe codec_name  | Kodi NFO | Notes              |
| ------------------- | -------- | ------------------ |
| `subrip`            | `srt`    | Most common in MKV |
| `ass`               | `ass`    | Same               |
| `hdmv_pgs_subtitle` | `pgs`    | Blu-ray subs       |
| `dvd_subtitle`      | `vobsub` | DVD subs           |
| `mov_text`          | `tx3g`   | MP4 text           |
| `webvtt`            | `webvtt` | WebVTT             |

### Mapping Code

```python
# Video codecs: ffprobe name -> Kodi NFO name
VIDEO_CODEC_MAP: dict[str, str] = {
    "mpeg2video": "mpeg2",
}

# Audio codecs: ffprobe name -> Kodi NFO name
# Atmos is handled separately via profile detection
AUDIO_CODEC_MAP: dict[str, str] = {
    # Most pass through unchanged; only list exceptions
}

# Subtitle codecs: ffprobe name -> Kodi NFO name
SUBTITLE_CODEC_MAP: dict[str, str] = {
    "subrip": "srt",
    "hdmv_pgs_subtitle": "pgs",
    "dvd_subtitle": "vobsub",
    "mov_text": "tx3g",
}


def map_video_codec(codec_name: str) -> str:
    return VIDEO_CODEC_MAP.get(codec_name, codec_name)


def map_audio_codec(codec_name: str, profile: str = "") -> str:
    """Map audio codec, with special Atmos detection."""
    if "Atmos" in profile:
        return "atmos"
    if codec_name == "dts" and profile:
        if "DTS-HD MA" in profile:
            return "dtshd_ma"
        if "DTS-HD HRA" in profile or "DTS-HD HR" in profile:
            return "dtshd_hra"
    return AUDIO_CODEC_MAP.get(codec_name, codec_name)


def map_subtitle_codec(codec_name: str | None) -> str:
    if not codec_name:
        return ""
    return SUBTITLE_CODEC_MAP.get(codec_name, codec_name)
```

---

## 10. Common Flags

### Selective Output with -show_entries

Instead of `-show_streams -show_format` (which dumps everything), use `-show_entries` to request specific fields:

```bash
ffprobe -v quiet -print_format json \
  -show_entries "stream=codec_type,codec_name,profile,width,height,display_aspect_ratio,pix_fmt,color_transfer,color_primaries,color_space,channels,channel_layout,bit_rate,sample_rate:stream_tags=language,title:stream_disposition=default,forced,hearing_impaired:format=duration,size,bit_rate,format_name" \
  file.mkv
```

Syntax: `SECTION=field1,field2,field3:SECTION2=field1,field2`

Available sections:

- `stream=...` -- per-stream fields
- `stream_tags=...` -- stream tag fields
- `stream_disposition=...` -- disposition flags
- `format=...` -- container format fields
- `format_tags=...` -- container tag fields

### Filtering Streams with -select_streams

```bash
# Video streams only
ffprobe -select_streams v ...

# Audio streams only
ffprobe -select_streams a ...

# Subtitle streams only
ffprobe -select_streams s ...

# First video stream only
ffprobe -select_streams v:0 ...
```

### Counting Frames

```bash
# Count frames per stream (SLOW -- reads entire file)
ffprobe -count_frames -show_entries stream=nb_read_frames ...
```

**Warning:** `-count_frames` forces ffprobe to decode the entire file. This takes minutes on large files. Avoid unless actually needed.

### Error Verbosity

```bash
# Show only errors on stderr (useful for debugging)
-v error

# Show warnings too
-v warning

# Completely silent (for production)
-v quiet
```

---

## 11. Performance

### Speed

ffprobe reads **only the container headers and metadata**, NOT the full file content. This makes it extremely fast:

| File                   | Size   | Duration | ffprobe time |
| ---------------------- | ------ | -------- | ------------ |
| 4K HDR HEVC, 7 streams | 4.9 GB | 2h07m    | **0.065s**   |
| 1080p HEVC, 3 streams  | 1.3 GB | 1h29m    | ~0.04s       |

For a typical MKV file, ffprobe completes in **30-100ms** regardless of file size, because it only reads:

1. The Matroska container header
2. Stream codec parameters (stored in header)
3. Tag metadata
4. Side data (HDR metadata, etc.)

It does NOT:

- Decode any video/audio frames
- Seek through the file
- Read the actual media data

**Exception:** The `-count_frames` flag forces full file reading and decoding. Never use it unless you specifically need exact frame counts.

### Implications for Pipeline

- Can probe hundreds of files per second
- No concern about disk I/O bottleneck
- 30-second timeout is extremely generous; even a 100GB file probes in under 1 second
- Safe to run on network-mounted volumes (NFS, SMB) without performance concerns

---

## 12. Edge Cases

### File Does Not Exist

```bash
$ ffprobe -v quiet -print_format json -show_streams -show_format /nonexistent.mkv
{}
$ echo $?
1
```

Returns empty JSON `{}` with exit code 1. With `-v error`, stderr shows: `No such file or directory`.

### File Is Not a Media File

```bash
$ ffprobe -v quiet -print_format json -show_streams -show_format /etc/hosts
{}
$ echo $?
1
```

Same behavior: empty JSON, exit code 1. With `-v error`: `Invalid data found when processing input`.

### No Audio Tracks

Some video files (trailers, silent clips) have no audio streams. The `streams` array will contain only video (and possibly subtitle) entries. Code must not assume audio streams exist.

### No Subtitle Tracks

Common for many files. The `streams` array simply won't contain any `"codec_type": "subtitle"` entries.

### Multiple Video Streams

Rare but possible (e.g., files with embedded thumbnail/poster as a video stream, or multi-angle content). Typically take the first video stream (`index=0`) or the one with `disposition.default=1`.

### Missing Language Tags

Not all streams have language tags. The `tags` object may be empty or missing the `language` key entirely. Video streams almost never have language tags. Some audio/subtitle streams from certain sources may also lack them.

```python
language = stream.get("tags", {}).get("language", "und")  # "und" = undetermined
```

### Subtitle with No Codec

Some MKV files contain subtitle streams where `codec_name` is `None` or missing:

```json
{
  "index": 2,
  "codec_type": "subtitle",
  "codec_tag_string": "[0][0][0][0]",
  "tags": { "language": "fre" }
}
```

This happens with malformed or unusual subtitle formats. Handle by skipping the codec or defaulting to empty string.

### Dolby Atmos in EAC3

Atmos is NOT a separate codec. It is object-based audio metadata embedded within an EAC3 or TrueHD stream. ffprobe reports the base codec as `codec_name` and indicates Atmos via the `profile` field:

```json
{
  "codec_name": "eac3",
  "profile": "Dolby Digital Plus + Dolby Atmos",
  "channels": 6
}
```

The `channels` field shows 6 (5.1) because the EAC3 core is 5.1; the Atmos metadata extends this to object-based audio at the decoder level.

### Very Long Duration Strings

`format.duration` is a float-as-string, e.g., `"7626.560000"`. Convert with `round()` for `<durationinseconds>` to match MediaElch's rounding behavior:

```python
duration_secs = round(float(data["format"]["duration"]))
# 7626.56 -> 7627 (matches MediaElch)
# Using int() would give 7626 (truncation, off by 1 second)
```

### Files with Paths Containing Spaces or Special Characters

The project path `/path/to/staging/` contains spaces. When using `subprocess.run()` with a list of arguments (not a shell string), this is handled automatically -- no quoting needed.

```python
# CORRECT: list of args, spaces handled automatically
subprocess.run(["ffprobe", ..., str(video_path)], ...)

# WRONG: shell string, would need quoting
subprocess.run(f'ffprobe ... "{video_path}"', shell=True, ...)
```

---

## 13. Complete Implementation

### extract_stream_info() -- Production-Ready Function

```python
"""
Media stream info extraction via ffprobe.

Extracts video, audio, and subtitle stream details from media files
and returns data structured for Kodi NFO <streamdetails> generation.

Requires: ffprobe (installed via `brew install ffmpeg`)
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

FFPROBE_TIMEOUT = 30  # seconds -- generous; ffprobe reads only headers

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
}

# ISO 639-2/B (ffprobe/MKV) -> ISO 639-2/T (Kodi) -- only codes that differ
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
    """Convert ISO 639-2/B language code (ffprobe) to ISO 639-2/T (Kodi)."""
    return ISO_639_2_B_TO_T.get(code, code)


def _map_video_codec(codec_name: str) -> str:
    """Map ffprobe video codec name to Kodi NFO name."""
    return VIDEO_CODEC_MAP.get(codec_name, codec_name)


def _map_audio_codec(codec_name: str, profile: str = "") -> str:
    """Map ffprobe audio codec name to Kodi NFO name, with Atmos detection."""
    if "Atmos" in profile:
        return "atmos"
    if codec_name == "dts" and profile:
        if "DTS-HD MA" in profile:
            return "dtshd_ma"
        if "DTS-HD HRA" in profile or "DTS-HD HR" in profile:
            return "dtshd_hra"
    return codec_name


def _map_subtitle_codec(codec_name: str | None) -> str:
    """Map ffprobe subtitle codec name to Kodi NFO name."""
    if not codec_name:
        return ""
    return SUBTITLE_CODEC_MAP.get(codec_name, codec_name)


def _parse_aspect_ratio(dar_str: str | None, width: int, height: int) -> float:
    """Convert ffprobe display_aspect_ratio (e.g. '16:9') to decimal (1.778)."""
    if dar_str and ":" in dar_str:
        parts = dar_str.split(":")
        try:
            return round(int(parts[0]) / int(parts[1]), 3)
        except (ValueError, ZeroDivisionError):
            pass
    # Fallback: compute from pixel dimensions
    if width and height:
        return round(width / height, 3)
    return 0.0


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def extract_stream_info(video_path: Path) -> dict | None:
    """
    Extract stream details from a video file using ffprobe.

    Returns a dict ready for Kodi NFO <streamdetails> generation:
    {
        "duration_seconds": 7627,
        "video": {
            "codec": "hevc",
            "width": 3840,
            "height": 2160,
            "aspect": 1.778,
            "scantype": "progressive",
            "hdr": {
                "is_hdr": True,
                "hdr_type": "hdr10",
            },
        },
        "audio": [
            {"codec": "eac3", "channels": 6, "language": "fra"},
            {"codec": "atmos", "channels": 6, "language": "eng"},
        ],
        "subtitle": [
            {"language": "fra"},
            {"language": "eng"},
        ],
    }

    Returns None if ffprobe is not installed, the file is unreadable,
    or no streams are found.
    """
    # --- Run ffprobe ---
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT,
        )
    except FileNotFoundError:
        logger.warning(
            "ffprobe not found — install ffmpeg: brew install ffmpeg"
        )
        return None
    except subprocess.TimeoutExpired:
        logger.warning(
            "ffprobe timed out after %ds on: %s", FFPROBE_TIMEOUT, video_path
        )
        return None

    if result.returncode != 0:
        logger.warning(
            "ffprobe failed (exit %d) on: %s", result.returncode, video_path
        )
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

    # --- Parse video streams (take first) ---
    video_info = None
    for s in streams:
        if s.get("codec_type") != "video":
            continue
        # Skip attached pictures (poster/thumbnail embedded as video stream)
        if s.get("disposition", {}).get("attached_pic", 0):
            continue

        codec = _map_video_codec(s.get("codec_name", ""))
        width = s.get("width", 0)
        height = s.get("height", 0)
        aspect = _parse_aspect_ratio(
            s.get("display_aspect_ratio"), width, height
        )

        # HDR detection
        color_transfer = s.get("color_transfer", "")
        side_data = s.get("side_data_list", [])
        side_data_types = {
            sd.get("side_data_type", "") for sd in side_data
        }

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
        if field_order in ("tt", "bb", "tb", "bt"):
            scantype = "interlaced"
        else:
            scantype = "progressive"

        video_info = {
            "codec": codec,
            "width": width,
            "height": height,
            "aspect": aspect,
            "scantype": scantype,
            "hdr": {
                "is_hdr": is_hdr,
                "hdr_type": hdr_type,
            },
        }
        break  # Take only the first real video stream

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
        language = _lang_to_kodi(
            s.get("tags", {}).get("language", "und")
        )

        audio_tracks.append({
            "codec": codec,
            "channels": channels,
            "language": language,
        })

    # --- Parse subtitle streams (all) ---
    subtitle_tracks = []
    for s in streams:
        if s.get("codec_type") != "subtitle":
            continue

        language = _lang_to_kodi(
            s.get("tags", {}).get("language", "und")
        )

        subtitle_tracks.append({
            "language": language,
        })

    return {
        "duration_seconds": duration_seconds,
        "video": video_info,
        "audio": audio_tracks,
        "subtitle": subtitle_tracks,
    }
```

### NFO XML Generation from extract_stream_info() Output

```python
import xml.etree.ElementTree as ET


def build_streamdetails_xml(info: dict) -> ET.Element:
    """
    Build a <fileinfo><streamdetails>...</streamdetails></fileinfo> XML element
    from extract_stream_info() output.

    Args:
        info: Dict returned by extract_stream_info()

    Returns:
        ET.Element: <fileinfo> element ready to append to NFO root.
    """
    fileinfo = ET.Element("fileinfo")
    sd = ET.SubElement(fileinfo, "streamdetails")

    # --- Video ---
    video = info["video"]
    v_elem = ET.SubElement(sd, "video")
    ET.SubElement(v_elem, "durationinseconds").text = str(
        info["duration_seconds"]
    )
    ET.SubElement(v_elem, "codec").text = video["codec"]
    ET.SubElement(v_elem, "aspect").text = f"{video['aspect']:.3f}"
    ET.SubElement(v_elem, "width").text = str(video["width"])
    ET.SubElement(v_elem, "height").text = str(video["height"])
    ET.SubElement(v_elem, "scantype").text = video["scantype"]

    # --- Audio tracks ---
    for track in info["audio"]:
        a_elem = ET.SubElement(sd, "audio")
        ET.SubElement(a_elem, "language").text = track["language"]
        ET.SubElement(a_elem, "codec").text = track["codec"]
        ET.SubElement(a_elem, "channels").text = str(track["channels"])

    # --- Subtitle tracks ---
    for track in info["subtitle"]:
        s_elem = ET.SubElement(sd, "subtitle")
        ET.SubElement(s_elem, "language").text = track["language"]

    return fileinfo


def streamdetails_to_string(info: dict) -> str:
    """Return indented XML string for <fileinfo><streamdetails>."""
    elem = build_streamdetails_xml(info)
    ET.indent(elem, space="    ")
    return ET.tostring(elem, encoding="unicode")
```

### Usage Example

```python
from pathlib import Path

video = Path("/path/to/staging/001-MOVIES/The Piano Lesson (2024)/The Piano Lesson.mkv")
info = extract_stream_info(video)

if info:
    print(f"Duration: {info['duration_seconds']}s")
    print(f"Video: {info['video']['codec']} {info['video']['width']}x{info['video']['height']}")
    print(f"HDR: {info['video']['hdr']['hdr_type']}")
    print(f"Audio tracks: {len(info['audio'])}")
    for a in info['audio']:
        print(f"  {a['language']} {a['codec']} {a['channels']}ch")
    print(f"Subtitle tracks: {len(info['subtitle'])}")
    for s in info['subtitle']:
        print(f"  {s['language']}")

    # Generate XML
    xml_str = streamdetails_to_string(info)
    print(xml_str)
```

### Expected Output (from real file)

```
Duration: 7627s
Video: hevc 3840x2160
HDR: hdr10
Audio tracks: 3
  fra eac3 6ch
  fra eac3 6ch
  eng atmos 6ch
Subtitle tracks: 3
  fra
  fra
  eng
```

```xml
<fileinfo>
    <streamdetails>
        <video>
            <durationinseconds>7627</durationinseconds>
            <codec>hevc</codec>
            <aspect>1.778</aspect>
            <width>3840</width>
            <height>2160</height>
            <scantype>progressive</scantype>
        </video>
        <audio>
            <language>fra</language>
            <codec>eac3</codec>
            <channels>6</channels>
        </audio>
        <audio>
            <language>fra</language>
            <codec>eac3</codec>
            <channels>6</channels>
        </audio>
        <audio>
            <language>eng</language>
            <codec>atmos</codec>
            <channels>6</channels>
        </audio>
        <subtitle>
            <language>fra</language>
        </subtitle>
        <subtitle>
            <language>fra</language>
        </subtitle>
        <subtitle>
            <language>eng</language>
        </subtitle>
    </streamdetails>
</fileinfo>
```

---

## Real ffprobe JSON Output Reference

### Full output from a 4K HDR MKV (The Piano Lesson, 2024)

File: 4.9 GB, HEVC Main 10, 3840x2160, HDR10, 3 audio tracks (EAC3 + Atmos), 3 subtitle tracks (SubRip).

```json
{
  "streams": [
    {
      "index": 0,
      "codec_name": "hevc",
      "codec_long_name": "H.265 / HEVC (High Efficiency Video Coding)",
      "profile": "Main 10",
      "codec_type": "video",
      "width": 3840,
      "height": 2160,
      "sample_aspect_ratio": "1:1",
      "display_aspect_ratio": "16:9",
      "pix_fmt": "yuv420p10le",
      "color_range": "tv",
      "color_space": "bt2020nc",
      "color_transfer": "smpte2084",
      "color_primaries": "bt2020",
      "r_frame_rate": "24/1",
      "avg_frame_rate": "24/1",
      "disposition": { "default": 1, "forced": 0, "hearing_impaired": 0 },
      "tags": { "BPS": "3130495", "DURATION": "02:07:06.542000000" },
      "side_data_list": [
        {
          "side_data_type": "Content light level metadata",
          "max_content": 86,
          "max_average": 80
        },
        {
          "side_data_type": "Mastering display metadata",
          "max_luminance": "1000/1",
          "min_luminance": "209800/2098000053"
        }
      ]
    },
    {
      "index": 1,
      "codec_name": "eac3",
      "codec_type": "audio",
      "channels": 6,
      "channel_layout": "5.1(side)",
      "bit_rate": "640000",
      "disposition": { "default": 1 },
      "tags": { "language": "fre", "title": "French" }
    },
    {
      "index": 2,
      "codec_name": "eac3",
      "codec_type": "audio",
      "channels": 6,
      "channel_layout": "5.1(side)",
      "bit_rate": "640000",
      "disposition": { "default": 0 },
      "tags": { "language": "fre", "title": "French AD" }
    },
    {
      "index": 3,
      "codec_name": "eac3",
      "profile": "Dolby Digital Plus + Dolby Atmos",
      "codec_type": "audio",
      "channels": 6,
      "channel_layout": "5.1(side)",
      "bit_rate": "768000",
      "disposition": { "default": 0 },
      "tags": { "language": "eng", "title": "English" }
    },
    {
      "index": 4,
      "codec_name": "subrip",
      "codec_type": "subtitle",
      "disposition": { "default": 0, "hearing_impaired": 0 },
      "tags": { "language": "fre", "title": "French Full" }
    },
    {
      "index": 5,
      "codec_name": "subrip",
      "codec_type": "subtitle",
      "disposition": { "default": 0, "hearing_impaired": 1 },
      "tags": { "language": "fre", "title": "French SDH" }
    },
    {
      "index": 6,
      "codec_name": "subrip",
      "codec_type": "subtitle",
      "disposition": { "default": 0, "hearing_impaired": 1 },
      "tags": { "language": "eng", "title": "English SDH" }
    }
  ],
  "format": {
    "filename": "/path/to/staging/001-MOVIES/The Piano Lesson (2024)/The Piano Lesson.mkv",
    "nb_streams": 7,
    "format_name": "matroska,webm",
    "format_long_name": "Matroska / WebM",
    "duration": "7626.560000",
    "size": "4939499917",
    "bit_rate": "5181366",
    "probe_score": 100,
    "tags": {
      "title": "The.Piano.Lesson.2024.MULTI.AD.2160p.WEBRip.NF.HDR.x265.EAC3.5.1.Atmos-Amen",
      "encoder": "libebml v1.4.5 + libmatroska v1.7.1"
    }
  }
}
```

### Comparison with MediaElch NFO Output

For the same file, MediaElch generated this streamdetails (present in the actual NFO):

```xml
<streamdetails>
    <video>
        <durationinseconds>7627</durationinseconds>
        <codec>hevc</codec>
        <aspect>1.778</aspect>
        <width>3840</width>
        <height>2160</height>
        <scantype>progressive</scantype>
    </video>
    <audio>
        <language>fra</language>
        <codec>eac3</codec>
        <channels>6</channels>
    </audio>
    <audio>
        <language>fra</language>
        <codec>eac3</codec>
        <channels>6</channels>
    </audio>
    <audio>
        <language>eng</language>
        <codec>atmos</codec>
        <channels>6</channels>
    </audio>
    <subtitle><language>fra</language></subtitle>
    <subtitle><language>fra</language></subtitle>
    <subtitle><language>eng</language></subtitle>
</streamdetails>
```

Key observations from MediaElch's behavior:

- Duration is rounded up: `int(7626.56) + 1 = 7627` (or `round()`)
- Language codes are ISO 639-2/T: `fra` not `fre`
- Atmos EAC3 track mapped to codec `atmos`
- Aspect ratio is decimal with 3 decimal places: `1.778`
- Scantype is always provided
