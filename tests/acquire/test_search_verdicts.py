"""Test-first: every search exit path persists its verdict.

These tests INTENTIONALLY FAIL today (ImportError / AttributeError) — the
``SearchVerdict``, ``SEARCH_OUTCOMES``, ``INCONCLUSIVE_OUTCOMES``,
``SEARCH_OUTCOME_STATUS``, and ``run_search`` API do not exist yet.
Sub-phase 2.3 implements them.  Do NOT mark xfail/skip.

Design: contract_phase2.md § exit-path table + § exhaustiveness guarantee +
§ inconclusive invariant.  The plan is phase-02-search-grab-split.md §2.2.

Outage-path invariant (load-bearing): ``found`` is ``None`` on every path where
the search did NOT conclude (circuit open, API error, all trackers down, empty
swarm after min_seeders, tracker auth).  Zero would mean « I looked, there is
nothing », which is **false** on an outage — exactly the lie this feature
removes (panne ≠ absence, DESIGN §1).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

# ---------------------------------------------------------------------------
# Store fixture (mirrors test_service.py — no acquire/ conftest yet).
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


# Pinned service clock: 1h after the items' enqueued_at (1_700_000_000).  With
# the default Hot/Warm/Cold/30d cadence this puts every _pending_item in the Hot
# tier (age 1h < 72h) and well within the 30d cutoff, so a fresh row
# (last_search_at is None) is DUE immediately.
_PINNED_NOW = 1_700_003_600  # enqueued_at + 3600s


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin ``service.time.time`` so legacy fixture rows stay due."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


# ---------------------------------------------------------------------------
# Helpers — mirror test_search_pass.py helpers.
# ---------------------------------------------------------------------------


def _pending_item(tvdb_id: int = 99) -> WantedItem:
    """Minimal pending WantedItem — mirrors test_service._pending_item."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="movie",
        status="pending",
        enqueued_at=1_700_000_000,
    )


def _service(
    store: ConcreteAcquireStore,
    orchestrator: GrabOrchestrator | MagicMock,
) -> AcquisitionService:
    """Build a service with a (mock) event_bus — mirrors test_search_pass._service."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    )


# ---------------------------------------------------------------------------
# Parametrized matrix — 9 orchestrator exit paths, one case each.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verdict_kwargs,expected_status,expected_outcome,expected_found",
    [
        # --- retryable (outage) — found=None: panne ≠ absence ---
        (
            {"disposition": "retryable", "outcome": "circuit_open", "found": None},
            "pending",
            "circuit_open",
            None,
        ),
        (
            {"disposition": "retryable", "outcome": "search_api_error", "found": None},
            "pending",
            "search_api_error",
            None,
        ),
        (
            {"disposition": "retryable", "outcome": "trackers_unavailable", "found": None},
            "pending",
            "trackers_unavailable",
            None,
        ),
        # --- retryable (dead swarm) — found=None: not concluded ---
        (
            {"disposition": "retryable", "outcome": "no_seeders", "found": None},
            "pending",
            "no_seeders",
            None,
        ),
        # --- not_found (clean search, nothing takeable yet) — found=0 ---
        (
            {"disposition": "not_found", "outcome": "no_candidates", "found": 0},
            "pending",
            "no_candidates",
            0,
        ),
        (
            {"disposition": "not_found", "outcome": "no_matching_episode", "found": 0},
            "pending",
            "no_matching_episode",
            0,
        ),
        (
            {"disposition": "not_found", "outcome": "no_matching_season", "found": 0},
            "pending",
            "no_matching_season",
            0,
        ),
        (
            {"disposition": "not_found", "outcome": "all_filtered", "found": 0},
            "pending",
            "all_filtered",
            0,
        ),
        # --- available — the one path where the item leaves pending ---
        (
            {"disposition": "available", "outcome": "available", "found": 3},
            "available",
            "available",
            3,
        ),
        # --- terminal — tracker_auth is permanent, but DEBOUNCED ---
        # This row has no previous verdict, so this is the FIRST all-auth
        # observation: the verdict is recorded, the status stays 'pending'. The
        # abandon lands on the second CONSECUTIVE one, which is the subject of
        # test_tracker_auth_debounce.py — the mapping in SEARCH_OUTCOME_STATUS
        # is still 'abandoned'; what changed is when the service applies it.
        (
            {"disposition": "terminal", "outcome": "tracker_auth", "found": None},
            "pending",
            "tracker_auth",
            None,
        ),
    ],
    ids=[
        "circuit_open",
        "search_api_error",
        "trackers_unavailable",
        "no_seeders",
        "no_candidates",
        "no_matching_episode",
        "no_matching_season",
        "all_filtered",
        "available",
        "tracker_auth",
    ],
)
def test_search_exit_path_persists_verdict(
    store: ConcreteAcquireStore,
    verdict_kwargs: dict,
    expected_status: str,
    expected_outcome: str,
    expected_found: int | None,
) -> None:
    """Every orchestrator exit path maps to the correct persisted triple.

    Outage paths assert ``found IS None`` — zero would mean « I looked, there
    is nothing », which is false on an outage; that lie is exactly what this
    feature removes (panne ≠ absence).
    """
    rowid = store.wanted.add(_pending_item())

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(**verdict_kwargs)

    service = _service(store, orch)
    summary = service.run_search()

    item = store.wanted.get(rowid)
    assert item is not None

    # --- Status transition ---
    assert item.status == expected_status, (
        f"expected status={expected_status!r} for outcome {expected_outcome!r}; got status={item.status!r}"
    )

    # --- Persisted outcome ---
    assert item.last_search_outcome == expected_outcome, (
        f"expected last_search_outcome={expected_outcome!r}; got {item.last_search_outcome!r}"
    )

    # --- Persisted found count ---
    if expected_found is None:
        assert item.last_search_found is None, (
            f"outcome {expected_outcome!r} MUST persist found=NULL (search did "
            f"not conclude); got {item.last_search_found!r}"
        )
    else:
        assert item.last_search_found == expected_found, (
            f"expected last_search_found={expected_found!r} for outcome "
            f"{expected_outcome!r}; got {item.last_search_found!r}"
        )

    # --- Summary buckets ---
    if expected_status == "available":
        assert summary.available == 1, f"expected summary.available=1; got {summary.available}"
    elif expected_status == "abandoned":
        assert summary.abandoned == 1, f"expected summary.abandoned=1; got {summary.abandoned}"
    elif expected_found is None:
        # retryable with found=None → unverified (search did not conclude)
        assert summary.unverified == 1, f"expected summary.unverified=1 for retryable; got {summary.unverified}"
    else:
        # not_found → waiting
        assert summary.waiting == 1, f"expected summary.waiting=1 for not_found; got {summary.waiting}"


# ---------------------------------------------------------------------------
# Exhaustiveness guarantee — a new outcome without a mapping fails here.
# ---------------------------------------------------------------------------


def test_outcome_status_mapping_is_exhaustive() -> None:
    """Every named outcome has a service status mapping, and vice versa.

    A new outcome added to the orchestrator without a service mapping fails
    here — the « forgotten exit path » cannot reopen silently.
    """
    from personalscraper.acquire.orchestrator import SEARCH_OUTCOMES
    from personalscraper.acquire.service import SEARCH_OUTCOME_STATUS

    assert set(SEARCH_OUTCOME_STATUS) == set(SEARCH_OUTCOMES), (
        f"SEARCH_OUTCOME_STATUS keys ({sorted(SEARCH_OUTCOME_STATUS)}) "
        f"must match SEARCH_OUTCOMES ({sorted(SEARCH_OUTCOMES)}) exactly — "
        f"a new outcome without a mapping (or a stale mapping) fails here"
    )


# ---------------------------------------------------------------------------
# Inconclusive invariant — outage outcomes ALWAYS map to pending.
# ---------------------------------------------------------------------------


def test_inconclusive_outcomes_never_map_to_waiting() -> None:
    """Every inconclusive outcome maps to 'pending' (never 'waiting' / 'available').

    INCONCLUSIVE_OUTCOMES are the paths where the search did NOT conclude:
    trackers_unavailable, circuit_open, search_api_error, no_seeders.  The
    parametrized matrix rows above already proved these persist ``found=None``
    (panne ≠ absence).  This test is the exhaustiveness backstop: a new
    inconclusive outcome added to the orchestrator MUST map to 'pending' in
    the service mapping — no silent drift into a « concluded » bucket.
    """
    from personalscraper.acquire.orchestrator import INCONCLUSIVE_OUTCOMES
    from personalscraper.acquire.service import SEARCH_OUTCOME_STATUS

    for outcome in INCONCLUSIVE_OUTCOMES:
        assert outcome in SEARCH_OUTCOME_STATUS, (
            f"inconclusive outcome {outcome!r} has no entry in SEARCH_OUTCOME_STATUS"
        )
        assert SEARCH_OUTCOME_STATUS[outcome] == "pending", (
            f"inconclusive outcome {outcome!r} maps to "
            f"{SEARCH_OUTCOME_STATUS[outcome]!r}, not 'pending' — "
            f"an outage must never read as « À jour » (panne ≠ absence)"
        )
