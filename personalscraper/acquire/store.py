"""Concrete ``AcquireStore`` over ``core/sqlite``: 4 sub-stores, lock-free reads.

One ``acquire.db`` file shared by four sub-store method namespaces
(``store.follow.*``, ``store.wanted.*``, ``store.seed.*``, ``store.ratio.*``)
over a single connection — matching the indexer precedent where one DB file
backs many logical writers (no 3-file/3-lock split).

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
event names ``acquire.store.*``.

Import direction: ``core/``, ``conf/`` + stdlib only — never indexer/ or triage.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
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

    The four sub-stores are exposed as properties (``follow`` / ``wanted`` /
    ``seed`` / ``ratio``) that ensure-open on first touch and return a sub-store
    bound to the shared connection.

    Attributes:
        follow: ``followed_series`` sub-store (lazy).
        wanted: ``wanted`` sub-store (lazy).
        seed: ``seed_obligation`` sub-store (deletion authority, lazy).
        ratio: ``ratio_state`` sub-store (data-carrier, lazy).
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
        self._seed: _SeedSubStore | None = None
        self._ratio: _RatioSubStore | None = None

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
        conn = self._ensure_open()
        if self._wanted is None:
            self._wanted = _WantedSubStore(conn)
        return self._wanted

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
