"""The design host's post-deploy smoke check, run against a fake host and a fake CLI.

WHAT IT PAYS FOR. After each redeploy the smoke signs in as the owner through the dev-only
CLI, calls every ``get`` operation of the contract and names each failure. A tool the
orchestrator wakes on must not go quiet when a GET breaks, must not call a write, must always
sign out, and must never print the session token.

WHAT MAKES IT NON-VACUOUS. The host is a real HTTP server on an ephemeral port that records
every request it gets (method, path, cookie); the CLI is a real child process (a one-line
Python script); the contract is a small sample written per test. Everything is read on the wire
and on the script's own stdout, never on a mock.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "design-host-smoke.py"
TOKEN = "fake-session-value"
COOKIE = "tm_v1_session"


def _load() -> ModuleType:
    """Import the script by path (its file name has dashes).

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("design_host_smoke", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract(tmp_path: Path, extra_gets: dict[str, dict[str, Any]] | None = None) -> Path:
    """Write a sample contract: three GETs, a POST that must never be called.

    Args:
        tmp_path: Where the file goes.
        extra_gets: More GET paths, by path, each an operation object.

    Returns:
        The contract's path.
    """
    paths: dict[str, Any] = {
        "/version": {"get": {"operationId": "readVersion"}},
        "/library/items": {"get": {"operationId": "readLibraryItems"}},
        "/media/{provider}/{providerId}": {
            "get": {
                "operationId": "readMediaSheet",
                "parameters": [
                    {"name": "provider", "in": "path", "required": True},
                    {"name": "providerId", "in": "path", "required": True},
                ],
            }
        },
        "/library/items/delete": {"post": {"operationId": "deleteLibraryItems"}},
        "/auth/logout": {"post": {"operationId": "signOut"}},
    }
    for path, operation in (extra_gets or {}).items():
        paths[path] = {"get": operation}
    target = tmp_path / "contract.json"
    target.write_text(json.dumps({"paths": paths}))
    return target


def _cli(tmp_path: Path, token: str = TOKEN, exit_code: int = 0) -> list[str]:
    """Build the fake CLI: a child process that prints a token alone.

    Args:
        tmp_path: Where the script goes.
        token: What it prints.
        exit_code: Its exit code.

    Returns:
        The argv the smoke runs.
    """
    script = tmp_path / "fake_cli.py"
    script.write_text(f"import sys\nprint({token!r})\nsys.exit({exit_code})\n")
    return [sys.executable, str(script)]


class FakeHost:
    """A fake v1 host that records every request and answers by a per-path table."""

    def __init__(self, answers: dict[str, tuple[int, Any]]) -> None:
        """Start from the answers.

        Args:
            answers: ``(status, JSON body)`` by ``METHOD path``; an unlisted GET is a 200 ``{}``.
        """
        self.answers = answers
        self.requests: list[tuple[str, str, str | None]] = []


@contextmanager
def _host(answers: dict[str, tuple[int, Any]] | None = None) -> Iterator[tuple[FakeHost, str]]:
    """Serve a fake host on an ephemeral port (never a real one).

    Args:
        answers: See ``FakeHost``.

    Yields:
        The host (its recorded requests) and its base URL.
    """
    host = FakeHost(answers or {})
    items = {"items": [{"ids": {"tmdb": 603}}], "total": 1, "matching": 1, "loaded": 1}

    class Handler(http.server.BaseHTTPRequestHandler):
        def _answer(self) -> None:
            path = self.path.split("?")[0]
            cookies = self.headers.get("Cookie") or ""
            sent = cookies.split(f"{COOKIE}=")[1] if f"{COOKIE}=" in cookies else None
            host.requests.append((self.command, path, sent))
            key = f"{self.command} {path.removeprefix('/api/v1')}"
            default = (200, items if key == "GET /library/items" else {})
            status, body = host.answers.get(key, default)
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = _answer

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Callable[..., tuple[int, str]]:
    """Run the smoke's ``main`` against a base and a contract, with the fake CLI.

    Args:
        tmp_path: Scratch directory.
        capsys: Captures the script's stdout and stderr.

    Returns:
        A callable returning the exit code and everything printed.
    """
    module = _load()

    def _run(base: str, contract: Path, cli: list[str] | None = None) -> tuple[int, str]:
        code = module.main(["--base", base, "--contract", str(contract)], cli=cli or _cli(tmp_path))
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    return _run


def test_every_get_is_called_and_no_write_is(tmp_path: Path, run: Callable[..., tuple[int, str]]) -> None:
    """Every GET of the contract is called, signed in, with the library's ids; no POST but the sign-out."""
    with _host() as (host, base):
        code, out = run(base, _contract(tmp_path))
    gets = [(path, cookie) for method, path, cookie in host.requests if method == "GET"]
    assert sorted(path for path, _ in gets) == [
        "/api/v1/library/items",
        "/api/v1/media/tmdb/603",
        "/api/v1/version",
    ]
    assert {cookie for _, cookie in gets} == {TOKEN}
    assert [(m, p) for m, p, _ in host.requests if m != "GET"] == [("POST", "/api/v1/auth/logout")]
    assert (code, out.strip()) == (0, "SMOKE OK 3 GETs")


def test_a_503_names_the_operation(tmp_path: Path, run: Callable[..., tuple[int, str]]) -> None:
    """A 503 gives one ``SMOKE RED`` line with the operation id, the status and the problem's code."""
    with _host({"GET /media/tmdb/603": (503, {"code": "library.unavailable"})}) as (_, base):
        code, out = run(base, _contract(tmp_path))
    assert code == 1
    assert out.strip().splitlines() == ["SMOKE RED readMediaSheet 503 library.unavailable"]


def test_a_new_get_with_an_unknown_required_parameter_is_red(
    tmp_path: Path, run: Callable[..., tuple[int, str]]
) -> None:
    """A required parameter with no source is red by name, and that GET is not called."""
    new_get = {"operationId": "readThing", "parameters": [{"name": "shelf", "in": "query", "required": True}]}
    with _host() as (host, base):
        code, out = run(base, _contract(tmp_path, {"/thing": new_get}))
    assert code == 1
    assert out.strip().splitlines() == ["SMOKE RED readThing 0 unresolvable parameter shelf"]
    assert all(path != "/api/v1/thing" for _, path, _ in host.requests)


def test_sign_out_happens_even_after_a_red(tmp_path: Path, run: Callable[..., tuple[int, str]]) -> None:
    """After a red, the session is still closed, with its own cookie."""
    with _host({"GET /version": (500, {"code": "internal"})}) as (host, base):
        code, _ = run(base, _contract(tmp_path))
    assert code == 1
    assert ("POST", "/api/v1/auth/logout", TOKEN) in host.requests


def test_the_token_never_appears_in_the_output(tmp_path: Path, run: Callable[..., tuple[int, str]]) -> None:
    """Green, red, a 401 or a dead host: the session value is on no printed line."""
    outputs = []
    with _host() as (_, base):
        outputs.append(run(base, _contract(tmp_path))[1])
    with _host({"GET /version": (401, {"code": TOKEN}), "GET /media/tmdb/603": (500, {})}) as (_, base):
        outputs.append(run(base, _contract(tmp_path))[1])
    outputs.append(run("http://127.0.0.1:1", _contract(tmp_path))[1])
    assert all(TOKEN not in out for out in outputs)
    assert "SMOKE RED readVersion 401" in outputs[1]


def test_an_empty_library_is_red(tmp_path: Path, run: Callable[..., tuple[int, str]]) -> None:
    """A library with no item is red: nothing proves the host serves any title."""
    empty = {"items": [], "total": 0, "matching": 0, "loaded": 0}
    with _host({"GET /library/items": (200, empty)}) as (_, base):
        code, out = run(base, _contract(tmp_path))
    assert code == 1
    assert "SMOKE RED readLibraryItems 200 library.empty" in out


def test_a_cli_that_fails_is_red_and_calls_nothing(tmp_path: Path, run: Callable[..., tuple[int, str]]) -> None:
    """No token, no call: the CLI's failure is one red line."""
    with _host() as (host, base):
        code, out = run(base, _contract(tmp_path), cli=_cli(tmp_path, token="", exit_code=1))
    assert code == 1
    assert host.requests == []
    assert out.strip().startswith("SMOKE RED openSession 1 ")
