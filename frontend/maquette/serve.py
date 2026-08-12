#!/usr/bin/env python3
"""Serve the design prototype over HTTP, behind its own login screen.

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

**The credential check runs here, not in the page.** The prototype carries the
real library index, the follows and the staging contents. A check written in
the page it protects is readable by everyone that page reaches, so it protects
nothing; and the page cannot be sent before the check without giving away what
the check was for. The gate is therefore built by EXTRACTING the login screen
from the prototype — markup, styles and typeface, between explicit markers —
so the screen a visitor meets is the screen the design defines, never a copy of
it that drifts.

Only a scrypt hash of the password is stored. Set `TM_DESIGN_PASSWORD_HASH` to
rotate it without touching this file:

    python3 -c "import hashlib,os,base64; s=os.urandom(16); \\
        print(base64.b64encode(s).decode()+':'+base64.b64encode( \\
        hashlib.scrypt(b'<password>', salt=s, n=16384, r=8, p=1, dklen=32)).decode())"
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.cookies
import http.server
import os
import secrets
import socketserver
import sys
import urllib.parse
from pathlib import Path

PROTOTYPE = Path(__file__).resolve().parent / "refonte.html"

IDENTIFIANT = os.environ.get("TM_DESIGN_USER", "izno")

# scrypt, salt included, both base64. The password itself is nowhere here, and
# nowhere in the repository.
EMPREINTE = os.environ.get(
    "TM_DESIGN_PASSWORD_HASH",
    "6AyZBOfVp7Qj5pwFOepikA==:7sVyqbzeLHD4/FA8pUfqPb7RPSe+wmesEZi7fhXm9hw=",
)

# Regenerated at every boot: a restart ends every session, which is the right
# trade for a design host and removes any need to persist secrets.
SECRET_SESSION = secrets.token_bytes(32)
NOM_COOKIE = "tm_design"

PUBLIC = PROTOTYPE.parent.parent / "public"

# Brand assets and the manifest are served WITHOUT a session: they carry no
# private data, and a `<link rel="manifest">` is fetched without credentials
# unless asked otherwise — a 401 there costs the install prompt entirely.
ASSETS = {
    "/pwa-192.png": "image/png",
    "/pwa-512.png": "image/png",
    "/maskable-192.png": "image/png",
    "/maskable-512.png": "image/png",
    "/apple-touch-icon.png": "image/png",
    "/favicon.svg": "image/svg+xml",
}

MANIFESTE = b"""{
  "name": "TorrentMate \\u2014 design",
  "short_name": "TM design",
  "description": "Prototype de r\\u00e9f\\u00e9rence de l'interface TorrentMate.",
  "lang": "fr",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#0b0b0d",
  "theme_color": "#0b0b0d",
  "icons": [
    { "src": "/pwa-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "/pwa-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "/maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" },
    { "src": "/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
"""

# A fetch handler is what makes a page installable, and this one deliberately
# does nothing else. A caching worker would serve yesterday's prototype to
# someone judging today's design — the exact failure a design reference cannot
# afford.
WORKER = b"""self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
"""

HEAD = (
    b'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
    b'<meta name="viewport" '
    b'content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">'
    # An HTML entity, not the character: a bytes literal accepts no accent and
    # no dash beyond ASCII, and this file has already paid for that twice.
    b"<title>TorrentMate &mdash; refonte mobile</title>"
    b'<link rel="manifest" href="/manifest.webmanifest">'
    b'<meta name="theme-color" content="#0b0b0d">'
    b'<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
    b'<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
    # iOS reads neither the manifest's display nor its short_name: standalone
    # mode and the home-screen label are declared with these two, or the icon
    # opens a Safari tab instead of an app.
    b'<meta name="apple-mobile-web-app-capable" content="yes">'
    b'<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
    b'<meta name="apple-mobile-web-app-title" content="TM design">'
    b'<script>if("serviceWorker" in navigator)'
    b'addEventListener("load",()=>navigator.serviceWorker.register("/sw.js"));</script>'
    b"</head><body>"
)
TAIL = b"</body></html>"

MANQUANT = (
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


def extraire(source: str, marque: str) -> str:
    """Returns the text between a pair of markers.

    Args:
        source: The prototype's full text.
        marque: The marker name, without its `login:` prefix or `:start` /
            `:end` suffix.

    Returns:
        The text between the two markers.

    Raises:
        ValueError: When either marker is missing — the gate must fail loudly
            rather than serve a login screen stripped of its design.
    """
    debut = source.find(f"login:{marque}:start")
    fin = source.find(f"login:{marque}:end")
    if debut < 0 or fin < 0 or fin < debut:
        raise ValueError(f"marqueurs login:{marque} introuvables dans le prototype")
    return source[source.index("\n", debut) + 1 : source.rindex("\n", debut, fin) + 1]


def page_connexion(refusee: bool) -> bytes:
    """Builds the login page out of the prototype's own login screen.

    Args:
        refusee: True to show the rejection state.

    Returns:
        A complete HTML document.
    """
    source = PROTOTYPE.read_text()
    balisage = extraire(source, "markup")
    # The screen is drawn hidden inside the shell and centred against it. Here
    # it IS the page, so it drops both.
    balisage = balisage.replace(' id="login" hidden', ' id="login"', 1)
    balisage = balisage.replace('<form class="logincard" id="loginform"',
                                '<form class="logincard" id="loginform" method="post" action="/connexion"', 1)
    if refusee:
        balisage = balisage.replace('id="loginerr" hidden', 'id="loginerr"', 1)
    styles = extraire(source, "font") + extraire(source, "style")
    # The palette, the box model and the typeface the screen INHERITS inside
    # the prototype. They live in the reset, outside the extracted range, and
    # without them the design silently degrades rather than breaking: the
    # wordmark falls back to Times, and `max-width: 340px` applies to a content
    # box instead of a border box, so the card renders 378px wide.
    socle = """
  :root {
    --background: #0b0b0d; --card: #131316; --border: #26262b;
    --foreground: #ededf0; --muted-foreground: #9b9ba4;
    --accent: #f5a524; --accent-foreground: #1a1a1d; --danger: #f4515b;
  }
  *, *::before, *::after { box-sizing: border-box; }
  html, body {
    margin: 0;
    min-height: 100%;
    background: var(--background);
    color: var(--foreground);
    font-family: "Geist", system-ui, sans-serif;
  }
"""
    # After the extract, so they win: inside the prototype the screen covers a
    # phone frame; here it IS the page.
    ajustements = """
  .loginscreen { position: static; min-height: 100vh; }
"""
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>TorrentMate — connexion</title><style>"
        f"{socle}{styles}{ajustements}</style></head><body>{balisage}</body></html>"
    ).encode()


def jeton() -> str:
    """Returns the session value a cookie must carry to be accepted."""
    return hmac.new(SECRET_SESSION, b"session", hashlib.sha256).hexdigest()


def mot_de_passe_correct(propose: str) -> bool:
    """Checks a password against the stored scrypt hash.

    Args:
        propose: The submitted password.

    Returns:
        True when it matches.
    """
    try:
        sel_b64, attendu_b64 = EMPREINTE.split(":", 1)
        sel = base64.b64decode(sel_b64)
        attendu = base64.b64decode(attendu_b64)
    except (ValueError, TypeError):
        return False
    calcule = hashlib.scrypt(propose.encode(), salt=sel, n=16384, r=8, p=1, dklen=32)
    return hmac.compare_digest(calcule, attendu)


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves the wrapped prototype to a session, the login screen otherwise."""

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

    def _authentifie(self) -> bool:
        """Returns True when the request carries a valid session cookie."""
        brut = self.headers.get("Cookie")
        if not brut:
            return False
        biscuits = http.cookies.SimpleCookie()
        try:
            biscuits.load(brut)
        except http.cookies.CookieError:
            return False
        valeur = biscuits.get(NOM_COOKIE)
        return valeur is not None and hmac.compare_digest(valeur.value, jeton())

    def _send(
        self,
        status: int,
        body: bytes,
        entetes: list[tuple[str, str]] | None = None,
        type_mime: str = "text/html; charset=utf-8",
    ) -> None:
        """Writes one complete response, headers included.

        Args:
            status: HTTP status code.
            body: Response body; sent verbatim.
            entetes: Extra headers to add.
            type_mime: The Content-Type to declare.
        """
        self.send_response(status)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(body)))
        # The design is read to be judged, and a judgement passed on a stale
        # copy is worse than no judgement. Revalidate every time.
        self.send_header("Cache-Control", "no-store")
        for nom, valeur in entetes or []:
            self.send_header(nom, valeur)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 — name imposed by BaseHTTPRequestHandler
        """Answers a GET: the prototype to a session, the login screen otherwise."""
        chemin = self.path.split("?", 1)[0]
        if chemin == "/manifest.webmanifest":
            self._send(200, MANIFESTE, type_mime="application/manifest+json")
            return
        if chemin == "/sw.js":
            self._send(200, WORKER, type_mime="text/javascript")
            return
        if chemin in ASSETS:
            fichier = PUBLIC / chemin.lstrip("/")
            if not fichier.is_file():
                self._send(404, b"")
                return
            self._send(200, fichier.read_bytes(), type_mime=ASSETS[chemin])
            return
        if chemin == "/deconnexion":
            self._send(303, b"", [("Location", "/"),
                                  ("Set-Cookie", f"{NOM_COOKIE}=; Path=/; Max-Age=0")])
            return
        if chemin not in ("/", "/index.html"):
            self._send(404, b"<!doctype html><title>404</title>Rien ici.")
            return
        if not self._authentifie():
            self._send(401, page_connexion(refusee="refus" in self.path))
            return
        body = self._document()
        if body is None:
            self._send(503, MANQUANT)
            return
        self._send(200, body)

    do_HEAD = do_GET

    def do_POST(self) -> None:  # noqa: N802 — name imposed by BaseHTTPRequestHandler
        """Answers the login form: a session cookie, or the rejection state."""
        if self.path.split("?", 1)[0] != "/connexion":
            self._send(404, b"<!doctype html><title>404</title>Rien ici.")
            return
        taille = min(int(self.headers.get("Content-Length") or 0), 4096)
        champs = urllib.parse.parse_qs(self.rfile.read(taille).decode("utf-8", "replace"))
        identifiant = (champs.get("identifiant") or [""])[0].strip()
        motdepasse = (champs.get("motdepasse") or [""])[0]
        # Both sides compared in constant time, and the username checked even
        # when it is wrong, so a wrong name and a wrong password cost the same.
        nom_ok = hmac.compare_digest(identifiant, IDENTIFIANT)
        mdp_ok = mot_de_passe_correct(motdepasse)
        if not (nom_ok and mdp_ok):
            self._send(303, b"", [("Location", "/?refus=1")])
            return
        self._send(303, b"", [
            ("Location", "/"),
            ("Set-Cookie",
             f"{NOM_COOKIE}={jeton()}; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=2592000"),
        ])

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
