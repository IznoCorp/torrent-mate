"""Concrete ``AcquireStore`` over ``core/sqlite``: 4 sub-stores, one leaf lock.

One ``acquire.db`` file, one ``acquire.db`` writer lock (via
:func:`personalscraper.core.sqlite.db_lock`, with
:class:`~personalscraper.acquire.errors.AcquireLockError` as the error factory).
Logical write authority is partitioned into method namespaces
(``store.follow.*``, ``store.wanted.*``, ``store.seed.*``, ``store.ratio.*``)
that all share the single connection — matching the indexer precedent where one
lock serializes one DB file (no 3-file/3-lock split).

Lock-scope choice (LEAF-LOCK DISCIPLINE):
    The store acquires the single-writer lock at construction (around
    open → migrate) and **holds it for its entire lifetime**, releasing it only
    in :meth:`ConcreteAcquireStore.close`.  This is sound because the ROADMAP
    mandates a single writer: short-lived stores are built per pipeline step via
    the factory, so the lock is never held across a full pipeline run.  The lock
    is a **strict leaf**: it is never acquired while holding ``pipeline.lock`` or
    ``indexer_lock`` (total order ``pipeline.lock > indexer_lock >
    acquire.db.lock``), and the store performs no FS operation or HTTP call while
    holding it — every method here is a pure DB read/write.

    The dispatch-time seed-obligation writer (Phase 5) is **lock-free** and
    fail-soft (a short raw ``sqlite3`` connection + ``busy_timeout``); it does
    NOT use this lock.  That writer is noted here but not built in RP3.

Connection: opened by :func:`personalscraper.core.sqlite.open_db`, which uses
``isolation_level=None`` (autocommit).  Writes are wrapped in explicit
``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK`` (indexer convention) so a failed
write does not leave a half-applied transaction.  ``conn.row_factory`` is set to
:class:`sqlite3.Row` lazily before SELECTs so row mappers can index by column
name.

``close()`` is **fail-soft**: it releases the connection and the lock without
raising, and is idempotent (double-close is safe), honoring
``AcquireContext.close()``'s no-suppress contract.

Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``);
event names ``acquire.store.*``.

Import direction: ``core/``, ``conf/`` + stdlib only — never indexer/ or triage.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import cast

from personalscraper.acquire.domain import (
    FollowedSeries,
    RatioState,
    SeedObligation,
    WantedItem,
    WantedKind,
    WantedStatus,
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

# Factory bundle so the core (event-free) open_db raises the rich, attribute-
# bearing AcquireCorruptError through the acquire open path.  Only `corrupt` is
# wired: the other failure shapes (invalid-path / disk-full / fk-orphans) are
# already prevented upstream (AcquireConfig WAL-safety validator; no FKs that an
# external writer could orphan on a fresh acquire.db) and keep their bare core
# markers, which still subclass the same hierarchy.
_OPEN_DB_ERROR_FACTORIES = OpenDbErrorFactories(corrupt=AcquireCorruptError)


# ---------------------------------------------------------------------------
# Row mappers (sqlite3.Row -> frozen domain VOs)
# ---------------------------------------------------------------------------


def _media_ref_to_json(ref: MediaRef) -> str:
    """Serialize a :class:`MediaRef` to a compact JSON string.

    Args:
        ref: The provider-ID value object.

    Returns:
        A JSON object string with ``tvdb_id`` / ``tmdb_id`` / ``imdb_id`` keys.
    """
    return json.dumps({"tvdb_id": ref.tvdb_id, "tmdb_id": ref.tmdb_id, "imdb_id": ref.imdb_id})


def _media_ref_from_json(blob: str) -> MediaRef:
    """Deserialize a :class:`MediaRef` from its JSON string.

    Args:
        blob: A JSON object string produced by :func:`_media_ref_to_json`.

    Returns:
        The reconstructed :class:`MediaRef`.
    """
    data = json.loads(blob)
    return MediaRef(
        tvdb_id=data.get("tvdb_id"),
        tmdb_id=data.get("tmdb_id"),
        imdb_id=data.get("imdb_id"),
    )


def _row_to_followed(row: sqlite3.Row) -> FollowedSeries:
    """Map a ``followed_series`` row to a :class:`FollowedSeries`.

    Args:
        row: A :class:`sqlite3.Row` from a ``followed_series`` SELECT.

    Returns:
        The frozen :class:`FollowedSeries` value object.
    """
    return FollowedSeries(
        media_ref=_media_ref_from_json(row["media_ref_json"]),
        title=row["title"],
        added_at=row["added_at"],
        active=bool(row["active"]),
        quality_profile_json=row["quality_profile_json"],
        cadence_json=row["cadence_json"],
    )


def _row_to_wanted(row: sqlite3.Row) -> WantedItem:
    """Map a ``wanted`` row to a :class:`WantedItem`.

    Args:
        row: A :class:`sqlite3.Row` from a ``wanted`` SELECT.

    Returns:
        The frozen :class:`WantedItem` value object.
    """
    return WantedItem(
        media_ref=_media_ref_from_json(row["media_ref_json"]),
        # kind/status are CHECK-constrained columns; cast the raw string to the
        # Literal alias (WantedItem.__post_init__ re-validates at construction).
        kind=cast(WantedKind, row["kind"]),
        status=cast(WantedStatus, row["status"]),
        enqueued_at=row["enqueued_at"],
        followed_id=row["followed_id"],
        season=row["season"],
        episode=row["episode"],
        criteria_json=row["criteria_json"],
        last_search_at=row["last_search_at"],
        attempts=row["attempts"],
    )


def _row_to_seed(row: sqlite3.Row) -> SeedObligation:
    """Map a ``seed_obligation`` row to a :class:`SeedObligation`.

    Args:
        row: A :class:`sqlite3.Row` from a ``seed_obligation`` SELECT.

    Returns:
        The frozen :class:`SeedObligation` value object.
    """
    return SeedObligation(
        info_hash=row["info_hash"],
        source_tracker=row["source_tracker"],
        min_seed_time_s=row["min_seed_time_s"],
        min_ratio=row["min_ratio"],
        added_at=row["added_at"],
        dispatched_path=row["dispatched_path"],
        satisfied_at=row["satisfied_at"],
        breached_at=row["breached_at"],
        released_at=row["released_at"],
    )


def _row_to_ratio(row: sqlite3.Row) -> RatioState:
    """Map a ``ratio_state`` row to a :class:`RatioState`.

    Args:
        row: A :class:`sqlite3.Row` from a ``ratio_state`` SELECT.

    Returns:
        The frozen :class:`RatioState` value object.
    """
    return RatioState(
        tracker_name=row["tracker_name"],
        observed_ratio=row["observed_ratio"],
        accumulated_seed_time_s=row["accumulated_seed_time_s"],
        hnr_count=row["hnr_count"],
        updated_at=row["updated_at"],
    )


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
        """Insert a :class:`FollowedSeries` row and return its rowid.

        Args:
            series: The :class:`FollowedSeries` to persist.

        Returns:
            The rowid of the newly inserted row.
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO followed_series
                  (media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _media_ref_to_json(series.media_ref),
                    series.title,
                    1 if series.active else 0,
                    series.quality_profile_json,
                    series.cadence_json,
                    series.added_at,
                ),
            )
            row_id = cur.lastrowid
        assert row_id is not None  # noqa: S101 — INSERT always sets lastrowid
        return row_id

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
            SELECT media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at
            FROM followed_series WHERE id = ?
            """,
            (followed_id,),
        ).fetchone()
        return _row_to_followed(row) if row is not None else None


class _WantedSubStore:
    """Writer + reader for the ``wanted`` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with the shared connection.

        Args:
            conn: Shared :class:`sqlite3.Connection` to ``acquire.db``.
        """
        self._conn = conn

    def add(self, item: WantedItem) -> int:
        """Insert a :class:`WantedItem` row and return its rowid.

        Args:
            item: The :class:`WantedItem` to persist.

        Returns:
            The rowid of the newly inserted row.
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO wanted
                  (followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.followed_id,
                    _media_ref_to_json(item.media_ref),
                    item.kind,
                    item.season,
                    item.episode,
                    item.status,
                    item.criteria_json,
                    item.enqueued_at,
                    item.last_search_at,
                    item.attempts,
                ),
            )
            row_id = cur.lastrowid
        assert row_id is not None  # noqa: S101 — INSERT always sets lastrowid
        return row_id

    def get(self, wanted_id: int) -> WantedItem | None:
        """Return the :class:`WantedItem` for *wanted_id*, or ``None``.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            The :class:`WantedItem` if present, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts
            FROM wanted WHERE id = ?
            """,
            (wanted_id,),
        ).fetchone()
        return _row_to_wanted(row) if row is not None else None

    def set_status(self, wanted_id: int, status: WantedStatus) -> None:
        """Transition the ``status`` column of a ``wanted`` row.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            status: Target status (one of the CHECK-constrained enum values).
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE wanted SET status = ? WHERE id = ?",
                (status, wanted_id),
            )

    def list_pending(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='pending'``.

        Exercises the ``idx_wanted_pending`` partial index.

        Returns:
            A list of :class:`WantedItem`, possibly empty.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts
            FROM wanted WHERE status = 'pending'
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_wanted(r) for r in rows]


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

    Holds the single ``acquire.db`` writer lock for its entire lifetime and
    exposes the four sub-store namespaces over one shared connection.

    Attributes:
        follow: ``followed_series`` sub-store.
        wanted: ``wanted`` sub-store.
        seed: ``seed_obligation`` sub-store (deletion authority).
        ratio: ``ratio_state`` sub-store (data-carrier).
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        db_path: Path,
        lock_cm: AbstractContextManager[None],
    ) -> None:
        """Initialise with an open connection, the DB path, and the held lock.

        Args:
            conn: Open :class:`sqlite3.Connection` to ``acquire.db`` (PRAGMAs
                applied, migrations run).
            db_path: Path to ``acquire.db`` (for logging + lock-file derivation).
            lock_cm: The *already-entered* ``db_lock`` context manager; released
                by :meth:`close`.  Holding it keeps the writer lock for the
                store's lifetime.
        """
        self._conn = conn
        self._db_path = db_path
        self._lock_cm = lock_cm
        self._closed = False
        self.follow = _FollowSubStore(conn)
        self.wanted = _WantedSubStore(conn)
        self.seed = _SeedSubStore(conn)
        self.ratio = _RatioSubStore(conn)
        log.info("acquire.store.opened", db_path=str(db_path))

    def close(self) -> None:
        """Release the connection and the writer lock (fail-soft, idempotent).

        Never raises (honors ``AcquireContext.close()``'s no-suppress contract):
        connection-close and lock-release errors are swallowed and logged.
        Double-close is a no-op.
        """
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.close()
        except Exception as exc:  # noqa: BLE001 — fail-soft close contract
            log.warning("acquire.store.close_conn_failed", error=str(exc))
        # Release the lifetime lock by exiting the db_lock context manager.
        try:
            self._lock_cm.__exit__(None, None, None)
        except Exception as exc:  # noqa: BLE001 — fail-soft close contract
            log.warning("acquire.store.close_lock_failed", error=str(exc))
        log.info("acquire.store.closed", db_path=str(self._db_path))


def build_acquire_store(config: AcquireConfig) -> ConcreteAcquireStore:
    """Build a :class:`ConcreteAcquireStore` for the given config.

    Acquires the single ``acquire.db`` writer lock (held for the store's
    lifetime), opens ``acquire.db`` with the canonical PRAGMAs, and applies any
    pending migrations.

    Args:
        config: :class:`AcquireConfig` with a resolved ``db_path``.

    Returns:
        A :class:`ConcreteAcquireStore` ready for use.

    Raises:
        ValueError: If ``config.db_path`` is ``None`` (must be resolved by
            ``Config._resolve_derived_paths`` before this call).
        AcquireLockError: If the ``acquire.db`` writer lock is held by a live
            process.
        AcquireCorruptError: If ``acquire.db`` is malformed.
        AcquireMigrationError: If a pending migration fails to apply.
    """
    if config.db_path is None:
        raise ValueError("AcquireConfig.db_path must be resolved before calling build_acquire_store")
    db_path: Path = config.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Acquire the lifetime writer lock FIRST (timeout=0 — fail fast on contention).
    # We enter the db_lock @contextmanager manually so the lock spans the store's
    # lifetime rather than a single `with` block; the entered context manager is
    # handed to the store and `__exit__`-ed in ConcreteAcquireStore.close.
    lock_cm = db_lock(db_path, timeout=0, error_factory=AcquireLockError)
    lock_cm.__enter__()  # raises AcquireLockError on live contention; holds the lock on success

    try:
        conn = open_db(db_path, errors=_OPEN_DB_ERROR_FACTORIES)
        apply_migrations(conn, _MIGRATIONS_DIR, error_factory=AcquireMigrationError)
    except BaseException:
        # Open/migrate failed — release the lock we just took so we don't leak it.
        lock_cm.__exit__(None, None, None)
        raise

    return ConcreteAcquireStore(conn, db_path, lock_cm)


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
