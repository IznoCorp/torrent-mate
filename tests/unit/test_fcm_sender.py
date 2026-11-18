"""Unit tests for ``personalscraper.api.notify.fcm`` — the FCM HTTP v1 sender.

Never a live call: the token grant and the send are answered by a fake session, the
send answers from the documented fixtures under ``docs/reference/_samples/fcm/``. The
service account is a throwaway one generated for the suite (a fresh RSA key).

The leak suite plants recognisable values — the device token, the access token, the
private key — and proves none of them reaches a log record, the RENDERED console
(the production formatter expands tracebacks with frame locals), an exception text or
a ``repr``.
"""

from __future__ import annotations

import contextlib
import gc
import io
import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import requests
import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from personalscraper.api.notify import fcm
from personalscraper.api.notify.fcm import FcmSender, PushMessage, PushOutcome

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "fcm"
DEVICE_TOKEN = "PLANTED-device-token-fcm-0123456789"
ACCESS_TOKEN = "PLANTED-access-token-ya29-abcdef"
PROJECT = "planted-project"
TOKEN_URI = "https://oauth2.googleapis.com/token"


@pytest.fixture(scope="module")
def private_key_pem() -> str:
    """A throwaway RSA key, generated for this suite only.

    Returns:
        The PKCS#8 PEM text.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


@pytest.fixture
def service_account_file(tmp_path: Path, private_key_pem: str) -> Path:
    """A service-account JSON file in Google's shape, holding the throwaway key.

    Args:
        tmp_path: pytest's temporary directory.
        private_key_pem: The throwaway key.

    Returns:
        The file's path.
    """
    path = tmp_path / "sa.json"
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": PROJECT,
                "private_key_id": "kid-1",
                "private_key": private_key_pem,
                "client_email": f"fcm@{PROJECT}.iam.gserviceaccount.com",
                "client_id": "1",
                "token_uri": TOKEN_URI,
            }
        )
    )
    return path


class _Response:
    """A minimal ``requests.Response`` stand-in, enough for ``classify`` and google-auth."""

    def __init__(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
        """Builds the answer.

        Args:
            status: HTTP status.
            body: JSON body.
            headers: Response headers.
        """
        self.status_code = status
        self.status = status
        self._body = body
        self.headers = headers or {}
        self.text = json.dumps(body)
        self.content = self.text.encode()
        self.data = self.content

    def json(self) -> Any:
        """Returns the JSON body."""
        return self._body


def _fixture(name: str) -> _Response:
    """Loads one documented answer.

    Args:
        name: The fixture's stem.

    Returns:
        The answer.
    """
    raw = json.loads((SAMPLES / f"{name}.json").read_text())
    return _Response(raw["status"], raw["body"], raw["headers"])


class _FakeGoogle:
    """Answers the token grant and the send."""

    def __init__(self, send_answer: _Response | Exception, grant: _Response | None = None) -> None:
        """Builds the fake.

        Args:
            send_answer: What ``messages:send`` answers, or raises.
            grant: What the token endpoint answers (a valid grant by default).
        """
        self.send_answer = send_answer
        self.grant = grant or _Response(200, {"access_token": ACCESS_TOKEN, "expires_in": 3600, "token_type": "Bearer"})
        self.sends: list[dict[str, Any]] = []
        self.grants = 0
        self.closes = 0

    def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        """google-auth's token grant goes through ``request``.

        Args:
            method: HTTP method.
            url: The token endpoint.
            **kwargs: Ignored.

        Returns:
            The grant answer.
        """
        assert url == TOKEN_URI
        self.grants += 1
        return self.grant

    def close(self) -> None:
        """Counts the closes google-auth's ``Request`` performs on the shared session."""
        self.closes += 1

    def post(self, url: str, **kwargs: Any) -> _Response:
        """The send.

        Args:
            url: The send URL.
            **kwargs: ``json``, ``headers``, ``timeout``, ``allow_redirects``.

        Returns:
            The configured answer.

        Raises:
            Exception: The configured exception.
        """
        self.sends.append({"url": url, **kwargs})
        if isinstance(self.send_answer, Exception):
            raise self.send_answer
        return self.send_answer


def _message() -> PushMessage:
    """A ratio alert, as facts.

    Returns:
        The message.
    """
    return PushMessage(
        code="tracker.ratio_low",
        params={"tracker": "c411", "ratio": 1.12},
        link="/trackers/c411",
        tag="ratio-c411",
        ttl_seconds=3600,
        urgency="high",
    )


def _sender(sa: Path, fake: _FakeGoogle) -> FcmSender:
    """Builds a sender over the fake.

    Args:
        sa: The service-account file.
        fake: The fake Google.

    Returns:
        The sender.
    """
    return FcmSender.from_service_account_file(sa, session=fake)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("fixture", "outcome", "retry_after", "fcm_error"),
    [
        ("send-200", PushOutcome.DELIVERED, None, None),
        ("unregistered-404", PushOutcome.TOKEN_DEAD, None, "UNREGISTERED"),
        ("sender-id-mismatch-403", PushOutcome.MISCONFIGURED, None, "SENDER_ID_MISMATCH"),
        ("invalid-argument-400", PushOutcome.REJECTED, None, "INVALID_ARGUMENT"),
        ("quota-exceeded-429", PushOutcome.QUOTA_EXCEEDED, 120.0, "QUOTA_EXCEEDED"),
        ("unavailable-503", PushOutcome.RETRY_LATER, 30.0, "UNAVAILABLE"),
        ("internal-500", PushOutcome.RETRY_LATER, None, "INTERNAL"),
        ("third-party-auth-error-401", PushOutcome.MISCONFIGURED, None, "THIRD_PARTY_AUTH_ERROR"),
        ("permission-denied-403", PushOutcome.MISCONFIGURED, None, "PERMISSION_DENIED"),
    ],
)
def test_every_documented_answer_maps_to_its_outcome(
    fixture: str, outcome: PushOutcome, retry_after: float | None, fcm_error: str | None, service_account_file: Path
) -> None:
    """Firebase's error table, answer by answer."""
    result = _sender(service_account_file, _FakeGoogle(_fixture(fixture))).send(DEVICE_TOKEN, _message())
    assert result.outcome is outcome
    assert result.retry_after_seconds == retry_after
    assert result.fcm_error == fcm_error


def test_quota_without_retry_after_still_backs_off_a_minute() -> None:
    """QUOTA_EXCEEDED: at least 60 s even when the header is absent."""
    raw = json.loads((SAMPLES / "quota-exceeded-429.json").read_text())
    result = fcm.classify(_Response(429, raw["body"], {}))  # type: ignore[arg-type]
    assert result.outcome is PushOutcome.QUOTA_EXCEEDED and result.retry_after_seconds == 60.0


@pytest.mark.parametrize(
    "body",
    [
        {"error": {"code": 429, "message": "Quota exceeded.", "status": "RESOURCE_EXHAUSTED"}},
        "<html>Too Many Requests</html>",
    ],
)
def test_a_429_without_an_fcm_detail_is_the_quota(body: Any) -> None:
    """Google's own ``RESOURCE_EXHAUSTED``, or a bare 429: the quota outcome, decided here once."""
    result = fcm.classify(_Response(429, body))  # type: ignore[arg-type]
    assert result.outcome is PushOutcome.QUOTA_EXCEEDED and result.retry_after_seconds == 60.0


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("inf", None),
        ("1e400", None),
        ("nan", None),
        ("-inf", None),
        ("1e300", fcm.RETRY_AFTER_CEILING_SECONDS),
        ("Fri, 31 Dec 9999 23:59:59 GMT", fcm.RETRY_AFTER_CEILING_SECONDS),
        ("30", 30.0),
    ],
)
def test_retry_after_is_finite_and_bounded(header: str, expected: float | None) -> None:
    """A non-finite ``Retry-After`` is no answer; a finite one is clamped to the ceiling."""
    result = fcm.classify(_Response(503, {"error": {"status": "UNAVAILABLE"}}, {"Retry-After": header}))  # type: ignore[arg-type]
    assert result.outcome is PushOutcome.RETRY_LATER and result.retry_after_seconds == expected


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (404, PushOutcome.MISCONFIGURED),
        (502, PushOutcome.RETRY_LATER),
        (418, PushOutcome.REJECTED),
        (429, PushOutcome.QUOTA_EXCEEDED),
    ],
)
def test_an_answer_without_a_code_is_read_by_its_status(status: int, outcome: PushOutcome) -> None:
    """A 404 that does not say UNREGISTERED is a wrong project, never a dead token."""
    result = fcm.classify(_Response(status, "<html>not json</html>"))  # type: ignore[arg-type]
    assert result.outcome is outcome and result.fcm_error == f"HTTP_{status}"


def test_the_request_is_a_data_only_webpush_message(service_account_file: Path) -> None:
    """URL with the project, Bearer access token, data-only body with TTL / Urgency, no redirect."""
    fake = _FakeGoogle(_fixture("send-200"))
    _sender(service_account_file, fake).send(DEVICE_TOKEN, _message())
    (sent,) = fake.sends
    assert sent["url"] == f"https://fcm.googleapis.com/v1/projects/{PROJECT}/messages:send"
    assert sent["headers"] == {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    assert sent["allow_redirects"] is False
    message = sent["json"]["message"]
    assert message["token"] == DEVICE_TOKEN
    assert set(message) == {"token", "webpush"}, "data-only: no notification block, the worker words it"
    assert message["webpush"]["headers"] == {"TTL": "3600", "Urgency": "high"}
    assert message["webpush"]["data"] == {
        "code": "tracker.ratio_low",
        "params": '{"ratio": 1.12, "tracker": "c411"}',
        "link": "/trackers/c411",
        "tag": "ratio-c411",
    }
    assert "validate_only" not in sent["json"]


def test_the_recipients_language_rides_in_the_data() -> None:
    """``language`` set: carried as ``data.language`` for the worker to word the code in (FG-2 A)."""
    message = PushMessage(code="account.sign_in.unknown_device", language="en")

    assert message.webpush_data()["language"] == "en"


def test_no_language_leaves_the_data_without_one() -> None:
    """``language`` unset: no ``data.language`` — the worker words it in English (OPEN-2 B)."""
    assert "language" not in PushMessage(code="tracker.ratio_low").webpush_data()


def test_validate_only_is_sent_when_asked(service_account_file: Path) -> None:
    """The probe's credential check asks FCM not to deliver."""
    fake = _FakeGoogle(_fixture("invalid-argument-400"))
    _sender(service_account_file, fake).send("placeholder", _message(), validate_only=True)
    assert fake.sends[0]["json"]["validate_only"] is True


def test_the_access_token_is_minted_once_and_reused(service_account_file: Path) -> None:
    """One grant for two sends while the token is valid."""
    fake = _FakeGoogle(_fixture("send-200"))
    sender = _sender(service_account_file, fake)
    sender.send(DEVICE_TOKEN, _message())
    sender.send(DEVICE_TOKEN, _message())
    assert fake.grants == 1 and len(fake.sends) == 2


def test_a_grant_never_closes_the_session_the_sends_use(service_account_file: Path) -> None:
    """Two grants (an expired token) and three sends: the shared session stays open."""
    fake = _FakeGoogle(_fixture("send-200"), grant=_Response(200, {"access_token": ACCESS_TOKEN, "expires_in": 1}))
    sender = _sender(service_account_file, fake)
    for _ in range(3):
        sender.send(DEVICE_TOKEN, _message())
        gc.collect()
    assert fake.grants >= 2 and len(fake.sends) == 3
    assert fake.closes == 0


def test_the_access_token_grant_is_bounded_by_the_timeout(service_account_file: Path) -> None:
    """The grant reaches the transport with the sender's timeout, not google-auth's 120 s default."""
    timeouts: list[Any] = []

    class _Recording(_FakeGoogle):
        def request(self, method: str, url: str, **kwargs: Any) -> _Response:
            timeouts.append(kwargs.get("timeout"))
            return super().request(method, url, **kwargs)

    _sender(service_account_file, _Recording(_fixture("send-200"))).send(DEVICE_TOKEN, _message())
    assert timeouts == [fcm._TIMEOUT]


def test_a_refused_grant_is_misconfigured_and_sends_nothing(service_account_file: Path) -> None:
    """``invalid_grant`` (a revoked key) → MISCONFIGURED, no send attempted."""
    fake = _FakeGoogle(_fixture("send-200"), grant=_Response(400, {"error": "invalid_grant"}))
    result = _sender(service_account_file, fake).send(DEVICE_TOKEN, _message())
    assert result.outcome is PushOutcome.MISCONFIGURED and fake.sends == []


def test_an_unreadable_service_account_file_is_misconfigured(tmp_path: Path) -> None:
    """A missing or malformed file never raises: every send answers MISCONFIGURED."""
    bad = tmp_path / "broken.json"
    bad.write_text("{ not json")
    for path in (bad, tmp_path / "absent.json"):
        sender = FcmSender.from_service_account_file(path, session=_FakeGoogle(_fixture("send-200")))  # type: ignore[arg-type]
        assert sender.send(DEVICE_TOKEN, _message()).outcome is PushOutcome.MISCONFIGURED


def test_no_answer_is_unreachable(service_account_file: Path) -> None:
    """A timeout or a connection error → UNREACHABLE, never an exception."""
    for exc in (requests.Timeout("slow"), requests.ConnectionError("down")):
        result = _sender(service_account_file, _FakeGoogle(exc)).send(DEVICE_TOKEN, _message())
        assert result.outcome is PushOutcome.UNREACHABLE


@pytest.mark.parametrize("link", ["https://evil.example/x", "//evil.example/x", "trackers", "/\\evil.example"])
def test_a_message_link_must_stay_in_the_application(link: str) -> None:
    """Only a same-origin path is accepted."""
    with pytest.raises(ValueError):
        PushMessage(code="x", link=link)


def test_repr_names_the_project_only(service_account_file: Path, private_key_pem: str) -> None:
    """No key, no token in the ``repr``."""
    sender = _sender(service_account_file, _FakeGoogle(_fixture("send-200")))
    sender.send(DEVICE_TOKEN, _message())
    assert repr(sender) == f"FcmSender(project_id={PROJECT!r})"


# --- the leak suite ----------------------------------------------------------------


@contextlib.contextmanager
def _rendered_console(logger_name: str) -> Iterator[io.StringIO]:
    """Captures one logger's output through the renderer PRODUCTION uses.

    The test session swaps the console renderer for a key-value one; the production
    ``ConsoleRenderer`` is the component that expands ``exc_info`` with frame locals,
    so it is rebuilt here explicitly.

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
            ]
        )
    )
    logger = logging.getLogger(logger_name)
    previous = logger.propagate
    logger.addHandler(handler)
    logger.propagate = False
    try:
        yield buf
    finally:
        logger.removeHandler(handler)
        logger.propagate = previous


class _HeaderEchoingError(Exception):
    """Raised with the secrets in its text and in the raising frame, as a broken transport would."""


@pytest.mark.parametrize(
    "answer",
    [
        _HeaderEchoingError(f"boom {DEVICE_TOKEN} Bearer {ACCESS_TOKEN}"),
        requests.ConnectionError(f"down {DEVICE_TOKEN}"),
        "invalid-argument-400",
        "third-party-auth-error-401",
        "unavailable-503",
    ],
)
def test_no_secret_reaches_a_log_the_console_or_a_result(
    answer: Any, service_account_file: Path, private_key_pem: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Device token, access token, private key: absent from records, rendered output and results."""
    send_answer = _fixture(answer) if isinstance(answer, str) else answer
    key_body = private_key_pem.splitlines()[1]
    name = fcm.log.name
    assert name, "the module's logger must be resolvable, else the capture is vacuous"
    with caplog.at_level(logging.DEBUG), _rendered_console(name) as buf:
        result = _sender(service_account_file, _FakeGoogle(send_answer)).send(DEVICE_TOKEN, _message())
    rendered = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
    assert rendered.strip(), "a failed send must be logged (a silent failure is the other bug)"
    for secret in (DEVICE_TOKEN, ACCESS_TOKEN, key_body):
        assert secret not in rendered
        assert secret not in caplog.text
        assert secret not in repr(result)
        for record in caplog.records:
            assert secret not in record.getMessage()
            assert record.exc_info is None


def test_an_unreadable_file_logs_no_part_of_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file whose parse error QUOTES a key fragment: the log names the error type only.

    The loader's exception carries the fragment in its text, as a parser quoting the offending
    line would — so logging ``str(exc)`` or ``exc_info`` instead of the type fails here.
    """
    from google.oauth2 import service_account

    path = tmp_path / "sa.json"
    path.write_text('{"type": "service_account", "private_key": "PLANTED-KEY-FRAGMENT", ')

    def _quoting_loader(filename: str, **kwargs: Any) -> Any:
        raise ValueError(f"No key could be detected in {Path(filename).read_text()!r}")

    monkeypatch.setattr(service_account.Credentials, "from_service_account_file", _quoting_loader)
    with caplog.at_level(logging.DEBUG), _rendered_console(fcm.log.name) as buf:
        FcmSender.from_service_account_file(path)
    assert "PLANTED-KEY-FRAGMENT" not in buf.getvalue() + caplog.text
    assert "service_account_unreadable" in buf.getvalue() and "ValueError" in buf.getvalue()


# --- the operator's probe (scripts/fcm-probe.py) ------------------------------------


def _load_probe() -> Any:
    """Imports the probe despite its hyphenated filename.

    Returns:
        The loaded module.
    """
    import importlib.util
    import sys

    path = Path(__file__).resolve().parents[2] / "scripts" / "fcm-probe.py"
    spec = importlib.util.spec_from_file_location("fcm_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("fixture", "code"),
    [("invalid-argument-400", 0), ("third-party-auth-error-401", 1), ("permission-denied-403", 1), ("send-200", 1)],
)
def test_the_probe_passes_only_on_the_expected_invalid_argument(
    fixture: str, code: int, service_account_file: Path
) -> None:
    """INVALID_ARGUMENT on the placeholder proves the credentials; anything else names what is wrong."""
    probe = _load_probe()
    fake = _FakeGoogle(_fixture(fixture))
    said: list[str] = []
    exit_code = probe.run(
        {"FCM_SERVICE_ACCOUNT_FILE": str(service_account_file)},
        build=lambda p: FcmSender.from_service_account_file(p, session=fake),  # type: ignore[arg-type]
        say=said.append,
    )
    assert exit_code == code
    assert fake.sends[0]["json"]["validate_only"] is True
    assert fake.sends[0]["json"]["message"]["token"] == probe.PLACEHOLDER_TOKEN
    assert all(ACCESS_TOKEN not in line for line in said)


def test_the_probe_without_the_file_setting_sends_nothing() -> None:
    """No ``FCM_SERVICE_ACCOUNT_FILE``: misconfigured, nothing built."""
    probe = _load_probe()
    said: list[str] = []
    assert probe.run({}, build=lambda p: pytest.fail("nothing must be built"), say=said.append) == 1
    assert said == ["misconfigured: FCM_SERVICE_ACCOUNT_FILE is not set"]
