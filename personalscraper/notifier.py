"""TRANSITIONAL — healthchecks only.

Telegram migrated to api/notify/telegram.py (Phase 22).
Healthchecks migration scheduled in Phase 24.
This module will be deleted in Phase 24.
"""

import requests

from personalscraper.logger import get_logger

log = get_logger("notifier")


def ping_healthcheck(url: str, status: str = "") -> None:
    """Ping healthchecks.io (or compatible service).

    Non-blocking, never raises. Used as a dead-man's switch:
    if the pipeline crashes before sending Telegram, the missing
    ping triggers an external alert.

    Args:
        url: Base healthcheck URL (e.g. "https://hc-ping.com/{uuid}").
            Empty string disables pinging silently.
        status: Endpoint suffix: "" (success), "/start", or "/fail".
    """
    if not url:
        return
    try:
        requests.get(f"{url}{status}", timeout=5)
    except requests.RequestException as exc:
        log.warning("healthcheck_ping_failed", url=url, status=status, error=str(exc))
    except Exception as exc:
        log.warning("healthcheck_unexpected_error", url=url, status=status, error=str(exc), exc_info=True)
