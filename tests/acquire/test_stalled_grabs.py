"""Tests for the stalled-grab detector (acquire/stalled_grabs.py).

Regression anchor: wanted #95 « Spider-Man : Brand New Day » sat at ``grabbed``
from 2026-08-05 20:35 with its provenance stuck at ``ingested`` (the grabbed
release was a FLAC soundtrack that could never reach the film library). Nothing
in the product ever said so: the search pass only reclaims
``pending``/``searching``/``available``, so the row was parked for good, and the
F4 ``stuck`` flag is journey-level AND requires the folder to still be on disk.

product-intent §14.1: « récupéré » is a TRANSITORY state that must advance on
its own — only « pas encore diffusé » and « cherché, rien trouvé » are legitimate
resting states.
"""

from __future__ import annotations

from personalscraper.acquire._provenance_store import ProvenanceRow
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.stalled_grabs import (
    STALLED_AFTER_DISPATCH_SECONDS,
    STALLED_AFTER_INGEST_SECONDS,
    STALLED_WITHOUT_INGEST_SECONDS,
    list_stalled_grabs,
    stalled_grab_reason,
)
from personalscraper.core.identity import MediaRef

NOW = 1_800_000_000


def _wanted(
    *,
    status: str = "grabbed",
    last_search_at: int | None = None,
    enqueued_at: int = NOW,
    kind: str = "movie",
) -> WantedItem:
    return WantedItem(
        media_ref=MediaRef(tmdb_id=969681),
        kind=kind,
        status=status,
        enqueued_at=enqueued_at,
        last_search_at=last_search_at,
        id=95,
        grabbed_hash="1329fe9eef22234bd44cf0d1ce11f3bc76e11a75",
    )


def _prov(
    *,
    status: str = "ingested",
    grabbed_at: int | None = None,
    ingested_at: int | None = None,
    scraped_at: int | None = None,
    dispatched_at: int | None = None,
) -> ProvenanceRow:
    return ProvenanceRow(
        info_hash="1329fe9eef22234bd44cf0d1ce11f3bc76e11a75",
        followed_id=24,
        media_ref=MediaRef(tmdb_id=969681),
        kind="movie",
        ingest_path="/staging/097-TEMP/Michael Giacchino Spider-Man… FLAC",
        current_path="/staging/004-AUDIO/Michael Giacchino Spider-Man… FLAC",
        scraped_ref=None,
        dispatch_path=None,
        grabbed_at=grabbed_at,
        ingested_at=ingested_at,
        scraped_at=scraped_at,
        dispatched_at=dispatched_at,
        status=status,
    )


class TestIngestedButNeverShelved:
    """The Spider-Man shape: the download FINISHED (it was ingested) and stopped there."""

    def test_the_live_incident_is_flagged(self) -> None:
        """Ingested 3h ago, never dispatched, still at 'grabbed' → stalled, with a reason."""
        wanted = _wanted(last_search_at=NOW - 10_800)
        row = _prov(status="ingested", grabbed_at=NOW - 11_000, ingested_at=NOW - 10_800)

        reason = stalled_grab_reason(wanted, row, now=NOW)

        assert reason == "ingéré mais jamais rangé en médiathèque"

    def test_just_ingested_is_not_flagged(self) -> None:
        """LOAD-BEARING: dispatch is the LONG step (~50 min on a full run).

        Flagging an item that is merely mid-pipeline would cry wolf on every
        normal run — the horizon exists precisely to outlast a dispatch.
        """
        wanted = _wanted(last_search_at=NOW - 60)
        row = _prov(status="ingested", ingested_at=NOW - 60)

        assert stalled_grab_reason(wanted, row, now=NOW) is None

    def test_boundary_is_exclusive(self) -> None:
        """Exactly at the horizon is not yet stalled; one second past it is."""
        row_at = _prov(status="ingested", ingested_at=NOW - STALLED_AFTER_INGEST_SECONDS)
        row_past = _prov(status="ingested", ingested_at=NOW - STALLED_AFTER_INGEST_SECONDS - 1)

        assert stalled_grab_reason(_wanted(), row_at, now=NOW) is None
        assert stalled_grab_reason(_wanted(), row_past, now=NOW) is not None

    def test_scraped_counts_as_finished_download_too(self) -> None:
        """A row that reached 'scraped' and stopped is the same failure, later in the chain."""
        row = _prov(status="scraped", ingested_at=NOW - 20_000, scraped_at=NOW - 10_800)

        assert stalled_grab_reason(_wanted(), row, now=NOW) is not None


class TestStillDownloading:
    """A grab whose torrent has not finished must NOT be flagged — that is a legitimate wait."""

    def test_recent_grab_without_ingest_is_not_flagged(self) -> None:
        """LOAD-BEARING: a big torrent legitimately takes hours; 'grabbed' alone proves nothing."""
        wanted = _wanted(last_search_at=NOW - 10_800)
        row = _prov(status="grabbed", grabbed_at=NOW - 10_800, ingested_at=None)

        assert stalled_grab_reason(wanted, row, now=NOW) is None

    def test_safety_net_fires_past_the_long_horizon(self) -> None:
        """A download that never lands is still a « rien silencieux » — caught, later."""
        old = NOW - STALLED_WITHOUT_INGEST_SECONDS - 1
        wanted = _wanted(last_search_at=old)
        row = _prov(status="grabbed", grabbed_at=old, ingested_at=None)

        assert stalled_grab_reason(wanted, row, now=NOW) == "récupéré, rien n'a suivi depuis"

    def test_no_provenance_row_falls_back_to_the_wanted_clock(self) -> None:
        """A grab predating the spine has no journey — it must not become invisible."""
        old = NOW - STALLED_WITHOUT_INGEST_SECONDS - 1

        assert stalled_grab_reason(_wanted(last_search_at=old), None, now=NOW) is not None
        assert stalled_grab_reason(_wanted(last_search_at=NOW - 60), None, now=NOW) is None

    def test_falls_back_to_enqueued_at_when_never_searched(self) -> None:
        """No last_search_at either → the enqueue instant is the only clock left."""
        old = NOW - STALLED_WITHOUT_INGEST_SECONDS - 1

        assert stalled_grab_reason(_wanted(last_search_at=None, enqueued_at=old), None, now=NOW) is not None


class TestNotApplicable:
    """Only a parked « récupéré » qualifies — never a row that did its job."""

    def test_a_journey_that_just_reached_the_library_is_not_stalled(self) -> None:
        """The media reached the library: the wanted is legitimately awaiting reconcile.

        « Legitimately » is bounded — see :class:`TestLandedButNeverClosed` for what
        happens when that wait never ends.
        """
        row = _prov(status="dispatched", ingested_at=NOW - 900, dispatched_at=NOW - 600)

        assert stalled_grab_reason(_wanted(), row, now=NOW) is None

    def test_other_wanted_statuses_are_ignored(self) -> None:
        """Only 'grabbed' is the parked state §14.1 calls out; pending/done are not."""
        row = _prov(status="ingested", ingested_at=NOW - 90_000)

        for status in ("pending", "searching", "available", "done", "abandoned"):
            assert stalled_grab_reason(_wanted(status=status), row, now=NOW) is None


class TestRunFinishedWithoutShelving:
    """The deterministic trigger: a pipeline run COMPLETED and left the item behind.

    On 2026-08-05 the run that ingested the soundtrack finished at 20:40:24 with
    ``step=dispatch skipped, reason='no verified items'``. At that instant the product
    already knew the item would not be shelved — yet the operator had to ask two hours
    later. §14.3: the closing follows the LIBRARY, not a clock; the alert must follow the
    run, not a horizon.
    """

    INGESTED = NOW - 600  # ingested 10 min ago — far inside every horizon

    def test_run_finished_after_ingest_fires_immediately(self) -> None:
        """No horizon wait: the run is over and the item is still not shelved."""
        row = _prov(status="ingested", ingested_at=self.INGESTED)

        reason = stalled_grab_reason(_wanted(), row, now=NOW, last_run_finished_at=self.INGESTED + 5)

        assert reason == "un run s'est terminé depuis l'ingestion sans la ranger"

    def test_run_still_running_does_not_fire(self) -> None:
        """LOAD-BEARING: a run that has NOT finished since the ingest proves nothing.

        The item may be mid-pipeline, and dispatch alone takes ~50 min.
        """
        row = _prov(status="ingested", ingested_at=self.INGESTED)

        assert stalled_grab_reason(_wanted(), row, now=NOW, last_run_finished_at=self.INGESTED - 5) is None

    def test_unknown_last_run_falls_back_to_the_horizon(self) -> None:
        """No run history (fresh install, unreadable KV) → the clock still guards."""
        row = _prov(status="ingested", ingested_at=self.INGESTED)

        assert stalled_grab_reason(_wanted(), row, now=NOW, last_run_finished_at=None) is None

    def test_dispatched_item_never_fires_even_after_a_run(self) -> None:
        """The item DID reach the library — a finished run is the normal ending."""
        row = _prov(status="dispatched", ingested_at=self.INGESTED, dispatched_at=NOW - 60)

        assert stalled_grab_reason(_wanted(), row, now=NOW, last_run_finished_at=NOW - 30) is None

    def test_not_yet_ingested_is_untouched_by_run_history(self) -> None:
        """A still-downloading grab is not « left behind » by a run it never entered."""
        row = _prov(status="grabbed", grabbed_at=NOW - 600, ingested_at=None)

        assert stalled_grab_reason(_wanted(), row, now=NOW, last_run_finished_at=NOW - 30) is None


class TestLandedButNeverClosed:
    """The « Les Groos » shape: the media IS shelved and the acquisition never closed.

    Excluding a dispatched journey outright made this class of stall MUTE by
    construction. wanted 184 (Les Groos S01) was dispatched on 2026-08-28 11:08 and
    still read ``grabbed`` four days later: the reconciliation could not close it (the
    pack was one episode short of the aired catalog) and this detector answered « a
    success awaiting reconciliation » for as long as it was asked. Nothing else looks
    at that row — the search pass walks ``pending``, the grab pass ``available``.

    §14.1 admits two resting states, « pas encore diffusé » and « cherché, rien
    trouvé ». « Rangé, mais l'acquisition est restée ouverte » is neither.
    """

    def test_a_landed_acquisition_still_open_a_day_later_is_flagged(self) -> None:
        """Dispatched 22 h ago, wanted still 'grabbed' → the closure will never come."""
        row = _prov(status="dispatched", ingested_at=NOW - 90_000, dispatched_at=NOW - 80_000)

        reason = stalled_grab_reason(_wanted(), row, now=NOW)

        assert reason == "rangé en médiathèque, mais l'acquisition ne s'est jamais refermée"

    def test_a_reconciled_journey_still_open_is_flagged_too(self) -> None:
        """Either terminal name: an open row long after the media landed is the anomaly."""
        row = _prov(status="reconciled", ingested_at=NOW - 90_000, dispatched_at=NOW - 80_000)

        assert stalled_grab_reason(_wanted(), row, now=NOW) is not None

    def test_a_freshly_dispatched_acquisition_is_left_alone(self) -> None:
        """LOAD-BEARING: reconciliation runs on the NEXT pass, not the same instant."""
        row = _prov(status="dispatched", ingested_at=NOW - 600, dispatched_at=NOW - 60)

        assert stalled_grab_reason(_wanted(), row, now=NOW) is None

    def test_the_horizon_is_not_reached_at_the_horizon(self) -> None:
        """Boundary: strictly past the horizon fires, exactly at it does not."""
        at_horizon = _prov(status="dispatched", dispatched_at=NOW - STALLED_AFTER_DISPATCH_SECONDS)
        past_horizon = _prov(status="dispatched", dispatched_at=NOW - STALLED_AFTER_DISPATCH_SECONDS - 1)

        assert stalled_grab_reason(_wanted(), at_horizon, now=NOW) is None
        assert stalled_grab_reason(_wanted(), past_horizon, now=NOW) is not None

    def test_a_landed_journey_with_no_dispatch_instant_never_fires(self) -> None:
        """No instant is « I don't know », never « since the epoch ».

        Unreachable on today's data — both dispatch writers stamp status and instant
        together — but the horizon cannot be computed without a date, so the shape is
        pinned rather than left to arithmetic on ``None``.
        """
        row = _prov(status="dispatched", ingested_at=NOW - 90_000, dispatched_at=None)

        assert stalled_grab_reason(_wanted(), row, now=NOW) is None

    def test_a_freshly_reconciled_journey_is_left_alone_too(self) -> None:
        """The horizon applies to BOTH terminal names, not just the one that fires."""
        row = _prov(status="reconciled", ingested_at=NOW - 900, dispatched_at=NOW - 600)

        assert stalled_grab_reason(_wanted(), row, now=NOW) is None

    def test_the_alert_dates_the_stall_from_the_dispatch(self) -> None:
        """« Depuis quand » must read the LAST step, which for a landed journey is dispatch."""
        row = _prov(status="dispatched", ingested_at=NOW - 90_000, dispatched_at=NOW - 80_000)

        stalled = list_stalled_grabs(
            [_wanted()],
            lambda _hash: row,
            now=NOW,
            release_name_for=lambda _row: "Les.Groos.2026.S01…LOLOPC",
        )

        assert len(stalled) == 1
        assert stalled[0].since == NOW - 80_000
