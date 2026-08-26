#!/usr/bin/env python3
"""What makes the served prototype installable.

The manifest, the service worker, the offline page, and the head block the
sign-in gate borrows.

WHY IT IS A FILE OF ITS OWN. It came out of `serve.py`, which sat exactly on
the 800-line soft ceiling after the served identity arrived. The split is on
the SUBJECT and not on the line count, and that is checkable: `serve.py`
answers « what document do I send, and to whom? »; `host_identity.py` answers
« what tree am I sending it from? »; this answers « what does a phone need in
order to keep it? ». Nothing here decides who may see a page.

IT READS THE ENVELOPE, IT DOES NOT RESTATE IT. `design/index.html` is the
document's single source of truth, and the sign-in gate — which sits in front
of that document — must be installable too. So the gate borrows the same head
block by extracting it between markers rather than carrying a copy: a restated
copy is where drift hides, measured twice on the login screen's styles.

THE ONE FRENCH SENTENCE IT SERVES is read from `design/src/i18n/fr.json`, like
every other word this host emits.
"""

from __future__ import annotations

import json

# NOTHING IS IMPORTED FROM `serve.py`, and that is a constraint rather than a
# preference: `serve.py` imports THIS, so a sibling import back would be a
# cycle. What this module needs from the host — where the design root is, and
# how to read the interface's words — arrives as arguments, the same shape
# `host_identity.served_identity(root)` already uses.
from collections.abc import Callable
from pathlib import Path

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


def manifest(texts: Callable[[], dict]) -> bytes:
    """Returns the web manifest, its one French sentence read from the resource.

    Args:
        texts: Reads the interface's words; called per request, never cached.

    Returns:
        The manifest's bytes, escaped to ASCII exactly as the served copy was.
    """
    description = json.dumps(texts()["manifest"]["description"])[1:-1]
    return MANIFEST.replace("DESCRIPTION", description, 1).encode()


def offline_page(texts: Callable[[], dict]) -> bytes:
    """Returns the one page that exists offline.

    It says what is true — the prototype lives on the server and is not
    available — rather than showing a stale copy of it.

    Args:
        texts: Reads the interface's words; called per request, never cached.

    Returns:
        A complete HTML document.
    """
    words = texts()["offline"]
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{words['title']}</title>"
        "<style>html,body{margin:0;height:100%;display:grid;place-items:center;"
        "background:#0b0b0d;color:#ededf0;font-family:system-ui,sans-serif;"
        "text-align:center;padding:24px}p{color:#9b9ba4;font-size:14px;"
        "line-height:1.5;max-width:30ch}</style></head><body><div>"
        f"<h1 style=\"font-size:17px;margin:0 0 8px\">{words['heading']}</h1>"
        f"<p>{words['body']}</p></div></body></html>"
    ).encode()


def pwa_head(design_root: Path) -> str:
    """Returns the PWA head block, extracted from the envelope.

    The envelope (`design/index.html`) is the document's single source of
    truth since the host began serving the build; the login gate sits in
    front of that document and must be installable too, so it borrows the
    same block rather than restating it — a restated copy is where drift
    hides (measured twice on the login screen's styles).

    Args:
        design_root: The design root, whose `index.html` is the envelope.

    Raises:
        ValueError: When the markers are missing — the gate must fail loudly
            rather than serve a page that silently lost its installability.
        FileNotFoundError: When the envelope itself is absent.
    """
    source = (design_root / "index.html").read_text()
    start = source.find("pwa:start")
    end = source.find("<!-- pwa:end -->")
    after_comment = source.find("-->", start, end)
    if start < 0 or end < 0 or end < start or after_comment < 0:
        raise ValueError("pwa markers not found in design/index.html")
    return source[after_comment + 3 : end]
