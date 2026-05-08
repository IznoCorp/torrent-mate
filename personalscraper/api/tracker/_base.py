"""Tracker family base — TrackerClient Protocol and TrackerResult model.

Implements DESIGN §6.1: TrackerClient Protocol and TrackerResult dataclass.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Protocol

from personalscraper.api._contracts import MediaType
from personalscraper.api._units import ByteSize


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

    Implementations must provide a provider_name class attribute, the set
    of required credentials, and implement search() and get_categories().
    """

    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def search(self, query: str, media_type: MediaType = "movie", year: int | None = None) -> list[TrackerResult]: ...

    def get_categories(self) -> dict[str, str]: ...
