"""R-menu — the maquette's two controls live in the side menu, nothing floats over the page.

THE DEFECT (B-681). The prototype's own controls — the design notes and the
real/dense world switch — sat in a floating bar over the page, and the operator
read it covering the maquette's own information, « souvent ». They are now
entries of the side menu, in a group of their own at its end, contributed by
the harness module (which only the maquette loads) and never written into the
product's drawer.

WHAT THIS RULE HOLDS, at 390 px and at desktop width:

1. NOTHING OF THE MAQUETTE'S CONTROLS IS DRAWN OVER THE PAGE. Every element
   that carries one of the controls' ids, or the old bar's name or class, is
   inside `#drawer`; none is left outside it, and none is laid out inside the
   viewport while the menu is closed (on a phone the closed menu is off screen;
   on a desktop the menu is the pinned rail, so the second half of this hold
   reads the first only).
2. BOTH ENTRIES ARE IN THE OPEN MENU, together, in one group, after every one of
   the product's own entries.
3. THEY WORK: the notes entry toggles `notes` on `<html>` and its own
   `aria-pressed`; the world entry flips `scen` and its own label.

THE SUBJECT IS THE DOCUMENT AS SERVED, read through `getBoundingClientRect` and
`closest`, so a rule written another way — a utility, an inline style — passes
as long as the controls are really in the menu.
"""
import asyncio

from common import Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

# Both sides of the 520px breakpoint: a phone's drawer slides in over the page,
# a desktop's is the pinned rail.
WIDTHS = [390, 1280]

# A control that cannot be tapped is a finding, not a hang: the old bar sat under
# the open menu, and a 30 s default made that read as a crash.
CLICK_MS = 5000

NOTES = "#notesBtn"
WORLD = "#scenarioBtn"

# Every handle the controls have ever had: their ids, the old bar's part name,
# and its class. The bar is gone, so the last two must find nothing.
READ_PLACES = """() => {
  const found = [...document.querySelectorAll(
    '#notesBtn, #scenarioBtn, [data-part="harness/bar"], .hbtn')];
  const viewport = {width: innerWidth, height: innerHeight};
  return found.map((el) => {
    const box = el.getBoundingClientRect();
    const inView = box.width > 0 && box.height > 0
      && box.right > 0 && box.bottom > 0
      && box.left < viewport.width && box.top < viewport.height;
    return {
      name: el.id || el.getAttribute('data-part') || el.className,
      inDrawer: !!el.closest('#drawer'),
      inView,
    };
  });
}"""

READ_MENU = """() => {
  const drawer = document.querySelector('#drawer');
  const notes = document.querySelector('#notesBtn');
  const world = document.querySelector('#scenarioBtn');
  if (!drawer || !notes || !world || !drawer.contains(notes) || !drawer.contains(world))
    return {found: false};
  const group = notes.closest('[data-part="harness/menu"]');
  const entries = [...drawer.querySelectorAll('[data-navgo]')];
  const after = (el) => entries.every((entry) =>
    !!(entry.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING));
  const visible = (el) => {
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  };
  return {
    found: true,
    sameGroup: !!group && group === world.closest('[data-part="harness/menu"]'),
    afterProduct: entries.length > 0 && after(notes) && after(world),
    visible: visible(notes) && visible(world),
    notesPressed: notes.getAttribute('aria-pressed'),
    notesClass: document.documentElement.classList.contains('notes'),
    worldPressed: world.getAttribute('aria-pressed'),
    worldLabel: (world.textContent.trim() || world.getAttribute('aria-label') || ''),
    scen: window.__store.read().state.scen,
  };
}"""


async def main():
    """Runs the rule at both widths.

    Returns:
        Nothing; the journal exits non-zero on any violation.
    """
    journal = Journal("R-menu — the maquette's controls live in the side menu")
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for width in WIDTHS:
            at = f"@{width}px"
            context, page = await open_page(
                browser,
                viewport={"width": width, "height": 844},
                is_mobile=width < 520,
                has_touch=width < 520,
            )
            page.on("pageerror", lambda error: errors.append(str(error)))

            # 1. NOTHING IS OVER THE PAGE, the menu closed.
            places = await page.evaluate(READ_PLACES)
            outside = [one["name"] for one in places if not one["inDrawer"]]
            journal.check(f"{at} no control of the maquette is outside the side menu",
                          not outside, str(outside) if outside else f"{len(places)} found, all in it")
            journal.check(f"{at} the old bar is gone",
                          not any(one["name"] in ("harness/bar", "hbtn") for one in places), str(places))
            if width < 520:
                shown = [one["name"] for one in places if one["inView"]]
                journal.check(f"{at} none is on screen while the menu is closed",
                              not shown, str(shown))

            # 2. BOTH ARE IN THE OPEN MENU.
            menu = await read_at(page, "drawer-navigation", READ_MENU)
            journal.check(f"{at} both entries are in the open menu", menu["found"], str(menu))
            if menu["found"]:
                journal.check(f"{at} they sit together in one group of their own",
                              menu["sameGroup"], str(menu))
                journal.check(f"{at} the group comes after every product entry",
                              menu["afterProduct"], str(menu))
                journal.check(f"{at} both are laid out", menu["visible"], str(menu))

                # 3. THEY WORK. A state wait on the entry's own attribute,
                #    never a fixed number.
                notes_before = menu["notesPressed"]
                await page.locator(NOTES).click(timeout=CLICK_MS)
                await page.wait_for_function(
                    "(was)=>document.querySelector('#notesBtn').getAttribute('aria-pressed')!==was",
                    arg=notes_before)
                pressed = await page.evaluate(READ_MENU)
                journal.check(f"{at} the notes entry toggles the notes",
                              pressed["notesPressed"] == "true" and pressed["notesClass"], str(pressed))
                await page.locator(NOTES).click(timeout=CLICK_MS)
                await page.wait_for_function(
                    "()=>document.querySelector('#notesBtn').getAttribute('aria-pressed')==='false'")
                released = await page.evaluate(READ_MENU)
                journal.check(f"{at} and releases them",
                              released["notesPressed"] == "false" and not released["notesClass"], str(released))

                label_before, scen_before = menu["worldLabel"], menu["scen"]
                await page.locator(WORLD).click(timeout=CLICK_MS)
                await page.wait_for_function(
                    "(was)=>window.__store.read().state.scen!==was", arg=scen_before)
                await page.wait_for_function(
                    "(was)=>(()=>{const w=document.querySelector('#scenarioBtn');return (w.textContent.trim()||w.getAttribute('aria-label'))!==was;})()",
                    arg=label_before)
                switched = await page.evaluate(READ_MENU)
                journal.check(f"{at} the world entry flips the world and its own label",
                              switched["scen"] != scen_before and switched["worldLabel"] != label_before,
                              f"{scen_before} → {switched['scen']}, « {label_before} » → « {switched['worldLabel']} »")
            await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
