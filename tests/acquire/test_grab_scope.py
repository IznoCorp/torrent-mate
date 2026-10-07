"""Tests for the grab under a client scope (shared qBittorrent, own category and tags).

With no scope configured the grab is what it always was (characterisation, green
before and after the change). With a scope: the add carries the scope's category
and the instance tags (with ``seed-pure`` while ``v0_seed_pure`` is on), a hash already in the shared
client is refused, and the global caps are never applied.

Mocking note (Python 3.12): the runtime-protocol ``isinstance`` check uses
``getattr_static``, so the fake carries REAL methods, not ``MagicMock`` attributes.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import build_acquire_store
from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.conf.models.acquire import AcquireConfig, BandwidthConfig
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
        self.held: dict[str, set[str]] = {}
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

    def get_by_category(self, category: str) -> list:
        """Return the torrents filed under exactly *category*, as a client with the subcategories setting off does."""
        return [SimpleNamespace(hash=h, category=category) for h in self.held.get(category, ())]

    def get_by_hashes(self, hashes: set[str]) -> list:
        """Return the held torrents among *hashes*, each with the category it is filed under."""
        wanted = {h.lower() for h in hashes}
        return [
            SimpleNamespace(hash=h, category=category)
            for category, held in self.held.items()
            for h in held
            if h.lower() in wanted
        ]

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
    sandbox_categories: tuple[str, ...] = (),
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
    extra: dict[str, object] = {} if scope is None else {"scope": scope}
    if sandbox_categories:
        extra["sandbox_categories"] = sandbox_categories
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


def test_scope_without_v0_flag_add_carries_instance_tags_only() -> None:
    """Scope set, v0_seed_pure off → the grab carries the provider and the instance tags, no seed-pure."""
    client = _SharedClient()
    scope = SCOPE.model_copy(update={"v0_seed_pure": False})
    outcome = _grab(_orchestrator(client, scope=scope))

    assert client.add_calls == [{"category": "tm-preprod", "tags": [PROVIDER, "tm-preprod"], "limits": None}]
    assert outcome.tags == (PROVIDER, "tm-preprod")


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


# ── The scope's category must exist, filed under the scope's download root, before an add ──


class _CategoryClient(_SharedClient):
    """A shared client that also defines categories, counting the reads.

    Attributes:
        categories: Category name → save path.
        category_reads: How many times the categories were read.
    """

    def __init__(self, categories: dict[str, str]) -> None:
        """Hold the categories the client defines.

        Args:
            categories: Category name → save path.
        """
        super().__init__()
        self.categories = categories
        self.category_reads = 0

    def get_categories(self) -> dict[str, str]:
        """Count the read and return the categories."""
        self.category_reads += 1
        return dict(self.categories)


def test_scope_set_missing_category_skips_the_pass_with_its_cause() -> None:
    """The client defines no ``tm-preprod``: the pass is refused once, one event names the cause."""
    client = _CategoryClient({"prod": "/downloads/complete"})

    with patch("personalscraper.acquire.orchestrator.log") as mock_log:
        allowed = _orchestrator(client, scope=SCOPE).scope_allows_grab()

    assert allowed is False
    assert client.add_calls == []
    events = [c for c in mock_log.warning.call_args_list if c.args[0] == "acquire.grab_pass.scope_refused"]
    assert len(events) == 1
    assert events[0].kwargs["reason"] == "category_missing"


def test_scope_set_category_filed_outside_the_download_root_skips_the_pass() -> None:
    """The category exists but its save path is not under the scope's root: the pass is refused."""
    client = _CategoryClient({"tm-preprod": "/downloads/complete"})

    with patch("personalscraper.acquire.orchestrator.log") as mock_log:
        allowed = _orchestrator(client, scope=SCOPE).scope_allows_grab()

    assert allowed is False
    events = [c for c in mock_log.warning.call_args_list if c.args[0] == "acquire.grab_pass.scope_refused"]
    assert [c.kwargs["reason"] for c in events] == ["category_save_path"]


def test_scope_set_a_category_read_error_skips_the_pass_and_is_logged() -> None:
    """The client cannot list its categories: the pass is refused and the error text is logged."""

    class _Failing(_CategoryClient):
        """A client whose category read fails."""

        def get_categories(self) -> dict[str, str]:
            """Fail like a client that cannot be reached."""
            raise ApiError("qbit unreachable", http_status=None)

    with patch("personalscraper.acquire.orchestrator.log") as mock_log:
        allowed = _orchestrator(_Failing({}), scope=SCOPE).scope_allows_grab()

    assert allowed is False
    events = [c for c in mock_log.warning.call_args_list if c.args[0] == "acquire.grab_pass.scope_refused"]
    assert len(events) == 1
    assert events[0].kwargs["reason"] == "category_check_failed"
    assert "qbit unreachable" in events[0].kwargs["error"]


def test_scope_set_a_valid_category_allows_the_pass() -> None:
    """The category exists under the scope's root: the pass may run."""
    client = _CategoryClient({"tm-preprod": "/downloads/preprod/complete"})

    assert _orchestrator(client, scope=SCOPE).scope_allows_grab() is True


def test_scope_none_allows_the_pass_without_reading_categories() -> None:
    """No scope: the pass is allowed and the client is not asked for its categories."""
    client = _CategoryClient({})

    assert _orchestrator(client, scope=None).scope_allows_grab() is True
    assert client.category_reads == 0


def test_a_refused_category_costs_no_tracker_search(tmp_path: Path) -> None:
    """Service level: a refused category skips the whole pass — zero tracker searches, rows untouched."""
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        for tvdb_id in (11111, 22222):
            store.wanted.add(
                WantedItem(
                    media_ref=MediaRef(tvdb_id=tvdb_id), kind="movie", status="available", enqueued_at=int(time.time())
                )
            )
        orch = _orchestrator(_CategoryClient({}), scope=SCOPE)
        config = MagicMock()
        config.acquire = AcquireConfig()
        service = AcquisitionService(store=store, orchestrator=orch, event_bus=MagicMock(), config=config)

        with patch("personalscraper.acquire.orchestrator.log") as mock_log:
            summary = service.run()

        orch._tracker_registry.search_candidates.assert_not_called()
        assert summary.grabbed == summary.retried == 0
        assert [row.status for row in store.wanted.list_available()] == ["available", "available"]
        events = [c for c in mock_log.warning.call_args_list if c.args[0] == "acquire.grab_pass.scope_refused"]
        assert len(events) == 1
    finally:
        store.close()


def test_scope_set_category_under_the_download_root_is_added() -> None:
    """The category exists and files under the scope's root: the add goes through."""
    client = _CategoryClient({"tm-preprod": "/downloads/preprod/complete"})

    outcome = _grab(_orchestrator(client, scope=SCOPE))

    assert outcome.disposition == "success"
    assert len(client.add_calls) == 1


def test_scope_set_a_client_without_categories_keeps_todays_path() -> None:
    """A client that does not define categories (no capability) is added to as before."""
    client = _SharedClient()

    assert _grab(_orchestrator(client, scope=SCOPE)).disposition == "success"


# --- Unscoped instance (prod): never adopt a torrent held under a sandbox category ---

SANDBOXES = ("tm-preprod", "tm-dev")


def test_unscoped_grab_of_a_hash_held_by_a_sandbox_is_refused_without_add() -> None:
    """Prod, hash in a sandbox category -> no add, the decision reason is sandbox_hash."""
    client = _SharedClient(present={INFO_HASH})
    client.held = {"tm-dev": {INFO_HASH}}
    outcome = _grab(_orchestrator(client, scope=None, sandbox_categories=SANDBOXES))

    assert client.add_calls == []
    assert outcome.disposition == "retryable"
    assert outcome.reason == "sandbox_hash"


def test_unscoped_grab_of_a_hash_held_under_a_sandbox_subcategory_is_refused() -> None:
    """A category filter that is exact misses ``tm-dev/x``; the torrent's own category still says it is a sandbox's."""
    client = _SharedClient(present={INFO_HASH})
    client.held = {"tm-dev/x": {INFO_HASH}}
    assert client.get_by_category("tm-dev") == []
    outcome = _grab(_orchestrator(client, scope=None, sandbox_categories=SANDBOXES))

    assert client.add_calls == []
    assert outcome.disposition == "retryable"
    assert outcome.reason == "sandbox_hash"


def test_unscoped_grab_of_a_hash_under_a_lookalike_category_keeps_todays_add() -> None:
    """``tm-devX`` is not under ``tm-dev``: the subcategory prefix is ``tm-dev/``."""
    client = _SharedClient(present={INFO_HASH})
    client.held = {"tm-devX": {INFO_HASH}}
    outcome = _grab(_orchestrator(client, scope=None, sandbox_categories=SANDBOXES))

    assert outcome.disposition == "success"
    assert len(client.add_calls) == 1


def test_unscoped_grab_sandbox_hash_comparison_ignores_case() -> None:
    """A sandbox hash reported in upper case is still the sandbox's."""
    client = _SharedClient(present={INFO_HASH})
    client.held = {"tm-preprod": {INFO_HASH.upper()}}
    _grab(_orchestrator(client, scope=None, sandbox_categories=SANDBOXES))

    assert client.add_calls == []


def test_unscoped_grab_of_a_hash_prod_holds_keeps_todays_add() -> None:
    """Prod, hash held outside every sandbox category (prod's own) -> the add proceeds as ever."""
    client = _SharedClient(present={INFO_HASH})
    client.held = {"tm-dev": {"beef5678"}}
    outcome = _grab(_orchestrator(client, scope=None, sandbox_categories=SANDBOXES))

    assert outcome.disposition == "success"
    assert client.add_calls == [{"category": None, "tags": [PROVIDER], "limits": None}]


def test_unscoped_grab_without_sandbox_categories_is_unchanged() -> None:
    """No sandbox category configured -> no listing, the add proceeds as ever."""
    client = _SharedClient()
    client.held = {"tm-dev": {INFO_HASH}}
    outcome = _grab(_orchestrator(client, scope=None))

    assert outcome.disposition == "success"
    assert len(client.add_calls) == 1


def test_unscoped_grab_is_refused_when_the_client_cannot_look_a_hash_up() -> None:
    """Fail closed: a client that cannot look a hash up cannot prove the hash is not a sandbox's."""

    class _NoLookup(_SharedClient):
        get_by_hashes = None  # type: ignore[assignment]

    client = _NoLookup()
    outcome = _grab(_orchestrator(client, scope=None, sandbox_categories=SANDBOXES))

    assert client.add_calls == []
    assert outcome.reason == "scope_unverifiable"


def test_unscoped_grab_with_an_underivable_hash_is_refused() -> None:
    """Fail closed: a source yielding no hash cannot be proved free of the sandboxes."""
    client = _SharedClient()
    outcome = _grab(_orchestrator(client, scope=None, sandbox_categories=SANDBOXES), _source(ValueError("no hash")))

    assert client.add_calls == []
    assert outcome.reason == "hash_underivable"


def test_unscoped_grab_gives_way_to_the_next_candidate_when_a_sandbox_holds_the_top() -> None:
    """The top candidate is a sandbox's torrent: the next ranked one is added."""
    client = _SharedClient()
    client.held = {"tm-dev": {INFO_HASH}}
    orch = _orchestrator(
        client,
        scope=None,
        sandbox_categories=SANDBOXES,
        candidates=[_candidate("t1", INFO_HASH, 50), _candidate("t2", "beef5678", 10)],
    )
    outcome = _grab(orch, _source(INFO_HASH), _source("beef5678"))

    assert outcome.disposition == "success"
    assert len(client.add_calls) == 1
