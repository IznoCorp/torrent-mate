"""Tests for the `kanban serve` webhook receiver (ingress-multiproject §4 / §9).

Drives a REAL :class:`ThreadingHTTPServer` on an ephemeral loopback port in a background thread and
sends requests via ``http.client`` — exercising the full hardened stack (bounded read, HMAC-first,
method/path allow-list, fixed responses). The nudge is INJECTED so a managed-project POST records a
nudge call without needing a real daemon.

Covers: valid sig + projects_v2_item known project → 202 + nudge; unknown project → 202 no nudge;
oversized body → 413; chunked → 411; bad method/path → 405/404; ping → 200; healthz → 200; invalid
/missing HMAC → 401 + NO nudge; serve refuses to start with no secret / privileged port / root.
"""

from __future__ import annotations

import hmac
import json
import socket
import threading
import time
from hashlib import sha256
from http.client import HTTPConnection
from pathlib import Path

import pytest

from kanbanmate.cli.init import _projects_path, _upsert_project
from kanbanmate.cli.init import ProjectEntry
from kanbanmate.http import serve as serve_mod
from kanbanmate.http.serve import (
    PrivilegedPortError,
    RootPrivilegeError,
    WebhookConfig,
    WebhookSecretMissingError,
    build_server,
    load_webhook_secret,
    main,
)

_SECRET = b"test-webhook-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(_SECRET, body, sha256).hexdigest()


def _register(root: Path, pid: str, repo: str = "o/r") -> None:
    """Register one project in <root>/projects.json so the receiver can route to it."""
    _upsert_project(
        _projects_path(root),
        pid,
        ProjectEntry(repo=repo, clone="/c", project_id=pid, status_field_node_id="F"),
    )


class _ServerFixture:
    """A running receiver on an ephemeral port + a list capturing nudge calls."""

    def __init__(self, root: Path) -> None:
        self.nudged: list[Path] = []
        config = WebhookConfig(root=root, secret=_SECRET, host="127.0.0.1", port=0)
        self.server = build_server(config, nudge=self.nudged.append)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def request(
        self, method: str, path: str, *, body: bytes = b"", headers: dict[str, str] | None = None
    ) -> tuple[int, bytes]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def server(tmp_path: Path):  # type: ignore[no-untyped-def]
    fix = _ServerFixture(tmp_path)
    yield fix
    fix.close()


def _post_webhook(
    server: _ServerFixture, body: bytes, *, event: str = "projects_v2_item", sign: bool = True
) -> tuple[int, bytes]:
    headers = {"Content-Type": "application/json", "X-GitHub-Event": event}
    if sign:
        headers["X-Hub-Signature-256"] = _sign(body)
    return server.request("POST", "/webhook", body=body, headers=headers)


def test_valid_sig_known_project_202_and_nudges(server: _ServerFixture, tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A")
    body = json.dumps({"projects_v2_item": {"project_node_id": "PVT_A"}}).encode()
    status, _ = _post_webhook(server, body)
    assert status == 202
    assert server.nudged == [tmp_path]


def test_unknown_project_202_no_nudge(server: _ServerFixture, tmp_path: Path) -> None:
    # No registered project → unmanaged → 202 accepted, NO nudge (never 4xx an unmanaged board).
    body = json.dumps({"projects_v2_item": {"project_node_id": "PVT_UNKNOWN"}}).encode()
    status, _ = _post_webhook(server, body)
    assert status == 202
    assert server.nudged == []


def test_invalid_signature_401_no_nudge(server: _ServerFixture, tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A")
    body = json.dumps({"projects_v2_item": {"project_node_id": "PVT_A"}}).encode()
    # Tamper the signature.
    headers = {
        "X-GitHub-Event": "projects_v2_item",
        "X-Hub-Signature-256": "sha256=deadbeef",
        "Content-Type": "application/json",
    }
    status, _ = server.request("POST", "/webhook", body=body, headers=headers)
    assert status == 401
    assert server.nudged == []


def test_missing_signature_401(server: _ServerFixture, tmp_path: Path) -> None:
    body = b"{}"
    status, _ = _post_webhook(server, body, sign=False)
    assert status == 401
    assert server.nudged == []


def test_ping_event_200(server: _ServerFixture) -> None:
    body = b'{"zen":"hello"}'
    status, payload = _post_webhook(server, body, event="ping")
    assert status == 200
    assert payload == b"pong"


def test_other_event_204(server: _ServerFixture) -> None:
    body = b"{}"
    status, _ = _post_webhook(server, body, event="issues")
    assert status == 204
    assert server.nudged == []


def test_healthz_200(server: _ServerFixture) -> None:
    status, payload = server.request("GET", "/healthz")
    assert status == 200
    assert payload == b"ok"


def test_unknown_path_404(server: _ServerFixture) -> None:
    status, _ = server.request("GET", "/nope")
    assert status == 404


def test_wrong_method_on_webhook_405(server: _ServerFixture) -> None:
    # GET /webhook is a KNOWN path with the wrong method → 405 (not 404), per DESIGN §4.2 (#7b).
    status, _ = server.request("GET", "/webhook")
    assert status == 405


def test_wrong_method_on_healthz_405(server: _ServerFixture) -> None:
    # POST /healthz is a KNOWN path with the wrong method → 405 (only GET /healthz is allowed).
    status, _ = server.request("POST", "/healthz")
    assert status == 405


def test_disallowed_verb_on_known_path_405(server: _ServerFixture) -> None:
    # An entirely different verb (DELETE) on a known path → 405, never the stdlib default 501 (#7b).
    status, _ = server.request("DELETE", "/webhook")
    assert status == 405


def test_disallowed_verb_on_unknown_path_404(server: _ServerFixture) -> None:
    # A non-GET verb on an UNKNOWN path → 404 (the path is unknown; method is moot).
    status, _ = server.request("DELETE", "/nope")
    assert status == 404


def test_oversized_body_413(server: _ServerFixture, tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A")
    # Declare a Content-Length over the 1 MiB cap (we send a small body; the length header is the
    # guard — the handler rejects on the declared length before reading).
    headers = {
        "X-GitHub-Event": "projects_v2_item",
        "Content-Length": str(serve_mod.MAX_BODY_BYTES + 1),
    }
    status, _ = server.request("POST", "/webhook", body=b"x", headers=headers)
    assert status == 413


def test_chunked_transfer_411(server: _ServerFixture) -> None:
    # http.client adds Transfer-Encoding: chunked when we omit Content-Length and pass a generator;
    # simpler: set the header explicitly with no Content-Length.
    headers = {"X-GitHub-Event": "projects_v2_item", "Transfer-Encoding": "chunked"}
    status, _ = server.request("POST", "/webhook", body=b"", headers=headers)
    assert status == 411


def test_bad_json_after_valid_sig_400(server: _ServerFixture, tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A")
    body = b"not json"
    status, _ = _post_webhook(server, body)
    assert status == 400


# --- slow-loris guard (#2) ---------------------------------------------------------------------


def test_slow_loris_partial_body_dropped_after_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#2: a client that declares a body but stalls is DROPPED after the per-connection timeout.

    Proves the slow-loris guard sits on the ACCEPTED socket (the handler's ``setup`` deadline), not
    the listening socket. A raw client sends a POST /webhook with Content-Length=100 then sends NO
    body and never closes; the server must time out reading the body, drop the connection (the raw
    socket sees EOF / a closed peer well within the test budget), AND stay responsive to a normal
    request afterwards (the worker was freed, not pinned).
    """
    # A tiny per-connection timeout so the test is fast; read at the handler's ``setup`` per request.
    monkeypatch.setattr(serve_mod, "SOCKET_TIMEOUT_SECONDS", 0.5)
    _register(tmp_path, "PVT_A")
    fix = _ServerFixture(tmp_path)
    try:
        raw = socket.create_connection(("127.0.0.1", fix.port), timeout=5)
        try:
            # Declare a 100-byte body, send the headers, then NEVER send the body (the slow loris).
            raw.sendall(
                b"POST /webhook HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"X-GitHub-Event: projects_v2_item\r\n"
                b"Content-Length: 100\r\n"
                b"\r\n"
            )
            # The server's accepted-socket read must time out (~0.5 s) and drop the connection well
            # within this 5 s recv budget. A pinned worker (the OLD ineffective guard) would block
            # here until OUR recv timeout fires at 5 s — so a prompt EOF proves the guard works.
            raw.settimeout(5.0)
            start = time.monotonic()
            data = raw.recv(4096)  # b"" on a clean peer-close, or a short error response then EOF
            elapsed = time.monotonic() - start
            # Dropped promptly (well under the recv budget), proving the accepted-socket timeout fired.
            assert elapsed < 4.0
            # No full successful body was served (the body was never sent); a closed peer → b"".
            assert b"202" not in data
        finally:
            raw.close()

        # The server is still responsive: a normal healthz succeeds (the worker was freed).
        status, payload = fix.request("GET", "/healthz")
        assert status == 200
        assert payload == b"ok"
    finally:
        fix.close()


# --- start-time guards (no server) -------------------------------------------------------------


def test_load_secret_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(WebhookSecretMissingError):
        load_webhook_secret(tmp_path)


def test_load_secret_strips_trailing_newline(tmp_path: Path) -> None:
    (tmp_path / "webhook_secret").write_bytes(b"my-secret\n")
    assert load_webhook_secret(tmp_path) == b"my-secret"


# --- #3: reject a placeholder / empty / comment-only secret ------------------------------------


def test_load_secret_empty_file_rejected(tmp_path: Path) -> None:
    """An empty secret file → refused (a publicly-known/blank HMAC key is a security hole, #3)."""
    (tmp_path / "webhook_secret").write_bytes(b"")
    with pytest.raises(WebhookSecretMissingError):
        load_webhook_secret(tmp_path)


def test_load_secret_whitespace_only_rejected(tmp_path: Path) -> None:
    """A whitespace-only secret file → refused (#3)."""
    (tmp_path / "webhook_secret").write_bytes(b"   \n\t\n")
    with pytest.raises(WebhookSecretMissingError):
        load_webhook_secret(tmp_path)


def test_load_secret_comment_only_placeholder_rejected(tmp_path: Path) -> None:
    """A comment-only file (every line starts with '#') → refused — the seeded placeholder shape (#3)."""
    (tmp_path / "webhook_secret").write_bytes(
        b"# paste a strong random secret on the next line\n# keep this file 600\n"
    )
    with pytest.raises(WebhookSecretMissingError):
        load_webhook_secret(tmp_path)


def test_load_secret_seeded_init_placeholder_rejected(tmp_path: Path) -> None:
    """The EXACT placeholder `kanban init` seeds is rejected (#3 — its bytes are public in source)."""
    from kanbanmate.cli.init import _WEBHOOK_SECRET_PLACEHOLDER

    (tmp_path / "webhook_secret").write_text(_WEBHOOK_SECRET_PLACEHOLDER, encoding="utf-8")
    with pytest.raises(WebhookSecretMissingError):
        load_webhook_secret(tmp_path)


def test_load_secret_real_value_accepted(tmp_path: Path) -> None:
    """A real secret on its own line → accepted (comments/whitespace stripped, the value survives)."""
    (tmp_path / "webhook_secret").write_text(
        "# paste below\nmy-real-strong-secret\n", encoding="utf-8"
    )
    assert load_webhook_secret(tmp_path) == b"my-real-strong-secret"


def test_main_refuses_placeholder_secret(tmp_path: Path) -> None:
    """`kanban serve` (main) refuses to start when only the placeholder is present (#3 part b)."""
    from kanbanmate.cli.init import _WEBHOOK_SECRET_PLACEHOLDER

    (tmp_path / "webhook_secret").write_text(_WEBHOOK_SECRET_PLACEHOLDER, encoding="utf-8")
    with pytest.raises(WebhookSecretMissingError):
        main(root=tmp_path, geteuid=lambda: 1000)


def test_main_refuses_root(tmp_path: Path) -> None:
    (tmp_path / "webhook_secret").write_bytes(b"s")
    with pytest.raises(RootPrivilegeError):
        main(root=tmp_path, geteuid=lambda: 0)


def test_main_refuses_privileged_port(tmp_path: Path) -> None:
    (tmp_path / "webhook_secret").write_bytes(b"s")
    with pytest.raises(PrivilegedPortError):
        main(root=tmp_path, port=80, geteuid=lambda: 1000)


def test_main_refuses_without_secret(tmp_path: Path) -> None:
    with pytest.raises(WebhookSecretMissingError):
        main(root=tmp_path, geteuid=lambda: 1000)
