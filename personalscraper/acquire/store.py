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
    obligation writer.  The store does **NOT** hold a lifetime flock.

    The core ``db_lock`` (flock) is taken **only briefly** around
    open + migrate (idempotent ``apply_migrations`` — a no-op once the schema is
    current), then released immediately.  It is a **strict leaf**: never held
    across an FS operation or a qBit/Transmission HTTP call, never acquired with
    ``timeout=0``, never held for the store's lifetime.  The total lock order is
    ``pipeline.lock > indexer_lock > acquire.db.lock > app.db.lock`` (``app.db.lock`` is a
    leaf, see ``app/store/store.py``); the ``acquire.db.lock`` is now only the
    brief migration lock.

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
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

from personalscraper.acquire._aired_store import _AiredSubStore
from personalscraper.acquire._candidate_store import _CandidateSubStore
from personalscraper.acquire._cross_seed_store import _CrossSeedSubStore
from personalscraper.acquire._download_marks import DownloadMarksStore
from personalscraper.acquire._provenance_store import _ProvenanceSubStore
from personalscraper.acquire._requester_store import _RequesterSubStore
from personalscraper.acquire._store_rows import (
    _media_ref_to_json,
    _row_to_followed,
    _row_to_ratio,
    _row_to_seed,
)
from personalscraper.acquire._suggestion_store import _SuggestionSubStore
from personalscraper.acquire._wanted_store import _WantedSubStore
from personalscraper.acquire._watch_store import _WatchSubStore
from personalscraper.acquire.domain import (
    OPEN_WANTED_STATUSES,
    FollowCard,
    FollowedSeries,
    FollowKind,
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


#: The savepoint a write joining an open transaction runs under (SQLite stacks equal names).
_NESTED_WRITE = "acquire_nested_write"


@contextmanager
def _write_tx(conn: sqlite3.Connection) -> Generator[None, None, None]:
    """Run a write transaction with explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK.

    The connection is opened in autocommit mode (``isolation_level=None``), so
    an explicit ``BEGIN IMMEDIATE`` is required to take the writer lock for the
    duration of the mutation.  On any exception the transaction is rolled back
    and the exception re-raised.

    Inside a transaction already open on the connection (a unit of work,
    :meth:`ConcreteAcquireStore.transaction`), the write JOINS it as a savepoint:
    its own failure undoes only its statements, and nothing commits before the
    outer transaction does.

    Args:
        conn: The shared :class:`sqlite3.Connection` to ``acquire.db``.

    Yields:
        ``None`` — the transaction is open for the duration of the ``with``
        block.

    Raises:
        Exception: Whatever the wrapped write raises (after rollback).
    """
    if conn.in_transaction:
        conn.execute(f"SAVEPOINT {_NESTED_WRITE}")
        try:
            yield
        except BaseException:
            conn.execute(f"ROLLBACK TO {_NESTED_WRITE}")
            conn.execute(f"RELEASE {_NESTED_WRITE}")
            raise
        conn.execute(f"RELEASE {_NESTED_WRITE}")
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


# ---------------------------------------------------------------------------
# Follow identity: the ids a follow learns, and the duplicates it reports
# ---------------------------------------------------------------------------


def _learned[T: (int, str)](held: T | None, offered: T | None, held_elsewhere: set[T | None]) -> T | None:
    """Return one provider slot of a follow after an add offered it an id.

    Args:
        held: The id the follow holds in this slot, or ``None``.
        offered: The id the add carries in this slot, or ``None``.
        held_elsewhere: The ids the other rows of the same medium hold in this slot.

    Returns:
        *held* when the follow holds an id (never overwritten), when nothing is offered,
        or when another row already holds the offered id; else the offered id.
    """
    if held is not None or offered is None or offered in held_elsewhere:
        return held
    return offered


def _widened_ref(held: MediaRef, offered: MediaRef, others: list[MediaRef]) -> MediaRef | None:
    """Return *held* widened with the ids of *offered* it lacks, or ``None`` when it learns none.

    The separation of ids: a slot the follow fills is never overwritten, and an id that
    another row of the same medium and kind (*others*, a duplicate) already holds is not
    copied: a duplicate already shares an id with the follow, so copying its other ids can
    make the two rows the same whole JSON, which ``ux_followed_media_ref`` refuses. Every
    id learned is held by no duplicate; a row of the other kind is checked by the caller
    before the write.

    Args:
        held: The ids of the row merged into.
        offered: The ids of the follow being added.
        others: The ids of the other rows of its kind holding one of *offered*'s ids.

    Returns:
        The widened ref, or ``None`` when *held* already says all it can learn.
    """
    widened = MediaRef(
        tvdb_id=_learned(held.tvdb_id, offered.tvdb_id, {other.tvdb_id for other in others}),
        tmdb_id=_learned(held.tmdb_id, offered.tmdb_id, {other.tmdb_id for other in others}),
        imdb_id=_learned(held.imdb_id, offered.imdb_id, {other.imdb_id for other in others}),
    )
    return None if widened == held else widened


def _log_duplicate_id(media_ref: MediaRef, rowids: list[int | None]) -> None:
    """Report that two or more follow rows hold one of *media_ref*'s ids.

    The rows are a medium written twice: before ``add`` merged learned ids, or as a film
    and a show sharing an IMDb id, which ``add`` keeps apart (``acquire.follow.kind_conflict``).
    A lookup given neither a kind nor a TVDB id matches a TMDB id in both kinds, so it may
    also gather a film and a show that only share that number. They are reported, never
    folded here: they are measured first, and what becomes of them is the operator's
    decision. ``acquisition-follow-duplicates`` lists the shared ids.

    Args:
        media_ref: The ids looked up.
        rowids: The rows holding them, in the lookup's order.
    """
    log.warning(
        "acquire.follow.duplicate_id",
        tvdb_id=media_ref.tvdb_id,
        tmdb_id=media_ref.tmdb_id,
        imdb_id=media_ref.imdb_id,
        rowids=rowids,
    )


def _log_id_conflicts(target: FollowedSeries, offered: MediaRef) -> None:
    """Report each slot where the row merged into holds another id than the one offered.

    The held id is kept (never overwritten); the offered one is not written. Two media
    sharing one id, or a TVDB/TMDB mapping that changed, would otherwise vanish in silence.

    Args:
        target: The row merged into.
        offered: The ids of the follow being added.
    """
    held = target.media_ref
    for provider, held_id, offered_id in (
        ("tvdb", held.tvdb_id, offered.tvdb_id),
        ("tmdb", held.tmdb_id, offered.tmdb_id),
        ("imdb", held.imdb_id, offered.imdb_id),
    ):
        if held_id is not None and offered_id is not None and held_id != offered_id:
            log.warning(
                "acquire.follow.id_conflict",
                rowid=target.id,
                provider=provider,
                held=held_id,
                offered=offered_id,
            )


def _log_kind_conflict(rowid: int | None, held_kind: str, offered_kind: FollowKind) -> None:
    """Report a row of another kind in the way of the follow being added.

    Two ways. IMDb numbers films and shows together, so the follow's IMDb id may find a
    row of the other kind: an add never merges into it, which would rewrite a film as a
    show, and goes on within its own kind. Or the row holds exactly the ids the follow's
    row would learn: the unique index admits one row per JSON, so they stay unlearned.
    One case still takes the row over: when no row of the follow's kind is found and the
    row holds the follow's very ids, the insert's ``ON CONFLICT`` backstop gives it the
    offered kind, as before this merge existed.

    Args:
        rowid: The row of the other kind.
        held_kind: Its kind.
        offered_kind: The kind of the follow being added.
    """
    log.warning(
        "acquire.follow.kind_conflict",
        rowid=rowid,
        held_kind=held_kind,
        offered_kind=offered_kind,
    )


#: Lookups one :meth:`_FollowSubStore.find_all_by_refs` statement carries: five bound values each,
#: so a chunk stays far under SQLite's variable limit whatever the build's default.
_LOOKUP_CHUNK = 100


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
        """Persist a :class:`FollowedSeries` on the row of its medium and return that rowid.

        The medium is looked up first by any of its provider ids, within its kind
        (:meth:`find_all_by_ref`). An add never merges into a row of another kind,
        which its IMDb id may find (IMDb numbers both kinds together): such a row is
        logged as ``acquire.follow.kind_conflict`` and the add goes on within its own
        kind. The first row of its kind found is the follow: the ids it lacks are
        merged into its ``media_ref_json`` (widened, never narrowed, a held id never
        overwritten, a clash logged as ``acquire.follow.id_conflict``) and it is
        reactivated and refreshed exactly as the
        ``ON CONFLICT`` path below does. Both paths also make the row a standing follow
        (``scope = 'follow'``, ``removed_at`` cleared): adding a medium a one-off request
        or a removed row holds is how it becomes a follow, on the same row. So the same show stored ``{tvdb: X}`` and
        later followed from its TMDB card as ``{tvdb: X, tmdb: Y}`` stays ONE row,
        which the whole-JSON ``ux_followed_media_ref`` index (migration 004) never
        caught. Two or more rows of its kind found are a duplicate written before this
        merge existed: the first is the follow, the duplicate is logged, and it learns
        only the ids no other row of its kind holds (copying one can make the two rows'
        JSON equal, which the unique index refuses; a row of the other kind is checked
        for that too, a ``kind_conflict`` when it holds them all); nothing is folded.

        No row of its kind found inserts, as before: ``ON CONFLICT(media_ref_json)``
        stays the backstop and ``RETURNING id`` reads the surviving rowid on both
        branches (``cur.lastrowid`` is unreliable on the DO-UPDATE path). A row of the
        other kind holding the very same JSON (a film once followed as a show) leaves
        the unique index no room for a second row: it is reactivated and takes the new
        kind, as before, its ``kind_conflict`` logged first when its IMDb id found it.

        The lookup and the write share one ``BEGIN IMMEDIATE``: a second
        concurrent add serialises behind the first, then finds its row and merges
        into it — one row, no ``IntegrityError`` leaking to the caller.

        Args:
            series: The :class:`FollowedSeries` to persist.

        Returns:
            The rowid of the row holding the follow (the found row, or the freshly
            inserted one).
        """
        with _write_tx(self._conn):
            found = self.find_all_by_ref(series.media_ref, kind=series.kind)
            for follow in found:
                if follow.kind != series.kind:
                    _log_kind_conflict(follow.id, follow.kind, series.kind)
            target = next((follow for follow in found if follow.kind == series.kind), None)
            if target is not None:
                return self._merge_into(target, found, series)
            row = self._conn.execute(
                """
                INSERT INTO followed_series
                  (media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind, year, replace_owned,
                   original_title)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(media_ref_json) DO UPDATE SET
                  active = 1,
                  -- Adding a medium makes it a standing follow, whatever the row was: a
                  -- one-off request or a removed row comes back as the follow asked for.
                  scope = 'follow',
                  removed_at = NULL,
                  title = excluded.title,
                  kind = excluded.kind,
                  -- Re-following an owned film to replace it must carry the
                  -- authorisation even when the row already exists.
                  replace_owned = MAX(followed_series.replace_owned, excluded.replace_owned),
                  -- A re-add that does not know the original title (older
                  -- client, manual form) must not erase a healed value (#435).
                  original_title = COALESCE(excluded.original_title, followed_series.original_title)
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
                    series.year,
                    1 if series.replace_owned else 0,
                    series.original_title,
                ),
            ).fetchone()
        assert row is not None  # RETURNING always yields the affected row
        return int(row[0])

    def _merge_into(self, target: FollowedSeries, found: list[FollowedSeries], series: FollowedSeries) -> int:
        """Merge *series* into *target*, the first row of its kind found (inside :meth:`add`'s transaction).

        The row keeps its kind: *target* is of the series' kind, so the merge never
        rewrites a film as a show. Only the other rows of that kind are its duplicates:
        a row of the other kind numbers its TVDB and TMDB ids apart, so it neither counts
        as one nor keeps *target* from learning an id (the exact-JSON check below still
        guards the unique index).

        Args:
            target: The row merged into, of the series' kind.
            found: Every row holding one of the series' ids, in the lookup's order,
                *target* among them.
            series: The follow being added.

        Returns:
            The rowid of the row merged into.
        """
        same_kind = [follow for follow in found if follow.kind == target.kind]
        others = [follow for follow in same_kind if follow is not target]
        assert target.id is not None  # read from the table, so it carries its rowid
        if others:
            _log_duplicate_id(series.media_ref, [follow.id for follow in same_kind])
        _log_id_conflicts(target, series.media_ref)
        widened = _widened_ref(target.media_ref, series.media_ref, [other.media_ref for other in others])
        widened_json = _media_ref_to_json(widened) if widened is not None else None
        if widened_json is not None:
            # A row of the other kind is never among `others`, yet it may hold exactly the
            # widened ids: the whole-JSON unique index would refuse the write. Only such a
            # row can: one of the target's kind holding them holds an offered id, so it was
            # found, and an id it holds is never learned.
            clash = self._conn.execute(
                "SELECT id, kind FROM followed_series WHERE media_ref_json = ? AND id != ?",
                (widened_json, target.id),
            ).fetchone()
            if clash is not None:
                if int(clash[0]) not in {follow.id for follow in found}:  # else logged by `add`
                    _log_kind_conflict(int(clash[0]), str(clash[1]), series.kind)
                widened_json = None
        self._conn.execute(
            """
            UPDATE followed_series SET
              -- NULL keeps the stored JSON byte for byte when no id was learned.
              media_ref_json = COALESCE(?, media_ref_json),
              active = 1,
              scope = 'follow',
              removed_at = NULL,
              title = ?,
              replace_owned = MAX(replace_owned, ?),
              original_title = COALESCE(?, original_title)
            WHERE id = ?
            """,
            (
                widened_json,
                series.title,
                1 if series.replace_owned else 0,
                series.original_title,
                target.id,
            ),
        )
        return target.id

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
                   quality_profile_json, cadence_json, added_at, kind, year, replace_owned,
                   original_title, scope, removed_at
            FROM followed_series WHERE id = ?
            """,
            (followed_id,),
        ).fetchone()
        return _row_to_followed(row) if row is not None else None

    def find_all_by_ref(self, media_ref: MediaRef, *, kind: FollowKind | None = None) -> list[FollowedSeries]:
        """Return every row holding one of *media_ref*'s provider ids, by the id it matches.

        Each id the ref carries is tried by ``json_extract`` on ``media_ref_json``, active
        and inactive rows alike: a lookup ``{tvdb: A, tmdb: Y}`` finds a row stored
        ``{tmdb: Y}`` though its TVDB id misses. Rows matched by the TVDB id come first,
        then the TMDB id, then the IMDb id, each oldest first: the first row is the one
        the lookup by the first id present always answered, and the fall-through only
        speaks when that lookup found nothing.

        TVDB and TMDB number films and shows apart, so their ids match only rows of the
        medium's kind. With *kind* ``None``, a ref holding a TVDB id is taken for a show
        (TVDB is the shows' provider) for its TVDB and TMDB ids alike: a film row holding
        a TVDB id is found by a lookup given ``kind="movie"``. A ref holding none matches
        a TMDB id whatever the row's kind, as the lookup always did. IMDb
        numbers both kinds together: its id matches across kinds. An id the ref does not
        carry is bound as ``NULL``, and ``= NULL`` matches nothing.

        Args:
            media_ref: The provider ids to look up.
            kind: The medium's kind, when the caller knows it.

        Returns:
            The matching rows (``id`` populated); empty when none holds any of the ids. Two
            or more rows are one medium written twice (a duplicate).
        """
        numbered_kind = kind if kind is not None else ("show" if media_ref.tvdb_id is not None else None)
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT * FROM (
                SELECT id, media_ref_json, title, active,
                       quality_profile_json, cadence_json, added_at, kind, replace_owned,
                       original_title, scope, removed_at,
                       CASE
                         WHEN json_extract(media_ref_json, '$.tvdb_id') = :tvdb
                              AND (:kind IS NULL OR kind = :kind) THEN 0
                         WHEN json_extract(media_ref_json, '$.tmdb_id') = :tmdb
                              AND (:kind IS NULL OR kind = :kind) THEN 1
                         WHEN json_extract(media_ref_json, '$.imdb_id') = :imdb THEN 2
                       END AS match_rank
                FROM followed_series
            )
            WHERE match_rank IS NOT NULL
            ORDER BY match_rank, id
            """,
            {
                "tvdb": media_ref.tvdb_id,
                "tmdb": media_ref.tmdb_id,
                "imdb": media_ref.imdb_id,
                "kind": numbered_kind,
            },
        ).fetchall()
        return [_row_to_followed(r) for r in rows]

    def find_all_by_refs(self, lookups: Sequence[tuple[MediaRef, FollowKind | None]]) -> list[list[FollowedSeries]]:
        """Answer many :meth:`find_all_by_ref` lookups with one query per :data:`_LOOKUP_CHUNK`.

        A page of search results is flagged ``followed`` from this: a query per result is the
        cost it replaces. Each lookup gets what the single lookup gives it, by the same rule
        (TVDB, then TMDB, then IMDb matches, each oldest first; the kind restricting the TVDB
        and TMDB ids), in its own slot, so the answer lines up with the ask.

        Args:
            lookups: ``(media_ref, kind)`` pairs, as :meth:`find_all_by_ref` takes them.

        Returns:
            One list of rows per lookup, in the order asked; ``[]`` for a medium no row holds.
        """
        answers: list[list[FollowedSeries]] = []
        for start in range(0, len(lookups), _LOOKUP_CHUNK):
            answers.extend(self._find_chunk(lookups[start : start + _LOOKUP_CHUNK]))
        return answers

    def _find_chunk(self, lookups: Sequence[tuple[MediaRef, FollowKind | None]]) -> list[list[FollowedSeries]]:
        """Answer one chunk of lookups with a single statement.

        Args:
            lookups: At most :data:`_LOOKUP_CHUNK` ``(media_ref, kind)`` pairs.

        Returns:
            One list of rows per lookup, in the order asked.
        """
        answers: list[list[FollowedSeries]] = [[] for _ in lookups]
        if not lookups:
            return answers
        values: list[object] = []
        for number, (media_ref, kind) in enumerate(lookups):
            numbered_kind = kind if kind is not None else ("show" if media_ref.tvdb_id is not None else None)
            values.extend((number, media_ref.tvdb_id, media_ref.tmdb_id, media_ref.imdb_id, numbered_kind))
        placeholders = ", ".join("(?, ?, ?, ?, ?)" for _ in lookups)
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            f"""
            WITH asked(n, tvdb, tmdb, imdb, kind) AS (VALUES {placeholders})
            SELECT * FROM (
                SELECT asked.n AS n, f.id, f.media_ref_json, f.title, f.active,
                       f.quality_profile_json, f.cadence_json, f.added_at, f.kind, f.replace_owned,
                       f.original_title, f.scope, f.removed_at,
                       CASE
                         WHEN json_extract(f.media_ref_json, '$.tvdb_id') = asked.tvdb
                              AND (asked.kind IS NULL OR f.kind = asked.kind) THEN 0
                         WHEN json_extract(f.media_ref_json, '$.tmdb_id') = asked.tmdb
                              AND (asked.kind IS NULL OR f.kind = asked.kind) THEN 1
                         WHEN json_extract(f.media_ref_json, '$.imdb_id') = asked.imdb THEN 2
                       END AS match_rank
                FROM asked CROSS JOIN followed_series AS f
            )
            WHERE match_rank IS NOT NULL
            ORDER BY n, match_rank, id
            """,  # noqa: S608 — only the placeholder groups are interpolated; every value is bound
            values,
        ).fetchall()
        for row in rows:
            answers[row["n"]].append(_row_to_followed(row))
        return answers

    def find_by_ref(self, media_ref: MediaRef, *, kind: FollowKind | None = None) -> FollowedSeries | None:
        """Return the follow of *media_ref*'s medium, or ``None``.

        The first row :meth:`find_all_by_ref` finds: the oldest row matched by the
        highest-priority id. Two or more rows are a duplicate, logged as
        ``acquire.follow.duplicate_id`` (the ids and the rowids). Used by the follow
        CLI and v0's create route to enforce the idempotent-add / reactivate logic.

        Args:
            media_ref: Provider-ID key to look up.
            kind: The medium's kind, when the caller knows it (see
                :meth:`find_all_by_ref`).

        Returns:
            The :class:`FollowedSeries` (with ``id`` populated) if found, else
            ``None``.
        """
        found = self.find_all_by_ref(media_ref, kind=kind)
        if not found:
            return None
        if len(found) > 1:
            _log_duplicate_id(media_ref, [follow.id for follow in found])
        return found[0]

    def list_active(self) -> list[FollowedSeries]:
        """Return the active FOLLOWS, ordered by id.

        A follow is a ``scope = 'follow'`` row that is neither inactive nor removed. A
        one-off request row (``scope = 'request'``, DESIGN O-2 A) is not a follow: detect,
        the airing poll and ``follow list`` all read this and never see one. The projection
        writes ``active = 0`` for a removed row, and ``removed_at IS NULL`` holds the same
        line for a writer that forgot it. Requests are read by :meth:`list_requests`.

        Returns:
            A list of :class:`FollowedSeries` where ``active=True``, of scope ``follow``
            and not removed, possibly empty.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind, replace_owned,
                   original_title, scope, removed_at
            FROM followed_series
            WHERE active = 1 AND scope = 'follow' AND removed_at IS NULL
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_followed(r) for r in rows]

    def list_requests(self) -> list[FollowedSeries]:
        """Return the standing one-off request rows, ordered by id.

        A request is a ``scope = 'request'`` row that is active and not removed. Detect
        reads it to keep its aired cache and series status fresh, and enqueues nothing for
        it: the request's season wanted row is its whole work.

        Returns:
            A list of :class:`FollowedSeries` of scope ``request``, possibly empty.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind, replace_owned,
                   original_title, scope, removed_at
            FROM followed_series
            WHERE active = 1 AND scope = 'request' AND removed_at IS NULL
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_followed(r) for r in rows]

    def list_all(self) -> list[FollowedSeries]:
        """Return every ``followed_series`` row (any scope, active, inactive or removed), ordered by id.

        Used by ``follow list --all`` and by the title maps, which want a title by id
        whatever the row is.

        Returns:
            A list of all :class:`FollowedSeries`, possibly empty.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at, kind, replace_owned,
                   original_title, scope, removed_at
            FROM followed_series
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_followed(r) for r in rows]

    def mark_removed(self, followed_id: int, *, now: int) -> bool:
        """Mark a row removed and inactive: its last requester is gone or its request ended.

        Writes ``removed_at`` and ``active = 0`` together (the projection of DESIGN § 2.4
        for a removed row), in one transaction. The row, its wanted rows and its history
        stay. A row already removed keeps its first stamp.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            now: Unix epoch seconds of the removal.

        Returns:
            ``True`` when this call removed the row, ``False`` when it was already removed
            or does not exist.
        """
        with _write_tx(self._conn):
            cursor = self._conn.execute(
                "UPDATE followed_series SET removed_at = ?, active = 0 WHERE id = ? AND removed_at IS NULL",
                (now, followed_id),
            )
        return cursor.rowcount > 0

    def end_request(self, followed_id: int, *, now: int) -> bool:
        """End a one-off request whose season is closed, deciding and writing in ONE statement.

        The request is marked removed and inactive only if, at the instant of the write, it
        is a standing request (scope ``request``, not removed), none of its wanted rows is
        open (:data:`~personalscraper.acquire.domain.OPEN_WANTED_STATUSES`) and it holds at
        least one season row. The conditions live inside the ``UPDATE``, so a row opened
        or inserted by a concurrent pass between a caller's read and this write keeps the
        request standing: the check and the write cannot be separated.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            now: Unix epoch seconds of the removal.

        Returns:
            ``True`` when this call ended the request, ``False`` when a condition did not hold.
        """
        open_statuses = sorted(OPEN_WANTED_STATUSES)
        placeholders = ", ".join("?" for _ in open_statuses)
        with _write_tx(self._conn):
            cursor = self._conn.execute(
                f"""
                UPDATE followed_series SET removed_at = ?, active = 0
                WHERE id = ? AND scope = 'request' AND removed_at IS NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM wanted
                    WHERE wanted.followed_id = followed_series.id AND wanted.status IN ({placeholders})
                  )
                  AND EXISTS (
                    SELECT 1 FROM wanted
                    WHERE wanted.followed_id = followed_series.id AND wanted.kind = 'season'
                  )
                """,  # noqa: S608 — the placeholders are literal '?' marks, every value is bound
                (now, followed_id, *open_statuses),
            )
        return cursor.rowcount > 0

    def refollow(self, followed_id: int) -> None:
        """Make an existing row a standing follow again: active, scope ``follow``, not removed.

        The row keeps its id, its wanted rows and its history. Used by ``follow add`` on a
        medium whose row is inactive, a one-off request or removed.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET active = 1, scope = 'follow', removed_at = NULL WHERE id = ?",
                (followed_id,),
            )

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

    def set_replace_owned(self, followed_id: int, value: bool) -> None:
        """Write the §5 replacement authorisation on an EXISTING follow.

        Re-following a film already in the library goes through the
        reactivation branch, where the row is already there — the flag has to
        be written, not carried by an insert.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            value: ``True`` to authorise one replacement acquisition.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET replace_owned = ? WHERE id = ?",
                (1 if value else 0, followed_id),
            )

    def set_series_status(self, followed_id: int, series_status: str) -> None:
        """Record the provider's production status for a followed series.

        Written by the detect pass from the catalogue poll it already performs,
        so the card can say « Terminé » on a positive fact rather than on the
        absence of announced episodes — an absence that, on 2026-08-09, would
        have declared « House of the Dragon » finished while it aired that day.

        Only ever called with a NAMED status: the caller skips a silent provider
        rather than blanking a stored value, because ``NULL`` reads as « not
        known to have ended » and would silently demote « Terminé ».

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            series_status: The provider's raw status string (« Ended »,
                « Continuing », « Returning Series », …).
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET series_status = ? WHERE id = ?",
                (series_status, followed_id),
            )

    def clear_replace_owned(self, followed_id: int) -> None:
        """Spend the §5 replacement authorisation.

        Called once the wanted row exists: the acquisition the operator asked
        for is under way, so the flag has done its job. Leaving it set would
        make EVERY future detect re-acquire the film, which is a loop, not a
        replacement.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET replace_owned = 0 WHERE id = ?",
                (followed_id,),
            )

    def delete(self, followed_id: int) -> None:
        """REMOVE a follow and everything still queued for it.

        Distinct from :meth:`set_active` (« mettre en pause »), which the API
        used to call for BOTH verbs: « Retirer le suivi » and « Mettre en
        pause » wrote the same row, so a removal the operator asked for never
        happened (their report, 2026-08-08).

        Open ``wanted`` rows go with it: the schema's ``ON DELETE SET NULL``
        would otherwise leave them orphaned yet still queued, and the search
        pass would keep working for a follow that no longer exists. Rows that
        already reached the client (``grabbed``/``done``/…) are KEPT — their
        acquisition is real and its provenance must stay readable; they simply
        lose their back-link.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "DELETE FROM wanted WHERE followed_id = ? AND status IN ('pending', 'searching', 'available')",
                (followed_id,),
            )
            self._conn.execute(
                "DELETE FROM followed_series WHERE id = ?",
                (followed_id,),
            )

    def set_titles(self, followed_id: int, *, title: str, original_title: str) -> None:
        """Replace a follow's display title and original title together.

        The one writer that may REPLACE a non-empty title (``merge_metadata``
        only fills an empty one): the detect heal of a TVDB-only show stored
        under its original-language name moves that name to ``original_title``
        and gives the row its configured-language title, in one transaction so
        the original name is never lost between two writes.

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            title: The display title (the configured-language name).
            original_title: The original-language title.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET title = ?, original_title = ? WHERE id = ?",
                (title, original_title, followed_id),
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

    def card(self, followed_id: int) -> FollowCard | None:
        """Return the card facts of one row: its poster and its show's production status.

        Args:
            followed_id: Rowid of the ``followed_series`` row.

        Returns:
            The facts, or ``None`` when the row does not exist.
        """
        row = self._conn.execute(
            "SELECT poster_url, series_status FROM followed_series WHERE id = ?", (followed_id,)
        ).fetchone()
        return None if row is None else FollowCard(poster_url=row[0], series_status=row[1])

    def merge_metadata(
        self,
        followed_id: int,
        *,
        poster_url: str | None,
        overview: str | None,
        year: int | None,
        title: str | None = None,
        original_title: str | None = None,
    ) -> None:
        """Merge the OBJ3 card metadata columns of a followed series (additive).

        Persists the ``poster_url`` / ``overview`` / ``year`` resolved for a
        follow — from the add-by-search candidate and/or the server-side
        provider enrichment (acq-states §7). ``None`` means « not known right
        now », NEVER « clear »: each column is written through ``COALESCE(?,
        col)`` so a provider outage cannot erase a value a previous add path
        already stored. Runs inside a single ``_write_tx`` BEGIN IMMEDIATE so
        the web route never opens its own connection — single-writer discipline
        (ACQUIRE-09).

        Args:
            followed_id: Rowid of the ``followed_series`` row.
            poster_url: Poster URL, or ``None`` to leave the stored one intact.
            overview: Overview/synopsis text, or ``None`` to leave it intact.
            year: Release/first-air year, or ``None`` to leave it intact.
            title: Provider title, written ONLY over an empty one. A follow
                created before the title was resolved (the add-by-ID form)
                sits there nameless — blank in the list and in its own sheet —
                and the backfill is what repairs it. A row that already has a
                name keeps it: the operator may have chosen it.
            original_title: The provider's original-language title (#435), or
                ``None`` to leave the stored one intact (COALESCE, like the
                card fields — an add path that does not know it must never
                erase a healed value).
        """
        with _write_tx(self._conn):
            self._conn.execute(
                "UPDATE followed_series SET poster_url = COALESCE(?, poster_url), "
                "overview = COALESCE(?, overview), year = COALESCE(?, year), "
                "title = CASE WHEN trim(COALESCE(title, '')) = '' THEN COALESCE(?, title) ELSE title END, "
                "original_title = COALESCE(?, original_title) "
                "WHERE id = ?",
                (poster_url, overview, year, title, original_title, followed_id),
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
        assert row_id is not None  # INSERT always sets lastrowid
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
            SELECT id, info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at, absent_since
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
            SELECT id, info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at, absent_since
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
            SELECT id, info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at, absent_since
            FROM seed_obligation
            WHERE (dispatched_path = ? OR dispatched_path LIKE ? ESCAPE '\\')
              AND released_at IS NULL
            """,
            (path_str, like_pattern),
        ).fetchall()
        return [_row_to_seed(r) for r in rows]

    def list_open(self) -> list[SeedObligation]:
        """Return every obligation that is neither satisfied nor released.

        Returns:
            The open :class:`SeedObligation` rows, oldest id first.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at, absent_since
            FROM seed_obligation
            WHERE satisfied_at IS NULL AND released_at IS NULL
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_seed(r) for r in rows]

    def list_unreleased(self) -> list[SeedObligation]:
        """Return every obligation whose ``released_at`` is still NULL, met or not.

        The sweep reads this one: an obligation already satisfied is released
        when its torrent leaves the client, so it must stay in the sweep's view.

        Returns:
            The unreleased :class:`SeedObligation` rows, oldest id first.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at, absent_since
            FROM seed_obligation
            WHERE released_at IS NULL
            ORDER BY id
            """
        ).fetchall()
        return [_row_to_seed(r) for r in rows]

    def mark_satisfied(self, obligation_id: int, satisfied_at: int) -> int:
        """Set ``satisfied_at`` on an open ``seed_obligation`` row.

        Guarded so a satisfied or released row is never re-stamped.

        Args:
            obligation_id: Rowid of the obligation.
            satisfied_at: Unix epoch seconds.

        Returns:
            The number of rows updated (0 when the row was already closed).
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                "UPDATE seed_obligation SET satisfied_at = ? "
                "WHERE id = ? AND satisfied_at IS NULL AND released_at IS NULL",
                (satisfied_at, obligation_id),
            )
            return cur.rowcount

    def mark_absent(self, obligation_id: int, seen_at: int) -> int:
        """Record the first pass that did not find the torrent in the client.

        Args:
            obligation_id: Rowid of the obligation.
            seen_at: Unix epoch seconds of that pass.

        Returns:
            The number of rows updated (0 when already marked absent or released).
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                "UPDATE seed_obligation SET absent_since = ? "
                "WHERE id = ? AND absent_since IS NULL AND released_at IS NULL",
                (seen_at, obligation_id),
            )
            return cur.rowcount

    def clear_absent(self, obligation_id: int) -> int:
        """Forget an absence: the torrent was seen again.

        Args:
            obligation_id: Rowid of the obligation.

        Returns:
            The number of rows updated (0 when it was not marked absent).
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                "UPDATE seed_obligation SET absent_since = NULL WHERE id = ? AND absent_since IS NOT NULL",
                (obligation_id,),
            )
            return cur.rowcount

    def mark_released(self, obligation_id: int, released_at: int) -> int:
        """Set ``released_at``: the torrent is gone, nothing seeds any more.

        Args:
            obligation_id: Rowid of the obligation.
            released_at: Unix epoch seconds.

        Returns:
            The number of rows updated (0 when already released).
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                "UPDATE seed_obligation SET released_at = ? WHERE id = ? AND released_at IS NULL",
                (released_at, obligation_id),
            )
            return cur.rowcount

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
    ``BEGIN IMMEDIATE`` + ``busy_timeout``); no flock is held for the
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
        download_marks: ``download_marks`` advisory sub-store (O4/D7, lazy).
        requesters: ``acquisition_requester`` sub-store (who asked for a follow, lazy).
        candidates: ``wanted_candidate`` sub-store (a wanted row's ranked candidates, lazy).
        suggestions: ``suggestion`` sub-store (the deck of titles worth following, lazy).
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
        self._provenance: _ProvenanceSubStore | None = None
        self._download_marks: DownloadMarksStore | None = None
        self._requesters: _RequesterSubStore | None = None
        self._candidates: _CandidateSubStore | None = None
        self._suggestions: _SuggestionSubStore | None = None

    def _ensure_open(self) -> sqlite3.Connection:
        """Open the connection and migrate the schema on first access.

        Takes the core ``db_lock`` (flock) with a generous timeout ONLY
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

    @property
    def provenance(self) -> _ProvenanceSubStore:
        """``staging_provenance`` advisory registry sub-store (ensures open)."""
        if self._provenance is None:
            self._provenance = _ProvenanceSubStore(self._ensure_open(), _write_tx)
        return self._provenance

    @property
    def download_marks(self) -> DownloadMarksStore:
        """``download_marks`` advisory sub-store (ensures the store is open)."""
        conn = self._ensure_open()
        if self._download_marks is None:
            self._download_marks = DownloadMarksStore(conn)
        return self._download_marks

    @property
    def requesters(self) -> _RequesterSubStore:
        """``acquisition_requester`` sub-store: who asked for a follow (ensures open)."""
        if self._requesters is None:
            self._requesters = _RequesterSubStore(self._ensure_open(), _write_tx)
        return self._requesters

    @property
    def candidates(self) -> _CandidateSubStore:
        """``wanted_candidate`` sub-store: a wanted row's ranked candidates (ensures open)."""
        if self._candidates is None:
            self._candidates = _CandidateSubStore(self._ensure_open(), _write_tx)
        return self._candidates

    @property
    def suggestions(self) -> _SuggestionSubStore:
        """``suggestion`` sub-store: the deck of titles worth following (ensures open)."""
        if self._suggestions is None:
            self._suggestions = _SuggestionSubStore(self._ensure_open(), _write_tx)
        return self._suggestions

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """One unit of work: every write of the block in ONE ``BEGIN IMMEDIATE``, committed together.

        The writer lock is taken at the start, so what the block reads stays what it writes
        over: a load and a save inside it are serialised against every other writer, in any
        process (WAL + ``busy_timeout``). Each sub-store write joins it as a savepoint; an
        exception leaving the block rolls everything back.

        Yields:
            ``None`` while the transaction is open.

        Raises:
            Exception: Whatever the block raises (after rollback).
        """
        with _write_tx(self._ensure_open()):
            yield

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
