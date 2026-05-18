"""Notify capability composition tests (phase 14).

Sub-phase 1.5 moved the ``Notifier`` and ``HealthChecker`` Protocols
to :mod:`personalscraper.api.notify._contracts` with
``@runtime_checkable``. Phase 14 pins that the concrete clients
satisfy the matching capability via structural subtyping and *only*
that capability.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.notify._contracts import HealthChecker, Notifier
from personalscraper.api.notify.healthchecks import HealthcheckClient
from personalscraper.api.notify.telegram import TelegramNotifier


def _telegram() -> TelegramNotifier:
    """Build a :class:`TelegramNotifier` with a mock HTTP transport."""
    transport = MagicMock()
    return TelegramNotifier(transport=transport, chat_id="42")


def _healthcheck() -> HealthcheckClient:
    """Build a :class:`HealthcheckClient` with a mock HTTP transport."""
    transport = MagicMock()
    return HealthcheckClient(transport=transport)


def test_telegram_notifier_is_notifier_isinstance() -> None:
    """``TelegramNotifier`` satisfies :class:`Notifier` via structural subtyping."""
    assert isinstance(_telegram(), Notifier)


def test_telegram_notifier_not_health_checker_isinstance() -> None:
    """``TelegramNotifier`` does not advertise the :class:`HealthChecker` capability."""
    assert not isinstance(_telegram(), HealthChecker)


def test_healthcheck_client_is_health_checker_isinstance() -> None:
    """``HealthcheckClient`` satisfies :class:`HealthChecker`."""
    assert isinstance(_healthcheck(), HealthChecker)


def test_healthcheck_client_not_notifier_isinstance() -> None:
    """``HealthcheckClient`` does not advertise the :class:`Notifier` capability."""
    assert not isinstance(_healthcheck(), Notifier)
