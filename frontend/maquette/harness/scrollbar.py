"""R99 — the scrollbar wears the design system, in both spellings and both themes.

D11 (operator, 2026-08-26): the scroll container's bar is given the design
system's appearance through `scrollbar-width`, `scrollbar-color` and
`::-webkit-scrollbar` — declarative, in `base.css`. **A scrollbar rebuilt in
JavaScript is refused**: it loses the keyboard (PageUp/Down, Home/End, the
gutter click), the middle-click and the native role, and its thumb would be
positioned by a `scroll` handler, which is D9's first rule exactly.

**No declaration existed until L10-bis** (B-146). The decision was settled and
nothing implemented it.

WHY THE ORACLE CANNOT HOLD THIS, AND IT IS NOT THE GAP ANYBODY EXPECTED. The
entry predicted that narrowing the gutter would move « every measured rectangle
in that container », and it moved NONE: measured on this machine,
`#port.offsetWidth - #port.clientWidth` is **0**, because macOS paints an
OVERLAY scrollbar that occupies no layout space. So the change costs no geometry
here — and the oracle's twenty numbers per region are geometry and computed
properties OF THE ELEMENT. A scrollbar's colour is in none of them, and a
pseudo-element is in none of them by contract (B-061, D8). The oracle is green
over this whether it is styled or not, which is why the rule exists.

WHAT IT HOLDS:

  the standard spelling   `scrollbar-width: thin` and a `scrollbar-color` whose
                          thumb is the border token and whose track is
                          transparent. This is what Firefox reads.
  the WebKit spelling     `::-webkit-scrollbar` at 6px with a coloured thumb.
                          This is what Chrome reads — and Chrome is what the
                          oracle, this harness and the operator's phone all run,
                          so a rule holding only the standard property would
                          hold the browser nobody here measures.
  both themes             the colour is a TOKEN, so it resolves differently
                          under `data-theme="light"`. A rule that drove one
                          theme would prove half a palette, which is B-055's
                          defect one instrument to the left.
  a real scroll container the container it reads must actually overflow. A
                          scrollbar on a page that does not scroll is a
                          declaration nobody can see, and asserting over it is
                          asserting about nothing.

WHAT IT DOES NOT READ:

  - THE GUTTER. Whether the bar takes layout space is the PLATFORM's answer and
    changes between macOS, Linux and a phone. D11 records that a desktop keeps
    its gutter and calls it correct; pinning a number here would pin this
    machine.
  - HOW IT LOOKS. That 6px and the border token are the right choices is a
    drawing decision, and the maquette is where that is decided. This holds that
    the declaration reaches the element.
  - FIREFOX. The standard properties are asserted as DECLARED, not as rendered:
    this harness drives Chrome. Holding the declaration is what is available,
    and saying so is better than a rule that implies a browser it never opened.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

# A page with enough rows to overflow, so the bar has something to be about.
STATE = "lib-list"

# The scroll container the shell owns. Selected by its id, which the region
# table also uses — one anchor rather than two spellings of it.
PORT = "#port"

# What `base.css` declares. Held as VALUES rather than by re-reading the
# stylesheet: a rule that greps the CSS proves the text exists, and a rule that
# reads `getComputedStyle` proves it reached the element — which is the
# difference between a declaration and a style.
WANTED_WIDTH = "thin"
WANTED_PSEUDO_WIDTH = "6px"

# The token the thumb wears. Resolved in the page rather than written here as an
# oklch literal, because it changes with the theme and a literal would hold one.
THUMB_TOKEN = "--color-border"


async def measure(page):
    """Reads the bar's declarations and the container's own overflow."""
    return await page.evaluate(
        """({ port, token }) => {
             const element = document.querySelector(port);
             if (!element) return null;
             const style = getComputedStyle(element);
             const pseudo = getComputedStyle(element, "::-webkit-scrollbar");
             const probe = document.createElement("span");
             probe.style.color = `var(${token})`;
             element.appendChild(probe);
             const wanted = getComputedStyle(probe).color;
             probe.remove();
             return {
               width: style.scrollbarWidth,
               color: style.scrollbarColor,
               pseudoWidth: pseudo.width,
               wanted,
               overflow: element.scrollHeight - element.clientHeight,
               gutter: element.offsetWidth - element.clientWidth,
             };
           }""",
        {"port": PORT, "token": THUMB_TOKEN})


def thumb_matches(color: str, wanted: str) -> bool:
    """Says whether `scrollbar-color`'s thumb is the token, whatever the track.

    Chrome writes the pair as « thumb track ». The track is asserted separately
    as transparent, in either of the two spellings it uses.

    Args:
        color: The computed `scrollbar-color`.
        wanted: What the token resolves to in the same document.

    Returns:
        True when the first colour of the pair is the token.
    """
    # `wanted` MUST BE NON-EMPTY, and that is the whole of this line's history.
    # It read `bool(color) and color.startswith(wanted)`, and `startswith("")`
    # is ALWAYS true — so a token that resolved to nothing made the hold pass
    # over any colour at all. Proved rather than reasoned: a red thumb against
    # an empty token returned True. A comparison whose reference can be empty
    # is a comparison that is pre-satisfied, which is the shape this register
    # counts eighty-four times.
    return bool(color) and bool(wanted) and color.startswith(wanted)


def track_is_transparent(color: str) -> bool:
    """Says whether the track paints nothing."""
    return "rgba(0, 0, 0, 0)" in color or "transparent" in color


async def hold_one_theme(journal, page, label, light):
    """Holds every declaration under one theme."""
    await page.evaluate(
        """(on) => {
             if (on) document.documentElement.setAttribute("data-theme", "light");
             else document.documentElement.removeAttribute("data-theme");
           }""", light)
    await page.wait_for_timeout(300)
    reading = await measure(page)

    if reading is None:
        journal.check(f"{label}: the scroll container is there", False, PORT)
        return

    journal.check(
        f"{label}: the container actually overflows",
        reading["overflow"] > 0,
        f"{reading['overflow']}px of content past the viewport — a scrollbar on "
        "a page that does not scroll is a declaration nobody can see")
    journal.check(
        f"{label}: the standard spelling is declared",
        reading["width"] == WANTED_WIDTH,
        f"`scrollbar-width` computes {reading['width']!r} — this is what "
        "Firefox reads, and the harness drives Chrome, so it is held as "
        "DECLARED rather than as rendered")
    journal.check(
        f"{label}: the thumb wears the border token",
        thumb_matches(reading["color"], reading["wanted"]),
        f"`scrollbar-color` computes {reading['color']!r} and "
        f"`var({THUMB_TOKEN})` computes {reading['wanted']!r} in the same "
        "document — compared against the token, never against a literal, "
        "because it changes with the theme")
    journal.check(
        f"{label}: the track paints nothing",
        track_is_transparent(reading["color"]),
        f"the pair reads {reading['color']!r}")
    journal.check(
        f"{label}: the WebKit spelling is styled",
        reading["pseudoWidth"] == WANTED_PSEUDO_WIDTH,
        f"`::-webkit-scrollbar` computes width {reading['pseudoWidth']!r} — "
        "this is the one Chrome reads, and Chrome is what the oracle, this "
        "harness and the operator's phone all run")


async def hold(journal):
    """Drives one scrolling page under both themes."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(state)=>window.__go(state)", STATE)
        await page.wait_for_timeout(1000)

        await hold_one_theme(journal, page, "dark", light=False)
        await hold_one_theme(journal, page, "light", light=True)
        await page.evaluate(
            "()=>document.documentElement.removeAttribute('data-theme')")

        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal(
        "R99 — the scrollbar wears the design system, both spellings, both themes")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
