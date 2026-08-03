"""Historical rows of REMOVED trackers must stay readable and honoured.

When a tracker is decommissioned, its client, its ``ProviderName`` member, its
activation entries and its ``tracker.json5`` provider block all disappear — but
the rows it left in ``acquire.db`` do not. A seed obligation is a promise made
to a tracker: it must keep vetoing a deletion until its seed time is served,
even though nothing in the code knows that tracker's name any more.

This file pins BOTH decommissioned trackers — ``"torr9"`` and ``"lacale"`` —
and is the single grep exemption for the zero-remnant proofs (rm-lacale D8 and
D10): every read-path test runs once per removed tracker.

These tests pin that the whole read path stays **string-based and fail-soft**
for an unknown tracker name:

- the store round-trips ``source_tracker`` / ``tracker_name`` / ``tracker``
  verbatim — no enum coercion anywhere, so a removed member cannot raise
  ``ValueError``;
- :class:`DeleteAuthority` still VETOes an unmet historical obligation (the
  floors live ON the row, not in config) and still ALLOWs a served one;
- the dispatch-time writer degrades to a logged ``tracker-unresolved`` MISS
  instead of crashing when a live torrent still carries the removed tracker's
  tag;
- the grab-time writer skips silently when the tracker has no config entry;
- ``ratio_state`` and ``cross_seed_history`` rows keyed on the removed tracker
  remain readable and inert;
- the web obligations read model (``ObligationItem.source_tracker: str``)
  renders a historical row as a plain string — no coercion, no crash.

Where the surviving rows actually are (measured on the operator's
``.data/acquire.db`` on 2026-07-28, so the tests target the real risk rather
than an assumed one):

- ``cross_seed_history`` — **6 torr9 rows** (alongside 6 c411). This is the
  only table holding real torr9 data, and it was the one table these tests
  originally missed.
- ``seed_obligation`` — 14 rows, **all c411, zero torr9**.
- ``ratio_state`` — empty.

The obligation and ratio tests therefore pin the contract *prospectively*: no
removed-tracker row exists in those tables today, but the guarantee they
encode (a promise made to a tracker outlives that tracker's code) is what must
hold every time a tracker is decommissioned while holding live obligations.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority, build_delete_authority
from personalscraper.acquire.domain import RatioState, SeedObligation
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._contracts import ProviderName
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import TrackerConfig, TrackerEconomyConfig, TrackerProviderConfig
from personalscraper.config import Settings
from personalscraper.core.delete_permit import ALLOW
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.auth.tokens import create_session_token
from tests.web._web_harness import web_client

#: The decommissioned trackers whose historical rows must stay readable.
_REMOVED_TRACKERS = ("torr9", "lacale")

_LIVE_ECONOMY = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time=259_200)


@pytest.fixture(params=_REMOVED_TRACKERS)
def removed(request: pytest.FixtureRequest) -> str:
    """Yield each decommissioned tracker name in turn.

    Args:
        request: Pytest fixture request carrying the current param.

    Returns:
        The decommissioned tracker name under test.
    """
    return str(request.param)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real lazy acquire store on a temp acquire.db, closed afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A :class:`ConcreteAcquireStore` (opens on first sub-store access).
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _historical_obligation(
    dispatched_path: str, *, tracker: str, min_seed_time_s: int, added_at: int
) -> SeedObligation:
    """Build a seed obligation left behind by a removed tracker.

    Args:
        dispatched_path: Absolute path the obligation guards.
        tracker: The decommissioned tracker name stored on the row.
        min_seed_time_s: Seeding floor stored ON the row (not read from config).
        added_at: Unix epoch seconds when the obligation was recorded.

    Returns:
        A frozen :class:`SeedObligation` whose ``source_tracker`` no longer
        matches any configured tracker.
    """
    return SeedObligation(
        info_hash="dead" * 10,
        source_tracker=tracker,
        min_seed_time_s=min_seed_time_s,
        min_ratio=1.0,
        added_at=added_at,
        dispatched_path=dispatched_path,
    )


def _torrent_item(*, name: str, size_bytes: int, tags: list[str]) -> MagicMock:
    """Build a torrent item with the REAL client surface (hash/name/size_bytes/tags)."""
    item = MagicMock()
    item.hash = "dead" * 10
    item.name = name
    item.size_bytes = size_bytes
    item.tags = tags
    return item


def test_enum_no_longer_carries_the_removed_tracker() -> None:
    """Precondition: torr9 is really gone from ``ProviderName``.

    Everything below is only meaningful because coercing the stored name would
    now raise — which is exactly why no read path may coerce it.
    """
    assert not hasattr(ProviderName, "TORR9")
    with pytest.raises(ValueError, match="torr9"):
        ProviderName("torr9")


def test_obligation_round_trips_verbatim(store: ConcreteAcquireStore, tmp_path: Path, removed: str) -> None:
    """A historical obligation is stored and read back with its tracker name intact."""
    guarded = tmp_path / "library" / "Old.Film.mkv"
    store.seed.add(
        _historical_obligation(str(guarded), tracker=removed, min_seed_time_s=259_200, added_at=int(time.time()))
    )

    by_hash = store.seed.find_active_by_hash("dead" * 10)
    assert by_hash is not None
    assert by_hash.source_tracker == removed

    under = store.seed.find_active_under(guarded)
    assert [o.source_tracker for o in under] == [removed]


def test_unmet_historical_obligation_still_vetoes_deletion(
    store: ConcreteAcquireStore, tmp_path: Path, removed: str
) -> None:
    """The promise outlives the client: an unserved obligation still blocks deletion."""
    guarded = tmp_path / "library" / "Old.Film.mkv"
    guarded.parent.mkdir(parents=True)
    guarded.write_bytes(b"x")
    store.seed.add(
        _historical_obligation(str(guarded), tracker=removed, min_seed_time_s=999_999, added_at=int(time.time()))
    )

    authority = build_delete_authority(store=store, torrent_client=None, economy={})
    decision = authority.may_delete(guarded)

    assert decision is not ALLOW
    assert removed in decision.reason


def test_served_historical_obligation_allows_deletion(
    store: ConcreteAcquireStore, tmp_path: Path, removed: str
) -> None:
    """Once the stored seed time is served, the historical obligation stops vetoing."""
    guarded = tmp_path / "library" / "Old.Film.mkv"
    guarded.parent.mkdir(parents=True)
    guarded.write_bytes(b"x")
    store.seed.add(
        _historical_obligation(str(guarded), tracker=removed, min_seed_time_s=60, added_at=int(time.time()) - 3_600),
    )

    authority = build_delete_authority(store=store, torrent_client=None, economy={})

    assert authority.may_delete(guarded) is ALLOW


def test_record_dispatch_degrades_to_a_logged_miss(
    store: ConcreteAcquireStore, tmp_path: Path, caplog: pytest.LogCaptureFixture, removed: str
) -> None:
    """A live torrent still tagged with the removed tracker yields a MISS, not a crash."""
    staging = tmp_path / "staging" / "Film.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Film.mkv"

    item = _torrent_item(name="Film.mkv", size_bytes=512, tags=[removed])
    client = MagicMock()
    client.get_completed.return_value = [item]
    client.is_seeding.return_value = True

    authority = DeleteAuthority(store=store, torrent_client=client, economy={"c411": _LIVE_ECONOMY})
    authority.record_dispatch(staging_source=staging, dispatched_dest=dest)

    # No obligation written (the tag resolves to no configured economy), and the
    # store was never even opened — the MISS returns before any write.
    assert store.seed.find_active_by_hash("dead" * 10) is None
    assert "tracker-unresolved" in caplog.text


def test_grab_obligation_writer_skips_the_removed_tracker(store: ConcreteAcquireStore, removed: str) -> None:
    """The grab-time writer skips silently when the tracker has no config entry."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    config.tracker = TrackerConfig(
        providers={"c411": TrackerProviderConfig(enabled=True, economy=_LIVE_ECONOMY)},
        priority=["c411"],
    )
    service = AcquisitionService(
        store=store,
        orchestrator=MagicMock(),
        event_bus=MagicMock(),
        config=config,
    )

    service._record_seed_obligation("beef" * 10, removed)  # must not raise

    assert store.seed.find_active_by_hash("beef" * 10) is None


def test_historical_cross_seed_row_stays_readable_and_inert(store: ConcreteAcquireStore, removed: str) -> None:
    """A ``cross_seed_history`` row from the removed tracker reads back and affects nobody.

    This is the ONE table that actually holds torr9 rows in production (6 of
    them). ``tracker`` is only ever a bound parameter in a ``WHERE`` / ``INSERT``
    — never SELECTed back out and never coerced to ``ProviderName`` — so the row
    stays readable under its own name, and a live tracker's dedup lookup for the
    same source hash is unaffected by it.
    """
    source_hash = "cafe" * 10

    store.cross_seed.record_search(source_hash, removed)

    # Readable under the removed tracker's own name.
    assert store.cross_seed.was_searched_recently(source_hash, removed, days=30) is True
    # Inert for everyone else: the historical row must not make a live tracker
    # look "already searched" and suppress a legitimate cross-seed search.
    assert store.cross_seed.was_searched_recently(source_hash, "c411", days=30) is False


def test_historical_ratio_state_row_stays_readable(store: ConcreteAcquireStore, removed: str) -> None:
    """``ratio_state`` is keyed by a plain tracker name — a removed one still reads back."""
    store.ratio.upsert(
        RatioState(
            tracker_name=removed,
            observed_ratio=1.8,
            accumulated_seed_time_s=500_000,
            hnr_count=0,
            updated_at=int(time.time()),
        )
    )

    row = store.ratio.get(removed)

    assert row is not None
    assert row.tracker_name == removed
    assert row.observed_ratio == 1.8


# ---------------------------------------------------------------------------
# Web read model (mirrors tests/unit/web/routes/test_acquisition_read.py)
# ---------------------------------------------------------------------------

#: Minimal acquire.db schema for the obligations endpoint (seed_obligation
#: LEFT JOIN ratio_state, plus the wanted/followed_series title-resolver join).
_WEB_ACQUIRE_DDL = """
CREATE TABLE IF NOT EXISTS followed_series (
    id                   INTEGER PRIMARY KEY,
    media_ref_json       TEXT    NOT NULL,
    title                TEXT    NOT NULL,
    active               INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    quality_profile_json TEXT,
    cadence_json         TEXT,
    added_at             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wanted (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'grabbed', 'done', 'abandoned')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    grabbed_hash    TEXT
);

CREATE TABLE IF NOT EXISTS seed_obligation (
    id               INTEGER PRIMARY KEY,
    info_hash        TEXT    NOT NULL,
    source_tracker   TEXT    NOT NULL,
    dispatched_path  TEXT,
    min_seed_time_s  INTEGER NOT NULL,
    min_ratio        REAL    NOT NULL,
    added_at         INTEGER NOT NULL,
    satisfied_at     INTEGER,
    breached_at      INTEGER,
    released_at      INTEGER,
    CHECK (min_seed_time_s >= 0 AND min_ratio >= 0)
);

CREATE TABLE IF NOT EXISTS ratio_state (
    tracker_name            TEXT    PRIMARY KEY,
    observed_ratio          REAL    NOT NULL DEFAULT 0.0,
    accumulated_seed_time_s INTEGER NOT NULL DEFAULT 0,
    hnr_count               INTEGER NOT NULL DEFAULT 0,
    updated_at              INTEGER NOT NULL
);
"""


def test_web_obligations_read_model_renders_removed_tracker(test_config: Any, tmp_path: Path) -> None:
    """The obligations web read model renders a decommissioned tracker verbatim.

    ``ObligationItem.source_tracker`` is typed ``str`` (never ``ProviderName``),
    so a historical ``seed_obligation`` row left by the removed ``"lacale"``
    tracker must flow through ``GET /api/acquisition/obligations`` as a plain
    string — no enum coercion, no crash.
    """
    config = test_config
    acquire_path = tmp_path / "acquire.db"
    config.acquire.db_path = acquire_path
    config.indexer.db_path = tmp_path / "library.db"
    acquire_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(acquire_path))
    apply_pragmas(conn)
    conn.executescript(_WEB_ACQUIRE_DDL)
    conn.execute(
        "INSERT INTO seed_obligation (info_hash, source_tracker, min_seed_time_s, "
        "min_ratio, added_at) VALUES (?, ?, 86400, 1.5, ?)",
        ("feed" * 10, "lacale", int(time.time())),
    )
    conn.commit()
    conn.close()

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    client = web_client(config, settings)
    token = create_session_token("izno", "testsecret", 24)

    resp = client.get("/api/acquisition/obligations", cookies={"tm_session": token})

    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert [it["source_tracker"] for it in items] == ["lacale"]
