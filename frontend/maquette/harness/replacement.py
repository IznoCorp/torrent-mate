"""R121 — DOIT-8: a medium the library already owns is never replaced in silence.

THE CLAUSE. « confirmation avant remplacement d'un film déjà en médiathèque ».
`product-intent-map.md` reads it `served, unproved` and names L19 as owing the
instrument: the confirmation exists — it was ONE line of the engine's add
handler — and **no rule walked « add a film the library owns » and read it**.

WHY THAT MATTERS MORE THAN THE USUAL. A confirmation nobody measures is a
confirmation one refactor away from being a `return`, and the act it guards
overwrites a file the operator already has. The engine's own branch is three
lines from the one that adds without asking.

THREE THINGS ARE READ, and each fails differently:

  1. THE PANEL SAYS IT BEFORE THE ACT IS TAPPED. A result the library owns is
     announced as a REPLACEMENT in the panel that offers the act, so the
     decision is taken with the fact in view rather than after it.
  2. THE ACT RAISES A CONFIRMATION, and the confirmation says « remplacera ».
     It is read as a DIALOG — `#dlg[data-open]` — and not as a toast: a message
     that appears after the fact is not consent.
  3. CANCELLING LEAVES THE MEDIUM UNADDED. This is the half a cheaper rule
     skips, and it is the half that separates a confirmation from a delay.

AND THE OTHER SIDE OF THE SAME CLAUSE: a result the library does NOT own is
added with no dialog at all. A rule that only read the owned case would pass a
build that asked « are you sure? » about everything, which is the shape that
teaches an operator to tap through without reading.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright


# WHICH RESULT THE LIBRARY OWNS, read from the layer's own answer rather than
# named here: a title written into this file goes stale the day the fixture
# changes, and the rule would then walk a result that is not owned and pass for
# the wrong reason.
OWNED_AT = """()=>{
  const answered = window.__searchResults();
  const at = answered.results.findIndex((r) => r.owned);
  const free = answered.results.findIndex((r) => !r.owned);
  return {owned: at, free, total: answered.results.length};}"""

DIALOG = """()=>{
  const dialog = document.querySelector('#dlg');
  if (!dialog || !dialog.hasAttribute('data-open')) return null;
  return {text: dialog.textContent.replace(/\\s+/g, ' ').trim(),
          actions: [...dialog.querySelectorAll('button')].map(
            (b) => b.textContent.trim())};}"""


async def main():
    journal = Journal("R121 — DOIT-8: nothing is replaced in silence")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("()=>window.__go('acq-add-results')")
        await page.wait_for_timeout(700)
        where = await page.evaluate(OWNED_AT)
        journal.check(
            "the search really answers a result the library OWNS and one it "
            "does not, so both halves of the clause have a subject",
            where["owned"] >= 0 and where["free"] >= 0,
            str(where))

        # 1. THE PANEL ANNOUNCES THE REPLACEMENT, before anything is tapped.
        await page.evaluate("(at)=>window.__panel.produce('add', String(at))",
                            where["owned"])
        await page.wait_for_timeout(400)
        announced = await page.evaluate(
            """()=>{const body = document.querySelector('#sheetin');
                    return body ? body.textContent.replace(/\\s+/g,' ') : '';}""")
        journal.check(
            "the panel of a medium the library owns says the acquisition will "
            "REPLACE it (DOIT-8)",
            "remplacera" in announced,
            announced[:160])

        # 2. THE ACT RAISES A CONFIRMATION, and it is a dialog.
        await page.evaluate(
            """()=>{const act = document.querySelector(
                 '#sheetin [data-part="sheet/action"]'); if (act) act.click();}""")
        await page.wait_for_timeout(600)
        dialog = await page.evaluate(DIALOG)
        journal.check(
            "and tapping the act raises a CONFIRMATION, not a message after "
            "the fact (DOIT-8)",
            dialog is not None, str(dialog))
        journal.check(
            "the confirmation says what will happen, in the word the panel used",
            dialog is not None and "remplacera" in dialog["text"],
            (dialog or {}).get("text", "")[:160])
        journal.check(
            "and it offers a way OUT as well as a way through",
            dialog is not None and len(dialog["actions"]) >= 2,
            str((dialog or {}).get("actions")))

        # 3. CANCELLING LEAVES IT UNADDED — the half that separates a
        #    confirmation from a delay.
        before = await page.evaluate(
            "()=>[...window.__store.read().state.added]")
        await page.evaluate(
            """()=>{const out = [...document.querySelectorAll('#dlg button')]
                 .find((b) => !b.dataset.confirmadd); if (out) out.click();}""")
        await page.wait_for_timeout(400)
        after_cancel = await page.evaluate(
            "()=>[...window.__store.read().state.added]")
        journal.check(
            "cancelling leaves the medium UNADDED (DOIT-8)",
            sorted(after_cancel) == sorted(before)
            and where["owned"] not in after_cancel,
            f"{before} → {after_cancel}")

        # AND THE OTHER SIDE: a medium the library does not own is added with no
        # dialog at all. Without this, a build asking « are you sure? » about
        # everything would pass — the shape that teaches tapping through.
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(200)
        await page.evaluate("(at)=>window.__panel.produce('add', String(at))",
                            where["free"])
        await page.wait_for_timeout(400)
        await page.evaluate(
            """()=>{const act = document.querySelector(
                 '#sheetin [data-part="sheet/action"]'); if (act) act.click();}""")
        await page.wait_for_timeout(600)
        free_dialog = await page.evaluate(DIALOG)
        added_after = await page.evaluate(
            "()=>[...window.__store.read().state.added]")
        journal.check(
            "a medium the library does NOT own is added with no confirmation",
            free_dialog is None and where["free"] in added_after,
            f"dialog {free_dialog} · added {added_after}")

        journal.check("no JS error along the walk", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
