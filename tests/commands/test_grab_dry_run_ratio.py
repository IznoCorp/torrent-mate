"""F4 parity for the ratio standing: ``grab --dry-run`` previews the Top the real grab acts on.

Once a ranking criterion names ``tracker_ratio_state`` and a ratio is stored, the real grab scores
each candidate with its tracker's standing (the orchestrator's resolver). A preview that ranked
without it would score that criterion 0 and could print another Top: a lie, the very one F4 forbids.
The real grab's orchestrator comes from ``build_acquire_context``; the dry-run builds its standing
from the same configured trackers (``tracker_economies``).
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rich.console import Console

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire._factory import build_acquire_context
from personalscraper.acquire.context import AcquireContext
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import RatioState, WantedItem
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig, RankingCriterion
from personalscraper.commands.grab import _run_dry
from personalscraper.conf.models.acquire import BandwidthConfig
from personalscraper.conf.models.api_config import TrackerEconomyConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.units import ByteSize

_ECONOMY = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time="72h")

#: The standing alone decides: it dwarfs the one other axis the candidates differ on (seeders).
_RANKING = RankingConfig(
    criteria=[RankingCriterion(field="tracker_ratio_state", values={"under_floor": -50, "comfortable": 10})],
    min_seeders=1,
)

_MEDIA_REF = MediaRef(tvdb_id=54321)


def _candidate(provider: str, tracker_id: str, group: str, seeders: int) -> TrackerResult:
    """Build one takeable release of *provider*; two groups make two distinct releases.

    Args:
        provider: The tracker's name.
        tracker_id: The tracker's id for it.
        group: The release group, part of the title.
        seeders: Its seeders.

    Returns:
        The result.
    """
    return TrackerResult(
        provider=provider,
        tracker_id=tracker_id,
        title=f"Alpha 2024 MULTi 1080p WEB-DL x264-{group}",
        size=ByteSize(4_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=tracker_id.encode().hex().ljust(40, "0")[:40],
        download_url=f"https://{provider}.test/t/{tracker_id}",
    )


# The starved tracker lists FIRST and holds the most seeders: only its standing sinks it.
_STARVED = _candidate("c411", "s1", "QTSTARVED", 800)
_FED = _candidate("tr4ker", "f2", "QTFED", 5)


def _acquire(tmp_path: Path) -> tuple[AcquireContext, dict[str, SimpleNamespace]]:
    """Build the acquire context the way production does, over a temp ``acquire.db``.

    The ``c411`` ratio is under its floor, the ``tr4ker`` one above its target.

    Args:
        tmp_path: Pytest temp directory.

    Returns:
        The context, its grab handle present, and the configured trackers the dry-run reads.
    """
    config = MagicMock()
    config.acquire.db_path = tmp_path / "acquire.db"
    config.acquire.bandwidth = BandwidthConfig()
    config.ranking = _RANKING
    providers = {
        "c411": SimpleNamespace(economy=_ECONOMY),
        "tr4ker": SimpleNamespace(economy=_ECONOMY),
    }
    config.tracker.providers = providers
    config.torrent.active_scope.return_value = None
    config.torrent.active_sandbox_categories.return_value = ()
    registry = MagicMock()
    registry.ranking = _RANKING
    registry.search_candidates.return_value = SearchOutcome(
        results=[_STARVED, _FED], trackers_queried=2, trackers_errored=0
    )
    with patch("personalscraper.acquire._factory.build_tracker_registry", return_value=registry):
        ctx = build_acquire_context(
            config, MagicMock(), event_bus=EventBus(), cb_policy=MagicMock(), torrent_client=MagicMock()
        )
    for tracker, ratio in (("c411", 0.3), ("tr4ker", 5.0)):
        ctx.store.ratio.upsert(  # type: ignore[union-attr]
            RatioState(
                tracker_name=tracker,
                observed_ratio=ratio,
                accumulated_seed_time_s=0,
                hnr_count=0,
                updated_at=int(time.time()),
            )
        )
    return ctx, providers


def test_dry_run_top_is_the_one_the_real_grab_picks(tmp_path: Path) -> None:
    """A criterion on the standing and a stored ratio: dry-run and real search name the same Top."""
    ctx, providers = _acquire(tmp_path)
    try:
        assert ctx.store is not None
        assert ctx.grab is not None
        item = WantedItem(media_ref=_MEDIA_REF, kind="movie", status="pending", enqueued_at=int(time.time()))
        ctx.store.wanted.add(item)

        real_top = ctx.grab.orchestrator.search(item, QualityProfile()).chosen
        assert real_top is not None
        assert real_top.provider == "tr4ker", "fixture: the standing must sink the 800-seeder c411 release"

        out = io.StringIO()
        _run_dry(ctx, Console(file=out, width=300), limit=None, tracker_providers=providers)

        assert real_top.title in out.getvalue(), f"the preview must show the real Top; got:\n{out.getvalue()}"
        assert _STARVED.title not in out.getvalue(), (
            f"the preview must not show the sunk release; got:\n{out.getvalue()}"
        )
    finally:
        ctx.close()
