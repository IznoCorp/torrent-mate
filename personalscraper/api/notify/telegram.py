"""Telegram notifier — `Notifier` Protocol implementation.

Implements DESIGN §7.2 on top of the unified `HttpTransport` infrastructure.

Telegram particularities (see `docs/reference/telegram-api.md`):

- **Token-in-URL auth**: the bot token is part of the URL path
  (`https://api.telegram.org/bot<TOKEN>/<method>`). `auth = NoAuth()`; the
  `base_url` is built per-instance from the token at `policy()` time.
- **Fail-soft contract**: `send()` and `send_report()` MUST NEVER raise.
  Any `ApiError` is logged and the call returns `False`.
- **Per-chat rate limit**: 1 message/second per chat (Telegram FAQ). The
  pipeline only sends to one chat → `requests_per_second = 1.0`.
- **Message length**: hard cap of 4096 chars per `text` field. Long messages
  are chunked at this boundary by `_chunk()`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._auth import NoAuth
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger
from personalscraper.models import PipelineReport

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport
    from personalscraper.config import Settings

log = get_logger("api.telegram")

# Telegram message length cap (per Telegram Bot API).
_MAX_MESSAGE_LEN = 4096

# Tolerant circuit policy — Telegram is best-effort observability;
# brief outages must not lock out reporting for the whole pipeline run.
_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=10, cooldown_seconds=60.0)
_DEFAULT_RETRY = RetryPolicy(max_attempts=3)
_DEFAULT_RATE = RateLimitPolicy(requests_per_second=1.0)


class TelegramNotifier:
    """Send pipeline notifications via the Telegram Bot API.

    Implements the `Notifier` Protocol (DESIGN §7.1). Fail-soft by contract:
    any transport or API error is logged and converted to a `False` return —
    the notifier MUST NEVER raise, so a Telegram outage cannot abort the
    pipeline.

    Attributes:
        provider_name: Always `"telegram"`.
        REQUIRED_CREDS: `.env` variable names — `TELEGRAM_BOT_TOKEN`,
            `TELEGRAM_CHAT_ID`.
    """

    provider_name: ClassVar[str] = "telegram"
    REQUIRED_CREDS: ClassVar[list[str]] = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]

    @classmethod
    def policy(cls, bot_token: str) -> TransportPolicy:
        """Build a `TransportPolicy` for the Telegram Bot API.

        The bot token is embedded in the `base_url` path because Telegram
        does not expose a header-based auth surface (see doc §Authentication).

        Args:
            bot_token: Bot token obtained from @BotFather, format
                `<bot_id>:<35-char-secret>`.

        Returns:
            TransportPolicy configured for `https://api.telegram.org/bot<TOKEN>`.
        """
        return TransportPolicy(
            provider_name="telegram",
            base_url=f"https://api.telegram.org/bot{bot_token}",
            auth=NoAuth(),
            timeout_seconds=10.0,
            retry=_DEFAULT_RETRY,
            circuit=_DEFAULT_CIRCUIT,
            rate_limit=_DEFAULT_RATE,
        )

    def __init__(self, transport: HttpTransport, chat_id: str) -> None:
        """Initialize the notifier.

        Args:
            transport: Pre-configured `HttpTransport` (typically built from
                `TelegramNotifier.policy(bot_token)`).
            chat_id: Numeric chat identifier from `.env`. May be a string
                wrapping a negative number for groups.
        """
        self._transport = transport
        self._chat_id = chat_id

    # -- Notifier Protocol --------------------------------------------------

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Post a free-form message via `sendMessage`.

        Long messages are split into 4096-char chunks; each chunk becomes a
        separate POST. The send is treated as successful only when every
        chunk succeeds — a mid-send failure aborts the remaining chunks and
        returns `False` (fail-soft).

        Args:
            message: Text body. Empty strings are accepted (Telegram rejects
                them at the API level; the rejection is logged and `False`
                returned, never raised).
            parse_mode: One of `"HTML"`, `"Markdown"`, `"MarkdownV2"`. Default
                `"HTML"` matches the legacy `notifier.py` behavior.

        Returns:
            `True` if every chunk was accepted; `False` on any error.
        """
        try:
            for chunk in self._chunk(message, max_len=_MAX_MESSAGE_LEN):
                self._transport.post(
                    "/sendMessage",
                    data={
                        "chat_id": self._chat_id,
                        "text": chunk,
                        "parse_mode": parse_mode,
                    },
                )
        except ApiError as exc:
            log.warning(
                "telegram_send_failed",
                http_status=exc.http_status,
                message=exc.message,
            )
            return False
        except Exception as exc:  # noqa: BLE001 — fail-soft: notifier must never abort the pipeline
            log.exception("telegram_unexpected_error", error=str(exc))
            return False

        log.info("telegram_sent", chat_id=self._chat_id)
        return True

    def send_report(self, report: PipelineReport) -> bool:
        """Serialize a `PipelineReport` to HTML and send it.

        Args:
            report: Completed pipeline report.

        Returns:
            `True` on success, `False` on any send failure.
        """
        return self.send(report.to_html())

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def is_configured(settings: Settings) -> bool:
        """Check if both Telegram credentials are present in `Settings`.

        Args:
            settings: Application settings to inspect.

        Returns:
            `True` if both `telegram_bot_token` and `telegram_chat_id` are
            non-empty strings.
        """
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)

    @staticmethod
    def _chunk(text: str, max_len: int) -> list[str]:
        """Split `text` into pieces no longer than `max_len`.

        No semantic awareness — splitting happens at the byte boundary.
        Telegram parses each chunk independently, so an HTML tag straddling
        a chunk boundary will produce a 400 error on the chunk that lacks
        its opener (caught by `send`'s fail-soft handler).

        Args:
            text: Source string. Empty input returns `[""]` so the caller
                still issues one POST and lets Telegram surface its
                empty-body 400 via `ApiError`.
            max_len: Maximum chunk size in characters.

        Returns:
            List of chunks. Length always ≥ 1.
        """
        if not text:
            return [""]
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]
