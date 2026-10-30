"""Unit tests for ``personalscraper.app.accounts.pin_repository`` — Plex PINs ↔ dataclasses over ``app.db``.

Every method round-trips its dataclass; a check is claimed once per interval and a purge is bounded.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.pin_repository import PlexPinRepository, PlexPinRow
from personalscraper.app.store.store import AppStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` on ``tmp_path``.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def repo(store: AppStore) -> PlexPinRepository:
    """The store's Plex PIN repository.

    Args:
        store: The fresh store.

    Returns:
        Its repository.
    """
    return store.pins


class TestPins:
    """Plex PINs."""

    def test_pin_round_trips_checked_and_consumed(self, repo: PlexPinRepository) -> None:
        """Inserted, checked, consumed."""
        pin = PlexPinRow(
            pin_id=9,
            code="ABCD",
            nonce_hash="n",
            created_at=1.0,
            expires_at=2.0,
            last_checked_at=None,
            consumed_at=None,
        )
        repo.insert_pin(pin)
        assert repo.pin(9) == pin
        repo.mark_pin_checked(9, now=1.5)
        repo.consume_pin(9, now=1.7)
        assert repo.pin(9) == PlexPinRow(**{**pin.__dict__, "last_checked_at": 1.5, "consumed_at": 1.7})
        assert repo.pin(10) is None

    def test_claim_pin_check_lets_one_check_through_per_interval(self, repo: PlexPinRepository) -> None:
        """The first claim wins; a second inside the interval loses; one past it wins again."""
        repo.insert_pin(PlexPinRow(9, "ABCD", "n", 1.0, None, None, None))
        assert repo.claim_pin_check(9, now=5.0, min_interval=1.0) is True
        assert repo.claim_pin_check(9, now=5.5, min_interval=1.0) is False
        assert repo.pin(9).last_checked_at == 5.0  # type: ignore[union-attr]
        assert repo.claim_pin_check(9, now=6.0, min_interval=1.0) is True
        assert repo.claim_pin_check(10, now=7.0, min_interval=1.0) is False

    def test_a_consumed_pin_is_neither_claimed_nor_consumed_again(self, repo: PlexPinRepository) -> None:
        """``consume_pin`` answers whether this call consumed it; a consumed PIN is never checked again."""
        repo.insert_pin(PlexPinRow(9, "ABCD", "n", 1.0, None, None, None))
        assert repo.consume_pin(9, now=2.0) is True
        assert repo.consume_pin(9, now=3.0) is False
        assert repo.pin(9).consumed_at == 2.0  # type: ignore[union-attr]
        assert repo.claim_pin_check(9, now=9.0, min_interval=1.0) is False

    def test_purge_pins_deletes_the_expired_and_the_consumed_only(self, repo: PlexPinRepository) -> None:
        """Past its expiry, consumed, or with no expiry and older than the lifetime: deleted; the live kept."""
        repo.insert_pin(PlexPinRow(1, "A", "n", 1.0, 50.0, None, None))  # expired
        repo.insert_pin(PlexPinRow(2, "B", "n", 90.0, 200.0, None, 95.0))  # consumed, not yet expired
        repo.insert_pin(PlexPinRow(3, "C", "n", 10.0, None, None, None))  # no expiry, past the lifetime
        repo.insert_pin(PlexPinRow(4, "D", "n", 90.0, 200.0, 95.0, None))  # alive
        repo.insert_pin(PlexPinRow(5, "E", "n", 90.0, None, None, None))  # no expiry, within the lifetime

        assert repo.purge_pins(now=100.0, lifetime=30.0, limit=10) == 3

        assert [pin_id for pin_id in range(1, 6) if repo.pin(pin_id) is not None] == [4, 5]

    def test_purge_pins_is_bounded(self, repo: PlexPinRepository) -> None:
        """One call deletes at most ``limit`` rows; the next takes the rest."""
        for pin_id in range(1, 6):
            repo.insert_pin(PlexPinRow(pin_id, "A", "n", 1.0, 2.0, None, None))

        assert repo.purge_pins(now=100.0, lifetime=30.0, limit=2) == 2
        assert repo.purge_pins(now=100.0, lifetime=30.0, limit=10) == 3
        assert repo.purge_pins(now=100.0, lifetime=30.0, limit=10) == 0
