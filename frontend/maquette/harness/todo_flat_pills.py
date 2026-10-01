"""R508 — « À traiter » is one flat list in the urgency order, filtered and sorted by the one pill.

DECIDED 1 of maquette-blocked, the operator's word: « Liste à plat avec filtre. »
— no section says what unblocks a card (its cause line does), the order by
default is urgency (what needs his judgement, then the external blocks, then
the closures, newest first inside each), the Torrents tab's one-pill selector
filters it by cause, and a sort pill of the same component orders it. Both are
remembered (« retenue comme le filtre »).

What this holds, on `acq-todo-every-cause` (four cards for his judgement, four
external blocks posed 5, 20, 40 and 90 minutes ago):

1. the list draws no section title — « Mis de côté » apart;
2. its order is urgency: the judgement's cards first, then the external blocks
   newest first;
3. the filter pill reads « Tout » and the number of cards drawn, not pressed;
4. a finger on it opens the panel of causes, in order, each with its count;
5. a choice filters — « Disque plein » keeps its one card; the pill says it,
   pressed, with its count; the Acquisition badge does not move;
6. the sort pill's « Plus ancien » orders the external blocks oldest first;
7. after a reload, the filter and the sort chosen are still in force.

Red before the lot: the tab draws three titled sections and no pill.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
ACQ = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["acquisition"]
FILTERS = ACQ.get("todoFilter", {})
SORTS = ACQ.get("todoSort", {})
ORDER = ["all", "resolve", "plex", "step", "disks", "ratio", "unreachable", "closed"]
# The external blocks the state poses, newest first, by the key they are drawn under.
EXTERNAL_NEWEST = ["President Curtis", "Conclave", "This City Is Ours", "Silo|S03"]

LIST = """() => {
  const body = document.querySelector('#view [data-region="acquisition/body"]');
  if (!body) return null;
  const pill = (verb) => {
    const node = body.querySelector(`[data-part="pill/select"][${verb}]`);
    return node ? {text: node.firstChild?.textContent.trim() ?? '', pressed: node.getAttribute('aria-pressed') === 'true',
      count: node.querySelector('[data-part="pill/select-count"]')?.textContent.trim() ?? null} : null;
  };
  return {
    titles: [...body.querySelectorAll('[data-part="section/title"]')]
      .filter(title => !title.closest('[data-part="section/set-aside"]')).map(title => title.textContent.trim()),
    keys: [...body.querySelectorAll('[data-part="card"]')].filter(card => !card.closest('[data-part="section/set-aside"]'))
      .map(card => card.dataset.acquisition),
    filter: pill('data-todo-filter-pill'),
    sort: pill('data-todo-sort-pill'),
  };
}"""
CHOICES = """() => { const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return null;
  return [...sheet.querySelectorAll('[data-part="option"]')].map(choice => ({
    text: choice.querySelector('.lb')?.firstChild?.textContent.trim() ?? '',
    hint: choice.querySelector('small')?.textContent.trim() ?? '',
    checked: choice.getAttribute('aria-checked') === 'true'})); }"""
BADGE = """() => document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]')?.textContent.trim() ?? null"""


async def tap(page, selector):
    """Taps the first element a selector finds, if any, and lets it act."""
    target = page.locator(selector)
    if await target.count():
        await target.first.tap()
        await page.wait_for_timeout(ACTED)
    return await target.count()


async def choose(page, pill, text):
    """Opens a pill's panel and taps the choice that reads `text`."""
    await tap(page, f'#view [data-part="pill/select"][{pill}]')
    await tap(page, f'#sheet[data-open] [data-part="option"]:has-text("{text}")')


async def main():
    journal = Journal("R508 — « À traiter » is one flat list, filtered and sorted by the one pill")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-todo-every-cause');return null}catch(error){return String(error)}}")
        await page.wait_for_timeout(SETTLED)
        journal.check("the named state acq-todo-every-cause exists", answer is None, answer or "")
        read = await page.evaluate(LIST)
        journal.check("the list draws no section title", read is not None and read["titles"] == [],
                      str(read and read["titles"]))
        keys = (read or {}).get("keys") or []
        external = [key for key in keys if key in EXTERNAL_NEWEST]
        judgement = keys[:len(keys) - len(external)]
        journal.check("urgency: his judgement's cards first, then the external blocks newest first",
                      len(keys) == 8 and external == EXTERNAL_NEWEST and keys[len(judgement):] == EXTERNAL_NEWEST,
                      str(keys))
        filter_pill = (read or {}).get("filter")
        journal.check(f"the filter pill reads « {FILTERS.get('all')} » and the cards drawn, not pressed",
                      filter_pill is not None and filter_pill["text"] == FILTERS.get("all")
                      and filter_pill["count"] == str(len(keys)) and not filter_pill["pressed"], repr(filter_pill))
        badge = await page.evaluate(BADGE)

        await tap(page, '#view [data-part="pill/select"][data-todo-filter-pill]')
        choices = await page.evaluate(CHOICES)
        journal.check("a finger on it opens every cause, in order, each with its count, « Tout » checked",
                      choices is not None and [choice["text"] for choice in choices] == [FILTERS.get(key) for key in ORDER]
                      and all(choice["hint"][:1].isdigit() for choice in choices) and choices[0]["checked"],
                      repr(choices))
        await tap(page, f'#sheet[data-open] [data-part="option"]:has-text("{FILTERS.get("disks")}")')
        read = await page.evaluate(LIST)
        journal.check(f"« {FILTERS.get('disks')} » keeps its one card; the pill says it, pressed, with its count",
                      read is not None and read["keys"] == ["This City Is Ours"] and read["filter"]["text"] == FILTERS.get("disks")
                      and read["filter"]["pressed"] and read["filter"]["count"] == "1", repr(read))
        journal.check("the badge counts the whole list, whatever the filter shows",
                      badge is not None and await page.evaluate(BADGE) == badge, f"{badge} -> {await page.evaluate(BADGE)}")

        await choose(page, "data-todo-filter-pill", FILTERS.get("all"))
        await choose(page, "data-todo-sort-pill", SORTS.get("oldest"))
        read = await page.evaluate(LIST)
        oldest = [key for key in (read or {}).get("keys", []) if key in EXTERNAL_NEWEST]
        journal.check(f"« {SORTS.get('oldest')} » orders the external blocks oldest first, the pill pressed",
                      read is not None and oldest == list(reversed(EXTERNAL_NEWEST))
                      and read["keys"][:4] == oldest and read["sort"]["text"] == SORTS.get("oldest")
                      and read["sort"]["pressed"], repr(read))

        await choose(page, "data-todo-filter-pill", FILTERS.get("disks"))
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.wait_for_timeout(SETTLED)
        await tap(page, '[data-acqtab="todo"]')
        read = await page.evaluate(LIST)
        journal.check("after a reload, the filter and the sort chosen are still in force",
                      read is not None and read["filter"] is not None and read["filter"]["text"] == FILTERS.get("disks")
                      and read["sort"]["text"] == SORTS.get("oldest"), repr(read))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
