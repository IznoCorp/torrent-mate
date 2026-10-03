"""R480 — the desktop shell: the menu pinned beside a reading column (desktop milestone, phase 1).

The operator, 2026-10-01 — DECIDED 1 = C: « a reading column ≈ 760 px (dialogs ≈ 480 px); galleries and
the deck full width »; DECIDED 2 = B with his word: « B, le même menu latéral, épinglé ouvert par défaut,
avec possibilité de le "fermé" version réduite (barre verticale avec icones seulement) ».
`docs/features/maquette-desktop/DESIGN.md` § 3.

WHAT IS READ, out of the harness's phone frame, with a pointer and no touch:

  1. at 1280 over EVERY named state, and at 1024 and 1440 over a subset: the drawer is pinned at the
     window's left, at the open width, the burger gone, the header and the page beside it — never under
     it; a page without a gallery or the deck is no wider than the column, an open screen's content no
     wider than the column, an open confirmation no wider than its card;
  2. the pinned menu is chrome: reachable beside a screen, background under a sheet;
  3. every page the menu lists is ONE click away, the menu open and the menu folded;
  4. the fold: the toggle draws the icon bar, its words still the entries' names, the choice kept on
     this device across a reload, and unfolding gives the open width back;
  5. the phone is untouched: at 390 the drawer is a closed layer behind the burger and the page fills
     the port; inside the frame at 1280 the same.

The lot's reader, N-bis (2026-10-01), red on `edd817f08`:

  6. from a Réglages rubric or a Maintenance topic ENTERED BY A POINTER CLICK, a click on the pinned
     menu lands on the page clicked, in the same document (no reload), and Retour gives the rubric's page
     back; with an edit waiting it asks first, the three-choice confirmation over Réglages;
  7. at 1280 × 800 and 1024 × 768 every entry of the pinned menu is visible without scrolling it, open
     and folded.
"""
import asyncio

import json
import pathlib

from common import (ACTED, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal, browser_channel, chrome_launch_args,
                    open_page, read_at)
from playwright.async_api import async_playwright

COLUMN = 760
DIALOG = 480
RAIL_OPEN = 288
RAIL_FOLDED = 72
SETTLE = 320
WIDTHS_SAMPLED = (1024, 1440)
SAMPLE = ("acq-follows-list", "acq-now-loaded", "acq-todo-loaded", "lib-grid", "lib-list", "lib-film-panel",
          "lib-delete", "mediasheet-series", "discover-full", "discover-deck", "trackers-page",
          "trackers-roster", "system", "run-detail-log", "maintenance", "settings-topic", "ranking-editor",
          "accounts-roster", "screen-releases", "acq-resolution-tie")
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


READ = """([column, dialog]) => {
  const box = (el) => el ? el.getBoundingClientRect() : null;
  const drawer = document.querySelector('#drawer'), header = document.querySelector('[data-part="shell/header"]');
  const burger = document.querySelector('[data-part="shell/header"] [data-drawer]');
  const view = document.querySelector('#view'), port = document.querySelector('#port');
  const screen = [...document.querySelectorAll('[data-part="screen"][data-open]')].pop();
  const dlg = document.querySelector('#dlg[data-open]'), sheet = document.querySelector('#sheet[data-open]');
  const d = box(drawer), seen = getComputedStyle(drawer);
  const out = [];
  if (!(Math.round(d.left) === 0 && seen.visibility === 'visible')) out.push(`drawer not pinned at the left (${Math.round(d.left)}, ${seen.visibility})`);
  if (burger && burger.getBoundingClientRect().width > 0) out.push('the burger is drawn');
  if (box(header).left < d.right - 1) out.push(`the header under the menu (${Math.round(box(header).left)} < ${Math.round(d.right)})`);
  if (box(port).left < d.right - 1) out.push(`the page under the menu (${Math.round(box(port).left)} < ${Math.round(d.right)})`);
  if (screen) {
    if (box(screen).left < d.right - 1) out.push('a screen over the menu');
    const port2 = screen.querySelector('.port');
    for (const child of port2 ? port2.children : []) {
      if (child.getBoundingClientRect().width > column + 1) { out.push(`screen content ${Math.round(child.getBoundingClientRect().width)} > ${column}`); break; }
    }
  } else if (!view.querySelector('.gallery, .deck') && box(view).width > column + 1) {
    out.push(`the page ${Math.round(box(view).width)} > ${column}`);
  }
  if (dlg && box(dlg).width > dialog + 1) out.push(`the confirmation ${Math.round(box(dlg).width)} > ${dialog}`);
  const inert = drawer.hasAttribute('inert');
  if ((dlg || sheet) && !inert) out.push('the menu reachable under a scrim');
  if (!(dlg || sheet) && inert) out.push('the menu inert with no scrim over it');
  return {out, rail: Math.round(d.width)};
}"""

TOGGLE = "() => document.querySelector('[data-part=\"shell/rail-toggle\"]')?.click()"
ENTRIES = "() => [...document.querySelectorAll('#drawer [data-navgo]:not([data-reserved])')].map((one) => one.dataset.navgo)"


async def walk(page, states, width, journal):
    """Reads every state in STATES at WIDTH and holds hold 1 and 2."""
    bad = []
    for state in states:
        await page.evaluate("(id) => window.__go(id)", state)
        await page.wait_for_timeout(SETTLE)
        seen = await page.evaluate(READ, [COLUMN, 480])
        if seen["out"] or seen["rail"] != RAIL_OPEN:
            bad.append(f"{state} rail={seen['rail']} {seen['out']}")
    journal.check(f"{width}: the menu pinned, the content beside it and in the column ({len(states)} states)",
                  bad == [], "\n      ".join(bad[:15]))


async def one_click(page, journal, label):
    """Every page the menu lists is one click away — no burger, no scrim."""
    await read_at(page, "acq-follows-list", "() => true")
    entries = await page.evaluate(ENTRIES)
    missed = []
    for entry in entries:
        await page.evaluate("(go) => document.querySelector(`#drawer [data-navgo=\"${go}\"]`).click()", entry)
        await page.wait_for_timeout(SETTLED)
        landed = await page.evaluate("() => state.page")
        if landed != entry:
            missed.append(f"{entry} → {landed}")
    journal.check(f"{label}: every page the menu lists is one click away", entries and missed == [],
                  f"{len(entries)} entries; missed {missed}")


WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1] / "design/src/i18n/fr.json").read_text(
    encoding="utf-8"))["screens"]["settings"]
# « Ce qui tourne », « Où vont les médias », « Ce qu'on va chercher » — the reader's three rubrics.
RUBRICS = ("service", "rangement", "acquisition")
EDITED = "thresholds:thresholds.min_free_space_staging_gb"
LANDED = """() => ({page: window.state?.page ?? null, path: decodeURIComponent(location.pathname),
  same: window.__sameDocument === true,
  dialog: document.querySelector('#dlg[data-open] h2')?.textContent.trim() ?? null,
  buttons: [...document.querySelectorAll('#dlg[data-open] [data-part="dialog/button"]')].length})"""


async def cold_at(browser, page_id, width=1280, height=800):
    """A desktop context out of the frame, cold at a page's address, marked as one document."""
    context, page = await open_page(browser, **{**desktop(width), "viewport": {"width": width, "height": height}})
    await context.add_init_script(OUT_OF_FRAME)
    await page.goto(PROTOTYPE + PAGE_PATHS[page_id].lstrip("/"), wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(SETTLED)
    await page.evaluate("()=>{window.__sameDocument = true}")
    return context, page


async def menu_from_a_topic(browser, journal):
    """Hold 6: a pointer click on the pinned menu from a topic entered by a pointer click."""
    entries = [("cfg", f'#view [data-topic="{rubric}"]') for rubric in RUBRICS]
    entries.append(("maint", "#view [data-maintopic]"))
    for page_id, topic in entries:
        context, page = await cold_at(browser, page_id)
        await page.click(topic)
        await page.wait_for_timeout(ACTED)
        await page.click('#drawer [data-navgo="sys"]')
        await page.wait_for_timeout(ACTED)
        landed = await page.evaluate(LANDED)
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        back = await page.evaluate(LANDED)
        journal.check(f"6: from {topic} entered by a click, the pinned menu lands on Système in the same document, "
                      "and Retour gives the page back",
                      landed["page"] == "sys" and landed["path"] == PAGE_PATHS["sys"] and landed["same"]
                      and back["page"] == page_id and back["same"], f"{landed} → {back}")
        await context.close()

    context, page = await cold_at(browser, "cfg")
    await page.evaluate("""(identifier)=>{
      const setting = window.__queries.getQueryData(['/api/v1/config/schema']).flatMap(t => t.settings)
        .find(s => window.settingId(s) === identifier);
      window.__changeSetting(identifier, Number(setting.raw) + 7);}""", EDITED)
    await page.wait_for_timeout(ACTED)
    await page.click('#view [data-topic="acquisition"]')
    await page.wait_for_timeout(ACTED)
    await page.click('#drawer [data-navgo="sys"]')
    await page.wait_for_timeout(ACTED)
    asked = await page.evaluate(LANDED)
    journal.check("6: with an edit waiting, the pinned menu from a rubric asks first — the three-choice "
                  "confirmation over Réglages, same document",
                  asked["page"] == "cfg" and asked["same"] and asked["dialog"] == WORDS["leaveHeading"]
                  and asked["buttons"] == 3, f"{asked}")
    await context.close()


UNSCROLLED = """() => {
  const drawer = document.querySelector('#drawer');
  const scrolled = [drawer, ...drawer.querySelectorAll('*')].filter((n) => n.scrollTop > 0).length;
  const hidden = [...drawer.querySelectorAll('[data-navgo]')].filter((entry) => {
    const box = entry.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return box.bottom > innerHeight || !(hit && entry.contains(hit));
  }).map((entry) => entry.dataset.navgo);
  return {scrolled, hidden};
}"""


async def every_entry_seen(browser, journal):
    """Hold 7: every entry of the pinned menu visible without scrolling it, open and folded."""
    for width, height in ((1280, 800), (1024, 768)):
        context, page = await cold_at(browser, "acq", width, height)
        for fold in ("open", "folded"):
            if fold == "folded":
                await page.evaluate(TOGGLE)
                await page.wait_for_timeout(SETTLED)
            seen = await page.evaluate(UNSCROLLED)
            journal.check(f"7: {width} × {height}, {fold}: every entry of the pinned menu is visible unscrolled",
                          seen == {"scrolled": 0, "hidden": []}, f"{seen}")
        await context.close()


async def main():
    journal = Journal("R480 — the desktop shell: the menu pinned beside a reading column")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())

        context, page = await open_page(browser, **desktop(1280))
        await context.add_init_script(OUT_OF_FRAME)
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        page.on("pageerror", lambda error: errors.append(str(error)))
        await walk(page, await page.evaluate("() => window.__states()"), 1280, journal)
        await one_click(page, journal, "1280, open")

        await read_at(page, "acq-follows-list", "() => true")
        await page.evaluate(TOGGLE)
        await page.wait_for_timeout(SETTLED)
        folded = await page.evaluate("""() => ({rail: Math.round(document.querySelector('#drawer').getBoundingClientRect().width),
          kept: localStorage.getItem('tm-rail'),
          words: [...document.querySelectorAll('#drawer [data-navgo] > span:not([data-part])')].every((w) => w.getBoundingClientRect().width <= 1 && w.textContent.trim().length > 0),
          titled: [...document.querySelectorAll('#drawer [data-navgo]')].every((a) => a.title)})""")
        journal.check("the toggle folds the menu to its icons, its words read aloud and as a tooltip, kept",
                      folded == {"rail": RAIL_FOLDED, "kept": "collapsed", "words": True, "titled": True}, f"{folded}")
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.wait_for_timeout(SETTLED)
        kept = await page.evaluate("() => Math.round(document.querySelector('#drawer').getBoundingClientRect().width)")
        journal.check("a reload opens the menu folded on this device", kept == RAIL_FOLDED, f"{kept} px")
        await one_click(page, journal, "1280, folded")
        await page.evaluate(TOGGLE)
        await page.wait_for_timeout(SETTLED)
        back = await page.evaluate("() => Math.round(document.querySelector('#drawer').getBoundingClientRect().width)")
        journal.check("unfolding gives the open width back", back == RAIL_OPEN, f"{back} px")
        await context.close()

        for width in WIDTHS_SAMPLED:
            context, page = await open_page(browser, **desktop(width))
            await context.add_init_script(OUT_OF_FRAME)
            await page.reload(wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            page.on("pageerror", lambda error: errors.append(str(error)))
            await walk(page, SAMPLE, width, journal)
            await context.close()

        phone = """() => {
          const drawer = document.querySelector('#drawer'), view = document.querySelector('#view');
          const burger = document.querySelector('[data-part="shell/header"] [data-drawer]');
          return {closed: getComputedStyle(drawer).visibility === 'hidden', burger: burger.getBoundingClientRect().width > 0,
                  fills: Math.abs(view.getBoundingClientRect().width - document.querySelector('#port').clientWidth) <= 1};
        }"""
        await menu_from_a_topic(browser, journal)
        await every_entry_seen(browser, journal)

        context, page = await open_page(browser)
        seen = await read_at(page, "acq-follows-list", phone)
        journal.check("390: the drawer a closed layer behind the burger, the page filling the port",
                      seen == {"closed": True, "burger": True, "fills": True}, f"{seen}")
        await context.close()
        context, page = await open_page(browser, **desktop(1280))
        seen = await read_at(page, "acq-follows-list", phone)
        journal.check("1280 inside the phone frame: the phone's presentation, untouched",
                      seen == {"closed": True, "burger": True, "fills": True}, f"{seen}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
