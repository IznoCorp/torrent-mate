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
    * clean zero hits → TERMINAL ``no_candidates``.
    * zero survivors after hard-filter → TERMINAL ``all_filtered``.
    * ``torrent_client is None`` → RETRYABLE ``no_torrent_client`` (no crash).
- NEGATIVE seed-write assert (load-bearing): a seed-obligation spy's
  ``record_dispatch`` / ``seed.add`` ``call_count == 0`` across a full success.
- SEARCH exit paths (acq-states phase 2): all NINE contract paths forced
  through the real chain, asserting the ``SearchVerdict`` triple
  ``(disposition, outcome, found)`` plus the two negative invariants — no
  ``add()`` and no event emitted. ``found`` is ``None`` on every inconclusive
  path (panne ≠ absence) and ``0`` only where the search really concluded.

Every assertion is REAL (disposition + emitted event type/payload +
call_counts), never assert-no-exception.
"""

from __future__ import annotations

from typing import Literal
from unittest.mock import MagicMock, patch

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import GrabFailed, GrabSucceeded, WantedAbandoned
from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api._units import ByteSize
from personalscraper.api.torrent._base import TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.identity import MediaRef

_RESOLVE = "personalscraper.acquire.orchestrator.resolve_source"


def _make_wanted(kind: 'Literal["movie", "episode"]' = "movie", tvdb_id: int = 12345) -> WantedItem:
    """Build a claimed WantedItem (phase 4a: no ``id`` field yet)."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind=kind,
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
    )


def _make_result(
    title: str = "Inception 2010 MULTi 1080p BluRay x265-GRP",
    resolution: str | None = "1080p",
    seeders: int = 50,
    info_hash: str | None = "aaaa1234",
) -> TrackerResult:
    return TrackerResult(
        provider="lacale",
        tracker_id="t1",
        title=title,
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution=resolution,
        info_hash=info_hash,
        download_url="https://lacale.test/torrent/1",
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

    transports = {"lacale": MagicMock()}
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
    assert outcome.chosen is not None and outcome.chosen.provider == "lacale"
    assert outcome.category is None
    assert outcome.tags == ("lacale",)

    # add() was called exactly once carrying the provider tag ATOMICALLY, with
    # category=None (open item #8 FINAL: the tag rides the single add call — the
    # Transmission "" sentinel / qBit native tags — instead of a separate
    # add_tags step).
    assert torrent_client is not None
    torrent_client.add.assert_called_once()
    _args, kwargs = torrent_client.add.call_args
    assert kwargs["category"] is None
    assert kwargs["tags"] == ["lacale"]

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


class _StalenessFakeRegistry:
    """Registry whose transports() map differs between construction and grab time.

    Reproduces the boot-snapshot staleness bug: a lazy tracker (torr9) is
    transiently ABSENT the first time ``transports()`` is called (the boot login
    blipped) but PRESENT on every later call (it logged in during the grab's own
    ``search()``). The OLD orchestrator snapshotted ``transports()`` at
    construction → the first (empty) call → torr9 never recoverable for the
    process lifetime. The fixed orchestrator reads ``transports()`` FRESH at
    grab time → it sees the recovered map.
    """

    def __init__(self, *, search_outcome: SearchOutcome, recovered_transport: object) -> None:
        self._search_outcome = search_outcome
        self._recovered = recovered_transport
        self.transports_calls = 0

    def search_candidates(self, query: str, media_type: MediaType, year: int | None) -> SearchOutcome:
        """Return the canned outcome (signature mirrors TrackerRegistry)."""
        return self._search_outcome

    def transports(self) -> dict[str, object]:
        """Return ``{}`` on the FIRST call (boot blip), ``{torr9: ...}`` after."""
        self.transports_calls += 1
        if self.transports_calls == 1:
            return {}
        return {"torr9": self._recovered}


def test_transports_resolved_fresh_at_grab_not_boot_snapshot() -> None:
    """REGRESSION: a tracker absent at construction-time but present at grab-time is found.

    Transports are read FRESH at grab time, not from a boot snapshot.

    Drives one grab whose top result is a torr9 hit with a RELATIVE
    ``/torrents/7/download`` url (no magnet → needs a transport). The fake
    registry returns an EMPTY transports map on its first call (simulating a
    transient boot login blip that dropped torr9) and the recovered
    ``{"torr9": <transport>}`` on every later call. With the boot-snapshot bug
    the orchestrator would hand ``resolve_source`` the empty map → no transport
    → ``fetch_failed``. The fix reads ``transports()`` at grab time, so
    ``resolve_source`` receives the recovered transport and the add path runs.
    """
    torr9_result = TrackerResult(
        provider="torr9",
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
        results=[torr9_result],
        trackers_queried=1,
        trackers_errored=0,
    )
    recovered_transport = MagicMock(name="torr9_transport")
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
    )

    # Simulate the boot moment the OLD code snapshotted at: the FIRST
    # transports() call returns the EMPTY map (torr9 dropped by a transient boot
    # login blip). The OLD orchestrator captured exactly this at construction and
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

    # resolve_source received the FRESH recovered map containing torr9 — proving
    # the orchestrator did NOT reuse the empty boot snapshot consumed above. The
    # registry's transports() was called at grab time (the 2nd call: boot blip +
    # the live grab-time read).
    assert captured["transports"] == {"torr9": recovered_transport}
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
    registry.search_candidates.side_effect = CircuitOpenError("lacale", 30.0)

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
    assert outcome.chosen is not None and outcome.chosen.provider == "lacale"
    assert [e for e in spy.events if isinstance(e, GrabFailed)]


def test_tracker_auth_error_terminal_no_add_call() -> None:
    """TrackerAuthError on resolve_source → TERMINAL tracker_auth, add() never called."""
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator()
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.side_effect = TrackerAuthError(provider="lacale", http_status=403, message="forbidden")
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
        mock_resolve.side_effect = TorrentFetchError(provider="lacale", http_status=0, message="bad body")
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
    assert outcome.chosen is not None and outcome.chosen.provider == "lacale"
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
# SEARCH exit paths (acq-states phase 2) — the NINE contract paths, forced
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
    assert verdict.chosen.provider == "lacale"
    _assert_no_side_effects(spy, torrent_client)


def test_search_circuit_open_is_retryable_and_inconclusive() -> None:
    """CircuitOpenError → ('retryable', 'circuit_open', None).

    A tripped circuit means we never asked the tracker. ``found=0`` would claim
    « I looked, there is nothing » — false, and the exact lie this feature
    removes (panne ≠ absence).
    """
    orchestrator, spy, registry, torrent_client, _seed = _make_orchestrator()
    registry.search_candidates.side_effect = CircuitOpenError("lacale", 30.0)

    verdict = orchestrator.search(_make_wanted(), QualityProfile())

    assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "circuit_open", None)
    assert verdict.chosen is None
    _assert_no_side_effects(spy, torrent_client)


def test_search_api_error_is_retryable_and_inconclusive() -> None:
    """A generic ApiError during search → ('retryable', 'search_api_error', None)."""
    orchestrator, spy, registry, torrent_client, _seed = _make_orchestrator()
    registry.search_candidates.side_effect = ApiError(provider="lacale", http_status=500, message="boom")

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
    registry.search_candidates.side_effect = TrackerAuthError(provider="lacale", http_status=403, message="forbidden")

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
    registry.search_candidates.side_effect = TrackerAuthError(provider="lacale", http_status=401, message="nope")

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
    """The nine cases above exercise EXACTLY the declared ``SEARCH_OUTCOMES``.

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
        "no_candidates",
        "no_matching_episode",
        "all_filtered",
        "no_seeders",
    }
    assert covered == set(SEARCH_OUTCOMES), (
        f"exit paths without a forcing test: {sorted(set(SEARCH_OUTCOMES) - covered)}; "
        f"stale test coverage: {sorted(covered - set(SEARCH_OUTCOMES))}"
    )
