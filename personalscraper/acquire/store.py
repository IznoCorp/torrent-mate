"""Concrete ``AcquireStore`` over ``core/sqlite``: 6 sub-stores, lock-free reads.

One ``acquire.db`` file shared by six sub-store method namespaces
(``store.follow.*``, ``store.wanted.*``, ``store.seed.*``, ``store.ratio.*``,
``store.cross_seed.*``, ``store.watch.*``) over a single connection — matching
the indexer precedent where one DB file backs many logical writers (no
3-file/3-lock split).

Concurrency model (CORRECTED — see DESIGN §6.3):
    Cross-process single-writer is provided by **SQLite itself** — WAL mode +
    an explicit ``BEGIN IMMEDIATE`` on every write (:func:`_write_tx`) +
    ``busy_timeout=5000`` (in the canonical PRAGMA set).  This is exactly the
    model used by the indexer outbox publisher and the Phase-5 lock-free seed-
    obligation writer.  The store does **NOT** hold a lifetime ``FileLock``.

    The core ``db_lock`` (FileLock) is taken **only briefly** around
    open + migrate (idempotent ``apply_migrations`` — a no-op once the schema is
    current), then released immediately.  It is a **strict leaf**: never held
    across an FS operation or a qBit/Transmission HTTP call, never acquired with
    ``timeout=0``, never held for the store's lifetime.  Total lock order
    (``pipeline.lock > indexer_lock > acquire.db.lock``) is unchanged; the
    ``acquire.db.lock`` is now only the brief migration lock.

    **Reads are lock-free** (WAL).  No lock anywhere on the read path — this is
    a hard requirement of the Phase-4/5 fail-open delete-permit reader, which
    must never block on or contend for the writer lock.

Lazy open:
    :func:`build_acquire_store` returns an inert handle — it opens nothing (no
    ``mkdir``, no connection, no lock, no migration).  The connection opens on
    the **first sub-store access** via :meth:`ConcreteAcquireStore._ensure_open`.
    Commands that never touch acquire state (e.g. the read-only JSON CLI
    commands, the library-index cron) open nothing and take no lock — so the
    shared composition root does NOT serialize unrelated commands.  Open and
    migration errors (``AcquireCorruptError`` / ``AcquireMigrationError`` /
    ``AcquireLockError``) therefore surface at **first access**, not at boot;
    this is intentional and fail-open-friendly (the future delete-permit treats
    store-unavailable as ALLOW).

Connection: opened by :func:`personalscraper.core.sqlite.open_db`, which uses
``isolation_level=None`` (autocommit).  Writes are wrapped in explicit
``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK`` (indexer convention) so a failed
write does not leave a half-applied transaction.  ``conn.row_factory`` is set to
:class:`sqlite3.Row` lazily before SELECTs so row mappers can index by column
name.

``close()`` is **fail-soft**: if a connection was opened it is closed without
raising; it is idempotent (double-close is safe) and a pure no-op when the store
was never opened, honoring ``AcquireContext.close()``'s no-suppress contract.

Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``);
event names ``acquire.store.*``.  Imports: ``core/``, ``conf/`` + stdlib only.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from personalscraper.acquire._aired_store import _AiredSubStore  # noqa: PLC0415
from personalscraper.acquire._cross_seed_store import _CrossSeedSubStore  # noqa: PLC0415
from personalscraper.acquire._store_rows import (
    _media_ref_to_json,
    _row_to_followed,
    _row_to_ratio,
    _row_to_seed,
)
from personalscraper.acquire._wanted_store import _WantedSubStore  # noqa: PLC0415
from personalscraper.acquire._watch_store import _WatchSubStore  # noqa: PLC0415
from personalscraper.acquire.domain import (
    FollowedSeries,
    RatioState,
    SeedObligation,
)
from personalscraper.acquire.errors import (
    AcquireCorruptError,
    AcquireLockError,
    AcquireMigrationError,
)
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.core.sqlite import apply_migrations, db_lock, open_db
from personalscraper.core.sqlite._open import OpenDbErrorFactories
from personalscraper.logger import get_logger

log = get_logger("acquire.store")

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Generous timeout for the BRIEF open+migrate lock.  apply_migrations is
# idempotent (a no-op once user_version is current), so the steady-state path
# holds this lock for microseconds; the timeout only matters on a genuine first-
# boot race where two processes try to create the schema at once.  It is NOT
# timeout=0: that was the lifetime-lock regression and is wrong for a migration
# lock that several short-lived processes can legitimately contend for.
_MIGRATION_LOCK_TIMEOUT_S = 10.0

# Factory bundle so the core (event-free) open_db raises the rich, attribute-
# bearing AcquireCorruptError through the acquire open path.  Only `corrupt` is
# wired: the other failure shapes (invalid-path / disk-full / fk-orphans) are
# already prevented upstream (AcquireConfig WAL-safety validator; no FKs that an
# external writer could orphan on a fresh acquire.db) and keep their bare core
# markers, which still subclass the same hierarchy.
_OPEN_DB_ERROR_FACTORIES = OpenDbErrorFactories(corrupt=AcquireCorruptError)


# ---------------------------------------------------------------------------
# Write transaction helper
# ---------------------------------------------------------------------------


@contextmanager
def _write_tx(conn: sqlite3.Connection) -> Generator[None, None, None]:
    """Run a write transaction with explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK.

    The connection is opened in autocommit mode (``isolation_level=None``), so
    an explicit ``BEGIN IMMEDIATE`` is required to take the writer lock for the
    duration of the mutation.  On any exception the transaction is rolled back
    and the exception re-raised.

    Args:
        conn: The shared :class:`sqlite3.Connection` to ``acquire.db``.

    Yields:
        ``None`` — the transaction is open for the duration of the ``with``
        block.

    Raises:
        Exception: Whatever the wrapped write raises (after rollback).
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


# ---------------------------------------------------------------------------
# Sub-stores (method namespaces over the shared connection)
# ---------------------------------------------------------------------------


class _FollowSubStore:
    """Writer + reader for the ``followed_series`` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with the shared connection.

        Args:
            conn: Shared :class:`sqlite3.Connection` to ``acquire.db``.
        """
        self._conn = conn

    def add(self, series: FollowedSeries) -> int:
        """Insert a :class:`FollowedSeries` row (idempotent) and return its rowid.

        The ``ux_followed_media_ref`` UNIQUE index (migration 004) makes
        ``media_ref_json`` the natural key.  A second add of the same provider-ID
        tuple therefore does not insert a duplicate: it hits
        ``ON CONFLICT(media_ref_json)`` and reactivates the existing row
        (``active=1``) while refreshing its ``title`` from the new payload.  The
        surviving rowid is read back via ``RETURNING id`` — ``cur.lastrowid`` is
        unreliable on the DO-UPDATE (conflict) path, whereas ``RETURNING`` yields
        the affected row's id for both the INSERT and the UPDATE branch.

        This closes the race the old plain-INSERT + app-level ``find_by_ref``
        dedup left open (two concurrent adds of the same ref could both insert):
        the second concurrent ``BEGIN IMMEDIATE`` serialises behind the first and
        then hits the conflict path — exactly one active row, no
        ``IntegrityError`` leaks to the caller.

        Args:
            series: The :class:`FollowedSeries` to persist.

        Returns:
            The rowid of the surviving row (freshly inserted, or the reactivated
            pre-existing row on a duplicate ``media_ref_json``).
        """
        with _write_tx(self._conn):
            row = self._conn.execute(
                """
                INSERT INTO followed_series
                  (media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(media_ref_json) DO UPDATE SET
                  active = 1,
                  title = excluded.title,
                  kind = excluded.kind
                RETURNING id
                """,
                (
                    _media_ref_to_json(series.media_ref),
                    series.title,
                    1 if series.active else 0,
                    series.quality_profile_json,
                    series.cadence_json,
                    series.added_at,
                    series.kind,
                ),
            ).fetchone()
        assert row is not None  # noqa: S101 — RETURNING always yields the affected row
        return int(row[0])

    def get(self, followed_id: int) -> FollowedSeries | None:
        """Return the :class:`FollowedSeries` for *followed_id*, or ``None``.

        Args:
            followed_id: Rowid of the ``followed_series`` row.

        Returns:
            The :class:`FollowedSeries` if present, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT id, media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind
            FROM followed_series WHERE id = ?
            """,
            (followed_id,),
        ).fetchone()
        return _row_to_followed(row) if row is not None else None

    def find_by_ref(self, media_ref: MediaRef) -> FollowedSeries | None:
        """Return the :class:`FollowedSeries` keyed on *media_ref*, or ``None``.

        Matches on the **primary available provider ID** (tvdb > tmdb > imdb),
        using ``json_extract`` on the ``media_ref_json`` column.  This ensures
        that a lookup with ``tvdb_id`` X matches any stored row whose
        ``tvdb_id`` is X, regardless of the other IDs present — and likewise
        for ``tmdb_id`` or ``imdb_id`` when the higher-priority key is absent.

        Used by the follow CLI to enforce the idempotent-add / reactivate logic.

        Args:
            media_ref: Provider-ID key to look up.

        Returns:
            The :class:`FollowedSeries` (with ``id`` populated) if found, else
            ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        if media_ref.tvdb_id is not None:
            row = self._conn.execute(
                """
                SELECT id, media_ref_json, title, active,
                       quality_profile_json, cadence_json, added_at, kind
                FROM followed_series
                WHERE json_extract(media_ref_json, '$.tvdb_id') = ?
                ORDER BY id LIMIT 1
                """,
                (media_ref.tvdb_id,),
            ).fetchone()
        elif media_ref.tmdb_id is not None:
            row = self._conn.execute(
                """
                SELECT id, media_ref_json, title, active,
                       quality_profile_json, cadence_json, added_at, kind
                FROM followed_series
                WHERE json_extract(media_ref_json, '$.tmdb_id') = ?
                ORDER BY id LIMIT 1
                """,
                (media_ref.tmdb_id,),
            ).fetchone()
        elif media_ref.imdb_id is not None:
            row = self._conn.execute(
                """
                SELECT id, media_ref_json, title, active,
                       quality_profile_json, cadence_json, added_at, kind
                FROM followed_series
                WHERE json_extract(media_ref_json, '$.imdb_id') = ?
                ORDER BY id LIMIT 1
                """,
                (media_ref.imdb_id,),
            ).fetchone()
        else:
            return None
        return _row_to_followed(row) if row is not None else None

    def list_active(self) -> list[FollowedSeries]:
        """Return all active ``followed_series`` rows, ordered by id.

        Returns:
            A list of :class:`FollowedSeries` where ``active=True``,
            possibly empty.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind
            FROM followed_series
            WHERE active = 1
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_followed(r) for r in rows]

    def list_all(self) -> list[FollowedSeries]:
        """Return all ``followed_series`` rows (active and inactive), ordered by id.

        Used by ``follow list --all``.

        Returns:
            A list of all :class:`FollowedSeries`, possibly empty.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind
            FROM followed_series
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_followed(r) for r in rows]

    def set_active(self, followed_id: int, active: bool) -> None:
        """Set the ``active`` flag on a ``followed_series`` row.

        Used for both soft unfollow (``active=False``) and refollow
        (``active=True``).  Runs inside a single ``_write_tx`` BEGIN IMMEDIATE
        so concurrent callers serialize correctly.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            active: ``True`` to refollow; ``False`` to soft-unfollow.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET active = ? WHERE id = ?",
                (1 if active else 0, followed_id),
            )

    def set_kind(self, followed_id: int, kind: str) -> None:
        """Update the ``kind`` ('movie'|'show') of a ``followed_series`` row.

        Used when re-following an inactive item as a different kind (§5: a film
        once followed as a series must land ``kind='movie'`` on re-follow, else
        its lifecycle stays series-shaped).

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            kind: ``'movie'`` or ``'show'``.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET kind = ? WHERE id = ?",
                (kind, followed_id),
            )

    def set_cadence(self, followed_id: int, cadence_json: str | None) -> None:
        """Update the ``cadence_json`` column for a followed series.

        Runs inside a single ``_write_tx`` BEGIN IMMEDIATE so concurrent
        callers (web, pipeline, watcher) serialize correctly via SQLite's
        write lock.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            cadence_json: The serialized cadence dict, or ``None`` to clear.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET cadence_json = ? WHERE id = ?",
                (cadence_json, followed_id),
            )

    def set_metadata(
        self,
        followed_id: int,
        *,
        poster_url: str | None,
        overview: str | None,
        year: int | None,
    ) -> None:
        """Overwrite the OBJ3 card metadata columns for a followed series.

        Persists the ``poster_url`` / ``overview`` / ``year`` captured from an
        add-by-search candidate. All three columns are written together (a
        ``None`` clears its column), matching the web layer's former raw
        ``UPDATE``. Runs inside a single ``_write_tx`` BEGIN IMMEDIATE so the web
        route no longer opens its own connection — single-writer discipline
        (ACQUIRE-09).

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            poster_url: Poster URL, or ``None`` to clear it.
            overview: Overview/synopsis text, or ``None`` to clear it.
            year: Release/first-air year, or ``None`` to clear it.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET poster_url = ?, overview = ?, year = ? WHERE id = ?",
                (poster_url, overview, year, followed_id),
            )


class _SeedSubStore:
    """Writer + reader for the ``seed_obligation`` table (deletion authority)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with the shared connection.

        Args:
            conn: Shared :class:`sqlite3.Connection` to ``acquire.db``.
        """
        self._conn = conn

    def add(self, obligation: SeedObligation) -> int:
        """Insert a :class:`SeedObligation` row and return its rowid.

        Args:
            obligation: The :class:`SeedObligation` to persist.

        Returns:
            The rowid of the newly inserted row.
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO seed_obligation
                  (info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obligation.info_hash,
                    obligation.source_tracker,
                    obligation.dispatched_path,
                    obligation.min_seed_time_s,
                    obligation.min_ratio,
                    obligation.added_at,
                    obligation.satisfied_at,
                    obligation.breached_at,
                    obligation.released_at,
                ),
            )
            row_id = cur.lastrowid
        assert row_id is not None  # noqa: S101 — INSERT always sets lastrowid
        return row_id

    def find_active_by_hash(self, info_hash: str) -> SeedObligation | None:
        """Return the first active obligation carrying *info_hash*, or ``None``.

        Active = ``released_at IS NULL`` (mirrors :meth:`find_active_under`).
        Used by the grab-time writer's dedup guard and by the dispatch-time
        correlation to backfill ``dispatched_path`` instead of duplicating.

        Args:
            info_hash: Torrent info-hash (hex string).

        Returns:
            The active :class:`SeedObligation`, or ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at
            FROM seed_obligation
            WHERE info_hash = ? AND released_at IS NULL
            LIMIT 1
            """,
            (info_hash,),
        ).fetchone()
        return _row_to_seed(row) if row is not None else None

    def set_dispatched_path(self, info_hash: str, path: str) -> int:
        """Backfill ``dispatched_path`` on the active obligations for *info_hash*.

        Grab-time obligations are written with ``dispatched_path = NULL`` (the
        media is not on disk yet); the dispatch-time correlation calls this to
        attach the destination so path-based HnR protection engages.

        Args:
            info_hash: Torrent info-hash (hex string).
            path: Absolute dispatched destination path.

        Returns:
            Number of rows updated.
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                "UPDATE seed_obligation SET dispatched_path = ? WHERE info_hash = ? AND released_at IS NULL",
                (path, info_hash),
            )
            return cur.rowcount

    def find_by_dispatched_path(self, path: Path) -> SeedObligation | None:
        """Return the first active obligation for *dispatched_path*, or ``None``.

        An obligation is "active" when it is neither satisfied nor released.

        Args:
            path: The dispatched media path to look up (exact match).

        Returns:
            A :class:`SeedObligation` if found, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at
            FROM seed_obligation
            WHERE dispatched_path = ?
              AND satisfied_at IS NULL
              AND released_at IS NULL
            LIMIT 1
            """,
            (str(path),),
        ).fetchone()
        return _row_to_seed(row) if row is not None else None

    def find_active_under(self, path: Path) -> list[SeedObligation]:
        """Return all active obligations for *path* or any of its descendants.

        Matches obligations whose ``dispatched_path`` is either exactly *path*
        OR a descendant of *path* (i.e. starts with ``path/``).  Uses a
        boundary-safe LIKE with ESCAPE so that ``/a/b`` matches ``/a/b/x``
        but NOT ``/a/bc`` or ``/a/b-other``.  Only returns obligations where
        ``released_at IS NULL`` (still active).

        Args:
            path: Absolute path to match against ``dispatched_path``.

        Returns:
            A list of :class:`SeedObligation` (possibly empty).
        """
        path_str = str(path)
        # Escape LIKE wildcards in the path prefix so that literal %
        # and _ characters in the path string don't act as patterns.
        escaped = path_str.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like_pattern = escaped + "/%"

        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at
            FROM seed_obligation
            WHERE (dispatched_path = ? OR dispatched_path LIKE ? ESCAPE '\\')
              AND released_at IS NULL
            """,
            (path_str, like_pattern),
        ).fetchall()
        return [_row_to_seed(r) for r in rows]

    def mark_satisfied(self, obligation_id: int, satisfied_at: int) -> None:
        """Set ``satisfied_at`` on a ``seed_obligation`` row.

        Args:
            obligation_id: Rowid of the obligation.
            satisfied_at: Unix epoch seconds.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE seed_obligation SET satisfied_at = ? WHERE id = ?",
                (satisfied_at, obligation_id),
            )

    def mark_breached(self, obligation_id: int, breached_at: int) -> None:
        """Set ``breached_at`` on a ``seed_obligation`` row.

        Args:
            obligation_id: Rowid of the obligation.
            breached_at: Unix epoch seconds.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE seed_obligation SET breached_at = ? WHERE id = ?",
                (breached_at, obligation_id),
            )

    def mark_breached_under(self, path: Path, breached_at: int) -> int:
        """Set ``breached_at`` on every active obligation under *path*.

        Marks the breach (DESIGN §7.3) for all still-active obligations whose
        ``dispatched_path`` is either exactly *path* OR a descendant of *path*
        (boundary-safe LIKE with ESCAPE, mirroring :meth:`find_active_under` so
        ``D/child`` is matched but ``D-other`` / ``Dx`` are not). Only rows
        where ``released_at IS NULL`` are touched, and only those not already
        breached (``breached_at IS NULL``), so a re-run is idempotent.

        This avoids the id-juggling the deletion-time caller would otherwise
        need: :meth:`find_active_under` returns value objects WITHOUT the row
        id, so a path-scoped UPDATE is the natural breach primitive.

        Args:
            path: Absolute path whose active obligations should be breached.
            breached_at: Unix epoch seconds to stamp on ``breached_at``.

        Returns:
            The number of obligation rows updated.
        """
        path_str = str(path)
        # Escape LIKE wildcards in the path prefix so that literal % and _
        # characters in the path string don't act as patterns (same scheme as
        # find_active_under to keep the descendant boundary safe).
        escaped = path_str.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like_pattern = escaped + "/%"

        with _write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE seed_obligation
                SET breached_at = ?
                WHERE (dispatched_path = ? OR dispatched_path LIKE ? ESCAPE '\\')
                  AND released_at IS NULL
                  AND breached_at IS NULL
                """,
                (breached_at, path_str, like_pattern),
            )
            count = cur.rowcount
        return count if count is not None else 0


class _RatioSubStore:
    """Reader + upsert for the ``ratio_state`` table (data-carrier; Ratio C1)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with the shared connection.

        Args:
            conn: Shared :class:`sqlite3.Connection` to ``acquire.db``.
        """
        self._conn = conn

    def get(self, tracker_name: str) -> RatioState | None:
        """Return the :class:`RatioState` for *tracker_name*, or ``None``.

        Args:
            tracker_name: The tracker primary key.

        Returns:
            The :class:`RatioState` if present, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT tracker_name, observed_ratio, accumulated_seed_time_s,
                   hnr_count, updated_at
            FROM ratio_state WHERE tracker_name = ?
            """,
            (tracker_name,),
        ).fetchone()
        return _row_to_ratio(row) if row is not None else None

    def upsert(self, state: RatioState) -> None:
        """Insert or replace the ``ratio_state`` row keyed on ``tracker_name``.

        Args:
            state: The :class:`RatioState` to persist.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                """
                INSERT INTO ratio_state
                  (tracker_name, observed_ratio, accumulated_seed_time_s,
                   hnr_count, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tracker_name) DO UPDATE SET
                  observed_ratio = excluded.observed_ratio,
                  accumulated_seed_time_s = excluded.accumulated_seed_time_s,
                  hnr_count = excluded.hnr_count,
                  updated_at = excluded.updated_at
                """,
                (
                    state.tracker_name,
                    state.observed_ratio,
                    state.accumulated_seed_time_s,
                    state.hnr_count,
                    state.updated_at,
                ),
            )


# ---------------------------------------------------------------------------
# Concrete store
# ---------------------------------------------------------------------------


class ConcreteAcquireStore:
    """Concrete implementation of the :class:`AcquireStore` protocol.

    Lazy + lock-free-on-the-read-path.  Construction opens nothing: the
    connection is opened (and migrations applied under a brief leaf lock) on the
    first sub-store access.  Cross-process single-writer is SQLite-native (WAL +
    ``BEGIN IMMEDIATE`` + ``busy_timeout``); no ``FileLock`` is held for the
    store's lifetime.

    The six sub-stores are exposed as properties (``follow`` / ``wanted`` /
    ``seed`` / ``ratio`` / ``cross_seed`` / ``watch``) that ensure-open on
    first touch and return a sub-store bound to the shared connection.

    Attributes:
        follow: ``followed_series`` sub-store (lazy).
        wanted: ``wanted`` sub-store (lazy).
        seed: ``seed_obligation`` sub-store (deletion authority, lazy).
        ratio: ``ratio_state`` sub-store (data-carrier, lazy).
        cross_seed: ``cross_seed_history`` + ``cross_seed_quota`` sub-store (lazy).
        watch: ``watch_state`` KV sub-store (watcher daemon state, lazy).
    """

    def __init__(self, db_path: Path) -> None:
        """Initialise an INERT handle for ``db_path`` (no I/O).

        No directory is created, no connection is opened, no lock is taken and
        no migration is run until the first sub-store access.

        Args:
            db_path: Path to ``acquire.db`` (resolved by the config layer).
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._closed = False
        self._follow: _FollowSubStore | None = None
        self._wanted: _WantedSubStore | None = None
        self._aired: _AiredSubStore | None = None
        self._seed: _SeedSubStore | None = None
        self._ratio: _RatioSubStore | None = None
        self._cross_seed: _CrossSeedSubStore | None = None
        self._watch: _WatchSubStore | None = None

    def _ensure_open(self) -> sqlite3.Connection:
        """Open the connection and migrate the schema on first access.

        Takes the core ``db_lock`` (FileLock) with a generous timeout ONLY
        around ``open_db`` + ``apply_migrations`` and releases it immediately —
        the lock spans a single ``with`` block, never the store's lifetime.
        ``apply_migrations`` is idempotent, so the steady-state path holds the
        lock for microseconds.  After this, ``self._conn`` stays open with no
        held lock; subsequent calls return it directly.

        Returns:
            The open :class:`sqlite3.Connection` to ``acquire.db``.

        Raises:
            RuntimeError: If the store has already been closed.
            AcquireLockError: If the brief migration lock cannot be acquired
                within :data:`_MIGRATION_LOCK_TIMEOUT_S`.
            AcquireCorruptError: If ``acquire.db`` is malformed.
            AcquireMigrationError: If a pending migration fails to apply.
        """
        if self._closed:
            raise RuntimeError("AcquireStore is closed")
        if self._conn is not None:
            return self._conn

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # Brief leaf lock around open+migrate only (generous timeout, NOT 0).
        # Released the instant the `with` block exits; the connection survives.
        with db_lock(
            self._db_path,
            timeout=_MIGRATION_LOCK_TIMEOUT_S,
            error_factory=AcquireLockError,
        ):
            conn = open_db(self._db_path, errors=_OPEN_DB_ERROR_FACTORIES)
            apply_migrations(conn, _MIGRATIONS_DIR, error_factory=AcquireMigrationError)

        self._conn = conn
        log.info("acquire.store.opened", db_path=str(self._db_path))
        return conn

    @property
    def follow(self) -> _FollowSubStore:
        """``followed_series`` sub-store (ensures the store is open)."""
        conn = self._ensure_open()
        if self._follow is None:
            self._follow = _FollowSubStore(conn)
        return self._follow

    @property
    def wanted(self) -> _WantedSubStore:
        """``wanted`` sub-store (ensures the store is open)."""
        if self._wanted is None:
            self._wanted = _WantedSubStore(self._ensure_open(), _write_tx)
        return self._wanted

    @property
    def aired(self) -> _AiredSubStore:
        """``aired_episode`` catalog-cache sub-store (ensures the store is open)."""
        if self._aired is None:
            self._aired = _AiredSubStore(self._ensure_open(), _write_tx)
        return self._aired

    @property
    def seed(self) -> _SeedSubStore:
        """``seed_obligation`` sub-store (deletion authority; ensures open)."""
        conn = self._ensure_open()
        if self._seed is None:
            self._seed = _SeedSubStore(conn)
        return self._seed

    @property
    def ratio(self) -> _RatioSubStore:
        """``ratio_state`` sub-store (data-carrier; ensures open)."""
        conn = self._ensure_open()
        if self._ratio is None:
            self._ratio = _RatioSubStore(conn)
        return self._ratio

    @property
    def cross_seed(self) -> _CrossSeedSubStore:
        """``cross_seed_history`` + ``cross_seed_quota`` sub-store (ensures open)."""
        conn = self._ensure_open()
        if self._cross_seed is None:
            self._cross_seed = _CrossSeedSubStore(conn, _write_tx)
        return self._cross_seed

    @property
    def watch(self) -> _WatchSubStore:
        """``watch_state`` KV sub-store (ensures open)."""
        if self._watch is None:
            self._watch = _WatchSubStore(self._ensure_open(), _write_tx)
        return self._watch

    def close(self) -> None:
        """Close the connection if one was opened (fail-soft, idempotent).

        Never raises (honors ``AcquireContext.close()``'s no-suppress contract):
        a connection-close error is swallowed and logged.  Double-close is a
        no-op, and close-without-open (the store was never accessed) is a pure
        no-op — there is no lifetime lock to release.
        """
        if self._closed:
            return
        self._closed = True
        if self._conn is None:
            # Never opened — nothing to release.
            return
        try:
            self._conn.close()
        except Exception as exc:  # noqa: BLE001 — fail-soft close contract
            log.warning("acquire.store.close_conn_failed", error=str(exc))
        log.info("acquire.store.closed", db_path=str(self._db_path))


def build_acquire_store(config: AcquireConfig) -> ConcreteAcquireStore:
    """Build an INERT :class:`ConcreteAcquireStore` handle (no I/O at build).

    Building opens nothing: no directory is created, no connection is opened, no
    lock is taken and no migration runs.  The connection opens lazily on the
    first sub-store access (:meth:`ConcreteAcquireStore._ensure_open`), at which
    point open/migration errors (``AcquireLockError`` / ``AcquireCorruptError`` /
    ``AcquireMigrationError``) may surface.  This keeps the shared composition
    root from serializing unrelated commands and is fail-open-friendly for the
    deletion path.

    Args:
        config: :class:`AcquireConfig` with a resolved ``db_path``.

    Returns:
        An inert :class:`ConcreteAcquireStore`; opens on first use.

    Raises:
        ValueError: If ``config.db_path`` is ``None`` (must be resolved by
            ``Config._resolve_derived_paths`` before this call).
    """
    if config.db_path is None:
        raise ValueError("AcquireConfig.db_path must be resolved before calling build_acquire_store")
    return ConcreteAcquireStore(config.db_path)


# Public alias so ``isinstance(store, AcquireStore)`` reads naturally at call
# sites that import the protocol name from this module.
AcquireStore = ConcreteAcquireStore

__all__ = [
    "AcquireCorruptError",
    "AcquireLockError",
    "AcquireMigrationError",
    "AcquireStore",
    "ConcreteAcquireStore",
    "build_acquire_store",
]
