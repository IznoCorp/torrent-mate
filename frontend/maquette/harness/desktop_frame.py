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

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
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

# THE FRAME'S OWN CLASS IS ASKED OF THE DOCUMENT, never written here. The
# stylesheet selects the device by a style class and cannot stop doing so: the
# control document is built by REMOVING that class, which is what makes « what
# the app would draw » readable at all. But this rule may not hold the token
# (D4), and a literal here would be a selector in a variable whatever it is
# used for. So the page is asked what classes the device carries — through
# `DEVICE`, the naming anchor — and the parser matches the stylesheet's text
# against those. A rename then shows up as a parse that finds nothing, which
# falls the completeness hold loudly rather than quietly widening it.
DEVICE_CLASSES = """(device)=>[...document.querySelector(device).classList]"""

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


def device_spellings(device_classes):
    """Every way this stylesheet can name the device element.

    The parser matched the CLASS alone, so a re-assertion written on the ID —
    `#device [data-part="shell/header"]` — was invisible to it while applying
    perfectly in the browser. And the ID is not an exotic spelling somebody
    would have to invent: it is this rule's own `DEVICE` constant, the anchor
    every reading here goes through.

    Args:
        device_classes: The classes the device element carries, read from the
            document.

    Returns:
        The spellings, longest first so that a compound selector is matched at
        its most specific occurrence rather than at a prefix of it.
    """
    return sorted([DEVICE] + [f".{name}" for name in device_classes],
                  key=len, reverse=True)


def declared_reassertions(device_classes):
    """Every declaration the harness makes on an element inside the device.

    Args:
        device_classes: The classes the device element actually carries, read
            from the document rather than written here (D4).

    The stylesheet is parsed rather than the rendered page, because the
    question is what the frame DECLARES: once the cascade has resolved, a
    declaration that was left behind and one that was never written look
    identical.

    Returns:
        A set of `(anchor, longhand property, scoped)` triples, shorthands
        expanded, covering every rule that names a DESCENDANT of the device —
        whether or not the switch's scope is on it. The device's own blocks
        are excluded: they are the frame itself, held by the geometry, skin
        and survivor holds rather than by `FORCED`.
    """
    text = HARNESS_STYLESHEET.read_text(encoding="utf-8")
    # Comments carry example selectors and whole declaration blocks; parsing
    # them would have the hold refuse the day someone documents a rule.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    declared = set()
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        # PER TARGET, never per BLOCK. `all(SCOPE in one …)` skipped a whole
        # rule whose selector list mixed a scoped target with an unscoped one,
        # so a scoped re-assertion standing beside an unscoped sibling was
        # invisible to this parser — a comma away from being read.
        targets = [one.strip() for one in selectors.split(",")]
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
        # AND UNSCOPED ONES COUNT. This parser read only what the frame
        # SCOPES, so a re-assertion written on a device descendant WITHOUT the
        # scope survived the press unread — and the hold comparing values
        # caught it only if the property was already in the list, which is the
        # dependence this hold exists to remove. Both kinds are collected; the
        # caller refuses an unscoped one the list does not carry.
        inside = []
        for one in targets:
            token = next((spelling for spelling in device_spellings(
                device_classes) if spelling in one), None)
            if token is None:
                continue
            after = one.split(token, 1)[1].strip()
            if not after:
                continue          # the frame's own element, held elsewhere
            inside.append((after, SCOPE in one))
        if not inside:
            continue
        for after, scoped in inside:
            for declaration in body.split(";"):
                if ":" not in declaration:
                    continue
                name = declaration.split(":", 1)[0].strip()
                if not name or name.startswith("-"):
                    continue
                for longhand in LONGHANDS.get(name, (name,)):
                    declared.add((after, longhand, scoped))
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

# EVERY INTERACTIVE THING THE APP DRAWS, and not a list of five. `FIXED_CHROME`
# names the avatar, the header's buttons, the tab bar's buttons, the FAB and the
# add action — and out of the frame at a desktop width the tab bar is
# `display: none`, the header is at the top and the FAB is at the bottom RIGHT,
# so not one of the five can ever be where the control parks. The hold reading
# them was at its most vacuous in the state it was written for: it answered
# « nothing » while the app's « Annuler » sat underneath. That is B-370's
# species — a promise about a CLASS held by a reading of named members — and
# the answer is to ask the class.
INTERACTIVE = ('button, a[href], input, select, textarea, summary, '
               '[role="button"], [role="link"], [role="tab"], [role="menuitem"], '
               '[role="checkbox"], [role="switch"], [contenteditable="true"]')

# The control crossing its OWN label is not a finding, so its own subtree is
# excluded — but every OTHER piece of harness chrome is read beside the app's
# controls, and that is deliberate. Nothing in this harness holds that two
# pieces of its own chrome do not cover each other: B-370 is exactly R51
# reading ONE of them by literal. And this wave's placement depends on it —
# the harness bar sits at the top bar's empty middle while the frame is drawn
# and moves to the top right out of it, which is the whole reason top centre
# is free out there. A comment saying so is not a reading; this is.
HARNESS_CHROME = '[data-part^="harness/"]'

# WHERE THE PAGE ACTUALLY IS, asked of the page rather than assumed from a
# click that happened before the loop. `checked` is the state itself; the
# device filling the window is what that state is FOR, and reading both means
# a press that silently stopped working cannot pass as a corner that is free.
# THE ONE LAYER ALLOWED OVER IT, named by STATE and by COVERER together so
# that a different layer in the same state still falls the hold, and the same
# layer in another state does too.
#
# `startup` draws the boot splash, and a splash is transient by construction:
# it covers the whole window for as long as the application is starting and
# then it is gone. Nothing can be reached under it — that is what it is FOR —
# and the way back into the frame is no more entitled to be reachable during
# the boot than the app's own controls are. The operator meets it for the
# moment the prototype loads and never again in that session.
#
# It is an exemption and not a discovery, so it is written here rather than
# absorbed: the reading that produced it was ONE state out of 87, and the
# other twelve that once appeared beside it were this rule's own settle
# reading the page mid-transition, not layers of the app's.
TRANSIENT_COVERERS = {"startup": ["splash"]}

# THE OTHER DIRECTION, and the sweep asked only one of them. « What does the
# control cover » and « what covers the control » are different questions with
# different answers: a layer the app paints AFTER the control, at the same
# stacking rank, wins on document order and takes the press while every
# crossing count reads zero. The control is the way BACK into the frame — if a
# finger cannot reach it, the operator is stranded in the state that covers it,
# and the keyboard still working is a consolation rather than an answer.
#
# Read at the centre AND the four corners, because a layer that covers half of
# a control leaves it half usable, which is not a state worth shipping either.
WHAT_COVERS_IT = """(argument)=>{
  const [switchSelector, label] = argument;
  const node = document.querySelector(switchSelector);
  if (!node) return ['ABSENT'];
  const a = node.getBoundingClientRect();
  if (!a.width || !a.height) return ['NOT DRAWN'];
  const ours = document.querySelector(label);
  const points = [[a.left + a.width / 2, a.top + a.height / 2],
                  [a.left + 1, a.top + 1], [a.right - 1, a.top + 1],
                  [a.left + 1, a.bottom - 1], [a.right - 1, a.bottom - 1]];
  const strangers = [];
  for (const [x, y] of points) {
    const top = document.elementFromPoint(x, y);
    if (!top) { strangers.push('nothing'); continue; }
    if (node.contains(top) || (ours && ours.contains(top))) continue;
    strangers.push(top.getAttribute('data-part') || top.id
                   || top.className || top.tagName);
  }
  return [...new Set(strangers)];
}"""

OUT_OF_THE_FRAME = """(argument)=>{
  const [checkbox, device] = argument;
  const box = document.querySelector(device).getBoundingClientRect();
  return {checked: document.querySelector(checkbox).checked,
          fillsTheWindow: Math.round(box.width) === window.innerWidth
                          && Math.round(box.height) === window.innerHeight,
          box: [Math.round(box.x), Math.round(box.y),
                Math.round(box.width), Math.round(box.height)]};
}"""

CROSSED = """(argument)=>{
  const [switchSelector, interactive, harness] = argument;
  const node = document.querySelector(switchSelector);
  if (!node) return ['ABSENT'];
  const a = node.getBoundingClientRect();
  if (!a.width || !a.height) return ['NOT DRAWN'];
  const crosses = (b) => !(a.right <= b.left || b.right <= a.left
                           || a.bottom <= b.top || b.bottom <= a.top);
  return [...document.querySelectorAll(interactive + ', ' + harness)]
    .filter((el) => el !== node && !node.contains(el) && !el.contains(node))
    .filter((el) => el.getClientRects().length > 0)
    .filter((el) => crosses(el.getBoundingClientRect()))
    .map((el) => el.getAttribute('data-part') || el.id
                 || (el.textContent || '').trim().slice(0, 24) || el.tagName);
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
DEVICE_SURVIVES = {"position": "relative",
                   "display": "flex",
                   "flex-direction": "column"}

# The rest of what that block declares survives too, and cannot be held by a
# TYPED value because every one of them is relative to the window or to a
# token. They were held by « each must read DIFFERENTLY from the control
# document », and that is not a hold: a WRONG value differs from the control
# just as well as the right one does. `.device{background:red}` left the window
# red out of the frame with every hold green, which is the shape this rule
# exists to refuse, sitting inside the hold written to refuse it.
#
# Each is held to what its own declaration MEANS — and « means » is resolved by
# the browser rather than worked out here. A first version computed the
# meanings by hand (the window's width for `width: 100%`, its height for
# `height: 100svh`) and got `max-width` wrong on the first run: percentages
# stay percentages in a computed reading, so the expected `1280px` met a real
# `100%` and the hold fell on a correct tree. Working out what a declaration
# resolves to is the browser's job, and asking it is one probe element.
DEVICE_SURVIVES_DYNAMIC = ("width", "max-width", "height", "background-color")

# THE PROBE CARRIES THE FRAME'S OWN DECLARATIONS, read from the stylesheet, and
# is mounted in the device's own parent so that a percentage resolves against
# the same containing block. Whatever the browser computes for it is what the
# declaration means; the device must read the same, or the declaration has
# stopped arriving. `background: red` then differs from the token's colour and
# the hold falls, which « differs from the control document » could never see.
WHAT_THE_DECLARATIONS_MEAN = """(argument)=>{
  const [device, declarations, wanted] = argument;
  const el = document.querySelector(device);
  const probe = document.createElement('div');
  for (const [name, value] of Object.entries(declarations))
    probe.style.setProperty(name, value);
  el.parentElement.appendChild(probe);
  const style = getComputedStyle(probe);
  const out = {};
  for (const property of wanted) out[property] = style.getPropertyValue(property);
  probe.remove();
  return out;
}"""


def frame_own_declarations(device_classes):
    """The frame's own block as `name: value`, read from the stylesheet.

    Args:
        device_classes: The classes the device element carries.

    Returns:
        A mapping of declared property to declared value, verbatim, so that a
        probe can be given the same declarations and the browser can say what
        they resolve to.
    """
    text = HARNESS_STYLESHEET.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    spellings = set(device_spellings(device_classes))
    declarations = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        targets = [one.strip() for one in selectors.split(",")]
        if len(targets) != 1 or targets[0] not in spellings:
            continue
        for declaration in body.split(";"):
            if ":" not in declaration:
                continue
            name, _, value = declaration.partition(":")
            if name.strip() and not name.strip().startswith("-"):
                declarations[name.strip()] = value.strip()
    return declarations


def declared_by_the_frame_itself(device_classes):
    """Every property the device's own unscoped block declares.

    Args:
        device_classes: The classes the device element carries, read from the
            document (D4 — see `DEVICE_CLASSES`).

    The block's own comment said « the rule holds each of these three by name »
    while `DEVICE_SURVIVES` had ONE key, and the hold's « a fourth one
    appearing here is the defect » could not be read: the block declares seven,
    and `max-width`, `background`, `display` and `flex-direction` were covered
    by nothing at all — `.device{background:red}` left every hold green and the
    window red out of the frame.

    Returns:
        The set of longhand property names the block declares, read from the
        file so that a declaration added to it has to be answered here.
    """
    text = HARNESS_STYLESHEET.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    names = set()
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        targets = [one.strip() for one in selectors.split(",")]
        if len(targets) != 1 or targets[0] not in set(
                device_spellings(device_classes)):
            continue
        for declaration in body.split(";"):
            if ":" not in declaration:
                continue
            name = declaration.split(":", 1)[0].strip()
            if not name or name.startswith("-"):
                continue
            names.update(SHORTHAND_ON_THE_DEVICE.get(name, (name,)))
    return names


# `background` resolves to `background-color` in a computed reading, and the
# hold compares computed readings.
SHORTHAND_ON_THE_DEVICE = {"background": ("background-color",)}

DEVICE_BOX = """(argument)=>{
  const [device, skin, survives, dynamic] = argument;
  const el = document.querySelector(device);
  const box = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  const out = {rect: [Math.round(box.x), Math.round(box.y),
                      Math.round(box.width), Math.round(box.height)]};
  for (const property of skin) out[property] = style.getPropertyValue(property);
  for (const property of survives)
    out['survives:' + property] = style.getPropertyValue(property);
  for (const property of dynamic)
    out['dynamic:' + property] = style.getPropertyValue(property);
  return out;
}"""

# The same removal the FORCED control document uses, on the device itself: the
# frame's whole contribution is written `.device …`, so the element with that
# class off is what the app's cascade alone says about it.
UNFRAMED_DEVICE = """(argument)=>{
  const [device, skin, dynamic] = argument;
  const el = document.querySelector(device);
  el.classList.remove('device');
  const style = getComputedStyle(el);
  const out = {};
  for (const property of skin) out[property] = style.getPropertyValue(property);
  for (const property of dynamic)
    out['dynamic:' + property] = style.getPropertyValue(property);
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
# THE ABSENT CONTROL READS ZEROS, AND ZEROS PASS. `getBoundingClientRect` on a
# `display: none` element is all zeros, so `frameLeft - 0` is a comfortable
# positive gap and the hold that exists to catch an overlap was green over a
# control that was not drawn at all. 520px is the ONLY width where the
# control's PRESENCE can be read — 390 requires it absent and at 1280 the
# gutter is 332px — so the breakpoint regressing to 700px would leave all
# nineteen holds green and the operator with no way out of the frame at 640.
# The reading says which case it is instead of collapsing them.
GEOMETRY = """(argument)=>{
  const [switchSelector, device] = argument;
  const node = document.querySelector(switchSelector);
  const box = node.getBoundingClientRect();
  const frame = document.querySelector(device).getBoundingClientRect();
  const input = document.querySelector('#desktop-switch');
  input.focus();
  const focused = document.activeElement === input;
  input.blur();
  return {drawn: node.getClientRects().length > 0 && box.width > 0
                 && box.height > 0,
          rects: node.getClientRects().length,
          area: Math.round(box.width * box.height),
          focusable: focused,
          labelRight: Math.round(box.right),
          frameLeft: Math.round(frame.left),
          gap: Math.round(frame.left - box.right)};
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
    device_classes = await page.evaluate(DEVICE_CLASSES, DEVICE)
    declared = declared_reassertions(device_classes)
    read = {(selector, property_name) for selector, property_name in FORCED}
    unread = sorted((anchor, name) for anchor, name, _ in declared
                    if (anchor, name) not in read)
    # AN UNSCOPED RE-ASSERTION IS A DEFECT IN ITSELF, not merely something to
    # read. Scoped, a declaration leaves with the frame and the value hold
    # sees it go. Unscoped, it survives the press — and it survives it
    # SILENTLY unless this list already happened to carry the property, which
    # is exactly the dependence this hold exists to remove.
    unscoped = sorted((anchor, name) for anchor, name, scoped in declared
                      if not scoped)
    journal.check(
        "every declaration on an element inside the device is one this rule "
        "reads AND one the frame takes back, and the STYLESHEET is what says "
        "how many there are",
        not unread and not unscoped,
        f"{len(declared)} declared in {HARNESS_STYLESHEET.name}, "
        f"{len(FORCED)} read — unread: {unread or 'none'}; declared on a "
        f"device descendant WITHOUT the switch's scope, so it would survive "
        f"the press: {unscoped or 'none'}. The list is not trusted to be "
        f"complete: it is compared against the file, so a declaration added "
        f"there without a reading here falls this hold")

    framed_box = await page.evaluate(
        DEVICE_BOX, [DEVICE, DEVICE_SKIN, list(DEVICE_SURVIVES),
                     list(DEVICE_SURVIVES_DYNAMIC)])
    unframed_box = await page.evaluate(UNFRAMED_DEVICE, [DEVICE, DEVICE_SKIN,
                          list(DEVICE_SURVIVES_DYNAMIC)])
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
        DEVICE_BOX, [DEVICE, DEVICE_SKIN, list(DEVICE_SURVIVES),
                     list(DEVICE_SURVIVES_DYNAMIC)])
    height = DESKTOP["viewport"]["height"]
    journal.check(
        "one press and the device is the window, not a phone drawn inside it "
        "— the whole box, not its width alone",
        left_box["rect"] == [0, 0, width, height],
        f"at {width}px — the device box is {left_box['rect']}, against the "
        f"window's [0, 0, {width}, {height}]")

    # BOTH SIDES RESTRICTED TO THE SKIN'S OWN KEYS. The control document is
    # asked for the window-relative survivors too, so comparing the whole
    # dictionaries compared a four-key reading with an eight-key one and fell
    # over a difference that was entirely the question's shape.
    skin_left = {k: left_box[k] for k in DEVICE_SKIN}
    skin_control = {k: unframed_box[k] for k in DEVICE_SKIN}
    journal.check(
        "and the frame's SKIN went with its dimensions — no border, no "
        "radius, no shadow, nothing clipped, on a device the app alone draws",
        skin_left == skin_control,
        f"at {width}px — read {skin_left}, and a document with no frame reads "
        f"{skin_control}")

    stayed = {k: left_box["survives:" + k] for k in DEVICE_SURVIVES}
    dynamic_left = {k: left_box["dynamic:" + k]
                    for k in DEVICE_SURVIVES_DYNAMIC}
    dynamic_control = {k: unframed_box["dynamic:" + k]
                       for k in DEVICE_SURVIVES_DYNAMIC}
    meant = await page.evaluate(
        WHAT_THE_DECLARATIONS_MEAN,
        [DEVICE, frame_own_declarations(device_classes),
         list(DEVICE_SURVIVES_DYNAMIC)])
    still_arriving = [k for k in DEVICE_SURVIVES_DYNAMIC
                      if dynamic_left[k] == meant[k]]
    declared_own = declared_by_the_frame_itself(device_classes)
    held_own = set(DEVICE_SURVIVES) | set(DEVICE_SURVIVES_DYNAMIC)
    journal.check(
        "and what the harness keeps out of the frame is what it SAYS it "
        "keeps — every declaration of its own block, and nothing besides",
        stayed == DEVICE_SURVIVES
        and len(still_arriving) == len(DEVICE_SURVIVES_DYNAMIC)
        and declared_own == held_own,
        f"at {width}px — the block declares {sorted(declared_own)} and this "
        f"rule holds {sorted(held_own)}; the static ones read {stayed} "
        f"against {DEVICE_SURVIVES}; the window-relative ones read "
        f"{dynamic_left} against what their own declarations mean here, "
        f"{meant} (a frameless document reads {dynamic_control}, which is a "
        f"different question and was the wrong one). Still arriving: "
        f"{sorted(still_arriving)}. An eighth declaration appearing "
        f"in that block, or one of these quietly ceasing to arrive, is the "
        f"defect this reads")

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
        DEVICE_BOX, [DEVICE, DEVICE_SKIN, list(DEVICE_SURVIVES),
                     list(DEVICE_SURVIVES_DYNAMIC)])
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
    # PRESENCE FIRST, and it is not a formality. Every other hold in this rule
    # requires the control to be ABSENT (at 390) or reads it where the gutter
    # is 332px wide (at 1280). This is the only width at which « the control
    # is drawn » is a question, so if it is not asked here it is asked
    # nowhere, and a breakpoint moved to 700px would leave the whole rule
    # green over an operator with no way out of the frame at 640.
    journal.check(
        "the way out of the frame IS drawn at the tightest width the frame is "
        "drawn at — the frame's own breakpoint, where the two must agree",
        reading["drawn"] and reading["focusable"],
        f"at {width}px — client rects {reading['rects']}, area "
        f"{reading['area']}, takes focus {reading['focusable']}. The frame "
        f"appears at this width and the way out of it must appear with it")

    journal.check(
        "and at that width it does not sit on the prototype",
        reading["drawn"] and reading["gap"] >= 0,
        f"at {width}px — the label's right edge is at "
        f"{reading['labelRight']}, the frame's left edge at "
        f"{reading['frameLeft']}, gap {reading['gap']}px. It ABUTS by "
        f"arithmetic (`16px + (50% - 211px)` = `50% - 195px`) and must never "
        f"cross; the stylesheet's comment claimed 16px of clearance for a "
        f"while and the true figure is 0")
    await context.close()


# THE SETTLE IS THE DRAWN DURATION, not a number that felt long enough. The
# walk waited 120 ms while the prototype's longest transition is 450 ms
# (`--duration-4`), so sixteen states were read mid-transition: their topmost
# element at the control's own centre came back as `HTML` — nothing hit-testable
# there yet — and the hold that asks « what covers the way back » was about to
# report fifteen coverers that do not exist. A delay set by hand in an
# instrument outliving the drawn duration it was set against is this
# register's B-276, and it produced a reading, not just a risk.
#
# BUT A NUMBER IS STILL A NUMBER. 470 cleared eleven of the sixteen and left
# five, four of them media sheets that animate for longer than the constant
# anyone would have written down — which is B-276 again, one raise later. So
# the wait is not a duration at all: the page is asked whether anything is
# still animating, and the reading is taken when nothing is. The ceiling below
# is a refusal to hang, not an expectation.
SETTLE_FLOOR = 120
SETTLE_CEILING = 3000
NOTHING_IS_MOVING = """()=>document.getAnimations()
  .every((one)=>one.playState !== 'running')"""


async def measure_every_state(browser, journal):
    """Holds that the way out of the frame covers no control the app draws.

    OUT of the frame there is no gutter: the device is the window and the
    control is parked in a corner of the app itself. Whether that corner is
    free is not a property of the corner — it is a property of what is on
    screen, which is what a NAMED STATE changes. So the question is asked at
    every one of them rather than at whichever screen the prototype happens to
    boot on, and it is asked of every interactive element rather than of five
    named ones.

    Args:
        browser: A launched Playwright browser.
        journal: The run's journal.
    """
    context, page = await open_page(browser, **DESKTOP)
    width = DESKTOP["viewport"]["width"]
    await page.click(LABEL)                      # out of the frame, and stay there
    await page.wait_for_timeout(200)
    states = await page.evaluate("()=>window.__states()")
    crossed = {}
    # NOT OUT OF THE FRAME IS NOT A PASS. This walk counts what the control
    # covers, and framed it covers nothing at all — the control is in the
    # frame's gutter and the app is a 390px phone in the middle of the page —
    # so a sweep that never checked WHERE it was reported zero crossings over
    # a page that had not left the frame, and the reading would have been the
    # same if the press had silently stopped working. A named state can also
    # re-render the shell, so the question is asked at EVERY state rather than
    # once before the loop.
    not_out = {}
    covered = {}
    still_moving = []
    for state in states:
        await page.evaluate("(one)=>window.__go(one)", state)
        # THE FLOOR FIRST, THEN THE QUESTION, and the order is the whole of
        # it: asked immediately, « is anything animating? » answers YES —
        # nothing has started yet — so waiting on that alone read the page
        # EARLIER than the fixed delay did and the count went up rather than
        # down. The floor lets the transition begin; the question then waits
        # out whatever its real duration is, which no constant here can know.
        await page.wait_for_timeout(SETTLE_FLOOR)
        try:
            await page.wait_for_function(NOTHING_IS_MOVING,
                                         timeout=SETTLE_CEILING)
        except PlaywrightTimeoutError:
            still_moving.append(state)
        where = await page.evaluate(OUT_OF_THE_FRAME, [CHECKBOX, DEVICE])
        if not (where["checked"] and where["fillsTheWindow"]):
            not_out[state] = where
            continue
        hits = await page.evaluate(
            CROSSED, [SWITCH, INTERACTIVE, HARNESS_CHROME])
        if hits:
            crossed[state] = hits
        over = await page.evaluate(WHAT_COVERS_IT, [SWITCH, LABEL])
        if over and over != TRANSIENT_COVERERS.get(state):
            covered[state] = over
    journal.check(
        "and every one of those readings was taken OUT of the frame — the "
        "checkbox checked and the device filling the window, in each state",
        not not_out,
        f"at {width}px — {len(states) - len(not_out)} of {len(states)} state(s) "
        f"were read out of the frame; the rest were not and their crossings "
        f"mean nothing: {dict(list(not_out.items())[:4])}")

    journal.check(
        "and nothing of the app's covers the way BACK — the control answers "
        "the finger at its centre and its four corners, in every state but "
        "the boot, whose splash is named and transient",
        not covered,
        f"at {width}px, out of the frame — {len(covered)} of {len(states)} "
        f"state(s) put something over it: "
        f"{dict(list(covered.items())[:6])}"
        f"{' …' if len(covered) > 6 else ''}. The control is the way BACK into "
        f"the frame: a layer that takes its press strands the operator in the "
        f"state that draws it, and a keyboard that still reaches it is a "
        f"consolation rather than an answer"
        + (f". Still animating after {SETTLE_CEILING}ms and read anyway: "
           f"{still_moving}" if still_moving else ""))
    journal.check(
        "out of the frame the way back covers no control the app draws NOR "
        "any other piece of harness chrome, in ANY named state — the class, "
        "not five members of it",
        not crossed,
        f"at {width}px, out of the frame, over {len(states)} named state(s) — "
        f"{len(crossed)} cross something interactive: "
        f"{dict(list(crossed.items())[:6])}"
        f"{' …' if len(crossed) > 6 else ''}. Out of the frame the device is "
        f"the window, so the control is parked in a corner of the APP; "
        f"whether that corner is free is a property of what is on screen, "
        f"which is what a named state changes")
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
        await measure_every_state(browser, journal)
        await browser.close()
    journal.summary()


def main():
    """Runs the rule."""
    journal = Journal(
        "R140 — the way out of the phone frame is a desktop's alone, and total")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
