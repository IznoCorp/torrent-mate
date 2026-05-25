"""Regression tests for ``library-fix-season-counts`` repair CLI.

Covers:
- End-to-end repair of drifted ``season.episode_count`` values.
- Idempotence: re-running after a successful pass reports 0 fixes.
- Dry-run: reports ``would_fix`` without mutating the DB.
- Coherent seasons are left untouched (control rows).
- Empty seasons (0 episodes) with stale ``episode_count`` are corrected to 0.

Seeds an on-disk migrated DB via :func:`_e2e_helpers.make_synthetic_db`,
invokes the Typer CLI via :func:`_e2e_helpers.run_cli`, and asserts the
JSON output schema and DB state after each operation.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.commands._e2e_helpers import make_synthetic_db, run_cli


def _json_from_result(result: Any) -> dict[str, Any]:
    r"""Extract a JSON dict from CliRunner result output, stripping Rich escapes.

    The emit() output is pretty-printed JSON where the top-level ``{`` sits at
    column 0 on its own line. Inner ``{`` characters (e.g. detail dicts) are
    indented so ``\n{`` at column 0 reliably identifies the top-level opening
    brace. Falls back to a simple ``rfind("{")`` for compact (single-line) output.
    """
    raw: str = result.output.strip()
    import re

    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    pos = clean.rfind("\n{")
    if pos == -1:
        pos = clean.rfind("{")
    if pos == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[pos + 1 :] if clean[pos] == "\n" else clean[pos:])


def _seed_show_with_seasons(conn: sqlite3.Connection) -> None:
    """Seed a show with 3 seasons and episodes, 2 of them with drifted episode_count.

    Creates:
    - 1 ``media_item`` (kind='show').
    - Season 1: episode_count=2 but actually 3 episodes (drifted).
    - Season 2: episode_count=5, 5 episodes (coherent).
    - Season 3: episode_count=5 but 0 episodes (drifted).
    """
    now = 1700000000

    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'Test Show', 'Test Show', 'tv_shows', '{}', 'tvdb', ?, ?)",
        (now, now),
    )
    item_id = cur.lastrowid

    # Season 1: drifted — says 2, actually 3 episodes.
    cur = conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, 1, 2, 0, 0)",
        (item_id,),
    )
    s1_id = cur.lastrowid
    for ep_num in range(1, 4):
        conn.execute(
            "INSERT INTO episode (season_id, number, title) VALUES (?, ?, ?)",
            (s1_id, ep_num, f"Episode {ep_num}"),
        )

    # Season 2: coherent — 5 episodes, episode_count=5.
    cur = conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, 2, 5, 0, 0)",
        (item_id,),
    )
    s2_id = cur.lastrowid
    for ep_num in range(1, 6):
        conn.execute(
            "INSERT INTO episode (season_id, number, title) VALUES (?, ?, ?)",
            (s2_id, ep_num, f"Episode {ep_num}"),
        )

    # Season 3: drifted — says 5, actually 0 episodes.
    conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, 3, 5, 0, 0)",
        (item_id,),
    )

    conn.commit()


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------


def test_drifted_season_count_is_fixed(tmp_path: Path, test_config: Any) -> None:
    """--apply corrects drifted episode_counts to match actual COUNT(*) of episodes."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_show_with_seasons(conn)
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-season-counts", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["seasons_scanned"] == 3
    assert data["fixed"] == 2, f"Expected 2 fixed seasons, got {data}"

    # Verify DB state.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    s1 = conn.execute("SELECT episode_count FROM season WHERE number=1").fetchone()
    assert s1 is not None
    assert s1["episode_count"] == 3, f"Season 1 not fixed: episode_count={s1['episode_count']}"

    s2 = conn.execute("SELECT episode_count FROM season WHERE number=2").fetchone()
    assert s2 is not None
    assert s2["episode_count"] == 5, f"Season 2 changed: episode_count={s2['episode_count']}"

    s3 = conn.execute("SELECT episode_count FROM season WHERE number=3").fetchone()
    assert s3 is not None
    assert s3["episode_count"] == 0, f"Season 3 not fixed: episode_count={s3['episode_count']}"

    conn.close()


# ---------------------------------------------------------------------------
# Coherent control
# ---------------------------------------------------------------------------


def test_coherent_season_is_left_alone(tmp_path: Path, test_config: Any) -> None:
    """Seasons whose episode_count already matches COUNT(*) are untouched."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_show_with_seasons(conn)

    # Pre-fix the drifted counts so all seasons are coherent.
    conn.execute("UPDATE season SET episode_count = 3 WHERE number = 1")
    conn.execute("UPDATE season SET episode_count = 0 WHERE number = 3")
    conn.commit()
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-season-counts", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["fixed"] == 0, f"Expected 0 fixed, got {data}"


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def test_dry_run_does_not_mutate(tmp_path: Path, test_config: Any) -> None:
    """Dry-run reports would_fix and details without changing episode_count."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_show_with_seasons(conn)

    # Snapshot before dry-run.
    before = {
        r["number"]: r["episode_count"]
        for r in conn.execute("SELECT number, episode_count FROM season ORDER BY number").fetchall()
    }
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-season-counts", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["apply"] is False
    assert data["seasons_scanned"] == 3
    assert data["would_fix"] == 2, f"Expected 2 would_fix, got {data}"

    # Verify details contain the expected drift entries.
    details_by_number = {(d["number"], d["old_count"], d["actual_count"]) for d in data["details"]}
    assert (1, 2, 3) in details_by_number, f"Missing season 1 drift detail: {details_by_number}"
    assert (3, 5, 0) in details_by_number, f"Missing season 3 drift detail: {details_by_number}"

    # DB must be unchanged.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    after = {
        r["number"]: r["episode_count"]
        for r in conn.execute("SELECT number, episode_count FROM season ORDER BY number").fetchall()
    }
    conn.close()

    assert before == after, f"Dry-run mutated season rows: {before} -> {after}"


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


def test_idempotent_re_run(tmp_path: Path, test_config: Any) -> None:
    """Second repair pass reports 0 fixed after first pass corrected everything."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_show_with_seasons(conn)
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result1 = run_cli(["--format", "json", "library-fix-season-counts", "--db", str(db_path), "--apply"])
        assert result1.exit_code == 0, result1.output
        data1 = _json_from_result(result1)
        assert data1["fixed"] == 2, f"First pass: expected 2, got {data1}"

        result2 = run_cli(["--format", "json", "library-fix-season-counts", "--db", str(db_path), "--apply"])
        assert result2.exit_code == 0, result2.output
        data2 = _json_from_result(result2)
        assert data2["fixed"] == 0, f"Second pass: expected 0, got {data2}"


# ---------------------------------------------------------------------------
# Empty season → 0
# ---------------------------------------------------------------------------


def test_empty_season_episode_count_zero(tmp_path: Path, test_config: Any) -> None:
    """Season with 0 episodes and episode_count=5 is corrected to 0."""
    db_path = make_synthetic_db(tmp_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = 1700000000

    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'Empty Show', 'Empty Show', 'tv_shows', '{}', 'tvdb', ?, ?)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (1, 1, 5, 0, 0)",
    )
    conn.commit()
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-fix-season-counts", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, result.output
    data = _json_from_result(result)
    assert data["fixed"] == 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    row = conn.execute("SELECT episode_count FROM season WHERE number=1").fetchone()
    assert row is not None
    assert row["episode_count"] == 0
    conn.close()
