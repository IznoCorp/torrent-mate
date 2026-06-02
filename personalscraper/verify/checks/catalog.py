"""Web-UI enumeration API: list_checks(), run_check().

Read-only, JSON-serializable surface consumed by the future Web Management UI.
Imports verify/checks/__init__.py to trigger plugin registration before listing.
"""

from __future__ import annotations

from personalscraper.verify.checks.base import (
    CheckContext,
    CheckResult,
    CheckSpec,
    CheckStage,
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
