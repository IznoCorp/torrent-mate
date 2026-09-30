"""R-L16bis-b, -c — the « Torrents » tab filters by tracker, and says what its colours mean.

The operator, 2026-09-29 (16:4x, points 2 and 3): « un sélecteur de tracker en
tête de liste » — the list of trackers is long, so ONE pill opens a panel of
choices rather than a row of pills hiding what is off-screen — and a legend of
every colour code the page draws, its absence being a defect (order 57). His Q5:
the legend is the one legend component, inline above the list, only the codes
present.

R-L16bis-b — the selector:
1. `torrents-selector`: ONE pill atop the list, « Tous les trackers », not pressed,
   counting every entry;
2. `torrents-list-filtered`: the pill names the tracker, pressed, counting its
   entries — and RULINGS 3's line « Filtré sur … · Tout voir » is gone;
3. a finger on the pill opens the panel: « Tous les trackers » first, then every
   tracker of the roster in its order, each with its entry count — and one
   switched off says so beside its name, in S7's words (off by you, or off and
   why: « Identifiant refusé », « Injoignable »), where an active one says none;
4. a choice closes the panel and filters: the list shows that tracker's entries
   alone, the pill names it, the address carries it — and nothing is pushed;
5. « Tous les trackers » lifts the filter;
6. `torrents-empty-filtered` keeps the pill pressed, so the filter can be lifted.

R-L16bis-c — the legend is complete:
7. on `torrents-list`, `torrents-legend` and `torrents-legend-partial`, every tone
   a card draws (a chip or a dot) has its legend entry, and no entry names a tone
   no card draws;
8. `torrents-legend` draws every code the page has — five tones at least — and each
   entry says the words of the chips it colours;
9. `torrents-legend-partial` — filtered to tr4ker — says only that list's codes.

RE-AIMED OUT LOUD — the successor of `trackers_roster.py`'s holds 12 and 13 (RULINGS
3's line and its « Tout voir »): the pill says the filter, and « Tous les
trackers » lifts it.

Hold 3's off-tracker clause came with the reader's N-bis (2026-09-30): the hint
was the count alone; red on `515c277bd`.

Red before the move: the tab draws no selector and no legend.
"""
import asyncio
import json
import pathlib

from common import ACTED, PAGE_PATHS, PROTOTYPE, SETTLED, Journal, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
DOWNLOADS = json.loads((SOURCE / "mocks/seeds/downloads.json").read_text(encoding="utf-8"))
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["torrents"]
TRACKER_WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["trackers"]
TRACKERS = json.loads((SOURCE / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))


def off_word(tracker):
    """What S7 says of a tracker switched off — by the operator, or off and why; None when it is on."""
    off = tracker.get("disabled")
    if off is None:
        return None
    if off["by"] == "operator":
        return TRACKER_WORDS.get("legendOperator", "<no copy>")
    return TRACKER_WORDS.get("failureReasons", {}).get(off.get("reason") or "other", "<no copy>")
ALL = WORDS.get("selectorAll", "<no copy>")
CHOSEN = "tr4ker"

PILL = """() => { const pills = [...document.querySelectorAll('#view [data-part="torrents/selector"]')];
  const pill = pills[0];
  return pill ? {count: pills.length, text: pill.firstChild?.textContent.trim() ?? '',
    pressed: pill.getAttribute('aria-pressed') === 'true',
    number: Number(pill.querySelector('[data-part="torrents/selector-count"]')?.textContent ?? NaN),
    line: document.querySelector('#view [data-part="torrents/filter"]') !== null} : null; }"""
ROWS = """() => [...document.querySelectorAll('#view [data-part="torrents/row"]')].map(row => row.dataset.tracker)"""
CHOICES = """() => { const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return null;
  return [...sheet.querySelectorAll('[data-part="option"]')].map(choice => ({
    text: choice.querySelector('.lb')?.firstChild?.textContent.trim() ?? '',
    hint: choice.querySelector('small')?.textContent.trim() ?? '',
    value: choice.getAttribute('data-trackers-choose'), checked: choice.getAttribute('aria-checked') === 'true'})); }"""
CODES = """() => {
  const drawn = [...document.querySelectorAll('#view [data-part="torrents/row"] [data-tone]')]
    .map(node => ({tone: node.dataset.tone, word: node.textContent.trim()}));
  const legend = [...document.querySelectorAll('#view [data-part="legend"] [data-tone]')]
    .map(entry => ({tone: entry.dataset.tone, text: entry.textContent.trim()}));
  return {drawn, legend, above: (() => {
    const legendBox = document.querySelector('#view [data-part="legend"]')?.getBoundingClientRect();
    const first = document.querySelector('#view [data-part="torrents/row"]')?.getBoundingClientRect();
    return legendBox && first ? legendBox.bottom <= first.top : null; })()};
}"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def complete(page, journal, state):
    """Hold 7 on one state: every drawn tone has its entry, no entry is idle."""
    answer = await enter(page, state)
    codes = await page.evaluate(CODES)
    drawn = {code["tone"] for code in codes["drawn"]}
    listed = {entry["tone"] for entry in codes["legend"]}
    journal.check(f"{state}: every tone drawn has its legend entry, above the list, and none is idle",
                  answer is None and bool(drawn) and drawn == listed and codes["above"] is True,
                  answer or f"drawn {sorted(drawn)} · legend {sorted(listed)} · above {codes['above']}")
    return codes


async def main():
    journal = Journal("R-L16bis-b/c — the « Torrents » tab filters by tracker and says what its colours mean")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── b: the pill ──────────────────────────────────────────────────────
        answer = await enter(page, "torrents-selector")
        pill = await page.evaluate(PILL)
        journal.check(f"one pill atop the list reads « {ALL} », not pressed, counting every entry",
                      answer is None and pill is not None and pill["count"] == 1 and pill["text"] == ALL
                      and not pill["pressed"] and pill["number"] == len(DOWNLOADS), answer or repr(pill))
        await enter(page, "torrents-list-filtered")
        pill = await page.evaluate(PILL)
        named = DOWNLOADS[0]["tracker"]
        journal.check(f"filtered, the pill names {named}, pressed, counting its entries — and the old line is gone",
                      pill is not None and pill["text"] == named and pill["pressed"] and not pill["line"]
                      and pill["number"] == sum(1 for entry in DOWNLOADS if entry["tracker"] == named),
                      repr(pill))

        # ── b: the panel, by a finger, from a cold address ───────────────────
        await page.goto(PROTOTYPE.rstrip("/") + PAGE_PATHS.get("trackers", "/trackers"), wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.wait_for_timeout(SETTLED)
        roster = await page.evaluate("()=>(window.__queries?.getQueryData(['/api/trackers']) || []).map(t => t.name)")
        selector = page.locator('#view [data-part="torrents/selector"]')
        if await selector.count():
            await selector.first.tap()
            await page.wait_for_timeout(ACTED)
        choices = await page.evaluate(CHOICES)
        wanted = [("", ALL, len(DOWNLOADS))] + [
            (name, name, sum(1 for entry in DOWNLOADS if entry["tracker"] == name)) for name in roster]
        journal.check("the pill opens the panel: « Tous les trackers », then every roster tracker in order, each counted",
                      choices is not None and bool(roster)
                      and [(choice["value"], choice["text"], choice["hint"].split(" ")[0]) for choice in choices]
                      == [(value, text, str(count)) for value, text, count in wanted],
                      f"{choices!r} against roster {roster}")
        hints = {choice["value"]: choice["hint"] for choice in choices or []}
        words = {tracker["name"]: off_word(tracker) for tracker in TRACKERS}
        every_off = {word for word in words.values() if word}
        journal.check("a tracker switched off says so beside its name, in S7's words; an active one says none",
                      bool(every_off) and all(
                          (word in hints.get(name, "")) if word else not any(one in hints.get(name, "") for one in every_off)
                          for name, word in words.items()),
                      f"{hints} against {words}")
        before = await page.evaluate("()=>history.length")
        option = page.locator(f'#sheet[data-open] [data-part="option"][data-trackers-choose="{CHOSEN}"]')
        if await option.count():
            await option.first.tap()
            await page.wait_for_timeout(ACTED)
        after = await page.evaluate("""()=>({length: history.length, search: location.search,
          open: document.querySelector('#sheet')?.hasAttribute('data-open') ?? false})""")
        rows = await page.evaluate(ROWS)
        pill = await page.evaluate(PILL)
        journal.check(f"a choice closes the panel and shows {CHOSEN}'s entries alone, the pill naming it",
                      not after["open"] and bool(rows) and set(rows) == {CHOSEN}
                      and pill is not None and pill["text"] == CHOSEN and pill["pressed"], f"{rows} · {pill!r}")
        journal.check("the address carries it, and the choice pushes nothing",
                      f"tracker={CHOSEN}" in after["search"] and after["length"] == before,
                      f"{after['search']!r} · history.length {before} -> {after['length']}")
        if await selector.count():
            await selector.first.tap()
            await page.wait_for_timeout(ACTED)
        every = page.locator('#sheet[data-open] [data-part="option"][data-trackers-choose=""]')
        if await every.count():
            await every.first.tap()
            await page.wait_for_timeout(ACTED)
        rows = await page.evaluate(ROWS)
        pill = await page.evaluate(PILL)
        journal.check(f"« {ALL} » lifts the filter: every entry, the pill unpressed",
                      len(rows) == len(DOWNLOADS) and pill is not None and not pill["pressed"], f"{len(rows)} · {pill!r}")

        await enter(page, "torrents-empty-filtered")
        pill = await page.evaluate(PILL)
        journal.check("nothing on the filtered tracker: the pill stays pressed, the filter can be lifted",
                      pill is not None and pill["pressed"] and pill["number"] == 0, repr(pill))

        # ── c: the legend ────────────────────────────────────────────────────
        await complete(page, journal, "torrents-list")
        codes = await complete(page, journal, "torrents-legend")
        tones = {entry["tone"] for entry in codes["legend"]}
        unsaid = [code for code in codes["drawn"]
                  if code["word"] and code["word"] in WORDS.get("states", {}).values()
                  and not any(code["word"] in entry["text"] for entry in codes["legend"] if entry["tone"] == code["tone"])]
        journal.check("torrents-legend draws five tones at least, each saying the state words it colours",
                      len(tones) >= 5 and not unsaid, f"{sorted(tones)} · unsaid {unsaid}")
        partial = await complete(page, journal, "torrents-legend-partial")
        journal.check("filtered to tr4ker, the legend says that list's codes alone",
                      {entry["tone"] for entry in partial["legend"]} < tones,
                      f"{sorted(entry['tone'] for entry in partial['legend'])} within {sorted(tones)}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
