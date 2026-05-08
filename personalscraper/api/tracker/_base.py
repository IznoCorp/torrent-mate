"""Tracker family base — TrackerClient Protocol and TrackerResult model.

Implements DESIGN §6.1: TrackerClient Protocol and TrackerResult dataclass.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Protocol, TypeVar

from personalscraper.api._contracts import ApiError, MediaType
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
        provider: Tracker provider name (e.g. "LaCale", "C411").
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
        audio: Audio language/track info (VFF, VFQ, TrueHD...).
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


class TrackerClient(Protocol):
    """Protocol for tracker API providers.

    Implementations must provide a ``provider_name`` class attribute, the
    set of required credentials, and implement ``search()`` and
    ``get_categories()``.

    Implementor contract for ``search()``:
        Trackers whose parsers may surface ``KeyError`` / ``IndexError`` /
        ``TypeError`` / ``AttributeError`` / ``ValueError`` on schema drift
        MUST wrap their parse code via :func:`wrap_parser_drift` (or raise
        :class:`ApiError` directly) so the error reaches
        :class:`TrackerRegistry` as an operational failure. The registry
        deliberately does NOT swallow bare programming exceptions —
        unwrapped drift would crash every other tracker's search.
    """

    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]: ...

    def get_categories(self) -> dict[str, str]: ...
