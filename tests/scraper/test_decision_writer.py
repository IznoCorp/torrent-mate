"""Unit tests for :class:`DecisionWriter` (scrape-arbiter feature).

Covers the scenarios required by DESIGN §4 and sub-phase 1.3 plan:

- ``upsert`` → row present with pending status and epoch timestamps.
- NFC dedup — same path in NFD form updates the SAME row (no duplicate).
- Refresh pending — ``candidates_json``, ``run_uid``, ``updated_at`` updated.
- Non-resurrection — a dismissed row is never revived by upsert.
- ``mark_superseded_orphans`` → rows with missing paths become superseded.
- ``resolve`` → status resolved, ``resolution_json`` set, ``resolved_at`` set.
- ``dismiss`` → status dismissed, ``updated_at`` refreshed.
- Fail-soft: a broken DB path never raises — the method logs a warning and returns.

The DB is created from the **real** migration file
``personalscraper/indexer/migrations/013_scrape_decision.sql`` via
``executescript``, mirroring the ``test_pipeline_history.py`` convention.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from pathlib import Path

import pytest

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.scraper.decision_writer import DecisionWriteError, DecisionWriter

# ---------------------------------------------------------------------------
# Path to the real migration artefact
# ---------------------------------------------------------------------------

_MIGRATION_013 = (
    Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations" / "013_scrape_decision.sql"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_db(db_path: Path) -> None:
    """Create a SQLite DB with the ``scrape_decision`` table from the real migration.

    The migration 013 script inserts into ``schema_version``, so the helper
    creates that table first, then runs the full migration via ``executescript``.

    Args:
        db_path: Path to the on-disk SQLite database file to create.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.commit()
    migration_sql = _MIGRATION_013.read_text(encoding="utf-8")
    conn.executescript(migration_sql)
    conn.close()


def _select_row(db_path: Path, decision_id: int) -> dict | None:
    """Return the ``scrape_decision`` row as a dict, or ``None``.

    Args:
        db_path: Path to the SQLite database file.
        decision_id: Primary key of the row to fetch.

    Returns:
        A dict of column-name → value, or ``None`` if not found.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM scrape_decision WHERE id = ?", (decision_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _count_rows(db_path: Path, where: str = "", params: tuple = ()) -> int:
    """Return the number of rows in ``scrape_decision``, optionally filtered.

    Args:
        db_path: Path to the SQLite database file.
        where: Optional ``WHERE`` clause fragment (without the ``WHERE`` keyword).
        params: Query parameters for the ``WHERE`` clause.

    Returns:
        The row count.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    sql = "SELECT COUNT(*) FROM scrape_decision"
    if where:
        sql += f" WHERE {where}"
    count = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Tests — upsert
# ---------------------------------------------------------------------------


class TestDecisionWriterUpsert:
    """``upsert()`` tests."""

    def test_upsert_inserts_pending_row_with_epoch_timestamps(self, tmp_path: Path) -> None:
        """After ``upsert()`` a new row exists with ``status='pending'`` and epoch timestamps."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Inception (2010)"
        staging.mkdir(parents=True)
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Inception",
            extracted_year=2010,
            trigger="mid_band",
            candidates_json='[{"provider":"tmdb","provider_id":27205,"title":"Inception","year":2010,"score":0.85}]',
            run_uid="run-001",
        )

        assert _count_rows(db_path) == 1
        row = _select_row(db_path, 1)
        assert row is not None
        assert row["staging_path"] == str(staging)
        assert row["media_kind"] == "movie"
        assert row["extracted_title"] == "Inception"
        assert row["extracted_year"] == 2010
        assert row["trigger"] == "mid_band"
        assert row["status"] == "pending"
        assert row["run_uid"] == "run-001"
        assert row["created_at"] > 0
        assert row["updated_at"] > 0
        assert row["created_at"] == row["updated_at"]  # equal on insert
        assert row["resolution_json"] is None
        assert row["resolved_at"] is None

    def test_upsert_with_nullable_fields_none(self, tmp_path: Path) -> None:
        """``extracted_year=None`` and ``run_uid=None`` are stored as NULL."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Unknown Year"
        staging.mkdir(parents=True)
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Unknown Year",
            extracted_year=None,
            trigger="below_threshold",
            candidates_json="[]",
            run_uid=None,
        )

        row = _select_row(db_path, 1)
        assert row is not None
        assert row["extracted_year"] is None
        assert row["run_uid"] is None

    def test_upsert_nfc_dedup_same_row_no_duplicate(self, tmp_path: Path) -> None:
        """Same path supplied in NFD form updates the SAME row (NFC normalization)."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        # macOS filesystem uses NFD, so construct both forms explicitly.
        # "Pokémon" NFC = U+00E9 (LATIN SMALL LETTER E WITH ACUTE)
        # "Pokémon" NFD = "e" + U+0301 (COMBINING ACUTE ACCENT)
        nfc_name = "Pokémon"  # NFC — the normalised form the writer enforces
        nfd_name = unicodedata.normalize("NFD", nfc_name)  # NFD — what macFUSE yields
        assert nfc_name != nfd_name  # different code point sequences
        staging_nfc = tmp_path / "001-TVSHOWS" / nfc_name
        staging_nfc.mkdir(parents=True)

        # First upsert with NFC path.
        writer.upsert(
            staging_path=staging_nfc,
            media_kind="tvshow",
            extracted_title=nfc_name,
            extracted_year=2020,
            trigger="ambiguous",
            candidates_json='[{"provider":"tvdb","provider_id":100,"title":"Pokemon","year":2020,"score":0.82}]',
            run_uid="run-001",
        )
        assert _count_rows(db_path) == 1

        # Second upsert with NFD path — must update the SAME row, not insert a new one.
        # Use the full path so that NFC normalization produces the same stored value.
        staging_nfd = tmp_path / "001-TVSHOWS" / nfd_name
        writer.upsert(
            staging_path=staging_nfd,  # NFD form — writer normalizes to NFC internally
            media_kind="tvshow",
            extracted_title=nfd_name,
            extracted_year=2020,
            trigger="mid_band",
            candidates_json='[{"provider":"tvdb","provider_id":999,"title":"Pokemon","year":2020,"score":0.75}]',
            run_uid="run-002",
        )
        assert _count_rows(db_path) == 1  # still one row, no duplicate

        row = _select_row(db_path, 1)
        assert row["run_uid"] == "run-002"  # refreshed
        assert row["trigger"] == "mid_band"  # refreshed

    def test_upsert_refreshes_pending_row(self, tmp_path: Path) -> None:
        """Calling ``upsert()`` on an existing pending row refreshes its fields."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Refresh Test"
        staging.mkdir(parents=True)

        # Initial insert.
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Old Title",
            extracted_year=1999,
            trigger="below_threshold",
            candidates_json='[{"provider":"tmdb","provider_id":1,"title":"Old","year":1999,"score":0.3}]',
            run_uid="run-old",
        )
        row1 = _select_row(db_path, 1)
        created_at_1 = row1["created_at"]
        updated_at_1 = row1["updated_at"]
        assert row1["candidates_json"].startswith('[{"provider":"tmdb","provider_id":1')

        # Refresh with new data.
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="New Title",
            extracted_year=2000,
            trigger="mid_band",
            candidates_json='[{"provider":"tmdb","provider_id":2,"title":"New","year":2000,"score":0.7}]',
            run_uid="run-new",
        )
        row2 = _select_row(db_path, 1)
        assert row2["created_at"] == created_at_1  # unchanged
        assert row2["updated_at"] >= updated_at_1  # refreshed
        # Only candidates_json, trigger, run_uid, updated_at are refreshed
        # per DESIGN §4 — extracted_title/media_kind/extracted_year stay unchanged.
        assert row2["extracted_title"] == "Old Title"  # NOT refreshed
        assert row2["trigger"] == "mid_band"  # refreshed
        assert row2["run_uid"] == "run-new"
        assert row2["status"] == "pending"


class TestDecisionWriterUpsertNonResurrection:
    """``upsert()`` must never resurrect a non-pending row."""

    def test_upsert_does_not_resurrect_dismissed_row(self, tmp_path: Path) -> None:
        """A dismissed row is NOT revived — status stays dismissed, candidates unchanged."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Dismissed Movie"
        staging.mkdir(parents=True)

        # Insert, then dismiss.
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Dismissed Movie",
            extracted_year=2021,
            trigger="mid_band",
            candidates_json='[{"provider":"tmdb","provider_id":100,"title":"Dismissed Movie","year":2021,"score":0.6}]',
            run_uid="run-001",
        )
        writer.dismiss(1)

        # Verify dismissed.
        row = _select_row(db_path, 1)
        assert row["status"] == "dismissed"
        original_candidates = row["candidates_json"]

        # Try to upsert again — must NOT resurrect.
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Dismissed Movie (Revived)",
            extracted_year=2021,
            trigger="ambiguous",
            candidates_json='[{"provider":"tmdb","provider_id":999,"title":"Revived","year":2021,"score":0.9}]',
            run_uid="run-002",
        )

        row = _select_row(db_path, 1)
        assert row["status"] == "dismissed"  # still dismissed
        assert row["candidates_json"] == original_candidates  # unchanged
        assert row["run_uid"] == "run-001"  # unchanged

    def test_upsert_does_not_resurrect_resolved_row(self, tmp_path: Path) -> None:
        """A resolved row is NOT overwritten by a subsequent upsert."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Resolved Movie"
        staging.mkdir(parents=True)

        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Resolved Movie",
            extracted_year=2022,
            trigger="mid_band",
            candidates_json='[{"provider":"tmdb","provider_id":200,"title":"Resolved Movie","year":2022,"score":0.7}]',
            run_uid="run-001",
        )
        writer.resolve(1, provider="tmdb", provider_id=200)

        # Verify resolved.
        row = _select_row(db_path, 1)
        assert row["status"] == "resolved"

        # Try to upsert again — must NOT resurrect.
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Resolved Movie (Again)",
            extracted_year=2022,
            trigger="ambiguous",
            candidates_json='[{"provider":"tmdb","provider_id":999,"title":"Again","year":2022,"score":0.9}]',
            run_uid="run-002",
        )

        row = _select_row(db_path, 1)
        assert row["status"] == "resolved"  # still resolved

    def test_upsert_revives_superseded_row(self, tmp_path: Path) -> None:
        """F07 — a superseded row IS revived to pending when re-enqueued.

        A folder re-created at a path a previous run superseded (re-download,
        retry after a failed grab) must re-enter the queue rather than being
        permanently blacklisted.  The revive resets created_at and clears the
        stale resolution fields; resolved/dismissed rows (operator verdicts)
        are still never resurrected (separate tests above).
        """
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Superseded Movie"
        staging.mkdir(parents=True)

        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Superseded Movie",
            extracted_year=2023,
            trigger="mid_band",
            candidates_json=(
                '[{"provider":"tmdb","provider_id":300,"title":"Superseded Movie","year":2023,"score":0.7}]'
            ),
            run_uid="run-001",
        )

        # Simulate a prior GC + stale resolution artifacts on the row.
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        apply_pragmas(conn)
        conn.execute(
            "UPDATE scrape_decision SET status = 'superseded', "
            'resolution_json = \'{"provider":"tmdb","provider_id":1,"via":"pick"}\', '
            "resolved_at = 1.0 WHERE id = 1"
        )
        conn.commit()
        conn.close()

        # Re-enqueue (the path exists again) — must revive to pending.
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Superseded Movie (Revived)",
            extracted_year=2023,
            trigger="ambiguous",
            candidates_json='[{"provider":"tmdb","provider_id":999,"title":"Revived","year":2023,"score":0.9}]',
            run_uid="run-002",
        )

        row = _select_row(db_path, 1)
        assert row["status"] == "pending"  # revived
        assert row["trigger"] == "ambiguous"  # refreshed
        assert row["run_uid"] == "run-002"
        assert row["resolution_json"] is None  # stale artifacts cleared
        assert row["resolved_at"] is None


# ---------------------------------------------------------------------------
# Tests — mark_superseded_orphans
# ---------------------------------------------------------------------------


class TestDecisionWriterMarkSupersededOrphans:
    """``mark_superseded_orphans()`` tests."""

    def test_orphans_superseded_missing_paths(self, tmp_path: Path) -> None:
        """Pending rows whose staging path is gone are marked superseded."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        # Row 1 — path exists.
        existing = tmp_path / "001-MOVIES" / "Exists"
        existing.mkdir(parents=True)
        writer.upsert(
            staging_path=existing,
            media_kind="movie",
            extracted_title="Exists",
            extracted_year=2020,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-001",
        )

        # Row 2 — path does not exist (never created).
        writer.upsert(
            staging_path=tmp_path / "001-MOVIES" / "Gone",
            media_kind="movie",
            extracted_title="Gone",
            extracted_year=2021,
            trigger="below_threshold",
            candidates_json="[]",
            run_uid="run-001",
        )

        # Row 3 — path created then deleted.
        deleted = tmp_path / "001-MOVIES" / "Deleted"
        deleted.mkdir(parents=True)
        writer.upsert(
            staging_path=deleted,
            media_kind="movie",
            extracted_title="Deleted",
            extracted_year=2022,
            trigger="ambiguous",
            candidates_json="[]",
            run_uid="run-001",
        )
        deleted.rmdir()  # now gone

        writer.mark_superseded_orphans()

        # Row 1 — still pending (path exists).
        row1 = _select_row(db_path, 1)
        assert row1["status"] == "pending"

        # Row 2 — superseded (path never existed).
        row2 = _select_row(db_path, 2)
        assert row2["status"] == "superseded"

        # Row 3 — superseded (path deleted).
        row3 = _select_row(db_path, 3)
        assert row3["status"] == "superseded"

    def test_orphans_leaves_non_pending_alone(self, tmp_path: Path) -> None:
        """Only pending rows are tested; resolved/dismissed rows are untouched."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        # Row 1 — resolved, path exists.
        existing = tmp_path / "001-MOVIES" / "ResolvedExists"
        existing.mkdir(parents=True)
        writer.upsert(
            staging_path=existing,
            media_kind="movie",
            extracted_title="ResolvedExists",
            extracted_year=2020,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-001",
        )
        writer.resolve(1, provider="tmdb", provider_id=1)

        # Row 2 — dismissed, path gone.
        writer.upsert(
            staging_path=tmp_path / "001-MOVIES" / "DismissedGone",
            media_kind="movie",
            extracted_title="DismissedGone",
            extracted_year=2021,
            trigger="below_threshold",
            candidates_json="[]",
            run_uid="run-001",
        )
        writer.dismiss(2)

        writer.mark_superseded_orphans()

        # Row 1 — still resolved (not touched by orphan GC).
        row1 = _select_row(db_path, 1)
        assert row1["status"] == "resolved"

        # Row 2 — still dismissed (not touched by orphan GC).
        row2 = _select_row(db_path, 2)
        assert row2["status"] == "dismissed"


# ---------------------------------------------------------------------------
# Tests — resolve
# ---------------------------------------------------------------------------


class TestDecisionWriterResolve:
    """``resolve()`` tests."""

    def test_resolve_sets_status_and_resolution_json(self, tmp_path: Path) -> None:
        """After ``resolve()`` the row has status resolved and resolution_json populated.

        Design: docs/reference/indexer-json-shapes.md#scrape_decisionresolution_json
        Contract: Calling resolve() on a pending decision row sets status to
        'resolved', populates resolution_json with a dict containing provider,
        provider_id, and via, and sets resolved_at to a positive epoch timestamp.
        """
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Resolve Me"
        staging.mkdir(parents=True)
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Resolve Me",
            extracted_year=2024,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-001",
        )

        writer.resolve(1, provider="tmdb", provider_id=27205, via="pick")

        row = _select_row(db_path, 1)
        assert row["status"] == "resolved"
        assert row["resolved_at"] is not None
        assert row["resolved_at"] > 0
        resolution = json.loads(row["resolution_json"])
        assert resolution["provider"] == "tmdb"
        assert resolution["provider_id"] == 27205
        assert resolution["via"] == "pick"

    def test_resolve_default_via(self, tmp_path: Path) -> None:
        """When ``via`` is omitted, it defaults to ``'pick'``."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-TVSHOWS" / "Default Via"
        staging.mkdir(parents=True)
        writer.upsert(
            staging_path=staging,
            media_kind="tvshow",
            extracted_title="Default Via",
            extracted_year=2024,
            trigger="ambiguous",
            candidates_json="[]",
            run_uid="run-001",
        )

        writer.resolve(1, provider="tvdb", provider_id=78901)

        row = _select_row(db_path, 1)
        resolution = json.loads(row["resolution_json"])
        assert resolution["via"] == "pick"

    def test_resolve_search_override(self, tmp_path: Path) -> None:
        """``via='search_override'`` is recorded correctly."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Search Override"
        staging.mkdir(parents=True)
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Search Override",
            extracted_year=2024,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-001",
        )

        writer.resolve(1, provider="tmdb", provider_id=999, via="search_override")

        row = _select_row(db_path, 1)
        resolution = json.loads(row["resolution_json"])
        assert resolution["via"] == "search_override"


# ---------------------------------------------------------------------------
# Tests — dismiss
# ---------------------------------------------------------------------------


class TestDecisionWriterDismiss:
    """``dismiss()`` tests."""

    def test_dismiss_sets_status(self, tmp_path: Path) -> None:
        """After ``dismiss()`` the row has ``status='dismissed'``."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Dismiss Me"
        staging.mkdir(parents=True)
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Dismiss Me",
            extracted_year=2024,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-001",
        )

        writer.dismiss(1)

        row = _select_row(db_path, 1)
        assert row["status"] == "dismissed"
        assert row["updated_at"] > 0

    def test_dismiss_preserves_other_fields(self, tmp_path: Path) -> None:
        """Dismissing does not alter ``created_at``, ``candidates_json``, etc."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)

        staging = tmp_path / "001-MOVIES" / "Dismiss Preserve"
        staging.mkdir(parents=True)
        writer.upsert(
            staging_path=staging,
            media_kind="movie",
            extracted_title="Dismiss Preserve",
            extracted_year=2024,
            trigger="below_threshold",
            candidates_json='[{"provider":"tmdb","provider_id":42,"title":"DP","year":2024,"score":0.4}]',
            run_uid="run-001",
        )

        row_before = _select_row(db_path, 1)
        writer.dismiss(1)
        row_after = _select_row(db_path, 1)

        assert row_after["created_at"] == row_before["created_at"]
        assert row_after["candidates_json"] == row_before["candidates_json"]
        assert row_after["extracted_title"] == "Dismiss Preserve"


# ---------------------------------------------------------------------------
# Tests — fail-soft
# ---------------------------------------------------------------------------


class TestDecisionWriterFailSoft:
    """Fail-soft tests — the writer must never raise."""

    def test_upsert_bad_db_path_does_not_raise(self, tmp_path: Path) -> None:
        """Pointing at a non-existent directory does not raise."""
        writer = DecisionWriter(tmp_path / "nonexistent" / "library.db")
        # Must not raise.
        writer.upsert(
            staging_path="/some/path",
            media_kind="movie",
            extracted_title="Test",
            extracted_year=2020,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-fs",
        )

    def test_upsert_dropped_table_does_not_raise(self, tmp_path: Path) -> None:
        """Dropping the table before upsert does not raise."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        # Drop the table to simulate schema mismatch.
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        apply_pragmas(conn)
        conn.execute("DROP TABLE scrape_decision")
        conn.commit()
        conn.close()

        writer = DecisionWriter(db_path)
        # Must not raise.
        writer.upsert(
            staging_path="/some/path",
            media_kind="movie",
            extracted_title="Test",
            extracted_year=2020,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-fs",
        )

    def test_mark_superseded_orphans_bad_db_path_does_not_raise(self, tmp_path: Path) -> None:
        """Pointing at a non-existent directory does not raise."""
        writer = DecisionWriter(tmp_path / "nonexistent" / "library.db")
        # Must not raise.
        writer.mark_superseded_orphans()

    def test_resolve_bad_db_path_raises(self, tmp_path: Path) -> None:
        """F05/F29 — resolve is fail-loud: a DB error raises DecisionWriteError.

        The operator-verdict path must never silently report success when the
        status write could not land.
        """
        writer = DecisionWriter(tmp_path / "nonexistent" / "library.db")
        with pytest.raises(DecisionWriteError):
            writer.resolve(1, provider="tmdb", provider_id=1)

    def test_dismiss_bad_db_path_raises(self, tmp_path: Path) -> None:
        """F29 — dismiss is fail-loud: a DB error raises DecisionWriteError."""
        writer = DecisionWriter(tmp_path / "nonexistent" / "library.db")
        with pytest.raises(DecisionWriteError):
            writer.dismiss(1)

    def test_resolve_non_pending_returns_false(self, tmp_path: Path) -> None:
        """F28/F34 — resolve of a non-pending row returns False, leaves it unchanged."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)
        writer.upsert("/p", "movie", "T", 2020, "mid_band", "[]", None)
        assert writer.resolve(1, "tmdb", 1) is True  # first resolve wins
        # Second resolve on the now-resolved row: no-op, returns False.
        assert writer.resolve(1, "tmdb", 2) is False
        row = _select_row(db_path, 1)
        assert row["status"] == "resolved"
        assert '"provider_id": 1' in row["resolution_json"]  # not overwritten to 2

    def test_dismiss_non_pending_returns_false(self, tmp_path: Path) -> None:
        """F28/F33 — dismiss of a resolved row returns False, preserves resolution."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = DecisionWriter(db_path)
        writer.upsert("/p", "movie", "T", 2020, "mid_band", "[]", None)
        assert writer.resolve(1, "tmdb", 1, via="pick") is True
        # Dismiss on a resolved row must not flip it.
        assert writer.dismiss(1) is False
        row = _select_row(db_path, 1)
        assert row["status"] == "resolved"
        assert row["resolution_json"] is not None

    def test_insert_on_path_that_is_a_file_not_a_db_does_not_raise(self, tmp_path: Path) -> None:
        """Pointing at a regular file that is not a SQLite DB does not raise."""
        not_a_db = tmp_path / "not_a_db.txt"
        not_a_db.write_text("hello")
        writer = DecisionWriter(not_a_db)
        # Must not raise (sqlite3 will complain but we catch it).
        writer.upsert(
            staging_path="/some/path",
            media_kind="movie",
            extracted_title="Test",
            extracted_year=2020,
            trigger="mid_band",
            candidates_json="[]",
            run_uid="run-fs",
        )
