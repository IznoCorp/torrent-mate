"""Pure PM2 daemon-control allowlist (bosun §5.1, decision D1).

Enforces lockout safety: daemon-control may act on an allowlisted PM2 app, but a STANDALONE
start/stop/restart of a UI app (the config server) is refused — a UI app is only ever bounced as the
tail of a redeploy job (§8). ``status`` is permitted on any allowlisted app including UI apps.
No I/O — the app layer runs ``pm2`` and calls this for the decision.
"""

from __future__ import annotations

PM2_ALLOWLIST: frozenset[str] = frozenset(
    {"kanban-km", "kanban-km-serve", "kanban-km-config", "kanban-staging-config"}
)
UI_APP_NAMES: frozenset[str] = frozenset({"kanban-km-config", "kanban-staging-config"})
_DAEMON_ACTIONS: frozenset[str] = frozenset({"start", "stop", "restart", "status"})


def validate_daemon_action(app: str, action: str) -> str | None:
    """Return ``None`` if ``(app, action)`` is permitted, else a refusal reason (DESIGN §5.1).

    Args:
        app: The PM2 app name.
        action: One of ``start``/``stop``/``restart``/``status``.

    Returns:
        ``None`` when permitted; otherwise a human-readable refusal string (the HTTP layer maps a
        non-``None`` return to a 422).
    """
    if action not in _DAEMON_ACTIONS:
        return f"unknown action '{action}'"
    if app not in PM2_ALLOWLIST:
        return f"app '{app}' is not in the PM2 allowlist"
    if app in UI_APP_NAMES and action in {"start", "stop", "restart"}:
        return f"standalone '{action}' of UI app '{app}' is refused (bounce only via redeploy)"
    return None


def validate_graceful_restart(app: str) -> str | None:
    """Return ``None`` if ``app`` may be GRACEFULLY restarted, else a refusal reason.

    A *graceful* restart is the sanctioned way to bounce a **UI app** (config server) on its own: the
    HTTP layer spawns a detached ``pm2 restart`` job that survives the server's own death, and the
    browser tolerates the gap and reconnects. It is therefore the inverse of
    :func:`validate_daemon_action`'s D1 rule — permitted ONLY for the UI apps, which a plain
    ``restart`` refuses. Non-UI daemons (``kanban-km`` / ``kanban-km-serve``) do not serve the UI, so
    they use the ordinary restart and have no graceful variant.

    Args:
        app: The PM2 app name.

    Returns:
        ``None`` when ``app`` is a graceful-restartable UI app; otherwise a human-readable refusal
        string (the HTTP layer maps a non-``None`` return to a 422).
    """
    if app not in PM2_ALLOWLIST:
        return f"app '{app}' is not in the PM2 allowlist"
    if app not in UI_APP_NAMES:
        return f"graceful restart applies only to a UI app, not '{app}' (use a plain restart)"
    return None
