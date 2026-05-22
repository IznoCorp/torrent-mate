"""Regression tests for oshash retry on NULL rows (DEV #51 + DEV #52).

DEV #51 — Enrich path does not recompute oshash on Stage-A rows with oshash=NULL.
    ``_enrich_one_file`` must add oshash when the current value is NULL, even
    when ``enriched_at`` is already set (i.e. the file was "enriched" before
    oshash retry was wired in).

DEV #52 — Full walker does not retry oshash on existing rows with oshash=NULL.
    ``_upsert_file_row`` UPDATE path must preserve a previously-computed oshash
    when recomputation fails (oshash_value=None due to OSError), and must update
    the oshash column when recomputation succeeds and the existing value was NULL.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._db_writes import _upsert_file_row
from personalscraper.indexer.scanner._modes import _enrich_one_file

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied.

    Returns:
        Open :class:`sqlite3.Connection` with FK checks enabled and all
        migrations applied.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _seed_file_with_null_oshash(
    conn: sqlite3.Connection,
    *,
    enriched_at: int | None = None,
) -> tuple[int, int, int]:
    """Insert disk → path → media_file with oshash=NULL.

    Args:
        conn: Open SQLite connection.
        enriched_at: Value to seed for ``enriched_at`` on the media_file row.
            ``None`` means the file has not been enriched yet (Stage A).

    Returns:
        Tuple of ``(disk_id, path_id, file_id)``.
    """
    now = int(time.time())

    disk_id: int = conn.execute(
        """
        INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes)
        VALUES ('uuid-retry', 'RetryDisk', '/mnt/retry', ?, 1, 0)
        """,
        (now,),
    ).lastrowid  # type: ignore[assignment]

    path_id: int = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, '001-MOVIES/TestMovie')",
        (disk_id,),
    ).lastrowid  # type: ignore[assignment]

    file_id: int = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (NULL, ?, 'movie.mkv', 2097152, ?, NULL,
                  NULL, NULL, NULL, 1, ?, ?, 0, NULL)
        """,
        (path_id, now * 1_000_000_000, now, enriched_at),
    ).lastrowid  # type: ignore[assignment]

    return disk_id, path_id, file_id


# ---------------------------------------------------------------------------
# DEV #51 — Enrich path recomputes oshash when NULL
# ---------------------------------------------------------------------------


class TestEnrichRecomputesNullOshash:
    """_enrich_one_file must populate oshash when the current value is NULL (DEV #51).

    The enrich pass handles streams, NFO status, and artwork (steps 1-3).
    Step 4 (added by this fix) retries oshash if the row has oshash=NULL,
    regardless of whether enriched_at is already set.
    """

    def test_enrich_recomputes_null_oshash(self) -> None:
        """_enrich_one_file populates oshash=NULL rows via Step 4.

        Seed a media_file row with oshash=NULL and enriched_at already set
        (simulating a Stage-A file whose enrich ran before oshash-retry was
        wired in).  After calling _enrich_one_file, oshash must be non-NULL.
        """
        conn = _make_conn()
        now = int(time.time())
        # enriched_at is already set — simulates a file enriched in a previous
        # run that lacked the oshash retry step.
        _, _, file_id = _seed_file_with_null_oshash(conn, enriched_at=now - 3600)

        # Verify precondition: oshash IS NULL before enrich.
        before = conn.execute("SELECT oshash FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert before["oshash"] is None, "precondition: oshash must be NULL before enrich"

        # Patch oshash computation to return a deterministic value without I/O.
        fake_oshash = "abcdef1234567890"
        with (
            patch(
                "personalscraper.indexer.scanner._modes.enrich.os.scandir",
                side_effect=OSError("no dir"),
            ),
            patch(
                "personalscraper.indexer.fingerprint.oshash",
                return_value=fake_oshash,
            ),
        ):
            _enrich_one_file(
                conn,
                file_id,
                Path("/mnt/retry/001-MOVIES/TestMovie/movie.mkv"),
                None,  # item_id — no release linkage needed for oshash test
                None,  # wrapper — stream extraction skipped
            )

        after = conn.execute("SELECT oshash FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert after["oshash"] == fake_oshash, (
            f"Expected oshash='{fake_oshash}' after enrich retry; got: {after['oshash']!r}"
        )

    def test_enrich_skips_oshash_step_when_already_set(self) -> None:
        """_enrich_one_file does NOT overwrite an existing non-NULL oshash.

        If oshash is already populated the step must be a no-op so that a
        transient I/O error during recomputation cannot silently wipe good data.
        """
        conn = _make_conn()
        _, path_id, _ = _seed_file_with_null_oshash(conn)

        # Overwrite the seeded NULL with a known good oshash.
        good_oshash = "1122334455667788"
        conn.execute(
            "UPDATE media_file SET oshash = ? WHERE path_id = ?",
            (good_oshash, path_id),
        )

        file_id: int = conn.execute("SELECT id FROM media_file WHERE path_id = ?", (path_id,)).fetchone()["id"]

        # Patch computation to a *different* value — must NOT be used.
        with (
            patch(
                "personalscraper.indexer.scanner._modes.enrich.os.scandir",
                side_effect=OSError("no dir"),
            ),
            patch(
                "personalscraper.indexer.fingerprint.oshash",
                return_value="ffffffffffffffff",
            ),
        ):
            _enrich_one_file(
                conn,
                file_id,
                Path("/mnt/retry/001-MOVIES/TestMovie/movie.mkv"),
                None,
                None,
            )

        after = conn.execute("SELECT oshash FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert after["oshash"] == good_oshash, (
            f"Existing oshash '{good_oshash}' was overwritten; got: {after['oshash']!r}"
        )

    def test_enrich_oshash_oserror_is_soft(self) -> None:
        """OSError during oshash recomputation is logged and swallowed (fail-soft).

        enriched_at must still be updated so the file is not re-queued infinitely.
        """
        conn = _make_conn()
        _, _, file_id = _seed_file_with_null_oshash(conn)

        with (
            patch(
                "personalscraper.indexer.scanner._modes.enrich.os.scandir",
                side_effect=OSError("no dir"),
            ),
            patch(
                "personalscraper.indexer.fingerprint.oshash",
                side_effect=OSError("read error"),
            ),
        ):
            # Must not raise.
            _enrich_one_file(
                conn,
                file_id,
                Path("/mnt/retry/001-MOVIES/TestMovie/movie.mkv"),
                None,
                None,
            )

        row = conn.execute("SELECT oshash, enriched_at FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert row["oshash"] is None, "oshash must remain NULL after failed recomputation"
        assert row["enriched_at"] is not None, "enriched_at must be set even after OSError"


# ---------------------------------------------------------------------------
# DEV #52 — Full walker preserves non-NULL oshash on UPDATE; retries NULL
# ---------------------------------------------------------------------------


class TestWalkerRetriesOshashOnExistingNull:
    """_upsert_file_row UPDATE path handles oshash correctly on existing rows (DEV #52).

    Two invariants:
    1. If the existing oshash is non-NULL and the new computation returns NULL
       (transient OSError), the existing good value must NOT be wiped.
    2. If the existing oshash IS NULL and the new computation returns a value,
       the NULL must be replaced (retry succeeds).
    """

    def test_walker_retries_oshash_on_existing_null(self) -> None:
        """UPDATE with a non-NULL oshash_value fills a previously-NULL oshash row.

        This is the core DEV #52 contract: the full walker visits an existing
        Stage-A row (oshash=NULL) and successfully computes an oshash; the row
        must be updated to reflect the new value.
        """
        conn = _make_conn()
        now = int(time.time())

        # Insert a path row so _upsert_file_row can find the file.
        disk_id: int = conn.execute(
            """
            INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes)
            VALUES ('uuid-walker', 'WalkerDisk', '/mnt/walk', ?, 1, 0)
            """,
            (now,),
        ).lastrowid  # type: ignore[assignment]

        path_id: int = conn.execute(
            "INSERT INTO path (disk_id, rel_path) VALUES (?, '.')",
            (disk_id,),
        ).lastrowid  # type: ignore[assignment]

        # Insert initial Stage-A row with oshash=NULL.
        conn.execute(
            """
            INSERT INTO media_file (
                release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
                oshash, xxh3_partial, xxh3_full, scan_generation,
                last_verified_at, enriched_at, miss_strikes, deleted_at
            ) VALUES (NULL, ?, 'film.mkv', 1048576, ?, NULL,
                      NULL, NULL, NULL, 1, ?, NULL, 0, NULL)
            """,
            (path_id, now * 1_000_000_000, now),
        )

        # Precondition: oshash is NULL.
        before = conn.execute(
            "SELECT oshash FROM media_file WHERE path_id = ? AND filename = 'film.mkv'",
            (path_id,),
        ).fetchone()
        assert before["oshash"] is None, "precondition: oshash must be NULL"

        # Second walk: computation succeeds — oshash must be populated.
        new_oshash = "deadbeefcafebabe"
        _upsert_file_row(
            conn,
            path_id=path_id,
            filename="film.mkv",
            size_bytes=1048576,
            mtime_ns=now * 1_000_000_000,
            ctime_ns=None,
            generation=2,
            oshash_value=new_oshash,
        )

        after = conn.execute(
            "SELECT oshash FROM media_file WHERE path_id = ? AND filename = 'film.mkv'",
            (path_id,),
        ).fetchone()
        assert after["oshash"] == new_oshash, (
            f"Expected oshash='{new_oshash}' after walker retry; got: {after['oshash']!r}"
        )

    def test_walker_preserves_good_oshash_on_recompute_failure(self) -> None:
        """UPDATE with oshash_value=None must NOT wipe an existing non-NULL oshash.

        When recomputation fails (OSError → None) for an existing row that already
        has a good oshash, the DB value must be preserved (COALESCE semantics).
        """
        conn = _make_conn()
        now = int(time.time())

        disk_id: int = conn.execute(
            """
            INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes)
            VALUES ('uuid-preserve', 'PreserveDisk', '/mnt/preserve', ?, 1, 0)
            """,
            (now,),
        ).lastrowid  # type: ignore[assignment]

        path_id: int = conn.execute(
            "INSERT INTO path (disk_id, rel_path) VALUES (?, '.')",
            (disk_id,),
        ).lastrowid  # type: ignore[assignment]

        good_oshash = "0011223344556677"
        conn.execute(
            """
            INSERT INTO media_file (
                release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
                oshash, xxh3_partial, xxh3_full, scan_generation,
                last_verified_at, enriched_at, miss_strikes, deleted_at
            ) VALUES (NULL, ?, 'film.mkv', 1048576, ?, NULL,
                      ?, NULL, NULL, 1, ?, NULL, 0, NULL)
            """,
            (path_id, now * 1_000_000_000, good_oshash, now),
        )

        # Second walk: recomputation fails → oshash_value=None.
        _upsert_file_row(
            conn,
            path_id=path_id,
            filename="film.mkv",
            size_bytes=1048576,
            mtime_ns=now * 1_000_000_000,
            ctime_ns=None,
            generation=2,
            oshash_value=None,  # simulates OSError during recomputation
        )

        after = conn.execute(
            "SELECT oshash FROM media_file WHERE path_id = ? AND filename = 'film.mkv'",
            (path_id,),
        ).fetchone()
        assert after["oshash"] == good_oshash, (
            f"Good oshash '{good_oshash}' was wiped by a failed recomputation; got: {after['oshash']!r}"
        )
