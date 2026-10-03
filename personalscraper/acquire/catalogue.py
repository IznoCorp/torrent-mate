"""The library-wide aired catalogue: its store and its refresh (migration 026).

A provider-id-keyed record of the episodes a show has announced, with their air
dates, kept in ``acquire.db``. It answers « x of y aired episodes » for every
show of the library, not only the followed ones (``aired_episode`` is per follow).

``personalscraper library-catalogue-refresh`` is the only writer: it reads the
shows of the index, asks the providers for what is due under the politeness rule
(a continuing show once a week, an ended show once, a show whose attempt failed
no sooner than a week later) and replaces a show's rows in one transaction. A show never fetched reads ``None`` from
:meth:`CatalogueStore.episodes` — « unknown », never « complete ».

Season 0 (specials) is stored and never counted as aired — the rule the follows
already apply when they poll (``acquire.airing``: ``season_number >= 1``).

Logging: ``personalscraper.logger.get_logger`` (NEVER ``structlog.get_logger``).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from personalscraper.acquire.errors import AcquireLockError, AcquireMigrationError
from personalscraper.acquire.store import _MIGRATION_LOCK_TIMEOUT_S, _OPEN_DB_ERROR_FACTORIES
from personalscraper.api.metadata._base import EpisodeInfo, MediaDetails
from personalscraper.core.sqlite import apply_migrations, db_lock, open_db
from personalscraper.logger import get_logger

log = get_logger("acquire.catalogue")

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# A show is « ended » when the provider says so; anything else, and above all
# no status at all, is a show that may still announce episodes.
_ENDED_STATUSES = ("ended", "canceled", "cancelled")

_CONTINUING_AFTER_S = 7 * 86400.0
_PROVIDERS = ("tvdb", "tmdb")


@dataclass(frozen=True)
class CatalogueEpisode:
    """One announced episode of a catalogued show.

    Attributes:
        season: Season number (0 = specials).
        episode: Episode number within the season.
        air_date: The announced air date, or ``None`` when the provider gives none.
        title: The episode title, or ``None``.
    """

    season: int
    episode: int
    air_date: date | None
    title: str | None


class CatalogueStore:
    """Reader and writer of the ``catalogue_show`` / ``catalogue_episode`` tables.

    The database is opened (and migrated under a brief lock) on first use.
    """

    def __init__(self, db_path: Path) -> None:
        """Remember the database; nothing is opened yet.

        Args:
            db_path: Path of ``acquire.db``.
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _ensure_open(self) -> sqlite3.Connection:
        """Open and migrate the database once, then reuse the connection.

        Returns:
            The open connection.

        Raises:
            AcquireLockError: If the brief migration lock cannot be acquired.
            AcquireCorruptError: If ``acquire.db`` is malformed.
            AcquireMigrationError: If a pending migration fails to apply.
        """
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with db_lock(self._db_path, timeout=_MIGRATION_LOCK_TIMEOUT_S, error_factory=AcquireLockError):
                conn = open_db(self._db_path, errors=_OPEN_DB_ERROR_FACTORIES)
                apply_migrations(conn, _MIGRATIONS_DIR, error_factory=AcquireMigrationError)
            self._conn = conn
        return self._conn

    def close(self) -> None:
        """Close the connection if one is open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def replace_show(
        self,
        provider: str,
        provider_id: str,
        status: str | None,
        episodes: Sequence[CatalogueEpisode],
        fetched_at: float,
    ) -> None:
        """Replace a show's status and episodes in ONE transaction.

        Args:
            provider: ``"tvdb"`` or ``"tmdb"``.
            provider_id: The show's id at that provider.
            status: The provider's raw production status, or ``None``.
            episodes: Every announced episode; the previous rows are dropped.
            fetched_at: Unix time of this refresh.

        Raises:
            sqlite3.IntegrityError: Two episodes share a (season, episode); the
                previous rows are left untouched.
        """
        conn = self._ensure_open()
        key = (provider, provider_id)
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("DELETE FROM catalogue_episode WHERE provider = ? AND provider_id = ?", key)
            conn.execute(
                "INSERT OR REPLACE INTO catalogue_show "
                "(provider, provider_id, status, fetched_at, last_attempt_at, failures) VALUES (?, ?, ?, ?, ?, 0)",
                (*key, status, fetched_at, fetched_at),
            )
            conn.executemany(
                "INSERT INTO catalogue_episode (provider, provider_id, season, episode, air_date, title) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (*key, e.season, e.episode, e.air_date.isoformat() if e.air_date else None, e.title)
                    for e in episodes
                ],
            )
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")

    def record_failure(self, provider: str, provider_id: str, attempted_at: float) -> None:
        """Record a failed attempt on a show, keeping any rows it already has.

        A show that has only ever failed gets a row with no ``fetched_at``: it
        still reads ``None`` from :meth:`episodes`.

        Args:
            provider: ``"tvdb"`` or ``"tmdb"``.
            provider_id: The show's id at that provider.
            attempted_at: Unix time of the failed attempt.
        """
        conn = self._ensure_open()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO catalogue_show (provider, provider_id, status, fetched_at, last_attempt_at, failures) "
                "VALUES (?, ?, NULL, NULL, ?, 1) "
                "ON CONFLICT (provider, provider_id) DO UPDATE SET "
                "last_attempt_at = excluded.last_attempt_at, failures = failures + 1",
                (provider, provider_id, attempted_at),
            )
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")

    def episodes(self, provider: str, provider_id: str) -> list[CatalogueEpisode] | None:
        """Read a show's catalogue.

        Args:
            provider: ``"tvdb"`` or ``"tmdb"``.
            provider_id: The show's id at that provider.

        Returns:
            The episodes ordered by season then episode, ``[]`` for a fetched show
            with none, and ``None`` when the show was never fetched.
        """
        conn = self._ensure_open()
        key = (provider, provider_id)
        fetched = conn.execute(
            "SELECT fetched_at FROM catalogue_show WHERE provider = ? AND provider_id = ?", key
        ).fetchone()
        if fetched is None or fetched[0] is None:
            return None
        rows = conn.execute(
            "SELECT season, episode, air_date, title FROM catalogue_episode "
            "WHERE provider = ? AND provider_id = ? ORDER BY season, episode",
            key,
        ).fetchall()
        return [CatalogueEpisode(int(r[0]), int(r[1]), _to_date(r[2]), r[3]) for r in rows]

    def due(
        self,
        now: float,
        *,
        continuing_after_s: float = _CONTINUING_AFTER_S,
        known: Iterable[tuple[str, str]] = (),
    ) -> list[tuple[str, str]]:
        """List the shows the politeness rule allows to refresh.

        A show is due when it was never fetched, or when it may still announce
        episodes (not ended, or ended with no episode stored: an empty answer is
        doubt, not closure) and was fetched more than ``continuing_after_s`` ago. A
        show whose last attempt failed waits ``continuing_after_s`` from that
        attempt, whatever it was.

        Args:
            now: Current unix time.
            continuing_after_s: Age after which a show is refreshed or retried.
            known: The ``(provider, provider_id)`` shows the library holds; those
                the store has never seen are due first.

        Returns:
            Never-fetched known shows (in the order given), then stored shows
            past their period, stalest first, then the shows that failed, whose
            period has elapsed, last. An ended show with episodes is never due.
        """
        conn = self._ensure_open()
        rows = conn.execute(
            "SELECT s.provider, s.provider_id, s.status, s.fetched_at, s.last_attempt_at, s.failures, "
            "(SELECT COUNT(*) FROM catalogue_episode e "
            " WHERE e.provider = s.provider AND e.provider_id = s.provider_id) "
            "FROM catalogue_show s"
        ).fetchall()
        stored = {(r[0], r[1]) for r in rows}
        never = [k for k in dict.fromkeys(known) if k not in stored]
        stale: list[tuple[float, tuple[str, str]]] = []
        failing: list[tuple[float, tuple[str, str]]] = []
        for provider, provider_id, status, fetched_at, last_attempt_at, failures, n_episodes in rows:
            key = (provider, provider_id)
            if failures:
                if now - last_attempt_at > continuing_after_s:
                    failing.append((last_attempt_at, key))
            elif (not _is_ended(status) or n_episodes == 0) and now - fetched_at > continuing_after_s:
                stale.append((fetched_at, key))
        return never + [key for _, key in sorted(stale)] + [key for _, key in sorted(failing)]


def _is_ended(status: str | None) -> bool:
    """Whether a provider status says the show will announce nothing more."""
    return status is not None and status.strip().lower() in _ENDED_STATUSES


def _to_date(raw: str | None) -> date | None:
    """Parse a stored or provider ISO date; ``None`` for empty or malformed."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def aired_by_season(episodes: Sequence[CatalogueEpisode], today: date) -> dict[int, int]:
    """Count the aired episodes of each season.

    Args:
        episodes: A show's catalogue.
        today: The reference date; an episode airing today counts as aired.

    Returns:
        ``{season: aired count}`` for every catalogued season from 1, a season
        with nothing aired yet reading 0. Specials (season 0) are excluded and an
        undated episode never counts.
    """
    counts: dict[int, int] = {}
    for ep in episodes:
        if ep.season < 1:
            continue
        counts.setdefault(ep.season, 0)
        if ep.air_date is not None and ep.air_date <= today:
            counts[ep.season] += 1
    return counts


class TvCatalogueClient(Protocol):
    """The two calls a provider client must answer to be catalogued."""

    def get_tv(self, provider_id: int | str) -> MediaDetails:
        """Return a show's details, its status and season list included."""
        ...

    def get_episodes(self, series_id: str | int, season: int) -> list[EpisodeInfo]:
        """Return the episodes of one season."""
        ...


@dataclass(frozen=True)
class ProviderClients:
    """The provider clients a refresh may ask; ``None`` = provider unavailable."""

    tvdb: TvCatalogueClient | None
    tmdb: TvCatalogueClient | None

    def get(self, provider: str) -> TvCatalogueClient | None:
        """Return the client of ``provider`` (``"tvdb"`` / ``"tmdb"``), or ``None``."""
        return self.tvdb if provider == "tvdb" else self.tmdb if provider == "tmdb" else None


@dataclass(frozen=True)
class CatalogueRefreshReport:
    """What one refresh run did.

    Attributes:
        refreshed: Shows whose rows were replaced.
        failed: Shows whose provider call failed (their previous rows are kept and
            the attempt is recorded: they are not due again for a week).
        skipped: Due shows whose provider had no client; they make no provider call
            and take no ``max_shows`` slot.
        remaining: Due shows not attempted in this run because ``max_shows`` was
            reached; a show that failed here is in ``failed``, not in ``remaining``.
    """

    refreshed: int = 0
    failed: int = 0
    skipped: int = 0
    remaining: int = 0


def library_shows(index_conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """List the ``(provider, provider_id)`` key of every show of the index.

    The key is the show's canonical provider id; a show with no canonical
    provider falls back to TVDB, then TMDB (TVDB-first for TV).

    Args:
        index_conn: An open connection to ``library.db``.

    Returns:
        The distinct keys, in index order. Shows with no usable id are left out.
    """
    keys: list[tuple[str, str]] = []
    rows = index_conn.execute(
        "SELECT canonical_provider, external_ids_json FROM media_item WHERE kind = 'show' ORDER BY id"
    )
    for canonical, raw in rows:
        try:
            ids = json.loads(raw or "{}")
        except json.JSONDecodeError:
            continue
        for provider in ([canonical] if canonical in _PROVIDERS else []) + list(_PROVIDERS):
            series_id = (ids.get(provider) or {}).get("series_id")
            if series_id:
                keys.append((provider, str(series_id)))
                break
    return list(dict.fromkeys(keys))


def refresh_catalogue(
    store: CatalogueStore,
    index_conn: sqlite3.Connection,
    provider_clients: ProviderClients,
    *,
    now: float,
    max_shows: int,
) -> CatalogueRefreshReport:
    """Refresh the catalogue of the shows that are due, at most ``max_shows``.

    A provider failure on one show keeps its previous rows, is recorded so the
    show waits its period instead of holding a slot on every run, and the run
    goes on.

    Args:
        store: The catalogue store.
        index_conn: An open connection to ``library.db`` (read only).
        provider_clients: The provider clients.
        now: Current unix time (stamped as ``fetched_at``).
        max_shows: Upper bound of shows attempted in this run (each costs one
            ``get_tv`` and one ``get_episodes`` per season).

    Returns:
        The run's report.
    """
    due = store.due(now, known=library_shows(index_conn))
    refreshed = failed = skipped = remaining = 0
    for provider, provider_id in due:
        client = provider_clients.get(provider)
        if client is None:
            # No provider call, so no ``--max`` slot: an unconfigured provider must not starve the others.
            skipped += 1
            continue
        if refreshed + failed >= max_shows:
            remaining += 1
            continue
        try:
            status, episodes = _fetch_show(client, provider_id)
            store.replace_show(provider, provider_id, status, episodes, now)
        except Exception as exc:  # noqa: BLE001 — fail-soft: one bad show must not stop the run
            failed += 1
            store.record_failure(provider, provider_id, now)
            log.warning("acquire.catalogue.refresh_failed", provider=provider, provider_id=provider_id, error=str(exc))
            continue
        refreshed += 1
    return CatalogueRefreshReport(refreshed=refreshed, failed=failed, skipped=skipped, remaining=remaining)


def _fetch_show(client: TvCatalogueClient, provider_id: str) -> tuple[str | None, list[CatalogueEpisode]]:
    """Read a show's status and every episode, specials included.

    Args:
        client: The provider client.
        provider_id: The show's id at that provider.

    Returns:
        ``(status, episodes)``. Any provider error propagates: a show is replaced
        whole or not at all.
    """
    details = client.get_tv(provider_id)
    episodes: dict[tuple[int, int], CatalogueEpisode] = {}
    for season in sorted({s.season_number for s in details.seasons or []}):
        for info in client.get_episodes(provider_id, season):
            episodes.setdefault(
                (season, info.episode_number),
                CatalogueEpisode(season, info.episode_number, _to_date(info.air_date), info.title or None),
            )
    return details.series_status, [episodes[k] for k in sorted(episodes)]
