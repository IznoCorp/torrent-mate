"""R206 — Acquisition's four tabs fit a phone, in their order.

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
4. the four are in the DOM in the ruled order, each under its own words.

Read where the bar is empty of counts and where it carries them.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))["screens"]["acquisition"]
# The ruled order, by the tab values the markup carries and the keys of their words.
ORDER = [("follows", "tabFollows"), ("now", "tabNow"), ("todo", "tabTodo"), ("discover", "tabDiscover")]
TOUCH_TARGET = 44
PHONE_WIDTH = 390

BAR = """() => {
  const control = document.querySelector('[data-region="acquisition/tabs"] [data-part="segment"]');
  const more = document.querySelector('[data-region="acquisition/tabs"] [data-more]');
  const box = element => element.getBoundingClientRect();
  return {
    control: control ? {overflow: control.scrollWidth > control.clientWidth + 1} : null,
    more: more ? {right: box(more).right, width: box(more).width, height: box(more).height} : null,
    tabs: [...document.querySelectorAll('[data-region="acquisition/tabs"] [data-acqtab]')].map(tab => ({
      value: tab.dataset.acqtab,
      text: tab.textContent,
      cut: tab.scrollWidth > tab.clientWidth + 1,
      width: box(tab).width,
      height: box(tab).height,
    })),
  };
}"""


async def main():
    journal = Journal("R206 — four tabs at 390 px, in their order")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state in ("acq-todo-empty", "acq-now-loaded"):
            answer = await page.evaluate(
                "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            await page.wait_for_timeout(SETTLED)
            bar = await page.evaluate(BAR)
            tabs = bar["tabs"]
            journal.check(
                f"{state}: the four tabs read « Suivis · En cours · À traiter · Découvrir »",
                [tab["value"] for tab in tabs] == [value for value, _ in ORDER]
                and all(tab["text"].startswith(WORDS.get(key, "\0"))
                        for tab, (_, key) in zip(tabs, ORDER)),
                str([(tab["value"], tab["text"]) for tab in tabs]))
            journal.check(f"{state}: no label is truncated",
                          bool(tabs) and not any(tab["cut"] for tab in tabs),
                          str([(tab["value"], tab["cut"]) for tab in tabs]))
            journal.check(f"{state}: the control does not overflow, and « ⋮ » stays on the screen",
                          bar["control"] is not None and not bar["control"]["overflow"]
                          and bar["more"] is not None and bar["more"]["right"] <= PHONE_WIDTH,
                          str(bar["control"]) + " " + str(bar["more"]))
            targets = tabs + ([bar["more"]] if bar["more"] else [])
            journal.check(f"{state}: every tab and « ⋮ » meet the touch minimum",
                          bool(tabs) and all(target["height"] >= TOUCH_TARGET
                                             and target["width"] >= TOUCH_TARGET for target in targets),
                          str([(round(target["width"]), round(target["height"])) for target in targets]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
