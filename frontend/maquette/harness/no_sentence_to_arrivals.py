"""R239 — nothing sends the reader to Arrivées any more.

An arrival is an acquisition card, and the page that described the arrivals
dies with this lot; so no sentence may keep sending the operator there. Five
did: Système's introduction and its runs' cross-reference, a run's « what this
run left behind », « En cours »'s cross-reference, and the toast a maintenance
command raises. A sixth promised a section that is gone: the quality screen
said an exhausted profile reads « cherché, rien trouvé » on a card, and what
was not found now reads on the follow, whose live search answers « aucun
torrent trouvé ».

1. Système, a run's detail, « En cours » and the quality screen draw no
   sentence naming Arrivées, and no control addressed to it;
2. every cross-reference that leaves Système or a run's detail for another
   page (`data-go`; Maintenance is reached by `data-page`) lands on
   Acquisition, tapped by a finger — on « À traiter », which it names: the
   address it settles on says `tab=todo`, and « À traiter » is the tab drawn,
   though the device remembers no tab (« Suivis » otherwise);
   A run's detail is reached BY FINGER for the landing — home, the menu,
   Système, a run — because its named state lays Système without the entry a
   finger pushes, and the landing's walk back through the history then has no
   floor to land on: the address would be read off a history no finger makes.
   RE-AIMED OUT LOUD (§ 16 as amended, Q12, the navigation lot): the landing
   STANDS ON THE TRAIL, never on the floor — a link inside a page stacks, even
   towards the entry page, so Retour gives back Système (or the run's screen).
   Its entry is the floor's plus what the finger stacked: Système, then the
   landing (floor + 2), and the run's screen between them (floor + 3);
2b. and the landing home that every bar tap makes is unchanged: on a
   history a finger laid with « En cours » in the floor's address and « À
   traiter » remembered, the bar's Médiathèque then its Acquisition come back
   to « En cours », the address saying it (the step back home is ANNOUNCED
   since the landings above, and the floor takes the page's own state);
2d. a run's screen opened by a row COUNTS its entry into the step home (held
   by the walk above); a run's address loaded cold — no entry pushed — lands
   its cross-reference on Acquisition without leaving the application. The
   bar is not a second reader: the screen covers it, and no finger reaches it;
2c. a control that names no tab (the not-found page's « Acquisition ») lands
   on the tab the device remembers, « En cours » here;
3. « En cours » draws no cross-reference at all: its subject — what entered
   without a follow and waits for a hand — is « À traiter » and its count;
4. a maintenance command, run for real, is said in the sentence that names
   Système, where its run is listed, and not Arrivées;
5. the quality screen promises no « cherché, rien trouvé ».

Every expected sentence is read from the interface's resources, never written
here. The page's own name is NOT: the page is gone from the resources with the
page, and a sentence naming it is the defect this rule looks for, so its name is
written here, once.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, PAGE_PATHS, PROTOTYPE, PANEL_IN, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
# The page's name in the interface, and its plural in running text.
PAGES = WORDS["navigation"]["pages"]
# THE DEAD PAGE'S NAME, as the interface wrote it while it lived.
ARRIVALS_NAME = "Arrivées"  # french-ok: the removed page's name, asserted absent
ARRIVALS = re.compile(r"\b" + re.escape(ARRIVALS_NAME.lower()) + r"\b")
STARTED = WORDS["verbs"]["maintenance"]["started"]
SYSTEM = PAGES["sys"]
REMOVED_PROMISE = "cherché, rien trouvé"  # french-ok: the removed section's words, asserted absent
SYSTEM_PATH = PAGE_PATHS["sys"]
# Where a landing ends: the page the interface holds, and the address it shows.
# The entry of the stack is the home page's own address, so a landing that
# rewinds to it reads the entry's path rather than the page's.
LANDED = """()=>({ page: state.page, path: location.pathname,
  tab: new URLSearchParams(location.search).get('tab'),
  drawn: document.querySelector('[data-acqtab][aria-selected="true"]')?.dataset.acqtab ?? null })"""
# The storage key the device remembers Acquisition's tab under (R202's).
KEY = "acquisition-tab"
FORGET = "(key)=>{ try { localStorage.removeItem(key); } catch (error) {} }"
REMEMBER = "([key, tab])=>{ try { localStorage.setItem(key, tab); } catch (error) {} }"
# The index of the history entry the page stands on, as the router writes it.
ENTRY = "()=>(history.state || {}).__TSR_index ?? null"
TODO = "todo"
NOW = "now"
REAL_COMMAND = "library-status"
RULE_NOTE = WORDS["screens"]["profile"]["rulenote"]
# A page's body is drawn from the navigation table, so it is read as the view.
PAGE = "#view"
RUN_BODY = '[data-region="run/body"]'
PROFILE_BODY = '[data-region="screen-profile/body"]'
TEXT = "(selector)=>(document.querySelector(selector)||{}).innerText || ''"
LINKS = """(selector)=>[...document.querySelectorAll(selector + ' [data-go]')]
  .map((control) => control.dataset.go)"""
CROSS_REFERENCES = """(selector)=>document.querySelectorAll(
  selector + ' [data-part="cross-reference"][data-go]').length"""
EVERY_CROSS_REFERENCE = """(selector)=>document.querySelectorAll(
  selector + ' [data-part="cross-reference"]').length"""


def names_arrivals(text):
    """Whether a text names the Arrivées page."""
    return ARRIVALS.search(text.lower()) is not None


async def step(page, journal, where, selector):
    """Taps what a selector finds, by a finger; a step nobody can tap is a named failure."""
    try:
        await page.locator(selector).first.tap(timeout=5000)
    except Exception as error:  # the walk cannot go on, and says where it stopped
        journal.check(f"{where}: the finger reaches {selector}", False, str(error).splitlines()[0])
        return False
    await page.wait_for_timeout(ACTED)
    return True


async def drive(page, state):
    """Drives one named state and lets it settle."""
    await page.evaluate("()=>window.__mocks.reset()")
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(SETTLED)


async def reads(page, journal, state, selector):
    """Holds that one surface names no Arrivées, in its text or its controls."""
    await drive(page, state)
    text = await page.evaluate(TEXT, selector)
    journal.check(f"{state}: the surface is drawn", text.strip() != "", selector)
    journal.check(f"{state}: no sentence names « {ARRIVALS_NAME} »",
                  not names_arrivals(text), text[:400])
    links = await page.evaluate(LINKS, selector)
    journal.check(f"{state}: no control is addressed to it", "arr" not in links, str(links))


async def lands(page, journal, state, selector, walked=False):
    """Holds that each cross-reference of a surface that leaves for a page, tapped, lands on Acquisition.

    Système's cross-references to Maintenance are a page of its own reached
    by `data-page`; the ones that left for Arrivées are the `data-go` ones.
    """
    await reads(page, journal, state, selector)
    count = await page.evaluate(CROSS_REFERENCES, selector)
    journal.check(f"{state}: it draws a cross-reference that leaves the page", count > 0, str(count))
    if walked:
        return
    for index in range(count):
        await drive(page, state)
        await page.evaluate(FORGET, KEY)
        await page.locator(f'{selector} [data-part="cross-reference"][data-go]').nth(index).tap()
        await page.wait_for_timeout(ACTED)
        landed = await page.evaluate(LANDED)
        journal.check(f"{state}: its cross-reference {index + 1} lands on Acquisition, and leaves Système",
                      landed["page"] == "acq" and not landed["path"].startswith(SYSTEM_PATH), str(landed))
        journal.check(f"{state}: on « À traiter », which it names — the address says it, and the tab is drawn",
                      landed["tab"] == TODO and landed["drawn"] == TODO, str(landed))


# The walks a finger makes from home to each cross-reference.
TO_SYSTEM = ('[data-drawer]', '#drawer [data-navgo="sys"]')
WALKS = {
    "system": (*TO_SYSTEM, f'{PAGE} [data-part="cross-reference"][data-go]'),
    "run-detail": (*TO_SYSTEM, '[data-run]', f'{RUN_BODY} [data-part="cross-reference"][data-go]'),
}
# How many entries each walk stacks above the floor: Système, the run's screen
# where it is walked through, and the landing itself.
STACKED = {"system": 2, "run-detail": 3}


async def walked(browser, journal, name):
    """Holds the landing of a cross-reference on a history a finger laid."""
    context, page = await open_page(browser)
    await page.evaluate(FORGET, KEY)
    floor = await page.evaluate(ENTRY)
    for selector in WALKS[name]:
        if not await step(page, journal, f"{name}, walked", selector):
            await context.close()
            return
    landed = await page.evaluate(LANDED)
    journal.check(f"{name}, walked: its cross-reference lands on Acquisition, and leaves Système",
                  landed["page"] == "acq" and not landed["path"].startswith(SYSTEM_PATH), str(landed))
    journal.check(f"{name}, walked: on « À traiter », which it names — the address says it, and the tab is drawn",
                  landed["tab"] == TODO and landed["drawn"] == TODO, str(landed))
    standing = await page.evaluate(ENTRY)
    journal.check(f"{name}, walked: the landing stands on the trail the finger walked, the floor "
                  f"{STACKED[name]} entries down",
                  floor is not None and standing == floor + STACKED[name],
                  f"floor {floor}, landed on {standing}")
    await context.close()


async def bar_home(browser, journal):
    """Holds a bar tap home on a floor whose tab is not the remembered one."""
    context, page = await open_page(browser)
    walk = ('[data-acqtab="now"]', '#nav button[data-page="lib"]', '#nav button[data-page="acq"]')
    for index, selector in enumerate(walk):
        if not await step(page, journal, "the bar, walked home", selector):
            await context.close()
            return
        if index == 0:
            await page.evaluate(REMEMBER, [KEY, TODO])
    landed = await page.evaluate(LANDED)
    journal.check("the bar, walked home: back on « En cours », the floor's tab, and the address says it",
                  landed["page"] == "acq" and landed["drawn"] == NOW and landed["tab"] == NOW, str(landed))
    await page.evaluate(FORGET, KEY)
    await context.close()


async def cold_run(browser, journal):
    """Holds a run's cross-reference on the run's address loaded cold."""
    context, page = await open_page(browser)
    for selector in (*TO_SYSTEM, '[data-run]'):
        if not await step(page, journal, "a run's address, read", selector):
            await context.close()
            return
    address = await page.evaluate("()=>location.pathname")
    await context.close()

    context, page = await open_page(browser)
    await page.goto(PROTOTYPE.rstrip("/") + address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(SETTLED)
    if not await step(page, journal, "a run's address loaded cold", f'{RUN_BODY} [data-part="cross-reference"][data-go]'):
        await context.close()
        return
    inside = page.url.startswith(PROTOTYPE.rstrip("/"))
    landed = await page.evaluate(LANDED) if inside else {"url": page.url}
    journal.check("a run's address loaded cold: its cross-reference lands on Acquisition, inside the application",
                  inside and landed.get("page") == "acq", f"{address} → {landed}")
    await context.close()


async def maintenance_toast(page, journal):
    """Holds what a real maintenance run says."""
    await drive(page, "maintenance")
    await page.evaluate('(id)=>window.__panel.produce("action", id)', REAL_COMMAND)
    await page.wait_for_timeout(PANEL_IN)
    await page.locator("[data-maintenance-run]").first.tap()
    await page.wait_for_timeout(ACTED)
    said = (await page.evaluate(TEXT, "#toast")).strip()
    journal.check("a real maintenance run is said in its started sentence", said == STARTED, repr(said))
    journal.check(f"which names « {SYSTEM} », where its run is listed, and not « {ARRIVALS_NAME} »",
                  SYSTEM in said and not names_arrivals(said), repr(said))


async def main():
    journal = Journal("R239 — nothing sends the reader to Arrivées any more")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await lands(page, journal, "system", PAGE)
        await lands(page, journal, "run-detail", RUN_BODY, walked=True)
        await walked(browser, journal, "system")
        await walked(browser, journal, "run-detail")
        await bar_home(browser, journal)
        await cold_run(browser, journal)

        await reads(page, journal, "acq-now-loaded", PAGE)
        staged = await page.evaluate("async()=>(await (await fetch('/api/staging/media?scenario=loaded')).json())")
        journal.check("acq-now-loaded: the world holds folders that entered without a follow",
                      len((staged or {}).get("stuck", [])) > 0, str(staged)[:200])
        count = await page.evaluate(EVERY_CROSS_REFERENCE, PAGE)
        journal.check("acq-now-loaded: « En cours » draws no cross-reference", count == 0, str(count))

        await drive(page, "not-found")
        await page.evaluate(REMEMBER, [KEY, NOW])
        await page.locator('[data-part="card/foot"][data-go="acq"]').first.tap()
        await page.wait_for_timeout(ACTED)
        landed = await page.evaluate(LANDED)
        journal.check("not-found: a control that names no tab lands on the remembered one, « En cours »",
                      landed["page"] == "acq" and landed["drawn"] == NOW, str(landed))
        await page.evaluate(FORGET, KEY)

        await maintenance_toast(page, journal)

        await drive(page, "screen-profile")
        note = await page.evaluate(TEXT, PROFILE_BODY)
        journal.check("screen-profile: the screen draws its rule note", RULE_NOTE in note, note[-400:])
        journal.check("screen-profile: no sentence promises « cherché, rien trouvé »",
                      REMOVED_PROMISE not in note and REMOVED_PROMISE not in RULE_NOTE, RULE_NOTE)

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
