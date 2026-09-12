"""R156 — a follow without a media sheet is refused.

THE RULING THIS HOLDS is the operator's, and it is about what the product may
represent rather than about how a tile draws: « il ne doit pas y avoir de suivi
sans fiche, si on a un suivi c'est qu'on a identifié le média, si on a
identifié le média alors on peut afficher sa fiche, le suivi sans fiche n'est
pas un état possible ».

So this is not a guard on a poster. Following a title IS having identified the
medium, and an identified medium has a sheet; a followed title that resolves to
no sheet is a state the product does not have, and this rule refuses it wherever
it appears.

IT ASKS THE PAGE'S OWN RESOLVER, and that is the whole of its correctness. The
lookup is not an equality on titles: it falls back to the base title, then to a
normalised key, then to a prefix match for a title a list truncated. A rule that
re-implemented any of that in Python would be a second source of truth for the
question it is asking, and would go green or red on its own arithmetic — the
first version of this check did exactly that and reported a sheetless follow
that resolves perfectly well through the real lookup.

WHAT IS NOT THIS DEFECT, and must not be folded into it: a follow with no
EPISODE data. A show whose provider offers no episode listing is identified, has
a sheet, and is followed on purpose. « No sheet » and « no episodes » are two
different absences, and a rule that conflated them would refuse a state the
product needs.

WHAT IT DOES NOT CLAIM. Refusing the state is not the same as making it
unrepresentable. The contract can still describe a follow with no sheet, and
until it cannot, this rule is the thing standing between that description and
the interface.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE FOLLOWS ARE DRAWN, so the list this rule reads is the one the
# interface has, not a file's idea of it.
FOLLOWS_STATE = "acq-follows-list"

# EVERY FOLLOW, AGAINST THE RESOLVER THE DRAWING ITSELF USES. `sheetFor` is
# published on the drawing seam and is the function the tile calls to decide
# whether it may offer a poster at all.
FOLLOWS_AND_SHEETS = """()=>{
  const all = (window.__followActions?.all?.() || []).map((one) => one.t);
  const sheetFor = window.__referentiel?.sheetFor;
  if (typeof sheetFor !== 'function') return {resolver: false, all, without: []};
  return {resolver: true, all,
          without: all.filter((title) => sheetFor(title) == null)};}"""


async def main():
    journal = Journal("R156 — a follow without a media sheet is refused")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        seen = await page.evaluate(FOLLOWS_AND_SHEETS)

        journal.check(
            "the drawing's own sheet resolver is reachable — a rule that could "
            "not call it would have to re-implement a lookup with three "
            "fallbacks, and would then be measuring its own arithmetic",
            seen["resolver"], str(seen["resolver"]))

        journal.check(
            "and there are follows to ask about — an empty list would make the "
            "hold below green over nothing",
            len(seen["all"]) > 0, f"{len(seen['all'])} follow(s)")

        journal.check(
            "every followed title resolves to a media sheet: a follow means "
            "the medium was identified, and an identified medium has a sheet",
            seen["resolver"] and bool(seen["all"]) and not seen["without"],
            str(seen["without"][:5]))

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
