#!/usr/bin/env python3
r"""Serve the design prototype over HTTP, behind its own login screen.

`refonte.html` is a head-less fragment: it starts at `<title>` and owns no
`<html>` or `<head>`, because it is authored to be embedded by a host page.
Served raw as a top-level document it renders in quirks mode, and a phone with
no viewport meta falls back to the legacy 980px layout viewport and scales the
frame down to roughly 40 % — measured, not feared.

This server serves the Vite build (`dist/index.html`), rebuilt when its
inputs are newer. The harness measures the source through its own copy of the
design root, and R72 is the bridge that keeps the two interchangeable: both
read from the same inputs, both emit the same bytes.

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
import html
import http.cookies
import http.server
import json
import os
import re
import secrets
import socketserver
import subprocess
import sys
import threading
import urllib.parse
from collections.abc import Callable
from pathlib import Path


def renamed_env(current: str, former: str) -> str | None:
    """Returns an environment value, answering to the name it used to have.

    Both of this host's environment names were translated. A caller outside the
    tree — a shell profile, a launcher — cannot be renamed with the file, and
    silently falling back to the default is the one behaviour change this wave
    would otherwise have shipped. The old name still works and says so.

    Args:
        current: The name to read first.
        former: The name it used to be.

    Returns:
        The value, or None when neither name is set.
    """
    value = os.environ.get(current)
    if value:
        return value
    value = os.environ.get(former)
    if value:
        print(f"{former} is the old name of {current}; still honoured, "
              "rename it", file=sys.stderr, flush=True)
    return value


# The design root is overridable so a harness rule can point the server at a
# SCRATCH copy and mutate it freely: no measurement may ever write into the
# operator's real source.
DESIGN_ROOT = Path(
    renamed_env("TM_DESIGN_ROOT", "TM_DESIGN_RACINE")
    or Path(__file__).resolve().parent / "design"
).resolve()
PROTOTYPE = DESIGN_ROOT / "refonte.html"
# The base layer (D3). It carries the `login:font` and `login:socle` regions
# the sign-in gate inherits, which lived in the fragment's BLOCK 1 until L07.
BASE_STYLESHEET = DESIGN_ROOT / "src" / "styles" / "base.css"
# The document Vite owns, and where the application shell's markup lives — the
# phone frame, the sign-in card, the startup screen. The login gate clones
# those from here and inherits its style from the fragment above.
SHELL_DOCUMENT = DESIGN_ROOT / "index.html"
DIST = DESIGN_ROOT / "dist" / "index.html"
# The build inputs that always exist, at the design root.
BUILD_INPUTS = (
    PROTOTYPE,
    SHELL_DOCUMENT,
    DESIGN_ROOT / "vite.config.mjs",
)

# The shell's own translation resource. Everything this host SERVES in French —
# the sign-in gate, the two 503s, the offline page, the manifest's description —
# reads its words here, because the application has exactly one place where its
# French lives and a second copy is a second thing to keep in step.
TEXTS = DESIGN_ROOT / "src" / "i18n" / "fr.json"


def served_texts() -> dict[str, dict[str, str]]:
    """Returns the French copy of the pages this host serves itself.

    Read on every request, exactly like the login screen's markup below and for
    the same reason: a copy loaded once at boot drifts away from the file it
    claims to quote, and the whole point of extracting instead of restating is
    that there is nothing left to drift.

    Returns:
        The resource's `server` namespace: one entry per served page.

    Raises:
        ValueError: When the namespace is missing or malformed — a page must
            fail loudly rather than be served with holes where its words go.
        FileNotFoundError: When the resource file itself is absent.
    """
    document = json.loads(TEXTS.read_text(encoding="utf-8"))
    # Every layer is checked, not only the middle one. A document that is not an
    # object, or a page entry that is not an object, would otherwise raise an
    # AttributeError or a TypeError — neither of which the callers catch, so the
    # host would answer NOTHING AT ALL where it promises to answer loudly, and
    # the front door of a credential gate would be indistinguishable from a
    # dead host.
    texts = document.get("server") if isinstance(document, dict) else None
    if not isinstance(texts, dict) or not all(
            isinstance(page, dict) and all(isinstance(word, str)
                                           for word in page.values())
            for page in texts.values()):
        raise ValueError(f'no usable "server" namespace in {TEXTS.name}')
    return texts


def mtime_sources() -> int:
    """Returns the newest mtime among every input the build reads.

    The three roots above, plus every file under `src/` — the shell is a
    DIRECTORY, and a module added there tomorrow must not be invisible to
    staleness, or the host would serve yesterday's build saying nothing.

    Returns:
        The newest modification time, in nanoseconds.

    Raises:
        FileNotFoundError: When a root build input is missing — the caller
            turns it into the named build error.
    """
    stamps = [source.stat().st_mtime_ns for source in BUILD_INPUTS]
    shell = DESIGN_ROOT / "src"
    if shell.is_dir():
        stamps.extend(file_.stat().st_mtime_ns
                      for file_ in shell.rglob("*") if file_.is_file())
    return max(stamps)


NPM = "/Users/izno/.nvm/versions/node/v22.13.1/bin/npm"
# Overridable so the timeout path itself can be proven live, the same way
# TM_DESIGN_ROOT lets a rule serve a scratch root.
BUILD_TIMEOUT = float(
    renamed_env("TM_DESIGN_BUILD_TIMEOUT", "TM_DESIGN_DELAI_BUILD") or 120)

USERNAME = os.environ.get("TM_DESIGN_USER", "izno")

# scrypt, salt included, both base64. The password itself is nowhere here, and
# nowhere in the repository.
PASSWORD_HASH = os.environ.get(
    "TM_DESIGN_PASSWORD_HASH",
    "6AyZBOfVp7Qj5pwFOepikA==:7sVyqbzeLHD4/FA8pUfqPb7RPSe+wmesEZi7fhXm9hw=",
)

# Regenerated at every boot: a restart ends every session, which is the right
# trade for a design host and removes any need to persist secrets.
SESSION_SECRET = secrets.token_bytes(32)
COOKIE_NAME = "tm_design"

ASSETS_DIR = PROTOTYPE.parent / "assets"

# Where the build writes the shell's module entry (`build.assetsDir` = "vite",
# kept out of `dist/assets` because a symlink owns that name).
VITE_DIR = DESIGN_ROOT / "dist" / "vite"

# Brand assets and the manifest are served WITHOUT a session: they carry no
# private data, and a `<link rel="manifest">` is fetched without credentials
# unless asked otherwise — a 401 there costs the install prompt entirely.
#
# The DESIGN set, never the app's. A name distinguishes two entries in a list;
# on a home screen what is seen first is the picture, and two identical pictures
# with different labels are still two identical pictures. The three sets are one
# family — the app's icons plain, staging's with a cyan ring, these with a
# yellow one — and they are generated by `frontend/scripts/make-design-icons.py`
# rather than drawn by hand, so the ring cannot drift between them.
ASSETS = {
    "/pwa-192.png": "image/png",
    "/pwa-512.png": "image/png",
    "/maskable-192.png": "image/png",
    "/maskable-512.png": "image/png",
    "/apple-touch-icon.png": "image/png",
    "/favicon.svg": "image/svg+xml",
}

# The file each path is answered with. The URLs keep the app's names so the
# manifest reads the same on all three hosts; only what comes back differs.
ASSET_FILE = {
    "/pwa-192.png": "pwa-192-design.png",
    "/pwa-512.png": "pwa-512-design.png",
    "/maskable-192.png": "maskable-192-design.png",
    "/maskable-512.png": "maskable-512-design.png",
    "/apple-touch-icon.png": "apple-touch-icon-design.png",
    "/favicon.svg": "favicon.svg",
}

# The prototype is a SEPARATE application, and it has to say so everywhere the
# system reads a name.
#
# The shipped app installs as « TorrentMate », and this one used to install as
# « TM design » — an abbreviation nobody recognises next to it, over the same
# icon. Two entries on one home screen that differ only by an abbreviation are
# two entries nobody can tell apart, and the one that gets opened is whichever
# was tapped last.
#
# `id` is declared rather than left to default: without it the identity falls
# back to `start_url`, which is « / » here and « / » there, so nothing but the
# origin separates them. Naming it removes the ambiguity instead of relying on
# a browser to resolve it.
#
# The description is the one French sentence in it, so it is substituted from
# the shell's resource rather than written here; `json.dumps` re-escapes it to
# the same ASCII the hand-written literal used, so the served bytes are the
# bytes that were served before it moved.
MANIFEST = """{
  "id": "/?app=torrentmate-design",
  "name": "TorrentMate Design",
  "short_name": "TorrentMate Design",
  "description": "DESCRIPTION",
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

# Installability asks two things of a worker: that it handle fetches, and that
# a navigation still get an answer with the network gone. An empty handler
# satisfies the first and fails the second, so the prompt never came.
#
# The answer is NETWORK-FIRST, with one cached page as the only fallback, and
# the prototype itself never cached. A caching worker would serve yesterday's
# prototype to someone judging today's design — the exact failure a design
# reference cannot afford. Being offline says so instead of lying quietly.
WORKER = b"""const CACHE = "tm-design-offline";
const OFFLINE = "/offline.html";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.add(OFFLINE)));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(
    fetch(e.request).catch(() => caches.match(OFFLINE))
  );
});
"""


def manifest() -> bytes:
    """Returns the web manifest, its one French sentence read from the resource.

    Returns:
        The manifest's bytes, escaped to ASCII exactly as the served copy was.
    """
    description = json.dumps(served_texts()["manifest"]["description"])[1:-1]
    return MANIFEST.replace("DESCRIPTION", description, 1).encode()


def offline_page() -> bytes:
    """Returns the one page that exists offline.

    It says what is true — the prototype lives on the server and is not
    available — rather than showing a stale copy of it.

    Returns:
        A complete HTML document.
    """
    texts = served_texts()["offline"]
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{texts['title']}</title>"
        "<style>html,body{margin:0;height:100%;display:grid;place-items:center;"
        "background:#0b0b0d;color:#ededf0;font-family:system-ui,sans-serif;"
        "text-align:center;padding:24px}p{color:#9b9ba4;font-size:14px;"
        "line-height:1.5;max-width:30ch}</style></head><body><div>"
        f"<h1 style=\"font-size:17px;margin:0 0 8px\">{texts['heading']}</h1>"
        f"<p>{texts['body']}</p></div></body></html>"
    ).encode()


ENVELOPE = DESIGN_ROOT / "index.html"


def pwa_head() -> str:
    """Returns the PWA head block, extracted from the envelope.

    The envelope (`design/index.html`) is the document's single source of
    truth since the host began serving the build; the login gate sits in
    front of that document and must be installable too, so it borrows the
    same block rather than restating it — a restated copy is where drift
    hides (measured twice on the login screen's styles).

    Raises:
        ValueError: When the markers are missing — the gate must fail loudly
            rather than serve a page that silently lost its installability.
        FileNotFoundError: When the envelope itself is absent.
    """
    source = ENVELOPE.read_text()
    start = source.find("pwa:start")
    end = source.find("<!-- pwa:end -->")
    after_comment = source.find("-->", start, end)
    if start < 0 or end < 0 or end < start or after_comment < 0:
        raise ValueError("pwa markers not found in design/index.html")
    return source[after_comment + 3 : end]


def missing_page() -> bytes:
    """Returns the 503 shown when the served checkout has no prototype.

    Returns:
        A complete HTML document.
    """
    texts = served_texts()["missing"]
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{texts['title']}</title></head><body "
        'style="font:16px system-ui;max-width:34em;margin:12vh auto;padding:0 1.5em">'
        f"<h1>{texts['heading']}</h1><p>{texts['body']}</p>"
        f"<p>{texts['reassurance']}</p></body></html>"
    ).encode()


def build_failure(error: str) -> bytes:
    """Builds the 503 shown when the build fails.

    Serving the PREVIOUS build instead would be a stale reference wearing
    today's date — the exact failure a design host exists to avoid. The page
    says what broke, with the build's own last words.

    Args:
        error: The error message from the failed build, typically stderr output.

    Returns:
        A complete HTML 503 error page as bytes, with the error escaped.
    """
    try:
        texts = served_texts()["buildFailure"]
    except (OSError, ValueError, KeyError) as unreadable:
        # This page is how every other failure here gets reported, so it is the
        # one page that may not fail itself. Restating its French copy as a
        # fallback would reintroduce exactly the second copy this indirection
        # removes, so the last resort speaks the developer's language and names
        # the copy as what broke — alongside the error it was called for.
        return diagnostic_page(f"{error}\n\n{unreadable}")
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{texts['title']}</title></head><body "
        'style="font:16px system-ui;max-width:44em;margin:12vh auto;padding:0 1.5em">'
        f"<h1>{texts['heading']}</h1><p>{texts['body']}"
        "</p><pre style=\"white-space:pre-wrap;background:#f6f6f6;"
        'padding:12px;border-radius:8px">'
        f"{html.escape(error)}"
        "</pre></body></html>"
    ).encode()


def diagnostic_page(error: str) -> bytes:
    """Returns the 503 served when the served copy itself cannot be read.

    Args:
        error: What was being reported, plus why the copy could not be read.

    Returns:
        A complete HTML document, in English — nobody but a developer can be
        looking at it, since a reader of the interface would be looking at the
        page this one stands in for.
    """
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Design host: copy unreadable</title></head><body "
        'style="font:16px system-ui;max-width:44em;margin:12vh auto;padding:0 1.5em">'
        "<h1>The design host cannot read its own copy</h1><p>The pages this "
        "host serves read their words from <code>design/src/i18n/fr.json</code>"
        ", and that read failed. Below is what was being reported when it "
        "did, followed by the read error itself.</p>"
        "<pre style=\"white-space:pre-wrap;background:#f6f6f6;"
        'padding:12px;border-radius:8px">'
        f"{html.escape(error)}"
        "</pre></body></html>"
    ).encode()


def extract(source: str, marker: str) -> str:
    """Returns the text between a pair of markers.

    Args:
        source: The full text of whichever file holds the block.
        marker: The marker name, without its `login:` prefix or `:start` /
            `:end` suffix.

    Returns:
        The text between the two markers.

    Raises:
        ValueError: When either marker is missing — the gate must fail loudly
            rather than serve a login screen stripped of its design.
    """
    start = source.find(f"login:{marker}:start")
    end = source.find(f"login:{marker}:end")
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"login:{marker} markers not found in the source given")
    return source[source.index("\n", start) + 1 : source.rindex("\n", start, end) + 1]


# Signing in navigates to a document of several megabytes. Until its first
# frame is painted the browser still shows THIS page, so the wait belongs here:
# without it, a tap on « Se connecter » answers with nothing at all for as long
# as the load takes, which reads as a form that did not submit.
#
# The screen shown is the prototype's own startup screen, extracted like the
# rest of the gate, so the wait that follows a sign-in is the same surface the
# document then keeps showing — not a copy of it that drifts.
STARTUP_SWITCH = """
<script>
document.querySelector('#loginform').addEventListener('submit', function (e) {
  if (!e.currentTarget.checkValidity()) return;
  document.querySelector('#login').hidden = true;
  document.querySelector('#splash').hidden = false;
});
</script>
"""


def login_page(refused: bool) -> bytes:
    """Builds the login page out of the prototype's own login screen.

    Args:
        refused: True to show the rejection state.

    Returns:
        A complete HTML document.
    """
    # TWO SOURCES, because the gate borrows from two. The MARKUP it clones —
    # the sign-in card and the startup screen — is the application shell, and
    # that lives in `index.html` since the fragment stopped carrying a
    # program. The STYLE it inherits is still the fragment's: the CSS contract
    # does not move before SP5. Each `extract` below reads whichever file
    # actually holds its block, and `extract` itself raises when a marker is
    # missing — so pointing one of them at the wrong file fails the gate
    # loudly instead of serving a screen stripped of its design.
    # THREE SOURCES SINCE L07, and each `extract` below still names exactly
    # one of them. The base layer left the fragment for `src/styles/base.css`,
    # taking `login:font` and `login:socle` with it — so the honest shape is a
    # second BINDING, not a concatenation. `scripts/check-css-tokens.py`'s
    # login arm follows these bindings to know which file holds which chunk;
    # a concatenated source would leave it resolving every chunk to the first
    # file and reporting the rest missing, which is exactly what it did for as
    # long as this line was `PROTOTYPE.read_text() + BASE_STYLESHEET.read_text()`.
    styles_source = PROTOTYPE.read_text()
    base_source = BASE_STYLESHEET.read_text()
    markup_source = SHELL_DOCUMENT.read_text()
    markup = extract(markup_source, "markup")
    # The screen is drawn hidden inside the shell and centred against it. Here
    # it IS the page, so it drops both.
    #
    # THE `hidden` IS REMOVED BY PATTERN, NOT BY ADJACENCY. This was
    # `replace(' id="login" hidden', …)`, which needed the two attributes to
    # remain neighbours in the markup — and `str.replace` that matches nothing
    # returns the string unchanged, silently. Adding one attribute between them
    # served a sign-in screen that was still `hidden`: every element measured
    # 0x0, six holds in `entry.py` fell at once and `startup.py` timed out
    # filling a form that was not there. The markup may now carry whatever
    # attributes it needs, in whatever order.
    markup = re.sub(r'(<div[^>]*\bid="login"[^>]*?)\s+hidden\b', r"\1", markup,
                    count=1)
    markup = markup.replace('<form class="logincard" id="loginform"',
                            '<form class="logincard" id="loginform" method="post" action="/login"', 1)
    if refused:
        markup = markup.replace('id="loginerr" hidden', 'id="loginerr"', 1)
    # Inside the prototype the startup screen is what the document opens on;
    # here it waits for the submit that makes it true.
    markup += extract(markup_source, "splash").replace(
        ' id="splash"', ' id="splash" hidden', 1
    )
    # Everything the screen INHERITS inside the prototype — the palette, the box
    # model, the typography — is taken from it rather than restated. Both were
    # retyped here once, and both times the copy rendered correctly while the
    # reference was broken: the brand colour had been renamed to `--primary` and
    # the wordmark's line height was `normal` instead of 1.35. A retyped value
    # does not merely risk drifting; it CONCEALS a defect in the reference,
    # because the copy is the only place anyone ever looks. The scale block is
    # emitted first so every step a folded declaration reads resolves on the
    # composed page.
    styles = (extract(styles_source, "scale") + extract(base_source, "font")
              + extract(styles_source, "palette") + extract(base_source, "socle")
              + extract(styles_source, "style") + extract(styles_source, "splashstyle"))
    # After the extract, so they win: inside the prototype the screen covers a
    # phone frame; here it IS the page.
    adjustments = """
  .loginscreen { position: static; min-height: 100vh; }
  /* No positioned frame to cover here: the startup screen answers to the
     viewport instead, so it stays put whatever the page does. */
  .splash { position: fixed; }
"""
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{served_texts()['login']['title']}</title>"
        f"{pwa_head()}"
        "<style>"
        f"{styles}{adjustments}</style></head><body>{markup}"
        f"{STARTUP_SWITCH}</body></html>"
    ).encode()


def session_token() -> str:
    """Returns the session value a cookie must carry to be accepted."""
    return hmac.new(SESSION_SECRET, b"session", hashlib.sha256).hexdigest()


def password_matches(submitted: str) -> bool:
    """Checks a password against the stored scrypt hash.

    Args:
        submitted: The submitted password.

    Returns:
        True when it matches.
    """
    try:
        salt_b64, expected_b64 = PASSWORD_HASH.split(":", 1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(expected_b64)
    except (ValueError, TypeError):
        return False
    computed = hashlib.scrypt(submitted.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return hmac.compare_digest(computed, expected)


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves the wrapped prototype to a session, the login screen otherwise."""

    # The document is the BUILD, reconstructed on demand: comparing the
    # newest source mtime against dist's answers « is what I would serve
    # what the sources say? », and 0.4 s of vite build is cheaper than one
    # stale judgement. mtime_ns, not mtime: a second-resolution stamp
    # misses two edits within the same second — the cadence of an editing
    # session. One lock, or two stale requests race the same build.
    _cache: tuple[int, bytes] | None = None
    _build_lock = threading.Lock()

    protocol_version = "HTTP/1.1"

    def _document(self) -> bytes:
        """Returns the built document, rebuilding it when sources changed.

        Returns:
            The bytes of `dist/index.html`, freshly rebuilt if any build
            input was newer.

        Raises:
            FileNotFoundError: When `refonte.html` is absent (branch without
                the prototype) — the caller answers with the missing page.
            RuntimeError: When the build fails or a build input is missing —
                the caller answers with the error message, never with a stale
                document.
        """
        if not PROTOTYPE.exists():
            raise FileNotFoundError(PROTOTYPE)
        try:
            sources = mtime_sources()
        except FileNotFoundError as absent:
            # A missing build INPUT is a build problem, not a missing
            # prototype: say which file, never the wrong diagnosis.
            raise RuntimeError(f"missing build input: {absent.filename}")
        with Handler._build_lock:
            try:
                built = DIST.stat().st_mtime_ns
            except FileNotFoundError:
                built = -1
            if built < sources:
                try:
                    run = subprocess.run(
                        [NPM, "run", "build"], cwd=DESIGN_ROOT,
                        capture_output=True, text=True, timeout=BUILD_TIMEOUT)
                except subprocess.TimeoutExpired:
                    raise RuntimeError(
                        f"build aborted after {BUILD_TIMEOUT:g} s — "
                        "the npm process had stopped answering")
                if run.returncode != 0:
                    tail = (run.stderr or run.stdout).strip().splitlines()[-12:]
                    raise RuntimeError("\n".join(tail))
            try:
                stamp = DIST.stat().st_mtime_ns
            except FileNotFoundError:
                raise RuntimeError("the build succeeded without emitting dist/index.html")
            cached = Handler._cache
            if cached is None or cached[0] != stamp:
                Handler._cache = (stamp, DIST.read_bytes())
            return Handler._cache[1]  # type: ignore[index]

    def _authenticated(self) -> bool:
        """Returns True when the request carries a valid session cookie."""
        raw = self.headers.get("Cookie")
        if not raw:
            return False
        cookies = http.cookies.SimpleCookie()
        try:
            cookies.load(raw)
        except http.cookies.CookieError:
            return False
        value = cookies.get(COOKIE_NAME)
        return value is not None and hmac.compare_digest(value.value, session_token())

    def _send(
        self,
        status: int,
        body: bytes,
        extra_headers: list[tuple[str, str]] | None = None,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        """Writes one complete response, headers included.

        Args:
            status: HTTP status code.
            body: Response body; sent verbatim.
            extra_headers: Extra headers to add.
            content_type: The Content-Type to declare.
        """
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # The design is read to be judged, and a judgement passed on a stale
        # copy is worse than no judgement. Revalidate every time — except where
        # a route says otherwise: hash-named assets change URL when they change
        # content, so they alone may claim immutability.
        if not any(n.lower() == "cache-control" for n, _ in extra_headers or []):
            self.send_header("Cache-Control", "no-store")
        for name, value in extra_headers or []:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_page(self, status: int, build: Callable[[], bytes],
                   content_type: str = "text/html; charset=utf-8") -> None:
        """Sends a page built from the served copy, or the 503 that names the break.

        The pages this host builds itself read both their markup (from the
        prototype) and their words (from the shell's resource) at request time.
        Both can break under editing, and answering nothing would hide it: say
        what broke, like every other failure here.

        Args:
            status: The status the page answers with when it builds.
            build: The page builder to call.
            content_type: The Content-Type to declare.
        """
        try:
            body = build()
        except KeyError as incomplete:
            # An entry that is absent is the COPY being incomplete, not a build
            # that failed: answering « Build en échec » would name the wrong
            # culprit, and the reader would go looking at the build.
            self._send(503, diagnostic_page(
                f"missing entry in the served copy: {incomplete}"))
            return
        except (OSError, ValueError) as broken:
            self._send(503, build_failure(str(broken)))
            return
        self._send(status, body, content_type=content_type)

    def do_GET(self) -> None:  # noqa: N802 — name imposed by BaseHTTPRequestHandler
        """Answers a GET: the prototype to a session, the login screen otherwise."""
        path_ = self.path.split("?", 1)[0]
        if path_ == "/manifest.webmanifest":
            self._send_page(200, manifest, "application/manifest+json")
            return
        if path_ == "/sw.js":
            self._send(200, WORKER, content_type="text/javascript")
            return
        # Outside the session, like the manifest: the worker caches this page at
        # install time, and that install happens before anyone has signed in.
        if path_ == "/offline.html":
            self._send_page(200, offline_page)
            return
        if path_ in ASSETS:
            file_ = ASSETS_DIR / ASSET_FILE[path_]
            if not file_.is_file():
                self._send(404, b"")
                return
            self._send(200, file_.read_bytes(), content_type=ASSETS[path_])
            return
        if path_.startswith("/assets/"):
            # The library's real artwork: session-gated, unlike the brand set.
            if not self._authenticated():
                self._send(401, b"")
                return
            # self.path arrives raw: BaseHTTPRequestHandler never percent-decodes
            # it, so an encoded traversal (%2e%2e%2f) reaches the filesystem as a
            # literal file name that does not exist. The resolve() + containment
            # check below is the backstop that must hold if that ever changes.
            file_ = (ASSETS_DIR / path_[len("/assets/"):]).resolve()
            types = {".webp": "image/webp", ".png": "image/png",
                     ".svg": "image/svg+xml"}
            content_type = types.get(file_.suffix)
            if (content_type is None or not file_.is_file()
                    or not file_.is_relative_to(ASSETS_DIR.resolve())):
                self._send(404, b"")
                return
            self._send(200, file_.read_bytes(),
                       [("Cache-Control", "private, max-age=31536000, immutable")],
                       content_type=content_type)
            return
        if path_.startswith("/vite/"):
            # The shell's bundle: the module entry the emitted document names,
            # written there by the build. Session-gated like the artwork — the
            # document itself is, and a shell served to no one is only weight.
            if not self._authenticated():
                self._send(401, b"")
                return
            # Same backstop as /assets/ above: resolve() then containment, so a
            # traversal cannot reach outside the build's own output directory.
            file_ = (VITE_DIR / path_[len("/vite/"):]).resolve()
            types = {".js": "text/javascript", ".css": "text/css",
                     ".map": "application/json"}
            content_type = types.get(file_.suffix)
            if (content_type is None or not file_.is_file()
                    or not file_.is_relative_to(VITE_DIR.resolve())):
                self._send(404, b"")
                return
            self._send(200, file_.read_bytes(),
                       [("Cache-Control", "private, max-age=31536000, immutable")],
                       content_type=content_type)
            return
        if path_ == "/logout":
            self._send(303, b"", [("Location", "/"),
                                  ("Set-Cookie", f"{COOKIE_NAME}=; Path=/; Max-Age=0")])
            return
        if path_ == "/login":
            # `/login` accepts only POST (do_POST below): a reload or a
            # back-navigation after signing in must not re-render a form that
            # can only submit once. Matched BEFORE the fallback, so it keeps
            # this exact special case rather than falling into it.
            self._send(303, b"", [("Location", "/")])
            return
        # Every other path — "/", "/index.html", and any address the
        # client-side router owns (/mediasheet/…, /profile/…, …) — answers the ONE
        # document, session-gated exactly like "/".
        #
        # A 303 here would drop the address bar's path before the router ever
        # runs, and a 404 would dead-end a reload or a shared link. Both read
        # as smaller failures than a broken page; neither is: an installed
        # PWA, whose whole scope is `/`, has no address bar to escape either
        # one with. The scope must therefore be a place one cannot leave by
        # accident, at any depth the router grows into.
        if not self._authenticated():
            # The rejection state is signalled by the `refus` QUERY PARAMETER
            # `do_POST` redirects to (`/?refus=1`), not by the substring
            # "refus" anywhere in the path — a raw substring match also fired
            # on any unrelated address merely containing it (e.g.
            # `/profile/refusé`), showing the rejection banner to someone who
            # never submitted anything.
            params = urllib.parse.parse_qs(
                urllib.parse.urlsplit(self.path).query)
            self._send_page(401, lambda: login_page("refus" in params))
            return
        try:
            body = self._document()
        except FileNotFoundError:
            self._send_page(503, missing_page)
            return
        except RuntimeError as error:
            self._send(503, build_failure(str(error)))
            return
        self._send(200, body)

    do_HEAD = do_GET

    def do_POST(self) -> None:  # noqa: N802 — name imposed by BaseHTTPRequestHandler
        """Answers the login form: a session cookie, or the rejection state."""
        if self.path.split("?", 1)[0] != "/login":
            self._send(303, b"", [("Location", "/")])
            return
        size = min(int(self.headers.get("Content-Length") or 0), 4096)
        # The field NAMES are the login form's own, extracted from the
        # prototype: they are markup this host reads, not names it chooses.
        fields = urllib.parse.parse_qs(self.rfile.read(size).decode("utf-8", "replace"))
        username = (fields.get("username") or [""])[0].strip()
        password = (fields.get("password") or [""])[0]
        # Both sides compared in constant time, and the username checked even
        # when it is wrong, so a wrong name and a wrong password cost the same.
        name_ok = hmac.compare_digest(username, USERNAME)
        password_ok = password_matches(password)
        if not (name_ok and password_ok):
            self._send(303, b"", [("Location", "/?refus=1")])
            return
        self._send(303, b"", [
            ("Location", "/"),
            ("Set-Cookie",
             f"{COOKIE_NAME}={session_token()}; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=2592000"),
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
