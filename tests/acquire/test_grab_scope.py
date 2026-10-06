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
from unittest.mock import MagicMock, patch

from personalscraper.acquire import orchestrator as orchestrator_module
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


def _orchestrator(client: object, *, scope: TorrentScope | None, bw: BandwidthConfig | None = None) -> GrabOrchestrator:
    """Build a grab-ready orchestrator whose search yields one takeable candidate."""
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(
        results=[
            TrackerResult(
                provider=PROVIDER,
                tracker_id="t1",
                title="Movie 2010 MULTi 1080p BluRay x265-GRP",
                size=ByteSize(5_000_000_000),
                seeders=50,
                leechers=0,
                resolution="1080p",
                info_hash=INFO_HASH,
                download_url=f"https://{PROVIDER}.test/torrent/1",
            )
        ],
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


def _grab(orch: GrabOrchestrator):
    """Run one grab with ``resolve_source`` patched."""
    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
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
    assert outcome.reason == orchestrator_module.GrabRefusal.SHARED_HASH == "shared_hash"


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


def test_scope_set_non_lister_client_refuses_rather_than_adds_blind() -> None:
    """A client that cannot list its hashes cannot prove the hash is free → no add."""

    class _AddOnly:
        def __init__(self) -> None:
            self.add_calls: list[dict] = []

        def add(self, source: TorrentSource, **kwargs: object) -> str:
            self.add_calls.append(dict(kwargs))
            return INFO_HASH

    client = _AddOnly()
    result = orchestrator_module._add_in_scope(
        client,  # type: ignore[arg-type]
        MagicMock(spec=TorrentSource),
        provider=PROVIDER,
        info_hash=INFO_HASH,
        scope=SCOPE,
        limits=None,
    )

    assert result is None
    assert client.add_calls == []


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
