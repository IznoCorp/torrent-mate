"""Tests for the grab under a client scope (shared qBittorrent, own category and tags).

With no scope configured the grab is what it always was (characterisation, green
before and after the change). With a scope: the add carries the scope's category
and the instance tags (``seed-pure`` included), a hash already in the shared
client is refused, and the global caps are never applied.

Mocking note (Python 3.12): the runtime-protocol ``isinstance`` check uses
``getattr_static``, so the fake carries REAL methods, not ``MagicMock`` attributes.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.conf.models.acquire import BandwidthConfig
from personalscraper.conf.models.api_config import TorrentScope
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.units import ByteSize

_RESOLVE = "personalscraper.acquire._resolve_walk.resolve_source"
PROVIDER = "c411"
INFO_HASH = "cafe1234"

SCOPE = TorrentScope(category="tm-preprod", download_root=Path("/downloads/preprod"))


class _SharedClient:
    """Fake client with real ``add``, the ``TorrentLister`` methods and ``apply_global_limits`` methods."""

    def __init__(self, present: set[str] | None = None) -> None:
        self.present = present or set()
        self.add_calls: list[dict] = []
        self.global_calls: list[dict] = []

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Record the add call and return INFO_HASH."""
        self.add_calls.append({"category": category, "tags": list(tags), "limits": limits})
        return INFO_HASH

    def get_all_hashes(self) -> set[str]:
        """Return the hashes already in the (shared) client."""
        return set(self.present)

    def get_completed(self) -> list:
        """Satisfy the ``TorrentLister`` runtime gate; the grab never reads it."""
        return []

    def get_by_hashes(self, hashes: set[str]) -> list:
        """Satisfy the ``TorrentLister`` runtime gate; the grab never reads it."""
        return []

    def apply_global_limits(self, *, down_bytes_per_s: int | None, up_bytes_per_s: int | None) -> None:
        """Record a global-limits call."""
        self.global_calls.append({"down": down_bytes_per_s, "up": up_bytes_per_s})


def _wanted() -> WantedItem:
    """Build a movie WantedItem reaching the grab add path."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=11111),
        kind="movie",
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
    )


def _candidate(tracker_id: str, info_hash: str | None, seeders: int) -> TrackerResult:
    """Build one takeable tracker result; more seeders rank first."""
    return TrackerResult(
        provider=PROVIDER,
        tracker_id=tracker_id,
        title=f"Movie 2010 MULTi 1080p BluRay x265-GRP{tracker_id}",
        size=ByteSize(5_000_000_000 + seeders),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=info_hash,
        download_url=f"https://{PROVIDER}.test/torrent/{tracker_id}",
    )


def _source(info_hash: str | Exception = INFO_HASH) -> MagicMock:
    """Build a fetched source whose ``info_hash`` is a value, or raises when given an exception."""
    source = MagicMock(spec=TorrentSource)
    if isinstance(info_hash, Exception):
        type(source).info_hash = PropertyMock(side_effect=info_hash)
    else:
        type(source).info_hash = PropertyMock(return_value=info_hash)
    return source


def _orchestrator(
    client: object,
    *,
    scope: TorrentScope | None,
    bw: BandwidthConfig | None = None,
    candidates: list[TrackerResult] | None = None,
) -> GrabOrchestrator:
    """Build a grab-ready orchestrator whose search yields the given candidates (one by default)."""
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(
        results=candidates if candidates is not None else [_candidate("t1", INFO_HASH, 50)],
        trackers_queried=1,
        trackers_errored=0,
    )
    registry.transports.return_value = {PROVIDER: MagicMock()}
    # ``scope`` is passed only when set, so the characterisation tests build the
    # orchestrator exactly as every caller did before the parameter existed.
    extra = {} if scope is None else {"scope": scope}
    return GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=client,  # type: ignore[arg-type]
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        bandwidth=bw or BandwidthConfig(),
        **extra,
    )


def _grab(orch: GrabOrchestrator, *sources: MagicMock):
    """Run one grab with ``resolve_source`` patched to return *sources* in turn (one INFO_HASH source by default)."""
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.side_effect = list(sources) if sources else [_source()] * 3
        return orch.grab(_wanted(), QualityProfile())


def test_scope_set_add_carries_category_and_instance_tags() -> None:
    """Scope set → add(category=scope.category, tags=[provider, *instance_tags])."""
    client = _SharedClient()
    outcome = _grab(_orchestrator(client, scope=SCOPE))

    assert outcome.disposition == "success"
    assert client.add_calls == [
        {"category": "tm-preprod", "tags": [PROVIDER, "tm-preprod", "seed-pure"], "limits": None},
    ]
    assert outcome.category == "tm-preprod"
    assert outcome.tags == (PROVIDER, "tm-preprod", "seed-pure")


def test_scope_set_shared_hash_is_refused_without_add() -> None:
    """Scope set, hash already in the client → no add, the decision reason is shared_hash."""
    client = _SharedClient(present={INFO_HASH})
    outcome = _grab(_orchestrator(client, scope=SCOPE))

    assert client.add_calls == []
    assert outcome.disposition == "retryable"
    assert outcome.reason == "shared_hash"


def test_scope_set_shared_hash_comparison_ignores_case() -> None:
    """A client reporting the hash in upper case is still a shared hash."""
    client = _SharedClient(present={INFO_HASH.upper()})
    _grab(_orchestrator(client, scope=SCOPE))

    assert client.add_calls == []


def test_scope_set_global_caps_are_skipped() -> None:
    """Scope set → apply_global_limits is never called, even with global caps configured."""
    client = _SharedClient()
    orch = _orchestrator(client, scope=SCOPE, bw=BandwidthConfig(global_down=5_000_000, global_up=1_000_000))

    with patch("personalscraper.acquire.orchestrator.log") as mock_log:
        orch.apply_global_caps()

    assert client.global_calls == []
    assert any(c.args and c.args[0] == "acquire.global_limits_skipped" for c in mock_log.info.call_args_list)


def test_scope_set_non_lister_client_refuses_with_its_own_reason() -> None:
    """A client that cannot list its hashes cannot prove the hash is free → no add, reason scope_unverifiable."""

    class _AddOnly:
        """Fake client with an ``add`` and no hash listing."""

        def __init__(self) -> None:
            """Start with no recorded add."""
            self.add_calls: list[dict] = []

        def add(self, source: TorrentSource, **kwargs: object) -> str:
            """Record the add call and return INFO_HASH."""
            self.add_calls.append(dict(kwargs))
            return INFO_HASH

    client = _AddOnly()
    outcome = _grab(_orchestrator(client, scope=SCOPE))

    assert client.add_calls == []
    assert outcome.disposition == "retryable"
    assert outcome.reason == "scope_unverifiable"


def test_scope_set_tracker_hash_none_still_checks_the_source_hash() -> None:
    """Tracker gave no hash, the source's hash is already in the client → no add (no fail-open)."""
    client = _SharedClient(present={INFO_HASH})
    orch = _orchestrator(client, scope=SCOPE, candidates=[_candidate("t1", None, 50)])

    outcome = _grab(orch, _source(INFO_HASH))

    assert client.add_calls == []
    assert outcome.reason == "shared_hash"


def test_scope_set_underivable_source_hash_refuses() -> None:
    """The source's hash cannot be derived → fail closed, no add."""
    client = _SharedClient()

    outcome = _grab(_orchestrator(client, scope=SCOPE), _source(ValueError("no hash")))

    assert client.add_calls == []
    assert outcome.disposition == "retryable"
    assert outcome.reason == "hash_underivable"


def test_scope_set_tracker_hash_case_does_not_hide_a_shared_hash() -> None:
    """The source hash (not the tracker's) is compared, whatever the case on each side."""
    client = _SharedClient(present={INFO_HASH})
    orch = _orchestrator(client, scope=SCOPE, candidates=[_candidate("t1", INFO_HASH.upper(), 50)])

    _grab(orch, _source(INFO_HASH))

    assert client.add_calls == []


def test_scope_set_shared_first_candidate_gives_way_to_the_next() -> None:
    """Two candidates, the first shared → the second is added within the same grab."""
    client = _SharedClient(present={INFO_HASH})
    orch = _orchestrator(
        client,
        scope=SCOPE,
        candidates=[_candidate("t1", INFO_HASH, 50), _candidate("t2", "beef5678", 10)],
    )

    outcome = _grab(orch, _source(INFO_HASH), _source("beef5678"))

    assert outcome.disposition == "success"
    assert len(client.add_calls) == 1
    assert outcome.chosen is not None
    assert outcome.chosen.tracker_id == "t2"


def test_scope_set_every_candidate_shared_is_retryable_shared_hash() -> None:
    """All candidates shared → no add, retryable shared_hash."""
    client = _SharedClient(present={INFO_HASH, "beef5678"})
    orch = _orchestrator(
        client,
        scope=SCOPE,
        candidates=[_candidate("t1", INFO_HASH, 50), _candidate("t2", "beef5678", 10)],
    )

    outcome = _grab(orch, _source(INFO_HASH), _source("beef5678"))

    assert client.add_calls == []
    assert outcome.disposition == "retryable"
    assert outcome.reason == "shared_hash"


# ── Characterisation: scope None is today's behaviour (green before AND after) ──


def test_scope_none_add_is_unchanged() -> None:
    """No scope → add(category=None, tags=[provider]) and no hash listing."""
    client = _SharedClient(present={INFO_HASH})
    outcome = _grab(_orchestrator(client, scope=None))

    assert outcome.disposition == "success"
    assert client.add_calls == [{"category": None, "tags": [PROVIDER], "limits": None}]
    assert outcome.category is None
    assert outcome.tags == (PROVIDER,)


def test_scope_none_global_caps_still_applied() -> None:
    """No scope → apply_global_limits is called with the configured values."""
    client = _SharedClient()
    orch = _orchestrator(client, scope=None, bw=BandwidthConfig(global_down=5_000_000, global_up=1_000_000))

    orch.apply_global_caps()

    assert client.global_calls == [{"down": 5_000_000, "up": 1_000_000}]
