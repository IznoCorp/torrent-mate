"""R529 — every Acquisition tab carries the filter and sort zone, and the zone keeps one place from tab to tab.

The operator (BUGS.md B-706): the whole filter and sort zone belongs on every
tab of Acquisition, save the display switch, which not every tab can show; and
the placing has to give an impression of stability when one goes from a tab to
another.

What this holds, at 390 px, on « Suivis », « En cours » and « À traiter »:

1. each tab draws the zone: the search field, the filter pill, the sort pill;
2. only « Suivis » draws the display switch (list · grouped · grid);
3. typing in the search field narrows the list to the titles that hold it, and
   the filter pill says how many are left;
4. a choice of the filter pill keeps part of the list, its count being the
   list's; on « En cours » the series and the films add up to the whole;
5. a choice of the sort pill reorders the list; « A → Z » and « Z → A »
   order it by French collation, one the reverse of the other;
6. the zone's box (top, height, left, width), its search field's, its pills'
   top and height (and the filter pill's left edge — a pill's width is its
   label's) and the tab bar's are the same on the three tabs, whether the tab was
   posed by name or reached by a tap on the bar — and the page is not wider
   than the screen.

Red before the fix: « En cours » draws no zone, « À traiter » draws two pills
inside its body and no search field, and the tabs do not share a place.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
ACQ = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["acquisition"]
WIDTH = 390
TOLERANCE = 0.5
# What each tab is posed by, its search field, its pills, and the two sorts that
# must order its list differently. A tab's filter choice is the SECOND of its panel.
TABS = [
    {"id": "follows", "state": "acq-follows-list", "search": "#follq", "filter": "data-follows-filter-pill",
     "sort": "data-follows-sort-pill", "first": ACQ["followSort"]["az"], "second": ACQ["followSort"]["za"],
     "by_title": True, "switch": True},
    {"id": "now", "state": "acq-now-loaded", "search": "#nowq", "filter": "data-now-filter-pill",
     "sort": "data-now-sort-pill", "first": ACQ.get("nowSort", {}).get("az", ""),
     "second": ACQ.get("nowSort", {}).get("za", ""), "by_title": True, "switch": False},
    {"id": "todo", "state": "acq-todo-every-cause", "search": "#todoq", "filter": "data-todo-filter-pill",
     "sort": "data-todo-sort-pill", "first": ACQ["todoSort"]["newest"], "second": ACQ["todoSort"]["oldest"],
     "by_title": False, "switch": False},
]

TITLES = """() => [...document.querySelectorAll('#view [data-part="card/title"]')]
  .filter(node => !node.closest('[data-part="section/set-aside"], [data-part="section/paused"]'))
  .map(node => node.textContent.trim())"""
ZONE = """() => {
  const view = document.querySelector('#view');
  const zone = view?.querySelector('[data-region="acquisition/filters"]');
  const box = node => { if (!node) return null; const rect = node.getBoundingClientRect();
    return {top: rect.top, height: rect.height, left: rect.left, width: rect.width}; };
  const pills = zone ? [...zone.querySelectorAll('[data-part="pill/select"]')] : [];
  return {
    present: !!zone,
    search: !!zone?.querySelector('input[type="search"]'),
    pills: pills.length,
    switchButtons: zone ? zone.querySelectorAll('[data-part="view/switch"] [data-fmode]').length : 0,
    boxes: {zone: box(zone), search: box(zone?.querySelector('input[type="search"]')), filter: box(pills[0]),
      sort: box(pills[1]), tabs: box(view?.querySelector('[data-region="acquisition/tabs"]'))},
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
}"""
PILL = """(verb) => { const node = document.querySelector(`#view [data-part="pill/select"][${verb}]`);
  return node ? {text: node.firstChild?.textContent.trim() ?? '', pressed: node.getAttribute('aria-pressed') === 'true',
    count: node.querySelector('[data-part="pill/select-count"]')?.textContent.trim() ?? null} : null; }"""
SORTED_BY_TITLE = """(titles) => [...titles].sort((left, right) => left.localeCompare(right, 'fr'))"""
CHOICES = """() => { const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return null;
  return [...sheet.querySelectorAll('[data-part="option"]')].map(choice =>
    choice.querySelector('.lb')?.firstChild?.textContent.trim() ?? ''); }"""


async def tap(page, selector):
    """Taps the first element a selector finds, if any, and lets it act."""
    target = page.locator(selector)
    if await target.count():
        await target.first.tap()
        await page.wait_for_timeout(ACTED)
    return await target.count()


async def choose_text(page, pill, text):
    """Opens a pill's panel and taps the choice that reads `text`."""
    await tap(page, f'#view [data-part="pill/select"][{pill}]')
    return await tap(page, f'#sheet[data-open] [data-part="option"]:has-text("{text}")')


async def choose_nth(page, pill, index):
    """Opens a pill's panel and taps its `index`th choice."""
    await tap(page, f'#view [data-part="pill/select"][{pill}]')
    target = page.locator('#sheet[data-open] [data-part="option"]')
    if await target.count() > index:
        await target.nth(index).tap()
        await page.wait_for_timeout(ACTED)
        return True
    return False


async def pose(page, state):
    """Poses a named state; returns the error text, or None."""
    answer = await page.evaluate(
        "(state)=>{try{window.__go(state);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    return answer


# What makes a box « in the same place »: a pill's WIDTH is its label's (« Tout 12 », « À résoudre 3 »), and
# so is the left edge of the sort pill that follows the filter pill; every other box is held on all four.
PLACE = {"filter": ("top", "height", "left"), "sort": ("top", "height")}
ALL_SIDES = ("top", "height", "left", "width")


def same_place(name, reference, other):
    """Whether two boxes share what places them, within a half pixel."""
    if reference is None or other is None:
        return reference is other
    return all(abs(reference[key] - other[key]) <= TOLERANCE for key in PLACE.get(name, ALL_SIDES))


def mismatches(reference, other):
    """The names of the boxes of `other` that sit elsewhere than `reference`'s."""
    return [name for name in reference["boxes"]
            if not same_place(name, reference["boxes"][name], other["boxes"][name])]


def term_for(titles):
    """A three-letter term held by some of the titles and not by all of them."""
    for title in titles:
        term = title[:3].lower()
        held = [other for other in titles if term in other.lower()]
        if 0 < len(held) < len(titles):
            return term, held
    return None, []


async def check_tab(journal, page, tab):
    """Holds the zone's presence, the search, the filter and the sort of one tab."""
    name = tab["id"]
    journal.check(f"{name}: the named state {tab['state']} exists", await pose(page, tab["state"]) is None)
    zone = await page.evaluate(ZONE)
    journal.check(f"{name}: the zone is drawn — the search field and the two pills",
                  zone["present"] and zone["search"] and zone["pills"] == 2, str(zone))
    journal.check(f"{name}: the display switch is {'drawn' if tab['switch'] else 'left out'}",
                  (zone["switchButtons"] == 3) == tab["switch"] and (zone["switchButtons"] in (0, 3)),
                  f"{zone['switchButtons']} buttons")
    titles = await page.evaluate(TITLES)
    journal.check(f"{name}: the list draws at least three cards to narrow and to order", len(titles) >= 3, str(titles))
    term, held = term_for(titles)
    journal.check(f"{name}: a term held by some of the titles and not by all exists", term is not None, str(titles))
    if term is not None and zone["search"]:
        await page.fill(tab["search"], term)
        await page.wait_for_timeout(ACTED)
        narrowed = await page.evaluate(TITLES)
        pill = await page.evaluate(PILL, tab["filter"])
        journal.check(f"{name}: typing « {term} » narrows the list to the titles that hold it, the pill counting them",
                      sorted(narrowed) == sorted(held) and pill is not None and pill["count"] == str(len(held)),
                      f"{narrowed} · {pill}")
        await page.fill(tab["search"], "")
        await page.wait_for_timeout(ACTED)
    whole = await page.evaluate(PILL, tab["filter"])
    if whole is not None and await choose_nth(page, tab["filter"], 1):
        kept = await page.evaluate(TITLES)
        pill = await page.evaluate(PILL, tab["filter"])
        journal.check(f"{name}: the filter's second choice keeps part of the list, its count the list's",
                      0 < len(kept) < len(titles) and pill is not None and pill["count"] == str(len(kept))
                      and pill["pressed"], f"{len(titles)} -> {kept} · {pill}")
        if name == "now":
            await choose_nth(page, tab["filter"], 2)
            other = await page.evaluate(TITLES)
            journal.check("now: the series and the films add up to the whole", len(kept) + len(other) == len(titles),
                          f"{len(kept)} + {len(other)} vs {len(titles)}")
        await choose_nth(page, tab["filter"], 0)
    else:
        journal.check(f"{name}: the filter pill opens its choices", False, str(whole))
    await choose_text(page, tab["sort"], tab["first"])
    first = await page.evaluate(TITLES)
    await choose_text(page, tab["sort"], tab["second"])
    second = await page.evaluate(TITLES)
    sort_pill = await page.evaluate(PILL, tab["sort"])
    journal.check(f"{name}: « {tab['first']} » and « {tab['second']} » order the list differently, the pill saying it",
                  first != second and sorted(first) == sorted(second) and sort_pill is not None
                  and sort_pill["text"] == tab["second"], f"{first} / {second} · {sort_pill}")
    if tab["by_title"]:
        by_title = await page.evaluate(SORTED_BY_TITLE, first)
        journal.check(f"{name}: the two orders are the titles' by French collation, one the reverse of the other",
                      first == by_title and second == list(reversed(by_title)), f"{first} / {second}")


async def main():
    journal = Journal("R529 — every Acquisition tab carries the filter and sort zone, in one place")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for tab in TABS:
            await check_tab(journal, page, tab)

        # THE ZONE'S PLACE, tab by tab: posed by name, then reached by a finger on the bar.
        places = {}
        for tab in TABS:
            await pose(page, tab["state"])
            places[f"{tab['id']} (posed)"] = await page.evaluate(ZONE)
        await pose(page, "acq-todo-every-cause")
        for tab in TABS:
            await tap(page, f'[data-acqtab="{tab["id"]}"]')
            places[f"{tab['id']} (tapped)"] = await page.evaluate(ZONE)
        reference_name, reference = next(iter(places.items()))
        for label, zone in places.items():
            moved = mismatches(reference, zone) if zone["present"] and reference["present"] else ["zone"]
            journal.check(f"the zone, the field, the pills and the tab bar of « {label} » sit where « {reference_name} »'s do",
                          not moved, f"moved: {moved} · {zone['boxes']} vs {reference['boxes']}")
            journal.check(f"« {label} » is not wider than the screen", zone["overflow"] <= 0, str(zone["overflow"]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
