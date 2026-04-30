"""Tests for personalscraper.indexer.mediainfo.

Covers:
- ``MediaInfoWrapper.extract_streams`` — size gate (skip below threshold).
- ``MediaInfoWrapper.extract_streams`` — correct shape on mocked parse result.
- ``MediaInfoWrapper.__init__`` — raises ``MediaInfoUnavailableError`` when
  ``_LIBMEDIAINFO_AVAILABLE`` is ``False``.
- ``MediaInfoWrapper.extract_streams`` — General tracks are filtered out.
- ``MediaInfoWrapper.extract_streams`` — ``MediaInfo.parse`` is called for
  files at or above the size threshold.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.indexer.mediainfo import MediaInfoUnavailableError, MediaInfoWrapper
from personalscraper.indexer.schema import MediaStreamRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_track(track_type: str, **kwargs: object) -> SimpleNamespace:
    """Build a minimal fake pymediainfo track namespace.

    Args:
        track_type: The ``track_type`` attribute value (e.g. ``"Video"``).
        **kwargs: Additional attributes to set on the namespace.

    Returns:
        A :class:`types.SimpleNamespace` whose attributes mirror those read
        by :meth:`MediaInfoWrapper.extract_streams`.
    """
    defaults: dict[str, object] = {
        "track_type": track_type,
        "stream_identifier": None,
        "codec_id": None,
        "format": None,
        "language": None,
        "channel_s": None,
        "width": None,
        "height": None,
        "duration": None,
        "bit_rate": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _fake_mediainfo(tracks: list[SimpleNamespace]) -> MagicMock:
    """Return a mock object that looks like a ``MediaInfo`` parse result.

    Args:
        tracks: List of fake track namespaces to attach to the result.

    Returns:
        A :class:`~unittest.mock.MagicMock` with a ``.tracks`` attribute.
    """
    mi = MagicMock()
    mi.tracks = tracks
    return mi


# ---------------------------------------------------------------------------
# Test: size gate — tiny file should return [] without calling parse
# ---------------------------------------------------------------------------


def test_skip_files_below_min_size_mb() -> None:
    """Files below min_size_mb must be skipped; MediaInfo.parse must NOT fire.

    A file smaller than 1 KB is written to a temp dir.  The wrapper is
    configured with ``min_size_mb=10``.  We assert that the returned list is
    empty *and* that ``pymediainfo.MediaInfo.parse`` was never called.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mkv") as fh:
        fh.write(b"tiny")
        tiny_path = Path(fh.name)

    try:
        wrapper = MediaInfoWrapper(min_size_mb=10)
        with patch("personalscraper.indexer.mediainfo.MediaInfo") as mock_mi_cls:
            result = wrapper.extract_streams(tiny_path)

        assert result == [], "Expected empty list for sub-threshold file"
        mock_mi_cls.parse.assert_not_called()
    finally:
        os.unlink(tiny_path)


# ---------------------------------------------------------------------------
# Test: correct shape — 1 video + 1 audio track
# ---------------------------------------------------------------------------


def test_extract_streams_shape() -> None:
    """extract_streams returns one MediaStreamRow per video/audio/text track.

    A fake MediaInfo result with 1 Video + 1 Audio track is injected via
    mock.  We assert that the returned list has exactly 2 MediaStreamRow
    items with the expected ``kind`` values.
    """
    video_track = _make_track("Video", codec_id="avc1", width=1920, height=1080)
    audio_track = _make_track("Audio", codec_id="mp4a", language="fr", channel_s=2)
    fake_mi = _fake_mediainfo([video_track, audio_track])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mkv") as fh:
        # Write enough bytes to exceed the 1 MB threshold used in this test.
        fh.seek(1 * 1024 * 1024)
        fh.write(b"\x00")
        big_path = Path(fh.name)

    try:
        wrapper = MediaInfoWrapper(min_size_mb=1)
        with patch("personalscraper.indexer.mediainfo.MediaInfo") as mock_mi_cls:
            mock_mi_cls.parse.return_value = fake_mi
            result = wrapper.extract_streams(big_path)

        assert len(result) == 2, f"Expected 2 rows, got {len(result)}"
        assert all(isinstance(r, MediaStreamRow) for r in result)
        kinds = [r.kind for r in result]
        assert "video" in kinds, f"Expected 'video' in kinds: {kinds}"
        assert "audio" in kinds, f"Expected 'audio' in kinds: {kinds}"
    finally:
        os.unlink(big_path)


# ---------------------------------------------------------------------------
# Test: MediaInfoUnavailableError raised on init when lib is absent
# ---------------------------------------------------------------------------


def test_mediainfo_unavailable_error_on_init() -> None:
    """MediaInfoWrapper() must raise MediaInfoUnavailableError when lib absent.

    We patch ``_LIBMEDIAINFO_AVAILABLE`` to ``False`` and assert that
    instantiating the wrapper raises the custom exception with the expected
    remediation message.
    """
    with patch("personalscraper.indexer.mediainfo._LIBMEDIAINFO_AVAILABLE", False):
        with pytest.raises(MediaInfoUnavailableError) as exc_info:
            MediaInfoWrapper()

    assert "brew install media-info" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: General track is silently skipped
# ---------------------------------------------------------------------------


def test_general_track_skipped() -> None:
    """General tracks must be excluded from the returned stream list.

    A fake MediaInfo result with 1 General + 1 Video + 1 Audio track is
    injected.  We assert that only 2 rows are returned (General filtered out).
    """
    general_track = _make_track("General")
    video_track = _make_track("Video", codec_id="hevc")
    audio_track = _make_track("Audio", codec_id="ac3")
    fake_mi = _fake_mediainfo([general_track, video_track, audio_track])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mkv") as fh:
        fh.seek(1 * 1024 * 1024)
        fh.write(b"\x00")
        big_path = Path(fh.name)

    try:
        wrapper = MediaInfoWrapper(min_size_mb=1)
        with patch("personalscraper.indexer.mediainfo.MediaInfo") as mock_mi_cls:
            mock_mi_cls.parse.return_value = fake_mi
            result = wrapper.extract_streams(big_path)

        assert len(result) == 2, f"Expected 2 rows (General excluded), got {len(result)}"
        kinds = [r.kind for r in result]
        assert "video" in kinds
        assert "audio" in kinds
    finally:
        os.unlink(big_path)


# ---------------------------------------------------------------------------
# Test: MediaInfo.parse IS called for files at/above the size threshold
# ---------------------------------------------------------------------------


def test_extract_streams_above_threshold_calls_parse() -> None:
    """MediaInfo.parse must be called for files at or above min_size_mb.

    A sparse 60 MB file is created via truncation so that the test runs
    quickly without actually allocating disk space.  We assert that
    ``MediaInfo.parse`` was invoked exactly once.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mkv") as fh:
        # Create a sparse 60 MiB file using seek + single-byte write.
        fh.seek(60 * 1024 * 1024)
        fh.write(b"\x00")
        sparse_path = Path(fh.name)

    try:
        video_track = _make_track("Video", codec_id="h264")
        audio_track = _make_track("Audio", codec_id="aac")
        fake_mi = _fake_mediainfo([video_track, audio_track])

        wrapper = MediaInfoWrapper(min_size_mb=50)
        with patch("personalscraper.indexer.mediainfo.MediaInfo") as mock_mi_cls:
            mock_mi_cls.parse.return_value = fake_mi
            wrapper.extract_streams(sparse_path)

        mock_mi_cls.parse.assert_called_once_with(str(sparse_path), parse_speed=0.5)
    finally:
        os.unlink(sparse_path)
