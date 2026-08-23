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
   write is where the not-found state used to compose the bare root.
   « As typed » is the whole address, QUERY INCLUDED — keeping the path and
   dropping the rest is the same rewrite, only quieter.
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
   end of an ordinary walk, where it must still be false. « Every writer »
   is read literally, and it is the whole of the hold: the gate's release as
   well as its raise, and the BOOT's own three, which no gesture can reach and
   which are therefore broken from OUTSIDE the page, before its first script
   runs. THREE writes need THREE seams, one load each — the settlement of the
   arrival address and the exit guard both travel through `replaceState`, the
   arrival entry through `pushState`, so a seam over one primitive refuses one
   of them and leaves the other two catches held by nothing. Each seam records
   the address and the state it refused, and each hold reads that back: a
   refusal the boot did not issue would otherwise read as a catch that worked.
11. A back puts EVERY dial back. The history entry carries the state one
   arrived in, so a dial the entry does not carry is a dial no back can
   restore — the address drops it while the interface goes on showing it, a
   disagreement no cold load can reveal because a cold load has no interface
   to keep anything from.
12. EVERY page has its address, not most of them. Four of the seven were
   asserted nowhere, because the nav carries four and a rule written from the
   nav measures the nav. The pages come from the model, so a page added
   tomorrow is covered the day it is added rather than the day someone
   remembers, and a page this rule does not know how to reach is a failure
   rather than an entry quietly skipped.
13. EVERY addressed panel kind reopens cold. The table has four and one was
   exercised; a kind nothing opens from an address is a kind whose address is
   decoration, written and never read. And the two panels DROPPED before
   anything can decline them — one carrying no value, one asked for over the
   sign-in screen — say so out loud. The parameter leaves the address either
   way, and a parameter that disappears without a word is one nobody can
   account for from the outside; the words are held against the engine's own
   source as well as heard on a console, so rewording one fells this rule
   rather than quietly leaving it listening for a line nothing prints.
"""
import asyncio
import json
import pathlib
import re
import urllib.parse

from common import PHONE, design_source
from playwright.async_api import async_playwright

PROTOTYPE = "http://127.0.0.1:8899/"

# The page a path names. Kept in step with `design/src/lib/addresses.ts`,
# which is the model this rule measures — a contract has three ends, and this
# is one of them.
HOME = "/acquisition"
HOME_PAGE = "acq"
LIBRARY = "/media"
ARRIVALS = "/arrivals"

# And the model itself, READ rather than transcribed. The dial list and the
# page table were both written out here once, and the dial list had already
# drifted — five names against the model's six — in the very wave that wrote
# the comment forbidding a second list. A copy nothing renders drifts in
# silence, so the names come from the declaration, exactly as
# `scripts/check-frontend-boundaries.py` reads them.
MODEL = pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "lib" / "addresses.ts"
DECLARATION = MODEL.read_text(encoding="utf-8")
DIAL_PARAMETERS = tuple(
    re.findall(r'parameter:\s*"([^"]+)"', DECLARATION)
    + re.findall(r'PANEL_PARAMETER = "([^"]+)"', DECLARATION)
)
PAGE_PATHS = dict(re.findall(r'^\s{2}(\w+):\s*"(/[^"]*)"', DECLARATION, re.M))
# And the SCREEN routes, from the same declaration and with the same regex
# `scripts/check-frontend-boundaries.py` uses. A `$segment` stands for any
# one non-empty segment; what fills it is this rule's, the LIST is the
# model's. Written out here it was a copy, and a copy of a table drifts the
# day a screen is added — silently, because a screen this rule never opens
# is a screen this rule never contradicts.
SCREEN_PATHS = tuple(re.findall(r'^\s{2}"(/[^"]*)"', DECLARATION, re.M))

# How the interface OFFERS each page, so its address can be read off a real
# arrival rather than off a cold load that proves only the other direction.
# The nav carries four of the seven; the system page cross-references two more
# and the account panel the last, which is why a rule written from the nav
# measured three addresses and called that every page. A step beginning `JS:`
# is a verb the engine publishes — the account panel has no control of its own
# until it is open. This table is held against the model below: a page the
# model declares and this does not is a violation, so the seventh page is
# covered the day it is added.
PAGE_WALKS = {
    "acq": ['#nav button[data-page="acq"]'],
    "lib": ['#nav button[data-page="lib"]'],
    "arr": ['#nav button[data-page="arr"]'],
    "sys": ['#nav button[data-page="sys"]'],
    "maint": ['#nav button[data-page="sys"]', '[data-page="maint"]'],
    "cfg": ['#nav button[data-page="sys"]', '[data-page="cfg"]'],
    "profile": ["JS:window.openUserSheet()", '[data-go="profile"]'],
}

# The four kinds the boot's REOPEN table carries, and where the SUBJECT of
# each is read from — the engine's own republished surface, never a value
# typed in here: a subject nobody holds is refused, so an invented one would
# measure the refusal instead of the reopening.
# Each reader answers "" rather than reaching into an empty list: a fixture
# with no follow, no acquisition in flight or no maintenance action is a
# fixture this rule has to REPORT, and an exception inside `page.evaluate`
# ends the run at the line it was thrown from instead.
PANEL_SUBJECTS = {
    "follow": "()=>(window.__store.read().world.follows[0]||{}).t||''",
    "journey": "()=>(window.INFLIGHT[0]||{}).t||''",
    "setting": "()=>{const s=window.allSettings()[0]; return s?window.settingId(s):'';}",
    "action": "()=>(window.MAINT_ACTIONS[0]||{}).id||''",
}

# One concrete value per `$segment` a screen route carries, so the address
# this rule opens is composed FROM the model's route rather than written
# beside it. The media sheet's two are DERIVED from the running application:
# they are provider ids, and a constant nothing verifies against its source
# rots the day the fixture moves.
SHEET_TITLE = "Silo (2023)"
QUALITY_PROFILE = "Test Profile"
RESOLUTION_FOLDER = "Backrooms.2026.MULTi.2160p.WEB-DL"
RELEASES_TITLE = "Silo"

# What the not-found surface says. Asserted, never authored: this is the
# interface's own rendered output, and translating it here would stop the hold
# measuring anything.
NOT_FOUND_TEXT = "Cette adresse ne mène nulle part."  # french-ok: rendered interface text a hold asserts

# The boot's own writers run before anything in the document can reach the
# bridge, so a cold load cannot break them the way the walks below do. What is
# left is the history primitives themselves, wrapped before the first script of
# the page runs. And the boot writes THREE times, not once: the settlement and
# the guard both travel through `replaceState`, the arrival entry through
# `pushState`. A seam over `pushState` alone therefore refuses one write and
# says nothing whatever about the other two — measured: either `replace` catch
# reverted to a bare call left every hold here green.
BOOT_DIAL = "lens=inc"
BOOT_ADDRESS = f"media?{BOOT_DIAL}"
BOOT_PATH = "/" + BOOT_ADDRESS
# The markers the boot's entries carry, read back off the refused write so a
# hold can say the refusal was the boot's own. They are the ENGINE's data,
# matched here and never authored here.
NAV_MARKER = "nav"
GUARD_MARKER = "garde"  # french-ok: the engine's own history marker, matched not authored


def refuse_one_boot_write(primitive, condition):
    """Composes an init script refusing exactly ONE of the boot's history writes.

    Args:
        primitive: The `History.prototype` method to wrap — `pushState` for
            the arrival entry, `replaceState` for the two before it.
        condition: A JavaScript expression over `url` (the address the call
            carries) and `given` (its state argument), true for the one call
            to refuse.

    Returns:
        The script, installed before the page's first script runs. It refuses
        the FIRST call the condition matches, records the address and the state
        it refused on `window.__refused`, and lets every later call through.
    """
    return """
const native = History.prototype.PRIMITIVE;
let refused = false;
History.prototype.PRIMITIVE = function (...args) {
  const url = String(args[2] ?? "");
  const given = args[0] || {};
  if (!refused && (CONDITION)) {
    refused = true;
    window.__refused = { url: url, state: given };
    throw new Error("refused");
  }
  return native.apply(this, args);
};
""".replace("PRIMITIVE", primitive).replace("CONDITION", condition)


# One seam per boot write, in the order the boot issues them, each with the
# marker its entry carries. The settlement is recognised by the ADDRESS it
# writes, the guard by the marker in its state — it writes no address of its
# own — and the arrival entry is the first push of the load, whatever it
# carries. What each seam refused is read back against these: a boot that
# stopped writing through the primitive while some later writer still did would
# otherwise read as a swallowed refusal instead of a rotted seam.
BOOT_WRITES = (
    ("the arrival address", "replaceState", f'url.includes("{BOOT_ADDRESS}")', NAV_MARKER),
    ("the exit guard", "replaceState", f'given.tm === "{GUARD_MARKER}"', GUARD_MARKER),
    ("the arrival entry", "pushState", "true", NAV_MARKER),
)

# The two ways an addressed panel is dropped BEFORE anything can decline it —
# an empty value names no panel at all, and one asked for over the sign-in
# screen is never read, the gate covering everything there is to open over.
# Each is a parameter that leaves the address, and the engine says so on the
# console. The address to ask for it, and the words the engine says.
PANEL_DROPS = (
    ("carrying no value", "acquisition?panel=",
     "the addressed panel carries no value, so nothing is opened:"),
    ("asked for over the sign-in screen", "login?panel=follow:Silo",
     "the sign-in screen covers everything, so the addressed panel is dropped:"),
)

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

    # Read before anything is driven: every hold below is measured against the
    # model, so a model this rule read wrongly would make the rest describe
    # something else. Six is the count the declaration carries — five dials
    # and the panel parameter — and the number is written down so that adding
    # a dial without telling this rule is a failure rather than a silence.
    journal.check("the rule reads the model's dials, and the model declares six",
                  len(DIAL_PARAMETERS) == 6, f"{len(DIAL_PARAMETERS)}: {DIAL_PARAMETERS}")

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

        # And the RELEASE writer, which the walk above cannot reach: it puts
        # the bridge back BEFORE letting the gate through, so that catch is
        # only ever exercised over a write that works. Broken the other way
        # round — the gate raised over an intact bridge, the bridge broken
        # next — the release is the write that is refused, and the screen has
        # to come off all the same.
        ctx, pg, errors = await open_page(b)
        await pg.evaluate("()=>window.showSignIn(false)")
        await pg.wait_for_timeout(300)
        await pg.evaluate(
            """()=>{ window.__savedReplace = window.__bridge.replace;
                     window.__bridge.replace = () => { throw new Error("refused"); }; }""")
        await pg.evaluate("()=>window.hideSignIn()")
        await pg.wait_for_timeout(300)
        released = await pg.evaluate(
            """()=>({down: document.querySelector('#login').hidden,
                     failed: window.__navEchec})""")
        journal.check("the gate comes down even when its release cannot be written",
                      released["down"], f"hidden={released['down']} at {path(pg.url)}")
        journal.check("and the refused release write is on record too",
                      released["failed"] is True, f"__navEchec={released['failed']}")
        await pg.evaluate("()=>{ window.__bridge.replace = window.__savedReplace; }")
        journal.check("no JS error when a release write is refused", not errors, str(errors))
        await ctx.close()

        # And the BOOT's writers, which no gesture can reach: they run before
        # the page can be touched, so the refusal is installed from outside it.
        # « Every writer » has to mean the ones that fire when nobody is
        # looking, and those three are exactly where a swallow costs most —
        # the interface is already drawn by then, so a refusal leaves a real
        # screen standing on an address nothing wrote.
        #
        # THREE writes, THREE seams, a fresh context each. One seam refuses one
        # write: the load that has its settlement refused is not the load that
        # has its guard refused, and a rule holding only the third of them held
        # the other two catches by nothing at all.
        for wanted, primitive, condition, marker in BOOT_WRITES:
            ctx = await b.new_context(**PHONE)
            await ctx.add_init_script(refuse_one_boot_write(primitive, condition))
            pg = await ctx.new_page()
            errors = []
            pg.on("pageerror", lambda e, sink=errors: sink.append(str(e)))
            await pg.goto(PROTOTYPE + BOOT_ADDRESS, wait_until="load")
            await pg.evaluate("()=>window.__loadingDone?.()")
            await pg.wait_for_timeout(400)
            booted = await pg.evaluate(
                """()=>({page: state.page, refused: window.__refused || null,
                         failed: window.__navEchec})""")
            refused = booted["refused"] or {}
            # Read first, and separately: a seam that stopped firing would make
            # the holds below fall for a reason that has nothing to do with the
            # flag, and a hold blaming the wrong thing is worse than none. WHICH
            # write was caught is part of that reading — the refusal has to be
            # the boot's own, by the address it carries and by the marker of the
            # entry it was writing.
            journal.check(
                f"the seam refused the boot's write of {wanted}, and it is the boot's own",
                refused.get("url") == BOOT_PATH
                and (refused.get("state") or {}).get("tm") == marker,
                f"refused={refused.get('url')!r} "
                f"state.tm={(refused.get('state') or {}).get('tm')!r} · wanted {BOOT_PATH!r}/{marker!r}")
            journal.check(
                f"and a refused write of {wanted} is on record like any other",
                booted["failed"] is True,
                f"__navEchec={booted['failed']} · page={booted['page']}")
            journal.check(
                f"the interface is drawn even though {wanted} could not be written",
                bool(booted["page"]), f"page={booted['page']}")
            journal.check(f"no JS error when the boot's write of {wanted} is refused",
                          not errors, str(errors))
            await ctx.close()

        # ── 9. a screen address resolves to the page UNDERNEATH ────────────
        # Same reasoning as `/login` above, applied to every screen route: a
        # screen covers the frame, so while it is open nothing reveals which
        # page it sits on — and a not-found page underneath surfaces only once
        # the screen closes, on the stable link the wave exists to serve.
        ctx, pg, errors = await open_page(b)
        sheet_ids = await pg.evaluate(f"()=>window.addressIdsFor({json.dumps(SHEET_TITLE)})")
        await ctx.close()
        # A fixture that moved leaves this empty, and reading a provider id off
        # it would raise where the rule should FALL: a traceback names the line
        # it died on, a fallen hold names the promise nobody could keep.
        sheet_resolved = journal.check(
            "the media sheet's own address ids are resolvable",
            bool(sheet_ids and sheet_ids.get("provider") and sheet_ids.get("id")),
            f"{SHEET_TITLE} -> {sheet_ids}")
        sheet_address = (
            f"media/{sheet_ids['provider']}/{sheet_ids['id']}" if sheet_resolved else "")
        examples = {
            "/quality/$name": {"$name": QUALITY_PROFILE},
            "/resolution/$folder": {"$folder": RESOLUTION_FOLDER},
            "/releases/$title": {"$title": RELEASES_TITLE},
        }
        if sheet_resolved:
            examples["/media/$provider/$id"] = {
                "$provider": sheet_ids["provider"], "$id": sheet_ids["id"]}
        screens = []
        for route in SCREEN_PATHS:
            filled = examples.get(route, {})
            segments = route.strip("/").split("/")
            if any(part.startswith("$") and part not in filled for part in segments):
                continue
            screens.append((route, "/".join(
                urllib.parse.quote(str(filled[part]), safe="") if part.startswith("$")
                else part for part in segments)))
        # The count is the model's. A screen declared and composed by nothing
        # here is a screen this rule silently stops opening, which is the whole
        # failure the derivation exists to make loud.
        journal.check("every screen the model declares has a concrete address here",
                      len(screens) == len(SCREEN_PATHS),
                      f"{len(screens)} composed of {len(SCREEN_PATHS)} declared: "
                      f"{[route for route, _ in screens]}")
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
        # saying the address leads nowhere. It hangs off the derived address,
        # so it is skipped — never guessed at — when that address is not there.
        if sheet_resolved:
            ctx, pg, errors = await open_page(b, PROTOTYPE + sheet_address)
            await pg.evaluate(
                """()=>document.querySelector('[data-part="screen"][data-open]'
                   + ' [data-part="screen/back"]').click()""")
            await pg.wait_for_timeout(420)
            closed = await pg.evaluate(WHERE)
            journal.check(
                "closing a screen opened cold leaves the home page showing, "
                "not the not-found one",
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

        # AND « AS TYPED » IS THE WHOLE ADDRESS, query included. The walk above
        # uses a path with nothing after the `?`, so it cannot see the half of
        # the rewrite that keeps the path and drops the rest: the arrival looks
        # untouched, and the first write puts a shorter link in the bar than
        # the one that was opened.
        with_query = PROTOTYPE + "nimportequoi?x=1"
        ctx, pg, errors = await open_page(b, with_query)
        lost = await pg.evaluate(WHERE)
        journal.check("an unknown address keeps its query on arrival",
                      path(pg.url) == "/nimportequoi" and query(pg.url) == "x=1", pg.url)
        journal.check("and the interface names the whole of what was asked for",
                      lost["notFound"] == "/nimportequoi?x=1", lost["notFound"])
        await pg.go_back()
        await pg.wait_for_timeout(500)
        journal.check("and a Back re-pushes it whole, query and all",
                      path(pg.url) == "/nimportequoi" and query(pg.url) == "x=1", pg.url)
        journal.check("no JS error on an unknown address carrying a query",
                      not errors, str(errors))
        await ctx.close()

        # The panel parameter is the ONE thing an unknown address does not keep,
        # and for the reason every other address does not keep it either: it
        # names a panel the interface declined, so it is not part of the address
        # one is left on. Kept in this field it would come BACK into the bar on
        # the first write of the state.
        ctx, pg, errors = await open_page(b, PROTOTYPE + "nimportequoi?panel=follow:Silo")
        lost = await pg.evaluate(WHERE)
        journal.check("a declined panel is off the unknown address that named it",
                      path(pg.url) == "/nimportequoi" and query(pg.url) == "", pg.url)
        journal.check("and off what the interface will compose from it",
                      lost["notFound"] == "/nimportequoi", lost["notFound"])
        await ctx.close()

        # AND THE TWO DROPS THAT HAPPEN BEFORE ANYTHING CAN DECLINE ANYTHING.
        # The value above is REFUSED — the interface read it and said no. These
        # two never get that far: an empty value names no panel, and a panel
        # asked for over the sign-in screen is never read at all. Either way the
        # parameter leaves the address, and a parameter that disappears without
        # a word is one nobody can account for from the outside.
        #
        # The words are read TWICE, and the second reading is what keeps the
        # first honest: off the ENGINE'S OWN SOURCE, and off a live console. A
        # hold that only listens goes quiet the day the message is reworded —
        # it waits for a line that can no longer be printed and reports the
        # silence as a defect it cannot name. Held against the source, a reword
        # fells the rule here, where it says what changed.
        source = design_source()
        for wanted, address, message in PANEL_DROPS:
            journal.check(
                f"the engine still says, in those words, why a panel {wanted} is dropped",
                message in source, message)
            ctx = await b.new_context(**PHONE)
            pg = await ctx.new_page()
            logged = []
            errors = []
            pg.on("console", lambda entry, sink=logged: sink.append(entry.text))
            pg.on("pageerror", lambda e, sink=errors: sink.append(str(e)))
            await pg.goto(PROTOTYPE + address, wait_until="load")
            await pg.evaluate("()=>window.__loadingDone?.()")
            await pg.wait_for_timeout(400)
            journal.check(
                f"a panel {wanted} is dropped OUT LOUD",
                any(message in line for line in logged),
                f"/{address} -> {logged}")
            journal.check("and the address it left carries no panel",
                          "panel=" not in query(pg.url), pg.url)
            journal.check(f"no JS error dropping a panel {wanted}", not errors, str(errors))
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

        # ── 12. every page the model declares has its address ──────────────
        journal.check("every page the model declares is one this rule knows how to reach",
                      set(PAGE_WALKS) == set(PAGE_PATHS),
                      f"walked {sorted(PAGE_WALKS)} · declared {sorted(PAGE_PATHS)}")
        for page, steps in PAGE_WALKS.items():
            ctx, pg, errors = await open_page(b)
            for step in steps:
                if step.startswith("JS:"):
                    await pg.evaluate("()=>{" + step[3:] + "}")
                else:
                    await pg.tap(step)
                await pg.wait_for_timeout(420)
            landed = await pg.evaluate("()=>state.page")
            journal.check(
                f"arriving on « {page} » writes the address the model declares for it",
                path(pg.url) == PAGE_PATHS[page] and landed == page and not errors,
                f"{page} -> {pg.url} · landed on page {landed} · {errors}")
            await ctx.close()

        # ── 13. every addressed panel kind reopens cold ────────────────────
        # One of the four was exercised anywhere; the other three were opened
        # by nothing, so their `resolves` could have refused every subject in
        # the world and no rule would have noticed. The subject of each comes
        # from the engine's own surface, because a subject nobody holds is
        # REFUSED — an invented one would measure the refusal and pass for the
        # wrong reason.
        ctx, pg, errors = await open_page(b)
        subjects = {kind: await pg.evaluate(reader) for kind, reader in PANEL_SUBJECTS.items()}
        await ctx.close()
        journal.check("every panel kind has a subject the interface really holds",
                      all(subjects.values()), f"{subjects}")
        for kind, subject in subjects.items():
            if not subject:
                continue
            address = (PROTOTYPE + "acquisition?panel="
                       + urllib.parse.quote(f"{kind}:{subject}", safe=""))
            ctx, pg, errors = await open_page(b, address)
            await pg.wait_for_timeout(400)
            reopened = await pg.evaluate(
                """()=>({open: window.__panel.isOpen(),
                         title: (window.__store.read().state.panelDescriptor||{}).title||''})""")
            journal.check(
                f"a cold ?panel={kind}:… reopens the panel it names",
                reopened["open"] and bool(reopened["title"])
                and "panel=" in query(pg.url) and not errors,
                f"{kind}:{subject} -> open={reopened['open']} "
                f"title={reopened['title']!r} at {pg.url} · {errors}")
            await ctx.close()

        # ── 11. a back puts EVERY dial back, not most of them ──────────────
        # The history entry carries the state one arrived in, and a dial left
        # off it is a dial the back cannot restore: the address drops it and
        # the interface goes on showing it, which is invariant 1 broken in the
        # one direction a cold load can never reveal. The maintenance topic is
        # the dial this holds on, and its value is READ off the page rather
        # than written down here — a topic list is the engine's, not this
        # rule's.
        ctx, pg, errors = await open_page(b, PROTOTYPE + "maintenance")
        topics = await pg.evaluate(
            """()=>[...document.querySelectorAll('[data-maintopic]')]
                 .map((node) => node.dataset.maintopic).filter(Boolean)""")
        # A page offering no topic at all fells the hold below and stops there:
        # the walk that follows is a walk THROUGH a topic, so with none to take
        # it would raise on the empty list and take the rest of the rule with
        # it — a fixture's silence reported as a crash.
        if journal.check("the maintenance page offers a topic to select",
                         bool(topics), f"{topics}"):
            topic = topics[0]
            await pg.tap(f'[data-maintopic="{topic}"]')
            await pg.wait_for_timeout(400)
            journal.check("selecting a maintenance topic writes it into the query",
                          query(pg.url) == f"topic={topic}", pg.url)
            await pg.tap('#nav button[data-page="sys"]')
            await pg.wait_for_timeout(400)
            await pg.go_back()
            await pg.wait_for_timeout(500)
            back_topic = await pg.evaluate("()=>state.maintTopic")
            journal.check("a back onto a topic address restores the topic the address names",
                          path(pg.url) == "/maintenance"
                          and query(pg.url) == f"topic={topic}"
                          and back_topic == topic,
                          f"{pg.url} · maintTopic={back_topic!r}")
            await pg.go_back()
            await pg.wait_for_timeout(500)
            cleared = await pg.evaluate("()=>state.maintTopic")
            journal.check(
                "and a second back drops the topic from the interface as well as the address",
                path(pg.url) == "/maintenance" and query(pg.url) == "" and not cleared,
                f"{pg.url} · maintTopic={cleared!r}")
            journal.check("no JS error walking the topic back", not errors, str(errors))
        await ctx.close()

        await b.close()

    journal.summary()


asyncio.run(main())
