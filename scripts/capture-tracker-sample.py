#!/usr/bin/env python3
"""Capture one tracker's answers as redacted fixtures — run by the operator, never by a session.

A tracker client's unit tests read recorded answers from ``docs/reference/_samples/<tracker>/``;
recording them is a live call with the operator's key, so he runs this script himself
(``docs/features/backend-bricks/trackers-t1/DESIGN.md`` § 5, T-3 = B) and a session
only ever reads the redacted files. No key enters an agent's context.

Per tracker it calls, with raw ``requests`` and the key from ``.env``:

- the capabilities document, where the tracker has one (Torznab ``t=caps``);
- one movie search and one TV search (the queries are arguments);
- one call with a deliberately INVALID key, to record the auth failure's shape.

**Every key and passkey is redacted** before anything is written: each secret of
every tracker the code declares (``secret_envs``) is replaced wherever it appears,
raw or percent-encoded (bodies, recorded request paths). A link may also carry a
per-user secret this script was never told about, so, whatever its value: every
URL parameter whose name says « key », « pass », « token » (``apikey``,
``x-api-key``, ``torrent_pass``), its separators literal or percent-encoded
(``%3F``, ``%26``, ``%3D``); the whole announce of a magnet (``tr=``); and every
opaque path segment (16+ alphanumerics) of an announce or download URL
(``/dl/55/<passkey>/file.torrent``). A final scan, over the text and its decoded
forms, refuses the WHOLE set when a known secret survives: nothing is written,
and the refusal names no secret.

Usage (his hand only):
    python scripts/capture-tracker-sample.py <tracker> [--movie "Inception"] [--tv "The Office"]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, quote_plus, unquote, unquote_plus

import requests

SAMPLES_ROOT = Path(__file__).resolve().parents[1] / "docs" / "reference" / "_samples"
_TIMEOUT: tuple[float, float] = (5.0, 30.0)
#: Sent instead of the real key, once, to record the auth failure.
INVALID_KEY = "invalid-key-for-the-auth-capture"
REDACTED = "REDACTED"
#: A query-parameter separator, literal, HTML-escaped or percent-encoded (``?``, ``&``, ``&amp;``, ``%3F``, ``%26``).
_SEP = r"(?:[?&;]|&amp;|%3F|%26)"
#: A URL query parameter whose NAME marks a secret (``apikey``, ``x-api-key``, ``torrent_pass``…), its ``=``
#: literal or encoded (``%3D``): its value goes, whatever it is.
_SECRET_PARAM = re.compile(
    rf"(?P<name>{_SEP}[A-Za-z_-]*(?:key|pass|token|auth|rss)[A-Za-z_-]*(?:=|%3D))(?P<value>(?:(?!%26)[^&\"'<>\s])+)",
    re.IGNORECASE,
)
#: A magnet's announce (``tr=``): its WHOLE value goes — it is a tracker URL, and its passkey hides in any shape.
_ANNOUNCE_PARAM = re.compile(rf"(?P<name>{_SEP}tr(?:=|%3D))(?P<value>[^&\"'<>\s]+)", re.IGNORECASE)
#: A URL, plain or percent-encoded (``https%3A%2F%2F…``).
_URL = re.compile(r"(?:https?|udp)(?::|%3A)(?://|%2F%2F)[^\s\"'<>]+", re.IGNORECASE)
#: What makes a URL an announce or a download link: where a tracker puts a passkey as a path segment.
_ANNOUNCE_OR_DOWNLOAD = re.compile(r"announce|/dl/|%2Fdl%2F|download|\.torrent|/rss", re.IGNORECASE)
#: What splits a URL into segments, literal or percent-encoded: ``/``, ``?``, ``&``, ``=``, ``:``.
_URL_SPLIT = re.compile(r"(%2F|%3F|%26|%3D|%3A|&amp;|[/?&=:;#])", re.IGNORECASE)
#: An opaque segment: 16+ alphanumerics, never a word, an id or a release name (those carry dots or dashes).
_OPAQUE_SEGMENT = re.compile(r"[A-Za-z0-9]{16,}")


def secret_envs() -> set[str]:
    """Names every tracker credential the code declares, and those of the trackers this script captures.

    Every tracker's, not only the captured one's: an answer may echo any key the operator holds
    (a cross-posted release, a shared announce), and redacting a value that never appears costs nothing.

    Returns:
        The environment variable names whose values are secrets.
    """
    from personalscraper.api._activation import PROVIDER_CREDS, PROVIDER_OPTIONAL_SECRETS
    from personalscraper.api.tracker._factory import _TRACKER_CLASSES

    declared = {name for tracker in _TRACKER_CLASSES for name in PROVIDER_CREDS.get(tracker, [])}
    declared |= {name for names in PROVIDER_OPTIONAL_SECRETS.values() for name in names}
    return declared | {name for t in TRACKERS.values() for name in (t.key_env, *t.extra_secret_envs)}


@dataclass(frozen=True)
class Call:
    """One request of a capture.

    Attributes:
        name: The fixture's file stem.
        path: The path on the tracker's base URL.
        params: Query parameters (the key is added by the auth, never here).
    """

    name: str
    path: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class TrackerSpec:
    """How one tracker is asked.

    Attributes:
        base_url: The tracker's API origin.
        key_env: The ``.env`` variable holding the API key.
        auth: ``query`` (the key as a query parameter) or ``header``.
        auth_name: The query parameter or header name.
        extension: The fixtures' file extension (``xml`` / ``json``).
        calls: Builds the capture's calls from the movie and TV queries.
        extra_secret_envs: Other ``.env`` secrets of the tracker, redacted too (a passkey).
    """

    base_url: str
    key_env: str
    auth: str
    auth_name: str
    extension: str
    calls: Callable[[str, str], list[Call]]
    extra_secret_envs: tuple[str, ...] = ()


def _torznab_calls(movie: str, tv: str) -> list[Call]:
    """Torznab: caps, a movie search, a TV search.

    Args:
        movie: The movie query.
        tv: The TV query.

    Returns:
        The calls.
    """
    return [
        Call("caps", "/torznab/api", {"t": "caps"}),
        Call("search-movie", "/torznab/api", {"t": "movie", "q": movie}),
        Call("search-tv", "/torznab/api", {"t": "tvsearch", "q": tv}),
    ]


def _v3x_calls(movie: str, tv: str) -> list[Call]:
    """v3x.club's JSON indexer API: a movie and a TV search (no caps document is public).

    Args:
        movie: The movie query.
        tv: The TV query.

    Returns:
        The calls.
    """
    return [
        Call("search-movie", "/indexer/search", {"q": movie, "cat": "2000", "limit": 100}),
        Call("search-tv", "/indexer/search", {"q": tv, "cat": "5000", "limit": 100}),
    ]


def _digitalcore_calls(movie: str, tv: str) -> list[Call]:
    """digitalcore.club's API v1: a movie and a TV search.

    Args:
        movie: The movie query.
        tv: The TV query.

    Returns:
        The calls.
    """
    common = {
        "limit": 100,
        "index": 0,
        "page": "search",
        "section": "all",
        "sort": "d",
        "order": "desc",
        "dead": "false",
    }
    return [
        Call(
            "search-movie",
            "/api/v1/torrents",
            {**common, "searchText": movie, "categories[]": [1, 2, 3, 4, 5, 6, 7, 38]},
        ),
        Call(
            "search-tv",
            "/api/v1/torrents",
            {**common, "searchText": tv, "categories[]": [8, 9, 10, 11, 12, 13, 14, 15]},
        ),
    ]


TRACKERS: Mapping[str, TrackerSpec] = {
    "draupnirr": TrackerSpec("https://draupnirr.xyz", "DRAUPNIRR_API_KEY", "query", "apikey", "xml", _torznab_calls),
    "v3x": TrackerSpec("https://api.v3x.club", "V3X_API_KEY", "query", "apikey", "json", _v3x_calls),
    "digitalcore": TrackerSpec(
        "https://digitalcore.club",
        "DIGITALCORE_API_KEY",
        "header",
        "X-API-KEY",
        "json",
        _digitalcore_calls,
        extra_secret_envs=("DIGITALCORE_PASSKEY",),
    ),
}


class CaptureError(Exception):
    """The capture cannot go on; its text never carries a key."""


class RedactionLeak(CaptureError):
    """A known secret survived redaction — nothing is written."""


def _forms(secret: str) -> set[str]:
    """Returns a secret as it may be written: raw, percent-encoded, form-encoded.

    Args:
        secret: The secret.

    Returns:
        Its distinct written forms.
    """
    return {secret, quote(secret, safe=""), quote_plus(secret, safe="")}


def _strip_opaque_segments(match: re.Match[str]) -> str:
    """Replaces the opaque path segments of an announce or download URL.

    Args:
        match: A URL.

    Returns:
        The URL, each opaque segment ``REDACTED`` when it is an announce or a download link — its
        query values too: an opaque value there is as likely a secret.
    """
    url = match.group(0)
    if not _ANNOUNCE_OR_DOWNLOAD.search(url):
        return url
    parts = _URL_SPLIT.split(url)
    return "".join(REDACTED if _OPAQUE_SEGMENT.fullmatch(part) else part for part in parts)


def redact(text: str, secrets: list[str]) -> str:
    """Removes every known secret, and every value a tracker URL hides a secret in.

    Args:
        text: A body or a recorded request path.
        secrets: The secrets read from the environment.

    Returns:
        The text without each known secret (raw or percent-encoded), each secret-named parameter's
        value (separators literal or encoded, names hyphenated or not), each magnet announce, and
        each opaque path segment of an announce or download URL.
    """
    forms = {form for s in secrets if s for form in _forms(s)}
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, REDACTED)
    text = _ANNOUNCE_PARAM.sub(lambda m: m.group("name") + REDACTED, text)
    text = _SECRET_PARAM.sub(lambda m: m.group("name") + REDACTED, text)
    return _URL.sub(_strip_opaque_segments, text)


def check(text: str, secrets: list[str]) -> None:
    """Refuses a text in which a known secret remains, as written or once decoded.

    Args:
        text: A file's full text as it would be written.
        secrets: The secrets read from the environment.

    Raises:
        RedactionLeak: A secret survived (the secret itself is not in the message).
    """
    views = {text, unquote(text), unquote_plus(text), html.unescape(text), unquote(unquote(text))}
    if any(secret and secret in view for secret in secrets for view in views):
        raise RedactionLeak("a key survived redaction; nothing written")


def _request(session: requests.Session, spec: TrackerSpec, call: Call, key: str) -> requests.Response:
    """One GET with the key placed as the tracker expects it.

    Args:
        session: The HTTP session.
        spec: The tracker.
        call: What to ask.
        key: The key sent (the real one, or ``INVALID_KEY``).

    Returns:
        The response.

    Raises:
        CaptureError: No answer (the key-bearing exception is not chained).
    """
    params = dict(call.params)
    headers = {"Accept": "application/json" if spec.extension == "json" else "application/xml"}
    if spec.auth == "query":
        params[spec.auth_name] = key
    else:
        headers[spec.auth_name] = key
    try:
        return session.get(
            spec.base_url + call.path, params=params, headers=headers, timeout=_TIMEOUT, allow_redirects=False
        )
    except Exception as exc:  # noqa: BLE001 — a key-bearing frame must not escape
        raise CaptureError(f"GET {call.path} failed: {type(exc).__name__}") from None


def capture(
    tracker: str,
    *,
    session: requests.Session,
    env: Mapping[str, str],
    out_dir: Path,
    movie: str,
    tv: str,
    say: Callable[[str], None] = print,
) -> list[Path]:
    """Captures one tracker's answers and writes them redacted.

    Args:
        tracker: A key of ``TRACKERS``.
        session: The HTTP session (a fake one in tests).
        env: Where the key and the extra secrets are read.
        out_dir: The tracker's fixtures directory.
        movie: The movie query.
        tv: The TV query.
        say: Progress output (never a key).

    Returns:
        The written paths.

    Raises:
        CaptureError: Unknown tracker, missing key, or no answer.
        RedactionLeak: A secret survived; nothing is written.
    """
    spec = TRACKERS.get(tracker)
    if spec is None:
        raise CaptureError(f"unknown tracker {tracker!r}; known: {', '.join(sorted(TRACKERS))}")
    key = env.get(spec.key_env, "")
    if not key:
        raise CaptureError(f"{spec.key_env} is not set")
    secrets = [key, *(env.get(name, "") for name in sorted(secret_envs()))]

    calls = spec.calls(movie, tv)
    answers: list[tuple[str, Call, requests.Response]] = [(c.name, c, _request(session, spec, c, key)) for c in calls]
    auth_call = calls[-1]
    answers.append(("error-auth", auth_call, _request(session, spec, auth_call, INVALID_KEY)))

    rendered: list[tuple[Path, str]] = []
    index: dict[str, Any] = {}
    for name, call, response in answers:
        file_name = f"{name}.{spec.extension}"
        body = redact(response.text, secrets)
        check(body, secrets)
        rendered.append((out_dir / file_name, body))
        index[file_name] = {
            "request": redact(f"GET {call.path}?" + "&".join(f"{k}={v}" for k, v in call.params.items()), secrets),
            "auth": f"{spec.auth} {spec.auth_name}",
            "status": response.status_code,
            "content_type": response.headers.get("Content-Type", ""),
        }
    index_text = json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    check(index_text, secrets)
    rendered.append((out_dir / "index.json", index_text))

    out_dir.mkdir(parents=True, exist_ok=True)
    for path, text in rendered:
        path.write_text(text, encoding="utf-8")
    say(f"recorded {len(rendered)} redacted files in {out_dir}")
    return [path for path, _ in rendered]


def main(argv: list[str] | None = None) -> int:
    """Parses the arguments and captures one tracker.

    Args:
        argv: The arguments (``sys.argv[1:]`` when None).

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tracker", choices=sorted(TRACKERS))
    parser.add_argument("--movie", default="Inception", help="the movie search's query")
    parser.add_argument("--tv", default="The Office", help="the TV search's query")
    parser.add_argument("--out", type=Path, default=None, help="fixtures directory (default: _samples/<tracker>)")
    args = parser.parse_args(argv)
    from dotenv import load_dotenv

    load_dotenv()
    try:
        with requests.Session() as session:
            capture(
                args.tracker,
                session=session,
                env=os.environ,
                out_dir=args.out or SAMPLES_ROOT / args.tracker,
                movie=args.movie,
                tv=args.tv,
            )
    except CaptureError as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
