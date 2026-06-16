"""Tests verifying grab() adds torrent then tags separately (Phase 2.2).

Motivation: Transmission rejects ``add(tags=(...))`` with ValueError because
its ``labels[0]`` slot is reserved for the category; tags must be written via
a separate ``add_tags()`` call AFTER the torrent is added.  The new production
code calls ``add(category=None)`` (no tags) then, if the client implements
``TorrentTagger``, calls ``add_tags(info_hash, [provider])``.

Load-bearing tests:

- ``test_grab_adds_then_tags_provider_on_tagger_client``: fake Transmission-like
  client (TorrentAdder + TorrentTagger) — grab() succeeds; ``add()`` called
  with NO tags kwarg; ``add_tags()`` called with the provider label.
  Mutation-proof: the OLD call ``add(..., tags=(provider,))`` raises
  ``ValueError`` on this fake → test FAILS on mutation, passes on restore.
- ``test_grab_tag_failure_is_swallowed_success``: ``add()`` succeeds but
  ``add_tags()`` raises ``ApiError`` → outcome is SUCCESS (not retryable
  add_failed); demonstrates the inner swallow contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import MagicMock, patch

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.api._contracts import ApiError
from personalscraper.api._units import ByteSize
from personalscraper.api.torrent._base import TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentTagger
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.identity import MediaRef

_RESOLVE = "personalscraper.acquire.orchestrator.resolve_source"

TOP_PROVIDER = "lacale"
INFO_HASH = "bbbb5678"
WANTED_TVDB_ID = 11111
EXPECTED_MEDIA_REF = MediaRef(tvdb_id=WANTED_TVDB_ID)


class _EventSpy:
    """Capturing subscriber: records every Event it receives, in order."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


class _FakeTransmissionClient(TorrentAdder, TorrentTagger):
    """Minimal fake Transmission-like client implementing TorrentAdder + TorrentTagger.

    Mirrors the real Transmission constraint: ``add()`` with non-empty
    ``tags`` raises ``ValueError`` (labels[0] is reserved for category).
    ``add()`` with no tags (or empty tags) succeeds and returns INFO_HASH.
    ``add_tags()`` records calls for assertion.
    """

    def __init__(self, add_tags_side_effect: Exception | None = None) -> None:
        self._add_tags_side_effect = add_tags_side_effect
        self.add_calls: list[dict] = []
        self.add_tags_calls: list[tuple[str, Sequence[str]]] = []

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits=None,
    ) -> str:
        """Add a torrent — raise ValueError if tags is non-empty (Transmission constraint).

        Args:
            source: Torrent source (ignored in fake).
            category: Category label (Transmission labels[0]).
            tags: Must be empty; non-empty raises ValueError.
            paused: Ignored.
            limits: Ignored.

        Returns:
            INFO_HASH constant.

        Raises:
            ValueError: If tags is non-empty (mirrors Transmission behavior).
        """
        if tags:
            raise ValueError(f"Transmission add() does not accept tags={tags!r}; use add_tags() after add().")
        self.add_calls.append({"category": category, "tags": list(tags)})
        return INFO_HASH

    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Record the call; optionally raise a configured side-effect.

        Args:
            info_hash: The torrent's info hash.
            tags: Tags to add.

        Raises:
            Exception: If ``add_tags_side_effect`` was set at construction.
        """
        self.add_tags_calls.append((info_hash, list(tags)))
        if self._add_tags_side_effect is not None:
            raise self._add_tags_side_effect

    def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """No-op stub (TorrentTagger protocol requirement).

        Args:
            info_hash: The torrent's info hash.
            tags: Tags to remove.
        """


def _make_wanted() -> WantedItem:
    """Build a WantedItem with a pinned MediaRef for assertion correlation."""
    return WantedItem(
        media_ref=EXPECTED_MEDIA_REF,
        kind="movie",
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
    )


def _make_result() -> TrackerResult:
    """Build a minimal TrackerResult from the pinned provider."""
    return TrackerResult(
        provider=TOP_PROVIDER,
        tracker_id="t1",
        title="Movie 2010 MULTi 1080p BluRay x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=50,
        leechers=0,
        resolution="1080p",
        info_hash=INFO_HASH,
        download_url=f"https://{TOP_PROVIDER}.test/torrent/1",
    )


def _make_orchestrator(torrent_client) -> tuple[GrabOrchestrator, _EventSpy]:
    """Build a GrabOrchestrator wired to a real EventBus spy.

    Args:
        torrent_client: The torrent client to inject (must implement TorrentAdder).

    Returns:
        Tuple of (orchestrator, spy).
    """
    search_outcome = SearchOutcome(
        results=[_make_result()],
        trackers_queried=1,
        trackers_errored=0,
    )
    registry = MagicMock()
    registry.search_candidates.return_value = search_outcome

    transports = {TOP_PROVIDER: MagicMock()}

    bus = EventBus()
    spy = _EventSpy()
    bus.subscribe(Event, spy)

    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        transports=transports,
        torrent_client=torrent_client,
        event_bus=bus,
        ranking=RankingConfig(min_seeders=0),
    )
    return orchestrator, spy


# ---------------------------------------------------------------------------
# Mutation-proof: add-then-tag flow
# ---------------------------------------------------------------------------


def test_grab_adds_then_tags_provider_on_tagger_client() -> None:
    """grab() calls add(category=None) then add_tags([provider]) on a TorrentTagger client.

    Mutation-proof: the OLD production line ``add(..., tags=(provider,))``
    raises ``ValueError`` on the fake Transmission client, making this test
    FAIL on mutation and PASS only after the fix restores the correct sequence.

    Verified contract:
    - ``add()`` is called exactly once with no tags (empty sequence).
    - ``add_tags()`` is called with (INFO_HASH, [TOP_PROVIDER]).
    - Outcome disposition is ``success``.
    """
    fake_client = _FakeTransmissionClient()
    orchestrator, spy = _make_orchestrator(fake_client)

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Success — torrent was added.
    assert outcome.disposition == "success"

    # add() called once with empty tags (Transmission-safe).
    assert len(fake_client.add_calls) == 1
    assert fake_client.add_calls[0]["tags"] == []
    assert fake_client.add_calls[0]["category"] is None

    # add_tags() called with the provider label on the correct hash.
    assert len(fake_client.add_tags_calls) == 1
    assert fake_client.add_tags_calls[0] == (INFO_HASH, [TOP_PROVIDER])


def test_grab_tag_failure_is_swallowed_success() -> None:
    """add() succeeds but add_tags() raises ApiError → outcome is SUCCESS.

    The inner ``try/except ApiError`` around ``add_tags()`` swallows the
    tagging failure and logs a warning; the overall grab is still a success.
    The torrent was added — the tag failure must NOT promote to retryable
    ``add_failed``.
    """
    fake_client = _FakeTransmissionClient(
        add_tags_side_effect=ApiError(provider="transmission", http_status=500, message="rpc error")
    )
    orchestrator, spy = _make_orchestrator(fake_client)

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Still a success — add() completed; tag failure is a warning, not a hard error.
    assert outcome.disposition == "success"

    # add() was called (torrent in client).
    assert len(fake_client.add_calls) == 1

    # add_tags() was attempted (and raised, but swallowed).
    assert len(fake_client.add_tags_calls) == 1
