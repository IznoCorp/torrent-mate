"""Library analyzer — query indexer DB for health metrics + ffprobe deep scan.

Two modes of analysis are exposed:

1. ``analyze(conn) -> AnalysisResult`` — lightweight, always available.
   Queries the indexer DB (populated by :func:`personalscraper.library.scanner.scan_library`)
   and returns aggregate health counts plus disk / category distribution and
   per-item sizes.  No ffprobe or filesystem access required.

2. ``analyze_library(config, ...) -> LibraryAnalysisResult`` — heavy, optional.
   Runs ffprobe on every video file and returns per-file codec/audio/subtitle
   information in memory (no on-disk cache).  Schedule during off-peak hours.

Callers in ``reporter.py`` and ``rescraper.py`` consume :class:`AnalysisResult`.
``analyze_library`` is consumed by the ``library-analyze`` and
``library-recommend`` CLI commands for on-demand ffprobe deep-scan.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# AnalysisResult — DB-query health summary
# ---------------------------------------------------------------------------


@dataclass
class NfoStatusCounts:
    """NFO status breakdown across the whole library.

    Attributes:
        valid: Number of items whose NFO is present and valid.
        invalid: Number of items with a present but invalid NFO.
        missing: Number of items with no NFO at all.
    """

    valid: int = 0
    invalid: int = 0
    missing: int = 0


@dataclass
class ArtworkCounts:
    """Artwork presence counts across the whole library.

    Attributes:
        poster_present: Items that have a poster.
        poster_missing: Items that have no poster.
    """

    poster_present: int = 0
    poster_missing: int = 0


@dataclass
class AnalysisResult:
    """Aggregate library health metrics queried from the indexer DB.

    Produced by :func:`analyze`.  Preserved for consumers in
    ``library/reporter.py`` and ``library/rescraper.py``.

    Attributes:
        analyzed_at: ISO 8601 timestamp of analysis.
        total_items: Total ``media_item`` rows in the DB.
        total_size_gb: Total bytes of all ``media_file`` rows, expressed in GB.
        movies_count: Items with ``kind='movie'``.
        shows_count: Items with ``kind='show'``.
        nfo: NFO status breakdown (valid / invalid / missing).
        artwork: Poster presence breakdown.
        seasons_missing_poster: Total ``season`` rows with ``has_poster=0``.
        nfo_invalid_by_category: Count of invalid-NFO items per ``category_id``.
        poster_missing_by_category: Count of poster-missing items per ``category_id``.
        items_needing_rescrape: Items with ``nfo_status != 'valid'`` or
            ``date_metadata_refreshed IS NULL`` — candidates for rescraper.
        items_per_disk: Item count per ``disk.label`` (i.e. config disk ID).
        items_per_category: Item count per ``category_id``.
        size_per_disk_gb: Total ``media_file`` bytes per disk, in GB.
        top_largest: Top 20 ``(title, size_gb)`` ordered by descending size.
    """

    analyzed_at: str = ""
    total_items: int = 0
    total_size_gb: float = 0.0
    movies_count: int = 0
    shows_count: int = 0
    nfo: NfoStatusCounts = field(default_factory=NfoStatusCounts)
    artwork: ArtworkCounts = field(default_factory=ArtworkCounts)
    seasons_missing_poster: int = 0
    nfo_invalid_by_category: dict[str, int] = field(default_factory=dict)
    poster_missing_by_category: dict[str, int] = field(default_factory=dict)
    items_needing_rescrape: int = 0
    items_per_disk: dict[str, int] = field(default_factory=dict)
    items_per_category: dict[str, int] = field(default_factory=dict)
    size_per_disk_gb: dict[str, float] = field(default_factory=dict)
    top_largest: list[tuple[str, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DB-query analysis
# ---------------------------------------------------------------------------


def analyze(conn: sqlite3.Connection) -> AnalysisResult:
    """Query the indexer DB and return an aggregate health summary.

    Does not access the filesystem or run ffprobe.  Requires that
    :func:`personalscraper.library.scanner.scan_library` has already been
    called with the same ``conn`` so the ``media_item``, ``season``, and
    ``episode`` tables are populated.

    Queries performed:

    * ``SELECT COUNT(*) FROM media_item`` — totals.
    * ``SELECT COUNT(*) ... WHERE nfo_status = ?`` — NFO breakdown.
    * ``SELECT COUNT(*) ... WHERE json_extract(artwork_json, '$.poster') = 0`` —
      poster coverage.
    * ``SELECT COUNT(*) FROM season WHERE has_poster = 0`` — season poster gaps.
    * ``SELECT category_id, COUNT(*) ... GROUP BY category_id`` — per-category breakdowns.
    * ``SELECT COUNT(*) FROM media_item WHERE nfo_status != 'valid'
      OR date_metadata_refreshed IS NULL`` — rescrape candidates.

    Args:
        conn: Open SQLite connection with all migrations applied and
            ``media_item`` / ``season`` tables populated.

    Returns:
        :class:`AnalysisResult` with aggregate health metrics.
    """
    result = AnalysisResult(analyzed_at=datetime.now(tz=timezone.utc).isoformat())

    # --- total / kind breakdown -----------------------------------------------
    result.total_items = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    result.movies_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()[0]
    result.shows_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'show'").fetchone()[0]

    # --- NFO status breakdown -------------------------------------------------
    result.nfo.valid = conn.execute("SELECT COUNT(*) FROM media_item WHERE nfo_status = 'valid'").fetchone()[0]
    result.nfo.invalid = conn.execute("SELECT COUNT(*) FROM media_item WHERE nfo_status = 'invalid'").fetchone()[0]
    result.nfo.missing = conn.execute(
        "SELECT COUNT(*) FROM media_item WHERE nfo_status = 'missing' OR nfo_status IS NULL"
    ).fetchone()[0]

    # --- Poster presence (artwork_json column) ---------------------------------
    # artwork_json is a JSON string; $.poster is a boolean stored as 0/1/true/false.
    # json_extract returns SQLite JSON types: true→1, false→0 (as integers in SQLite).
    result.artwork.poster_present = conn.execute(
        "SELECT COUNT(*) FROM media_item WHERE json_extract(artwork_json, '$.poster') = 1"
    ).fetchone()[0]
    result.artwork.poster_missing = conn.execute(
        "SELECT COUNT(*) FROM media_item WHERE json_extract(artwork_json, '$.poster') = 0 OR artwork_json IS NULL"
    ).fetchone()[0]

    # --- Season poster gaps ---------------------------------------------------
    result.seasons_missing_poster = conn.execute("SELECT COUNT(*) FROM season WHERE has_poster = 0").fetchone()[0]

    # --- Per-category NFO-invalid breakdown -----------------------------------
    rows = conn.execute(
        "SELECT category_id, COUNT(*) AS cnt FROM media_item WHERE nfo_status != 'valid' GROUP BY category_id"
    ).fetchall()
    result.nfo_invalid_by_category = {row[0]: row[1] for row in rows}

    # --- Per-category poster-missing breakdown --------------------------------
    rows = conn.execute(
        "SELECT category_id, COUNT(*) AS cnt FROM media_item "
        "WHERE json_extract(artwork_json, '$.poster') = 0 OR artwork_json IS NULL "
        "GROUP BY category_id"
    ).fetchall()
    result.poster_missing_by_category = {row[0]: row[1] for row in rows}

    # --- Rescrape candidates: NFO invalid/missing OR never scraped ------------
    result.items_needing_rescrape = conn.execute(
        "SELECT COUNT(*) FROM media_item WHERE nfo_status != 'valid' OR date_metadata_refreshed IS NULL"
    ).fetchone()[0]

    # --- Per-category item counts --------------------------------------------
    rows = conn.execute("SELECT category_id, COUNT(*) FROM media_item GROUP BY category_id").fetchall()
    result.items_per_category = {row[0]: row[1] for row in rows}

    # --- Per-disk distribution -----------------------------------------------
    # Source items_per_disk from item_attribute(dispatch_disk) so the count is
    # populated by every library-scanned item, regardless of whether enrich
    # has linked its files to a media_release.
    rows = conn.execute(
        "SELECT ia.value AS disk_label, COUNT(DISTINCT ia.item_id) AS items "
        "FROM item_attribute ia "
        "WHERE ia.key = 'dispatch_disk' "
        "GROUP BY ia.value"
    ).fetchall()
    result.items_per_disk = {row[0]: row[1] for row in rows}

    # --- Disk-level size aggregation -----------------------------------------
    # Sum media_file.size_bytes per disk via path → disk join.  Independent
    # of media_release, so size totals are populated whether or not enrich
    # has run.  Excludes soft-deleted files.
    rows = conn.execute(
        "SELECT d.label AS disk_label, COALESCE(SUM(mf.size_bytes), 0) AS bytes "
        "FROM media_file mf "
        "INNER JOIN path p ON p.id = mf.path_id "
        "INNER JOIN disk d ON d.id = p.disk_id "
        "WHERE mf.deleted_at IS NULL "
        "GROUP BY d.label"
    ).fetchall()
    bytes_to_gb = 1024**3
    size_per_disk: dict[str, int] = {row[0]: int(row[1]) for row in rows}
    result.size_per_disk_gb = {k: round(v / bytes_to_gb, 1) for k, v in size_per_disk.items()}
    result.total_size_gb = round(sum(size_per_disk.values()) / bytes_to_gb, 1)

    # --- Top-20 largest items ------------------------------------------------
    # Per-item size requires linking media_file rows to a media_item.  When
    # release linkage is present (post-enrich), the join is exact.  Otherwise
    # we fall back to matching media_file paths by their on-disk parent
    # against item_attribute(dispatch_path), which is written for every
    # library-scanned item.  No release linkage and no dispatch_path → the
    # item is skipped from top_largest only (still counted everywhere else).
    rows = conn.execute(
        "SELECT m.title AS title, SUM(mf.size_bytes) AS bytes "
        "FROM media_item m "
        "INNER JOIN media_release mr ON mr.item_id = m.id "
        "INNER JOIN media_file mf ON mf.release_id = mr.id "
        "WHERE mf.deleted_at IS NULL "
        "GROUP BY m.id "
        "UNION ALL "
        "SELECT m.title AS title, COALESCE(SUM(mf.size_bytes), 0) AS bytes "
        "FROM media_item m "
        "INNER JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
        "INNER JOIN item_attribute id_disk ON id_disk.item_id = m.id AND id_disk.key = 'dispatch_disk' "
        "INNER JOIN disk d ON d.label = id_disk.value "
        "INNER JOIN path p ON p.disk_id = d.id "
        "  AND ia.value = d.mount_path || '/' || p.rel_path "
        "INNER JOIN media_file mf ON mf.path_id = p.id "
        "WHERE mf.deleted_at IS NULL "
        "  AND NOT EXISTS ( "
        "    SELECT 1 FROM media_release mr2 WHERE mr2.item_id = m.id "
        "  ) "
        "GROUP BY m.id"
    ).fetchall()
    item_sizes: dict[str, int] = {}
    for title, byte_count in rows:
        item_sizes[title] = item_sizes.get(title, 0) + int(byte_count or 0)
    sorted_sizes = sorted(item_sizes.items(), key=lambda kv: -kv[1])
    result.top_largest = [(title, round(byte_count / bytes_to_gb, 1)) for title, byte_count in sorted_sizes[:20]]

    log.info(
        "library_analyze_complete",
        total=result.total_items,
        nfo_valid=result.nfo.valid,
        nfo_invalid=result.nfo.invalid,
        poster_missing=result.artwork.poster_missing,
        seasons_missing_poster=result.seasons_missing_poster,
        total_size_gb=result.total_size_gb,
    )
    return result


# ---------------------------------------------------------------------------
# Audio profile deduction (retained — used by analyze_library)
# ---------------------------------------------------------------------------


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


