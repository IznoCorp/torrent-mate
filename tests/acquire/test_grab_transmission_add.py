"""Tests verifying grab() adds the torrent with its provider tag in ONE call.

Open item #8 (FINAL): Transmission's ``add()`` now emits the category-less
``""`` sentinel (``labels=["", *tags]``), so a category-less torrent carrying
tags is representable in a single ``add_torrent`` call. The grab orchestrator
therefore adds the torrent and its source-tracker tag ATOMICALLY —
``add(category=None, tags=[provider])`` — instead of the former two-step
(``add(category=None)`` then a best-effort ``add_tags``). Both clients apply
category+tags inline in their single add call, so a torrent is never
added-but-untagged.

Load-bearing tests:

- ``test_grab_adds_with_provider_tag_atomically``: fake Transmission-like client
  (TorrentAdder + TorrentTagger) — grab() succeeds; ``add()`` called ONCE with
  ``category=None`` and ``tags=[provider]``; ``add_tags()`` is NOT called
  (mutation-proof against a re-introduced two-step).
- ``test_grab_add_failure_is_retryable``: ``add()`` raises ``ApiError`` (the tag
  is part of the atomic add, so a tag/label failure fails the add) → outcome is
  RETRYABLE ``add_failed``, not a silent success.
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

    Mirrors the real (post open-item-#8) Transmission adder: ``add()`` accepts
    ``category=None`` together with ``tags`` — the client encodes the tags
    behind the ``""`` sentinel internally — and returns INFO_HASH.
    ``add_tags()`` records calls so a re-introduced two-step is detectable
    (the orchestrator must NOT call it anymore).
    """

    def __init__(self, add_side_effect: Exception | None = None) -> None:
        self._add_side_effect = add_side_effect
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
        """Record the add call and return INFO_HASH (or raise a configured side-effect).

        Args:
            source: Torrent source (ignored in fake).
            category: Category label (Transmission labels[0]); None → sentinel.
            tags: Tags carried atomically with the add.
            paused: Ignored.
            limits: Ignored.

        Returns:
            INFO_HASH constant.

        Raises:
            Exception: If ``add_side_effect`` was set at construction.
        """
        if self._add_side_effect is not None:
            raise self._add_side_effect
        self.add_calls.append({"category": category, "tags": list(tags)})
        return INFO_HASH

    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Record the call (must NOT be reached by the atomic-add orchestrator).

        Args:
            info_hash: The torrent's info hash.
            tags: Tags to add.
        """
        self.add_tags_calls.append((info_hash, list(tags)))

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
    # Transports are read FRESH at grab time via the registry, not snapshotted.
    registry.transports.return_value = transports

    bus = EventBus()
    spy = _EventSpy()
    bus.subscribe(Event, spy)

    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=torrent_client,
        event_bus=bus,
        ranking=RankingConfig(min_seeders=0),
    )
    return orchestrator, spy


# ---------------------------------------------------------------------------
# Atomic single-call add-with-tag flow
# ---------------------------------------------------------------------------


def test_grab_adds_with_provider_tag_atomically() -> None:
    """grab() calls add(category=None, tags=[provider]) ONCE and never add_tags().

    Mutation-proof: re-introducing the two-step (``add(category=None)`` then
    ``add_tags``) would make ``add_tags_calls`` non-empty and drop the tag from
    the ``add`` call, failing the assertions below.

    Verified contract:
    - ``add()`` is called exactly once with ``category=None`` and
      ``tags=[TOP_PROVIDER]``.
    - ``add_tags()`` is NOT called (the tag rides the atomic add).
    - Outcome disposition is ``success``.
    """
    fake_client = _FakeTransmissionClient()
    orchestrator, _spy = _make_orchestrator(fake_client)

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    # Success — torrent was added.
    assert outcome.disposition == "success"

    # add() called once carrying the provider tag with no category.
    assert len(fake_client.add_calls) == 1
    assert fake_client.add_calls[0]["category"] is None
    assert fake_client.add_calls[0]["tags"] == [TOP_PROVIDER]

    # The former two-step is dead — no separate add_tags() call.
    assert fake_client.add_tags_calls == []


def test_grab_add_failure_is_retryable() -> None:
    """add() raising ApiError → RETRYABLE add_failed (tag is part of the atomic add).

    With tagging folded into the atomic add, a tag/label write failure fails the
    add itself. That surfaces as the taxonomy's retryable ``add_failed`` (the
    idempotent re-grab retries next run) — NOT a silent success.
    """
    fake_client = _FakeTransmissionClient(
        add_side_effect=ApiError(provider="transmission", http_status=500, message="rpc error")
    )
    orchestrator, _spy = _make_orchestrator(fake_client)

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orchestrator.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "retryable"
    assert outcome.reason == "add_failed"
    # No add_tags fallback exists anymore.
    assert fake_client.add_tags_calls == []
