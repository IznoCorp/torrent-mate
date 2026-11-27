# personalscraper/acquire/domain.py
"""Frozen domain value objects for the acquisition lobe (RP3).

All objects are keyed on ``core.identity.MediaRef`` (tvdb_id primary).
QualityProfile + source-criteria are deferred to RP3a; the columns are
present in the schema as nullable JSON passthroughs until then.

Import direction: core.identity + stdlib only (acquire/ must never import
indexer/, scraper/, or any triage package).
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
#: Why a ``followed_series`` row exists: ``"follow"`` (a standing follow, every row written before
#: migration 027) or ``"request"`` (a one-off request, DESIGN O-2 A).
FollowScope = Literal["follow", "request"]
#: How an account asked for a follow (``acquisition_requester.via``).
RequesterVia = Literal["follow", "request"]
#: What put a ``wanted`` row in the queue: a person's ask, or the engine's own rule.
WantedTrigger = Literal["manual", "automatic"]
#: Why a title is suggested, as the CODE the interface words: it resembles one the library holds, or one
#: an account follows (``suggestion.reason``).
SuggestionReason = Literal["similar_to_owned", "similar_to_followed"]
#: The quality floors a requester can set, as vertical resolutions.
REQUESTER_FLOORS: frozenset[int] = frozenset({720, 1080, 2160})

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
    #: The provider's ORIGINAL-language title (TMDB ``original_title``), or
    #: ``None`` when not resolved yet. Releases are commonly named in the
    #: original language while the follow carries the localized display title
    #: (« Avant d'aller dormir » vs `Before.I.Go.To.Sleep.2014...`), so the
    #: movie identity filter matches against BOTH (#435). Stored verbatim even
    #: when equal to ``title`` — non-NULL means « healed », which stops the
    #: detect-pass backfill from refetching. Populated only by SELECTs that
    #: fetch the column (decoded defensively, like ``year``).
    original_title: str | None = None
    #: The operator authorised REPLACING a copy already in the library (§5).
    #: Detect honours it once — without it, a film already owned is closed on
    #: sight and the replacement the UI promised never runs. Cleared as soon as
    #: the wanted row exists.
    replace_owned: bool = False
    #: ``"follow"`` (every row written before migration 027) or ``"request"``: a one-off
    #: request is a ``followed_series`` row with this scope (DESIGN O-2 A). Populated by
    #: every ``followed_series`` reader; no writer sets it yet.
    scope: FollowScope = "follow"
    #: Unix epoch seconds when the last requester left, ``None`` while the follow stands.
    removed_at: int | None = None

    def __post_init__(self) -> None:
        """Validate the kind and scope literals.

        Raises:
            ValueError: If ``kind`` is not ``"movie"`` or ``"show"``, or ``scope`` is not
                ``"follow"`` or ``"request"``.
        """
        if self.kind not in ("movie", "show"):
            raise ValueError(f'Invalid FollowedSeries.kind={self.kind!r}; must be "movie" or "show"')
        if self.scope not in ("follow", "request"):
            raise ValueError(f'Invalid FollowedSeries.scope={self.scope!r}; must be "follow" or "request"')

    @property
    def is_following(self) -> bool:
        """Whether this row is a standing follow: active, of scope ``follow`` and not removed.

        A one-off request row (DESIGN O-2 A) or a removed row is not a follow even when its
        ``active`` flag reads true, so a caller asking « is this medium followed? » reads
        this and never ``active`` alone.

        Returns:
            ``True`` for a standing follow.
        """
        return self.active and self.scope == "follow" and self.removed_at is None


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
class SeriesCatalog:
    """Everything ONE provider poll learned about one followed series.

    Emitted by :func:`~personalscraper.acquire.airing.poll_catalog`. It exists so
    the production status can reach the store without a second round of provider
    calls: the poll already fetches the series details to enumerate the seasons,
    and used to discard every field but the season list.

    Attributes:
        followed_id: The ``followed_series`` rowid this catalogue belongs to, or
            ``None`` for an unpersisted follow.
        media_ref: Provider-ID key of the series (tvdb_id primary).
        series_status: The provider's raw production status (TVDB « Continuing »
            / « Ended », TMDB « Returning Series » / « Ended » / « Canceled »),
            or ``None`` when the provider names none. ``None`` is IGNORANCE, not
            « still running » — the card never claims « Terminé » on it.
        episodes: Every episode with a known air date, futures included.
    """

    followed_id: int | None
    media_ref: MediaRef
    series_status: str | None
    episodes: list[AiredEpisode]


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
        trigger: What put the row in the queue: ``"manual"`` (a person's ask) or
            ``"automatic"`` (detect, the search conversions). ``None`` is an honest
            "unknown": every row written before migration 027, and v0's frozen season
            route, which writes none.
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
    trigger: WantedTrigger | None = None

    def __post_init__(self) -> None:
        """Validate kind, status and trigger values.

        Raises:
            ValueError: If kind, status or trigger is not a valid literal.
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
        if self.trigger not in (None, "manual", "automatic"):
            raise ValueError(f'Invalid WantedItem.trigger={self.trigger!r}; must be "manual", "automatic" or None')


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
        id: ``seed_obligation`` row id, set on rows read back from the store and
            ``None`` on a not-yet-stored obligation.
        absent_since: Unix epoch seconds of the first sweep that did not find the
            torrent in the client (nullable); cleared when the torrent is seen again.
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
    id: int | None = None
    absent_since: int | None = None

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


@dataclass(frozen=True)
class FollowCard:
    """The card facts of a ``followed_series`` row the follow readers show, beside its identity.

    Attributes:
        poster_url: The poster's address the add path or the backfill stored, or ``None``.
        series_status: The provider's raw production status of a show (« Continuing »,
            « Ended »), or ``None`` when unknown or for a film.
    """

    poster_url: str | None
    series_status: str | None


@dataclass(frozen=True)
class FollowRequester:
    """One account's ask for a follow (``acquisition_requester`` table).

    The engine never learns of rights: ``account_id`` is an opaque id, and the rules over
    requesters (what is in force, who may read) are the acquisition model's, not the store's.

    Attributes:
        followed_id: FK to the ``followed_series`` row asked for.
        account_id: The asking account, opaque to the engine.
        via: How the account asked: ``"follow"`` or ``"request"``.
        floor: The requester's own quality floor as a vertical resolution (720, 1080 or
            2160), ``None`` when none is set.
        paused: Whether this requester paused its ask.
        since: Unix epoch seconds when the account first asked.
    """

    followed_id: int
    account_id: str
    via: RequesterVia
    floor: int | None
    paused: bool
    since: int

    def __post_init__(self) -> None:
        """Validate the via and the floor before the CHECK constraints would.

        Raises:
            ValueError: If ``via`` is not ``"follow"`` or ``"request"``, or ``floor`` is
                neither ``None`` nor one of :data:`REQUESTER_FLOORS`.
        """
        if self.via not in ("follow", "request"):
            raise ValueError(f'Invalid FollowRequester.via={self.via!r}; must be "follow" or "request"')
        if self.floor is not None and self.floor not in REQUESTER_FLOORS:
            raise ValueError(
                f"Invalid FollowRequester.floor={self.floor!r}; must be None or one of {sorted(REQUESTER_FLOORS)}"
            )


@dataclass(frozen=True)
class WantedCandidate:
    """One ranked candidate a concluded search found for a wanted row (``wanted_candidate``).

    The set of a wanted row is replaced wholesale by its next concluded search. The row
    carries no ``wanted_id``: the set is read and written by the wanted row's id.

    Attributes:
        rank: Position in the ranked set, 1 the best; unique within a wanted row.
        provider: The tracker that offered the release.
        title: The release's title as the tracker published it.
        info_hash: The torrent info-hash, ``None`` when the tracker gave none.
        size_bytes: The release's size.
        seeders: The seeders when searched.
        resolution: The parsed resolution (``"1080p"``), ``None`` when unknown.
        source: The parsed source (``"WEB"``), ``None`` when unknown.
        language: The parsed language tag, ``None`` when unknown.
        score: The ranking score.
        season: The season the release numbers, ``None`` when it numbers none.
        episode: The episode the release numbers, ``None`` for a pack or none.
        searched_at: Unix epoch seconds of the concluded search that found it.
    """

    rank: int
    provider: str
    title: str
    info_hash: str | None
    size_bytes: int
    seeders: int
    resolution: str | None
    source: str | None
    language: str | None
    score: int
    season: int | None
    episode: int | None
    searched_at: int


@dataclass(frozen=True)
class SuggestionRow:
    """One title of the suggestions deck (``suggestion``, migration 028).

    The deck is replaced wholesale by each refresh; a title is in it once, by
    ``(provider, provider_id, kind)``.

    Attributes:
        provider: The provider that recommended the title (``"trakt"``, ``"tmdb"``…).
        provider_id: The title's id at that provider: a number, an IMDb id or a slug.
        kind: ``"movie"`` or ``"show"``.
        title: The provider's title.
        year: The release or first-air year, ``None`` when the provider gave none.
        rating: The provider's rating, ``None`` when the recommendation carried none.
        poster: The poster's address, ``None`` when the recommendation carried none.
        reason: Why it is suggested, as a code.
        seed_key: The title whose recommendation this is (``"tmdb:603"``, ``"imdb:tt0133093"``).
        refreshed_at: Unix epoch seconds of the refresh that wrote the row.
        id: The row's rising key (the deck's order and its cursor); ``None`` until persisted.
        external_ids: The other ids the provider gave the title beside ``provider_id``
            (``"imdb"`` / ``"tmdb"`` / ``"tvdb"`` → the id as text): a provider that names its titles
            by a slug is matched to the library and the follows by these. Empty when it gave none.
    """

    provider: str
    provider_id: str
    kind: FollowKind
    title: str
    year: int | None
    rating: float | None
    poster: str | None
    reason: SuggestionReason
    seed_key: str
    refreshed_at: int
    id: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)


__all__ = [
    "OPEN_WANTED_STATUSES",
    "REQUESTER_FLOORS",
    "AiredEpisode",
    "AiredEpisodeRow",
    "FollowRequester",
    "FollowScope",
    "FollowedSeries",
    "RatioState",
    "RequesterVia",
    "SeedObligation",
    "SuggestionReason",
    "SuggestionRow",
    "WantedCandidate",
    "WantedItem",
    "WantedKind",
    "WantedStatus",
    "WantedTrigger",
]
