#!/usr/bin/env python3
"""Serve the design prototype over HTTP, wrapped in a real document.

`refonte.html` is a head-less fragment: it starts at `<title>` and owns no
`<html>` or `<head>`, because it is authored to be embedded by a host page.
Served raw as a top-level document it renders in quirks mode, and a phone with
no viewport meta falls back to the legacy 980px layout viewport and scales the
frame down to roughly 40 % — measured, not feared.

This server supplies exactly the wrapper the harness builds, so the page a
browser is shown here is byte-for-byte the page the harness measures. Any
divergence between the two would make the published design unable to serve as
the reference it is meant to be.

It serves one document and nothing else. The directory around the prototype
holds the extraction contract, the harness and its scratch output; none of that
belongs on a public host.
"""

from __future__ import annotations

import http.server
import socketserver
import sys
from pathlib import Path

PROTOTYPE = Path(__file__).resolve().parent / "refonte.html"

# Identical to the wrapper the harness scripts build. Keep the two in step: the
# whole point of this server is that what is published equals what is measured.
HEAD = (
    b'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
    b'<meta name="viewport" '
    b'content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">'
    b"</head><body>"
)
TAIL = b"</body></html>"

# Encoded rather than written as a bytes literal: interface copy stays in
# French, and a bytes literal accepts no accented character.
MISSING = (
    '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    "<title>Prototype indisponible</title></head><body "
    'style="font:16px system-ui;max-width:34em;margin:12vh auto;padding:0 1.5em">'
    "<h1>Prototype indisponible</h1><p>Le fichier <code>refonte.html</code> est "
    "absent du checkout servi. C'est ce qui arrive quand la copie de travail est "
    "sur une branche qui ne le porte pas.</p><p>Rien n'est perdu : le prototype "
    "est en dépôt. Revenir sur la branche qui le porte le remet en ligne "
    "aussitôt.</p></body></html>"
).encode()


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves the wrapped prototype at the root, and 404s everything else."""

    # The file is ~15 MB and changes only when the design does, so it is read
    # once per modification rather than once per request. mtime_ns, not mtime:
    # a second-resolution stamp misses two edits within the same second, which
    # is exactly the cadence of an editing session.
    _cache: tuple[int, bytes] | None = None

    protocol_version = "HTTP/1.1"

    def _document(self) -> bytes | None:
        """Returns the wrapped prototype, or None when the file is absent.

        Returns:
            The full HTML document as bytes, or None if `refonte.html` does not
            exist in the served checkout.
        """
        try:
            stamp = PROTOTYPE.stat().st_mtime_ns
        except FileNotFoundError:
            return None
        cached = Handler._cache
        if cached is None or cached[0] != stamp:
            Handler._cache = (stamp, HEAD + PROTOTYPE.read_bytes() + TAIL)
        return Handler._cache[1]  # type: ignore[index]

    def _send(self, status: int, body: bytes) -> None:
        """Writes one complete response, headers included.

        Args:
            status: HTTP status code.
            body: Response body; sent verbatim.
        """
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # The design is read to be judged, and a judgement passed on a stale
        # copy is worse than no judgement. Revalidate every time.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 — name imposed by BaseHTTPRequestHandler
        """Answers a GET: the prototype at the root, 404 anywhere else."""
        if self.path.split("?", 1)[0] not in ("/", "/index.html"):
            self._send(404, b"<!doctype html><title>404</title>Rien ici.")
            return
        body = self._document()
        if body is None:
            self._send(503, MISSING)
            return
        self._send(200, body)

    do_HEAD = do_GET

    def log_message(self, fmt: str, *args: object) -> None:
        """Silences per-request logging.

        Caddy already writes one access-log line per request; a second copy in
        the PM2 log buys nothing and grows without bound.
        """


class Server(socketserver.ThreadingTCPServer):
    """Threaded so a slow client cannot hold the single document hostage."""

    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    """Runs the server until interrupted.

    Returns:
        Process exit status.
    """
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8712
    # Bound to the loopback: the reverse proxy is the only intended caller, and
    # binding wider would publish the prototype on the LAN behind the proxy's
    # back, outside whatever access control the proxy applies.
    with Server(("127.0.0.1", port), Handler) as httpd:
        print(f"prototype served on http://127.0.0.1:{port} from {PROTOTYPE}", flush=True)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
