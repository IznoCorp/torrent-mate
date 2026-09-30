"""R-conformity-s — every lens of the library is filtered by the same category pills.

THE DECISION THIS HOLDS. The operator ruled (Q20) that « Récents » and
« Incomplets » get the category filters the « Médias » lens has: the same pills,
the same remembered category, and on « Incomplets » counts of its own from the
rows it draws — « Films » there reads 0, since only series are incomplete, and
the lens says so by its empty note rather than by a blank.

WHAT IT READS:
  s1. On « Récents » and « Incomplets », the pills are drawn and exactly one is
      pressed.
  s2. On « Récents » with « Films » pressed, every title drawn is a film — read
      against the seed's own categories, never retyped here.
  s3. On « Incomplets », each pressed pill's figure is the number of rows the
      lens draws: all of them under « Tout », none under « Films », where the
      empty note is drawn.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "mocks" / "seeds"
MOVIE_CATEGORY = "movies"

READ = """()=>{
  const view = document.querySelector('#view');
  const pills = [...view.querySelectorAll('[data-part="pill"][data-cat]')];
  const pressed = pills.filter((pill) => pill.getAttribute('aria-pressed') === 'true');
  const body = view.querySelector('[data-part="surface/body"]');
  const rows = body ? [...body.querySelectorAll('[data-part="tile"], [data-part="card"]')] : [];
  return {
    pills: pills.length,
    pressed: pressed.map((pill) => pill.dataset.cat),
    figure: pressed.length === 1 ? Number(pressed[0].lastElementChild?.textContent ?? NaN) : null,
    titles: rows.map((row) => (row.querySelector('[data-part="tile/title"], [data-part="card/title"]')
      ?.textContent ?? '').trim()),
    empty: !!body?.querySelector('[data-part="empty-state"]'),
  };
}"""


async def read(page, state):
    """Drives one named state and reads its pills and its rows."""
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(SETTLED)
    return await page.evaluate(READ)


async def main():
    """Reads the pills and the rows of the two lenses."""
    journal = Journal("R-conformity-s — the category pills on every lens")
    items = json.loads((SEEDS / "library-items.json").read_text(encoding="utf-8"))
    movies = {item["title"] for item in items if item.get("category") == MOVIE_CATEGORY}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in ("lib-recent", "lib-incomplete"):
            seen = await read(page, state)
            journal.check(f"{state}: the pills are drawn, one of them pressed",
                          seen["pills"] >= 2 and len(seen["pressed"]) == 1, f"{seen}")
        seen = await read(page, "lib-recent-movies")
        journal.check("lib-recent-movies: « Films » is pressed, and every title drawn is a film",
                      seen["pressed"] == [MOVIE_CATEGORY] and bool(seen["titles"])
                      and all(title in movies for title in seen["titles"]),
                      f"pressed {seen['pressed']}; not movies: "
                      f"{[title for title in seen['titles'] if title not in movies][:3]} of {len(seen['titles'])}")
        for state, empty in (("lib-incomplete", False), ("lib-incomplete-movies", True)):
            seen = await read(page, state)
            journal.check(f"{state}: the pressed pill counts the rows drawn",
                          seen["figure"] == len(seen["titles"]) and bool(seen["titles"]) != empty,
                          f"figure {seen['figure']} for {len(seen['titles'])} rows")
            if empty:
                journal.check(f"{state}: and the lens says it is empty", seen["empty"], f"{seen}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
