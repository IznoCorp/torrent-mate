"""Notify family base — Notifier and HealthChecker Protocols.

Implements DESIGN §7.1.

`PipelineReport` is the existing pipeline-run aggregator from
`personalscraper.models`; notifiers serialize it (typically to HTML) before
sending. Both Protocols are fail-soft contracts: implementations MUST NOT
raise on transport or API errors — they log and return `False` (or no-op,
for `HealthChecker`) so that notification failures never abort the pipeline.
"""

from typing import ClassVar, Protocol

from personalscraper.models import PipelineReport


class Notifier(Protocol):
    """Protocol for notification providers (Telegram, Slack, …).

    Required members:
        provider_name: Human-readable provider identifier.
        REQUIRED_CREDS: List of .env variable names needed by this provider.
        send(): Post a free-form message; returns True on success, False on failure.
        send_report(): Serialize and send a PipelineReport; returns success flag.
    """

    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def send(self, message: str, parse_mode: str = "HTML") -> bool: ...

    def send_report(self, report: PipelineReport) -> bool: ...


class HealthChecker(Protocol):
    """Protocol for dead-man's-switch health-check providers (healthchecks.io, …).

    Implementations are fail-soft: ping_* methods never raise, even when the
    backend is unreachable. They are pure side-effects (no return value) used
    to bracket pipeline runs so external monitoring can detect crashes.

    Required members:
        provider_name: Human-readable provider identifier.
        REQUIRED_CREDS: List of .env variable names needed by this provider.
        ping_start(): Signal that a pipeline run has started.
        ping_success(): Signal that a pipeline run completed successfully.
        ping_fail(): Signal that a pipeline run failed.
    """

    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def ping_start(self) -> None: ...

    def ping_success(self) -> None: ...

    def ping_fail(self) -> None: ...
