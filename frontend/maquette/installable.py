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

# THE THREE ENTRY POINTS THE PLATFORM OFFERS AN INSTALLED APPLICATION, and the
# operator's principle behind them (Q4, 2026-08-30): every one is declared,
# unless a written reason says why not. « La meilleure intégration possible. »
#
#   `share_target` — another application shares a title, a note or a link into
#       TorrentMate. All three land on `/add` as `q`, which the add screen
#       already reads: sharing a series name from a browser opens the search
#       with that name in it, and nothing had to be written for it to.
#   `launch_handler` — an installed application reopens the window it already
#       has instead of a second one. « navigate-existing » so a share into a
#       running application navigates it rather than stacking a copy.
#   `handle_links` — the system opens this origin's links in the application.
#
# WHAT IS DELIBERATELY NOT HERE: push notifications. The principle demands a
# written reason, and this is it — a permission prompt with nothing to send
# trains the operator to refuse it, and a browser remembers a refusal far longer
# than this wave. The consumer exists and is named: §18's ratio alert, which is
# L16. Recorded in the register so it is declined rather than forgotten.
#
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
  ],
  "share_target": {
    "action": "/add",
    "method": "GET",
    "params": { "title": "q", "text": "q", "url": "q" }
  },
  "launch_handler": { "client_mode": "navigate-existing" },
  "handle_links": "preferred"
}
"""

# THE WORKER IS BUILT, NOT WRITTEN HERE (L11). It used to be a literal in this
# file caching exactly one page — the offline notice — and never the prototype,
# because a caching worker would have served yesterday's copy to someone judging
# today's design. That decision is gone, and the failure it named is gone with
# it rather than merely tolerated: a navigation goes to the NETWORK first and
# falls back to the cache, so a reachable host always serves what it has now.
#
# The source is `design/sw.js` and the build writes `design/dist/sw.js`,
# substituting the bundle names it actually emitted. They carry content hashes,
# so a list restated here would be wrong the moment anything changed — and wrong
# in the silent direction, precaching a file that no longer exists while the one
# that does goes uncached. Same reason `pwa_head` extracts rather than restates.


def worker(design_root: Path) -> bytes:
    """Returns the built service worker.

    Args:
        design_root: The design root, whose `dist/sw.js` the build wrote.

    Returns:
        The worker's bytes.

    Raises:
        FileNotFoundError: When the build has not run. It is NEVER answered
            with an empty body or a stub: a worker that installs and caches
            nothing is indistinguishable from a working one until the network
            goes, which is the only moment anybody would find out.
    """
    return (design_root / "dist" / "sw.js").read_bytes()


def build_identity(design_root: Path) -> bytes:
    """Returns the identity of the build now in `dist/`.

    WHY IT IS NOT UNDER `/api/`. The mock layer replaces `globalThis.fetch`, so
    anything the page asks for under `/api/` is answered by a fixture and never
    reaches this host — a freshness poll there could not fail, whatever the
    server did. The endpoint is `/build.json` for that reason and no other.

    Args:
        design_root: The design root, whose `dist/build.json` the build wrote.

    Returns:
        The identity's bytes.

    Raises:
        FileNotFoundError: When the build has not run.
    """
    return (design_root / "dist" / "build.json").read_bytes()


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
