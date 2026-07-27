"""Artwork presence checks: poster, landscape, season posters (DISPATCH stage).

Ported verbatim from ``verify/checker.py`` (the inline ``poster_present`` /
``artwork_landscape`` / ``season_posters`` blocks in ``check_movie`` and
``check_tvshow``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from personalscraper.core.artwork_naming import artwork_status
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from typing import Any

    from personalscraper.verify.checks.base import CheckContext, IndexContext


def _parsed_movie_title(ctx: "CheckContext") -> str:
    """Return the movie title parsed from the directory name (``checker.py`` parity).

    Args:
        ctx: Shared check context.

    Returns:
        Title with the ``(Year)`` suffix stripped.
    """
    m = re.match(r"^(.+?)\s*\(\d{4}\)$", ctx.media_dir.name)
    return m.group(1).strip() if m else ctx.media_dir.name


@register_check
class PosterPresent:
    """Check that the poster artwork exists (blocking — dispatch requires poster)."""

    name = "poster_present"
    group = "artwork"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "Poster artwork must be present"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False if poster absent.

        Presence is resolved by the ONE canonical detector
        (:func:`personalscraper.core.artwork_naming.artwork_status`), so this
        dispatch gate recognises every legitimate poster spelling — the bare Kodi
        ``poster.jpg``/``folder.jpg``, the scraper's ``{Title}-poster.jpg`` and the
        MediaElch folder-prefixed form — and agrees with the rescraper's own
        canonical detection (F5 / DESIGN §9: the gate and the repair loop must not
        contradict each other on the same directory). The error message still
        names the strict spelling the scraper *writes*, so the operator sees the
        expected filename.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``poster_present`` result.
        """
        exists = artwork_status(ctx.media_dir, ctx.media_type).poster
        if ctx.media_type == "movie":
            parsed_title = _parsed_movie_title(ctx)
            poster_name = ctx.patterns.format("movie_poster", Title=parsed_title)
            message = f"Poster not found: {poster_name}" if not exists else ""
        else:
            message = "poster.jpg not found" if not exists else ""
        return [
            CheckResult(
                name="poster_present",
                passed=exists,
                severity=Severity.ERROR,
                message=message,
            )
        ]

    def from_index(self, row: Mapping[str, Any], ctx: IndexContext) -> list[CheckResult] | None:
        """Derive poster_present result from DB row artwork_json.

        Args:
            row: DB row with artwork_json field.
            ctx: IndexContext.

        Returns:
            [failed CheckResult] if poster absent; [] if present; None if no artwork_json.
        """
        import json as _json

        artwork_raw = row["artwork_json"] if hasattr(row, "__getitem__") else getattr(row, "artwork_json", None)
        if not artwork_raw:
            return None
        try:
            artwork = _json.loads(artwork_raw)
        except (TypeError, ValueError):
            artwork = {}
        if not artwork.get("poster"):
            return [
                CheckResult(
                    name="poster_present",
                    passed=False,
                    severity=Severity.ERROR,
                    message="Poster missing (from index)",
                )
            ]
        return []


@register_check
class ArtworkLandscape:
    """Check that the landscape artwork exists (informational warning)."""

    name = "artwork_landscape"
    group = "artwork"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.WARNING
    description = "Landscape artwork should be present"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False if landscape absent.

        Presence is resolved by the ONE canonical detector
        (:func:`personalscraper.core.artwork_naming.artwork_status`), the same
        union the poster gate and the rescraper consult (F5 / DESIGN §9), so a
        landscape spelled ``{Folder}-landscape.jpg`` (MediaElch) or bare
        ``landscape.jpg`` is recognised regardless of media type.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``artwork_landscape`` result.
        """
        exists = artwork_status(ctx.media_dir, ctx.media_type).landscape
        if ctx.media_type == "movie":
            parsed_title = _parsed_movie_title(ctx)
            landscape_name = ctx.patterns.format("movie_landscape", Title=parsed_title)
            message = f"Landscape not found: {landscape_name}" if not exists else ""
        else:
            message = "landscape.jpg not found" if not exists else ""
        return [
            CheckResult(
                name="artwork_landscape",
                passed=exists,
                severity=Severity.WARNING,
                message=message,
            )
        ]

    def from_index(self, row: Mapping[str, Any], ctx: IndexContext) -> list[CheckResult] | None:
        """Derive artwork_landscape result from DB row — movie-only in DB-mode.

        Args:
            row: DB row with artwork_json field.
            ctx: IndexContext.

        Returns:
            None for tvshow (not derivable); [result] or [] for movie.
        """
        import json as _json

        if ctx.media_type != "movie":
            return None  # DB-mode landscape is movie-only (DESIGN §9 quirk)
        artwork_raw = row["artwork_json"] if hasattr(row, "__getitem__") else getattr(row, "artwork_json", None)
        if not artwork_raw:
            return None
        try:
            artwork = _json.loads(artwork_raw)
        except (TypeError, ValueError):
            artwork = {}
        if not artwork.get("landscape"):
            return [
                CheckResult(
                    name="artwork_landscape",
                    passed=False,
                    severity=Severity.WARNING,
                    message="Landscape missing (from index)",
                )
            ]
        return []


@register_check
class SeasonPosters:
    """Check that each ``Saison XX`` season directory has its poster (TV shows only)."""

    name = "season_posters"
    group = "artwork"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.WARNING
    description = "Each season should have a season poster"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return N missing-poster warnings, or one ``passed=True`` result.

        Mirrors ``check_tvshow`` exactly : emit one WARNING per season dir
        whose poster is missing ; if none are missing, emit a single
        ``passed=True`` placeholder.

        Args:
            ctx: Shared check context.

        Returns:
            List of ``season_posters`` results (≥ 1).
        """
        show_dir = ctx.media_dir
        # Sort by name so the per-season CheckResults are emitted in a stable
        # order across filesystems (APFS vs ext4 iterdir order differs).
        season_dirs = sorted(
            (d for d in show_dir.iterdir() if d.is_dir() and SEASON_DIR_RE.match(d.name)),
            key=lambda d: d.name,
        )
        results: list[CheckResult] = []
        for sd in season_dirs:
            season_num = int(sd.name.split()[-1])
            poster_name = ctx.patterns.format("season_poster", Season=season_num)
            if not (show_dir / poster_name).exists():
                results.append(
                    CheckResult(
                        name="season_posters",
                        passed=False,
                        severity=Severity.WARNING,
                        message=f"Missing {poster_name}",
                    )
                )
        if not results:
            results.append(
                CheckResult(
                    name="season_posters",
                    passed=True,
                    severity=Severity.WARNING,
                    message="",
                )
            )
        return results
