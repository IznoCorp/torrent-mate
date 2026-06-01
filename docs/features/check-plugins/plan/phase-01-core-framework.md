# Phase 1 — Core Framework

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `verify/checks/` package with `base.py` (all types + protocols), `registry.py` (CheckRegistry + `@register_check` + explicit `_ORDER` table + `apply_fixes`), and `catalog.py` (Web-UI enumeration API). No production checks are migrated yet — only the framework skeleton and its unit tests.

**Architecture:** `base.py` is the single canonical source for `Severity`, `CheckResult`, `FixAction`, `CheckStage`, `CheckContext`, `IndexContext`, `CheckSpec`, and the three Protocols. `registry.py` holds the singleton registry and the `_ORDER` table. `catalog.py` wraps the registry for external enumeration.

**Tech Stack:** Python 3.11 `dataclasses`, `enum`, `typing.Protocol`, `runtime_checkable`, pytest

---

## Gate (previous phase)

- `tests/verify/golden/checker_movie.json` and `checker_tvshow.json` exist and are committed.
- `pytest tests/verify/test_characterization_golden.py -q` passes (stubs green).

---

## Sub-phase 1.1 — `verify/checks/base.py`

**Files:**

- Create: `personalscraper/verify/checks/__init__.py`
- Create: `personalscraper/verify/checks/base.py`

- [ ] **Step 1: Write failing test for base types**

```python
# tests/verify/checks/test_base.py
"""Unit tests for verify/checks/base.py — types, protocols, context."""
import pytest
from personalscraper.verify.checks.base import (
    CheckStage, Severity, CheckResult, FixAction, CheckSpec,
    Check, FixableCheck, IndexableCheck, CheckContext,
)

def test_check_stage_values():
    assert CheckStage.STAGING.value == "staging"
    assert CheckStage.DISPATCH.value == "dispatch"

def test_severity_values():
    assert Severity.ERROR.value == "error"
    assert Severity.WARNING.value == "warning"

def test_check_result_defaults():
    r = CheckResult(name="x", passed=True, severity=Severity.ERROR, message="")
    assert r.fixable is False

def test_fix_action_fields():
    from pathlib import Path
    a = FixAction(description="renamed", old_path=Path("/a"), new_path=Path("/b"))
    assert a.new_path == Path("/b")

def test_check_spec_fields():
    spec = CheckSpec(
        stage=CheckStage.DISPATCH, name="nfo_present", group="nfo",
        media_types=frozenset({"movie", "tvshow"}), default_severity=Severity.ERROR,
        fixable=False, indexable=True, description="NFO file must exist",
    )
    assert spec.indexable is True
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
pytest tests/verify/checks/test_base.py -q
```

Expected: `ImportError: No module named 'personalscraper.verify.checks'`

- [ ] **Step 3: Create the package and `base.py`**

```bash
mkdir -p personalscraper/verify/checks
touch personalscraper/verify/checks/__init__.py
```

```python
# personalscraper/verify/checks/base.py
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
from typing import TYPE_CHECKING, Mapping, runtime_checkable
from typing import Protocol

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.core.media_types import FileType


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

    Carries a parse-once, cached NFO root to avoid O(checks) re-parsing.
    A sentinel (_NOT_PARSED) distinguishes "not yet parsed" from "parse failed → None".

    Attributes:
        media_dir: Absolute path to the media directory.
        media_type: "movie" or "tvshow".
        stage: CheckStage for this invocation.
        config: Config with category and classifier rules.
        patterns: NamingPatterns for file naming lookups.
        dry_run: If True, fixes are described but not applied.
        expected_file_type: For enforce wrong-category detection.
        resolved_category: Set by the category check; read by _classify.
    """

    media_dir: Path
    media_type: str
    stage: CheckStage
    config: "Config"
    patterns: "NamingPatterns"
    dry_run: bool = False
    expected_file_type: "FileType | None" = None
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
                except (ET.ParseError, OSError):
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

    row: Mapping
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

    def from_index(self, row: Mapping, ctx: IndexContext) -> "list[CheckResult] | None":
        """Derive results from an indexer DB row.

        Args:
            row: sqlite3.Row from media_item join.
            ctx: IndexContext with media_type and category.

        Returns:
            List of CheckResult, or None if not derivable from this row.
        """
        ...
```

- [ ] **Step 4: Run test — expect pass**

```bash
pytest tests/verify/checks/test_base.py -q
```

Expected: `5 passed`

- [ ] **Step 5: Add `tests/verify/checks/__init__.py`**

```bash
touch tests/verify/checks/__init__.py
```

- [ ] **Step 6: Commit**

```bash
git add personalscraper/verify/checks/ tests/verify/checks/
git commit -m "feat(check-plugins): add verify/checks/base.py — types, protocols, CheckContext"
```

---

## Sub-phase 1.2 — `registry.py` + `catalog.py`

**Files:**

- Create: `personalscraper/verify/checks/registry.py`
- Create: `personalscraper/verify/checks/catalog.py`
- Expand: `tests/verify/checks/test_base.py` (add registry + catalog tests)

- [ ] **Step 1: Write failing tests for registry and catalog**

```python
# tests/verify/checks/test_registry.py
"""Unit tests for CheckRegistry, @register_check, checks_for, apply_fixes."""
import pytest
from personalscraper.verify.checks.base import (
    CheckStage, CheckResult, CheckContext, CheckSpec, Severity,
)
from personalscraper.verify.checks.registry import CheckRegistry, register_check


def _make_ctx(media_type: str = "movie", stage: CheckStage = CheckStage.DISPATCH) -> CheckContext:
    from pathlib import Path
    from unittest.mock import MagicMock
    return CheckContext(
        media_dir=Path("/tmp/fake"),
        media_type=media_type,
        stage=stage,
        config=MagicMock(),
        patterns=MagicMock(),
    )


def test_register_and_get():
    reg = CheckRegistry()

    @reg.register
    class DummyCheck:
        name = "dummy_test"
        group = "test"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.ERROR
        description = "test check"
        def run(self, ctx): return []

    check = reg.get(CheckStage.DISPATCH, "dummy_test")
    assert check is not None
    assert check.name == "dummy_test"


def test_get_unknown_returns_none():
    reg = CheckRegistry()
    assert reg.get(CheckStage.DISPATCH, "nonexistent") is None


def test_list_specs_returns_check_spec():
    reg = CheckRegistry()

    @reg.register
    class ACheck:
        name = "a_check"
        group = "grp"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.WARNING
        description = "a"
        def run(self, ctx): return []

    specs = reg.list_specs()
    names = [s.name for s in specs]
    assert "a_check" in names


def test_checks_for_filters_by_stage_and_media_type():
    reg = CheckRegistry()

    @reg.register
    class MovieCheck:
        name = "movie_only"
        group = "g"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.ERROR
        description = "movie only"
        def run(self, ctx): return []

    @reg.register
    class TvCheck:
        name = "tv_only"
        group = "g"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"tvshow"})
        default_severity = Severity.ERROR
        description = "tv only"
        def run(self, ctx): return []

    movie_checks = reg.checks_for(CheckStage.DISPATCH, "movie")
    tv_checks = reg.checks_for(CheckStage.DISPATCH, "tvshow")
    assert all(c.name != "tv_only" for c in movie_checks)
    assert all(c.name != "movie_only" for c in tv_checks)


def test_stage_name_collision():
    """(stage, name) keys are independent — nfo_ids on DISPATCH != STAGING."""
    reg = CheckRegistry()

    @reg.register
    class DispatchNfoIds:
        name = "nfo_ids"
        group = "nfo"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie", "tvshow"})
        default_severity = Severity.ERROR
        description = "dispatch nfo_ids"
        def run(self, ctx): return []

    @reg.register
    class StagingNfoIds:
        name = "nfo_ids"
        group = "coherence"
        stages = frozenset({CheckStage.STAGING})
        media_types = frozenset({"movie", "tvshow"})
        default_severity = Severity.WARNING
        description = "staging nfo_ids"
        def run(self, ctx): return []

    d = reg.get(CheckStage.DISPATCH, "nfo_ids")
    s = reg.get(CheckStage.STAGING, "nfo_ids")
    assert d is not s
    assert d is not None and s is not None
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
pytest tests/verify/checks/test_registry.py -q
```

Expected: `ImportError: No module named '...registry'`

- [ ] **Step 3: Write `registry.py`**

```python
# personalscraper/verify/checks/registry.py
"""CheckRegistry: decorator registration, ordered dispatch, apply_fixes.

The _ORDER table encodes the exact per-(stage, media_type) append sequence
from the pre-refactor checker.py and coherence_checker.py, calibrated from
the Phase 0 baseline. checks_for() returns checks in that order.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.verify.checks.base import (
    CheckContext, CheckResult, CheckSpec, CheckStage, FixableCheck, Severity,
)

if TYPE_CHECKING:
    from personalscraper.verify.checks.base import Check, FixAction

# Explicit order table — calibrated from pre-refactor append sequence (DESIGN §8).
# Each entry is the check name; checks_for() returns instances in this order.
_ORDER: dict[tuple[CheckStage, str], list[str]] = {
    (CheckStage.DISPATCH, "movie"): [
        "video_present", "not_sample", "dir_naming", "nfo_present", "nfo_valid",
        "nfo_ids", "poster_present", "artwork_landscape", "streamdetails",
        "no_empty_dirs", "category", "no_duplicate_videos", "ntfs_safe_names",
    ],
    (CheckStage.DISPATCH, "tvshow"): [
        "video_present", "dir_naming", "nfo_present", "nfo_valid", "nfo_ids",
        "poster_present", "artwork_landscape", "season_structure", "season_posters",
        "episode_renamed", "episode_nfo", "no_empty_dirs", "category",
        "root_video_files", "episode_canonical_uniqueid_present",
        "episode_xref_secondary_id_present", "episode_xref_imdb_id_present",
        "ntfs_safe_names",
    ],
    (CheckStage.STAGING, "movie"): ["sort_process_coherence", "nfo_ids"],
    (CheckStage.STAGING, "tvshow"): ["nfo_ids", "genre_coherence", "sort_process_coherence"],
}


class CheckRegistry:
    """Registry for Check plugins — keyed by (stage, name).

    Attributes:
        _checks: Maps (CheckStage, name) → Check instance.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._checks: dict[tuple[CheckStage, str], "Check"] = {}

    def register(self, cls: type) -> type:
        """Register a Check class (decorator form).

        Creates one instance of ``cls`` and stores it under every
        ``(stage, name)`` pair declared by the check.

        Args:
            cls: Class implementing the Check Protocol.

        Returns:
            The class unchanged (decorator contract).
        """
        instance = cls()
        for stage in instance.stages:
            key = (stage, instance.name)
            self._checks[key] = instance  # type: ignore[assignment]
        return cls

    def get(self, stage: CheckStage, name: str) -> "Check | None":
        """Return the check registered for (stage, name), or None.

        Args:
            stage: CheckStage to look up.
            name: Check name to look up.

        Returns:
            Check instance or None if not registered.
        """
        return self._checks.get((stage, name))  # type: ignore[return-value]

    def checks_for(self, stage: CheckStage, media_type: str) -> list["Check"]:
        """Return checks for a (stage, media_type) pair in _ORDER sequence.

        Checks not listed in _ORDER are appended after ordered ones.

        Args:
            stage: Pipeline stage.
            media_type: "movie" or "tvshow".

        Returns:
            Ordered list of Check instances.
        """
        order = _ORDER.get((stage, media_type), [])
        ordered: list["Check"] = []
        seen: set[str] = set()
        for name in order:
            check = self._checks.get((stage, name))
            if check is not None and media_type in check.media_types:
                ordered.append(check)
                seen.add(name)
        # Append any registered checks not in the order table
        for (s, n), check in self._checks.items():
            if s == stage and n not in seen and media_type in check.media_types:
                ordered.append(check)
        return ordered

    def list_specs(self) -> list[CheckSpec]:
        """Return CheckSpec for every registered check.

        Returns:
            List of CheckSpec sorted by (stage, name).
        """
        specs = []
        seen: set[tuple[CheckStage, str]] = set()
        for (stage, name), check in sorted(self._checks.items(), key=lambda kv: (kv[0][0].value, kv[0][1])):
            if (stage, name) in seen:
                continue
            seen.add((stage, name))
            specs.append(CheckSpec(
                stage=stage,
                name=check.name,
                group=check.group,
                media_types=check.media_types,
                default_severity=check.default_severity,
                fixable=isinstance(check, FixableCheck),
                indexable=hasattr(check, "from_index"),
                description=check.description,
            ))
        return specs


# Module-level singleton — imported by checks/__init__.py after all plugins load
registry = CheckRegistry()


def register_check(cls: type) -> type:
    """Decorator: register a Check class on the singleton registry.

    Args:
        cls: Check class to register.

    Returns:
        The class unchanged.
    """
    return registry.register(cls)


def apply_fixes(
    ctx: CheckContext,
    failed: list[CheckResult],
    policy: frozenset[str],
) -> list["FixAction"]:
    """Apply fix() for every failed check whose name is in the policy.

    Args:
        ctx: Shared CheckContext (respects ctx.dry_run).
        failed: List of CheckResult where passed=False.
        policy: Allow-set of check names that may be auto-fixed.

    Returns:
        List of FixAction for each correction applied.
    """
    actions: list[FixAction] = []
    for r in failed:
        if r.name not in policy:
            continue
        check = registry.get(ctx.stage, r.name)
        if check is not None and isinstance(check, FixableCheck):
            actions.extend(check.fix(ctx))
    return actions
```

- [ ] **Step 4: Write `catalog.py`**

```python
# personalscraper/verify/checks/catalog.py
"""Web-UI enumeration API: list_checks(), run_check().

Read-only, JSON-serializable surface consumed by the future Web Management UI.
Imports verify/checks/__init__.py to trigger plugin registration before listing.
"""
from __future__ import annotations

from personalscraper.verify.checks.base import (
    CheckContext, CheckResult, CheckSpec, CheckStage,
)
from personalscraper.verify.checks.registry import registry


def list_checks() -> list[CheckSpec]:
    """Return CheckSpec for all registered checks across both stages.

    Returns:
        List of CheckSpec sorted by (stage.value, name).
    """
    # Import __init__ to ensure all plugin modules have registered
    import personalscraper.verify.checks  # noqa: F401
    return registry.list_specs()


def run_check(stage: CheckStage, name: str, ctx: CheckContext) -> list[CheckResult]:
    """Run a single named check by (stage, name).

    Args:
        stage: CheckStage for this invocation.
        name: Check name to run.
        ctx: Shared CheckContext.

    Returns:
        List of CheckResult (empty if check not found or precondition unmet).

    Raises:
        KeyError: If no check is registered for (stage, name).
    """
    check = registry.get(stage, name)
    if check is None:
        raise KeyError(f"No check registered for ({stage!r}, {name!r})")
    return check.run(ctx)
```

- [ ] **Step 5: Run registry tests — expect pass**

```bash
pytest tests/verify/checks/test_registry.py -q
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add personalscraper/verify/checks/registry.py personalscraper/verify/checks/catalog.py tests/verify/checks/test_registry.py
git commit -m "feat(check-plugins): add registry.py (CheckRegistry + _ORDER + apply_fixes) and catalog.py"
```

---

## Phase Gate

```bash
make lint        # 0 errors
make test        # all pass, 0 collection ERROR
make check       # rc=0, coverage ≥ 90%, all modules << 800 LOC
python -c "import personalscraper"  # exits 0
# ACC-02: existing verify/enforce suites still green
pytest tests/verify tests/enforce -q
```

Expected: all green. `verify/checks/base.py`, `registry.py`, `catalog.py` created; 0 production code changed.
