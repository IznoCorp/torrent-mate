"""Healthchecks ping client — `HealthChecker` Protocol implementation.

Implements DESIGN §7.2 on top of the unified `HttpTransport` infrastructure.
Responses are plain text — `TransportPolicy.response_format = "text"` is
used so the call still flows through retry/circuit/logging.

Healthchecks particularities (see `docs/reference/healthchecks-api.md`):

- **UUID-in-URL auth**: the ping URL embeds the credential. `auth = NoAuth()`;
  `base_url` is the env var `HEALTHCHECK_URL` verbatim.
- **Plain-text responses**: a 200 returns `OK`; non-200 returns a short
  error string. The provider does not parse the body — a successful HTTP
  status is success by definition.
- **Fail-soft contract** (Protocol returns `None`): every ping_* method
  catches all exceptions and logs a warning. The pipeline never aborts on a
  failed ping.
- **Self-hosted variants**: treat `HEALTHCHECK_URL` as opaque. Suffixes
  (`/start`, `/fail`) are appended verbatim — no hostname assumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from personalscraper.api._contracts import ProviderName
from personalscraper.api.notify._contracts import HealthChecker
from personalscraper.api.transport._auth import NoAuth
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport
    from personalscraper.config import Settings

log = get_logger("api.healthchecks")

# Tolerant circuit — pings are best-effort observability; outages must not
# lock the pipeline out of reporting.
_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=10, cooldown_seconds=60.0)
_DEFAULT_RETRY = RetryPolicy(max_attempts=2)


class HealthcheckClient(HealthChecker):
    """Send lifecycle pings to a healthchecks.io-compatible endpoint.

    Composes the `HealthChecker` Protocol (DESIGN §7.1). All three ping_*
    methods are pure side-effects with `-> None` return type. They MUST NEVER
    raise — pipeline runs always finish even if the ping endpoint is down.

    Attributes:
        provider_name: Always `"healthchecks"`.
        REQUIRED_CREDS: `.env` variable names — `HEALTHCHECK_URL`.
    """

    provider_name: ClassVar[str] = ProviderName.HEALTHCHECKS.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["HEALTHCHECK_URL"]

    @classmethod
    def policy(cls, ping_url: str) -> TransportPolicy:
        """Build a `TransportPolicy` for the healthchecks ping endpoint.

        The full ping URL (including the UUID and any self-hosted prefix)
        becomes the policy's `base_url`. Suffixes like `/start` and `/fail`
        are appended at request time via the `path` argument.

        Args:
            ping_url: Full ping URL from `.env`, no trailing slash. Empty
                string yields a degenerate policy — callers should check
                `is_configured()` and skip construction when unset.

        Returns:
            TransportPolicy with `response_format = "text"`.
        """
        return TransportPolicy(
            provider_name=ProviderName.HEALTHCHECKS,
            base_url=ping_url,
            auth=NoAuth(),
            timeout_seconds=5.0,
            retry=_DEFAULT_RETRY,
            circuit=_DEFAULT_CIRCUIT,
            response_format="text",
        )

    def __init__(self, transport: HttpTransport) -> None:
        """Initialize the client with a pre-configured transport.

        Args:
            transport: `HttpTransport` built from `HealthcheckClient.policy()`.
        """
        self._transport = transport

    # -- HealthChecker Protocol --------------------------------------------

    def ping_start(self) -> None:
        """Signal that the pipeline run has started (`/start` suffix)."""
        self._safe_get("/start")

    def ping_success(self) -> None:
        """Signal that the pipeline run finished successfully (no suffix)."""
        self._safe_get("")

    def ping_fail(self) -> None:
        """Signal that the pipeline run failed (`/fail` suffix)."""
        self._safe_get("/fail")

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def is_configured(settings: Settings) -> bool:
        """Check if the healthcheck URL is set in `Settings`.

        Args:
            settings: Application settings to inspect.

        Returns:
            `True` if `healthcheck_url` is non-empty.
        """
        return bool(settings.healthcheck_url)

    def _safe_get(self, suffix: str) -> None:
        """Issue a GET to `base_url + suffix`, swallowing all exceptions.

        Args:
            suffix: Path suffix appended to the policy's base_url. Empty
                string targets the base URL itself (success ping).
        """
        try:
            self._transport.get(suffix)
        except Exception as exc:  # noqa: BLE001 — fail-soft: ping must never abort the pipeline
            log.warning("healthcheck_ping_failed", suffix=suffix, error=str(exc))
