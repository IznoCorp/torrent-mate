"""Port protocols for the acquire lobe.

RP5c established the minimal lifecycle seam (``close()``).  RP3 extends
``AcquireStore`` with the query/write surface for the five sub-stores,
exposed as attribute namespaces:

  * ``store.follow``     — ``followed_series`` writer + reader
  * ``store.wanted``     — ``wanted`` writer + reader (status transitions)
  * ``store.seed``       — ``seed_obligation`` writer + reader (deletion authority)
  * ``store.ratio``      — ``ratio_state`` reader + upsert (data-carrier)
  * ``store.cross_seed`` — ``cross_seed_history`` + ``cross_seed_quota`` (watch-seed)
  * ``store.watch``      — ``watch_state`` KV store (watcher daemon state)

All five sub-stores share a single ``acquire.db`` connection.  Cross-process
single-writer is SQLite-native (WAL + ``BEGIN IMMEDIATE`` + ``busy_timeout``):
no ``FileLock`` is held for the store's lifetime, and reads are lock-free.  The
concrete store opens lazily (on first sub-store access).  See
:mod:`personalscraper.acquire.store` for the concrete implementation.

Import direction: this module imports only from ``personalscraper.acquire``
domain VOs + stdlib — never from triage packages (layering, RP5c D3).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from personalscraper.acquire._download_marks import DownloadMark
    from personalscraper.acquire._provenance_store import ProvenanceRow

from personalscraper.acquire.domain import (
    AiredEpisodeRow,
    FollowedSeries,
    RatioState,
    SeedObligation,
    WantedItem,
    WantedKind,
    WantedStatus,
)
from personalscraper.core.identity import MediaRef


@runtime_checkable
class FollowSubStore(Protocol):
    """Writer + reader for the ``followed_series`` table."""

    def add(self, series: FollowedSeries) -> int:
        """Insert a :class:`FollowedSeries` row and return its rowid."""
        ...

    def get(self, followed_id: int) -> FollowedSeries | None:
        """Return the :class:`FollowedSeries` for *followed_id*, or ``None``."""
        ...

    def find_by_ref(self, media_ref: MediaRef) -> FollowedSeries | None:
        """Return the :class:`FollowedSeries` keyed on *media_ref*, or ``None``.

        Matches on the primary available provider ID (tvdb > tmdb > imdb),
        so a lookup matches any stored row sharing that ID regardless of
        other IDs, returning the oldest (first-by-id) on ties, or ``None``.
        """
        ...

    def list_active(self) -> list[FollowedSeries]:
        """Return all active ``followed_series`` rows, ordered by id."""
        ...

    def list_all(self) -> list[FollowedSeries]:
        """Return all ``followed_series`` rows (active and inactive), ordered by id."""
        ...

    def set_active(self, followed_id: int, active: bool) -> None:
        """Set the ``active`` flag on a ``followed_series`` row."""
        ...

    def set_kind(self, followed_id: int, kind: str) -> None:
        """Update the ``kind`` ('movie'|'show') of a ``followed_series`` row."""
        ...


@runtime_checkable
class WantedSubStore(Protocol):
    """Writer + reader for the ``wanted`` table."""

    def add(self, item: WantedItem) -> int:
        """Insert a :class:`WantedItem` row and return its rowid."""
        ...

    def get(self, wanted_id: int) -> WantedItem | None:
        """Return the :class:`WantedItem` for *wanted_id*, or ``None``."""
        ...

    def set_status(self, wanted_id: int, status: WantedStatus) -> None:
        """Transition the ``status`` column of a ``wanted`` row."""
        ...

    def list_pending(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='pending'`` (partial-index path)."""
        ...

    def list_grabbed(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='grabbed'`` (downloads read-model)."""
        ...

    def list_searching(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='searching'`` — NO age threshold.

        Reconciliation input: a row can hold a ``grabbed_hash`` while reading
        'searching' (§11(d) crash window), and that row is closable ONLY here.
        """
        ...

    def list_available(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='available'`` — the grab pass queue."""
        ...

    def record_search_outcome(self, wanted_id: int, outcome: str, found: int | None) -> None:
        """Persist the verdict of the last search on *wanted_id*.

        Called at EVERY exit path of the search pass. ``found`` is ``None``
        when the search did NOT conclude (outage / dead swarm / open circuit):
        zero would falsely claim « I looked, there is nothing ».
        """
        ...

    def claim_for_search(self, wanted_id: int, now: int) -> bool:
        """Atomically claim a pending item; return ``True`` iff this call won."""
        ...

    def claim_for_grab(self, wanted_id: int, now: int) -> bool:
        """Atomically claim an ``available`` item; return ``True`` iff this call won.

        The grab pass's counterpart to :meth:`claim_for_search`: it matches
        ``status='available'`` only, so the two passes never steal each other's
        rows.
        """
        ...

    def reclaim_stale_searching(self, wanted_id: int, older_than: int) -> bool:
        """Atomically recover a stale hash-less 'searching' row to 'pending'.

        Rowcount-gated exactly like :meth:`claim_for_search`: a row already
        re-claimed, already grabbed, or carrying a ``grabbed_hash`` (the
        §11(d) crash window) is NEVER reverted. Returns ``True`` iff this call
        recovered it.
        """
        ...

    def record_grab_intent(self, wanted_id: int, info_hash: str) -> bool:
        """Reserve the chosen hash on a 'searching' row BEFORE ``add()`` (D2).

        Guarded on ``status='searching' AND grabbed_hash IS NULL``; returns
        ``True`` iff this call reserved the row.
        """
        ...

    def confirm_grab_intent(self, wanted_id: int, info_hash: str) -> bool:
        """Promote an intent row to 'grabbed' once its torrent is confirmed (D2).

        Guarded on ``status='searching' AND grabbed_hash IS NOT NULL`` — the
        reconciliation's replay of a decision already taken, idempotent.
        """
        ...

    def clear_grab_intent(self, wanted_id: int) -> bool:
        """Release a reserved hash whose ``add()`` failed (D2).

        Guarded on ``status='searching' AND grabbed_hash IS NOT NULL`` so it can
        never disarm a confirmed grab; returns ``True`` iff it released one.
        """
        ...

    def hashes_in_flight(self) -> set[str]:
        """Return the lowercase hashes of every OPEN row carrying one (probe set)."""
        ...

    def mark_grabbed(self, wanted_id: int, info_hash: str) -> None:
        """Persist ``status='grabbed'`` + ``info_hash`` — the confirmation half of the two-phase claim (D2)."""
        ...

    def mark_done_by_hash(self, info_hash: str) -> list[WantedItem]:
        """Close every OPEN row carrying *info_hash* (§5 dispatch closure).

        The open-status filter derives from ``OPEN_WANTED_STATUSES``, so a row
        left 'searching' or 'available' while holding the hash of a torrent the
        pipeline already dispatched still closes.
        """
        ...

    def mark_done(self, wanted_id: int) -> bool:
        """Close ONE ``grabbed`` row confirmed in the library (reconciliation)."""
        ...

    def requeue_missing(self, wanted_id: int) -> bool:
        """Requeue an OPEN hash-carrying row whose torrent vanished (and is unowned).

        Guarded on ``grabbed_hash IS NOT NULL`` + the OPEN statuses, so the
        §11(d) crash window ('searching' + hash) is requeueable too.
        """
        ...

    def list_tried_hashes(self, wanted_id: int) -> tuple[str, ...]:
        """Return the info-hashes already grabbed-and-failed for this item (reswitch #342)."""
        ...

    def append_tried_hash(self, wanted_id: int, info_hash: str) -> None:
        """Remember *info_hash* as a release already grabbed-and-failed (idempotent, lowercase)."""
        ...

    def requeue_for_reswitch(self, wanted_id: int, failed_hash: str, now: int) -> bool:
        """Atomically append *failed_hash* to tried_hashes AND requeue the row, clock reset (reswitch #342)."""
        ...

    def resurrect(self, wanted_id: int, now: int) -> bool:
        """Re-open an ``abandoned`` row for a still-missing aired episode (B.4)."""
        ...

    def list_stale_searching(self, older_than: int) -> list[WantedItem]:
        """Return ``wanted`` rows stuck in 'searching' older than the threshold."""
        ...

    def list_for_followed(self, followed_id: int, *, kind: WantedKind) -> list[WantedItem]:
        """Return EVERY ``wanted`` row of one follow (any status), ordered by id.

        Closed rows are included on purpose: the « which row governs » rule
        belongs to the shared selector, not to each caller's WHERE clause.
        """
        ...

    def find(
        self,
        *,
        followed_id: int | None,
        kind: WantedKind,
        season: int | None,
        episode: int | None,
        statuses: tuple[str, ...] | None = None,
    ) -> WantedItem | None:
        """Return the first matching wanted row, or None (soft dedup guard).

        Uses NULL-safe comparison (``IS`` not ``=``) for ``season`` and
        ``episode`` so that a NULL episode in a future movie case does not
        accidentally match an episode row.

        Without ``statuses`` the lookup is status-agnostic and returns the
        OLDEST matching row; with ``statuses`` only rows in those statuses
        match — the way to find the LIVE row when an older terminal one
        shares the same coordinates.

        Args:
            followed_id: FK to ``followed_series`` row, or ``None``.
            kind: ``"movie"``, ``"episode"`` or ``"season"``.
            season: Season number, or ``None`` for movies.
            episode: Episode number, or ``None`` for movies.
            statuses: When given, restrict the match to these statuses.

        Returns:
            The first matching :class:`WantedItem` if found, else ``None``.
        """
        ...

    def absorb_episodes(self, season_wanted_id: int, episode_ids: tuple[int, ...]) -> int:
        """Transition episode wanteds to ``absorbed``, linking them to the season row.

        Called when a season wanted absorbs its live episode siblings (R5).

        Args:
            season_wanted_id: Rowid of the absorbing season ``wanted`` row.
            episode_ids: Rowids of the episode rows to absorb.

        Returns:
            Number of rows actually transitioned.
        """
        ...

    def fallback_season(self, season_wanted_id: int) -> bool:
        """Transition a season row to ``fallback_episodes`` — the cutoff path (R6).

        Guarded on ``kind='season'`` and OPEN_WANTED_STATUSES.

        Args:
            season_wanted_id: Rowid of the season ``wanted`` row.

        Returns:
            ``True`` iff the row transitioned.
        """
        ...


@runtime_checkable
class SeedSubStore(Protocol):
    """Writer + reader for the ``seed_obligation`` table (deletion authority)."""

    def add(self, obligation: SeedObligation) -> int:
        """Insert a new :class:`SeedObligation`; returns the row id."""
        ...

    def find_by_dispatched_path(self, path: Path) -> SeedObligation | None:
        """Return the active obligation for *dispatched_path*, or ``None``."""
        ...

    def find_active_by_hash(self, info_hash: str) -> SeedObligation | None:
        """Return the first active obligation carrying *info_hash*, or ``None``."""
        ...

    def set_dispatched_path(self, info_hash: str, path: str) -> int:
        """Backfill ``dispatched_path`` on the active obligations for *info_hash*."""
        ...

    def find_active_under(self, path: Path) -> list[SeedObligation]:
        """Return all active obligations for *path* or any of its descendants.

        Matches obligations whose ``dispatched_path`` is either exactly *path*
        OR a descendant of *path* (boundary-safe LIKE with ESCAPE).
        Only returns obligations where ``released_at IS NULL``.
        """
        ...

    def mark_satisfied(self, obligation_id: int, satisfied_at: int) -> None:
        """Set ``satisfied_at`` on an obligation row."""
        ...

    def mark_breached(self, obligation_id: int, breached_at: int) -> None:
        """Set ``breached_at`` on an obligation row."""
        ...

    def mark_breached_under(self, path: Path, breached_at: int) -> int:
        """Breach every active obligation under *path*; return the row count.

        Matches obligations whose ``dispatched_path`` is exactly *path* OR a
        descendant (boundary-safe LIKE with ESCAPE). Only touches rows with
        ``released_at IS NULL`` that are not already breached.
        """
        ...


@runtime_checkable
class RatioSubStore(Protocol):
    """Reader + upsert for the ``ratio_state`` table (data-carrier; Ratio C1)."""

    def get(self, tracker_name: str) -> RatioState | None:
        """Return the :class:`RatioState` for *tracker_name*, or ``None``."""
        ...

    def upsert(self, state: RatioState) -> None:
        """Insert or replace the ``ratio_state`` row keyed on ``tracker_name``."""
        ...


@runtime_checkable
class WatchSubStore(Protocol):
    """Writer + reader for the ``watch_state`` key-value table."""

    def get_last_successful_run_at(self) -> float | None:
        """Return the persisted ``last_successful_run_at`` timestamp, or ``None``."""
        ...

    def set_last_successful_run_at(self, ts: float) -> None:
        """Persist the ``last_successful_run_at`` timestamp (upsert)."""
        ...


@runtime_checkable
class CrossSeedSubStore(Protocol):
    """Writer + reader for the ``cross_seed_history`` and ``cross_seed_quota`` tables."""

    def record_search(self, source_hash: str, tracker: str) -> None:
        """Record a cross-seed search attempt (upsert by source_hash+tracker)."""
        ...

    def was_searched_recently(self, source_hash: str, tracker: str, days: int) -> bool:
        """Return ``True`` if the pair was searched within *days*."""
        ...

    def daily_searches_remaining(self, max_per_day: int) -> int:
        """Return remaining quota for today (max_per_day - today's count)."""
        ...

    def increment_daily_count(self) -> None:
        """Increment today's search count (UPSERT)."""
        ...


@runtime_checkable
class AcquireStore(Protocol):
    """Full store contract for the acquisition lobe (RP3).

    Sub-stores are accessed via attribute namespaces.  Writes are serialized
    cross-process by SQLite itself (WAL + ``BEGIN IMMEDIATE`` + ``busy_timeout``);
    reads are lock-free.  The concrete store opens lazily on first access.

    The five sub-store namespaces are **read-only accessors** (the concrete
    store exposes them as ensure-open properties): callers read ``store.follow``
    but never assign it.
    """

    @property
    def follow(self) -> FollowSubStore:
        """``followed_series`` sub-store (opens the store on first access)."""
        ...

    @property
    def wanted(self) -> WantedSubStore:
        """``wanted`` sub-store (opens the store on first access)."""
        ...

    @property
    def seed(self) -> SeedSubStore:
        """``seed_obligation`` sub-store / deletion authority (opens on access)."""
        ...

    @property
    def ratio(self) -> RatioSubStore:
        """``ratio_state`` sub-store / data-carrier (opens on access)."""
        ...

    @property
    def cross_seed(self) -> CrossSeedSubStore:
        """``cross_seed_history`` + ``cross_seed_quota`` sub-store (opens on access)."""
        ...

    @property
    def watch(self) -> WatchSubStore:
        """``watch_state`` KV sub-store (opens on access)."""
        ...

    @property
    def aired(self) -> AiredSubStore:
        """``aired_episode`` catalog-cache sub-store (opens on access)."""
        ...

    @property
    def provenance(self) -> ProvenanceSubStore:
        """``staging_provenance`` advisory registry sub-store (opens on access)."""
        ...

    @property
    def download_marks(self) -> DownloadMarksSubStore:
        """``download_marks`` advisory sub-store (opens on access)."""
        ...

    def close(self) -> None:
        """Release all resources held by the store (fail-soft — never raises)."""
        ...


@runtime_checkable
class ProvenanceSubStore(Protocol):
    """Advisory writer + reader for the ``staging_provenance`` registry (F0).

    All writes are best-effort (never raise); reads are fail-soft (``None`` on
    error). ``upsert_grab`` is the ONLY row-creator (follow-driven grabs); the
    setters are UPDATE-only no-ops when untracked (a manual/direct grab).
    """

    def upsert_grab(
        self,
        info_hash: str,
        *,
        followed_id: int | None,
        media_ref: MediaRef | None,
        kind: str | None,
        grabbed_at: int,
        run_uid: str | None = None,
    ) -> None:
        """Create/refresh the row for a follow-driven grab (the identity seed)."""
        ...

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int, run_uid: str | None = None) -> None:
        """Record the staging folder at ingest (no-op if untracked)."""
        ...

    def set_current_path(self, info_hash: str, *, path: str) -> None:
        """Keep the live folder path in sync across a sort/rename (no-op if untracked)."""
        ...

    def set_scraped(self, info_hash: str, *, scraped_ref: MediaRef | None, scraped_at: int) -> None:
        """Record the identity actually scraped (no-op if untracked)."""
        ...

    def set_dispatch(self, info_hash: str, *, dispatch_path: str, dispatched_at: int) -> None:
        """Record the final destination at dispatch (no-op if untracked)."""
        ...

    def move_path(self, old_path: str, new_path: str) -> None:
        """Re-point a tracked folder old_path → new_path (path-keyed sort/rename)."""
        ...

    def set_scrape_run(self, staging_path: str, *, run_uid: str | None, scraped_at: int) -> None:
        """Record the scrape stage (status='scraped' + scraped_at) + the run (path-keyed, F3)."""
        ...

    def record_dispatch_by_path(
        self, staging_path: str, *, dispatch_path: str, dispatched_at: int, run_uid: str | None = None
    ) -> None:
        """Record the dispatch of the folder currently at *staging_path* (path-keyed)."""
        ...

    def set_resolution(
        self,
        staging_path: str,
        *,
        state: str,
        resolved_at: int,
        decision_id: int | None = None,
        trigger: str | None = None,
    ) -> None:
        """Project a decision verdict onto *staging_path* (path-keyed, advisory, F2)."""
        ...

    def by_hash(self, info_hash: str) -> ProvenanceRow | None:
        """Return the row for *info_hash*, or ``None`` (fail-soft)."""
        ...

    def by_path(self, path: str) -> ProvenanceRow | None:
        """Return the row whose ``current_path`` equals *path*, or ``None``."""
        ...

    def path_ref_index(self) -> dict[str, MediaRef]:
        """Snapshot ``{current_path: media_ref}`` for tracked, identified rows (#30)."""
        ...

    def list_journeys(self, limit: int = 200) -> "list[ProvenanceRow]":
        """Return provenance rows most-recent first (F1 journey view; fail-soft)."""
        ...

    def list_journeys_for_run(self, run_uid: str, limit: int = 500) -> "list[ProvenanceRow]":
        """Return acquisitions a run advanced at any stage (F3 converse view; fail-soft)."""
        ...

    def list_stuck(self, older_than: int, exists_fn: Callable[[str], bool], limit: int = 500) -> "list[ProvenanceRow]":
        """Return in-flight items stuck past *older_than* whose folder still exists (F4; fail-soft)."""
        ...

    def stage_counts(self) -> "dict[str, int]":
        """Return ``{status: count}`` over the registry (F5 overview, uncapped; fail-soft)."""
        ...

    def prune_stale(self, exists_fn: Callable[[str], bool]) -> int:
        """Delete rows whose ``current_path`` no longer exists (FS = truth)."""
        ...


@runtime_checkable
class AiredSubStore(Protocol):
    """Writer + reader for the ``aired_episode`` catalog cache (P0-B.1)."""

    def replace_for_followed(
        self,
        followed_id: int,
        episodes: Sequence[tuple[int, int, str | None, str]],
        *,
        now: int,
    ) -> int:
        """Replace one series' cached catalog with ``(season, episode, title, air_date)`` rows."""
        ...

    def list_for_followed(self, followed_id: int) -> list[AiredEpisodeRow]:
        """Return the cached aired catalog of one followed series (may be empty)."""
        ...


@runtime_checkable
class DownloadMarksSubStore(Protocol):
    """Reader + writer for the ``download_marks`` advisory table (O4/D7).

    One row per grabbed torrent info-hash, recording which download-progress
    transitions the reconcile sweep has already emitted (started / 25-50-75
    thresholds / completed) for exactly-once event semantics. Marks are
    persisted BEFORE the emit (emit-after-persist) and pruned when the hash no
    longer belongs to any OPEN wanted row.
    """

    def get(self, info_hash: str) -> DownloadMark | None:
        """Return the mark for *info_hash* (stored lowercase), or ``None``."""
        ...

    def upsert(
        self,
        info_hash: str,
        *,
        started: bool | None = None,
        threshold: int | None = None,
        completed: bool | None = None,
    ) -> None:
        """Insert or partially update a mark (only non-None keywords written)."""
        ...

    def prune_stale(self, active_hashes: Iterable[str]) -> int:
        """Delete marks whose hash is not in *active_hashes*; return the count."""
        ...


__all__ = [
    "AcquireStore",
    "AiredSubStore",
    "CrossSeedSubStore",
    "DownloadMarksSubStore",
    "FollowSubStore",
    "RatioSubStore",
    "SeedSubStore",
    "WantedSubStore",
    "WatchSubStore",
]
