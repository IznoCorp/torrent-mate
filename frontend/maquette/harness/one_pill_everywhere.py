"""R509 — the one pill everywhere: Médiathèque and Suivis filter and sort with the Torrents tab's selector.

DECIDED 1 of maquette-blocked, the operator's word: « J'aime beaucoup le
composant filtre des trackers mis sur la liste des torrents, j'aimerai qu'on
utilise celui là et qu'on aille plus loin qu'on remplace les autres filtres
(médiathèque et suivis: Tout, films, séries) par ce nouveau composant ! » — and
beside each filter pill, a sort pill of the same component (DESIGN § 1.9). His
round 3 q1 = C gave Suivis five sorts: « Urgence » (today's one fixed order),
« A → Z », « Z → A », « Suivi récemment » (the follow's creation, `addedAt`),
« Prochaine sortie » (`nextAirDate`, a follow with none last) — BK8.

What this holds:

1. ONE MARKUP: Trackers › « Torrents », « À traiter », the Médiathèque and
   Suivis each draw their filter pill as `data-part="pill/select"`, every one
   with the same class and `aria-haspopup="dialog"` — the one component, fed
   four lists of choices; no row of `data-cat` / `data-pill` pills remains;
2. MÉDIATHÈQUE: the filter pill reads « Tout » and the library's count, not
   pressed; a finger opens the panel of categories, each with its count, in the
   order the categories are served; « Films » filters — the pill says it,
   pressed, with the category's count, and the list draws films alone; on
   « Incomplets » the panel's counts are the lens' own (« Films » 0);
3. MÉDIATHÈQUE's sort pill, beside it, says the way in force; a finger opens the
   panel of its SIX ways (the names `features/library/sorting.ts` publishes),
   the one in force checked; « Z → A » orders the list the other way of
   « A → Z », and the pill says it, pressed;
4. the category and the sort are REMEMBERED as they were: another page and back,
   both still in force;
5. SUIVIS: the filter pill reads « Tout » and the follows counted; its panel
   offers « Tout », « Séries », « Films » with their counts; « Films » keeps the
   films alone, the pill pressed with its count;
6. SUIVIS' sort pill opens its FIVE ways, « Urgence » checked; « Prochaine
   sortie » orders the follows by `nextAirDate`, soonest first, those with none
   last; « Suivi récemment » by `addedAt`, newest first; « A → Z » by French
   collation;
7. after a reload, Suivis' filter and sort are still in force (the device's
   memory, as « À traiter »'s);
8. the six named states of § 3 exist;
9. AT 320 PX, the narrowest phone: on the Médiathèque under its longest sort
   (« Les plus incomplets ») and on Suivis under « Prochaine sortie », the two
   pills are whole — no word cut, the strip not scrolling, no pill under the view
   switch, the page not wider than the screen.

Red before the lot's phase 6: the Médiathèque and Suivis draw rows of pills
(DESIGN § 4).
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
FR = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
ACQ = FR["screens"]["acquisition"]
FOLLOW_SORTS = ACQ.get("followSort", {})
FOLLOW_SORT_ORDER = ["urgency", "az", "za", "added", "nextRelease"]
FOLLOW_FILTERS = [ACQ["pillAll"], ACQ["pillSeries"], ACQ["pillMovies"]]
STATES = ["library-filter-panel", "library-sort-panel", "library-filter-movies",
          "follows-filter-panel", "follows-sort-panel", "follows-sort-next-release"]
# Where each surface's filter pill stands, the state that draws it, and the
# attribute its tap raises.
SURFACES = [
    ("Trackers › « Torrents »", "torrents-selector", "data-trackers-selector"),
    ("« À traiter »", "acq-todo-every-cause", "data-todo-filter-pill"),
    ("Médiathèque", "lib-list", "data-library-filter-pill"),
    ("Suivis", "acq-follows-list", "data-follows-filter-pill"),
]

PILL = """(verb) => {
  const node = document.querySelector(`#view [data-part="pill/select"][${verb}]`);
  return node ? {className: node.className, popup: node.getAttribute('aria-haspopup'),
    text: node.firstChild?.textContent.trim() ?? '', pressed: node.getAttribute('aria-pressed') === 'true',
    count: node.querySelector('[data-part="pill/select-count"]')?.textContent.trim() ?? null} : null;
}"""
ROWS = """() => ({cats: document.querySelectorAll('#view [data-cat]').length,
  pills: document.querySelectorAll('#view [data-pill]').length})"""
CHOICES = """() => { const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return null;
  return [...sheet.querySelectorAll('[data-part="option"]')].map(choice => ({
    text: choice.querySelector('.lb')?.firstChild?.textContent.trim() ?? '',
    hint: choice.querySelector('small')?.textContent.trim() ?? '',
    checked: choice.getAttribute('aria-checked') === 'true'})); }"""
CATEGORIES = """() => window.__queries.getQueryData(['/api/v1/library/categories']) ?? null"""
LIBRARY_TITLES = """() => [...document.querySelectorAll('#libitems [data-part="card/title"], #libitems [data-part="tile"] [data-part="tile/title"]')]
  .map((element) => element.textContent.trim())"""
LIBRARY_ROWS = """() => (window.__queries.getQueryCache().getAll().filter(q => q.queryKey[0] === '/api/v1/library/items')
  .sort((l, r) => r.state.dataUpdatedAt - l.state.dataUpdatedAt)[0]?.state.data?.pages ?? []).flatMap(p => p.items)
  .map(item => ({title: item.title, category: item.category}))"""
FOLLOW_TITLES = """() => [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-part="card/title"]')]
  .filter(title => !title.closest('[data-part="section/paused"]')).map(title => title.textContent.trim())"""
FOLLOWS = """() => window.__queries.getQueryData(['/api/v1/acquisition/followed', '']) ?? null"""


async def tap(page, selector):
    """Taps the first element a selector finds, if any, and lets it act."""
    target = page.locator(selector)
    found = await target.count()
    if found:
        await target.first.tap()
        await page.wait_for_timeout(ACTED)
    return found


async def choose(page, pill, text):
    """Opens a pill's panel and taps the choice that reads `text`, exactly."""
    await tap(page, f'#view [data-part="pill/select"][{pill}]')
    choices = page.locator('#sheet[data-open] [data-part="option"]')
    for index in range(await choices.count()):
        label = await choices.nth(index).evaluate(
            "(choice) => choice.querySelector('.lb')?.firstChild?.textContent.trim() ?? ''")
        if label == text:
            await choices.nth(index).tap()
            await page.wait_for_timeout(ACTED)
            return True
    return False


async def go(page, state):
    """Drives a named state and lets it settle; answers the error, if any."""
    answer = await page.evaluate("(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    return answer


async def one_markup(journal, page):
    """Hold 1: the four filter pills are the one component; no row of pills remains."""
    drawn = {}
    for name, state, verb in SURFACES:
        await go(page, state)
        await page.wait_for_timeout(SETTLED)
        drawn[name] = await page.evaluate(PILL, verb)
        rows = await page.evaluate(ROWS)
        journal.check(f"{name}: no row of data-cat / data-pill pills remains",
                      rows["cats"] == 0 and rows["pills"] == 0, repr(rows))
    reference = drawn[SURFACES[0][0]]
    for name, pill in drawn.items():
        journal.check(f"{name} draws its filter pill from the one markup (pill/select, the same class, a dialog)",
                      pill is not None and reference is not None and pill["className"] == reference["className"]
                      and pill["popup"] == "dialog", repr(pill))


async def library(journal, page):
    """Holds 2 to 4: the Médiathèque's filter pill and sort pill."""
    await go(page, "lib-list")
    categories = await page.evaluate(CATEGORIES) or []
    whole = next((category for category in categories if category["id"] == "all"), None)
    movies = next((category for category in categories if category["id"] == "movies"), None)
    pill = await page.evaluate(PILL, "data-library-filter-pill")
    journal.check("Médiathèque: the filter pill reads « Tout » and the library's count, not pressed",
                  pill is not None and whole is not None and pill["text"] == whole["label"]
                  and pill["count"] == str(whole["count"]) and not pill["pressed"], repr(pill))
    await tap(page, '#view [data-part="pill/select"][data-library-filter-pill]')
    await page.wait_for_timeout(PANEL_IN)
    choices = await page.evaluate(CHOICES)
    journal.check("a finger opens the categories, served order, each with its count, « Tout » checked",
                  choices is not None and [choice["text"] for choice in choices] == [c["label"] for c in categories]
                  and all(str(category["count"]) in choice["hint"] for choice, category in zip(choices, categories))
                  and choices[0]["checked"], repr(choices))
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(ACTED)
    chosen = movies is not None and await choose(page, "data-library-filter-pill", movies["label"])
    pill = await page.evaluate(PILL, "data-library-filter-pill")
    rows = await page.evaluate(LIBRARY_ROWS)
    journal.check("« Films » filters: the pill says it, pressed, with the category's count; films alone listed",
                  chosen and pill is not None and pill["text"] == movies["label"] and pill["pressed"]
                  and pill["count"] == str(movies["count"]) and rows
                  and all(row["category"] in movies["includes"] for row in rows),
                  f"{pill!r} · {len(rows)} rows, categories {sorted({row['category'] for row in rows})}")

    ways = await page.evaluate("()=>window.__sortWays()")
    names = [name for key in ways for name in (ways[key]["normal"], ways[key]["inverse"])]
    sort = await page.evaluate(PILL, "data-sort")
    journal.check("the sort pill stands beside it, saying the way in force, not pressed",
                  sort is not None and sort["text"] == ways.get("recent", {}).get("normal") and not sort["pressed"]
                  and sort["className"] == (pill or {}).get("className"), repr(sort))
    await tap(page, '#view [data-part="pill/select"][data-sort]')
    await page.wait_for_timeout(PANEL_IN)
    choices = await page.evaluate(CHOICES)
    journal.check("a finger opens its SIX ways, by their names, the one in force checked",
                  choices is not None and len(names) == 6 and [choice["text"] for choice in choices] == names
                  and [choice["checked"] for choice in choices] == [True, False, False, False, False, False],
                  repr(choices))
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(ACTED)
    await choose(page, "data-library-filter-pill", whole["label"] if whole else "")
    # french-ok: a French search WORD, typed into the app's own search.
    await page.evaluate("()=>{window.__store.write({q: 'star'}); window.__store.touch();}")
    await page.wait_for_timeout(SETTLED)
    await choose(page, "data-sort", ways["az"]["normal"])
    ascending = await page.evaluate(LIBRARY_TITLES)
    await choose(page, "data-sort", ways["az"]["inverse"])
    descending = await page.evaluate(LIBRARY_TITLES)
    sort = await page.evaluate(PILL, "data-sort")
    journal.check(f"« {ways['az']['inverse']} » orders the list the other way of « {ways['az']['normal']} », the pill says it, pressed",
                  len(ascending) > 1 and descending == list(reversed(ascending))
                  and sort is not None and sort["text"] == ways["az"]["inverse"] and sort["pressed"],
                  f"{ascending[:2]} … / {descending[:2]} … · {sort!r}")

    await page.evaluate("()=>{window.__store.write({q: ''}); window.__store.touch();}")
    await choose(page, "data-library-filter-pill", movies["label"] if movies else "")
    await tap(page, '#nav button[data-page="acq"]')
    await tap(page, '#nav button[data-page="lib"]')
    pill = await page.evaluate(PILL, "data-library-filter-pill")
    sort = await page.evaluate(PILL, "data-sort")
    journal.check("another page and back: the category and the sort are still in force",
                  pill is not None and movies is not None and pill["text"] == movies["label"]
                  and sort is not None and sort["text"] == ways["az"]["inverse"], f"{pill!r} · {sort!r}")

    await page.evaluate("()=>{window.__store.write({libLens: 'inc', libCat: 'all'}); window.__store.touch();}")
    await page.wait_for_timeout(SETTLED)
    await tap(page, '#view [data-part="pill/select"][data-library-filter-pill]')
    await page.wait_for_timeout(PANEL_IN)
    choices = await page.evaluate(CHOICES) or []
    film = next((choice for choice in choices if movies and choice["text"] == movies["label"]), None)
    journal.check("on « Incomplets », the panel counts the lens' own rows (« Films » 0)",
                  film is not None and film["hint"][:1] == "0", repr(film))
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(ACTED)


def ordered(values, newest_first):
    """Whether a run of dated values is ordered, the ones with no date last."""
    dated = [value for value in values if value is not None]
    return (values[:len(dated)] == dated
            and dated == sorted(dated, reverse=newest_first))


async def follows(journal, page):
    """Holds 5 to 7: Suivis' filter pill and sort pill."""
    await go(page, "acq-follows-list")
    seeded = await page.evaluate(FOLLOWS) or []
    active = [follow for follow in seeded if follow["status"] != "disabled"]
    films = [follow for follow in active if follow["kind"] == "movie"]
    pill = await page.evaluate(PILL, "data-follows-filter-pill")
    journal.check("Suivis: the filter pill reads « Tout » and the follows counted, not pressed",
                  pill is not None and pill["text"] == ACQ["pillAll"] and pill["count"] == str(len(active))
                  and not pill["pressed"], repr(pill))
    await tap(page, '#view [data-part="pill/select"][data-follows-filter-pill]')
    await page.wait_for_timeout(PANEL_IN)
    choices = await page.evaluate(CHOICES)
    journal.check("a finger opens « Tout », « Séries », « Films », each with its count, « Tout » checked",
                  choices is not None and [choice["text"] for choice in choices] == FOLLOW_FILTERS
                  and [choice["hint"].split(" ")[0] for choice in choices]
                  == [str(len(active)), str(len(active) - len(films)), str(len(films))]
                  and choices[0]["checked"], repr(choices))
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(ACTED)
    await choose(page, "data-follows-filter-pill", ACQ["pillMovies"])
    pill = await page.evaluate(PILL, "data-follows-filter-pill")
    titles = await page.evaluate(FOLLOW_TITLES)
    journal.check("« Films » keeps the films alone, the pill pressed with its count",
                  pill is not None and pill["text"] == ACQ["pillMovies"] and pill["pressed"]
                  and pill["count"] == str(len(films)) and sorted(titles) == sorted(f["title"] for f in films),
                  f"{pill!r} · {titles}")
    await choose(page, "data-follows-filter-pill", ACQ["pillAll"])

    sort = await page.evaluate(PILL, "data-follows-sort-pill")
    journal.check("the sort pill stands beside it, « Urgence », not pressed, from the same markup",
                  sort is not None and sort["text"] == FOLLOW_SORTS.get("urgency") and not sort["pressed"]
                  and pill is not None and sort["className"] == pill["className"], repr(sort))
    await tap(page, '#view [data-part="pill/select"][data-follows-sort-pill]')
    await page.wait_for_timeout(PANEL_IN)
    choices = await page.evaluate(CHOICES)
    journal.check("a finger opens its FIVE ways, in his order, « Urgence » checked",
                  choices is not None and len(FOLLOW_SORTS) == 5
                  and [choice["text"] for choice in choices] == [FOLLOW_SORTS.get(key) for key in FOLLOW_SORT_ORDER]
                  and choices[0]["checked"], repr(choices))
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(ACTED)

    by_title = {follow["title"]: follow for follow in active}
    await choose(page, "data-follows-sort-pill", FOLLOW_SORTS.get("nextRelease"))
    titles = await page.evaluate(FOLLOW_TITLES)
    dates = [by_title.get(title, {}).get("nextAirDate") for title in titles]
    journal.check("« Prochaine sortie »: soonest first, a follow with none last",
                  len(titles) == len(active) and any(dates) and None in dates and ordered(dates, newest_first=False),
                  str(list(zip(titles, dates))))
    await choose(page, "data-follows-sort-pill", FOLLOW_SORTS.get("added"))
    titles = await page.evaluate(FOLLOW_TITLES)
    added = [by_title.get(title, {}).get("addedAt") for title in titles]
    journal.check("« Suivi récemment »: the newest follow first",
                  len(titles) == len(active) and all(added) and ordered(added, newest_first=True),
                  str(list(zip(titles, added))))
    await choose(page, "data-follows-sort-pill", FOLLOW_SORTS.get("az"))
    titles = await page.evaluate(FOLLOW_TITLES)
    collated = await page.evaluate("(titles)=>[...titles].sort((a, b) => a.localeCompare(b, 'fr'))", titles)
    journal.check("« A → Z »: by French collation", len(titles) > 1 and titles == collated, str(titles))

    await choose(page, "data-follows-sort-pill", FOLLOW_SORTS.get("nextRelease"))
    await choose(page, "data-follows-filter-pill", ACQ["pillSeries"])
    await page.reload(wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.wait_for_timeout(SETTLED)
    await tap(page, '#nav button[data-page="acq"]')
    await tap(page, '[data-acqtab="follows"]')
    pill = await page.evaluate(PILL, "data-follows-filter-pill")
    sort = await page.evaluate(PILL, "data-follows-sort-pill")
    journal.check("after a reload, Suivis' filter and sort are still in force",
                  pill is not None and pill["text"] == ACQ["pillSeries"]
                  and sort is not None and sort["text"] == FOLLOW_SORTS.get("nextRelease"), f"{pill!r} · {sort!r}")


NARROW = {"viewport": {"width": 320, "height": 844}}
FIT = """() => {
  const strip = document.querySelector('#view [data-part="pill/list"]');
  const views = document.querySelector('#view [data-part="view/switch"]');
  const pills = [...document.querySelectorAll('#view [data-part="pill/select"]')];
  return {
    pills: pills.map((pill) => ({text: pill.textContent.trim(), whole: pill.scrollWidth <= pill.clientWidth,
      clear: !views || pill.getBoundingClientRect().right <= views.getBoundingClientRect().left})),
    scrolls: !strip || strip.scrollWidth > strip.clientWidth,
    page: document.documentElement.scrollWidth,
  };
}"""


async def narrow(journal, browser):
    """Hold 9: at 320 px, the two pills are whole beside the view switch."""
    context, page = await open_page(browser, **NARROW)
    for name, state, dials in (
        ("Médiathèque", "lib-list", "{sortKey: 'missing', sortReversed: false}"),
        ("Suivis", "follows-sort-next-release", "{}"),
    ):
        await go(page, state)
        await page.evaluate(f"()=>{{window.__store.write({dials}); window.__store.touch();}}")
        await page.wait_for_timeout(SETTLED)
        fit = await page.evaluate(FIT)
        journal.check(f"at 320 px, {name}: two pills whole, beside the view switch, nothing scrolls sideways",
                      len(fit["pills"]) == 2 and all(pill["whole"] and pill["clear"] for pill in fit["pills"])
                      and not fit["scrolls"] and fit["page"] <= NARROW["viewport"]["width"], repr(fit))
    await context.close()


async def main():
    journal = Journal("R509 — the one pill everywhere: Médiathèque and Suivis")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await one_markup(journal, page)
        await library(journal, page)
        await follows(journal, page)
        for state in STATES:
            answer = await go(page, state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await narrow(journal, browser)
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
