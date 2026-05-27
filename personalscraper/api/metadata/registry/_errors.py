"""Exception hierarchy for the provider registry (DESIGN §7.1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import (
        AttemptOutcome,
        ConfigIssue,
    )


class RegistryError(Exception):
    """Base class for all registry errors."""


class RegistryConfigError(RegistryError):
    """Config inconsistency detected at boot.

    Carries structured ``list[ConfigIssue]`` so tests assert on ``code``
    rather than substring-matching the human message.

    Attributes:
        issues: The list of structured config issues.
    """

    def __init__(self, issues: list[ConfigIssue]) -> None:
        self.issues = issues
        super().__init__(self._format(issues))

    @staticmethod
    def _format(issues: list[ConfigIssue]) -> str:
        lines = ["RegistryConfigError — provider config is invalid:"]
        for issue in issues:
            suggestion = f" (did you mean {issue.message!r}?)" if "did you mean" in issue.message else ""
            lines.append(
                f"  [{issue.code}] section={issue.section} provider={issue.provider}: {issue.message}{suggestion}"
            )
        return "\n".join(lines)


class UnknownProviderError(RegistryError):
    """``registry.get(name)`` called with an unregistered name.

    Attributes:
        name: The provider name that was not found.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown provider: {name!r}")


class ProviderExhausted(RegistryError):
    """All chain providers failed for an item.

    Carries the last underlying exception so the immediate caller can
    surface the original error message in legacy fail-soft contracts
    (DESIGN §6.2 + §10) — ACC-13 requires that ``"<original detail>"``
    appears in ``result.error`` after the chain raises.

    Attributes:
        capability: The capability Protocol type that was exhausted.
        attempted: The list of ``AttemptOutcome`` for each tried provider.
        item_context: Optional dict with item details for diagnostics.
        last_exception: The last exception raised by a chain provider
            (``CircuitOpenError`` / ``ApiError`` / ``OSError`` …) — used
            by callers to preserve the original error message.
    """

    def __init__(
        self,
        capability: type,
        attempted: list[AttemptOutcome],
        item_context: dict[str, Any] | None = None,
        last_exception: Exception | None = None,
    ) -> None:
        self.capability = capability
        self.attempted = attempted
        self.item_context = item_context
        self.last_exception = last_exception
        last_msg = f": {last_exception}" if last_exception is not None else ""
        super().__init__(
            f"Chain exhausted for {capability.__name__}{last_msg} "
            f"(attempted: {[a.provider for a in attempted]})"
        )


class WrongSemanticBug(RegistryError):
    """Caller invoked wrong registry operation for a capability.

    Programmer bug — must NOT be caught. The name "Bug" (not "Error") signals
    that this exception is never recoverable.
    """
