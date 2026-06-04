"""Tracker-family typed errors.

Kept separate from ``_base.py`` to avoid a circular import: ``_fetch.py``
imports both ``_base.py`` (for TrackerResult) and these error types, and
``_base.py`` must not import from ``_fetch.py``. Same hygiene pattern as
``api/torrent/_errors.py``.

Design: §5.3 (D4).
"""

from __future__ import annotations

from personalscraper.api._contracts import ApiError


class TrackerAuthError(ApiError):
    """Authentication failure on a tracker download (HTTP 401 or 403).

    Raised by ``fetch_torrent_source`` when the tracker returns 401/403,
    signalling an expired token or invalid API key. Callers (RP7 and
    beyond) can catch this to trigger a credential refresh or alert.

    Inherits ``ApiError``'s ``__init__``: ``provider``, ``http_status``,
    ``provider_code``, ``message``.
    """


class TorrentFetchError(ApiError):
    """Unrecoverable error fetching or validating a ``.torrent`` file.

    Raised by ``fetch_torrent_source`` / ``resolve_source`` for:
    - Empty body from a successful HTTP response
    - Body exceeds the size cap
    - Body is not a valid bencoded dict (HTML-200 login wall, JSON error)
    - Bencoded dict has no top-level ``info`` key
    - Derived info_hash does not match the expected hash
    - ``TrackerResult.download_url`` is None
    - ``TrackerResult.provider`` key not found in the transports map

    Inherits ``ApiError``'s ``__init__``: ``provider``, ``http_status``,
    ``provider_code``, ``message``.
    """


__all__ = ["TrackerAuthError", "TorrentFetchError"]
