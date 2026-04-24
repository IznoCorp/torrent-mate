"""Library analyzer — deep ffprobe scan for encoding, audio, subtitles.

Most I/O-intensive library command. Designed for off-peak scheduling.
Supports --incremental to skip already-analyzed files.

``analyze_library`` accepts a ``Config`` object and resolves folder
names from ``config.category(id).folder_name``. TV detection uses
``TV_CATEGORY_IDS`` from ``conf/ids``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.conf.models import Config

from personalscraper.conf.ids import TV_CATEGORY_IDS
from personalscraper.library.models import (
    AudioTrack,
    LibraryAnalysisItem,
    LibraryAnalysisResult,
    MediaFileAnalysis,
    SubtitleTrack,
    VideoInfo,
)
from personalscraper.library.scanner import _VIDEO_EXTENSIONS, parse_title_year
from personalscraper.logger import get_logger
from personalscraper.scraper.mediainfo import extract_stream_info

log = get_logger("library.analyzer")

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

    # Check subtitles for VOSTFR
    sub_languages = {s.get("language", "und") for s in subtitle_tracks}
    if sub_languages & _FRENCH_CODES:
        return "vostfr"

    return "vo"


def _analyze_video_file(path: Path) -> MediaFileAnalysis | None:
    """Run ffprobe on a single video file and return analysis.

    Args:
        path: Path to the video file.

    Returns:
        MediaFileAnalysis if ffprobe succeeds, None on failure.
    """
    try:
        size_gb = round(path.stat().st_size / (1024**3), 3)
    except OSError:
        size_gb = 0.0

    try:
        info = extract_stream_info(path)
    except Exception as exc:
        log.warning("library_ffprobe_failed", path=str(path), exc_info=True, error=str(exc))
        return None

    if not info:
        return None

    video_stream = info.get("video")
    audio_streams = info.get("audio", [])
    subtitle_streams = info.get("subtitles", [])

    if not video_stream:
        return None

    # Build AudioTrack objects
    audio_tracks = []
    for a in audio_streams:
        audio_tracks.append(
            AudioTrack(
                codec=a.get("codec", ""),
                language=a.get("language", "und"),
                channels=a.get("channels", 2),
                is_atmos=a.get("is_atmos", False),
                is_default=a.get("is_default", False),
            )
        )

    # Build SubtitleTrack objects
    subtitle_tracks = []
    for s in subtitle_streams:
        subtitle_tracks.append(
            SubtitleTrack(
                language=s.get("language", "und"),
                format=s.get("format", "unknown"),
                forced=s.get("forced", False),
                is_default=s.get("is_default", False),
            )
        )

    raw_audio = [{"language": a.language} for a in audio_tracks]
    raw_subs = [{"language": s.language} for s in subtitle_tracks]
    audio_profile = deduce_audio_profile(raw_audio, raw_subs)

    duration_seconds = info.get("duration_seconds")

    hdr_info = video_stream.get("hdr", {})
    hdr = bool(hdr_info)
    hdr_type = hdr_info.get("type") if isinstance(hdr_info, dict) else None

    return MediaFileAnalysis(
        path=str(path),
        size_gb=size_gb,
        duration_seconds=duration_seconds,
        video=VideoInfo(
            codec=video_stream.get("codec", ""),
            width=video_stream.get("width", 0),
            height=video_stream.get("height", 0),
            bitrate_kbps=video_stream.get("bitrate_kbps"),
            hdr=hdr,
            hdr_type=hdr_type,
        ),
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        audio_profile=audio_profile,
        subtitle_languages=[s.language for s in subtitle_tracks],
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
    config: Config,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    incremental: bool = False,
    existing_sizes: dict[str, float] | None = None,
    max_items: int | None = None,
) -> LibraryAnalysisResult:
    """Analyze all video files in the library with ffprobe.

    Iterates ``config.disks``, resolves folder names from
    ``config.category(id).folder_name``, and analyzes media files.
    TV detection uses ``TV_CATEGORY_IDS`` from ``conf/ids``.

    Args:
        config: Config with disk and category definitions.
        disk_filter: Only analyze this disk (by disk.id). None = all.
        category_filter: Only analyze this category_id. None = all.
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

    for disk in config.disks:
        if disk_filter and disk.id != disk_filter:
            continue
        if not disk.path.exists():
            log.warning("library_disk_not_mounted", disk=disk.id, path=str(disk.path))
            continue

        for category_id in disk.categories:
            if category_filter and category_id != category_filter:
                continue

            # Resolve physical folder name from config
            cat_cfg = config.category(category_id)
            category_dir = disk.path / cat_cfg.folder_name
            if not category_dir.is_dir():
                log.debug("library_category_not_found", category_dir=str(category_dir), disk=disk.id)
                continue

            is_series = category_id in TV_CATEGORY_IDS

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
                            log.debug("library_analyze_skip_unchanged", path=str(vf))
                            continue

                    analysis = _analyze_video_file(vf)
                    if analysis:
                        file_analyses.append(analysis)
                        file_count += 1

                if file_analyses:
                    items.append(
                        LibraryAnalysisItem(
                            path=str(media_dir),
                            disk=disk.id,
                            category=category_id,
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
