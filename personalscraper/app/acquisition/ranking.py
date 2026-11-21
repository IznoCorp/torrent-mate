"""``RankingPreview``: ``previewRanking``'s samples, each with its tracker's ratio standing (K3 § 2.10).

The ranking editor's live preview is read-only and pure: the backend's fixed, representative
sample set scored under a candidate ranking, every sample kept visible. The samples are
duplicated from v0's (``web/routes/acquisition_ranking.py``: v1 never imports ``web/``), and
each carries the standing of its tracker so a criterion naming ``tracker_ratio_state`` scores
here exactly as :func:`personalscraper.api.tracker._ranking.rank` scores it in a grab — the
preview calls the same ``rank()`` and never a copy of it.

Every standing reads ``None`` until K5 writes ``ratio_state`` (O-8 A).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from personalscraper.api.tracker import RankingConfig, TrackerResult, rank
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.core.units import ByteSize

__all__ = ["PreviewedRelease", "RankingPreview"]


def _sample(
    tid: str,
    provider: str,
    title: str,
    size_gb: float,
    seeders: int,
    leechers: int,
    resolution: str,
    codec: str,
    source: str,
    language: str,
    *,
    freeleech: bool = False,
) -> TrackerResult:
    """Build one synthetic sample, its fields set as a tracker would after title-parsing.

    Args:
        tid: The sample's tracker id.
        provider: The tracker it stands for.
        title: Its title.
        size_gb: Its size in decimal gigabytes.
        seeders: Its seeders.
        leechers: Its leechers.
        resolution: Its resolution token.
        codec: Its video codec token.
        source: Its media source token.
        language: Its language marker.
        freeleech: Whether it is freeleech.

    Returns:
        The sample.
    """
    return TrackerResult(
        provider=provider,
        tracker_id=tid,
        title=title,
        size=ByteSize(round(size_gb * 1_000_000_000)),
        seeders=seeders,
        leechers=leechers,
        is_freeleech=freeleech,
        resolution=resolution,
        codec=codec,
        source=source,
        language=language,
    )


#: The preview's fixed samples: twelve releases spanning every scored axis (resolution, codec,
#: language, source, provider, seeders, freeleech) across two trackers. Same set as v0's preview.
_SAMPLES: tuple[TrackerResult, ...] = (
    _sample(
        "s1",
        "tr4ker",
        "Sample.2024.MULTi.2160p.UHD.BluRay.x265 — tr4ker",
        15,
        40,
        2,
        "2160p",
        "x265",
        "BluRay",
        "MULTI",
        freeleech=True,
    ),
    _sample(
        "s2",
        "tr4ker",
        "Sample.2024.MULTi.1080p.WEB-DL.x265 — tr4ker",
        4.5,
        120,
        5,
        "1080p",
        "x265",
        "WEB-DL",
        "MULTI",
        freeleech=True,
    ),
    _sample("s3", "c411", "Sample.2024.VFF.1080p.WEB-DL.x264 — c411", 4, 60, 3, "1080p", "x264", "WEB-DL", "VFF"),
    _sample(
        "s4",
        "c411",
        "Sample.2024.TRUEFRENCH.1080p.BluRay.x265 — c411",
        8,
        8,
        1,
        "1080p",
        "x265",
        "BluRay",
        "TRUEFRENCH",
    ),
    _sample("s5", "c411", "Sample.2024.VOSTFR.720p.HDTV.x264 — c411", 1.5, 15, 0, "720p", "x264", "HDTV", "VOSTFR"),
    _sample(
        "s6",
        "tr4ker",
        "Sample.2024.MULTi.2160p.BluRay.x265 — tr4ker (low seed)",
        16,
        3,
        0,
        "2160p",
        "x265",
        "BluRay",
        "MULTI",
    ),
    _sample(
        "s7",
        "tr4ker",
        "Demo.2025.TRUEFRENCH.2160p.REMUX.BluRay.x265 — tr4ker",
        52,
        200,
        10,
        "2160p",
        "x265",
        "BluRay",
        "TRUEFRENCH",
    ),
    _sample(
        "s8",
        "tr4ker",
        "Demo.S01.FRENCH.1080p.WEB-DL.x264 Season.Pack — tr4ker",
        80,
        25,
        6,
        "1080p",
        "x264",
        "WEB-DL",
        "FRENCH",
        freeleech=True,
    ),
    _sample(
        "s9",
        "c411",
        "Demo.2025.VOSTFR.1080p.WEB-DL.x265 — c411 (leech trap)",
        5,
        2,
        15,
        "1080p",
        "x265",
        "WEB-DL",
        "VOSTFR",
    ),
    _sample("s10", "c411", "Demo.2025.VFF.720p.HDTV.x264 — c411", 2.2, 4, 1, "720p", "x264", "HDTV", "VFF"),
    _sample(
        "s11",
        "tr4ker",
        "Demo.2025.MULTi.2160p.WEB-DL.x265 — tr4ker",
        12,
        35,
        8,
        "2160p",
        "x265",
        "WEB-DL",
        "MULTI",
        freeleech=True,
    ),
    _sample(
        "s12",
        "c411",
        "Demo.2025.VOSTFR.2160p.BluRay.x265 — c411 (FL low seed)",
        18,
        5,
        0,
        "2160p",
        "x265",
        "BluRay",
        "VOSTFR",
        freeleech=True,
    ),
)


@dataclass(frozen=True)
class PreviewedRelease:
    """One sample, scored under the candidate ranking.

    Attributes:
        title: The sample's title.
        provider: The tracker it stands for.
        size_bytes: Its size.
        seeders: Its seeders.
        leechers: Its leechers.
        freeleech: Whether it is freeleech.
        resolution: Its resolution token, or ``None``.
        codec: Its video codec token, or ``None``.
        source: Its media source token, or ``None``.
        language: Its language marker, or ``None``.
        score: Its score under the ranking.
        excluded: Whether it has fewer seeders than the ranking's ``min_seeders``: shown, sunk
            last, never dropped.
        tracker_ratio_state: Its tracker's standing against that tracker's own economy
            (``under_floor`` / ``under_target`` / ``comfortable``), or ``None`` when the tracker
            declares no economy or no ratio was observed.
    """

    title: str
    provider: str
    size_bytes: int
    seeders: int
    leechers: int
    freeleech: bool
    resolution: str | None
    codec: str | None
    source: str | None
    language: str | None
    score: int
    excluded: bool
    tracker_ratio_state: str | None


class RankingPreview:
    """``previewRanking``: the fixed samples scored under a candidate ranking, standing included."""

    def __init__(self, *, standing_of: Callable[[str], str | None]) -> None:
        """Hold the standing resolver.

        Args:
            standing_of: Tracker name → its ratio standing
                (:meth:`personalscraper.acquire.standing.RatioStanding.of`), or ``None``.
        """
        self._standing_of = standing_of

    @requires("previewRanking")
    def preview(self, actor: Actor, ranking: RankingConfig) -> list[PreviewedRelease]:
        """Score the fixed samples under *ranking*.

        Read-only and pure. To keep every sample visible, ``rank()`` runs with ``min_seeders``
        neutralised; each sample is instead flagged ``excluded`` when its seeders fall below the
        candidate's ``min_seeders`` — the operator SEES what the real ``rank()`` would drop.

        Args:
            actor: Who previews; authorised by ``@requires`` (``configuration.write``).
            ranking: The candidate ranking to score with.

        Returns:
            Every sample, scored: the kept ones by score descending (ties in the samples' order),
            then the excluded ones in the same order.

        Raises:
            AppUnauthenticated: ``auth.required`` — no actor.
            AppForbidden: ``right.missing`` or ``instance.forbidden_write`` — the actor may not.
        """
        standings = {provider: self._standing_of(provider) for provider in sorted({s.provider for s in _SAMPLES})}
        samples = [replace(s, tracker_ratio_state=standings[s.provider]) for s in _SAMPLES]
        scored = rank(samples, ranking.model_copy(update={"min_seeders": 0}))
        rows = [
            PreviewedRelease(
                title=result.title,
                provider=result.provider,
                size_bytes=result.size.bytes,
                seeders=result.seeders,
                leechers=result.leechers,
                freeleech=result.is_freeleech,
                resolution=result.resolution,
                codec=result.codec,
                source=result.source,
                language=result.language,
                score=score,
                excluded=result.seeders < ranking.min_seeders,
                tracker_ratio_state=result.tracker_ratio_state,
            )
            for result, score in scored
        ]
        # Excluded rows sink to the end; the sort is stable, so each group keeps its score order.
        rows.sort(key=lambda row: row.excluded)
        return rows
