"""The pause gate (K3 P5, DESIGN § 2.4, O-3 A): a paused follow is neither searched nor grabbed.

The operator's ruling: « un suivi en pause n'est plus ni cherché ni téléchargé ; ses épisodes en
attente restent en attente et repartent à la reprise ». The gate sits in the queue both passes
share, BEFORE the ``limit``, so a capped pass counts takeable rows only. A paused follow's rows
keep their status untouched; a row with no follow is unaffected.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import structlog
from structlog.testing import capture_logs

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome, SearchVerdict
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

#: The items' enqueue clock and the pinned service clock one hour later: every fresh row is in
#: the Hot tier, due, and far from the cutoff.
_ENQUEUED_AT = 1_700_000_000
_PINNED_NOW = _ENQUEUED_AT + 3600


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin ``service.time.time`` so the fixture rows stay due."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


@pytest.fixture(autouse=True)
def _structlog_defaults() -> Iterator[None]:
    """Reset structlog so ``capture_logs`` sees the service's events whatever ran before."""
    structlog.reset_defaults()
    yield


def _follow(store: ConcreteAcquireStore, tvdb_id: int, *, active: bool = True) -> int:
    """Add a show follow, paused when ``active`` is false.

    Args:
        store: The acquire store.
        tvdb_id: The follow's TVDB id (a distinct one per follow).
        active: Whether the follow takes work.

    Returns:
        The follow's rowid.
    """
    fid = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=tvdb_id), title=f"Show {tvdb_id}", added_at=1))
    if not active:
        store.follow.set_active(fid, False)
    return fid


def _row(store: ConcreteAcquireStore, fid: int | None, tvdb_id: int, episode: int, *, status: str = "pending") -> int:
    """Insert an episode ``wanted`` row in the given status, the way the search pass leaves it.

    Args:
        store: The acquire store.
        fid: The owning follow's rowid, or ``None`` for a follow-less row.
        tvdb_id: The row's TVDB id.
        episode: The episode number.
        status: ``pending`` or ``available``.

    Returns:
        The row's rowid.
    """
    wid = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=tvdb_id),
            kind="episode",
            status="pending",
            enqueued_at=_ENQUEUED_AT,
            followed_id=fid,
            season=1,
            episode=episode,
        )
    )
    if status == "available":
        store.wanted.claim_for_search(wid, _PINNED_NOW)
        store.wanted.record_search_outcome(wid, "available", 3)
        store.wanted.set_status(wid, "available")
    return wid


def _status(store: ConcreteAcquireStore, wid: int) -> str:
    """Return a row's current status.

    Args:
        store: The acquire store.
        wid: The row's rowid.

    Returns:
        The status string.
    """
    row = store.wanted.get(wid)
    assert row is not None
    return row.status


def _orchestrator() -> MagicMock:
    """Build an orchestrator mock whose search finds nothing and whose grab succeeds.

    Returns:
        The mock; ``search`` and ``grab`` are the calls the tests watch.
    """
    orch = MagicMock(spec=GrabOrchestrator)
    orch.scope_allows_grab.return_value = True
    orch.search.return_value = SearchVerdict(disposition="not_found", outcome="no_candidates", found=0)
    orch.grab.return_value = MagicMock(spec=GrabOutcome, disposition="success", info_hash="abc123")
    return orch


def _service(store: ConcreteAcquireStore, orchestrator: MagicMock) -> AcquisitionService:
    """Build an acquisition service over a mock orchestrator.

    Args:
        store: The acquire store.
        orchestrator: The mock orchestrator.

    Returns:
        The service.
    """
    config = MagicMock()
    config.acquire = AcquireConfig()
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    )


# --- the grab pass ------------------------------------------------------------


def test_grab_pass_leaves_an_available_row_of_a_paused_follow(store: ConcreteAcquireStore) -> None:
    """An ``available`` row of an inactive follow is not grabbed and stays ``available``."""
    fid = _follow(store, 11, active=False)
    wid = _row(store, fid, 11, 1, status="available")
    orch = _orchestrator()

    with capture_logs() as logs:
        summary = _service(store, orch).run()

    orch.grab.assert_not_called()
    assert _status(store, wid) == "available"
    assert (summary.grabbed, summary.skipped) == (0, 1)
    paused = [e for e in logs if e["event"] == "acquire.service.follow_paused_skip"]
    assert [(e["wanted_id"], e["followed_id"]) for e in paused] == [(wid, fid)]


def test_grab_pass_takes_the_row_again_once_the_follow_resumes(store: ConcreteAcquireStore) -> None:
    """Reactivated, the waiting ``available`` row is grabbed at the next pass."""
    fid = _follow(store, 11, active=False)
    wid = _row(store, fid, 11, 1, status="available")
    orch = _orchestrator()
    svc = _service(store, orch)

    svc.run()
    orch.grab.assert_not_called()

    store.follow.set_active(fid, True)
    summary = svc.run()

    orch.grab.assert_called_once()
    assert summary.grabbed == 1
    assert _status(store, wid) == "grabbed"


def test_grab_pass_ignores_a_paused_follow_for_a_follow_less_row(store: ConcreteAcquireStore) -> None:
    """A row with no follow is taken as before, next to a paused follow's skipped one."""
    paused = _follow(store, 11, active=False)
    _row(store, paused, 11, 1, status="available")
    free = _row(store, None, 12, 1, status="available")
    orch = _orchestrator()

    summary = _service(store, orch).run()

    assert [c.args[0].id for c in orch.grab.call_args_list] == [free]
    assert (summary.grabbed, summary.skipped) == (1, 1)


def test_grab_pass_cap_counts_takeable_rows_only(store: ConcreteAcquireStore) -> None:
    """``limit=1`` whose first row is a paused follow's takes the next row: the gate is before the cap."""
    paused = _follow(store, 11, active=False)
    live = _follow(store, 12)
    first = _row(store, paused, 11, 1, status="available")
    second = _row(store, live, 12, 1, status="available")
    orch = _orchestrator()

    summary = _service(store, orch).run(limit=1)

    assert [c.args[0].id for c in orch.grab.call_args_list] == [second]
    assert _status(store, first) == "available"
    assert summary.grabbed == 1


def test_grab_pass_scoped_to_a_paused_follow_takes_nothing(store: ConcreteAcquireStore) -> None:
    """A per-series manual trigger on a paused follow grabs nothing and counts only its own rows."""
    paused = _follow(store, 11, active=False)
    other = _follow(store, 12, active=False)
    _row(store, paused, 11, 1, status="available")
    _row(store, other, 12, 1, status="available")
    orch = _orchestrator()

    summary = _service(store, orch).run(followed_id=paused)

    orch.grab.assert_not_called()
    assert (summary.grabbed, summary.skipped) == (0, 1)


# --- the search pass ----------------------------------------------------------


def test_search_pass_leaves_a_pending_row_of_a_paused_follow(store: ConcreteAcquireStore) -> None:
    """A ``pending`` row of an inactive follow is not searched and stays ``pending`` (not claimed)."""
    fid = _follow(store, 11, active=False)
    wid = _row(store, fid, 11, 1)
    orch = _orchestrator()

    with capture_logs() as logs:
        summary = _service(store, orch).run_search()

    orch.search.assert_not_called()
    assert _status(store, wid) == "pending"
    row = store.wanted.get(wid)
    assert row is not None and row.attempts == 0 and row.last_search_at is None
    assert summary.skipped == 1
    paused = [e for e in logs if e["event"] == "acquire.service.follow_paused_skip"]
    assert [(e["wanted_id"], e["followed_id"]) for e in paused] == [(wid, fid)]


def test_search_pass_takes_the_row_again_once_the_follow_resumes(store: ConcreteAcquireStore) -> None:
    """Reactivated, the waiting ``pending`` row is searched at the next pass."""
    fid = _follow(store, 11, active=False)
    wid = _row(store, fid, 11, 1)
    orch = _orchestrator()
    svc = _service(store, orch)

    svc.run_search()
    orch.search.assert_not_called()

    store.follow.set_active(fid, True)
    svc.run_search()

    assert [c.args[0].id for c in orch.search.call_args_list] == [wid]


def test_search_pass_ignores_a_paused_follow_for_a_follow_less_row(store: ConcreteAcquireStore) -> None:
    """A row with no follow is searched as before, next to a paused follow's skipped one."""
    paused = _follow(store, 11, active=False)
    _row(store, paused, 11, 1)
    free = _row(store, None, 12, 1)
    orch = _orchestrator()

    summary = _service(store, orch).run_search()

    assert [c.args[0].id for c in orch.search.call_args_list] == [free]
    assert summary.skipped == 1


def test_search_pass_cap_counts_takeable_rows_only(store: ConcreteAcquireStore) -> None:
    """``limit=1`` whose first row is a paused follow's searches the next row."""
    paused = _follow(store, 11, active=False)
    live = _follow(store, 12)
    first = _row(store, paused, 11, 1)
    second = _row(store, live, 12, 1)
    orch = _orchestrator()

    _service(store, orch).run_search(limit=1)

    assert [c.args[0].id for c in orch.search.call_args_list] == [second]
    assert _status(store, first) == "pending"


def test_search_pass_leaves_a_stale_searching_row_of_a_paused_follow(store: ConcreteAcquireStore) -> None:
    """The stale-searching sweep is gated too: a paused follow's orphan is not reclaimed."""
    fid = _follow(store, 11, active=False)
    wid = _row(store, fid, 11, 1)
    store.wanted.claim_for_search(wid, _ENQUEUED_AT - 3600)  # claimed long before the pinned clock
    orch = _orchestrator()

    _service(store, orch).run_search()

    orch.search.assert_not_called()
    assert _status(store, wid) == "searching"


def test_search_pass_skips_the_rows_of_a_removed_follow(store: ConcreteAcquireStore) -> None:
    """A removed follow is inactive by the projection (``active = 0``): its kept open rows wait too."""
    fid = _follow(store, 11)
    wid = _row(store, fid, 11, 1)
    store.follow.set_active(fid, False)  # what the projection writes for a removed follow
    orch = _orchestrator()

    _service(store, orch).run_search()

    orch.search.assert_not_called()
    assert _status(store, wid) == "pending"
