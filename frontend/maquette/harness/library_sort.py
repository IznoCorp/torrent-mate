"""R78 — every sort goes BOTH ways, and each way says its own name.

The library shipped with three sorts and one direction each: « Ajout récent »,
« A → Z », « Les plus incomplets ». Asking for the other end of any of them was
impossible — the operator reported it (E-001), and an operator who cannot ask
for Z → A cannot use a sorted list to find the last thing either.

What this holds to:

  · every sort is offered in BOTH directions, and each direction carries its
    own NAME rather than an arrow bolted onto a shared one — « Ajout récent »
    reversed is « Ajout ancien », which is what one would say out loud;
  · the direction in force is MARKED, and exactly one of them is;
  · choosing a direction really reverses the LIST — measured on the rendered
    rows, not on the data, because a sort that reorders an array nobody draws
    is a sort nobody has;
  · the control on the count line reads the direction in force;
  · and the sort stays OUT of the address. It is a preference, not a place
    (A7): two people opening the same link see their own sort, and the panel
    says so in its own note.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

# The rendered rows, read through the TITLE each one draws — not through
# `data-mediasheet`, which a first version used and which is only on the rows whose
# title resolves to an embedded media sheet: measured, one end of the library
# had twenty-four of them and the other end none, so the rule read an empty
# list and called it a failed reversal. The title is the row's identity
# everywhere in this prototype; the sheet is a property of some rows.
TITLES = """()=>[...document.querySelectorAll('#libitems [data-part="card/title"], #libitems .tile .nm')]
  .map((element) => element.textContent.trim())"""

PANEL = """()=>[...document.querySelectorAll('.sheetacts .sact')].map((button) => ({
  text: button.textContent.trim(),
  sort: button.dataset.setsort || null,
  reversed: button.dataset.reversed === '1',
  current: button.className.split(' ').includes('primary'),
}))"""


async def open_sort_panel(page):
    """Opens the sort panel from the count line, the way a finger does."""
    await page.click("#view [data-sort]")
    await page.wait_for_timeout(420)
    return await page.evaluate(PANEL)


async def main():
    journal = Journal("R78 — every sort goes both ways")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("()=>window.__go('lib-list')")
        await page.wait_for_timeout(700)

        # THE WHOLE SET HAS TO BE ON SCREEN before a reversal can be read off
        # it: the library draws its first page only (24 of 260), so reversing
        # the ORDER and then taking the first page again gives the LAST rows of
        # the other end — which is right, and is not the reverse of what was
        # drawn. Narrowing to a handful is what makes the promise checkable on
        # the DRAWING rather than on the array behind it.
        #
        # AND THE NARROWING ITSELF IS HELD, because a narrowing can hide a
        # sort: « les plus incomplets » ranks by episodes missing, and a set
        # where no row is incomplete ranks by nothing at all — every row scores
        # the same, the sort is stable, and the order comes back identical to
        # « ajout récent ». A rule reading such a set cannot tell those two
        # sorts apart. So the set is chosen to CONTAIN incomplete shows, and
        # that is asserted rather than assumed.
        # french-ok: a French search WORD, typed into the app's own search.
        await page.evaluate(
            "()=>{window.__store.write({q: 'star', libCount: 24}); render();}")
        await page.wait_for_timeout(700)
        narrowed = await page.evaluate(TITLES)
        journal.check(
            "a narrowed library fits on one page, so a reversal can be READ",
            1 < len(narrowed) <= 24, f"{len(narrowed)} rows: {narrowed}")
        incomplete = await page.evaluate("""()=>{
          const shown = new Set([...document.querySelectorAll(
            '#libitems [data-part="card/title"], #libitems .tile b')].map((x) => x.textContent.trim()));
          return window.__referentiel.INCOMPLETE
            .filter((show) => shown.has(show.t)).map((show) => show.t);}""")
        journal.check(
            "and it holds media the « incomplets » sort can actually rank",
            len(incomplete) > 0,
            f"{len(incomplete)} incomplete show(s) in the narrowed set: {incomplete}"
            if incomplete else "none — that sort would rank a set where every "
            "row scores the same, and answer the source order, which is what "
            "« ajout récent » answers")

        declared = await page.evaluate("()=>window.__referentiel.TRIS")
        journal.check(
            "the prototype declares a name for both ways of every sort",
            bool(declared) and all(
                isinstance(ways, dict) and ways.get("normal") and ways.get("inverse")
                and ways["normal"] != ways["inverse"]
                for ways in declared.values()),
            str(declared))

        offered = await open_sort_panel(page)
        journal.check(
            "the panel offers every sort in both directions",
            len(offered) == 2 * len(declared)
            and {(entry["sort"], entry["reversed"]) for entry in offered}
            == {(key, reversed_) for key in declared for reversed_ in (False, True)},
            str([(entry["text"], entry["reversed"]) for entry in offered]))
        journal.check(
            "and each direction carries its own name",
            len({entry["text"] for entry in offered}) == len(offered),
            str([entry["text"] for entry in offered]))
        journal.check(
            "exactly one of them is marked as the one in force",
            sum(1 for entry in offered if entry["current"]) == 1,
            str([entry["text"] for entry in offered if entry["current"]]))

        # THE REVERSAL IS MEASURED ON WHAT IS DRAWN. Comparing the sorted array
        # against itself would be a derivation reading back its own output, and
        # a list nobody draws is a list nobody can use.
        for key, ways in declared.items():
            drawn = {}
            for sense, reversed_ in (("normal", False), ("inverse", True)):
                if not await page.evaluate(
                        "()=>!!document.querySelector('#sheet[data-open]')"):
                    await open_sort_panel(page)
                selector = (f"#sheet .sact[data-setsort='{key}']"
                            + ("[data-reversed='1']" if reversed_
                               else ":not([data-reversed])"))
                control = page.locator(selector).first
                if not await control.count():
                    journal.check(f"« {ways[sense]} » can be chosen", False,
                                  f"no action carries {selector}")
                    continue
                await control.click()
                await page.wait_for_timeout(700)
                drawn[sense] = await page.evaluate(TITLES)
                label = await page.evaluate(
                    "()=>document.querySelector('#view [data-sort]').textContent.trim()")
                journal.check(
                    f"choosing « {ways[sense]} » says so on the control",
                    label.endswith(ways[sense]), label)

            if len(drawn) != 2:
                continue
            journal.check(
                f"« {ways['inverse']} » really reverses « {ways['normal']} »",
                len(drawn["normal"]) > 1
                and sorted(drawn["inverse"]) == sorted(drawn["normal"])
                and drawn["inverse"] == list(reversed(drawn["normal"])),
                f"{len(drawn['normal'])} rows — "
                f"{drawn['normal'][0]} … {drawn['normal'][-1]} became "
                f"{drawn['inverse'][0]} … {drawn['inverse'][-1]}")

        # THE MARK FOLLOWS THE DIRECTION, not only the sort. Measured after a
        # REVERSED direction has been chosen: a marking that reads the sort
        # alone leaves two rows marked, and one that forgets the reversed case
        # leaves none — neither is visible from the resting state, where the
        # normal direction is in force.
        await page.evaluate(
            "()=>{window.__store.write({sortKey: 'az', sortReversed: true}); render();}")
        await page.wait_for_timeout(400)
        marked = await open_sort_panel(page)
        current = [entry for entry in marked if entry["current"]]
        journal.check(
            "with a reversed direction in force, exactly that one is marked",
            len(current) == 1 and current[0]["sort"] == "az"
            and current[0]["reversed"],
            str([(entry["text"], entry["current"]) for entry in marked]))
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(300)

        # AND THE NORMAL DIRECTION IS NOT MERELY THE OTHER ONE: « A → Z » says
        # alphabetical, which is a property of the LIST and not of the
        # implementation. Without it, this rule holds only that one order is
        # the reverse of the other — true of any comparator, and of a broken
        # one.
        await page.evaluate(
            "()=>{window.__store.write({sortKey: 'az', sortReversed: false}); render();}")
        await page.wait_for_timeout(500)
        alphabetical = await page.evaluate(TITLES)
        # Sorted by the PLATFORM's French collation, not by the app's — and not
        # by Python's default ordering either, which puts « Z » before « à » and
        # would call almost anything alphabetical. `Intl` is the independent
        # oracle here: it is the same rule a reader applies, and it is not the
        # code under test.
        expected = await page.evaluate(
            "(titles)=>[...titles].sort((a, b) => a.localeCompare(b, 'fr'))",
            alphabetical)
        journal.check(
            "« A → Z » really is alphabetical, by French collation",
            alphabetical == expected,
            str(alphabetical[:3]) + " … " + str(alphabetical[-1:])
            + ("" if alphabetical == expected else f" — expected {expected}"))

        # AND IN THE OTHER FORMAT. The rows are drawn by a different emitter in
        # grid mode (`tileHTML`, not `libRowHTML`), so a direction that reached
        # only the list would be a working sort on one half of the page.
        await page.evaluate(
            "()=>{window.__store.write({libMode: 'grid', sortKey: 'az',"
            " sortReversed: false}); render();}")
        await page.wait_for_timeout(600)
        grid_normal = await page.evaluate(TITLES)
        await page.evaluate(
            "()=>{window.__store.write({sortReversed: true}); render();}")
        await page.wait_for_timeout(600)
        grid_reversed = await page.evaluate(TITLES)
        journal.check(
            "the direction reaches the GRID as well as the list",
            len(grid_normal) > 1
            and grid_reversed == list(reversed(grid_normal)),
            f"{len(grid_normal)} tiles — {grid_normal[:1]}…{grid_normal[-1:]} "
            f"became {grid_reversed[:1]}…{grid_reversed[-1:]}")
        await page.evaluate("()=>{window.__store.write({libMode: 'list'}); render();}")
        await page.wait_for_timeout(400)

        # A PREFERENCE, NOT A PLACE. The panel's own note says the sort stays on
        # this device; the address is what would betray it.
        address = await page.evaluate("()=>location.pathname + location.search")
        journal.check(
            "the sort stays out of the address",
            "tri" not in address and "sort" not in address, address)

        await browser.close()
    journal.summary(errors)


asyncio.run(main())
