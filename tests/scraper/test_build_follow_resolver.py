"""Tests for _build_follow_tvdb_resolver (scrape-follow-id wiring).

Covers the review's invariant-4 (no MagicMock DB-file leak on a mock config) and
the build-path fail-soft (store errors ⇒ None ⇒ free match).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.scraper.run import _build_follow_tvdb_resolver


def test_mock_config_returns_none_and_leaks_no_file(tmp_path: Path, monkeypatch: Any) -> None:
    """Invariant 4: a mock/absent acquire config ⇒ None, and NO DB file created."""
    monkeypatch.chdir(tmp_path)
    resolver = _build_follow_tvdb_resolver(MagicMock())  # config.acquire.db_path is a mock
    assert resolver is None
    leaked = [p.name for p in tmp_path.iterdir() if "MagicMock" in p.name]
    assert leaked == []


def test_store_build_error_returns_none(tmp_path: Path) -> None:
    """A store that cannot be built ⇒ None (free match), never raises."""
    config = MagicMock()
    config.acquire.db_path = tmp_path / "acquire.db"
    with patch("personalscraper.acquire.store.build_acquire_store", side_effect=RuntimeError("boom")):
        assert _build_follow_tvdb_resolver(config) is None


def test_list_grabbed_error_returns_none(tmp_path: Path) -> None:
    """A store whose list_grabbed raises ⇒ None, never propagates."""
    config = MagicMock()
    config.acquire.db_path = tmp_path / "acquire.db"
    store = MagicMock()
    store.wanted.list_grabbed.side_effect = RuntimeError("db locked")
    with patch("personalscraper.acquire.store.build_acquire_store", return_value=store):
        assert _build_follow_tvdb_resolver(config) is None
    store.close.assert_called_once()  # store is always closed (finally)


def test_empty_grabbed_returns_none(tmp_path: Path) -> None:
    """No grabbed rows ⇒ None (nothing to force)."""
    config = MagicMock()
    config.acquire.db_path = tmp_path / "acquire.db"
    store = MagicMock()
    store.wanted.list_grabbed.return_value = []
    store.follow.list_all.return_value = []
    with (
        patch("personalscraper.acquire.store.build_acquire_store", return_value=store),
        patch("personalscraper.scraper.run._read_follow_years", return_value={}),
    ):
        assert _build_follow_tvdb_resolver(config) is None
