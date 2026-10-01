#!/usr/bin/env python3
"""Probe the plex.tv account sign-in by hand, and record its answers as redacted fixtures.

The Plex SSO brick (``docs/features/backend-bricks/plex-sso/DESIGN.md``) talks to
plex.tv with a PIN, a user token, the user's identity and the user's resources.
None of those answers is public in full, and no session holds a Plex account, so
the OPERATOR runs this probe: it is both his end-to-end check and the capture of
the fixtures the client's unit tests read.

What one run does, with raw ``requests`` (the client does not exist yet):

1. creates a strong PIN and prints the sign-in URL — he opens it and signs in;
2. checks the PIN once per second until it is claimed or expired;
3. reads the identity behind the token and prints ``plex_id`` and ``title`` only;
4. reads the account's resources and prints its access to THIS server
   (``owner`` / ``shared`` / ``none``), the server named by ``GET <PLEX_URL>/identity``
   with the existing ``PLEX_TOKEN``.

With ``--record`` it also writes every answer to ``docs/reference/_samples/plex-account/``
after REDACTION, plus a ``user`` 401 (a deliberately invalid token) and an
expired PIN (``--record-expired``, which waits out a fresh unclaimed PIN).

**Redaction is the whole point of the record path.** Every token, PIN code,
e-mail, account / resource id, uuid, name, address and URL is replaced by a
placeholder, CONSISTENTLY — one real value maps to one placeholder across every
file, so the server's ``machineIdentifier`` still equals its resource's
``clientIdentifier`` and the fixtures stay usable. A final scan refuses to write
any file in which a collected secret still appears, whatever key carried it.

**The user's token never leaves this process's memory**: it is sent in the
``X-Plex-Token`` header only, never printed, never logged, never written;
redirects are not followed (``requests`` strips only ``Authorization`` on a
cross-host redirect).

Usage (his hand only — it calls plex.tv and reads ``PLEX_URL`` / ``PLEX_TOKEN``):
    python scripts/plex-signin-probe.py [--record] [--record-expired]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

PLEX_TV = "https://plex.tv"
PLEX_AUTH_APP = "https://app.plex.tv/auth"
PRODUCT = "TorrentMate (probe)"
SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "reference" / "_samples" / "plex-account"
#: The probe's own client identifier, generated once and re-used (Plex's article: one per application).
CLIENT_ID_FILE = Path.home() / ".torrentmate" / "plex-probe-client-identifier"
_TIMEOUT: tuple[float, float] = (5.0, 15.0)
#: Plex's own polling cadence for a PIN.
_POLL_SECONDS = 1.0
#: How long the claim is awaited before giving up; the PIN's real lifetime is read from the capture.
_CLAIM_WAIT_SECONDS = 300.0
#: How long ``--record-expired`` waits a fresh unclaimed PIN out, polling gently.
_EXPIRE_WAIT_SECONDS = 3600.0
_EXPIRE_POLL_SECONDS = 30.0
#: An invalid token, sent once to record plex.tv's 401.
_INVALID_TOKEN = "invalid-token-for-the-401-capture"

#: Keys whose value is replaced wherever they appear, by placeholder family.
_SECRET_KEYS: Mapping[str, str] = {
    "authToken": "token",
    "accessToken": "token",
    "token": "token",
    "code": "code",
    "email": "email",
    "id": "id",
    "ownerId": "id",
    "sourceTitle": "name",
    "uuid": "uuid",
    "clientIdentifier": "machine",
    "machineIdentifier": "machine",
    "username": "name",
    "title": "name",
    "friendlyName": "name",
    "name": "name",
    "thumb": "url",
    "uri": "url",
    "address": "address",
    "publicAddress": "address",
    "localAddresses": "address",
    "host": "address",
    "clientIdentifierHash": "machine",
    "subscriptionId": "id",
    "joinedAt": "time",
    "lastSeenAt": "time",
}


class ProbeError(Exception):
    """The probe cannot go on; its text never carries a token, a code or an e-mail."""


class RedactionLeak(ProbeError):
    """A collected secret survived redaction — nothing is written."""


@dataclass
class Redactor:
    """Replaces secrets consistently: one real value, one placeholder, across every file.

    Attributes:
        secrets: Every real value seen under a secret key, plus those planted by the caller
            (the user's token, the server token) — the final scan looks for each of them.
        mapping: Real value → its placeholder.
    """

    secrets: set[str] = field(default_factory=set)
    mapping: dict[Any, Any] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def remember(self, value: str | None) -> None:
        """Adds a secret that must never appear in a written file, whatever key carries it.

        Args:
            value: The secret; empty or None is ignored.
        """
        if value:
            self.secrets.add(str(value))

    def _placeholder(self, family: str, value: Any) -> Any:
        """Returns the placeholder of one value, creating it at first sight.

        Args:
            family: The placeholder family (``token``, ``id``, ``machine``…).
            value: The real value.

        Returns:
            An int for an int (ids stay ints, so parsers are exercised), a bool kept as is,
            else a ``REDACTED-<family>-<n>`` string.
        """
        if isinstance(value, bool) or value is None:
            return value
        key = (family, value) if not isinstance(value, str) else value
        if key in self.mapping:
            return self.mapping[key]
        n = self._counters.get(family, 0) + 1
        self._counters[family] = n
        if isinstance(value, int):
            placeholder: Any = 900_000 + n
        elif isinstance(value, float):
            placeholder = 1_700_000_000.0 + n
        elif family == "email":
            placeholder = f"redacted-{n}@example.invalid"
        elif family == "url":
            placeholder = f"https://redacted.invalid/{family}-{n}"
        else:
            placeholder = f"REDACTED-{family}-{n}"
        self.mapping[key] = placeholder
        if isinstance(value, str) and len(value) >= 4:
            self.secrets.add(value)
        return placeholder

    def redact(self, node: Any, family: str | None = None) -> Any:
        """Returns a redacted copy of a JSON node.

        Args:
            node: A parsed JSON value.
            family: The placeholder family inherited from the parent key, if secret.

        Returns:
            The node with every value under a secret key replaced.
        """
        if isinstance(node, dict):
            return {k: self.redact(v, _SECRET_KEYS.get(k)) for k, v in node.items()}
        if isinstance(node, list):
            return [self.redact(v, family) for v in node]
        if family == "time":
            return 1_700_000_000 if isinstance(node, (int, float)) and not isinstance(node, bool) else node
        if family is not None:
            return self._placeholder(family, node)
        return node

    def scrub_tree(self, node: Any) -> Any:
        """Scrubs every string of an already-redacted tree, once every secret is known.

        Args:
            node: A redacted JSON value.

        Returns:
            The value with every known secret substring replaced in its strings and keys.
        """
        if isinstance(node, dict):
            return {self.scrub(k): self.scrub_tree(v) for k, v in node.items()}
        if isinstance(node, list):
            return [self.scrub_tree(v) for v in node]
        if isinstance(node, str):
            return self.scrub(node)
        return node

    def scrub(self, text: str) -> str:
        """Replaces every already-known secret inside free text (a URL carrying a token…).

        Args:
            text: Any string.

        Returns:
            The string with each known secret substring replaced by its placeholder.
        """
        for secret in sorted(self.secrets, key=len, reverse=True):
            if secret in text:
                text = text.replace(secret, str(self.mapping.get(secret, "REDACTED")))
        return text

    def check(self, text: str) -> None:
        """Refuses a serialized file in which any collected secret remains.

        Args:
            text: The file's full text, as it would be written.

        Raises:
            RedactionLeak: A secret is still present (the secret itself is NOT in the message).
        """
        for secret in self.secrets:
            if secret and secret in text:
                raise RedactionLeak("a collected secret survived redaction; nothing written")


@dataclass(frozen=True)
class Answer:
    """One recorded answer: what was asked and what came back, before redaction.

    Attributes:
        name: The fixture's file stem (``pin-created``, ``user-200``…).
        method: HTTP method.
        path: The path asked (no query string carrying anything secret).
        status: HTTP status.
        body: The parsed JSON body, or the raw text when not JSON.
    """

    name: str
    method: str
    path: str
    status: int
    body: Any


def _headers(client_id: str, token: str | None = None) -> dict[str, str]:
    """Builds plex.tv's headers.

    Args:
        client_id: The probe's ``X-Plex-Client-Identifier``.
        token: A Plex token, sent in ``X-Plex-Token`` only — never in a URL.

    Returns:
        The header dict.
    """
    headers = {"Accept": "application/json", "X-Plex-Product": PRODUCT, "X-Plex-Client-Identifier": client_id}
    if token:
        headers["X-Plex-Token"] = token
    return headers


def _body(response: requests.Response) -> Any:
    """Parses a body as JSON, else keeps its text.

    Args:
        response: The answer.

    Returns:
        The JSON value or the raw text.
    """
    try:
        return response.json()
    except ValueError:
        return response.text


def _call(
    session: requests.Session,
    method: str,
    url: str,
    *,
    client_id: str,
    token: str | None = None,
    params: Mapping[str, Any] | None = None,
) -> requests.Response:
    """One request; a failure is re-raised as ``ProbeError`` naming only the exception type.

    Args:
        session: The HTTP session.
        method: ``GET`` or ``POST``.
        url: The absolute URL (never carrying a token).
        client_id: The probe's client identifier.
        token: The token for ``X-Plex-Token``.
        params: Query parameters (never a token).

    Returns:
        The response.

    Raises:
        ProbeError: No answer (the token-bearing exception is not chained).
    """
    try:
        return session.request(
            method, url, headers=_headers(client_id, token), params=params, timeout=_TIMEOUT, allow_redirects=False
        )
    except Exception as exc:  # noqa: BLE001 — a token-bearing frame must not escape
        raise ProbeError(f"{method} {url.split('?')[0]} failed: {type(exc).__name__}") from None


def sign_in_url(client_id: str, code: str) -> str:
    """Builds the URL the operator opens to claim the PIN.

    Args:
        client_id: The probe's client identifier.
        code: The PIN code.

    Returns:
        ``https://app.plex.tv/auth#?clientID=…&code=…&context%5Bdevice%5D%5Bproduct%5D=…``.
    """
    query = urlencode({"clientID": client_id, "code": code, "context[device][product]": PRODUCT})
    return f"{PLEX_AUTH_APP}#?{query}"


def access_to(resources: Any, machine_identifier: str) -> str:
    """Tells what an account is to this server, from its resource list.

    Args:
        resources: ``GET /api/v2/resources`` body (a list of resources).
        machine_identifier: This server's ``machineIdentifier``.

    Returns:
        ``owner``, ``shared`` or ``none``.
    """
    for resource in resources if isinstance(resources, list) else []:
        if isinstance(resource, dict) and resource.get("clientIdentifier") == machine_identifier:
            return "owner" if resource.get("owned") in (True, 1, "1") else "shared"
    return "none"


def run(
    *,
    session: requests.Session,
    env: Mapping[str, str],
    client_id: str,
    record: bool,
    record_expired: bool,
    out_dir: Path,
    say: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Runs the probe once.

    Args:
        session: The HTTP session (a fake one in tests).
        env: Where ``PLEX_URL`` and ``PLEX_TOKEN`` are read.
        client_id: The probe's client identifier.
        record: Write the redacted answers to ``out_dir``.
        record_expired: Also wait out a fresh unclaimed PIN and record its expired answer.
        out_dir: Where the fixtures go.
        say: Where the operator reads the progress (never a token, code-free except the sign-in URL).
        sleep: Waits between polls.
        clock: Measures the waits.

    Returns:
        The process exit code: 0 on success.

    Raises:
        ProbeError: plex.tv or the server did not answer as the protocol says.
    """
    plex_url = env.get("PLEX_URL", "").rstrip("/")
    server_token = env.get("PLEX_TOKEN", "")
    if not plex_url or not server_token:
        raise ProbeError("PLEX_URL and PLEX_TOKEN must be set (the server's identity is read with them)")
    redactor = Redactor()
    redactor.remember(server_token)
    redactor.remember(client_id)
    answers: list[Answer] = []

    identity = _call(session, "GET", f"{plex_url}/identity", client_id=client_id, token=server_token)
    identity_body = _body(identity)
    answers.append(Answer("server-identity", "GET", "/identity", identity.status_code, identity_body))
    try:
        machine_identifier = str(identity_body["MediaContainer"]["machineIdentifier"])
    except (KeyError, TypeError) as exc:
        raise ProbeError(f"the server's /identity carries no machineIdentifier (HTTP {identity.status_code})") from exc

    created = _call(session, "POST", f"{PLEX_TV}/api/v2/pins", client_id=client_id, params={"strong": "true"})
    pin = _body(created)
    answers.append(Answer("pin-created", "POST", "/api/v2/pins?strong=true", created.status_code, pin))
    if created.status_code not in (200, 201) or not isinstance(pin, dict) or "id" not in pin:
        raise ProbeError(f"plex.tv refused the PIN (HTTP {created.status_code})")
    pin_id, code = pin["id"], str(pin["code"])
    redactor.remember(code)
    say("Open this URL and sign in with your Plex account:")
    say(sign_in_url(client_id, code))

    token: str | None = None
    pending_recorded = False
    deadline = clock() + _CLAIM_WAIT_SECONDS
    while clock() < deadline:
        polled = _call(session, "GET", f"{PLEX_TV}/api/v2/pins/{pin_id}", client_id=client_id, params={"code": code})
        body = _body(polled)
        if polled.status_code != 200 or not isinstance(body, dict):
            answers.append(Answer("pin-refused", "GET", "/api/v2/pins/{id}", polled.status_code, body))
            raise ProbeError(f"plex.tv answered the PIN check with HTTP {polled.status_code}")
        if body.get("authToken"):
            token = str(body["authToken"])
            redactor.remember(token)
            answers.append(Answer("pin-claimed", "GET", "/api/v2/pins/{id}", polled.status_code, body))
            break
        if not pending_recorded:
            answers.append(Answer("pin-pending", "GET", "/api/v2/pins/{id}", polled.status_code, body))
            pending_recorded = True
        sleep(_POLL_SECONDS)
    if token is None:
        raise ProbeError("the PIN was not claimed in time")

    user = _call(session, "GET", f"{PLEX_TV}/api/v2/user", client_id=client_id, token=token)
    user_body = _body(user)
    answers.append(Answer("user-200", "GET", "/api/v2/user", user.status_code, user_body))
    if user.status_code != 200 or not isinstance(user_body, dict):
        raise ProbeError(f"plex.tv answered the identity read with HTTP {user.status_code}")
    redactor.remember(str(user_body.get("email") or ""))
    say(f"plex_id={user_body.get('id')} title={user_body.get('title')}")

    resources = _call(
        session, "GET", f"{PLEX_TV}/api/v2/resources", client_id=client_id, token=token, params={"includeHttps": "1"}
    )
    resources_body = _body(resources)
    access = access_to(resources_body, machine_identifier)
    answers.append(
        Answer(f"resources-{access}", "GET", "/api/v2/resources?includeHttps=1", resources.status_code, resources_body)
    )
    say(f"access={access}")

    if record:
        refused = _call(session, "GET", f"{PLEX_TV}/api/v2/user", client_id=client_id, token=_INVALID_TOKEN)
        answers.append(Answer("user-401", "GET", "/api/v2/user", refused.status_code, _body(refused)))
        if record_expired:
            answers.append(_wait_out_a_pin(session, client_id, redactor, say=say, sleep=sleep, clock=clock))
        write_samples(answers, redactor, out_dir)
        say(f"recorded {len(answers)} redacted answers in {out_dir}")
    return 0


def _wait_out_a_pin(
    session: requests.Session,
    client_id: str,
    redactor: Redactor,
    *,
    say: Callable[[str], None],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> Answer:
    """Creates a PIN nobody claims and polls it until plex.tv stops answering it as pending.

    Args:
        session: The HTTP session.
        client_id: The probe's client identifier.
        redactor: Learns the PIN code.
        say: Progress output.
        sleep: Waits between polls.
        clock: Measures the wait.

    Returns:
        The first non-pending answer, recorded as ``pin-expired``.

    Raises:
        ProbeError: The PIN was still pending after ``_EXPIRE_WAIT_SECONDS``.
    """
    created = _call(session, "POST", f"{PLEX_TV}/api/v2/pins", client_id=client_id, params={"strong": "true"})
    pin = _body(created)
    if not isinstance(pin, dict) or "id" not in pin:
        raise ProbeError(f"plex.tv refused the second PIN (HTTP {created.status_code})")
    redactor.remember(str(pin["code"]))
    say("Waiting a fresh PIN out (do NOT open it)…")
    deadline = clock() + _EXPIRE_WAIT_SECONDS
    while clock() < deadline:
        polled = _call(
            session, "GET", f"{PLEX_TV}/api/v2/pins/{pin['id']}", client_id=client_id, params={"code": pin["code"]}
        )
        body = _body(polled)
        if polled.status_code != 200 or not isinstance(body, dict) or body.get("authToken"):
            return Answer("pin-expired", "GET", "/api/v2/pins/{id}", polled.status_code, body)
        sleep(_EXPIRE_POLL_SECONDS)
    raise ProbeError("the unclaimed PIN was still pending when the wait ended")


def write_samples(answers: list[Answer], redactor: Redactor, out_dir: Path) -> list[Path]:
    """Redacts every answer, scans it, and only then writes the files.

    The scan runs over EVERY file before the first one is written, so a leak in the last
    answer leaves no partial set on disk.

    Args:
        answers: The recorded answers.
        redactor: The redactor that saw the secrets.
        out_dir: The fixtures directory.

    Returns:
        The written paths.

    Raises:
        RedactionLeak: A collected secret survived; nothing is written.
    """
    # Redact every body first, so every secret is known before any free text is scrubbed:
    # a URL in the first answer may carry an identifier only the last answer names.
    redacted = [(a, redactor.redact(a.body)) for a in answers]
    rendered: list[tuple[Path, str]] = []
    for answer, body in redacted:
        payload = {
            "request": {"method": answer.method, "path": answer.path},
            "status": answer.status,
            "body": redactor.scrub_tree(body),
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        redactor.check(text)
        rendered.append((out_dir / f"{answer.name}.json", text))
    out_dir.mkdir(parents=True, exist_ok=True)
    for path, text in rendered:
        path.write_text(text, encoding="utf-8")
    return [path for path, _ in rendered]


def _client_identifier() -> str:
    """Reads the probe's client identifier, generating it once.

    Returns:
        A uuid string persisted in ``CLIENT_ID_FILE``.
    """
    if CLIENT_ID_FILE.is_file():
        return CLIENT_ID_FILE.read_text(encoding="utf-8").strip()
    CLIENT_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = str(uuid.uuid4())
    CLIENT_ID_FILE.write_text(value + "\n", encoding="utf-8")
    CLIENT_ID_FILE.chmod(0o600)
    return value


def main(argv: list[str] | None = None) -> int:
    """Parses the arguments and runs the probe against plex.tv.

    Args:
        argv: The arguments (``sys.argv[1:]`` when None).

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true", help="write the redacted answers as fixtures")
    parser.add_argument("--record-expired", action="store_true", help="with --record, also wait out an unclaimed PIN")
    parser.add_argument("--out", type=Path, default=SAMPLES_DIR, help="fixtures directory")
    args = parser.parse_args(argv)
    from dotenv import load_dotenv

    load_dotenv()
    try:
        with requests.Session() as session:
            return run(
                session=session,
                env=os.environ,
                client_id=_client_identifier(),
                record=args.record,
                record_expired=args.record and args.record_expired,
                out_dir=args.out,
            )
    except ProbeError as exc:
        print(f"probe failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
