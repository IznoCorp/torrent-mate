"""E2E tests for ``personalscraper library-analyze`` — CLI-level harness.

Tests the --from-index path (DB-backed, no ffprobe) and the global --format
flag.  Seeds complete items with media_stream rows to exercise the analysis
summary (codec distribution, audio profiles).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _seed_analyze_item(
    conn: sqlite3.Connection,
    disk_id: int,
    mount_path: Path,
    title: str,
    category_id: str,
    kind: str,
    video_codec: str = "hevc",
    width: int = 1920,
    height: int = 1080,
    audio_lang: str = "fra",
    audio_channels: int = 6,
    subtitle_lang: str = "fra",
    size_bytes: int = 5_000_000_000,
) -> tuple[int, int, int]:
    """Seed a complete item chain: item → release → file → streams → attributes.

    Returns (item_id, release_id, file_id).
    """
    now = int(time.time())
    rel_path = f"cat_{category_id}/{title}"

    cursor = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "date_created, date_modified, nfo_status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'valid')",
        (kind, title, title, category_id, now, now),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]

    cursor = conn.execute(
        "INSERT INTO media_release (item_id, edition) VALUES (?, 'Standard')",
        (item_id,),
    )
    release_id: int = cursor.lastrowid  # type: ignore[assignment]

    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    path_id: int = cursor.lastrowid  # type: ignore[assignment]

    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, "
        "mtime_ns, ctime_ns, oshash, scan_generation, last_verified_at, "
        "enriched_at, deleted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'abc123', 1, ?, ?, NULL)",
        (release_id, path_id, f"{title}.mkv", size_bytes, now, now, now, now),
    )
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, width, height, "
        "duration_ms, bitrate) "
        "VALUES (?, 0, 'video', ?, ?, ?, 6000000, 8000000)",
        (file_id, video_codec, width, height),
    )
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, "
        "is_atmos, is_default, forced) "
        "VALUES (?, 1, 'audio', 'aac', ?, ?, 0, 1, 0)",
        (file_id, audio_lang, audio_channels),
    )
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, lang, format, is_default, forced) "
        "VALUES (?, 2, 'subtitle', ?, 'srt', 0, 0)",
        (file_id, subtitle_lang),
    )

    abs_path = str(mount_path / rel_path)
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_disk', ?)",
        (item_id, f"uuid-{disk_id}"),
    )
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
        (item_id, abs_path),
    )

    conn.commit()
    return item_id, release_id, file_id


# ── 1. Help ─────────────────────────────────────────────────────────────────────


def test_analyze_help_exits_zero() -> None:
    """--help exits 0 and shows usage."""
    result = run_cli(["library-analyze", "--help"])
    assert result.exit_code == 0, result.output
    assert "Deep scan video files" in result.output


# ── 2. From-index path ──────────────────────────────────────────────────────────


def test_analyze_from_index_uses_db_streams(tmp_path, test_config) -> None:
    """--from-index reads media_stream rows from the DB (no ffprobe call)."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_analyze_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Test Movie (2024)",
        category_id="movies",
        kind="movie",
        video_codec="hevc",
        audio_lang="fra",
    )
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "--format",
                "json",
                "library-analyze",
                "--from-index",
            ]
        )

    assert result.exit_code == 0, result.output
    assert "1 items" in result.output
    assert "1 files" in result.output
    assert "hevc=1" in result.output


def test_analyze_emits_summary_counts(tmp_path, test_config) -> None:
    """Seeding N items with different codecs → output has codec + audio distribution."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")

    _seed_analyze_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Movie HEVC (2024)",
        category_id="movies",
        kind="movie",
        video_codec="hevc",
        audio_lang="fra",
    )
    _seed_analyze_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Movie H264 (2023)",
        category_id="movies",
        kind="movie",
        video_codec="h264",
        audio_lang="eng",
        subtitle_lang="eng",
    )
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "--format",
                "json",
                "library-analyze",
                "--from-index",
            ]
        )

    assert result.exit_code == 0, result.output
    assert "2 items" in result.output
    assert "2 files" in result.output

    # Build a dict of codec→count and audio→count from the output.
    output = result.output
    assert "hevc=1" in output
    assert "h264=1" in output
    # Audio profiles: fra→vf, eng→vo (no French subtitles for eng item → vo)
    assert "vf=1" in output
    assert "vo=1" in output


# ── 3. Format JSON ──────────────────────────────────────────────────────────────


def test_analyze_format_json(tmp_path, test_config) -> None:
    """--format json does not crash library-analyze (output is Rich text)."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_analyze_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Format Test (2024)",
        category_id="movies",
        kind="movie",
    )
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "--format",
                "json",
                "library-analyze",
                "--from-index",
            ]
        )

    assert result.exit_code == 0, result.output
    assert len(result.output) > 0, "Expected non-empty output"
    assert "Analyzing library" in result.output


# ── 3. Errors ──


def test_analyze_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-analyze", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_analyze_db_path_none_exits_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → exit non-zero, no traceback."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-analyze", "--from-index"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_analyze_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-analyze", "--from-index"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_analyze_json_output_contains_expected_fields(tmp_path, test_config) -> None:
    """``--format json`` output contains analysis summary fields."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_analyze_item(conn, disk_id, tmp_path / "drive_a", title="Test (2024)", category_id="movies", kind="movie")
    conn.close()
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-analyze", "--from-index"])
    assert result.exit_code == 0
    assert len(result.output) > 0
    assert "items" in result.output.lower()


def test_analyze_error_exits_nonzero(tmp_path, test_config) -> None:
    """Corrupt DB with ``--from-index`` → non-zero exit code."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-analyze", "--from-index"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-analyze`` is a read-only diagnostic command.  It reads
# ``media_stream`` rows from the indexer database (via ``--from-index``)
# or invokes ffprobe on disk files, then prints a codec/audio/subtitle
# distribution summary.  No domain event is published.
