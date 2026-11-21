"""Tracker family public surface.

Exposes the tracker-agnostic fetch boundary (D1) and the tracker-family error
types so callers can resolve a :class:`~personalscraper.api.tracker._base.TrackerResult`
into a :class:`~personalscraper.api.torrent._base.TorrentSource` without reaching
into private modules.

It also exposes the ranking surface (:class:`TrackerResult`, :class:`RankingConfig`, :func:`rank`)
so the application layer scores results with the engine's own ``rank()`` rather than a copy.

Design: §5.2, §5.3, §7 (D1/D4).
"""

from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.api.tracker._fetch import fetch_torrent_source, resolve_source
from personalscraper.api.tracker._ranking import RankingConfig, rank

__all__ = [
    "RankingConfig",
    "TorrentFetchError",
    "TrackerAuthError",
    "TrackerResult",
    "fetch_torrent_source",
    "rank",
    "resolve_source",
]
