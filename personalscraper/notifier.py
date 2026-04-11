"""Telegram notification client — stub, implemented in V6."""

from personalscraper.config import Settings
from personalscraper.models import PipelineReport


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """POST to Telegram API. Returns True on success. Stub — always returns False."""
        return False

    def send_report(self, report: PipelineReport) -> bool:
        """Format a PipelineReport as HTML and send it. Stub — always returns False."""
        return False

    @staticmethod
    def is_configured(settings: Settings) -> bool:
        """Check if bot_token and chat_id are set in config."""
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)
