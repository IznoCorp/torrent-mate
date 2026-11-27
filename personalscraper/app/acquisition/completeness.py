"""``FollowCompleteness``: what a follow has aired against what the library holds, season by season (v1).

v1's twin of ``web/acquisition/completeness.py`` (v1 never imports ``web/``), over the same facts and
the same derivation: the detect-written ``aired_episode`` cache (never a provider poll, NE-DOIT-PAS-8),
the library's ownership by provider id, and the follow's ``wanted`` rows, whose governing row per
episode :func:`~personalscraper.app.acquisition.states.governing_facts_by_episode` picks. Every
episode's state comes from :func:`~personalscraper.app.acquisition.states.derive_episode_state`.

:func:`episode_states` is the ONE read both surfaces of a follow use: the completeness matrix here,
and the follow card's counts (``FollowService``), so the two cannot answer differently about one
episode. Read only; each source fail-soft (an unreadable cache is ignorance, never a 500).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal, Protocol

from personalscraper.app.accounts.authorise import requires
from personalscraper.app.acquisition.follow_repository import FollowAmbiguous, FollowRepository
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.acquisition.refusals import refuse_ambiguous, refuse_not_found
from personalscraper.app.acquisition.states import (
    NO_WANTED_FACTS,
    EpisodeState,
    derive_episode_state,
    governing_facts_by_episode,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import AiredEpisodeRow, FollowedSeries
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.accounts.ids import AccountId
    from personalscraper.core.identity import MediaRef

log = get_logger("app.acquisition.completeness")

__all__ = [
    "Completeness",
    "EpisodeCompleteness",
    "FollowCompleteness",
    "OwnershipReader",
    "SeasonCompleteness",
    "episode_states",
]

#: The episode states a season header counts as « in motion »: takeable, taken, or carried by a season row.
_IN_MOTION: frozenset[EpisodeState] = frozenset({"to_grab", "acquiring", "absorbed"})


class OwnershipReader(Protocol):
    """What the library holds, by provider id: the indexer's ownership checker, as the follows read it."""

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Whether the library holds a live file of a work (fail-open: an error reads not owned).

        Args:
            media_ref: The work's provider ids.
            kind: ``"movie"`` or ``"episode"``.
            season: The season of an episode.
            episode: The episode's number.

        Returns:
            True on a live file.
        """
        ...

    def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
        """The ``(season, episode)`` pairs of a show the library holds live files of.

        Args:
            media_ref: The show's provider ids.

        Returns:
            The held pairs; empty on a read error.
        """
        ...

    def close(self) -> None:
        """Release the reader's connection."""
        ...


@dataclass(frozen=True)
class EpisodeCompleteness:
    """One episode of the aired catalogue, and its state.

    Attributes:
        season: Its season.
        episode: Its number within the season.
        title: Its title, ``None`` when the provider gave none.
        air_date: Its ISO ``YYYY-MM-DD`` air date, ``None`` when unknown (read as aired).
        state: The single derivation's reading.
        last_search_outcome: The verdict of the governing ``wanted`` row the state was derived from.
    """

    season: int
    episode: int
    title: str | None
    air_date: str | None
    state: EpisodeState
    last_search_outcome: str | None


@dataclass(frozen=True)
class SeasonCompleteness:
    """One season's tallies and its episodes.

    Attributes:
        season: Its number.
        owned: Aired episodes the library holds.
        queued: Aired episodes in motion (takeable, taken, or absorbed by a season row).
        total: Aired episodes (the announced ones apart).
        announced: Episodes whose air date is still ahead.
        episodes: Its episodes, by number.
    """

    season: int
    owned: int
    queued: int
    total: int
    announced: int
    episodes: tuple[EpisodeCompleteness, ...]


@dataclass(frozen=True)
class Completeness:
    """A follow's completeness.

    Attributes:
        follow_id: The follow's row.
        key: The follow's wire key: what the contract's ``FollowCompleteness.followedId`` carries.
        title: Its title.
        kind: ``"show"`` or ``"movie"`` (a film has no seasons).
        seasons: Its seasons, newest first; empty for a film or with no cached catalogue.
        source: ``"cache"`` when the aired catalogue was read, ``"unknown"`` when none is held.
        catalog_refreshed_at: Epoch seconds of the detect pass that wrote the cache, ``None`` without one.
    """

    follow_id: int
    key: str
    title: str
    kind: str
    seasons: tuple[SeasonCompleteness, ...]
    source: Literal["cache", "unknown"]
    catalog_refreshed_at: float | None


def _parse_iso(value: str | None) -> date | None:
    """Parse an ISO ``YYYY-MM-DD`` air date, tolerating garbage.

    Args:
        value: The cached air date, or ``None``.

    Returns:
        The date, or ``None`` when absent or malformed (the episode then reads as aired).
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def episode_states(
    store: AcquireStore, ownership: OwnershipReader, row: FollowedSeries, today: date
) -> tuple[list[EpisodeCompleteness], float | None]:
    """Derive the state of every cached episode of a followed show.

    Args:
        store: The acquire store (aired cache, wanted rows).
        ownership: What the library holds.
        row: The follow's row, its id set.
        today: The reference date for the aired / announced split.

    Returns:
        The episodes, by season then number, and the epoch the cache was written at; ``([], None)``
        for a film, a row without id, or when no catalogue is cached or it cannot be read.
    """
    if row.kind != "show" or row.id is None:
        return [], None
    try:
        cached = store.aired.list_for_followed(row.id)
    except Exception:  # fail-soft: a broken cache read is ignorance, not a 500
        log.warning("app.acquisition.completeness_cache_unreadable", followed_id=row.id, exc_info=True)
        return [], None
    if not cached:
        return [], None
    unique: dict[tuple[int, int], AiredEpisodeRow] = {}
    for one in cached:
        unique.setdefault((one.season, one.episode), one)
    try:
        episode_rows = [
            (r.id or 0, r.season, r.episode, r.status, r.last_search_outcome, r.last_search_found, r.absorbed_by)
            for r in store.wanted.list_for_followed(row.id, kind="episode")
            if r.season is not None and r.episode is not None
        ]
        season_rows = [
            (r.id or 0, r.status, r.last_search_outcome, r.last_search_found)
            for r in store.wanted.list_for_followed(row.id, kind="season")
        ]
        facts = governing_facts_by_episode(episode_rows, season_rows)
    except Exception:  # fail-soft: an unreadable queue reads as « never searched »
        log.warning("app.acquisition.completeness_queue_unreadable", followed_id=row.id, exc_info=True)
        facts = {}
    owned = ownership.owned_pairs(row.media_ref)
    episodes: list[EpisodeCompleteness] = []
    for (season, number), one in sorted(unique.items()):
        status, outcome, found = facts.get((season, number), NO_WANTED_FACTS)
        episodes.append(
            EpisodeCompleteness(
                season=season,
                episode=number,
                title=one.title,
                air_date=one.air_date,
                state=derive_episode_state(
                    owned=(season, number) in owned,
                    wanted_status=status,
                    last_search_outcome=outcome,
                    last_search_found=found,
                    air_date=_parse_iso(one.air_date),
                    today=today,
                ),
                last_search_outcome=outcome,
            )
        )
    return episodes, float(max(one.updated_at for one in cached))


def seasons_of(episodes: list[EpisodeCompleteness]) -> tuple[SeasonCompleteness, ...]:
    """Group episodes by season and tally each, newest season first.

    Args:
        episodes: The episodes :func:`episode_states` derived.

    Returns:
        The seasons.
    """
    by_season: dict[int, list[EpisodeCompleteness]] = {}
    for one in episodes:
        by_season.setdefault(one.season, []).append(one)
    return tuple(
        SeasonCompleteness(
            season=season,
            owned=sum(1 for e in eps if e.state == "in_library"),
            queued=sum(1 for e in eps if e.state in _IN_MOTION),
            total=sum(1 for e in eps if e.state != "announced"),
            announced=sum(1 for e in eps if e.state == "announced"),
            episodes=tuple(eps),
        )
        for season, eps in sorted(by_season.items(), reverse=True)
    )


class FollowCompleteness:
    """Reads a follow's completeness for an actor allowed to read the follow."""

    def __init__(
        self,
        *,
        open_store: Callable[[], AcquireStore],
        open_ownership: Callable[[], OwnershipReader],
        owner: Callable[[], AccountId],
        today: Callable[[], date] = date.today,
    ) -> None:
        """Build the service; nothing is opened until a read.

        Args:
            open_store: Opens the acquire store for one call (closed after it).
            open_ownership: Opens the library's ownership reader for one call (closed after it).
            owner: The account a follow with no requester is the ask of (ruling 9).
            today: Today's date.
        """
        self._open_store = open_store
        self._open_ownership = open_ownership
        self._owner = owner
        self._today = today

    @requires("readFollowCompleteness")
    def read(self, actor: Actor, key: AcquisitionKey) -> Completeness:
        """Read the completeness of the follow *key* names.

        Args:
            actor: Who reads; reads a follow it asked for, or any with ``acquisition.see.others``.
            key: The medium's key.

        Returns:
            The completeness.

        Raises:
            AppNotFound: ``acquisition.not_found`` when no standing follow or request holds the key,
                or the actor may not read it (never a 403: a read is filtered).
            AppConflict: ``follow.ambiguous`` when two rows hold the key.
        """
        with closing(self._open_store()) as store:
            repository = FollowRepository(store)
            try:
                follow = repository.get(key)
            except FollowAmbiguous as exc:
                raise refuse_ambiguous(key) from exc
            if follow is None or follow.removed_at is not None or not follow.readable_by(actor, self._owner()):
                raise refuse_not_found(key)
            row = repository.row(follow.id)
            if row is None:
                raise refuse_not_found(key)
            with closing(self._open_ownership()) as ownership:
                episodes, refreshed_at = episode_states(store, ownership, row, self._today())
        return Completeness(
            follow_id=int(follow.id),
            key=follow.key.wire,
            title=row.title,
            kind=row.kind,
            seasons=seasons_of(episodes),
            source="cache" if refreshed_at is not None else "unknown",
            catalog_refreshed_at=refreshed_at,
        )
