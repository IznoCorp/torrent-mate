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
- **No prefetch hint** — the previous ``sequential_hint`` call on a separate
  Python fd was removed (see audit/13-ntfs-cache-pressure.md §Cause-3).
  libmediainfo opens its own fd internally and reads sequentially, which
  receives natural kernel readahead.  The Python-side hint targeted a
  different fd and polluted the UBC without a reliable prefetch benefit.

Usage example::

    wrapper = MediaInfoWrapper(min_size_mb=50, parse_speed=0.5)
    rows = wrapper.extract_streams(Path("/mnt/disk/movie.mkv"))
    for row in rows:
        print(row.kind, row.codec, row.lang)
"""

from __future__ import annotations

import threading
from pathlib import Path

from personalscraper.indexer._container_fastpath import (
    extract_via_enzyme,
    is_fastpath_supported,
    merge_hdr_atmos,
    needs_pymediainfo_fallback,
)
from personalscraper.indexer._throttle import acquire as _acquire_read_tokens
from personalscraper.indexer.schema import MediaStreamRow, StreamKind

# libmediainfo (the C library behind pymediainfo) is not safe under concurrent
# parse() calls — Python segfaults reproducibly when four ThreadPoolExecutor
# workers parse files in parallel. Serialise every MediaInfo.parse() call
# behind this module-level lock. Per-call parse cost dominates I/O, so the
# scan is still I/O-bound; we just lose any (illusory) parse-level
# parallelism the previous code pretended to offer.
_MEDIAINFO_PARSE_LOCK = threading.Lock()

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
# Track-type mapping
# ---------------------------------------------------------------------------

# Map pymediainfo track_type strings to MediaStreamRow.kind values.
# Unmapped types (e.g. "General", "Menu", "Other") are excluded.
_TRACK_TYPE_MAP: dict[str, StreamKind] = {
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
        file_size = path.stat().st_size
        if file_size < self._min_size_bytes:
            return []

        # No explicit prefetch hint: libmediainfo opens its own fd internally
        # and reads sequentially, which receives natural kernel readahead.  The
        # previous mmap+MADV_SEQUENTIAL hint on a separate Python fd polluted
        # the UBC without a reliable prefetch benefit — the two fds don't
        # coordinate, and for Matroska/WebM files the enzyme fastpath reads
        # only the EBML header, so the prefetched pages are never used by
        # libmediainfo at all.  See audit/13-ntfs-cache-pressure.md §Cause-3.

        # Throttle: pymediainfo reads container headers and a tail of stream
        # data — empirically a few MiB even for very large files.  We bound
        # the throttle cost at the file size since we cannot observe the
        # exact byte count read by libmediainfo.  In passthrough mode this
        # is a no-op.
        _acquire_read_tokens(file_size)

        # Container fast path (DESIGN §11.4): for Matroska / WebM files,
        # use the pure-Python enzyme parser to read the EBML header in one
        # pass — codec, language, channels, dimensions, default / forced.
        # Falls back to pymediainfo only when the fast-path output is
        # ambiguous on HDR / Atmos (4 K HEVC/AV1, TrueHD/E-AC-3 + 8ch).
        # Bypasses the parse lock entirely for the common SD/HD case.
        if is_fastpath_supported(path):
            fastpath_rows = extract_via_enzyme(path)
            if fastpath_rows is not None:
                if not needs_pymediainfo_fallback(fastpath_rows):
                    return fastpath_rows
                # HDR/Atmos suspected: parse with pymediainfo and overlay
                # the two flags onto the fast-path result.
                pymediainfo_rows = self._extract_via_pymediainfo(path)
                return merge_hdr_atmos(fastpath_rows, pymediainfo_rows)

        return self._extract_via_pymediainfo(path)

    def _extract_via_pymediainfo(self, path: Path) -> list[MediaStreamRow]:
        """Extract per-stream metadata using libmediainfo (slow path).

        Holds :data:`_MEDIAINFO_PARSE_LOCK` for the entire call.

        Args:
            path: Absolute filesystem path of the media file.

        Returns:
            List of stream rows.
        """
        # The constructor raises ``MediaInfoUnavailableError`` when the
        # library is missing, so any reachable instance method has a real
        # ``MediaInfo`` class bound here. The assert narrows the import-time
        # ``MediaInfo | None`` union for static analysis.
        assert MediaInfo is not None
        # Hold the lock for the **entire** extraction, not just the parse call:
        # libmediainfo (the C library) keeps internal state shared between the
        # ``MediaInfo`` instance and lazily-resolved ``Track`` attributes.
        # Letting another thread call ``parse()`` while we are still iterating
        # ``mi.tracks`` and reading attributes corrupts that shared state and
        # segfaults the interpreter.
        with _MEDIAINFO_PARSE_LOCK:
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
                        hdr_format=_normalise_hdr_format(track) if kind == "video" else None,
                        is_atmos=_detect_atmos(track) if kind == "audio" else None,
                        is_default=_yesno_to_bool(getattr(track, "default", None)),
                        forced=_yesno_to_bool(getattr(track, "forced", None)) if kind == "subtitle" else None,
                        format=_normalise_subtitle_format(track) if kind == "subtitle" else None,
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


def _yesno_to_bool(value: object) -> bool | None:
    """Map pymediainfo's ``"Yes"`` / ``"No"`` (or ``True`` / ``False``) to bool.

    pymediainfo exposes track flags as either ``"Yes"`` / ``"No"`` strings
    (legacy MediaInfo XML) or native booleans depending on the version. We
    accept both and return ``None`` when the attribute is absent so that
    callers can store NULL in the DB rather than fabricate a default.

    Args:
        value: Raw attribute value pulled from a pymediainfo track.

    Returns:
        ``True`` for truthy "Yes" / 1 / True; ``False`` for "No" / 0 /
        False; ``None`` when the value is ``None`` or unrecognised.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"yes", "true", "1"}:
        return True
    if text in {"no", "false", "0"}:
        return False
    return None


def _normalise_hdr_format(track: object) -> str | None:
    """Derive a normalised HDR label from a pymediainfo video track.

    pymediainfo exposes HDR information through several adjacent fields:
    ``hdr_format``, ``hdr_format_compatibility``, ``transfer_characteristics``,
    and ``color_primaries``. We collapse those into one of the four labels
    the rest of the codebase uses: ``"HDR10"``, ``"HDR10+"``, ``"Dolby Vision"``,
    ``"HLG"``. Returns ``None`` for SDR or undetectable cases.

    Args:
        track: Video track from ``pymediainfo.MediaInfo.parse``.

    Returns:
        Normalised HDR label or ``None``.
    """
    raw_hdr = getattr(track, "hdr_format", None) or getattr(track, "hdr_format_commercial", None)
    raw_transfer = getattr(track, "transfer_characteristics", None)

    blob = " ".join(str(v) for v in (raw_hdr, raw_transfer) if v).lower()

    if not blob:
        return None
    if "dolby vision" in blob:
        return "Dolby Vision"
    if "hdr10+" in blob or "hdr10 plus" in blob:
        return "HDR10+"
    if "hdr10" in blob or "smpte st 2084" in blob or "pq" == blob.strip():
        return "HDR10"
    if "hlg" in blob or "arib std-b67" in blob:
        return "HLG"
    if "hdr" in blob:
        return "HDR10"
    return None


def _detect_atmos(track: object) -> bool | None:
    """Detect Dolby Atmos on a pymediainfo audio track.

    Atmos surfaces in pymediainfo via ``commercial_name`` / ``format_commercial``
    (e.g. ``"Dolby Atmos"``, ``"Dolby TrueHD with Dolby Atmos"``) and
    occasionally via ``additionalfeatures`` (``"JOC"`` for E-AC-3+JOC). We
    union those signals.

    Args:
        track: Audio track from ``pymediainfo.MediaInfo.parse``.

    Returns:
        ``True`` when any Atmos signal is found, ``False`` otherwise. Never
        returns ``None`` for an audio track — the negative answer is itself
        information.
    """
    candidates: list[str] = []
    for attr in ("commercial_name", "format_commercial", "format_commercial_if_any", "additionalfeatures"):
        v = getattr(track, attr, None)
        if v:
            candidates.append(str(v).lower())
    blob = " ".join(candidates)
    if not blob:
        return False
    return ("atmos" in blob) or ("joc" in blob)


def _normalise_subtitle_format(track: object) -> str | None:
    """Map a pymediainfo subtitle track's codec / format string to a normalised label.

    Returns one of ``"srt"``, ``"pgs"``, ``"ass"``, ``"dvd_subtitle"``,
    ``"vobsub"``, ``"webvtt"``, or the lower-cased raw string when no
    match is found.

    Args:
        track: Subtitle ("Text") track from pymediainfo.

    Returns:
        Normalised subtitle format string, or ``None`` when no codec / format
        is exposed by the track.
    """
    raw = getattr(track, "codec_id", None) or getattr(track, "format", None)
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    if "subrip" in text or text in {"s_text/utf8", "srt"}:
        return "srt"
    if "pgs" in text or text == "s_hdmv/pgs":
        return "pgs"
    if "ass" in text or "ssa" in text:
        return "ass"
    if "dvd" in text or text == "s_vobsub":
        return "vobsub" if "vobsub" in text else "dvd_subtitle"
    if "webvtt" in text or text == "s_text/webvtt":
        return "webvtt"
    return text


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
