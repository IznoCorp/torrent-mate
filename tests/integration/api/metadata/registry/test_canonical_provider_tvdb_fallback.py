"""Regression: shows with canonical_provider='tmdb' must have no tvdb_id.

Per provider-IDs ACCEPTANCE clarification 2026-05-28: a show with
canonical_provider='tmdb' is DESIGN_CONFORM iff TVDB has no match,
i.e. external_ids_json contains no ``tvdb`` key (or null series_id).

Enforced by ``_SHOWS_COUNT_SQL`` / ``_SHOWS_REPAIR_SQL`` in
``personalscraper/commands/library/fix_canonical_provider.py`` (the
``library-fix-canonical-provider`` CLI tool) AND by the
``pipeline-bdd-validator`` agent v2.3 as a read-only audit.
This test pins the SQL implementation.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path

from personalscraper.commands.library.fix_canonical_provider import _SHOWS_COUNT_SQL


def test_show_canonical_tmdb_implies_no_tvdb_in_external_ids(tmp_path: Path) -> None:
    """A show with canonical_provider='tmdb' is DESIGN_CONFORM iff TVDB has no match.

    ``external_ids_json`` contains no ``tvdb`` key (or null series_id).
    When ``tvdb`` IS present with a non-null series_id, the registry should
    have preferred TVDB — flagging it as a DESIGN_DEVIATION.

    The assertion uses the production ``_SHOWS_COUNT_SQL`` directly rather
    than re-implementing the rule in Python, so drift in the SQL is caught.
    """
    db = tmp_path / "lib.db"
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
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
            # Edge case: explicit JSON null — IS NOT NULL correctly excludes
            # (json_extract returns SQL NULL for JSON null).
            (
                5,
                "show",
                "tmdb",
                json.dumps({"tvdb": {"series_id": None, "episode_id": None}}),
            ),
            # Edge case: tvdb key without series_id field — json_extract
            # returns SQL NULL for a missing key, so IS NOT NULL excludes it.
            (
                6,
                "show",
                "tmdb",
                json.dumps({"tvdb": {}}),
            ),
            # Edge case: empty string series_id — IS NOT NULL is TRUE for
            # the empty string, so production SQL DOES count this row as a
            # violation. This is a known design quirk (Python falsy-check
            # would exclude it, but the SQL rule is purely IS NOT NULL).
            (
                7,
                "show",
                "tmdb",
                json.dumps({"tvdb": {"series_id": "", "episode_id": None}}),
            ),
            # Edge case: movie with tvdb entry — WHERE kind='show' excludes it
            (
                8,
                "movie",
                "tmdb",
                json.dumps({"tvdb": {"series_id": "999", "episode_id": None}}),
            ),
        ]
        conn.executemany("INSERT INTO media_item VALUES (?, ?, ?, ?)", rows)
        conn.commit()

        count = conn.execute(_SHOWS_COUNT_SQL).fetchone()[0]

    # Expected: row 3 (series_id="333") + row 7 (series_id="" — empty string
    # passes IS NOT NULL) = 2. Rows 5 (null), 6 (no field), 8 (movie) excluded.
    assert count == 2, f"expected 2 violations, got {count}"
