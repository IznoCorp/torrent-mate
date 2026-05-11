"""Pipeline observer implementations."""

from personalscraper.observers.rich_console import RichConsoleObserver
from personalscraper.observers.telegram import TelegramObserver

__all__ = ["RichConsoleObserver", "TelegramObserver"]
