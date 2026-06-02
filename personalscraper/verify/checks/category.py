"""Category-resolution check (DISPATCH stage, both media types).

Ported verbatim from ``verify/checker.py`` (the inline ``category`` blocks in
``check_movie`` and ``check_tvshow``). The check classifies the media from its
NFO genres and, as a side effect required by downstream consumers, stashes the
resolved category on ``ctx.resolved_category`` (DESIGN; plan Step 3).
Returns ``[]`` when the NFO is absent (mirrors ``check_*``: the block is guarded
by ``if nfo_exists``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.conf.classifier import classify_from_nfo
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.nfo import _movie_nfo_path, _tvshow_nfo_path
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from personalscraper.verify.checks.base import CheckContext


@register_check
class Category:
    """Resolve the storage category from NFO genres; stash it on the context."""

    name = "category"
    group = "category"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "Category must be resolvable from NFO genres"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[]`` if NFO absent; ``[CheckResult]`` otherwise.

        Side effect: sets ``ctx.resolved_category`` to the resolved category
        ID (or None) so later consumers can read it without re-classifying.

        Args:
            ctx: Shared check context.

        Returns:
            Empty list when the NFO file is absent, else a single result.
        """
        if ctx.media_type == "movie":
            nfo_path = _movie_nfo_path(ctx)
        else:
            nfo_path = _tvshow_nfo_path(ctx)
        if not nfo_path.exists():
            return []
        category, _reason = classify_from_nfo(ctx.config, nfo_path, ctx.media_type)
        ctx.resolved_category = category
        return [
            CheckResult(
                name="category",
                passed=category is not None,
                severity=Severity.ERROR,
                message="" if category else "Cannot determine category from genres",
            )
        ]
