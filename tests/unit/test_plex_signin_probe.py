"""Unit tests for ``scripts/plex-signin-probe.py`` — above all, its redaction.

The probe is the operator's hand on plex.tv: its record path writes plex.tv's answers
into the repository as fixtures. Those answers carry his Plex token, the PIN code, his
e-mail, his account id and uuid, the server's identifier and its addresses. Every test
here plants recognisable values in fake answers and proves none of them reaches a
written file or the console — and that the redaction stays CONSISTENT, so the fixtures
remain usable (the server's identifier still matches its resource).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "plex-signin-probe.py"


def _load() -> Any:
    """Imports the probe as a module, despite its hyphenated filename.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("plex_signin_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules while the class is built.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = _load()

TOKEN = "PLANTED-user-token-7f3a9c"
SERVER_TOKEN = "PLANTED-server-token-91bd"
RESOURCE_TOKEN = "PLANTED-resource-token-55e1"
CODE = "plantedcode0123456789abcd"
EXPIRED_CODE = "plantedexpired9876543210zz"
EMAIL = "planted.person@example.com"
USER_ID = 48151623
PIN_ID = 77001122
UUID = "planted-uuid-0000-1111"
MACHINE = "plantedmachine0123456789abcdef"
CLIENT_ID = "planted-client-identifier-42"
USERNAME = "planted-username"
TITLE = "Planted Title"
PLEX_URL = "http://planted-server.local:32400"

PLANTED_STRINGS = (
    TOKEN,
    SERVER_TOKEN,
    RESOURCE_TOKEN,
    CODE,
    EXPIRED_CODE,
    EMAIL,
    UUID,
    MACHINE,
    CLIENT_ID,
    USERNAME,
    TITLE,
    str(USER_ID),
    str(PIN_ID),
    "planted-server.local",
    "192-168-1-2",
)


class _Response:
    """A minimal ``requests.Response`` stand-in."""

    def __init__(self, status: int, body: Any) -> None:
        """Builds the answer.

        Args:
            status: HTTP status.
            body: JSON body, or a string for a non-JSON body.
        """
        self.status_code = status
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self) -> Any:
        """Returns the JSON body.

        Raises:
            ValueError: The body is not JSON.
        """
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


class _FakePlex:
    """Answers the probe's requests as plex.tv and the server would, with planted values."""

    def __init__(self, *, owned: int = 1, polls_before_claim: int = 1) -> None:
        """Builds the fake.

        Args:
            owned: ``owned`` of this server's resource (1 owner, 0 shared).
            polls_before_claim: How many pending answers precede the claimed one.
        """
        self.calls: list[dict[str, Any]] = []
        self.owned = owned
        self.pending_left = polls_before_claim
        self.pins_created = 0

    def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        """Records the call and routes it.

        Args:
            method: HTTP method.
            url: Absolute URL.
            **kwargs: ``headers``, ``params``, ``timeout``, ``allow_redirects``.

        Returns:
            The fake answer.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        headers = kwargs.get("headers") or {}
        if url == f"{PLEX_URL}/identity":
            return _Response(200, {"MediaContainer": {"size": 0, "machineIdentifier": MACHINE, "version": "1.40"}})
        if method == "POST" and url.endswith("/api/v2/pins"):
            self.pins_created += 1
            if self.pins_created == 1:
                return _Response(201, {"id": PIN_ID, "code": CODE, "authToken": None, "expiresIn": 1800})
            return _Response(201, {"id": PIN_ID + 1, "code": EXPIRED_CODE, "authToken": None})
        if url.endswith(f"/api/v2/pins/{PIN_ID}"):
            if self.pending_left > 0:
                self.pending_left -= 1
                return _Response(200, {"id": PIN_ID, "code": CODE, "authToken": None})
            return _Response(200, {"id": PIN_ID, "code": CODE, "authToken": TOKEN, "clientIdentifier": CLIENT_ID})
        if url.endswith(f"/api/v2/pins/{PIN_ID + 1}"):
            return _Response(404, {"errors": [{"code": 1020, "message": "Code not found or expired"}]})
        if url.endswith("/api/v2/user"):
            if headers.get("X-Plex-Token") != TOKEN:
                return _Response(401, {"errors": [{"code": 1001, "message": "User could not be authenticated"}]})
            return _Response(
                200,
                {
                    "id": USER_ID,
                    "uuid": UUID,
                    "username": USERNAME,
                    "title": TITLE,
                    "email": EMAIL,
                    "thumb": f"https://plex.tv/users/{UUID}/avatar?c=1",
                    "authToken": TOKEN,
                    "subscription": {"active": True, "id": 31337},
                    "note": f"free text that happens to carry {TOKEN} and {EMAIL}",
                },
            )
        if url.endswith("/api/v2/resources"):
            return _Response(
                200,
                [
                    {
                        "name": "Planted Server Name",
                        "clientIdentifier": MACHINE,
                        "owned": self.owned,
                        "ownerId": None if self.owned else 999,
                        "provides": "server",
                        "accessToken": RESOURCE_TOKEN,
                        "publicAddress": "203.0.113.9",
                        "connections": [
                            {
                                "protocol": "https",
                                "address": "192.168.1.2",
                                "port": 32400,
                                "local": True,
                                "uri": f"https://192-168-1-2.{MACHINE}.plex.direct:32400",
                            }
                        ],
                    },
                    {
                        "name": "Someone Else's",
                        "clientIdentifier": "other-machine-xyz",
                        "owned": 0,
                        "provides": "server",
                    },
                ],
            )
        raise AssertionError(f"unexpected call {method} {url}")


def _run(tmp_path: Path, fake: _FakePlex, *, record: bool = True, record_expired: bool = True) -> list[str]:
    """Runs the probe on a fake plex.tv with a frozen clock.

    Args:
        tmp_path: Output directory root.
        fake: The fake session.
        record: Pass ``--record``.
        record_expired: Pass ``--record-expired``.

    Returns:
        Every line the probe printed.
    """
    said: list[str] = []
    now = [0.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    probe.run(
        session=fake,
        env={"PLEX_URL": PLEX_URL, "PLEX_TOKEN": SERVER_TOKEN},
        client_id=CLIENT_ID,
        record=record,
        record_expired=record_expired,
        out_dir=tmp_path / "plex-account",
        say=said.append,
        sleep=sleep,
        clock=lambda: now[0],
    )
    return said


def _files(tmp_path: Path) -> dict[str, str]:
    """Reads every written fixture.

    Args:
        tmp_path: Output directory root.

    Returns:
        File name → text.
    """
    return {p.name: p.read_text(encoding="utf-8") for p in sorted((tmp_path / "plex-account").glob("*.json"))}


def test_record_writes_every_documented_answer(tmp_path: Path) -> None:
    """The record path writes the captures the client's tests will read (DESIGN § 4)."""
    _run(tmp_path, _FakePlex())
    assert set(_files(tmp_path)) == {
        "server-identity.json",
        "pin-created.json",
        "pin-pending.json",
        "pin-claimed.json",
        "user-200.json",
        "user-401.json",
        "resources-owner.json",
        "pin-expired.json",
    }


def test_no_planted_value_reaches_a_written_file(tmp_path: Path) -> None:
    """Token, code, e-mail, ids, uuid, machine id, names and addresses: all redacted, in every file."""
    _run(tmp_path, _FakePlex())
    for name, text in _files(tmp_path).items():
        for planted in PLANTED_STRINGS:
            assert planted not in text, f"{planted!r} leaked into {name}"


def test_redaction_is_consistent_across_files(tmp_path: Path) -> None:
    """The server's identifier still matches its resource, so the fixtures still decide OWNER."""
    _run(tmp_path, _FakePlex())
    files = {name: json.loads(text) for name, text in _files(tmp_path).items()}
    machine = files["server-identity.json"]["body"]["MediaContainer"]["machineIdentifier"]
    resources = files["resources-owner.json"]["body"]
    assert machine != MACHINE
    assert probe.access_to(resources, machine) == "owner"
    pin_ids = {files[n]["body"]["id"] for n in ("pin-created.json", "pin-pending.json", "pin-claimed.json")}
    assert len(pin_ids) == 1 and isinstance(next(iter(pin_ids)), int)
    assert isinstance(files["user-200.json"]["body"]["id"], int)
    assert files["user-200.json"]["body"]["email"].endswith("@example.invalid")
    assert files["pin-claimed.json"]["body"]["authToken"].startswith("REDACTED-token-")
    assert files["user-401.json"]["status"] == 401
    assert files["pin-expired.json"]["status"] == 404


def test_shared_account_is_recorded_as_shared(tmp_path: Path) -> None:
    """A household member's run (``owned == 0``) records ``resources-shared``."""
    said = _run(tmp_path, _FakePlex(owned=0), record_expired=False)
    assert "resources-shared.json" in _files(tmp_path)
    assert "access=shared" in said


def test_console_never_shows_a_token_or_the_email(tmp_path: Path) -> None:
    """The operator reads the sign-in URL, his id and title — never a token or the e-mail."""
    said = "\n".join(_run(tmp_path, _FakePlex()))
    for secret in (TOKEN, SERVER_TOKEN, RESOURCE_TOKEN, EMAIL, UUID):
        assert secret not in said
    assert f"plex_id={USER_ID}" in said and "access=owner" in said


def test_tokens_travel_in_the_header_only_and_no_redirect_is_followed(tmp_path: Path) -> None:
    """Never a token in a URL or the query; ``allow_redirects=False`` on every call."""
    fake = _FakePlex()
    _run(tmp_path, fake)
    for call in fake.calls:
        assert call["allow_redirects"] is False
        visible = call["url"] + json.dumps(call.get("params") or {})
        for secret in (TOKEN, SERVER_TOKEN):
            assert secret not in visible
    tokens_sent = {call["headers"].get("X-Plex-Token") for call in fake.calls}
    assert {TOKEN, SERVER_TOKEN} <= tokens_sent


def test_without_record_nothing_is_written(tmp_path: Path) -> None:
    """The plain E2E run writes no file."""
    _run(tmp_path, _FakePlex(), record=False)
    assert not (tmp_path / "plex-account").exists()


def test_a_leak_writes_nothing_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When a secret survives (scrub broken), the scan refuses the WHOLE set, and says no secret."""
    monkeypatch.setattr(probe.Redactor, "scrub", lambda self, text: text)
    with pytest.raises(probe.RedactionLeak) as caught:
        _run(tmp_path, _FakePlex())
    assert not (tmp_path / "plex-account").exists()
    assert all(secret not in str(caught.value) for secret in PLANTED_STRINGS)


def test_a_failed_call_names_the_exception_type_only(tmp_path: Path) -> None:
    """A connection error whose text carries the token is re-raised without it, unchained."""

    class _Exploding(_FakePlex):
        def request(self, method: str, url: str, **kwargs: Any) -> _Response:
            raise requests.ConnectionError(f"boom with {kwargs['headers'].get('X-Plex-Token')}")

    with pytest.raises(probe.ProbeError) as caught:
        _run(tmp_path, _Exploding())
    assert "ConnectionError" in str(caught.value)
    assert SERVER_TOKEN not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_missing_server_settings_stop_before_any_call(tmp_path: Path) -> None:
    """Without ``PLEX_URL`` / ``PLEX_TOKEN`` nothing is called."""
    fake = _FakePlex()
    with pytest.raises(probe.ProbeError):
        probe.run(
            session=fake,
            env={},
            client_id=CLIENT_ID,
            record=False,
            record_expired=False,
            out_dir=tmp_path,
            say=lambda _: None,
        )
    assert fake.calls == []


@pytest.mark.parametrize(
    ("resources", "expected"),
    [
        ([{"clientIdentifier": "m", "owned": 1}], "owner"),
        ([{"clientIdentifier": "m", "owned": True}], "owner"),
        ([{"clientIdentifier": "m", "owned": 0}], "shared"),
        ([{"clientIdentifier": "other", "owned": 1}], "none"),
        ([], "none"),
        ({"not": "a list"}, "none"),
    ],
)
def test_access_to(resources: Any, expected: str) -> None:
    """OWNER / SHARED / NONE from a resource list, NONE when the list is empty or malformed."""
    assert probe.access_to(resources, "m") == expected


def test_sign_in_url_carries_the_three_parameters() -> None:
    """The URL Plex's article documents, URL-encoded."""
    url = probe.sign_in_url("cid", "abc")
    assert url.startswith("https://app.plex.tv/auth#?")
    assert "clientID=cid" in url and "code=abc" in url
    assert "context%5Bdevice%5D%5Bproduct%5D=TorrentMate+%28probe%29" in url
