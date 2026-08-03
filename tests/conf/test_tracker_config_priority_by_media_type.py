"""Validation tests for ``TrackerConfig.priority_by_media_type`` (phase 12)."""

from __future__ import annotations

import pytest

from personalscraper.conf.models.api_config import TrackerConfig, TrackerProviderConfig


def _providers() -> dict[str, TrackerProviderConfig]:
    return {
        "tr4ker": TrackerProviderConfig(enabled=True),
        "c411": TrackerProviderConfig(enabled=True),
    }


def test_priority_by_media_type_defaults_to_empty_dict() -> None:
    """Field is optional and defaults to ``{}``."""
    config = TrackerConfig(providers=_providers(), priority=["tr4ker", "c411"])
    assert config.priority_by_media_type == {}


def test_priority_by_media_type_accepts_subset_of_providers() -> None:
    """Override lists referencing only declared providers pass validation."""
    config = TrackerConfig(
        providers=_providers(),
        priority=["tr4ker", "c411"],
        priority_by_media_type={"movie_french": ["c411", "tr4ker"], "anime_jp": ["tr4ker"]},
    )
    assert config.priority_by_media_type["movie_french"] == ["c411", "tr4ker"]


def test_priority_by_media_type_rejects_unknown_provider() -> None:
    """A reference to a non-declared tracker fails validation loud."""
    with pytest.raises(ValueError) as exc_info:
        TrackerConfig(
            providers=_providers(),
            priority=["tr4ker", "c411"],
            priority_by_media_type={"movie_french": ["unknown_tracker", "c411"]},
        )
    assert "unknown_tracker" in str(exc_info.value)
