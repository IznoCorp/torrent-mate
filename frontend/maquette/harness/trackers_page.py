"""R260 — « Trackers » is a page of the bottom bar, between Médiathèque and Découvrir.

Organisation ruling 20 gives the bar four places: Acquisition, Médiathèque,
Trackers, Découvrir — Trackers INSERTED before Découvrir, never appended after a
free slot. Its place and its address are read off the navigation table and the
address model, never written here; its body is its own oracle region,
`trackers/body`.

1. the table marks the page `inBar`, third of the bar, between `lib` and
   `discover`, and the address model declares its address;
2. walked by a finger from Médiathèque, a tap on its button lands on its
   address and draws its body — and REPLACES the entry rather than stacking one,
   as every change of bar page does (§ 16 point 2): `history.length` unchanged;
3. the bar then draws four buttons, each a quarter of its width;
4. the address opened cold lands on the same page;
5. its two tabs, « Torrents » then « Trackers », are DIALS of the page: « Trackers »
   is selected when the address names none; a finger's tap on the other ADJUSTS —
   the address says `?list=`, `history.length` unchanged — and a back then leaves
   the page for the one beneath it rather than stepping between tabs;
6. the address carries both dials: `?list=torrents&tracker=<name>` opened cold
   lands on that tab, filtered to that tracker;
7. the tab a bare address opens is « Trackers » the first time, then the tab
   opened last on this device — the same rule, and the same mechanism, as
   Acquisition's: storage empty, refused or holding no tab opens « Trackers »; an
   address naming its tab wins; a tab tapped is the next cold entry's, and the
   next landing's from the bar, the address then naming it;
8. `trackers-loading`: while the page's reads are in flight, each tab — « Trackers »,
   then « Torrents » under a finger — says so with its skeletons: no row, and no
   sentence of absence standing for the wait;
9. `trackers-error`: the reads answered a failure, and each tab says it, naming
   what it could not load — never an empty body, never « nothing here ».

Red before the move: no such page exists. RE-AIMED OUT LOUD: holds 5 and 6 came
with the page's tabs, red on the page that had none; hold 7 with the tab memory,
red while a bare address always opened « Trackers ». Holds 8 and 9 came with the
wait and the failure DESIGN § 4.1 names and no phase drew, red while both tabs
drew nothing at all.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, HOME_PAGE, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TABLE = (SOURCE / "app/navigation.ts").read_text(encoding="utf-8")
IN_BAR = [identifier for identifier, flag
          in re.findall(r'\bid: "([^"]+)",.*?\binBar: (true|false)', TABLE, re.S) if flag == "true"]
PAGE = "trackers"
# The pages it stands between, by ruling 20.
BEFORE = "lib"
AFTER = "discover"
# The state the finger walk starts from: Médiathèque, drawn.
START = "lib-grid"
# A width a quarter may miss by: sub-pixel layout, never a missing button.
TOLERANCE = 1.5
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
# What each tab says it could not load, in the failure's own sentence.
FAILED = {tab: WORDS["surfaces"]["error"]["lead"].replace("{{subject}}", WORDS["screens"][tab]["errorSubject"])
          for tab in ("trackers", "torrents")}
SURFACE = """() => {
  const page = document.querySelector('#view [data-part="trackers"]');
  return {
    skeletons: page?.querySelectorAll('[data-skeleton]').length ?? 0,
    failure: page?.querySelector('[data-part="surface-error"]')?.textContent.trim() ?? null,
    rows: page?.querySelectorAll('[data-part="trackers/entry"], [data-part="torrents/row"]').length ?? 0,
    absence: page?.querySelector('[data-part="empty-state"]') !== null && page !== null,
  };
}"""

DRAWN = """() => ({
  page: window.state?.page ?? null,
  where: location.pathname,
  body: !!document.querySelector('#view [data-part="trackers"]'),
  length: history.length,
})"""

TABS = """() => ({
  tabs: [...document.querySelectorAll('#view [role="tablist"] [data-trackers-tab]')]
    .map(tab => ({tab: tab.dataset.trackersTab, selected: tab.getAttribute('aria-selected') === 'true'})),
  dial: window.state?.trackersTab ?? null,
  filter: window.state?.trackersFilter ?? null,
  address: location.pathname + location.search,
  length: history.length,
})"""
# The tabs in the operator's order (organisation ruling 19), and the one a bare
# address opens (OPEN 4, ruled C).
ORDER = ["torrents", "trackers"]
FIRST = "trackers"
OTHER = "torrents"
# A tracker the configuration declares, read off the seed the page reads.
FILTERED = json.loads((SOURCE / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))[0]["name"]

# The storage key the tab is remembered under, and what a tab reads as selected.
KEY = "trackers-tab"
SELECTED = """() => document.querySelector('[data-trackers-tab][aria-selected="true"]')?.dataset.trackersTab ?? null"""
ENTRY = PROTOTYPE.rstrip("/") + PAGE_PATHS.get(PAGE, "/trackers")


def prepared(value=None, throwing=False):
    """An init script that sets the storage before the document loads."""
    if throwing:
        return ("Storage.prototype.getItem = function () { throw new Error('storage refused'); };"
                "Storage.prototype.setItem = function () { throw new Error('storage refused'); };")
    if value is None:
        return "try { localStorage.clear(); } catch (error) {}"
    return f"try {{ localStorage.setItem({json.dumps(KEY)}, {json.dumps(value)}); }} catch (error) {{}}"


async def cold(browser, script, address):
    """Opens the address cold in a fresh context, its storage prepared first."""
    context = await browser.new_context(**PHONE)
    if script:
        await context.add_init_script(script)
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.goto(address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.wait_for_timeout(SETTLED)
    return context, page, errors


async def remembered(browser, journal):
    """Hold 7: the tab a bare address opens, first and then remembered."""
    for label, script, address, wanted in (
        ("empty storage opens « Trackers »", prepared(), ENTRY, FIRST),
        ("« Torrents » remembered opens « Torrents »", prepared(OTHER), ENTRY, OTHER),
        ("storage that throws opens « Trackers »", prepared(throwing=True), ENTRY, FIRST),
        ("a remembered value that is no tab opens « Trackers »", prepared("nowhere"), ENTRY, FIRST),
        ("an address naming its tab wins over the memory", prepared(OTHER), f"{ENTRY}?list={FIRST}", FIRST),
    ):
        context, page, errors = await cold(browser, script, address)
        selected = await page.evaluate(SELECTED)
        journal.check(label, selected == wanted, f"{selected!r} — wanted {wanted!r}")
        journal.check(f"no JS error ({label})", not errors, str(errors))
        await context.close()

    context, page, errors = await cold(browser, prepared(OTHER), ENTRY)
    where = await page.evaluate("()=>location.pathname + location.search")
    journal.check("a cold landing on the remembered « Torrents » says it in the address",
                  where == f"{PAGE_PATHS.get(PAGE)}?list={OTHER}", where)
    await context.close()

    # A TAB TAPPED BY A FINGER IS REMEMBERED: the next cold entry opens it, and so
    # does the next landing from the bar. No init script: it would run again on
    # the second page and undo the very memory being read.
    context, page, errors = await cold(browser, None, ENTRY)
    await page.tap(f'#view [data-trackers-tab="{OTHER}"]')
    await page.wait_for_timeout(ACTED)
    second = await context.new_page()
    second.on("pageerror", lambda error: errors.append(str(error)))
    await second.goto(ENTRY, wait_until="load")
    await second.evaluate("()=>window.__loadingDone?.()")
    await second.wait_for_timeout(SETTLED)
    journal.check("a tab tapped is the one the next cold entry opens",
                  await second.evaluate(SELECTED) == OTHER, str(await second.evaluate(SELECTED)))
    await second.goto(PROTOTYPE.rstrip("/") + PAGE_PATHS[HOME_PAGE], wait_until="load")
    await second.evaluate("()=>window.__loadingDone?.()")
    await second.wait_for_timeout(SETTLED)
    await second.tap(f'#nav button[data-page="{PAGE}"]')
    await second.wait_for_timeout(ACTED)
    landed = await second.evaluate(SELECTED)
    journal.check("and the one a landing from the bar opens, the address naming it",
                  landed == OTHER and second.url.endswith(f"?list={OTHER}"), f"{landed!r} · {second.url}")
    journal.check("no JS error around the memory", not errors, str(errors))
    await context.close()


BAR = """() => [...document.querySelectorAll('#nav button[data-page]')]
  .map(button => ({page: button.dataset.page, width: button.getBoundingClientRect().width}))"""


async def main():
    journal = Journal("R260 — « Trackers » is a bar page between Médiathèque and Découvrir")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        placed = (PAGE in IN_BAR and BEFORE in IN_BAR and AFTER in IN_BAR
                  and IN_BAR.index(BEFORE) + 1 == IN_BAR.index(PAGE) == IN_BAR.index(AFTER) - 1)
        journal.check("the table puts « Trackers » in the bar, between Médiathèque and Découvrir",
                      placed, str(IN_BAR))
        journal.check("and the address model declares its address", PAGE in PAGE_PATHS, str(PAGE_PATHS))

        answer = await page.evaluate(
            f"()=>{{try{{window.__go('{START}');return null}}catch(error){{return String(error)}}}}")
        journal.check(f"the named state {START} exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(DRAWN)
        button = f'#nav button[data-page="{PAGE}"]'
        present = await page.locator(button).count() == 1
        journal.check("the bar carries its button", present, f"{await page.evaluate(BAR)}")
        if present:
            await page.tap(button)
            await page.wait_for_timeout(ACTED)
        after = await page.evaluate(DRAWN)
        journal.check("a finger's tap from Médiathèque lands on its address, its body drawn",
                      after["page"] == PAGE and after["where"] == PAGE_PATHS.get(PAGE) and after["body"],
                      str(after))
        journal.check("and the change of page REPLACES the entry — history.length unchanged",
                      present and after["length"] == before["length"],
                      f"history.length {before['length']} -> {after['length']}")

        strip = await page.evaluate(TABS)
        journal.check("its strip draws « Torrents » then « Trackers », « Trackers » selected on a bare address",
                      [entry["tab"] for entry in strip["tabs"]] == ORDER
                      and [entry["tab"] for entry in strip["tabs"] if entry["selected"]] == [FIRST]
                      and strip["dial"] == FIRST, str(strip))
        other = f'#view [data-trackers-tab="{OTHER}"]'
        if await page.locator(other).count() == 1:
            await page.tap(other)
            await page.wait_for_timeout(ACTED)
        switched = await page.evaluate(TABS)
        journal.check("a finger's tap on « Torrents » ADJUSTS: the address names it, history.length unchanged",
                      switched["dial"] == OTHER and switched["address"] == f"{PAGE_PATHS.get(PAGE)}?list={OTHER}"
                      and switched["length"] == strip["length"] and after["length"] == strip["length"],
                      f"{strip} -> {switched}")
        # FROM THE ENTRY PAGE the page is PUSHED, so what lies beneath it is
        # known: Acquisition. A back after the tabs moved must land there.
        for step in ("acq", PAGE):
            await page.tap(f'#nav button[data-page="{step}"]')
            await page.wait_for_timeout(ACTED)
        if await page.locator(other).count() == 1:
            await page.tap(other)
            await page.wait_for_timeout(ACTED)
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        back = await page.evaluate(DRAWN)
        journal.check("and a back then leaves the page for the one beneath it, never a step between tabs",
                      back["page"] == HOME_PAGE, str(back))

        bar = await page.evaluate(BAR)
        total = sum(entry["width"] for entry in bar)
        quarters = len(bar) == 4 and all(abs(entry["width"] - total / 4) <= TOLERANCE for entry in bar)
        journal.check("the bar draws four buttons, each a quarter of it", quarters, str(bar))

        cold = await browser.new_context(**PHONE)
        fresh = await cold.new_page()
        fresh.on("pageerror", lambda error: errors.append(str(error)))
        await fresh.goto(PROTOTYPE.rstrip("/") + PAGE_PATHS.get(PAGE, "/trackers"), wait_until="load")
        await fresh.evaluate("()=>window.__loadingDone?.()")
        await fresh.wait_for_timeout(SETTLED)
        opened = await fresh.evaluate(DRAWN)
        journal.check("its address opened cold lands on the page",
                      opened["page"] == PAGE and opened["body"], str(opened))
        filtered_context = await browser.new_context(**PHONE)
        filtered = await filtered_context.new_page()
        filtered.on("pageerror", lambda error: errors.append(str(error)))
        address = f"{PAGE_PATHS.get(PAGE, '/trackers')}?list={OTHER}&tracker={FILTERED}"
        await filtered.goto(PROTOTYPE.rstrip("/") + address, wait_until="load")
        await filtered.evaluate("()=>window.__loadingDone?.()")
        await filtered.wait_for_timeout(SETTLED)
        dials = await filtered.evaluate(TABS)
        journal.check("the address carries both dials: its tab and its tracker, opened cold",
                      dials["dial"] == OTHER and dials["filter"] == FILTERED and dials["address"] == address,
                      str(dials))
        await filtered_context.close()
        await cold.close()

        # ── the wait and the failure, on both tabs ───────────────────────
        for state in ("trackers-loading", "trackers-error"):
            answer = await page.evaluate(
                f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
            await page.wait_for_timeout(SETTLED)
            seen = {"trackers": await page.evaluate(SURFACE)}
            torrents = page.locator('#view [data-trackers-tab="torrents"]')
            if await torrents.count():
                await torrents.first.tap()
                await page.wait_for_timeout(ACTED)
            seen["torrents"] = await page.evaluate(SURFACE)
            for tab, surface in seen.items():
                quiet = surface["rows"] == 0 and not surface["absence"]
                if state == "trackers-loading":
                    journal.check(f"{state}: « {tab} » says its reads are under way — skeletons, no row, no absence",
                                  answer is None and quiet and surface["skeletons"] > 0 and surface["failure"] is None,
                                  f"{answer or ''} {surface}")
                else:
                    journal.check(f"{state}: « {tab} » says « {FAILED[tab]} », no row, no absence",
                                  answer is None and quiet and surface["failure"] is not None
                                  and FAILED[tab] in surface["failure"], f"{answer or ''} {surface}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await remembered(browser, journal)
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
