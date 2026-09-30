"""R-L16bis-k — Découvrir's header: beside the view switch, and every figure read.

The operator, 2026-09-29 16:52: the header's message beside the view buttons, its
content replaced by something useful; his Q8: « n séries et m films à découvrir ».
The four `fr.json` strings it drew — « Réserve remplie il y a 2 h », « 503 »,
« 1 832 », « ids TMDB possédés exclus » — were copy standing as figures (§ 13).

1. `discover-header`: the message is in the view row — the pill place beside the
   view switch — and not in the page's body; in each view (list, posters, deck);
2. its two figures are the suggestions already read, split by kind, the rejected
   left out — and a rejection moves them in the render that follows;
3. no copy stands as a figure: the four `live*` strings are gone from `fr.json`;
4. `discover-header-narrow`, at 369 px: one line, cut at the switch and never
   past it — and its tap opens the sentence whole;
5. `discover-header-loading` and `discover-header-unavailable` say so, never blank.

Red before the move: the message is a child of `discover/body`, and its figures
are `fr.json` strings.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
ALL = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
WORDS = ALL["screens"]["acquisition"]
LITERALS = ("liveBefore", "liveSuggestions", "liveMiddle", "liveOwned", "liveAfter")

HEADER = """() => {
  const header = document.querySelector('#view [data-part="discover/header"]');
  if (!header) return null;
  const text = header.querySelector('[data-part="discover/header-text"]');
  const row = header.closest('.pillbar');
  const box = header.getBoundingClientRect(), view = row?.querySelector('[data-part="view/switch"]')?.getBoundingClientRect();
  const style = text ? getComputedStyle(text) : null;
  return {
    text: text?.textContent.trim() ?? '',
    inRow: !!row && !!view, inBody: !!header.closest('[data-region="discover/body"]'),
    beside: view ? box.right <= view.left + 1 : false,
    oneLine: text ? text.getBoundingClientRect().height <= parseFloat(style.lineHeight || '20') * 1.5 : false,
    cut: text ? text.scrollWidth > text.clientWidth : false,
  };
}"""
# The figures the header must say, counted here from the answer the layer served.
COUNTED = """() => {
  const reserve = window.__suggestions?.() ?? [];
  const gone = window.state?.sugGone ?? new Set();
  const left = reserve.filter((_, position) => !gone.has(position));
  const films = left.filter((one) => one.kind === 'Film').length;
  return {series: left.length - films, films};
}"""


def sentence(series, films):
    """The header's sentence, as the interface's words compose it."""
    def plural(key, count):
        return WORDS[f"{key}_{'one' if count == 1 else 'other'}"].replace("{{count}}", str(count))
    return (WORDS["headerCount"].replace("{{series}}", plural("headerSeries", series))
            .replace("{{films}}", plural("headerFilms", films)))


async def enter(page, state, wait=SETTLED):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(wait)
    return answer


async def main():
    journal = Journal("R-L16bis-k — Découvrir's header: beside the view switch, every figure read")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await enter(page, "discover-header")
        header = await page.evaluate(HEADER)
        counted = await page.evaluate(COUNTED)
        wanted = sentence(counted["series"], counted["films"])
        journal.check("the message sits in the view row, beside the switch, not in the body",
                      answer is None and header is not None and header["inRow"] and header["beside"]
                      and not header["inBody"], answer or repr(header))
        journal.check(f"it says the suggestions read, split by kind: « {wanted} »",
                      header is not None and header["text"] == wanted and counted["series"] + counted["films"] > 0,
                      repr(header and header["text"]))
        for mode in ("poster", "deck"):
            await page.evaluate(f"()=>{{window.__store.write({{sugMode: '{mode}'}}); window.__store.touch();}}")
            await page.wait_for_timeout(ACTED)
            seen = await page.evaluate(HEADER)
            journal.check(f"in the {mode} view too", seen is not None and seen["text"] == wanted and seen["inRow"],
                          repr(seen))
        await page.evaluate("()=>{window.__store.write({sugMode: 'list'}); window.__store.touch();}")
        await page.wait_for_timeout(ACTED)
        await page.evaluate("""()=>{const first = document.querySelector('#view [data-part="suggestion/wrap"]');
          if (first) { window.state.sugGone.add(Number(first.dataset.dismissable)); window.__store.touch(); }}""")
        await page.wait_for_timeout(ACTED)
        header = await page.evaluate(HEADER)
        counted = await page.evaluate(COUNTED)
        journal.check("a rejection moves the figures in the render that follows — they are read, never copy",
                      header is not None and header["text"] == sentence(counted["series"], counted["films"])
                      and header["text"] != wanted, f"{header and header['text']!r} after {wanted!r}")
        journal.check("no copy stands as a figure: the four live strings are gone",
                      not any(key in WORDS for key in LITERALS), str([key for key in LITERALS if key in WORDS]))

        await page.set_viewport_size({"width": 369, "height": 800})
        await enter(page, "discover-header")
        header = await page.evaluate(HEADER)
        journal.check("at 369 px: one line, cut at the switch and never past it",
                      header is not None and header["oneLine"] and header["beside"], repr(header))
        tap = page.locator('#view [data-discover-header]')
        if await tap.count():
            await tap.first.tap()
            await page.wait_for_timeout(ACTED)
        whole = await page.evaluate("""()=>document.querySelector('#sheet[data-open]')?.textContent ?? null""")
        journal.check("its tap opens the sentence whole",
                      whole is not None and (header or {}).get("text", "<none>") in whole, repr(whole))
        answer = await enter(page, "discover-header-narrow")
        journal.check("the named state discover-header-narrow opens it", answer is None
                      and await page.evaluate("()=>document.querySelector('#sheet')?.hasAttribute('data-open') ?? false"),
                      answer or "")
        await page.set_viewport_size({"width": 390, "height": 844})

        for state, key in (("discover-header-loading", "headerLoading"), ("discover-header-unavailable", "headerUnavailable")):
            answer = await enter(page, state)
            header = await page.evaluate(HEADER)
            journal.check(f"{state}: says « {WORDS.get(key, '<no copy>')} », never blank",
                          answer is None and header is not None and header["text"] == WORDS.get(key), answer or repr(header))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
