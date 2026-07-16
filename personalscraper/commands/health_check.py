"""``personalscraper health-check`` — proactive local health monitor.

Designed to run under PM2 on a cron cadence. It checks the things the pipeline's
own Telegram/healthcheck alerting does NOT cover — daemon liveness and recent
log anomalies — and sends a single Telegram alert when something is wrong.

Checks (all fail-soft — a check that itself errors is reported, never crashes):

1. **Daemon liveness** — the ``personalscraper-watch`` PM2 app must be ``online``
   with a real OS pid (a pyenv-shim / crash-loop leaves it ``online`` with
   ``pid=None`` — the exact failure fixed in #216).
2. **Recent log errors** — ``logs/personalscraper.json`` scanned for ``level ==
   "error"`` within the lookback window, minus known-benign events.
3. **Stuck pipeline** — ``pipeline.lock`` held for longer than a run should take
   (a crashed run that never released the lock).

Exit code is 0 when healthy, 1 when any anomaly was found (so healthchecks.io /
PM2 can surface it too). The Telegram alert is best-effort and never affects the
exit code.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from personalscraper import cli_helpers
from personalscraper.cli_app import app, command_with_telemetry
from personalscraper.logger import LOGS_DIR, get_logger

if TYPE_CHECKING:
    from personalscraper.cli_state import AppCtx

log = get_logger("health_check")

# The long-running daemon that MUST have a live process. Cron apps (follow-detect,
# grab, index-enrich, backfill-ids) legitimately sit ``pid=None`` between fires.
_REQUIRED_DAEMONS = ("personalscraper-watch",)

# Events that are noise, not failures, and must not trigger an alert.
_BENIGN_EVENTS = frozenset(
    {
        "indexer.spotlight.flag_ignored_macfuse",  # macFUSE ghost inodes — operator directive: ignore
    }
)


def _check_daemons() -> list[str]:
    """Return anomaly strings for any required daemon that is not truly running.

    Returns:
        One string per unhealthy required daemon (empty when all are live).
    """
    anomalies: list[str] = []
    try:
        raw = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        apps = {a.get("name"): a for a in json.loads(raw.stdout or "[]")}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return [f"pm2 jlist failed ({type(exc).__name__}: {exc}) — cannot verify daemons"]

    for name in _REQUIRED_DAEMONS:
        app_entry = apps.get(name)
        if app_entry is None:
            anomalies.append(f"{name}: not registered in PM2")
            continue
        status = app_entry.get("pm2_env", {}).get("status")
        pid = app_entry.get("pid")
        if status != "online" or not pid:
            anomalies.append(f"{name}: status={status!r} pid={pid!r} (expected online with a live pid)")
    return anomalies


def _check_recent_errors(lookback_minutes: int) -> list[str]:
    """Scan the JSON log for ``error``-level lines within the lookback window.

    Args:
        lookback_minutes: How far back to consider a log line recent.

    Returns:
        Up to 5 anomaly strings summarising recent errors (empty when none).
    """
    log_path = LOGS_DIR / "personalscraper.json"
    if not log_path.exists():
        return []
    cutoff = datetime.now() - timedelta(minutes=lookback_minutes)
    hits: list[str] = []
    try:
        # Tail-ish: only the last slice matters; read all but keep it bounded.
        lines = log_path.read_text(errors="replace").splitlines()[-4000:]
    except OSError as exc:
        return [f"cannot read {log_path.name} ({exc})"]

    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("level") != "error":
            continue
        event = d.get("event", "")
        if event in _BENIGN_EVENTS:
            continue
        ts_raw = d.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", ""))
        except ValueError:
            ts = None
        if ts is not None and ts < cutoff:
            continue
        hits.append(f"{ts_raw[-19:]} {event}")
    if not hits:
        return []
    summary = [f"{len(hits)} error log line(s) in the last {lookback_minutes}min:"]
    summary.extend(f"  • {h}" for h in hits[-5:])
    return summary


def _check_stuck_lock(state: "AppCtx", max_run_minutes: int) -> list[str]:
    """Report a pipeline.lock that has been held longer than a run should take.

    Args:
        state: CLI state carrying the loaded config.
        max_run_minutes: Age beyond which a held lock is considered stuck.

    Returns:
        A one-element anomaly list when the lock looks stuck, else empty.
    """
    from personalscraper.lock import is_lock_held  # noqa: PLC0415

    config = state.config
    assert config is not None
    lock_path = Path(config.paths.data_dir) / "pipeline.lock"
    if not lock_path.exists() or not is_lock_held(lock_path):
        return []
    try:
        age_min = (datetime.now().timestamp() - lock_path.stat().st_mtime) / 60
    except OSError:
        return []
    if age_min > max_run_minutes:
        return [f"pipeline.lock held for {age_min:.0f}min (> {max_run_minutes}min) — a run may be stuck"]
    return []


def _send_alert(config_obj: object, anomalies: list[str]) -> None:
    """Best-effort Telegram alert; failures are logged and swallowed.

    Args:
        config_obj: Unused placeholder kept for call-site symmetry.
        anomalies: The anomaly lines to include in the alert body.
    """
    from personalscraper.api.notify.telegram import TelegramNotifier  # noqa: PLC0415
    from personalscraper.api.transport._http import HttpTransport  # noqa: PLC0415
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

    settings = cli_helpers.get_settings()
    if not TelegramNotifier.is_configured(settings):
        log.warning("health_check_telegram_unconfigured")
        return
    body = "⚠️ <b>personalscraper health-check</b>\n" + "\n".join(anomalies)
    try:
        transport = HttpTransport(TelegramNotifier.policy(settings.telegram_bot_token), event_bus=EventBus())
        TelegramNotifier(transport, settings.telegram_chat_id).send(body)
    except Exception as exc:  # noqa: BLE001 - alerting must never crash the check
        log.warning("health_check_alert_failed", error=str(exc), exc_info=True)


@app.command(name="health-check")
@command_with_telemetry("health-check")
def health_check(
    ctx: typer.Context,
    lookback_minutes: int = typer.Option(90, "--lookback-minutes", help="Recent-error window."),
    max_run_minutes: int = typer.Option(60, "--max-run-minutes", help="Held-lock age considered stuck."),
    no_alert: bool = typer.Option(False, "--no-alert", help="Do not send the Telegram alert (check only)."),
) -> None:
    """Check daemon liveness + recent log errors + stuck lock; alert on anomalies.

    Exits 0 when healthy, 1 when any anomaly is found (Telegram alert sent unless
    ``--no-alert``). Intended to run under PM2 on an hourly cron.

    Args:
        ctx: Typer context carrying the loaded config on ``ctx.obj``.
        lookback_minutes: Recent-error scan window.
        max_run_minutes: Held-lock age beyond which the pipeline is stuck.
        no_alert: Suppress the Telegram alert (still logs + exits non-zero).
    """
    state: AppCtx = ctx.obj

    anomalies: list[str] = []
    anomalies += _check_daemons()
    anomalies += _check_recent_errors(lookback_minutes)
    anomalies += _check_stuck_lock(state, max_run_minutes)

    if not anomalies:
        log.info("health_check_ok")
        typer.echo("health-check: OK")
        return

    log.warning("health_check_anomalies", count=len(anomalies), anomalies=anomalies)
    typer.echo("health-check: ANOMALIES\n" + "\n".join(anomalies))
    if not no_alert:
        _send_alert(state.config, anomalies)
    raise typer.Exit(1)
