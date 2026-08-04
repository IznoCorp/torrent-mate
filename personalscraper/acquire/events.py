"""Acquisition event catalog (RP4).

Defines the 10 typed events emitted by the acquisition lobe. All classes are
frozen kw_only dataclasses over :class:`~personalscraper.core.event_bus.Event`.
Payload fields mirror the already-persisted
:mod:`personalscraper.acquire.domain` value objects so shapes are determined
by shipped data, not speculation (DESIGN §3).

Import direction: imports ``core.event_bus``, ``core.identity``, and stdlib
only — no ``indexer``, ``scraper``, or triage imports (acquire/ layering rule).

Producers arrive in waves 4–5 (Follow D1–D3, Ratio C1, Seed-Safety O2,
Watcher). RP4 defines the shapes; events stay unused until then.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from personalscraper.core.event_bus import Event
from personalscraper.core.identity import MediaRef


@dataclass(frozen=True, kw_only=True)
class SeriesFollowed(Event):
    """A TV series or movie was added to the follow list.

    Emitted by Follow D1 when the user subscribes to a series.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        title: Human-readable title for logging/display.
    """

    media_ref: MediaRef
    title: str


@dataclass(frozen=True, kw_only=True)
class SeriesUnfollowed(Event):
    """A TV series or movie was removed from the follow list.

    Emitted by Follow D1 when the user unsubscribes from a series.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
    """

    media_ref: MediaRef


@dataclass(frozen=True, kw_only=True)
class FilmAcquired(Event):
    """A followed FILM is now in the library — auto-removed from the follows.

    §5 closure (product-intent): "une fois récupéré et acquis (pipeline
    terminé), il est retiré des suivis automatiquement". Emitted by the detect
    reconciliation when a movie follow's ownership check flips to owned: the
    live wanted rows are closed (``done``) and the follow is deactivated. The
    event is the operator-visible trace ("Film X acquis — retiré des suivis").

    Attributes:
        media_ref: Provider-ID key of the acquired film.
        title: Human-readable film title (for the feed/toast).
        followed_id: The deactivated ``followed_series`` rowid.
    """

    media_ref: MediaRef
    title: str
    followed_id: int


@dataclass(frozen=True, kw_only=True)
class WantedEnqueued(Event):
    """A specific episode or movie was added to the wanted queue.

    Emitted by Follow D2 when a new episode/movie is queued for acquisition.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        kind: ``"movie"`` or ``"episode"``.
        season: Season number (episodes only; ``None`` for movies).
        episode: Episode number (episodes only; ``None`` for movies).
    """

    media_ref: MediaRef
    kind: Literal["movie", "episode", "season"]
    season: int | None
    episode: int | None


@dataclass(frozen=True, kw_only=True)
class WantedAbandoned(Event):
    """A wanted item was abandoned (e.g. cutoff reached, no source found).

    Emitted by Follow D2 when an item leaves the queue without being grabbed.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        reason: Human-readable abandonment reason.
    """

    media_ref: MediaRef
    reason: str


@dataclass(frozen=True, kw_only=True)
class SeasonAbsorbedEpisodes(Event):
    """A season wanted absorbed its season's live episode wanteds (R5).

    Emitted when detection or the conversion path absorbs episode rows
    into a season wanted — the episode rows transition to ``absorbed``
    and the season wanted governs their acquisition.

    Attributes:
        season_wanted_id: Rowid of the absorbing season ``wanted`` row.
        media_ref: Provider-ID key of the parent series.
        season: Season number.
        absorbed_ids: Rowids of the episode rows that were absorbed.
    """

    season_wanted_id: int
    media_ref: MediaRef
    season: int
    absorbed_ids: tuple[int, ...]


@dataclass(frozen=True, kw_only=True)
class SeasonEscalatedAfterEpisodeFailures(Event):
    """A season pack was enqueued because the per-episode route provably failed (D1).

    Distinct from :class:`SeasonAbsorbedEpisodes`, which says WHAT happened but not
    WHY. The operator UI needs the reason to state, in plain French, that the
    episodes do not exist separately and the whole-season pack is being taken
    instead (product-intent §2 — every state carries a clear label).

    Emitted only on the starvation path: an episode row that concluded a
    ``not_found`` search at least twice, on a fully-aired season, for which a
    covering season pack was then found. The calendar/ownership detection path
    (R4) emits :class:`WantedEnqueued` + :class:`SeasonAbsorbedEpisodes` alone.

    Attributes:
        season_wanted_id: Rowid of the season ``wanted`` row that now carries the work.
        media_ref: Provider-ID key of the parent series.
        season: Season number that was escalated.
        trigger_outcome: The episode verdict that armed the escalation —
            ``'no_candidates'`` or ``'no_matching_episode'``.
        starved_episode_ids: Rowids of the episode rows whose repeated concluded
            failure motivated the escalation.
    """

    season_wanted_id: int
    media_ref: MediaRef
    season: int
    trigger_outcome: str
    starved_episode_ids: tuple[int, ...]


@dataclass(frozen=True, kw_only=True)
class SeasonFellBackToEpisodes(Event):
    """A season wanted fell back to per-episode retry (R6).

    Emitted when a season wanted reaches its cutoff — the season row
    transitions to ``fallback_episodes`` and the missing episodes are
    re-enqueued individually. Telegram notification fires per existing
    cutoff path.

    Attributes:
        season_wanted_id: Rowid of the season ``wanted`` row.
        media_ref: Provider-ID key of the parent series.
        season: Season number.
        reenqueued_count: Number of missing episodes re-enqueued.
    """

    season_wanted_id: int
    media_ref: MediaRef
    season: int
    reenqueued_count: int


@dataclass(frozen=True, kw_only=True)
class GrabSucceeded(Event):
    """A torrent was successfully grabbed from a tracker.

    Emitted by RP5b (Follow D3 + Ratio C1) after a successful grab POST.

    Attributes:
        media_ref: Provider-ID key; ``None`` when the grab is unbound to a
            specific media item (e.g. manual grab or freeleech sweep).
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"c411"``).
        category: Category ID string (``None`` if unknown at grab time).
        tags: Ordered tuple of tracker-assigned tags.
    """

    media_ref: MediaRef | None
    info_hash: str
    source_tracker: str
    category: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class GrabFailed(Event):
    """A torrent grab attempt failed.

    Emitted by RP5b on any grab failure (network, parse, no results, etc.).

    Attributes:
        media_ref: Provider-ID key; ``None`` when unbound to a specific item.
        source_tracker: Tracker name; ``None`` when failure is pre-selection.
        reason: Human-readable failure reason.
    """

    media_ref: MediaRef | None
    source_tracker: str | None
    reason: str


@dataclass(frozen=True, kw_only=True)
class GrabReswitched(Event):
    """A grabbed release was declared dead-stalled and switched for another.

    Emitted by :func:`personalscraper.acquire._reswitch.reswitch_stalled` when a
    grabbed torrent is classified ``STALLED_DEAD`` (dead swarm / broken payload /
    stuck past the deadline): the dead torrent is removed from the client, the
    item is requeued with the failed hash remembered (so the next search excludes
    it), and the next grab picks a DIFFERENT release. Never a silent state — the
    operator sees WHY an « en cours d'acquisition » item went back to searching
    (product-intent §2 / §méthode).

    Attributes:
        media_ref: Provider-ID key of the item being reswitched.
        old_hash: The dead release's info-hash (now recorded in ``tried_hashes``).
        reason: Why it was declared dead — a short machine-stable token
            (``dead_swarm`` / ``broken`` / ``deadline``).
    """

    media_ref: MediaRef
    old_hash: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class SeedObligationRecorded(Event):
    """A seed obligation was created when a dispatched payload is registered.

    Emitted by the dispatch step / O2 when a new ``SeedObligation`` row is
    inserted (e.g. after a successful real dispatch with ``action != "dry_run"``).

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"c411"``).
        min_seed_time_s: Minimum seed time in seconds (snapshot from economy config).
        dispatched_path: Absolute path of the dispatched media; ``None`` until move.
    """

    info_hash: str
    source_tracker: str
    min_seed_time_s: int
    dispatched_path: str | None


@dataclass(frozen=True, kw_only=True)
class SeedObligationBreached(Event):
    """A seed obligation was breached (seeding stopped before min_seed_time).

    Emitted by O2 when ``acquire.hnr_risk`` structlog warning would fire
    today (this event is the typed equivalent that supervisors subscribe to).

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"c411"``).
        dispatched_path: Absolute path of the dispatched media; ``None`` if unset.
    """

    info_hash: str
    source_tracker: str
    dispatched_path: str | None


@dataclass(frozen=True, kw_only=True)
class SeedObligationSatisfied(Event):
    """A seed obligation was satisfied (seeding completed successfully).

    Emitted by O2 when the obligation's min_seed_time_s has elapsed.

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name (e.g. ``"c411"``).
    """

    info_hash: str
    source_tracker: str


@dataclass(frozen=True, kw_only=True)
class RatioMeasured(Event):
    """A tracker ratio measurement was recorded.

    Emitted by Ratio C1 after each ratio poll cycle.

    Attributes:
        tracker: Tracker identifier string (e.g. ``"c411"``).
        observed_ratio: Latest measured upload/download ratio.
        target_ratio: Configured minimum ratio threshold.
    """

    tracker: str
    observed_ratio: float
    target_ratio: float


@dataclass(frozen=True, kw_only=True)
class TrackerAuthFailed(Event):
    """A tracker rejected the grab with an auth error (HTTP 401/403).

    Emitted by the acquisition orchestrator's ``except TrackerAuthError``
    branch when a ``.torrent`` download fails because the tracker credential
    (apikey/passkey/token) is broken. The item is abandoned (a broken
    credential will not self-heal by retrying the same item); this event is
    the operator-routable signal that the credential needs fixing.

    Attributes:
        tracker: Provider wire name the grab targeted (``top.provider``,
            lowercase).
        http_status: The rejecting HTTP status (401 or 403).
        media_ref: The desired item that could not be grabbed.
    """

    tracker: str
    http_status: int
    media_ref: MediaRef


@dataclass(frozen=True, kw_only=True)
class WatcherRunTriggered(Event):
    """Emitted when the Watcher daemon triggers a pipeline run.

    Emitted by ``personalscraper run --trigger-reason <reason>`` before
    ``PipelineStarted``. The reason is set by the watcher loop.

    Attributes:
        reason: Why the run was triggered — ``"completion"``,
            ``"safety_net"``, or ``"manual"`` (watch-now sentinel).
    """

    reason: str


@dataclass(frozen=True, kw_only=True)
class CrossSeedInjected(Event):
    """Emitted when a cross-seed torrent is successfully injected + verified.

    Emitted by :class:`~personalscraper.acquire.cross_seed.CrossSeedService`
    after the obligation record is persisted (emit-after-persist convention).

    Attributes:
        info_hash: The info-hash of the injected torrent.
        source_tracker: The tracker the ``.torrent`` was fetched from (target).
        source_hash: The info-hash of the original (source) torrent.
        save_path: Absolute path to the data directory used as save path.
    """

    info_hash: str
    source_tracker: str
    source_hash: str
    save_path: str


@dataclass(frozen=True, kw_only=True)
class CrossSeedRejected(Event):
    """Emitted when a cross-seed candidate is rejected before injection.

    Emitted by :class:`~personalscraper.acquire.cross_seed.CrossSeedService`
    at each rejection point — fetch failure, magnet, parse error, structural
    mismatch, or recheck failure.

    Attributes:
        info_hash: The info-hash of the CANDIDATE ``.torrent`` (not the
            source). When the candidate carries no hash, this is the
            download URL or ``"unknown"``.
        tracker: The tracker the candidate was fetched from.
        reason: Closed-set rejection reason:
            ``"fetch_failed"``
                Transport/auth/circuit error during candidate download.
            ``"magnet_not_supported"``
                Candidate resolved to a magnet link (no ``.torrent`` bytes).
            ``"parse_failed"``
                Candidate ``.torrent`` bytes failed bencode parsing.
            ``"inject_failed"``
                Injection failed — the candidate's info-hash could not be
                computed (:class:`ValueError` from bencode) or the torrent
                client rejected the injection (:class:`ApiError`).
            ``"self_candidate"``
                Candidate ``info_hash`` equals the source ``info_hash``
                (same-release cross-post, or origin-unresolvable loop).
            ``"piece_length_mismatch"``
                ``structural_match``: ``piece_length`` differs.
            ``"file_list_mismatch"``
                ``structural_match``: file count or name/size list differs.
            ``"root_name_mismatch"``
                ``structural_match``: ``info.name`` differs.
            ``"v2_hybrid"``
                ``structural_match``: candidate is v2/hybrid (non-v1).
            ``"obligation_write_failed"``
                Seed obligation persist failed — injection deleted.
            ``"verify_timeout"``
                Recheck verification deadline passed without progress ≥ 1.0.
            ``"recheck_failed"``
                **Reserved** — recheck finished but progress < 1.0 (not
                reachable with the current progress-only poll).
        source_hash: The info-hash of the source torrent that triggered the
            cross-seed attempt.
    """

    info_hash: str
    tracker: str
    reason: str
    source_hash: str


@dataclass(frozen=True, kw_only=True)
class DownloadStarted(Event):
    """A wanted item's torrent was first observed downloading in the client.

    Emitted by the reconcile sweep (O4) when a hash-carrying OPEN wanted row
    is first observed in the torrent client with ``progress < 1.0``. Fires at
    most once per info-hash — the ``download_marks`` table persists the mark
    BEFORE the emit (exactly-once, emit-after-persist convention).

    Attributes:
        info_hash: Torrent info-hash (hex string).
        title: Human-readable title of the wanted item (for the feed/toast).
        provider: Tracker wire name the release was grabbed from
            (e.g. ``"c411"``, lowercase), snapshot from the wanted row.
        kind: Wanted kind — ``"movie"``, ``"episode"`` or ``"season"``.
    """

    info_hash: str
    title: str
    provider: str
    kind: str


@dataclass(frozen=True, kw_only=True)
class DownloadProgressed(Event):
    """A downloading torrent crossed a 25/50/75 % progress threshold.

    Emitted by the reconcile sweep (O4) when the observed progress crosses a
    milestone. Only the HIGHEST threshold crossed per reconcile pass fires
    (D8 anti-spam): a 0 → 0.60 jump emits ONE event with ``threshold_pct=50``,
    never two. Progress regressions (e.g. a qBittorrent recheck dropping
    0.80 → 0.20) never re-emit lower thresholds — the persisted
    ``last_threshold`` mark only moves forward.

    Attributes:
        info_hash: Torrent info-hash (hex string).
        title: Human-readable title of the wanted item (for the feed/toast).
        progress: Observed completion ratio at emission time (``0.0``–``1.0``).
        threshold_pct: The milestone crossed — ``25``, ``50`` or ``75``.
    """

    info_hash: str
    title: str
    progress: float
    threshold_pct: int


@dataclass(frozen=True, kw_only=True)
class DownloadCompleted(Event):
    """A wanted item's torrent was first observed fully downloaded.

    Emitted by the reconcile sweep (O4) on the first observation with
    ``progress >= 1.0``. A torrent already complete on its first sighting
    emits ONLY this event — no synthetic ``DownloadStarted`` /
    ``DownloadProgressed`` backfill (events are observations, not history).

    Attributes:
        info_hash: Torrent info-hash (hex string).
        title: Human-readable title of the wanted item (for the feed/toast).
        provider: Tracker wire name the release was grabbed from
            (e.g. ``"c411"``, lowercase), snapshot from the wanted row.
        kind: Wanted kind — ``"movie"``, ``"episode"`` or ``"season"``.
    """

    info_hash: str
    title: str
    provider: str
    kind: str


__all__ = [
    "CrossSeedInjected",
    "CrossSeedRejected",
    "DownloadCompleted",
    "DownloadProgressed",
    "DownloadStarted",
    "FilmAcquired",
    "GrabFailed",
    "GrabSucceeded",
    "RatioMeasured",
    "SeasonAbsorbedEpisodes",
    "SeasonEscalatedAfterEpisodeFailures",
    "SeasonFellBackToEpisodes",
    "SeedObligationBreached",
    "SeedObligationRecorded",
    "SeedObligationSatisfied",
    "SeriesFollowed",
    "SeriesUnfollowed",
    "TrackerAuthFailed",
    "WantedAbandoned",
    "WantedEnqueued",
    "WatcherRunTriggered",
]
