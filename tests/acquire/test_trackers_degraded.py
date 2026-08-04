"""A partial tracker outage must not be persisted as a definitive absence (D2).

``SearchOutcome.all_errored`` only covers a UNANIMOUS failure. With one tracker down and
the other legitimately empty, the search used to conclude ``no_candidates`` / ``found=0``
— claiming knowledge it did not have, and burning an attempt for it.

Live evidence (2026-08-04 03:10): c411 answered HTTP 429 "Rate limit exceeded" three times
for ``Widow's Bay S01E10``; the row persisted ``no_candidates`` / ``found=0``. The same
query replayed at 14:00 returned ``raw=25, exact_episode=9`` — the releases existed.

This is the module's OWN documented contract: ``SearchVerdict.found`` is
« None = not concluded (NEVER 0 on outage) ».
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.conf.models.acquire import AcquireConfig, BandwidthConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef

# Pinned service clock: 1h after the items' enqueued_at (1_700_000_000). With the
# default Hot/Warm/Cold/30d cadence this keeps a fresh row DUE and far from cutoff —
# mirrors tests/acquire/test_search_verdicts.py.
_PINNED_NOW = 1_700_003_600


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin ``service.time.time`` so the fixture rows stay due and pre-cutoff."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _orchestrator_returning(outcome: SearchOutcome) -> GrabOrchestrator:
    """Build an orchestrator whose registry answers with *outcome*."""
    registry = MagicMock()
    registry.search_candidates.return_value = outcome
    return GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=None,
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )


def _item() -> WantedItem:
    """A minimal movie wanted item — the kind is irrelevant to this exit path."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=99),
        kind="movie",
        status="pending",
        enqueued_at=1_700_000_000,
    )


class TestPartialOutageIsRetryable:
    """Empty results + SOME tracker errors ⇒ degraded, never a clean not_found."""

    def test_one_of_two_trackers_errored_yields_trackers_degraded(self) -> None:
        """1 tracker down, 1 tracker empty ⇒ retryable / trackers_degraded / found is None."""
        orchestrator = _orchestrator_returning(
            SearchOutcome(
                results=[],
                trackers_queried=2,
                trackers_errored=1,
                errored_names=["c411"],
                queried_names=["c411", "tr4ker"],
                errors={"c411": "api"},
            )
        )

        verdict = orchestrator.search(_item(), QualityProfile())

        assert verdict.outcome == "trackers_degraded"
        assert verdict.disposition == "retryable"
        assert verdict.found is None, "found=0 on an outage is the exact lie this fixes"

    def test_clean_empty_search_is_unchanged(self) -> None:
        """0 trackers errored + 0 results ⇒ the historical not_found / no_candidates / 0."""
        orchestrator = _orchestrator_returning(
            SearchOutcome(
                results=[],
                trackers_queried=2,
                trackers_errored=0,
                errored_names=[],
                queried_names=["c411", "tr4ker"],
                errors={},
            )
        )

        verdict = orchestrator.search(_item(), QualityProfile())

        assert verdict.outcome == "no_candidates"
        assert verdict.disposition == "not_found"
        assert verdict.found == 0

    def test_all_trackers_errored_is_unchanged(self) -> None:
        """Unanimous failure keeps its own name — trackers_unavailable, not degraded."""
        orchestrator = _orchestrator_returning(
            SearchOutcome(
                results=[],
                trackers_queried=2,
                trackers_errored=2,
                errored_names=["c411", "tr4ker"],
                queried_names=["c411", "tr4ker"],
                errors={"c411": "api", "tr4ker": "api"},
            )
        )

        verdict = orchestrator.search(_item(), QualityProfile())

        assert verdict.outcome == "trackers_unavailable"
        assert verdict.found is None


class TestVocabularyStaysCoherent:
    """The new outcome must be declared everywhere the taxonomy is enumerated."""

    def test_trackers_degraded_is_a_known_outcome(self) -> None:
        """It belongs to SEARCH_OUTCOMES and maps to a status."""
        from personalscraper.acquire.orchestrator import SEARCH_OUTCOMES
        from personalscraper.acquire.service import SEARCH_OUTCOME_STATUS

        assert "trackers_degraded" in SEARCH_OUTCOMES
        assert SEARCH_OUTCOME_STATUS["trackers_degraded"] == "pending"

    def test_trackers_degraded_is_inconclusive(self) -> None:
        """It must never be reported as « searched, nothing exists »."""
        from personalscraper.acquire.orchestrator import INCONCLUSIVE_OUTCOMES

        assert "trackers_degraded" in INCONCLUSIVE_OUTCOMES


class TestDegradedEpisodeReadsAsNotVerified:
    """The UI must not say « En attente » about a search that never concluded (§2)."""

    def test_state_is_non_verifie_not_en_attente(self) -> None:
        """A degraded last verdict yields 'non_verifie', never 'en_attente'.

        ``derive_episode_state`` routes every member of ``INCONCLUSIVE_OUTCOMES`` to
        'non_verifie'. Adding ``trackers_degraded`` to that frozenset is what stops a
        rate-limited tracker from being displayed as « searched, nothing exists ».
        """
        from personalscraper.web.acquisition.states import derive_episode_state

        state = derive_episode_state(
            owned=False,
            wanted_status="pending",
            last_search_outcome="trackers_degraded",
            last_search_found=None,
        )

        assert state == "non_verifie"


class TestDegradedSearchDoesNotBurnAnAttempt:
    """A search that never concluded must not count toward the escalation threshold."""

    def test_refund_decrements_the_claim(self, store: ConcreteAcquireStore) -> None:
        """The refund gives back exactly the attempt ``claim_for_search`` consumed."""
        wid = store.wanted.add(_item())
        assert store.wanted.claim_for_search(wid, 1_700_003_600) is True
        assert store.wanted.get(wid).attempts == 1

        store.wanted.refund_search_attempt(wid)

        assert store.wanted.get(wid).attempts == 0

    def test_refund_never_goes_negative(self, store: ConcreteAcquireStore) -> None:
        """A refund on a row at attempts == 0 leaves it at 0, whatever the interleaving."""
        wid = store.wanted.add(_item())
        assert store.wanted.get(wid).attempts == 0

        store.wanted.refund_search_attempt(wid)
        store.wanted.refund_search_attempt(wid)

        assert store.wanted.get(wid).attempts == 0

    def test_attempts_unchanged_end_to_end_on_a_degraded_pass(self, store: ConcreteAcquireStore) -> None:
        """One full search pass ending degraded leaves ``attempts`` where it started."""
        from personalscraper.acquire.service import AcquisitionService

        wid = store.wanted.add(_item())
        before = store.wanted.get(wid).attempts

        orchestrator = _orchestrator_returning(
            SearchOutcome(
                results=[],
                trackers_queried=2,
                trackers_errored=1,
                errored_names=["c411"],
                queried_names=["c411", "tr4ker"],
                errors={"c411": "api"},
            )
        )
        config = MagicMock()
        config.acquire = AcquireConfig()
        service = AcquisitionService(
            store=store,  # type: ignore[arg-type]
            orchestrator=orchestrator,
            event_bus=MagicMock(),
            config=config,
        )

        service.run_search()

        row = store.wanted.get(wid)
        assert row.status == "pending", "a degraded search leaves the row queued"
        assert row.last_search_outcome == "trackers_degraded"
        assert row.last_search_found is None, "found must stay None — panne ≠ absence"
        assert row.attempts == before, (
            "a search that never concluded must not consume an attempt: it is the counter "
            "the starvation escalation reads"
        )
