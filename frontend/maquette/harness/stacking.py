"""R101 — the frame's layers paint in ONE ranked order, and the top one is reachable.

WHAT WENT WRONG, AND WHAT NOBODY COULD SEE. `.dlg` was `z-index: 48` and the tab
bar `z-50`, both children of `.device` — so a delete confirmation opened with
four TAPPABLE tabs painted over its lower edge, on an element declaring
`aria-modal="true"` (B-237). Nothing here could see it: the oracle measures
nineteen computed properties and no stacking one, a rectangle carries no paint
order, and the accessibility tier reads the background as `inert` — so the bar
was inert AND on top, which is the worst of both.

WHY THIS RULE HIT-TESTS RATHER THAN COMPARING TWO NUMBERS. Reading `z-index`
from two elements and comparing them is a table written beside the code: it says
nothing when the two sit in different stacking contexts, and everything about
this defect turns on their sharing one. `elementFromPoint` asks the browser what
a finger would reach, which is the question.

AND ONE HALF OF B-237'S TEXT IS CORRECTED HERE RATHER THAN REPEATED. The entry
says « the bar's four buttons stay tappable over a modal that says
`aria-modal="true"` ». Measured on the served copy: they are not tappable.
`app/focus.ts` marks the whole background `inert` while a layer is open — `#nav`
among the thirteen elements it names — and `inert` takes an element out of
hit-testing as well as out of the focus order. What was really wrong is what
this rule holds: the bar was PAINTED over a modal wherever the two met, which
is a defect a reader sees and a finger cannot report.

WHAT IT DOES NOT READ. It holds the layers the FRAME paints — the confirmation,
the drawer, the message, the selection bar — against the tab bar and against
each other. It says nothing about a surface's own internal stacking, and nothing
about a layer that declares no rank at all: an element with `z-index: auto` is
ordered by the document, and this rule would report it reachable or not without
being able to say why.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

# What a finger reaches at a point, named by the nearest layer it belongs to.
AT = """([selector, fraction]) => {
  const node = document.querySelector(selector);
  if (!node) return {absent: true};
  const box = node.getBoundingClientRect();
  const x = box.x + box.width / 2;
  const y = box.y + box.height * fraction;
  const hit = document.elementFromPoint(x, y);
  if (!hit) return {nothing: true};
  const owner = hit.closest('#dlg, #drawer, #nav, #toast, [data-part="selection/bar"], #sheet');
  return {
    inside: node.contains(hit) || node === hit,
    owner: owner ? (owner.id || owner.dataset.part) : hit.tagName,
    box: [Math.round(box.x), Math.round(box.y), Math.round(box.width), Math.round(box.height)],
  };
}"""


async def main():
    journal = Journal("R101 — one ranked order, and the top layer answers the finger")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # THE BAR IS REALLY THERE AND REALLY ON TOP OF THE PAGE, so the holds
        # below are not passing over an element that is simply absent.
        await page.evaluate("()=>window.__go('lib-list')")
        await page.wait_for_timeout(300)
        bar = await page.evaluate(AT, ['#nav', 0.5])
        journal.check(
            "the tab bar is on screen and answers a finger — the subject exists",
            bar.get("owner") == "nav",
            str(bar))

        # (a) THE CONFIRMATION OVER THE BAR — AND THE OVERLAP IS MADE, not
        # assumed. Measured at 390 x 844: the two delete confirmations the
        # named states raise are 184–660 and 142–702, and the bar is 787–844.
        # THEY DO NOT TOUCH. A hold that opened one of them and hit-tested its
        # own rectangle would have passed at `z-48` exactly as it passes at
        # `z-56` — a reading that cannot come out the other way, which is what
        # this rule exists not to be.
        #
        # So the overlap is produced: a manifest long enough that the dialog
        # reaches past the bar's top edge, opened through the layer's own verb
        # with a real descriptor. That is the case a delete of thirty items
        # makes on a real phone, and it is where the rank decides what is
        # painted.
        await page.evaluate("()=>window.__go('lib-list')")
        await page.evaluate("""()=>window.__dialog.open({
          heading: 'probe',
          body: [{type: 'manifest', entries: Array.from({length: 40},
            (_, n) => ({text: 'ligne ' + n, value: String(n)}))}],
          actions: [{text: 'Annuler', dismiss: true}]})""")
        await page.wait_for_timeout(400)
        overlapping = await page.evaluate("""()=>{
          const dialog = document.querySelector('#dlg').getBoundingClientRect();
          const bar = document.querySelector('#nav').getBoundingClientRect();
          const hit = document.elementFromPoint(bar.x + bar.width / 2, bar.y + 4);
          return {overlap: dialog.bottom > bar.top,
                  dialog: [Math.round(dialog.y), Math.round(dialog.bottom)],
                  bar: Math.round(bar.y),
                  at: hit ? (hit.closest('#dlg') ? 'dlg'
                             : hit.closest('#nav') ? 'nav' : hit.tagName) : null};}""")
        journal.check(
            "the overlap this hold needs really exists — otherwise it measures "
            "nothing",
            overlapping["overlap"],
            f"dialog {overlapping['dialog']}, bar top {overlapping['bar']}")

        # AND THE HIT-TEST CANNOT SEE IT WHILE THE BAR IS `inert`. That was the
        # second version of this hold and it was vacuous for a reason worth
        # writing down: `app/focus.ts` marks the whole background `inert` while
        # a layer is open, and `inert` takes an element out of HIT-TESTING as
        # well as out of the focus order — so `elementFromPoint` answered the
        # dialog at `z-48` exactly as it does at `z-56`, and the hold passed
        # over the defect it was written for.
        #
        # WHAT IS REALLY WRONG IS THE PAINT, and the paint is what is measured:
        # the bar's `inert` is lifted for the length of one reading and put
        # back. The browser then answers the question a reader's eye asks —
        # which of the two is on top where they meet.
        painted = await page.evaluate("""()=>{
          const bar = document.querySelector('#nav');
          const was = bar.hasAttribute('inert');
          bar.removeAttribute('inert');
          const box = bar.getBoundingClientRect();
          const hit = document.elementFromPoint(box.x + box.width / 2, box.y + 4);
          if (was) bar.setAttribute('inert', '');
          return {lifted: was,
                  at: hit ? (hit.closest('#dlg') ? 'dlg'
                             : hit.closest('#nav') ? 'nav' : hit.tagName) : null,
                  dialogRank: getComputedStyle(document.querySelector('#dlg')).zIndex,
                  barRank: getComputedStyle(bar).zIndex,
                  sameParent: bar.parentElement
                    === document.querySelector('#dlg').parentElement};}""")
        journal.check(
            "the two are ranked in ONE stacking context, so their numbers are "
            "comparable at all",
            painted["sameParent"],
            f"dialog {painted['dialogRank']}, bar {painted['barRank']}, "
            f"same parent: {painted['sameParent']}")
        journal.check(
            "where a confirmation and the tab bar overlap, the confirmation is "
            "PAINTED on top (B-237)",
            painted["at"] == "dlg",
            str(painted))
        await page.evaluate("()=>window.__dialog.close()")
        await page.wait_for_timeout(250)

        # (b) AND OVER THE SELECTION BAR, which is the bar a delete confirmation
        # is usually opened FROM: 51 against the dialog's 56. Here the two DO
        # overlap without help — the selection bar is at the bottom and the
        # confirmation is 560 pixels tall.
        # The same `inert` lift, for the same reason: with a dialog open the
        # selection bar is background too, so a plain hit-test could not tell
        # 51 from 56 either.
        # `lib-selection` and NOT `lib-delete-multiple`: the second opens the
        # confirmation with three titles and enables no selection mode at all,
        # so the bar this hold is about is not on screen in it. Measured, after
        # the hold reported « absent » — a premise nobody had checked.
        await page.evaluate("()=>window.__go('lib-selection')")
        await page.wait_for_timeout(350)
        await page.evaluate("""()=>window.__dialog.open({
          heading: 'probe',
          body: [{type: 'manifest', entries: Array.from({length: 40},
            (_, n) => ({text: 'ligne ' + n, value: String(n)}))}],
          actions: [{text: 'Annuler', dismiss: true}]})""")
        await page.wait_for_timeout(450)
        over_selection = await page.evaluate("""()=>{
          const bar = document.querySelector('[data-part="selection/bar"]');
          if (!bar) return {absent: true};
          const dialog = document.querySelector('#dlg').getBoundingClientRect();
          const box = bar.getBoundingClientRect();
          if (dialog.bottom <= box.top) return {noOverlap: true};
          const was = bar.hasAttribute('inert');
          bar.removeAttribute('inert');
          const hit = document.elementFromPoint(box.x + box.width / 2, box.y + 4);
          if (was) bar.setAttribute('inert', '');
          return {at: hit ? (hit.closest('#dlg') ? 'dlg'
                             : hit.closest('[data-part="selection/bar"]') ? 'selbar'
                             : hit.tagName) : null};}""")
        journal.check(
            "and PAINTED over the selection bar it was opened from",
            over_selection.get("at") == "dlg",
            str(over_selection))

        # (c) THE DRAWER, which was already above the bar and must stay there.
        await page.evaluate("()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(400)
        drawer_hit = await page.evaluate(AT, ['#drawer', 0.95])
        journal.check(
            "the drawer answers the finger at its lower edge too",
            drawer_hit.get("owner") == "drawer",
            str(drawer_hit))

        # (d) AND THE ONE THAT IS DELIBERATELY UNDER THE BAR: the message sits
        # ABOVE the bar's height rather than over the bar itself (z-49 against
        # 50), and that is the arrangement `--tm-bottom-bar-h` exists for. The
        # hold states it so a future change that lifts the message reads as a
        # decision rather than as a repair.
        await page.evaluate("()=>window.__go('lib-list')")
        await page.evaluate("()=>window.__toast.show({message: 'probe'})")
        await page.wait_for_timeout(350)
        message_hit = await page.evaluate(AT, ['#toast', 0.5])
        journal.check(
            "the message clears the bar rather than painting over it",
            message_hit.get("owner") == "toast",
            str(message_hit))

        # (d-bis) THE BOTTOM SHEET PAINTS OVER THE TAB BAR (B-248, P31).
        # Dictated by the operator on 2026-08-30 from a screenshot: while a
        # bottom layer is open the bar is not seen. It used to be z-47 under the
        # bar's z-50, so it rose BEHIND the chrome and reserved the bar's height
        # in its own body so its last action stayed reachable.
        #
        # THE ANCHORING IS NOT WHAT MOVED, and the hold says so by reading it:
        # the sheet still rises from the screen's bottom edge, so the overlap
        # with the bar is there by construction and needs no producing — which
        # is the one thing this hold has that the confirmation's did not. What
        # it DOES need is the same `inert` lift: the bar is background while a
        # layer is open, and `inert` takes an element out of hit-testing, so a
        # plain reading answers the sheet at 47 exactly as at 52.
        await page.evaluate("()=>window.__go('sheet-user')")
        await page.wait_for_timeout(500)
        over_bar = await page.evaluate("""()=>{
          const sheet = document.querySelector('#sheet');
          const bar = document.querySelector('#nav');
          if (!sheet || !bar) return {absent: true};
          const sheetBox = sheet.getBoundingClientRect();
          const barBox = bar.getBoundingClientRect();
          const was = bar.hasAttribute('inert');
          bar.removeAttribute('inert');
          const hit = document.elementFromPoint(
            barBox.x + barBox.width / 2, barBox.y + 4);
          if (was) bar.setAttribute('inert', '');
          return {
            anchored: Math.round(sheetBox.bottom) === Math.round(barBox.bottom),
            overlap: sheetBox.bottom > barBox.top,
            at: hit ? (hit.closest('#sheet') ? 'sheet'
                       : hit.closest('#nav') ? 'nav' : hit.tagName) : null,
            sheetRank: getComputedStyle(sheet).zIndex,
            barRank: getComputedStyle(bar).zIndex};}""")
        journal.check(
            "the sheet is anchored on the screen's bottom edge, so it overlaps "
            "the bar by construction",
            over_bar.get("anchored") and over_bar.get("overlap"),
            str({k: over_bar.get(k) for k in ("anchored", "overlap")}))
        journal.check(
            "and it is PAINTED over the tab bar (B-248, P31)",
            over_bar.get("at") == "sheet",
            str(over_bar))
        # AND NOTHING RESERVES THE BAR'S HEIGHT ANY MORE. The padding that
        # compensated the overlap goes with the rank; left behind it would be a
        # blank strip inside every sheet, which is a defect no hit-test sees.
        reserved = await page.evaluate("""()=>{
          const inner = document.querySelector('#sheetin');
          return inner ? getComputedStyle(inner).paddingBottom : null;}""")
        journal.check(
            "and the sheet's body reserves no bar height",
            reserved is not None and float(reserved.replace("px", "")) < 40,
            f"padding-bottom {reserved}")
        await page.evaluate("()=>window.__closeLayers?.()")
        await page.wait_for_timeout(300)

        # (e) THE POPOVER STAYS INSIDE THE FRAME, on both edges. That clamp is
        # the whole of what this layer does that a tooltip does not, and it is
        # measured against `#device` rather than against the window: a 390px
        # frame on a desktop is CENTRED, so a clamp written against the viewport
        # would let the popover leave the device on the left and still pass.
        await page.evaluate("()=>window.__go('followsheet-gaps')")
        await page.wait_for_timeout(500)
        cells = await page.evaluate(
            """()=>document.querySelectorAll('[data-part="episode"]').length""")
        journal.check(
            "an episode matrix is on screen, so the clamp has a subject",
            cells > 2, f"{cells} episode cell(s)")
        # THE LEFTMOST AND THE RIGHTMOST CELL, not the first and the last: a
        # matrix wraps, so its last cell can sit in the left column and both
        # readings would exercise the same clamp. Chosen by x, so each edge is
        # really met — which the first version of this hold did not do, and it
        # reported the same placement twice.
        placements = []
        for edge in ("left", "right"):
            await page.evaluate(
                """(edge)=>{const cells=[...document.querySelectorAll('[data-part="episode"]')];
                   const sorted = cells.slice().sort((a, b) =>
                     a.getBoundingClientRect().left - b.getBoundingClientRect().left);
                   (edge === 'left' ? sorted[0] : sorted[sorted.length - 1]).click();}""",
                edge)
            await page.wait_for_timeout(300)
            placements.append(await page.evaluate("""()=>{
              const layer = document.querySelector('[data-part="episode/popover"]');
              if (!layer) return {absent: true};
              const box = layer.getBoundingClientRect();
              const frame = document.querySelector('#device').getBoundingClientRect();
              return {left: Math.round(box.left - frame.left),
                      right: Math.round(frame.right - box.right),
                      shown: getComputedStyle(layer).visibility};}"""))
        journal.check(
            "a popover opened at either end of the matrix stays inside the frame",
            all(not p.get("absent") and p["left"] >= 0 and p["right"] >= 0
                and p["shown"] == "visible" for p in placements),
            str(placements))

        await context.close()
        await browser.close()
    journal.summary(errors)


asyncio.run(main())
