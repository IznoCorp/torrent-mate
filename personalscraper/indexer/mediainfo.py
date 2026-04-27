"""pymediainfo wrapper for the media indexer.

This module provides :class:`MediaInfoWrapper`, a thin façade over the
``pymediainfo`` library that extracts per-stream metadata from a media file
and returns typed :class:`~personalscraper.indexer.schema.MediaStreamRow`
objects.

Key design decisions
--------------------
- **Deferred availability check** — ``pymediainfo`` is imported at module load
  time inside a try/except.  If ``libmediainfo`` is absent the import raises
  ``OSError``; we catch it, set ``_LIBMEDIAINFO_AVAILABLE = False``, and
  re-raise :class:`MediaInfoUnavailableError` only when
  :class:`MediaInfoWrapper` is *instantiated*.  This prevents a hard import-
  time crash for callers that merely import this module but have a fallback
  path.
- **Size gate** — files below ``min_size_mb`` are silently skipped (return
  ``[]``) to avoid wasting I/O on small sidecar files or subtitles.
- **General track filtering** — pymediainfo always emits one ``General``
  track that carries container-level metadata, not a discrete A/V/subtitle
  stream.  It is intentionally excluded from the returned list.
- **``_sequential_hint``** — a no-op stub reserved for Phase 4
  (``_macos_io.py``), which will advise the OS to read the file sequentially
  before a full mediainfo parse to avoid seek amplification on spinning disks.

Usage example::

    wrapper = MediaInfoWrapper(min_size_mb=50, parse_speed=0.5)
    rows = wrapper.extract_streams(Path("/mnt/disk/movie.mkv"))
    for row in rows:
        print(row.kind, row.codec, row.lang)
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.indexer.schema import MediaStreamRow

# ---------------------------------------------------------------------------
# Availability guard — try to import pymediainfo at module load time
# ---------------------------------------------------------------------------

_LIBMEDIAINFO_AVAILABLE: bool
_libmediainfo_exc: OSError | None = None

try:
    from pymediainfo import MediaInfo

    _LIBMEDIAINFO_AVAILABLE = True
except OSError as _exc:
    # libmediainfo shared library is not present on this system.
    _LIBMEDIAINFO_AVAILABLE = False
    _libmediainfo_exc = _exc
    # Provide a dummy name so type-checkers that analyse this branch don't
    # complain about 'MediaInfo' being undefined further down.
    MediaInfo = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class MediaInfoUnavailableError(RuntimeError):
    """Raised when libmediainfo is not installed on the host system.

    This exception is raised at :class:`MediaInfoWrapper` instantiation time
    (not at module import time) so that callers that import the module but
    always take a fallback path are not penalised.

    Args:
        message: Human-readable explanation with a remediation hint.
    """

    def __init__(self, message: str) -> None:
        """Initialise with a descriptive message."""
        super().__init__(message)


# ---------------------------------------------------------------------------
# Private I/O hint stub (Phase 4 placeholder)
# ---------------------------------------------------------------------------


def _sequential_hint(path: Path) -> None:  # noqa: ARG001
    """Advise the OS to read *path* sequentially (no-op stub).

    This function will be implemented in Phase 4 (``_macos_io.py``) using
    ``fcntl.F_RDADVISE`` / ``posix_fadvise`` to pre-fetch bytes before the
    full mediainfo parse, reducing seek amplification on spinning disks.

    Args:
        path: The media file that is about to be parsed.
    """
    # Phase 4 implementation goes here.


# ---------------------------------------------------------------------------
# Track-type mapping
# ---------------------------------------------------------------------------

# Map pymediainfo track_type strings to MediaStreamRow.kind values.
# Unmapped types (e.g. "General", "Menu", "Other") are excluded.
_TRACK_TYPE_MAP: dict[str, str] = {
    "Video": "video",
    "Audio": "audio",
    "Text": "subtitle",
}


# ---------------------------------------------------------------------------
# MediaInfoWrapper
# ---------------------------------------------------------------------------


class MediaInfoWrapper:
    """Thin façade over pymediainfo for extracting per-stream metadata.

    Only files at or above ``min_size_mb`` are parsed; smaller files return
    an empty list immediately without calling ``MediaInfo.parse``.

    Args:
        min_size_mb: Minimum file size in megabytes required before parsing.
            Files below this threshold return an empty stream list.
        parse_speed: Value in ``[0.0, 1.0]`` passed to ``MediaInfo.parse``
            as ``parse_speed``.  Lower values skip optional tags and run
            faster; 1.0 performs a full sequential parse.

    Raises:
        MediaInfoUnavailableError: If ``libmediainfo`` was not found when this
            module was imported.
    """

    def __init__(self, *, min_size_mb: int = 50, parse_speed: float = 0.5) -> None:
        """Initialise the wrapper, raising immediately if libmediainfo is absent."""
        if not _LIBMEDIAINFO_AVAILABLE:
            raise MediaInfoUnavailableError("libmediainfo not found — brew install media-info") from _libmediainfo_exc

        self._min_size_bytes: int = min_size_mb * 1024 * 1024
        self._parse_speed: float = parse_speed

    def extract_streams(self, path: Path) -> list[MediaStreamRow]:
        """Extract per-stream metadata from a media file.

        Files below the size threshold are silently skipped.  The ``General``
        track emitted by pymediainfo is filtered out; only ``Video``,
        ``Audio``, and ``Text`` tracks produce rows.

        Args:
            path: Absolute (or relative) path to the media file.

        Returns:
            A list of :class:`~personalscraper.indexer.schema.MediaStreamRow`
            instances — one per discrete stream — or ``[]`` if the file is
            below the size threshold or contains no mappable tracks.
        """
        # Size gate: avoid parsing small sidecar files.
        if path.stat().st_size < self._min_size_bytes:
            return []

        # Advise the OS about the upcoming sequential read (Phase 4 stub).
        _sequential_hint(path)

        mi = MediaInfo.parse(str(path), parse_speed=self._parse_speed)

        rows: list[MediaStreamRow] = []
        video_idx = audio_idx = subtitle_idx = 0  # per-kind stream counters

        for track in mi.tracks:
            kind = _TRACK_TYPE_MAP.get(track.track_type)
            if kind is None:
                # Skip General, Menu, Other, and any future unknown types.
                continue

            # Assign a 0-based index within the file using the track's own
            # stream_identifier when available, falling back to a counter.
            if track.stream_identifier is not None:
                idx = int(track.stream_identifier)
            else:
                # Compute per-kind counter as a fallback.
                if kind == "video":
                    idx = video_idx
                    video_idx += 1
                elif kind == "audio":
                    idx = audio_idx
                    audio_idx += 1
                else:
                    idx = subtitle_idx
                    subtitle_idx += 1

            rows.append(
                MediaStreamRow(
                    # id=0 and file_id=0 are placeholder values; the repository
                    # layer assigns real PKs on INSERT.
                    id=0,
                    file_id=0,
                    idx=idx,
                    kind=kind,
                    codec=_str_or_none(track.codec_id or track.format),
                    lang=_str_or_none(getattr(track, "language", None)),
                    channels=_int_or_none(getattr(track, "channel_s", None)),
                    width=_int_or_none(getattr(track, "width", None)),
                    height=_int_or_none(getattr(track, "height", None)),
                    duration_ms=_int_or_none(getattr(track, "duration", None)),
                    bitrate=_int_or_none(getattr(track, "bit_rate", None)),
                )
            )

        return rows


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _str_or_none(value: object) -> str | None:
    """Return *value* cast to ``str``, or ``None`` if falsy.

    Args:
        value: Any value returned by a pymediainfo track attribute.

    Returns:
        ``str(value)`` when *value* is truthy, else ``None``.
    """
    return str(value) if value else None


def _int_or_none(value: object) -> int | None:
    """Return *value* cast to ``int``, or ``None`` if conversion fails.

    pymediainfo sometimes returns numeric values as strings or floats
    (e.g. ``"48000"`` for sample rate).  This helper normalises them.

    Args:
        value: Any value returned by a pymediainfo track attribute.

    Returns:
        ``int(value)`` on success, ``None`` if *value* is ``None`` or
        raises ``(TypeError, ValueError)`` on conversion.
    """
    if value is None:
        return None
    try:
        # Cast through str to satisfy mypy's int() overload constraints;
        # pymediainfo may return int, float, or str for numeric attributes.
        return int(str(value))
    except (TypeError, ValueError):
        return None
