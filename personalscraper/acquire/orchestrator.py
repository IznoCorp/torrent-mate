"""Grab orchestrator — search pass + grab pass (acq-states phase 2).

``GrabOrchestrator.search(item, profile)`` runs the search→filter→rank chain
and returns a :class:`SearchVerdict` — a pure verdict with NO side effects
(no torrent-client use, no add, no event emit). The :meth:`grab` method
re-uses the same chain then proceeds to resolve_source + add + event emission.

The split (DESIGN §3.3–§3.4) is the heart of the acq-states feature: before it,
« À récupérer » existed for milliseconds inside a single function call and the
operator could never see what was available but not yet taken.

Shared chain: :meth:`_search_chain` runs query build → search_candidates →
filter_to_episode → apply_hard_filters → dedup → rank and returns a
:class:`_SearchChainResult` both public methods consume.

It does **not** touch the store or the wanted state machine — the
``AcquisitionService`` (phase 4b) owns the atomic claim, the status
transitions and ``mark_grabbed``. The orchestrator returns typed dispositions
the service maps onto statuses.

Emission asymmetry (DESIGN §15 / §11(d)): the orchestrator emits the FAILURE
events (``GrabFailed`` / ``WantedAbandoned``) itself but NOT ``GrabSucceeded``.
Success is special — the torrent ``add()`` is an irreversible external
side-effect that precedes persistence, so emitting before ``mark_grabbed`` left
a double-emit window (a ``mark_grabbed`` crash kept the row 'searching', and
stale-recovery re-grabbed (idempotent ``add``) then emitted a SECOND
``GrabSucceeded``). The orchestrator therefore carries the success payload on
``GrabOutcome`` (``info_hash`` / ``category`` / ``tags``) and the SERVICE emits
``GrabSucceeded`` only AFTER ``mark_grabbed`` persists — exactly-once.

Failure routing is a first-class taxonomy (DESIGN §6.2), not a flat
``GrabFailed``:

- **RETRYABLE** → ``GrabFailed(reason)``, ``disposition="retryable"`` (the
  service resets ``searching → pending``, item retried next run).
- **TERMINAL**  → ``WantedAbandoned(reason)``, ``disposition="terminal"`` (the
  service sets ``searching → abandoned`` — won't self-heal).
- **Success**   → ``disposition="success"`` (the service emits
  ``GrabSucceeded`` after persisting — DESIGN §15 / §11(d)).

``CircuitOpenError`` is a *sibling* of ``ApiError`` (NOT a subclass — see
``core/_contracts.py``), so it is caught in a SEPARATE ``except`` clause. A
bare ``except ApiError`` would miss it and crash the whole batch.

NEGATIVE invariant (DESIGN §9, load-bearing): the orchestrator NEVER writes a
seed obligation (``record_dispatch`` / ``seed.add``) at grab time — it has no
store/seed dependency at all. Seed obligations are a dispatch-time concern.

Dep injection: narrow constructor (NOT ``AppContext`` — boundary rule). The
orchestrator holds the ``TrackerRegistry`` and resolves transports FRESH at
grab time (``tracker_registry.transports()``), NOT from a boot snapshot. This
matters for a lazy tracker (torr9's TVDB-lazy ``_transport`` property logs in on
first access): by grab time it has already logged in during that same grab's
``search()`` (search precedes resolve in the chain), so its authed transport is
present — and a transient boot-time login blip can no longer strand it in a
stale snapshot for the process lifetime.

Import direction: ``acquire/`` imports ``api/`` / ``core/`` / ``conf/`` /
``events/`` downward only — never the triage packages (layering guard).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from personalscraper.acquire._dedup import SearchOutcome, dedup
from personalscraper.acquire._filters import apply_hard_filters
from personalscraper.acquire.events import GrabFailed, TrackerAuthFailed, WantedAbandoned
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.torrent._contracts import TorrentTagger
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.api.tracker._fetch import resolve_source
from personalscraper.api.tracker._ranking import rank
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.acquire.desired import QualityProfile
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.api.torrent._contracts import TorrentAdder
    from personalscraper.api.tracker._base import TrackerResult
    from personalscraper.api.tracker._ranking import RankingConfig
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.identity import MediaRef

log = get_logger("acquire.orchestrator")

#: Named outcomes a search pass can conclude with. The service's status mapping
#: must cover EXACTLY this set (set-equality test) — a new outcome added here
#: without a service mapping fails the exhaustiveness test.
SEARCH_OUTCOMES: frozenset[str] = frozenset(
    {
        "available",
        "no_candidates",
        "no_matching_episode",
        "all_filtered",
        "trackers_unavailable",
        "circuit_open",
        "search_api_error",
        "no_seeders",
        "tracker_auth",
    }
)

#: Outcomes meaning « the search did NOT conclude » — outage/circuit/dead swarm.
#: Reporting these as « En attente » would claim knowledge we do not have.
INCONCLUSIVE_OUTCOMES: frozenset[str] = frozenset(
    {
        "trackers_unavailable",
        "circuit_open",
        "search_api_error",
        "no_seeders",
    }
)


@dataclass(frozen=True)
class _SearchChainResult:
    """Intermediate of the shared search→filter→rank pipeline.

    Produced by :meth:`GrabOrchestrator._search_chain` and consumed by both
    :meth:`search` (→ :class:`SearchVerdict`) and :meth:`grab` (→
    :class:`GrabOutcome`).  Encodes the exit path so the two callers can map
    it onto their respective outcome types without duplicating the chain
    logic.

    Attributes:
        exit_path: Named outcome — one of the :data:`SEARCH_OUTCOMES` values.
        ranked: Ranked candidates (empty on every path except ``"available"``).
        top: Top-ranked candidate, or ``None`` when no candidate survived.
    """

    exit_path: str
    ranked: list[tuple[TrackerResult, float]]
    top: tuple[TrackerResult, float] | None


@dataclass(frozen=True)
class SearchVerdict:
    """Verdict of one search pass for one wanted item (no side effects).

    Returned by :meth:`GrabOrchestrator.search`.  The orchestrator never
    touches the torrent client, never emits events, and never writes to the
    store on this path — the verdict is a pure data object the service maps
    onto a wanted status via :func:`personalscraper.acquire.service.SEARCH_OUTCOME_STATUS`.

    Attributes:
        disposition: High-level bucket the service uses for summary counting.
        outcome: Named outcome — a member of :data:`SEARCH_OUTCOMES`.
        found: Number of takeable candidates that survived every filter,
            including the ``min_seeders`` floor.  ``None`` when the search
            did NOT conclude (outage / circuit open / dead swarm): zero would
            falsely claim « I looked, there is nothing » (panne ≠ absence).
        chosen: The top-ranked candidate, for logging only — the grab pass
            re-searches rather than re-using a stored reference.
    """

    disposition: Literal["available", "not_found", "retryable", "terminal"]
    outcome: str  # member of SEARCH_OUTCOMES
    found: int | None  # takeable count; None = not concluded (NEVER 0 on outage)
    chosen: TrackerResult | None = None  # top-ranked candidate, for logging only


def build_search_query(item: "WantedItem", title: str | None) -> str:
    """Build a tracker search query from a wanted item + resolved series title.

    This is the Follow D3 title-resolution seam. When the series ``title`` is
    known (resolved from the followed-series row), an episode query becomes
    ``"{title} SxxEyy"`` and a movie query becomes ``"{title}"`` — the form the
    title-based trackers (c411, torr9) actually match. When ``title`` is
    ``None`` (standalone item with no followed row, or a resolver miss), it
    falls back to the primary provider ID string — the legacy behavior, which
    finds nothing on title-based trackers but keeps the query non-empty.

    Args:
        item: The claimed wanted item (carries ``kind`` + ``season`` +
            ``episode`` + ``media_ref``).
        title: The resolved series/movie title, or ``None``.

    Returns:
        A non-empty query string.
    """
    if title:
        if item.kind == "episode" and item.season is not None and item.episode is not None:
            return f"{title} S{item.season:02d}E{item.episode:02d}"
        return title
    media_ref = item.media_ref
    if media_ref.tvdb_id is not None:
        return str(media_ref.tvdb_id)
    if media_ref.tmdb_id is not None:
        return str(media_ref.tmdb_id)
    return str(media_ref.imdb_id)


def filter_to_episode(
    results: "list[TrackerResult]",
    season: int,
    episode: int,
) -> "list[TrackerResult]":
    """Keep only results whose title carries the exact ``SxxEyy`` token.

    A title-based query (``"{title} SxxEyy"``) returns fuzzy matches — other
    episodes of the season, season packs — because trackers match loosely. Left
    unfiltered they rank by seeders, so the wrong episode can win (observed:
    ``S09E05`` wanted → an ``S09E01`` release ranked top). This keeps only
    releases naming the requested episode, tolerating zero-padding (``S9E5`` /
    ``S09E05``) and multi-episode spans (``S09E05-E06`` / ``S09E05E06`` still
    match E05). Season packs (no ``E`` token) are intentionally dropped — an
    exact-episode want should not pull a whole season.

    Args:
        results: The raw tracker results for the query.
        season: Wanted season number.
        episode: Wanted episode number.

    Returns:
        The subset whose title names the exact episode (possibly empty).
    """
    # (?<![0-9]) / (?![0-9]) bound the numbers so E5 does not match E51 and
    # S9 does not match S19; 0* absorbs the zero-padding difference.
    pattern = re.compile(rf"(?<![0-9])s0*{season}e0*{episode}(?![0-9])", re.IGNORECASE)
    return [r for r in results if pattern.search(r.title)]


@dataclass(frozen=True, kw_only=True)
class GrabOutcome:
    """Result of one :meth:`GrabOrchestrator.grab` call.

    The orchestrator is store-agnostic: it returns this typed disposition and
    the ``AcquisitionService`` (phase 4b) maps it onto a wanted status —
    ``"success"`` → grabbed, ``"retryable"`` → pending, ``"terminal"`` →
    abandoned. The orchestrator never writes a status itself.

    Emission asymmetry (DESIGN §15 / §11(d)): the orchestrator emits
    ``GrabFailed`` / ``WantedAbandoned`` on the failure paths itself (no
    external side-effect precedes them, so there is no persist-then-crash
    window). ``GrabSucceeded`` is the exception — the orchestrator does NOT
    emit it; it carries the payload fields (``info_hash`` / ``category`` /
    ``tags``) on this outcome and the service emits ``GrabSucceeded`` only
    AFTER ``mark_grabbed`` persists. Success is special because the torrent
    ``add()`` is an irreversible external side-effect that precedes
    persistence; deferring the emit closes the §11(d) double-emit window.

    Attributes:
        disposition: ``"success"`` (torrent added — the service emits
            ``GrabSucceeded`` after persisting), ``"retryable"`` (transient
            failure — orchestrator already emitted ``GrabFailed``, retry next
            run and counts toward the attempts cap), ``"not_found"`` (clean
            search but nothing usable on the trackers yet — retry under
            cadence pacing WITHOUT counting toward the attempts cap; only the
            cutoff ages it out), or ``"terminal"`` (permanent — orchestrator
            already emitted ``WantedAbandoned``).
        info_hash: Torrent info-hash on success, otherwise ``None``.
        reason: Machine-readable failure/abandonment reason, ``None`` on success.
        chosen: The ranked top :class:`TrackerResult` that was acted on, or
            ``None`` when the chain failed before a candidate was picked.
        category: Category passed to ``add()`` (carried for the service's
            ``GrabSucceeded`` payload). ``None`` off the success path.
        tags: Tags passed to ``add()`` (carried for the service's
            ``GrabSucceeded`` payload). Empty off the success path.
    """

    disposition: Literal["success", "retryable", "not_found", "terminal"]
    info_hash: str | None = None
    reason: str | None = None
    chosen: TrackerResult | None = None
    category: str | None = None
    tags: tuple[str, ...] = ()


class GrabOrchestrator:
    """Single-item grab chain (DESIGN §1) — narrow deps, no AppContext.

    Executes profile → search → hard-filter → dedup → rank → resolve_source →
    add → emit for ONE ``WantedItem`` and returns a :class:`GrabOutcome`. The
    wanted state machine (claim / status transitions / ``mark_grabbed``) is the
    ``AcquisitionService``'s concern (phase 4b) — this class only reads the
    item and fires exactly one event.

    Attributes:
        _tracker_registry: Multi-tracker search coordinator
            (``search_candidates``). Also the source of the per-grab transport
            map: ``resolve_source`` reads ``tracker_registry.transports()``
            FRESH at grab time rather than a boot snapshot, so a lazy tracker
            that logs in during the same grab's search is present.
        _torrent_client: Active :class:`TorrentAdder`, or ``None`` when no
            torrent client is configured (search-only / dry-run) — a ``None``
            client routes to a RETRYABLE ``no_torrent_client`` rather than a
            crash.
        _event_bus: In-process event bus (fire-and-forget).
        _ranking: Ranking configuration for the soft-score sort.
    """

    def __init__(
        self,
        *,
        tracker_registry: TrackerRegistry,
        torrent_client: TorrentAdder | None,
        event_bus: EventBus,
        ranking: RankingConfig,
        title_resolver: Callable[[WantedItem], str | None] | None = None,
    ) -> None:
        """Initialise the orchestrator with injected narrow deps.

        No transport snapshot is taken at construction: ``resolve_source`` reads
        ``tracker_registry.transports()`` FRESH at grab time (see
        :meth:`grab`), so a lazy tracker that materializes its authed transport
        during the grab's own ``search()`` is present, and a transient boot
        login blip can't leave a stale snapshot for the process lifetime.

        Args:
            tracker_registry: Multi-tracker search coordinator; also the source
                of the per-grab transport map (read fresh in :meth:`grab`).
            torrent_client: Torrent add capability, or ``None`` (search-only).
            event_bus: In-process event bus.
            ranking: Ranking configuration applied after dedup.
            title_resolver: Follow D3 seam — resolves a claimed
                ``WantedItem`` to its series/movie title (from the followed-series
                row) so the tracker query is ``"{title} SxxEyy"`` rather than the
                bare provider ID. ``None`` (or a resolver miss) falls back to the
                ID query (legacy behavior). See :func:`build_search_query`.
        """
        self._tracker_registry = tracker_registry
        self._torrent_client = torrent_client
        self._event_bus = event_bus
        self._ranking = ranking
        self._title_resolver = title_resolver

    # ------------------------------------------------------------------
    # Shared search→filter→rank chain
    # ------------------------------------------------------------------

    def _search_chain(self, item: WantedItem, profile: QualityProfile) -> _SearchChainResult:
        """Run the shared search→filter→rank pipeline and return the exit path.

        Both :meth:`search` and :meth:`grab` call this private method.  It
        executes the full chain — query build → search_candidates →
        filter_to_episode → apply_hard_filters → dedup → rank — catches
        operational exceptions, and encodes the result as a
        :class:`_SearchChainResult` whose ``exit_path`` the two callers map
        onto their respective outcome types.

        The torrent client is never touched and no events are emitted here.
        The :exc:`ApiError` catch subsumes :exc:`TrackerAuthError` and
        :exc:`TorrentFetchError` (both subclasses), preserving :meth:`grab`'s
        historical mapping of search-time API errors to the retryable
        ``search_api_error`` bucket.  :exc:`CircuitOpenError` is caught
        separately because it is a sibling of :exc:`ApiError`
        (``core/_contracts.py``).

        Args:
            item: The claimed ``WantedItem`` to search for.
            profile: The effective :class:`QualityProfile` for the hard-filter
                stage.

        Returns:
            A :class:`_SearchChainResult` whose ``exit_path`` is one of the
            :data:`SEARCH_OUTCOMES` values.
        """
        media_ref = item.media_ref
        media_type = MediaType.TV if item.kind == "episode" else MediaType.MOVIE
        title = self._title_resolver(item) if self._title_resolver is not None else None
        query = build_search_query(item, title)
        year: int | None = None

        # --- Search (CircuitOpenError is NOT an ApiError → catch separately) ---
        try:
            outcome: SearchOutcome = self._tracker_registry.search_candidates(query, media_type, year)
        except CircuitOpenError:
            return _SearchChainResult(exit_path="circuit_open", ranked=[], top=None)
        except ApiError:
            return _SearchChainResult(exit_path="search_api_error", ranked=[], top=None)

        if outcome.all_errored:
            return _SearchChainResult(exit_path="trackers_unavailable", ranked=[], top=None)
        if not outcome.results:
            return _SearchChainResult(exit_path="no_candidates", ranked=[], top=None)

        # --- Episode-exactness (BEFORE hard-filter): the title query returns
        # fuzzy matches (other episodes, season packs); keep only releases
        # naming the wanted SxxEyy so ranking cannot pick the wrong episode. ---
        results = outcome.results
        if item.kind == "episode" and item.season is not None and item.episode is not None:
            results = filter_to_episode(results, item.season, item.episode)
            if not results:
                return _SearchChainResult(exit_path="no_matching_episode", ranked=[], top=None)

        # --- Hard-filter (BEFORE dedup — DESIGN §15 stage order) ---
        survivors = apply_hard_filters(results, profile, media_ref)
        if not survivors:
            return _SearchChainResult(exit_path="all_filtered", ranked=[], top=None)

        # --- Dedup → rank ---
        representatives = dedup(survivors)
        ranked = rank(representatives, self._ranking)
        if not ranked:
            return _SearchChainResult(exit_path="no_seeders", ranked=[], top=None)

        return _SearchChainResult(exit_path="available", ranked=ranked, top=ranked[0])

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search(self, item: WantedItem, profile: QualityProfile) -> SearchVerdict:
        """State availability for one wanted item — NEVER downloads.

        Runs the full search→filter→rank chain and returns a pure
        :class:`SearchVerdict`.  This method has **no side effects**: it
        never touches the torrent client, never emits events (logging only),
        and never writes to the store.  The verdict is a data object the
        service maps onto a wanted status.

        Exit mapping (exhaustive — every path returns a verdict):

        ============================= =============== ===================== =====
        Condition                      Disposition     Outcome               Found
        ============================= =============== ===================== =====
        ``CircuitOpenError``           ``retryable``   ``circuit_open``      None
        ``ApiError``                   ``retryable``   ``search_api_error``  None
        ``all_errored``                ``retryable``   ``trackers_unavail.`` None
        No results                     ``not_found``   ``no_candidates``     0
        ``filter_to_episode`` empty    ``not_found``   ``no_matching_ep.``   0
        ``apply_hard_filters`` empty   ``not_found``   ``all_filtered``      0
        ``rank`` empty (min_seeders)   ``retryable``   ``no_seeders``        None
        Ranked non-empty               ``available``   ``available``         len(ranked)
        ============================= =============== ===================== =====

        Args:
            item: The wanted item to search for (read-only).
            profile: The effective :class:`QualityProfile` for the hard-filter
                stage.

        Returns:
            A :class:`SearchVerdict` describing availability.
        """
        result = self._search_chain(item, profile)

        mapping: dict[str, tuple[str, str, int | None]] = {
            "circuit_open": ("retryable", "circuit_open", None),
            "search_api_error": ("retryable", "search_api_error", None),
            "trackers_unavailable": ("retryable", "trackers_unavailable", None),
            "no_candidates": ("not_found", "no_candidates", 0),
            "no_matching_episode": ("not_found", "no_matching_episode", 0),
            "all_filtered": ("not_found", "all_filtered", 0),
            "no_seeders": ("retryable", "no_seeders", None),
            "available": ("available", "available", len(result.ranked)),
        }
        disposition, outcome, found = mapping[result.exit_path]

        chosen = result.top[0] if result.top is not None else None
        log.debug(
            "acquire.search.verdict",
            disposition=disposition,
            outcome=outcome,
            found=found,
            kind=item.kind,
        )
        return SearchVerdict(disposition=disposition, outcome=outcome, found=found, chosen=chosen)

    def grab(self, item: WantedItem, profile: QualityProfile) -> GrabOutcome:
        """Execute the full grab chain for one claimed ``WantedItem``.

        The item is assumed already claimed (``status='searching'``) by the
        service. This method performs NO store writes — it returns a
        :class:`GrabOutcome` whose ``disposition`` the service maps onto a
        status. On a FAILURE path it emits exactly one event (``GrabFailed`` /
        ``WantedAbandoned``); on SUCCESS it emits nothing and instead carries
        the ``GrabSucceeded`` payload on the outcome — the service emits
        ``GrabSucceeded`` after ``mark_grabbed`` persists (DESIGN §15 /
        §11(d), emit-after-persist).

        The search→filter→rank chain is delegated to :meth:`_search_chain`;
        this method adds the grab-only stages (resolve_source → add → event
        emission) on top.

        Failure routing (DESIGN §6.2), in catch order — ``CircuitOpenError``
        is a sibling of ``ApiError`` (caught FIRST and SEPARATELY, else a bare
        ``except ApiError`` misses it and crashes the batch):

        - ``CircuitOpenError`` → RETRYABLE ``circuit_open``.
        - ``TrackerAuthError`` (401/403, passkey broken) → TERMINAL
          ``tracker_auth``.
        - ``TorrentFetchError`` → RETRYABLE ``fetch_failed``.
        - other ``ApiError`` (add failure / transient) → RETRYABLE
          ``add_failed``.

        Args:
            item: The claimed ``WantedItem`` to grab (read-only here).
            profile: The effective :class:`QualityProfile` for the hard-filter
                stage (resolved by the service before dispatch).

        Returns:
            The :class:`GrabOutcome` describing success / retryable / terminal.
        """
        media_ref = item.media_ref

        # --- Shared search→filter→rank chain ---
        result = self._search_chain(item, profile)

        # Map each exit path to the same disposition + event the inline chain
        # produced before the extraction (outcome.reason strings unchanged).
        if result.exit_path == "circuit_open":
            return self._retryable(media_ref, "circuit_open")
        if result.exit_path == "search_api_error":
            return self._retryable(media_ref, "search_api_error")
        if result.exit_path == "trackers_unavailable":
            return self._retryable(media_ref, "trackers_unavailable")
        if result.exit_path == "no_candidates":
            return self._not_found(media_ref, "no_candidates")
        if result.exit_path == "no_matching_episode":
            return self._not_found(media_ref, "no_matching_episode")
        if result.exit_path == "all_filtered":
            return self._not_found(media_ref, "all_filtered")
        if result.exit_path == "no_seeders":
            return self._retryable(media_ref, "no_seeders")

        # --- Available: proceed to the grab-only stages ---
        top, _score = result.top  # guaranteed non-None on "available"

        # --- No torrent client → cannot add (search-only / dry-run). RETRYABLE. ---
        if self._torrent_client is None:
            return self._retryable(media_ref, "no_torrent_client", chosen=top)

        # --- Resolve source then add (taxonomy: §6.2 catch order) ---
        # category stays None — Transmission uses labels[0] for category, so
        # passing tags=(...) alongside would clobber it; tags are applied via
        # a separate add_tags() call on clients that implement TorrentTagger.
        category: str | None = None
        try:
            # Read transports FRESH (not a boot snapshot): by here the top
            # result's tracker has already run its search() in THIS grab, so a
            # lazy tracker (torr9) has materialized + cached its authed
            # transport. transports() is cheap (cached transports;
            # plain-attribute for lacale/c411). A transient boot login blip can
            # no longer strand a recovered tracker behind a stale snapshot.
            source = resolve_source(top, self._tracker_registry.transports())
            info_hash = self._torrent_client.add(source, category=category)
            if isinstance(self._torrent_client, TorrentTagger):
                try:
                    self._torrent_client.add_tags(info_hash, [top.provider])
                except ApiError as exc:
                    # Tagging is best-effort: the torrent is already added.
                    # Log a warning and continue — do NOT surface as add_failed.
                    log.warning(
                        "acquire.grab.tag_failed",
                        hash=info_hash,
                        provider=top.provider,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
        except CircuitOpenError:
            # Sibling of ApiError — MUST precede the ApiError clause.
            return self._retryable(media_ref, "circuit_open", chosen=top)
        except TrackerAuthError as exc:
            # 401/403: passkey/config broken — won't self-heal → abandon.
            # Emit the operator-routable signal BEFORE abandoning (follows the
            # orchestrator's self-emit-on-failure convention; correlation_id
            # propagates via the Event base ContextVar).
            self._event_bus.emit(
                TrackerAuthFailed(
                    tracker=top.provider,
                    http_status=exc.http_status,
                    media_ref=media_ref,
                )
            )
            return self._terminal(media_ref, "tracker_auth", chosen=top)
        except TorrentFetchError:
            # Download/validation failure — transient, retry next run.
            return self._retryable(media_ref, "fetch_failed", chosen=top)
        except ApiError:
            # Any other add/transport failure (incl. idempotent Conflict that a
            # client surfaces as the existing hash on return, not a raise).
            return self._retryable(media_ref, "add_failed", chosen=top)

        # --- Success: return the outcome; the SERVICE emits GrabSucceeded
        # AFTER a successful mark_grabbed (emit-after-persist — DESIGN §15 /
        # §11(d)). The orchestrator does NOT emit here: emitting before the
        # status write opened a double-emit window — a mark_grabbed crash left
        # the row 'searching', and stale-recovery re-grabbed (idempotent add)
        # then emitted a SECOND GrabSucceeded. By deferring the emit to follow
        # persistence, a mark_grabbed crash means NO emit happened and the
        # single re-grab emits exactly once. (NO seed write — DESIGN §9.)
        log.info(
            "acquire.grab.succeeded",
            info_hash=info_hash,
            provider=top.provider,
            kind=item.kind,
        )
        return GrabOutcome(
            disposition="success",
            info_hash=info_hash,
            chosen=top,
            category=category,
            tags=(top.provider,),
        )

    def _retryable(
        self,
        media_ref: MediaRef | None,
        reason: str,
        *,
        chosen: TrackerResult | None = None,
    ) -> GrabOutcome:
        """Emit ``GrabFailed`` and return a RETRYABLE outcome (DESIGN §6.2).

        Args:
            media_ref: The item's provider-ID key (carried into the event).
            reason: Machine-readable failure reason.
            chosen: The ranked top result, if one was picked before failing.

        Returns:
            A :class:`GrabOutcome` with ``disposition="retryable"``.
        """
        source_tracker = chosen.provider if chosen is not None else None
        self._event_bus.emit(GrabFailed(media_ref=media_ref, source_tracker=source_tracker, reason=reason))
        log.warning("acquire.grab.retryable", reason=reason, source_tracker=source_tracker)
        return GrabOutcome(disposition="retryable", reason=reason, chosen=chosen)

    def _not_found(
        self,
        media_ref: MediaRef | None,
        reason: str,
    ) -> GrabOutcome:
        """Emit ``GrabFailed`` and return a NOT-FOUND outcome (B.4).

        A clean search that found nothing usable is not an abandonment: the
        release may simply not be on the trackers yet. The service keeps the
        row ``pending`` (cadence-paced, cutoff-bounded) and the cap does not
        apply — abandoning after one 03:20 search 20 minutes post-detect was
        the released-but-never-grabbed bug.

        Args:
            media_ref: The item's provider-ID key (carried into the event).
            reason: Machine-readable reason (``no_candidates`` /
                ``no_matching_episode`` / ``all_filtered``).

        Returns:
            A :class:`GrabOutcome` with ``disposition="not_found"``.
        """
        self._event_bus.emit(GrabFailed(media_ref=media_ref, source_tracker=None, reason=reason))
        log.info("acquire.grab.not_found", reason=reason)
        return GrabOutcome(disposition="not_found", reason=reason)

    def _terminal(
        self,
        media_ref: MediaRef | None,
        reason: str,
        *,
        chosen: TrackerResult | None = None,
    ) -> GrabOutcome:
        """Emit ``WantedAbandoned`` and return a TERMINAL outcome (DESIGN §6.2).

        Args:
            media_ref: The item's provider-ID key (carried into the event).
            reason: Machine-readable abandonment reason.
            chosen: The ranked top result, if one was picked before abandoning.

        Returns:
            A :class:`GrabOutcome` with ``disposition="terminal"``.
        """
        # WantedAbandoned.media_ref is non-optional; the orchestrator always has
        # one (every WantedItem carries a MediaRef), so the cast is safe.
        assert media_ref is not None  # noqa: S101 — every WantedItem has a MediaRef
        self._event_bus.emit(WantedAbandoned(media_ref=media_ref, reason=reason))
        log.warning("acquire.grab.terminal", reason=reason)
        return GrabOutcome(disposition="terminal", reason=reason, chosen=chosen)


__all__ = [
    "GrabOrchestrator",
    "GrabOutcome",
    "SearchVerdict",
    "SEARCH_OUTCOMES",
    "INCONCLUSIVE_OUTCOMES",
]
