"""``library-duplicates-by-id``: read-only report of provider ids naming two rows or folders.

The output is codes and counts (no sentence); the database is opened ``mode=ro``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

from personalscraper.app.maintenance.registry import REGISTRY
from tests.commands._e2e_helpers import make_synthetic_db, run_cli


def _json_from(result: Any) -> dict[str, Any]:
    """Extract the last JSON object from CLI output (strips ANSI codes).

    Args:
        result: CliRunner result.

    Returns:
        The decoded payload.
    """
    raw = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    return json.loads(raw[raw.find("{") :])


def _seed_shared_tvdb(db_path: Path) -> None:
    """Seed a row with files and its 0-file phantom (tvdb 371572), and a movie copied on two disks.

    Args:
        db_path: Path of the migrated database.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u', 'Disk1', '/d', 1)")
    conn.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u2', 'Disk2', '/d2', 1)")
    ids = json.dumps({"tvdb": {"series_id": "371572", "episode_id": None}})
    for title in ("House of the Dragon (2022)", "House of the Dragon"):
        conn.execute(
            "INSERT INTO media_item(kind, title, title_sort, category_id, date_created, date_modified,"
            " external_ids_json) VALUES ('show', ?, ?, 'tv_shows', 0, 0, ?)",
            (title, title, ids),
        )
    conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1, 'series/House of the Dragon (2022)/Saison 01')")
    season = conn.execute("INSERT INTO season(item_id, number) VALUES (1, 1)").lastrowid
    episode = conn.execute("INSERT INTO episode(season_id, number) VALUES (?, 1)", (season,)).lastrowid
    release = conn.execute("INSERT INTO media_release(episode_id) VALUES (?)", (episode,)).lastrowid
    conn.execute(
        "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
        " scan_generation, last_verified_at) VALUES (?, 1, 'e01.mkv', 1, 1, '0', 1, 1)",
        (release,),
    )
    # A third row: one movie whose folder is copied whole on both disks (one row, two folders).
    movie_ids = json.dumps({"tmdb": {"series_id": "77", "episode_id": None}})
    conn.execute(
        "INSERT INTO media_item(kind, title, title_sort, year, category_id, date_created, date_modified,"
        " external_ids_json) VALUES ('movie', 'Enemy', 'Enemy', 2014, 'movies', 0, 0, ?)",
        (movie_ids,),
    )
    for disk_id in (1, 2):
        path_id = conn.execute(
            "INSERT INTO path(disk_id, rel_path) VALUES (?, 'films/Enemy (2014)')", (disk_id,)
        ).lastrowid
        movie_release = conn.execute("INSERT INTO media_release(item_id) VALUES (3)").lastrowid
        conn.execute(
            "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
            " scan_generation, last_verified_at) VALUES (?, ?, 'enemy.mkv', 1, 1, '0', 1, 1)",
            (movie_release, path_id),
        )
    conn.commit()
    conn.close()


def test_report_is_codes_and_counts(tmp_path: Path, test_config: Any) -> None:
    """The report counts groups, rows and empty rows and names each row by id."""
    db_path = make_synthetic_db(tmp_path)
    _seed_shared_tvdb(db_path)

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-duplicates-by-id", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert _json_from(result) == {
        "groups": 2,
        "rows": 3,
        "empty_rows": 1,
        "duplicates": [
            {
                "provider": "tmdb",
                "provider_id": "77",
                "kind": "movie",
                "rows": [{"item_id": 3, "live_files": 2, "folders": 2}],
            },
            {
                "provider": "tvdb",
                "provider_id": "371572",
                "kind": "show",
                "rows": [
                    {"item_id": 1, "live_files": 1, "folders": 1},
                    {"item_id": 2, "live_files": 0, "folders": 0},
                ],
            },
        ],
    }


def test_report_writes_nothing(tmp_path: Path, test_config: Any) -> None:
    """The command leaves the database byte-identical (opened read only)."""
    db_path = make_synthetic_db(tmp_path)
    _seed_shared_tvdb(db_path)
    before = db_path.read_bytes()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        run_cli(["--format", "json", "library-duplicates-by-id", "--db", str(db_path)])

    assert db_path.read_bytes() == before


def test_action_is_registered_read_only() -> None:
    """The maintenance registry lists the action as a read-only query."""
    (action,) = [a for a in REGISTRY if a.id == "library-duplicates-by-id"]
    assert (action.risk, action.category) == ("ro", "query")
