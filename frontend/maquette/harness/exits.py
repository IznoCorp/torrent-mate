"""R103 — a layer's exit is SEEN, and the page is not left bare while it leaves.

B-249, reported by the operator on a phone: tapping an action of a sheet that
NAVIGATES — « Voir la fiche », « Voir le parcours », « Chercher une autre
release » — flashes the whole interface; closing the sheet alone does not.

WHAT THE TIMELINE SHOWS, sampled frame by frame on the operator's own path
(a long press on a library tile, then the first action of the sheet it raises):

  frame 0   the scrim is up, the sheet is in place
  frame 2   `visibility: hidden` on BOTH — while `opacity` and `transform` still
            have 200 and 300 ms to run
  frame 18  the destination screen appears, already in place

So the dimmed page snapped to full brightness in ONE frame and stayed bare for
sixteen. **`visibility` is not animatable the way `opacity` is**: left out of the
transition list it swaps immediately, so the exit every producer waits for was
already over before the wait began — `data-mediasheet` closes the panel and
calls `setTimeout(…, 260)` « to let the sheet finish leaving ».

WHAT THIS RULE HOLDS is the frame's half: while a layer is leaving, it is still
VISIBLE. The idiom is the standard one — `visibility` transitions with a delay
equal to the fade, so it holds `visible` for the whole exit and flips at the
end. Nothing at REST changes, which is why the oracle has nothing to say.

WHAT IT DOES NOT HOLD, and the distinction is the wave's boundary. The 260 ms
wait belongs to the PRODUCER (`legacy.js`'s click delegation), and a producer is
Part 12's — L19's. This rule measures the gap and PRINTS it; it refuses only the
part the frame owns. A rule that refused the gap would be refusing a number
nobody in this wave may change.

AND IT CANNOT SEE A FLASH. A flash is a paint, and no assertion here can time
one. What it reads is the fact the flash is made of: a layer that stops being
visible before it has finished leaving.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

# The operator's own path: a long press on a library tile raises the action
# sheet, and its first action navigates. A pointer event of type « touch » —
# the handlers serve finger, mouse and pen through one path.
LONG_PRESS = """()=>{
  const tile = document.querySelector('[data-tile]');
  const box = tile.getBoundingClientRect();
  const pointer = {bubbles: true, cancelable: true, isPrimary: true,
                   pointerId: 1, pointerType: 'touch',
                   clientX: box.left + box.width / 2,
                   clientY: box.top + box.height / 2};
  tile.dispatchEvent(new PointerEvent('pointerdown', pointer));
  window.setTimeout(
    () => window.dispatchEvent(new PointerEvent('pointerup', pointer)), 600);
}"""

# One reading per animation frame, for as long as the exit lasts.
SAMPLE = """(frames)=>new Promise((done)=>{
  const seen = [];
  const read = () => {
    const of = (selector) => {
      const node = document.querySelector(selector);
      if (!node) return null;
      const style = getComputedStyle(node);
      return {opacity: Number(style.opacity), visibility: style.visibility,
              moved: style.transform !== 'none'};
    };
    const screens = [...document.querySelectorAll('[data-part="screen"]')]
      .filter((node) => node.hasAttribute('data-open')).length;
    seen.push({scrim: of('#scrim'), sheet: of('#sheet'), screens});
    if (seen.length >= frames) return done(seen);
    requestAnimationFrame(read);
  };
  requestAnimationFrame(read);
})"""


def leaving(frames, layer):
    """The frames in which a layer is mid-exit: moved or partly faded."""
    return [
        frame for frame in frames
        if frame[layer] and (frame[layer]["moved"] or 0 < frame[layer]["opacity"] < 1)
    ]


async def main():
    journal = Journal("R103 — a layer's exit is seen (B-249)")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("()=>window.__go('lib-grid')")
        await page.wait_for_timeout(500)
        await page.evaluate(LONG_PRESS)
        await page.wait_for_timeout(900)
        raised = await page.evaluate("""()=>{
          const sheet = document.querySelector('#sheet');
          return {open: sheet.hasAttribute('data-open'),
                  actions: [...sheet.querySelectorAll('[data-part="sheet/action"]')]
                    .map((action) => action.textContent.trim())};}""")
        journal.check(
            "a long press raises the action sheet, so this walk has a subject",
            raised["open"] and len(raised["actions"]) > 1,
            str(raised["actions"]))

        sampling = asyncio.create_task(page.evaluate(SAMPLE, 24))
        await asyncio.sleep(0.02)
        await page.evaluate(
            """()=>[...document.querySelectorAll(
                 '#sheet [data-part="sheet/action"]')][0].click()""")
        frames = await sampling

        moving_scrim = leaving(frames, "scrim")
        moving_sheet = leaving(frames, "sheet")
        journal.check(
            "the exit really animates, so the holds below have something to "
            "measure",
            len(moving_scrim) > 3 and len(moving_sheet) > 3,
            f"{len(moving_scrim)} frame(s) of scrim, "
            f"{len(moving_sheet)} of sheet")
        journal.check(
            "the scrim is still VISIBLE while it is fading (B-249)",
            all(frame["scrim"]["visibility"] == "visible"
                for frame in moving_scrim),
            str([frame["scrim"]["visibility"] for frame in moving_scrim][:6]))
        journal.check(
            "and the sheet is still VISIBLE while it is sliding out",
            all(frame["sheet"]["visibility"] == "visible"
                for frame in moving_sheet),
            str([frame["sheet"]["visibility"] for frame in moving_sheet][:6]))

        # MEASURED AND PRINTED, NEVER REFUSED. The gap is what the producer's
        # own `setTimeout(…, 260)` leaves between the layer being gone and the
        # destination arriving, and a producer is Part 12's — L19's. Refusing a
        # number nobody in this wave may change would be a rule against the
        # wrong subject; a number nobody prints is a number nobody acts on.
        gone = next((at for at, frame in enumerate(frames)
                     if frame["scrim"]["opacity"] == 0), None)
        arrived = next((at for at, frame in enumerate(frames)
                        if frame["screens"] > 0), None)
        journal.check(
            "the destination really arrives inside the window this walk "
            "samples",
            arrived is not None,
            f"screen at frame {arrived}")
        print(f"  note the scrim reaches zero at frame {gone} and the "
              f"destination arrives at frame {arrived} — "
              f"{'' if gone is None or arrived is None else arrived - gone} "
              "frame(s) of bare page between them. The wait is the PRODUCER's "
              "(`setTimeout(…, 260)` beside `data-mediasheet`) and moves with "
              "it at L19; this rule prints it and refuses nothing about it.")

        await context.close()
        await browser.close()
    journal.summary(errors)


asyncio.run(main())
