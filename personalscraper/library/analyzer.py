"""Library analyzer — deep ffprobe scan for encoding, audio, subtitles.

Most I/O-intensive library command. Designed for off-peak scheduling.
Supports --incremental to skip already-analyzed files.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.dispatch.disk_scanner import DiskConfig

from personalscraper.library.models import (
    AudioTrack,
    LibraryAnalysisItem,
    LibraryAnalysisResult,
    MediaFileAnalysis,
    SubtitleTrack,
    VideoInfo,
)
from personalscraper.library.scanner import _SERIES_CATEGORIES, _VIDEO_EXTENSIONS, parse_title_year
from personalscraper.scraper.mediainfo import extract_stream_info

logger = logging.getLogger(__name__)

# French language codes (ISO 639-2/T and /B variants)
_FRENCH_CODES = frozenset({"fra", "fre"})


def deduce_audio_profile(
    audio_tracks: list[dict[str, Any]],
    subtitle_tracks: list[dict[str, Any]],
) -> str:
    """Deduce audio profile from track information.

    Rules:
    - multi: >=2 audio tracks with different languages
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
        size_gb = video_path.stat().st_size / (1024**3)
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


def _file_size_bytes(path: Path) -> int:
    """Get file size in bytes for incremental comparison.

    Args:
        path: File path.

    Returns:
        File size in bytes, or 0 if inaccessible.
    """
    try:
        return path.stat().st_size
    except OSError:
        return 0


def analyze_library(
    disk_configs: list[DiskConfig],
    disk_filter: str | None = None,
    category_filter: str | None = None,
    incremental: bool = False,
    existing_sizes: dict[str, float] | None = None,
    max_items: int | None = None,
) -> LibraryAnalysisResult:
    """Analyze all video files in the library with ffprobe.

    Args:
        disk_configs: List of DiskConfig objects.
        disk_filter: Only analyze this disk. None = all.
        category_filter: Only analyze this category. None = all.
        incremental: Skip files whose size_gb hasn't changed since last analysis.
        existing_sizes: Dict of path -> size_gb from previous analysis.
        max_items: Maximum number of media items to analyze. None = unlimited.

    Returns:
        LibraryAnalysisResult with per-file analysis.
    """
    items: list[LibraryAnalysisItem] = []
    file_count = 0
    items_processed = 0
    start = datetime.now(tz=timezone.utc).isoformat()
    existing = existing_sizes or {}

    for config in disk_configs:
        if disk_filter and config.name != disk_filter:
            continue
        if not config.path.exists():
            logger.warning("Disk not mounted: %s (%s)", config.name, config.path)
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

                title, year = parse_title_year(media_dir.name)

                # Find all video files (skip macOS resource forks "._*")
                video_files = [
                    f
                    for f in media_dir.rglob("*")
                    if f.is_file() and f.suffix.lstrip(".").lower() in _VIDEO_EXTENSIONS and not f.name.startswith("._")
                ]

                if not video_files:
                    continue

                file_analyses: list[MediaFileAnalysis] = []
                for vf in video_files:
                    # Incremental: skip if file size_gb hasn't changed
                    if incremental:
                        try:
                            current_size_gb = round(vf.stat().st_size / (1024**3), 3)
                        except OSError:
                            current_size_gb = -1.0  # force re-analyze
                        prev_size_gb = existing.get(str(vf))
                        if prev_size_gb is not None and prev_size_gb == current_size_gb:
                            logger.debug("Skipping unchanged: %s", vf)
                            continue

                    analysis = _analyze_video_file(vf)
                    if analysis:
                        file_analyses.append(analysis)
                        file_count += 1

                if file_analyses:
                    items.append(
                        LibraryAnalysisItem(
                            path=str(media_dir),
                            disk=config.name,
                            category=category_dir.name,
                            media_type="tvshow" if is_series else "movie",
                            title=title,
                            year=year,
                            files=file_analyses,
                        )
                    )
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


def _reconstruct_analysis_items(data: dict[str, Any]) -> list[LibraryAnalysisItem]:
    """Reconstruct LibraryAnalysisItem list from JSON data.

    Args:
        data: Parsed library_analysis.json dict.

    Returns:
        List of LibraryAnalysisItem with full type structure.
    """
    items = []
    for item_data in data.get("items", []):
        files = []
        for f_data in item_data.get("files", []):
            vid = f_data.get("video", {})
            files.append(
                MediaFileAnalysis(
                    path=f_data.get("path", ""),
                    size_gb=f_data.get("size_gb", 0),
                    duration_seconds=f_data.get("duration_seconds"),
                    video=VideoInfo(
                        codec=vid.get("codec", ""),
                        width=vid.get("width", 0),
                        height=vid.get("height", 0),
                        bitrate_kbps=vid.get("bitrate_kbps"),
                        hdr=vid.get("hdr", False),
                        hdr_type=vid.get("hdr_type"),
                    ),
                    audio_tracks=[
                        AudioTrack(
                            codec=a.get("codec", ""),
                            language=a.get("language", "und"),
                            channels=a.get("channels", 2),
                            is_atmos=a.get("is_atmos", False),
                            is_default=a.get("is_default", False),
                        )
                        for a in f_data.get("audio_tracks", [])
                    ],
                    subtitle_tracks=[
                        SubtitleTrack(
                            language=s.get("language", "und"),
                            format=s.get("format", "unknown"),
                            forced=s.get("forced", False),
                            is_default=s.get("is_default", False),
                        )
                        for s in f_data.get("subtitle_tracks", [])
                    ],
                    audio_profile=f_data.get("audio_profile", "vo"),
                    subtitle_languages=f_data.get("subtitle_languages", []),
                    analyzed_at=f_data.get("analyzed_at", ""),
                )
            )
        items.append(
            LibraryAnalysisItem(
                path=item_data.get("path", ""),
                disk=item_data.get("disk", ""),
                category=item_data.get("category", ""),
                media_type=item_data.get("media_type", "movie"),
                title=item_data.get("title", ""),
                year=item_data.get("year"),
                files=files,
            )
        )
    return items
