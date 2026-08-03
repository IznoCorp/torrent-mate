"""Tracker-family typed errors.

Kept separate from ``_base.py`` to avoid a circular import: ``_fetch.py``
imports both ``_base.py`` (for TrackerResult) and these error types, and
``_base.py`` must not import from ``_fetch.py``. Same hygiene pattern as
``api/torrent/_errors.py``.

Design: §5.3 (D4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from personalscraper.api._contracts import ApiError

#: HTTP statuses that mean « this credential is broken », as opposed to « this
#: service is having a bad day ». The distinction is what separates a PERMANENT
#: failure an operator must fix from a transient one worth retrying, so it is
#: defined ONCE and shared by every place that makes the call: the torrent
#: download (``_fetch.fetch_torrent_source``) and the tracker searches
#: (``torznab.TorznabClient``).
AUTH_HTTP_STATUSES: frozenset[int] = frozenset({401, 403})


class TrackerAuthError(ApiError):
    """Authentication failure on a tracker (HTTP 401/403, or an auth error document).

    Two paths raise it, and both matter:

    * ``fetch_torrent_source`` — the GRAB stage's ``.torrent`` download returns
      401/403. Terminal at grab time: the orchestrator abandons the item.
    * ``TorznabClient.search`` — the SEARCH stage gets 401/403 or one of the
      Torznab auth error codes. The registry books it as the ``auth`` taxon on
      :class:`~personalscraper.acquire._dedup.SearchOutcome`, and a UNANIMOUS
      set of those is what earns the terminal ``tracker_auth`` verdict (D4).
      Without this second path the taxon is unreachable and a broken passkey is
      retried forever as a generic outage.

    Being an :exc:`ApiError` subclass is load-bearing: every fail-soft consumer
    that already catches ``ApiError`` keeps working unchanged, and only the code
    that WANTS the distinction has to name the subclass — which is why the
    catch order (this class BEFORE its base) is load-bearing wherever both are
    caught.

    Inherits ``ApiError``'s ``__init__``: ``provider``, ``http_status``,
    ``provider_code``, ``message``.
    """


class TorrentFetchError(ApiError):
    """Unrecoverable error fetching or validating a ``.torrent`` file.

    Raised by ``fetch_torrent_source`` / ``resolve_source`` for:
    - Empty body from a successful HTTP response
    - Body exceeds the size cap
    - Body is not a valid bencoded dict (HTML-200 login wall, JSON error)
    - Bencoded dict has no top-level ``info`` key
    - Derived info_hash does not match the expected hash
    - ``TrackerResult.download_url`` is None
    - ``TrackerResult.provider`` key not found in the transports map

    Inherits ``ApiError``'s ``__init__``: ``provider``, ``http_status``,
    ``provider_code``, ``message``.
    """


# ---------------------------------------------------------------------------
# Boot-validation error hierarchy — tracker-wiring RP5a
# ---------------------------------------------------------------------------


class TrackerError(Exception):
    """Base exception for the tracker provider family.

    All tracker-specific errors derive from this class, mirroring the
    ``RegistryError`` base in ``api/metadata/registry/_errors.py``.
    Catching ``TrackerError`` handles every tracker-family exception without
    accidentally swallowing unrelated ``Exception`` subclasses.
    """


@dataclass(frozen=True)
class TrackerConfigIssue:
    """One boot-validation finding for the tracker factory (DESIGN §Components.2).

    Attributes:
        severity: ``"error"`` → fatal (raises :class:`TrackerConfigError`);
            ``"warning"`` → logged, non-fatal.
        code: Machine-readable issue identifier.
            ``missing_credentials`` — tracker enabled but API key absent.
            ``protocol_mismatch`` — built client fails ``TorrentSearchable`` check.
            ``unknown_provider`` — a referenced tracker cannot be activated:
                either a name in ``priority`` is absent from ``providers``,
                or an enabled provider has no client implementation registered.
            ``disabled_in_priority`` — disabled tracker referenced in priority
                when ≥1 tracker is active (warning only).
        provider: Tracker name (e.g. ``"c411"``), or ``None`` for issues
            not tied to a single provider.
        message: Human-readable description for operator logs / error output.
    """

    severity: Literal["error", "warning"]
    code: Literal[
        "missing_credentials",
        "protocol_mismatch",
        "unknown_provider",
        "disabled_in_priority",
    ]
    provider: str | None
    message: str


class TrackerConfigError(TrackerError):
    """Aggregated, fail-loud tracker boot-config error (parity with RegistryConfigError).

    Carries every error-severity :class:`TrackerConfigIssue` so the operator
    sees all problems at once (never fail-fast on the first). Raised by
    :func:`~personalscraper.api.tracker._factory.build_tracker_registry` at the
    composition root when any error-severity issue is found.

    Attributes:
        issues: Frozen tuple of all error-severity issues found during boot
            validation.
    """

    def __init__(self, issues: list[TrackerConfigIssue]) -> None:
        """Initialise with the aggregated list of error-severity issues.

        Args:
            issues: Non-empty list of :class:`TrackerConfigIssue` instances,
                all with ``severity == "error"``.

        Raises:
            ValueError: If *issues* is empty or contains any non-error issue.
        """
        if not issues:
            raise ValueError("TrackerConfigError requires at least one issue")
        if any(i.severity != "error" for i in issues):
            raise ValueError("TrackerConfigError accepts only error-severity issues")
        self.issues: tuple[TrackerConfigIssue, ...] = tuple(issues)
        codes = ", ".join(f"{i.provider or '?'}:{i.code}" for i in self.issues)
        super().__init__(f"Tracker boot validation failed ({len(self.issues)} error(s)): {codes}")


__all__ = [
    "AUTH_HTTP_STATUSES",
    "TrackerAuthError",
    "TorrentFetchError",
    "TrackerError",
    "TrackerConfigIssue",
    "TrackerConfigError",
]
