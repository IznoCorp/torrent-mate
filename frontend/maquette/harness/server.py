"""A static server that lets deep client-side paths be requested directly.

The plain `http.server` on 8899 — the one every existing rule points at —
answers a file for a file's own path and nothing else: request `/profile/12`
against it and the answer is 404, because no such file exists on disk. The
router only ever sees a path like that from inside an already-loaded
document, never from a fresh navigation, so nothing measured through 8899
can tell a reload, a shared link, or a browser back button from a 404.

This module holds the server that closes that gap, and nothing else. Files
under its root are served as-is; any other path that does not resolve to an
existing file instead answers `wrapped.html`, exactly the way a host serving
a single-page application is expected to — EXCEPT under `ASSET_PREFIXES`,
where a missing file stays a 404: a route-shaped address can carry dots of
its own (a release folder name, `Backrooms.2026.MULTi.2160p.WEB-DL`, is not
a file extension), so a dot in the final segment is no longer what decides
the fold. It is not a replacement for 8899: that server keeps its narrower
job, and every existing rule keeps pointing at it. This one is a second,
thread-backed server a rule can start on its own scratch port, hand a root,
and stop again without leaving a process behind.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import os
import pathlib
import threading
from collections.abc import Iterator

# Never one of these: 8710/8711/8712 are the reverse proxy's routes to prod
# and staging, and 8899 is the prototype's own host — 45 rules already point
# at it, and a second server on the same port would just race it for the
# socket.
RESERVED_PORTS = (8710, 8711, 8712, 8899)


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
    # addressable static files (`assets/…`, `vite/…`), never a route param
    # that merely happens to contain a dot.
    ASSET_PREFIXES = ("/assets/", "/vite/")

    def translate_path(self, path: str) -> str:
        """Returns the filesystem path a request resolves to.

        Args:
            path: The raw request path, exactly as `http.server` passes it
                to this seam — query string and fragment included.

        Returns:
            The resolved path from the parent implementation when it names
            an existing file, or falls under `ASSET_PREFIXES` (a missing
            asset reference stays a 404, never the document);
            `directory/wrapped.html` for every other path with no file
            behind it.
        """
        resolved = super().translate_path(path)
        if os.path.isfile(resolved):
            return resolved
        path_ = path.split("?", 1)[0]
        if path_.startswith(self.ASSET_PREFIXES):
            return resolved
        return os.path.join(self.directory, "wrapped.html")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — name imposed by BaseHTTPRequestHandler
        """Silences per-request logging.

        A rule driving many requests does not need a stderr line per one —
        the assertions it runs afterward ARE the record of what happened.
        """


@contextlib.contextmanager
def start_server(port: int, root: pathlib.Path) -> Iterator[None]:
    """Serves `root` on `port` for the lifetime of the `with` block.

    Files under `root` are served as-is; any path with no file behind it
    instead answers `root/wrapped.html` — the fallback that lets a deep
    client-side address (`/profile/…`, `/add`, `/resolution/<dossier
    portant des points>`) be requested directly rather than only reached by
    navigating there inside an already-loaded document — EXCEPT under
    `FallbackHandler.ASSET_PREFIXES`, where a missing file still 404s.

    Args:
        port: The loopback port to bind. Must not be one of
            `RESERVED_PORTS`.
        root: The directory to serve. Must contain `wrapped.html`.

    Yields:
        Nothing — the server runs on a daemon thread for the block's
        duration and is reachable at `http://127.0.0.1:{port}/` as soon as
        the `with` statement is entered.

    Raises:
        ValueError: When `port` is one of `RESERVED_PORTS`.
    """
    if port in RESERVED_PORTS:
        raise ValueError(f"reserved port: {port}")
    handler = functools.partial(FallbackHandler, directory=str(root))
    # ThreadingHTTPServer's constructor binds and listens before returning
    # (bind_and_activate defaults to True) — by the time this line completes,
    # a connection from another thread queues rather than being refused.
    # Nothing below is timing-sensitive: the serving thread only pulls
    # requests off a queue that already exists, so no sleep is needed
    # between starting it and treating the server as ready.
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    import sys
    import urllib.error
    import urllib.request

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from common import Journal

    PROOF_PORT = 8917
    PROOF_ROOT = pathlib.Path("/tmp/tm-refonte")

    journal = Journal("server.py — the fallback answers deep addresses")

    expected = (PROOF_ROOT / "wrapped.html").read_bytes()
    bundles = sorted((PROOF_ROOT / "vite").glob("*.js"))
    if not journal.check("a bundle exists under vite/ for the proof",
                         bool(bundles), f"{len(bundles)} found"):
        journal.summary()
    bundle = bundles[0]

    with start_server(PROOF_PORT, PROOF_ROOT):
        base = f"http://127.0.0.1:{PROOF_PORT}"

        with urllib.request.urlopen(f"{base}/profile/X%20Y", timeout=5) as response:
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

    journal.summary()
