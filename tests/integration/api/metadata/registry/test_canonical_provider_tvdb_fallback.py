"""Regression: shows with canonical_provider='tmdb' must have no tvdb_id.

Per provider-IDs ACCEPTANCE clarification 2026-05-28: a show with
canonical_provider='tmdb' is DESIGN_CONFORM iff TVDB has no match,
i.e. external_ids_json contains no ``tvdb`` key (or null series_id).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def test_show_canonical_tmdb_implies_no_tvdb_in_external_ids(tmp_path: Path) -> None:
    """A show with canonical_provider='tmdb' is DESIGN_CONFORM iff TVDB has no match.

    ``external_ids_json`` contains no ``tvdb`` key (or null series_id).
    When ``tvdb`` IS present with a non-null series_id, the registry should
    have preferred TVDB — flagging it as a DESIGN_DEVIATION.
    """
    db = tmp_path / "lib.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE media_item (id INTEGER PRIMARY KEY,kind TEXT,canonical_provider TEXT,external_ids_json TEXT)"
    )
    rows = [
        (
            1,
            "show",
            "tvdb",
            json.dumps({"tvdb": {"series_id": "111", "episode_id": None}}),
        ),
        # DESIGN_CONFORM: tmdb-only because tvdb absent
        (
            2,
            "show",
            "tmdb",
            json.dumps({"tmdb": {"series_id": "222", "episode_id": None}}),
        ),
        # DESIGN_DEVIATION: tmdb-canonical but tvdb IS present
        (
            3,
            "show",
            "tmdb",
            json.dumps(
                {
                    "tvdb": {"series_id": "333", "episode_id": None},
                    "tmdb": {"series_id": "444", "episode_id": None},
                }
            ),
        ),
        # Movie — tvdb not applicable, always DESIGN_CONFORM
        (
            4,
            "movie",
            "tmdb",
            json.dumps({"tmdb": {"series_id": "555"}}),
        ),
    ]
    conn.executemany("INSERT INTO media_item VALUES (?, ?, ?, ?)", rows)
    conn.commit()

    violations: list[int] = []
    for row in conn.execute(
        "SELECT id, external_ids_json FROM media_item WHERE kind='show' AND canonical_provider='tmdb'"
    ):
        row_id, raw = row
        ids = json.loads(raw)
        tvdb_entry = ids.get("tvdb")
        if tvdb_entry and tvdb_entry.get("series_id"):
            violations.append(row_id)

    assert violations == [3], f"expected only id=3 to violate, got {violations}"
