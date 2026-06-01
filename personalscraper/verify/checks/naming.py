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
        """Stub — the real directory-rename fix is wired in Phase 3.

        Args:
            ctx: Shared check context (respects ``ctx.dry_run``).

        Returns:
            Currently an empty list (no-op placeholder).
        """
        return []
