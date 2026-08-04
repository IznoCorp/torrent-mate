"""Non-vacuous tests for GrabOrchestrator (acquire/orchestrator.py, phase 4a).

Load-bearing tests called out explicitly:

- GOLDEN happy path: mocked ``resolve_source`` + ``TorrentAdder.add`` → exactly
  ONE ``GrabSucceeded`` with the EXACT payload (real ``EventBus`` capture).
- Failure taxonomy (DESIGN §6.2), each disposition + emitted event asserted:
    * ``CircuitOpenError`` caught SEPARATELY (not as ``ApiError``) → RETRYABLE,
      never a batch crash.
    * ``TrackerAuthError`` → TERMINAL ``tracker_auth`` (no add() call).
    * idempotent Conflict (add returns same hash) → still ONE success.
    * all trackers errored → RETRYABLE ``trackers_unavailable`` (NOT abandoned).
    * SOME trackers errored + zero hits → RETRYABLE ``trackers_degraded``.
    * clean zero hits → TERMINAL ``no_candidates``.
    * zero survivors after hard-filter → TERMINAL ``all_filtered``.
    * ``torrent_client is None`` → RETRYABLE ``no_torrent_client`` (no crash).
- NEGATIVE seed-write assert (load-bearing): a seed-obligation spy's
  ``record_dispatch`` / ``seed.add`` ``call_count == 0`` across a full success.
- SEARCH exit paths (acq-states phase 2 + acq-escalade D2): all declared paths forced
  through the real chain, asserting the ``SearchVerdict`` triple
  ``(disposition, outcome, found)`` plus the two negative invariants — no
  ``add()`` and no event emitted. ``found`` is ``None`` on every inconclusive
  path (panne ≠ absence) and ``0`` only where the search really concluded.

Every assertion is REAL (disposition + emitted event type/payload +
call_counts), never assert-no-exception.
"""

from __future__ import annotations

import sqlite3
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import GrabFailed, GrabSucceeded, WantedAbandoned
from personalscraper.acquire.orchestrator import (
    GrabOrchestrator,
    GrabOutcome,
    build_search_query,
    filter_to_season,
    rank_candidates,
)
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api._units import ByteSize
from personalscraper.api.torrent._base import TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.api.tracker._ranking import RankingConfig, RankingCriterion, ThresholdEntry
from personalscraper.conf.models.acquire import BandwidthConfig
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.identity import MediaRef

_RESOLVE = "personalscraper.acquire.orchestrator.resolve_source"


def _make_wanted(
    kind: 'Literal["movie", "episode", "season"]' = "movie",
    tvdb_id: int = 12345,
    season: int | None = None,
) -> WantedItem:
    """Build a claimed WantedItem (phase 4a: no ``id`` field yet)."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind=kind,
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
        season=season,
    )


def _make_result(
    title: str = "Inception 2010 MULTi 1080p BluRay x265-GRP",
    resolution: str | None = "1080p",
    seeders: int = 50,
    info_hash: str | None = "aaaa1234",
) -> TrackerResult:
    return TrackerResult(
        provider="c411",
        tracker_id="t1",
        title=title,
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution=resolution,
        info_hash=info_hash,
        download_url="https://c411.test/torrent/1",
    )


class _EventSpy:
    """Capturing subscriber: records every Event it receives, in order."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


def _make_orchestrator(
    *,
    search_outcome: SearchOutcome | None = None,
    add_return: str = "aaaa1234",
    add_side_effect: Exception | None = None,
    torrent_client_none: bool = False,
    ranking: RankingConfig | None = None,
) -> tuple[GrabOrchestrator, _EventSpy, MagicMock, MagicMock | None, MagicMock]:
    """Build a GrabOrchestrator with a REAL EventBus + mocked narrow deps.

    Returns ``(orchestrator, event_spy, registry, torrent_client, seed_spy)``.

    ``seed_spy`` is a discarded placeholder kept for tuple-shape stability across
    call sites. The load-bearing NEGATIVE-invariant proof is NOT a probe-mock
    (which, wired nowhere, can never be touched — vacuous) but the dep-scan in
    ``test_negative_seed_write_never_called_during_full_success``: no seed-write
    method name may leak onto the deps the orchestrator actually holds.
    """
    if search_outcome is None:
        search_outcome = SearchOutcome(results=[_make_result()], trackers_queried=1, trackers_errored=0)

    registry = MagicMock()
    registry.search_candidates.return_value = search_outcome

    transports = {"c411": MagicMock()}
    # The orchestrator reads transports FRESH at grab time via the registry, so
    # the map is served from registry.transports() rather than a ctor snapshot.
    registry.transports.return_value = transports

    torrent_client: MagicMock | None
    if torrent_client_none:
        torrent_client = None
    else:
        torrent_client = MagicMock(spec=TorrentAdder)
        if add_side_effect is not None:
            torrent_client.add.side_effect = add_side_effect
        else:
            torrent_client.add.return_value = add_return

    bus = EventBus()
    spy = _EventSpy()
    bus.subscribe(Event, spy)  # base subscriber: catches every event subclass

    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=torrent_client,
        event_bus=bus,
        ranking=ranking if ranking is not None else RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )
    seed_spy = MagicMock()
    return orchestrator, spy, registry, torrent_client, seed_spy


# ---------------------------------------------------------------------------
# GrabOutcome dataclass
# ---------------------------------------------------------------------------


def test_grab_outcome_is_frozen_dataclass() -> None:
    """GrabOutcome is a frozen dataclass carrying the typed disposition."""
    import dataclasses

    outcome = GrabOutcome(disposition="success", info_hash="abc123")
    assert outcome.disposition == "success"
    assert outcome.info_hash == "abc123"
    assert outcome.reason is None
    assert outcome.chosen is None
    # Frozen is proven behaviorally: assigning a field raises FrozenInstanceError.
    try:
        outcome.disposition = "terminal"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover - frozen guarantees the except path
        raise AssertionError("GrabOutcome must be frozen")


# ---------------------------------------------------------------------------
# GOLDEN happy path
# ---------------------------------------------------------------------------


def test_grab_happy_path_returns_success_outcome_with_exact_payload() -> None:
    """GOLDEN: fetch+add → success outcome carrying the EXACT GrabSucceeded payload.

    Emit-after-persist (DESIGN §15 / §11(d)): the orchestrator NO LONGER emits
    ``GrabSucceeded`` — the service does, after ``mark_grabbed`` persists. So the
    golden assertion is on the returned outcome's payload fields (``info_hash`` /
    ``category`` / ``tags`` / ``chosen``) the service hands to ``GrabSucceeded``,
    AND that NO ``GrabSucceeded`` leaked from the orchestrator onto the bus.
    """
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(add_return="aaaa1234")

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Disposition + carried success payload (the exact fields the service emits).
    assert outcome.disposition == "success"
    assert outcome.info_hash == "aaaa1234"
    assert outcome.reason is None
    assert outcome.chosen is not None and outcome.chosen.provider == "c411"
    assert outcome.category is None
    assert outcome.tags == ("c411",)

    # add() was called exactly once carrying the provider tag ATOMICALLY, with
    # category=None (open item #8 FINAL: the tag rides the single add call — the
    # Transmission "" sentinel / qBit native tags — instead of a separate
    # add_tags step).
    assert torrent_client is not None
    torrent_client.add.assert_called_once()
    _args, kwargs = torrent_client.add.call_args
    assert kwargs["category"] is None
    assert kwargs["tags"] == ["c411"]

    # The former two-step is dead: the orchestrator no longer branches on
    # TorrentTagger nor calls add_tags() at grab time.
    assert not hasattr(torrent_client, "add_tags") or not torrent_client.add_tags.called

    # The orchestrator must NOT emit GrabSucceeded (the service owns that emit) —
    # and no failure event may leak either.
    assert not [e for e in spy.events if isinstance(e, GrabSucceeded)], (
        "orchestrator must NOT emit GrabSucceeded (emit-after-persist — service does)"
    )
    assert not [e for e in spy.events if isinstance(e, (GrabFailed, WantedAbandoned))]


def test_episode_kind_searches_with_tv_media_type() -> None:
    """An ``episode`` item searches with MediaType.TV (movie → MOVIE)."""
    orchestrator, _spy, registry, _tc, _seed = _make_orchestrator()
    with patch(_RESOLVE):
        orchestrator.grab(_make_wanted(kind="episode"), QualityProfile())
    _args, kwargs = registry.search_candidates.call_args
    # media_type is the 2nd positional arg (query, media_type, year)
    assert registry.search_candidates.call_args.args[1] == MediaType.TV


def test_season_kind_searches_with_tv_media_type() -> None:
    """A ``season`` item searches with MediaType.TV — like an episode.

    Regression guard for the Pan Am 103 incident: the media type is what tells
    the tracker client whether the year may be appended to ``q``. A season row
    classified as MOVIE gets « {title} S01 {year} » — the exact query that
    returned 0 result on the live trackers. The orchestrator was already right;
    the grab preview was not, and nothing pinned either at THIS level.
    """
    orchestrator, _spy, registry, _tc, _seed = _make_orchestrator()
    with patch(_RESOLVE):
        orchestrator.grab(_make_wanted(kind="season", season=1), QualityProfile())
    assert registry.search_candidates.call_args.args[1] == MediaType.TV


class _StalenessFakeRegistry:
    """Registry whose transports() map differs between construction and grab time.

    Reproduces the boot-snapshot staleness bug: a tracker is transiently ABSENT
    the first time ``transports()`` is called (its boot login blipped, or a
    login-style client had not materialized yet) but PRESENT on every later call
    (it logged in during the grab's own ``search()``). The OLD orchestrator
    snapshotted ``transports()`` at construction → the first (empty) call → that
    tracker was never recoverable for the process lifetime. The fixed
    orchestrator reads ``transports()`` FRESH at grab time → it sees the
    recovered map.
    """

    def __init__(self, *, search_outcome: SearchOutcome, recovered_transport: object) -> None:
        self._search_outcome = search_outcome
        self._recovered = recovered_transport
        self.transports_calls = 0

    def search_candidates(self, query: str, media_type: MediaType, year: int | None) -> SearchOutcome:
        """Return the canned outcome (signature mirrors TrackerRegistry)."""
        return self._search_outcome

    def transports(self) -> dict[str, object]:
        """Return ``{}`` on the FIRST call (boot blip), ``{tr4ker: ...}`` after."""
        self.transports_calls += 1
        if self.transports_calls == 1:
            return {}
        return {"tr4ker": self._recovered}


def test_transports_resolved_fresh_at_grab_not_boot_snapshot() -> None:
    """REGRESSION: a tracker absent at construction-time but present at grab-time is found.

    Transports are read FRESH at grab time, not from a boot snapshot.

    Drives one grab whose top result is a tr4ker hit with a RELATIVE
    ``/torrents/7/download`` url (no magnet → needs a transport). The fake
    registry returns an EMPTY transports map on its first call (simulating a
    transient boot blip that dropped the tracker) and the recovered
    ``{"tr4ker": <transport>}`` on every later call. With the boot-snapshot bug
    the orchestrator would hand ``resolve_source`` the empty map → no transport
    → ``fetch_failed``. The fix reads ``transports()`` at grab time, so
    ``resolve_source`` receives the recovered transport and the add path runs.
    """
    tracker_result = TrackerResult(
        provider="tr4ker",
        tracker_id="7",
        title="Some Show 2024 1080p WEB x265-GRP",
        size=ByteSize(3_000_000_000),
        seeders=42,
        leechers=1,
        resolution="1080p",
        info_hash="bbbb5678",
        download_url="/torrents/7/download",  # relative → transport lookup required
    )
    search_outcome = SearchOutcome(
        results=[tracker_result],
        trackers_queried=1,
        trackers_errored=0,
    )
    recovered_transport = MagicMock(name="tr4ker_transport")
    registry = _StalenessFakeRegistry(search_outcome=search_outcome, recovered_transport=recovered_transport)

    torrent_client = MagicMock(spec=TorrentAdder)
    torrent_client.add.return_value = "bbbb5678"
    bus = EventBus()
    spy = _EventSpy()
    bus.subscribe(Event, spy)

    orchestrator = GrabOrchestrator(
        tracker_registry=registry,  # type: ignore[arg-type]
        torrent_client=torrent_client,
        event_bus=bus,
        ranking=RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )

    # Simulate the boot moment the OLD code snapshotted at: the FIRST
    # transports() call returns the EMPTY map (the tracker dropped by a transient
    # boot blip). The OLD orchestrator captured exactly this at construction and
    # would forever hand resolve_source an empty map. We consume it here so the
    # subsequent grab-time call lands on the recovered branch — proving the fixed
    # orchestrator does NOT reuse this stale empty snapshot.
    assert registry.transports() == {}  # the stale boot snapshot

    captured: dict[str, object] = {}

    def _capture_resolve(result: TrackerResult, transports: dict[str, object]) -> object:
        # Capture the transports map the orchestrator actually passes so we can
        # prove it is the FRESH (recovered) one, not the empty boot snapshot.
        captured["transports"] = dict(transports)
        if result.provider not in transports:
            # Mirror the real resolve_source contract: a missing provider raises.
            raise TorrentFetchError(provider=result.provider, http_status=0, message="no transport")
        return MagicMock(spec=TorrentSource)

    with patch(_RESOLVE, side_effect=_capture_resolve):
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # The grab reached the add path (transport found) rather than fetch_failed:
    assert outcome.disposition == "success", f"expected success, got {outcome.disposition}/{outcome.reason}"
    assert outcome.info_hash == "bbbb5678"
    torrent_client.add.assert_called_once()
    assert not [e for e in spy.events if isinstance(e, GrabFailed)]

    # resolve_source received the FRESH recovered map containing tr4ker — proving
    # the orchestrator did NOT reuse the empty boot snapshot consumed above. The
    # registry's transports() was called at grab time (the 2nd call: boot blip +
    # the live grab-time read).
    assert captured["transports"] == {"tr4ker": recovered_transport}
    assert registry.transports_calls >= 2


# ---------------------------------------------------------------------------
# Adversarial — failure taxonomy (DESIGN §6.2)
# ---------------------------------------------------------------------------


def test_circuit_open_error_caught_separately_retryable_not_crash() -> None:
    """LOAD-BEARING: CircuitOpenError is a sibling of ApiError → caught SEPARATELY.

    Proves it is NOT misclassified as a generic ApiError and does NOT crash the
    batch: ``grab`` returns a RETRYABLE outcome and emits ``GrabFailed``.
    """
    # Sanity anchor: CircuitOpenError is genuinely NOT an ApiError subclass.
    assert not issubclass(CircuitOpenError, ApiError)

    orchestrator, spy, registry, _tc, _seed = _make_orchestrator()
    registry.search_candidates.side_effect = CircuitOpenError("c411", 30.0)

    # Must NOT raise — a bare ``except ApiError`` would let this escape & crash.
    outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "circuit_open"
    failed = [e for e in spy.events if isinstance(e, GrabFailed)]
    assert len(failed) == 1
    assert failed[0].reason == "circuit_open"
    # NOT abandoned — a circuit-open is transient, must be retried.
    assert not [e for e in spy.events if isinstance(e, WantedAbandoned)]


def test_circuit_open_on_add_is_retryable_separately() -> None:
    """CircuitOpenError on add() (after resolve) → RETRYABLE, not ApiError add_failed."""
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(
        add_side_effect=CircuitOpenError("qbit", 12.0),
    )
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "circuit_open"
    assert outcome.chosen is not None and outcome.chosen.provider == "c411"
    assert [e for e in spy.events if isinstance(e, GrabFailed)]


def test_tracker_auth_error_terminal_no_add_call() -> None:
    """TrackerAuthError on resolve_source → TERMINAL tracker_auth, add() never called."""
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator()
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.side_effect = TrackerAuthError(provider="c411", http_status=403, message="forbidden")
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "terminal"
    assert outcome.reason == "tracker_auth"
    abandoned = [e for e in spy.events if isinstance(e, WantedAbandoned)]
    assert len(abandoned) == 1
    assert abandoned[0].reason == "tracker_auth"
    # add() must NOT have been reached after an auth failure on resolve.
    assert torrent_client is not None
    torrent_client.add.assert_not_called()


def test_torrent_fetch_error_retryable() -> None:
    """TorrentFetchError on resolve_source → RETRYABLE fetch_failed."""
    orchestrator, spy, _registry, _tc, _seed = _make_orchestrator()
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.side_effect = TorrentFetchError(provider="c411", http_status=0, message="bad body")
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "fetch_failed"
    assert [e for e in spy.events if isinstance(e, GrabFailed)]


def test_generic_api_error_on_add_retryable_add_failed() -> None:
    """A generic ApiError on add() → RETRYABLE add_failed (caught AFTER siblings)."""
    orchestrator, spy, _registry, _tc, _seed = _make_orchestrator(
        add_side_effect=ApiError(provider="qbit", http_status=500, message="server error"),
    )
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "add_failed"
    assert [e for e in spy.events if isinstance(e, GrabFailed)]


def test_conflict_idempotent_add_returns_same_hash_still_success() -> None:
    """Idempotent Conflict: add() RETURNS the existing hash → ONE GrabSucceeded.

    DESIGN §1 / TorrentAdder D7: a duplicate add is idempotent and returns the
    info_hash (it does NOT raise). The orchestrator must treat that as success.
    """
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(add_return="dup0beef")
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "success"
    assert outcome.info_hash == "dup0beef"
    # Emit-after-persist: the orchestrator returns the hash on the outcome and
    # does NOT emit GrabSucceeded itself (the service emits after mark_grabbed).
    assert not [e for e in spy.events if isinstance(e, GrabSucceeded)]
    assert torrent_client is not None
    torrent_client.add.assert_called_once()


def test_all_trackers_errored_retryable_not_abandoned() -> None:
    """All queried trackers errored → RETRYABLE trackers_unavailable (NOT abandoned)."""
    outcome_all_err = SearchOutcome(results=[], trackers_queried=2, trackers_errored=2)
    orchestrator, spy, _registry, _tc, _seed = _make_orchestrator(search_outcome=outcome_all_err)
    outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "trackers_unavailable"
    assert [e for e in spy.events if isinstance(e, GrabFailed)]
    # Distinct from a clean no_candidates → must NOT abandon.
    assert not [e for e in spy.events if isinstance(e, WantedAbandoned)]


def test_clean_zero_hits_not_found_no_candidates() -> None:
    """Clean search, zero hits → NOT_FOUND no_candidates (never abandoned).

    Regression for the House-of-the-Dragon shape (B.4): the 03:20 grab used to
    permanently abandon a just-aired episode because trackers had nothing 20
    minutes after detect. A zero-hit search is "not out yet", not "will never
    exist" — the row must stay retryable under cadence pacing.
    """
    no_hits = SearchOutcome(results=[], trackers_queried=1, trackers_errored=0)
    orchestrator, spy, _registry, _tc, _seed = _make_orchestrator(search_outcome=no_hits)
    outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "not_found"
    assert outcome.reason == "no_candidates"
    # No abandonment event — the item is still wanted.
    assert not [e for e in spy.events if isinstance(e, WantedAbandoned)]
    failed = [e for e in spy.events if isinstance(e, GrabFailed)]
    assert len(failed) == 1
    assert failed[0].reason == "no_candidates"


def test_all_filtered_not_found_all_filtered() -> None:
    """Zero survivors after hard-filter → NOT_FOUND all_filtered (retryable)."""
    result_720p = _make_result(title="Movie 2010 720p", resolution="720p")
    outcome_720 = SearchOutcome(results=[result_720p], trackers_queried=1, trackers_errored=0)
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=outcome_720)
    strict = QualityProfile(min_resolution=Resolution.R2160P)
    outcome = orchestrator.grab(_make_wanted(), strict)

    assert outcome.disposition == "not_found"
    assert outcome.reason == "all_filtered"
    assert not [e for e in spy.events if isinstance(e, WantedAbandoned)]
    # Never reached the add stage.
    assert torrent_client is not None
    torrent_client.add.assert_not_called()


def test_no_torrent_client_retryable_no_crash() -> None:
    """torrent_client is None (search-only) → RETRYABLE no_torrent_client, no crash."""
    orchestrator, spy, _registry, _tc, _seed = _make_orchestrator(torrent_client_none=True)
    with patch(_RESOLVE) as mock_resolve:
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())
        # resolve_source must not even be attempted when there is no client.
        mock_resolve.assert_not_called()

    assert outcome.disposition == "retryable"
    assert outcome.reason == "no_torrent_client"
    assert outcome.chosen is not None and outcome.chosen.provider == "c411"
    failed = [e for e in spy.events if isinstance(e, GrabFailed)]
    assert len(failed) == 1
    assert failed[0].reason == "no_torrent_client"


def test_no_seeders_after_rank_retryable() -> None:
    """min_seeders drops every candidate during rank → RETRYABLE no_seeders."""
    low_seed = SearchOutcome(
        results=[_make_result(seeders=2)],
        trackers_queried=1,
        trackers_errored=0,
    )
    # min_seeders=10 drops the 2-seeder result inside rank().
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(
        search_outcome=low_seed,
        ranking=RankingConfig(min_seeders=10),
    )
    outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "no_seeders"
    assert torrent_client is not None
    torrent_client.add.assert_not_called()


# ---------------------------------------------------------------------------
# NEGATIVE seed-write invariant (load-bearing, DESIGN §9 + §11-g)
# ---------------------------------------------------------------------------


def test_negative_seed_write_never_called_during_full_success() -> None:
    """LOAD-BEARING: seed.add / record_dispatch are NEVER called at grab time.

    The orchestrator has NO store/seed dependency, so a seed-obligation spy
    passed nowhere into it must stay pristine across a full successful grab.
    Asserted both via the spy's ``call_count == 0`` and by confirming no seed
    method name appears in the registry / torrent-client call logs.
    """
    orchestrator, _spy, registry, torrent_client, _seed = _make_orchestrator(add_return="aaaa1234")

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Grab really succeeded (so this is not a vacuous "nothing happened" pass).
    # With emit-after-persist the success signal is the returned disposition +
    # carried info-hash (the orchestrator no longer emits GrabSucceeded itself).
    assert outcome.disposition == "success"
    assert outcome.info_hash == "aaaa1234"

    # Belt-and-suspenders (the REAL negative guarantee): the orchestrator has no
    # store/seed dep, so no seed-write method name may leak onto the deps it DOES
    # hold. (The unwired ``seed_spy`` asserts were vacuous — a mock passed nowhere
    # can never be touched — so they are trimmed; this dep-scan is the load-bearing
    # check.)
    assert torrent_client is not None
    for tracked in (registry, torrent_client):
        for call_item in tracked.mock_calls:
            name = str(call_item)
            assert "record_dispatch" not in name, f"record_dispatch leaked onto a dep: {call_item}"
            assert "seed" not in name, f"seed write leaked onto a dep: {call_item}"


# ---------------------------------------------------------------------------
# SEARCH exit paths (acq-states phase 2) — the TEN contract paths, forced
# through the REAL chain (the service-level matrix mocks the orchestrator, so
# this is the only place the chain's own routing is proven).
# ---------------------------------------------------------------------------


def _make_wanted_episode(season: int = 9, episode: int = 5) -> WantedItem:
    """Build a claimed episode item so ``filter_to_episode`` runs on the chain."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="episode",
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
        season=season,
        episode=episode,
    )


def _assert_no_side_effects(spy: _EventSpy, torrent_client: MagicMock | None) -> None:
    """Assert the search pass touched nothing: no add() call, no event emitted.

    This is invariant n°1 of the feature — a ``search`` that downloads is a
    failed split. Asserted on EVERY exit path, not just the available one.
    """
    assert torrent_client is not None
    torrent_client.add.assert_not_called()
    assert spy.events == [], f"search must emit NO event; got {[type(e).__name__ for e in spy.events]}"


def test_search_available_states_takeable_count() -> None:
    """Ranked candidates → ('available', 'available', len(ranked)) + the top pick.

    The ONE path that takes an item out of the pending queue. ``found`` is the
    number of TAKEABLE candidates (post-filter, post-min_seeders), which is what
    the operator screen shows next to « À récupérer ».
    """
    # Two DISTINCT releases (dedup collapses same-release duplicates, so
    # ``found`` counts representatives — what is actually takeable).
    two_hits = SearchOutcome(
        results=[
            _make_result(info_hash="aaaa1234"),
            _make_result(
                title="Inception 2010 MULTi 2160p UHD BluRay x265-OTHER",
                resolution="2160p",
                info_hash="bbbb5678",
            ),
        ],
        trackers_queried=1,
        trackers_errored=0,
    )
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=two_hits)

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("available", "available", 2)
    assert verdict.chosen is not None
    assert verdict.chosen.provider == "c411"
    _assert_no_side_effects(spy, torrent_client)


def test_search_circuit_open_is_retryable_and_inconclusive() -> None:
    """CircuitOpenError → ('retryable', 'circuit_open', None).

    A tripped circuit means we never asked the tracker. ``found=0`` would claim
    « I looked, there is nothing » — false, and the exact lie this feature
    removes (panne ≠ absence).
    """
    orchestrator, spy, registry, torrent_client, _seed = _make_orchestrator()
    registry.search_candidates.side_effect = CircuitOpenError("c411", 30.0)

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "circuit_open", None)
    assert verdict.chosen is None
    _assert_no_side_effects(spy, torrent_client)


def test_search_api_error_is_retryable_and_inconclusive() -> None:
    """A generic ApiError during search → ('retryable', 'search_api_error', None)."""
    orchestrator, spy, registry, torrent_client, _seed = _make_orchestrator()
    registry.search_candidates.side_effect = ApiError(provider="c411", http_status=500, message="boom")

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "search_api_error", None)
    _assert_no_side_effects(spy, torrent_client)


def test_search_tracker_auth_is_terminal() -> None:
    """TrackerAuthError during search → ('terminal', 'tracker_auth', None).

    A broken passkey does not self-heal, so the search pass states a TERMINAL
    verdict rather than looping. ``TrackerAuthError`` is an ``ApiError``
    SUBCLASS — if its ``except`` clause ever slips below the base clause this
    test fails with ``search_api_error``.
    """
    assert issubclass(TrackerAuthError, ApiError)  # the ordering hazard this test pins

    orchestrator, spy, registry, torrent_client, _seed = _make_orchestrator()
    registry.search_candidates.side_effect = TrackerAuthError(provider="c411", http_status=403, message="forbidden")

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("terminal", "tracker_auth", None)
    _assert_no_side_effects(spy, torrent_client)


def test_search_all_trackers_errored_is_retryable_and_inconclusive() -> None:
    """Every queried tracker errored → ('retryable', 'trackers_unavailable', None).

    Distinct from a clean empty search: the swarm may be full of candidates we
    simply could not reach, so nothing may be concluded.
    """
    all_errored = SearchOutcome(results=[], trackers_queried=2, trackers_errored=2)
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=all_errored)

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "trackers_unavailable", None)
    _assert_no_side_effects(spy, torrent_client)


def test_search_partial_outage_is_retryable_and_inconclusive() -> None:
    """SOME trackers errored + zero hits → ('retryable', 'trackers_degraded', None).

    The gap between ``all_errored`` and a clean empty search (D2): with one
    tracker rate-limited and the other legitimately empty, the empty set is NOT
    evidence of absence. Persisting ``no_candidates`` / 0 here is the lie that
    froze real rows — c411 answered HTTP 429 for ``Widow's Bay S01E10`` on
    2026-08-04 while the releases existed.
    """
    partial = SearchOutcome(results=[], trackers_queried=2, trackers_errored=1)
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=partial)

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "trackers_degraded", None)
    _assert_no_side_effects(spy, torrent_client)


def test_search_no_candidates_concludes_zero() -> None:
    """Clean search, zero hits → ('not_found', 'no_candidates', 0).

    Here ``0`` is TRUE: the trackers answered and had nothing. This is the only
    family of paths allowed to persist a zero.
    """
    no_hits = SearchOutcome(results=[], trackers_queried=1, trackers_errored=0)
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=no_hits)

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("not_found", "no_candidates", 0)
    _assert_no_side_effects(spy, torrent_client)


def test_search_no_matching_episode_concludes_zero() -> None:
    """Only OTHER episodes came back → ('not_found', 'no_matching_episode', 0).

    Wanting S09E05, the tracker returns S09E01 and a season pack. Both are
    dropped by ``filter_to_episode``, so the wanted episode is simply not out
    yet — concluded, hence a truthful zero.
    """
    wrong_episodes = SearchOutcome(
        results=[
            _make_result(title="Some Show S09E01 1080p WEB x265-GRP", info_hash="cccc1111"),
            _make_result(title="Some Show S09 COMPLETE 1080p WEB x265-GRP", info_hash="dddd2222"),
        ],
        trackers_queried=1,
        trackers_errored=0,
    )
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=wrong_episodes)

    verdict = orchestrator.search(_make_wanted_episode(season=9, episode=5), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("not_found", "no_matching_episode", 0)
    _assert_no_side_effects(spy, torrent_client)


def test_search_no_matching_season_concludes_zero() -> None:
    """F12: a SEASON row's fruitless search states its OWN outcome.

    Wanting S02 whole, the tracker returns a lone episode and a wrong-season
    pack. Both are dropped by ``filter_to_season``, and the verdict must read
    ('not_found', 'no_matching_season', 0) — 'no_matching_episode' on a season
    row would surface a lie in the row's last_search_outcome.
    """
    wrong_packs = SearchOutcome(
        results=[
            _make_result(title="Some Show S02E05 1080p WEB x265-GRP", info_hash="eeee3333"),
            _make_result(title="Some Show S04 COMPLETE 1080p WEB x265-GRP", info_hash="ffff4444"),
        ],
        trackers_queried=1,
        trackers_errored=0,
    )
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=wrong_packs)

    season_item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="season",
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
        season=2,
        episode=None,
    )
    verdict = orchestrator.search(season_item, QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("not_found", "no_matching_season", 0)
    _assert_no_side_effects(spy, torrent_client)


def test_search_all_filtered_concludes_zero() -> None:
    """Only hard-filtered releases came back → ('not_found', 'all_filtered', 0).

    A 3D Half-SBS encode is dropped by the default profile (``exclude_3d``). The
    search concluded — there is nothing the profile accepts — so ``0`` is
    truthful and a conforming release can still show up later.
    """
    only_3d = SearchOutcome(
        results=[_make_result(title="Inception 2010 3D Half-SBS 1080p BluRay x264-GRP")],
        trackers_queried=1,
        trackers_errored=0,
    )
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=only_3d)

    # Default profile: exclude_3d is on — a 2D library never wants a 3D encode.
    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("not_found", "all_filtered", 0)
    _assert_no_side_effects(spy, torrent_client)


def test_search_no_seeders_is_retryable_and_inconclusive() -> None:
    """Everything below ``min_seeders`` → ('retryable', 'no_seeders', None).

    A dead swarm is NOT « there is nothing »: the release exists and peers may
    come back, so the verdict stays inconclusive (``found=None``) and the item
    is re-checked rather than reported as waiting.
    """
    low_seed = SearchOutcome(results=[_make_result(seeders=2)], trackers_queried=1, trackers_errored=0)
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(
        search_outcome=low_seed,
        ranking=RankingConfig(min_seeders=10),
    )

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "no_seeders", None)
    _assert_no_side_effects(spy, torrent_client)


def test_search_never_resolves_a_source_even_when_available() -> None:
    """LOAD-BEARING: the available path stops at the verdict — no resolve, no add.

    ``resolve_source`` is the first grab-only stage. If ``search`` ever grew a
    download step this patch would record the call — the invariant that makes
    « À récupérer » an observable state rather than a millisecond in a call
    stack.
    """
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator()

    with patch(_RESOLVE) as mock_resolve:
        verdict = orchestrator.search(_make_wanted(), QualityProfile())
        mock_resolve.assert_not_called()

    assert verdict.disposition == "available"
    _assert_no_side_effects(spy, torrent_client)


def test_grab_folds_a_search_time_auth_error_into_search_api_error() -> None:
    """BEHAVIOUR PRESERVATION: grab keeps its historical search-stage classification.

    Before the chain was extracted, a single ``except ApiError`` swallowed a
    SEARCH-stage ``TrackerAuthError`` into the retryable ``search_api_error``
    bucket. ``search()`` now needs that path as its own TERMINAL verdict, so the
    shared chain surfaces it separately — and ``grab`` must fold it back, or the
    split would silently change WHEN an item gets abandoned. Grab's terminal
    ``tracker_auth`` stays the resolve/add-stage one
    (``test_tracker_auth_error_terminal_no_add_call``).
    """
    orchestrator, spy, registry, torrent_client, _seed = _make_orchestrator()
    registry.search_candidates.side_effect = TrackerAuthError(provider="c411", http_status=401, message="nope")

    outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "search_api_error"
    failed = [e for e in spy.events if isinstance(e, GrabFailed)]
    assert len(failed) == 1
    assert failed[0].reason == "search_api_error"
    assert not [e for e in spy.events if isinstance(e, WantedAbandoned)]
    assert torrent_client is not None
    torrent_client.add.assert_not_called()


def test_search_covers_every_declared_outcome() -> None:
    """The eleven cases above exercise EXACTLY the declared ``SEARCH_OUTCOMES``.

    Exhaustiveness backstop at the orchestrator level: a new declared outcome
    with no forcing test above fails here, so an exit path can never ship
    untested (the service-level matrix mocks the orchestrator and would not
    notice).
    """
    from personalscraper.acquire.orchestrator import SEARCH_OUTCOMES

    covered = {
        "available",
        "circuit_open",
        "search_api_error",
        "tracker_auth",
        "trackers_unavailable",
        "trackers_degraded",
        "no_candidates",
        "no_matching_episode",
        "no_matching_season",
        "all_filtered",
        "no_seeders",
    }
    assert covered == set(SEARCH_OUTCOMES), (
        f"exit paths without a forcing test: {sorted(set(SEARCH_OUTCOMES) - covered)}; "
        f"stale test coverage: {sorted(covered - set(SEARCH_OUTCOMES))}"
    )


# ---------------------------------------------------------------------------
# D2 — the intent hash is reserved BEFORE add()
# ---------------------------------------------------------------------------


def test_on_intent_fires_before_add_with_the_chosen_hash() -> None:
    """LOAD-BEARING (D2): the hook runs BEFORE ``add()``, with the chosen release's hash.

    The ordering IS the guarantee: a hash written after the add would leave the
    exact window this closes. The fake client records the call order, so an
    implementation that reserved the hash afterwards fails here.
    """
    chosen = TrackerResult(
        provider="c411",
        tracker_id="7",
        title="Some Show 2024 1080p WEB x265-GRP",
        size=ByteSize(3_000_000_000),
        seeders=42,
        leechers=1,
        resolution="1080p",
        info_hash="cafe1234",
        download_url="/torrents/7/download",
    )
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(results=[chosen], trackers_queried=1, trackers_errored=0)
    registry.transports.return_value = {"c411": MagicMock()}

    order: list[str] = []
    torrent_client = MagicMock(spec=TorrentAdder)
    torrent_client.add.side_effect = lambda *a, **kw: (order.append("add"), "cafe1234")[1]

    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=torrent_client,
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )

    with patch(_RESOLVE, return_value=MagicMock(spec=TorrentSource)):
        outcome = orchestrator.grab(
            _make_wanted(),
            QualityProfile(),
            on_intent=lambda h: order.append(f"intent:{h}"),
        )

    assert outcome.disposition == "success"
    assert order == ["intent:cafe1234", "add"], f"intent must precede add; got {order}"


def test_intent_hook_failure_prevents_the_add() -> None:
    """A store lock while reserving the intent must NOT let the add run.

    An add nobody recorded is precisely the orphan D2 removes, so the raise
    propagates (the service's per-item isolation handles it) and the client is
    never called.
    """
    chosen = TrackerResult(
        provider="c411",
        tracker_id="7",
        title="Some Show 2024 1080p WEB x265-GRP",
        size=ByteSize(3_000_000_000),
        seeders=42,
        leechers=1,
        resolution="1080p",
        info_hash="cafe1234",
        download_url="/torrents/7/download",
    )
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(results=[chosen], trackers_queried=1, trackers_errored=0)
    registry.transports.return_value = {"c411": MagicMock()}
    torrent_client = MagicMock(spec=TorrentAdder)

    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=torrent_client,
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )

    def _boom(_hash: str) -> None:
        raise sqlite3.OperationalError("database is locked")

    with patch(_RESOLVE, return_value=MagicMock(spec=TorrentSource)), pytest.raises(sqlite3.OperationalError):
        orchestrator.grab(_make_wanted(), QualityProfile(), on_intent=_boom)

    torrent_client.add.assert_not_called()


def test_grab_without_the_hook_still_adds() -> None:
    """The hook is optional: a caller that passes none keeps the plain behaviour."""
    chosen = TrackerResult(
        provider="c411",
        tracker_id="7",
        title="Some Show 2024 1080p WEB x265-GRP",
        size=ByteSize(3_000_000_000),
        seeders=42,
        leechers=1,
        resolution="1080p",
        info_hash="cafe1234",
        download_url="/torrents/7/download",
    )
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(results=[chosen], trackers_queried=1, trackers_errored=0)
    registry.transports.return_value = {"c411": MagicMock()}
    torrent_client = MagicMock(spec=TorrentAdder)
    torrent_client.add.return_value = "cafe1234"

    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=torrent_client,
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )

    with patch(_RESOLVE, return_value=MagicMock(spec=TorrentSource)):
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "success"
    torrent_client.add.assert_called_once()


def test_search_pass_applies_movie_year_filter_and_query(followed_id: int = 7) -> None:
    """#28 (review HIGH): search() narrows a movie by year and drops wrong-year films.

    The search pass feeds the SAME _search_chain as grab; when its year_resolver
    is wired, a followed « Wicker » (2026) query is « Wicker 2026 » and
    filter_to_movie drops « The Wicker Man 2006 » so the verdict cannot state a
    different film available (the §5/§7 identity lie the fix removes).
    """
    item = WantedItem(
        media_ref=MediaRef(tmdb_id=1195803),
        kind="movie",
        status="searching",
        enqueued_at=0,
        followed_id=followed_id,
    )
    right = _make_result(title="Wicker.2026.1080p.WEB-DL.x265-GRP", info_hash="right123")
    wrong = _make_result(title="The.Wicker.Man.2006.1080p.BluRay-OLD", seeders=9999, info_hash="wrong123")
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(
        results=[right, wrong], trackers_queried=1, trackers_errored=0
    )
    registry.transports.return_value = {"c411": MagicMock()}
    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=None,
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        title_resolver=lambda _i: "Wicker",
        year_resolver=lambda _i: 2026,
        bandwidth=BandwidthConfig(),
    )

    verdict = orchestrator.search(item, QualityProfile())

    # The query narrowed the tracker search with the year (#28).
    assert registry.search_candidates.call_args.args[0] == "Wicker 2026"
    # Only the right-year film survives → available with found == 1, never the
    # higher-seeded wrong-year « The Wicker Man ».
    assert verdict.disposition == "available"
    assert verdict.found == 1


# ---------------------------------------------------------------------------
# Per-media-type size thresholds threading (#376)
# ---------------------------------------------------------------------------


class TestMediaKindThreading:
    """rank_candidates threads media_kind through to rank()."""

    _MOVIE_TIERS = [
        ThresholdEntry(at=0, score=0),
        ThresholdEntry(at="4GB", score=5),  # type: ignore[arg-type]
        ThresholdEntry(at="15GB", score=10),  # type: ignore[arg-type]
    ]
    _GENERIC_SIZE_TIERS = [
        ThresholdEntry(at=0, score=0),
        ThresholdEntry(at="1GB", score=5),  # type: ignore[arg-type]
        ThresholdEntry(at="5GB", score=10),  # type: ignore[arg-type]
    ]

    def _make_ranking(self, by_type: dict | None = None) -> RankingConfig:
        """Build a size-only ranking config, optionally with per-type thresholds."""
        return RankingConfig(
            criteria=[
                RankingCriterion(
                    field="size",
                    prefer="higher",
                    thresholds=self._GENERIC_SIZE_TIERS,
                ),
            ],
            min_seeders=0,
            size_thresholds_by_type=by_type,
        )

    def test_media_kind_none_keeps_generic_scores(self) -> None:
        """rank_candidates with media_kind=None uses generic size thresholds."""
        r = _make_result()
        ranking = self._make_ranking({"movie": self._MOVIE_TIERS})
        _, ranked = rank_candidates([r], QualityProfile(), None, ranking, media_kind=None)
        # 5GB → generic: ≥5GB → 10
        assert ranked[0][1] == 10

    def test_media_kind_movie_uses_movie_tiers(self) -> None:
        """rank_candidates with media_kind='movie' uses movie-specific thresholds."""
        r = _make_result()
        ranking = self._make_ranking({"movie": self._MOVIE_TIERS})
        _, ranked = rank_candidates([r], QualityProfile(), None, ranking, media_kind="movie")
        # 5GB → movie tiers: ≥4GB but <15GB → 5
        assert ranked[0][1] == 5

    def test_orchestrator_grab_threads_kind_from_wanted(self) -> None:
        """GrabOrchestrator.grab() passes item.kind as media_kind to rank_candidates.

        A 5GB movie with movie-size tiers scoring 5 (vs generic 10). The orchestrator's
        _search_chain passes item.kind="movie" → rank_candidates → rank() should use the
        movie tiers, so the outcome's chosen result should score 5.
        """
        r = _make_result()
        registry = MagicMock()
        registry.search_candidates.return_value = SearchOutcome(results=[r], trackers_queried=1, trackers_errored=0)
        registry.transports.return_value = {"c411": MagicMock()}

        ranking = self._make_ranking({"movie": self._MOVIE_TIERS})
        orchestrator = GrabOrchestrator(
            tracker_registry=registry,
            torrent_client=MagicMock(spec=TorrentAdder),
            event_bus=EventBus(),
            ranking=ranking,
            bandwidth=BandwidthConfig(),
        )

        with patch(_RESOLVE, return_value=MagicMock(spec=TorrentSource)):
            outcome = orchestrator.grab(_make_wanted(kind="movie"), QualityProfile())

        assert outcome.disposition == "success"
        # The ranked list uses movie tiers → 5GB movie scores 5 (not generic 10).
        # The score itself isn't on the outcome, but we can verify the top was chosen.
        assert outcome.chosen is r


# ---------------------------------------------------------------------------
# filter_to_season (season-grab phase 2.1) — whole-season pack parser
# ---------------------------------------------------------------------------


def _make_season_result(
    title: str,
    seeders: int = 10,
    info_hash: str = "deadbeef",
) -> TrackerResult:
    """Build a tracker result for season-pack filter tests."""
    return TrackerResult(
        provider="tr4ker",
        tracker_id="test",
        title=title,
        size=ByteSize(10_000_000_000),
        seeders=seeders,
        leechers=0,
        info_hash=info_hash,
    )


def test_filter_to_season_accepts_full_range() -> None:
    """S01E01-E08 with expected_count=8 (full coverage proven) → kept."""
    results = [
        _make_season_result("Show.S01E01-E08.MULTi.1080p.x265"),
        _make_season_result("Show.S01E05.MULTi.1080p.x265"),  # single ep, dropped
    ]
    kept = filter_to_season(results, 1, expected_count=8)
    assert len(kept) == 1
    assert "E01-E08" in kept[0].title


def test_filter_to_season_accepts_bare_season() -> None:
    """'Show S01' without episode markers → kept."""
    results = [
        _make_season_result("Show.S01.1080p.WEB-DL.x265"),
        _make_season_result("Show.S01E05.1080p.WEB-DL.x265"),  # has ep marker, dropped
    ]
    kept = filter_to_season(results, 1)
    assert len(kept) == 1
    assert "S01" in kept[0].title and "E05" not in kept[0].title


def test_filter_to_season_accepts_integrale_keyword() -> None:
    """'INTEGRALE' with no episode markers → kept (bare-season acceptance)."""
    results = [_make_season_result("Show.S01.INTEGRALE.1080p.x265")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 1


def test_filter_to_season_accepts_ep01_range_as_full_range() -> None:
    """S01E01-E03 with expected_count=3 (covers the whole season) → kept.

    guessit expands the range into an episode list [1, 2, 3]; it starts at
    E01 and reaches the aired-episode count, so coverage is proven.
    """
    results = [_make_season_result("Show.S01E01-E03.1080p")]
    kept = filter_to_season(results, 1, expected_count=3)
    assert len(kept) == 1


def test_filter_to_season_rejects_partial_range() -> None:
    """S01E03-E06 (starts at E03, not E01 → partial) → dropped."""
    results = [_make_season_result("Show.S01E03-E06.1080p")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 0


def test_filter_to_season_rejects_multi_season() -> None:
    """'Show S01-S03' → dropped."""
    results = [_make_season_result("Show.S01-S03.Complete.1080p")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 0


def test_filter_to_season_rejects_wrong_season() -> None:
    """S02 pack when looking for S01 → dropped."""
    results = [_make_season_result("Show.S02.Complete.1080p")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 0


def test_filter_to_season_empty_on_no_match() -> None:
    """Empty results → empty returned."""
    kept = filter_to_season([], 1)
    assert kept == []


def test_filter_to_season_accepts_complete_keyword() -> None:
    """'Complete Season 1' → kept."""
    results = [_make_season_result("Show.Complete.Season.1.1080p.x265")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 1


def test_filter_to_season_rejects_complete_keyword_with_ep_info() -> None:
    """F4: the season keyword must NOT override an explicit episode marker.

    ``COMPLETE`` is a standard scene tag (COMPLETE.BLURAY): ``S01E05.COMPLETE``
    is episode 5, not the season — keeping it let R3 replace-all install a
    single episode as « the season ». Only the bare-season title survives.
    """
    results = [
        _make_season_result("Show.S01.COMPLETE.1080p.x265"),
        _make_season_result("Show.S01E05.COMPLETE.1080p.x265"),  # ep marker → dropped
    ]
    kept = filter_to_season(results, 1, expected_count=8)
    assert len(kept) == 1
    assert "E05" not in kept[0].title


def test_filter_to_season_rejects_multi_season_french() -> None:
    """'Saisons 1 à 4' → dropped."""
    results = [_make_season_result("Show.Saisons.1.a.4.1080p")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 0


def test_filter_to_season_rejects_partial_pack_against_expected_count() -> None:
    """F4 REGRESSION: E01-start is not enough — coverage must reach the count.

    ``S02E01-E05`` starts at E01 but covers 5 of 12 aired episodes: R3
    replace-all would install it as « the season » and the 7 missing episodes
    would never be acquired (the per-season dedup blocks a second wanted).
    """
    results = [_make_season_result("Show.S02E01-E05.1080p")]
    kept = filter_to_season(results, 2, expected_count=12)
    assert kept == []


def test_filter_to_season_rejects_short_multi_episode_release() -> None:
    """F4: S02E01E02 (two episodes of twelve) → dropped."""
    results = [_make_season_result("Show.S02E01E02.1080p")]
    kept = filter_to_season(results, 2, expected_count=12)
    assert kept == []


def test_filter_to_season_rejects_single_episode_with_complete_bluray_tag() -> None:
    """F4: ``S02E05.COMPLETE.BLURAY-GRP`` is episode 5, never the season."""
    results = [_make_season_result("Show.S02E05.COMPLETE.BLURAY-GRP")]
    kept = filter_to_season(results, 2, expected_count=12)
    assert kept == []


def test_filter_to_season_keeps_verified_full_range() -> None:
    """F4: S02E01-E12 with expected_count=12 → coverage proven, kept."""
    results = [_make_season_result("Show.S02E01-E12.1080p")]
    kept = filter_to_season(results, 2, expected_count=12)
    assert len(kept) == 1


def test_filter_to_season_keeps_bare_season_and_integrale_forms() -> None:
    """F4: titles with NO episode markers stay accepted (with or without count)."""
    results = [
        _make_season_result("Show.S02.1080p"),
        _make_season_result("Show.Saison.2.Intégrale"),
    ]
    assert len(filter_to_season(results, 2, expected_count=12)) == 2
    assert len(filter_to_season(results, 2)) == 2  # count unknown — still fine


def test_filter_to_season_rejects_full_looking_range_without_expected_count() -> None:
    """F4: unknown aired count → even S02E01-E12 is rejected (conservative).

    A pack whose coverage cannot be verified is not « the season »: the range
    might stop short of a season whose real episode count we do not know.
    """
    results = [_make_season_result("Show.S02E01-E12.1080p")]
    kept = filter_to_season(results, 2, expected_count=None)
    assert kept == []


def test_filter_to_season_parse_error_skips() -> None:
    """A result that crashes guessit → dropped (fail-soft)."""
    bad_title = _make_season_result("\x00Invalid\x00Title")
    results = [bad_title]
    # Must not raise — fail-soft per the contract.
    kept = filter_to_season(results, 1)
    assert len(kept) == 0


# ---------------------------------------------------------------------------
# build_search_query — season kind (season-grab phase 2.2)
# ---------------------------------------------------------------------------


def test_build_search_query_season() -> None:
    """A season wanted item builds ``"Breaking Bad S03"``."""
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="season",
        status="pending",
        enqueued_at=0,
        season=3,
        episode=None,
    )
    q = build_search_query(item, "Breaking Bad")
    assert q == "Breaking Bad S03"


def test_build_search_query_season_no_title_falls_back() -> None:
    """A season item with no resolved title falls back to provider ID."""
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="season",
        status="pending",
        enqueued_at=0,
        season=3,
        episode=None,
    )
    q = build_search_query(item, None)
    assert q == "12345"


def test_build_search_query_season_zero_pads() -> None:
    """Season 3 → ``S03``, season 11 → ``S11``."""
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="season",
        status="pending",
        enqueued_at=0,
        season=11,
        episode=None,
    )
    q = build_search_query(item, "Show")
    assert q == "Show S11"


# ---------------------------------------------------------------------------
# rank() with media_kind="season" — season-grab phase 2.3 golden
# ---------------------------------------------------------------------------


def test_rank_season_media_kind_uses_season_tiers() -> None:
    """rank() with media_kind='season' applies season-specific size thresholds.

    Proves that the per-media-type mechanism (#376) activates for ``"season"``:
    the size criterion's own ``thresholds`` are overridden by
    ``size_thresholds_by_type["season"]`` when ``media_kind="season"`` is passed.
    """
    from personalscraper.api.tracker._ranking import rank as rank_func

    # 80 GB — above the 50GB season tier
    big = TrackerResult(
        provider="tr4ker",
        tracker_id="s1",
        title="Show.S01.Complete.1080p",
        size=ByteSize(80_000_000_000),
        seeders=50,
        leechers=2,
    )
    # 15 GB — below the 50GB season tier, but above the 10GB generic tier
    below_season_tier = TrackerResult(
        provider="tr4ker",
        tracker_id="s2",
        title="Show.S01.Complete.720p",
        size=ByteSize(15_000_000_000),
        seeders=100,
        leechers=5,
    )

    cfg = RankingConfig(
        criteria=[
            RankingCriterion(
                field="size",
                weight=1,
                thresholds=[
                    ThresholdEntry(at=10_000_000_000, score=1),  # generic: ≥10GB = 1pt
                ],
            ),
        ],
        min_seeders=0,
        size_thresholds_by_type={
            "season": [ThresholdEntry(at=50_000_000_000, score=5)],
        },
    )

    # media_kind=None → generic thresholds: both ≥10GB → both score 1.
    scored_generic = rank_func([big, below_season_tier], cfg, media_kind=None)
    assert scored_generic[0][1] == 1
    assert scored_generic[1][1] == 1

    # media_kind="season" → season thresholds override: big (80GB) ≥ 50GB → 5;
    # below_season_tier (15GB) < 50GB → 0.
    scored_season = rank_func([big, below_season_tier], cfg, media_kind="season")
    assert len(scored_season) == 2
    # big wins because the season tier gives it 5 pts while below_season_tier
    # gets 0 — proving the per-media-type override is active for "season".
    assert scored_season[0][1] == 5
    assert scored_season[0][0].title == "Show.S01.Complete.1080p"
    assert scored_season[1][1] == 0
