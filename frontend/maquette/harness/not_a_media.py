"""R228 — « Ce n'est pas un média »: the folder is reclassified, and leaves the acquisitions.

Ruling 5: the candidates screen offers « Ce n'est pas un média ». The folder is
reclassified « other » and filed where the sort files that category — the
destinations are the CONFIGURATION's, never hard-coded (DESIGN § 3.4) — and its
card leaves the acquisitions: the operator does not see it again. An « Annuler »
window answers every resolve with its inverse (`backend-demands-architecture.md`
§ 9, demand C).

Walked by finger on a folder the sort typed as a medium and that no provider
identifies, « Backrooms.2026.MULTi.2160p.WEB-DL », in the dense world's « À
traiter ». RE-AIMED OUT LOUD: it was walked on the real world's game folder,
which the sort files as « autre » and ruling 1 keeps out of the acquisitions —
that folder was never a card, and it left the seeds:

1. « Résoudre → » on its card, then « Ce n'est pas un média » on the screen,
   opens a choice offering exactly the destinations the layer answers — read
   off the seed the layer answers from, never written here;
2. a destination tapped is ANSWERED by the reclassification operation, and the
   message says the destination the answer names;
3. the operator is back on « À traiter », the tab open, no screen left;
4. the card is in NEITHER « À traiter » — its folded section included — nor
   « En cours »;
5. « Annuler » is answered by the inverse operation, and the card is back.

Red before the move: the exit does not exist.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
FOLDER = next(row for row in json.loads((SEEDS / "stuck-loaded.json").read_text(encoding="utf-8"))
              if row.get("ids") is None and "Backrooms" in row["title"])["title"]
DESTINATIONS = [row["name"] for row in json.loads((SEEDS / "staging-destinations.json").read_text(encoding="utf-8"))]
CHOSEN = DESTINATIONS[-1]

ANSWERED = """(operation) => (window.__mocks?.answered() || [])
  .filter(call => call.operationId === operation && call.status === 200)
  .map(call => decodeURIComponent(call.path))"""
TITLES = """() => [...document.querySelectorAll('#view [data-part="card/title"]')].map(one => one.textContent)"""
WHERE = """() => ({
  selected: document.querySelector('[data-acqtab][aria-selected="true"]')?.dataset.acqtab ?? null,
  screen: !!document.querySelector('[data-part="screen"][data-open]'),
})"""
CHOICES = """() => { const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return null;
  return [...sheet.querySelectorAll('[data-part="sheet/action"][data-reclassify]')]
    .map(one => ({ text: one.textContent.trim(), target: one.getAttribute('data-reclassify') })); }"""


async def tab(page, value):
    """Taps one of Acquisition's tabs and reads the titles it draws, folds included."""
    await page.evaluate(f"()=>document.querySelector('[data-acqtab=\"{value}\"]')?.click()")
    await page.wait_for_timeout(ACTED)
    return await page.evaluate(TITLES)


async def main():
    journal = Journal("R228 — « Ce n'est pas un média » reclassifies the folder")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-todo-dense');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-todo-dense exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        journal.check("the folder is on « À traiter »", FOLDER in await page.evaluate(TITLES), FOLDER)

        # ── by finger: « Résoudre → », then « Ce n'est pas un média » ────────
        await page.evaluate("""(title)=>[...document.querySelectorAll('#view [data-part="card/foot"]')]
            .find(one => one.getAttribute('data-resolution') === title)?.click()""", FOLDER)
        await page.wait_for_timeout(ACTED)
        exit_ = await page.evaluate(
            "()=>{const exit=document.querySelector('[data-not-media]'); if(!exit) return false; exit.click(); return true;}")
        await page.wait_for_timeout(ACTED)
        choices = await page.evaluate(CHOICES)
        journal.check("« Ce n'est pas un média » opens a choice of the configuration's destinations",
                      exit_ and choices is not None and [one["text"] for one in choices] == DESTINATIONS,
                      f"exit {exit_}, {choices} — wanted {DESTINATIONS}")

        # ── a destination tapped ──────────────────────────────────────────
        before = await page.evaluate(ANSWERED, "reclassifyStagedMedia")
        await page.evaluate("""(chosen)=>[...document.querySelectorAll('#sheet [data-part="sheet/action"][data-reclassify]')]
            .find(one => one.getAttribute('data-reclassify').endsWith('|' + chosen))?.click()""", CHOSEN)
        await page.wait_for_timeout(SETTLED)
        after = await page.evaluate(ANSWERED, "reclassifyStagedMedia")
        sent = after[len(before):]
        toast = await page.evaluate("()=>(document.querySelector('#toast')?.textContent || '').trim()")
        journal.check("the reclassification is answered, and the message says the destination",
                      len(sent) == 1 and FOLDER in sent[0] and f"« {CHOSEN} »" in toast,
                      f"{sent}, {toast!r}")
        where = await page.evaluate(WHERE)
        journal.check("and the operator is back on « À traiter », no screen left",
                      where["selected"] == "todo" and not where["screen"], str(where))
        todo = await page.evaluate(TITLES)
        now = await tab(page, "now")
        journal.check("the card is in neither « À traiter » nor « En cours »",
                      FOLDER not in todo and FOLDER not in now, f"todo {todo}, now {now}")

        # ── « Annuler »: the inverse ──────────────────────────────────────
        await tab(page, "todo")
        undone_before = len(await page.evaluate(ANSWERED, "restoreReclassifiedMedia"))
        undo = await page.evaluate("()=>{const undo=document.querySelector('#toastundo'); if(!undo) return false; undo.click(); return true;}")
        await page.wait_for_timeout(SETTLED)
        undone = len(await page.evaluate(ANSWERED, "restoreReclassifiedMedia")) - undone_before
        journal.check("« Annuler » is answered by the inverse, and the card is back",
                      undo and undone == 1 and FOLDER in await page.evaluate(TITLES),
                      f"undo {undo}, inverse answered {undone}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
