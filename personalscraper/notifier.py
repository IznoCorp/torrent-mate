"""Telegram notification client — stub, fully implemented in V6.

Provides the TelegramNotifier interface for sending pipeline reports
via Telegram Bot API. Stub methods return False until V6 implementation.
"""

from personalscraper.config import Settings
from personalscraper.models import PipelineReport


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
        Stub implementation — always returns False until V6.

        Args:
            message: Message text to send.
            parse_mode: Telegram parse mode ("HTML" or "Markdown").

        Returns:
            True on success, False on failure or stub.
        """
        return False

    def send_report(self, report: PipelineReport) -> bool:
        """Format a PipelineReport as HTML and send it.

        Stub implementation — always returns False until V6.

        Args:
            report: Completed pipeline report to format and send.

        Returns:
            True on success, False on failure or stub.
        """
        return False

    @staticmethod
    def is_configured(settings: Settings) -> bool:
        """Check if Telegram bot_token and chat_id are set in config.

        Args:
            settings: Application settings to check.

        Returns:
            True if both token and chat_id are non-empty.
        """
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)
