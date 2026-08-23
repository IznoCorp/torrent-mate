"""R69 — the URL carries the state, and a reload lands back where one was (DOIT-10).

« Chaque détail a son URL » is a rule of the constitution, and the prototype was
measurably not obeying it: `history.pushState` appeared four times and
`location` was read ZERO times. The interface told the browser where it was and
never once asked. That is not a debt to hand over with the binding mission — it
is a non-conformity, and one that shows: a reload landed on the opening page,
and no screen could be sent to anyone.

The state travels in the QUERY rather than in the path, which is a decision
rather than a shortcut: this file is opened from a static server, from a design
host and from `file://`, and a path-based route needs a server that rewrites
every unknown path onto the document — two of those three cannot. A query is
addressable everywhere, survives a reload and pastes into a message, which is
the whole of what DOIT-10 asks. The binding mission maps `?page=lib` onto
production's `/medias`; what is judged now is that the URL and the interface
never disagree.

What this holds to:

1. Only what DIFFERS from the opening state is written, so the common case has
   a clean address and a link carries only what it means to carry.
2. Walking the interface WRITES the address, one entry per arrival.
3. Reloading that address lands on the same screen — the finger's journey and
   the cold one end in the same place.
4. A wrong address is left ALONE. Rendering an unknown id moves the state onto
   the not-found surface, and deriving the address from it would rewrite a
   mistyped link into « ?page=404 » — the interface correcting the operator's
   address behind their back. A browser answering 404 leaves it as typed.
5. Back walks the addresses in reverse, not only the screens.
"""
import asyncio

from common import PHONE
from playwright.async_api import async_playwright

PROTOTYPE = "http://127.0.0.1:8899/"

WHERE = """() => ({
  page: state.page,
  tab: state.acqTab,
  lens: state.libLens,
  mode: state.libMode,
  empty: (document.querySelector('#view [data-part="empty-state"] b') || {}).textContent || '',
  notFound: state.notFound || '',
})"""


async def open_page(b, url=PROTOTYPE):
    """Opens the prototype AT AN ADDRESS, past the startup screen."""
    ctx = await b.new_context(**PHONE)
    pg = await ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    await pg.goto(url, wait_until="load")
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(280)
    return ctx, pg, errors


def query(url):
    """The query part of an address, or '' when it carries none."""
    return url.split("?", 1)[1] if "?" in url else ""


async def main():
    from common import Journal

    journal = Journal("R69 — the URL carries the state, and a reload lands back on it")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── 1. the opening state writes nothing ────────────────────────────
        ctx, pg, errors = await open_page(b)
        journal.check("the opening page has a clean address",
                         query(pg.url) == "", pg.url)

        # ── 2. walking writes the address ──────────────────────────────────
        await pg.tap('#nav button[data-page="lib"]')
        await pg.wait_for_timeout(360)
        after_tab = pg.url
        journal.check("changing tab writes the address",
                         "page=lib" in query(after_tab), after_tab)

        await pg.tap('[data-lens="inc"]')
        await pg.wait_for_timeout(360)
        address = pg.url
        journal.check("changing lens writes it too",
                         "lens=inc" in query(address), address)
        journal.check("and the address carries ONLY what differs from the opening state",
                         set(query(address).split("&")) == {"page=lib", "lens=inc"},
                         query(address))
        walked = await pg.evaluate(WHERE)
        await ctx.close()

        # ── 3. the cold journey ends where the finger's did ────────────────
        ctx, pg, errors = await open_page(b, address)
        cold = await pg.evaluate(WHERE)
        journal.check("reloading that address lands on the same screen",
                         (cold["page"], cold["lens"]) == (walked["page"], walked["lens"]),
                         f"{cold['page']}/{cold['lens']} vs {walked['page']}/{walked['lens']}")
        journal.check("and the address did not move on the way",
                         query(pg.url) == query(address),
                         f"{query(pg.url)} vs {query(address)}")
        journal.check("no JS error on the cold load", not errors, str(errors))
        await ctx.close()

        # ── 4. a wrong address is left alone ───────────────────────────────
        wrong = PROTOTYPE + "?page=nimportequoi"
        ctx, pg, errors = await open_page(b, wrong)
        lost = await pg.evaluate(WHERE)
        journal.check("an unknown address renders the surface made for it",
                         lost["page"] == "404", lost["page"])
        journal.check("and the interface NAMES what was asked for",
                         lost["notFound"] == "/nimportequoi", lost["notFound"])
        journal.check("and the address stays exactly as typed",
                         query(pg.url) == "page=nimportequoi", pg.url)
        journal.check("no JS error on an unknown address", not errors, str(errors))
        await ctx.close()

        # ── 5. back walks the addresses in reverse ─────────────────────────
        ctx, pg, errors = await open_page(b)
        await pg.tap('#nav button[data-page="lib"]')
        await pg.wait_for_timeout(340)
        await pg.tap('#nav button[data-page="arr"]')
        await pg.wait_for_timeout(340)
        journal.check("after two steps, the address is the second one's",
                         "page=arr" in query(pg.url), pg.url)
        await pg.go_back()
        await pg.wait_for_timeout(420)
        journal.check("a back returns to the first one's address",
                         "page=lib" in query(pg.url), pg.url)
        journal.check("and the screen is the one that address names",
                         (await pg.evaluate(WHERE))["page"] == "lib",
                         (await pg.evaluate(WHERE))["page"])
        await pg.go_back()
        await pg.wait_for_timeout(420)
        journal.check("a second back returns to the opening address",
                         query(pg.url) == "", pg.url)
        journal.check("no JS error during the backs", not errors, str(errors))
        await ctx.close()

        await b.close()

    journal.summary()


asyncio.run(main())
