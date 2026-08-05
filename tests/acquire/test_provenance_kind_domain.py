"""Migration 015 — ``staging_provenance.kind`` accepts every domain ``WantedKind``.

The founding defect (`docs/features/spine-truth/DESIGN.md` cause A): season-grab (#378)
introduced ``kind='season'`` while the table still declared
``CHECK (kind IN ('movie', 'episode'))``. Every season grab was rejected at write time and
the error was swallowed by the advisory writer — the acquisition never appeared on the spine.

The guard here (G1) is **behavioural, not declarative**: it does not read the ``CHECK`` text
out of ``sqlite_master`` (a store that stopped writing ``kind`` at all would still pass such a
test). It drives the real ``upsert_grab`` for EVERY literal of :data:`WantedKind` against a
real migrated database and demands the row be there afterwards — what the domain can actually
record.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import get_args

import pytest

from personalscraper.acquire.domain import WantedKind
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite import apply_migrations

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "migrations"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


class TestKindDomainEquality:
    """G1 — every ``WantedKind`` the domain can produce is storable on the spine."""

    def test_every_wanted_kind_is_accepted_by_upsert_grab(self, store: ConcreteAcquireStore) -> None:
        """A grab of ANY domain kind lands a row — no kind is silently rejected.

        This is the executable form of « un futur ``kind`` ne pourra plus être rejeté en
        silence ». Adding a literal to ``WantedKind`` without widening the table's CHECK
        fails here, loudly, before the write ever reaches production.
        """
        kinds = get_args(WantedKind)
        assert "season" in kinds, "the domain must still carry the kind that broke the spine"

        for index, kind in enumerate(kinds):
            info_hash = f"kind{index}"
            store.provenance.upsert_grab(
                info_hash,
                followed_id=None,
                media_ref=MediaRef(tvdb_id=100 + index),
                kind=kind,
                grabbed_at=1000 + index,
            )
            row = store.provenance.by_hash(info_hash)
            assert row is not None, f"kind={kind!r} was rejected by staging_provenance"
            assert row.kind == kind

    def test_a_kind_outside_the_domain_is_still_refused(self, store: ConcreteAcquireStore) -> None:
        """The CHECK is widened, not dropped: an unknown kind still never lands.

        Without this the migration could 'pass' G1 by removing the constraint entirely,
        which would trade a loud rejection for a silent corruption of the registry.
        """
        store.provenance.upsert_grab(
            "bogus", followed_id=None, media_ref=None, kind="chapter", grabbed_at=1
        )
        assert store.provenance.by_hash("bogus") is None


class TestMigration015:
    """The table rebuild preserves every row, column and index."""

    def _apply_upto_014(self, db_path: Path, tmp_path: Path) -> None:
        """Apply migrations 001..014 only, so the DB sits at the pre-015 schema."""
        staged = tmp_path / "migrations_014"
        staged.mkdir()
        for script in MIGRATIONS_DIR.glob("*.sql"):
            if int(script.name.split("_", 1)[0]) <= 14:
                shutil.copy2(script, staged / script.name)
        conn = sqlite3.connect(str(db_path))
        try:
            apply_migrations(conn, staged)
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 14
        finally:
            conn.close()

    def test_rebuild_preserves_existing_rows_and_all_columns(self, tmp_path: Path) -> None:
        """A fully-populated pre-015 row survives the rebuild byte-for-byte."""
        db_path = tmp_path / "acquire.db"
        self._apply_upto_014(db_path, tmp_path)

        columns = (
            "info_hash, followed_id, media_ref_json, kind, ingest_path, current_path, "
            "scraped_ref_json, dispatch_path, grabbed_at, ingested_at, scraped_at, "
            "dispatched_at, status, resolution_state, decision_id, resolution_trigger, "
            "resolution_at, grab_run_uid, ingest_run_uid, scrape_run_uid, dispatch_run_uid"
        )
        values = (
            "abc123",
            7,
            '{"tvdb_id": 1}',
            "episode",
            "/stage/in",
            "/stage/live",
            '{"tvdb_id": 2}',
            "/disk/out",
            10,
            20,
            30,
            40,
            "dispatched",
            "resolved",
            99,
            "mid_band",
            50,
            "runA",
            "runB",
            "runC",
            "runD",
        )
        conn = sqlite3.connect(str(db_path))
        try:
            placeholders = ", ".join("?" * len(values))
            conn.execute(f"INSERT INTO staging_provenance ({columns}) VALUES ({placeholders})", values)  # noqa: S608
            conn.commit()
        finally:
            conn.close()

        conn = sqlite3.connect(str(db_path))
        try:
            apply_migrations(conn, MIGRATIONS_DIR)
            assert conn.execute("PRAGMA user_version").fetchone()[0] >= 15
            after = conn.execute(f"SELECT {columns} FROM staging_provenance").fetchall()  # noqa: S608
            assert after == [values]
            indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            assert "idx_provenance_current_path" in indexes
            assert "idx_provenance_resolution_state" in indexes
            versions = {r[0] for r in conn.execute("SELECT version FROM schema_version")}
            assert 15 in versions
        finally:
            conn.close()

    def test_season_row_is_writable_after_the_rebuild(self, tmp_path: Path) -> None:
        """The whole point: a pre-015 database can store a season grab once migrated."""
        db_path = tmp_path / "acquire.db"
        self._apply_upto_014(db_path, tmp_path)
        conn = sqlite3.connect(str(db_path))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO staging_provenance (info_hash, kind) VALUES ('s1', 'season')")
        finally:
            conn.close()

        conn = sqlite3.connect(str(db_path))
        try:
            apply_migrations(conn, MIGRATIONS_DIR)
            conn.execute("INSERT INTO staging_provenance (info_hash, kind) VALUES ('s1', 'season')")
            conn.commit()
            assert conn.execute("SELECT kind FROM staging_provenance WHERE info_hash='s1'").fetchone()[0] == "season"
        finally:
            conn.close()
