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
matters for a login-style tracker whose ``_transport`` materializes lazily on
first access (none is wired today): by grab time it has already logged in during
that same grab's ``search()`` (search precedes resolve in the chain), so its
authed transport is present — and a transient boot-time login blip can no longer
strand it in a stale snapshot for the process lifetime.

Import direction: ``acquire/`` imports ``api/`` / ``core/`` / ``conf/`` /
``events/`` downward only — never the triage packages (layering guard).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from personalscraper.acquire._dedup import SearchOutcome, dedup
from personalscraper.acquire._filters import (
    apply_hard_filters,
    filter_to_episode,
    filter_to_movie,
    filter_to_season,
)
from personalscraper.acquire._query import build_search_query
from personalscraper.acquire._resolve_walk import resolve_first_available
from personalscraper.acquire.events import GrabFailed, TrackerAuthFailed, WantedAbandoned
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.torrent._base import TorrentLimits
from personalscraper.api.torrent._contracts import GlobalRateLimiter, TorrentLimiter
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
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
    from personalscraper.conf.models.acquire import BandwidthConfig
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
        "no_matching_season",
        "all_filtered",
        "trackers_unavailable",
        "trackers_degraded",
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
        "trackers_degraded",
        "circuit_open",
        "search_api_error",
        "no_seeders",
    }
)


def _all_errored_exit_path(outcome: SearchOutcome) -> str:
    """Name the verdict of a search where EVERY queried tracker failed (D4).

    Reads the per-tracker taxa the registry recorded. Only a UNANIMOUS failure
    mode earns a specific name — a mixed set is not a diagnosis, so it keeps the
    historical ``trackers_unavailable``.

    Args:
        outcome: The all-errored :class:`SearchOutcome`.

    Returns:
        ``"tracker_auth"`` (every tracker's key is broken — permanent),
        ``"circuit_open"`` (every breaker is open), else
        ``"trackers_unavailable"``.
    """
    taxa = set(outcome.errors.values())
    if taxa == {"auth"}:
        return "tracker_auth"
    if taxa == {"circuit"}:
        return "circuit_open"
    return "trackers_unavailable"


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
        ranked: Ranked ``(result, score)`` pairs as returned by
            :func:`personalscraper.api.tracker._ranking.rank` (integer scores).
            Empty on every path except ``"available"``.
        top: Top-ranked ``(result, score)`` pair, or ``None`` when no candidate
            survived.
    """

    exit_path: str
    ranked: list[tuple[TrackerResult, int]]
    top: tuple[TrackerResult, int] | None
    raw_before_filter: list[TrackerResult] | None = None


@dataclass(frozen=True)
class _QueryAttempt:
    """Outcome of ONE tracker query + kind-specific narrowing (#435).

    Produced by :meth:`GrabOrchestrator._query_and_narrow`; the three shapes
    and their retry semantics are documented on that method.

    Attributes:
        hard_stop: A verdict a retry must not overwrite (outage/auth/circuit/
            degraded), or ``None``.
        empty_verdict: The fully-healthy « nothing matched » verdict to state
            when no retry rescues the query, or ``None``.
        results: The narrowed candidates (possibly empty — for a movie whose
            identity filter dropped everything, both verdict fields are
            ``None`` and the empty list flows on to ``rank_candidates``).
    """

    hard_stop: "_SearchChainResult | None" = None
    empty_verdict: "_SearchChainResult | None" = None
    results: "list[TrackerResult]" = field(default_factory=list)


#: High-level bucket a search verdict falls into. Kept as a named alias so the
#: exit-path mapping table in :meth:`GrabOrchestrator.search` is typed against
#: the SAME literals as :attr:`SearchVerdict.disposition` (a typo in either
#: place is then a type error, not a runtime surprise).
SearchDisposition = Literal["available", "not_found", "retryable", "terminal"]


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

    disposition: SearchDisposition
    outcome: str  # member of SEARCH_OUTCOMES
    found: int | None  # takeable count; None = not concluded (NEVER 0 on outage)
    chosen: TrackerResult | None = None  # top-ranked candidate, for logging only
    raw_results: tuple[TrackerResult, ...] | None = None
    """Raw results before the per-kind filter, captured for R2 conversion.

    Populated when the search path reaches ``no_matching_episode`` —
    the raw results from the trackers carried season packs the episode
    filter dropped. ``None`` on every other path (the conversion path
    has no use for them).
    """


def rank_candidates(
    results: "list[TrackerResult]",
    profile: "QualityProfile",
    media_ref: "MediaRef | None",
    ranking: "RankingConfig",
    *,
    exclude_hashes: "frozenset[str]" = frozenset(),
    media_kind: "str | None" = None,
) -> "tuple[list[TrackerResult], list[tuple[TrackerResult, int]]]":
    """Run the hard-filter → dedup → rank tail of the grab chain (DESIGN §15).

    Shared by :meth:`GrabOrchestrator.grab` (the real acquisition path) and the
    ``grab --dry-run`` preview so both consume the SAME ranked result — F4: a
    preview that ranks differently from the run is a lie (a lying preview once
    surfaced a 3D SBS release as "top"), which the operator's dry-run-first rule
    exists to prevent. It returns BOTH intermediate lists so callers can
    distinguish the two empty cases the grab failure taxonomy separates:

    - empty ``representatives`` ⇒ every candidate failed the hard profile
      (``all_filtered``);
    - non-empty ``representatives`` but empty ``ranked`` ⇒ nothing met
      ``ranking.min_seeders`` (``no_seeders``).

    ``dedup([])`` is ``[]``, so ``not representatives`` is exactly
    ``not apply_hard_filters(...)`` — the orchestrator's original
    ``if not survivors`` guard is preserved bit-for-bit.

    Args:
        results: Candidate results from the search (already narrowed to the
            exact episode for TV items — see :func:`filter_to_episode`).
        profile: Effective quality profile for the hard-filter stage.
        media_ref: The wanted item's provider IDs (TMDB-identity filter seam);
            ``None`` for a manual CLI grab with no wanted item.
        ranking: Ranking configuration for the soft-score sort.
        exclude_hashes: Lowercase info-hashes to exclude from ranking — releases
            already grabbed-and-failed for this item (reswitch #342). Empty by
            default, so the ordinary grab and the dry-run preview are unchanged.
        media_kind: The wanted item's kind (``"movie"`` or ``"episode"``) for
            per-media-type size thresholds (#376). ``None`` (default) keeps the
            current byte-identical behaviour; passed by the orchestrator's
            ``_search_chain`` from the wanted item's ``.kind`` field.

    Returns:
        ``(representatives, ranked)`` — the deduped post-hard-filter survivors
        and the scored, sub-``min_seeders``-dropped, descending
        ``(result, score)`` list (highest score first).
    """
    survivors = apply_hard_filters(results, profile, media_ref)
    representatives = dedup(survivors)
    ranked = rank(representatives, ranking, exclude_hashes=exclude_hashes, media_kind=media_kind)
    return representatives, ranked


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
        found: Number of takeable candidates that survived the search→filter→rank
            chain. Populated with ``len(ranked)`` on the success path and ``0``
            on the ``not_found`` paths (the grab's own re-search concluded with
            nothing). ``None`` everywhere else (retryable/terminal — the search
            did not conclude).
    """

    disposition: Literal["success", "retryable", "not_found", "terminal"]
    info_hash: str | None = None
    reason: str | None = None
    chosen: TrackerResult | None = None
    category: str | None = None
    tags: tuple[str, ...] = ()
    found: int | None = None


def _build_limits(bw: "BandwidthConfig", *, client_is_limiter: bool) -> "TorrentLimits | None":
    """Build per-torrent limits from bandwidth config (O4).

    Returns ``None`` when no caps are configured or the client lacks
    :class:`TorrentLimiter` support — the caller handles the unsupported
    warning (D4: one-shot logging at the grab site).

    Args:
        bw: Bandwidth config carrying per-torrent caps.
        client_is_limiter: Whether the torrent client satisfies
            :class:`TorrentLimiter` (``isinstance`` check already done).

    Returns:
        A :class:`TorrentLimits` instance, or ``None``.
    """
    if bw.per_torrent_down is None and bw.per_torrent_up is None:
        return None
    if not client_is_limiter:
        return None
    return TorrentLimits(
        down_bytes_per_s=bw.per_torrent_down,
        up_bytes_per_s=bw.per_torrent_up,
    )


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
        _bandwidth: Per-torrent and global bandwidth caps (O4). Applied at
            :meth:`grab` add-time (per-torrent) and at run start (global).
        _limits_unsupported_warned: One-shot gate — set to ``True`` after
            the first ``limits_unsupported`` warning so the log is not
            flooded on every grab (D4).
    """

    def __init__(
        self,
        *,
        tracker_registry: TrackerRegistry,
        torrent_client: TorrentAdder | None,
        event_bus: EventBus,
        ranking: RankingConfig,
        title_resolver: Callable[[WantedItem], str | None] | None = None,
        year_resolver: "Callable[[WantedItem], int | None] | None" = None,
        original_title_resolver: "Callable[[WantedItem], str | None] | None" = None,
        episode_count_resolver: "Callable[[WantedItem], int | None] | None" = None,
        bandwidth: "BandwidthConfig",
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
            year_resolver: Resolves a claimed ``WantedItem`` to its release year
                (from the followed-series row) — disambiguates an ambiguous movie
                title (#28). ``None`` (or a miss) leaves the query yearless and
                the movie identity filter inert on the year axis.
            original_title_resolver: Resolves a claimed ``WantedItem`` to the
                movie's ORIGINAL-language title (from the followed-series row,
                #435) so the identity filter accepts releases named in the
                original language (« Avant d'aller dormir » vs
                `Before.I.Go.To.Sleep...`). ``None`` (or a miss) leaves the
                filter on the display title alone (pre-#435 behavior).
            episode_count_resolver: Resolves a claimed SEASON ``WantedItem`` to
                the number of aired episodes in its season (from the aired
                catalog cache) so ``filter_to_season`` can verify a pack's
                coverage (review F4). ``None`` (or a miss) makes the filter
                reject any episode-marker release conservatively.
            bandwidth: Per-torrent and global bandwidth caps for seed safety
                (O4). Carries per-torrent limits applied at add time and
                global limits re-asserted at run start.
        """
        self._tracker_registry = tracker_registry
        self._torrent_client = torrent_client
        self._event_bus = event_bus
        self._ranking = ranking
        self._title_resolver = title_resolver
        self._year_resolver = year_resolver
        self._original_title_resolver = original_title_resolver
        self._episode_count_resolver = episode_count_resolver
        self._bandwidth = bandwidth
        self._limits_unsupported_warned = False

    def apply_global_caps(self) -> None:
        """Re-assert global transfer limits from config (O4/D5).

        No-op when no global cap is configured or the client is absent /
        lacks :class:`GlobalRateLimiter`. Fail-soft on :exc:`ApiError`: warn
        and continue — a dead client must never block the run.
        """
        bw = self._bandwidth
        if bw.global_down is None and bw.global_up is None:
            return
        tc = self._torrent_client
        if tc is None or not isinstance(tc, GlobalRateLimiter):
            return
        try:
            tc.apply_global_limits(
                down_bytes_per_s=bw.global_down,
                up_bytes_per_s=bw.global_up,
            )
        except ApiError as exc:
            log.warning("acquire.global_limits.failed", error=str(exc))

    # ------------------------------------------------------------------
    # Shared search→filter→rank chain
    # ------------------------------------------------------------------

    def _query_and_narrow(
        self,
        item: WantedItem,
        query: str,
        title: str | None,
        original_title: str | None,
        year: int | None,
    ) -> "_QueryAttempt":
        """Run ONE tracker query and the kind-specific identity narrowing.

        The seam that lets :meth:`_search_chain` play the same
        search→narrow stage twice — once with the display-title query, once
        with the original-title query (#435) — without duplicating the exit
        taxonomy. Three shapes come back:

        * ``hard_stop`` set — outage/auth/circuit/degraded: a verdict that a
          retry with another spelling must NOT overwrite;
        * empty ``results`` with ``empty_verdict`` set — a fully-healthy
          « nothing matched » conclusion (``no_candidates`` /
          ``no_matching_episode`` / ``no_matching_season``), the retry
          trigger, and the verdict to state if the retry finds nothing;
        * empty ``results`` with NO ``empty_verdict`` — the movie identity
          filter dropped everything: the caller lets the empty list flow to
          :func:`rank_candidates` so the historical ``all_filtered`` verdict
          is preserved bit-for-bit.

        Args:
            item: The claimed ``WantedItem``.
            query: The exact ``q=`` to send (already year-narrowed).
            title: The follow's display title (movie identity filter).
            original_title: The follow's original-language title (idem).
            year: The follow's release year.

        Returns:
            The :class:`_QueryAttempt` for this query.
        """
        media_type = MediaType.TV if item.kind in ("episode", "season") else MediaType.MOVIE

        # CircuitOpenError is NOT an ApiError → needs its own clause;
        # TrackerAuthError IS an ApiError → must precede its base clause. Both
        # cover a raise OUTSIDE the registry's per-tracker loop; inside it, the
        # failures come back as taxa on the outcome — see _search_chain.
        try:
            outcome: SearchOutcome = self._tracker_registry.search_candidates(query, media_type, year)
        except CircuitOpenError:
            return _QueryAttempt(hard_stop=_SearchChainResult(exit_path="circuit_open", ranked=[], top=None))
        except TrackerAuthError:
            return _QueryAttempt(hard_stop=_SearchChainResult(exit_path="tracker_auth", ranked=[], top=None))
        except ApiError:
            return _QueryAttempt(hard_stop=_SearchChainResult(exit_path="search_api_error", ranked=[], top=None))

        if outcome.all_errored:
            return _QueryAttempt(
                hard_stop=_SearchChainResult(exit_path=_all_errored_exit_path(outcome), ranked=[], top=None)
            )
        if not outcome.results:
            # A PARTIAL outage is not an absence. ``all_errored`` (handled above)
            # only catches a unanimous failure; with one tracker rate-limited and
            # the other legitimately empty, the empty set used to be persisted as
            # « I looked, there is nothing » — false, and it burned an attempt.
            # Only a fully-healthy, fully-empty search may conclude no_candidates.
            if outcome.trackers_errored > 0:
                return _QueryAttempt(hard_stop=_SearchChainResult(exit_path="trackers_degraded", ranked=[], top=None))
            return _QueryAttempt(empty_verdict=_SearchChainResult(exit_path="no_candidates", ranked=[], top=None))

        # --- Kind-specific identity narrowing (BEFORE hard-filter): the title
        # query returns fuzzy matches (other episodes, season packs, other
        # « Wicker* » films); keep only releases naming the wanted identity so
        # ranking cannot pick the wrong one. ---
        results = outcome.results
        if item.kind == "episode" and item.season is not None and item.episode is not None:
            raw_before_filter = list(results)  # R2: snapshot for season conversion
            results = filter_to_episode(results, item.season, item.episode)
            if not results:
                return _QueryAttempt(
                    empty_verdict=_SearchChainResult(
                        exit_path="no_matching_episode",
                        ranked=[],
                        top=None,
                        raw_before_filter=raw_before_filter,
                    )
                )
        elif item.kind == "season" and item.season is not None:
            # F4 — verify a pack's coverage against the aired-episode count;
            # None (no resolver / empty cache) → the filter rejects any
            # episode-marker release conservatively.
            expected_count = self._episode_count_resolver(item) if self._episode_count_resolver is not None else None
            results = filter_to_season(results, item.season, expected_count=expected_count)
            if not results:
                # A SEASON row's fruitless search states its own outcome —
                # 'no_matching_episode' on a season row would surface a lie in
                # the row's last_search_outcome (review F12).
                return _QueryAttempt(
                    empty_verdict=_SearchChainResult(exit_path="no_matching_season", ranked=[], top=None)
                )
        elif item.kind == "movie" and title is not None:
            # #28 — a movie title query pulls the WRONG « Wicker* » films; keep
            # only releases whose parsed title+year match the wanted movie so
            # ranking cannot pick a different film (§5/§7 identity). An empty
            # result flows to rank_candidates → all_filtered (honest « rien de
            # conforme »), never a wrong-movie grab. The filter gets EVERY
            # known title (#435): releases are commonly named in the original
            # language while the follow carries the localized display title.
            results = filter_to_movie(results, [title, original_title], year)

        return _QueryAttempt(results=results)

    def _search_chain(
        self,
        item: WantedItem,
        profile: QualityProfile,
        *,
        exclude_hashes: "frozenset[str]" = frozenset(),
    ) -> _SearchChainResult:
        """Run the shared search→filter→rank pipeline and return the exit path.

        Both :meth:`search` and :meth:`grab` call this private method.  It
        executes the full chain — query build → search_candidates →
        filter_to_episode → apply_hard_filters → dedup → rank — catches
        operational exceptions, and encodes the result as a
        :class:`_SearchChainResult` whose ``exit_path`` the two callers map
        onto their respective outcome types.

        The torrent client is never touched and no events are emitted here.
        Catch order is load-bearing: :exc:`CircuitOpenError` first (it is a
        *sibling* of :exc:`ApiError`, ``core/_contracts.py`` — a bare
        ``except ApiError`` would miss it), then :exc:`TrackerAuthError`
        (a *subclass*, so it must precede its base to reach its own exit
        path), then :exc:`ApiError` for everything else (including
        :exc:`TorrentFetchError`).

        The ``"tracker_auth"`` exit path exists for :meth:`search`, which
        must state a TERMINAL verdict on a broken passkey.  :meth:`grab`
        deliberately folds it back into its historical retryable
        ``search_api_error`` bucket, so this extraction leaves grab's
        behaviour and reason strings byte-identical.

        The registry swallows every per-tracker exception (fail-soft: one
        broken tracker must not erase the results the healthy ones returned),
        so the ``except`` clauses above only ever fire for a raise OUTSIDE that
        loop. What the loop DOES report is the failure taxon per tracker
        (``SearchOutcome.errors``: ``auth`` / ``circuit`` / ``api``), and that is
        what makes the all-errored verdict honest (D4):

        * every queried tracker in ``auth`` ⇒ ``tracker_auth`` — a broken key is
          permanent, so :meth:`search` states a TERMINAL verdict and the item is
          abandoned instead of retrying an unfixable failure forever;
        * every queried tracker in ``circuit`` ⇒ ``circuit_open`` — the breakers
          are open, which is a real outage that names itself;
        * anything else (mixed taxa, or any ``api``) ⇒ ``trackers_unavailable``,
          the historical label, unchanged.

        Unanimity is the rule because a partial failure is not a diagnosis: one
        broken key among two working trackers is not « the trackers are broken »,
        it is a degraded search, and the results that came back still stand.

        WHAT MAKES THE ``auth`` TAXON REACHABLE. It is not automatic, and it was
        not always true: :exc:`TrackerAuthError` used to be raised in exactly one
        place — ``fetch_torrent_source``, on the GRAB stage's ``.torrent``
        download — so a broken key during a SEARCH surfaced as a plain
        :exc:`ApiError`, taxon ``api``, verdict ``trackers_unavailable``, retried
        forever. The registry's ``except TrackerAuthError`` clause was dead code.
        ``TorznabClient`` now classifies its own auth failures (HTTP 401/403 and
        the Torznab 100-102 error codes) so the search path raises it too. The
        two paths stay distinct and both matter:

        * SEARCH (``TorznabClient._request`` / ``_parse_rss``) ⇒ the ``auth``
          taxon ⇒ this method's terminal ``tracker_auth`` verdict;
        * GRAB (``fetch_torrent_source``) ⇒ the ``except TrackerAuthError``
          clause in :meth:`grab`, which is where a download-time 401/403 is
          caught — outside any registry loop.

        A test that proves the first path MUST drive a real tracker client: a
        stub whose ``search()`` raises :exc:`TrackerAuthError` asserts the
        classification of an exception nothing produced.

        BLAST RADIUS. Because the verdict really is terminal, a genuine
        all-trackers-auth failure abandons rows — including during a passkey
        rotation, when every key is briefly invalid at once. The search pass
        therefore debounces it: the first all-auth verdict is recorded but the
        row stays queued, and only a second CONSECUTIVE one abandons (see
        ``_search_pass._DEBOUNCED_TERMINAL_OUTCOMES``). This method is unchanged
        by that — it states the verdict; the service decides when to act on it.

        :meth:`grab` folds ``tracker_auth`` back into its historical retryable
        ``search_api_error`` bucket, so a search-stage auth failure NEVER
        abandons at grab time — the grab dispositions are unchanged by this.

        Args:
            item: The claimed ``WantedItem`` to search for.
            profile: The effective :class:`QualityProfile` for the hard-filter
                stage.
            exclude_hashes: Lowercase info-hashes to drop from ranking — releases
                already grabbed-and-failed for this item (reswitch #342). Empty
                by default, so the search path is unchanged.

        Returns:
            A :class:`_SearchChainResult` whose ``exit_path`` is one of the
            :data:`SEARCH_OUTCOMES` values.
        """
        media_ref = item.media_ref
        title = self._title_resolver(item) if self._title_resolver is not None else None
        # #28 — resolve the follow's release year to narrow an ambiguous movie
        # title (« Wicker » → every « Wicker* » film) in BOTH the query and the
        # identity filter below.
        year = self._year_resolver(item) if self._year_resolver is not None else None
        original_title = self._original_title_resolver(item) if self._original_title_resolver is not None else None

        # --- First attempt: the display-title query. Hard failures (outage,
        # auth, circuit, degraded) state their verdict immediately — retrying
        # them with another spelling would muddle an honest diagnosis. ---
        first = self._query_and_narrow(item, build_search_query(item, title, year), title, original_title, year)
        if first.hard_stop is not None:
            return first.hard_stop

        chosen = first
        if not first.results and original_title and original_title != title:
            # #435 — some trackers only match what the release NAME carries
            # (the original language): one retry with the original-title query,
            # same narrowing. A hard failure here must not overwrite the first
            # attempt's honest healthy-empty verdict, so it degrades to empty.
            log.info(
                "acquire.search.retry_original_title",
                kind=item.kind,
                title=title,
                original_title=original_title,
            )
            second = self._query_and_narrow(
                item, build_search_query(item, original_title, year), title, original_title, year
            )
            if second.hard_stop is None and second.results:
                chosen = second

        if not chosen.results and chosen.empty_verdict is not None:
            return chosen.empty_verdict
        results = chosen.results

        # --- Hard-filter → dedup → rank (DESIGN §15 stage order) ---
        # Delegated to the module-level :func:`rank_candidates` seam so the
        # search pass, the grab pass AND the ``grab --dry-run`` preview all
        # consume the SAME ranked result (solidify F4 — a preview that ranks
        # differently from the run is a lie). Empty ``representatives`` ⇔ empty
        # hard-filter survivors (``dedup([])`` is ``[]``), so the two guards
        # below keep the all_filtered / no_seeders taxonomy bit-for-bit.
        representatives, ranked = rank_candidates(
            results, profile, media_ref, self._ranking, exclude_hashes=exclude_hashes, media_kind=item.kind
        )
        if not representatives:
            return _SearchChainResult(exit_path="all_filtered", ranked=[], top=None)
        if not ranked:
            return _SearchChainResult(exit_path="no_seeders", ranked=[], top=None)

        return _SearchChainResult(exit_path="available", ranked=ranked, top=ranked[0])

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search(
        self,
        item: WantedItem,
        profile: QualityProfile,
        *,
        exclude_hashes: "frozenset[str]" = frozenset(),
    ) -> SearchVerdict:
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
        ``TrackerAuthError``           ``terminal``    ``tracker_auth``      None
        ``ApiError``                   ``retryable``   ``search_api_error``  None
        ``all_errored``                ``retryable``   ``trackers_unavail.`` None
        Empty + SOME tracker errored   ``retryable``   ``trackers_degraded`` None
        No results                     ``not_found``   ``no_candidates``     0
        ``filter_to_episode`` empty    ``not_found``   ``no_matching_ep.``   0
        ``filter_to_season`` empty     ``not_found``   ``no_matching_sea.``  0
        ``apply_hard_filters`` empty   ``not_found``   ``all_filtered``      0
        ``rank`` empty (min_seeders)   ``retryable``   ``no_seeders``        None
        Ranked non-empty               ``available``   ``available``         len(ranked)
        ============================= =============== ===================== =====

        ``found`` is ``None`` on every path where the search did NOT conclude
        (panne ≠ absence): zero would claim « I looked, there is nothing »,
        which is false during an outage — the founding lie this feature removes.

        One row of that table is currently UNREACHABLE from the search stage:
        ``TrackerAuthError`` → ``tracker_auth``. The registry swallows
        per-tracker exceptions and reports only tracker NAMES, so a broken
        passkey arrives here as ``trackers_unavailable`` (or is silently absent
        from the results). The mapping is kept — it is correct, and the clause
        that feeds it still guards auth failures raised outside that loop — but
        it must not be read as « a broken passkey abandons the item today ».
        See :meth:`_search_chain` for what surfacing it would cost.

        Args:
            item: The wanted item to search for (read-only).
            profile: The effective :class:`QualityProfile` for the hard-filter
                stage.
            exclude_hashes: Lowercase info-hashes to drop from ranking — releases
                already grabbed-and-failed for this item (reswitch #342), so the
                availability verdict never counts a known-dead release as takeable
                (review M1). Empty by default, so the ordinary search is unchanged.

        Returns:
            A :class:`SearchVerdict` describing availability.
        """
        result = self._search_chain(item, profile, exclude_hashes=exclude_hashes)

        mapping: dict[str, tuple[SearchDisposition, str, int | None]] = {
            "circuit_open": ("retryable", "circuit_open", None),
            "tracker_auth": ("terminal", "tracker_auth", None),
            "search_api_error": ("retryable", "search_api_error", None),
            "trackers_unavailable": ("retryable", "trackers_unavailable", None),
            "trackers_degraded": ("retryable", "trackers_degraded", None),
            "no_candidates": ("not_found", "no_candidates", 0),
            "no_matching_episode": ("not_found", "no_matching_episode", 0),
            "no_matching_season": ("not_found", "no_matching_season", 0),
            "all_filtered": ("not_found", "all_filtered", 0),
            "no_seeders": ("retryable", "no_seeders", None),
            "available": ("available", "available", len(result.ranked)),
        }
        disposition, outcome, found = mapping[result.exit_path]

        chosen = result.top[0] if result.top is not None else None
        raw_results = tuple(result.raw_before_filter) if result.raw_before_filter is not None else None
        log.debug(
            "acquire.search.verdict",
            disposition=disposition,
            outcome=outcome,
            found=found,
            kind=item.kind,
        )
        return SearchVerdict(
            disposition=disposition,
            outcome=outcome,
            found=found,
            chosen=chosen,
            raw_results=raw_results,
        )

    def grab(
        self,
        item: WantedItem,
        profile: QualityProfile,
        *,
        on_intent: "Callable[[str], None] | None" = None,
        exclude_hashes: "frozenset[str]" = frozenset(),
    ) -> GrabOutcome:
        """Execute the full grab chain for one claimed ``WantedItem``.

        The item is assumed already claimed (``status='searching'``) by the
        service. This method performs NO store writes of its own — it returns a
        :class:`GrabOutcome` whose ``disposition`` the service maps onto a
        status. The ONE persistence point it reaches is the caller-supplied
        ``on_intent`` hook (D2), invoked with the chosen info-hash
        immediately before ``add()`` so the orchestrator keeps no store
        dependency while the window still closes. On a FAILURE path it emits exactly one event (``GrabFailed`` /
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
          ``tracker_auth``. This applies to the resolve/add stage only: a
          SEARCH-stage auth failure keeps its historical RETRYABLE
          ``search_api_error`` classification (see the exit-path fold below),
          so the chain extraction changed no grab behaviour.
        - ``TorrentFetchError`` → RETRYABLE ``fetch_failed``.
        - other ``ApiError`` (add failure / transient) → RETRYABLE
          ``add_failed``.

        Args:
            item: The claimed ``WantedItem`` to grab (read-only here).
            profile: The effective :class:`QualityProfile` for the hard-filter
                stage (resolved by the service before dispatch).
            on_intent: Optional pre-add hook (D2) called with the chosen
                release's info-hash right before ``add()``. The service writes
                the intent hash onto the still-'searching' row there, so a crash
                in the add→confirm window leaves a row that can be REPLAYED
                (confirmed against the client) instead of an orphan torrent.
                Skipped when the chosen result carries no info-hash; a raise
                propagates (the add does NOT run — no orphan).
            exclude_hashes: Lowercase info-hashes to exclude from ranking —
                releases already grabbed-and-failed for this item (reswitch
                #342), so a re-grab after an auto-reswitch never re-picks the
                same dead release. Empty by default (the ordinary first grab).

        Returns:
            The :class:`GrabOutcome` describing success / retryable / terminal.
        """
        media_ref = item.media_ref

        # --- Shared search→filter→rank chain ---
        # reswitch #342: exclude releases already grabbed-and-failed for this item
        # so a re-grab after a dead-swarm stall never re-picks the same release.
        result = self._search_chain(item, profile, exclude_hashes=exclude_hashes)

        # Map each exit path to the same disposition + event the inline chain
        # produced before the extraction (outcome.reason strings unchanged).
        if result.exit_path == "circuit_open":
            return self._retryable(media_ref, "circuit_open")
        if result.exit_path in ("search_api_error", "tracker_auth"):
            # A search-time auth failure keeps grab's HISTORICAL classification
            # (retryable ``search_api_error``): before the chain extraction the
            # single ``except ApiError`` swallowed TrackerAuthError here. Only
            # ``search()`` states the TERMINAL ``tracker_auth`` verdict; grab's
            # terminal auth path stays the post-search resolve/add one below.
            return self._retryable(media_ref, "search_api_error")
        if result.exit_path == "trackers_unavailable":
            return self._retryable(media_ref, "trackers_unavailable")
        if result.exit_path == "no_candidates":
            return self._not_found(media_ref, "no_candidates")
        if result.exit_path == "no_matching_episode":
            return self._not_found(media_ref, "no_matching_episode")
        if result.exit_path == "no_matching_season":
            return self._not_found(media_ref, "no_matching_season")
        if result.exit_path == "all_filtered":
            return self._not_found(media_ref, "all_filtered")
        if result.exit_path == "no_seeders":
            return self._retryable(media_ref, "no_seeders")

        # --- Available: proceed to the grab-only stages ---
        # The chain only reaches "available" with a non-empty ``ranked`` list, so
        # ``top`` is guaranteed present here; assert it so the invariant is
        # checked rather than implied by the exit-path chain above.
        assert result.top is not None  # noqa: S101 — "available" always carries a top
        top, _score = result.top

        # --- No torrent client → cannot add (search-only / dry-run). RETRYABLE. ---
        if self._torrent_client is None:
            return self._retryable(media_ref, "no_torrent_client", chosen=top)

        # --- Resolve source then add (taxonomy: §6.2 catch order) ---
        # No torrent-client category (labels[0]) — the grab tags the release
        # with its source tracker only. The provider tag is carried ATOMICALLY
        # by add(): qBittorrent sets native tags inline, Transmission encodes
        # the category-less tag behind the "" sentinel (labels=["", provider],
        # F-A). Both round-trip to (category=None, tags=[provider]). Resolved
        # open item #8: add() now emits the sentinel, so the former two-step
        # (add then a separate add_tags) is gone — no category is forced to
        # dodge a gap, and a torrent is never added-but-untagged.
        try:
            # A fetch failure is CANDIDATE-specific, so the walk tries a few
            # ranked siblings rather than starving the item on one dead
            # release; it also attributes a tracker-wide failure to the
            # tracker that raised it (see `_resolve_walk`).
            # Transports read FRESH (never a boot snapshot): by here the
            # tracker has already run its search() in THIS grab, so a
            # login-style tracker's authed transport exists — a transient boot
            # login blip can no longer strand it for the process lifetime.
            attempt = resolve_first_available(result.ranked, self._tracker_registry.transports(), top=top)
            if attempt.source is None:
                # Nothing resolved: conclude on the candidate the walk blames,
                # so the operator alert names the tracker that broke rather
                # than the ranked top.
                chosen = attempt.chosen
                if isinstance(attempt.error, CircuitOpenError):
                    return self._retryable(media_ref, "circuit_open", chosen=chosen)
                if isinstance(attempt.error, TrackerAuthError):
                    self._event_bus.emit(
                        TrackerAuthFailed(
                            tracker=chosen.provider,
                            http_status=attempt.error.http_status,
                            media_ref=media_ref,
                        )
                    )
                    return self._terminal(media_ref, "tracker_auth", chosen=chosen)
                # Fetch failure, or any other transport error DURING the fetch
                # (add() was never reached, so never « add_failed »).
                return self._retryable(media_ref, "fetch_failed", chosen=chosen)
            source, top = attempt.source, attempt.chosen
            # D2 — reserve the hash BEFORE handing the torrent to the client.
            # ``resolve_source`` has just cross-checked the fetched payload
            # against ``top.info_hash``, so the value written here is the hash
            # the client is about to report. A raise here means the intent could
            # not be persisted: the add is skipped on purpose (an unrecorded add
            # is exactly the orphan this closes).
            if on_intent is not None and top.info_hash:
                on_intent(top.info_hash)
            # --- Apply per-torrent caps when configured (O4) ---
            limits = _build_limits(
                self._bandwidth,
                client_is_limiter=isinstance(self._torrent_client, TorrentLimiter),
            )
            if (
                limits is None
                and (self._bandwidth.per_torrent_down is not None or self._bandwidth.per_torrent_up is not None)
                and not self._limits_unsupported_warned
            ):
                self._limits_unsupported_warned = True
                log.warning(
                    "acquire.grab.limits_unsupported",
                    client_type=type(self._torrent_client).__name__,
                )
            info_hash = self._torrent_client.add(source, category=None, tags=[top.provider], limits=limits)
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
            category=None,
            tags=(top.provider,),
            found=len(result.ranked),
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
        return GrabOutcome(disposition="retryable", reason=reason, chosen=chosen, found=None)

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
        return GrabOutcome(disposition="not_found", reason=reason, found=0)

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
        return GrabOutcome(disposition="terminal", reason=reason, chosen=chosen, found=None)


__all__ = [
    "GrabOrchestrator",
    "build_search_query",
    "GrabOutcome",
    "SearchDisposition",
    "SearchVerdict",
    "SEARCH_OUTCOMES",
    "INCONCLUSIVE_OUTCOMES",
    "filter_to_episode",
    "filter_to_movie",
    "filter_to_season",
    "rank_candidates",
]
