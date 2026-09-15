"""R195 — the library's selection survives every change of what the listing shows (B-312).

WHAT THE OPERATOR SAW. « à la sélection de médias, quand je change de filtre —
je passe de Tout à Films ou Séries — et que je sélectionne un média, la
sélection précédente est reset ». Every control that changes the listing's
question wrote `selected: new Set()` beside its own key.

WHAT WAS RULED. « La sélection doit survivre au changement des filtres. » The
selection is keyed by TITLE, so a tick that outlives a change of listing cannot
land on another medium. Two guard-rails come with it, because a tick nobody can
see must still be accounted for somewhere before anything is destroyed: the bar
counts every ticked medium, the hidden ones included, and the delete dialog
NAMES every ticked title, the hidden ones included.

THE WRITERS, one hold each, so a fall names the control that dropped the set:
the lens, the category, the sort, typing in the search, and the search's clear
cross. Each walk starts again from the named state, so no writer is read over a
set a previous writer already emptied.

WHAT IT READS, per writer:

  w1. THE STORE STILL HOLDS THE SAME TITLES — the titles, not a count: a
      selection that survived as a number and lost what it pointed at would
      pass a count and delete the wrong media.
  w2. THE BAR'S CAPTION COUNTS ALL OF THEM, read off the drawn caption.
  w3. WHERE THE CHANGE NARROWS, SOME OF WHAT IS TICKED IS HIDDEN AND SOME IS
      STILL DRAWN. Without the first half the two holds above would pass over a
      listing that still draws every ticked title, and the guard-rails would be
      proved on nothing; without the second, a reading that saw no row at all
      would call everything hidden. The start is held the same way: under
      « Tout » nothing ticked is hidden. The sort and the widening clear cross
      hide nothing and carry no such hold.

And once, under « Films », which hides the documentary and the series:

  d1. THE DELETE DIALOG NAMES EVERY TICKED TITLE, the hidden ones included,
      read off the dialog's manifest. THREE titles are ticked: the dialog names
      the first four and counts the rest as « et N autres » in media — that fold
      is the drawn dialog, and a selection of five or more is not this rule's.

THE CLEAR CROSS IS DRAWN ONLY OVER A QUERY, so its walk types one first and
then writes the named state's titles back through the store before tapping:
the typing is the other writer's subject, and reading the cross over a set the
typing had already emptied would read nothing.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# THE LIBRARY IN SELECTION MODE under « Tout », three titles ticked: two films
# and a documentary. french-ok: media titles, which are data.
SELECTION_STATE = "lib-selection"

# THE CATEGORY that hides the documentary; the query that hides the two others.
NARROWING_CATEGORY = "movies"
NARROWING_QUERY = "Marjorie"
OTHER_LENS = "rec"

# WHAT IS SELECTED, read where the selection lives rather than off the caption.
SELECTED = """()=>[...(window.__store?.read().state.selected || [])]"""

# PUTS TITLES BACK INTO THE SELECTION, the way the named state seeds it.
RESEED = """(titles)=>{
  window.__store.write({ selected: new Set(titles) });
}"""

# THE CAPTION'S FIGURE, and which ticked titles the listing still draws.
DRAWN = """(titles)=>{
  const caption = document.querySelector('[data-part="selection/caption"]');
  const figure = caption ? (caption.textContent.match(/\\d+/) || [null])[0] : null;
  const drawn = new Set([...document.querySelectorAll('[data-selected-title]')]
    .map((row) => row.dataset.selectedTitle));
  return {
    caption: caption ? caption.textContent.trim() : null,
    figure: figure === null ? null : Number(figure),
    hidden: titles.filter((title) => !drawn.has(title)),
  };
}"""

# THE DIALOG'S NAMED ENTRIES — every manifest row's own text, before its value.
DIALOG_NAMES = """()=>{
  const dialog = document.querySelector('[data-part="dialog"]');
  if (!dialog) return null;
  return [...dialog.querySelectorAll('[data-part="dialog/manifest"] li')]
    .map((row) => row.firstChild?.textContent?.trim() ?? '');
}"""


async def tap(page, selector):
    """Taps the first element a selector finds, by a finger at its own centre."""
    await page.evaluate("""(selector)=>document.querySelector(selector)
      ?.scrollIntoView({block: 'center', inline: 'center'})""", selector)
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate("""(selector) => {
      const one = document.querySelector(selector);
      if (!one) return {found: false};
      const box = one.getBoundingClientRect();
      const x = box.left + box.width / 2;
      const y = box.top + box.height / 2;
      const hit = document.elementFromPoint(x, y);
      return {found: true, x, y,
              reachable: !!hit && (hit === one || one.contains(hit)),
              covering: hit === null ? 'nothing' : hit.tagName};
    }""", selector)
    aim["tapped"] = bool(aim.get("found") and aim.get("reachable"))
    if aim["tapped"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        await page.wait_for_timeout(ACTED)
    return aim


async def start(page):
    """Asks for the named state and returns the titles it ticked."""
    await page.evaluate("(id)=>window.__go(id)", SELECTION_STATE)
    await page.wait_for_timeout(SETTLED)
    return await page.evaluate(SELECTED)


async def by_lens(page, titles):
    """Changes the lens."""
    return await tap(page, f'[data-lens="{OTHER_LENS}"]')


async def by_category(page, titles):
    """Changes the category."""
    return await tap(page, f'[data-cat="{NARROWING_CATEGORY}"]')


async def by_sort(page, titles):
    """Chooses a sort other than the one in force, from the sort panel."""
    opened = await tap(page, '#view [data-sort]')
    await page.wait_for_timeout(PANEL_IN)
    key = await page.evaluate("""()=>{
      const current = window.__store.read().state.sortKey;
      const other = [...document.querySelectorAll('#sheet [data-setsort]')]
        .find((action) => action.dataset.setsort !== current);
      return other ? other.dataset.setsort : null;
    }""")
    if not opened["tapped"] or key is None:
        return {"tapped": False, "covering": f"panel {opened.get('covering')}, key {key}"}
    return await tap(page, f"#sheet [data-setsort='{key}']:not([data-reversed])")


async def by_typing(page, titles):
    """Types a query into the search field."""
    await page.fill("#libq", NARROWING_QUERY)
    await page.wait_for_timeout(ACTED)
    return {"tapped": True}


async def by_clear_cross(page, titles):
    """Types a query, puts the ticks back, then taps the search's clear cross."""
    await page.fill("#libq", NARROWING_QUERY)
    await page.wait_for_timeout(ACTED)
    await page.evaluate(RESEED, titles)
    await page.wait_for_timeout(SETTLED)
    return await tap(page, "[data-clear-search]")


# THE WRITERS, each with whether its change narrows what is drawn.
WRITERS = (
    ("the lens", by_lens, False),
    ("the category", by_category, True),
    ("the sort", by_sort, False),
    ("typing in the search", by_typing, True),
    ("the search's clear cross", by_clear_cross, False),
)


async def main():
    """Walks every writer of the listing's question over a selection."""
    journal = Journal("R195 — the selection survives every change of what the listing shows")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        titles = await start(page)
        before = await page.evaluate(DRAWN, titles)
        journal.check("the named state ticks three titles, all drawn, and the bar counts them",
                      len(titles) == 3 and before["figure"] == 3 and before["hidden"] == [],
                      f"{titles}, hidden {before['hidden']}, caption {before['caption']!r}")

        for name, writer, narrows in WRITERS:
            titles = await start(page)
            acted = await writer(page, titles)
            kept = await page.evaluate(SELECTED)
            drawn = await page.evaluate(DRAWN, titles)
            journal.check(f"{name}: the store still holds the same titles",
                          acted["tapped"] and bool(titles) and sorted(kept) == sorted(titles),
                          f"acted {acted}, before {titles}, after {kept}")
            journal.check(f"{name}: the bar's caption counts all of them",
                          drawn["figure"] == len(titles),
                          f"caption {drawn['caption']!r} for {len(titles)} title(s)")
            if narrows:
                journal.check(f"{name}: some of what is ticked is hidden, some still drawn",
                              1 <= len(drawn["hidden"]) < len(titles),
                              f"hidden {drawn['hidden']} of {titles}")

        titles = await start(page)
        await by_category(page, titles)
        hidden = (await page.evaluate(DRAWN, titles))["hidden"]
        opened = await tap(page, "[data-delsel]")
        await page.wait_for_timeout(PANEL_IN)
        named = await page.evaluate(DIALOG_NAMES)
        journal.check("under « Films » the delete dialog names every ticked title, hidden ones included",
                      opened["tapped"] and named is not None
                      and 1 <= len(hidden) < len(titles)
                      and all(title in named for title in titles),
                      f"hidden {hidden}; named {named}; missing "
                      f"{[title for title in titles if named is None or title not in named]}")

        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
