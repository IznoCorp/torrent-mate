"""Failing-first truth table for the five acquisition states (phase 4.1).

These tests import the FUTURE API (``personalscraper.web.acquisition.states``)
and assert the FROZEN CONTRACT in ``docs/features/acq-states/plan/phase-04-state-derivation.md``.
They MUST fail today — ``states.py`` does not exist and the current
``FollowedSeriesItem.status`` returns ``up_to_date`` for the founding-incident
case (empty catalog + no wanted rows → declared « À jour » while aired episodes
are missing).

Once phase 4.2 delivers ``states.py`` + the updated ``FollowedSeriesItem.status``
delegation, every test here must pass.
"""

from __future__ import annotations

import ast

import pytest

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES
from personalscraper.web.acquisition.states import NO_WANTED_FACTS, select_wanted_facts
from personalscraper.web.models.acquisition import FollowedSeriesItem, MediaRefResponse

# ── 1. The founding incident ──────────────────────────────────────────────


def test_empty_catalog_is_never_up_to_date() -> None:
    """A follow with no aired catalog must read « Non vérifié », never « À jour ».

    Reproduces the founding incident: Furious (TVDB 468000) was added at 09:18,
    the detect cron had last run at 03:00, so the catalog was empty and the card
    fell through to the raw wanted counters — zero rows — and declared « À jour »
    while three aired episodes were missing from the library.

    Fix: ``aired_count is None`` + no wanted activity → ``unverified``, never
    ``up_to_date``.  Current code returns ``up_to_date`` here — this test MUST fail
    with ``AssertionError`` today.
    """
    item = FollowedSeriesItem(
        id=1,
        title="Furious",
        media_ref=MediaRefResponse(tvdb_id=468000),
        active=True,
        kind="show",
        added_at=1750000000.0,
        wanted_pending=0,
        wanted_grabbed=0,
        aired_count=None,
        owned_count=None,
        inflight_count=None,
        queued_count=None,
        missing_count=None,
    )
    assert item.status == "unverified", (
        f"Founding incident: empty catalog returned {item.status!r}, expected 'unverified'. "
        "A series with zero catalogue knowledge is NOT up to date — we know nothing about it."
    )


# ── 2. Exhaustive truth table for derive_episode_state ────────────────────
#
# These imports WILL fail today (ModuleNotFoundError) — states.py does not
# exist yet.  Imported inside the test function so that test 1 above can still
# be collected and fail with the AssertionError we need to see.


def _import_future_api():
    """Import the future states module (will fail until 4.2 delivers it)."""
    from personalscraper.acquire.orchestrator import (  # noqa: F811
        INCONCLUSIVE_OUTCOMES,
    )
    from personalscraper.web.acquisition.states import (  # noqa: F811
        EpisodeState,
        derive_episode_state,
    )

    return EpisodeState, derive_episode_state, INCONCLUSIVE_OUTCOMES


#: Truth table — every contract rule, ordered as the spec demands (first-match
#: wins).  Each row is ``(owned, wanted_status, last_search_outcome,
#: last_search_found, expected, label)``.
TRUTH_TABLE: list[tuple[bool, str | None, str | None, int | None, str, str]] = [
    # ── Rule 1: owned beats everything ──
    # A file on disk wins — stale grabbed rows and inconclusive verdicts are
    # phantoms, exactly the Silo bug (the card said « En cours d'acquisition »
    # while every episode chip was green).
    (True, "grabbed", "success", 5, "in_library", "owned-beats-grabbed-phantom"),
    (True, None, None, None, "in_library", "owned-no-wanted-row"),
    (True, "searching", "circuit_open", 0, "in_library", "owned-beats-inconclusive"),
    (True, "available", "success", 3, "in_library", "owned-beats-available"),
    # ── Rule 2: wanted_status == "grabbed" ──
    (False, "grabbed", "success", 3, "acquiring", "grabbed-success"),
    (False, "grabbed", None, None, "acquiring", "grabbed-never-searched"),
    (False, "grabbed", "trackers_unavailable", 0, "acquiring", "grabbed-beats-inconclusive"),
    # ── Rule 3: wanted_status == "available" ──
    (False, "available", "success", 5, "to_grab", "available-with-found"),
    (False, "available", None, None, "to_grab", "available-never-searched"),
    (False, "available", "success", 0, "to_grab", "available-zero-found"),
    # ── Rule 4: last_search_outcome is None (never searched) ──
    # "searching" status falls through — a claim in flight derives from its
    # last verdict, not from the transient status.
    (False, "searching", None, None, "unverified", "searching-never-searched"),
    (False, None, None, None, "unverified", "no-row-never-searched"),
    (False, "pending", None, None, "unverified", "pending-never-searched"),
    # ── Rule 5: each INCONCLUSIVE outcome → unverified ──
    # A search that did NOT conclude (provider outage, open circuit, dead
    # swarm) must never read as « En attente ».  Absence of knowledge is
    # « Non vérifié », never an assertion about the trackers.
    (False, "searching", "trackers_unavailable", None, "unverified", "inconclusive-trackers-unavailable"),
    (False, "searching", "circuit_open", None, "unverified", "inconclusive-circuit-open"),
    (False, "searching", "search_api_error", None, "unverified", "inconclusive-search-api-error"),
    (False, "searching", "no_seeders", None, "unverified", "inconclusive-no-seeders"),
    # No wanted row + inconclusive outcome (still unverified — no knowledge).
    (False, None, "trackers_unavailable", None, "unverified", "inconclusive-no-row"),
    # ── Rule 6: (last_search_found or 0) > 0 → to_grab (defensive) ──
    (False, "searching", "success", 2, "to_grab", "found-positive-searching"),
    (False, None, "success", 1, "to_grab", "found-positive-no-row"),
    (False, "pending", "success", 3, "to_grab", "found-positive-pending"),
    # ── Rule 7: otherwise → pending (searched, concluded, nothing takeable) ──
    (False, "searching", "success", 0, "pending", "concluded-zero-searching"),
    (False, None, "success", 0, "pending", "concluded-zero-no-row"),
    (False, "pending", "success", 0, "pending", "concluded-zero-pending"),
    # Edge: abandoned/done rows should still derive from last verdict.
    (False, "abandoned", "success", 0, "pending", "abandoned-concluded-zero"),
    (False, "done", None, None, "unverified", "done-never-searched"),
    # ── Rule 1b (season-grab R5, review F7): absorbed short-circuits ──
    # An absorbed episode's acquisition is carried by its season wanted — it
    # is IN MOTION, never « never checked ». Ownership still wins above.
    (False, "absorbed", None, None, "absorbed", "absorbed-never-searched"),
    (False, "absorbed", "no_candidates", 0, "absorbed", "absorbed-beats-stale-verdict"),
    (True, "absorbed", None, None, "in_library", "owned-beats-absorbed"),
]


@pytest.mark.parametrize(
    "owned, wanted_status, last_search_outcome, last_search_found, expected, label",
    TRUTH_TABLE,
    ids=[row[5] for row in TRUTH_TABLE],
)
def test_derive_episode_state_truth_table(
    owned: bool,
    wanted_status: str | None,
    last_search_outcome: str | None,
    last_search_found: int | None,
    expected: str,
    label: str,
) -> None:
    """Every contract rule produces the expected EpisodeState.

    The derivation order IS the spec — first match wins.  This parametrised
    table covers every rule in the contract, including:
    - Ownership beats everything (the Silo phantom-grabbed bug).
    - Each INCONCLUSIVE outcome → ``unverified`` (panne ≠ absence).
    - ``searching`` status falls through to the verdict layer.
    - ``(last_search_found or 0) > 0`` → ``to_grab`` (defensive: verdict
      says takeable).
    - Concluded + zero found → ``pending``.
    - No wanted row at all + not owned → ``unverified``.
    """
    _EpisodeState, derive_episode_state, _INCONCLUSIVE_OUTCOMES = _import_future_api()
    result = derive_episode_state(
        owned=owned,
        wanted_status=wanted_status,
        last_search_outcome=last_search_outcome,
        last_search_found=last_search_found,
    )
    assert result == expected, (
        f"derive_episode_state(owned={owned}, wanted_status={wanted_status!r}, "
        f"last_search_outcome={last_search_outcome!r}, last_search_found={last_search_found}) "
        f"returned {result!r}, expected {expected!r}  [{label}]"
    )


# ── 3. Aggregation: FollowedSeriesItem.status ─────────────────────────────
#
# These tests assert the NEW aggregation rules (contract lines 51-60) against
# the future FollowedSeriesItem carrying the new per-state count fields
# (to_grab_count, acquiring_count, pending_count, unverified_count).
# They WILL fail today — those fields do not exist yet and the current status
# property uses the old inflight/queued/missing counters.


def _build_item(**overrides: object) -> FollowedSeriesItem:
    """Build a minimal FollowedSeriesItem with defaults for aggregation tests.

    Args:
        **overrides: Field values to override the defaults.

    Returns:
        A FollowedSeriesItem ready for status assertion.
    """
    defaults: dict[str, object] = {
        "id": 1,
        "title": "Test Series",
        "media_ref": MediaRefResponse(tvdb_id=403245),
        "active": True,
        "kind": "show",
        "added_at": 1750000000.0,
        "wanted_pending": 0,
        "wanted_grabbed": 0,
        "aired_count": 10,
        "owned_count": 0,
    }
    defaults.update(overrides)
    return FollowedSeriesItem(**defaults)  # type: ignore[arg-type]


def test_not_active_always_disabled() -> None:
    """An inactive follow is ``disabled`` regardless of any other state."""
    item = _build_item(active=False, aired_count=None)
    assert item.status == "disabled"


def test_no_catalog_not_active_disabled() -> None:
    """Inactive + no catalog → still ``disabled`` (active check wins)."""
    item = _build_item(active=False, aired_count=None, wanted_pending=0, wanted_grabbed=0)
    assert item.status == "disabled"


def test_aggregation_all_owned_is_up_to_date() -> None:
    """Every aired episode owned, nothing wanted → ``up_to_date``.

    Uses the future fields that phase 4.2 will add to FollowedSeriesItem.
    """
    item = _build_item(
        aired_count=5,
        owned_count=5,
        to_grab_count=0,  # type: ignore[call-arg]
        acquiring_count=0,  # type: ignore[call-arg]
        pending_count=0,  # type: ignore[call-arg]
        unverified_count=0,  # type: ignore[call-arg]
    )
    assert item.status == "up_to_date"


def test_aggregation_to_grab_wins_over_acquiring() -> None:
    """Most-actionable-first: ``to_grab`` beats ``acquiring``."""
    item = _build_item(
        aired_count=5,
        owned_count=1,
        to_grab_count=2,  # type: ignore[call-arg]
        acquiring_count=1,  # type: ignore[call-arg]
        pending_count=0,  # type: ignore[call-arg]
        unverified_count=0,  # type: ignore[call-arg]
    )
    assert item.status == "to_grab"


def test_aggregation_acquiring_wins_over_pending() -> None:
    """Most-actionable-first: ``acquiring`` beats ``pending``."""
    item = _build_item(
        aired_count=5,
        owned_count=1,
        to_grab_count=0,  # type: ignore[call-arg]
        acquiring_count=3,  # type: ignore[call-arg]
        pending_count=1,  # type: ignore[call-arg]
        unverified_count=0,  # type: ignore[call-arg]
    )
    assert item.status == "acquiring"


def test_aggregation_pending_wins_over_unverified() -> None:
    """Most-actionable-first: ``pending`` beats ``unverified``."""
    item = _build_item(
        aired_count=5,
        owned_count=1,
        to_grab_count=0,  # type: ignore[call-arg]
        acquiring_count=0,  # type: ignore[call-arg]
        pending_count=2,  # type: ignore[call-arg]
        unverified_count=2,  # type: ignore[call-arg]
    )
    assert item.status == "pending"


def test_aggregation_unverified_wins_over_up_to_date() -> None:
    """Most-actionable-first: ``unverified`` beats ``up_to_date``.

    A series with some owned episodes and some never-verified ones should read
    ``unverified``, not ``up_to_date`` — we genuinely do not know the state of
    the unverified episodes.
    """
    item = _build_item(
        aired_count=5,
        owned_count=3,
        to_grab_count=0,  # type: ignore[call-arg]
        acquiring_count=0,  # type: ignore[call-arg]
        pending_count=0,  # type: ignore[call-arg]
        unverified_count=2,  # type: ignore[call-arg]
    )
    assert item.status == "unverified"


# ── 3b. Which row governs (select_wanted_facts) ───────────────────────────


def test_no_rows_at_all_yields_the_never_searched_facts() -> None:
    """No row is no knowledge — the derivation must not be handed a verdict."""
    assert select_wanted_facts(()) == NO_WANTED_FACTS


@pytest.mark.parametrize("closed_status", ["done", "abandoned"])
def test_a_closed_row_never_governs(closed_status: str) -> None:
    """A closed row is history: its concluded verdict must not answer for the unit.

    Letting it speak is what made the completeness panel read ``pending``
    where the card read ``unverified`` for the same episode (acq-states §5.2).
    """
    rows = [(10, closed_status, "no_candidates", 0)]
    assert select_wanted_facts(rows) == NO_WANTED_FACTS


@pytest.mark.parametrize("open_status", ["pending", "searching", "available", "grabbed"])
def test_every_open_status_governs(open_status: str) -> None:
    """The four in-flight statuses all speak for their unit."""
    assert select_wanted_facts([(1, open_status, "available", 2)]) == (open_status, "available", 2)


def test_the_latest_open_row_wins_over_an_older_open_one() -> None:
    """A leftover open row from a previous pass must not outrank the current intent."""
    rows = [(10, "pending", "no_candidates", 0), (11, "grabbed", None, None)]
    assert select_wanted_facts(rows) == ("grabbed", None, None)


def test_the_latest_open_row_wins_regardless_of_input_order() -> None:
    """Selection is by id, not by the order the caller happens to yield rows in."""
    rows = [(11, "grabbed", None, None), (10, "pending", "no_candidates", 0)]
    assert select_wanted_facts(rows) == ("grabbed", None, None)


def test_a_closed_row_with_a_higher_id_does_not_shadow_an_open_one() -> None:
    """Closing a row must not silence the open row that replaced it."""
    rows = [(10, "available", "available", 2), (11, "abandoned", "no_candidates", 0)]
    assert select_wanted_facts(rows) == ("available", "available", 2)


def test_an_absorbed_row_governs_when_it_is_the_latest() -> None:
    """Review F7: an absorbed row SPEAKS — its episode is carried by a season.

    Silencing it (open-statuses-only selection) dropped the episode to the
    all-None « never searched » facts → « Non vérifié » on the matrix for
    every episode of a season being grabbed.
    """
    rows = [(10, "done", "success", 1), (12, "absorbed", None, None)]
    assert select_wanted_facts(rows) == ("absorbed", None, None)


def test_a_newer_live_row_outranks_an_older_absorbed_one() -> None:
    """Review F7 (R6 ordering): after a season fallback, the NEW live row wins.

    ``fallback_episodes`` re-enqueues fresh episode rows; the old absorbed row
    keeps its lower id, so the highest-id rule must hand governance to the new
    live row — not freeze the episode at « Absorbé » forever.
    """
    rows = [(10, "absorbed", None, None), (11, "pending", "no_candidates", 0)]
    assert select_wanted_facts(rows) == ("pending", "no_candidates", 0)
    # Order-independence, same pair.
    assert select_wanted_facts(reversed(rows)) == ("pending", "no_candidates", 0)


def test_an_absorbed_row_newer_than_a_stale_open_one_governs() -> None:
    """The absorption is the CURRENT intent when it is the latest row."""
    rows = [(10, "pending", "no_candidates", 0), (11, "absorbed", None, None)]
    assert select_wanted_facts(rows) == ("absorbed", None, None)


def test_open_statuses_come_from_the_domain_definition() -> None:
    """The « open » vocabulary has ONE definition — readers must not re-invent it."""
    assert OPEN_WANTED_STATUSES == frozenset({"pending", "searching", "available", "grabbed"})
    assert "done" not in OPEN_WANTED_STATUSES
    assert "abandoned" not in OPEN_WANTED_STATUSES


# ── 4. Module purity ──────────────────────────────────────────────────────


def test_states_module_is_pure() -> None:
    """``states.py`` imports NO provider/tracker/network module.

    The derivation MUST be a pure function of persisted facts — zero network
    I/O, zero provider client imports, zero tracker client imports.  This test
    will fail with ``FileNotFoundError`` until 4.2 creates ``states.py``, then
    it must pass permanently.
    """
    states_path = "personalscraper/web/acquisition/states.py"
    try:
        with open(states_path) as f:
            source = f.read()
    except FileNotFoundError:
        pytest.fail(
            f"{states_path} does not exist yet — it will be created in phase 4.2. "
            "This is expected in the failing-first run."
        )

    tree = ast.parse(source)

    forbidden: set[str] = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "socket",
    }
    # Provider/tracker subpackages (any import path starting with these).
    forbidden_prefixes: tuple[str, ...] = (
        "personalscraper.api.",
        "personalscraper.providers.",
        "personalscraper.trackers.",
    )

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[0]
                if base in forbidden:
                    violations.append(f"import {alias.name}")
                if alias.name.startswith(forbidden_prefixes):
                    violations.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            base = module.split(".")[0]
            if base in forbidden:
                violations.append(f"from {module} import ...")
            if module.startswith(forbidden_prefixes):
                violations.append(f"from {module} import ...")

    assert not violations, "states.py must be pure (no network/provider/tracker imports):\n" + "\n".join(
        f"  - {v}" for v in violations
    )
