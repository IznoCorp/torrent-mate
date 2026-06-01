"""Tests for the index-aware paths added to library tooling.

Covers:
- :func:`personalscraper.insights.analytics.analyze_from_index` — builds
  :class:`LibraryAnalysisResult` from ``media_file`` + ``media_stream``
  rows in lieu of running ffprobe.
- :func:`personalscraper.library.validator.validate_from_index` — fast
  pre-screen that surfaces NFO + artwork issues directly from the index.

Both paths are drop-in replacements for their FS-direct counterparts:
the assertions check the returned dataclasses, not implementation details.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.insights.analytics import analyze_from_index
from personalscraper.library.validator import validate_from_index

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with the full migration chain applied."""
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _seed_disk(c: sqlite3.Connection, *, label: str = "Disk1", mount: str = "/Volumes/Disk1") -> int:
    cur = c.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, NULL, 1, 0)",
        (label, label, mount, int(time.time())),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_path(c: sqlite3.Connection, *, disk_id: int, rel_path: str) -> int:
    cur = c.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (?, ?, NULL, NULL)",
        (disk_id, rel_path),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_item(
    c: sqlite3.Connection,
    *,
    kind: str,
    title: str,
    category_id: str,
    year: int | None = None,
    disk_label: str | None = None,
    dispatch_path: str | None = None,
    nfo_status: str | None = "valid",
    artwork_json: str | None = None,
) -> int:
    now = int(time.time())
    cur = c.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        " external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, date_created, date_modified, "
        " date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES (?, ?, ?, NULL, ?, ?, '{}', NULL, NULL, ?, ?, ?, ?, NULL, 0, 'fr')",
        (kind, title, title, year, category_id, nfo_status, artwork_json, now, now),
    )
    item_id = cur.lastrowid
    assert item_id is not None
    if disk_label is not None:
        c.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_disk', ?)",
            (item_id, disk_label),
        )
    if dispatch_path is not None:
        c.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, dispatch_path),
        )
    return item_id


def _seed_movie_release(c: sqlite3.Connection, *, item_id: int) -> int:
    cur = c.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (?, NULL, NULL, NULL, NULL)",
        (item_id,),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_episode_release(c: sqlite3.Connection, *, item_id: int, season_num: int, episode_num: int) -> int:
    season_row = c.execute(
        "SELECT id FROM season WHERE item_id = ? AND number = ?",
        (item_id, season_num),
    ).fetchone()
    if season_row is None:
        cur_s = c.execute(
            "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, ?, 0, 0, 0)",
            (item_id, season_num),
        )
        season_id = cur_s.lastrowid
    else:
        season_id = season_row[0]
    cur_e = c.execute(
        "INSERT INTO episode (season_id, number, title) VALUES (?, ?, NULL)",
        (season_id, episode_num),
    )
    episode_id = cur_e.lastrowid
    cur_r = c.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (NULL, ?, NULL, NULL, NULL)",
        (episode_id,),
    )
    assert cur_r.lastrowid is not None
    return cur_r.lastrowid


def _seed_file(
    c: sqlite3.Connection,
    *,
    release_id: int,
    path_id: int,
    filename: str,
    size_bytes: int = 1_000_000_000,
) -> int:
    now = int(time.time())
    cur = c.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns, "
        " oshash, xxh3_partial, xxh3_full, scan_generation, last_verified_at, enriched_at, "
        " miss_strikes, deleted_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, 1, ?, ?, 0, NULL)",
        (release_id, path_id, filename, size_bytes, now * 1_000_000_000, now, now),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_streams(
    c: sqlite3.Connection,
    *,
    file_id: int,
    video: dict | None = None,
    audios: list[dict] | None = None,
    subs: list[dict] | None = None,
) -> None:
    idx = 0
    if video:
        c.execute(
            "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
            " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
            "VALUES (?, ?, 'video', ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)",
            (
                file_id,
                idx,
                video.get("codec"),
                video.get("lang"),
                video.get("channels"),
                video.get("width"),
                video.get("height"),
                video.get("duration_ms"),
                video.get("bitrate"),
                video.get("hdr_format"),
                video.get("is_default"),
            ),
        )
        idx += 1
    for a in audios or []:
        c.execute(
            "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
            " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
            "VALUES (?, ?, 'audio', ?, ?, ?, NULL, NULL, NULL, ?, NULL, ?, ?, NULL, NULL)",
            (
                file_id,
                idx,
                a.get("codec"),
                a.get("lang"),
                a.get("channels"),
                a.get("bitrate"),
                a.get("is_atmos"),
                a.get("is_default"),
            ),
        )
        idx += 1
    for s in subs or []:
        c.execute(
            "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, width, height, "
            " duration_ms, bitrate, hdr_format, is_atmos, is_default, forced, format) "
            "VALUES (?, ?, 'subtitle', ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?, ?)",
            (
                file_id,
                idx,
                s.get("codec"),
                s.get("lang"),
                s.get("is_default"),
                s.get("forced"),
                s.get("format"),
            ),
        )
        idx += 1


# ---------------------------------------------------------------------------
# analyze_from_index
# ---------------------------------------------------------------------------


def test_analyze_from_index_empty_db_returns_empty_result(conn: sqlite3.Connection) -> None:
    """Empty DB → no items, no files, no errors."""
    result = analyze_from_index(conn)
    assert result.item_count == 0
    assert result.file_count == 0
    assert result.items == []


def test_analyze_from_index_movie_returns_one_item(conn: sqlite3.Connection) -> None:
    """Movie with media_file + streams → one LibraryAnalysisItem with one MediaFileAnalysis."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="films/Inception (2010)")
    item_id = _seed_item(
        conn,
        kind="movie",
        title="Inception",
        category_id="movies",
        year=2010,
        disk_label="Disk1",
        dispatch_path="/Volumes/Disk1/films/Inception (2010)",
    )
    release_id = _seed_movie_release(conn, item_id=item_id)
    file_id = _seed_file(
        conn, release_id=release_id, path_id=path_id, filename="Inception.mkv", size_bytes=2_000_000_000
    )
    _seed_streams(
        conn,
        file_id=file_id,
        video={"codec": "hevc", "width": 3840, "height": 2160, "bitrate": 12_500_000, "duration_ms": 9000000},
        audios=[{"codec": "eac3", "lang": "fra", "channels": 6, "bitrate": 640_000}],
        subs=[{"lang": "fra"}, {"lang": "eng"}],
    )

    result = analyze_from_index(conn)
    assert result.item_count == 1
    assert result.file_count == 1
    item = result.items[0]
    assert item.title == "Inception"
    assert item.media_type == "movie"
    assert item.disk == "Disk1"

    f = item.files[0]
    assert f.video.codec == "hevc"
    assert f.video.width == 3840
    assert f.video.height == 2160
    assert f.video.resolution == "2160p"
    assert f.video.bitrate_kbps == 12_500  # 12.5 Mbps → 12500 kbps
    assert f.duration_seconds == 9000.0
    assert f.audio_tracks[0].codec == "eac3"
    assert f.audio_tracks[0].language == "fra"
    assert f.audio_tracks[0].channels == 6
    assert f.audio_tracks[0].is_atmos is False  # 6 channels < 8
    assert f.subtitle_languages == ["eng", "fra"]
    assert f.audio_profile == "vf"


def test_analyze_from_index_atmos_approximation(conn: sqlite3.Connection) -> None:
    """eac3 codec with >=8 channels → is_atmos True (heuristic, used when is_atmos column is NULL)."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="films/Movie")
    item_id = _seed_item(conn, kind="movie", title="Movie", category_id="movies", disk_label="Disk1")
    release_id = _seed_movie_release(conn, item_id=item_id)
    file_id = _seed_file(conn, release_id=release_id, path_id=path_id, filename="Movie.mkv")
    _seed_streams(
        conn,
        file_id=file_id,
        video={"codec": "h264", "width": 1920, "height": 1080},
        audios=[{"codec": "eac3", "lang": "eng", "channels": 8}],  # is_atmos column NULL → heuristic kicks in
    )

    result = analyze_from_index(conn)
    assert result.items[0].files[0].audio_tracks[0].is_atmos is True


def test_analyze_from_index_uses_persisted_atmos_flag_when_set(conn: sqlite3.Connection) -> None:
    """When ``media_stream.is_atmos`` is persisted, that value wins over the heuristic."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="films/Movie")
    item_id = _seed_item(conn, kind="movie", title="Movie", category_id="movies", disk_label="Disk1")
    release_id = _seed_movie_release(conn, item_id=item_id)
    # Heuristic would say False (DTS); persisted column says True → persisted wins.
    file_id = _seed_file(conn, release_id=release_id, path_id=path_id, filename="A.mkv")
    _seed_streams(
        conn,
        file_id=file_id,
        video={"codec": "h264", "width": 1920, "height": 1080},
        audios=[{"codec": "dts", "lang": "fra", "channels": 6, "is_atmos": 1}],
    )
    # And the inverse: heuristic would say True, persisted says False → persisted wins.
    file_id_b = _seed_file(conn, release_id=release_id, path_id=path_id, filename="B.mkv")
    _seed_streams(
        conn,
        file_id=file_id_b,
        video={"codec": "h264", "width": 1920, "height": 1080},
        audios=[{"codec": "eac3", "lang": "fra", "channels": 8, "is_atmos": 0}],
    )

    result = analyze_from_index(conn)
    files = sorted(result.items[0].files, key=lambda f: f.path)
    a_track = next(t for t in files[0].audio_tracks if t.codec == "dts")
    b_track = next(t for t in files[1].audio_tracks if t.codec == "eac3")
    assert a_track.is_atmos is True
    assert b_track.is_atmos is False


def test_analyze_from_index_persisted_hdr_propagates(conn: sqlite3.Connection) -> None:
    """``hdr_format`` column populates VideoInfo.hdr + hdr_type."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="films/HDR")
    item_id = _seed_item(conn, kind="movie", title="HDR", category_id="movies", disk_label="Disk1")
    release_id = _seed_movie_release(conn, item_id=item_id)
    file_id = _seed_file(conn, release_id=release_id, path_id=path_id, filename="HDR.mkv")
    _seed_streams(
        conn,
        file_id=file_id,
        video={"codec": "hevc", "width": 3840, "height": 2160, "hdr_format": "Dolby Vision"},
    )

    video = analyze_from_index(conn).items[0].files[0].video
    assert video.hdr is True
    assert video.hdr_type == "Dolby Vision"


def test_analyze_from_index_subtitle_metadata_propagates(conn: sqlite3.Connection) -> None:
    """Subtitle ``format`` / ``forced`` / ``is_default`` columns flow into SubtitleTrack."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="films/Subs")
    item_id = _seed_item(conn, kind="movie", title="Subs", category_id="movies", disk_label="Disk1")
    release_id = _seed_movie_release(conn, item_id=item_id)
    file_id = _seed_file(conn, release_id=release_id, path_id=path_id, filename="Subs.mkv")
    _seed_streams(
        conn,
        file_id=file_id,
        video={"codec": "h264", "width": 1920, "height": 1080},
        subs=[{"lang": "fra", "format": "pgs", "forced": 1, "is_default": 0}],
    )

    sub = analyze_from_index(conn).items[0].files[0].subtitle_tracks[0]
    assert sub.format == "pgs"
    assert sub.forced is True
    assert sub.is_default is False


def test_analyze_from_index_skips_files_without_streams(conn: sqlite3.Connection) -> None:
    """File enriched=NULL (no streams yet) → item not surfaced."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="films/Pending")
    item_id = _seed_item(conn, kind="movie", title="Pending", category_id="movies", disk_label="Disk1")
    release_id = _seed_movie_release(conn, item_id=item_id)
    _seed_file(conn, release_id=release_id, path_id=path_id, filename="Pending.mkv")
    # No streams seeded.

    result = analyze_from_index(conn)
    assert result.item_count == 0


def test_analyze_from_index_filters_non_video_files(conn: sqlite3.Connection) -> None:
    """Sidecars (.nfo, .jpg) are excluded even when they have stream rows."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="films/M")
    item_id = _seed_item(conn, kind="movie", title="M", category_id="movies", disk_label="Disk1")
    release_id = _seed_movie_release(conn, item_id=item_id)
    file_video = _seed_file(conn, release_id=release_id, path_id=path_id, filename="M.mkv")
    _seed_streams(conn, file_id=file_video, video={"codec": "h264", "width": 1920, "height": 1080})
    file_nfo = _seed_file(conn, release_id=release_id, path_id=path_id, filename="M.nfo")
    _seed_streams(conn, file_id=file_nfo, video={"codec": "junk", "width": 0, "height": 0})

    result = analyze_from_index(conn)
    assert result.file_count == 1
    assert result.items[0].files[0].video.codec == "h264"


def test_analyze_from_index_tv_show_collects_episodes(conn: sqlite3.Connection) -> None:
    """TV show with two episodes returns one item with two MediaFileAnalysis entries."""
    disk_id = _seed_disk(conn)
    path_id = _seed_path(conn, disk_id=disk_id, rel_path="series/Show/Saison 01")
    item_id = _seed_item(
        conn,
        kind="show",
        title="Show",
        category_id="tv_shows",
        disk_label="Disk1",
        dispatch_path="/Volumes/Disk1/series/Show",
    )
    rel1 = _seed_episode_release(conn, item_id=item_id, season_num=1, episode_num=1)
    rel2 = _seed_episode_release(conn, item_id=item_id, season_num=1, episode_num=2)
    f1 = _seed_file(conn, release_id=rel1, path_id=path_id, filename="S01E01.mkv")
    f2 = _seed_file(conn, release_id=rel2, path_id=path_id, filename="S01E02.mkv")
    for fid in (f1, f2):
        _seed_streams(conn, file_id=fid, video={"codec": "h264", "width": 1920, "height": 1080})

    result = analyze_from_index(conn)
    assert result.item_count == 1
    assert result.items[0].media_type == "tvshow"
    assert len(result.items[0].files) == 2


def test_analyze_from_index_disk_filter(conn: sqlite3.Connection) -> None:
    """Items on a different disk are excluded by disk_filter."""
    disk_a = _seed_disk(conn, label="DiskA", mount="/Volumes/DiskA")
    disk_b = _seed_disk(conn, label="DiskB", mount="/Volumes/DiskB")
    path_a = _seed_path(conn, disk_id=disk_a, rel_path="films/A")
    path_b = _seed_path(conn, disk_id=disk_b, rel_path="films/B")
    item_a = _seed_item(conn, kind="movie", title="A", category_id="movies", disk_label="DiskA")
    item_b = _seed_item(conn, kind="movie", title="B", category_id="movies", disk_label="DiskB")
    rel_a = _seed_movie_release(conn, item_id=item_a)
    rel_b = _seed_movie_release(conn, item_id=item_b)
    fa = _seed_file(conn, release_id=rel_a, path_id=path_a, filename="A.mkv")
    fb = _seed_file(conn, release_id=rel_b, path_id=path_b, filename="B.mkv")
    for fid in (fa, fb):
        _seed_streams(conn, file_id=fid, video={"codec": "h264", "width": 1920, "height": 1080})

    result = analyze_from_index(conn, disk_filter="DiskA")
    assert result.item_count == 1
    assert result.items[0].title == "A"


def test_analyze_from_index_max_items(conn: sqlite3.Connection) -> None:
    """max_items caps the number of items returned (in title_sort order)."""
    disk_id = _seed_disk(conn)
    for letter in ("A", "B", "C"):
        path_id = _seed_path(conn, disk_id=disk_id, rel_path=f"films/{letter}")
        item_id = _seed_item(conn, kind="movie", title=letter, category_id="movies", disk_label="Disk1")
        rel = _seed_movie_release(conn, item_id=item_id)
        f = _seed_file(conn, release_id=rel, path_id=path_id, filename=f"{letter}.mkv")
        _seed_streams(conn, file_id=f, video={"codec": "h264", "width": 1920, "height": 1080})

    result = analyze_from_index(conn, max_items=2)
    assert result.item_count == 2
    assert [i.title for i in result.items] == ["A", "B"]


# ---------------------------------------------------------------------------
# validate_from_index
# ---------------------------------------------------------------------------


def test_validate_from_index_valid_when_all_present(conn: sqlite3.Connection) -> None:
    """nfo_status=valid + poster + landscape → status='valid', no errors/warnings."""
    artwork = json.dumps({"poster": 1, "landscape": 1, "fanart": 1})
    _seed_item(
        conn,
        kind="movie",
        title="Good",
        category_id="movies",
        disk_label="Disk1",
        nfo_status="valid",
        artwork_json=artwork,
    )
    result = validate_from_index(conn)
    assert result.valid_count == 1
    assert result.issues_count == 0
    assert result.items[0].status == "valid"


def test_validate_from_index_missing_nfo_is_error(conn: sqlite3.Connection) -> None:
    """nfo_status=missing → errors=['nfo_present']."""
    _seed_item(
        conn,
        kind="movie",
        title="NoNfo",
        category_id="movies",
        disk_label="Disk1",
        nfo_status="missing",
        artwork_json=json.dumps({"poster": 1, "landscape": 1}),
    )
    result = validate_from_index(conn)
    assert result.issues_count == 1
    assert "nfo_present" in result.items[0].errors


def test_validate_from_index_invalid_nfo_is_error(conn: sqlite3.Connection) -> None:
    """nfo_status=invalid → errors=['nfo_valid']."""
    _seed_item(
        conn,
        kind="movie",
        title="BadNfo",
        category_id="movies",
        disk_label="Disk1",
        nfo_status="invalid",
        artwork_json=json.dumps({"poster": 1, "landscape": 1}),
    )
    result = validate_from_index(conn)
    assert "nfo_valid" in result.items[0].errors


def test_validate_from_index_missing_poster_is_error(conn: sqlite3.Connection) -> None:
    """artwork_json poster=0 → errors=['poster_present']."""
    _seed_item(
        conn,
        kind="movie",
        title="NoPoster",
        category_id="movies",
        disk_label="Disk1",
        nfo_status="valid",
        artwork_json=json.dumps({"poster": 0, "landscape": 1}),
    )
    result = validate_from_index(conn)
    assert "poster_present" in result.items[0].errors


def test_validate_from_index_movie_missing_landscape_is_warning(conn: sqlite3.Connection) -> None:
    """Movies missing landscape → warnings=['artwork_landscape'], not an error."""
    _seed_item(
        conn,
        kind="movie",
        title="NoLandscape",
        category_id="movies",
        disk_label="Disk1",
        nfo_status="valid",
        artwork_json=json.dumps({"poster": 1, "landscape": 0}),
    )
    result = validate_from_index(conn)
    assert result.items[0].errors == []
    assert "artwork_landscape" in result.items[0].warnings


def test_validate_from_index_show_missing_landscape_is_not_warning(conn: sqlite3.Connection) -> None:
    """Shows missing landscape do not produce the artwork_landscape warning."""
    _seed_item(
        conn,
        kind="show",
        title="Show",
        category_id="tv_shows",
        disk_label="Disk1",
        nfo_status="valid",
        artwork_json=json.dumps({"poster": 1, "landscape": 0}),
    )
    result = validate_from_index(conn)
    assert result.items[0].warnings == []
    assert result.items[0].status == "valid"


def test_validate_from_index_disk_filter(conn: sqlite3.Connection) -> None:
    """disk_filter restricts the set of items returned."""
    artwork = json.dumps({"poster": 1, "landscape": 1})
    _seed_item(
        conn,
        kind="movie",
        title="A",
        category_id="movies",
        disk_label="DiskA",
        nfo_status="valid",
        artwork_json=artwork,
    )
    _seed_item(
        conn,
        kind="movie",
        title="B",
        category_id="movies",
        disk_label="DiskB",
        nfo_status="valid",
        artwork_json=artwork,
    )
    result = validate_from_index(conn, disk_filter="DiskA")
    assert result.total_items == 1
    assert result.items[0].title == "A"


def test_validate_from_index_category_filter(conn: sqlite3.Connection) -> None:
    """category_filter restricts the set of items returned."""
    artwork = json.dumps({"poster": 1, "landscape": 1})
    _seed_item(
        conn,
        kind="movie",
        title="Movie",
        category_id="movies",
        disk_label="Disk1",
        nfo_status="valid",
        artwork_json=artwork,
    )
    _seed_item(
        conn,
        kind="show",
        title="Show",
        category_id="tv_shows",
        disk_label="Disk1",
        nfo_status="valid",
        artwork_json=artwork,
    )
    result = validate_from_index(conn, category_filter="tv_shows")
    assert result.total_items == 1
    assert result.items[0].title == "Show"
