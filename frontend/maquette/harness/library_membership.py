"""R191 — whether the library holds a medium is ANSWERED, exactly, and a deletion is heard.

The follow panel states one fact about the library — the medium is in it — and
offers « Re-scraper » on that fact alone. Until this rule the fact was read off
the dying engine's own copy of the library, a table the served layer never
writes: a title deleted through the layer stayed « in the library » for every
panel opened about it, and a title the table did not carry was « absent »
whatever the layer held.

WHAT IS READ, and against what:

  1. FIVE TITLES, chosen from the layer's WHOLE seed rather than from what a
     page happens to show: the two first rows (page one of the listing), two
     rows far beyond the first page, and one medium the library does not hold.
     The panel offers « Re-scraper » for exactly the four the seed holds. A read
     that asked only the listing's first page would say « absent » for the two
     beyond it — that is the narrower answer this rule refuses.
  2. A DELETION, made through the removal's own verb and dialog, and the
     panel opened about that title afterwards, in the same session: it no
     longer offers « Re-scraper ». No reload — a reload starts a fresh layer and
     would put the title back, which measures nothing.

WHAT IT DOES NOT HOLD: the removal dialog's own walk (R-numbers of the library's
verbs), and the media sheet's ownership, which reads its own served answer.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal, open_page  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

journal = Journal("R191 — library membership is exact, and a deletion is heard")

SEEDS = ROOT / "design" / "src" / "mocks" / "seeds"
# Beyond the listing's first page: the layer pages by 24.
FAR_ROWS = (60, 300)

OPEN_FOLLOW_PANEL = """async (title)=>{
  window.__reset?.();
  window.__go('acq-follows-list');
  await new Promise((done) => setTimeout(done, 400));
  window.__panel.produce('follow', title);
  await new Promise((done) => setTimeout(done, 700));
  const sheet = document.querySelector('#sheet');
  return {open: !!sheet?.hasAttribute('data-open'),
          rescrape: !!sheet?.querySelector('[data-rescrape]')};
}"""


async def main():
    library = [row["title"] for row in json.loads((SEEDS / "library-items.json").read_text())]
    followed = [one["title"] for one in json.loads((SEEDS / "follows.json").read_text())]
    absent = next(title for title in followed if title not in library)
    held = [library[0], library[1], *(library[index] for index in FAR_ROWS)]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for title in [*held, absent]:
            reading = await page.evaluate(OPEN_FOLLOW_PANEL, title)
            expected = title in library
            journal.check(
                f"the panel about « {title} » says {'in' if expected else 'NOT in'} the library",
                reading["open"] and reading["rescrape"] == expected,
                f"{reading} — the whole seed {'holds' if expected else 'does not hold'} it")

        deleted = library[1]
        # THROUGH THE REMOVAL'S OWN VERB AND DIALOG: an element carrying
        # `data-del` is tapped (the registry answers it like any row's), and the
        # dialog's first action — the removal — is pressed. The layer's call and
        # the cache's settlement are the product's, not this rule's.
        confirmed = await page.evaluate(
            """async (title)=>{
              const tap = document.createElement('button');
              tap.dataset.del = title;
              document.querySelector('#view').append(tap);
              tap.click();
              tap.remove();
              await new Promise((done) => setTimeout(done, 400));
              const remove = document.querySelector('#dlg[data-open] button');
              if (!remove) return false;
              remove.click();
              await new Promise((done) => setTimeout(done, 900));
              return true;
            }""", deleted)
        journal.check(f"the removal dialog opens about « {deleted} » and is confirmed",
                      confirmed, "no open dialog offered the removal")
        # NOT reset: a named state resets the layer, which would put the title back.
        reading = await page.evaluate(
            """async (title)=>{
              window.__panel.produce('follow', title);
              await new Promise((done) => setTimeout(done, 700));
              const sheet = document.querySelector('#sheet');
              return {open: !!sheet?.hasAttribute('data-open'),
                      rescrape: !!sheet?.querySelector('[data-rescrape]')};
            }""", deleted)
        journal.check(
            f"and the panel about « {deleted} » opened afterwards no longer says it is in the library",
            reading["open"] and not reading["rescrape"],
            f"{reading} — the fact was read off a copy the deletion never reached")

        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
