"""Container-level fast paths for stream extraction (DESIGN §11.4).

The enrich pass parses every video file with ``pymediainfo``, which reads
several MB of container header per file (~500 ms-1 s). For containers
where a pure-Python parser exists, we can extract the same per-stream
metadata from the first ~64 KB-1 MB of the file, an order of magnitude
faster.

Currently supported:

- **Matroska / WebM** (``.mkv`` / ``.webm``) via the :mod:`enzyme` library.
  Reads codec, language, channels, dimensions, and the default / forced
  flags from the EBML header.

Deliberately not supported:

- **MP4 / AVI / MOV / TS**: the popular pure-Python options
  (``mutagen.MP4``, ``av``, ``pymp4``) either expose only audio metadata
  or pull in heavy native dependencies that defeat the speed advantage.
  These containers fall back to the existing pymediainfo path.

HDR detection and Atmos detection are *not* exposed by enzyme: HDR
metadata lives in elementary-stream-level color descriptors that the
EBML container does not expose, and Atmos / TrueHD-Atmos identification
requires parsing audio sub-streams that enzyme does not decode. The
fast path therefore returns rows with ``hdr_format=None`` and
``is_atmos=None`` for codecs / resolutions where these flags could
*plausibly* be present (4 K HEVC / AV1, TrueHD / E-AC-3 + 8 channels);
``MediaInfoWrapper.extract_streams`` then falls back to pymediainfo for
those cases. SD content and stereo / 5.1 audio are returned outright,
which covers the majority of a typical library.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.indexer.schema import MediaStreamRow
from personalscraper.logger import get_logger

log = get_logger("indexer.fastpath")

try:
    from enzyme import MKV

    _ENZYME_AVAILABLE = True
except ImportError:  # pragma: no cover — runtime guard
    MKV = None
    _ENZYME_AVAILABLE = False


# Codec-family heuristics for deciding when fast-path output is sufficient
# vs. when we must fall back to pymediainfo for HDR / Atmos detection.
# All codec_id strings here are the EBML codec identifiers enzyme reports.

# Video codecs that *can* carry HDR; combined with a 4K-or-higher
# resolution they trigger a pymediainfo fallback so the HDR variant is
# detected. Lower-resolution HEVC/AV1 keeps the fast-path result.
_HDR_CAPABLE_VIDEO_CODECS = frozenset(
    {
        "V_MPEGH/ISO/HEVC",  # HEVC / H.265
        "V_AV1",  # AOMedia AV1
    }
)

# Audio codecs that *can* be Atmos-encoded; combined with a high channel
# count (>= 8 — Dolby Atmos uses 7.1.4 = 12 channels but stores 8 base
# channels in the bed) we fall back to pymediainfo for the Atmos flag.
_ATMOS_CAPABLE_AUDIO_CODECS = frozenset(
    {
        "A_TRUEHD",  # Dolby TrueHD (Atmos rider)
        "A_EAC3",  # Dolby E-AC-3 (Atmos via JOC)
        "A_AC3+",  # Older alias for E-AC-3
    }
)

_HDR_RESOLUTION_THRESHOLD = 2160  # 4 K and above
_ATMOS_CHANNEL_THRESHOLD = 8


def is_fastpath_supported(path: Path) -> bool:
    """Return ``True`` when *path* has a container the fast path can read.

    Args:
        path: Filesystem path of the file under consideration.

    Returns:
        ``True`` for ``.mkv`` and ``.webm``; ``False`` otherwise. Always
        ``False`` if enzyme is not installed.
    """
    if not _ENZYME_AVAILABLE:
        return False
    return path.suffix.lower() in {".mkv", ".webm"}


def needs_pymediainfo_fallback(rows: list[MediaStreamRow]) -> bool:
    """Decide whether the fast-path result needs a pymediainfo confirmation.

    Returns ``True`` when at least one stream is *plausibly* HDR or Atmos
    based on its codec + dimensions / channel count — pymediainfo is
    invoked then to populate ``hdr_format`` / ``is_atmos``. Returns
    ``False`` when no stream looks like a candidate, in which case the
    fast-path output is taken as-is and ``hdr_format`` / ``is_atmos``
    remain ``None`` (correctly representing "not HDR" / "not Atmos").

    Args:
        rows: Stream rows returned by :func:`extract_via_enzyme`.

    Returns:
        ``True`` when a pymediainfo fallback is required.
    """
    for row in rows:
        if row.kind == "video":
            if row.codec in _HDR_CAPABLE_VIDEO_CODECS and (row.height or 0) >= _HDR_RESOLUTION_THRESHOLD:
                return True
        elif (
            row.kind == "audio"
            and row.codec in _ATMOS_CAPABLE_AUDIO_CODECS
            and (row.channels or 0) >= _ATMOS_CHANNEL_THRESHOLD
        ):
            return True
    return False


def extract_via_enzyme(path: Path) -> list[MediaStreamRow] | None:
    """Extract per-stream metadata from a Matroska / WebM container.

    Reads only the EBML header (typically 64 KB-1 MB), so it returns
    ~10× faster than ``pymediainfo.MediaInfo.parse`` on the same file.

    The returned rows carry codec / language / channels / dimensions /
    duration / default / forced; ``hdr_format`` / ``is_atmos`` are
    intentionally left ``None`` because enzyme does not expose them
    (call :func:`needs_pymediainfo_fallback` to decide whether to
    follow up with pymediainfo).

    Returns ``None`` when enzyme is not installed, the file is not a
    Matroska container, or the parse failed for any reason — the
    caller should then fall back to the pymediainfo path.

    Args:
        path: Absolute filesystem path of the media file.

    Returns:
        List of :class:`~personalscraper.indexer.schema.MediaStreamRow`
        instances, or ``None`` on unsupported / failed inputs.
    """
    if not _ENZYME_AVAILABLE:
        return None
    if not is_fastpath_supported(path):
        return None

    try:
        with path.open("rb") as fh:
            mkv = MKV(fh)
    except Exception as exc:  # noqa: BLE001 — enzyme raises a wide range of parse errors
        log.debug("indexer.fastpath.enzyme_failed", path=str(path), error=str(exc), error_type=type(exc).__name__)
        return None

    duration_ms: int | None = None
    if mkv.info is not None and mkv.info.duration is not None:
        duration_ms = int(mkv.info.duration.total_seconds() * 1000)

    rows: list[MediaStreamRow] = []
    video_idx = audio_idx = subtitle_idx = 0

    for track in mkv.video_tracks or []:
        rows.append(
            MediaStreamRow(
                id=0,
                file_id=0,
                idx=video_idx,
                kind="video",
                codec=track.codec_id,
                lang=getattr(track, "language", None),
                channels=None,
                width=getattr(track, "width", None),
                height=getattr(track, "height", None),
                duration_ms=duration_ms,
                bitrate=None,
                hdr_format=None,
                is_atmos=None,
                is_default=bool(getattr(track, "default", False)),
                forced=None,
                format=None,
            )
        )
        video_idx += 1

    for track in mkv.audio_tracks or []:
        rows.append(
            MediaStreamRow(
                id=0,
                file_id=0,
                idx=audio_idx,
                kind="audio",
                codec=track.codec_id,
                lang=getattr(track, "language", None),
                channels=getattr(track, "channels", None),
                width=None,
                height=None,
                duration_ms=duration_ms,
                bitrate=None,
                hdr_format=None,
                is_atmos=None,
                is_default=bool(getattr(track, "default", False)),
                forced=None,
                format=None,
            )
        )
        audio_idx += 1

    for track in mkv.subtitle_tracks or []:
        rows.append(
            MediaStreamRow(
                id=0,
                file_id=0,
                idx=subtitle_idx,
                kind="subtitle",
                codec=track.codec_id,
                lang=getattr(track, "language", None),
                channels=None,
                width=None,
                height=None,
                duration_ms=None,
                bitrate=None,
                hdr_format=None,
                is_atmos=None,
                is_default=bool(getattr(track, "default", False)),
                forced=bool(getattr(track, "forced", False)),
                format=_normalise_subtitle_codec(track.codec_id),
            )
        )
        subtitle_idx += 1

    return rows


def merge_hdr_atmos(
    fastpath_rows: list[MediaStreamRow],
    pymediainfo_rows: list[MediaStreamRow],
) -> list[MediaStreamRow]:
    """Overlay pymediainfo's HDR / Atmos values onto the fast-path rows.

    The fast path produces the canonical row set (correct ordering, all
    common fields). pymediainfo only contributes the two flags enzyme
    cannot expose. Match by ``(kind, idx)``; rows present in only one
    source are kept as-is.

    Args:
        fastpath_rows: Rows from :func:`extract_via_enzyme`.
        pymediainfo_rows: Rows from
            :meth:`personalscraper.indexer.mediainfo.MediaInfoWrapper.extract_streams`.

    Returns:
        Merged row list.
    """
    by_key = {(r.kind, r.idx): r for r in pymediainfo_rows}
    merged: list[MediaStreamRow] = []
    for row in fastpath_rows:
        rich = by_key.get((row.kind, row.idx))
        if rich is None:
            merged.append(row)
            continue
        merged.append(
            MediaStreamRow(
                id=row.id,
                file_id=row.file_id,
                idx=row.idx,
                kind=row.kind,
                codec=row.codec or rich.codec,
                lang=row.lang or rich.lang,
                channels=row.channels if row.channels is not None else rich.channels,
                width=row.width if row.width is not None else rich.width,
                height=row.height if row.height is not None else rich.height,
                duration_ms=row.duration_ms if row.duration_ms is not None else rich.duration_ms,
                bitrate=row.bitrate if row.bitrate is not None else rich.bitrate,
                hdr_format=rich.hdr_format,
                is_atmos=rich.is_atmos,
                is_default=row.is_default if row.is_default is not None else rich.is_default,
                forced=row.forced if row.forced is not None else rich.forced,
                format=row.format if row.format is not None else rich.format,
            )
        )
    return merged


_SUBTITLE_CODEC_MAP = {
    "S_TEXT/UTF8": "srt",
    "S_TEXT/ASCII": "srt",
    "S_HDMV/PGS": "pgs",
    "S_TEXT/ASS": "ass",
    "S_TEXT/SSA": "ass",
    "S_VOBSUB": "vobsub",
    "S_DVBSUB": "dvb_subtitle",
    "S_TEXT/WEBVTT": "webvtt",
}


def _normalise_subtitle_codec(codec_id: str | None) -> str | None:
    """Map an EBML subtitle codec_id to the canonical short label.

    Falls back to the lowercased raw id when no mapping is defined so
    callers can still distinguish unknown formats.

    Args:
        codec_id: EBML codec identifier (e.g. ``"S_HDMV/PGS"``).

    Returns:
        Normalised label, or ``None`` when *codec_id* is ``None``.
    """
    if codec_id is None:
        return None
    return _SUBTITLE_CODEC_MAP.get(codec_id, codec_id.lower())
