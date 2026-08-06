"""Fixtures for the acquisition web read-model tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.config import Config


def _cfg_with_acquire(test_config: Config, acquire_db: Path) -> Config:
    """Return *test_config* with its acquire sub-config pointed at *acquire_db*."""
    return test_config.model_copy(update={"acquire": test_config.acquire.model_copy(update={"db_path": acquire_db})})


@pytest.fixture
def acquire_store(test_config: Config, tmp_path: Path):
    """A ConcreteAcquireStore on a temp database.

    Builds the store the same way the app does (via build_acquire_store), so the
    test exercises the real schema managed by the store, not a hand-rolled one.
    """
    cfg = _cfg_with_acquire(test_config, tmp_path / "acquire.db")
    return build_acquire_store(cfg.acquire)
