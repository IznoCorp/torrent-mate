"""R114 — a poster arriving late shifts nothing (P29).

`scripts/check-poster-box.py` holds that the boxes are DECLARED. That is a
static read, and it is green over a declared box the layout ignores — a
`aspect-ratio` on an element whose parent sizes it some other way changes
nothing, and no reader of source text can tell. This is the runtime half.

THE PROBE MUST MAKE THE IMAGE ARRIVE LATE, and that is the whole difficulty.
A fixture that resolves instantly produces no shift whether or not the box is
declared, so a probe run against fast local files measures NOTHING and reads
exactly like a probe that measured success. Every poster request is therefore
held back deliberately, released only after the layout has been recorded, and
the release is what the second measurement is taken across.

HOW THE SHIFT IS MEASURED. Not by `LayoutShift` entries: the browser attributes
those to a session window and coalesces them, so a small shift inside an
existing window reports zero and a rule reading the entry list is quiet about
the very thing it watches. What is read instead is the ground truth the entries
are derived FROM — the bounding rectangle of a node BELOW the posters, before
the images land and after. If a poster grew, everything under it moved, and the
difference is in pixels rather than in a score somebody has to interpret.

WHAT THIS DOES NOT READ: the CLS score the field would report, which depends on
viewport fraction and on distance and is a browser's arithmetic rather than a
layout fact; and whether the box is the RIGHT shape, which the oracle owns at
rest.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

# The gallery: the surface that draws the most posters at once.
STATE = "lib-grid"

# How long the posters are held back. Long enough that the layout is
# unambiguously recorded before any of them lands.
WITHHOLD_MILLISECONDS = 600

# A shift of this many pixels or more is a jump. Sub-pixel differences are
# rounding in the layout engine, not movement.
SHIFT_TOLERANCE_PIXELS = 1.0


async def hold(journal):
    """Withholds every poster, records the layout, releases, and compares."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        context = await browser.new_context(**PHONE)
        page = await context.new_page()

        # EVERY POSTER IS HELD BACK. Without this the probe proves nothing: a
        # local fixture answers before the first layout and there is no
        # « before » to compare against.
        released = asyncio.Event()
        withheld = {"count": 0}

        async def hold_the_image(route):
            withheld["count"] += 1
            await released.wait()
            await route.continue_()

        await page.route(
            lambda url: any(url.lower().endswith(suffix)
                            for suffix in (".jpg", ".jpeg", ".png", ".webp", ".avif")),
            hold_the_image)

        await page.goto(PROTOTYPE, wait_until="domcontentloaded")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.wait_for_timeout(250)
        await page.evaluate("(s)=>window.__go(s)", STATE)
        await page.wait_for_timeout(WITHHOLD_MILLISECONDS)

        # THE PROBE IS ONLY WORTH READING IF IT ACTUALLY HELD SOMETHING BACK.
        # A route that matched nothing would leave every hold below green over a
        # page whose images had all arrived before the first measurement.
        journal.check("posters were actually held back",
                      withheld["count"] > 0,
                      f"{withheld['count']} request(s) intercepted — with none, "
                      "nothing below measures anything")

        async def geometry():
            return await page.evaluate("""()=>{
              const tiles = [...document.querySelectorAll('[data-part="tile"]')];
              if (tiles.length < 2) return null;
              // A node BELOW the first posters: if one grew, this moved.
              const last = tiles[tiles.length - 1].getBoundingClientRect();
                // HOW MANY POSTERS HAVE ACTUALLY DECODED. Without this the
              // comparison below is green over images that never arrived at
              // all: point the fixture at a missing file, nothing loads,
              // nothing grows, nothing moves, and « nothing moved when the
              // posters landed » passes over posters that did not land. The
              // probe holds the requests back itself, so it is the probe's own
              // release that has to be shown to have worked.
              const landed = [...document.querySelectorAll(
                '[data-part="tile"] img')]
                .filter((image) => image.complete && image.naturalWidth > 0)
                .length;
              return {top: last.top, count: tiles.length, landed,
                      firstHeight: tiles[0].getBoundingClientRect().height};
            }""")

        before = await geometry()
        journal.check("the gallery is drawn with its posters pending",
                      before is not None and before["count"] >= 2,
                      f"read {before} — the box must be laid out before its "
                      "image arrives, which is exactly what a declared box buys")
        if not before:
            await browser.close()
            journal.summary(errors)
            return

        # The first tile must already HAVE a height: that is the declared box
        # doing its work, and it is the fact the static guard cannot reach.
        journal.check(
            "a poster box has its height BEFORE its image arrives",
            before["firstHeight"] > 1,
            f"height {before['firstHeight']}px with the image still pending — "
            "an undeclared box is zero-high until the bytes land")

        released.set()
        await page.wait_for_timeout(700)
        after = await geometry()

        journal.check(
            "the posters ACTUALLY landed once released",
            after["landed"] >= 2 and after["landed"] > before["landed"],
            f"{before['landed']} poster(s) decoded while withheld and "
            f"{after['landed']} after the release — the hold below reads a "
            "gallery whose images never arrived, and an image that never "
            "arrives never pushes anything: it would pass over the defect it "
            "exists to catch")

        moved = abs(after["top"] - before["top"])
        journal.check(
            "and nothing moved when the posters landed",
            moved < SHIFT_TOLERANCE_PIXELS,
            f"the gallery's last tile moved {moved:.1f}px when the images "
            "arrived — every poster that grows pushes the whole list under the "
            "reader's thumb")

        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R114 — a poster arriving late shifts nothing (P29)")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
