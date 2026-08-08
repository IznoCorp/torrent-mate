"""Tests for per-torrent bandwidth caps wiring (O4).

Covers :func:`personalscraper.acquire.orchestrator._build_limits` — the
pure limits-building helper extracted for testability — the REAL grab-path
wiring of ``add(limits=...)`` (review BLOCKER: the « remove ``limits=limits`` »
mutation survived the suite), and the one-shot ``limits_unsupported`` warning
gate in :meth:`GrabOrchestrator.grab`.

Mocking note (Python 3.12): the runtime-checkable protocol ``isinstance``
check uses ``getattr_static``, which does NOT see MagicMock's lazily-created
attributes — a bare ``MagicMock`` FAILS the :class:`TorrentLimiter` gate. The
fake clients below therefore carry ``add`` / ``apply_limits`` as REAL methods
(cf. the ``_StubClient`` pattern of ``test_global_caps_service.py``).
"""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import MagicMock, patch

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator, _build_limits
from personalscraper.api._units import ByteSize
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentLimiter
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.conf.models.acquire import BandwidthConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef

_RESOLVE = "personalscraper.acquire._resolve_walk.resolve_source"

TOP_PROVIDER = "c411"
INFO_HASH = "cafe1234"


class _LimiterAdderClient:
    """Fake client with REAL ``add`` + ``apply_limits`` methods.

    Real methods (not MagicMock attributes on the class) so the Python 3.12
    ``getattr_static``-based runtime protocol check sees them and the client
    passes ``isinstance(client, TorrentLimiter)``.
    """

    def __init__(self) -> None:
        self.add_calls: list[dict] = []

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Record the add call (kwargs included) and return INFO_HASH."""
        self.add_calls.append({"category": category, "tags": list(tags), "limits": limits})
        return INFO_HASH

    def apply_limits(self, info_hash: str, limits: TorrentLimits) -> None:
        """Real no-op method — makes the TorrentLimiter runtime gate pass."""


class _AdderOnlyClient:
    """Fake client with a REAL ``add`` but NO ``apply_limits`` (non-limiter)."""

    def __init__(self) -> None:
        self.add_calls: list[dict] = []

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


def _make_wanted() -> WantedItem:
    """Build a movie WantedItem reaching the grab add path."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=11111),
        kind="movie",
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
    )


def _make_result() -> TrackerResult:
    """Build a minimal takeable TrackerResult from the pinned provider."""
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


def _make_grab_orchestrator(torrent_client: object, bw: BandwidthConfig) -> GrabOrchestrator:
    """Build a GrabOrchestrator whose search chain yields one takeable candidate.

    Mirrors the fixture of ``test_grab_transmission_add.py``: mocked registry
    returning a single-result SearchOutcome + fresh transports, real EventBus.

    Args:
        torrent_client: The fake torrent client to inject.
        bw: The bandwidth caps configuration under test.

    Returns:
        A grab-ready orchestrator (callers patch ``resolve_source``).
    """
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(
        results=[_make_result()],
        trackers_queried=1,
        trackers_errored=0,
    )
    registry.transports.return_value = {TOP_PROVIDER: MagicMock()}
    return GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=torrent_client,  # type: ignore[arg-type]
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        bandwidth=bw,
    )


# ── _build_limits unit tests ───────────────────────────────────────────────────


def test_no_caps_configured_returns_none():
    """Both per-torrent fields None → no limits."""
    bw = BandwidthConfig(per_torrent_down=None, per_torrent_up=None)
    result = _build_limits(bw, client_is_limiter=True)
    assert result is None


def test_down_only_sets_down_and_leaves_up_none():
    """per_torrent_down set, per_torrent_up None → correct down cap."""
    bw = BandwidthConfig(per_torrent_down=1_000_000, per_torrent_up=None)
    result = _build_limits(bw, client_is_limiter=True)
    assert result is not None
    assert result.down_bytes_per_s == 1_000_000
    assert result.up_bytes_per_s is None


def test_up_only_sets_up_and_leaves_down_none():
    """per_torrent_up set, per_torrent_down None → correct up cap."""
    bw = BandwidthConfig(per_torrent_down=None, per_torrent_up=500_000)
    result = _build_limits(bw, client_is_limiter=True)
    assert result is not None
    assert result.up_bytes_per_s == 500_000
    assert result.down_bytes_per_s is None


def test_both_set_returns_both_fields():
    """Both per-torrent fields set → both in TorrentLimits."""
    bw = BandwidthConfig(per_torrent_down=2_000_000, per_torrent_up=1_000_000)
    result = _build_limits(bw, client_is_limiter=True)
    assert result is not None
    assert result.down_bytes_per_s == 2_000_000
    assert result.up_bytes_per_s == 1_000_000


def test_ratio_and_seed_time_always_none():
    """Ratio and seed_time_minutes remain None — out of scope (§7)."""
    bw = BandwidthConfig(per_torrent_down=1_000_000, per_torrent_up=500_000)
    result = _build_limits(bw, client_is_limiter=True)
    assert result is not None
    assert result.ratio is None
    assert result.seed_time_minutes is None


def test_unsupported_client_returns_none():
    """Client lacks TorrentLimiter → None, no crash."""
    bw = BandwidthConfig(per_torrent_down=1_000_000, per_torrent_up=500_000)
    result = _build_limits(bw, client_is_limiter=False)
    assert result is None


def test_caps_configured_but_unsupported_client_still_none():
    """Even with caps, unsupported client → None (D4: no crash)."""
    bw = BandwidthConfig(per_torrent_down=10_000, per_torrent_up=None)
    result = _build_limits(bw, client_is_limiter=False)
    assert result is None


# ── Grab-path add(limits=) wiring (review BLOCKER) ─────────────────────────────


def test_grab_passes_built_limits_to_add() -> None:
    """Regression (review BLOCKER): grab() hands the built limits to ``add(limits=...)``.

    The mutation « remove ``limits=limits`` from the add call » survived the
    whole suite — nothing exercised the real grab path with a limiter-capable
    client and caps configured. This pins the wiring: the fake client must
    receive ``limits == TorrentLimits(down_bytes_per_s=1_000_000)``.
    """
    client = _LimiterAdderClient()
    assert isinstance(client, TorrentLimiter), "the fake must pass the runtime TorrentLimiter gate"
    orch = _make_grab_orchestrator(client, BandwidthConfig(per_torrent_down=1_000_000))

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orch.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "success"
    assert len(client.add_calls) == 1
    assert client.add_calls[0]["limits"] == TorrentLimits(down_bytes_per_s=1_000_000, up_bytes_per_s=None)


def test_grab_passes_none_limits_when_no_caps_configured() -> None:
    """Mirror: no per-torrent caps configured → ``add(limits=None)`` on the same path."""
    client = _LimiterAdderClient()
    orch = _make_grab_orchestrator(client, BandwidthConfig())

    with patch(_RESOLVE) as mock_resolve:
        mock_resolve.return_value = MagicMock(spec=TorrentSource)
        outcome = orch.grab(_make_wanted(), QualityProfile())

    assert outcome.disposition == "success"
    assert len(client.add_calls) == 1
    assert client.add_calls[0]["limits"] is None


# ── GrabOrchestrator limits-unsupported warning gate ───────────────────────────


class TestGrabOrchestratorLimitsWarning:
    """One-shot warning gate — only warns ONCE (D4).

    Regression (review MAJOR): the previous test set the one-shot flag
    ITSELF and never called ``grab()`` — it proved nothing about the gate.
    This one drives two REAL consecutive grabs on a non-limiter client with
    caps configured and counts the actual ``limits_unsupported`` warning.
    """

    def test_warns_once_then_silent(self) -> None:
        """Two grabs on an adder-only client + caps → exactly ONE warning."""
        client = _AdderOnlyClient()
        assert not isinstance(client, TorrentLimiter), "the fake must FAIL the runtime TorrentLimiter gate"
        orch = _make_grab_orchestrator(client, BandwidthConfig(per_torrent_down=1_000_000))

        with (
            patch(_RESOLVE) as mock_resolve,
            patch("personalscraper.acquire.orchestrator.log") as mock_log,
        ):
            mock_resolve.return_value = MagicMock(spec=TorrentSource)
            first = orch.grab(_make_wanted(), QualityProfile())
            second = orch.grab(_make_wanted(), QualityProfile())

        # Both grabs really ran to the add stage (the warning gate sits there).
        assert first.disposition == "success"
        assert second.disposition == "success"
        assert len(client.add_calls) == 2

        # Exactly ONE limits_unsupported warning across the two grabs (D4).
        mock_log.warning.assert_called_once()
        assert mock_log.warning.call_args.args[0] == "acquire.grab.limits_unsupported"


# ── TorrentLimits fields invariant ─────────────────────────────────────────────


def test_torrent_limits_fields_match_bandwidth_config():
    """TorrentLimits created from BandwidthConfig has correct field mapping."""
    bw = BandwidthConfig(per_torrent_down=5_000_000, per_torrent_up=2_500_000)
    limits = _build_limits(bw, client_is_limiter=True)
    assert limits is not None
    assert limits.down_bytes_per_s == bw.per_torrent_down
    assert limits.up_bytes_per_s == bw.per_torrent_up
    # ratio/seed_time are separate concerns (#173/#174) — never set here.
    assert limits.ratio is None
    assert limits.seed_time_minutes is None
