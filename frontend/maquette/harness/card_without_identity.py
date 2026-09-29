"""R208 — a folder nobody recognised is an acquisition card, without identity.

An arrival is an acquisition card (ruling 2), and a folder the sort could not
name is one too (ruling 5): the folder's own name for a title, no poster, the
ladder resting on « identifié » with `blocked` and its reason IN FULL. It has no
sheet to open and nothing to follow — and NE-DOIT-PAS-9's exception says where
it leads instead: to the candidates screen, never to a dead link or a sheet that
does not exist.

Read on the operator's own data: a folder the sort typed as a medium and that no
provider identifies — « Backrooms.2026.MULTi.2160p.WEB-DL », in the dense world's
stuck list, its reason the sort's own sentence (« ni TMDB ni TVDB ne renvoient de
correspondance »).

RE-AIMED OUT LOUD: this rule was read on the real world's game folder, « c'est un
jeu, pas un média ». The sort files a folder with no video as « autre », and ruling
1 keeps « autre » out of the acquisitions, so that folder was never a card: it left
the seeds, and this rule now reads the folder the ruling is about. A last hold says
it: in neither world does « À traiter » draw a card from a category the sort files
as no medium — the staging folders of the configuration's non-media destinations —
and neither « À traiter » nor « En cours » draws a folder the engine's sort files as
other, named by the rule since no seed carries the sort's type.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
FOLDER = next(row for row in json.loads((SEEDS / "stuck-loaded.json").read_text(encoding="utf-8"))
              if row["ids"] is None and "Backrooms" in row["title"])
# The staging folders of the destinations the sort files as no medium, named the
# way the staging area names every category: its id on three digits, then its name.
NOT_MEDIA_FOLDERS = [f"{row['id']:03d}-{row['name'].upper()}" for row in
                     json.loads((SEEDS / "staging-destinations.json").read_text(encoding="utf-8"))]
# THE FOLDERS THE ENGINE'S SORT FILES AS OTHER, by name: a folder with no video is
# a film only when its NAME carries a video-release signal
# (`personalscraper/sorter/file_type.py:178–200`, `_looks_like_video_release`),
# and these two carry none — the game folder, and « doc_fr_2026_final » (.nfo
# files and an unextracted .rar). Ruling 1 keeps « autre » out of the acquisitions.
SORTED_OTHER = ["Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto", "doc_fr_2026_final"]
DRAWN_TITLES = """()=>[...document.querySelectorAll('#view [data-part="card/title"]')].map(one => one.textContent)"""
WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
IDENTIFIED = WORDS["surfaces"]["ladder"]["rungs"]["identified"] if "ladder" in WORDS["surfaces"] else None
# The ladder's sixth rung, « identifié », counted from one.
IDENTIFIED_INDEX = 5

CARD = """(title) => {
  const card = [...document.querySelectorAll('#view [data-part="card"]')]
    .find(one => one.querySelector('[data-part="card/title"]')?.textContent === title);
  if (!card) return null;
  const cells = [...card.querySelectorAll('[data-part="card/step"]')];
  const foot = card.querySelector('[data-part="card/foot"]');
  return {
    page: state.page,
    nonmedia: card.hasAttribute('data-nonmedia'),
    poster: !!card.querySelector('img'),
    sheetLink: !!card.querySelector('[data-mediasheet]'),
    follow: [card, ...card.querySelectorAll('*')].some(one => one.getAttributeNames().some(name => name.startsWith('data-follow'))),
    cells: cells.map(cell => cell.dataset.state),
    rung: (card.querySelector('[data-part="card/meta"] [data-part="chip"]') || {}).textContent || null,
    reason: (card.querySelector('[data-part="card/reason"]') || {}).textContent || null,
    resolution: foot ? foot.getAttribute('data-resolution') : null,
  };
}"""


async def main():
    journal = Journal("R208 — a folder without identity is an acquisition card")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-card-no-identity');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-card-no-identity exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        drawn = (await page.evaluate(
            """()=>({page: state.page, scen: state.scen, tab: state.acqTab,
                     titles: [...document.querySelectorAll('#view [data-part="card/title"]')].map(e=>e.textContent)})"""))
        card = await page.evaluate(CARD, FOLDER["title"])
        journal.check("the folder is a card in acquisition, under its folder's name",
                      card is not None and card["page"] == "acq", str(card or drawn))
        card = card or {}
        journal.check("it is marked as no medium, and draws no poster",
                      card.get("nonmedia") is True and card.get("poster") is False, str(card))
        journal.check("it offers no sheet link and no « Suivre »",
                      card.get("sheetLink") is False and card.get("follow") is False, str(card))
        cells = card.get("cells") or []
        journal.check(
            "its ladder rests on « identifié », blocked there",
            len(cells) == 8 and cells[IDENTIFIED_INDEX] == "blocked"
            and card.get("rung") == IDENTIFIED,
            f"cells={cells} rung={card.get('rung')!r}")
        journal.check("its reason is drawn in full", card.get("reason") == FOLDER["reason"],
                      repr(card.get("reason")))
        journal.check("its foot leads to the candidates screen for that folder",
                      card.get("resolution") == FOLDER["title"], repr(card.get("resolution")))

        if card.get("resolution"):
            await page.evaluate("""(title)=>[...document.querySelectorAll('#view [data-part="card/foot"]')]
                .find(foot => foot.getAttribute('data-resolution') === title).click()""", FOLDER["title"])
            await page.wait_for_timeout(ACTED)
            opened = await page.evaluate(
                """()=>document.querySelector('[data-part="screen"][data-open]')?.dataset.key ?? null""")
            journal.check("a tap on it opens the candidates screen on that folder",
                          opened == f"resolution:{FOLDER['title']}", repr(opened))

        for state in ("acq-todo-loaded", "acq-todo-dense"):
            await page.evaluate(f"()=>window.__go('{state}')")
            await page.wait_for_timeout(SETTLED)
            filed = await page.evaluate(
                """(folders)=>[...document.querySelectorAll('#view [data-part="card"]')]
                    .filter(card => folders.some(folder => (card.querySelector('[data-part="card/subtitle"]')
                        ?.textContent || '').startsWith(folder)))
                    .map(card => card.querySelector('[data-part="card/title"]')?.textContent)""",
                NOT_MEDIA_FOLDERS)
            journal.check(f"{state}: « À traiter » draws no folder the sort filed as no medium",
                          filed == [], str(filed))
            drawn = await page.evaluate(DRAWN_TITLES)
            await page.evaluate("()=>document.querySelector('[data-acqtab=\"now\"]')?.click()")
            await page.wait_for_timeout(SETTLED)
            drawn += await page.evaluate(DRAWN_TITLES)
            other = [title for title in SORTED_OTHER if title in drawn]
            journal.check(f"{state}: neither « À traiter » nor « En cours » draws a folder the sort files as other",
                          other == [], str(other))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
