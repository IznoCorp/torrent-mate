"""F4 regression: ``grab --dry-run`` must preview the REAL ranked candidate.

The ``--dry-run`` preview exists to let the operator validate a grab decision
BEFORE it is acted on (the dry-run-first rule). A preview that shows anything
other than the candidate the real grab would act on is a lie — and a lying
preview already caused a wrong-variant grab (a 3D SBS release previewed as the
top). DESIGN §10 ACC-07 / conformity fix F4: the preview must run the SAME
chain the orchestrator runs — search → filter → dedup → **rank** — and print
``rank(...)[0]``, NOT the unranked ``dedup(...)[0]``.

This test crafts two surviving candidates whose input order (``dedup`` keeps
first-seen order) puts the LOWER-ranked one first: ``deduped[0]`` and
``rank(...)[0]`` therefore differ. The dry-run must print the ranked winner.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from personalscraper.acquire._dedup import SearchOutcome, dedup
from personalscraper.acquire._filters import apply_hard_filters
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import (
    RankingConfig,
    RankingCriterion,
    ThresholdEntry,
    rank,
)
from personalscraper.cli import app
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

runner = CliRunner()


def _make_mock_app_context(*, acquire):
    """Build a minimal AppContext wrapping the given acquire context."""
    from personalscraper.core.app_context import AppContext
    from personalscraper.core.event_bus import EventBus

    return AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(),
        acquire=acquire,
    )


# A ranking config that discriminates purely on seeders: the 800-seeder release
# scores 1000, the 5-seeder release scores 0. rank() therefore reorders the
# list so the high-seeder candidate wins — the whole point of ranking.
_SEEDER_RANKING = RankingConfig(
    criteria=[
        RankingCriterion(
            field="seeders",
            thresholds=[ThresholdEntry(at=100, score=1000)],
        )
    ],
    min_seeders=1,
)

# Candidate A — FIRST in the search results, so it is ``dedup(...)[0]``. Low
# seeders ⇒ rank() scores it 0. This is the release the OLD (lying) dry-run
# printed as "Top".
_CANDIDATE_A = TrackerResult(
    provider="lacale",
    tracker_id="a1",
    title="Alpha 2024 MULTi 1080p WEB-DL x264-QTA",
    size=ByteSize(4_000_000_000),
    seeders=5,
    leechers=0,
    resolution="1080p",
    info_hash="a1a1a1",
    download_url="https://lacale.test/t/a",
)

# Candidate B — SECOND in the results, a distinct release (different codec +
# group ⇒ different fuzzy key ⇒ no merge with A). 800 seeders ⇒ rank() scores
# it 1000 and floats it to the top. This is the release the REAL grab acts on.
_CANDIDATE_B = TrackerResult(
    provider="lacale",
    tracker_id="b2",
    title="Alpha 2024 MULTi 1080p BluRay x265-QTB",
    size=ByteSize(9_000_000_000),
    seeders=800,
    leechers=0,
    resolution="1080p",
    info_hash="b2b2b2",
    download_url="https://lacale.test/t/b",
)


def test_grab_dry_run_top_is_real_ranked_candidate(tmp_path: Path, monkeypatch) -> None:
    """F4: dry-run prints ``rank(...)[0]``, not the unranked ``dedup(...)[0]``.

    Ground truth — run the real chain tail (hard-filter → dedup → rank) with
    the SAME ranking config the preview must use, and confirm the ordering is
    discriminating: ``dedup(...)[0]`` (A, 5 seeders) is NOT ``rank(...)[0]``
    (B, 800 seeders). The dry-run output must show B, never A.
    """
    media_ref = MediaRef(tvdb_id=54321)
    results = [_CANDIDATE_A, _CANDIDATE_B]
    survivors = apply_hard_filters(results, QualityProfile(), media_ref)
    representatives = dedup(survivors)
    ranked = rank(representatives, _SEEDER_RANKING)

    # Pre-conditions that make this a *discriminating* fixture: both candidates
    # survive + dedup keeps them distinct, and ranking reorders them.
    assert len(representatives) == 2, f"expected both candidates to survive+dedup; got {representatives}"
    assert representatives[0] is _CANDIDATE_A, "dedup must keep first-seen order (A first)"
    expected_top = ranked[0][0]
    assert expected_top is _CANDIDATE_B, "ranking must float the 800-seeder release to the top"
    assert expected_top is not representatives[0], "fixture must make dedup[0] != rank[0]"

    # 1. Seed a pending movie item.
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    seed_store = build_acquire_store(cfg)
    seed_store.wanted.add(
        WantedItem(
            media_ref=media_ref,
            kind="movie",
            status="pending",
            enqueued_at=int(time.time()),
        )
    )
    seed_store.close()

    # 2. Mock registry returns [A, B] and exposes the discriminating ranking
    #    (the real TrackerRegistry.ranking property in production).
    mock_registry = MagicMock()
    mock_registry.search_candidates.return_value = SearchOutcome(
        results=results, trackers_queried=1, trackers_errored=0
    )
    mock_registry.ranking = _SEEDER_RANKING

    test_store = build_acquire_store(cfg)
    from personalscraper.acquire.context import AcquireContext

    mock_acquire = AcquireContext(tracker_registry=mock_registry, store=test_store, grab=None)
    mock_app_ctx = _make_mock_app_context(acquire=mock_acquire)

    @contextmanager
    def _fake_boundary(config, settings, *, build_torrent_client=False):
        yield mock_app_ctx

    monkeypatch.setattr("personalscraper.commands.grab.per_step_boundary", _fake_boundary)

    result = runner.invoke(app, ["grab", "--dry-run"])
    assert result.exit_code == 0, f"expected exit 0; got {result.exit_code}:\n{result.output}"

    # The printed Top must be the REAL ranked winner (B, 800 seeders) — the
    # unranked dedup[0] (A) must NOT be presented as the candidate.
    assert "x265-QTB" in result.output, (
        f"F4: dry-run must preview the ranked winner (B); got:\n{result.output}"
    )
    assert "800 seeders" in result.output, f"F4: expected B's seeder count; got:\n{result.output}"
    assert "x264-QTA" not in result.output, (
        f"F4: dry-run must NOT present the unranked dedup[0] (A) as Top; got:\n{result.output}"
    )

    test_store.close()
