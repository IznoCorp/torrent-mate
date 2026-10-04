"""Unit tests for ``personalscraper.api.plex_account`` and ``PlexClient.machine_identifier``.

The plex-sso brick (``docs/features/backend-bricks/plex-sso/DESIGN.md`` § 4): every answer is
one the operator recorded with ``scripts/plex-signin-probe.py --record``
(``docs/reference/_samples/plex-account/``), replayed by a fake session — no test reaches
plex.tv or the Plex server. Two answers are NOT recorded and are said so where they are built:
the expired PIN (the operator ran no ``--record-expired``; the 404 is inferred) and a Plex Home
member's resources (``resources-home-derived.json``, derived from the owner's capture).

What they pin: the right URL, headers and token placement on every request; each answer →
its type; only a 401 is a refusal, every other failure is « unreachable »; and the user's
token, the PIN code and the e-mail never reach a log record, a rendered console line, an
exception text or a ``repr``.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import structlog

import personalscraper.api.plex_account as _plex_account
from personalscraper.api.plex import PlexClient
from personalscraper.api.plex_account import (
    PlexAccount,
    PlexAccountClient,
    PlexAccountError,
    PlexAccountUnreachable,
    PlexPin,
    PlexPinExpired,
    PlexServerAccess,
    PlexTokenRefused,
)

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "plex-account"

PRODUCT = "TorrentMate (test)"
CLIENT_ID = "test-client-identifier-0b1c"
#: The planted secrets of the leak suite: none may reach a log, an exception text or a repr.
TOKEN = "PLANTED-plex-user-token-31f7"
CODE = "plantedpincode0123456789ab"
EMAIL = "planted.person@example.com"
SERVER_TOKEN = "PLANTED-server-token-c4d2"
#: This server's machineIdentifier as the captures redact it (``server-identity.json``).
MACHINE = "REDACTED-machine-1"
#: A server the owner's account reaches without owning it (``resources-owner.json``, real capture).
SHARED_MACHINE = "REDACTED-machine-3"


def _sample(name: str) -> dict[str, Any]:
    """Read one recorded capture.

    Args:
        name: The fixture's stem (``pin-created``, ``user-200``…).

    Returns:
        The capture: ``request``, ``status`` and ``body``.
    """
    data: dict[str, Any] = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return data


class _Response:
    """A minimal ``requests.Response`` stand-in."""

    def __init__(self, status: int, body: Any) -> None:
        """Build the answer.

        Args:
            status: HTTP status.
            body: A JSON value, or a ``str`` for a non-JSON body.
        """
        self.status_code = status
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self) -> Any:
        """Return the JSON body.

        Raises:
            ValueError: The body is not JSON.
        """
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


def _answer(name: str) -> _Response:
    """Replay one capture as a response.

    Args:
        name: The fixture's stem.

    Returns:
        Its status and body.
    """
    sample = _sample(name)
    return _Response(sample["status"], sample["body"])


class _Session:
    """Records every request and replays canned answers in order."""

    def __init__(self, *answers: Any) -> None:
        """Queue the answers.

        Args:
            *answers: Responses, or exceptions to raise.
        """
        self._answers = list(answers)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Record the call and return (or raise) the next answer.

        Args:
            method: HTTP method.
            url: Absolute URL.
            **kwargs: ``headers``, ``params``, ``timeout``, ``allow_redirects``.

        Returns:
            The next queued answer.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        nxt = self._answers.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt

    def get(self, url: str, **kwargs: Any) -> Any:
        """The server client's verb, routed through :meth:`request`.

        Args:
            url: Absolute URL.
            **kwargs: The request's options.

        Returns:
            The next queued answer.
        """
        return self.request("GET", url, **kwargs)


def _client(*answers: Any) -> tuple[PlexAccountClient, _Session]:
    """Build an account client over a fake session.

    Args:
        *answers: The answers it replays.

    Returns:
        The client and its session.
    """
    session = _Session(*answers)
    return PlexAccountClient(product=PRODUCT, client_identifier=CLIENT_ID, session=session), session  # type: ignore[arg-type]


def _expired_pin() -> _Response:
    """plex.tv's answer to a check of an expired PIN — NOT recorded, INFERRED.

    The operator's capture holds no ``pin-expired.json`` (no ``--record-expired`` run). The
    shape is the one the probe's own fake carries and python-plexapi's handling implies:
    a 404 with plex.tv's error envelope. The approval to read 404 / 410 as an expiry is the
    orchestrator's (2026-10-04), documented as inferred in ``plex-account-api.md``.

    Returns:
        The answer.
    """
    return _Response(404, {"errors": [{"code": 1020, "message": "Code not found or expired"}]})


# ---------------------------------------------------------------------------
# Requests: URL, headers, token placement, no redirect
# ---------------------------------------------------------------------------


class TestRequests:
    """Every request: the right URL, the three headers, the token in the header only."""

    def test_create_pin_posts_a_strong_pin(self) -> None:
        """Create pin posts a strong pin."""
        client, session = _client(_answer("pin-created"))
        client.create_pin()
        call = session.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == "https://plex.tv/api/v2/pins"
        assert call["params"] == {"strong": "true"}
        assert call["headers"] == {
            "Accept": "application/json",
            "X-Plex-Product": PRODUCT,
            "X-Plex-Client-Identifier": CLIENT_ID,
        }

    def test_check_pin_reads_the_pin_with_its_code(self) -> None:
        """Check pin reads the pin with its code."""
        client, session = _client(_answer("pin-pending"))
        client.check_pin(900001, CODE)
        call = session.calls[0]
        assert call["method"] == "GET"
        assert call["url"] == "https://plex.tv/api/v2/pins/900001"
        assert call["params"] == {"code": CODE}
        assert "X-Plex-Token" not in call["headers"]

    def test_account_reads_the_user_with_the_token_in_the_header(self) -> None:
        """Account reads the user with the token in the header."""
        client, session = _client(_answer("user-200"))
        client.account(TOKEN)
        call = session.calls[0]
        assert (call["method"], call["url"]) == ("GET", "https://plex.tv/api/v2/user")
        assert call["headers"]["X-Plex-Token"] == TOKEN
        assert call["headers"]["X-Plex-Client-Identifier"] == CLIENT_ID

    def test_server_access_reads_the_resources_with_https(self) -> None:
        """Server access reads the resources with https."""
        client, session = _client(_answer("resources-owner"))
        client.server_access(TOKEN, MACHINE)
        call = session.calls[0]
        assert (call["method"], call["url"]) == ("GET", "https://plex.tv/api/v2/resources")
        assert call["params"] == {"includeHttps": "1"}
        assert call["headers"]["X-Plex-Token"] == TOKEN

    def test_no_token_in_a_url_or_the_params_and_no_redirect_followed(self) -> None:
        """No token in a url or the params and no redirect followed."""
        client, session = _client(
            _answer("pin-created"), _answer("pin-claimed"), _answer("user-200"), _answer("resources-owner")
        )
        client.create_pin()
        client.check_pin(900001, CODE)
        client.account(TOKEN)
        client.server_access(TOKEN, MACHINE)
        for call in session.calls:
            assert call["allow_redirects"] is False
            assert call["timeout"] == _plex_account._TIMEOUT
            visible = call["url"] + json.dumps(call.get("params") or {})
            assert TOKEN not in visible


# ---------------------------------------------------------------------------
# Answers → types
# ---------------------------------------------------------------------------


class TestCreatePin:
    """``create_pin`` — the recorded 201."""

    def test_the_capture_becomes_a_pin(self) -> None:
        """The capture becomes a pin."""
        client, _ = _client(_answer("pin-created"))
        pin = client.create_pin()
        assert pin == PlexPin(id=900001, code="REDACTED-code-1", expires_at=pin.expires_at)
        # ``expiresAt`` 2026-10-04T12:47:35Z, as recorded.
        assert pin.expires_at == 1_791_118_055.0

    def test_an_answer_without_an_expiry_carries_none(self) -> None:
        """An answer without an expiry carries none."""
        body = {"id": 5, "code": "abc", "authToken": None}
        client, _ = _client(_Response(201, body))
        assert client.create_pin().expires_at is None

    @pytest.mark.parametrize(
        "answer",
        [
            _Response(500, {"errors": []}),
            _Response(201, "<html>maintenance</html>"),
            _Response(201, {"code": "abc"}),
            _Response(201, ["not", "a", "pin"]),
            _Response(401, {"errors": [{"code": 1001}]}),
            requests.ConnectionError("down"),
            requests.Timeout("slow"),
        ],
        ids=["500", "html", "no-id", "list", "401", "connection", "timeout"],
    )
    def test_every_failure_is_unreachable(self, answer: Any) -> None:
        """Every failure is unreachable."""
        client, _ = _client(answer)
        with pytest.raises(PlexAccountUnreachable):
            client.create_pin()


class TestSignInUrl:
    """``sign_in_url`` — pure, the four parameters, URL-encoded."""

    def _query(self, url: str) -> dict[str, list[str]]:
        """Parse the parameters after ``#?``.

        Args:
            url: The sign-in URL.

        Returns:
            The parsed parameters.
        """
        assert url.startswith("https://app.plex.tv/auth#?")
        return parse_qs(urlsplit(url).fragment[1:])

    def test_three_parameters_without_forward_url(self) -> None:
        """Three parameters without forward url."""
        client, session = _client()
        url = client.sign_in_url(PlexPin(id=1, code=CODE, expires_at=None))
        assert self._query(url) == {
            "clientID": [CLIENT_ID],
            "code": [CODE],
            "context[device][product]": [PRODUCT],
        }
        assert "context%5Bdevice%5D%5Bproduct%5D=TorrentMate+%28test%29" in url
        assert "forwardUrl" not in url
        assert session.calls == []

    def test_forward_url_present_only_when_given(self) -> None:
        """Forward url present only when given."""
        client, _ = _client()
        url = client.sign_in_url(PlexPin(id=1, code=CODE, expires_at=None), forward_url="https://tm.example/back?x=1")
        assert self._query(url)["forwardUrl"] == ["https://tm.example/back?x=1"]


class TestCheckPin:
    """``check_pin`` — one call: pending, claimed, expired, unreachable."""

    def test_pending_is_none(self) -> None:
        """Pending is none."""
        client, _ = _client(_answer("pin-pending"))
        assert client.check_pin(900001, CODE) is None

    def test_claimed_is_the_token(self) -> None:
        """Claimed is the token."""
        client, _ = _client(_answer("pin-claimed"))
        assert client.check_pin(900001, CODE) == "REDACTED-token-1"

    @pytest.mark.parametrize("status", [404, 410])
    def test_expired_raises_pin_expired(self, status: int) -> None:
        """Expired raises pin expired."""
        expired = _expired_pin()
        expired.status_code = status
        client, _ = _client(expired)
        with pytest.raises(PlexPinExpired):
            client.check_pin(900001, CODE)

    @pytest.mark.parametrize(
        "answer",
        [
            _Response(500, {}),
            _Response(200, "<html/>"),
            _Response(200, []),
            _Response(429, {}),
            requests.ConnectionError("down"),
        ],
        ids=["500", "html", "list", "429", "connection"],
    )
    def test_every_other_failure_is_unreachable(self, answer: Any) -> None:
        """Every other failure is unreachable."""
        client, _ = _client(answer)
        with pytest.raises(PlexAccountUnreachable):
            client.check_pin(900001, CODE)

    def test_one_call_and_no_loop(self) -> None:
        """One call and no loop."""
        client, session = _client(_answer("pin-pending"), _answer("pin-claimed"))
        client.check_pin(900001, CODE)
        assert len(session.calls) == 1


class TestAccount:
    """``account`` — the recorded 200 and 401."""

    def test_the_capture_becomes_an_account(self) -> None:
        """The capture becomes an account."""
        client, _ = _client(_answer("user-200"))
        assert client.account(TOKEN) == PlexAccount(
            plex_id=900002,
            uuid="REDACTED-uuid-1",
            username="REDACTED-name-1",
            title="REDACTED-name-2",
            email="redacted-1@example.invalid",
            thumb="https://redacted.invalid/url-1",
        )

    def test_the_recorded_401_is_a_refusal(self) -> None:
        """The recorded 401 is a refusal."""
        client, _ = _client(_answer("user-401"))
        with pytest.raises(PlexTokenRefused):
            client.account(TOKEN)

    def test_a_missing_thumb_is_none(self) -> None:
        """A missing thumb is none."""
        body = copy.deepcopy(_sample("user-200")["body"])
        del body["thumb"]
        client, _ = _client(_Response(200, body))
        assert client.account(TOKEN).thumb is None

    @pytest.mark.parametrize(
        "answer",
        [
            _Response(500, {}),
            _Response(403, {}),
            _Response(200, "<html/>"),
            _Response(200, {"uuid": "u", "email": "e@x.invalid"}),
            _Response(200, {"id": 1, "email": ""}),
            requests.ConnectionError("down"),
            requests.Timeout("slow"),
        ],
        ids=["500", "403", "html", "no-id", "no-email", "connection", "timeout"],
    )
    def test_only_a_401_refuses_every_other_failure_is_unreachable(self, answer: Any) -> None:
        """Only a 401 refuses every other failure is unreachable."""
        client, _ = _client(answer)
        with pytest.raises(PlexAccountUnreachable):
            client.account(TOKEN)


def _derived_home_resources() -> Any:
    """The recorded ``resources-home-derived.json``: a Plex Home member's view of this server.

    DERIVED, not recorded: the operator's own account owns the server and is in no Home, so
    the fixture is ``resources-owner.json`` with this server's resource flipped to
    ``owned: false, home: true``. Reading ``home`` as Home membership is INFERRED (the
    orchestrator's approval, 2026-10-04), to confirm with a real Home member's capture.

    Returns:
        The response body.
    """
    sample = _sample("resources-home-derived")
    assert sample["derived"], "the derived fixture must say it is derived"
    return sample["body"]


def _resources_with(match: Any, **flags: Any) -> Any:
    """The owner's recorded resources with the matching ones' flags set — a DERIVED variant.

    Args:
        match: A predicate on one resource.
        **flags: The keys to set on every matching resource (``owned``, ``home``).

    Returns:
        A deep copy of ``resources-owner.json``'s body, edited.
    """
    body = copy.deepcopy(_sample("resources-owner")["body"])
    for resource in body:
        if match(resource):
            resource.update(flags)
    return body


class TestServerAccess:
    """``server_access`` — OWNER / HOME / SHARED / NONE."""

    def test_the_owner_capture_is_owner(self) -> None:
        """The owner capture is owner."""
        client, _ = _client(_answer("resources-owner"))
        assert client.server_access(TOKEN, MACHINE) is PlexServerAccess.OWNER

    def test_a_server_reached_without_owning_it_is_shared(self) -> None:
        """A server reached without owning it is shared."""
        client, _ = _client(_answer("resources-owner"))
        assert client.server_access(TOKEN, SHARED_MACHINE) is PlexServerAccess.SHARED

    def test_a_home_member_is_home(self) -> None:
        """A home member is home."""
        client, _ = _client(_Response(200, _derived_home_resources()))
        assert client.server_access(TOKEN, MACHINE) is PlexServerAccess.HOME

    def test_the_derived_fixture_differs_from_the_owner_capture_only_on_this_server(self) -> None:
        """The derived fixture differs from the owner capture only on this server."""
        owner = _sample("resources-owner")["body"]
        home = _derived_home_resources()
        assert [r for r in home if r["clientIdentifier"] != MACHINE] == [
            r for r in owner if r["clientIdentifier"] != MACHINE
        ]

    def test_a_server_absent_from_the_list_is_none(self) -> None:
        """A server absent from the list is none."""
        client, _ = _client(_answer("resources-owner"))
        assert client.server_access(TOKEN, "some-other-machine") is PlexServerAccess.NONE

    def test_an_empty_list_is_none(self) -> None:
        """An empty list is none."""
        client, _ = _client(_Response(200, []))
        assert client.server_access(TOKEN, MACHINE) is PlexServerAccess.NONE

    def test_owned_wins_over_home(self) -> None:
        """A resource both owned and flagged home is OWNER (DERIVED from the owner's capture)."""
        body = _resources_with(lambda r: r["clientIdentifier"] == MACHINE, owned=True, home=True)
        client, _ = _client(_Response(200, body))
        assert client.server_access(TOKEN, MACHINE) is PlexServerAccess.OWNER

    def test_a_not_owned_duplicate_listed_first_does_not_demote_the_owner(self) -> None:
        """A not-owned duplicate before the owned resource is still OWNER (DERIVED from the owner's capture)."""
        body = copy.deepcopy(_sample("resources-owner")["body"])
        owned = next(r for r in body if r["clientIdentifier"] == MACHINE)
        duplicate = {**copy.deepcopy(owned), "owned": False, "home": False}
        body.insert(0, duplicate)
        client, _ = _client(_Response(200, body))
        assert client.server_access(TOKEN, MACHINE) is PlexServerAccess.OWNER

    def test_a_not_owned_resource_without_a_home_key_is_shared(self) -> None:
        """A not-owned matching resource whose ``home`` key is absent is SHARED (DERIVED from the owner's capture)."""
        body = _resources_with(lambda r: r["clientIdentifier"] == MACHINE, owned=False)
        for resource in body:
            if resource["clientIdentifier"] == MACHINE:
                del resource["home"]
        client, _ = _client(_Response(200, body))
        assert client.server_access(TOKEN, MACHINE) is PlexServerAccess.SHARED

    def test_an_empty_machine_identifier_is_refused_before_any_request(self) -> None:
        """An empty identifier matches nothing: a resource listed without one would otherwise answer."""
        body = [{"clientIdentifier": "", "owned": True}, {"owned": True}]
        client, session = _client(_Response(200, body))
        with pytest.raises(ValueError):
            client.server_access(TOKEN, "")
        assert session.calls == []

    def test_a_resource_without_a_client_identifier_matches_nothing(self) -> None:
        """A resource lacking ``clientIdentifier`` is never this server."""
        client, _ = _client(_Response(200, [{"owned": True, "home": False}]))
        assert client.server_access(TOKEN, MACHINE) is PlexServerAccess.NONE

    def test_a_401_is_a_refusal(self) -> None:
        """A 401 is a refusal."""
        client, _ = _client(_answer("user-401"))
        with pytest.raises(PlexTokenRefused):
            client.server_access(TOKEN, MACHINE)

    @pytest.mark.parametrize(
        "answer",
        [_Response(500, {}), _Response(200, "<html/>"), _Response(200, {"not": "a list"}), requests.Timeout("x")],
        ids=["500", "html", "dict", "timeout"],
    )
    def test_every_other_failure_is_unreachable(self, answer: Any) -> None:
        """Every other failure is unreachable."""
        client, _ = _client(answer)
        with pytest.raises(PlexAccountUnreachable):
            client.server_access(TOKEN, MACHINE)


# ---------------------------------------------------------------------------
# The token, the PIN code and the e-mail never leak
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _rendered_console(logger_name: str) -> Iterator[io.StringIO]:
    """Capture one logger through the console renderer PRODUCTION installs.

    The test session swaps that renderer out (``tests/conftest.py``), and it is the one
    that expands ``exc_info`` into a traceback with frame locals — the leak a record-level
    assertion cannot see (``test_plex_refresh.py``, F-B1).

    Args:
        logger_name: The stdlib logger to capture.

    Yields:
        The buffer receiving the rendered output.
    """
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=False),
            ],
        )
    )
    logger = logging.getLogger(logger_name)
    previous_propagate = logger.propagate
    logger.addHandler(handler)
    logger.propagate = False
    try:
        yield buf
    finally:
        logger.removeHandler(handler)
        logger.propagate = previous_propagate


def _logger_name() -> str:
    """The account client's stdlib logger name, read from the module (never spelled out).

    Returns:
        The name.
    """
    name: str = _plex_account.log.name
    assert name, "the client's logger must be resolvable, else the captures are vacuous"
    return name


def _leaky(exc_type: type[BaseException] = requests.ConnectionError) -> BaseException:
    """An exception whose text carries every planted secret, as a transport's might.

    Args:
        exc_type: The exception class.

    Returns:
        The exception.
    """
    return exc_type(f"boom X-Plex-Token={TOKEN} code={CODE} email={EMAIL}")


_SECRETS = (TOKEN, CODE, EMAIL)


def _calls() -> list[tuple[str, Any]]:
    """Every public call of the client, each fed a leaky failure.

    Returns:
        ``(name, call)`` pairs.
    """
    return [
        ("create_pin", lambda c: c.create_pin()),
        ("check_pin", lambda c: c.check_pin(900001, CODE)),
        ("account", lambda c: c.account(TOKEN)),
        ("server_access", lambda c: c.server_access(TOKEN, MACHINE)),
    ]


class TestNoLeak:
    """Over every failure path: no log record, rendered line, exception text or repr carries a secret."""

    @pytest.mark.parametrize(
        "failure",
        [
            lambda: _leaky(),
            lambda: _leaky(requests.Timeout),
            lambda: UnicodeEncodeError("utf-8", f"{TOKEN}{CODE}{EMAIL}", 0, 1, "surrogates not allowed"),
            lambda: _Response(500, {"errors": [{"message": f"{TOKEN} {CODE} {EMAIL}"}]}),
            lambda: _Response(200, f"<html>{TOKEN} {CODE} {EMAIL}</html>"),
            lambda: _Response(401, {"errors": [{"message": f"{TOKEN} {EMAIL}"}]}),
            lambda: _Response(404, {"errors": [{"message": f"Code {CODE} not found"}]}),
        ],
        ids=["connection", "timeout", "non-requests", "500", "html", "401", "404"],
    )
    @pytest.mark.parametrize(("name", "call"), _calls(), ids=[n for n, _ in _calls()])
    def test_no_secret_anywhere(self, name: str, call: Any, failure: Any, caplog: pytest.LogCaptureFixture) -> None:
        """No secret anywhere."""
        client, _ = _client(failure())
        with caplog.at_level(logging.DEBUG), _rendered_console(_logger_name()) as buf:
            try:
                call(client)
            except PlexAccountError as exc:
                raised: BaseException | None = exc
            else:
                raised = None
        rendered = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
        texts = [caplog.text, rendered, repr(client)]
        if raised is not None:
            texts += [str(raised), repr(raised)]
            assert raised.__cause__ is None, "a token-bearing cause escaped"
            assert raised.__context__ is None, "a token-bearing context escaped"
        for record in caplog.records:
            texts += [record.getMessage(), str(record.args), str(record.msg)]
            assert record.exc_info is None, "a traceback renders frame locals, the headers among them"
        for text in texts:
            for secret in _SECRETS:
                assert secret not in text, f"{name}: a secret reached {text[:80]!r}"

    def test_a_transport_failure_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """A transport failure is logged."""
        client, _ = _client(_leaky())
        with caplog.at_level(logging.DEBUG), pytest.raises(PlexAccountUnreachable) as caught:
            client.account(TOKEN)
        assert "ConnectionError" in str(caught.value)
        assert any("ConnectionError" in r.getMessage() or "ConnectionError" in str(r.msg) for r in caplog.records)

    def test_reprs_carry_no_secret(self) -> None:
        """Reprs carry no secret."""
        client, _ = _client()
        pin = PlexPin(id=1, code=CODE, expires_at=None)
        account = PlexAccount(plex_id=1, uuid="u", username="n", title="t", email=EMAIL, thumb=None)
        assert repr(client) == f"PlexAccountClient(product={PRODUCT!r})"
        assert CLIENT_ID not in repr(client)
        assert CODE not in repr(pin)
        assert EMAIL not in repr(account)


# ---------------------------------------------------------------------------
# PlexClient.machine_identifier — the server's own identifier
# ---------------------------------------------------------------------------


def _server(*answers: Any) -> tuple[PlexClient, _Session]:
    """Build a server client over a fake session.

    Args:
        *answers: The answers it replays.

    Returns:
        The client and its session.
    """
    session = _Session(*answers)
    return PlexClient("http://plex.invalid:32400", SERVER_TOKEN, session=session), session  # type: ignore[arg-type]


class TestMachineIdentifier:
    """``machine_identifier`` — parsed from the capture, cached, fail-soft."""

    def test_the_capture_is_parsed(self) -> None:
        """The capture is parsed."""
        server, session = _server(_answer("server-identity"))
        assert server.machine_identifier() == MACHINE
        call = session.calls[0]
        assert call["url"] == "http://plex.invalid:32400/identity"
        assert call["headers"]["X-Plex-Token"] == SERVER_TOKEN
        assert call["allow_redirects"] is False
        assert SERVER_TOKEN not in call["url"] + json.dumps(call.get("params") or {})

    def test_two_calls_one_request(self) -> None:
        """Two calls one request."""
        server, session = _server(_answer("server-identity"))
        assert server.machine_identifier() == server.machine_identifier() == MACHINE
        assert len(session.calls) == 1

    @pytest.mark.parametrize(
        "answer",
        [
            _Response(401, {}),
            _Response(500, {}),
            _Response(200, "<html/>"),
            _Response(200, {"MediaContainer": {}}),
            _Response(200, {"MediaContainer": {"machineIdentifier": ""}}),
            requests.ConnectionError(f"boom {SERVER_TOKEN}"),
        ],
        ids=["401", "500", "html", "no-field", "empty", "connection"],
    )
    def test_failure_is_none_and_retried_next_time(self, answer: Any, caplog: pytest.LogCaptureFixture) -> None:
        """Failure is none and retried next time."""
        server, session = _server(answer, _answer("server-identity"))
        with caplog.at_level(logging.DEBUG):
            assert server.machine_identifier() is None
        assert caplog.records, "the failure must be logged"
        assert SERVER_TOKEN not in caplog.text
        assert all(r.exc_info is None for r in caplog.records)
        assert server.machine_identifier() == MACHINE
        assert len(session.calls) == 2
