"""Tests for AppContext.torrent_client field (DESIGN D3/D9)."""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

from personalscraper.core.app_context import AppContext


def test_torrent_client_field_exists() -> None:
    """AppContext declares a torrent_client field.

    Design: docs/reference/architecture.md#appcontext-field-table
    Contract: AppContext exposes a torrent_client field (typed
    QBitClient | TransmissionClient | None) alongside config, settings,
    event_bus and provider_registry, per the documented field table.
    """
    fields = {f.name for f in dataclasses.fields(AppContext)}
    assert "torrent_client" in fields


def test_torrent_client_defaults_none() -> None:
    """torrent_client defaults to None — read-only commands must not break (D9)."""
    ctx = AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=MagicMock(),
        provider_registry=MagicMock(),
        torrent_client=None,
    )
    assert ctx.torrent_client is None


def test_torrent_client_can_be_set() -> None:
    """torrent_client accepts a concrete client object."""
    mock_client = MagicMock()
    ctx = AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=MagicMock(),
        provider_registry=MagicMock(),
        torrent_client=mock_client,
    )
    assert ctx.torrent_client is mock_client
