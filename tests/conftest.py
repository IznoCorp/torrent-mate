"""Shared pytest fixtures for PersonalScraper tests."""

import os

import pytest

from personalscraper.config import Settings

# Disable Rich/Typer color output so help-text assertions (e.g. "--disk" in output)
# match the rendered text without ANSI escape codes splitting option names.
os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("TERM", "dumb")


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
