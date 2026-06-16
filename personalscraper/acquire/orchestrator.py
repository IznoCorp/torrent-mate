"""Grab orchestrator — single-item §1 chain (RP5b, phase 4a).

``GrabOrchestrator.grab(item, profile)`` executes the §1 grab chain for ONE
already-claimed ``WantedItem`` and returns a :class:`GrabOutcome`:

    profile → search → hard-filter → dedup → rank → resolve_source → add

It does **not** touch the store or the wanted state machine — the
``AcquisitionService`` (phase 4b) owns the atomic claim, the status
transitions (success→grabbed / retryable→pending / terminal→abandoned) and
``mark_grabbed``. The orchestrator returns the typed disposition the service
maps onto a status.

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
``transports`` map is injected directly (the ``_factory`` builds it via
``TrackerRegistry.transports()``) so ``resolve_source`` never reaches back into
the registry.

Import direction: ``acquire/`` imports ``api/`` / ``core/`` / ``conf/`` /
``events/`` downward only — never the triage packages (layering guard).
"""

from __future__ import annotations

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
    from collections.abc import Mapping

    from personalscraper.acquire.desired import QualityProfile
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.api.torrent._contracts import TorrentAdder
    from personalscraper.api.tracker._base import TrackerResult
    from personalscraper.api.tracker._ranking import RankingConfig
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.api.transport._http import HttpTransport
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.identity import MediaRef

log = get_logger("acquire.orchestrator")


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
            run), or ``"terminal"`` (permanent — orchestrator already emitted
            ``WantedAbandoned``).
        info_hash: Torrent info-hash on success, otherwise ``None``.
        reason: Machine-readable failure/abandonment reason, ``None`` on success.
        chosen: The ranked top :class:`TrackerResult` that was acted on, or
            ``None`` when the chain failed before a candidate was picked.
        category: Category passed to ``add()`` (carried for the service's
            ``GrabSucceeded`` payload). ``None`` off the success path.
        tags: Tags passed to ``add()`` (carried for the service's
            ``GrabSucceeded`` payload). Empty off the success path.
    """

    disposition: Literal["success", "retryable", "terminal"]
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
            (``search_candidates``).
        _transports: ``{provider → HttpTransport}`` map injected at
            construction (built by ``_factory`` via
            ``TrackerRegistry.transports()``) and passed to ``resolve_source``.
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
        transports: Mapping[str, HttpTransport],
        torrent_client: TorrentAdder | None,
        event_bus: EventBus,
        ranking: RankingConfig,
    ) -> None:
        """Initialise the orchestrator with injected narrow deps.

        Args:
            tracker_registry: Multi-tracker search coordinator.
            transports: ``{provider → HttpTransport}`` map for ``resolve_source``.
            torrent_client: Torrent add capability, or ``None`` (search-only).
            event_bus: In-process event bus.
            ranking: Ranking configuration applied after dedup.
        """
        self._tracker_registry = tracker_registry
        self._transports = transports
        self._torrent_client = torrent_client
        self._event_bus = event_bus
        self._ranking = ranking

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
        media_type = MediaType.TV if item.kind == "episode" else MediaType.MOVIE
        query = self._build_query(media_ref)
        year: int | None = None  # title/year resolution is a Follow D3 concern

        # --- Search (CircuitOpenError is NOT an ApiError → catch separately) ---
        try:
            outcome: SearchOutcome = self._tracker_registry.search_candidates(query, media_type, year)
        except CircuitOpenError:
            return self._retryable(media_ref, "circuit_open")
        except ApiError:
            return self._retryable(media_ref, "search_api_error")

        if outcome.all_errored:
            # Every queried tracker errored → transient outage, retry next run.
            return self._retryable(media_ref, "trackers_unavailable")
        if not outcome.results:
            # Clean search, zero hits → no source exists, won't self-heal.
            return self._terminal(media_ref, "no_candidates")

        # --- Hard-filter (BEFORE dedup — DESIGN §15 stage order) ---
        survivors = apply_hard_filters(outcome.results, profile)
        if not survivors:
            return self._terminal(media_ref, "all_filtered")

        # --- Dedup → rank → pick top ---
        representatives = dedup(survivors)
        ranked = rank(representatives, self._ranking)
        if not ranked:
            # Everything dropped below min_seeders during ranking — no healthy
            # swarm right now → retry next run rather than abandon permanently.
            return self._retryable(media_ref, "no_seeders")
        top, _score = ranked[0]

        # --- No torrent client → cannot add (search-only / dry-run). RETRYABLE. ---
        if self._torrent_client is None:
            return self._retryable(media_ref, "no_torrent_client", chosen=top)

        # --- Resolve source then add (taxonomy: §6.2 catch order) ---
        # category stays None — Transmission uses labels[0] for category, so
        # passing tags=(...) alongside would clobber it; tags are applied via
        # a separate add_tags() call on clients that implement TorrentTagger.
        category: str | None = None
        try:
            source = resolve_source(top, self._transports)
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

    @staticmethod
    def _build_query(media_ref: MediaRef) -> str:
        """Build a search query string from a :class:`MediaRef`.

        ``WantedItem`` carries no title at RP5b (real title resolution is a
        Follow D3 concern), so the query is the primary provider ID rendered as
        a string — pragmatic per the plan. ``MediaRef`` guarantees at least one
        of ``tvdb_id`` / ``tmdb_id`` / ``imdb_id`` is set, so the result is
        always non-empty.

        Args:
            media_ref: The item's provider-ID key (tvdb_id primary).

        Returns:
            A non-empty query string.
        """
        if media_ref.tvdb_id is not None:
            return str(media_ref.tvdb_id)
        if media_ref.tmdb_id is not None:
            return str(media_ref.tmdb_id)
        return str(media_ref.imdb_id)

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


__all__ = ["GrabOrchestrator", "GrabOutcome"]
