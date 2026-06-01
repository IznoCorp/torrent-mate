"""CheckRegistry: decorator registration, ordered dispatch, apply_fixes.

The _ORDER table encodes the exact per-(stage, media_type) append sequence
from the pre-refactor checker.py and coherence_checker.py, calibrated from
the Phase 0 baseline. checks_for() returns checks in that order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.verify.checks.base import (
    CheckContext,
    CheckResult,
    CheckSpec,
    CheckStage,
    FixableCheck,
)

if TYPE_CHECKING:
    from personalscraper.verify.checks.base import Check, FixAction

# Explicit order table — calibrated from pre-refactor append sequence (DESIGN §8).
# Each entry is the check name; checks_for() returns instances in this order.
_ORDER: dict[tuple[CheckStage, str], list[str]] = {
    (CheckStage.DISPATCH, "movie"): [
        "video_present",
        "not_sample",
        "dir_naming",
        "nfo_present",
        "nfo_valid",
        "nfo_ids",
        "poster_present",
        "artwork_landscape",
        "streamdetails",
        "no_empty_dirs",
        "category",
        "no_duplicate_videos",
        "ntfs_safe_names",
    ],
    (CheckStage.DISPATCH, "tvshow"): [
        "video_present",
        "dir_naming",
        "nfo_present",
        "nfo_valid",
        "nfo_ids",
        "poster_present",
        "artwork_landscape",
        "season_structure",
        "season_posters",
        "episode_renamed",
        "episode_nfo",
        "no_empty_dirs",
        "category",
        "root_video_files",
        "episode_canonical_uniqueid_present",
        "episode_xref_secondary_id_present",
        "episode_xref_imdb_id_present",
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
            self._checks[key] = instance
        return cls

    def get(self, stage: CheckStage, name: str) -> "Check | None":
        """Return the check registered for (stage, name), or None.

        Args:
            stage: CheckStage to look up.
            name: Check name to look up.

        Returns:
            Check instance or None if not registered.
        """
        return self._checks.get((stage, name))

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
            specs.append(
                CheckSpec(
                    stage=stage,
                    name=check.name,
                    group=check.group,
                    media_types=check.media_types,
                    default_severity=check.default_severity,
                    fixable=isinstance(check, FixableCheck),
                    indexable=hasattr(check, "from_index"),
                    description=check.description,
                )
            )
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
    actions: list["FixAction"] = []
    for r in failed:
        if r.name not in policy:
            continue
        check = registry.get(ctx.stage, r.name)
        if check is not None and isinstance(check, FixableCheck):
            actions.extend(check.fix(ctx))
    return actions
