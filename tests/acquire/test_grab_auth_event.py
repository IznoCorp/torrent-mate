"""Tests verifying TrackerAuthFailed emission on grab 401/403 (Phase 2.1).

Load-bearing tests called out explicitly:

- ``test_grab_emits_tracker_auth_failed_on_401``: resolve_source raising
  ``TrackerAuthError(http_status=401)`` → exactly one ``TrackerAuthFailed``
  event with the right payload; disposition still terminal ``tracker_auth``.
  Mutation-proof: deleting the emit makes this test FAIL.
- ``test_grab_fetch_error_emits_no_auth_event``: TorrentFetchError → retryable
  ``fetch_failed``, zero ``TrackerAuthFailed`` events.
- ``test_grab_api_error_on_add_emits_no_auth_event``: generic ApiError on add()
  → retryable ``add_failed``, zero ``TrackerAuthFailed`` events.

All tests use a REAL/captured EventBus (never a bare MagicMock) so event
emission is actually observed, not just asserted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import TrackerAuthFailed, WantedAbandoned
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.api._contracts import ApiError
from personalscraper.api._units import ByteSize
from personalscraper.api.torrent._base import TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.identity import MediaRef

_RESOLVE = "personalscraper.acquire.orchestrator.resolve_source"

# Constants used across tests — pin to expected values in assertions.
TOP_PROVIDER = "lacale"
WANTED_TVDB_ID = 99999
EXPECTED_MEDIA_REF = MediaRef(tvdb_id=WANTED_TVDB_ID)


class _EventSpy:
    """Capturing subscriber: records every Event it receives, in order."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


def _make_wanted() -> WantedItem:
    """Build a WantedItem with a pinned MediaRef for assertion correlation."""
    return WantedItem(
        media_ref=EXPECTED_MEDIA_REF,
        kind="movie",
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
    )


def _make_result(info_hash: str = "aaaa1234") -> TrackerResult:
    """Build a minimal TrackerResult from the pinned provider."""
    return TrackerResult(
        provider=TOP_PROVIDER,
        tracker_id="t1",
        title="Movie 2010 MULTi 1080p BluRay x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=50,
        leechers=0,
        resolution="1080p",
        info_hash=info_hash,
        download_url=f"https://{TOP_PROVIDER}.test/torrent/1",
    )


def _make_orchestrator_with_spy(
    *,
    add_side_effect: Exception | None = None,
    add_return: str = "aaaa1234",
) -> tuple[GrabOrchestrator, _EventSpy, MagicMock]:
    """Build a GrabOrchestrator wired to a real EventBus spy.

    The torrent client is a MagicMock(spec=TorrentAdder) so calls are
    tracked and the spec prevents accidental method leakage.

    Args:
        add_side_effect: Optional exception to raise on ``add()``.
        add_return: Info hash to return from ``add()`` on success.

    Returns:
        Tuple of (orchestrator, spy, torrent_client).
    """
    search_outcome = SearchOutcome(
        results=[_make_result()],
        trackers_queried=1,
        trackers_errored=0,
    )
    registry = MagicMock()
    registry.search_candidates.return_value = search_outcome

    transports = {TOP_PROVIDER: MagicMock()}

    torrent_client: MagicMock = MagicMock(spec=TorrentAdder)
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
        ranking=RankingConfig(min_seeders=0),
    )
    return orchestrator, spy, torrent_client


# ---------------------------------------------------------------------------
# Mutation-proof: emit TrackerAuthFailed on TrackerAuthError
# ---------------------------------------------------------------------------


def test_grab_emits_tracker_auth_failed_on_401() -> None:
    """resolve_source raising TrackerAuthError(401) emits exactly one TrackerAuthFailed.

    Mutation-proof: deleting the ``self._event_bus.emit(TrackerAuthFailed(...))``
    production line makes this test FAIL (no auth events on the bus).

    The auth branch emits BOTH ``TrackerAuthFailed`` AND (via ``_terminal``)
    ``WantedAbandoned`` — this test filters by ``isinstance(e, TrackerAuthFailed)``.
    """
    orchestrator, spy, torrent_client = _make_orchestrator_with_spy()

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.side_effect = TrackerAuthError(provider=TOP_PROVIDER, http_status=401, message="unauthorized")
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Disposition: terminal abandon, reason 'tracker_auth'.
    assert outcome.disposition == "terminal"
    assert outcome.reason == "tracker_auth"

    # Exactly one TrackerAuthFailed with the right payload.
    auth_events = [e for e in spy.events if isinstance(e, TrackerAuthFailed)]
    assert len(auth_events) == 1
    assert auth_events[0].tracker == TOP_PROVIDER
    assert auth_events[0].http_status == 401
    assert auth_events[0].media_ref == EXPECTED_MEDIA_REF

    # WantedAbandoned is also emitted by _terminal — that is by-design and
    # must not interfere: add() was never called.
    assert [e for e in spy.events if isinstance(e, WantedAbandoned)]
    torrent_client.add.assert_not_called()


def test_grab_emits_tracker_auth_failed_on_403() -> None:
    """resolve_source raising TrackerAuthError(403) emits TrackerAuthFailed(http_status=403)."""
    orchestrator, spy, _torrent_client = _make_orchestrator_with_spy()

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.side_effect = TrackerAuthError(provider=TOP_PROVIDER, http_status=403, message="forbidden")
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "terminal"
    assert outcome.reason == "tracker_auth"

    auth_events = [e for e in spy.events if isinstance(e, TrackerAuthFailed)]
    assert len(auth_events) == 1
    assert auth_events[0].tracker == TOP_PROVIDER
    assert auth_events[0].http_status == 403
    assert auth_events[0].media_ref == EXPECTED_MEDIA_REF


# ---------------------------------------------------------------------------
# Non-auth failures: zero TrackerAuthFailed events
# ---------------------------------------------------------------------------


def test_grab_fetch_error_emits_no_auth_event() -> None:
    """TorrentFetchError on resolve_source → retryable fetch_failed, zero auth events."""
    orchestrator, spy, _torrent_client = _make_orchestrator_with_spy()

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.side_effect = TorrentFetchError(provider=TOP_PROVIDER, http_status=0, message="bad body")
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "fetch_failed"
    assert not any(isinstance(e, TrackerAuthFailed) for e in spy.events)


def test_grab_api_error_on_add_emits_no_auth_event() -> None:
    """Generic ApiError on add() → retryable add_failed, zero auth events."""
    orchestrator, spy, _torrent_client = _make_orchestrator_with_spy(
        add_side_effect=ApiError(provider="qbit", http_status=500, message="server error"),
    )

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "add_failed"
    assert not any(isinstance(e, TrackerAuthFailed) for e in spy.events)
