"""R69 — the address carries the state, and a reload lands back where one was (DOIT-10).

« Chaque détail a son URL » is a rule of the constitution, and the prototype was
measurably not obeying it: `history.pushState` appeared four times and
`location` was read ZERO times. The interface told the browser where it was and
never once asked. That is not a debt to hand over with the binding mission — it
is a non-conformity, and one that shows: a reload landed on the opening page,
and no screen could be sent to anyone.

RENEGOTIATED BY L05, and this paragraph is the record rather than a rewrite of
history. This rule used to state the opposite of what it now holds, on purpose
and with its reason: « the state travels in the QUERY rather than in the path,
because this file is opened from a static server, from a design host and from
`file://`, and a path-based route needs a server that rewrites every unknown
path onto the document — two of those three cannot. »

D1 replaces that premise and accepts its cost explicitly. The path carries the
IDENTITY — which thing is being looked at — and the query carries the STATE —
how it is being looked at. `/media?lens=inc`, never `?page=lib`. What is lost is
exactly one use, named: the prototype no longer opens by double-clicking the
file. What is gained is what the query could never give — a page that is a place
rather than a parameter, an address production already serves under the same
name, and a harness that can drive by URL instead of through a seam that dies
with the engine.

What this holds to:

1. The opening address is the home page's own, and it carries no query — only
   what DIFFERS from the opening state is ever written, so the common case has
   a clean address and a link carries only what it means to carry.
2. Walking the interface WRITES the address: the page into the PATH, the dial
   into the query, one entry per arrival.
3. Reloading that address lands on the same screen — the finger's journey and
   the cold one end in the same place.
4. A wrong address is left ALONE. An unknown path renders the not-found
   surface, and deriving the address from it would rewrite a mistyped link into
   a different one — the interface correcting the operator's address behind
   their back. A browser answering 404 leaves it as typed.
5. Back walks the addresses in reverse, not only the screens.
6. No page identity survives in a query, and no dial in a path. This is
   invariant 1 read in both directions, and it is the hold the renegotiation
   adds: the shape D1 forbids is not merely absent today, it is refused.
7. The sign-in screen sits on a real path too. It is not a page — it is a
   layer covering everything — but it is what one SEES, and D1 gives every
   screen an address, so `/login` resolves to the page underneath plus the flag
   that raises the gate.
8. The bare root SETTLES rather than redirects. `/` names no page, so the boot
   replaces it with the home page's address — a replace, never a push, so
   nothing is inserted and the first Back still reaches the guard entry
   underneath instead of bouncing off a redirect.
"""
import asyncio

from common import PHONE
from playwright.async_api import async_playwright

PROTOTYPE = "http://127.0.0.1:8899/"

# The page a path names, and the dials a query may carry. Kept in step with
# `design/src/lib/addresses.ts`, which is the model this rule measures — a
# contract has three ends, and this is one of them.
HOME = "/acquisition"
LIBRARY = "/media"
ARRIVALS = "/arrivals"
DIAL_PARAMETERS = ("tab", "lens", "mode", "cat", "topic")

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


def path(url):
    """The path part of an address."""
    return url.split("?", 1)[0].split("http://127.0.0.1:8899", 1)[-1] or "/"


def query(url):
    """The query part of an address, or '' when it carries none."""
    return url.split("?", 1)[1] if "?" in url else ""


async def main():
    from common import Journal

    journal = Journal("R69 — the address carries the state, and a reload lands back on it")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── 1. the opening address is the home page's, and it is clean ─────
        ctx, pg, errors = await open_page(b)
        journal.check("the bare root settles onto the home page's own address",
                      path(pg.url) == HOME, pg.url)
        journal.check("and the opening address carries no query",
                      query(pg.url) == "", pg.url)

        # ── 7. the settling REPLACED, so the guard is still one back away ──
        # Had it pushed, this back would land on `/`, settle again, and the
        # guard would sit two entries down instead of one.
        await pg.go_back()
        await pg.wait_for_timeout(500)
        # `armedExit` is the ENGINE's own record that the guard entry was
        # popped — a live getter on the republished surface. The toast it also
        # raises is not the measure: the boot's design-notes hint shares that
        # element and wins the race, so a text test here reads the wrong toast
        # and reports on something else entirely. It did, on the first run.
        armed = await pg.evaluate("()=>window.armedExit")
        journal.check("the root SETTLED rather than redirected — one back reaches the guard",
                      bool(armed), f"armedExit={armed} · at {path(pg.url)}")
        await ctx.close()

        # ── the sign-in screen sits on a real path too ─────────────────────
        # It is not a page — it is a layer covering everything — but it is what
        # one SEES, and D1 gives every screen an address. Its address resolves
        # to the page UNDERNEATH plus the flag that raises the gate, which is
        # what lets a cold `/login` cover a frame already drawn.
        ctx, pg, errors = await open_page(b, PROTOTYPE + "login")
        gate = await pg.evaluate(
            """()=>({raised: !document.querySelector('#login').hidden,
                     page: state.page})""")
        journal.check("a cold /login raises the sign-in screen",
                      gate["raised"], f"raised={gate['raised']} over page={gate['page']}")
        journal.check("and it keeps its own address",
                      path(pg.url) == "/login", pg.url)
        journal.check("no JS error on a cold /login", not errors, str(errors))
        await ctx.close()

        # ── and the gate WRITES that address when it is raised from inside ──
        # The cold hold above reads the address; this one proves the other
        # direction. Without it the rule passes over a gate that never writes
        # anything — measured: severing the write left every hold above green.
        ctx, pg, errors = await open_page(b)
        before = path(pg.url)
        await pg.evaluate("()=>window.showSignIn(false)")
        await pg.wait_for_timeout(300)
        journal.check("raising the gate from inside writes its address",
                      path(pg.url) == "/login", f"{before} -> {path(pg.url)}")
        await pg.evaluate("()=>window.hideSignIn()")
        await pg.wait_for_timeout(300)
        journal.check("and letting it through gives the address back",
                      path(pg.url) == HOME, pg.url)
        journal.check("no JS error raising and clearing the gate", not errors, str(errors))
        await ctx.close()

        # ── 2. walking writes the address ──────────────────────────────────
        ctx, pg, errors = await open_page(b)
        await pg.tap('#nav button[data-page="lib"]')
        await pg.wait_for_timeout(360)
        journal.check("changing page writes the PATH",
                      path(pg.url) == LIBRARY and query(pg.url) == "", pg.url)

        await pg.tap('[data-lens="inc"]')
        await pg.wait_for_timeout(360)
        address = pg.url
        journal.check("changing a dial writes the QUERY, and leaves the path alone",
                      path(address) == LIBRARY and "lens=inc" in query(address), address)
        journal.check("and the address carries ONLY what differs from the opening state",
                      set(query(address).split("&")) == {"lens=inc"}, query(address))
        walked = await pg.evaluate(WHERE)

        # ── 6. neither half carries the other's business ───────────────────
        # The defect this refuses in both directions: a page id back in the
        # query (`?page=lib`, the shape D1 replaced) and a dial promoted into
        # the path (`/media/lens/inc`, the shape D1 names and forbids).
        journal.check("no page identity survives in the query",
                      "page=" not in query(address), query(address))
        segments = [s for s in path(address).split("/") if s]
        journal.check("and no dial is in the path",
                      not [s for s in segments if s in DIAL_PARAMETERS],
                      f"{segments}")
        await ctx.close()

        # ── 3. the cold journey ends where the finger's did ────────────────
        ctx, pg, errors = await open_page(b, address)
        cold = await pg.evaluate(WHERE)
        journal.check("reloading that address lands on the same screen",
                      (cold["page"], cold["lens"]) == (walked["page"], walked["lens"]),
                      f"{cold['page']}/{cold['lens']} vs {walked['page']}/{walked['lens']}")
        journal.check("and the address did not move on the way",
                      pg.url.endswith(address.split("8899", 1)[1]),
                      f"{pg.url} vs {address}")
        journal.check("no JS error on the cold load", not errors, str(errors))
        await ctx.close()

        # ── 4. a wrong address is left alone ───────────────────────────────
        wrong = PROTOTYPE + "nimportequoi"
        ctx, pg, errors = await open_page(b, wrong)
        lost = await pg.evaluate(WHERE)
        journal.check("an unknown address renders the surface made for it",
                      lost["page"] == "404", lost["page"])
        journal.check("and the interface NAMES what was asked for",
                      lost["notFound"] == "/nimportequoi", lost["notFound"])
        journal.check("and the address stays exactly as typed",
                      path(pg.url) == "/nimportequoi" and query(pg.url) == "", pg.url)
        journal.check("no JS error on an unknown address", not errors, str(errors))
        await ctx.close()

        # ── 5. back walks the addresses in reverse ─────────────────────────
        ctx, pg, errors = await open_page(b)
        await pg.tap('#nav button[data-page="lib"]')
        await pg.wait_for_timeout(340)
        await pg.tap('#nav button[data-page="arr"]')
        await pg.wait_for_timeout(340)
        journal.check("after two steps, the address is the second one's",
                      path(pg.url) == ARRIVALS, pg.url)
        await pg.go_back()
        await pg.wait_for_timeout(420)
        journal.check("a back returns to the first one's address",
                      path(pg.url) == LIBRARY, pg.url)
        journal.check("and the screen is the one that address names",
                      (await pg.evaluate(WHERE))["page"] == "lib",
                      (await pg.evaluate(WHERE))["page"])
        await pg.go_back()
        await pg.wait_for_timeout(420)
        journal.check("a second back returns to the opening address",
                      path(pg.url) == HOME and query(pg.url) == "", pg.url)
        journal.check("no JS error during the backs", not errors, str(errors))
        await ctx.close()

        await b.close()

    journal.summary()


asyncio.run(main())
