"""R97 — an avatar's image fills the box its host declares, in the shell and in a panel.

B-138: `ui/panel/index.tsx` drew `<span class="avatar …"><img></span>` with every
class on the SPAN and none on the IMG. Measured on the state `sheet-user`, before
the repair: the host declares 42x42 and the image rendered at **128x128** — its
natural size — with `object-fit: fill` and `display: inline`.

WHY EVERY INSTRUMENT WAS GREEN OVER IT, and this is the entry's real subject. The
recorded oracle reads a bounding rectangle plus nineteen computed properties **of
the region's own element**. `shell/sheet-content` measures `#sheetin`; a child
three times too large inside it changes none of those twenty numbers. That is the
same limit B-061 arbitrated for pseudo-elements and D8 writes down: the oracle
measures ELEMENTS. It is not a fault in the oracle — it is the reason a rule has
to exist beside it, the way R26 reads a `::after` the oracle cannot.

AND THE SHELL WAS WRONG TOO, which is why this rule holds both. The header's
avatar carried the complete class set — `w-full h-full object-cover
rounded-[inherit] block` — and rendered at **20x30 inside a 32x32 button**. A
`<button>` keeps the platform's own padding, so `w-full` resolved against a
content box the padding had already shrunk. Every class was right and the result
was a small oval. That is B-224, and it was found by measuring the half that was
supposed to be correct.

**A rule that held only the panel would go green over a fix that traded one
avatar for the other**, which is the shape `scroll_memory.py` names for its own
subject. Both are held, and both are named in their detail lines.

WHAT IT DOES NOT READ, said before what it does:

  - IT DOES NOT READ THE PICTURE. Whether the right person is shown, whether the
    crop is flattering, whether the image loaded at all beyond having a natural
    size — none of that is here. It holds a BOX and how that box is filled.
  - IT DOES NOT READ EVERY AVATAR IN THE APPLICATION. Cast portraits carry their
    own anchor (`cast/avatar`) and their own rule in `bugs.py`. The corpus here
    is the two elements that carry `data-part="avatar"`, and the count is
    PRINTED: a corpus that quietly loses one of them would otherwise report the
    same word as one that read both.
  - IT DOES NOT HOLD THE HOST'S SIZE. That 42 and 32 are the right numbers is a
    drawing decision and the oracle's business — which it does measure, since
    the host is an element. This rule holds only that the child agrees with
    whatever the host declares.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

# The state that opens a panel carrying an avatar. Driven through `__go`, the
# same seam the oracle drives, so this rule and the recorded references stand on
# one scenario rather than two spellings of it.
STATE = "sheet-user"

# The two avatars, by the anchor both already emit. Named rather than swept:
# each is held for its own reason, and a sweep would report « 2 of 2 agree »
# without saying which two.
AVATARS = (
    ("the shell's, in the header", 'header [data-part="avatar"]'),
    ("the panel's, in the open sheet", '#sheetin [data-part="avatar"]'),
)

# How many must be found. A corpus that loses an avatar reports « every avatar
# agrees » about the one it still reads.
CORPUS_FLOOR = 2

# A pixel of tolerance on each side. `object-fit: cover` and a rounded host can
# leave a sub-pixel edge, and a tolerance of zero would measure the rounding
# rather than the constraint.
TOLERANCE = 1


async def measure(page):
    """Reads each avatar's host box, its image's box and how the image fills it.

    Returns:
        One entry per avatar found, keyed by its selector.
    """
    return await page.evaluate(
        """(avatars) => {
             const out = {};
             for (const selector of avatars) {
               const host = document.querySelector(selector);
               if (!host) continue;
               const image = host.querySelector("img");
               if (!image) { out[selector] = { image: null }; continue; }
               const hostBox = host.getBoundingClientRect();
               const imageBox = image.getBoundingClientRect();
               const style = getComputedStyle(image);
               out[selector] = {
                 image: true,
                 host: [Math.round(hostBox.width), Math.round(hostBox.height)],
                 box: [Math.round(imageBox.width), Math.round(imageBox.height)],
                 natural: [image.naturalWidth, image.naturalHeight],
                 objectFit: style.objectFit,
                 display: style.display,
               };
             }
             return out;
           }""",
        [selector for _, selector in AVATARS])


async def hold(journal):
    """Opens the panel and holds both avatars."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(state)=>window.__go(state)", STATE)
        await page.wait_for_timeout(1200)
        found = await measure(page)

        journal.check(
            "both avatars are on the screen to be measured",
            len(found) >= CORPUS_FLOOR,
            f"{len(found)} of {CORPUS_FLOOR} found — an arm that reads one "
            "avatar reports the same word as one that read both")

        for label, selector in AVATARS:
            reading = found.get(selector)
            if not reading or not reading.get("image"):
                journal.check(f"{label} carries an image", False,
                              "no `img` under the avatar's anchor")
                continue
            host_width, host_height = reading["host"]
            box_width, box_height = reading["box"]
            journal.check(
                f"{label} fills the box its host declares",
                abs(box_width - host_width) <= TOLERANCE
                and abs(box_height - host_height) <= TOLERANCE,
                f"the host declares {host_width}x{host_height} and the image "
                f"renders {box_width}x{box_height}, from a natural "
                f"{reading['natural'][0]}x{reading['natural'][1]} — an "
                "unconstrained image renders at its natural size whatever its "
                "host says, and no region of the oracle can see it")
            journal.check(
                f"{label} is cropped rather than stretched",
                reading["objectFit"] == "cover",
                f"object-fit computes {reading['objectFit']}: the default is "
                "`fill`, which distorts a portrait to whatever box it is given")
            journal.check(
                f"{label} generates a block box",
                reading["display"] == "block",
                f"display computes {reading['display']}: an `img` is inline by "
                "default, which gives it a baseline gap and makes a percentage "
                "height resolve against a line box rather than against the host")

        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal(
        "R97 — an avatar's image fills its host, in the shell and in a panel")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
