"""Telegram notification client and healthcheck pinger.

Sends pipeline reports via Telegram Bot API and pings external
monitoring services (healthchecks.io). All external calls are
fault-tolerant and never raise — failures are logged as warnings
but never halt the pipeline.
"""

import requests

from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.models import PipelineReport

log = get_logger("notifier")

# Telegram API base URL (Bot API)
_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Timeout for all external HTTP calls (seconds)
_TIMEOUT = 10


class TelegramNotifier:
    """Send notifications via Telegram Bot API.

    Attributes:
        bot_token: Telegram bot authentication token.
        chat_id: Target chat/user ID for messages.
    """

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """Initialize the notifier with Telegram credentials.

        Args:
            bot_token: Telegram bot token from BotFather.
            chat_id: Target chat or user ID.
        """
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Post a message to Telegram API.

        Never raises — catches all exceptions and logs a warning.

        Args:
            message: Message text to send.
            parse_mode: Telegram parse mode ("HTML" or "Markdown").

        Returns:
            True on success, False on failure.
        """
        url = _TELEGRAM_API.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }
        try:
            resp = requests.post(url, json=payload, timeout=_TIMEOUT)
            if resp.ok:
                log.info("telegram_sent", chat_id=self.chat_id)
                return True
            log.warning("telegram_api_error", status_code=resp.status_code, body=resp.text[:200])
            return False
        except requests.Timeout:
            log.warning("telegram_timeout", timeout_s=_TIMEOUT)
            return False
        except requests.RequestException as exc:
            log.warning("telegram_send_failed", error=str(exc))
            return False
        except Exception as exc:  # noqa: BLE001 — best-effort fallback; notification must not mask the underlying operation
            log.exception("telegram_unexpected_error", error=str(exc))
            return False

    def send_report(self, report: PipelineReport) -> bool:
        """Format a PipelineReport as HTML and send it.

        Args:
            report: Completed pipeline report to format and send.

        Returns:
            True on success, False on failure.
        """
        return self.send(report.to_html())

    @staticmethod
    def is_configured(settings: Settings) -> bool:
        """Check if Telegram bot_token and chat_id are set in config.

        Args:
            settings: Application settings to check.

        Returns:
            True if both token and chat_id are non-empty.
        """
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)


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
