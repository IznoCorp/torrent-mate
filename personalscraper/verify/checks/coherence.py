"""STAGING-stage coherence checks (enforce). Read-only, WARNING-only."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from personalscraper.conf import ids as CID
from personalscraper.conf.classifier import classify_from_nfo
from personalscraper.logger import get_logger
from personalscraper.nfo_utils import glob_nfo_candidates
from personalscraper.verify.checks.base import CheckContext, CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

log = get_logger("verify.checks.coherence")


@register_check
class SortProcessCoherence:
    """Check that the media item's category matches its NFO type.

    Movies must not contain a tvshow.nfo; TV shows without a tvshow.nfo
    must not contain movie-style NFO files.
    """

    name = "sort_process_coherence"
    group = "coherence"
    stages = frozenset({CheckStage.STAGING})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.WARNING
    description = "Media item is in a category coherent with its NFO type"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        """Check sort↔process coherence for one media directory.

        Args:
            ctx: Shared check context with media_dir and media_type.

        Returns:
            Single-element list with a WARNING result. Always returns one
            result — an empty result list would mean "not applicable", but
            this check is always applicable.
        """
        if ctx.media_type == "movie":
            wrong = (ctx.media_dir / "tvshow.nfo").exists()
            msg = f"Wrong category: {ctx.media_dir.name} has tvshow.nfo but is in MOVIES" if wrong else ""
            return [CheckResult("sort_process_coherence", not wrong, Severity.WARNING, msg)]
        # tvshow
        if (ctx.media_dir / "tvshow.nfo").exists():
            return [CheckResult("sort_process_coherence", True, Severity.WARNING, "")]
        movie_nfos = [f for f in glob_nfo_candidates(ctx.media_dir) if f.name != "tvshow.nfo"]
        wrong = bool(movie_nfos)
        msg = f"Wrong category: {ctx.media_dir.name} has movie NFO but is in TVSHOWS" if wrong else ""
        return [CheckResult("sort_process_coherence", not wrong, Severity.WARNING, msg)]


@register_check
class NfoIdsCoherence:
    """Check that an NFO file contains at least one external ID (TMDB or IMDB).

    Returns an empty list when no NFO is found (the check is not applicable).
    Parses the NFO and checks for <uniqueid> elements with type="tmdb" or
    type="imdb".
    """

    name = "nfo_ids"
    group = "coherence"
    stages = frozenset({CheckStage.STAGING})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.WARNING
    description = "NFO carries at least one external ID (TMDB or IMDB)"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        """Check external IDs in the coherence NFO.

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when no NFO to inspect; otherwise a single-element
            list with pass/fail.
        """
        nfo_path = self._coherence_nfo(ctx)
        if nfo_path is None:
            return []  # nothing to inspect → name absent from CoherenceResult.checks (matches legacy)
        try:
            root = ET.parse(nfo_path).getroot()  # noqa: S314
        except (ET.ParseError, OSError):
            return [CheckResult("nfo_ids", False, Severity.WARNING, f"Cannot parse NFO: {nfo_path.name}")]
        has_tmdb = any(u.get("type") == "tmdb" and (u.text or "").strip() for u in root.findall("uniqueid"))
        has_imdb = any(u.get("type") == "imdb" and (u.text or "").strip() for u in root.findall("uniqueid"))
        ok = has_tmdb or has_imdb
        msg = "" if ok else f"Missing IDs: no TMDB or IMDB in {nfo_path.name}"
        return [CheckResult("nfo_ids", ok, Severity.WARNING, msg)]

    @staticmethod
    def _coherence_nfo(ctx: CheckContext) -> "Path | None":
        if ctx.media_type == "tvshow":
            p = ctx.media_dir / "tvshow.nfo"
            return p if p.exists() else None
        nfos = glob_nfo_candidates(ctx.media_dir)
        return nfos[0] if nfos else None


@register_check
class GenreCoherence:
    """Check that a TV show's genre does not imply a different category.

    Uses classify_from_nfo to determine the implied category. If the genre
    suggests TV_PROGRAMS, a warning is emitted so the operator can review
    and re-categorise manually. Returns an empty list when tvshow.nfo is
    absent.
    """

    name = "genre_coherence"
    group = "coherence"
    stages = frozenset({CheckStage.STAGING})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.WARNING
    description = "TV show genre does not imply a different category"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        """Check genre→category coherence for a TV show.

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when tvshow.nfo is absent; otherwise a single-element
            list. Fails when classify_from_nfo returns TV_PROGRAMS or raises
            an exception.
        """
        nfo_path = ctx.media_dir / "tvshow.nfo"
        if not nfo_path.exists():
            return []
        try:
            category_id, _ = classify_from_nfo(ctx.config, nfo_path, media_type="tvshow")
        except (ET.ParseError, OSError, ValueError) as exc:
            log.warning("coherence_genre_check_failed", nfo=nfo_path.name, error=str(exc))
            return [CheckResult("genre_coherence", False, Severity.WARNING, f"Genre check failed: {exc}")]
        if category_id == CID.TV_PROGRAMS:
            msg = f"Genre suggests TV program ({CID.TV_PROGRAMS}) not series for {ctx.media_dir.name}"
            return [CheckResult("genre_coherence", False, Severity.WARNING, msg)]
        return [CheckResult("genre_coherence", True, Severity.WARNING, "")]
