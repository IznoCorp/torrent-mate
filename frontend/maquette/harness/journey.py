"""R82 — Back retraces the path taken (§ 16).

The address model is R69's: what a page IS, what a dial is, and the boot seams
that write them. This rule holds the other half — WHERE BACK GOES. § 16
engraves it, and the shape it forbids is the one a web application betrays
itself with: a stack that grows with every tab tapped, so leaving means backing
over every page one merely passed through, and a Back meant to close a screen
undoes a sort instead.

The stack this holds to is the entry page plus at most one. Pages REPLACE each
other, settings REPLACE, and only an arrival — a screen, a panel — stacks.
Under all of it sits a floor, and under the floor the exit guard.

What this holds to:

1. A page opened COLD has a floor under it. The entry beneath a top-level page
   is the home page's own, so one Back lands there rendered, with the exit
   guard still one entry further down. Without that entry the same Back spends
   the guard, and whoever opened a link to the library is one gesture from
   leaving the application.
2. The not-found surface's own way out RECORDS rather than steps back, AND
   THE ENTRY IT WRITES IS THE FLOOR. A 404 arrival has no floor — the entry one
   down IS the exit guard — so the page switch that surface offers must write a
   new entry. Arming the guard on an arrival nobody made as a back would leave
   the document on the very next gesture, from the one surface whose whole
   purpose is to offer a way out. What that switch lays is a home entry, and
   every later switch has to reuse it: read off the arrival instead of off the
   writes, the floor was laid and the interface never knew, so five tab round
   trips read a depth of fourteen and twelve Backs to the exit. And that floor
   can be BACKED OFF, which the boot's own never can: the reader who steps
   below it is under a not-found arrival again, and the way out has to record
   there a second time rather than step onto the guard.
3. (c) Switching a top-level page STACKS NOTHING. Three pages walked leave
   exactly one entry behind, the entry page's own, so a Back from any of them
   lands there rendered with the guard still beneath — and tapping the entry
   page's own tab steps back onto that floor rather than laying a second copy
   of it down. The switches made from a LAYER obey the same rule, and they are
   where it was being broken: the drawer and the account menu used to give the
   destination the LAYER's entry, leaving the abandoned page's entry sandwiched
   underneath and three Backs to leave.
4. (d) The exit guard arms at the TOP and nowhere else. A Back from another
   page does not arm it; a Back from the entry page does. Read on the engine's
   own `armedExit`, because the address alone says nothing: a guard that arms
   one page too early answers the same address as one that does not.
5. (e) A setting leaves NO entry. A lens, an inner tab and a maintenance topic
   each write the address and leave the history depth exactly as it was, and
   one Back afterwards never UNDOES the setting. What that Back reaches is not
   the same on all three, which is why the hold names what they share: from the
   library and the maintenance page it leaves the surface, and from the
   acquisition tab — a setting made ON the entry page — it reaches the exit
   guard, the entry page being where the stack ends. A stack of settings is
   what makes Back undo a sort where the reader meant to leave the screen.
6. (a) A Back returns to the REAL ORIGIN, setting and all. Opening a sheet from
   a filtered library and backing off it lands on that filtered library, never
   on the page's root; opening a panel from the add screen's search and backing
   off it lands on the search. This is § 16 rule 1 said the way the reader
   feels it, and it is the hold rule 3 would break if it were applied without
   it — sending the reader who came from a search to the library.

The six are SEPARATE on purpose, and WHAT EACH READS beyond the address is not
the same — « every hold reads `history.length` and `armedExit` » is what this
paragraph used to claim, and it was neither true nor needed. Groups 2 and 3
read both, and they are the ones that hold a STACK SHAPE. Groups 1 and 4 read
`armedExit` alone: what they hold is where the guard is, and a depth says
nothing about that. Group 5 reads `history.length` alone: a setting is held by
the entry it did not leave behind. Group 6 reads both over the sheet and
NEITHER over the search, where the hold is what the Back gave back — the screen
still standing, the query still typed.

What none of them reads is the address ALONE, and that is the part that
mattered: a rule exercising only the cold load let two defects through under
green holds, because the destination's address is right whichever stack was
built under it.
"""
import asyncio
import json

from common import (
    ARRIVALS,
    HOME,
    HOME_PAGE,
    LIBRARY,
    PAGE_PATHS,
    PHONE,
    PROTOTYPE,
)
from playwright.async_api import async_playwright

# The medium the sheet walk opens, by the title the library really carries: a
# sheet asked for under a name nothing holds opens nothing at all, and the walk
# would then measure that refusal instead of the return it exists for.
SHEET_TITLE = "Silo (2023)"

# The settings held by (e), one per page that carries one: what to tap is READ
# off the running interface, because a lens, a tab or a topic is the engine's
# vocabulary and a value written down here measures nothing the day it moves.
# Each reader answers the selector to tap and the query that setting should
# write, or null when the page offers none — which is a fixture this rule has
# to report rather than a walk it silently skips.
SETTING_WALKS = (
    ("the library lens", "media", "lib",
     """()=>{const found = [...document.querySelectorAll('[data-lens]')]
          .map((node) => node.dataset.lens).find((value) => value && value !== 'cat');
        return found ? ['[data-lens="' + found + '"]', 'lens=' + found] : null;}"""),
    ("the acquisition tab", "acquisition", "acq",
     """()=>{const found = [...document.querySelectorAll('[data-acqtab]')]
          .map((node) => node.dataset.acqtab).find((value) => value && value !== 'now');
        return found ? ['[data-acqtab="' + found + '"]', 'tab=' + found] : null;}"""),
    ("the maintenance topic", "maintenance", "maint",
     """()=>{const found = [...document.querySelectorAll('[data-maintopic]')]
          .map((node) => node.dataset.maintopic).filter(Boolean)[0];
        return found ? ['[data-maintopic="' + found + '"]', 'topic=' + found] : null;}"""),
)

# What the add screen is left showing after a Back off a panel it opened.
SEARCH_BACK = """() => ({
  open: !!document.querySelector('[data-part="screen"][data-open]'),
  field: (document.querySelector('#addq') || {}).value || '',
})"""

WHERE = """() => ({
  page: state.page,
  tab: state.acqTab,
  lens: state.libLens,
  mode: state.libMode,
  empty: (document.querySelector('#view [data-part="empty-state"] b') || {}).textContent || '',
  notFound: state.notFound || '',
})"""


async def switch_to(pg, page, through_drawer):
    """Switches the top-level page, by the tab bar or through the drawer.

    The two are the same rule and different writes — the tab bar settles the
    page's own entry, the drawer settles the layer's — so a hold about the
    stack has to be able to ask for either.

    Args:
        pg: The page being driven.
        page: The page id to switch to.
        through_drawer: Whether to go through the drawer rather than the tab
            bar, opening it first as a finger has to.
    """
    if through_drawer:
        await pg.tap("[data-drawer]")
        await pg.wait_for_timeout(420)
        await pg.tap(f'#drawer [data-navgo="{page}"]')
        await pg.wait_for_timeout(620)
        return
    await pg.tap(f'#nav button[data-page="{page}"]')
    await pg.wait_for_timeout(400)


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

    journal = Journal("R82 — Back retraces the path taken")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── 1. the floor under a page opened cold ──────────────────────────
        # The entry beneath a top-level page is the home page's own, so one
        # Back lands there, rendered, with the exit guard still one entry
        # further down. Without that entry the same Back spends the guard, and
        # the operator who opened a link to the library is one gesture from
        # leaving the application.
        ctx, pg, errors = await open_page(b, PROTOTYPE + "media")
        await pg.go_back()
        await pg.wait_for_timeout(500)
        floor = await pg.evaluate(WHERE)
        armed = await pg.evaluate("()=>window.armedExit")
        journal.check(
            "a Back from a page opened cold lands on the home page, rendered, "
            "and does not reach the exit guard",
            path(pg.url) == HOME and floor["page"] == HOME_PAGE and not armed,
            f"{path(pg.url)} · page={floor['page']} · armedExit={armed}")
        journal.check("no JS error backing off a page opened cold", not errors, str(errors))
        await ctx.close()

        # ── 2. the not-found page's way out does not spend the guard ───────
        # A not-found arrival has no floor under it — the address rule holds
        # that, and it stands — so the page switch its own control offers
        # cannot step BACK onto one: the entry one down is the exit guard, and
        # arming it on an arrival nobody made as a back leaves the document on
        # the very next gesture, from the one surface whose whole purpose is to
        # offer a way out. The switch records instead, and the three
        # measurements below are what says so: the depth GREW, the guard is
        # untouched, and the address as typed is still one back away.
        wrong = PROTOTYPE + "nimportequoi"
        ctx, pg, errors = await open_page(b, wrong)
        depth = await pg.evaluate("()=>history.length")
        await pg.tap(f'[data-go="{HOME_PAGE}"]')
        await pg.wait_for_timeout(420)
        armed = await pg.evaluate("()=>window.armedExit")
        after = await pg.evaluate("()=>history.length")
        journal.check(
            "the not-found page's own way out RECORDS, and leaves the exit guard alone",
            path(pg.url) == HOME and not armed and after - depth == 1,
            f"{pg.url} · armedExit={armed} · history.length {depth} -> {after}")
        await pg.go_back()
        await pg.wait_for_timeout(500)
        # Read through the DEPARTURE, never past it. The defect this walk
        # exists for ends with the document gone, and an interface read on a
        # page that has left raises where it should name what happened — a
        # crash is a failure nobody can read.
        returned = await pg.evaluate(WHERE) if pg.url.startswith(PROTOTYPE) else None
        journal.check(
            "one Back off it returns to the address as typed, on the surface made for it",
            returned is not None
            and path(pg.url) == "/nimportequoi" and query(pg.url) == ""
            and returned["page"] == "404" and returned["notFound"] == "/nimportequoi",
            f"{pg.url} · {returned if returned else 'the document was left'}")
        if returned is not None:
            await pg.go_back()
            await pg.wait_for_timeout(500)
        armed = (await pg.evaluate("()=>window.armedExit")
                 if pg.url.startswith(PROTOTYPE) else None)
        journal.check("and only the NEXT Back arms the exit guard",
                      bool(armed), f"armedExit={armed} at {pg.url}")
        journal.check("no JS error leaving the not-found page by its own control",
                      not errors, str(errors))
        await ctx.close()

        # AND THE FLOOR THAT ESCAPE LAID IS KEPT. The entry it writes IS a home
        # entry — the reader is standing on it — so the switches that follow
        # step back onto it instead of laying another one down every time. What
        # says so is the DEPTH ACROSS TWO ROUND TRIPS and the way back, never
        # the address: the destination answers the same whether the stack under
        # it grew or not, which is how a floor laid by a gesture the interface
        # did not record cost fourteen entries and twelve Backs to the exit.
        # Both doors are walked, because they settle different entries: the tab
        # bar the page's own, the drawer the layer's.
        for wanted, through_drawer in (("the tab bar", False), ("the drawer", True)):
            ctx, pg, errors = await open_page(b, wrong)
            if through_drawer:
                await switch_to(pg, HOME_PAGE, True)
            else:
                await pg.tap(f'[data-go="{HOME_PAGE}"]')
                await pg.wait_for_timeout(420)
            await switch_to(pg, "lib", through_drawer)
            await switch_to(pg, HOME_PAGE, through_drawer)
            first = await pg.evaluate("()=>history.length")
            await switch_to(pg, "lib", through_drawer)
            await switch_to(pg, HOME_PAGE, through_drawer)
            second = await pg.evaluate("()=>history.length")
            journal.check(
                f"a second round trip through {wanted} after the escape lays nothing"
                " the first did not",
                second == first and path(pg.url) == HOME,
                f"history.length {first} -> {second} · {pg.url}")
            await pg.go_back()
            await pg.wait_for_timeout(520)
            typed = (await pg.evaluate(WHERE) if pg.url.startswith(PROTOTYPE) else None)
            journal.check(
                f"and one Back off {wanted}'s round trips is still the address as typed",
                typed is not None and path(pg.url) == "/nimportequoi"
                and typed["page"] == "404",
                f"{pg.url} · {typed if typed else 'the document was left'}")
            if typed is not None:
                await pg.go_back()
                await pg.wait_for_timeout(520)
            armed = (await pg.evaluate("()=>window.armedExit")
                     if pg.url.startswith(PROTOTYPE) else None)
            journal.check(
                f"and the exit guard is still the entry below it, two Backs from {wanted}",
                bool(armed), f"armedExit={armed} at {pg.url}")
            journal.check(f"no JS error round-tripping through {wanted} after the escape",
                          not errors, str(errors))
            await ctx.close()

        # AND A FORWARD OVER THAT FLOOR IS NOT A DESCENT. Back+Forward is the
        # pair every platform offers, and it RETRACES: the page a Forward lands
        # on was already reached with the floor beneath it, so the floor is
        # still there. Read on a flag lowered by any pop, that Forward looks
        # exactly like the Back under the floor above it — and the next switch
        # then lays a SECOND floor, two entries per cycle, one extra Back per
        # cycle walked to leave. Only the DEPTH ACROSS CYCLES says so: every
        # address along the walk is right whichever stack was built under it.
        ctx, pg, errors = await open_page(b, wrong)
        await pg.tap(f'[data-go="{HOME_PAGE}"]')
        await pg.wait_for_timeout(460)
        first = None
        for turn in range(4):
            await switch_to(pg, "lib", False)
            await pg.go_back()
            await pg.wait_for_timeout(520)
            await pg.go_forward()
            await pg.wait_for_timeout(520)
            await switch_to(pg, HOME_PAGE, False)
            if not turn:
                first = await pg.evaluate("()=>history.length")
        cycled = await pg.evaluate("()=>history.length")
        journal.check(
            "three more Back+Forward cycles after the escape lay nothing the first did not",
            cycled == first and path(pg.url) == HOME,
            f"history.length {first} -> {cycled} · {pg.url}")
        await pg.go_back()
        await pg.wait_for_timeout(520)
        retraced = await pg.evaluate(WHERE) if pg.url.startswith(PROTOTYPE) else None
        journal.check(
            "and one Back off the cycles is still the address as typed",
            retraced is not None and path(pg.url) == "/nimportequoi"
            and retraced["page"] == "404",
            f"{pg.url} · {retraced if retraced else 'the document was left'}")
        if retraced is not None:
            await pg.go_back()
            await pg.wait_for_timeout(520)
        armed = (await pg.evaluate("()=>window.armedExit")
                 if pg.url.startswith(PROTOTYPE) else None)
        journal.check(
            "and the exit guard is still the entry below it, two Backs from the cycles",
            bool(armed), f"armedExit={armed} at {pg.url}")
        journal.check("no JS error stepping forward over the floor the escape laid",
                      not errors, str(errors))
        await ctx.close()

        # AND A BACK GOES UNDER THAT FLOOR, which the round trips above cannot
        # see: they never step below the entry the escape wrote. The floor of a
        # not-found arrival is not the boot's — it is wherever a switch laid
        # one — so backing past it puts the reader under a not-found arrival
        # again, and the way out has to record there a second time. Left
        # standing, it steps onto the exit guard and arms it on a tap, which is
        # this surface's own defect reached by a Back instead of by a boot.
        ctx, pg, errors = await open_page(b, wrong)
        await pg.tap(f'[data-go="{HOME_PAGE}"]')
        await pg.wait_for_timeout(420)
        await switch_to(pg, "lib", False)
        for _ in range(2):
            await pg.go_back()
            await pg.wait_for_timeout(520)
        under = await pg.evaluate(WHERE) if pg.url.startswith(PROTOTYPE) else None
        journal.check(
            "two Backs off the escape return UNDER the floor it laid",
            under is not None and path(pg.url) == "/nimportequoi"
            and under["page"] == "404",
            f"{pg.url} · {under if under else 'the document was left'}")
        await pg.tap(f'[data-go="{HOME_PAGE}"]')
        await pg.wait_for_timeout(520)
        armed = (await pg.evaluate("()=>window.armedExit")
                 if pg.url.startswith(PROTOTYPE) else None)
        journal.check(
            "and the way out RECORDS there a second time, guard untouched",
            path(pg.url) == HOME and not armed, f"{pg.url} · armedExit={armed}")
        journal.check("no JS error taking the not-found page's way out twice",
                      not errors, str(errors))
        await ctx.close()

        # And the same Back onto a page that was reached BEFORE any floor
        # existed — the drawer's own switch off the not-found surface, which
        # lays no home entry at all. It looks exactly like a page standing on a
        # floor, and the tab bar must still reach the entry page from it rather
        # than step back onto the address as typed.
        ctx, pg, errors = await open_page(b, wrong)
        await switch_to(pg, "lib", True)
        await switch_to(pg, HOME_PAGE, False)
        await switch_to(pg, "lib", False)
        for _ in range(2):
            await pg.go_back()
            await pg.wait_for_timeout(520)
        early = await pg.evaluate(WHERE) if pg.url.startswith(PROTOTYPE) else None
        journal.check(
            "two Backs reach the page the drawer opened before any floor was laid",
            early is not None and path(pg.url) == LIBRARY and early["page"] == "lib",
            f"{pg.url} · {early if early else 'the document was left'}")
        await switch_to(pg, HOME_PAGE, False)
        armed = (await pg.evaluate("()=>window.armedExit")
                 if pg.url.startswith(PROTOTYPE) else None)
        journal.check(
            "and the tab bar reaches the entry page from it, not the address as typed",
            path(pg.url) == HOME and not armed, f"{pg.url} · armedExit={armed}")
        journal.check("no JS error switching page off a floorless one",
                      not errors, str(errors))
        await ctx.close()

        # ── 3. (c) a page switch writes the address and stacks nothing ─────
        # The three pages are walked in one go, and what is measured is the
        # DEPTH: under the model the stack is the entry page plus at most one,
        # so three pages leave exactly one entry behind. Backing over the
        # pages one visited is the gesture no platform offers and the one a
        # web application betrays itself with.
        ctx, pg, errors = await open_page(b)
        depth = await pg.evaluate("()=>history.length")
        for page in ("lib", "sys", "arr"):
            await pg.tap(f'#nav button[data-page="{page}"]')
            await pg.wait_for_timeout(340)
        walked = await pg.evaluate("()=>history.length")
        journal.check("after three steps, the address is the third one's",
                      path(pg.url) == ARRIVALS, pg.url)
        journal.check(
            "and walking three top-level pages left exactly ONE entry behind",
            walked - depth == 1, f"history.length {depth} -> {walked}")
        await pg.go_back()
        await pg.wait_for_timeout(420)
        landed = await pg.evaluate(WHERE)
        armed = await pg.evaluate("()=>window.armedExit")
        journal.check(
            "one Back lands on the entry page, rendered, with the guard still beneath it",
            path(pg.url) == HOME and query(pg.url) == ""
            and landed["page"] == HOME_PAGE and not armed,
            f"{pg.url} · page={landed['page']} · armedExit={armed}")
        journal.check("no JS error during the backs", not errors, str(errors))
        # The flag's general meaning, read once over an ordinary walk rather
        # than over an injected failure: pages, a dial and two backs have all
        # written the address, and none of those writes was refused. Nothing
        # ever clears the flag back to false, so this reads the whole walk.
        journal.check("no navigation write failed during the walk",
                      await pg.evaluate("()=>window.__navEchec") is False,
                      f"__navEchec={await pg.evaluate('()=>window.__navEchec')}")
        await ctx.close()

        # And the same Back from each of the other pages, one at a time: a
        # walk that only ever measures the LAST page tells nothing about the
        # ones before it, and « lands on the entry page » is a promise every
        # page makes.
        for page in ("lib", "sys"):
            ctx, pg, errors = await open_page(b)
            await pg.tap(f'#nav button[data-page="{page}"]')
            await pg.wait_for_timeout(340)
            await pg.go_back()
            await pg.wait_for_timeout(500)
            landed = await pg.evaluate(WHERE)
            armed = await pg.evaluate("()=>window.armedExit")
            journal.check(
                f"a Back from « {page} » lands on the entry page too, guard untouched",
                path(pg.url) == HOME and landed["page"] == HOME_PAGE and not armed,
                f"{pg.url} · page={landed['page']} · armedExit={armed}")
            journal.check(f"no JS error backing off « {page} »", not errors, str(errors))
            await ctx.close()

        # And the entry page's own tab, which is the one direction that must
        # not write at all: the floor is already one entry down, so it is
        # stepped BACK onto. Pushing or replacing there would leave two
        # acquisition entries and a Back that changes nothing on screen.
        ctx, pg, errors = await open_page(b)
        await pg.tap('#nav button[data-page="lib"]')
        await pg.wait_for_timeout(340)
        await pg.tap('#nav button[data-page="acq"]')
        await pg.wait_for_timeout(500)
        home_again = await pg.evaluate(WHERE)
        journal.check(
            "tapping the entry page's own tab steps back onto the floor",
            path(pg.url) == HOME and query(pg.url) == "" and home_again["page"] == HOME_PAGE,
            f"{pg.url} · page={home_again['page']}")
        await pg.go_back()
        await pg.wait_for_timeout(500)
        armed = await pg.evaluate("()=>window.armedExit")
        journal.check(
            "and the very next Back arms the exit guard — nothing was laid down twice",
            bool(armed), f"armedExit={armed} at {path(pg.url)}")
        journal.check("no JS error stepping back onto the entry page", not errors, str(errors))
        await ctx.close()

        # AND THE SAME RULE FOR A SWITCH MADE FROM A LAYER, which is where it
        # was being broken: the drawer and the account menu are the two page
        # switches a finger reaches while something is open over the page, and
        # both used to give the destination the LAYER's entry — leaving the
        # abandoned page's entry sandwiched underneath. Rule 2 verbatim forbids
        # the shape that produces: a Back from the destination landing on the
        # page one had just left, two entries for the same page, three Backs to
        # leave. The address alone shows none of it — the destination's own
        # address is right either way — so what is measured is the WALK BACK:
        # every stop the rule allows, in order, and then the guard.
        #
        # `history.length` is reported and not asserted on, because a traversal
        # cannot shrink it: rewinding to the floor leaves the abandoned entries
        # AHEAD, exactly as the entry page's own tab already does. What the rule
        # is about is the way back, and the stops below are it.
        for wanted, opening, tap, arriving, address, stops in (
            # Arriving home, the destination IS the floor, so there is no stop
            # between it and the guard.
            ("the drawer", "[data-drawer]", f'#drawer [data-navgo="{HOME_PAGE}"]',
             HOME_PAGE, HOME, ()),
            # Anywhere else, exactly one: the entry page, and never the
            # médiathèque the layer was opened from.
            ("the account menu", 'JS:window.__panel.produce("account")', '[data-go="profile"]',
             "profile", PAGE_PATHS["profile"], ((HOME, HOME_PAGE),)),
        ):
            ctx, pg, errors = await open_page(b, PROTOTYPE + LIBRARY.lstrip("/"))
            depth = await pg.evaluate("()=>history.length")
            if opening.startswith("JS:"):
                await pg.evaluate("()=>{" + opening[3:] + ";}")
            else:
                await pg.tap(opening)
            await pg.wait_for_timeout(420)
            await pg.tap(tap)
            await pg.wait_for_timeout(620)
            landed = await pg.evaluate(WHERE)
            armed = await pg.evaluate("()=>window.armedExit")
            after = await pg.evaluate("()=>history.length")
            journal.check(
                f"a page switch from {wanted} lands on its destination with the guard untouched",
                path(pg.url) == address and landed["page"] == arriving and not armed,
                f"{pg.url} · page={landed['page']} · armedExit={armed}"
                f" · history.length {depth} -> {after}")
            for stop_address, stop_page in stops:
                await pg.go_back()
                await pg.wait_for_timeout(520)
                stopped = (await pg.evaluate(WHERE)
                           if pg.url.startswith(PROTOTYPE) else None)
                armed = (await pg.evaluate("()=>window.armedExit")
                         if stopped else None)
                journal.check(
                    f"and one Back off {wanted}'s destination reaches the entry page,"
                    " never the page it was opened from",
                    stopped is not None and path(pg.url) == stop_address
                    and stopped["page"] == stop_page and not armed,
                    f"{pg.url} · {stopped if stopped else 'the document was left'}"
                    f" · armedExit={armed}")
            await pg.go_back()
            await pg.wait_for_timeout(520)
            armed = (await pg.evaluate("()=>window.armedExit")
                     if pg.url.startswith(PROTOTYPE) else None)
            journal.check(
                f"and the guard is the next entry down, so {len(stops) + 1} Back(s) leave from {wanted}",
                bool(armed), f"armedExit={armed} at {pg.url}")
            journal.check(
                f"no navigation write failed switching page from {wanted}",
                pg.url.startswith(PROTOTYPE)
                and await pg.evaluate("()=>window.__navEchec") is False,
                f"at {pg.url}")
            journal.check(f"no JS error switching page from {wanted}",
                          not errors, str(errors))
            await ctx.close()

        # ── 4. (d) the exit guard arms at the TOP, and nowhere else ────────
        # The address says nothing here: a guard armed one page too early
        # answers exactly the same address as one that is not armed at all, so
        # the engine's own record is what is read, twice, in one walk.
        ctx, pg, errors = await open_page(b, PROTOTYPE + "media")
        await pg.go_back()
        await pg.wait_for_timeout(500)
        armed_off_page = await pg.evaluate("()=>window.armedExit")
        journal.check(
            "a Back from a page other than the entry page does NOT arm the exit guard",
            not armed_off_page, f"armedExit={armed_off_page} at {path(pg.url)}")
        await pg.go_back()
        await pg.wait_for_timeout(500)
        armed_at_home = await pg.evaluate("()=>window.armedExit")
        journal.check("and a Back from the entry page does",
                      bool(armed_at_home), f"armedExit={armed_at_home} at {path(pg.url)}")
        journal.check("no JS error walking down to the guard", not errors, str(errors))
        await ctx.close()

        # ── 5. (e) a setting leaves NO entry ───────────────────────────────
        # Three of them, on three pages, each read off the interface rather
        # than written down: what a lens or a topic is called is the engine's
        # business, and a value invented here would measure nothing when it
        # stops existing. Two holds each — the depth is unchanged, and the
        # Back afterwards never UNDOES the setting, which is the whole of what
        # a stack of settings costs. Named for what all three share: the
        # acquisition tab is a setting made on the ENTRY page, so its Back
        # reaches the guard rather than another surface.
        for wanted, address, page, reader in SETTING_WALKS:
            ctx, pg, errors = await open_page(b, PROTOTYPE + address)
            found = await pg.evaluate(reader)
            if not journal.check(f"the interface offers {wanted} to set", bool(found), f"{found}"):
                await ctx.close()
                continue
            selector, expected = found
            depth = await pg.evaluate("()=>history.length")
            await pg.tap(selector)
            await pg.wait_for_timeout(420)
            after = await pg.evaluate("()=>history.length")
            journal.check(
                f"setting {wanted} writes the address and leaves NO entry behind",
                after == depth and query(pg.url) == expected,
                f"history.length {depth} -> {after} · {pg.url}")
            await pg.go_back()
            await pg.wait_for_timeout(500)
            landed = await pg.evaluate(WHERE)
            undone = landed["page"] == page and query(pg.url) == ""
            journal.check(
                f"and one Back off {wanted} never undoes it",
                not undone, f"page={landed['page']} at {pg.url}")
            journal.check(f"no JS error setting {wanted}", not errors, str(errors))
            await ctx.close()

        # ── 6. (a) a Back returns to the REAL ORIGIN, setting and all ──────
        # § 16 rule 1 read the way the reader feels it: whoever opened a sheet
        # from a filtered library comes back to that filtered library. It is
        # also the hold rule 3 would break if the parent were treated as a
        # destination rather than as a floor — the Back would go to the
        # library's root and the filter would be gone.
        ctx, pg, errors = await open_page(b, PROTOTYPE + "media?lens=inc")
        depth = await pg.evaluate("()=>history.length")
        await pg.evaluate(f"()=>window.__screens.mediaSheet({json.dumps(SHEET_TITLE)})")
        await pg.wait_for_timeout(500)
        opened = await pg.evaluate("()=>history.length")
        journal.check(
            "opening a sheet from a filtered library stacks exactly one arrival",
            opened - depth == 1 and path(pg.url).startswith("/media/"),
            f"history.length {depth} -> {opened} · {pg.url}")
        await pg.go_back()
        await pg.wait_for_timeout(500)
        origin = await pg.evaluate(WHERE)
        armed = await pg.evaluate("()=>window.armedExit")
        journal.check(
            "and one Back returns to the library AS IT WAS FILTERED, not to its root",
            path(pg.url) == LIBRARY and query(pg.url) == "lens=inc"
            and origin["page"] == "lib" and origin["lens"] == "inc" and not armed,
            f"{pg.url} · page={origin['page']} lens={origin['lens']} armedExit={armed}")
        journal.check("no JS error backing off the sheet", not errors, str(errors))
        await ctx.close()

        # The same promise from the OTHER surface the constitution names: a
        # search. The add screen's own search REPLACES, so the entry the panel
        # is opened from is the search itself — and that is what a Back has to
        # give back, the screen still standing and the query still typed.
        ctx, pg, errors = await open_page(b, PROTOTYPE + "add?q=lucky")
        opened_panel = await pg.evaluate(
            """()=>{const card = document.querySelector(
                 '[data-part="card/body"][data-panel]');
               if (!card) return null; card.click(); return card.dataset.panel;}""")
        await pg.wait_for_timeout(450)
        panel_open = await pg.evaluate("()=>window.__panel.isOpen()")
        journal.check("a result of the add screen's search opens its panel",
                      bool(opened_panel) and panel_open,
                      f"panel={opened_panel!r} open={panel_open}")
        await pg.go_back()
        await pg.wait_for_timeout(500)
        search_back = await pg.evaluate(SEARCH_BACK)
        journal.check(
            "and one Back returns to the SEARCH it was opened from, screen still standing",
            path(pg.url) == "/add" and query(pg.url) == "q=lucky"
            and search_back["open"] and search_back["field"] == "lucky",
            f"{pg.url} · open={search_back['open']} field={search_back['field']!r}")
        journal.check("no JS error backing off the search's panel", not errors, str(errors))
        await ctx.close()

        # ── A COLD ADDRESSED REOPEN PUTS THE PANEL BACK, AND PUSHES NOTHING ──
        #
        # A Forward onto a layer entry finds the entry ALREADY recording the
        # panel — already `{layer: "sheet"}`, already carrying the panel's own
        # address — so the reopen must not push a second one. A duplicate is
        # spent by the next Back without taking the panel's address off, which
        # is a ladder with an invisible rung.
        #
        # THE PRODUCER'S OWN READ IS DROPPED BETWEEN THE BACK AND THE FORWARD,
        # and that is the whole of this hold. A producer whose subject has
        # landed opens SYNCHRONOUSLY, inside the window where the push is
        # suppressed, and every reading is then identical whether the
        # suppression travels or not. Cold, the producer asks first and opens a
        # beat later — after that window has shut — and the panel that came
        # back correctly leaves an entry behind it.
        #
        # ONE KEY, NEVER THE WHOLE CACHE, and the first version of this hold
        # cleared the whole cache and was a GREEN READING OF NOTHING on both
        # builds. The engine's addressed table asks `resolves` before it opens
        # anything, and the journey's `resolves` reads the LIBRARY and the
        # QUEUE — so an empty cache makes it answer no, the address is refused
        # with « the addressed panel names nothing this interface holds », and
        # the walk never reaches the suppression at all. What has to be cold is
        # the producer's own read and nothing else.
        #
        # The journey is the surface that guarantees the cold path: what it
        # needs is a function of its SUBJECT, so it is excluded from the boot's
        # prefill by construction and the first ask for any title is cold.
        reopen_context, reopen_page, errors = await open_page(b)
        await reopen_page.evaluate("()=>window.__go('followsheet-complete')")
        await reopen_page.wait_for_timeout(500)
        reached = await reopen_page.evaluate(
            """()=>{const act = document.querySelector('#sheet [data-journey]');
               if (!act) return false; act.click(); return true;}""")
        await reopen_page.wait_for_timeout(600)
        opened = await reopen_page.evaluate(
            """()=>({open: window.__panel.isOpen(),
                    depth: history.length,
                    address: location.search})""")
        journal.check(
            "the journey opens from the follow sheet, at an address of its own",
            reached and opened["open"] and "panel=journey" in opened["address"],
            f"reached={reached} open={opened['open']} {opened['address']!r}")

        await reopen_page.go_back()
        await reopen_page.wait_for_timeout(500)
        closed = await reopen_page.evaluate("()=>window.__panel.isOpen()")
        journal.check("one Back closes it", not closed, f"open={closed}")

        await reopen_page.evaluate(
            """()=>window.__queries.removeQueries(
                 {queryKey: ["/api/acquisition/journeys"]})""")
        await reopen_page.go_forward()
        await reopen_page.wait_for_timeout(900)
        returned = await reopen_page.evaluate(
            """()=>({open: window.__panel.isOpen(), depth: history.length})""")
        journal.check(
            "and a Forward on a COLD cache puts it back on the entry that already "
            "records it, pushing nothing",
            returned["open"] and returned["depth"] == opened["depth"],
            f"open={returned['open']} · history.length {opened['depth']} -> "
            f"{returned['depth']}")
        journal.check("no JS error on the cold addressed reopen", not errors,
                      str(errors))
        await reopen_context.close()

        # ── AND A COLD ADDRESSED REOPEN IS NOT REFUSED FOR BEING COLD ───────
        #
        # The engine's addressed table asks whether the interface HOLDS the
        # subject before it opens anything, and a feature answers that from the
        # query cache. Before the producers moved, the same question was
        # answered from a fixture the engine had in hand, so cold and warm could
        # not differ — measured on a build of the base: a Forward onto an
        # evicted `setting:` entry reopens the panel there. A « no » the cache
        # cannot yet mean must therefore not be spent as a refusal: the address
        # would stay in the bar naming a panel that never comes back, which is
        # the URL and the interface disagreeing.
        #
        # THE SETTING IS THE SURFACE THAT SHOWS IT, and it is not the journey's
        # case: its need is a LIST, so the boot prefills it and only an eviction
        # makes it cold — which is what a reader meets after a long visit, and
        # what this walk does on purpose.
        reopen_context, reopen_page, errors = await open_page(b)
        await reopen_page.evaluate("(id)=>window.__go(id)", "settings-one")
        await reopen_page.wait_for_timeout(500)
        reached = await reopen_page.evaluate(
            """()=>{const one = document.querySelector('[data-setting]');
               if (!one) return false; one.click(); return true;}""")
        await reopen_page.wait_for_timeout(600)
        settled = await reopen_page.evaluate(
            """()=>({open: window.__panel.isOpen(), depth: history.length,
                    address: location.search})""")
        journal.check(
            "a setting opens at an address of its own",
            reached and settled["open"] and "panel=setting" in settled["address"],
            f"reached={reached} open={settled['open']} {settled['address']!r}")

        await reopen_page.go_back()
        await reopen_page.wait_for_timeout(500)
        await reopen_page.evaluate(
            """()=>window.__queries.removeQueries(
                 {queryKey: ["/api/configuration"]})""")
        await reopen_page.go_forward()
        await reopen_page.wait_for_timeout(1200)
        settings_back = await reopen_page.evaluate(
            """()=>({open: window.__panel.isOpen(), depth: history.length,
                    address: location.search})""")
        journal.check(
            "and a Forward onto its EVICTED entry puts it back rather than "
            "refusing it for being cold",
            settings_back["open"]
            and settings_back["depth"] == settled["depth"]
            and "panel=setting" in settings_back["address"],
            f"open={settings_back['open']} · history.length {settled['depth']} -> "
            f"{settings_back['depth']} · {settings_back['address']!r}")
        journal.check("no JS error on the evicted addressed reopen", not errors,
                      str(errors))
        await reopen_context.close()

        await b.close()

    journal.summary()


asyncio.run(main())
