"""Tracker family base — TrackerClient Protocol and TrackerResult model.

Implements DESIGN §6.1: TrackerClient Protocol and TrackerResult dataclass.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from personalscraper.api._contracts import ApiError
from personalscraper.api._units import ByteSize

T = TypeVar("T")

# Exceptions that indicate operational schema-drift in a tracker payload
# (vs a programming error in the surrounding code). Centralised here so
# tracker implementations can reuse ``wrap_parser_drift`` without each
# duplicating the tuple — drift in one would otherwise diverge from the
# others.
_DRIFT_EXCEPTIONS = (KeyError, IndexError, TypeError, AttributeError, ValueError)


def wrap_parser_drift(provider: str, parse: Callable[[], T]) -> T:
    """Run ``parse()`` and re-raise schema-drift errors as ``ApiError``.

    Trackers receive untyped data (XML / JSON) and parse it into
    ``TrackerResult``. A field rename or shape change in the upstream
    payload would otherwise raise ``KeyError`` / ``IndexError`` /
    ``TypeError`` / ``AttributeError`` / ``ValueError`` — bare programming
    exceptions that the registry's narrowed ``except`` correctly does NOT
    swallow. Wrap parse code with this helper so drift surfaces as an
    operational ``ApiError`` (the registry logs it and the surviving
    trackers' results are still ranked).

    Args:
        provider: Provider identifier embedded in the resulting ``ApiError``.
        parse: Zero-arg callable that produces the parsed payload.

    Returns:
        The value returned by ``parse()``.

    Raises:
        ApiError: ``parse()`` raised one of the schema-drift exceptions.
        Exception: Any other exception is left to propagate (programming bug).
    """
    try:
        return parse()
    except _DRIFT_EXCEPTIONS as exc:
        raise ApiError(
            provider=provider,
            http_status=0,
            message=f"{provider} response shape drift while parsing search response: {exc!r}",
        ) from exc


@dataclass
class TrackerResult:
    """A single search result from a tracker.

    Attributes:
        provider: Tracker provider name as the lowercase wire value
            (e.g. "c411", "tr4ker"). This is the key used to look up the
            matching transport in ``resolve_source``'s ``transports`` map.
        tracker_id: Provider-specific identifier for this torrent.
        title: Human-readable torrent title.
        size: Torrent size as a typed ByteSize.
        seeders: Number of seeders.
        leechers: Number of leechers.
        category: Tracker-specific category name, if any.
        download_url: Direct download URL, if available.
        info_hash: Torrent info hash, if available.
        source_url: URL of the torrent detail page.
        is_freeleech: Whether this torrent is freeleech.
        is_silverleech: Whether this torrent is partial freeleech.
        upload_date: Upload timestamp, if known.
        format: Container format (MKV, MP4, AVI...).
        codec: Video codec (x265, HEVC, x264...).
        source: Media source (BluRay, WEB-DL, WEBRip...).
        resolution: Video resolution (2160p, 1080p, 720p...).
        audio: Audio codec info (DTS, AAC, TrueHD, AC3, ...).
            NOTE: this field is codec-only — it never contains language
            markers (VF/VOSTFR/VO). Those live in ``language`` (below).
        language: Language / audio-track marker parsed from the title, as an
            UPPERCASE canonical token: ``MULTI`` (several audio tracks), the
            French VF variants (``VFF`` / ``VFQ`` / ``VFI`` / ``VOF`` /
            ``TRUEFRENCH`` / ``FRENCH``), or the VO variants (``VOSTFR`` /
            ``SUBFRENCH`` / ``VO``). ``None`` when the title carries no marker.
            A SEPARATE axis from ``audio`` (the codec): a ranking criterion can
            score ``field: "language"`` to prefer ``MULTI`` releases — a
            preference the codec-only ``audio`` field could never serve.
        tmdb_id: TMDB id when the tracker exposes it, else None. The generic
            Torznab client maps the ``tmdbid`` attr (2026-07-28), so c411 and
            tr4ker both populate this whenever their indexer publishes it —
            which restores the TMDB identity hard-filter (the anti-remake
            guard) that lost its only producer when a legacy tracker was
            decommissioned. A
            missing or non-numeric attr yields ``None``. The filter engages
            ONLY when the result AND the wanted item's ``media_ref`` both
            carry a TMDB id; either side ``None`` makes it a no-op, so an
            un-tagged release is never dropped for lack of an id.
    """

    provider: str
    tracker_id: str
    title: str
    size: ByteSize
    seeders: int
    leechers: int
    category: str | None = None
    download_url: str | None = None
    info_hash: str | None = None
    source_url: str | None = None
    is_freeleech: bool = False
    is_silverleech: bool = False
    upload_date: datetime | None = None
    format: str | None = None
    codec: str | None = None
    source: str | None = None
    resolution: str | None = None
    audio: str | None = None
    language: str | None = None
    tmdb_id: int | None = None


# NOTE — provider-ids feature, sub-phase 11.1 :
# The historical monolithic ``TrackerClient(Protocol)`` defined here
# was dropped in favour of the atomic capability protocols hosted in
# ``personalscraper.api.tracker._contracts`` (``TorrentSearchable``,
# ``CategoryListable``, ``FreeleechAware``, ``TorrentDetailsProvider``).
# Each concrete client now composes only the capabilities it actually
# implements (DESIGN §4 — Composition par client). The
# :class:`TrackerRegistry` is typed with the minimum needed capability
# (``TorrentSearchable``) and uses ``isinstance`` to widen at the
# specific call sites where a stricter capability is required.
