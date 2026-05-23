"""E2E tests for ``personalscraper library-recommend`` — CLI-level harness.

Tests the --from-index path (DB-backed analysis inline), JSON file output,
config-preference-driven recommendations, and idempotent re-runs.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
    seed_disk,
)


def _seed_recommend_item(
    conn: sqlite3.Connection,
    disk_id: int,
    mount_path: Path,
    title: str,
    category_id: str,
    kind: str,
    video_codec: str = "h264",
    size_bytes: int = 5_000_000_000,
    audio_lang: str = "fra",
) -> tuple[int, int, int]:
    """Seed a complete item chain for recommend testing.

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
        "VALUES (?, 0, 'video', ?, 1920, 1080, 6000000, 8000000)",
        (file_id, video_codec),
    )
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang, channels, "
        "is_atmos, is_default, forced) "
        "VALUES (?, 1, 'audio', 'aac', ?, 6, 0, 1, 0)",
        (file_id, audio_lang),
    )
    conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, lang, format, is_default, forced) "
        "VALUES (?, 2, 'subtitle', 'fra', 'srt', 0, 0)",
        (file_id,),
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


_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── 1. Help ─────────────────────────────────────────────────────────────────────


def test_recommend_help_exits_zero() -> None:
    """--help exits 0 and shows usage."""
    result = run_cli(["library-recommend", "--help"])
    assert result.exit_code == 0, result.output
    assert "re-download" in result.output.lower()


# ── 2. JSON output path ─────────────────────────────────────────────────────────


def test_recommend_writes_json_to_default_output_path(tmp_path, test_config) -> None:
    """library-recommend --from-index writes library_recommendations.json to data_dir."""
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_recommend_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Overcoded Movie (2024)",
        category_id="movies",
        kind="movie",
        video_codec="h264",
        size_bytes=6_000_000_000,
    )
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "library-recommend",
                "--from-index",
            ]
        )

    assert result.exit_code == 0, result.output
    json_path = data_dir / "library_recommendations.json"
    assert json_path.exists(), f"Expected {json_path} to exist"
    data = json.loads(json_path.read_text())
    assert "total_recommendations" in data
    assert "estimated_total_savings_gb" in data
    assert "items" in data


# ── 3. Preferences respect ──────────────────────────────────────────────────────


def test_recommend_respects_config_preferences(tmp_path, test_config) -> None:
    """Seed items with h264 + oversized → recommendations match preferences."""
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_recommend_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Old Codec (2024)",
        category_id="movies",
        kind="movie",
        video_codec="h264",
        size_bytes=6_000_000_000,
    )
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "library-recommend",
                "--from-index",
            ]
        )

    assert result.exit_code == 0, result.output
    json_path = data_dir / "library_recommendations.json"
    data = json.loads(json_path.read_text())
    assert data["total_recommendations"] >= 1, f"No recommendations found: {data}"
    recs = data["items"]
    assert len(recs) >= 1

    # Default prefs: preferred_codec=hevc, fallback=["av1"], rejected=["mpeg2","mpeg4"]
    # h264 is non-preferred, not in fallback → flagged as "Non-preferred codec h264"
    h264_recs = [r for r in recs if r["current"]["codec"] == "h264"]
    assert len(h264_recs) >= 1, f"No h264 recommendations: {recs}"
    rec = h264_recs[0]
    assert rec["target"]["codec"] == "hevc", f"Expected target codec 'hevc', got {rec['target']}"
    reasons_str = "; ".join(rec["reasons"])
    assert "h264" in reasons_str.lower() or "hevc" in reasons_str.lower(), (
        f"Expected reasons to mention codec: {reasons_str}"
    )


# ── 4. Idempotence ──────────────────────────────────────────────────────────────


def test_recommend_idempotent(tmp_path, test_config) -> None:
    """Two consecutive recommend invocations produce the same JSON."""
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    disk_id = seed_disk(conn, "drive_a", tmp_path / "drive_a")
    _seed_recommend_item(
        conn,
        disk_id,
        tmp_path / "drive_a",
        title="Idempotent Test (2024)",
        category_id="movies",
        kind="movie",
        video_codec="h264",
        size_bytes=6_000_000_000,
    )
    conn.close()

    json_path = data_dir / "library_recommendations.json"

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["library-recommend", "--from-index"])
        assert r1.exit_code == 0, r1.output
        data1 = json.loads(json_path.read_text())

        r2 = run_cli(["library-recommend", "--from-index"])
        assert r2.exit_code == 0, r2.output
        data2 = json.loads(json_path.read_text())

    # generated_at differs, compare stable fields only.
    assert data1["total_recommendations"] == data2["total_recommendations"]
    assert data1["estimated_total_savings_gb"] == data2["estimated_total_savings_gb"]
    assert len(data1["items"]) == len(data2["items"])
    for rec1, rec2 in zip(data1["items"], data2["items"]):
        assert rec1["title"] == rec2["title"]
        assert rec1["priority"] == rec2["priority"]
        assert rec1["reasons"] == rec2["reasons"]
