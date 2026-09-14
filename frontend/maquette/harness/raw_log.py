"""R183 — B-296: a passage's raw output is FOLDED, and what is absent is said.

THE RULING THIS HOLDS. A run's raw output is diagnosis material: DOIT-1 asks the
interface to speak clear French, and a log line is not that. So the narrative of
a passage is its steps, and the raw output is a secondary disclosure — closed
until someone asks for it.

WHAT IS READ, and each hold is a different claim:

  1. AT REST THE LINES ARE NOT RENDERED. Read as `offsetParent === null` on the
     content, NOT as « the `open` attribute is absent ». An attribute's absence
     is a claim about markup; whether a reader can SEE the lines is the claim
     B-296 makes, and the two part company the moment anything styles the
     element.
  2. A TAP OPENS IT, by a finger, and what appears is the layer's own
     `outputTail` — verbatim, because it is data displayed and not copy.
  3. `outputTail: null` DRAWS THE SENTENCE, never an empty box. A run recorded
     before output capture existed has no log, and an empty frame reads as
     « nothing happened » — §14 asks the interface to say « inconnue » instead.
  4. THE BLOCK SCROLLS SIDEWAYS AND THE PAGE DOES NOT. A raw line is wider than
     390 px; DOIT-9 allows exactly one thing to scroll horizontally — a code
     block in its own container — and refuses the page doing it.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# THE STATES OF A PASSAGE'S SCREEN, by the id `window.__go` takes.
DETAIL = "run-detail"
OPENED = "run-detail-log"
NO_LOG = "run-detail-no-log"

# WHAT THE SCREEN CARRIES.
LOG = "run/log"
TOGGLE = "run/log-toggle"

# WHETHER THE LINES ARE RENDERED AT ALL — the claim, and not the attribute.
RENDERED = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  if (!node) return null;
  return node.offsetParent !== null;
}"""

# WHAT THE BLOCK HOLDS.
TEXT = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  return node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# PRESSED BY A FINGER, at its own centre, after scrolling to it.
PRESS = """(part)=>{
  const control = document.querySelector(`[data-part="${part}"]`);
  if (!control) return {found: false, pressed: false, covered: ''};
  control.scrollIntoView({block: 'center'});
  const box = control.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
                                        box.top + box.height / 2);
  const mine = Boolean(hit) && (hit === control || control.contains(hit)
                               || hit.contains(control));
  if (mine) control.click();
  return {found: true, pressed: mine,
          covered: mine ? '' : ((hit && (hit.dataset.part || hit.tagName)) || 'nothing')};
}"""

# WHAT THE LAYER ANSWERED FOR THE RUN ON SCREEN: its own output, to compare
# against what the fold reveals.
ANSWERED_TAIL = """async ()=>{
  const uid = location.pathname.split('/').pop();
  const detail = await (await fetch('/api/pipeline/history/' + uid)).json();
  return detail.outputTail;
}"""

# WHO SCROLLS SIDEWAYS: the block may, the page may not.
SCROLLS = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  const page = document.querySelector('#view') || document.scrollingElement;
  return {
    block: node ? node.scrollWidth > node.clientWidth + 1 : null,
    blockCanScroll: node ? ['auto', 'scroll'].includes(getComputedStyle(node).overflowX) : null,
    page: page ? page.scrollWidth > page.clientWidth + 1 : null,
  };
}"""


async def drive(journal, page, state):
    """Drives one named state and holds that the table declares it.

    Args:
        journal: The run's journal.
        page: The prototype's page.
        state: The named state's id.

    Returns:
        Whether the state could be driven.
    """
    try:
        await page.evaluate("(id)=>window.__go(id)", state)
        reached, detail = True, ""
    except Exception as error:  # noqa: BLE001 — the message IS the measurement
        reached, detail = False, str(error).splitlines()[0]
    journal.check(f"{state} is a state the table declares", reached, detail)
    await page.wait_for_timeout(SETTLED)
    return reached


async def main():
    """Reads the fold: closed, opened by a finger, absent, and its scrolling."""
    journal = Journal("R183 — B-296: a passage's raw output is folded, and what "
                      "is absent is said")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # 1 — AT REST, THE LINES ARE NOT RENDERED.
        await drive(journal, page, DETAIL)
        journal.check("the fold is offered", await page.evaluate(RENDERED, TOGGLE) is True,
                      f"{await page.evaluate(RENDERED, TOGGLE)}")
        journal.check("and at rest its lines are NOT rendered",
                      await page.evaluate(RENDERED, LOG) in (False, None),
                      f"{await page.evaluate(RENDERED, LOG)}")

        # 2 — A TAP OPENS IT, and what appears is the layer's own output.
        press = await page.evaluate(PRESS, TOGGLE)
        journal.check("the fold is reachable by a finger", press["pressed"], f"{press}")
        await page.wait_for_timeout(ACTED)
        journal.check("and a tap renders the lines",
                      await page.evaluate(RENDERED, LOG) is True,
                      f"{await page.evaluate(RENDERED, LOG)}")
        tail = await page.evaluate(ANSWERED_TAIL)
        shown = await page.evaluate(TEXT, LOG)
        sample = "" if not tail else " ".join(str(tail).split())[-60:]
        journal.check("what it shows is the run's own output, verbatim",
                      bool(shown) and bool(sample) and sample in shown,
                      f"{sample!r} in {(shown or '')[-120:]!r}")

        # 4 — THE BLOCK SCROLLS SIDEWAYS, THE PAGE DOES NOT.
        scrolling = await page.evaluate(SCROLLS, LOG)
        journal.check("the log block is the one allowed to scroll sideways",
                      scrolling["blockCanScroll"] is True, f"{scrolling}")
        journal.check("and the page itself does not", scrolling["page"] is False,
                      f"{scrolling}")

        # 3 — A RUN WITH NO OUTPUT SAYS SO, and draws no empty box.
        await drive(journal, page, NO_LOG)
        said = await page.evaluate(TEXT, LOG)
        toggle = await page.evaluate(RENDERED, TOGGLE)
        journal.check("a passage whose output was not kept says so",
                      bool(said) and "non conservée" in said.lower(), f"{said!r}")
        journal.check("and offers no fold onto an empty box", toggle in (False, None),
                      f"{toggle}")

        # AND THE STATE THAT STANDS FOR THE FOLD OPEN renders its lines.
        await drive(journal, page, OPENED)
        journal.check("the opened state really is opened",
                      await page.evaluate(RENDERED, LOG) is True,
                      f"{await page.evaluate(RENDERED, LOG)}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
