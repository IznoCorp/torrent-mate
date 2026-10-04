"""R409 — the title stands alone on line 1, on every card (L24, DOIT-9, § 12).

§ 12's card composition: the title alone on its first line, then the meta
line. `follows.py` PRINTED « title alone » over the first four follow cards and
asserted nothing; this rule holds it over every card of every named state.

WHAT IS READ, for every `data-part="card"` a named state draws, in the view or
in the layer the state opens:

  1. nothing is drawn BESIDE the title — no element of the card's body shares
     the title's line to its right;
  2. the title stands ABOVE the meta line, when the card has one;
  3. the title is never cut: its text fits its box.

RETIRED OUT LOUD: `follows.py`'s « title alone » print, which read four cards and
could not fail.
"""
import asyncio

from common import Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

# How long a state is let settle before its cards are read — `states.py`'s own.
SETTLE = 320

READ = """() => {
  const sheet = document.querySelector('#sheet[data-open]'), dialog = document.querySelector('#dlg[data-open]');
  const route = document.querySelector('[data-part="screen"][data-open][data-key]');
  const root = dialog ?? sheet ?? route ?? document.querySelector('#view');
  const faults = [];
  let cards = 0;
  for (const card of root?.querySelectorAll('[data-part="card"]') ?? []) {
    const title = card.querySelector('[data-part="card/title"]');
    if (!title || title.getClientRects().length === 0) continue;
    cards += 1;
    const box = title.getBoundingClientRect();
    const name = title.textContent.trim().slice(0, 40);
    const beside = [...card.querySelectorAll('*')].filter((other) => {
      if (other === title || title.contains(other) || other.contains(title)) return false;
      if (other.children.length > 0 || other.getClientRects().length === 0) return false;
      const near = other.getBoundingClientRect();
      if (near.width === 0 || near.height === 0) return false;
      return near.left >= box.right - 1 && near.top < box.bottom - 2 && near.bottom > box.top + 2;
    });
    if (beside.length) faults.push(`${name}: beside the title — ${beside[0].dataset.part ?? beside[0].tagName}`);
    const meta = card.querySelector('[data-part="card/meta"]');
    if (meta && meta.getClientRects().length && box.bottom > meta.getBoundingClientRect().top + 0.5)
      faults.push(`${name}: not above its meta line`);
    if (title.scrollWidth > title.clientWidth + 1) faults.push(`${name}: cut`);
  }
  return {cards, faults};
}"""


async def main():
    journal = Journal("R409 — the title stands alone on line 1, on every card")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        states = await page.evaluate("() => window.__states()")
        read = 0
        faults = []
        for state in states:
            await page.evaluate("(id) => window.__go(id)", state)
            await page.wait_for_timeout(SETTLE)
            seen = await page.evaluate(READ)
            read += seen["cards"]
            faults += [f"{state} · {fault}" for fault in seen["faults"]]
        journal.check("cards were read across the named states", read > 100, f"{read} cards, {len(states)} states")
        journal.check("every card: the title alone on its line, above its meta, never cut",
                      faults == [], "\n      ".join(faults[:20]) + (f"\n      … {len(faults)} in all" if faults else ""))
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
