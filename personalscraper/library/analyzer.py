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

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

from personalscraper._fs_utils import is_apple_double
from personalscraper.conf.ids import TV_CATEGORY_IDS
from personalscraper.core.media_types import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS
from personalscraper.library.models import (
    AudioTrack,
    LibraryAnalysisItem,
    LibraryAnalysisResult,
    MediaFileAnalysis,
    SubtitleTrack,
    VideoInfo,
)
from personalscraper.logger import get_logger
from personalscraper.nfo_utils import parse_title_year
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
        scan_issues: Count of items per directory-hygiene issue type
            (``actors_dir_present``, ``junk_files``, ``bad_dir_naming``,
            ``release_group_artifact``, ``empty_subdir``, ``ntfs_unsafe_name``).
            Populated by the indexer via the ``item_issue`` table.
        actors_dir_count: Convenience accessor — items with at least one
            ``.actors/`` directory.  Equivalent to
            ``scan_issues.get('actors_dir_present', 0)``.
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
    scan_issues: dict[str, int] = field(default_factory=dict)
    actors_dir_count: int = 0


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
    # populated by every indexed item, regardless of whether enrich has linked
    # its files to a media_release.
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
    # indexed item.  No release linkage and no dispatch_path → the
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

    # --- Directory-hygiene issue counts (sourced from item_issue) ----------
    # The library scanner persists scan-detected issue tags into
    # ``item_issue`` so the report layer can surface them without
    # re-walking the disks.  Drop "ISSUE_" prefix-less raw types straight
    # through — the reporter already maps issue keys to human strings.
    rows = conn.execute("SELECT type, COUNT(*) FROM item_issue GROUP BY type").fetchall()
    result.scan_issues = {row[0]: row[1] for row in rows}
    result.actors_dir_count = result.scan_issues.get("actors_dir_present", 0)

    log.info(
        "library_analyze_complete",
        total=result.total_items,
        nfo_valid=result.nfo.valid,
        nfo_invalid=result.nfo.invalid,
        poster_missing=result.artwork.poster_missing,
        seasons_missing_poster=result.seasons_missing_poster,
        total_size_gb=result.total_size_gb,
        scan_issue_types=len(result.scan_issues),
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


def analyze_from_index(
    conn: sqlite3.Connection,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    max_items: int | None = None,
) -> LibraryAnalysisResult:
    """Build a :class:`LibraryAnalysisResult` from the indexer DB without ffprobe.

    Reads ``media_file`` size/path data and ``media_stream`` codec/audio/subtitle
    rows that the enrich pass populated, and assembles the same
    :class:`LibraryAnalysisItem` / :class:`MediaFileAnalysis` structure that
    :func:`analyze_library` returns from filesystem ffprobe walks. Drop-in
    replacement for the recommender, with caveats:

    - HDR detection and HDR type are not stored in ``media_stream`` yet, so
      ``VideoInfo.hdr`` is always ``False`` here.
    - Dolby Atmos detection is approximated from codec + channel count
      (``eac3`` with >= 8 channels) since ``is_atmos`` is not persisted.
    - Subtitle ``format`` / ``forced`` / ``is_default`` flags are not stored;
      conservative defaults (``"unknown"`` / ``False`` / ``False``) are used.
    - ``AudioTrack.is_default`` defaults to ``False`` for the same reason.

    Items lacking any ``media_stream`` rows (Stage A only, never enriched, or
    enrich budget never reached them) are skipped — they would surface as
    ``files=[]`` items which the recommender treats as no-op anyway.

    Args:
        conn: Open SQLite connection on the indexer DB.
        disk_filter: Restrict to items on a specific disk (matches
            ``item_attribute.dispatch_disk``).
        category_filter: Restrict to a single ``media_item.category_id``.
        max_items: Cap the number of items returned (in title order).

    Returns:
        :class:`LibraryAnalysisResult` populated from the index.
    """
    start = datetime.now(tz=timezone.utc).isoformat()
    conn.row_factory = sqlite3.Row

    item_query = """
        SELECT mi.id, mi.kind, mi.title, mi.year, mi.category_id,
               ia_disk.value AS disk_label,
               ia_path.value AS dispatch_path
        FROM media_item mi
        LEFT JOIN item_attribute ia_disk
               ON ia_disk.item_id = mi.id AND ia_disk.key = 'dispatch_disk'
        LEFT JOIN item_attribute ia_path
               ON ia_path.item_id = mi.id AND ia_path.key = 'dispatch_path'
        ORDER BY mi.title_sort, mi.id
    """
    item_rows = conn.execute(item_query).fetchall()

    items: list[LibraryAnalysisItem] = []
    file_count = 0

    for it in item_rows:
        if disk_filter is not None and it["disk_label"] != disk_filter:
            continue
        if category_filter is not None and it["category_id"] != category_filter:
            continue
        if max_items is not None and len(items) >= max_items:
            break

        item_id: int = it["id"]
        files_for_item = _collect_files_for_item(conn, item_id)
        if not files_for_item:
            continue

        file_analyses: list[MediaFileAnalysis] = []
        for f in files_for_item:
            analysis = _file_analysis_from_index(conn, f)
            if analysis is not None:
                file_analyses.append(analysis)
                file_count += 1

        if not file_analyses:
            continue

        kind = it["kind"]
        media_type = "tvshow" if kind == "show" else "movie"

        items.append(
            LibraryAnalysisItem(
                path=str(it["dispatch_path"] or ""),
                disk=str(it["disk_label"] or ""),
                category=it["category_id"],
                media_type=media_type,
                title=it["title"],
                year=it["year"],
                files=file_analyses,
            )
        )

    conn.row_factory = None

    return LibraryAnalysisResult(
        analyzed_at=start,
        disk_filter=disk_filter,
        category_filter=category_filter,
        item_count=len(items),
        file_count=file_count,
        items=items,
    )


def _collect_files_for_item(conn: sqlite3.Connection, item_id: int) -> list[sqlite3.Row]:
    """Return media_file rows reachable from ``item_id`` (movie release + episode releases).

    Filters out non-video extensions and soft-deleted files. Each returned row
    carries the absolute path of the file via the ``abs_path`` virtual column.

    Args:
        conn: Open SQLite connection (row_factory must already be set to Row).
        item_id: PK of the owning ``media_item``.

    Returns:
        List of ``sqlite3.Row`` with columns ``id``, ``filename``, ``size_bytes``,
        ``abs_path``.
    """
    rows = conn.execute(
        """
        SELECT mf.id            AS id,
               mf.filename      AS filename,
               mf.size_bytes    AS size_bytes,
               (CASE WHEN p.rel_path = '.' THEN d.mount_path
                     ELSE d.mount_path || '/' || p.rel_path
                END) || '/' || mf.filename AS abs_path
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
          JOIN disk d ON d.id = p.disk_id
          JOIN media_release mr ON mr.id = mf.release_id
     LEFT JOIN episode e ON e.id = mr.episode_id
     LEFT JOIN season s ON s.id = e.season_id
         WHERE mf.deleted_at IS NULL
           AND (mr.item_id = ? OR s.item_id = ?)
        """,
        (item_id, item_id),
    ).fetchall()

    filtered: list[sqlite3.Row] = []
    for row in rows:
        ext = Path(row["filename"]).suffix.lstrip(".").lower()
        if ext in _VIDEO_EXTENSIONS:
            filtered.append(row)
    return filtered


def _file_analysis_from_index(conn: sqlite3.Connection, file_row: sqlite3.Row) -> MediaFileAnalysis | None:
    """Build a :class:`MediaFileAnalysis` from ``media_stream`` rows for ``file_row``.

    Returns ``None`` when no streams have been extracted yet (file pending
    enrich) or when the file has no video stream — both states are equivalent
    to "nothing to analyse".

    Args:
        conn: Open SQLite connection.
        file_row: ``media_file`` row from :func:`_collect_files_for_item`.

    Returns:
        :class:`MediaFileAnalysis` populated from the index, or ``None``.
    """
    stream_rows = conn.execute(
        """
        SELECT kind, codec, lang, channels, width, height, duration_ms, bitrate,
               hdr_format, is_atmos, is_default, forced, format
          FROM media_stream
         WHERE file_id = ?
         ORDER BY kind, idx
        """,
        (file_row["id"],),
    ).fetchall()

    if not stream_rows:
        return None

    video_row = next((s for s in stream_rows if s["kind"] == "video"), None)
    if video_row is None:
        return None

    audio_rows = [s for s in stream_rows if s["kind"] == "audio"]
    subtitle_rows = [s for s in stream_rows if s["kind"] == "subtitle"]

    audio_tracks: list[AudioTrack] = []
    for a in audio_rows:
        codec = a["codec"] or ""
        channels = a["channels"] or 2
        is_atmos_raw = a["is_atmos"]
        if is_atmos_raw is not None:
            is_atmos = bool(is_atmos_raw)
        else:
            # Pre-migration row: fall back to the codec + channel heuristic so
            # rows enriched before migration 004 still surface a best-effort
            # signal until the next enrich pass overwrites them.
            is_atmos = codec.lower() in {"eac3", "e-ac-3", "ac-3+"} and channels >= 8
        is_default_raw = a["is_default"]
        is_default = bool(is_default_raw) if is_default_raw is not None else False
        audio_tracks.append(
            AudioTrack(
                codec=codec,
                language=a["lang"] or "und",
                channels=channels,
                is_atmos=is_atmos,
                is_default=is_default,
            )
        )

    subtitle_tracks: list[SubtitleTrack] = []
    for s in subtitle_rows:
        format_raw = s["format"]
        forced_raw = s["forced"]
        is_default_raw = s["is_default"]
        subtitle_tracks.append(
            SubtitleTrack(
                language=s["lang"] or "und",
                format=format_raw if format_raw else "unknown",
                forced=bool(forced_raw) if forced_raw is not None else False,
                is_default=bool(is_default_raw) if is_default_raw is not None else False,
            )
        )

    raw_audio = [{"language": t.language} for t in audio_tracks]
    raw_subs = [{"language": t.language} for t in subtitle_tracks]
    audio_profile = deduce_audio_profile(raw_audio, raw_subs)

    duration_seconds: float | None = None
    if video_row["duration_ms"]:
        duration_seconds = float(video_row["duration_ms"]) / 1000.0

    bitrate_bps = video_row["bitrate"]
    bitrate_kbps = (bitrate_bps // 1000) if bitrate_bps else None

    size_gb = round((file_row["size_bytes"] or 0) / (1024**3), 3)

    hdr_format = video_row["hdr_format"]
    return MediaFileAnalysis(
        path=str(file_row["abs_path"]),
        size_gb=size_gb,
        duration_seconds=duration_seconds,
        video=VideoInfo(
            codec=video_row["codec"] or "",
            width=video_row["width"] or 0,
            height=video_row["height"] or 0,
            bitrate_kbps=bitrate_kbps,
            hdr=bool(hdr_format),
            hdr_type=hdr_format,
        ),
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        audio_profile=audio_profile,
        subtitle_languages=sorted({t.language for t in subtitle_tracks}),
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
                    if f.is_file() and f.suffix.lstrip(".").lower() in _VIDEO_EXTENSIONS and not is_apple_double(f.name)
                ]

                if not video_files:
                    continue

                # Filter out files we'd skip in incremental mode before
                # spawning ffprobe workers — saves the thread pool from
                # bouncing on cheap stat()-only paths.
                analyze_targets: list[Path] = []
                for vf in video_files:
                    if incremental:
                        try:
                            current_size_gb = round(vf.stat().st_size / (1024**3), 3)
                        except OSError:
                            current_size_gb = -1.0  # force re-analyze
                        prev_size_gb = existing.get(str(vf))
                        if prev_size_gb is not None and prev_size_gb == current_size_gb:
                            log.debug("library_analyze_skip_unchanged", path=str(vf))
                            continue
                    analyze_targets.append(vf)

                # Run ffprobe in parallel — each call shells out to a
                # subprocess that mostly waits on disk I/O and ffprobe
                # parsing, so a bounded ThreadPoolExecutor scales well
                # without saturating CPU.  Worker count capped at 4 for
                # NTFS-USB targets (mechanical drives saturate fast on
                # concurrent reads); SSD libraries can override via
                # ``LIBRARY_ANALYZER_MAX_WORKERS`` env var.
                file_analyses: list[MediaFileAnalysis] = []
                if analyze_targets:
                    max_workers = int(os.environ.get("LIBRARY_ANALYZER_MAX_WORKERS", "4"))
                    if max_workers <= 1 or len(analyze_targets) == 1:
                        for vf in analyze_targets:
                            analysis = _analyze_video_file(vf)
                            if analysis is not None:
                                file_analyses.append(analysis)
                                file_count += 1
                    else:
                        with ThreadPoolExecutor(max_workers=max_workers) as pool:
                            for analysis in pool.map(_analyze_video_file, analyze_targets):
                                if analysis is not None:
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
