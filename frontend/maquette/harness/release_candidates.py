"""R178 — every title offered « Chercher une autre release » has a release to choose.

B-501. The verb is offered on every medium still being acquired — a follow, an
incomplete series, a card waiting in the queue — and the list it opens came
back EMPTY for every title but one. The seed held four releases, all Silo, and
the handler kept a release only when the title appeared in its name, so the
screen the verb promised was « no candidate » everywhere the operator tried it.

WHY NOTHING ELSE SAW IT. The picker's named state opens on Silo, the one title
the seed covered; R137 reads that state, the oracle measures it, and both were
right about the only title they asked. A list that is non-empty for the title a
rule picked says nothing about the titles a reader picks.

WHAT IT READS, and it reads it where the reader walks:

  1. THE TITLES ARE ENUMERATED FROM THE SURFACES, never from a seed. Every card
     of Acquisition › Suivis and of Acquisition › En cours is tapped, and the
     titles whose panel offers the verb — `[data-part="sheet/action"]`
     carrying `data-releases` — are the ones judged. A hold first says the
     enumeration found titles on both surfaces, because « none is empty » is
     true of none.
  2. EACH OF THEM IS OPENED THROUGH ITS OWN VERB, tapped in the panel, and the
     open picker's rows are counted — the rows drawn, not the seed — so a
     handler, a query key or a fold that loses a title falls here by name.

WHAT IT DOES NOT READ: whether a release is plausible for its title, the order
the rows are drawn in, and any title the library offers the verb on outside
these two pages.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# The two pages the operator reported from, each a named state.
SURFACES = (("the follow panel", "acq-follows-list"), ("the queue card", "acq-now-idle"))

CARD_COUNT = """()=>document.querySelectorAll('#view [data-part="card"]').length"""

# THE CARD'S BODY IS TAPPED, the target a finger aims at to raise the panel.
TAP_CARD = """(index)=>{
  const card = document.querySelectorAll('#view [data-part="card"]')[index];
  const body = card?.querySelector('[data-part="card/body"]') || card;
  if (!body) return false;
  body.scrollIntoView({block: 'center'});
  body.click();
  return true;}"""

# THE VERB, read off the open panel: its presence and the title it names.
OFFERED = """()=>{
  const sheet = document.querySelector('#sheet[data-open]');
  const verb = sheet?.querySelector('[data-part="sheet/action"][data-releases]');
  return verb ? verb.dataset.releases : null;}"""

TAP_VERB = """()=>document.querySelector(
  '#sheet[data-open] [data-part="sheet/action"][data-releases]').click()"""

# THE ROWS THE OPEN PICKER DRAWS, inside the screen whose key names releases.
DRAWN = """()=>{
  const screen = [...document.querySelectorAll('[data-part="screen"][data-open]')]
    .find((one) => (one.dataset.key || '').startsWith('releases:'));
  if (!screen) return null;
  return [...screen.querySelectorAll('[data-part="card/foot"]')]
    .filter((one) => 'pickRelease' in one.dataset).length;}"""

# How long the picker's list may take to arrive before it is read as empty.
ROWS_DEADLINE = 3000
POLL_INTERVAL = 100


async def rows_of_the_picker(page):
    """Waits for the open picker to draw its rows, and counts them.

    Returns:
        The number of rows, 0 when none arrived within the deadline, or `None`
        when no picker opened at all.
    """
    waited = 0
    drawn = await page.evaluate(DRAWN)
    while (drawn is None or drawn == 0) and waited < ROWS_DEADLINE:
        await page.wait_for_timeout(POLL_INTERVAL)
        waited += POLL_INTERVAL
        drawn = await page.evaluate(DRAWN)
    return drawn


async def read_surface(page, state):
    """Taps every card of one page and opens the picker of each title offered it.

    Returns:
        `{title: rows}` for every title whose panel offered the verb.
    """
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(SETTLED)
    count = await page.evaluate(CARD_COUNT)
    found = {}
    for index in range(count):
        await page.evaluate("(id)=>window.__go(id)", state)
        await page.wait_for_timeout(SETTLED)
        if not await page.evaluate(TAP_CARD, index):
            continue
        await page.wait_for_timeout(ACTED)
        title = await page.evaluate(OFFERED)
        if title is None or title in found:
            continue
        await page.evaluate(TAP_VERB)
        found[title] = await rows_of_the_picker(page)
    return found


async def main():
    journal = Journal("R178 — every title offered another release has one to choose")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        for label, state in SURFACES:
            found = await read_surface(page, state)
            journal.check(
                f"{label} offers the verb on at least one title — the rest of this "
                "surface's holds are read over those titles",
                len(found) > 0, f"{state}: {len(found)} title(s) offered it")
            empty = sorted(title for title, rows in found.items() if not rows)
            journal.check(
                f"from {label}, every title offered « another release » opens a "
                "picker with at least one release to choose",
                len(found) > 0 and not empty,
                f"{len(found)} title(s) read on {state}; empty: "
                + (", ".join(f"« {title} »" for title in empty) or "none"))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
