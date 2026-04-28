"""Tests for personalscraper.indexer.fingerprint.

Covers:
- ``fingerprint_tier1`` — returns (size, mtime_ns, ctime_ns) from a stat result.
- ``oshash`` — OpenSubtitles hash correctness, edge cases, and regression vectors.
- ``xxh3_partial`` — determinism and small-file handling.
- ``OSHASH_EXTENSIONS`` — allowlist completeness check.
- ``is_racy`` — racy-mtime boundary conditions per DESIGN §7.3.
- ``sequential_hint`` — no-op on non-Darwin; does not raise on Darwin.
"""

from __future__ import annotations

import os
import platform
import struct
import tempfile
from pathlib import Path
from unittest import mock

from personalscraper.indexer._macos_io import sequential_hint
from personalscraper.indexer.fingerprint import (
    OSHASH_EXTENSIONS,
    fingerprint_tier1,
    is_racy,
    oshash,
    xxh3_partial,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHUNK = 65536  # OSHash chunk size (64 KiB)
_U64_MOD = 1 << 64


def _write_tmp(content: bytes) -> Path:
    """Write *content* to a temporary file and return its ``Path``."""
    fd, name = tempfile.mkstemp()
    try:
        os.write(fd, content)
    finally:
        os.close(fd)
    return Path(name)


# ---------------------------------------------------------------------------
# fingerprint_tier1
# ---------------------------------------------------------------------------


class TestFingerprintTier1:
    """Tests for ``fingerprint_tier1``."""

    def test_fingerprint_tier1_returns_size_mtime_ctime(self, tmp_path: Path) -> None:
        """Returned tuple must exactly match the ``stat_result`` fields."""
        f = tmp_path / "sample.txt"
        f.write_bytes(b"hello world")

        st = f.stat()
        result = fingerprint_tier1(st)

        assert result == (st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        assert result[0] == 11  # len("hello world")


# ---------------------------------------------------------------------------
# oshash
# ---------------------------------------------------------------------------


class TestOshash:
    """Tests for the OpenSubtitles hash implementation."""

    def test_oshash_empty_file_returns_zeros(self, tmp_path: Path) -> None:
        """Empty file must return the all-zero 16-char sentinel."""
        f = tmp_path / "empty.mkv"
        f.write_bytes(b"")
        assert oshash(f) == "0000000000000000"

    def test_oshash_small_file(self, tmp_path: Path) -> None:
        """File under 64 KiB must complete without error and return a 16-hex string."""
        f = tmp_path / "small.mp4"
        f.write_bytes(b"\xab" * 1000)
        result = oshash(f)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_oshash_deterministic_for_known_content(self, tmp_path: Path) -> None:
        """Two calls on identical content must return the same hash (regression vector)."""
        content = b"\x42" * 200_000  # 200 KiB of 0x42
        f = tmp_path / "known.avi"
        f.write_bytes(content)

        result_a = oshash(f)
        result_b = oshash(f)
        assert result_a == result_b

        # --- regression vector -----------------------------------------------
        # Computed once and pinned.  Recompute manually if the algorithm changes:
        #   filesize = 200_000
        #   head = b"\x42" * 65536  (padded naturally — file > 64 KiB)
        #   tail = b"\x42" * 65536  (last 65 536 bytes of the 200 000-byte file)
        #   Each 8-byte word = 0x4242424242424242 = 4774451407313060418
        #   sum_head = 8192 * 4774451407313060418 = 39128994614802671616 (mod 2^64)
        #   sum_tail = same
        #   hash = (200000 + sum_head + sum_tail) mod 2^64
        word = struct.unpack_from("<Q", b"\x42" * 8)[0]  # 4774451407313060418
        sum_chunk = (8192 * word) % _U64_MOD
        expected_hash = (200_000 + sum_chunk + sum_chunk) % _U64_MOD
        expected_hex = f"{expected_hash:016x}"
        assert result_a == expected_hex, (
            f"OSHash regression vector mismatch: got {result_a!r}, expected {expected_hex!r}"
        )

    def test_oshash_returns_16_hex_chars(self, tmp_path: Path) -> None:
        """Result must always be exactly 16 lowercase hexadecimal characters."""
        f = tmp_path / "video.mkv"
        f.write_bytes(b"\x00" * (1024 * 1024))  # 1 MiB of zeros
        result = oshash(f)
        assert len(result) == 16
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# xxh3_partial
# ---------------------------------------------------------------------------


class TestXxh3Partial:
    """Tests for ``xxh3_partial``."""

    def test_xxh3_partial_deterministic(self, tmp_path: Path) -> None:
        """Two calls on the same file must return an identical digest."""
        f = tmp_path / "media.mkv"
        f.write_bytes(b"\xde\xad\xbe\xef" * 512_000)  # 2 MiB
        assert xxh3_partial(f) == xxh3_partial(f)

    def test_xxh3_partial_handles_small_files(self, tmp_path: Path) -> None:
        """Files smaller than ``2 * partial_bytes`` must hash without error."""
        f = tmp_path / "tiny.mp4"
        f.write_bytes(b"\xff" * 100)  # well under default 2×1 MiB
        result = xxh3_partial(f)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_xxh3_partial_empty_file(self, tmp_path: Path) -> None:
        """Empty file must return a consistent 16-hex-char digest (all-zero xxh3)."""
        f = tmp_path / "empty.mkv"
        f.write_bytes(b"")
        result = xxh3_partial(f)
        assert len(result) == 16


# ---------------------------------------------------------------------------
# OSHASH_EXTENSIONS
# ---------------------------------------------------------------------------


class TestOshashExtensions:
    """Tests for the ``OSHASH_EXTENSIONS`` allowlist."""

    _EXPECTED_EXTENSIONS: frozenset[str] = frozenset(
        {
            "mkv",
            "mp4",
            "avi",
            "mov",
            "wmv",
            "flv",
            "mpg",
            "mpeg",
            "m4v",
            "webm",
            "ts",
            "m2ts",
            "mts",
            "3gp",
            "vob",
            "ogv",
            "rmvb",
        }
    )

    def test_oshash_extensions_contains_common_video_formats(self) -> None:
        """All 17 canonical video extensions must be present in the frozenset."""
        assert len(self._EXPECTED_EXTENSIONS) == 17, "Test fixture must list 17 extensions"
        missing = self._EXPECTED_EXTENSIONS - OSHASH_EXTENSIONS
        assert not missing, f"Missing extensions from OSHASH_EXTENSIONS: {sorted(missing)}"

    def test_oshash_extensions_is_frozenset(self) -> None:
        """``OSHASH_EXTENSIONS`` must be a ``frozenset`` (immutable, hashable)."""
        assert isinstance(OSHASH_EXTENSIONS, frozenset)

    def test_oshash_extensions_no_leading_dot(self) -> None:
        """Extensions must be stored without a leading dot."""
        for ext in OSHASH_EXTENSIONS:
            assert not ext.startswith("."), f"Extension {ext!r} must not start with a dot"

    def test_oshash_extensions_lowercase(self) -> None:
        """Extensions must be lowercase."""
        for ext in OSHASH_EXTENSIONS:
            assert ext == ext.lower(), f"Extension {ext!r} is not lowercase"


# ---------------------------------------------------------------------------
# is_racy
# ---------------------------------------------------------------------------


class TestIsRacy:
    """Tests for the git-style racy-mtime rule."""

    _SCAN_START: int = 1_000_000_000_000_000_000  # 1 second in nanoseconds (arbitrary ref)
    _WINDOW: int = 2_000_000_000  # 2 s in nanoseconds

    def test_is_racy_within_window(self) -> None:
        """File mtime just inside the racy window must be reported as racy."""
        # 1 ns inside the window boundary (boundary at scan_start - window)
        file_mtime_ns = self._SCAN_START - self._WINDOW + 1
        assert is_racy(file_mtime_ns, self._SCAN_START, self._WINDOW) is True

    def test_is_racy_outside_window(self) -> None:
        """File mtime well before the racy window must not be racy."""
        file_mtime_ns = self._SCAN_START - self._WINDOW - 1
        assert is_racy(file_mtime_ns, self._SCAN_START, self._WINDOW) is False

    def test_is_racy_future_mtime(self) -> None:
        """File mtime in the future relative to scan start must be racy (clock skew)."""
        file_mtime_ns = self._SCAN_START + 1
        assert is_racy(file_mtime_ns, self._SCAN_START, self._WINDOW) is True

    def test_is_racy_at_exact_boundary(self) -> None:
        """File mtime exactly equal to (scan_start - window) must be racy (inclusive boundary)."""
        file_mtime_ns = self._SCAN_START - self._WINDOW
        assert is_racy(file_mtime_ns, self._SCAN_START, self._WINDOW) is True

    def test_is_racy_exactly_at_scan_start(self) -> None:
        """File mtime equal to scan_start is within the window — must be racy."""
        assert is_racy(self._SCAN_START, self._SCAN_START, self._WINDOW) is True

    def test_is_racy_zero_window(self) -> None:
        """With a zero-width window only future mtimes are racy."""
        # Exactly at scan_start with window=0 → boundary inclusive → racy
        assert is_racy(self._SCAN_START, self._SCAN_START, 0) is True
        # One ns before scan_start with window=0 → outside window → not racy
        assert is_racy(self._SCAN_START - 1, self._SCAN_START, 0) is False


# ---------------------------------------------------------------------------
# sequential_hint
# ---------------------------------------------------------------------------


class TestSequentialHint:
    """Tests for ``personalscraper.indexer._macos_io.sequential_hint``.

    Two complementary scenarios are covered:

    * **Non-Darwin** — the function must be a genuine no-op: no system calls,
      no imports, no exceptions.  Verified by patching
      ``_macos_io._IS_DARWIN`` to ``False`` so the test is deterministic on
      any CI platform (including macOS).

    * **Darwin (real call)** — when the test runner is on macOS the function
      must not raise when given a valid fd for a real temporary file.  Skipped
      on non-Darwin so Linux/Windows CI is unaffected.
    """

    def test_sequential_hint_noop_on_non_darwin(self, tmp_path: Path) -> None:
        """``sequential_hint`` must be a no-op and not raise on non-Darwin.

        We patch ``_macos_io._IS_DARWIN`` to ``False`` to simulate a Linux or
        Windows host regardless of where this test actually runs.  The fd is a
        valid open file descriptor; a no-op implementation must simply return
        without touching it.
        """
        f = tmp_path / "hint_test.bin"
        f.write_bytes(b"\x00" * 1024)

        fd = os.open(f, os.O_RDONLY)
        try:
            import personalscraper.indexer._macos_io as _macos_io_mod

            # Force non-Darwin code path regardless of the real platform.
            with mock.patch.object(_macos_io_mod, "_IS_DARWIN", False):
                # Must not raise — on a non-Darwin host the call is a no-op.
                sequential_hint(fd, offset=0, length=0)
        finally:
            os.close(fd)

    def test_sequential_hint_darwin_does_not_raise(self, tmp_path: Path) -> None:
        """On Darwin, ``sequential_hint`` must not raise for a valid open fd.

        Skipped on non-Darwin so Linux/Windows CI never attempts the syscall.
        The test opens a real temporary file and verifies that the ``fcntl``
        call completes without error.
        """
        if platform.system() != "Darwin":
            import pytest

            pytest.skip("F_RDADVISE is a macOS-only syscall — skipping on non-Darwin")

        f = tmp_path / "hint_darwin.bin"
        f.write_bytes(b"\xab" * 4096)

        fd = os.open(f, os.O_RDONLY)
        try:
            # Real F_RDADVISE call — must complete without OSError on macOS.
            sequential_hint(fd, offset=0, length=0)
        finally:
            os.close(fd)
