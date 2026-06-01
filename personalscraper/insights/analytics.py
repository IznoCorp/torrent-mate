"""DB-backed library analytics (read-only).

Two functions are exposed, both reading exclusively from the indexer DB —
no filesystem walk, no ffprobe:

1. ``analyze(conn) -> AnalysisResult`` — aggregate health counts plus disk /
   category distribution and per-item sizes. Queries ``media_item`` /
   ``season`` / ``item_issue`` rows populated by ``indexer.scanner``.

2. ``analyze_from_index(conn) -> LibraryAnalysisResult`` — per-file
   codec / audio / subtitle / HDR / Atmos data read from the ``media_stream``
   rows the enrich pass persisted. This is the **sole** stream reader
   (DESIGN §4.5): the old filesystem ffprobe re-scan (``analyze_library``)
   has been deleted. Populate ``media_stream`` via
   ``library-index --mode enrich`` before calling.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from personalscraper.core.media_types import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS
from personalscraper.insights.models import (
    AnalysisResult,
    AudioTrack,
    LibraryAnalysisItem,
    LibraryAnalysisResult,
    MediaFileAnalysis,
    SubtitleTrack,
    VideoInfo,
)
from personalscraper.logger import get_logger

log = get_logger("insights.analytics")

# French language codes (ISO 639-2/T and /B variants)
_FRENCH_CODES = frozenset({"fra", "fre"})


# ---------------------------------------------------------------------------
# DB-query analysis
# ---------------------------------------------------------------------------


def analyze(conn: sqlite3.Connection) -> AnalysisResult:
    """Query the indexer DB and return an aggregate health summary.

    Does not access the filesystem or run ffprobe.  Requires that the indexer
    scan stage has already populated the ``media_item``, ``season``, and
    ``episode`` tables with the same ``conn``.

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
# Audio profile deduction
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


# ---------------------------------------------------------------------------
# Index-backed analysis (reads media_stream — sole stream reader)
# ---------------------------------------------------------------------------


def analyze_from_index(
    conn: sqlite3.Connection,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    max_items: int | None = None,
) -> LibraryAnalysisResult:
    """Build a :class:`LibraryAnalysisResult` from the indexer DB without ffprobe.

    Reads ``media_file`` size/path data and ``media_stream`` codec/audio/subtitle
    rows that the enrich pass populated, and assembles the
    :class:`LibraryAnalysisItem` / :class:`MediaFileAnalysis` structure consumed
    by the recommender. Caveats:

    - HDR detection and HDR type come from ``media_stream.hdr_format`` (populated
      by enrich); ``VideoInfo.hdr`` is ``True`` only when that column is set.
    - Dolby Atmos comes from ``media_stream.is_atmos`` when present, with a
      codec + channel-count fallback (``eac3`` with >= 8 channels) for rows
      enriched before migration 004.
    - Subtitle ``format`` / ``forced`` / ``is_default`` flags fall back to
      conservative defaults (``"unknown"`` / ``False`` / ``False``) when absent.
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
