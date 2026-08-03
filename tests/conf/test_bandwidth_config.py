"""Unit tests for BandwidthConfig — byte-size coercion, zero rejection, defaults."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personalscraper.conf.models.acquire import BandwidthConfig


class TestBandwidthConfigDefaults:
    """Default state: all four fields are None (no caps)."""

    def test_all_fields_none_by_default(self) -> None:
        """All four bandwidth fields default to None."""
        cfg = BandwidthConfig()
        assert cfg.per_torrent_down is None
        assert cfg.per_torrent_up is None
        assert cfg.global_down is None
        assert cfg.global_up is None


class TestByteSizeCoercion:
    """Human-readable byte-size strings are coerced to integer bytes (D10)."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("5MB", 5_000_000),
            ("1GB", 1_000_000_000),
            ("10MiB", 10_485_760),
            ("100KB", 100_000),
            ("2GiB", 2_147_483_648),
            ("500B", 500),
            ("1.5GB", 1_500_000_000),
        ],
    )
    def test_string_coercion(self, raw: str, expected: int) -> None:
        """Human-readable byte strings are coerced to integer bytes via ByteSize."""
        cfg = BandwidthConfig(per_torrent_down=raw)
        assert cfg.per_torrent_down == expected

    def test_int_passthrough(self) -> None:
        """Integer values pass through coercion unchanged."""
        cfg = BandwidthConfig(per_torrent_down=42_000)
        assert cfg.per_torrent_down == 42_000

    def test_none_passthrough(self) -> None:
        """None values pass through coercion unchanged."""
        cfg = BandwidthConfig(per_torrent_down=None)
        assert cfg.per_torrent_down is None

    def test_coercion_applies_to_all_fields(self) -> None:
        """Coercion applies independently to each of the four cap fields."""
        cfg = BandwidthConfig(
            per_torrent_down="1MB",
            per_torrent_up="2MB",
            global_down="10MB",
            global_up="5MB",
        )
        assert cfg.per_torrent_down == 1_000_000
        assert cfg.per_torrent_up == 2_000_000
        assert cfg.global_down == 10_000_000
        assert cfg.global_up == 5_000_000


class TestZeroRejection:
    """Zero and negative values are rejected (D2)."""

    def test_zero_rejected(self) -> None:
        """Zero is rejected — it is NOT the unlimited sentinel."""
        with pytest.raises(ValidationError, match="must be > 0"):
            BandwidthConfig(per_torrent_down=0)

    def test_negative_rejected(self) -> None:
        """Negative values are rejected."""
        with pytest.raises(ValidationError, match="must be > 0"):
            BandwidthConfig(per_torrent_down=-1)

    def test_garbage_string_rejected(self) -> None:
        """Unparseable strings raise a ValidationError."""
        with pytest.raises(ValidationError):
            BandwidthConfig(per_torrent_down="not_a_size")


class TestPartialConfig:
    """Only the fields that are set are validated; others stay None."""

    def test_partial_config_mixed_none_and_values(self) -> None:
        """Mixing set and None fields works — only set fields are validated."""
        cfg = BandwidthConfig(per_torrent_down="5MB", global_down=None)
        assert cfg.per_torrent_down == 5_000_000
        assert cfg.per_torrent_up is None
        assert cfg.global_down is None
        assert cfg.global_up is None
