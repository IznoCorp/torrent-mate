"""Tests for ByteSize custom type."""

import pytest

from personalscraper.api._units import ByteSize


class TestByteSizeParse:
    """ByteSize.parse() tests per DESIGN S3.2."""

    def test_from_int(self) -> None:
        """parse(1024) returns 1024 bytes."""
        assert ByteSize.parse(1024).bytes == 1024

    def test_from_float(self) -> None:
        """parse(1024.0) returns 1024 bytes."""
        assert ByteSize.parse(1024.0).bytes == 1024

    def test_decimal_gb(self) -> None:
        """parse('1GB') returns 1_000_000_000 bytes."""
        assert ByteSize.parse("1GB").bytes == 1_000_000_000

    def test_binary_gib(self) -> None:
        """parse('1GiB') returns 1_073_741_824 bytes."""
        assert ByteSize.parse("1GiB").bytes == 1_073_741_824

    def test_binary_mib(self) -> None:
        """parse('500MiB') returns 524_288_000 bytes."""
        assert ByteSize.parse("500MiB").bytes == 524_288_000

    def test_plain_b(self) -> None:
        """parse('1024B') returns 1024 bytes."""
        assert ByteSize.parse("1024B").bytes == 1024

    def test_decimal_tb(self) -> None:
        """parse('1TB') returns 1_000_000_000_000 bytes."""
        assert ByteSize.parse("1TB").bytes == 1_000_000_000_000

    def test_decimal_kb(self) -> None:
        """parse('1KB') returns 1000 bytes."""
        assert ByteSize.parse("1KB").bytes == 1000

    def test_case_insensitive(self) -> None:
        """Unit parsing is case-insensitive."""
        assert ByteSize.parse("1gb").bytes == 1_000_000_000
        assert ByteSize.parse("1GiB").bytes == 1_073_741_824

    def test_with_whitespace(self) -> None:
        """Leading/trailing whitespace is ignored."""
        assert ByteSize.parse("  1GB  ").bytes == 1_000_000_000

    def test_fractional(self) -> None:
        """Fractional values are supported."""
        assert ByteSize.parse("1.5GB").bytes == 1_500_000_000

    def test_invalid_raises(self) -> None:
        """parse('not-a-size') raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size literal"):
            ByteSize.parse("not-a-size")

    def test_empty_raises(self) -> None:
        """parse('') raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size literal"):
            ByteSize.parse("")

    def test_idempotent(self) -> None:
        """parse(ByteSize(1024)) returns the same ByteSize."""
        bs = ByteSize(1024)
        assert ByteSize.parse(bs) is bs

    def test_idempotent_equal(self) -> None:
        """parse(ByteSize(1024)) == ByteSize(1024)."""
        assert ByteSize.parse(ByteSize(1024)) == ByteSize(1024)


class TestByteSizeComparison:
    """Ordering/comparison tests."""

    def test_gb_gt_mb(self) -> None:
        """1GB > 999MB is True."""
        assert ByteSize.parse("1GB") > ByteSize.parse("999MB")

    def test_equal(self) -> None:
        """1GB == 1_000_000_000 bytes."""
        assert ByteSize.parse("1GB") == ByteSize(1_000_000_000)

    def test_lt(self) -> None:
        """500MB < 1GB is True."""
        assert ByteSize.parse("500MB") < ByteSize.parse("1GB")

    def test_sortable(self) -> None:
        """ByteSize instances are sortable."""
        sizes = [
            ByteSize.parse("1GB"),
            ByteSize.parse("10MB"),
            ByteSize.parse("1TB"),
            ByteSize.parse("500MB"),
        ]
        sorted_sizes = sorted(sizes)
        assert sorted_sizes[0].bytes == 10_000_000
        assert sorted_sizes[-1].bytes == 1_000_000_000_000

    def test_int_conversion(self) -> None:
        """int(ByteSize(1024)) returns 1024."""
        assert int(ByteSize(1024)) == 1024
