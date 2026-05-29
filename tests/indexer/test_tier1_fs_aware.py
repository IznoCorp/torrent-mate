"""Unit tests for the FS-aware tier-1 fingerprint helpers (Phase 5).

Covers the two pure helpers added to
:mod:`personalscraper.indexer.fingerprint`:

- :func:`round_mtime_ns` — floors an mtime to the capability's granularity
  bucket (identity for granularity 1).
- :func:`normalize_tier1` — capability-aware tier-1 tuple used for live drift
  comparison; byte-identical to the legacy ``(size, mtime_ns, ctime_ns)`` tuple
  for ``ntfs_macfuse`` / APFS / ext4 (granularity 1, ctime kept), but drops
  ctime on exFAT and buckets the mtime on HFS+ / exFAT.

The NTFS-identical invariant is the safety anchor for this phase: the new
branches (ctime drop, mtime bucketing) must *only* fire for exFAT / HFS+.
"""

from __future__ import annotations

import pytest

from personalscraper.indexer._fs_capability import (
    APFS,
    EXFAT,
    EXT4,
    HFSPLUS,
    NTFS_MACFUSE,
)
from personalscraper.indexer.fingerprint import normalize_tier1, round_mtime_ns

pytestmark = pytest.mark.multifs

# A representative epoch nanosecond timestamp (2023-11-14T...) used across cases.
_BASE_NS: int = 1_700_000_000_000_000_000


# ---------------------------------------------------------------------------
# round_mtime_ns
# ---------------------------------------------------------------------------


class TestRoundMtimeNs:
    """Granularity-aware mtime flooring."""

    def test_granularity_one_is_identity_ntfs(self) -> None:
        """NTFS (granularity 1) returns the mtime unchanged."""
        for m in (0, 1, 123, _BASE_NS, _BASE_NS + 999_999_999):
            assert round_mtime_ns(m, NTFS_MACFUSE) == m

    def test_granularity_one_is_identity_apfs_ext4(self) -> None:
        """APFS and ext4 (granularity 1) also return the mtime unchanged."""
        for cap in (APFS, EXT4):
            for m in (0, 7, _BASE_NS + 12_345):
                assert round_mtime_ns(m, cap) == m

    def test_hfsplus_floors_to_one_second(self) -> None:
        """HFS+ (granularity 1e9) floors to the 1-second bucket."""
        # 1.999... s past base floors back to the whole-second base.
        assert round_mtime_ns(_BASE_NS + 999_999_999, HFSPLUS) == _BASE_NS
        # Exactly on a 1-second boundary is unchanged.
        assert round_mtime_ns(_BASE_NS, HFSPLUS) == _BASE_NS
        # 1.000000001 s floors to the 1-second bucket above base.
        assert round_mtime_ns(_BASE_NS + 1_000_000_001, HFSPLUS) == _BASE_NS + 1_000_000_000

    def test_exfat_floors_to_two_seconds(self) -> None:
        """ExFAT (granularity 2e9) floors to the 2-second bucket."""
        # base is on a 2-second boundary (1.7e18 is divisible by 2e9).
        assert round_mtime_ns(_BASE_NS, EXFAT) == _BASE_NS
        # 1.0 s past base still floors back to base (same 2-s bucket).
        assert round_mtime_ns(_BASE_NS + 1_000_000_000, EXFAT) == _BASE_NS
        # 1.999999999 s past base still in the same bucket.
        assert round_mtime_ns(_BASE_NS + 1_999_999_999, EXFAT) == _BASE_NS
        # 2.0 s past base crosses into the next bucket.
        assert round_mtime_ns(_BASE_NS + 2_000_000_000, EXFAT) == _BASE_NS + 2_000_000_000


# ---------------------------------------------------------------------------
# normalize_tier1
# ---------------------------------------------------------------------------


class TestNormalizeTier1NtfsIdentical:
    """The safety anchor: NTFS/APFS/ext4 are byte-identical to the legacy tuple."""

    def test_ntfs_byte_identical(self) -> None:
        """NTFS keeps ctime and does not round mtime → legacy 3-tuple."""
        for s, m, c in (
            (10, 123, 456),
            (0, 0, 0),
            (1_073_741_824, _BASE_NS, _BASE_NS - 5),
            (42, _BASE_NS + 999_999_999, _BASE_NS + 1),
        ):
            assert normalize_tier1(s, m, c, NTFS_MACFUSE) == (s, m, c)

    def test_apfs_identical(self) -> None:
        """APFS (granularity 1, ctime True) matches the legacy tuple."""
        assert normalize_tier1(10, _BASE_NS + 7, 99, APFS) == (10, _BASE_NS + 7, 99)

    def test_ext4_identical(self) -> None:
        """ext4 (granularity 1, ctime True) matches the legacy tuple."""
        assert normalize_tier1(10, _BASE_NS + 7, 99, EXT4) == (10, _BASE_NS + 7, 99)


class TestNormalizeTier1Exfat:
    """exFAT drops ctime and buckets mtime to 2 seconds."""

    def test_drops_ctime_and_buckets_mtime(self) -> None:
        """ExFAT returns a 2-tuple ``(size, mtime_bucket)`` (no ctime)."""
        result = normalize_tier1(10, _BASE_NS + 1, 999, EXFAT)
        assert result == (10, round_mtime_ns(_BASE_NS + 1, EXFAT))
        assert len(result) == 2

    def test_within_two_second_bucket_normalize_equal(self) -> None:
        """Two mtimes within the same 2-second bucket normalize identically."""
        a = normalize_tier1(10, _BASE_NS, 111, EXFAT)
        b = normalize_tier1(10, _BASE_NS + 1_500_000_000, 222, EXFAT)
        assert a == b

    def test_three_seconds_apart_normalize_unequal(self) -> None:
        """Two mtimes 3 seconds apart fall in different buckets → unequal."""
        a = normalize_tier1(10, _BASE_NS, 0, EXFAT)
        b = normalize_tier1(10, _BASE_NS + 3_000_000_000, 0, EXFAT)
        assert a != b


class TestNormalizeTier1Hfsplus:
    """HFS+ keeps ctime but rounds mtime to 1 second."""

    def test_keeps_ctime_three_tuple(self) -> None:
        """HFS+ returns a 3-tuple with ctime preserved."""
        result = normalize_tier1(10, _BASE_NS, 555, HFSPLUS)
        assert len(result) == 3
        assert result == (10, round_mtime_ns(_BASE_NS, HFSPLUS), 555)

    def test_subsecond_jitter_normalize_equal_when_ctime_equal(self) -> None:
        """Sub-second mtime jitter (same ctime) normalizes equal on HFS+."""
        a = normalize_tier1(10, _BASE_NS, 555, HFSPLUS)
        b = normalize_tier1(10, _BASE_NS + 250_000_000, 555, HFSPLUS)
        assert a == b
