"""Acquisition ranking-preview route (ranking editor, #18).

Extracted from ``web/routes/acquisition.py`` to keep that module under the
1000-LOC ceiling (same precedent as ``acquisition_triggers.py`` and
``acquisition_overview.py``). This router shares the ``/api/acquisition``
prefix and is registered under the single ``guarded_api`` perimeter in
``app.py``.

Read-only + pure: no DB, no filesystem, no torrent client — scores a fixed
representative sample set with a POSTed candidate config. Not staging-guarded
and no CSRF header: it mutates nothing, so it is safe on the read-only staging
role and idempotent by construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from personalscraper.conf.models._ranking import RankingConfig
from personalscraper.web.models.acquisition import RankingPreviewRelease, RankingPreviewResponse

if TYPE_CHECKING:
    from personalscraper.api.tracker._base import TrackerResult

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])

# ── ranking preview (ranking editor, #18) ─────────────────────────────────


def _ranking_preview_samples() -> list["TrackerResult"]:
    """Build the fixed, representative release sample set for the ranking preview.

    Six synthetic releases spanning every scored axis (resolution, codec,
    language, source, provider, seeders, freeleech) so the operator sees a
    weight/value change reorder visible rows without running a real search.
    Fields are set explicitly (as the trackers would after title-parsing), so
    the preview scores exactly what a real grab would.
    """
    from personalscraper.api._units import ByteSize
    from personalscraper.api.tracker._base import TrackerResult

    return [
        TrackerResult(
            provider="tr4ker",
            tracker_id="s1",
            title="Sample.2024.MULTi.2160p.UHD.BluRay.x265 — tr4ker",
            size=ByteSize(15_000_000_000),
            seeders=40,
            leechers=2,
            is_freeleech=True,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="MULTI",
        ),
        TrackerResult(
            provider="tr4ker",
            tracker_id="s2",
            title="Sample.2024.MULTi.1080p.WEB-DL.x265 — tr4ker",
            size=ByteSize(4_500_000_000),
            seeders=120,
            leechers=5,
            is_freeleech=True,
            resolution="1080p",
            codec="x265",
            source="WEB-DL",
            language="MULTI",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s3",
            title="Sample.2024.VFF.1080p.WEB-DL.x264 — c411",
            size=ByteSize(4_000_000_000),
            seeders=60,
            leechers=3,
            resolution="1080p",
            codec="x264",
            source="WEB-DL",
            language="VFF",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s4",
            title="Sample.2024.TRUEFRENCH.1080p.BluRay.x265 — c411",
            size=ByteSize(8_000_000_000),
            seeders=8,
            leechers=1,
            resolution="1080p",
            codec="x265",
            source="BluRay",
            language="TRUEFRENCH",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s5",
            title="Sample.2024.VOSTFR.720p.HDTV.x264 — c411",
            size=ByteSize(1_500_000_000),
            seeders=15,
            leechers=0,
            resolution="720p",
            codec="x264",
            source="HDTV",
            language="VOSTFR",
        ),
        TrackerResult(
            provider="tr4ker",
            tracker_id="s6",
            title="Sample.2024.MULTi.2160p.BluRay.x265 — tr4ker (low seed)",
            size=ByteSize(16_000_000_000),
            seeders=3,
            leechers=0,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="MULTI",
        ),
        # ── 6 new samples (ticket 374) ──────────────────────────────
        TrackerResult(
            provider="tr4ker",
            tracker_id="s7",
            title="Demo.2025.TRUEFRENCH.2160p.REMUX.BluRay.x265 — tr4ker",
            size=ByteSize(52_000_000_000),
            seeders=200,
            leechers=10,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="TRUEFRENCH",
        ),
        TrackerResult(
            provider="tr4ker",
            tracker_id="s8",
            title="Demo.S01.FRENCH.1080p.WEB-DL.x264 Season.Pack — tr4ker",
            size=ByteSize(80_000_000_000),
            seeders=25,
            leechers=6,
            is_freeleech=True,
            resolution="1080p",
            codec="x264",
            source="WEB-DL",
            language="FRENCH",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s9",
            title="Demo.2025.VOSTFR.1080p.WEB-DL.x265 — c411 (leech trap)",
            size=ByteSize(5_000_000_000),
            seeders=2,
            leechers=15,
            resolution="1080p",
            codec="x265",
            source="WEB-DL",
            language="VOSTFR",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s10",
            title="Demo.2025.VFF.720p.HDTV.x264 — c411",
            size=ByteSize(2_200_000_000),
            seeders=4,
            leechers=1,
            resolution="720p",
            codec="x264",
            source="HDTV",
            language="VFF",
        ),
        TrackerResult(
            provider="tr4ker",
            tracker_id="s11",
            title="Demo.2025.MULTi.2160p.WEB-DL.x265 — tr4ker",
            size=ByteSize(12_000_000_000),
            seeders=35,
            leechers=8,
            is_freeleech=True,
            resolution="2160p",
            codec="x265",
            source="WEB-DL",
            language="MULTI",
        ),
        TrackerResult(
            provider="c411",
            tracker_id="s12",
            title="Demo.2025.VOSTFR.2160p.BluRay.x265 — c411 (FL low seed)",
            size=ByteSize(18_000_000_000),
            seeders=5,
            leechers=0,
            is_freeleech=True,
            resolution="2160p",
            codec="x265",
            source="BluRay",
            language="VOSTFR",
        ),
    ]


@router.post("/ranking/preview", response_model=RankingPreviewResponse)
def preview_ranking(body: RankingConfig) -> RankingPreviewResponse:
    """Score the representative sample set under a candidate ranking (#18).

    Read-only + pure: no DB, no filesystem, no torrent client — it scores the
    fixed :func:`_ranking_preview_samples` set with the POSTed candidate config
    so the editor can render a live preview of the acquisition ranking. To keep
    every sample VISIBLE (a live preview must never silently drop rows), scoring
    runs with ``min_seeders`` neutralized; each row is instead flagged
    ``excluded`` when its seeders fall below the candidate ``min_seeders`` — so
    the operator SEES which releases the real ``rank()`` would drop. Rows sort
    non-excluded first (by score desc), excluded last.

    Not staging-guarded and no CSRF header: it mutates nothing, so it is safe
    on the read-only staging role and idempotent by construction.

    Args:
        body: The candidate ranking configuration to score with.

    Returns:
        A :class:`RankingPreviewResponse` with the scored, sorted samples.
    """
    from personalscraper.api.tracker._ranking import rank

    samples = _ranking_preview_samples()
    # Neutralize the seeder floor so EVERY sample is scored and shown; flag the
    # ones the real min_seeders would have dropped rather than hiding them.
    scored = rank(samples, body.model_copy(update={"min_seeders": 0}))
    rows = [
        RankingPreviewRelease(
            title=result.title,
            provider=str(result.provider),
            resolution=result.resolution,
            codec=result.codec,
            language=result.language,
            source=result.source,
            seeders=result.seeders,
            leechers=result.leechers,
            is_freeleech=result.is_freeleech,
            score=score,
            excluded=result.seeders < body.min_seeders,
        )
        for result, score in scored
    ]
    # Excluded rows sink to the end; within each group keep the score order.
    rows.sort(key=lambda r: (r.excluded, -r.score))
    # known_trackers: the hardcoded factory roster, sorted for a stable order.
    # No torznab generic engine key exists in _TRACKER_CLASSES (ticket 374 check).
    from personalscraper.api.tracker._factory import _TRACKER_CLASSES

    known = sorted(_TRACKER_CLASSES)
    return RankingPreviewResponse(ranked=rows, known_trackers=known)
