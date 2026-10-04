"""The design host's two switches: its door, and its own rebuild.

WHAT IT PAYS FOR. Once the v1 sign-in is tm-design's door, the host must ask v1
who is signed in instead of checking its shared password (`TM_DESIGN_GATE=v1`),
and the application's code must never reach a visitor v1 has not signed in. And
a host that serves a tree another process builds must never rebuild it itself
(`TM_DESIGN_REBUILD=off`) — its own `npm run build` has no `--mode design-host`,
and would silently serve a full-mock build. The defaults (`shared`, `on`) are
what every harness rule reads.

WHAT MAKES IT NON-VACUOUS. `serve.py` runs as the process it is, on an
ephemeral port, over a scratch design root, and v1 is a stub on another port
that accepts one session value and counts what it is asked. The door is read on
the wire: the sign-in page and a 401 with no session or a refused one, the
document with an accepted one, a named 503 when v1 does not answer. The rebuild
is read through the scratch `package.json`, whose `build` script leaves a mark:
with the switch on, a stale build leaves it — so the probe sees a spawn when
there is one — and with it off, nothing is spawned.
"""

from __future__ import annotations

import http.client
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from _repo_paths import MAQUETTE

ROOT = Path(__file__).resolve().parents[2]
DESIGN = MAQUETTE / "design"
SERVE = MAQUETTE / "serve.py"

# What the scratch build serves, so the document is told from the sign-in page.
DOCUMENT = b"<!doctype html><html><head></head><body>the built document</body></html>"
# Where the scratch `build` script leaves its mark when npm runs it.
MARK = "npm-ran"
# The npm `serve.py` itself would call, mirrored: the operator's when present.
OPERATOR_NPM = "/Users/izno/.nvm/versions/node/v22.13.1/bin/npm"


def scratch_root(tmp_path: Path, *, stale: bool) -> Path:
    """Build a scratch design root that `serve.py` can serve.

    Args:
        tmp_path: The pytest scratch directory.
        stale: Whether the build is older than its sources.

    Returns:
        The root: the real shell document, stylesheets and resource (the sign-in
        page is extracted from them), a `package.json` whose build leaves a mark,
        and a `dist/` holding a known document.
    """
    root = tmp_path / "design"
    (root / "src" / "styles").mkdir(parents=True)
    (root / "src" / "i18n").mkdir()
    shutil.copy2(DESIGN / "index.html", root / "index.html")
    for name in ("base.css", "theme.css"):
        shutil.copy2(DESIGN / "src" / "styles" / name, root / "src" / "styles" / name)
    shutil.copy2(DESIGN / "src" / "i18n" / "fr.json", root / "src" / "i18n" / "fr.json")
    for name in ("vite.config.mjs", "build-identity.mjs", "worker-source.mjs"):
        (root / name).write_text("// scratch\n", encoding="utf-8")
    (root / "package.json").write_text(
        f'{{"name": "scratch", "private": true, "scripts": {{"build": "touch {MARK}"}}}}\n',
        encoding="utf-8",
    )
    (root / "dist" / "vite").mkdir(parents=True)
    (root / "dist" / "index.html").write_bytes(DOCUMENT)
    (root / "dist" / "vite" / "entry.js").write_text("export {};\n", encoding="utf-8")
    sources = max(path.stat().st_mtime for path in root.rglob("*") if path.is_file() and "dist" not in path.parts)
    built = sources - 60 if stale else sources + 60
    os.utime(root / "dist" / "index.html", (built, built))
    return root


def free_port() -> int:
    """Return a port nothing listens on now.

    Returns:
        An ephemeral port of the loopback.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def serving(root: Path, **switches: str) -> Iterator[int]:
    """Run `serve.py` over a scratch root until the block ends.

    Args:
        root: The scratch design root.
        **switches: The host's environment, by name.

    Yields:
        The port it answers on.
    """
    port = free_port()
    environment = {**os.environ, "TM_DESIGN_ROOT": str(root), **switches}
    process = subprocess.Popen(
        [sys.executable, str(SERVE), str(port)],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    # Stopped first: reading a live process's stderr would block.
                    process.kill()
                    process.wait(timeout=10)
                    said = process.stderr.read().decode() if process.stderr else ""
                    raise AssertionError(said or "serve.py never answered")
                time.sleep(0.05)
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)
        if process.stderr:
            process.stderr.close()


def ask(
    port: int, path: str, method: str = "GET", body: str | None = None, cookie: str | None = None
) -> tuple[int, dict[str, str], bytes]:
    """Ask the host once.

    Args:
        port: The host's port.
        path: The address.
        method: The method.
        body: A form body, if any.
        cookie: The `Cookie` header, if any.

    Returns:
        The status, the headers (lower-case names), and the body.
    """
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    headers = {"Content-Type": "application/x-www-form-urlencoded"} if body is not None else {}
    if cookie is not None:
        headers["Cookie"] = cookie
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    found = {name.lower(): value for name, value in response.getheaders()}
    connection.close()
    return response.status, found, data


# The one session value the stub v1 accepts.
ACCEPTED = "accepted-session"


@contextmanager
def stub_v1() -> Iterator[tuple[str, list[str]]]:
    """Run a stub v1 that accepts one session on `/api/v1/auth/me`.

    Yields:
        Its base URL, and the `Cookie` headers it was asked with, in order.
    """
    asked: list[str] = []

    class AuthMe(http.server.BaseHTTPRequestHandler):
        """Answers `/api/v1/auth/me`: 200 for the accepted session, 401 otherwise."""

        def do_GET(self) -> None:  # noqa: N802 — name imposed by BaseHTTPRequestHandler
            """Answer one session check."""
            cookie = self.headers.get("Cookie") or ""
            asked.append(cookie)
            status = 200 if self.path == "/api/v1/auth/me" and cookie == f"tm_v1_session={ACCEPTED}" else 401
            self.send_response(status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, fmt: str, *args: object) -> None:
            """Stay quiet."""

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), AuthMe)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", asked
    finally:
        server.shutdown()
        server.server_close()


def test_the_shared_door_by_default_shows_its_own_sign_in_page(tmp_path: Path) -> None:
    """With no switch set, the document is behind the host's own password form."""
    with serving(scratch_root(tmp_path, stale=False)) as port:
        status, _, body = ask(port, "/")
        assert status == 401
        assert b'action="/login"' in body
        assert b"/api/v1/auth/login" not in body
        assert b"the built document" not in body
        assert ask(port, "/vite/entry.js")[0] == 401


def test_the_v1_door_shows_its_sign_in_page_to_no_session(tmp_path: Path) -> None:
    """With no session, the v1 door answers 401 with a page that posts to v1, and asks v1 nothing."""
    with (
        stub_v1() as (v1, asked),
        serving(scratch_root(tmp_path, stale=False), TM_DESIGN_GATE="v1", TM_DESIGN_V1_URL=v1) as port,
    ):
        status, headers, body = ask(port, "/")
        assert status == 401
        assert b"/api/v1/auth/login" in body
        assert b'type="email"' in body
        assert b'action="/login"' not in body
        assert b"the built document" not in body
        assert ask(port, "/vite/entry.js")[0] == 401
        assert "set-cookie" not in headers
        assert asked == []


def test_the_v1_door_serves_the_document_to_a_session_v1_accepts(tmp_path: Path) -> None:
    """An accepted session gets the document and its bundle, v1 asked once for both."""
    with (
        stub_v1() as (v1, asked),
        serving(scratch_root(tmp_path, stale=False), TM_DESIGN_GATE="v1", TM_DESIGN_V1_URL=v1) as port,
    ):
        cookie = f"tm_design=other; tm_v1_session={ACCEPTED}"
        status, _, body = ask(port, "/", cookie=cookie)
        assert status == 200 and b"the built document" in body, body[:300]
        assert ask(port, "/vite/entry.js", cookie=cookie)[0] == 200
        # Only v1's own cookie is forwarded, and the second ask is the cache's.
        assert asked == [f"tm_v1_session={ACCEPTED}"]


def test_the_v1_door_refuses_a_session_v1_refuses(tmp_path: Path) -> None:
    """A session v1 refuses gets the sign-in page, and the refusal is asked again, never kept."""
    with (
        stub_v1() as (v1, asked),
        serving(scratch_root(tmp_path, stale=False), TM_DESIGN_GATE="v1", TM_DESIGN_V1_URL=v1) as port,
    ):
        for _ in range(2):
            status, _, body = ask(port, "/", cookie="tm_v1_session=ended")
            assert status == 401 and b"the built document" not in body
        assert len(asked) == 2


def test_the_v1_door_names_v1_when_it_does_not_answer(tmp_path: Path) -> None:
    """v1 down is a 503 naming it, never the sign-in page."""
    silent = f"http://127.0.0.1:{free_port()}"
    with serving(scratch_root(tmp_path, stale=False), TM_DESIGN_GATE="v1", TM_DESIGN_V1_URL=silent) as port:
        status, _, body = ask(port, "/", cookie=f"tm_v1_session={ACCEPTED}")
    assert status == 503
    assert silent.encode() in body
    assert b"loginform" not in body


def test_the_v1_door_answers_no_form_post_and_issues_no_cookie(tmp_path: Path) -> None:
    """Under the v1 door, the host's own form post is no door: 303 home, no cookie."""
    with (
        stub_v1() as (v1, _),
        serving(scratch_root(tmp_path, stale=False), TM_DESIGN_GATE="v1", TM_DESIGN_V1_URL=v1) as port,
    ):
        status, headers, _ = ask(port, "/login", "POST", "username=izno&password=wrong")
    assert (status, headers.get("location")) == (303, "/")
    assert "set-cookie" not in headers


def test_a_setting_takes_its_values_and_nothing_else(tmp_path: Path) -> None:
    """A switch set to a value it does not take stops the host at boot, naming it."""
    with pytest.raises(AssertionError, match="TM_DESIGN_GATE"):
        with serving(scratch_root(tmp_path, stale=False), TM_DESIGN_GATE="off"):
            pass


def test_the_rebuild_off_never_spawns_npm(tmp_path: Path) -> None:
    """With the rebuild off, a stale build is a named 503 and npm is never run."""
    root = scratch_root(tmp_path, stale=True)
    with stub_v1() as (v1, _), serving(root, TM_DESIGN_GATE="v1", TM_DESIGN_V1_URL=v1, TM_DESIGN_REBUILD="off") as port:
        status, _, body = ask(port, "/", cookie=f"tm_v1_session={ACCEPTED}")
    assert status == 503
    assert b"TM_DESIGN_REBUILD" in body
    assert not (root / MARK).exists()


def test_the_rebuild_on_spawns_npm_over_a_stale_build(tmp_path: Path) -> None:
    """The probe's control: with the rebuild on, the same stale build runs npm."""
    if not (os.path.exists(OPERATOR_NPM) or shutil.which("npm")):
        pytest.skip("no npm on this machine — the rebuild cannot be driven here")
    root = scratch_root(tmp_path, stale=True)
    with stub_v1() as (v1, _), serving(root, TM_DESIGN_GATE="v1", TM_DESIGN_V1_URL=v1) as port:
        ask(port, "/", cookie=f"tm_v1_session={ACCEPTED}")
    assert (root / MARK).exists()


# Drives the v1 sign-in page's script under node, over a stand-in document: the
# page is loaded `loads` times, sharing one session storage and one clock, and
# `/api/v1/auth/me` answers `status` each time it is asked.
PROBE_DRIVER = """
const script = process.argv[1];
const status = Number(process.argv[2]);
const loads = Number(process.argv[3]);
const stored = {};
const seen = { asked: 0, replaced: 0 };
globalThis.sessionStorage = {
  getItem: (key) => (key in stored ? stored[key] : null),
  setItem: (key, value) => { stored[key] = String(value); },
};
globalThis.location = { pathname: '/', search: '', replace: () => { seen.replaced += 1; } };
globalThis.document = { querySelector: () => ({ addEventListener: () => {} }) };
globalThis.fetch = (path) => {
  if (path === '/api/v1/auth/me') seen.asked += 1;
  return Promise.resolve({ ok: status === 200, status });
};
(async () => {
  for (let load = 0; load < loads; load += 1) {
    new Function(script)();
    await new Promise((settle) => setTimeout(settle, 0));
  }
  console.log(JSON.stringify(seen));
})();
"""


def probe(status: int, loads: int) -> dict[str, int]:
    """Run the v1 sign-in page's script, as `loads` page loads in a row.

    Args:
        status: What `/api/v1/auth/me` answers.
        loads: How many times the page loads within the ten seconds.

    Returns:
        How many times v1 was asked, and how many times the page reloaded.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("no node on this machine — the sign-in page's script cannot be driven here")
    sys.path.insert(0, str(MAQUETTE))
    try:
        import v1_door
    finally:
        sys.path.remove(str(MAQUETTE))
    script = v1_door.V1_SIGN_IN.strip().removeprefix("<script>").removesuffix("</script>")
    run = subprocess.run(
        [node, "-e", PROBE_DRIVER, script, str(status), str(loads)],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(run.stdout)


def test_the_sign_in_page_reloads_once_for_a_session_v1_holds() -> None:
    """A session held but not sent on arrival reloads the page once, and never again within ten seconds."""
    assert probe(200, loads=3) == {"asked": 1, "replaced": 1}


def test_the_sign_in_page_never_reloads_when_v1_refuses() -> None:
    """With no session v1 holds, the page asks once and stays: no reload, no loop."""
    assert probe(401, loads=3) == {"asked": 1, "replaced": 0}
