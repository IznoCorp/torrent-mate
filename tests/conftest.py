"""Shared pytest fixtures for PersonalScraper tests."""

import pytest

from personalscraper.config import Settings


@pytest.fixture
def mock_settings(tmp_path, monkeypatch):
    """Provide a Settings instance with temp paths and no real .env.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture for env vars.

    Returns:
        A Settings instance pointing to temporary directories.
    """
    monkeypatch.setenv("TORRENT_COMPLETE_DIR", str(tmp_path / "complete"))
    monkeypatch.setenv("STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setenv("DISK1_DIR", str(tmp_path / "disk1"))
    monkeypatch.setenv("DISK2_DIR", str(tmp_path / "disk2"))
    monkeypatch.setenv("DISK3_DIR", str(tmp_path / "disk3"))
    monkeypatch.setenv("DISK4_DIR", str(tmp_path / "disk4"))
    (tmp_path / "complete").mkdir()
    (tmp_path / "staging").mkdir()
    return Settings(_env_file=None)
