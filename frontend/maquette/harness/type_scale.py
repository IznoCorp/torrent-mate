"""R83 — the browser holds the type scale, and the fields reach 16 px.

Two things a static reading of the stylesheet cannot say.

THE FIELDS. Safari auto-zooms a focused input whose computed size is under
16 px, and the zoom is not undone when the field is left: the page stays
magnified and the operator pinches it back by hand. Removing
`maximum-scale=1, user-scalable=no` was right — those directives forbade the
pinch a low-vision reader depends on — and it made the auto-zoom visible. The
repair is the field's size. A grep proves the declaration names a token; only
the browser proves what the token resolves to under the cascade, and a later
rule overriding the size is exactly the shape a grep reads as green.

THE STEPS. The scale is worth naming only if every rendered size is on it. The
static arm counts LITERALS in the design's sources, so a size that never
appears as a literal there is invisible to it: one set from script, one written
into a React inline style, one composed from a variable. This reads what the
document actually renders, over every named state, and it found its first
defect the day it was written — a half-pixel size in an inline style, on a
paragraph six states draw, that the source-level fold could not have seen.

An element whose size is INHERITED is not a violation of its own: it resolves
to an ancestor's declared size, and naming it would name the wrong element. So
only an element whose own rendered size differs from its parent's is judged,
and the step set is READ FROM THE DOCUMENT — a rule carrying its own pixel list
measures the scale as it was on the day the list was typed.
"""
import asyncio
import json

from common import ROOT, Journal, open_page
from playwright.async_api import async_playwright

# The form fields, each with the sentence a refusal has to be able to speak.
#
# NOT ANCHORED ON THE CLASSES THAT STYLE THEM. A class is a style decision and
# the utility conversion takes it away, so a rule holding `.search input` dies
# with the stylesheet and cannot then say whether the anchor or the size was at
# fault. The first entry is a TYPE of element rather than a name at all: iOS
# magnifies any focused text field, so what the floor is about is every field
# that accepts text — which is also why it is written as a net and not as a list
# of ids. It covers seven fields where the class covered five, the two extra
# being the sign-in screen's.
#
# The settings field is anchored on the `data-part` the markup gives it, and its
# path variant on the boolean state attribute beside it — a monospace face is
# the one that would be taken back down first when a path overflows, so it is
# held apart from the family it belongs to.
FIELDS = (
    ('input:not([type="checkbox"]):not([type="radio"]), textarea',
     "a text field"),
    ('[data-part="field/input"]', "a settings field"),
    ('[data-part="field/input"][data-mono]', "a settings field carrying a path"),
)

# Below this, a focused field is magnified by Safari and the page stays
# magnified afterwards.
FLOOR_PX = 16.0

# An element painting a box thinner than this in either direction shows no
# glyph at any size — the visually-hidden pattern clips its heading to a single
# pixel. Its font-size is a fact about nothing anybody reads, so it is not
# judged against a scale of READING sizes.
PAINTED_PX = 2.0

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def region_selectors():
    """Returns the selector of every region the maquette declares.

    Returns:
        The list of CSS selectors, in declaration order, without the table's
        documentation keys.

    Raises:
        SystemExit: If the table is empty. A sweep over no region visits no
            element and reports success — the one outcome this rule must never
            be able to produce.
    """
    record = json.loads((ROOT / "regions.json").read_text(encoding="utf-8"))
    selectors = [value["selector"]
                 for key, value in record.get("regions", {}).items()
                 if not key.startswith("$")]
    if not selectors:
        raise SystemExit(
            f"{ROOT / 'regions.json'} declares no region: this rule would "
            "sweep nothing and exit 0.")
    return selectors


# Every `--text-*` property the document DECLARES, resolved to the pixels it
# renders as. The names come off the stylesheets rather than from a list here,
# so a step added or renamed joins the rule on the day it is written.
READ_STEPS = """() => {
  const names = new Set();
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch (e) { continue; }
    for (const rule of rules) {
      if (!rule.style) continue;
      for (const property of rule.style)
        if (property.startsWith('--text-')) names.add(property);
    }
  }
  const root = getComputedStyle(document.documentElement);
  const steps = {};
  for (const name of [...names].sort())
    steps[name] = parseFloat(root.getPropertyValue(name));
  return steps;
}"""

# The field's rendered size, in the state currently on screen. The SMALLEST
# painted instance answers, never the first: the anchor is a net, and a net
# whose first member clears the floor says nothing about the rest of it.
READ_FIELD = """(selector) => {
  let smallest = null;
  for (const element of document.querySelectorAll(selector)) {
    const box = element.getBoundingClientRect();
    if (box.width < 1 || box.height < 1) continue;
    const size = Math.round(
      parseFloat(getComputedStyle(element).fontSize) * 10) / 10;
    if (smallest === null || size < smallest) smallest = size;
  }
  return smallest;
}"""

# Every painted element inside the measured regions whose OWN rendered size is
# on no step. `seen` is per state and not per region: the regions nest, and an
# element reported once per enclosing region would report the same defect four
# times over.
SWEEP = """([selectors, steps]) => {
  const onStep = (size) => steps.some((step) => Math.abs(step - size) < 0.05);
  const rounded = (element) =>
    Math.round(parseFloat(getComputedStyle(element).fontSize) * 10) / 10;
  const seen = new Set();
  const off = [];
  for (const selector of selectors) {
    for (const region of document.querySelectorAll(selector)) {
      for (const element of region.querySelectorAll('*')) {
        if (seen.has(element)) continue;
        seen.add(element);
        const box = element.getBoundingClientRect();
        if (box.width < PAINTED || box.height < PAINTED) continue;
        const size = rounded(element);
        if (onStep(size)) continue;
        const parent = element.parentElement;
        // An inherited size is the ancestor's declaration, and the ancestor is
        // judged on its own line. Only a size the element itself introduces is
        // a defect here.
        if (parent && Math.abs(rounded(parent) - size) < 0.05) continue;
        // The locator names the element the way the markup does — its part,
        // its id — and never by the classes it is styled with: a refusal
        // pointing at a class would send the reader to a stylesheet that is on
        // its way out, and this rule must outlive it.
        const part = element.getAttribute('data-part');
        const id = element.id;
        // An element carrying neither — a bare `p` given a size in an inline
        // style — is unfindable by its own name, so the nearest named ancestor
        // is reported with it, and a few words of what it says.
        const named = element.parentElement
          && element.parentElement.closest('[data-part]');
        const words = (element.textContent || '').replace(/\\s+/g, ' ').trim();
        off.push({
          at: element.tagName.toLowerCase()
              + (id ? `#${id}` : '')
              + (part ? `[data-part="${part}"]` : '')
              + (!part && !id && named
                 ? ` under [data-part="${named.getAttribute('data-part')}"]` : '')
              + (!part && !id && words ? ` («\u00a0${words.slice(0, 28)}\u00a0»)` : ''),
          size: size,
        });
      }
    }
  }
  return off;
}""".replace("PAINTED", str(PAINTED_PX))


async def main():
    global _journal
    _journal = Journal("R83 — the type scale, as the browser renders it")

    selectors = region_selectors()

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(browser)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        steps = await pg.evaluate(READ_STEPS)
        # A step set read as empty would put every size on no step and a step
        # set read as « everything » would put every size on one. Both are the
        # rule measuring its own reading rather than the document, so the
        # reading is held before anything is judged against it.
        check("the type scale is declared by the document",
              len(steps) >= 2 and all(size > 0 for size in steps.values()),
              " · ".join(f"{name}={size:g}px" for name, size in steps.items()))
        sizes = sorted(steps.values())

        states = await pg.evaluate("()=>window.__states()")
        check("the named states are enumerable", len(states) > 1, f"{len(states)} states")

        under = {selector: [] for selector, _ in FIELDS}
        measured = {selector: [] for selector, _ in FIELDS}
        off_step = []
        for state in states:
            await pg.evaluate("(i)=>window.__go(i)", state)
            await pg.wait_for_timeout(200)

            for selector, _ in FIELDS:
                size = await pg.evaluate(READ_FIELD, selector)
                if size is None:
                    continue
                measured[selector].append(size)
                if size < FLOOR_PX:
                    under[selector].append(f"{state} at {size:g}px")

            for hit in await pg.evaluate(SWEEP, [selectors, sizes]):
                off_step.append(f"{state}: {hit['at']} at {hit['size']:g}px")

        for selector, what in FIELDS:
            seen = measured[selector]
            # A field no state draws is a field this rule never measured, and a
            # hold that measured nothing must not read as a hold that passed.
            check(f"{what} is drawn by a named state", bool(seen),
                  f"`{selector}` painted in {len(seen)} state(s)")
            # The detail says what was MEASURED when the hold stands and what
            # the refusal is when it falls. A green line printing the refusal's
            # own sentence reads as a failure to anyone scanning the log.
            check(f"{what} renders at least {FLOOR_PX:g}px",
                  not under[selector],
                  f"`{selector}` renders under the {FLOOR_PX:g}px at which a "
                  f"focused field zooms iOS — {' · '.join(under[selector][:6])}"
                  if under[selector]
                  else f"`{selector}` from {min(seen, default=0):g}px")

        check(f"every rendered size in the measured regions is a step "
              f"({len(states)} states)",
              not off_step,
              f"{len(off_step)} element(s) carry a rendered size that is on no "
              f"step of the type scale — {' · '.join(off_step[:6])}"
              if off_step
              else f"{len(selectors)} regions, {len(sizes)} steps")

        await browser.close()

    _journal.summary(errors)

asyncio.run(main())
