"""Unit tests for ``scripts/capture-tracker-sample.py`` — the redaction of a tracker's key.

The script writes a tracker's live answers into the repository. Those answers echo the
operator's API key (Torznab enclosure links carry it), and draupnirr's API key IS its
announce key. Every test plants a recognisable key and passkey in a fake tracker's
answers and proves neither reaches a written file — and that an unknown per-user
secret in a link is stripped by its parameter's name.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "capture-tracker-sample.py"


def _load() -> Any:
    """Imports the script as a module, despite its hyphenated filename.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("capture_tracker_sample", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules while the class is built.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


capture = _load()

KEY = "PLANTEDkey0123456789abcdef"
PASSKEY = "PLANTEDpass9876543210fedcba"
UNKNOWN_SECRET = "unknownrsssecret55555"


class _Response:
    """A minimal ``requests.Response`` stand-in."""

    def __init__(self, status: int, text: str, content_type: str) -> None:
        """Builds the answer.

        Args:
            status: HTTP status.
            text: The body.
            content_type: The ``Content-Type`` header.
        """
        self.status_code = status
        self.text = text
        self.headers = {"Content-Type": content_type}


class _FakeTracker:
    """Echoes the key and the passkey back in its answers, as real trackers do."""

    def __init__(self) -> None:
        """Builds the fake."""
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        """Records the call and answers with secrets embedded.

        Args:
            url: The absolute URL.
            **kwargs: ``params``, ``headers``, ``timeout``, ``allow_redirects``.

        Returns:
            The fake answer.
        """
        self.calls.append({"url": url, **kwargs})
        sent = (kwargs.get("params") or {}).get("apikey") or (kwargs.get("headers") or {}).get("X-API-KEY")
        if sent != KEY:
            if url.endswith("/torznab/api"):
                return _Response(200, '<error code="100" description="Invalid API Key"/>', "application/xml")
            return _Response(401, json.dumps({"error": "unauthorized"}), "application/json")
        if url.endswith("/torznab/api"):
            body = (
                f'<rss><channel><item><title>Inception</title><enclosure url="https://draupnirr.xyz/dl/1?apikey={KEY}'
                f'&amp;rsskey={UNKNOWN_SECRET}"/><comments>announce {KEY}</comments></item></channel></rss>'
            )
            return _Response(200, body, "application/xml")
        rows = [
            {
                "title": "Inception",
                "id": 1,
                "download": f"https://api.v3x.club/dl/1?apikey={KEY}",
                "announce": f"https://tracker.example/announce?passkey={PASSKEY}",
                "note": f"raw {PASSKEY} and {KEY}",
            }
        ]
        return _Response(200, json.dumps({"results": rows}), "application/json")


def _env() -> dict[str, str]:
    """The planted environment.

    Returns:
        Every tracker's key, and digitalcore's passkey.
    """
    return {"DRAUPNIRR_API_KEY": KEY, "V3X_API_KEY": KEY, "DIGITALCORE_API_KEY": KEY, "DIGITALCORE_PASSKEY": PASSKEY}


def _capture(tracker: str, tmp_path: Path, fake: _FakeTracker | None = None) -> dict[str, str]:
    """Runs one capture and reads the files back.

    Args:
        tracker: The tracker.
        tmp_path: Output root.
        fake: The fake session.

    Returns:
        File name → text.
    """
    out = tmp_path / tracker
    capture.capture(
        tracker,
        session=fake or _FakeTracker(),
        env=_env(),
        out_dir=out,
        movie="Inception",
        tv="The Office",
        say=lambda _: None,
    )
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(out.iterdir())}


@pytest.mark.parametrize("tracker", ["draupnirr", "v3x", "digitalcore"])
def test_no_key_or_passkey_reaches_a_written_file(tracker: str, tmp_path: Path) -> None:
    """The planted key, passkey and an unannounced link secret are absent from every file."""
    files = _capture(tracker, tmp_path)
    assert files
    for name, text in files.items():
        for secret in (KEY, PASSKEY, UNKNOWN_SECRET):
            assert secret not in text, f"a planted secret leaked into {tracker}/{name}"


def test_draupnirr_records_caps_both_searches_and_the_auth_failure(tmp_path: Path) -> None:
    """Torznab: caps, movie, TV, and the HTTP-200 ``<error code="100"/>`` of a bad key."""
    files = _capture("draupnirr", tmp_path)
    assert set(files) == {"caps.xml", "search-movie.xml", "search-tv.xml", "error-auth.xml", "index.json"}
    assert 'code="100"' in files["error-auth.xml"]
    index = json.loads(files["index.json"])
    assert index["error-auth.xml"]["status"] == 200
    assert "apikey=REDACTED" in files["search-movie.xml"]
    assert "rsskey=REDACTED" in files["search-movie.xml"]


def test_json_trackers_record_both_searches_and_a_401(tmp_path: Path) -> None:
    """v3x: two searches and the bad key's 401, the index naming each request without its key."""
    files = _capture("v3x", tmp_path)
    assert set(files) == {"search-movie.json", "search-tv.json", "error-auth.json", "index.json"}
    index = json.loads(files["index.json"])
    assert index["error-auth.json"]["status"] == 401
    assert index["search-movie.json"]["request"].startswith("GET /indexer/search?")


def test_the_bad_key_call_never_sends_the_real_key(tmp_path: Path) -> None:
    """The auth failure is recorded with the invalid key; the real key goes out only on the real calls."""
    fake = _FakeTracker()
    _capture("draupnirr", tmp_path, fake)
    keys = [call["params"]["apikey"] for call in fake.calls]
    assert keys[-1] == capture.INVALID_KEY
    assert keys[:-1] == [KEY] * (len(keys) - 1)


def test_digitalcore_key_travels_in_the_header_only(tmp_path: Path) -> None:
    """Header auth: the key is never in a URL or the query."""
    fake = _FakeTracker()
    _capture("digitalcore", tmp_path, fake)
    for call in fake.calls:
        assert "X-API-KEY" in call["headers"]
        assert KEY not in call["url"] + json.dumps(call["params"])
        assert call["allow_redirects"] is False


def test_a_leak_writes_nothing_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When redaction is broken, the scan refuses the whole set, and its message names no secret."""
    monkeypatch.setattr(capture, "redact", lambda text, secrets: text)
    with pytest.raises(capture.RedactionLeak) as caught:
        _capture("v3x", tmp_path)
    assert not (tmp_path / "v3x").exists()
    assert KEY not in str(caught.value) and PASSKEY not in str(caught.value)


def test_a_failed_call_names_the_exception_type_only(tmp_path: Path) -> None:
    """A connection error whose text carries the key is re-raised without it, unchained."""

    class _Exploding(_FakeTracker):
        def get(self, url: str, **kwargs: Any) -> _Response:
            raise requests.ConnectionError(f"boom {kwargs['params'].get('apikey')}")

    with pytest.raises(capture.CaptureError) as caught:
        _capture("v3x", tmp_path, _Exploding())
    assert KEY not in str(caught.value) and "ConnectionError" in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_a_missing_key_stops_before_any_call(tmp_path: Path) -> None:
    """Without the key nothing is called and nothing is written."""
    fake = _FakeTracker()
    with pytest.raises(capture.CaptureError):
        capture.capture("v3x", session=fake, env={}, out_dir=tmp_path / "v3x", movie="m", tv="t", say=lambda _: None)
    assert fake.calls == [] and not (tmp_path / "v3x").exists()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://x/dl?apikey=abc&id=1", "https://x/dl?apikey=REDACTED&id=1"),
        ("https://x/a?passkey=zz", "https://x/a?passkey=REDACTED"),
        ('url="https://x/a?id=1&amp;torrent_pass=zz"', 'url="https://x/a?id=1&amp;torrent_pass=REDACTED"'),
        ("https://x/a?t=search&q=Inception", "https://x/a?t=search&q=Inception"),
    ],
)
def test_secret_named_parameters_lose_their_value(text: str, expected: str) -> None:
    """A parameter whose name says key / pass / token loses its value; the others are kept."""
    assert capture.redact(text, []) == expected
