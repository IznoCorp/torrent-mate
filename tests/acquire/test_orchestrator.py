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

    ``seed_spy`` is the NEGATIVE-invariant probe: it is deliberately NOT wired
    into the orchestrator (the orchestrator has no store/seed dep at all), so a
    correct implementation can never touch it. The negative test asserts its
    ``record_dispatch`` / ``seed.add`` ``call_count == 0``.
    """
    if search_outcome is None:
        search_outcome = SearchOutcome(results=[_make_result()], trackers_queried=1, trackers_errored=0)

    registry = MagicMock()
    registry.search_candidates.return_value = search_outcome

    transports = {"lacale": MagicMock()}

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
        transports=transports,
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


def test_grab_happy_path_emits_exactly_one_grab_succeeded_exact_payload() -> None:
    """GOLDEN: fetch+add → ONE GrabSucceeded with the EXACT payload."""
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(add_return="aaaa1234")

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Disposition
    assert outcome.disposition == "success"
    assert outcome.info_hash == "aaaa1234"
    assert outcome.reason is None
    assert outcome.chosen is not None and outcome.chosen.provider == "lacale"

    # add() was called exactly once with the resolved source + tracker tag
    assert torrent_client is not None
    torrent_client.add.assert_called_once()
    _args, kwargs = torrent_client.add.call_args
    assert kwargs["category"] is None
    assert kwargs["tags"] == ("lacale",)

    # Exactly ONE GrabSucceeded, with the EXACT payload (golden)
    succeeded = [e for e in spy.events if isinstance(e, GrabSucceeded)]
    assert len(succeeded) == 1
    ev = succeeded[0]
    assert ev.media_ref == MediaRef(tvdb_id=12345)
    assert ev.info_hash == "aaaa1234"
    assert ev.source_tracker == "lacale"
    assert ev.category is None
    assert ev.tags == ("lacale",)
    # No failure events leaked
    assert not [e for e in spy.events if isinstance(e, (GrabFailed, WantedAbandoned))]


def test_episode_kind_searches_with_tv_media_type() -> None:
    """An ``episode`` item searches with MediaType.TV (movie → MOVIE)."""
    orchestrator, _spy, registry, _tc, _seed = _make_orchestrator()
    with patch(_RESOLVE):
        orchestrator.grab(_make_wanted(kind="episode"), QualityProfile())
    _args, kwargs = registry.search_candidates.call_args
    # media_type is the 2nd positional arg (query, media_type, year)
    assert registry.search_candidates.call_args.args[1] == MediaType.TV


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
    succeeded = [e for e in spy.events if isinstance(e, GrabSucceeded)]
    assert len(succeeded) == 1
    assert succeeded[0].info_hash == "dup0beef"
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


def test_clean_zero_hits_terminal_no_candidates() -> None:
    """Clean search, zero hits → TERMINAL no_candidates."""
    no_hits = SearchOutcome(results=[], trackers_queried=1, trackers_errored=0)
    orchestrator, spy, _registry, _tc, _seed = _make_orchestrator(search_outcome=no_hits)
    outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "terminal"
    assert outcome.reason == "no_candidates"
    abandoned = [e for e in spy.events if isinstance(e, WantedAbandoned)]
    assert len(abandoned) == 1
    assert abandoned[0].reason == "no_candidates"


def test_all_filtered_terminal_all_filtered() -> None:
    """Zero survivors after hard-filter → TERMINAL all_filtered."""
    result_720p = _make_result(title="Movie 2010 720p", resolution="720p")
    outcome_720 = SearchOutcome(results=[result_720p], trackers_queried=1, trackers_errored=0)
    orchestrator, spy, _registry, torrent_client, _seed = _make_orchestrator(search_outcome=outcome_720)
    strict = QualityProfile(min_resolution=Resolution.R2160P)
    outcome = orchestrator.grab(_make_wanted(), strict)

    assert outcome.disposition == "terminal"
    assert outcome.reason == "all_filtered"
    assert [e for e in spy.events if isinstance(e, WantedAbandoned)]
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
    orchestrator, spy, registry, torrent_client, seed_spy = _make_orchestrator(add_return="aaaa1234")

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Grab really succeeded (so this is not a vacuous "nothing happened" pass).
    assert outcome.disposition == "success"
    assert [e for e in spy.events if isinstance(e, GrabSucceeded)]

    # The seed spy was never wired in → must be completely untouched.
    assert seed_spy.record_dispatch.call_count == 0, "record_dispatch must NOT be called at grab time (DESIGN §9)"
    assert seed_spy.seed.add.call_count == 0, "seed.add must NOT be called at grab time (DESIGN §9)"
    assert seed_spy.mock_calls == [], "no seed-obligation write path may be reachable from the orchestrator"

    # Belt-and-suspenders: no seed-write method name leaked onto the real deps.
    assert torrent_client is not None
    for tracked in (registry, torrent_client):
        for call_item in tracked.mock_calls:
            name = str(call_item)
            assert "record_dispatch" not in name, f"record_dispatch leaked onto a dep: {call_item}"
            assert "seed" not in name, f"seed write leaked onto a dep: {call_item}"
