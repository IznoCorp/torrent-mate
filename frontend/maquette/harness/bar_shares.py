"""R232 — the bottom bar draws only the buttons it has, each at 1/n of its width.

A FRAME RULE, the operator's words: « la barre du bas s'adapte toujours au nombre de
boutons présents, chaque bouton prend toujours le même ratio » — 2 buttons at
1/2, 3 at 1/3, 4 at 1/4; 4 at most, 2 at least, never an empty slot. And ONE
page means NO bar at all, the operator ruled: a count of one
is read as the bar's absence, never as a button the bar's full width.

On every state read, at the count the table gives it (its `inBar` rows, read off
the table's own source):

1. the count is between 2 and 4 — or, at one, no bar is drawn;
2. each button is 1/n of the bar's inner width, within a pixel;
3. the buttons tile that width whole, edge to edge — no empty slot.

WRITTEN GREEN, and said so: the bar already shares its width equally
(`tabBarButton` is `flex-1 basis-0`); this rule is the guard the next edit to
that variant would otherwise lose silently. Its proof is its mutations.
"""
import asyncio
import pathlib
import re

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TABLE = (SOURCE / "app/navigation.ts").read_text(encoding="utf-8")
IN_BAR = [identifier for identifier, flag
          in re.findall(r'\bid: "([^"]+)",.*?\binBar: (true|false)', TABLE, re.S) if flag == "true"]
STATES = ("acq-todo-loaded", "acq-todo-empty", "drawer-navigation")
PIXEL = 1

MEASURE = """() => {
  const bar = document.querySelector('#nav');
  if (!bar || !bar.checkVisibility()) return null;
  const style = getComputedStyle(bar);
  const box = bar.getBoundingClientRect();
  const left = box.left + parseFloat(style.paddingLeft) + parseFloat(style.borderLeftWidth);
  const width = bar.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  return { left, width, buttons: [...bar.querySelectorAll('button[data-page]')]
    .map(button => { const one = button.getBoundingClientRect(); return { left: one.left, width: one.width }; }) };
}"""


async def main():
    journal = Journal("R232 — the bar draws its buttons at 1/n, 2 to 4, no empty slot")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        count = len(IN_BAR)
        journal.check("the table gives the bar between 1 and 4 places", 1 <= count <= 4, str(IN_BAR))
        for state in STATES:
            answer = await page.evaluate(
                "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            await page.wait_for_timeout(SETTLED)
            bar = await page.evaluate(MEASURE)
            if count == 1:
                journal.check(f"{state}: one page draws no bar at all",
                              bar is None or not bar["buttons"], str(bar))
                continue
            drawn = len(bar["buttons"]) if bar else 0
            journal.check(f"{state}: the bar draws its {count} buttons, 2 to 4",
                          bar is not None and drawn == count and 2 <= drawn <= 4, f"{drawn} drawn")
            if not bar or drawn != count:
                continue
            share = bar["width"] / count
            off = [round(one["width"], 1) for one in bar["buttons"] if abs(one["width"] - share) > PIXEL]
            journal.check(f"{state}: each button is 1/{count} of the bar", not off,
                          f"share {share:.1f}, off {off}")
            edges = [bar["left"]] + [one["left"] + one["width"] for one in bar["buttons"]]
            starts = [one["left"] for one in bar["buttons"]]
            gaps = [round(start - edge, 1) for start, edge in zip(starts, edges) if abs(start - edge) > PIXEL]
            end = abs(edges[-1] - (bar["left"] + bar["width"]))
            journal.check(f"{state}: the buttons tile the bar whole — no empty slot",
                          not gaps and end <= PIXEL, f"gaps {gaps}, short by {end:.1f}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
