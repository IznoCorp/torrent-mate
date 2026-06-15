"""Tests for SortConfig + ProcessCleanConfig seed-pure verify flags (phase 4.1)."""

from __future__ import annotations

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.conf.models.scraper import ProcessCleanConfig, SortConfig


def test_sort_config_verify_seed_pure_defaults_false() -> None:
    """SortConfig.verify_seed_pure defaults to False (guard off)."""
    assert SortConfig().verify_seed_pure is False


def test_process_clean_config_verify_seed_pure_defaults_false() -> None:
    """ProcessCleanConfig.verify_seed_pure defaults to False (reserved, not enforced)."""
    assert ProcessCleanConfig().verify_seed_pure is False


def test_sort_config_extra_fields_forbidden() -> None:
    """_StrictModel extra='forbid' rejects unknown fields on SortConfig."""
    with pytest.raises(Exception):
        SortConfig(unknown_field=True)  # type: ignore[call-arg]


def test_process_clean_config_extra_fields_forbidden() -> None:
    """_StrictModel extra='forbid' rejects unknown fields on ProcessCleanConfig."""
    with pytest.raises(Exception):
        ProcessCleanConfig(unknown_field=True)  # type: ignore[call-arg]


def test_config_sort_and_process_clean_default_factories(test_config: Config) -> None:
    """Config exposes sort + process_clean sub-models defaulting to seed-pure off."""
    assert isinstance(test_config.sort, SortConfig)
    assert isinstance(test_config.process_clean, ProcessCleanConfig)
    assert test_config.sort.verify_seed_pure is False
    assert test_config.process_clean.verify_seed_pure is False
