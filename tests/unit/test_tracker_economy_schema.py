"""Unit tests for TrackerEconomyConfig + TrackerProviderConfig.economy.

Design: tracker-economy §Components.1 — schema validation rules.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personalscraper.conf.models.api_config import TrackerEconomyConfig, TrackerProviderConfig


class TestTrackerEconomyConfig:
    """TrackerEconomyConfig Pydantic validation rules."""

    def test_valid_policy_stores_seconds(self) -> None:
        """Humanized duration strings are stored as integer seconds."""
        cfg = TrackerEconomyConfig(
            target_ratio=2.0,
            min_ratio=1.0,
            min_seed_time="72h",  # type: ignore[arg-type]
            hit_and_run_grace="48h",  # type: ignore[arg-type]
        )
        assert cfg.min_seed_time == 259_200  # 72 * 3600
        assert cfg.hit_and_run_grace == 172_800  # 48 * 3600

    def test_bare_int_duration_passes_through(self) -> None:
        """A bare int is accepted as already-seconds."""
        assert TrackerEconomyConfig(target_ratio=1.5, min_seed_time=3600).min_seed_time == 3_600

    def test_target_ratio_below_min_ratio_rejected(self) -> None:
        """target_ratio < min_ratio raises ValidationError."""
        with pytest.raises(ValidationError, match="target_ratio"):
            TrackerEconomyConfig(target_ratio=0.5, min_ratio=1.0, min_seed_time=0)

    def test_negative_target_ratio_rejected(self) -> None:
        """Negative target_ratio raises ValidationError."""
        with pytest.raises(ValidationError, match=r"target_ratio \(-1.0\) must be >= min_ratio"):
            TrackerEconomyConfig(target_ratio=-1.0, min_seed_time=0)

    def test_negative_min_ratio_rejected(self) -> None:
        """Negative min_ratio raises ValidationError."""
        with pytest.raises(ValidationError, match="min_ratio must be >= 0"):
            TrackerEconomyConfig(target_ratio=1.0, min_ratio=-0.1, min_seed_time=0)

    def test_extra_field_rejected(self) -> None:
        """_StrictModel forbids extra fields."""
        with pytest.raises(ValidationError):
            TrackerEconomyConfig(target_ratio=1.0, min_seed_time=0, unknown="oops")  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        """min_ratio defaults to 1.0; hit_and_run_grace defaults to 0."""
        cfg = TrackerEconomyConfig(target_ratio=2.0, min_seed_time=0)
        assert cfg.min_ratio == 1.0
        assert cfg.hit_and_run_grace == 0

    def test_malformed_duration_rejected(self) -> None:
        """Malformed duration string raises ValidationError."""
        with pytest.raises(ValidationError):
            TrackerEconomyConfig(target_ratio=1.0, min_seed_time="bad")  # type: ignore[arg-type]

    def test_equal_ratios_accepted(self) -> None:
        """Equal ratios are accepted (pins the inclusive target_ratio >= min_ratio boundary)."""
        cfg = TrackerEconomyConfig(target_ratio=1.0, min_ratio=1.0, min_seed_time=0)
        assert cfg.target_ratio == cfg.min_ratio == 1.0

    def test_negative_min_seed_time_rejected(self) -> None:
        """Negative bare-int min_seed_time raises ValidationError."""
        with pytest.raises(ValidationError, match="min_seed_time"):
            TrackerEconomyConfig(target_ratio=1.0, min_seed_time=-1)

    def test_negative_hit_and_run_grace_rejected(self) -> None:
        """Negative hit_and_run_grace raises ValidationError."""
        with pytest.raises(ValidationError, match="hit_and_run_grace"):
            TrackerEconomyConfig(target_ratio=1.0, min_seed_time=0, hit_and_run_grace=-5)

    def test_negative_humanized_duration_rejected(self) -> None:
        """Negative humanized duration '-3h' surfaces as ValidationError (parser rejects the sign)."""
        with pytest.raises(ValidationError, match="non-integer magnitude"):
            TrackerEconomyConfig(target_ratio=1.0, min_seed_time="-3h")  # type: ignore[arg-type]

    def test_nan_target_ratio_rejected(self) -> None:
        """NaN target_ratio raises ValidationError (finiteness guard catches it)."""
        with pytest.raises(ValidationError, match="finite"):
            TrackerEconomyConfig(target_ratio=float("nan"), min_seed_time=0)

    def test_inf_target_ratio_rejected(self) -> None:
        """Infinite target_ratio raises ValidationError (finiteness guard catches it)."""
        with pytest.raises(ValidationError, match="finite"):
            TrackerEconomyConfig(target_ratio=float("inf"), min_seed_time=0)

    def test_nan_min_ratio_rejected(self) -> None:
        """NaN min_ratio raises ValidationError (pins the min_ratio finiteness branch)."""
        with pytest.raises(ValidationError, match="finite"):
            TrackerEconomyConfig(target_ratio=2.0, min_ratio=float("nan"), min_seed_time=0)

    def test_inf_min_ratio_rejected(self) -> None:
        """Infinite min_ratio raises ValidationError (pins the min_ratio finiteness branch)."""
        with pytest.raises(ValidationError, match="finite"):
            TrackerEconomyConfig(target_ratio=2.0, min_ratio=float("inf"), min_seed_time=0)


class TestTrackerProviderConfigEconomy:
    """TrackerProviderConfig.economy optional field behaviour."""

    def test_economy_none_by_default(self) -> None:
        """Economy is None when not provided (activation-only mode)."""
        assert TrackerProviderConfig(enabled=True).economy is None

    def test_economy_attached_directly(self) -> None:
        """Economy can be set to a TrackerEconomyConfig instance."""
        cfg = TrackerProviderConfig(
            enabled=True,
            economy=TrackerEconomyConfig(target_ratio=2.0, min_seed_time="72h"),  # type: ignore[arg-type]
        )
        assert cfg.economy is not None
        assert cfg.economy.min_seed_time == 259_200

    def test_economy_from_nested_dict(self) -> None:
        """model_validate with a nested economy dict coerces durations."""
        cfg = TrackerProviderConfig.model_validate(
            {
                "enabled": True,
                "economy": {"target_ratio": 2.0, "min_seed_time": "72h", "hit_and_run_grace": "0h"},
            }
        )
        assert cfg.economy is not None
        assert cfg.economy.min_seed_time == 259_200
