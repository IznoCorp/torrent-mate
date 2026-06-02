"""Canonical types and protocols for the unified Check plugin framework.

Severity and CheckResult MOVE here from verify/checker.py.
Internal importers are repointed — no re-export shim (single source of truth,
pre-1.0).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Protocol, runtime_checkable

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from typing import Any

    from personalscraper.conf.models.config import Config
    from personalscraper.naming_patterns import NamingPatterns

log = get_logger("verify.checks.base")


class CheckStage(Enum):
    """Pipeline stage at which a check runs.

    Attributes:
        STAGING: enforce — post-sort coherence, pre-scrape, read-only.
        DISPATCH: verify — post-scrape, pre-dispatch, may fix/block.
    """

    STAGING = "staging"
    DISPATCH = "dispatch"


class Severity(Enum):
    """Check result severity level.

    Attributes:
        ERROR: Blocks dispatch — must be fixed or media is rejected.
        WARNING: Informational — dispatch proceeds but issue is logged.
    """

    ERROR = "error"
    WARNING = "warning"


@dataclass
class CheckResult:
    """Result of a single quality check.

    Attributes:
        name: Check identifier (e.g. "nfo_present", "category").
        passed: Whether the check passed.
        severity: ERROR (blocking) or WARNING (informational).
        message: Human-readable description of the issue.
        fixable: Whether the issue can be auto-corrected.
    """

    name: str
    passed: bool
    severity: Severity
    message: str
    fixable: bool = False


@dataclass
class FixAction:
    """Description of a correction applied to a media directory.

    Attributes:
        description: Human-readable description of the fix.
        old_path: Original path before the fix.
        new_path: New path after the fix (None if not a rename).
    """

    description: str
    old_path: Path
    new_path: Path | None = None


@dataclass
class CheckSpec:
    """Static metadata about a registered check (for enumeration / Web-UI).

    Attributes:
        stage: STAGING or DISPATCH.
        name: Stable check identifier.
        group: Family name (e.g. "nfo", "artwork").
        media_types: frozenset of "movie" and/or "tvshow".
        default_severity: Declared severity (actual severity is per-result).
        fixable: Whether a fix() method is implemented.
        indexable: Whether a from_index() method is implemented.
        description: One-line human description.
    """

    stage: CheckStage
    name: str
    group: str
    media_types: frozenset[str]
    default_severity: Severity
    fixable: bool
    indexable: bool
    description: str


@dataclass
class CheckContext:
    """Shared context passed to every check plugin.

    Exposes an OPTIONAL parse-once NFO cache (:meth:`nfo_root` /
    :meth:`nfo_path`) that a plugin MAY use to avoid O(checks) re-parsing.
    It is NOT currently wired into any plugin: the existing checks resolve
    the NFO per their own path rules (movie NFO resolution differs from this
    cache's first-candidate glob), so they parse independently. The cache
    remains available for future plugins. First call parses and memoizes the
    result; a ``_nfo_parsed`` flag distinguishes "not yet parsed" from a
    cached "parse failed → None".

    Attributes:
        media_dir: Absolute path to the media directory.
        media_type: "movie" or "tvshow".
        stage: CheckStage for this invocation.
        config: Config with category and classifier rules.
        patterns: NamingPatterns for file naming lookups.
        dry_run: If True, fixes are described but not applied.
        resolved_category: Set by the category check; read by _classify.
    """

    media_dir: Path
    media_type: str
    stage: CheckStage
    config: "Config"
    patterns: "NamingPatterns"
    dry_run: bool = False
    resolved_category: "str | None" = None

    _nfo_root: "ET.Element | None | object" = field(default=None, init=False, repr=False, compare=False)
    _nfo_parsed: bool = field(default=False, init=False, repr=False, compare=False)

    def nfo_root(self) -> "ET.Element | None":
        """Return cached NFO root, parsing on first call.

        Returns:
            Parsed root Element, or None if NFO absent or parse failed.
        """
        if not self._nfo_parsed:
            self._nfo_parsed = True
            p = self.nfo_path()
            if p is None or not p.exists():
                self._nfo_root = None
            else:
                try:
                    self._nfo_root = ET.parse(p).getroot()  # noqa: S314
                except (ET.ParseError, OSError) as exc:
                    log.warning("nfo_root_parse_failed", nfo=str(p), exc_info=True, error=str(exc))
                    self._nfo_root = None
        return self._nfo_root  # type: ignore[return-value]

    def nfo_path(self) -> "Path | None":
        """Return expected NFO path for this media item.

        Returns:
            Path to NFO file (may not exist).
        """
        if self.media_type == "tvshow":
            return self.media_dir / "tvshow.nfo"
        from personalscraper.nfo_utils import glob_nfo_candidates

        candidates = glob_nfo_candidates(self.media_dir)
        return candidates[0] if candidates else None


@dataclass
class IndexContext:
    """DB-mode context for IndexableCheck.from_index().

    Attributes:
        row: sqlite3.Row from the media_item + item_attribute join.
        media_type: "movie" or "tvshow".
        category: category_id from the DB row.
    """

    row: Mapping[str, Any]
    media_type: str
    category: str


@runtime_checkable
class Check(Protocol):
    """Protocol every check plugin must satisfy.

    Attributes:
        name: Stable identifier (e.g. "nfo_present").
        group: Family (e.g. "nfo", "artwork").
        stages: frozenset of CheckStage this check runs on.
        media_types: frozenset of media types ("movie", "tvshow").
        default_severity: Declared severity for enumeration.
        description: One-line human description.
    """

    name: str
    group: str
    stages: frozenset[CheckStage]
    media_types: frozenset[str]
    default_severity: Severity
    description: str

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        """Run the check; return [] when precondition is unmet.

        Args:
            ctx: Shared context with parsed NFO cache.

        Returns:
            List of CheckResult (empty when precondition not met).
        """
        ...


@runtime_checkable
class FixableCheck(Protocol):
    """Optional capability: the check can auto-correct the issue."""

    def fix(self, ctx: CheckContext) -> list[FixAction]:
        """Apply the fix.

        Args:
            ctx: Shared context (respects ctx.dry_run).

        Returns:
            List of FixAction describing corrections made.
        """
        ...


@runtime_checkable
class IndexableCheck(Protocol):
    """Optional capability: the check can derive results from a DB row."""

    def from_index(self, row: Mapping[str, Any], ctx: IndexContext) -> "list[CheckResult] | None":
        """Derive results from an indexer DB row.

        Args:
            row: sqlite3.Row from media_item join.
            ctx: IndexContext with media_type and category.

        Returns:
            List of CheckResult, or None if not derivable from this row.
        """
        ...
