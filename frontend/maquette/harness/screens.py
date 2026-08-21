"""R71 — a screen above another one: back redraws the screen it covered.

The screen layer replaces its content in place, so a poster tapped on the add
screen draws the media sheet where the result list stood. The layer used to
hold ONE history entry however many screens succeeded each other inside it,
and a back from the sheet closed the whole layer — the operator lost the very
list they came from, query, filter and scroll included.

Each direct replacement now pushes its own entry and records how to redraw
the screen it covers. This rule walks the reported journey — results → sheet
→ back — through BOTH exits (the browser back and the « Retour » button) and
holds four things: the list is redrawn with its query, its scroll position
survives, one more back actually leaves the layer, and a result card carries
no inline action in its foot — the panel is the single path to the act, which
is what keeps the card the size of what it lists.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

_journal = None


def check(name, condition, detail=""):
    return _journal.check(name, condition, detail)


async def main():
    global _journal
    _journal = Journal("R71 — the back redraws the screen it covered")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(browser)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        await pg.evaluate("()=>window.__go('acq-add-results')")
        await pg.wait_for_timeout(400)
        # The add screen left `#screen` for a real route (`/add`, rendered
        # inside `#coquille`): its results list is `[data-part="screen"][data-open]`, not
        # literally `#screen` — and so is the FICHE this journey opens further
        # down (`/mediasheet/$title`). Each is named by its own `data-key`.
        start = await pg.evaluate("""()=>({
            screen: !!document.querySelector('[data-part="screen"][data-open]'),
            key: document.querySelector('[data-part="screen"][data-open]')?.dataset.key,
            cards: document.querySelectorAll('[data-part="result/list"] [data-part="card"]').length,
            feet: document.querySelectorAll('[data-part="result/list"] [data-part="card/foot"]').length,
            query: document.querySelector('#addq')?.value})""")
        check("the results screen is there", start["screen"] and start["cards"] >= 2,
              f"{start['cards']} cards · key {start['key']}")
        check("a result card carries no action in its foot",
              start["feet"] == 0, f"{start['feet']} foot(s)")

        # The removal above is safe only because the act still has a home:
        # the result's panel must offer it.
        await pg.evaluate("""()=>document.querySelector('[data-part="result/list"] [data-part="card/body"]').click()""")
        await pg.wait_for_timeout(420)
        act = await pg.evaluate(
            """()=>document.querySelector('#sheet [data-part="sheet/action"][data-tone="primary"]')?.textContent.trim() ?? null""")
        check("the result's panel carries the act", bool(act), f"« {act} »")
        await pg.evaluate("()=>window.__close('sheet')")
        await pg.wait_for_timeout(300)

        # ── The reported journey, exit 1: the browser back ──────────────────
        await pg.evaluate("""()=>{document.querySelector('[data-part="screen"][data-open] [data-part="viewport"]').scrollTop = 300;}""")
        await pg.evaluate("""()=>document.querySelector('[data-part="result/list"] [data-part="card/poster"]').click()""")
        await pg.wait_for_timeout(450)
        # The poster's target is a MEDIA SHEET, and it left `#screen` for a
        # real route (`/mediasheet/$title`, rendered inside `#coquille`) as the add
        # screen did before it. It is read by its own IDENTITY — the screen
        # carrying `data-key="mediaSheet:…"` — and not by a bare `[data-part="screen"][data-open]`:
        # two screens can carry `open` at once, and a selector that cannot
        # tell them apart is exactly the ambiguity the explicit reads below
        # exist to remove.
        sheet_screen = await pg.evaluate("""()=>{
            const f = document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
            return {screen: !!f, hero: !!f?.querySelector('[data-part="hero"]'),
                    key: f?.dataset.key};}""")
        check("the poster opens the media sheet on the same layer",
              sheet_screen["screen"] and sheet_screen["hero"], f"key {sheet_screen['key']}")

        await pg.go_back()
        await pg.wait_for_timeout(500)
        # R-7: `[data-part="screen"][data-open]` alone is AMBIGUOUS once two screens can carry
        # `open` at the same time — the arrival is therefore identified by its
        # `data-key` below, and the screen one is leaving is looked up by ITS
        # own key rather than by a class shared with everything else. A mediaSheet
        # that failed to close is what a bare `[data-part="screen"][data-open]` would mask, so it
        # is read explicitly, by identity.
        back = await pg.evaluate("""()=>({
            screen: !!document.querySelector('[data-part="screen"][data-open]'),
            key: document.querySelector('[data-part="screen"][data-open]')?.dataset.key,
            cards: document.querySelectorAll('[data-part="result/list"] [data-part="card"]').length,
            query: document.querySelector('#addq')?.value,
            scroll: document.querySelector('[data-part="screen"][data-open] [data-part="viewport"]')?.scrollTop,
            sheetStillThere: !!document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]')})""")
        check("the back redraws the results list",
              back["screen"] and (back["key"] or "").startswith("add:")
              and back["cards"] == start["cards"]
              and back["query"] == start["query"],
              f"{back['cards']} cards · query « {back['query']} »")
        check("with its scroll position",
              abs(back["scroll"] - 300) <= 40, f"{back['scroll']}px")
        check("and the media sheet is gone",
              not back["sheetStillThere"], f"sheet open={back['sheetStillThere']}")

        await pg.go_back()
        await pg.wait_for_timeout(450)
        left = await pg.evaluate("""()=>({
            screen: !!document.querySelector('[data-part="screen"][data-open]'),
            page: state.page})""")
        check("and one more back leaves the layer",
              not left["screen"] and left["page"] == "acq",
              f"page {left['page']}")

        # ── Exit 2: the « Retour » button on the sheet ──────────────────────
        await pg.evaluate("()=>window.__go('acq-add-results')")
        await pg.wait_for_timeout(400)
        await pg.evaluate("""()=>document.querySelector('[data-part="result/list"] [data-part="card/poster"]').click()""")
        await pg.wait_for_timeout(450)
        # Same mediaSheet as exit 1, and its own « Retour » is clicked on the screen
        # identified as the mediaSheet — never on whatever `[data-part="screen"][data-open]` happens to
        # resolve first.
        await pg.evaluate(
            """()=>document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"] [data-part="screen/back"]').click()""")
        await pg.wait_for_timeout(500)
        # R-7: same read by identity as exit 1's `back` — a mediaSheet that failed
        # to close here is exactly what a bare `[data-part="screen"][data-open]` would miss.
        button = await pg.evaluate("""()=>({
            screen: !!document.querySelector('[data-part="screen"][data-open]'),
            key: document.querySelector('[data-part="screen"][data-open]')?.dataset.key,
            cards: document.querySelectorAll('[data-part="result/list"] [data-part="card"]').length,
            sheetStillThere: !!document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]')})""")
        check("the sheet's « Retour » button does the same",
              button["screen"] and (button["key"] or "").startswith("add:")
              and button["cards"] == start["cards"],
              f"{button['cards']} cards")
        check("and the media sheet is gone here too",
              not button["sheetStillThere"], f"sheet open={button['sheetStillThere']}")

        await browser.close()
    _journal.summary(errors)


asyncio.run(main())
