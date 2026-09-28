"""R240 — Système's levers stay live: the pipeline's state moves with the server's events.

The levers draw the pipeline's own state — « Mettre tout en pause » while a run
goes, « Reprendre » while it is held, the reason when nothing runs — from the
status read. What keeps that read current is a live rule: the run's lifecycle
events refresh it. That rule was written in Arrivées' table, so Système's levers
moved only because another page carried the rule for them; the day that page's
table died, the levers would have frozen at their last read and no rule about
Arrivées would have said so.

WHAT IS READ, on Système, the layer moved WITHOUT the interface being told, then
one event relayed:

  1. at rest the levers say nothing runs;
  2. the layer is set running and the levers still say nothing runs — no event
     yet, so nothing re-read the status; this is what makes the next hold about
     the event and not about a refetch that would have happened anyway;
  3. « PipelineStarted » arrives, and the levers offer « Mettre tout en pause »;
  4. the layer is paused, « PipelinePaused » arrives, and the levers offer
     « Reprendre »;
  5. the run is ended, « PipelineEnded » arrives, and the levers say nothing runs.

No state door is opened after the first: the page is reached once, and every
move afterwards is the layer's and the relay's.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# THE PAGE THE LEVERS ARE DRAWN ON, at rest.
SYSTEM_STATE = "system"

# WHAT THE LEVERS OFFER, by the part each control or sentence wears.
LEVERS = """()=>[...document.querySelectorAll(
  '#view [data-part="levers/pause"], #view [data-part="levers/resume"], #view [data-part="levers/nothing-running"]')]
  .map((one) => one.dataset.part)"""

# THE LAYER MOVED BEHIND THE INTERFACE'S BACK: a raw request, which no verb
# follows with a re-read.
LAYER = """async (path) => {
  await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
                     body: JSON.stringify({dryRun: false})});
  await window.__mocks.quiet();
}"""

# ONE EVENT THROUGH THE MOCK RELAY, and the layer let settle.
EMIT = """async (type) => {
  window.__mocks.stream.emit(type, {});
  await window.__mocks.quiet();
}"""

RUN = "/api/maintenance/actions/library-status/run"
PAUSE = "/api/pipeline/pause"
KILL = "/api/pipeline/kill"


async def settle(page):
    """Waits for the layer to be quiet and the page to have drawn."""
    await page.evaluate("()=>window.__mocks.quiet()")
    await page.wait_for_timeout(SETTLED)


async def main():
    journal = Journal("R240 — Système's levers stay live")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", SYSTEM_STATE)
        journal.check(f"the named state {SYSTEM_STATE} exists", answer is None, answer or "")
        await settle(page)
        at_rest = await page.evaluate(LEVERS)
        journal.check("at rest the levers say nothing runs",
                      at_rest == ["levers/nothing-running"], str(at_rest))

        await page.evaluate(LAYER, RUN)
        await settle(page)
        before_event = await page.evaluate(LEVERS)
        journal.check("the layer set running, and with no event yet the levers have not moved",
                      before_event == ["levers/nothing-running"], str(before_event))

        await page.evaluate(EMIT, "PipelineStarted")
        await settle(page)
        started = await page.evaluate(LEVERS)
        journal.check("« PipelineStarted » arrives, and the levers offer « Mettre tout en pause »",
                      started == ["levers/pause"], str(started))

        await page.evaluate(LAYER, PAUSE)
        await page.evaluate(EMIT, "PipelinePaused")
        await settle(page)
        paused = await page.evaluate(LEVERS)
        journal.check("« PipelinePaused » arrives, and the levers offer « Reprendre »",
                      paused == ["levers/resume"], str(paused))

        await page.evaluate(LAYER, KILL)
        await page.evaluate(EMIT, "PipelineEnded")
        await settle(page)
        ended = await page.evaluate(LEVERS)
        journal.check("« PipelineEnded » arrives, and the levers say nothing runs",
                      ended == ["levers/nothing-running"], str(ended))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
