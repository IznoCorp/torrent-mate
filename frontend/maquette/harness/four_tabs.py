"""R206 — Acquisition's tabs fit a phone, in their order.

RE-AIMED OUT LOUD: « Découvrir » left Acquisition for a page of the bottom bar,
so the tabs are THREE — « Suivis » · « En cours » · « À traiter » — and every
hold below reads the three. The file keeps its name; its subject is the tabs.

« À traiter » is a fourth tab of Acquisition (ruling 10), and the four read
« Suivis » · « En cours » · « À traiter » · « Découvrir » — the operator's own
order. Four labels and their counts in a segmented control at 390 px is the
cost the ruling accepted, and this is where it is paid:

1. no label is TRUNCATED. The segment cuts a label too long for its share with
   an ellipsis and never overflows, so a page-overflow test would pass over a
   cut label; each label is read on its own box (`scrollWidth ≤ clientWidth`);
2. the control itself does not overflow, and the « ⋮ » beside it stays on the
   screen;
3. every tab and the « ⋮ » meet the touch minimum — 44 px, the floor the harness
   holds locally (`add_footer.py`), not a written directive. The segment itself
   is 34 px tall where the library wears it; Acquisition's bar is lifted;
4. the three are in the DOM in the ruled order, each under its own words.

Read where the bar is empty of counts and where it carries them, at 390 px and
at 369 px — the narrowest phone the operator's screenshot measured — and, on the
dense bar, with every tab's count at three digits, the longest a count plausibly
reaches (the follows of a whole library run to hundreds):

5. with its count lit and at three digits, every counted tab (« En cours »,
   « À traiter ») keeps its label whole and its count badge inside its own box —
   never clipped by the tab's edge.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))["screens"]["acquisition"]
# The ruled order, by the tab values the markup carries and the keys of their words.
ORDER = [("follows", "tabFollows"), ("now", "tabNow"), ("todo", "tabTodo")]
TOUCH_TARGET = 44
PHONE_WIDTHS = (390, 369)
PHONE_HEIGHT = 844
# The longest count a tab plausibly carries, and the tabs that carry one:
# « Suivis » draws no count, « En cours » counts what moves and « À traiter »
# its cards.
LONGEST_COUNT = "999"
COUNTED = ("now", "todo")

BAR = """() => {
  const control = document.querySelector('[data-region="acquisition/tabs"] [data-part="segment"]');
  const more = document.querySelector('[data-region="acquisition/tabs"] [data-more]');
  const box = element => element.getBoundingClientRect();
  return {
    control: control ? {overflow: control.scrollWidth > control.clientWidth + 1} : null,
    more: more ? {right: box(more).right, width: box(more).width, height: box(more).height} : null,
    tabs: [...document.querySelectorAll('[data-region="acquisition/tabs"] [data-acqtab]')].map(tab => {
      const count = tab.querySelector('[data-part="segment/count"]');
      return {
        value: tab.dataset.acqtab,
        text: tab.textContent,
        cut: tab.scrollWidth > tab.clientWidth + 1,
        width: box(tab).width,
        height: box(tab).height,
        count: count ? {text: count.textContent, cut: count.scrollWidth > count.clientWidth + 1,
                        inside: box(count).left >= box(tab).left - 0.5 && box(count).right <= box(tab).right + 0.5}
                     : null,
      };
    }),
  };
}"""


async def read_the_bar(journal, page, where, width):
    """Holds the bar's order, its whole labels, its overflow and its targets.

    Args:
        journal: The rule's journal.
        page: The Playwright page, on Acquisition.
        where: The state and width, as the holds name them.
        width: The viewport's width, which « ⋮ » must stay inside.

    Returns:
        The bar as `BAR` read it.
    """
    bar = await page.evaluate(BAR)
    tabs = bar["tabs"]
    journal.check(
        f"{where}: the three tabs read « Suivis · En cours · À traiter »",
        [tab["value"] for tab in tabs] == [value for value, _ in ORDER]
        and all(tab["text"].startswith(WORDS.get(key, "\0"))
                for tab, (_, key) in zip(tabs, ORDER)),
        str([(tab["value"], tab["text"]) for tab in tabs]))
    journal.check(f"{where}: no label is truncated",
                  bool(tabs) and not any(tab["cut"] for tab in tabs),
                  str([(tab["value"], tab["cut"]) for tab in tabs]))
    journal.check(f"{where}: the control does not overflow, and « ⋮ » stays on the screen",
                  bar["control"] is not None and not bar["control"]["overflow"]
                  and bar["more"] is not None and bar["more"]["right"] <= width,
                  str(bar["control"]) + " " + str(bar["more"]))
    targets = tabs + ([bar["more"]] if bar["more"] else [])
    journal.check(f"{where}: every tab and « ⋮ » meet the touch minimum",
                  bool(tabs) and all(target["height"] >= TOUCH_TARGET
                                     and target["width"] >= TOUCH_TARGET for target in targets),
                  str([(round(target["width"]), round(target["height"])) for target in targets]))
    return bar


async def main():
    journal = Journal("R206 — Acquisition's tabs at 390 and 369 px, in their order")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for width in PHONE_WIDTHS:
            await page.set_viewport_size({"width": width, "height": PHONE_HEIGHT})
            for state in ("acq-todo-empty", "acq-now-loaded"):
                answer = await page.evaluate(
                    "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
                journal.check(f"the named state {state} exists", answer is None, answer or "")
                await page.wait_for_timeout(SETTLED)
                await read_the_bar(journal, page, f"{state} at {width} px", width)
            # The dense bar again, every count at the longest a count plausibly
            # reaches: the widest the three tabs and their badges are ever asked
            # to be.
            await page.evaluate(
                """(longest) => document.querySelectorAll(
                     '[data-region="acquisition/tabs"] [data-part="segment/count"]')
                     .forEach((count) => { count.textContent = longest; })""", LONGEST_COUNT)
            bar = await read_the_bar(journal, page, f"acq-now-loaded, counts at {LONGEST_COUNT}, at {width} px", width)
            counted = [tab for tab in bar["tabs"] if tab["count"] is not None]
            journal.check(f"at {width} px, the counted tabs' counts are lit, at three digits, each inside its own tab",
                          [tab["value"] for tab in counted] == list(COUNTED)
                          and all(tab["count"]["text"] == LONGEST_COUNT and not tab["count"]["cut"]
                                  and tab["count"]["inside"] for tab in counted),
                          str([(tab["value"], tab["count"]) for tab in bar["tabs"]]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
