"""DETECT service — aired-episode / followed-film detection engine (ACQUIRE-03).

Stage A of the acquisition flow: polls the active followed set for aired
episodes, reconciles grabbed rows against the library, then decides — per
followed film and per aired episode — whether to enqueue a wanted item, skip it
(owned / duplicate), resurrect a wrongfully-abandoned row, or (for a film whose
media already landed) close it and retire the follow.

This business logic used to live entirely in ``commands/follow.py``; unlike
``grab`` (:class:`~personalscraper.acquire.service.AcquisitionService`) and
``watch``, DETECT had no acquire engine. It is now a service (store, ownership,
metadata registry, bus, config injected) returning a per-item
:class:`DetectAction` list + a :class:`DetectSummary`, mirroring
``AcquisitionService`` / ``RunSummary``. The CLI keeps only table rendering,
run-row counts, and the redis-publisher lifecycle.

Import direction: acquire/ downward only — polls through the
``core``-agnostic metadata ``ProviderRegistry`` handed in by the composition
root, ownership through the ``core.ownership`` port, and emits acquire events on
the injected bus. Never imports triage packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from personalscraper.acquire.airing import poll_aired
from personalscraper.acquire.cadence import is_past_cutoff
from personalscraper.acquire.desired import cadence_from_config, cadence_from_json, effective_cadence
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import FilmAcquired, WantedEnqueued
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from datetime import date

    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import AiredEpisode, FollowedSeries
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.identity import MediaRef
    from personalscraper.core.ownership import OwnershipChecker

log = get_logger("acquire.detect")


class DetectStatus(str, Enum):
    """Top-level outcome of a detect run (drives the CLI's empty-set message)."""

    OK = "ok"
    NO_ACTIVE = "no_active"
    NO_MATCH = "no_match"


class DetectOutcome(str, Enum):
    """Per-item detect outcome — the CLI maps it to a table-cell label."""

    FILM_ACQUIRED = "film_acquired"
    SKIPPED_OWNED = "skipped_owned"
    SKIPPED_DUP = "skipped_dup"
    RESURRECTED = "resurrected"
    ENQUEUED = "enqueued"


@dataclass(frozen=True)
class DetectAction:
    """One detect decision, carrying the data the CLI renders as a table row.

    Attributes:
        kind: ``"movie"`` or ``"episode"`` (selects the column layout).
        title: Series/film title (column 1).
        season: Season number, or ``None`` for a film row.
        episode: Episode number, or ``None`` for a film row.
        air_date: ISO air-date string, or ``None`` for a film row.
        episode_title: Episode title, or ``None`` for a film row.
        outcome: The decision — the CLI maps ``outcome`` (+ dry-run) to the
            exact rich-markup label used before the extraction.
    """

    kind: str
    title: str
    season: int | None
    episode: int | None
    air_date: str | None
    episode_title: str | None
    outcome: DetectOutcome


@dataclass(frozen=True)
class DetectSummary:
    """Counts of one detect run (feeds the run row + CLI summary line).

    Attributes:
        enqueued: Wanted items newly enqueued (films + episodes).
        skipped_owned: Items skipped because the library owns them (includes
            retired films).
        skipped_dup: Items skipped because a live wanted row already exists.
        resurrected: Wrongfully-abandoned episode rows re-opened to pending.
        closed_owned: Grabbed rows closed ``done`` by the pre-pass reconcile.
    """

    enqueued: int = 0
    skipped_owned: int = 0
    skipped_dup: int = 0
    resurrected: int = 0
    closed_owned: int = 0

    @property
    def detected(self) -> int:
        """Total items considered (enqueued + owned + dup + resurrected)."""
        return self.enqueued + self.skipped_owned + self.skipped_dup + self.resurrected


@dataclass(frozen=True)
class DetectResult:
    """Full result of a detect run: status + per-item actions + counts."""

    status: DetectStatus
    actions: list[DetectAction]
    summary: DetectSummary


class DetectService:
    """Detect aired episodes / followed films and enqueue them as wanted items.

    Mirrors :class:`~personalscraper.acquire.service.AcquisitionService`: the
    store, ownership port, metadata registry, event bus, and config are injected
    once; :meth:`run` performs one detection pass and returns a structured
    result the CLI renders. All provider polls and ownership checks are
    fail-soft (a failure is logged and treated as "no episodes" / "not owned")
    so one bad series or a missing library never aborts the run.
    """

    def __init__(
        self,
        *,
        store: "AcquireStore",
        ownership: "OwnershipChecker",
        registry: "ProviderRegistry",
        event_bus: "EventBus",
        config: "Config",
    ) -> None:
        """Store the injected collaborators.

        Args:
            store: The acquire store (single-writer discipline via its sub-stores).
            ownership: The library ownership port (RP6).
            registry: The metadata provider registry ``poll_aired`` polls.
            event_bus: The bus on which ``WantedEnqueued`` / ``FilmAcquired`` fire.
            config: The validated config (read for the cadence default).
        """
        self._store = store
        self._ownership = ownership
        self._registry = registry
        self._event_bus = event_bus
        self._config = config

    def run(self, *, series: str | None, dry_run: bool, today: "date", now: int) -> DetectResult:
        """Run one detect pass over the active followed set.

        Args:
            series: Optional filter — an integer ``followed_id`` or a
                case-insensitive title substring.
            dry_run: When ``True`` no writes or events happen; the returned
                actions still reflect what would occur.
            today: The reference date for the airing poll.
            now: Unix-epoch timestamp stamped on new/resurrected rows.

        Returns:
            A :class:`DetectResult` — ``NO_ACTIVE`` / ``NO_MATCH`` (empty
            actions) or ``OK`` with the per-item actions and counts.
        """
        active = self._store.follow.list_active()
        if not active:
            return DetectResult(DetectStatus.NO_ACTIVE, [], DetectSummary())

        if series is not None:
            try:
                filter_id = int(series)
                active = [s for s in active if s.id == filter_id]
            except ValueError:
                active = [s for s in active if series.lower() in s.title.lower()]
            if not active:
                return DetectResult(DetectStatus.NO_MATCH, [], DetectSummary())

        # §5 films produce ONE WantedItem(kind='movie') with no airing poll; a
        # movie follow has no episode schedule and would be silently skipped by
        # the poller, so split the set.
        movie_follows = [s for s in active if s.kind == "movie"]
        show_follows = [s for s in active if s.kind != "movie"]
        by_ref = {s.media_ref: s for s in show_follows}

        aired = self._poll(show_follows, today=today)
        if not dry_run:
            self._persist_aired_cache(aired, by_ref, now=now)

        closed_owned = 0
        if not dry_run:
            # P0-B.3 — reconcile grabbed rows against the library BEFORE the
            # enqueue pass (detect has no torrent client, so the vanished-torrent
            # requeue is left to the grab cron).
            try:
                closed_owned = reconcile_wanted(self._store, self._ownership, None).closed_owned
            except Exception as exc:  # noqa: BLE001 — reconciliation must never abort detect
                log.warning("acquire.detect.reconcile_failed", error=str(exc))

        actions: list[DetectAction] = []
        counts = _MutableCounts()
        for mf in movie_follows:
            self._detect_movie(mf, actions, counts, dry_run=dry_run, now=now)
        for ep in aired:
            self._detect_episode(ep, by_ref, actions, counts, dry_run=dry_run, now=now)

        summary = DetectSummary(
            enqueued=counts.enqueued,
            skipped_owned=counts.skipped_owned,
            skipped_dup=counts.skipped_dup,
            resurrected=counts.resurrected,
            closed_owned=closed_owned,
        )
        return DetectResult(DetectStatus.OK, actions, summary)

    def _poll(self, show_follows: "list[FollowedSeries]", *, today: "date") -> "list[AiredEpisode]":
        """Poll aired episodes over the active shows (fail-soft → empty)."""
        if not show_follows:
            return []
        try:
            return poll_aired(show_follows, self._registry, today=today)
        except Exception as exc:  # noqa: BLE001 — defensive; poll_aired is already fail-soft per series
            log.warning("acquire.detect.poll_failed", error=str(exc))
            return []

    def _persist_aired_cache(
        self, aired: "list[AiredEpisode]", by_ref: "dict[MediaRef, FollowedSeries]", *, now: int
    ) -> None:
        """P0-B.1 — persist the polled aired catalog per followed series (best-effort).

        Skipped for a series whose poll came back empty: an outage or an empty
        catalog must never wipe a previously good cache.
        """
        aired_by_id: dict[int, list[tuple[int, int, str | None, str]]] = {}
        for ep in aired:
            fs = by_ref.get(ep.media_ref)
            if fs is not None and fs.id is not None:
                aired_by_id.setdefault(fs.id, []).append(
                    (ep.season, ep.episode, ep.title or None, ep.air_date.isoformat())
                )
        for fid, episodes in aired_by_id.items():
            try:
                self._store.aired.replace_for_followed(fid, episodes, now=now)
            except Exception as exc:  # noqa: BLE001 — cache is best-effort enrichment
                log.warning("acquire.detect.aired_cache_failed", followed_id=fid, error=str(exc))

    def _detect_movie(
        self, mf: "FollowedSeries", actions: list[DetectAction], counts: "_MutableCounts", *, dry_run: bool, now: int
    ) -> None:
        """Decide the action for one followed film and record it."""
        if mf.id is None:
            return
        try:
            owned = self._ownership.owns(mf.media_ref, kind="movie")
        except Exception as exc:  # noqa: BLE001 — fail-soft → treat as not-owned
            log.warning("acquire.detect.ownership_error", error=str(exc))
            owned = False

        if owned:
            if not dry_run:
                try:
                    # §5 closure: the film is IN the library — close its live
                    # wanted row (done) and auto-unfollow, with a visible trace.
                    live = self._store.wanted.find(followed_id=mf.id, kind="movie", season=None, episode=None)
                    if live is not None and live.id is not None and live.status != "done":
                        self._store.wanted.set_status(live.id, "done")
                    self._store.follow.set_active(mf.id, False)
                    self._event_bus.emit(FilmAcquired(media_ref=mf.media_ref, title=mf.title, followed_id=mf.id))
                    log.info("acquire.detect.film_acquired_unfollowed", series=mf.title)
                    actions.append(DetectAction("movie", mf.title, None, None, None, None, DetectOutcome.FILM_ACQUIRED))
                    counts.skipped_owned += 1
                    return
                except Exception as exc:  # noqa: BLE001 — fail-soft; retried next run
                    log.warning("acquire.detect.film_unfollow_failed", error=str(exc))
            actions.append(DetectAction("movie", mf.title, None, None, None, None, DetectOutcome.SKIPPED_OWNED))
            counts.skipped_owned += 1
            return

        # Dedup: one live wanted row per movie follow (NULL season/episode).
        if self._store.wanted.find(followed_id=mf.id, kind="movie", season=None, episode=None) is not None:
            actions.append(DetectAction("movie", mf.title, None, None, None, None, DetectOutcome.SKIPPED_DUP))
            counts.skipped_dup += 1
            return

        actions.append(DetectAction("movie", mf.title, None, None, None, None, DetectOutcome.ENQUEUED))
        counts.enqueued += 1
        if not dry_run:
            self._store.wanted.add(
                WantedItem(media_ref=mf.media_ref, kind="movie", status="pending", enqueued_at=now, followed_id=mf.id)
            )
            self._event_bus.emit(WantedEnqueued(media_ref=mf.media_ref, kind="movie", season=None, episode=None))
            log.info("acquire.detect.enqueued", series=mf.title, kind="movie")

    def _detect_episode(
        self,
        ep: "AiredEpisode",
        by_ref: "dict[MediaRef, FollowedSeries]",
        actions: list[DetectAction],
        counts: "_MutableCounts",
        *,
        dry_run: bool,
        now: int,
    ) -> None:
        """Decide the action for one aired episode and record it."""
        fs = by_ref.get(ep.media_ref)
        if fs is None or fs.id is None:
            return

        try:
            owned = self._ownership.owns(ep.media_ref, kind="episode", season=ep.season, episode=ep.episode)
        except Exception as exc:  # noqa: BLE001 — fail-soft → treat as not-owned
            log.warning("acquire.detect.ownership_error", error=str(exc))
            owned = False

        if owned:
            actions.append(
                DetectAction(
                    "episode", fs.title, ep.season, ep.episode, str(ep.air_date), ep.title, DetectOutcome.SKIPPED_OWNED
                )
            )
            counts.skipped_owned += 1
            return

        # Dedup against the wanted queue — with the B.4 exception: an
        # ``abandoned`` aired-but-unowned episode still within its cadence cutoff
        # was abandoned wrongfully and is resurrected to pending.
        existing = self._store.wanted.find(followed_id=fs.id, kind="episode", season=ep.season, episode=ep.episode)
        if existing is not None:
            resurrectable = False
            if existing.status == "abandoned" and existing.id is not None:
                cadence = effective_cadence(
                    cadence_from_json(fs.cadence_json) if fs.cadence_json is not None else None,
                    cadence_from_config(self._config.acquire.cadence),
                )
                resurrectable = not is_past_cutoff(cadence, now=now, enqueued_at=existing.enqueued_at)
            if resurrectable and (dry_run or self._store.wanted.resurrect(existing.id, now)):  # type: ignore[arg-type]
                actions.append(
                    DetectAction(
                        "episode",
                        fs.title,
                        ep.season,
                        ep.episode,
                        str(ep.air_date),
                        ep.title,
                        DetectOutcome.RESURRECTED,
                    )
                )
                counts.resurrected += 1
                log.info(
                    "acquire.detect.resurrected", series=fs.title, season=ep.season, episode=ep.episode, dry_run=dry_run
                )
                return
            actions.append(
                DetectAction(
                    "episode", fs.title, ep.season, ep.episode, str(ep.air_date), ep.title, DetectOutcome.SKIPPED_DUP
                )
            )
            counts.skipped_dup += 1
            return

        actions.append(
            DetectAction("episode", fs.title, ep.season, ep.episode, str(ep.air_date), ep.title, DetectOutcome.ENQUEUED)
        )
        counts.enqueued += 1
        if not dry_run:
            # No ``criteria_json`` set: DESIGN §6's mapping reduces to None at D2
            # since FollowedSeries has no per-series source-criteria field yet.
            self._store.wanted.add(
                WantedItem(
                    media_ref=ep.media_ref,
                    kind="episode",
                    status="pending",
                    enqueued_at=now,
                    followed_id=fs.id,
                    season=ep.season,
                    episode=ep.episode,
                )
            )
            self._event_bus.emit(
                WantedEnqueued(media_ref=ep.media_ref, kind="episode", season=ep.season, episode=ep.episode)
            )
            log.info("acquire.detect.enqueued", series=fs.title, season=ep.season, episode=ep.episode)


@dataclass
class _MutableCounts:
    """Running per-run counters mutated across the movie + episode passes."""

    enqueued: int = 0
    skipped_owned: int = 0
    skipped_dup: int = 0
    resurrected: int = 0


__all__ = [
    "DetectAction",
    "DetectOutcome",
    "DetectResult",
    "DetectService",
    "DetectStatus",
    "DetectSummary",
]
