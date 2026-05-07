"""Tests for ThresholdEntry — ByteSize-aware threshold parsing."""

import pytest
from pydantic import ValidationError

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._ranking import ThresholdEntry


class TestThresholdEntryAtParsing:
    """ThresholdEntry.at accepts int, ByteSize, or human-readable size string."""

    def test_decimal_gb_string(self) -> None:
        """ThresholdEntry(at='1GB', score=10).at == 1_000_000_000."""
        assert ThresholdEntry(at="1GB", score=10).at == 1_000_000_000  # type: ignore[arg-type]

    def test_binary_mib_string(self) -> None:
        """ThresholdEntry(at='500MiB', score=5).at == 524_288_000."""
        assert ThresholdEntry(at="500MiB", score=5).at == 524_288_000  # type: ignore[arg-type]

    def test_raw_int(self) -> None:
        """ThresholdEntry(at=100, score=2).at == 100 (raw counter, e.g. seeders)."""
        assert ThresholdEntry(at=100, score=2).at == 100

    def test_bytesize_instance(self) -> None:
        """ThresholdEntry(at=ByteSize.parse('2GB'), score=15).at == 2_000_000_000."""
        assert ThresholdEntry(at=ByteSize.parse("2GB"), score=15).at == 2_000_000_000  # type: ignore[arg-type]

    def test_invalid_literal_raises(self) -> None:
        """Invalid size literal raises ValidationError."""
        with pytest.raises(ValidationError):
            ThresholdEntry(at="not-a-size", score=1)  # type: ignore[arg-type]
