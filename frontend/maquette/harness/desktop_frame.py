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
would draw here » is « what this page draws with no `.device` in it »: every
declaration the frame contributes is written `.device ...` in the one
stylesheet that does not ship, so dropping that class from the element leaves
the app's own cascade answering, on the same page, in the same browser, at the
same width. Nothing is served twice and nothing is assumed.

AND ITS LIMIT, which is not a detail. Removing the class also removes the
element's `width: 100%`, `height: 100svh` and `position: relative`, so the
control document's device is a 312 x 427 un-positioned box rather than a
shell. For a property driven by a `@media` query on the WINDOW that changes
nothing — the window is the same width either way, which is every property
this rule compares. It would stop being harmless the day a property driven by
a CONTAINER query joined them: the app draws `@container/port` containers, and
a container query would answer about 312px in the control document and about
the window out of the frame. So this control document is the app's cascade
FOR WINDOW-DRIVEN PROPERTIES, and a container-driven one may not be added to
`FORCED` without giving it a control of its own.
"""
import asyncio
import pathlib
import re
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

# The frame's own breakpoint, which is the tightest width it is ever drawn at
# and the only place the control's arithmetic can go wrong. One pixel below it
# the frame is not drawn and the control is not in the layout.
TIGHTEST = {"viewport": {"width": 520, "height": 800},
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

# EVERY property the frame re-asserts on an element inside the device, each on
# the element the frame names — and « every » is not a claim this list makes
# about itself. An earlier version of this comment said « they are not a
# sample: they are every property the re-assertion block declares » while
# reading three of the four the blocks declared, and `padding-right` sat
# behind that sentence unread. A claim no hold reads is where the defect is,
# so the claim is measured now: `declared_reassertions()` parses the
# stylesheet and the completeness hold refuses the day a scoped declaration
# appears that this list does not carry.
#
# The connection label has no naming attribute of its own — it is the second
# of the two spans the mark draws, and the mark is the named element — so it is
# reached STRUCTURALLY rather than by the class the stylesheets select it with.
FORCED = [('[data-part="shell/tab-bar"]', "display"),
          ('[data-part="shell/tab-bar"]', "position"),
          ('[data-part="shell/tab-bar"]', "inset-inline-start"),
          ('[data-part="shell/tab-bar"]', "inset-inline-end"),
          ('[data-part="shell/tab-bar"]', "bottom"),
          ('[data-part="shell/header"]', "padding-left"),
          ('[data-part="shell/header"]', "padding-right"),
          ('[data-part="shell/connection-mark"] > span:last-child', "display"),
          ('[data-part="shell/add-action"]', "position"),
          ('[data-part="selection/bar"]', "position")]

# The three elements this page always draws. The others in FORCED may be absent
# from a given screen — the FAB and the selection bar are not on every one — and
# an absent element is REPORTED rather than silently dropped, because a
# comparison over a shrinking set of keys is the vacuity this rule exists to
# refuse.
# DECLARATIONS THE FRAME MAKES THAT THE APP ALREADY MAKES, so they read the
# same on both sides and can witness nothing. They are listed rather than
# tolerated: a property that cannot move is where a dead hold hides, and the
# hold below refuses BOTH a new one appearing and a listed one coming alive.
#
# Each was read in the app's own variants, not guessed:
#   `ui/variants/frame.ts:60`  the tab bar is `bottombar fixed inset-x-0
#                              bottom-0` — so the frame's `inset-inline: 0`
#                              and `bottom: 0` restate what the app declares,
#                              and only `position` is a real deviation;
#   `ui/variants/frame.ts:111` the action button is `fab absolute …`;
#   `ui/variants/frame.ts:124` the selection bar is `selbar absolute …`.
#
# So of the five declarations in the DECLARED HARNESS DEVIATION block, ONE
# deviates and four restate. The file's own comment calls that block « the
# ONLY accepted divergence in the shell », and the divergence is narrower than
# the block implementing it — B-373.
REDUNDANT = {('[data-part="shell/tab-bar"]', "inset-inline-start"),
             ('[data-part="shell/tab-bar"]', "inset-inline-end"),
             ('[data-part="shell/tab-bar"]', "bottom"),
             ('[data-part="shell/add-action"]', "position"),
             ('[data-part="selection/bar"]', "position")}


def key(selector, property_name):
    """The key one reading of one property is stored under.

    A dict keyed by the SELECTOR alone kept the last property written and
    silently dropped the four before it, so five readings on the tab bar
    became one and two holds compared a value nobody had asked for.

    Args:
        selector: The anchor the element is reached by.
        property_name: The CSS property read on it.

    Returns:
        The composite key, matching what the page script builds.
    """
    return f"{selector} · {property_name}"


ALWAYS_DRAWN = ('[data-part="shell/tab-bar"]',
                '[data-part="shell/header"]',
                '[data-part="shell/connection-mark"] > span:last-child')

# The stylesheet the frame is written in, read as TEXT by the completeness
# hold. It is the same file the served copy is built from; the hold asks what
# it DECLARES, which no browser reading can answer once the cascade has
# resolved it.
HARNESS_STYLESHEET = (pathlib.Path(__file__).resolve().parents[1]
                      / "design" / "src" / "styles" / "harness.css")

# The condition every scoped block carries. A block that has it is the frame
# speaking; a block without it is the shell's own and outlives the switch.
SCOPE = ":root:not(:has(#desktop-switch:checked))"

# `getComputedStyle` answers longhands. A shorthand in the stylesheet is
# therefore expanded here, so that the completeness hold compares like with
# like instead of reporting a difference that is only a spelling.
LONGHANDS = {"inset-inline": ("inset-inline-start", "inset-inline-end"),
             "border": ("border-top-width",),
             "padding": ("padding-left", "padding-right")}

# THE STYLESHEET AND THIS RULE NAME THE SAME THING, and that is why no table
# stands between them. The frame's re-assertions used to select the app's
# elements by their style class — `.device .bottombar` — so a rule comparing
# what the stylesheet declares against what it reads needed a class-to-anchor
# map, and that map IS a class-anchored selector spelled sideways (D4 refuses
# it, and was right to). The selectors are written on `data-part` now, which
# every one of those five elements already carried, so the leaf this parser
# lifts out of the stylesheet is character-for-character the anchor `FORCED`
# reads. The completeness hold compares them directly.


def declared_reassertions():
    """Every declaration the frame scopes onto an element inside the device.

    The stylesheet is parsed rather than the rendered page, because the
    question is what the frame DECLARES: once the cascade has resolved, a
    declaration that was left behind and one that was never written look
    identical.

    Returns:
        A set of `(class selector, longhand property)` pairs, shorthands
        expanded, covering every rule whose selector carries the switch's
        scope and names a DESCENDANT of the device. The device's own blocks
        are excluded — they are the frame itself, held by the geometry and
        skin holds rather than by `FORCED`.
    """
    text = HARNESS_STYLESHEET.read_text(encoding="utf-8")
    # Comments carry example selectors and whole declaration blocks; parsing
    # them would have the hold refuse the day someone documents a rule.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    declared = set()
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        targets = [one.strip() for one in selectors.split(",")]
        if not all(SCOPE in one for one in targets):
            continue
        # THE FRAME'S OWN ELEMENTS ARE TOLD APART BY SHAPE, not by name. A
        # block that scopes ONE token — the device, the stage — is the frame
        # itself; a block that scopes a token INSIDE another is a re-assertion
        # on the app. Naming them here would put the style classes this rule
        # is forbidden to hold (D4) back into it through the side door.
        #
        # Neither of the frame's own is unread: the device carries the
        # phone's dimensions and skin, held against the control document by
        # the geometry and skin holds, and the stage carries the gutter,
        # whose departure the device's own rect reads — a stage still padding
        # 24px by 16px cannot contain a device whose box starts at (0, 0) and
        # measures the whole window.
        inside = [one for one in targets
                  if len(one.split(SCOPE, 1)[1].split()) > 1]
        if not inside:
            continue
        for target in inside:
            # Everything after the scope and the device token: the anchor
            # whole, compound selectors included, so
            # `[data-part="shell/connection-mark"] > span:last-child` arrives
            # as one string rather than as its last word.
            after = target.split(SCOPE, 1)[1].split(None, 1)[1].strip()
            for declaration in body.split(";"):
                if ":" not in declaration:
                    continue
                name = declaration.split(":", 1)[0].strip()
                if not name or name.startswith("-"):
                    continue
                for longhand in LONGHANDS.get(name, (name,)):
                    declared.add((after, longhand))
    return declared

READ_FORCED = """(forced)=>{
  const out = {};
  for (const [selector, property] of forced) {
    const el = document.querySelector(selector);
    out[selector + " · " + property] =
      el ? getComputedStyle(el).getPropertyValue(property) : null;
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
    out[selector + " · " + property] =
      el ? getComputedStyle(el).getPropertyValue(property) : null;
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

# THE FRAME IS FIVE DECLARATIONS AND THE WIDTH IS ONE OF THEM. Reading the
# width alone let the whole SKIN stay behind — a rounded, bordered,
# drop-shadowed slab stopping 48px short of the window's bottom — while every
# hold in this rule read green and the header claimed it refused exactly that.
# So the device is read as a BOX plus the skin, both against the control
# document, and the width is no longer asked to speak for four properties it
# says nothing about.
# `height` is NOT here, and the first version of this list had it. Out of the
# frame the device is `height: 100svh` — the window — while the control
# document, which has no `.device` at all, is as tall as its content (861px
# against 800). The two are not comparable and the hold fell saying so. The
# device's height is held where it belongs: by the BOX hold, against the
# viewport's own rectangle, which is the reading that actually says « the
# device is the window ».
DEVICE_SKIN = ["border-top-width", "border-radius", "box-shadow", "overflow"]

# What the harness declares on the device and does NOT take back at the
# switch, each with the reason it stays. They are held by name so that
# « nothing says so » can never again be the answer to « why is this still
# firing out of the frame? ».
#
#   position: relative   `app/shell.tsx` re-parents the React root into
#                        `#device` before the first render, and a layer inside
#                        it resolves `position: absolute` against this element.
#                        Scoping it away would move every such layer to the
#                        viewport — the harness changing what the app draws,
#                        which is the one thing this file may never do.
DEVICE_SURVIVES = {"position": "relative"}

DEVICE_BOX = """(argument)=>{
  const [device, skin, survives] = argument;
  const el = document.querySelector(device);
  const box = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  const out = {rect: [Math.round(box.x), Math.round(box.y),
                      Math.round(box.width), Math.round(box.height)]};
  for (const property of skin) out[property] = style.getPropertyValue(property);
  for (const property of survives)
    out['survives:' + property] = style.getPropertyValue(property);
  return out;
}"""

# The same removal the FORCED control document uses, on the device itself: the
# frame's whole contribution is written `.device …`, so the element with that
# class off is what the app's cascade alone says about it.
UNFRAMED_DEVICE = """(argument)=>{
  const [device, skin] = argument;
  const el = document.querySelector(device);
  el.classList.remove('device');
  const style = getComputedStyle(el);
  const out = {};
  for (const property of skin) out[property] = style.getPropertyValue(property);
  el.classList.add('device');
  return out;
}"""

# THE NAME AGAINST THE WORD ON SCREEN. An accessible name is computed from the
# label's RENDERED subtree, so the hold that only asked the two states to
# differ was green over a control announcing « Sortir du cadre Revenir au
# cadre » — one word against two are never equal. The question is not whether
# the name changes; it is whether the name is the word the operator can read.
VISIBLE_WORDS = """(label)=>{
  return [...document.querySelector(label).querySelectorAll('span')]
    .filter((span)=>span.getClientRects().length > 0)
    .map((span)=>span.textContent.trim());
}"""

# The label's right edge against the frame's left edge. Read at the TIGHTEST
# width rather than at 1280, where the gutter is 332px wide and any constant
# between 195 and 500 would pass — a hold placed where nothing can go wrong
# measures nothing.
GEOMETRY = """(argument)=>{
  const [switchSelector, device] = argument;
  const control = document.querySelector(switchSelector).getBoundingClientRect();
  const frame = document.querySelector(device).getBoundingClientRect();
  return {labelRight: Math.round(control.right),
          frameLeft: Math.round(frame.left),
          gap: Math.round(frame.left - control.right)};
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
    missing = sorted({selector for selector, property_name in FORCED
                      if framed[key(selector, property_name)] is None})

    journal.check(
        "every property the frame forces is readable on the element the frame "
        "names, and the ones this screen does not draw are NAMED",
        all(selector not in missing for selector in ALWAYS_DRAWN),
        f"at {width}px — {framed}; a hold over an element that is not there "
        f"measures nothing, so absence is reported rather than dropped. "
        f"Not drawn on this screen: {missing or 'none'}; of the three this "
        f"page always draws, missing: "
        f"{[s for s in ALWAYS_DRAWN if s in missing] or 'none'}")
    # ONLY WHERE BOTH SIDES ANSWERED. An element this screen does not draw
    # reads `None` on both, and `None != None` is False — so an absent element
    # would silently shrink the set this hold counts over, which is the
    # vacuity the hold exists to refuse.
    answered = [(selector, property_name) for selector, property_name in FORCED
                if selector not in missing]
    moved = {pair for pair in answered
             if framed[key(*pair)] != unframed[key(*pair)]}
    redundant = {pair for pair in answered if pair not in moved}
    journal.check(
        "and the frame really is forcing them: each reads differently with the "
        "device's own class removed",
        redundant == {pair for pair in REDUNDANT if pair in answered}
        and len(answered) >= len(ALWAYS_DRAWN),
        f"at {width}px — {len(moved)} of {len(answered)} answered move. A "
        f"property the frame does not move cannot show that the frame left, "
        f"so the ones that cannot are DECLARED: expected "
        f"{sorted(REDUNDANT)}, read {sorted(redundant)}. Framed {framed}, "
        f"unframed {unframed}")

    # THE LIST IS COMPLETE, AND THAT IS MEASURED. `FORCED` used to carry a
    # sentence claiming it held every property the re-assertion blocks
    # declare, while reading three of four. The stylesheet is parsed and
    # compared here, so the sentence is a reading rather than a promise.
    declared = declared_reassertions()
    read = {(selector, property_name) for selector, property_name in FORCED}
    unread = sorted(pair for pair in declared if pair not in read)
    journal.check(
        "every declaration the frame scopes onto an element inside the device "
        "is one this rule reads, and the STYLESHEET is what says how many "
        "there are",
        not unread,
        f"{len(declared)} declared in {HARNESS_STYLESHEET.name}, "
        f"{len(FORCED)} read — unread: {unread or 'none'}. The list is not "
        f"trusted to be complete: it is compared against the file, so a "
        f"declaration added there without a reading here falls this hold")

    framed_box = await page.evaluate(
        DEVICE_BOX, [DEVICE, DEVICE_SKIN, list(DEVICE_SURVIVES)])
    unframed_box = await page.evaluate(UNFRAMED_DEVICE, [DEVICE, DEVICE_SKIN])
    journal.check(
        "the frame is drawn on a desktop window — its dimensions AND its skin",
        framed_box["rect"][2] == 390,
        f"at {width}px — the device box is {framed_box['rect']} and its skin "
        f"reads { {k: framed_box[k] for k in DEVICE_SKIN} }")

    skin_moved = [k for k in DEVICE_SKIN if framed_box[k] != unframed_box[k]]
    journal.check(
        "and every one of those skin properties really is the frame's: each "
        "reads differently with the device's own class removed",
        len(skin_moved) == len(DEVICE_SKIN),
        f"at {width}px — framed { {k: framed_box[k] for k in DEVICE_SKIN} }, "
        f"unframed {unframed_box}. A skin property the frame does not move "
        f"could not show the frame leaving: {sorted(skin_moved)}")

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
    framed_words = await page.evaluate(VISIBLE_WORDS, LABEL)
    journal.check(
        "and it is a named control, not a bare box, and the name is the word "
        "ON SCREEN — one word in the layout, and the tree saying that word",
        await page.evaluate(LABELLED, [CHECKBOX, LABEL])
        and "checkbox" in framed_name
        and len(framed_words) == 1
        and framed_words[0] in framed_name,
        f"the label names the checkbox; the tree reads {framed_name.strip()!r} "
        f"and the spans in the layout are {framed_words}. Two of them would be "
        f"a control announcing both verbs at once, which a hold asking only "
        f"that the name be non-empty cannot see")

    covers = await page.evaluate(COVERS, [SWITCH, FIXED_CHROME])
    journal.check(
        "and it covers none of the app's fixed chrome while the frame is drawn",
        covers == [],
        f"at {width}px, framed — {covers or 'nothing'}")

    # ONE PRESS.
    await page.click(LABEL)
    await page.wait_for_timeout(200)
    left_box = await page.evaluate(
        DEVICE_BOX, [DEVICE, DEVICE_SKIN, list(DEVICE_SURVIVES)])
    height = DESKTOP["viewport"]["height"]
    journal.check(
        "one press and the device is the window, not a phone drawn inside it "
        "— the whole box, not its width alone",
        left_box["rect"] == [0, 0, width, height],
        f"at {width}px — the device box is {left_box['rect']}, against the "
        f"window's [0, 0, {width}, {height}]")

    skin_left = {k: left_box[k] for k in DEVICE_SKIN}
    journal.check(
        "and the frame's SKIN went with its dimensions — no border, no "
        "radius, no shadow, nothing clipped, on a device the app alone draws",
        skin_left == unframed_box,
        f"at {width}px — read {skin_left}, and a document with no frame reads "
        f"{unframed_box}")

    stayed = {k: left_box["survives:" + k] for k in DEVICE_SURVIVES}
    journal.check(
        "and what the harness keeps out of the frame is what it SAYS it "
        "keeps, and nothing besides",
        stayed == DEVICE_SURVIVES,
        f"at {width}px — read {stayed}, declared {DEVICE_SURVIVES}. These "
        f"survive on purpose and each carries its reason where it is "
        f"declared; a fourth one appearing here is the defect")

    left = await page.evaluate(READ_FORCED, FORCED)
    journal.check(
        "and the app's own stylesheet answers every property the frame was "
        "forcing",
        left == unframed,
        f"at {width}px — read {left}, and a document with no frame reads "
        f"{unframed}")

    left_name = await page.locator(CHECKBOX).aria_snapshot()
    left_words = await page.evaluate(VISIBLE_WORDS, LABEL)
    journal.check(
        "and the control now names the way BACK, so the word says what the "
        "next press does rather than what the last one did — and that word is "
        "again the only one in the layout",
        left_name != framed_name
        and len(left_words) == 1
        and left_words[0] in left_name
        and left_words != framed_words,
        f"out of the frame the tree reads {left_name.strip()!r} over the span "
        f"{left_words}, against {framed_name.strip()!r} over {framed_words} "
        f"inside it")

    covers_left = await page.evaluate(COVERS, [SWITCH, FIXED_CHROME])
    journal.check(
        "and the way back covers none of the app's fixed chrome either",
        covers_left == [],
        f"at {width}px, out of the frame — {covers_left or 'nothing'}")

    # AND BACK.
    await page.click(LABEL)
    await page.wait_for_timeout(200)
    back_box = await page.evaluate(
        DEVICE_BOX, [DEVICE, DEVICE_SKIN, list(DEVICE_SURVIVES)])
    back = await page.evaluate(READ_FORCED, FORCED)
    journal.check(
        "a second press and the frame is back WHOLE — the box, the skin and "
        "the re-assertions together",
        back_box == framed_box and back == framed,
        f"at {width}px — the device box is {back_box['rect']} and its skin "
        f"{ {k: back_box[k] for k in DEVICE_SKIN} }, against "
        f"{framed_box['rect']} and { {k: framed_box[k] for k in DEVICE_SKIN} } "
        f"before the first press; the re-assertions read {back} against "
        f"{framed}")

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


async def measure_tightest(browser, journal):
    """Holds the label's edge against the frame's at the width that decides it.

    The arithmetic that keeps the control off the prototype is
    `left + max-width` against the frame's left edge, and it is tight for
    exactly one band of widths — from the frame's own breakpoint up to the
    width at which the label reaches its natural size. At 1280 the gutter is
    332px and any constant between 195 and 500 would pass, so a hold placed
    there reads nothing about the property it claims to hold.

    Args:
        browser: A launched Playwright browser.
        journal: The run's journal.
    """
    context, page = await open_page(browser, **TIGHTEST)
    width = TIGHTEST["viewport"]["width"]
    reading = await page.evaluate(GEOMETRY, [SWITCH, DEVICE])
    journal.check(
        "at the tightest width the frame is drawn at, the way out of it does "
        "not sit on the prototype",
        reading["gap"] >= 0,
        f"at {width}px — the label's right edge is at "
        f"{reading['labelRight']}, the frame's left edge at "
        f"{reading['frameLeft']}, gap {reading['gap']}px. It ABUTS by "
        f"arithmetic (`16px + (50% - 211px)` = `50% - 195px`) and must never "
        f"cross; the stylesheet's comment claimed 16px of clearance for a "
        f"while and the true figure is 0")
    await context.close()


async def hold(journal):
    """Runs all three viewports against one browser.

    Args:
        journal: The run's journal.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        await measure_phone(browser, journal)
        await measure_desktop(browser, journal)
        await measure_tightest(browser, journal)
        await browser.close()
    journal.summary()


def main():
    """Runs the rule."""
    journal = Journal(
        "R140 — the way out of the phone frame is a desktop's alone, and total")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
