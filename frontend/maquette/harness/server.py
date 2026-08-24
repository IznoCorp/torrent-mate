"""The prototype's host, and the reason it is not a plain static server.

A plain `http.server` answers a file for a file's own path and nothing else:
request `/media` against it and the answer is 404, because no such file exists
on disk. Every page now sits on a real path, so that answer is wrong twice
over — a reload, a shared link and a browser Back all arrive as fresh
navigations, and the router would render its not-found page for each. Nothing
measured through such a host could tell a deep address from a broken one.

Files under the served root go out as-is; any other path with no file behind
it answers `wrapped.html`, the way a host serving a single-page application is
expected to. Two sets are excepted, and a missing file in either stays a 404:
`ASSET_PREFIXES`, the directories that hold real addressable files, and
`ASSET_PATHS`, the root-level resources the document itself asks for. A dot in
the final segment is deliberately NOT what decides the fold — a release folder
name (`Backrooms.2026.MULTi.2160p.WEB-DL`) carries dots and is not a file.

It is used two ways. `serve_forever` is the HOST on 8899 that `run.sh` starts
and every rule reads. `start_server` is a scratch server a rule can raise on a
port the kernel picks, hand a root, and drop again without leaving a process
behind.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import os
import pathlib
import re
import tempfile
import threading
from collections.abc import Iterator

# Never one of these: 8710/8711/8712 are the reverse proxy's routes to prod,
# staging and the design host, and 8899 is the prototype's own host — every
# rule reads it, and a second server there would just race it for the socket.
# The HOST is exempt from 8899 alone, because it IS that host; nothing is ever
# exempt from the proxy's three, and « nothing » includes the host: `--serve
# 8710` would put the prototype on the port Caddy sends prod's traffic to.
RESERVED_PORTS = (8710, 8711, 8712, 8899)

# The prototype's own host, and the only reservation anything may claim.
HOST_PORT = 8899


def refuse_reserved(port: int, *, host_allowed: bool) -> None:
    """Refuses a port that belongs to something else, before any socket is asked for.

    Args:
        port: The loopback port about to be bound. 0 asks the kernel for a
            free one and is never reserved.
        host_allowed: True for the prototype's own host, which may bind
            `HOST_PORT` because it IS that host; False for a scratch server,
            which may bind none of the reserved ports at all.

    Raises:
        ValueError: When `port` is reserved and this caller may not have it.
            Named rather than described: the message carries the port, so a
            misconfigured launcher says which number it asked for.
    """
    if port not in RESERVED_PORTS:
        return
    if host_allowed and port == HOST_PORT:
        return
    raise ValueError(
        f"refusing to bind port {port}: it is reserved "
        f"({RESERVED_PORTS[0]}/{RESERVED_PORTS[1]}/{RESERVED_PORTS[2]} are the reverse "
        f"proxy's routes, {HOST_PORT} is the prototype's host)")


class FallbackHandler(http.server.SimpleHTTPRequestHandler):
    """Serves `directory` as-is; answers `wrapped.html` for every other path.

    `translate_path` is the one seam `SimpleHTTPRequestHandler` offers for
    this: it turns a request path into a filesystem path, and the base
    implementation has already resolved the query string, percent-encoding
    and any `..` segment before this override ever sees the result —
    reimplementing any of that here would be the same bug waiting to be
    reintroduced. A path is treated as the router's when the resolved path
    is not an existing FILE and does not fall under `ASSET_PREFIXES` — the
    directories this root actually serves real, addressable files from. A
    missing file THERE (`/vite/absent.js`) still 404s through the parent
    implementation; everywhere else, no file behind the address folds to the
    document.

    Testing for a FILE rather than mere existence is what makes the bare
    root fall back too: `self.directory` itself exists as a directory, so an
    `exists()` check alone would defer "/" to the parent's own directory
    listing instead of the document every other router-owned address
    already gets — the one entry point a single-page application is
    guaranteed to be asked for.

    A dot in the final segment is deliberately NOT what decides the fold: a
    route param can carry one of its own (a release folder name,
    `Backrooms.2026.MULTi.2160p.WEB-DL`) without being a file extension, and
    only the served directory's actual layout — not a string's shape — says
    which paths are real files.
    """

    # The only directories under a served root this handler answers a
    # missing path from with a 404 rather than the document — real,
    # addressable static files (`assets/…`, `vite/…`, the dev entry under
    # `src/…`), never a route param that merely happens to contain a dot.
    ASSET_PREFIXES = ("/assets/", "/vite/", "/src/")

    # And the root-level files the DOCUMENT ITSELF asks for. They are not a
    # directory, so no prefix covers them, and they must 404 when absent for
    # the same reason: they are resources, never addresses.
    #
    # This is written from the browser's own behaviour rather than guessed.
    # `index.html` registers `/sw.js` and links the other three; the harness
    # root carries none of them (the design host synthesises them). Folded onto
    # the document they answer 200 `text/html`, and the browser then logs « The
    # script has an unsupported MIME type ('text/html') » — a console ERROR,
    # which is a failure for every rule that counts them. A host claiming to
    # have a service worker it does not have is also simply untrue.
    #
    # Deciding this by a dot in the last segment is exactly what the class
    # docstring above refuses, and for a reason already paid for: a release
    # folder name carries dots and is not a file. So these are NAMED.
    ASSET_PATHS = (
        "/sw.js",
        "/manifest.webmanifest",
        "/favicon.svg",
        "/apple-touch-icon.png",
    )

    def translate_path(self, path: str) -> str:
        """Returns the filesystem path a request resolves to.

        Args:
            path: The raw request path, exactly as `http.server` passes it
                to this seam — query string and fragment included.

        Returns:
            The resolved path from the parent implementation when it names
            an existing file, or falls under `ASSET_PREFIXES`, or IS one of
            `ASSET_PATHS` (a missing asset reference stays a 404, never the
            document); `directory/wrapped.html` for every other path with no
            file behind it.
        """
        resolved = super().translate_path(path)
        if os.path.isfile(resolved):
            return resolved
        path_ = path.split("?", 1)[0]
        if path_.startswith(self.ASSET_PREFIXES) or path_ in self.ASSET_PATHS:
            return resolved
        return os.path.join(self.directory, "wrapped.html")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — name imposed by BaseHTTPRequestHandler
        """Silences per-request logging.

        A rule driving many requests does not need a stderr line per one —
        the assertions it runs afterward ARE the record of what happened.
        """


@contextlib.contextmanager
def start_server(root: pathlib.Path) -> Iterator[int]:
    """Serves `root` on a scratch port for the lifetime of the `with` block.

    Files under `root` are served as-is; any path with no file behind it
    instead answers `root/wrapped.html` — the fallback that lets a deep
    client-side address (`/quality/…`, `/add`, `/resolution/<dossier
    portant des points>`) be requested directly rather than only reached by
    navigating there inside an already-loaded document — EXCEPT under
    `FallbackHandler.ASSET_PREFIXES`, where a missing file still 404s.

    There is deliberately no `port` parameter: the kernel picks one, and
    the port actually bound is yielded so the caller composes its
    addresses from the truth rather than from the request. A scratch
    server has no reason to want a fixed port, and a fixed one is a list
    that drifts — rules that pick from the same list eventually collide
    on one socket.

    Args:
        root: The directory to serve. Must contain `wrapped.html`.

    Yields:
        int: The loopback port the kernel chose. The server runs on a
        daemon thread for the block's duration and is reachable on that
        port as soon as the `with` statement is entered.
    """
    handler = functools.partial(FallbackHandler, directory=str(root))
    # ThreadingHTTPServer's constructor binds and listens before returning
    # (bind_and_activate defaults to True) — by the time this line completes,
    # a connection from another thread queues rather than being refused.
    # Nothing below is timing-sensitive: the serving thread only pulls
    # requests off a queue that already exists, so no sleep is needed
    # between starting it and treating the server as ready.
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # The truth about where the server listens — the request said 0, the
        # kernel decided, and the caller composes addresses from this.
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def serve_forever(port: int, root: pathlib.Path) -> None:
    """Serves `root` on `port` in the FOREGROUND, until the process is killed.

    This is the prototype's own host, not a rule's scratch server, and the
    difference is ONE port. `start_server` asks for none — the kernel picks,
    so a rule can never race the host for the socket; here the caller IS
    that host, so 8899 is the one number it may have. The proxy's three are
    refused to it exactly as they are to a rule — `--serve 8710` would put the
    prototype on the port Caddy sends prod's traffic to, and « the caller is
    the host » is no reason to hand it a port that is somebody else's.

    The host must fold unknown addresses onto the document: a page sits at a
    real path (`/media`), and a plain `http.server` answers 404 for every path
    with no file behind it — which the router would render as its not-found
    page, collapsing every rule, the oracle and the accessibility audit at once
    for a reason unrelated to whatever was being measured.

    Args:
        port: The loopback port to bind. `HOST_PORT` is the one reservation
            this caller may claim.
        root: The directory to serve. Must contain `wrapped.html`.

    Raises:
        ValueError: When `port` is a reservation that is not this host's.
    """
    refuse_reserved(port, host_allowed=True)
    handler = functools.partial(FallbackHandler, directory=str(root))
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


# A Python comment and a Python string, the three quoting styles included. The
# reader below blanks them IN PLACE — spaces for everything but the newlines —
# so a line number counted afterwards is still the source's own.
_PROSE = re.compile(
    r'''#[^\n]*|"""(?:\\.|[^\\])*?"""|\'\'\'(?:\\.|[^\\])*?\'\'\''''
    r'''|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'''',
    re.S)


def without_prose(text: str) -> str:
    """Blanks every Python comment and string literal, leaving offsets where they were.

    Args:
        text: A Python source.

    Returns:
        The same text, its comments and string literals replaced by spaces.
    """
    return _PROSE.sub(lambda prose: re.sub(r"[^\n]", " ", prose.group(0)), text)


def scratch_call_offenders(directory: pathlib.Path) -> list[str]:
    """Names the `start_server` call sites under `directory` that pass a port.

    Reads each `*.py` file's WHOLE text and finds every `start_server(` in
    it, then reads the argument list with a balanced-parentheses walk,
    tolerant of newlines and of nested calls: a call the formatter wrapped
    over two lines is still seen, and a call whose argument is itself a call is
    not flagged for its inner comma. A call is an offender when its TOP-LEVEL
    argument list carries a comma — a second argument, the port — or is empty.
    A `def start_server(...)` line is the definition, not a call, and is
    skipped. An alias import (`from server import start_server as X`) never
    reaches this reader, because the aliased name is what its call sites
    would use — a reach this hold does not claim.

    AND PROSE IS NOT CODE. An example written in a docstring or behind a `#`
    used to be read as a call site, so the sentence explaining the rule could
    fail it — and the only fix available to whoever hit that would be to delete
    the explanation. Comments and string literals are blanked before the scan,
    in place, so the line numbers below are still the source's own.

    Args:
        directory: The harness directory; every `*.py` in it is read.

    Returns:
        list[str]: One `file:line` per offending call site, in read order.
    """
    offenders: list[str] = []
    for sibling in sorted(directory.glob("*.py")):
        text = without_prose(sibling.read_text(encoding="utf-8"))
        for match in re.finditer(r"\bstart_server\(", text):
            line = text.count("\n", 0, match.start()) + 1
            line_start = text.rfind("\n", 0, match.start()) + 1
            if text[line_start:match.start()].lstrip().startswith("def "):
                continue  # the definition, not a call site
            depth = 1
            cursor = match.end()
            while depth and cursor < len(text):
                if text[cursor] == "(":
                    depth += 1
                elif text[cursor] == ")":
                    depth -= 1
                cursor += 1
            if depth:
                continue  # unbalanced — not a call this reader can judge
            arguments = text[match.end():cursor - 1]
            nested = 0
            passes_a_port = False
            for character in arguments:
                if character == "(":
                    nested += 1
                elif character == ")":
                    nested -= 1
                elif character == "," and nested == 0:
                    passes_a_port = True
                    break
            if passes_a_port or not arguments.strip():
                offenders.append(f"{sibling.name}:{line}")
    return offenders


if __name__ == "__main__":
    import sys
    import urllib.error
    import urllib.request

    # `--serve` is the HOST; the bare invocation is the RULE. They are split by
    # a flag rather than by which module is run, because `run.sh` executes every
    # `*.py` in this directory as a rule: overloading the bare invocation into a
    # launcher would block the suite forever on this file, and removing the
    # self-proof to avoid that would silently drop a rule from the count.
    if "--serve" in sys.argv:
        arguments = sys.argv[sys.argv.index("--serve") + 1:]
        serve_forever(int(arguments[0]), pathlib.Path(arguments[1]))
        sys.exit(0)

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from common import Journal

    # The scratch port is ephemeral: 0 asks the kernel for a free one and the
    # port actually bound comes back from the context manager. A fixed port is
    # a list that drifts, and rules picking from the same list collide on it.
    PROOF_ROOT = pathlib.Path("/tmp/tm-refonte")

    journal = Journal("server.py — the fallback answers deep addresses")

    expected = (PROOF_ROOT / "wrapped.html").read_bytes()
    bundles = sorted((PROOF_ROOT / "vite").glob("*.js"))
    if not journal.check("a bundle exists under vite/ for the proof",
                         bool(bundles), f"{len(bundles)} found"):
        journal.summary()
    bundle = bundles[0]

    with start_server(PROOF_ROOT) as port:
        base = f"http://127.0.0.1:{port}"

        with urllib.request.urlopen(f"{base}/quality/X%20Y", timeout=5) as response:
            profile_status, profile_body = response.status, response.read()
        journal.check(
            "a deep address answers 200 + the document",
            profile_status == 200 and profile_body == expected,
            f"status {profile_status}, {len(profile_body)} bytes")

        with urllib.request.urlopen(f"{base}/vite/{bundle.name}", timeout=5) as response:
            bundle_status, bundle_body = response.status, response.read()
        journal.check(
            "the real bundle is served as-is",
            bundle_status == 200 and bundle_body == bundle.read_bytes(),
            f"status {bundle_status}, {bundle.name}")

        try:
            urllib.request.urlopen(f"{base}/assets/inexistant.png", timeout=5)
            missing_status = 200
        except urllib.error.HTTPError as error:
            missing_status = error.code
        journal.check(
            "a missing asset UNDER A SERVED DIRECTORY 404s instead of folding to the document",
            missing_status == 404, f"status {missing_status}")

        # The same promise for the root-level resources the document asks for
        # by name. Folded onto the document they answer 200 `text/html`, the
        # browser logs an unsupported MIME type, and every rule counting console
        # errors fails somewhere that looks nothing like a host setting.
        folded = []
        for named in FallbackHandler.ASSET_PATHS:
            try:
                with urllib.request.urlopen(f"{base}{named}", timeout=5) as response:
                    if response.status == 200:
                        folded.append(named)
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    folded.append(f"{named} → {error.code}")
        journal.check(
            "a missing root-level resource the document NAMES 404s "
            "instead of folding to the document",
            not folded, f"folded: {folded or 'none'}")

        # The regression this fold exists to close: a route-shaped address
        # whose deepest segment carries dots of its own — a release folder
        # name, never a file extension outside ASSET_PREFIXES — must fold
        # to the document exactly like the bare, extension-less case above.
        with urllib.request.urlopen(
            f"{base}/resolution/Backrooms.2026.MULTi.2160p.WEB-DL", timeout=5
        ) as response:
            folder_status, folder_body = response.status, response.read()
        journal.check(
            "a deep address whose last segment carries dots "
            "still answers the document",
            folder_status == 200 and folder_body == expected,
            f"status {folder_status}, {len(folder_body)} bytes")

        # A scratch server wanting a FIXED port is what this rule once
        # carried, and it is how two rules race one socket. Port 0 hands the
        # choice to the kernel; raising a SECOND scratch server while the
        # first is up proves the two never collide — it must get a different
        # free port and answer the same deep address on it.
        try:
            with start_server(PROOF_ROOT) as second_port:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{second_port}/quality/X%20Y", timeout=5
                ) as response:
                    second_status, second_body = response.status, response.read()
            second_holds = (
                isinstance(second_port, int)
                and second_port != 0
                and second_port != port
                and second_port not in RESERVED_PORTS
                and second_status == 200
                and second_body == expected)
            second_evidence = (
                f"first {port}, second {second_port}, status {second_status}")
        except urllib.error.HTTPError as answered:
            # An HTTP status is not a bind failure, and « refused » said it
            # was: the second server ANSWERED, and reading its answer as a
            # collision sends the next reader to the wrong half of this rule.
            second_holds = False
            second_evidence = f"first {port}, second server answered {answered.code}"
        except urllib.error.URLError as unreachable:
            second_holds = False
            second_evidence = (
                f"first {port}, second server unreachable: {unreachable.reason}")
        except OSError as error:
            # A socket error reaching HERE is not the request's: urlopen
            # wraps connection failures in URLError, caught above, and a
            # port-0 bind has no fixed address to collide on — so there is
            # nothing left to name but the raise itself.
            second_holds = False
            second_evidence = f"first {port}, second server failed to start: {error}"
        journal.check(
            "a scratch server yields a real ephemeral port, and a second never races it",
            isinstance(port, int) and port != 0 and port not in RESERVED_PORTS
            and second_holds,
            second_evidence)

    # ── the ports nothing here may bind ───────────────────────────────────
    # `--serve 8710` used to be accepted: the host had no guard at all, and
    # the only thing keeping the prototype off the port Caddy routes prod's
    # traffic to was that prod happened to be holding the socket. Read
    # through `serve_forever` itself rather than through the helper alone, so
    # the CALL is held and not merely the check — with the socket constructor
    # swapped for one that refuses, a broken guard is a caught assertion here
    # instead of a server left listening on a port that is not ours.
    def never_bind(*arguments: object, **keywords: object) -> None:
        """Stands in for the socket, so a guard that failed is caught, not bound."""
        raise AssertionError("reached the socket")

    real_server = http.server.ThreadingHTTPServer
    http.server.ThreadingHTTPServer = never_bind  # type: ignore[assignment,misc]
    try:
        serve_forever(8710, PROOF_ROOT)
        proxy_port = "bound it"
    except ValueError as refused:
        proxy_port = f"refused: {refused}"
    except AssertionError as reached:
        proxy_port = f"NOT refused, {reached}"
    finally:
        http.server.ThreadingHTTPServer = real_server  # type: ignore[misc]

    try:
        refuse_reserved(HOST_PORT, host_allowed=True)
        own_port = "kept"
    except ValueError as refused:
        own_port = f"refused: {refused}"
    try:
        refuse_reserved(HOST_PORT, host_allowed=False)
        rule_port = "accepted"
    except ValueError:
        rule_port = "refused"
    journal.check(
        "the host refuses a reverse-proxy port before it reaches the socket, "
        "and keeps only its own",
        proxy_port.startswith("refused:") and "8710" in proxy_port
        and own_port == "kept" and rule_port == "refused",
        f"8710 → {proxy_port} · {HOST_PORT} as the host → {own_port} · "
        f"{HOST_PORT} as a rule → {rule_port}")

    # ── every scratch server is raised without a port ────────────────────
    # A fixed port on a scratch server is invisible to every live hold
    # above: a non-zero, non-reserved one like 8918 answers « not 0 » and
    # « not reserved » both, so the rule stayed green over it — and two
    # rules set to that port would race one socket. What is read here is the
    # call sites themselves — every `*.py` in this directory, the same glob
    # `page_host.py` reads — and a call that still passes a port is named,
    # file and line. Reading the sources rather than running them is what
    # makes the hold bite on files nothing imports. The reader lives in
    # `scratch_call_offenders`, beside the host code it guards.
    harness_directory = pathlib.Path(__file__).resolve().parent
    offenders = scratch_call_offenders(harness_directory)
    journal.check(
        "every scratch server is raised without a port",
        not offenders,
        ", ".join(offenders)
        if offenders else
        f"{len(list(harness_directory.glob('*.py')))} file(s) read, no call passes a port")

    # AND THE READER READS CODE, NOT PROSE. An example written in a docstring
    # or behind a `#` is an example: a reader that flags one reports a defect
    # whose only fix is deleting the sentence that explains the rule. Both
    # directions are held over a scratch tree, because a reader that saw
    # nothing at all would pass the first half on its own.
    with tempfile.TemporaryDirectory() as scratch:
        room = pathlib.Path(scratch)
        (room / "prose.py").write_text(
            '"""An example, and it is prose: start_server(8918, ROOT)."""\n'
            "# start_server(8899, ROOT) behind a hash is prose too\n"
            "start_server(ROOT)\n",
            encoding="utf-8")
        written_as_prose = scratch_call_offenders(room)
        journal.check("a call site written in prose is not a call site",
                      written_as_prose == [], f"{written_as_prose}")
        (room / "real.py").write_text("start_server(8918, ROOT)\n", encoding="utf-8")
        really_called = scratch_call_offenders(room)
        journal.check("and a real call passing a port still is one",
                      really_called == ["real.py:1"], f"{really_called}")

    # ── the HOST, not a scratch server ────────────────────────────────────
    # Everything above proves the HANDLER, on a scratch port. This proves the
    # thing the suite actually reads: the host on 8899, which `run.sh` starts
    # through `--serve`. It is the hold that falls if anyone puts a plain
    # `python3 -m http.server` back there — that server answers a file for a
    # file's own path and 404 for every address the router owns, so the router
    # would render its not-found page and every rule after it would measure
    # that. Without this hold the failure looks like a broken interface rather
    # than a misconfigured host, which is a day of debugging in the wrong file.
    HOST = "http://127.0.0.1:8899"
    try:
        with urllib.request.urlopen(f"{HOST}/media", timeout=5) as response:
            host_status: object = response.status
    except urllib.error.HTTPError as error:
        host_status = error.code
    except OSError as trouble:  # noqa: BLE001 — a host that is not up IS the finding
        host_status = f"unreachable: {trouble}"
    journal.check(
        "the HOST on 8899 folds a router-owned address onto the document "
        "(a plain http.server would 404 here)",
        host_status == 200, f"GET {HOST}/media → {host_status}")

    journal.summary()
