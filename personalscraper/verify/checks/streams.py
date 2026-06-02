"""Streamdetails check (DISPATCH stage, movie-only).

Ported verbatim from ``verify/checker.py`` (the inline ``streamdetails``
block in ``check_movie``). Only ``check_movie`` emits this check, and only
when the movie NFO parses to a non-None root.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.nfo import _movie_nfo_path
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from pathlib import Path

    from personalscraper.verify.checks.base import CheckContext

log = get_logger("verify.checks.streams")


@register_check
class Streamdetails:
    """Check that the movie NFO carries a ``<streamdetails>`` block."""

    name = "streamdetails"
    group = "streams"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie"})
    default_severity = Severity.WARNING
    description = "NFO should contain a <streamdetails> block"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[]`` when the NFO root is None; ``[CheckResult]`` otherwise.

        Mirrors ``check_movie``: the check runs only when the movie NFO
        parses successfully.

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when the NFO cannot be parsed, else a single result.
        """
        nfo_path = _movie_nfo_path(ctx)
        nfo_root = _parse_nfo(nfo_path) if nfo_path.exists() else None
        if nfo_root is None:
            return []
        has_sd = nfo_root.find(".//streamdetails") is not None
        return [
            CheckResult(
                name="streamdetails",
                passed=has_sd,
                severity=Severity.WARNING,
                message="" if has_sd else "No <streamdetails> in NFO",
            )
        ]


def _parse_nfo(nfo_path: "Path") -> "ET.Element | None":
    """Parse an NFO XML file (copied verbatim from checker.py).

    Args:
        nfo_path: Path to the NFO file.

    Returns:
        Root Element, or None if parse fails.
    """
    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        return tree.getroot()
    except (ET.ParseError, OSError) as exc:
        log.warning("verify_nfo_parse_failed", nfo=nfo_path.name, exc_info=True, error=str(exc))
        return None
