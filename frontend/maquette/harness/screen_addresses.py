"""R75 — a screen route answers a real address, cold, and only while it is open.

`QualityScreen` (Task 9) is the first screen drawn from a real path rather than
from the legacy fragment's own state machine, so it is also the first screen
whose address can be typed, bookmarked or shared — and the first for which a
missing detail (a fallback route on the host, a `<base>` tag in the envelope)
only shows up once something is actually served from BELOW the document
root. `server.py` (Task 8) is what makes that depth reachable at all: the
plain 8899 host 45 other rules already point at answers a 404 for
`/quality/…`, because no such file exists — nothing served through it can
tell a deep reload from a broken link. This rule runs against an ephemeral
scratch port.

What it holds to:

1. A deep address opens the promised screen COLD — no journey, no click,
   just a fresh browser handed the URL.
2. Whatever that screen draws resolves through the document's `<base>`,
   the same way it would from `/` — proven not by the screen's own markup
   (`QualityScreen` draws no `<img>` of its own, only inline SVG) but by every
   image the WHOLE document loads at that depth: the legacy fragment mounts
   underneath it, on its own default page, and draws real posters through
   the same relative `assets/…` paths every other screen uses.
3. One back from a screen reached by walking there lands where the walk
   started, with the screen gone — the screen owns no address once closed.
4. The address is written only while the screen is open: walking onto it
   writes `/profile/…`, and the ONLY way off it is back (`screen/back` calls
   `__bridge.back()`, nothing else) — so closing it is, by construction,
   also the address returning to what it was.
5. A wrong deep address does not raise, blank the frame, or invent a
   not-found surface: `QualityProfile` is a GLOBAL setting, not a per-title
   record, so the screen has nothing to fail a lookup against — it renders
   its ordinary form for whatever string is in the address, and the address
   itself is left exactly as typed (R68's spirit, at depth).

EXTENDED (SP4b) to `MediaScreen` — the media sheet, the one screen every
poster, tile, suggestion and panel act already led to, now also reachable
as `/media/$provider/$id` on its own. Unlike `QualityScreen`, this screen DOES draw
an image of its own (the hero/poster banner), so its own artwork is the
proof at this depth rather than a stand-in read off the legacy fragment
underneath. And unlike a `QualityProfile` name, a title here resolves
against a real per-title record (`sheetFor`) — so the unknown-title hold
is not "the screen has nothing to fail a lookup against" but "the legacy
template it was transplanted from never had a not-found branch either":
`openFiche(title)` (`refonte.html`, deleted when this screen became a real
route — recovered from the commit that deleted it) built the SAME markup
whether `sheetFor(title)` found a record or not, every field simply
printing "inconnu" in its place. What the harness holds for the mediaSheet:
(f) a deep address opens it cold, `h2.ht` carrying the promised title;
(g) the hero/poster the screen draws ITSELF actually loads — proven on the
image the CSS background resolves to, not on a stand-in; (h) one Back
lands exactly where holds 3+4 already prove it does for `ProfileScreen`; (i)
an unknown title renders the SAME honest template, mirroring `openFiche`'s
own null path rather than inventing a not-found surface for it; (j) a
title the provider gave no trailer to renders `p.noinfo` in the
trailer's own place, never a silently missing section.
"""
import asyncio
import json
import pathlib
import sys
import urllib.parse

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal
from server import start_server

SERVED_ROOT = pathlib.Path("/tmp/tm-refonte")

# Where a Retour from a screen opened COLD lands. The screen's own entry is
# left behind and the page underneath writes its address, so what is measured
# is the HOME page's own path — not the bare root, which names no page.
HOME = "/acquisition"

TITLE = "Silo"
# Typed by hand, on purpose: the apostrophe is left unescaped, exactly the
# way an operator would type it — the point of hold 5 is that NOTHING
# corrects this on the way in.
UNKNOWN_ADDRESS = "N'Existe%20Pas"

# The mediaSheet titles below are picked straight from the embedded référentiel
# (`refonte.html`'s `SHEETS_RAW`/`HERO_IMAGES`/`trailerIds`), not invented:
# `Silo (2023)` carries both a hero image and a trailer (`sheetFor` resolves
# it directly, no `baseTitle` fallback needed), which is what makes holds
# (f)-(h) meaningful rather than vacuous. `Broadchurch` is the states
# table's own pick for "no trailer" (`fiche-sans-trailer`, refonte.html) —
# its `trailerIds` entry is absent and its sheet carries `trailer: null`
# explicitly, and its cast/seasons are otherwise fully populated so the
# ONLY `p.noinfo` the screen draws is the trailer's.
SHEET_TITLE = "Silo (2023)"
TITLE_WITHOUT_TRAILER = "Broadchurch"

# `Backrooms.2026.MULTi.2160p.WEB-DL` is the embedded référentiel's own
# folder waiting to be resolved (`refonte.html`'s `arr-charge` state opens
# it as the default « Résoudre → » target — `ident.py` walks that exact
# path) — and the real regression case for `server.py`'s dotted-segment
# fallback fix: its deepest path segment carries dots of its own, which the
# fallback used to mistake for a file extension and 404 on before folding.
# Opening it through THIS deep-entry hold is what proves the fix reaches the
# SPA, not merely the raw HTTP response `server.py`'s own self-test covers.
RESOLUTION_FOLDER = "Backrooms.2026.MULTi.2160p.WEB-DL"
# `Silo` is the states table's own pick for `screen-releases`
# (`window.__screens.releases("Silo")`, refonte.html).
RELEASES_TITLE = "Silo"

SCREEN_STATE = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open]');
  return {
    open: !!screen,
    key: screen?.dataset.key ?? null,
    title: (document.querySelector('[data-part="screen"][data-open] [data-part="screen/bar"] span') || {}).textContent ?? null,
    body: (screen?.querySelector('[data-part="surface/body"]') || {}).textContent ?? '',
    pathname: location.pathname,
  };
}"""

ADD_STATE = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open]');
  return {
    open: !!screen,
    key: screen?.dataset.key ?? null,
    field: document.querySelector('#addq')?.value ?? null,
    cards: document.querySelectorAll('[data-part="result/list"] [data-part="card"]').length,
    pathname: location.pathname,
    search: location.search,
  };
}"""

IMAGES_STATE = """() => {
  const loaded = [...document.querySelectorAll('img')].filter(i => i.complete);
  return {
    loaded: loaded.length,
    broken: loaded.filter(i => i.naturalWidth === 0).length,
  };
}"""

# `MediaScreen` draws its own artwork through a CSS `background-image`, not
# an `<img>` tag (`hero` / `hero/background`) — so `IMAGES_STATE`'s generic
# `<img>` sweep, which is what proves hold 2 for `ProfileScreen` (a screen
# that draws no image of its own), does not see it at all. Proof here
# instead re-fetches the SAME url the computed style resolves through a
# real `Image()`, and reads `complete`/`naturalWidth` off THAT — the exact
# pair hold (g) is phrased against.
HEROBG_STATE = """() => {
  const bg = document.querySelector('[data-part="screen"][data-open] [data-part="hero"] [data-part="hero/background"]');
  const style = bg ? getComputedStyle(bg).backgroundImage : '';
  const found = /url\\(["']?(.*?)["']?\\)/.exec(style || '');
  const url = found ? found[1] : null;
  if (!url) return Promise.resolve({ url: null, drawn: false });
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve({ url, drawn: image.complete && image.naturalWidth > 0 });
    image.onerror = () => resolve({ url, drawn: false });
    image.src = url;
  });
}"""

SHEET_STATE = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open]');
  return {
    open: !!screen,
    key: screen?.dataset.key ?? null,
    title: (screen?.querySelector('h2[data-part="hero/title"]') || {}).textContent ?? null,
    body: (screen?.querySelector('[data-part="surface/body"]') || {}).textContent ?? '',
    bar: (screen?.querySelector('[data-part="screen/bar"]') || {}).textContent ?? '',
    noinfos: [...document.querySelectorAll('[data-part="screen"][data-open] p[data-part="no-info"]')].map(
      (p) => p.textContent),
    pathname: location.pathname,
  };
}"""

RESOLUTION_STATE = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="resolution:"]');
  return {
    open: !!screen,
    key: screen?.dataset.key ?? null,
    folder: (screen?.querySelector('h2[data-part="heading"] code') || {}).textContent ?? null,
    body: (screen?.querySelector('[data-part="surface/body"]') || {}).textContent ?? '',
    pathname: location.pathname,
  };
}"""

# `RELEASES` (the ranked candidates) is a FIXED référentiel, not looked up
# per title — unlike `sheetFor` for a mediaSheet, there is nothing here for an
# unknown `title` to fail against, so `candidates` stays what it is
# regardless of which title the bar shows.
RELEASES_STATE = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="releases:"]');
  return {
    open: !!screen,
    key: screen?.dataset.key ?? null,
    bar: (screen?.querySelector('[data-part="screen/bar"] span') || {}).textContent ?? null,
    candidates: screen ? screen.querySelectorAll('[data-part="release"]').length : 0,
    pathname: location.pathname,
  };
}"""


async def open_at(browser, address):
    """Opens `address` cold, past the startup screen, on a fresh context."""
    ctx = await browser.new_context(**PHONE)
    pg = await ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    await pg.goto(address, wait_until="load")
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(300)
    return ctx, pg, errors


async def main():
    journal = Journal("R75 — the screen addresses")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")

        with start_server(SERVED_ROOT) as port:
            base = f"http://127.0.0.1:{port}"

            # ─── Hold 1: deep entry opens the promised screen, cold ────────
            title_address = f"{base}/quality/{urllib.parse.quote(TITLE)}"
            ctx, pg, errors = await open_at(browser, title_address)
            state_ = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "a deep address opens the right screen, cold",
                state_["open"] and state_["key"] == f"profile:{TITLE}",
                f"key={state_['key']}")
            journal.check(
                "the screen renders its promised content (resolution, tracks, locks)",
                "Résolution minimale" in state_["body"]
                and "Pistes audio exigées" in state_["body"]
                and "Deux verrous" in state_["body"],
                f"{len(state_['body'])} characters of body")
            journal.check("no JS error on deep entry", not errors, str(errors))

            # ─── Hold 2: everything the document draws resolves through <base> ─
            images = await pg.evaluate(IMAGES_STATE)
            journal.check(
                "no broken image at this depth (the <base> proof)",
                images["loaded"] > 0 and images["broken"] == 0,
                f"{images['broken']}/{images['loaded']} broken")
            await ctx.close()

            # ─── Holds 3+4: walking writes the address; back is the only close,
            # so back landing where the walk started IS the address returning ──
            ctx, pg, errors = await open_at(browser, f"{base}/")
            start = await pg.evaluate(SCREEN_STATE)
            journal.check("the starting point has no screen open",
                             not start["open"] and start["pathname"] == "/acquisition",
                             start["pathname"])

            await pg.evaluate(f"()=>window.__screens.profile({json.dumps(TITLE)})")
            await pg.wait_for_timeout(300)
            on_profile = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "walking to the profile WRITES the address",
                on_profile["open"] and on_profile["pathname"] == f"/quality/{TITLE}",
                on_profile["pathname"])

            await pg.evaluate("""()=>document.querySelector('[data-part="screen"][data-open] [data-part="screen/back"]').click()""")
            await pg.wait_for_timeout(300)
            returned = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "closing the screen (its only path: Retour) returns the address to what it was",
                returned["pathname"] == start["pathname"], returned["pathname"])
            journal.check("and the screen is indeed gone", not returned["open"],
                             str(returned["open"]))
            journal.check("no JS error during the walk", not errors, str(errors))
            await ctx.close()

            # ─── Hold 5: a wrong deep address renders the honest empty case ──
            wrong_address = f"{base}/quality/{UNKNOWN_ADDRESS}"
            ctx, pg, errors = await open_at(browser, wrong_address)
            lost = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "an unknown address still renders the screen, honestly",
                lost["open"] and "N'Existe Pas" in (lost["title"] or ""),
                f"key={lost['key']} title={lost['title']!r}")
            journal.check(
                "the address stays exactly as typed",
                pg.url == wrong_address, pg.url)
            journal.check("no JS error on an unknown address", not errors, str(errors))
            await ctx.close()

            # ─── Hold 6: /ajout deep entry, cold — field filled, results shown ──
            add_address = f"{base}/add?q=lucky"
            ctx, pg, errors = await open_at(browser, add_address)
            add_cold = await pg.evaluate(ADD_STATE)
            journal.check(
                "a deep /ajout address opens the screen, cold, with the field filled",
                add_cold["open"] and add_cold["field"] == "lucky"
                and add_cold["key"] == "add:follow",
                f"field={add_cold['field']!r} key={add_cold['key']}")
            journal.check(
                "and the query shows results",
                add_cold["cards"] >= 2, f"{add_cold['cards']} cards")
            journal.check("no JS error on deep /ajout entry", not errors, str(errors))
            await ctx.close()

            # ─── Hold 7: typing rewrites the address IN PLACE — R76 for a
            # CONTROLLED input, not a one-shot navigation. Proven by the
            # STRONGEST observable: one back from a five-keystroke session
            # must land exactly where the walk started, not mid-query — a
            # stacked entry per keystroke would instead surface one letter
            # short of the full word. `history.length` is deliberately not
            # read here: an observed landing state is the harder proof.
            ctx, pg, errors = await open_at(browser, f"{base}/")
            add_start = await pg.evaluate(SCREEN_STATE)
            journal.check("the starting point has no screen open (before /ajout)",
                             not add_start["open"] and add_start["pathname"] == "/acquisition",
                             add_start["pathname"])

            await pg.evaluate("()=>window.__screens.add('')")
            await pg.wait_for_timeout(300)
            on_add = await pg.evaluate(ADD_STATE)
            journal.check(
                "walking to /ajout WRITES the address",
                on_add["open"] and on_add["pathname"] == "/add",
                on_add["pathname"])

            await pg.click("#addq")
            for letter in "lucky":
                await pg.keyboard.type(letter)
                await pg.wait_for_timeout(80)
            await pg.wait_for_timeout(300)
            after_typing = await pg.evaluate(ADD_STATE)
            journal.check(
                "five keystrokes rewrite the field AND the address",
                after_typing["field"] == "lucky" and "q=lucky" in after_typing["search"],
                f"field={after_typing['field']!r} search={after_typing['search']!r}")

            await pg.go_back()
            await pg.wait_for_timeout(400)
            after_back = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "one back from five keystrokes lands where one stood BEFORE the screen"
                " (and not mid-query, which a stacked history would have produced)",
                not after_back["open"] and after_back["pathname"] == add_start["pathname"],
                after_back["pathname"])
            journal.check("no JS error while typing", not errors, str(errors))
            await ctx.close()

            # ─── Hold 8: leaving a screen through the bar ───────────────────
            # A legacy nav control (the bottom bar) can fire while a router
            # route is open — it writes through the SAME shared history the
            # router subscribes to, never through go()/navigate(). The
            # write alone must be enough: no code on this side of the bridge
            # calls the router, yet the screen must still actually leave.
            # Reached the same way an operator does: a REAL tap on the FAB,
            # then a REAL tap on « Médiathèque ».
            ctx, pg, errors = await open_at(browser, f"{base}/")
            await pg.click("#fab")
            await pg.wait_for_timeout(400)
            on_add_via_fab = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "the FAB opens the screen (the journey's start)",
                on_add_via_fab["open"] and on_add_via_fab["pathname"] == "/add",
                on_add_via_fab["pathname"])

            await pg.evaluate("()=>document.querySelector('[data-page=\"lib\"]').click()")
            await pg.wait_for_timeout(400)
            left = await pg.evaluate(
                """() => ({
                    open: !!document.querySelector('[data-part="screen"][data-open]'),
                    pathname: location.pathname,
                    search: location.search,
                    page: state.page,
                })"""
            )
            journal.check(
                "tapping « Médiathèque » from /ajout makes the screen LEAVE",
                not left["open"], f"open={left['open']}")
            journal.check(
                "the address returns to the library's own path (/media)",
                left["pathname"] == "/media" and left["search"] == "",
                f"{left['pathname']}{left['search']}")
            journal.check(
                "and the page rendered really is the library",
                left["page"] == "lib", f"page={left['page']}")
            journal.check("no JS error when leaving through the bar", not errors, str(errors))
            await ctx.close()

            # ─── Holds (f)-(h): the mediaSheet's deep entry, its OWN artwork,
            # one Back — same server, same `open_at`, a second screen. ──
            # The sheet is addressed by PROVIDER ID (DOIT-11), and the id is
            # DERIVED from the running application rather than written down
            # here: a constant nothing verifies against its source is a
            # coupling, and this one would rot the day the fixture moved.
            ctx, pg, errors = await open_at(browser, f"{base}/")
            sheet_ids = await pg.evaluate(
                f"()=>window.addressIdsFor({json.dumps(SHEET_TITLE)})")
            await ctx.close()
            journal.check(
                "(e2) the media sheet's own address ids are resolvable",
                bool(sheet_ids), f"{SHEET_TITLE} -> {sheet_ids}")
            sheet_address = f"{base}/media/{sheet_ids['provider']}/{sheet_ids['id']}"
            ctx, pg, errors = await open_at(browser, sheet_address)
            sheet_cold = await pg.evaluate(SHEET_STATE)
            journal.check(
                "(f) a deep /media/:provider/:id address opens the promised sheet, cold",
                sheet_cold["open"]
                and sheet_cold["key"] == f"mediaSheet:{SHEET_TITLE}"
                and sheet_cold["title"] == SHEET_TITLE.split(" (")[0],
                f"key={sheet_cold['key']} title={sheet_cold['title']!r}")
            artwork = await pg.evaluate(HEROBG_STATE)
            journal.check(
                "(g) the hero/poster the sheet draws ITSELF really loads",
                artwork["url"] is not None and artwork["drawn"],
                f"url={artwork['url']!r} drawn={artwork['drawn']}")
            journal.check("no JS error on deep /media/:provider/:id entry", not errors, str(errors))

            await pg.evaluate("""()=>document.querySelector('[data-part="screen"][data-open] [data-part="screen/back"]').click()""")
            await pg.wait_for_timeout(300)
            sheet_returned = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "(h) a Retour from the sheet lands on the default page, screen gone, "
                "at the home page's own address",
                not sheet_returned["open"] and sheet_returned["pathname"] == HOME,
                sheet_returned["pathname"])
            journal.check("no JS error during the back from the sheet", not errors, str(errors))
            await ctx.close()

            # ─── Hold (i): an id nobody carries renders the SAME honest
            # template `openFiche` always did — no not-found branch to
            # mirror, only a gabarit whose fields say "inconnu".
            #
            # It used to assert the screen ECHOED the unknown title back. An
            # address keyed on a provider id cannot: it names an id, not a
            # title, and inventing one to echo would be the interface making
            # something up. What is measured instead is what the screen
            # actually owes a stale bookmark — it renders, it does not raise,
            # and it says in its own bar that the medium is unidentified.
            # An id nobody carries — a stale bookmark's exact shape.
            wrong_sheet_address = f"{base}/media/tvdb/000000"
            ctx, pg, errors = await open_at(browser, wrong_sheet_address)
            sheet_lost = await pg.evaluate(SHEET_STATE)
            journal.check(
                "(i) an id nobody carries still renders the sheet, honestly — "
                "openFiche(title)'s own template had no « not found » branch",
                sheet_lost["open"]
                and "non identifié" in sheet_lost["bar"]
                and "Métadonnées inconnues" in sheet_lost["body"]
                and "Genres inconnus" in sheet_lost["body"],
                f"key={sheet_lost['key']} title={sheet_lost['title']!r}")
            journal.check(
                "the address stays exactly as typed",
                pg.url == wrong_sheet_address, pg.url)
            journal.check("no JS error on an unknown sheet title", not errors, str(errors))
            await ctx.close()

            # ─── Hold (j): a title with no trailer renders the no-info
            # part in the trailer's own place — Broadchurch's cast and
            # seasons are otherwise fully populated, so this is the ONLY
            # no-info part the screen draws; a stray match here would be a
            # real regression, not a coincidence from an unrelated
            # missing field. ────────────────────────────────────────────
            ctx, pg, errors = await open_at(browser, f"{base}/")
            no_trailer_ids = await pg.evaluate(
                f"()=>window.addressIdsFor({json.dumps(TITLE_WITHOUT_TRAILER)})")
            await ctx.close()
            no_trailer_address = (
                f"{base}/media/{no_trailer_ids['provider']}/{no_trailer_ids['id']}")
            ctx, pg, errors = await open_at(browser, no_trailer_address)
            sheet_no_trailer = await pg.evaluate(SHEET_STATE)
            journal.check(
                "(j) a sheet with no trailer renders the no-info part in its place",
                sheet_no_trailer["open"]
                and len(sheet_no_trailer["noinfos"]) == 1
                and "bande-annonce" in sheet_no_trailer["noinfos"][0],
                f"noinfos={sheet_no_trailer['noinfos']!r}")
            journal.check("no JS error on a sheet with no trailer", not errors, str(errors))
            await ctx.close()

            # ─── Holds (k)-(l): the arbitration screen's deep entry — the
            # SAME folder that regresses `server.py`'s fallback (its
            # deepest segment carries dots, `Backrooms.2026.MULTi.2160p.
            # WEB-DL`), so reaching it here is also what proves the fix
            # holds all the way to the SPA, not merely the raw HTTP
            # response `server.py`'s own self-test already covers. ──────
            resolution_address = f"{base}/resolution/{urllib.parse.quote(RESOLUTION_FOLDER)}"
            ctx, pg, errors = await open_at(browser, resolution_address)
            resolution_cold = await pg.evaluate(RESOLUTION_STATE)
            journal.check(
                "(k) a deep /resolution address opens the promised screen, cold — "
                "the folder as typed, in the mono face",
                resolution_cold["open"]
                and resolution_cold["key"] == f"resolution:{RESOLUTION_FOLDER}"
                and resolution_cold["folder"] == RESOLUTION_FOLDER,
                f"key={resolution_cold['key']} folder={resolution_cold['folder']!r}")
            journal.check("no JS error on deep /resolution entry", not errors, str(errors))

            await pg.evaluate("""()=>document.querySelector('[data-part="screen"][data-open] [data-part="screen/back"]').click()""")
            await pg.wait_for_timeout(300)
            resolution_returned = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "(l) a Retour from the resolution lands on the default page, "
                "screen gone, at the home page's own address",
                not resolution_returned["open"] and resolution_returned["pathname"] == HOME,
                resolution_returned["pathname"])
            journal.check("no JS error during the back from the resolution",
                             not errors, str(errors))
            await ctx.close()

            # ─── Holds (m)-(n): the release picker's deep entry — its bar
            # carries the title, not a lookup: RELEASES is a fixed
            # référentiel, so there is nothing here to fail against a title,
            # unlike the mediaSheet's `sheetFor`. ──────────────────────────────
            releases_address = f"{base}/releases/{urllib.parse.quote(RELEASES_TITLE)}"
            ctx, pg, errors = await open_at(browser, releases_address)
            releases_cold = await pg.evaluate(RELEASES_STATE)
            journal.check(
                "(m) a deep /releases address opens the promised screen, cold — "
                "the title in the bar, candidates drawn",
                releases_cold["open"]
                and releases_cold["key"] == f"releases:{RELEASES_TITLE}"
                and releases_cold["bar"] == RELEASES_TITLE
                and releases_cold["candidates"] > 0,
                f"key={releases_cold['key']} bar={releases_cold['bar']!r} "
                f"candidates={releases_cold['candidates']}")
            journal.check("no JS error on deep /releases entry", not errors, str(errors))

            await pg.evaluate("""()=>document.querySelector('[data-part="screen"][data-open] [data-part="screen/back"]').click()""")
            await pg.wait_for_timeout(300)
            releases_returned = await pg.evaluate(SCREEN_STATE)
            journal.check(
                "(n) a Retour from the releases lands on the default page, "
                "screen gone, at the home page's own address",
                not releases_returned["open"] and releases_returned["pathname"] == HOME,
                releases_returned["pathname"])
            journal.check("no JS error during the back from the releases",
                             not errors, str(errors))
            await ctx.close()

            # ─── Hold (o): an unknown deep /resolution value renders the
            # screen's OWN honest empty case — `decisionPending` finds no
            # pending decision for a name nobody scraped, so `ResolutionScreen`
            # takes the branch it already draws for that: no candidates
            # borrowed, the "aucun candidat" rulenote, and the two ways out
            # that do not depend on one still offered. ────────────────────
            wrong_resolution_address = f"{base}/resolution/{UNKNOWN_ADDRESS}"
            ctx, pg, errors = await open_at(browser, wrong_resolution_address)
            resolution_lost = await pg.evaluate(RESOLUTION_STATE)
            resolution_lost_body = resolution_lost["body"].lower()
            journal.check(
                "(o) an unknown folder still renders the screen, honestly — no candidate "
                "borrowed, the manual search and « laisser tel quel » still offered",
                resolution_lost["open"]
                and resolution_lost["folder"] == "N'Existe Pas"
                and "aucun candidat" in resolution_lost_body
                and "manuellement" in resolution_lost_body
                and "Laisser tel quel" in resolution_lost["body"],
                f"key={resolution_lost['key']} folder={resolution_lost['folder']!r}")
            journal.check(
                "the address stays exactly as typed",
                pg.url == wrong_resolution_address, pg.url)
            journal.check("no JS error on an unknown resolution folder",
                             not errors, str(errors))
            await ctx.close()

            # ─── Hold (p): an unknown deep /releases value renders the SAME
            # candidate list — RELEASES carries no per-title lookup to fail,
            # unlike a mediaSheet's `sheetFor`, so the honest case here is simply
            # the ordinary screen, wearing whatever title was typed. ───────
            wrong_releases_address = f"{base}/releases/{UNKNOWN_ADDRESS}"
            ctx, pg, errors = await open_at(browser, wrong_releases_address)
            releases_lost = await pg.evaluate(RELEASES_STATE)
            journal.check(
                "(p) an unknown title still renders the releases list, "
                "with that title in the bar",
                releases_lost["open"]
                and releases_lost["bar"] == "N'Existe Pas"
                and releases_lost["candidates"] > 0,
                f"key={releases_lost['key']} bar={releases_lost['bar']!r}")
            journal.check(
                "the address stays exactly as typed",
                pg.url == wrong_releases_address, pg.url)
            journal.check("no JS error on an unknown releases title",
                             not errors, str(errors))
            await ctx.close()

        await browser.close()

    journal.summary()


asyncio.run(main())
