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
   Acquisition, tapped by a finger;
3. « En cours » draws no cross-reference at all: its subject — what entered
   without a follow and waits for a hand — is « À traiter » and its count;
4. a maintenance command, run for real, is said in the sentence that names
   Système, where its run is listed, and not Arrivées;
5. the quality screen promises no « cherché, rien trouvé ».

Every expected sentence is read from the interface's resources, never written
here; the page's own name is read from them too.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, PAGE_PATHS, PANEL_IN, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
# The page's name in the interface, and its plural in running text.
PAGES = WORDS["navigation"]["pages"]
ARRIVALS = re.compile(r"\b" + re.escape(PAGES["arr"].lower()) + r"\b")
STARTED = WORDS["verbs"]["maintenance"]["started"]
SYSTEM = PAGES["sys"]
REMOVED_PROMISE = "cherché, rien trouvé"  # french-ok: the removed section's words, asserted absent
SYSTEM_PATH = PAGE_PATHS["sys"]
# Where a landing ends: the page the interface holds, and the address it shows.
# The entry of the stack is the home page's own address, so a landing that
# rewinds to it reads the entry's path rather than the page's.
LANDED = "()=>({ page: state.page, path: location.pathname })"
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
    journal.check(f"{state}: no sentence names « {PAGES['arr']} »",
                  not names_arrivals(text), text[:400])
    links = await page.evaluate(LINKS, selector)
    journal.check(f"{state}: no control is addressed to it", "arr" not in links, str(links))


async def lands(page, journal, state, selector):
    """Holds that each cross-reference of a surface that leaves for a page, tapped, lands on Acquisition.

    Système's cross-references to Maintenance are a page of its own reached
    by `data-page`; the ones that left for Arrivées are the `data-go` ones.
    """
    await reads(page, journal, state, selector)
    count = await page.evaluate(CROSS_REFERENCES, selector)
    journal.check(f"{state}: it draws a cross-reference that leaves the page", count > 0, str(count))
    for index in range(count):
        await drive(page, state)
        await page.locator(f'{selector} [data-part="cross-reference"][data-go]').nth(index).tap()
        await page.wait_for_timeout(ACTED)
        landed = await page.evaluate(LANDED)
        journal.check(f"{state}: its cross-reference {index + 1} lands on Acquisition, and leaves Système",
                      landed["page"] == "acq" and not landed["path"].startswith(SYSTEM_PATH), str(landed))


async def maintenance_toast(page, journal):
    """Holds what a real maintenance run says."""
    await drive(page, "maintenance")
    await page.evaluate('(id)=>window.__panel.produce("action", id)', REAL_COMMAND)
    await page.wait_for_timeout(PANEL_IN)
    await page.locator("[data-maintenance-run]").first.tap()
    await page.wait_for_timeout(ACTED)
    said = (await page.evaluate(TEXT, "#toast")).strip()
    journal.check("a real maintenance run is said in its started sentence", said == STARTED, repr(said))
    journal.check(f"which names « {SYSTEM} », where its run is listed, and not « {PAGES['arr']} »",
                  SYSTEM in said and not names_arrivals(said), repr(said))


async def main():
    journal = Journal("R239 — nothing sends the reader to Arrivées any more")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await lands(page, journal, "system", PAGE)
        await lands(page, journal, "run-detail", RUN_BODY)

        await reads(page, journal, "acq-now-loaded", PAGE)
        staged = await page.evaluate("async()=>(await (await fetch('/api/staging/media?scenario=loaded')).json())")
        journal.check("acq-now-loaded: the world holds folders that entered without a follow",
                      len((staged or {}).get("stuck", [])) > 0, str(staged)[:200])
        count = await page.evaluate(EVERY_CROSS_REFERENCE, PAGE)
        journal.check("acq-now-loaded: « En cours » draws no cross-reference", count == 0, str(count))

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
