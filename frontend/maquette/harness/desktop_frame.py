"""R140 — the way out of the phone frame is a desktop's alone, and it is total.

The prototype is read on two machines and the frame answers only one of them.
On a phone the device fills the window and the frame is nothing; on a desktop
browser it draws a 390px phone inside the page AND re-asserts the mobile
presentation inside it, because the app's own breakpoints measure the WINDOW
and a phone drawn in a wide page would otherwise switch to the desktop
presentation halfway. That second half is why the desktop layout is the one
surface the operator cannot look at on the design host: the frame is drawn, and
the frame forces the phone.

So the switch removes BOTH — the phone's dimensions and the re-assertions — and
this rule refuses either half being left behind. A device that fills a desktop
window while the re-assertions still fire is a desktop window wearing a phone's
presentation: the same defect moved rather than removed, and a rule that only
measured the device's width would pass over it.

WHAT IT REFUSES, hold by hold:

  * the control existing at all on a phone-sized viewport — not merely hidden,
    but out of the layout, out of reach of a finger and out of the focus order.
    A control drawn at 0x0 that still takes focus satisfies `visibility` and
    fails a hand;
  * the control sitting on top of the app's own fixed chrome at the width where
    it IS drawn, in either of its states — the harness bar's rule read for the
    second piece of harness chrome to exist;
  * the frame not leaving: the device's width, and three computed properties
    the frame forces, read against a document where the device carries no frame
    at all. The expected values are MEASURED in that control document and never
    typed here, because a number typed into a rule is a number that stops
    describing the stylesheet the day the stylesheet moves;
  * the frame not coming back: the same three properties and the same width,
    after a second press;
  * the control surviving `window.__measure(true)`, which would put harness
    chrome into a capture the oracle takes as the reference.

THE CONTROL DOCUMENT, and why it is built by removing a class. « What the app
would draw here » is exactly « what this page draws with no `.device` in it »:
every declaration the frame contributes is written `.device ...` in the one
stylesheet that does not ship, so dropping that class from the element leaves
the app's own cascade answering, on the same page, in the same browser, at the
same width. Nothing is served twice and nothing is assumed.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# Both sides of the frame's own breakpoint, which is where « desktop » stops
# being a word and becomes a width: the harness stylesheet turns the device into
# a phone at 520px, so below it there is no frame to leave and the control must
# not exist. The desktop width is the harness bar's own, so the two pieces of
# harness chrome are read at the same place.
PHONE_WIDTH = PHONE["viewport"]["width"]
DESKTOP = {"viewport": {"width": 1280, "height": 800},
           "is_mobile": False, "has_touch": False}

SWITCH = '[data-part="harness/desktop-switch"]'
LABEL = '[data-part="harness/desktop-switch-label"]'
CHECKBOX = "#desktop-switch"
DEVICE = "#device"

# The app's FIXED chrome — the controls that are in the same place whatever is
# on screen, and the same list the harness bar is held against. A floating
# control always covers something on a phone and content can be swiped out from
# under it; the avatar cannot, and neither can the tab bar.
FIXED_CHROME = ('[data-part="avatar"], [data-part="shell/header"] button, '
                '[data-part="shell/tab-bar"] button, #fab, '
                '[data-part="shell/add-action"]')

# The three the frame forces, each on the element the frame names. They are not
# a sample: they are every property the re-assertion block declares, so a
# re-assertion left behind has nowhere to hide.
# The connection label has no naming attribute of its own — it is the second
# of the two spans the mark draws, and the mark is the named element — so it is
# reached STRUCTURALLY rather than by the class the stylesheets select it with.
FORCED = [('[data-part="shell/tab-bar"]', "display"),
          ('[data-part="shell/header"]', "padding-left"),
          ('[data-part="shell/connection-mark"] > span:last-child', "display")]

READ_FORCED = """(forced)=>{
  const out = {};
  for (const [selector, property] of forced) {
    const el = document.querySelector(selector);
    out[selector] = el ? getComputedStyle(el).getPropertyValue(property) : null;
  }
  return out;
}"""

# The control document: the frame's whole contribution is written `.device ...`,
# so an element that has stopped answering to that class is the app's cascade
# and nothing else. The class goes back on before the reading is returned.
UNFRAMED = """(forced)=>{
  const device = document.getElementById('device');
  device.classList.remove('device');
  const out = {};
  for (const [selector, property] of forced) {
    const el = document.querySelector(selector);
    out[selector] = el ? getComputedStyle(el).getPropertyValue(property) : null;
  }
  device.classList.add('device');
  return out;
}"""

# A rect and the three ways a control can still be there after being hidden: a
# box, a point a finger lands on, and the focus order. `elementFromPoint` is
# asked at the corner the control occupies when it IS drawn, so the question is
# « is anything of it under that finger », not « does it have a size ».
PRESENCE = """(selectors)=>{
  const [switchSelector, label, checkbox] = selectors;
  const node = document.querySelector(switchSelector);
  if (!node) return {missing: true};
  const box = node.getBoundingClientRect();
  const at = document.elementFromPoint(20, 20);
  const input = document.querySelector(checkbox);
  input.focus();
  const focused = document.activeElement === input;
  input.blur();
  return {missing: false,
          rects: node.getClientRects().length,
          area: box.width * box.height,
          underFinger: !!(at && at.closest(switchSelector)),
          focused: focused};
}"""

COVERS = """(argument)=>{
  const [switchSelector, chrome] = argument;
  const node = document.querySelector(switchSelector);
  const a = node.getBoundingClientRect();
  if (!a.width) return ['ABSENT'];
  const crosses = (b) => !(a.right <= b.left || b.right <= a.left
                           || a.bottom <= b.top || b.bottom <= a.top);
  return [...document.querySelectorAll(chrome)]
    .filter((el) => el.getClientRects().length > 0)
    .filter((el) => crosses(el.getBoundingClientRect()))
    .map((el) => el.getAttribute('data-part') || el.id || el.tagName);
}"""

LABELLED = """(argument)=>{
  const [checkbox, label] = argument;
  return document.querySelector(label).control
         === document.querySelector(checkbox);
}"""

OUTSIDE = """(argument)=>{
  const [switchSelector, device] = argument;
  return !document.querySelector(device)
            .contains(document.querySelector(switchSelector));
}"""


async def measure_phone(browser, journal):
    """Holds that the control does not exist on a phone-sized viewport.

    Args:
        browser: A launched Playwright browser.
        journal: The run's journal.
    """
    context, page = await open_page(browser)
    reading = await page.evaluate(PRESENCE, [SWITCH, LABEL, CHECKBOX])
    journal.check(
        "the control is in the document on a phone, so its absence there is a "
        "decision and not an accident",
        not reading["missing"],
        f"{SWITCH} at {PHONE_WIDTH}px")
    if not reading["missing"]:
        journal.check(
            "and it is not in the layout on a phone: no box, no finger, no "
            "focus",
            reading["rects"] == 0 and reading["area"] == 0
            and not reading["underFinger"] and not reading["focused"],
            f"at {PHONE_WIDTH}px — client rects {reading['rects']}, area "
            f"{reading['area']}, under the finger at (20, 20) "
            f"{reading['underFinger']}, takes focus {reading['focused']}")
    await context.close()


async def measure_desktop(browser, journal):
    """Holds the frame's departure, its return, and what the control covers.

    Args:
        browser: A launched Playwright browser.
        journal: The run's journal.
    """
    width = DESKTOP["viewport"]["width"]
    context, page = await open_page(browser, **DESKTOP)

    # THE CONTROL DOCUMENT FIRST, and on the framed page: what the app draws
    # here is what this page draws with the frame's own class taken off the
    # device, so the expected values below are measured rather than declared.
    unframed = await page.evaluate(UNFRAMED, FORCED)
    framed = await page.evaluate(READ_FORCED, FORCED)
    missing = [selector for selector, _ in FORCED if framed[selector] is None]
    journal.check(
        "the three properties the frame forces are readable on the elements "
        "the frame names",
        not missing,
        f"at {width}px — {framed}; a hold over an element that is not there "
        f"measures nothing. Missing: {missing or 'none'}")
    moved = {selector for selector, _ in FORCED
             if framed[selector] != unframed[selector]}
    journal.check(
        "and the frame really is forcing them: each reads differently with the "
        "device's own class removed",
        len(moved) == len(FORCED),
        f"at {width}px — framed {framed}, unframed {unframed}. A property the "
        f"frame does not move cannot show that the frame left: {sorted(moved)}")

    device = page.locator(DEVICE)
    framed_width = await device.evaluate(
        "(el)=>el.getBoundingClientRect().width")
    journal.check(
        "the frame is drawn on a desktop window",
        round(framed_width) == 390,
        f"at {width}px — the device measures {framed_width:.0f}px")

    journal.check(
        "and the way out of it sits OUTSIDE the shell, which is a measured "
        "region and carries nothing the app does not have",
        await page.evaluate(OUTSIDE, [SWITCH, DEVICE]),
        f"{SWITCH} is not a descendant of {DEVICE}")

    # THE NAME IS READ FROM THE ACCESSIBILITY TREE and never from
    # `textContent`, which returns the text of BOTH words: the one on screen
    # and the one `display: none` is holding back. A hold reading that would be
    # green over a control whose name never changes, and green over a control
    # announcing two contradictory verbs at once.
    framed_name = await page.locator(CHECKBOX).aria_snapshot()
    journal.check(
        "and it is a named control, not a bare box",
        await page.evaluate(LABELLED, [CHECKBOX, LABEL])
        and "checkbox" in framed_name and framed_name.strip() != "- checkbox",
        f"the label names the checkbox, which the tree reads as "
        f"{framed_name.strip()!r}")

    covers = await page.evaluate(COVERS, [SWITCH, FIXED_CHROME])
    journal.check(
        "and it covers none of the app's fixed chrome while the frame is drawn",
        covers == [],
        f"at {width}px, framed — {covers or 'nothing'}")

    # ONE PRESS.
    await page.click(LABEL)
    await page.wait_for_timeout(200)
    left_width = await device.evaluate("(el)=>el.getBoundingClientRect().width")
    journal.check(
        "one press and the device is the window, not a phone drawn inside it",
        round(left_width) == width,
        f"at {width}px — the device measures {left_width:.0f}px")

    left = await page.evaluate(READ_FORCED, FORCED)
    journal.check(
        "and the app's own stylesheet answers every property the frame was "
        "forcing",
        left == unframed,
        f"at {width}px — read {left}, and a document with no frame reads "
        f"{unframed}")

    left_name = await page.locator(CHECKBOX).aria_snapshot()
    journal.check(
        "and the control now names the way BACK, so the word says what the "
        "next press does rather than what the last one did",
        left_name != framed_name,
        f"out of the frame the tree reads {left_name.strip()!r}, against "
        f"{framed_name.strip()!r} inside it")

    covers_left = await page.evaluate(COVERS, [SWITCH, FIXED_CHROME])
    journal.check(
        "and the way back covers none of the app's fixed chrome either",
        covers_left == [],
        f"at {width}px, out of the frame — {covers_left or 'nothing'}")

    # AND BACK.
    await page.click(LABEL)
    await page.wait_for_timeout(200)
    back_width = await device.evaluate("(el)=>el.getBoundingClientRect().width")
    back = await page.evaluate(READ_FORCED, FORCED)
    journal.check(
        "a second press and the frame is back, dimensions and re-assertions "
        "together",
        round(back_width) == 390 and back == framed,
        f"at {width}px — the device measures {back_width:.0f}px and the three "
        f"read {back}, against {framed} before the first press")

    # AND IT IS NOT IN A CAPTURE.
    await page.evaluate("()=>window.__measure(true)")
    await page.wait_for_timeout(120)
    hidden = await page.evaluate(
        "(s)=>document.querySelector(s).getClientRects().length", SWITCH)
    await page.evaluate("()=>window.__measure(false)")
    journal.check(
        "and the measuring pass clears it like every other piece of harness "
        "chrome",
        hidden == 0,
        f"at {width}px under `html.measuring` — client rects {hidden}")

    await context.close()


async def hold(journal):
    """Runs both viewports against one browser.

    Args:
        journal: The run's journal.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        await measure_phone(browser, journal)
        await measure_desktop(browser, journal)
        await browser.close()
    journal.summary()


def main():
    """Runs the rule."""
    journal = Journal(
        "R140 — the way out of the phone frame is a desktop's alone, and total")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
