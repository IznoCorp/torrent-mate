"""Tracker-agnostic fetch boundary (D1).

This module bridges the tracker family (which produces :class:`TrackerResult`
search hits) to the torrent family (which consumes a :class:`TorrentSource`).
It is the single place that owns ALL ``TorrentFetchError`` surfacing:

* :class:`~personalscraper.api.transport._http.HttpTransport` stays fully
  provider-agnostic — its ``get_bytes`` raises a bare ``ValueError`` on an
  empty/oversize body (Phase 2) and an ``ApiError`` on non-2xx.
* This boundary maps those agnostic errors onto the tracker-family error
  types: 401/403 → :class:`TrackerAuthError`, every other download or
  validation failure → :class:`TorrentFetchError`.

Layering: importing :class:`TorrentSource` from ``api.torrent._base`` and the
error types from ``api.tracker._errors`` is the *whole point* of this module
(it is the tracker→torrent bridge, D1). ``TrackerResult`` and ``HttpTransport``
are pulled in under ``TYPE_CHECKING`` only, mirroring ``api/torrent/_base.py``,
to keep the runtime import graph acyclic.

Design: §5.2, §7 (D1/D4/D5/D6/D7/D8).
"""

from __future__ import annotations

import base64
import re
from typing import TYPE_CHECKING

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentSource
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from personalscraper.api.tracker._base import TrackerResult
    from personalscraper.api.transport._http import HttpTransport

log = get_logger("api.tracker.fetch")

# HTTP statuses that signal an authentication failure on a tracker download
# (expired token / invalid passkey). Mapped to ``TrackerAuthError`` so callers
# can trigger a credential refresh; every other non-2xx propagates verbatim.
_AUTH_STATUSES = (401, 403)

# Preview length of an invalid download body embedded in the resulting
# ``TorrentFetchError`` message — enough to distinguish an HTML login wall
# (``<html>…``) from a JSON error page (``{"error":…}``) without dumping the
# whole body into logs.
_BODY_PREVIEW_BYTES = 64


def _is_magnet(url: str) -> bool:
    """Return whether ``url`` is a magnet URI.

    Scheme-based classifier (case-insensitive). A magnet needs no HTTP
    transport at all, so callers short-circuit on it before any network or
    transport-lookup work (D8).

    Args:
        url: The candidate download URL or magnet URI.

    Returns:
        ``True`` if ``url`` begins with the ``magnet:`` scheme.
    """
    return url.lower().startswith("magnet:")


def _canonical_info_hash(s: str) -> str:
    """Canonicalize an info_hash to lowercase hex (D7).

    Mirrors the btih parsing in
    :func:`personalscraper.api.torrent._base._parse_magnet_hash`:

    * 40-char hex → lower-cased verbatim.
    * 32-char base32 (RFC 4648 alphabet) → decoded to 20 raw bytes then
      hex-encoded. Case-insensitive per RFC 4648.

    Used to normalise the *expected* hash before comparing it against the
    fetched file's ``info_hash`` (which ``TorrentSource`` already returns as
    lowercase hex), so a base32 or upper-case expected value still matches.

    Args:
        s: The candidate info_hash string.

    Returns:
        Lowercase hex info_hash (40 chars).

    Raises:
        ValueError: ``s`` is neither 40-char hex nor 32-char base32.
    """
    s = s.strip()
    if re.fullmatch(r"[0-9a-fA-F]{40}", s):
        return s.lower()
    if re.fullmatch(r"[A-Za-z2-7]{32}", s):
        return base64.b32decode(s.upper()).hex()
    raise ValueError(f"Cannot canonicalize info_hash: {s!r}")


def fetch_torrent_source(
    url: str,
    transport: HttpTransport,
    *,
    expected_info_hash: str | None = None,
) -> TorrentSource:
    """Fetch and validate a torrent source from a tracker download URL (D5/D7/D8).

    Resolution order:

    1. If ``url`` is a magnet URI (D8), return :meth:`TorrentSource.from_magnet`
       immediately — no transport call.
    2. Otherwise download the body via ``transport.get_bytes(url)`` and map the
       transport's agnostic errors onto tracker-family errors (the boundary
       owns ALL ``TorrentFetchError`` surfacing):

       * ``ApiError`` with HTTP 401/403 → :class:`TrackerAuthError`.
       * any other ``ApiError`` → re-raised unchanged.
       * ``ValueError`` (empty/oversize body, agnostic — Phase 2) →
         :class:`TorrentFetchError`.
    3. Validate the bytes via :meth:`TorrentSource.from_file` and access
       ``.info_hash`` — a ``ValueError`` there (non-bencode body / no top-level
       ``info`` key) → :class:`TorrentFetchError` carrying a short body preview.
    4. If ``expected_info_hash`` is truthy, canonicalize it and compare against
       the fetched hash. A non-canonicalizable expected value is skipped
       silently; a genuine mismatch raises :class:`TorrentFetchError`.

    Args:
        url: Absolute download URL, path relative to the transport's base URL,
            or a magnet URI.
        transport: The provider's :class:`HttpTransport`. Used for the binary
            GET and as the source of the provider name embedded in errors.
        expected_info_hash: Optional info_hash to cross-check against the
            fetched file. ``None`` or ``""`` skips the check (C411 may return
            ``""``, LaCale may return ``None``).

    Returns:
        The validated :class:`TorrentSource`.

    Raises:
        TrackerAuthError: The tracker returned HTTP 401 or 403.
        TorrentFetchError: Empty/oversize body, body is not a valid ``.torrent``,
            no top-level ``info`` key, or an info_hash mismatch.
        ApiError: Any non-auth, non-2xx HTTP status (propagated unchanged).
    """
    # D8: a magnet carries the hash inline and needs no transport at all.
    if _is_magnet(url):
        return TorrentSource.from_magnet(url)

    provider = transport.provider_name

    # An empty url is invalid input: it would otherwise join onto the
    # transport's base_url and GET the tracker root instead of a torrent file.
    # ``fetch_torrent_source`` is publicly exported, so guard it directly.
    if not url:
        raise TorrentFetchError(
            provider=provider,
            http_status=0,
            message="no usable download_url: empty url",
        )

    try:
        data = transport.get_bytes(url)
    except ApiError as exc:
        if exc.http_status in _AUTH_STATUSES:
            # D4: surface 401/403 as a tracker-family auth error so callers
            # can trigger a credential refresh. ``from exc`` preserves context.
            raise TrackerAuthError(
                provider=provider,
                http_status=exc.http_status,
                provider_code=exc.provider_code,
                message=f"tracker download auth failed for {url}: {exc.message}",
            ) from exc
        # Every other non-2xx propagates unchanged (e.g. a 500 must NOT be
        # masked as an auth error).
        raise
    except ValueError as exc:
        # D5: the transport raises an *agnostic* ValueError on an empty or
        # oversize body. Map it to the tracker-family error here — the
        # transport stays provider-agnostic by design.
        raise TorrentFetchError(
            provider=provider,
            http_status=0,
            message=f"failed to download torrent from {url}: {exc}",
        ) from exc

    # Validate the bytes as a real ``.torrent``. Accessing ``.info_hash``
    # forces the bencode walk, which raises ValueError on a non-bencode body
    # (HTML-200 login wall, JSON error page) or a missing top-level ``info``.
    try:
        source = TorrentSource.from_file(data)
        info_hash = source.info_hash
    except ValueError as exc:
        preview = data[:_BODY_PREVIEW_BYTES]
        raise TorrentFetchError(
            provider=provider,
            http_status=0,
            message=f"invalid .torrent body from {url}: {exc} (preview={preview!r})",
        ) from exc

    # D7: optional cross-check. ``expected_info_hash`` may be None or "" (both
    # falsy) when the tracker did not expose a hash — skip silently. A junk
    # but non-empty value that cannot be canonicalised is also skipped: the
    # fetched file already validated structurally, so a bad *expected* value
    # is not grounds to reject it.
    if expected_info_hash:
        try:
            canonical_expected = _canonical_info_hash(expected_info_hash)
        except ValueError:
            # A requested integrity check is being downgraded to a no-check
            # because the *expected* value is junk — log it so the silent skip
            # is observable. Behavior is unchanged (the file already validated
            # structurally, so a bad expected value is not grounds to reject).
            log.warning(
                "expected_info_hash_uncanonicalizable",
                provider=provider,
                url=url,
                expected_info_hash=expected_info_hash,
            )
            return source
        if canonical_expected != info_hash:
            raise TorrentFetchError(
                provider=provider,
                http_status=0,
                message=(f"info_hash mismatch for {url}: expected {canonical_expected}, fetched {info_hash}"),
            )

    return source


def resolve_source(
    result: TrackerResult,
    transports: Mapping[str, HttpTransport],
    *,
    cross_check: bool = True,
) -> TorrentSource:
    """Resolve a :class:`TrackerResult` to a :class:`TorrentSource` (D6/D8).

    Routes by ``result.provider`` (the lowercase wire key, e.g. ``"c411"`` /
    ``"lacale"``) over a caller-supplied transport map, then delegates to
    :func:`fetch_torrent_source`.

    Resolution order:

    1. If ``result.download_url`` is a magnet URI (D8), short-circuit *before*
       the transport lookup — a magnet needs no transport, so a missing
       provider entry must not block it.
    2. ``download_url`` is empty/``None`` → :class:`TorrentFetchError`.
    3. ``result.provider`` not in ``transports`` → :class:`TorrentFetchError`
       whose message lists both the missing provider and the available keys.
    4. Otherwise delegate to :func:`fetch_torrent_source`, forwarding
       ``result.info_hash`` as the expected hash when ``cross_check`` is set.

    Args:
        result: The tracker search result to resolve.
        transports: Map of lowercase provider wire-key → :class:`HttpTransport`.
        cross_check: When ``True`` (default), cross-check the fetched file's
            info_hash against ``result.info_hash``. ``False`` disables the
            check entirely (forwards ``expected_info_hash=None``).

    Returns:
        The validated :class:`TorrentSource`.

    Raises:
        TrackerAuthError: Propagated from :func:`fetch_torrent_source`.
        TorrentFetchError: ``download_url`` is empty or ``None``, the provider
            has no transport, or any fetch/validation failure from
            :func:`fetch_torrent_source`.
        ApiError: Any non-auth, non-2xx HTTP status (propagated unchanged).
    """
    download_url = result.download_url

    # D8: magnet first — it carries its own hash and needs no transport, so the
    # transport-lookup guard below must not reject it.
    if download_url is not None and _is_magnet(download_url):
        return TorrentSource.from_magnet(download_url)

    if not download_url:
        raise TorrentFetchError(
            provider=result.provider,
            http_status=0,
            message=f"no usable download_url on TrackerResult from {result.provider!r}",
        )

    provider = result.provider
    if provider not in transports:
        available = sorted(transports)
        raise TorrentFetchError(
            provider=provider,
            http_status=0,
            message=f"no transport for provider {provider!r}; available: {available}",
        )

    expected = result.info_hash if cross_check else None
    return fetch_torrent_source(download_url, transports[provider], expected_info_hash=expected)
