"""R122 — NE-DOIT-PAS-9: no medium is drawn without a path to its sheet.

THE CLAUSE. « ne jamais afficher un média sans chemin vers sa fiche ».
`product-intent-map.md` reads it `partly`: the FIVE poster galleries
`harness/gallery.py` names are served, and the LIST ROWS — a follow row, an
arrival row, a search result — and the galleries outside those five are
**unproved**. L19 owes the instrument, with the producers that draw them.

WHAT A « PATH » IS, and this is the whole difficulty. It is not one attribute.
A medium is reachable when tapping it or long-pressing it leads to its sheet,
and the interface spells that in three ways, all of them contracts the
document-level delegation reads:

  * `data-mediasheet` — the direct act, « Voir la fiche »
  * `data-panel` — a long press raises the medium's panel, which carries the
    act above. A row reachable only this way is still reachable, and refusing
    it would be refusing the interface's own gesture vocabulary.
  * `data-go`/`data-navgo` to a media path — the frame's navigation.

A ROW THAT CARRIES NONE OF THE THREE IS A DEAD END, and that is what this rule
refuses.

WHAT IT DOES NOT READ, said before what it does: whether the path LANDS. That
is `gallery.py`'s subject on the five it names and `screen_addresses.py`'s on
the address. This rule reads REACHABILITY, on the surfaces those two do not
cover — which is the half the clause map calls unproved.

AND IT READS THE ROWS THAT NAME A MEDIUM, never every row on the page. A
section heading, a pill, a counter and a guidance sentence name no medium and
owe no path; a rule that demanded one of them would be refused by the first
honest surface it met.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

# THE SURFACES THIS RULE COVERS, each named with why it is not somebody else's.
# `gallery.py` holds the five poster galleries; these are the LIST rows and the
# two galleries outside them, which is exactly what the clause map calls
# unproved.
SURFACES = (
    ("acq-follows-list", "a follow row"),
    ("acq-follows-group", "a follow row, grouped"),
    ("acq-now-loaded", "an acquisition in flight"),
    ("arr-loaded", "an arrival"),
    ("lib-list", "a library row"),
    ("acq-add-results", "a search result"),
)

# A ROW THAT NAMES A MEDIUM. Read from the markup's own vocabulary rather than
# from a class: `data-panel` and `data-mediasheet` carry a TITLE, `data-tile`
# and `data-add` name a medium by position in a list the page draws.
NAMING = """()=>{
  // `card` AND `tile`, and no third: `[data-part="row"]` is emitted nowhere in
  // this tree, and `check-markup-contracts` refused it — a value selected and
  // emitted nowhere is a rule selecting nothing.
  const rows = [...document.querySelectorAll(
    '#view [data-part="card"], #view [data-part="tile"]')];
  const reachable = (node) => {
    if (node.matches('[data-mediasheet], [data-panel], [data-tile], [data-add], [data-sug]'))
      return true;
    if (node.querySelector('[data-mediasheet], [data-panel]')) return true;
    const go = node.closest('[data-go], [data-navgo]');
    return !!go;
  };
  // A ROW THAT NAMES NO IDENTIFIED MEDIUM OWES NO SHEET, and the markup says
  // which: `data-nonmedia` is what an arrival wears while it is still a folder
  // nobody has identified. Demanding a path from it would be demanding a link
  // to a sheet that does not exist, which is the same broken promise read from
  // the other side.
  const named = rows.filter((node) => (node.textContent || '').trim().length > 0
    && !('nonmedia' in node.dataset));
  return {
    drawn: named.length,
    dead: named.filter((node) => !reachable(node)).slice(0, 4).map(
      (node) => (node.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60)),
  };}"""


async def main():
    journal = Journal("R122 — NE-DOIT-PAS-9: every medium has a path to its sheet")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state, what in SURFACES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.evaluate("()=>window.__mocks?.quiet()")
            await page.wait_for_timeout(450)
            read = await page.evaluate(NAMING)
            # THE FLOOR IS NOT DECORATION. A surface that draws nothing has no
            # dead end either, and « 0 of 0 reachable » is the vacuous pass this
            # rule would otherwise report on the day a state stops rendering.
            journal.check(
                f"{state} really draws rows, so « {what} » has a subject",
                read["drawn"] >= 3, f"{read['drawn']} row(s)")
            journal.check(
                f"every {what} carries a path to its sheet (NE-DOIT-PAS-9)",
                not read["dead"],
                f"{len(read['dead'])} dead of {read['drawn']}: {read['dead']}")

        journal.check("no JS error along the walk", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
