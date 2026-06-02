"""Tests for TorrentAdder / TorrentLimiter Protocols and UnsupportedCapabilityError."""

from __future__ import annotations

import personalscraper.api.torrent._contracts as cm
import personalscraper.api.torrent._errors as em


def test_adder_in_all() -> None:
    """TorrentAdder is exported in _contracts.__all__."""
    assert "TorrentAdder" in cm.__all__


def test_limiter_in_all() -> None:
    """TorrentLimiter is exported in _contracts.__all__."""
    assert "TorrentLimiter" in cm.__all__


def test_adder_runtime_checkable() -> None:
    """TorrentAdder is a runtime_checkable Protocol."""
    from typing import Protocol

    from personalscraper.api.torrent._contracts import TorrentAdder

    assert issubclass(TorrentAdder, Protocol)  # type: ignore[arg-type]


def test_limiter_runtime_checkable() -> None:
    """TorrentLimiter is a runtime_checkable Protocol."""
    from typing import Protocol

    from personalscraper.api.torrent._contracts import TorrentLimiter

    assert issubclass(TorrentLimiter, Protocol)  # type: ignore[arg-type]


def test_unsupported_error_importable() -> None:
    """UnsupportedCapabilityError is importable and is an Exception subclass."""
    from personalscraper.api.torrent._errors import UnsupportedCapabilityError

    assert issubclass(UnsupportedCapabilityError, Exception)


def test_unsupported_error_in_all() -> None:
    """UnsupportedCapabilityError is exported in _errors.__all__."""
    assert "UnsupportedCapabilityError" in em.__all__


def test_adder_has_add_method() -> None:
    """TorrentAdder Protocol declares an add method."""
    from personalscraper.api.torrent._contracts import TorrentAdder

    assert hasattr(TorrentAdder, "add")


def test_limiter_has_apply_limits_method() -> None:
    """TorrentLimiter Protocol declares an apply_limits method."""
    from personalscraper.api.torrent._contracts import TorrentLimiter

    assert hasattr(TorrentLimiter, "apply_limits")
