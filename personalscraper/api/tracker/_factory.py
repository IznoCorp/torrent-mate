"""Config-driven factory for TrackerRegistry — tracker-wiring RP5a.

Builds a live :class:`TrackerRegistry` from ``TrackerConfig`` at the
composition-root boundary, mirroring ``api/torrent/_factory.py``.
Design: tracker-wiring §Components.1.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

import structlog

from personalscraper.api._activation import PROVIDER_CREDS
from personalscraper.api.tracker._contracts import TorrentSearchable
from personalscraper.api.tracker._errors import TrackerConfigError, TrackerConfigIssue
from personalscraper.api.tracker._registry import TrackerRegistry

if TYPE_CHECKING:
    from personalscraper.api.transport._policy import CircuitPolicy
    from personalscraper.conf.models.api_config import RankingConfig, TrackerConfig
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus

log = structlog.get_logger("api.tracker.factory")

_TRACKER_CLASSES: dict[str, str] = {
    "lacale": "personalscraper.api.tracker.lacale:LaCaleClient",
    "c411": "personalscraper.api.tracker.c411:C411Client",
}


def _resolve_tracker_class(name: str) -> type:
    """Import and return the tracker client class for *name*.

    Args:
        name: Tracker name key (e.g. ``"lacale"``).

    Returns:
        The concrete client class.
    """
    dotted = _TRACKER_CLASSES[name]
    module_path, _, class_name = dotted.partition(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)  # type: ignore[no-any-return]


def build_tracker_registry(
    tracker_config: TrackerConfig,
    ranking: RankingConfig,
    *,
    settings: Settings,
    event_bus: EventBus,
    cb_policy: CircuitPolicy,
    env: Mapping[str, str] | None = None,
) -> TrackerRegistry:
    """Build a live TrackerRegistry from config, at parity with the metadata registry.

    Args:
        tracker_config: Parsed ``tracker.json5`` config.
        ranking: Ranking config applied to merged search results.
        settings: Pydantic env-var settings (passed for API parity; tracker
            credentials are resolved from ``env``, not ``settings`` fields).
        event_bus: In-process event bus forwarded to each ``HttpTransport``.
        cb_policy: Circuit-breaker policy. Reserved for future circuit-wiring;
            the tracker clients' ``policy()`` does not accept a ``circuit=``
            argument yet (unlike the metadata clients), so it is not threaded
            into the transports in this phase.
        env: Credential source. Defaults to ``os.environ``; injectable for tests.

    Returns:
        A populated :class:`TrackerRegistry`.

    Raises:
        TrackerConfigError: Any error-severity issue found during validation.
    """
    from personalscraper.api.transport._http import HttpTransport  # noqa: PLC0415

    if env is None:
        env = os.environ

    issues: list[TrackerConfigIssue] = []
    built: dict[str, TorrentSearchable] = {}

    # Step 1: resolve enabled trackers; collect errors for missing creds.
    for name, provider_cfg in tracker_config.providers.items():
        if not provider_cfg.enabled:
            continue

        required = PROVIDER_CREDS.get(name, [])
        missing = [k for k in required if not env.get(k)]
        if missing:
            issues.append(
                TrackerConfigIssue(
                    severity="error",
                    code="missing_credentials",
                    provider=name,
                    message=f"Tracker {name!r} enabled but missing: {', '.join(missing)}",
                )
            )
            continue

        if name not in _TRACKER_CLASSES:
            issues.append(
                TrackerConfigIssue(
                    severity="error",
                    code="unknown_provider",
                    provider=name,
                    message=f"Tracker {name!r} enabled but has no client implementation.",
                )
            )
            continue

        client_cls = _resolve_tracker_class(name)
        api_key = env[required[0]] if required else ""
        transport = HttpTransport(client_cls.policy(api_key), event_bus=event_bus)  # type: ignore[attr-defined]
        client = client_cls(transport)

        if not isinstance(client, TorrentSearchable):
            issues.append(
                TrackerConfigIssue(
                    severity="error",
                    code="protocol_mismatch",
                    provider=name,
                    message=f"Built client for {name!r} does not satisfy TorrentSearchable.",
                )
            )
            continue

        built[name] = client

    # Step 2: unknown_provider — names in priority absent from providers.
    known_providers = set(tracker_config.providers)
    priority_names: set[str] = set(tracker_config.priority)
    for names_list in tracker_config.priority_by_media_type.values():
        priority_names.update(names_list)
    for name in sorted(priority_names - known_providers):
        issues.append(
            TrackerConfigIssue(
                severity="error",
                code="unknown_provider",
                provider=name,
                message=f"Priority references {name!r} not present in tracker.providers.",
            )
        )

    # Step 3: disabled_in_priority warning — only when ≥1 tracker active.
    if built:
        disabled_names = {n for n, c in tracker_config.providers.items() if not c.enabled}
        for name in sorted(priority_names & disabled_names & known_providers):
            issues.append(
                TrackerConfigIssue(
                    severity="warning",
                    code="disabled_in_priority",
                    provider=name,
                    message=f"Tracker {name!r} in priority but disabled; will be skipped.",
                )
            )

    # Step 4: raise on errors; log warnings; return registry.
    error_issues = [i for i in issues if i.severity == "error"]
    if error_issues:
        raise TrackerConfigError(error_issues)

    for issue in issues:
        log.warning("tracker_boot_warning", code=issue.code, provider=issue.provider, message=issue.message)

    log.info("tracker_registry_built", active_trackers=list(built), total=len(built))
    return TrackerRegistry(
        trackers=built,
        priority=tracker_config.priority,
        ranking=ranking,
        priority_by_media_type=tracker_config.priority_by_media_type or None,
    )


__all__ = ["build_tracker_registry"]
