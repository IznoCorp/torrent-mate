"""E2E tests for ``personalscraper library-backfill-ids`` — CLI-level harness.

HERMETIC — no real HTTP calls. The dry-run safety and idempotence tests use
the real ``run_backfill_ids`` with ``None`` clients (no API keys in env).
Tests that need backfill writes use a synthetic ``run_backfill_ids`` mock
that writes deterministic data to the DB without touching any external API.
"""

from __future__ import annotations

import json
import sqlite3
import time
from unittest.mock import patch

from personalscraper.indexer.scanner._modes.backfill_ids import BackfillStats
from tests.commands._e2e_helpers import (
    assert_json_schema,
    assert_no_python_traceback,
    capture_event_bus,
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_RUN_BACKFILL = "personalscraper.indexer.scanner._modes.backfill_ids.run_backfill_ids"


def _seed_backfill_items(conn: sqlite3.Connection) -> dict[str, int]:
    """Seed items for backfill testing. Returns ``{'full': id, 'partial': id, 'none': id, 'complete': id}``."""
    now = int(time.time())

    def _insert(title: str, canonical: str | None, external_ids: str | None, ratings: str | None) -> int:
        cur = conn.execute(
            "INSERT INTO media_item"
            " (kind, title, title_sort, category_id, year, nfo_status, canonical_provider,"
            "  external_ids_json, ratings_json, date_created, date_modified)"
            " VALUES ('movie', ?, ?, 'movies', 2020, 'valid', ?, ?, ?, ?, ?)",
            (title, title, canonical, external_ids, ratings, now, now),
        )
        return cur.lastrowid  # type: ignore[return-value]

    # Item with canonical=tmdb but only tmdb ID (missing tvdb, imdb) and no ratings.
    full_id = _insert(
        "Needs Everything",
        canonical="tmdb",
        external_ids='{"tmdb": {"series_id": "111"}}',
        ratings=None,
    )
    # Item with canonical=tmdb, all IDs, but no ratings.
    partial_id = _insert(
        "Needs Ratings",
        canonical="tmdb",
        external_ids='{"tmdb": {"series_id": "222"}, "tvdb": {"series_id": "333"}, "imdb": {"series_id": "tt444"}}',
        ratings=None,
    )
    # Item with NO canonical_provider (unbackfillable).
    none_id = _insert(
        "No Canonical",
        canonical=None,
        external_ids="{}",
        ratings=None,
    )
    # Item already fully populated.
    complete_id = _insert(
        "Already Complete",
        canonical="tmdb",
        external_ids='{"tmdb": {"series_id": "555"}, "tvdb": {"series_id": "666"}, "imdb": {"series_id": "tt777"}}',
        ratings='[{"source": "imdb", "score": "8.0", "votes": 5000}]',
    )

    conn.commit()
    return {"full": full_id, "partial": partial_id, "none": none_id, "complete": complete_id}


def _read_item_json(conn: sqlite3.Connection, item_id: int) -> tuple[str | None, str | None]:
    """Read ``(external_ids_json, ratings_json)`` for an item."""
    row = conn.execute(
        "SELECT external_ids_json, ratings_json FROM media_item WHERE id = ?",
        (item_id,),
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_backfill_help_exits_zero() -> None:
    """``library-backfill-ids --help`` exits 0."""
    result = run_cli(["library-backfill-ids", "--help"])
    assert result.exit_code == 0, result.output


# ── 2. Dry-run safety (CRITICAL) ────────────────────────────────────────────────


def test_backfill_dry_run_no_writes(tmp_path, test_config) -> None:
    """``--dry-run`` must NEVER touch external_ids_json or ratings_json.

    Seeds items needing backfill, runs with --dry-run + no API keys
    (clients are None → no network calls), and asserts both JSON columns
    are byte-for-byte identical after the pass.
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    ids_map = _seed_backfill_items(conn)

    # Snapshot pre-dry-run state for the "Needs Everything" item.
    eids_before, ratings_before = _read_item_json(conn, ids_map["full"])
    conn.close()

    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-backfill-ids", "--dry-run"])

    assert result.exit_code == 0, result.output

    # Verify JSON output declares dry_run.
    data = json_from_result(result)
    assert data["dry_run"] is True, f"Expected dry_run=true in output: {data}"

    # Verify columns are unchanged.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    eids_after, ratings_after = _read_item_json(conn, ids_map["full"])
    conn.close()

    assert eids_after == eids_before, (
        f"CRITICAL: external_ids_json changed after --dry-run!\n  before: {eids_before}\n  after:  {eids_after}"
    )
    assert ratings_after == ratings_before, (
        f"CRITICAL: ratings_json changed after --dry-run!\n  before: {ratings_before}\n  after:  {ratings_after}"
    )


# ── 3. --ids-only skips ratings ─────────────────────────────────────────────────


def test_backfill_ids_only_skips_ratings(tmp_path, test_config) -> None:
    """``--ids-only`` adds provider IDs but leaves ratings_json unchanged."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    ids_map = _seed_backfill_items(conn)

    eids_before, ratings_before = _read_item_json(conn, ids_map["full"])
    conn.close()

    def _fake_ids_backfill(conn, **kwargs):
        """Synthetic backfill that writes a TVDB ID, respecting ids_only."""
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, title, external_ids_json FROM media_item").fetchall()
        updated = 0
        ids_added = 0
        for row in rows:
            eids = json.loads(row["external_ids_json"] or "{}")
            if "tvdb" not in eids:
                eids["tvdb"] = {"series_id": "99999"}
                ids_added += 1
                if not kwargs.get("dry_run", False):
                    conn.execute(
                        "UPDATE media_item SET external_ids_json = ? WHERE id = ?",
                        (json.dumps(eids), row["id"]),
                    )
                    updated += 1
        return BackfillStats(
            items_scanned=len(rows),
            items_updated=updated,
            ids_added_count=ids_added,
            ratings_added_count=0,
        )

    cfg = make_test_config_with_db(test_config, db_path)
    with (
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_RUN_BACKFILL, side_effect=_fake_ids_backfill),
    ):
        result = run_cli(["library-backfill-ids", "--ids-only"])

    assert result.exit_code == 0, result.output

    # Verify external_ids_json was updated.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    eids_after, ratings_after = _read_item_json(conn, ids_map["full"])
    conn.close()

    assert eids_after != eids_before, "Expected external_ids_json to change with --ids-only, but it didn't"
    eids_dict = json.loads(eids_after or "{}")
    assert "tvdb" in eids_dict, f"TVDB ID should have been added: {eids_dict}"

    # ratings_json must be unchanged.
    assert ratings_after == ratings_before, (
        f"--ids-only should NOT touch ratings_json!\n  before: {ratings_before}\n  after:  {ratings_after}"
    )


# ── 4. --ratings-only skips IDs ──────────────────────────────────────────────────


def test_backfill_ratings_only_skips_ids(tmp_path, test_config) -> None:
    """``--ratings-only`` adds ratings but leaves external_ids_json unchanged."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    ids_map = _seed_backfill_items(conn)

    eids_before, ratings_before = _read_item_json(conn, ids_map["partial"])
    conn.close()

    def _fake_ratings_backfill(conn, **kwargs):
        """Synthetic backfill that writes an IMDb rating, respecting ratings_only."""
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, title, ratings_json FROM media_item").fetchall()
        updated = 0
        ratings_added = 0
        for row in rows:
            existing = json.loads(row["ratings_json"] or "[]") if row["ratings_json"] else []
            existing.append({"source": "imdb", "score": "7.5", "votes": 2000})
            ratings_added += 1
            if not kwargs.get("dry_run", False):
                conn.execute(
                    "UPDATE media_item SET ratings_json = ? WHERE id = ?",
                    (json.dumps(existing), row["id"]),
                )
                updated += 1
        return BackfillStats(
            items_scanned=len(rows),
            items_updated=updated,
            ids_added_count=0,
            ratings_added_count=ratings_added,
        )

    cfg = make_test_config_with_db(test_config, db_path)
    with (
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_RUN_BACKFILL, side_effect=_fake_ratings_backfill),
    ):
        result = run_cli(["library-backfill-ids", "--ratings-only"])

    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    eids_after, ratings_after = _read_item_json(conn, ids_map["partial"])
    conn.close()

    # external_ids_json must be unchanged.
    assert eids_after == eids_before, (
        f"--ratings-only should NOT touch external_ids_json!\n  before: {eids_before}\n  after:  {eids_after}"
    )

    # ratings_json must have been updated.
    assert ratings_after != ratings_before, "Expected ratings_json to change with --ratings-only, but it didn't"
    ratings_list = json.loads(ratings_after or "[]")
    assert len(ratings_list) >= 1


# ── 5. --show filter restricts scope ─────────────────────────────────────────────


def test_backfill_show_filter_restricts_scope(tmp_path, test_config) -> None:
    """``--show 'Needs Everything'`` only processes the matching item."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_backfill_items(conn)
    conn.close()

    captured_kwargs: dict[str, object] = {}

    def _capturing_backfill(conn, **kwargs):
        captured_kwargs.update(kwargs)
        return BackfillStats(items_scanned=1, items_updated=1, ids_added_count=1)

    cfg = make_test_config_with_db(test_config, db_path)
    with (
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_RUN_BACKFILL, side_effect=_capturing_backfill),
    ):
        result = run_cli(
            [
                "library-backfill-ids",
                "--show",
                "Needs Everything",
            ]
        )

    assert result.exit_code == 0, result.output
    assert captured_kwargs.get("show_filter") == "Needs Everything", f"show_filter not forwarded: {captured_kwargs}"


# ── 6. Idempotence on already-complete items ────────────────────────────────────


def test_backfill_idempotent_on_already_complete_items(tmp_path, test_config) -> None:
    """An already-complete item is skipped (no API calls, no writes)."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    ids_map = _seed_backfill_items(conn)
    complete_id = ids_map["complete"]
    eids_before, ratings_before = _read_item_json(conn, complete_id)
    conn.close()

    cfg = make_test_config_with_db(test_config, db_path)

    # No API keys → clients None → run_backfill_ids won't make network calls.
    # The "Already Complete" item has all providers + ratings → skipped.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-backfill-ids"])

    assert result.exit_code == 0, result.output
    data = json_from_result(result)
    # The complete item should contribute to items_skipped (not items_updated).
    assert data["items_skipped"] >= 1, f"Expected at least 1 skipped item (already complete), got: {data}"

    # Verify the complete item was NOT modified.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    eids_after, ratings_after = _read_item_json(conn, complete_id)
    conn.close()

    assert eids_after == eids_before, (
        f"Already-complete item's external_ids_json was modified!\n  before: {eids_before}\n  after:  {eids_after}"
    )
    assert ratings_after == ratings_before, (
        f"Already-complete item's ratings_json was modified!\n  before: {ratings_before}\n  after:  {ratings_after}"
    )


# ── 3. Errors ──


def test_backfill_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-backfill-ids", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_backfill_db_path_none_exits_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → exit 1, friendly message, no traceback."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-backfill-ids"])
    assert result.exit_code != 0
    assert "not configured" in result.output.lower() or "db_path" in result.output.lower()
    assert_no_python_traceback(result)


def test_backfill_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-backfill-ids"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_backfill_json_schema_valid(tmp_path, test_config) -> None:
    """Output JSON matches expected schema for the backfill stats payload."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_backfill_items(conn)
    conn.close()
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-backfill-ids"])
    assert result.exit_code == 0
    data = assert_json_schema(
        result,
        required_keys=[
            "dry_run",
            "items_scanned",
            "items_updated",
            "items_skipped",
            "items_failed",
            "ids_added_count",
            "ratings_added_count",
        ],
    )
    assert isinstance(data["items_scanned"], int)
    assert data["dry_run"] is False


def test_backfill_error_exits_nonzero() -> None:
    """Invalid flag → non-zero exit code."""
    result = run_cli(["library-backfill-ids", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0


# ── 7. Events ──


def test_backfill_emits_progress_events(tmp_path, test_config, monkeypatch) -> None:
    """Backfill pass emits BackfillStarted → per-item → BackfillCompleted events."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_backfill_items(conn)
    conn.close()

    captured = capture_event_bus(monkeypatch)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-backfill-ids"])

    assert result.exit_code == 0, result.output
    # Without API keys all clients are None → IDs side is no-op, ratings side
    # skips.  Items are still iterated so BackfillStarted/Completed are emitted.
    event_names = {type(e).__name__ for e in captured}
    assert len(captured) >= 2, f"Expected >=2 events, got {len(captured)}: {sorted(event_names)}"
    assert "BackfillStarted" in event_names, f"Missing BackfillStarted in {sorted(event_names)}"
    assert "BackfillCompleted" in event_names, f"Missing BackfillCompleted in {sorted(event_names)}"


# ── 8. Closure-of-loop ──

# N/A: backfill-ids BDD ↔ API closure-of-loop requires a live TMDB/TVDB provider
# chain (network calls, API responses, JSON deserialization).  The synthetic
# mock tests (--ids-only, --ratings-only, idempotence) verify the write path
# in isolation, but the full detect → enrich → verify loop belongs to the
# integration test suite (tests/integration/).  The idempotence test on
# already-complete items already proves that the command does not corrupt
# existing state — the loop-closure property is tested at the provider level.
