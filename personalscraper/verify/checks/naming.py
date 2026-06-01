"""Directory naming check: ``Title (Year)`` format (DISPATCH stage).

Ported verbatim from ``verify/checker.py`` (the inline ``dir_naming`` blocks
in ``check_movie`` and ``check_tvshow``). The two media types emit different
message strings, replicated here. ``fixable=True``; the real ``fix()`` is
added in Phase 3 — for now it is a stub.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from personalscraper.verify.checks.base import CheckContext, FixAction

# Regex for "Title (Year)" directory format (copied from checker.py _DIR_PATTERN).
_DIR_PATTERN = re.compile(r"^.+ \(\d{4}\)$")


@register_check
class DirNaming:
    """Check that the directory name matches the ``Title (Year)`` format."""

    name = "dir_naming"
    group = "naming"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "Directory must be named 'Title (Year)'"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False when name is malformed.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``dir_naming`` result.
        """
        title = ctx.media_dir.name
        matched = bool(_DIR_PATTERN.match(title))
        if ctx.media_type == "movie":
            message = f"Directory name '{title}' doesn't match 'Title (Year)' format" if not matched else ""
        else:
            message = f"'{title}' doesn't match 'Title (Year)'" if not matched else ""
        return [
            CheckResult(
                name="dir_naming",
                passed=matched,
                severity=Severity.ERROR,
                message=message,
                fixable=True,
            )
        ]

    def fix(self, ctx: "CheckContext") -> "list[FixAction]":
        """Rename directory using title + year from NFO.

        Args:
            ctx: CheckContext (ctx.dry_run controls whether rename is applied).

        Returns:
            List of FixAction (0 or 1 entries).
        """
        import xml.etree.ElementTree as ET

        from personalscraper.logger import get_logger
        from personalscraper.nfo_utils import glob_nfo_candidates
        from personalscraper.verify.checks.base import FixAction

        log = get_logger("verify.checks.naming")

        if ctx.media_type == "movie":
            nfo_files = glob_nfo_candidates(ctx.media_dir)
        else:
            nfo_files = [ctx.media_dir / "tvshow.nfo"]

        nfo_path = next((f for f in nfo_files if f.exists()), None)
        if not nfo_path:
            return []
        try:
            tree = ET.parse(nfo_path)  # noqa: S314
            root = tree.getroot()
        except (ET.ParseError, OSError) as exc:
            log.warning("dir_naming_fix_nfo_parse_error", nfo=nfo_path.name, error=str(exc))
            return []

        title = (root.findtext("title") or "").strip()
        year = (root.findtext("year") or "").strip()
        if not title:
            return []
        canonical = f"{title} ({year})" if year else title
        if ctx.media_dir.name == canonical:
            return []
        new_dir = ctx.media_dir.parent / canonical
        if new_dir.exists():
            log.warning("dir_naming_fix_target_exists", canonical=canonical)
            return []
        description = f"Renamed '{ctx.media_dir.name}' → '{canonical}'"
        if not ctx.dry_run:
            try:
                ctx.media_dir.rename(new_dir)
                log.info("dir_naming_fix_renamed", description=description)
            except OSError as exc:
                log.error("dir_naming_fix_rename_failed", error=str(exc))
                return []
        return [FixAction(description=description, old_path=ctx.media_dir, new_path=new_dir)]
