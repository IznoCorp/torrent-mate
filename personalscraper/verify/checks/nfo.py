"""NFO presence, validity, and IDs checks (DISPATCH stage).

Ported verbatim from ``verify/checker.py`` (the inline ``nfo_present`` /
``nfo_valid`` / ``nfo_ids`` blocks in ``check_movie`` and ``check_tvshow``).
Path resolution mirrors ``checker.py`` exactly : movies resolve the NFO via
``patterns.format("movie_nfo", Title=parsed_title)`` (NOT a glob), TV shows
via ``patterns.tvshow_nfo``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from personalscraper.verify.checks.base import CheckContext, IndexContext

log = get_logger("verify.checks.nfo")


def _movie_nfo_path(ctx: "CheckContext") -> "Path":
    """Resolve the movie NFO path exactly as ``checker.py`` does.

    Mirrors ``MediaChecker.check_movie`` : parses the title from the
    directory name (stripping the ``(Year)`` suffix) and formats the
    ``movie_nfo`` pattern. Does NOT glob.

    Args:
        ctx: Shared check context.

    Returns:
        Path to the expected movie NFO (may not exist).
    """
    parsed_title = _extract_title_from_dir(ctx.media_dir.name)
    nfo_name = ctx.patterns.format("movie_nfo", Title=parsed_title)
    return ctx.media_dir / nfo_name


def _tvshow_nfo_path(ctx: "CheckContext") -> "Path":
    """Resolve the tvshow NFO path exactly as ``checker.py`` does.

    Args:
        ctx: Shared check context.

    Returns:
        Path to ``show_dir/tvshow.nfo`` (may not exist).
    """
    return ctx.media_dir / ctx.patterns.tvshow_nfo


@register_check
class NfoPresent:
    """Check that the expected NFO file exists."""

    name = "nfo_present"
    group = "nfo"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "NFO file must be present"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False if NFO absent.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``nfo_present`` result.
        """
        if ctx.media_type == "movie":
            nfo_path = _movie_nfo_path(ctx)
            nfo_name = nfo_path.name
            nfo_exists = nfo_path.exists()
            message = f"NFO not found: {nfo_name}" if not nfo_exists else ""
        else:
            nfo_path = _tvshow_nfo_path(ctx)
            nfo_exists = nfo_path.exists()
            message = "tvshow.nfo not found" if not nfo_exists else ""
        return [
            CheckResult(
                name="nfo_present",
                passed=nfo_exists,
                severity=Severity.ERROR,
                message=message,
            )
        ]

    def from_index(self, row: Mapping[str, Any], ctx: IndexContext) -> list[CheckResult] | None:
        """Derive nfo_present result from DB row.

        Args:
            row: DB row with nfo_status field.
            ctx: IndexContext with media_type and category.

        Returns:
            [failed CheckResult] if nfo_status=="missing"; [] otherwise; None never.
        """
        nfo_status = row["nfo_status"] if hasattr(row, "__getitem__") else getattr(row, "nfo_status", None)
        if nfo_status == "missing":
            return [
                CheckResult(
                    name="nfo_present",
                    passed=False,
                    severity=Severity.ERROR,
                    message="NFO missing (from index)",
                )
            ]
        return []  # "valid", "invalid", or NULL → not flagged by this check


@register_check
class NfoValid:
    """Check that the NFO has required fields (title + year for movies; title for TV)."""

    name = "nfo_valid"
    group = "nfo"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "NFO must contain required fields"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[]`` if NFO absent; ``[CheckResult]`` otherwise.

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when the NFO file is absent, else a single result.
        """
        if ctx.media_type == "movie":
            nfo_path = _movie_nfo_path(ctx)
            if not nfo_path.exists():
                return []
            nfo_root = _parse_nfo(nfo_path)
            has_title = nfo_root is not None and nfo_root.findtext("title")
            has_year = nfo_root is not None and nfo_root.findtext("year")
            nfo_valid = has_title and has_year
            return [
                CheckResult(
                    name="nfo_valid",
                    passed=bool(nfo_valid),
                    severity=Severity.ERROR,
                    message="" if nfo_valid else "NFO missing <title> or <year>",
                )
            ]
        else:
            nfo_path = _tvshow_nfo_path(ctx)
            if not nfo_path.exists():
                return []
            nfo_root = _parse_nfo(nfo_path)
            tv_has_title = nfo_root is not None and nfo_root.findtext("title")
            tv_valid = bool(tv_has_title)
            return [
                CheckResult(
                    name="nfo_valid",
                    passed=tv_valid,
                    severity=Severity.ERROR,
                    message="" if tv_valid else "tvshow.nfo invalid or missing <title>",
                )
            ]

    def from_index(self, row: Mapping[str, Any], ctx: IndexContext) -> list[CheckResult] | None:
        """Derive nfo_valid result from DB row.

        Args:
            row: DB row with nfo_status field.
            ctx: IndexContext.

        Returns:
            [failed CheckResult] if nfo_status=="invalid"; [] otherwise.
        """
        nfo_status = row["nfo_status"] if hasattr(row, "__getitem__") else getattr(row, "nfo_status", None)
        if nfo_status == "invalid":
            return [
                CheckResult(
                    name="nfo_valid",
                    passed=False,
                    severity=Severity.ERROR,
                    message="NFO invalid (from index)",
                )
            ]
        return []


@register_check
class NfoIds:
    """Check NFO external IDs (dynamic severity for movies — DISPATCH stage)."""

    name = "nfo_ids"
    group = "nfo"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "NFO must contain required external IDs"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[]`` if NFO root is None; severity dynamic for movies.

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when the NFO cannot be parsed, else a single result.
        """
        if ctx.media_type == "movie":
            nfo_path = _movie_nfo_path(ctx)
            nfo_root = _parse_nfo(nfo_path) if nfo_path.exists() else None
            if nfo_root is None:
                return []
            ids = _extract_ids(nfo_root)
            has_tmdb = bool(ids.get("tmdb"))
            has_imdb = bool(ids.get("imdb"))
            has_both = has_tmdb and has_imdb
            has_any = has_tmdb or has_imdb
            return [
                CheckResult(
                    name="nfo_ids",
                    passed=has_both,
                    severity=Severity.ERROR if not has_any else Severity.WARNING,
                    message="" if has_both else f"Missing IDs: tmdb={has_tmdb}, imdb={has_imdb}",
                )
            ]
        else:
            nfo_path = _tvshow_nfo_path(ctx)
            nfo_root = _parse_nfo(nfo_path) if nfo_path.exists() else None
            if nfo_root is None:
                return []
            ids = _extract_ids(nfo_root)
            has_tvdb = bool(ids.get("tvdb")) or bool(ids.get("tmdb"))
            return [
                CheckResult(
                    name="nfo_ids",
                    passed=has_tvdb,
                    severity=Severity.ERROR,
                    message="" if has_tvdb else "No TVDB or TMDB uniqueid",
                )
            ]


# --- module-level NFO helpers (copied verbatim from checker.py; Phase 3 consolidates) ---


def _parse_nfo(nfo_path: "Path") -> "ET.Element | None":
    """Parse an NFO XML file.

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


def _extract_ids(root: ET.Element) -> dict[str, str]:
    """Extract uniqueid values by type from NFO root.

    Args:
        root: Parsed NFO root element.

    Returns:
        Dict mapping type to id value (e.g. ``{"tmdb": "550"}``).
    """
    ids: dict[str, str] = {}
    for uid in root.findall("uniqueid"):
        uid_type = uid.get("type", "")
        uid_text = uid.text or ""
        if uid_type and uid_text:
            ids[uid_type] = uid_text
    return ids


def _extract_title_from_dir(dir_name: str) -> str:
    """Extract title from a directory name, stripping ``(Year)`` suffix.

    Args:
        dir_name: Directory name, possibly ``"Title (2024)"``.

    Returns:
        Title portion, or the full name if no year found.
    """
    m = re.match(r"^(.+?)\s*\(\d{4}\)$", dir_name)
    return m.group(1).strip() if m else dir_name
