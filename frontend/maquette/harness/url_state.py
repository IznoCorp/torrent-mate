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
   their back. A browser answering 404 leaves it as typed. This covers the
   BACK as well as the cold load: the guard puts back where one is, and that
   write is where the not-found state used to compose the home page's path.
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
9. A SCREEN address resolves to the page underneath it, exactly as `/login`
   does. A screen is a layer over the home frame, not a page of its own, so
   putting the not-found surface below it means the operator who opened a
   stable link is told the address leads nowhere the moment they close the
   screen. Every screen route is opened cold here, and one of them is closed.
10. A navigation write that fails is on record: the flag is raised by every
   writer, and this rule reads it. A refused write leaves the address and the
   interface disagreeing, and a disagreement nothing records is one nobody can
   find — so the flag is read with a write broken on purpose, and again at the
   end of an ordinary walk, where it must still be false.
"""
import asyncio
import json
import urllib.parse

from common import PHONE
from playwright.async_api import async_playwright

PROTOTYPE = "http://127.0.0.1:8899/"

# The page a path names, and the dials a query may carry. Kept in step with
# `design/src/lib/addresses.ts`, which is the model this rule measures — a
# contract has three ends, and this is one of them.
HOME = "/acquisition"
HOME_PAGE = "acq"
LIBRARY = "/media"
ARRIVALS = "/arrivals"
DIAL_PARAMETERS = ("tab", "lens", "mode", "cat", "topic")

# One concrete address per SCREEN route, the routes being the other end of the
# `SCREEN_PATHS` contract. The media sheet's is DERIVED from the running
# application rather than written down: it is keyed on a provider id, and a
# constant nothing verifies against its source rots the day the fixture moves.
SHEET_TITLE = "Silo (2023)"
QUALITY_PROFILE = "Test Profile"
RESOLUTION_FOLDER = "Backrooms.2026.MULTi.2160p.WEB-DL"
RELEASES_TITLE = "Silo"

# What the not-found surface says. Asserted, never authored: this is the
# interface's own rendered output, and translating it here would stop the hold
# measuring anything.
NOT_FOUND_TEXT = "Cette adresse ne mène nulle part."  # french-ok: rendered interface text a hold asserts

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

        # ── 10. a navigation write that FAILS is on record ─────────────────
        # Every writer in the engine logs and raises `__navEchec` when the
        # bridge refuses its write, because otherwise the address and the
        # interface disagree with nothing anywhere saying so. The sign-in
        # writers are the pair an address can reach without any gesture, so
        # they are the pair broken on purpose here: the bridge is a plain
        # object, so its `replace` is swapped for one that throws and put back
        # afterwards — `delete` restores nothing.
        ctx, pg, errors = await open_page(b)
        await pg.evaluate(
            """()=>{ window.__savedReplace = window.__bridge.replace;
                     window.__bridge.replace = () => { throw new Error("refused"); }; }""")
        await pg.evaluate("()=>window.showSignIn(false)")
        await pg.wait_for_timeout(300)
        broken = await pg.evaluate(
            """()=>({raised: !document.querySelector('#login').hidden,
                     failed: window.__navEchec})""")
        journal.check("the gate is raised even when its address cannot be written",
                      broken["raised"], f"raised={broken['raised']} at {path(pg.url)}")
        journal.check("and the failed navigation write is on record",
                      broken["failed"] is True, f"__navEchec={broken['failed']}")
        await pg.evaluate("()=>{ window.__bridge.replace = window.__savedReplace; }")
        await pg.evaluate("()=>window.hideSignIn()")
        await pg.wait_for_timeout(300)
        journal.check("no JS error when a navigation write is refused", not errors, str(errors))
        await ctx.close()

        # ── 9. a screen address resolves to the page UNDERNEATH ────────────
        # Same reasoning as `/login` above, applied to every screen route: a
        # screen covers the frame, so while it is open nothing reveals which
        # page it sits on — and a not-found page underneath surfaces only once
        # the screen closes, on the stable link the wave exists to serve.
        ctx, pg, errors = await open_page(b)
        sheet_ids = await pg.evaluate(f"()=>window.addressIdsFor({json.dumps(SHEET_TITLE)})")
        await ctx.close()
        journal.check("the media sheet's own address ids are resolvable",
                      bool(sheet_ids), f"{SHEET_TITLE} -> {sheet_ids}")
        sheet_address = f"media/{sheet_ids['provider']}/{sheet_ids['id']}"
        screens = [
            ("/add", "add"),
            ("/quality/$name", f"quality/{urllib.parse.quote(QUALITY_PROFILE)}"),
            ("/media/$provider/$id", sheet_address),
            ("/resolution/$folder", f"resolution/{urllib.parse.quote(RESOLUTION_FOLDER)}"),
            ("/releases/$title", f"releases/{urllib.parse.quote(RELEASES_TITLE)}"),
        ]
        for route, address in screens:
            ctx, pg, errors = await open_page(b, PROTOTYPE + address)
            under = await pg.evaluate(WHERE)
            journal.check(
                f"a cold {route} shows the home page underneath the screen",
                under["page"] == HOME_PAGE and under["notFound"] == "",
                f"/{address} -> page={under['page']} notFound={under['notFound']!r}")
            journal.check(f"no JS error on a cold {route}", not errors, str(errors))
            await ctx.close()

        # And the one walk that exposes what the cold reads cannot: closing the
        # screen. The frame underneath is what the operator is left with, so it
        # is the frame that has to be the home page rather than the surface
        # saying the address leads nowhere.
        ctx, pg, errors = await open_page(b, PROTOTYPE + sheet_address)
        await pg.evaluate(
            """()=>document.querySelector('[data-part="screen"][data-open]'
               + ' [data-part="screen/back"]').click()""")
        await pg.wait_for_timeout(420)
        closed = await pg.evaluate(WHERE)
        journal.check(
            "closing a screen opened cold leaves the home page showing, not the not-found one",
            closed["page"] == HOME_PAGE and NOT_FOUND_TEXT not in closed["empty"],
            f"page={closed['page']} empty={closed['empty']!r} at {path(pg.url)}")
        journal.check("no JS error closing a screen opened cold", not errors, str(errors))
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

        # The cold load is not where the rewrite happened. One Back reaches the
        # guard entry, the guard puts back where one IS, and THAT write is what
        # composed the home page's path over the address the operator typed —
        # a state composing to another state's address, invisible until the
        # gesture. So the walk is held, not only the arrival.
        await pg.go_back()
        await pg.wait_for_timeout(500)
        after_back = await pg.evaluate(WHERE)
        armed = await pg.evaluate("()=>window.armedExit")
        failed = await pg.evaluate("()=>window.__navEchec")
        journal.check("a Back from an unknown address re-pushes the address as typed, never the root",
                      path(pg.url) == "/nimportequoi" and query(pg.url) == "", pg.url)
        journal.check("and the surface it names is still the not-found one",
                      after_back["page"] == "404" and after_back["notFound"] == "/nimportequoi",
                      f"page={after_back['page']} notFound={after_back['notFound']!r}")
        journal.check("the Back reached the exit guard, which is what wrote that address back",
                      bool(armed), f"armedExit={armed}")
        journal.check("and composing the not-found address was answered, not refused",
                      failed is False, f"__navEchec={failed}")
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
        # The flag's general meaning, read once over an ordinary walk rather
        # than over an injected failure: pages, a dial and two backs have all
        # written the address, and none of those writes was refused. Nothing
        # ever clears the flag back to false, so this reads the whole walk.
        journal.check("no navigation write failed during the walk",
                      await pg.evaluate("()=>window.__navEchec") is False,
                      f"__navEchec={await pg.evaluate('()=>window.__navEchec')}")
        await ctx.close()

        await b.close()

    journal.summary()


asyncio.run(main())
