"""R177 — every follow in the list mode shows its poster, not its initials.

THE DEFECT IT HOLDS. Acquisition › Suivis draws its follows two ways. The grid
read each follow's `poster`; the list built its card from a descriptor that
copied every field but that one, so every row drew the initials fallback.

WHY NOTHING ELSE SAW IT. The fallback fills the poster's box at the poster's
size: the oracle measures rectangles and `poster.py` measures the box's height,
and both were right about what they read. The seeds were right too — the
drawing dropped the field between the seed and the card.

WHAT IT READS, and it is the element: the `<img>` inside each row's
`card/poster`. Which rows must have one is read from the seed the mock layer
answers the follows from — a row whose seed carries no poster is entitled to its
initials, and is not counted.
"""
import asyncio
import json
import pathlib
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import SETTLED, Journal, open_page

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[3]
SEED = ROOT / "frontend" / "maquette" / "design" / "src" / "mocks" / "seeds" / "follows.json"
LIST_STATE = "acq-follows-list"
ROWS_DEADLINE = 3000
POLL_INTERVAL = 100

ROWS = """()=>[...document.querySelectorAll('#view [data-part="card"]')].map((row) => {
  const poster = row.querySelector('[data-part="card/poster"]');
  const image = poster ? poster.querySelector('img') : null;
  return {
    title: (row.querySelector('[data-part="card/title"]')?.textContent || '').trim(),
    image: image ? (image.getAttribute('src') || '') : null,
    initials: poster && !image ? poster.textContent.trim() : null,
  };
})"""


def normalised(title):
    """Puts a title in the one form both sides are compared in.

    Args:
        title: A title, as the seed or the page writes it.

    Returns:
        The NFC form.
    """
    return unicodedata.normalize("NFC", title)


async def main():
    journal = Journal("R177 — every follow in the list mode shows its poster, not its initials")
    with_poster = {normalised(follow["title"]) for follow in json.loads(SEED.read_text(encoding="utf-8"))
                   if follow.get("poster")}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        await page.evaluate("(id)=>window.__go(id)", LIST_STATE)
        await page.wait_for_timeout(SETTLED)
        rows = await page.evaluate(ROWS)
        waited = 0
        while not rows and waited < ROWS_DEADLINE:
            await page.wait_for_timeout(POLL_INTERVAL)
            waited += POLL_INTERVAL
            rows = await page.evaluate(ROWS)

        owed = [row for row in rows if normalised(row["title"]) in with_poster]
        journal.check(
            "the list mode draws follows whose seed carries a poster — an empty "
            "list would hold the rule below over nothing",
            bool(owed), f"{len(rows)} row(s), {len(owed)} with a seed poster")

        without = [f"{row['title']} « {row['initials']} »" for row in owed if not row["image"]]
        journal.check(
            "every one of them draws its poster as an image, not the initials "
            "the fallback fills the same box with",
            bool(owed) and not without,
            f"{len(owed) - len(without)} image(s); initials on {without[:4]}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
