"""Unit tests for ``personalscraper.app.store.setting_repository`` — the application settings over ``app.db``.

A setting is stored, read back and replaced.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.store.setting_repository import SettingRepository
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
def repo(store: AppStore) -> SettingRepository:
    """The store's setting repository.

    Args:
        store: The fresh store.

    Returns:
        Its repository.
    """
    return store.settings


class TestSettings:
    """The application's settings."""

    def test_setting_set_read_and_replaced(self, repo: SettingRepository) -> None:
        """Absent, set, replaced."""
        assert repo.setting("plex.client_identifier") is None
        repo.set_setting("plex.client_identifier", "one")
        repo.set_setting("plex.client_identifier", "two")
        assert repo.setting("plex.client_identifier") == "two"
