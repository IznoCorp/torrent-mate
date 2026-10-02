"""R516 — a focused field's scroller has one pixel to scroll, and nothing on the page moves for it (B-674).

« Le curseur est revenu à sa place après cette manipulation » (Laura, iPhone SE, the
installed app): the caret of the « + » search sat below its field until the result
list scrolled. THE MECHANISM, read on the device by the reporter: a field whose
scrolling container cannot scroll gets its caret drawn low; a container that
overflows gets its own scroll view from iOS, and the caret with it. THE REPAIR
(operator ruling « ok A »): while a field has the focus, an invisible spacer at the
end of its scroller leaves exactly one pixel to scroll, and leaves with the focus.

WHAT IS READ, for every text field of the census — screens' ports (the « + » search
and its identifier, the ranking weights), sheets (a setting's text, a secret's key,
a role's name) and pages' port (« Filtrer par nom », the Médiathèque's search, the
settings' search, a new account's name) — each reached by its named state, in
Chromium and in WebKit:
  1. focused, its scroller can scroll by exactly one pixel when it could not
     before, and by what it could when its content already overflowed;
  2. focused, no element of the scroller, nor the scroller, moved or changed size,
     and the scroll position did not move;
  3. blurred, the spacer is gone and the scroller scrolls by what it did before,
     with nothing moved.

WHAT NO ENGINE HERE SHOWS: the caret itself is the iPhone's; the reporter confirms
it on the device. The structural condition the caret depends on is what is held.
"""
import asyncio

from common import PANEL_IN, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

# The scrollers a field sits in, as `app/focus-spacer.ts` names them.
SCROLLERS = ".port, .sheetin"

# The field's scroller and every box in it, read at one instant.
READ = """([selector, scrollers]) => {
  const field = document.querySelector(selector);
  const scroller = field?.closest(scrollers);
  if (!field || !scroller) return null;
  const spacer = (element) => element.hasAttribute('data-focus-spacer');
  const boxes = [scroller, ...scroller.querySelectorAll('*')]
    .filter((element) => !spacer(element))
    .map((element) => {
      const r = element.getBoundingClientRect();
      return [r.x, r.y, r.width, r.height];
    });
  return { room: scroller.scrollHeight - scroller.clientHeight, top: scroller.scrollTop, boxes,
           spacers: document.querySelectorAll('[data-focus-spacer]').length,
           focused: document.activeElement === field };
}"""

# Two frames: what a focus change sets in motion has been laid out.
FRAMES = "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"

# The field brought into its scroller's view, if it is not.
IN_VIEW = "(selector) => document.querySelector(selector)?.scrollIntoView({ block: 'nearest' })"

# A sheet's first secret, opened the way a tap opens it.
OPEN_SECRET = "() => document.querySelector('#view [data-secret]')?.click()"

# The fields, each with the named state that draws it and what opens it, if anything.
FIELDS = (
    ("acq-add-empty", "#addq", "the « + » search", None),
    ("acq-add-empty", "#byidv", "the « + » identifier", "() => document.querySelector('[data-part=\"add/by-id\"] summary')?.click()"),
    ("ranking-editor", '[data-part="ranking/weight"]', "a ranking weight", None),
    ("settings-field-text", '#sheetin [data-part="field/input"]', "a setting's text", None),
    ("settings-secrets", '#sheetin [data-part="secret/input"]', "a secret's key", OPEN_SECRET),
    ("accounts-roles", '#sheetin [data-part="accounts/role-name"]', "a role's name", None),
    ("acq-follows-list", "#follq", "« Filtrer par nom »", None),
    ("lib-grid", "#libq", "the Médiathèque's search", None),
    ("settings", "#qsettings", "the settings' search", None),
    ("accounts-roster", '[data-part="accounts/create"] input[name="name"]', "a new account's name", None),
)

# Below half a pixel a difference is rounding, not a move.
TOLERANCE = 0.5


def moved(before, after):
    """Counts the boxes that moved or changed size between two readings.

    Args:
        before: The boxes read first.
        after: The boxes read second, in the same order.

    Returns:
        How many boxes differ, or -1 when the two readings do not hold the same boxes.
    """
    if len(before) != len(after):
        return -1
    return sum(1 for one, two in zip(before, after)
               if any(abs(a - b) > TOLERANCE for a, b in zip(one, two)))


async def engine_pass(journal, browser, engine):
    """Reads every field of the census in one engine.

    Args:
        journal: The rule's journal.
        browser: The launched browser.
        engine: Its name, for the journal.

    Returns:
        The page errors seen.
    """
    errors = []
    context, page = await open_page(browser)
    page.on("pageerror", lambda error: errors.append(str(error)))
    for state, selector, name, opener in FIELDS:
        where = f"{engine}, {state}, {name}"
        await read_at(page, state, "() => null", wait=PANEL_IN + SETTLED)
        if opener is not None:
            await page.evaluate(opener)
            await page.wait_for_timeout(PANEL_IN + SETTLED)
        # AT REST FIRST: a panel gives its field the focus as it opens, and the
        # spacer with it; the reading starts from no focus at all.
        await page.evaluate("() => document.activeElement?.blur()")
        # IN VIEW FIRST, as under the finger that taps it: the focus is then given
        # without the browser's own scroll to the field, which is not the spacer's.
        await page.evaluate(IN_VIEW, selector)
        await page.evaluate(FRAMES)
        rest = await page.evaluate(READ, [selector, SCROLLERS])
        if not journal.check(f"{where}: the field is drawn in a scroller", rest is not None, selector):
            continue
        await page.evaluate("(selector) => document.querySelector(selector).focus({ preventScroll: true })", selector)
        await page.evaluate(FRAMES)
        focused = await page.evaluate(READ, [selector, SCROLLERS])
        wanted = 1 if rest["room"] <= 0 else rest["room"]
        journal.check(f"{where}: focused, its scroller has {wanted} px to scroll",
                      focused["focused"] and focused["room"] == wanted,
                      f"room {rest['room']} → {focused['room']}, focused {focused['focused']}")
        shifted = moved(rest["boxes"], focused["boxes"])
        journal.check(f"{where}: focused, nothing moved", shifted == 0 and focused["top"] == rest["top"],
                      f"{shifted} box(es) moved, scrollTop {rest['top']} → {focused['top']}")
        await page.evaluate("() => document.activeElement?.blur()")
        await page.evaluate(FRAMES)
        blurred = await page.evaluate(READ, [selector, SCROLLERS])
        journal.check(f"{where}: blurred, the spacer is gone and the scroller is as it was",
                      blurred["spacers"] == 0 and blurred["room"] == rest["room"],
                      f"spacers {blurred['spacers']}, room {rest['room']} → {blurred['room']}")
        shifted = moved(rest["boxes"], blurred["boxes"])
        journal.check(f"{where}: blurred, nothing moved", shifted == 0, f"{shifted} box(es) moved")
    await context.close()
    return errors


async def main():
    journal = Journal("R516 — a focused field's scroller has a pixel to scroll, nothing moves")
    errors = []
    async with async_playwright() as playwright:
        chromium = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        errors += await engine_pass(journal, chromium, "chromium")
        await chromium.close()
        webkit = await playwright.webkit.launch()
        errors += await engine_pass(journal, webkit, "webkit")
        await webkit.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
