"""R131 — the deck's own verbs, and « Pas intéressé » is reversible.

THE DECK ASKS A QUESTION PER CARD and the answers are its own: follow it, or
drop it. The follow is the acquisition's act and has its own rule; the DROP is
the deck's, because nothing leaves the pile anywhere else.

WHAT MOVES IS THE READER, AND ONLY THE READER. `dismissSug` already lives in
`features/acquisition/discover-feed.ts` — the act, the collapse and the undo are
all there. The dying engine's delegation merely CALLS it, and moving the verb is
moving that call onto the tap registry and deleting the branch.

WHAT IT READS, and each fails differently:

  1. THE DECK OFFERS A CARD THAT HAS NOT ALREADY GONE. Held first: every hold
     below is vacuous over a pile whose cards are all spent.
  2. THE ACTION IS ON A BUTTON A FINGER REACHES, hit-tested at its own centre.
  3. THE CARD LEAVES, AND STAYS GONE ACROSS A RE-RENDER. `sugGone` is what the
     deck consults when it rebuilds, so a card removed from the document and
     absent there is a card that comes back on the next commit — which is a
     defect nobody would see in the moment the gesture is made.
  4. THE UNDO PUTS IT BACK. « Pas intéressé » is reversible on purpose: a quick
     gesture gets it wrong more often than a pressing finger does, and the offer
     to undo is the whole reason the act is allowed to be one tap. A rule that
     read only the removal would be green over a build that dropped the card
     irreversibly.
  5. NO ERROR IS RAISED.

THE UNDO IS PRESSED, not called. Its button is `#toastundo`, an id the message
host has carried since the inventory command — and pressing it is the only way
to read that the offer is actually WIRED to the act rather than merely drawn.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE SUGGESTIONS ARE DRAWN.
DECK_STATE = "acq-discover"

# WHAT THE DECK CONSIDERS SPENT — the positions it consults when it rebuilds.
SPENT = "()=>[...(window.__store?.read().state.sugGone || [])]"

# THE RESERVE, as the deck is drawn from it.
RESERVE = "()=>(window.__suggestions?.() || []).map((one) => ({t: one.t, k: one.k}))"

# THE ACTIONS THE PANEL OFFERS, by LABEL, read off the panel itself.
ACTIONS = """()=>[...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
  .map((one) => (one.textContent || '').trim())"""


async def tap_action(page, word):
    """Taps the panel action whose label carries a word, by a real finger."""
    aim = await page.evaluate("""(word)=>{
        const act = [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
          .find((one) => (one.textContent || '').toLowerCase().includes(word));
        if (!act) return {found: false};
        const box = act.getBoundingClientRect();
        const x = box.left + box.width / 2;
        const y = box.top + box.height / 2;
        const hit = document.elementFromPoint(x, y);
        return {found: true, x, y, label: (act.textContent || '').trim(),
                reachable: !!hit && (hit === act || act.contains(hit)),
                covering: hit === null ? "nothing" : hit.tagName};}""", word)
    if aim.get("found") and aim.get("reachable"):
        await page.touchscreen.tap(aim["x"], aim["y"])
        aim["tapped"] = True
    else:
        aim["tapped"] = False
    return aim


async def main():
    journal = Journal("R131 — the deck's drop, and the undo that makes it safe")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", DECK_STATE)
        await page.wait_for_timeout(SETTLED)

        reserve = await page.evaluate(RESERVE)
        spent_before = await page.evaluate(SPENT)
        position = next((at for at in range(len(reserve))
                         if at not in spent_before), None)
        journal.check(
            "the deck offers a card that has not already gone — without one, "
            "every hold below passes over a gesture that did nothing",
            position is not None,
            f"{len(reserve)} in the reserve, spent {spent_before}")
        if position is None:
            await context.close()
            await browser.close()
            journal.summary()
            return

        await page.evaluate("(at)=>window.__panel.produce('suggestion', String(at))",
                            position)
        await page.wait_for_timeout(PANEL_IN)
        offered = await page.evaluate(ACTIONS)
        journal.check(
            "the suggestion's panel offers « Pas intéressé »",
            any("intéress" in one.lower() for one in offered), str(offered))

        aim = await tap_action(page, "intéress")
        journal.check(
            "and it is on a button a finger reaches, hit-tested at its centre",
            aim["tapped"], str(aim))
        await page.wait_for_timeout(ACTED)

        spent_after = await page.evaluate(SPENT)
        journal.check(
            "the card LEAVES the deck — recorded where the deck consults it, so "
            "a card removed from the document and not from `sugGone` is a card "
            "that comes back on the next commit",
            position in spent_after and position not in spent_before,
            f"{spent_before} → {spent_after}, position {position}")

        # AND IT SURVIVES A RE-RENDER, which is the half a removal alone cannot
        # show: the pile is rebuilt from the reserve, and only `sugGone` keeps
        # the card out of it.
        await page.evaluate("()=>window.__store.touch()")
        await page.wait_for_timeout(SETTLED)
        still_spent = await page.evaluate(SPENT)
        journal.check(
            "and stays gone across a re-render",
            position in still_spent, str(still_spent))

        # ── THE UNDO, PRESSED RATHER THAN CALLED ───────────────────────────
        undo = await page.evaluate("""()=>{
            const one = document.querySelector('#toastundo');
            if (!one) return {found: false};
            const box = one.getBoundingClientRect();
            const x = box.left + box.width / 2;
            const y = box.top + box.height / 2;
            const hit = document.elementFromPoint(x, y);
            return {found: true, x, y,
                    reachable: !!hit && (hit === one || one.contains(hit)),
                    covering: hit === null ? "nothing" : hit.tagName};}""")
        journal.check(
            "the message offers an UNDO, on a button a finger reaches — the "
            "offer is what lets this act be one tap",
            undo.get("found") and undo.get("reachable"), str(undo))
        if undo.get("found") and undo.get("reachable"):
            await page.touchscreen.tap(undo["x"], undo["y"])
            await page.wait_for_timeout(ACTED)
        undone = await page.evaluate(SPENT)
        journal.check(
            "and pressing it puts the card BACK — read on the layer, so an undo "
            "that is drawn and wired to nothing is a failure here",
            position not in undone, f"{still_spent} → {undone}")

        journal.check("and the whole gesture raises no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
