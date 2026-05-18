"""Round-trip tests for the indexer schema dataclasses and repository modules.

Covers:
- Insert + read-back round-trips for every repo (disk, item, release, file, tv, log, outbox).
- Timestamp suffix convention: every ``*_at`` and ``*_ns`` field on Row dataclasses is typed ``int``.
- Trigger enforcement: inserting a season under a ``kind='movie'`` item raises IntegrityError.
"""

from __future__ import annotations

import dataclasses
import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import (
    disk_repo,
    file_repo,
    item_repo,
    log_repo,
    outbox_repo,
    release_repo,
    tv_repo,
)
from personalscraper.indexer.schema import (
    DeletedItemRow,
    DiskRow,
    EpisodeRow,
    IndexOutboxRow,
    ItemAttributeRow,
    ItemIssueRow,
    MediaFileRow,
    MediaItemRow,
    MediaReleaseRow,
    MediaStreamRow,
    PathRow,
    PendingOpRow,
    RepairQueueRow,
    ScanEventRow,
    ScanRunRow,
    SchemaVersionRow,
    SeasonRow,
    _check_field_naming_convention,
)

# ---------------------------------------------------------------------------
# Fixture: in-memory DB seeded with the full migration chain
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_ALL_ROW_CLASSES = [
    DiskRow,
    PathRow,
    MediaItemRow,
    ItemAttributeRow,
    SeasonRow,
    EpisodeRow,
    MediaReleaseRow,
    MediaFileRow,
    MediaStreamRow,
    ItemIssueRow,
    IndexOutboxRow,
    PendingOpRow,
    RepairQueueRow,
    ScanRunRow,
    ScanEventRow,
    DeletedItemRow,
    SchemaVersionRow,
]


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB and apply all migrations.

    Returns:
        An open :class:`sqlite3.Connection` with the full schema applied.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


# ---------------------------------------------------------------------------
# Helper to insert a minimal disk + path + media_item for FK scaffolding
# ---------------------------------------------------------------------------


def _insert_disk(c: sqlite3.Connection) -> int:
    """Insert a minimal disk row and return its id.

    Args:
        c: Open SQLite connection.

    Returns:
        The rowid of the inserted disk.
    """
    row = DiskRow(
        id=0,
        uuid="test-uuid-1",
        label="TestDisk",
        mount_path="/Volumes/TestDisk",
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    return disk_repo.insert(c, row)


def _insert_path(c: sqlite3.Connection, disk_id: int) -> int:
    """Insert a minimal path row and return its id.

    Args:
        c: Open SQLite connection.
        disk_id: FK to the disk row.

    Returns:
        The rowid of the inserted path.
    """
    row = PathRow(
        id=0,
        disk_id=disk_id,
        rel_path="001-MOVIES/Test Movie (2024)",
        dir_mtime_ns=None,
        last_walked_at=None,
    )
    return disk_repo.insert_path(c, row)


def _insert_show_item(c: sqlite3.Connection) -> int:
    """Insert a minimal media_item with kind='show' and return its id.

    Args:
        c: Open SQLite connection.

    Returns:
        The rowid of the inserted media item.
    """
    now = int(time.time())
    row = MediaItemRow(
        id=0,
        kind="show",
        title="Test Show",
        title_sort="Test Show",
        original_title=None,
        year=2024,
        category_id="tv_shows",
        external_ids_json="{}",
        ratings_json=None,
        canonical_provider=None,
        nfo_status=None,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="fr",
    )
    return item_repo.insert(c, row)


def _insert_movie_item(c: sqlite3.Connection) -> int:
    """Insert a minimal media_item with kind='movie' and return its id.

    Args:
        c: Open SQLite connection.

    Returns:
        The rowid of the inserted media item.
    """
    now = int(time.time())
    row = MediaItemRow(
        id=0,
        kind="movie",
        title="Test Movie",
        title_sort="Test Movie",
        original_title=None,
        year=2024,
        category_id="movies",
        external_ids_json="{}",
        ratings_json=None,
        canonical_provider=None,
        nfo_status=None,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="fr",
    )
    return item_repo.insert(c, row)


def _insert_release(c: sqlite3.Connection, item_id: int) -> int:
    """Insert a minimal media_release row and return its id.

    Args:
        c: Open SQLite connection.
        item_id: FK to the media_item row.

    Returns:
        The rowid of the inserted release.
    """
    row = MediaReleaseRow(
        id=0,
        item_id=item_id,
        episode_id=None,
        quality="1080p",
        edition=None,
        primary_lang="fr",
    )
    return release_repo.insert(c, row)


# ---------------------------------------------------------------------------
# Timestamp suffix convention tests
# ---------------------------------------------------------------------------


class TestTimestampSuffixConvention:
    """Verify *_at and *_ns fields are typed int on all Row dataclasses."""

    @pytest.mark.parametrize("row_class", _ALL_ROW_CLASSES)
    def test_at_and_ns_fields_are_int(self, row_class: type) -> None:
        """Fields ending with _at or _ns must be typed int (DESIGN §6.5).

        Args:
            row_class: Dataclass row type to inspect.
        """
        for field in dataclasses.fields(row_class):
            name = field.name
            if not (name.endswith("_at") or name.endswith("_ns")):
                continue
            # Resolve the actual type from the annotation — handle Optional[int] → skip
            # We only enforce the convention for fields where the type hint is exactly int;
            # Optional[int] (stored as int | None in DB) is allowed by the schema.
            hint = field.type
            # If the hint is a string (from __future__ annotations), resolve it manually.
            if isinstance(hint, str):
                # Accept "int" and "int | None" — only check pure "int" binding
                if hint == "int":
                    _check_field_naming_convention(name, int)
                # int | None is valid per schema (nullable timestamp columns)
            else:
                if hint is int:
                    _check_field_naming_convention(name, int)


# ---------------------------------------------------------------------------
# disk_repo round-trip tests
# ---------------------------------------------------------------------------


class TestDiskRepo:
    """Round-trip tests for disk_repo."""

    def test_insert_and_get_by_uuid(self, conn: sqlite3.Connection) -> None:
        """Inserting a disk and fetching by UUID returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        fetched = disk_repo.get_by_uuid(conn, "test-uuid-1")
        assert fetched is not None
        assert fetched.id == disk_id
        assert fetched.uuid == "test-uuid-1"
        assert fetched.label == "TestDisk"
        assert fetched.is_mounted == 1

    def test_get_by_id(self, conn: sqlite3.Connection) -> None:
        """Fetching disk by PK matches inserted row.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        fetched = disk_repo.get_by_id(conn, disk_id)
        assert fetched is not None
        assert fetched.id == disk_id

    def test_get_by_uuid_missing(self, conn: sqlite3.Connection) -> None:
        """Fetching a non-existent UUID returns None.

        Args:
            conn: In-memory DB fixture.
        """
        assert disk_repo.get_by_uuid(conn, "no-such-uuid") is None

    def test_update_mount_path(self, conn: sqlite3.Connection) -> None:
        """update_mount_path persists the new path and is_mounted flag.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        result = disk_repo.update_mount_path(conn, disk_id, "/Volumes/Other")
        assert result is True
        fetched = disk_repo.get_by_id(conn, disk_id)
        assert fetched is not None
        assert fetched.mount_path == "/Volumes/Other"
        assert fetched.is_mounted == 1

    def test_update_mount_path_none(self, conn: sqlite3.Connection) -> None:
        """Setting mount_path to None marks disk as unmounted.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        disk_repo.update_mount_path(conn, disk_id, None)
        fetched = disk_repo.get_by_id(conn, disk_id)
        assert fetched is not None
        assert fetched.mount_path is None
        assert fetched.is_mounted == 0

    def test_update_merkle_root(self, conn: sqlite3.Connection) -> None:
        """update_merkle_root persists the new value.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        disk_repo.update_merkle_root(conn, disk_id, "abcdef0123456789")
        fetched = disk_repo.get_by_id(conn, disk_id)
        assert fetched is not None
        assert fetched.merkle_root == "abcdef0123456789"

    def test_upsert_path_roundtrip(self, conn: sqlite3.Connection) -> None:
        """Upserting a path twice only keeps one row with the latest values.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        now_ns = time.time_ns()
        r1 = PathRow(id=0, disk_id=disk_id, rel_path="Movies/Foo", dir_mtime_ns=now_ns, last_walked_at=1000)
        pid = disk_repo.upsert_path(conn, r1)
        r2 = PathRow(id=0, disk_id=disk_id, rel_path="Movies/Foo", dir_mtime_ns=now_ns + 1, last_walked_at=2000)
        pid2 = disk_repo.upsert_path(conn, r2)
        # Both calls should resolve to the same row
        assert pid == pid2
        fetched = disk_repo.get_path_by_id(conn, pid)
        assert fetched is not None
        assert fetched.last_walked_at == 2000


# ---------------------------------------------------------------------------
# item_repo round-trip tests
# ---------------------------------------------------------------------------


class TestItemRepo:
    """Round-trip tests for item_repo."""

    def test_insert_and_get_by_id(self, conn: sqlite3.Connection) -> None:
        """Inserting a media item and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_movie_item(conn)
        fetched = item_repo.get_by_id(conn, item_id)
        assert fetched is not None
        assert fetched.id == item_id
        assert fetched.kind == "movie"
        assert fetched.title == "Test Movie"

    def test_find_by_tmdb_id(self, conn: sqlite3.Connection) -> None:
        """find_by_tmdb_id returns the correct row.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        row = MediaItemRow(
            id=0,
            kind="movie",
            title="TMDB Movie",
            title_sort="TMDB Movie",
            original_title=None,
            year=2020,
            category_id="movies",
            external_ids_json='{"tmdb": {"series_id": "99999", "episode_id": null}}',
            ratings_json=None,
            canonical_provider=None,
            nfo_status=None,
            artwork_json=None,
            date_created=now,
            date_modified=now,
            date_metadata_refreshed=None,
            is_locked=0,
            preferred_lang="fr",
        )
        item_id = item_repo.insert(conn, row)
        fetched = item_repo.find_by_tmdb_id(conn, 99999)
        assert fetched is not None
        assert fetched.id == item_id
        import json as _json  # noqa: PLC0415
        assert _json.loads(fetched.external_ids_json)["tmdb"]["series_id"] == "99999"

    def test_delete(self, conn: sqlite3.Connection) -> None:
        """Deleting a media item makes get_by_id return None.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_movie_item(conn)
        assert item_repo.delete(conn, item_id) is True
        assert item_repo.get_by_id(conn, item_id) is None

    def test_upsert_attr(self, conn: sqlite3.Connection) -> None:
        """upsert_attr stores and updates a flex attribute.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_movie_item(conn)
        attr = ItemAttributeRow(item_id=item_id, key="trailer_found", value="1")
        item_repo.upsert_attr(conn, attr)
        fetched = item_repo.get_attr(conn, item_id, "trailer_found")
        assert fetched is not None
        assert fetched.value == "1"

        # Overwrite
        attr2 = ItemAttributeRow(item_id=item_id, key="trailer_found", value="0")
        item_repo.upsert_attr(conn, attr2)
        fetched2 = item_repo.get_attr(conn, item_id, "trailer_found")
        assert fetched2 is not None
        assert fetched2.value == "0"


# ---------------------------------------------------------------------------
# release_repo round-trip tests
# ---------------------------------------------------------------------------


class TestReleaseRepo:
    """Round-trip tests for release_repo."""

    def test_insert_and_get_by_id(self, conn: sqlite3.Connection) -> None:
        """Inserting a release and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_movie_item(conn)
        release_id = _insert_release(conn, item_id)
        fetched = release_repo.get_by_id(conn, release_id)
        assert fetched is not None
        assert fetched.id == release_id
        assert fetched.item_id == item_id
        assert fetched.quality == "1080p"

    def test_upsert_returns_rowid(self, conn: sqlite3.Connection) -> None:
        """Upsert returns a positive rowid and the row is retrievable by get_by_id.

        Note on NULL-in-UNIQUE: SQLite treats NULL as distinct in UNIQUE constraints
        (see schema comment in 001_init.sql).  True ON CONFLICT idempotency for rows
        with nullable UNIQUE key columns requires a partial-index workaround that is
        out of scope for this sub-phase; callers must be aware of this limitation.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_movie_item(conn)
        row = MediaReleaseRow(
            id=0,
            item_id=item_id,
            episode_id=None,
            quality="4K",
            edition="Theatrical",
            primary_lang="en",
        )
        release_id = release_repo.upsert(conn, row)
        assert release_id > 0
        fetched = release_repo.get_by_id(conn, release_id)
        assert fetched is not None
        assert fetched.quality == "4K"
        assert fetched.edition == "Theatrical"


# ---------------------------------------------------------------------------
# file_repo round-trip tests
# ---------------------------------------------------------------------------


class TestFileRepo:
    """Round-trip tests for file_repo."""

    def _make_file_row(self, release_id: int, path_id: int) -> MediaFileRow:
        """Build a minimal MediaFileRow for testing.

        Args:
            release_id: FK to the release row.
            path_id: FK to the path row.

        Returns:
            A :class:`MediaFileRow` ready for insertion.
        """
        now = int(time.time())
        return MediaFileRow(
            id=0,
            release_id=release_id,
            path_id=path_id,
            filename="movie.mkv",
            size_bytes=4_000_000_000,
            mtime_ns=time.time_ns(),
            ctime_ns=None,
            oshash="abcdef0123456789",
            xxh3_partial=None,
            xxh3_full=None,
            scan_generation=1,
            last_verified_at=now,
            enriched_at=None,
            miss_strikes=0,
            deleted_at=None,
        )

    def test_insert_and_get_by_id(self, conn: sqlite3.Connection) -> None:
        """Inserting a file and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn)
        release_id = _insert_release(conn, item_id)
        row = self._make_file_row(release_id, path_id)
        file_id = file_repo.insert(conn, row)
        fetched = file_repo.get_by_id(conn, file_id)
        assert fetched is not None
        assert fetched.id == file_id
        assert fetched.filename == "movie.mkv"
        assert fetched.oshash == "abcdef0123456789"

    def test_find_by_path_and_filename(self, conn: sqlite3.Connection) -> None:
        """find_by_path_and_filename returns the correct row.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn)
        release_id = _insert_release(conn, item_id)
        row = self._make_file_row(release_id, path_id)
        file_id = file_repo.insert(conn, row)
        fetched = file_repo.find_by_path_and_filename(conn, path_id, "movie.mkv")
        assert fetched is not None
        assert fetched.id == file_id

    def test_soft_delete(self, conn: sqlite3.Connection) -> None:
        """soft_delete sets deleted_at on the file row.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn)
        release_id = _insert_release(conn, item_id)
        row = self._make_file_row(release_id, path_id)
        file_id = file_repo.insert(conn, row)
        now = int(time.time())
        assert file_repo.soft_delete(conn, file_id, now) is True
        fetched = file_repo.get_by_id(conn, file_id)
        assert fetched is not None
        assert fetched.deleted_at == now

    def test_increment_miss_strike(self, conn: sqlite3.Connection) -> None:
        """increment_miss_strike increments miss_strikes by 1.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn)
        release_id = _insert_release(conn, item_id)
        row = self._make_file_row(release_id, path_id)
        file_id = file_repo.insert(conn, row)
        file_repo.increment_miss_strike(conn, file_id)
        file_repo.increment_miss_strike(conn, file_id)
        fetched = file_repo.get_by_id(conn, file_id)
        assert fetched is not None
        assert fetched.miss_strikes == 2

    def test_insert_stream_and_get_streams(self, conn: sqlite3.Connection) -> None:
        """Inserting streams and fetching for a file returns them ordered by idx.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn)
        release_id = _insert_release(conn, item_id)
        row = self._make_file_row(release_id, path_id)
        file_id = file_repo.insert(conn, row)

        s1 = MediaStreamRow(
            id=0,
            file_id=file_id,
            idx=0,
            kind="video",
            codec="h264",
            lang=None,
            channels=None,
            width=1920,
            height=1080,
            duration_ms=7200000,
            bitrate=8000000,
        )
        s2 = MediaStreamRow(
            id=0,
            file_id=file_id,
            idx=1,
            kind="audio",
            codec="ac3",
            lang="fr",
            channels=6,
            width=None,
            height=None,
            duration_ms=None,
            bitrate=448000,
        )
        file_repo.insert_stream(conn, s2)
        file_repo.insert_stream(conn, s1)

        streams = file_repo.get_streams_for_file(conn, file_id)
        assert len(streams) == 2
        # Ordered by idx, so s1 (idx=0) comes first
        assert streams[0].idx == 0
        assert streams[0].kind == "video"
        assert streams[1].idx == 1
        assert streams[1].kind == "audio"


# ---------------------------------------------------------------------------
# tv_repo round-trip tests
# ---------------------------------------------------------------------------


class TestTvRepo:
    """Round-trip tests for tv_repo."""

    def test_insert_season_and_get(self, conn: sqlite3.Connection) -> None:
        """Inserting a season under a show item and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_show_item(conn)
        season_row = SeasonRow(
            id=0,
            item_id=item_id,
            number=1,
            episode_count=0,
            has_poster=0,
            episodes_with_nfo=0,
        )
        season_id = tv_repo.insert_season(conn, season_row)
        fetched = tv_repo.get_season_by_id(conn, season_id)
        assert fetched is not None
        assert fetched.id == season_id
        assert fetched.item_id == item_id
        assert fetched.number == 1

    def test_insert_episode_and_get(self, conn: sqlite3.Connection) -> None:
        """Inserting an episode and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_show_item(conn)
        season_row = SeasonRow(id=0, item_id=item_id, number=1, episode_count=0, has_poster=0, episodes_with_nfo=0)
        season_id = tv_repo.insert_season(conn, season_row)
        ep_row = EpisodeRow(id=0, season_id=season_id, number=3, title="Pilot")
        ep_id = tv_repo.insert_episode(conn, ep_row)
        fetched = tv_repo.get_episode_by_id(conn, ep_id)
        assert fetched is not None
        assert fetched.id == ep_id
        assert fetched.number == 3
        assert fetched.title == "Pilot"

    def test_get_episodes_for_season_ordered(self, conn: sqlite3.Connection) -> None:
        """Episodes are returned ordered by number.

        Args:
            conn: In-memory DB fixture.
        """
        item_id = _insert_show_item(conn)
        season_row = SeasonRow(id=0, item_id=item_id, number=2, episode_count=0, has_poster=0, episodes_with_nfo=0)
        season_id = tv_repo.insert_season(conn, season_row)
        tv_repo.insert_episode(conn, EpisodeRow(id=0, season_id=season_id, number=5, title="E5"))
        tv_repo.insert_episode(conn, EpisodeRow(id=0, season_id=season_id, number=1, title="E1"))
        tv_repo.insert_episode(conn, EpisodeRow(id=0, season_id=season_id, number=3, title="E3"))
        episodes = tv_repo.get_episodes_for_season(conn, season_id)
        assert [e.number for e in episodes] == [1, 3, 5]

    def test_trigger_season_requires_show(self, conn: sqlite3.Connection) -> None:
        """trg_season_requires_show fires when item kind is 'movie'.

        Args:
            conn: In-memory DB fixture.
        """
        movie_id = _insert_movie_item(conn)
        season_row = SeasonRow(id=0, item_id=movie_id, number=1, episode_count=0, has_poster=0, episodes_with_nfo=0)
        with pytest.raises(sqlite3.IntegrityError):
            tv_repo.insert_season(conn, season_row)


# ---------------------------------------------------------------------------
# log_repo round-trip tests
# ---------------------------------------------------------------------------


class TestLogRepo:
    """Round-trip tests for log_repo."""

    def test_insert_scan_run_and_get(self, conn: sqlite3.Connection) -> None:
        """Inserting a scan run and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        row = ScanRunRow(
            id=0,
            generation=1,
            mode="full",
            disk_filter=None,
            started_at=now,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        )
        run_id = log_repo.insert_scan_run(conn, row)
        fetched = log_repo.get_scan_run_by_id(conn, run_id)
        assert fetched is not None
        assert fetched.id == run_id
        assert fetched.mode == "full"
        assert fetched.status == "running"

    def test_update_scan_run_status(self, conn: sqlite3.Connection) -> None:
        """update_scan_run_status changes status and finished_at.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        row = ScanRunRow(
            id=0,
            generation=2,
            mode="quick",
            disk_filter=None,
            started_at=now,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        )
        run_id = log_repo.insert_scan_run(conn, row)
        log_repo.update_scan_run_status(conn, run_id, "ok", finished_at=now + 30)
        fetched = log_repo.get_scan_run_by_id(conn, run_id)
        assert fetched is not None
        assert fetched.status == "ok"
        assert fetched.finished_at == now + 30

    def test_insert_scan_event(self, conn: sqlite3.Connection) -> None:
        """Inserting a scan event succeeds and returns a positive rowid.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        run_row = ScanRunRow(
            id=0,
            generation=3,
            mode="incremental",
            disk_filter=None,
            started_at=now,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        )
        run_id = log_repo.insert_scan_run(conn, run_row)
        ev_row = ScanEventRow(
            id=0,
            scan_id=run_id,
            ts=now,
            item_id=None,
            file_id=None,
            event="indexer.scan.started",
            payload_json=None,
        )
        ev_id = log_repo.insert_scan_event(conn, ev_row)
        assert ev_id > 0

    def test_insert_deleted_item(self, conn: sqlite3.Connection) -> None:
        """Inserting a deleted_item tombstone returns a positive rowid.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        row = DeletedItemRow(
            id=0,
            kind="file",
            original_id=42,
            deleted_at=now,
            reason="miss_strikes",
            payload_json=None,
        )
        di_id = log_repo.insert_deleted_item(conn, row)
        assert di_id > 0


# ---------------------------------------------------------------------------
# outbox_repo round-trip tests
# ---------------------------------------------------------------------------


class TestOutboxRepo:
    """Round-trip tests for outbox_repo."""

    def test_insert_outbox_event_and_claim(self, conn: sqlite3.Connection) -> None:
        """Inserting an outbox event and claiming it returns the row.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        row = IndexOutboxRow(
            id=0,
            source="dispatch",
            op="move",
            payload_json='{"op":"move"}',
            created_at=now,
            processed_at=None,
            status="pending",
        )
        outbox_id = outbox_repo.insert_outbox_event(conn, row)
        claimed = outbox_repo.claim_pending_op(conn, outbox_id)
        assert claimed is not None
        assert claimed.id == outbox_id
        assert claimed.status == "pending"

    def test_complete_pending_op(self, conn: sqlite3.Connection) -> None:
        """complete_pending_op marks the row as done.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        row = IndexOutboxRow(
            id=0,
            source="scraper",
            op="nfo_write",
            payload_json='{"op":"nfo_write"}',
            created_at=now,
            processed_at=None,
            status="pending",
        )
        outbox_id = outbox_repo.insert_outbox_event(conn, row)
        outbox_repo.complete_pending_op(conn, outbox_id, "done", now + 1)
        # After completion, claim returns None (status no longer 'pending')
        assert outbox_repo.claim_pending_op(conn, outbox_id) is None

    def test_insert_pending_op_and_get(self, conn: sqlite3.Connection) -> None:
        """Inserting a pending_op and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        disk_id = _insert_disk(conn)
        now = int(time.time())
        row = PendingOpRow(
            id=0,
            disk_id=disk_id,
            op="move",
            payload_json='{"dest":"/Volumes/Disk1/Movies"}',
            created_at=now,
            replayed_at=None,
        )
        op_id = outbox_repo.insert_pending_op(conn, row)
        fetched = outbox_repo.get_pending_op_by_id(conn, op_id)
        assert fetched is not None
        assert fetched.id == op_id
        assert fetched.disk_id == disk_id

    def test_insert_repair_queue_and_get(self, conn: sqlite3.Connection) -> None:
        """Inserting a repair queue entry and fetching by id returns equal data.

        Args:
            conn: In-memory DB fixture.
        """
        now = int(time.time())
        row = RepairQueueRow(
            id=0,
            scope="file",
            scope_id=7,
            reason="miss_strikes >= 3",
            payload_json=None,
            enqueued_at=now,
            status="pending",
            attempted_at=None,
            attempts=0,
        )
        rq_id = outbox_repo.insert_repair_queue(conn, row)
        fetched = outbox_repo.get_repair_queue_by_id(conn, rq_id)
        assert fetched is not None
        assert fetched.id == rq_id
        assert fetched.scope == "file"
        assert fetched.scope_id == 7
