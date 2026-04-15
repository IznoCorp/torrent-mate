# Phase 5: Analyzer — library-analyze command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `personalscraper library-analyze` — deep ffprobe scan extracting codec, resolution, bitrate, audio tracks, subtitles. Extends `extract_stream_info()` with 5 new fields. Supports `--incremental` to skip already-analyzed files.

**Architecture:** `analyzer.py` iterates media files, calls extended `extract_stream_info()`, deduces audio profiles, writes `library_analysis.json`. Most I/O-intensive command — designed for off-peak scheduling.

**Tech Stack:** Python, Typer, ffprobe (subprocess), pytest

---

## Task 1: Extend extract_stream_info with new fields

**Files:**

- Modify: `personalscraper/scraper/mediainfo.py`
- Modify: `tests/scraper/test_mediainfo.py` (or create if not exists)

- [ ] **Step 1: Write failing tests for new fields**

```python
# tests/scraper/test_mediainfo_v14.py
"""Tests for extract_stream_info V14 extensions — bitrate, is_atmos, forced, format, is_default."""

from pathlib import Path
from unittest.mock import patch
import json

from personalscraper.scraper.mediainfo import extract_stream_info


def _mock_ffprobe_output(video_bitrate: str = "5000000", audio_profile: str = "",
                          sub_codec: str = "subrip", sub_forced: int = 0,
                          audio_default: int = 1, sub_default: int = 0) -> str:
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

        output = _mock_ffprobe_output(audio_profile="Dolby Atmos")
        with patch("personalscraper.scraper.mediainfo.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = output
            result = extract_stream_info(video)

        assert result["audio"][0]["is_atmos"] is True

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
        """Subtitle codec_name should be normalized (subrip → srt)."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/scraper/test_mediainfo_v14.py -v`
Expected: FAIL — new fields not in return dict

- [ ] **Step 3: Extend extract_stream_info in mediainfo.py**

Read the current file first, then make these changes:

1. **Video bitrate** — in the video stream processing section, add:

```python
bitrate_raw = video_stream.get("bit_rate", "")
bitrate_kbps = int(int(bitrate_raw) / 1000) if bitrate_raw and bitrate_raw.isdigit() else None
```

Add `"bitrate_kbps": bitrate_kbps` to the `"video"` dict in the return value.

2. **Audio is_atmos and is_default** — in the audio track loop, add:

```python
profile = stream.get("profile", "")
is_atmos = "atmos" in profile.lower() if profile else False
disposition = stream.get("disposition", {})
is_default = bool(disposition.get("default", 0))
```

Add `"is_atmos": is_atmos, "is_default": is_default` to each audio track dict.

3. **Subtitle format, forced, is_default** — in the subtitle track loop, add:

```python
sub_codec_name = stream.get("codec_name", "unknown")
# Normalize codec names
_SUB_FORMAT_MAP = {
    "subrip": "srt", "hdmv_pgs_subtitle": "pgs",
    "ass": "ass", "dvd_subtitle": "dvd_subtitle",
}
sub_format = _SUB_FORMAT_MAP.get(sub_codec_name, sub_codec_name)
disposition = stream.get("disposition", {})
forced = bool(disposition.get("forced", 0))
is_default = bool(disposition.get("default", 0))
```

Change subtitle dict from `{"language": lang}` to `{"language": lang, "format": sub_format, "forced": forced, "is_default": is_default}`.

- [ ] **Step 4: Run V14 extension tests**

Run: `python -m pytest tests/scraper/test_mediainfo_v14.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run existing mediainfo tests for regressions**

Run: `python -m pytest tests/scraper/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/scraper/mediainfo.py tests/scraper/test_mediainfo_v14.py
git commit -m "v14.5.1: Extend extract_stream_info with bitrate, is_atmos, forced, format, is_default"
```

---

## Task 2: Implement audio profile detection

**Files:**

- Modify: `personalscraper/library/analyzer.py`
- Create: `tests/library/test_analyzer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_analyzer.py
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
```

- [ ] **Step 2: Implement analyzer.py with audio profile detection**

```python
# personalscraper/library/analyzer.py
"""Library analyzer — deep ffprobe scan for encoding, audio, subtitles.

Most I/O-intensive library command. Designed for off-peak scheduling.
Supports --incremental to skip already-analyzed files.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from personalscraper.library.models import (
    AudioTrack,
    LibraryAnalysisItem,
    LibraryAnalysisResult,
    MediaFileAnalysis,
    SubtitleTrack,
    VideoInfo,
)
from personalscraper.library.scanner import _parse_title_year, _SERIES_CATEGORIES, _VIDEO_EXTENSIONS
from personalscraper.scraper.mediainfo import extract_stream_info

logger = logging.getLogger(__name__)

# French language codes (ISO 639-2/T and /B variants)
_FRENCH_CODES = frozenset({"fra", "fre"})


def deduce_audio_profile(
    audio_tracks: list[dict],
    subtitle_tracks: list[dict],
) -> str:
    """Deduce audio profile from track information.

    Rules:
    - multi: ≥2 audio tracks with different languages
    - vf: single French audio track
    - vostfr: non-French audio + French subtitle
    - vo: non-French audio without French subtitles

    Args:
        audio_tracks: List of audio track dicts with "language" key.
        subtitle_tracks: List of subtitle track dicts with "language" key.

    Returns:
        Audio profile string: "multi", "vf", "vostfr", or "vo".
    """
    if not audio_tracks:
        return "vo"

    languages = {t.get("language", "und") for t in audio_tracks}

    # Multi: 2+ different languages
    if len(languages) >= 2:
        return "multi"

    # Single language
    lang = next(iter(languages))
    if lang in _FRENCH_CODES:
        return "vf"

    # Non-French audio — check subtitles for VOSTFR
    sub_langs = {t.get("language", "und") for t in subtitle_tracks}
    if sub_langs & _FRENCH_CODES:
        return "vostfr"

    return "vo"


def _analyze_video_file(
    video_path: Path,
) -> MediaFileAnalysis | None:
    """Analyze a single video file with ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        MediaFileAnalysis or None if ffprobe fails.
    """
    info = extract_stream_info(video_path)
    if info is None:
        logger.warning("ffprobe failed for %s", video_path)
        return None

    vid = info["video"]
    video = VideoInfo(
        codec=vid["codec"],
        width=vid["width"],
        height=vid["height"],
        bitrate_kbps=vid.get("bitrate_kbps"),
        hdr=vid.get("hdr", {}).get("is_hdr", False),
        hdr_type=vid.get("hdr", {}).get("hdr_type"),
    )

    audio_tracks = [
        AudioTrack(
            codec=t["codec"],
            language=t["language"],
            channels=t["channels"],
            is_atmos=t.get("is_atmos", False),
            is_default=t.get("is_default", False),
        )
        for t in info.get("audio", [])
    ]

    subtitle_tracks = [
        SubtitleTrack(
            language=t["language"],
            format=t.get("format", "unknown"),
            forced=t.get("forced", False),
            is_default=t.get("is_default", False),
        )
        for t in info.get("subtitle", [])
    ]

    audio_profile = deduce_audio_profile(info.get("audio", []), info.get("subtitle", []))
    sub_languages = sorted({t["language"] for t in info.get("subtitle", [])})

    try:
        size_gb = video_path.stat().st_size / (1024 ** 3)
    except OSError:
        size_gb = 0.0

    return MediaFileAnalysis(
        path=str(video_path),
        size_gb=round(size_gb, 3),
        duration_seconds=info.get("duration_seconds"),
        video=video,
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        audio_profile=audio_profile,
        subtitle_languages=sub_languages,
        analyzed_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def _get_file_key(path: Path) -> tuple[int, float]:
    """Get size + mtime for incremental skip check.

    Args:
        path: File path.

    Returns:
        Tuple of (size_bytes, mtime_timestamp).
    """
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime)
    except OSError:
        return (0, 0.0)


def analyze_library(
    disk_configs: list,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    incremental: bool = False,
    existing_analysis: dict[str, tuple[int, float]] | None = None,
    max_items: int | None = None,
) -> LibraryAnalysisResult:
    """Analyze all video files in the library with ffprobe.

    Args:
        disk_configs: List of DiskConfig objects.
        disk_filter: Only analyze this disk. None = all.
        category_filter: Only analyze this category. None = all.
        incremental: Skip files whose size+mtime haven't changed.
        existing_analysis: Dict of path → (size, mtime) from previous analysis.
        max_items: Maximum number of media items to analyze. None = unlimited.

    Returns:
        LibraryAnalysisResult with per-file analysis.
    """
    items: list[LibraryAnalysisItem] = []
    file_count = 0
    items_processed = 0
    start = datetime.now(tz=timezone.utc).isoformat()
    existing = existing_analysis or {}

    for config in disk_configs:
        if disk_filter and config.name != disk_filter:
            continue
        if not config.path.exists():
            continue

        for category_dir in sorted(config.path.iterdir()):
            if not category_dir.is_dir():
                continue
            if category_dir.name not in config.categories:
                continue
            if category_filter and category_dir.name != category_filter:
                continue

            is_series = category_dir.name in _SERIES_CATEGORIES

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                if max_items and items_processed >= max_items:
                    break

                title, year = _parse_title_year(media_dir.name)

                # Find all video files
                video_files = [
                    f for f in media_dir.rglob("*")
                    if f.is_file() and f.suffix.lstrip(".").lower() in _VIDEO_EXTENSIONS
                ]

                if not video_files:
                    continue

                file_analyses: list[MediaFileAnalysis] = []
                for vf in video_files:
                    # Incremental: skip if unchanged
                    if incremental:
                        key = _get_file_key(vf)
                        prev = existing.get(str(vf))
                        if prev and prev == key:
                            logger.debug("Skipping unchanged: %s", vf)
                            continue

                    analysis = _analyze_video_file(vf)
                    if analysis:
                        file_analyses.append(analysis)
                        file_count += 1

                if file_analyses:
                    items.append(LibraryAnalysisItem(
                        path=str(media_dir),
                        disk=config.name,
                        category=category_dir.name,
                        media_type="tvshow" if is_series else "movie",
                        title=title,
                        year=year,
                        files=file_analyses,
                    ))
                    items_processed += 1

            if max_items and items_processed >= max_items:
                break
        if max_items and items_processed >= max_items:
            break

    return LibraryAnalysisResult(
        analyzed_at=start,
        disk_filter=disk_filter,
        category_filter=category_filter,
        item_count=len(items),
        file_count=file_count,
        items=items,
    )
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/library/test_analyzer.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add personalscraper/library/analyzer.py tests/library/test_analyzer.py
git commit -m "v14.5.2: Implement analyzer with audio profile detection and incremental skip"
```

---

## Task 3: Add library-analyze CLI command

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryAnalyze:
    """Tests for library-analyze CLI command."""

    def test_help(self, runner) -> None:
        result = runner.invoke(app, ["library-analyze", "--help"])
        assert result.exit_code == 0
        assert "--disk" in result.output
        assert "--incremental" in result.output
        assert "--max-items" in result.output
```

- [ ] **Step 2: Add command to cli.py**

```python
@app.command()
@handle_cli_errors
def library_analyze(
    disk: str = typer.Option(None, "--disk", help="Analyze only this disk"),
    category: str = typer.Option(None, "--category", help="Analyze only this category"),
    incremental: bool = typer.Option(False, "--incremental", help="Skip already-analyzed files"),
    max_items: int = typer.Option(None, "--max-items", help="Limit number of items to analyze"),
) -> None:
    """Deep scan video files with ffprobe (codec, audio, subtitles).

    Most I/O-intensive command — schedule during off-peak hours.
    Use --incremental to skip files that haven't changed since last analysis.

    Examples:
        personalscraper library-analyze --incremental
        personalscraper library-analyze --disk Disk2 --category series
        personalscraper library-analyze --max-items 50
    """
    from personalscraper.library.analyzer import analyze_library
    from personalscraper.library.models import read_json, write_json

    console = state["console"]
    settings = get_settings()

    # Load existing analysis for incremental mode
    existing = {}
    analysis_path = settings.data_dir / "library_analysis.json"
    if incremental and analysis_path.exists():
        try:
            data = read_json(analysis_path)
            for item in data.get("items", []):
                for f in item.get("files", []):
                    path = f.get("path", "")
                    size = int(f.get("size_gb", 0) * 1024 ** 3)
                    existing[path] = (size, 0.0)  # mtime not stored yet, size-only check
        except (OSError, KeyError):
            pass

    console.print("[bold]Analyzing library (ffprobe)...[/bold]")
    result = analyze_library(
        settings.disk_configs,
        disk_filter=disk,
        category_filter=category,
        incremental=incremental,
        existing_analysis=existing if incremental else None,
        max_items=max_items,
    )

    write_json(result, analysis_path)

    console.print(
        f"[green]Analysis complete:[/green] {result.item_count} items, "
        f"{result.file_count} files → {analysis_path}"
    )
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_cli.py::TestLibraryAnalyze tests/library/test_analyzer.py tests/scraper/test_mediainfo_v14.py -v`
Expected: ALL PASS

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "v14.5.3: Add library-analyze CLI with incremental and max-items"
```

---

## Acceptance Criteria — Phase 5

- [ ] `extract_stream_info()` returns 5 new fields: bitrate_kbps, is_atmos, forced, format, is_default
- [ ] Existing scraper tests still pass (backwards compatible)
- [ ] Audio profile detection: multi, vf, vostfr, vo (including anime = jpn + fra subs)
- [ ] `--incremental` skips unchanged files
- [ ] `--max-items` limits processing
- [ ] `library_analysis.json` written with per-file detail
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
