"""CSS extraction must leave NOTHING behind without saying so.

`regions.json` carries an allowlist: `extract-maquette-css.py` exports only
what it lists. A class defined in BLOCK 2 but absent from both lists would be
silently missing from the app — the most expensive defect possible, because it
only becomes visible once the screen is already wrong.

This script classifies EVERY BLOCK 2 class by what it actually does:

  app      — at least one element carries it, outside the prototype chrome
  harness  — seen only in the harness (state panel, notes, phone frame)
  written  — never present in a frozen state, but written by the code
             (transient classes: armed gesture, loading, selection)
  DEAD     — defined in CSS, never carried, never written by the code

« DEAD » is a failure: dead CSS in the prototype becomes dead CSS in the app
and, worse, suggests a class exists when it does not.
"""
import asyncio
import json
import pathlib
import re
import sys

from common import open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
BAR = "─" * 62

# The harness is physically identifiable in the DOM.
CHROME_PROTO = ".hpanel,.hbtn,.note,.states"
KNOWN_HARNESS = {"hpanel", "states", "notes", "stage", "device", "note", "hbtn"}


def block2_classes() -> set[str]:
    """Classes defined by a CSS rule inside BLOCK 2 — comments excluded."""
    h = (ROOT / "design" / "refonte.html").read_text()
    i = h.find("BLOCK 2")
    if i < 0:
        sys.exit("BLOCK 2 not found: the prototype lost its harness/app separation.")
    # Go back to the OPENER of the header comment: slicing on « BLOCK 2 »
    # leaves an orphan `*/`, and the header's own prose then parses as
    # selectors, producing false dead classes.
    i = h.rfind("/*", 0, i)
    css = re.sub(r"/\*.*?\*/", "", h[i : h.find("</style>", i)], flags=re.S)
    css = re.sub(r"\"[^\"]*\"|'[^']*'", '""', css)
    out = set()
    for m in re.finditer(r"([^{}]+)\{", css):
        if "@" in m.group(1) and "media" in m.group(1):
            continue
        out.update(re.findall(r"\.([a-zA-Z][\w-]*)", m.group(1)))
    return out


async def main():
    cl = sorted(block2_classes())
    src = (ROOT / "design" / "refonte.html").read_text()
    src = src[src.find("</style>"):]  # markup + JS, without the CSS
    # A migrated screen's markup lives in `design/src/**/*.tsx` now, not in
    # refonte.html: a class reached only through user interaction — never
    # present in any FROZEN `__go` state, like `.addfoot` (drawn once
    # `added.size > 0`) — is invisible to the DOM scan below AND to a
    # refonte.html-only source scan alike. Concatenating the TSX sources
    # here is what keeps this classifier's "written" detection working
    # across the strangler seam, one screen at a time, exactly the way it
    # already worked for the legacy templates it used to be the only source.
    # `.js` as well as `.tsx`, and that is not a detail: the legacy engine
    # emits the great majority of the class names in this document, and it
    # is a `.js` module under `src/` now rather than a script inside the
    # fragment. Globbing only `.tsx` classified every class it writes as
    # « defined but never written », i.e. as CSS the extraction would leave
    # behind — a red that says the stylesheet is wrong when what moved was
    # the writer.
    for written in sorted(p for p in (ROOT / "design" / "src").rglob("*")
                          if p.suffix in {".tsx", ".js"}):
        src += "\n" + written.read_text()

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        await pg.evaluate("()=>window.__measure(true)")
        states = await pg.evaluate("()=>window.__states()")
        app, harness = set(), set()
        for e in states:
            await pg.evaluate("(i)=>window.__go(i)", e)
            await pg.wait_for_timeout(170)
            r = await pg.evaluate("""([CL, CHROME])=>{const a=[],h=[];
              for (const c of CL) for (const el of document.getElementsByClassName(c)) {
                if (el.closest(CHROME) || el.classList.contains('stage') || el.classList.contains('device')) h.push(c);
                else a.push(c);
              }
              return {a:[...new Set(a)], h:[...new Set(h)]};}""", [cl, CHROME_PROTO])
            app |= set(r["a"]); harness |= set(r["h"])
        await b.close()

    harness -= app
    rest = set(cl) - app - harness
    # The harness is written by the code too: without this subtraction it
    # would land in « written », hence in the export allowlist.
    written = {c for c in rest - KNOWN_HARNESS
              if re.search(r"[\"'` ]" + re.escape(c) + r"[\"'` ]", src)}
    dead = sorted(rest - written - KNOWN_HARNESS)
    harness |= (rest & KNOWN_HARNESS)

    print(f"{BAR}\nClassification of the {len(cl)} BLOCK 2 classes\n{BAR}")
    print(f"  app       {len(app):4d}")
    print(f"  written   {len(written):4d}  (transient: {', '.join(sorted(written)) or '—'})")
    print(f"  harness   {len(harness):4d}")
    print(f"  DEAD      {len(dead):4d}  {', '.join(dead) or '—'}")

    # The allowlist must cover everything bound for the app: rendered AND
    # transient.
    regions = json.loads((ROOT / "regions.json").read_text())
    expected = {"." + c for c in (app | written)}
    missing = sorted(expected - set(regions["exportedSelectors"]))

    failures = []
    if dead:
        failures.append(f"{len(dead)} dead CSS rule(s): {', '.join(dead)}")
    if missing:
        failures.append(f"{len(missing)} class(es) outside the allowlist: {', '.join(missing)}")

    print()
    if failures:
        for x in failures:
            print("■", x)
        print(f"{BAR}\nFAILURE - extraction would leave CSS behind.")
        sys.exit(1)
    print(f"{BAR}\nOK - every BLOCK 2 class is classified, and the allowlist covers them all.")

asyncio.run(main())
