# personalscraper/acquire/domain.py
"""Frozen domain value objects for the acquisition lobe (RP3).

All objects are keyed on ``core.identity.MediaRef`` (tvdb_id primary).
QualityProfile + source-criteria are deferred to RP3a; the columns are
present in the schema as nullable JSON passthroughs until then.

Import direction: core.identity + stdlib only (acquire/ must never import
indexer/, scraper/, or any triage package).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from personalscraper.core.identity import MediaRef

WantedKind = Literal["movie", "episode", "season"]
WantedStatus = Literal[
    "pending",
    "searching",
    "available",
    "grabbed",
    "done",
    "abandoned",
    "absorbed",
    "fallback_episodes",
]
FollowKind = Literal["movie", "show"]

#: The ``wanted`` statuses that describe an acquisition still in flight — the
#: ONE definition of « open », so no reader can invent its own. ``done`` and
#: ``abandoned`` are deliberately absent: a closed row is history, not state,
#: and letting one speak for its episode is how two surfaces start disagreeing
#: about the same episode (acq-states phase 5).
OPEN_WANTED_STATUSES: frozenset[str] = frozenset({"pending", "searching", "available", "grabbed"})


@dataclass(frozen=True)
class FollowedSeries:
    """A TV series or movie the user wants to automatically acquire.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        title: Human-readable title (for logging/display).
        active: Whether this series is actively searched.
        added_at: Unix epoch seconds when the series was followed.
        quality_profile_json: Nullable JSON string; rich profile = RP3a.
        cadence_json: Nullable JSON string; RP9/D2.
        kind: ``"show"`` (default — every legacy row) or ``"movie"``. Drives
            the §5 film lifecycle: a movie follow produces ONE
            ``WantedItem(kind="movie")`` at detect time and is auto-unfollowed
            once the acquired file is dispatched; a show follow produces
            per-episode items and is never auto-removed.
        id: SQLite rowid — populated by ``find_by_ref()`` / ``list_active()`` /
            ``list_all()`` / ``get()``; ``None`` for an as-yet-unpersisted item.
            The follow CLI needs it to call ``set_active`` (Follow D1).
        year: Release year of the followed media, or ``None``. Used by the grab
            to disambiguate an ambiguous title — a movie query « Wicker » returns
            every « Wicker* » film, so the year narrows the search AND lets a
            ``filter_to_movie`` identity filter drop the wrong-year releases
            (the Wicker wrong-movie bug, §5/§7). Populated only by SELECTs that
            fetch the ``year`` column (decoded defensively); other reads leave it
            ``None``.
    """

    media_ref: MediaRef
    title: str
    added_at: int
    active: bool = True
    quality_profile_json: str | None = None
    cadence_json: str | None = None
    kind: FollowKind = "show"
    id: int | None = None
    year: int | None = None
    #: The operator authorised REPLACING a copy already in the library (§5).
    #: Detect honours it once — without it, a film already owned is closed on
    #: sight and the replacement the UI promised never runs. Cleared as soon as
    #: the wanted row exists.
    replace_owned: bool = False

    def __post_init__(self) -> None:
        """Validate the kind literal.

        Raises:
            ValueError: If ``kind`` is not ``"movie"`` or ``"show"``.
        """
        if self.kind not in ("movie", "show"):
            raise ValueError(f'Invalid FollowedSeries.kind={self.kind!r}; must be "movie" or "show"')


@dataclass(frozen=True)
class AiredEpisode:
    """A TV episode with a KNOWN air date — aired OR announced (episode-states D1).

    Emitted by :func:`~personalscraper.acquire.airing.poll_known` (all known
    dates) and, filtered to the aired subset, by
    :func:`~personalscraper.acquire.airing.poll_aired`. Only episodes with NO
    parseable date (unscheduled / TBA / malformed) are excluded. The name is kept
    (a rename would be pure churn); ``air_date`` carries the aired-vs-future
    distinction, compared against ``today`` by the caller.

    Attributes:
        media_ref: Provider-ID key of the parent followed series (tvdb_id primary).
        season: Season number (1-based; specials / season 0 are excluded by the poller).
        episode: Episode number within the season.
        air_date: The parsed air-date (always a real :class:`datetime.date`); may
            be in the future for an announced episode.
        title: Episode title for display/logging; empty string when the provider
            did not supply one.
    """

    media_ref: MediaRef
    season: int
    episode: int
    air_date: date
    title: str = ""


@dataclass(frozen=True)
class WantedItem:
    """A specific episode or movie the acquisition engine wants to grab.

    Attributes:
        media_ref: Provider-ID key.
        kind: ``"movie"`` or ``"episode"``.
        status: Current acquisition state.
        enqueued_at: Unix epoch seconds when the item was enqueued.
        followed_id: FK to followed_series row (optional when standalone).
        season: Season number (episodes only).
        episode: Episode number (episodes only).
        criteria_json: Nullable JSON for search criteria (RP3a).
        last_search_at: Unix epoch seconds of last search attempt.
        attempts: Number of tracker interactions — incremented by BOTH atomic
            claims (``claim_for_search`` for a search-pass claim,
            ``claim_for_grab`` for a grab-pass claim), since each one leads to a
            tracker query. It is NOT a count of search-pass attempts alone, and
            the grab pass deliberately applies no cap to it: capping there would
            abandon a known-available item on its first flaky add.
        id: SQLite rowid — populated by ``list_pending()`` / ``get()`` /
            ``list_stale_searching()``; ``None`` for an as-yet-unpersisted item.
            The acquisition service needs it to call ``claim_for_search`` /
            ``mark_grabbed`` / ``set_status`` (RP5b, was a blocking gap).
        grabbed_hash: Torrent info-hash of the release this row is committed to.
            Written in TWO phases (D2): ``record_grab_intent`` reserves it
            BEFORE the orchestrator's ``add()`` (the row still reads
            'searching' — an intention), and ``mark_grabbed`` /
            ``confirm_grab_intent`` promotes the row to 'grabbed' afterwards.

            The idempotence guard consults this hash rather than the status
            alone, so once it is set no later pass can re-grab or re-emit —
            including a row left at 'searching' by a crash anywhere in the
            add→confirm window. Such a row is never reclaimed by the stale
            sweep (that would add a second torrent); the reconciliation replays
            it against the torrent client: present ⇒ confirmed 'grabbed' with
            its seed obligation recorded, absent ⇒ hash cleared and the row is
            searchable again.

            A grab that FAILS rather than crashing releases the reservation
            itself, on the way out (``clear_grab_intent``, called for every
            non-success disposition before the status write). That path must
            not lean on the reconciliation: it decides nothing without a
            reachable torrent client, and an unreachable client is the very
            thing that makes ``add()`` fail. A row whose hash outlived its
            failed add is reachable by NOTHING — not the stale sweep (it
            refuses a hash-carrying row), not the grab pass (the guard above),
            not the search pass ('searching' is not 'pending'), not even the
            cadence cutoff (the gate skips out before the age check).

            So the hash always points at a torrent that was really handed to
            the client, and neither a crash nor a failed add can strand an
            orphan or swap the chosen release. ``None`` until a grab commits.
        last_search_outcome: Named issue of the last search pass
            (``no_candidates``, ``all_filtered``, ``trackers_unavailable``,
            ``available``, …). ``None`` means never searched — the honest
            default for pre-existing rows and freshly-enqueued items: we
            genuinely do not know. Distinguishing ``None`` from a real outcome
            is what prevents a tracker outage from reading as « À jour ».
        last_search_found: Count of TAKEABLE candidates — survivors of the
            exact-episode filter, the hard profile filters and the
            ``min_seeders`` floor — at the time of the last concluded search.
            ``None`` when the search did NOT conclude (outage, open circuit,
            dead swarm): zero would falsely claim « I looked, there is
            nothing », which is the lie of the Furious incident (DESIGN §1).
            ``None`` is also the default for never-searched rows.
        tried_hashes: Lowercase info-hashes of releases already grabbed-and-failed
            for this item (dead swarm / broken payload). The auto-reswitch
            (reswitch #342) appends the stalled hash before requeueing, and the
            next search ranks EXCLUDING these so it never loops back to a known
            dead release. Empty tuple = none tried (the default for pre-existing
            rows and the ordinary first grab). Populated only by SELECTs that
            fetch ``tried_hashes_json``; other reads leave it empty.
    """

    media_ref: MediaRef
    kind: WantedKind
    status: WantedStatus
    enqueued_at: int
    followed_id: int | None = None
    season: int | None = None
    episode: int | None = None
    criteria_json: str | None = None
    last_search_at: int | None = None
    attempts: int = 0
    id: int | None = None
    grabbed_hash: str | None = None
    last_search_outcome: str | None = None
    last_search_found: int | None = None
    tried_hashes: tuple[str, ...] = ()
    absorbed_by: int | None = None

    def __post_init__(self) -> None:
        """Validate kind and status values.

        Raises:
            ValueError: If kind or status is not a valid literal.
        """
        valid_kinds: tuple[str, ...] = ("movie", "episode", "season")
        valid_statuses: tuple[str, ...] = (
            "pending",
            "searching",
            "available",
            "grabbed",
            "done",
            "abandoned",
            "absorbed",
            "fallback_episodes",
        )
        if self.kind not in valid_kinds:
            raise ValueError(f"Invalid WantedItem.kind={self.kind!r}; must be one of {valid_kinds}")
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid WantedItem.status={self.status!r}; must be one of {valid_statuses}")


@dataclass(frozen=True)
class SeedObligation:
    """A seed obligation created when a torrent payload is dispatched.

    The deletion authority consults this table before permitting any deletion
    of a dispatched path.

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name string (e.g. ``"c411"``).
        min_seed_time_s: Minimum seed time in seconds (snapshot from TrackerEconomyConfig).
        min_ratio: Minimum ratio (snapshot).
        added_at: Unix epoch seconds when obligation was recorded.
        dispatched_path: Absolute path of the dispatched media (set after move).
        satisfied_at: Unix epoch seconds when obligation was satisfied (nullable).
        breached_at: Unix epoch seconds when obligation was breached (nullable).
        released_at: Unix epoch seconds when tracker released the obligation (nullable).
    """

    info_hash: str
    source_tracker: str
    min_seed_time_s: int
    min_ratio: float
    added_at: int
    dispatched_path: str | None = None
    satisfied_at: int | None = None
    breached_at: int | None = None
    released_at: int | None = None

    def __post_init__(self) -> None:
        """Enforce the non-negativity invariant on the seed-obligation floors.

        A negative ``min_seed_time_s`` would make
        ``seed_time_elapsed >= obligation.min_seed_time_s`` trivially true in
        :meth:`DeleteAuthority.may_delete`, silently passing the HnR guard for a
        live seed (T1). A negative ``min_ratio`` is likewise nonsensical. Both
        are snapshots from a TrackerEconomyConfig, so a negative value here is a
        programming error worth surfacing at construction.

        Raises:
            ValueError: If ``min_seed_time_s`` or ``min_ratio`` is negative.
        """
        if self.min_seed_time_s < 0:
            raise ValueError(f"SeedObligation.min_seed_time_s must be >= 0; got {self.min_seed_time_s}")
        if self.min_ratio < 0:
            raise ValueError(f"SeedObligation.min_ratio must be >= 0; got {self.min_ratio}")


@dataclass(frozen=True)
class RatioState:
    """Per-tracker ratio state (DORMANT — writer arrives with Ratio C1, Vague 5).

    Table is created now as a data-carrier; no RP3 code writes to it.

    Attributes:
        tracker_name: Tracker identifier (PK).
        observed_ratio: Last observed upload/download ratio.
        accumulated_seed_time_s: Total accumulated seed time in seconds.
        hnr_count: Number of hit-and-run events recorded.
        updated_at: Unix epoch seconds of last update.
    """

    tracker_name: str
    observed_ratio: float
    accumulated_seed_time_s: int
    hnr_count: int
    updated_at: int


@dataclass(frozen=True)
class AiredEpisodeRow:
    """One cached aired episode of a followed series (``aired_episode`` table).

    Attributes:
        followed_id: FK to the ``followed_series`` row.
        season: Season number (>= 1; specials are excluded upstream).
        episode: Episode number within the season.
        title: Episode title from the provider, or ``None``.
        air_date: ISO-8601 air date (``YYYY-MM-DD``).
        updated_at: Unix epoch seconds of the detect pass that wrote the row.
    """

    followed_id: int
    season: int
    episode: int
    title: str | None
    air_date: str
    updated_at: int


__all__ = [
    "OPEN_WANTED_STATUSES",
    "AiredEpisode",
    "AiredEpisodeRow",
    "FollowedSeries",
    "RatioState",
    "SeedObligation",
    "WantedItem",
    "WantedKind",
    "WantedStatus",
]
