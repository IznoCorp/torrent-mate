"""Tests for the tracker-agnostic fetch boundary.

Design: §5.2, §7 (D1/D5/D6/D7/D8) — standalone tracker-agnostic fetch boundary.
Contract: magnet bypass; 401/403 → TrackerAuthError; HTML-200 → TorrentFetchError;
hash cross-check (uppercase/base32/mismatch/skip); resolve_source routing;
missing provider/download_url errors.
"""

from __future__ import annotations

import base64
import hashlib
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.api.tracker._fetch import (
    _canonical_info_hash,
    _is_magnet,
    fetch_torrent_source,
    resolve_source,
)

# --------------------------------------------------------------------------- #
# Self-contained bencode test helpers (copied from test_torrent_source.py — NOT
# imported, to keep this suite standalone).
# --------------------------------------------------------------------------- #


def _bencode(obj: object) -> bytes:
    """Encode a Python value as bencode (test helper).

    Supports ``bytes``, ``int``, ``list`` and ``dict`` (with ``bytes`` keys).
    Dict keys are emitted in sorted order to match real ``.torrent`` shape.

    Args:
        obj: Value to encode (bytes/int/list/dict).

    Returns:
        The bencoded byte string.

    Raises:
        TypeError: Unsupported type.
    """
    if isinstance(obj, bytes):
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, bool):  # guard: bool is an int subclass
        raise TypeError("bool not supported in bencode")
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, list):
        return b"l" + b"".join(_bencode(x) for x in obj) + b"e"
    if isinstance(obj, dict):
        out = b"d"
        for key in sorted(obj):
            assert isinstance(key, bytes), "dict keys must be bytes"
            out += _bencode(key) + _bencode(obj[key])
        return out + b"e"
    raise TypeError(f"unsupported bencode type: {type(obj)!r}")


def _make_torrent() -> tuple[bytes, str]:
    """Build a representative single-file ``.torrent`` (test helper).

    Returns:
        A ``(raw_bytes, expected_info_hash_hex)`` pair where the hash is the
        lowercase hex SHA-1 of the bencoded top-level ``info`` value.
    """
    info: dict[bytes, object] = {
        b"length": 12345,
        b"name": b"some.movie.2024.mkv",
        b"piece length": 16384,
        b"pieces": b"\x00" * 20,
    }
    torrent: dict[bytes, object] = {
        b"announce": b"http://tracker.example/announce",
        b"comment": b"a perfectly ordinary comment",
        b"info": info,
    }
    raw = _bencode(torrent)
    info_hash = hashlib.sha1(_bencode(info)).hexdigest()
    return raw, info_hash


def _fake_transport(provider: str = "c411") -> MagicMock:
    """Return a MagicMock transport with a settable provider name.

    The fetcher reads ``transport.provider_name`` (the public accessor) for
    error context; set it to a real string so error messages are deterministic.
    ``_policy.provider_name`` is also set to mirror the real transport.

    Args:
        provider: Lowercase wire provider name.

    Returns:
        A MagicMock standing in for an ``HttpTransport``.
    """
    transport = MagicMock()
    transport.provider_name = provider
    transport._policy.provider_name = provider
    return transport


# --------------------------------------------------------------------------- #
# TestIsMagnet
# --------------------------------------------------------------------------- #


class TestIsMagnet:
    """Scheme-based magnet classifier (D8)."""

    def test_magnet_uri(self) -> None:
        """A standard magnet URI is recognised."""
        assert _is_magnet("magnet:?xt=urn:btih:aabbccddee") is True

    def test_uppercase_magnet(self) -> None:
        """The scheme check is case-insensitive."""
        assert _is_magnet("MAGNET:?xt=urn:btih:aabbccddee") is True

    def test_https_url(self) -> None:
        """An absolute https download URL is not a magnet."""
        assert _is_magnet("https://c411.org/dl/x") is False

    def test_relative_url(self) -> None:
        """A relative download path is not a magnet."""
        assert _is_magnet("/api/download/abc") is False


# --------------------------------------------------------------------------- #
# TestCanonicalInfoHash (D7)
# --------------------------------------------------------------------------- #


class TestCanonicalInfoHash:
    """Canonicalisation of expected info_hash values (D7)."""

    def test_lowercase_hex_unchanged(self) -> None:
        """A 40-char lowercase hex hash is returned verbatim."""
        h = "aabbcc112233ddeeff00112233445566778899aa"
        assert _canonical_info_hash(h) == h

    def test_uppercase_hex_lowercased(self) -> None:
        """A 40-char uppercase hex hash is lower-cased."""
        h = "AABBCC112233DDEEFF00112233445566778899AA"
        assert _canonical_info_hash(h) == h.lower()

    def test_mixed_case_hex(self) -> None:
        """A mixed-case 40-char hex hash is lower-cased."""
        h = "AaBbCc112233DDeeff00112233445566778899aA"
        assert _canonical_info_hash(h) == h.lower()

    def test_base32_decoded_to_hex(self) -> None:
        """A 32-char base32 hash decodes to the matching lowercase hex."""
        raw = bytes(range(20))
        b32 = base64.b32encode(raw).decode().rstrip("=")
        assert len(b32) == 32
        assert _canonical_info_hash(b32) == raw.hex()

    def test_invalid_raises_value_error(self) -> None:
        """A non-hash string raises ValueError."""
        with pytest.raises(ValueError, match="canonicalize"):
            _canonical_info_hash("not-a-hash")

    def test_31_char_invalid(self) -> None:
        """A 31-char string (neither 40-hex nor 32-base32) raises ValueError."""
        with pytest.raises(ValueError, match="canonicalize"):
            _canonical_info_hash("A" * 31)


# --------------------------------------------------------------------------- #
# TestFetchTorrentSourceMagnet (D8)
# --------------------------------------------------------------------------- #


class TestFetchTorrentSourceMagnet:
    """Magnet shortcut never touches the transport (D8)."""

    def test_magnet_returns_from_magnet_no_transport_call(self) -> None:
        """A magnet URL returns a magnet TorrentSource without any get_bytes call."""
        transport = _fake_transport()
        uri = "magnet:?xt=urn:btih:AABBCC112233DDEEFF00112233445566778899AA&dn=x"
        source = fetch_torrent_source(uri, transport)
        assert source.magnet == uri
        assert source.file_bytes is None
        transport.get_bytes.assert_not_called()


# --------------------------------------------------------------------------- #
# TestFetchTorrentSourceHttp (D5)
# --------------------------------------------------------------------------- #


class TestFetchTorrentSourceHttp:
    """HTTP download path validation (D5)."""

    def test_valid_torrent_bytes_returned(self) -> None:
        """Valid bencode bytes produce a file-backed TorrentSource."""
        raw, _ = _make_torrent()
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        source = fetch_torrent_source("https://c411.org/dl/x", transport)
        assert source.file_bytes == raw
        assert source.magnet is None

    def test_html_200_raises_torrent_fetch_error(self) -> None:
        """An HTML-200 login wall (not bencode) raises TorrentFetchError."""
        transport = _fake_transport()
        transport.get_bytes.return_value = b"<html><body>please log in</body></html>"
        with pytest.raises(TorrentFetchError, match="invalid"):
            fetch_torrent_source("https://c411.org/dl/x", transport)

    def test_json_error_page_raises_torrent_fetch_error(self) -> None:
        """A JSON error page (not bencode) raises TorrentFetchError."""
        transport = _fake_transport()
        transport.get_bytes.return_value = b'{"error":"forbidden"}'
        with pytest.raises(TorrentFetchError):
            fetch_torrent_source("https://c411.org/dl/x", transport)

    def test_bencode_without_info_key_raises_torrent_fetch_error(self) -> None:
        """A bencoded dict with no top-level ``info`` key raises TorrentFetchError."""
        transport = _fake_transport()
        transport.get_bytes.return_value = _bencode({b"announce": b"http://x/announce"})
        with pytest.raises(TorrentFetchError):
            fetch_torrent_source("https://c411.org/dl/x", transport)

    def test_get_bytes_oversize_valueerror_becomes_torrent_fetch_error(self) -> None:
        """An agnostic oversize ValueError from get_bytes maps to TorrentFetchError (D5)."""
        transport = _fake_transport()
        transport.get_bytes.side_effect = ValueError("download exceeds max_bytes=10485760")
        with pytest.raises(TorrentFetchError, match="download"):
            fetch_torrent_source("https://c411.org/dl/x", transport)

    def test_get_bytes_empty_valueerror_becomes_torrent_fetch_error(self) -> None:
        """An agnostic empty-body ValueError from get_bytes maps to TorrentFetchError (D5)."""
        transport = _fake_transport()
        transport.get_bytes.side_effect = ValueError("empty download body")
        with pytest.raises(TorrentFetchError):
            fetch_torrent_source("https://c411.org/dl/x", transport)

    def test_empty_url_raises_torrent_fetch_error_without_get_bytes(self) -> None:
        """An empty url is rejected upfront and never reaches get_bytes."""
        transport = _fake_transport()
        with pytest.raises(TorrentFetchError):
            fetch_torrent_source("", transport)
        transport.get_bytes.assert_not_called()

    def test_404_propagates_as_api_error_not_auth_error(self) -> None:
        """A non-auth 404 ApiError propagates unchanged and is NOT a TrackerAuthError.

        Exercises the ``_AUTH_STATUSES`` lower boundary: 404 is below 401/403 in
        intent (a missing resource, not an auth failure) and must surface as the
        raw ``ApiError``.
        """
        transport = _fake_transport()
        transport.get_bytes.side_effect = ApiError(provider="c411", http_status=404, message="not found")
        with pytest.raises(ApiError) as exc_info:
            fetch_torrent_source("https://c411.org/dl/x", transport)
        assert exc_info.value.http_status == 404
        assert not isinstance(exc_info.value, TrackerAuthError)


# --------------------------------------------------------------------------- #
# TestFetchTorrentSourceAuthErrors (D4)
# --------------------------------------------------------------------------- #


class TestFetchTorrentSourceAuthErrors:
    """Auth-status mapping (D4)."""

    def test_401_raises_tracker_auth_error(self) -> None:
        """An HTTP 401 ApiError is surfaced as TrackerAuthError preserving the status."""
        transport = _fake_transport()
        transport.get_bytes.side_effect = ApiError(provider="c411", http_status=401, message="unauthorized")
        with pytest.raises(TrackerAuthError) as exc_info:
            fetch_torrent_source("https://c411.org/dl/x", transport)
        assert exc_info.value.http_status == 401

    def test_403_raises_tracker_auth_error(self) -> None:
        """An HTTP 403 ApiError is surfaced as TrackerAuthError preserving the status."""
        transport = _fake_transport()
        transport.get_bytes.side_effect = ApiError(provider="c411", http_status=403, message="forbidden")
        with pytest.raises(TrackerAuthError) as exc_info:
            fetch_torrent_source("https://c411.org/dl/x", transport)
        assert exc_info.value.http_status == 403

    def test_500_propagates_as_api_error_not_auth_error(self) -> None:
        """An HTTP 500 ApiError propagates unchanged and is NOT a TrackerAuthError."""
        transport = _fake_transport()
        transport.get_bytes.side_effect = ApiError(provider="c411", http_status=500, message="server error")
        with pytest.raises(ApiError) as exc_info:
            fetch_torrent_source("https://c411.org/dl/x", transport)
        assert exc_info.value.http_status == 500
        assert not isinstance(exc_info.value, TrackerAuthError)


# --------------------------------------------------------------------------- #
# TestFetchTorrentSourceHashCrossCheck (D7)
# --------------------------------------------------------------------------- #


class TestFetchTorrentSourceHashCrossCheck:
    """Optional info_hash cross-check (D7)."""

    def test_matching_lowercase_hex_passes(self) -> None:
        """A correct lowercase hex expected hash does not raise."""
        raw, info_hash = _make_torrent()
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        source = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash=info_hash)
        assert source.file_bytes == raw

    def test_uppercase_expected_hash_passes(self) -> None:
        """An uppercased expected hash is canonicalised before compare — no raise."""
        raw, info_hash = _make_torrent()
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        source = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash=info_hash.upper())
        assert source.file_bytes == raw

    def test_base32_expected_hash_passes(self) -> None:
        """A base32-encoded expected hash is decoded before compare — no raise."""
        raw, info_hash = _make_torrent()
        b32_expected = base64.b32encode(bytes.fromhex(info_hash)).decode().rstrip("=")
        assert len(b32_expected) == 32
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        source = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash=b32_expected)
        assert source.file_bytes == raw

    def test_real_mismatch_raises_torrent_fetch_error(self) -> None:
        """A genuinely wrong expected hash raises TorrentFetchError."""
        raw, _ = _make_torrent()
        wrong = "0" * 40
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        with pytest.raises(TorrentFetchError, match="mismatch"):
            fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash=wrong)

    def test_empty_string_skips_cross_check(self) -> None:
        """An empty-string expected hash skips the check (C411 may return "")."""
        raw, _ = _make_torrent()
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        source = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash="")
        assert source.file_bytes == raw

    def test_none_skips_cross_check(self) -> None:
        """A None expected hash skips the check (LaCale may return None)."""
        raw, _ = _make_torrent()
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        source = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash=None)
        assert source.file_bytes == raw

    def test_uncanonicalizable_expected_hash_skips_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """A truthy-but-junk expected hash skips the check, returns source, and warns.

        The fetched file already validated structurally, so a bad *expected*
        value is not grounds to reject it — but the silent downgrade of a
        requested integrity check must be observable (a warning is logged).
        """
        import logging

        raw, _ = _make_torrent()
        transport = _fake_transport()
        transport.get_bytes.return_value = raw
        with caplog.at_level(logging.WARNING):
            source = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash="zzz")
        assert source.file_bytes == raw
        assert "expected_info_hash_uncanonicalizable" in caplog.text


# --------------------------------------------------------------------------- #
# TestResolveSource (D6)
# --------------------------------------------------------------------------- #


def _result(
    *,
    provider: str = "c411",
    download_url: str | None = "https://c411.org/dl/x",
    info_hash: str | None = None,
) -> TrackerResult:
    """Build a minimal TrackerResult for resolve_source tests.

    Args:
        provider: Lowercase wire provider name.
        download_url: Download URL or magnet URI (or None).
        info_hash: Optional info_hash to attach.

    Returns:
        A populated TrackerResult.
    """
    from personalscraper.api._units import ByteSize

    return TrackerResult(
        provider=provider,
        tracker_id="123",
        title="Some.Movie.2024.1080p",
        size=ByteSize(1_000_000),
        seeders=10,
        leechers=2,
        download_url=download_url,
        info_hash=info_hash,
    )


class TestResolveSource:
    """Provider routing over the transport map (D6/D8)."""

    def test_routes_c411_to_correct_transport(self) -> None:
        """The c411 transport is used; the lacale transport is left untouched."""
        raw, _ = _make_torrent()
        c411 = _fake_transport("c411")
        c411.get_bytes.return_value = raw
        lacale = _fake_transport("lacale")
        transports = {"c411": c411, "lacale": lacale}
        source = resolve_source(_result(provider="c411"), transports)
        assert source.file_bytes == raw
        c411.get_bytes.assert_called_once()
        lacale.get_bytes.assert_not_called()

    def test_routes_lacale_to_correct_transport(self) -> None:
        """A relative download URL routes to the lacale transport."""
        raw, _ = _make_torrent()
        lacale = _fake_transport("lacale")
        lacale.get_bytes.return_value = raw
        c411 = _fake_transport("c411")
        transports = {"c411": c411, "lacale": lacale}
        result = _result(provider="lacale", download_url="/api/download/abc")
        source = resolve_source(result, transports)
        assert source.file_bytes == raw
        lacale.get_bytes.assert_called_once_with("/api/download/abc")
        c411.get_bytes.assert_not_called()

    def test_missing_provider_raises_torrent_fetch_error_with_available_keys(self) -> None:
        """An unmapped provider raises TorrentFetchError listing the missing + available keys."""
        c411 = _fake_transport("c411")
        transports = {"c411": c411}
        result = _result(provider="lacale")
        with pytest.raises(TorrentFetchError) as exc_info:
            resolve_source(result, transports)
        message = str(exc_info.value)
        assert "lacale" in message  # the missing provider
        assert "c411" in message  # the available key

    def test_missing_download_url_raises_torrent_fetch_error(self) -> None:
        """A None download_url raises TorrentFetchError."""
        c411 = _fake_transport("c411")
        transports = {"c411": c411}
        result = _result(provider="c411", download_url=None)
        with pytest.raises(TorrentFetchError, match="download_url"):
            resolve_source(result, transports)

    def test_empty_download_url_raises_torrent_fetch_error(self) -> None:
        """An empty-string download_url (falsy-yet-not-None) raises TorrentFetchError."""
        c411 = _fake_transport("c411")
        transports = {"c411": c411}
        result = _result(provider="c411", download_url="")
        with pytest.raises(TorrentFetchError, match="download_url"):
            resolve_source(result, transports)
        c411.get_bytes.assert_not_called()

    def test_magnet_download_url_bypasses_transport(self) -> None:
        """A magnet download_url short-circuits before any transport lookup/call."""
        c411 = _fake_transport("c411")
        transports = {"c411": c411}
        uri = "magnet:?xt=urn:btih:AABBCC112233DDEEFF00112233445566778899AA&dn=x"
        result = _result(provider="c411", download_url=uri)
        source = resolve_source(result, transports)
        assert source.magnet == uri
        c411.get_bytes.assert_not_called()

    def test_cross_check_false_disables_hash_check(self) -> None:
        """cross_check=False forwards no expected hash even with a wrong info_hash set."""
        raw, _ = _make_torrent()
        c411 = _fake_transport("c411")
        c411.get_bytes.return_value = raw
        transports = {"c411": c411}
        result = _result(provider="c411", info_hash="0" * 40)  # deliberately wrong
        source = resolve_source(result, transports, cross_check=False)
        assert source.file_bytes == raw

    def test_empty_transports_map_raises_torrent_fetch_error(self) -> None:
        """An empty transport map raises TorrentFetchError mentioning availability."""
        result = _result(provider="c411")
        with pytest.raises(TorrentFetchError, match="available"):
            resolve_source(result, {})
