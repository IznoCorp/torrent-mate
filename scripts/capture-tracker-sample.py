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

**Every key and passkey is redacted** before anything is written: each secret read
from the environment is replaced wherever it appears (bodies, recorded request
paths), and every URL query parameter whose name says « key », « pass » or
« token » loses its value whatever it is — an enclosure link may carry a
per-user secret this script was never told about. A final scan refuses the WHOLE
set when a known secret survives: nothing is written, and the refusal names no
secret.

Usage (his hand only):
    python scripts/capture-tracker-sample.py <tracker> [--movie "Inception"] [--tv "The Office"]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

SAMPLES_ROOT = Path(__file__).resolve().parents[1] / "docs" / "reference" / "_samples"
_TIMEOUT: tuple[float, float] = (5.0, 30.0)
#: Sent instead of the real key, once, to record the auth failure.
INVALID_KEY = "invalid-key-for-the-auth-capture"
REDACTED = "REDACTED"
#: A URL query parameter whose NAME marks a secret: its value goes, whatever it is.
_SECRET_PARAM = re.compile(
    r"(?P<name>[?&](?:amp;)?[A-Za-z_]*(?:key|pass|token|auth|rss)[A-Za-z_]*=)(?P<value>[^&\"'<>\s]+)", re.IGNORECASE
)


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


def redact(text: str, secrets: list[str]) -> str:
    """Removes every known secret and every secret-named URL parameter's value.

    Args:
        text: A body or a recorded request path.
        secrets: The secrets read from the environment.

    Returns:
        The redacted text.
    """
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    return _SECRET_PARAM.sub(lambda m: m.group("name") + REDACTED, text)


def check(text: str, secrets: list[str]) -> None:
    """Refuses a text in which a known secret remains.

    Args:
        text: A file's full text as it would be written.
        secrets: The secrets read from the environment.

    Raises:
        RedactionLeak: A secret survived (the secret itself is not in the message).
    """
    if any(secret and secret in text for secret in secrets):
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
    # Every tracker's secrets, not only this one's: an answer may echo any key the
    # operator holds (a cross-posted release, a shared announce), and redacting a
    # value that never appears costs nothing.
    secret_envs = {name for t in TRACKERS.values() for name in (t.key_env, *t.extra_secret_envs)}
    secrets = [key, *(env.get(name, "") for name in sorted(secret_envs))]

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
