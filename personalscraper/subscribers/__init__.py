"""Event-bus subscribers (auto-subscribed on construction).

Subscribers self-subscribe to bus events in ``__init__`` and own their
subscription tokens. Each one calls ``close()`` to unsubscribe on teardown.
See ``docs/features/event-bus/DESIGN.md`` §Subscribers.
"""

from personalscraper.subscribers.rich_console import RichConsoleSubscriber
from personalscraper.subscribers.telegram import TelegramSubscriber

__all__ = ["RichConsoleSubscriber", "TelegramSubscriber"]
