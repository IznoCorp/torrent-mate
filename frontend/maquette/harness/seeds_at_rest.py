"""R128 — what the seeds offer to a HAND, with no named state (B-345).

THE HARNESS AND THE OPERATOR DO NOT REACH THE SAME INTERFACE. Every rule here
arrives through a NAMED STATE — `engine/states.js`, `window.__go` — which
re-seeds the layer for the case it is about. The operator has no such door: he
opens the design host on his phone and walks, so what he can try is exactly what
the seeds hold AT REST. B-345 is the gap between the two, and it was paid for:
the one verb B-309 repaired was unreachable to him because no followed medium
sat in Arrivées « à prendre » at rest, so a repair that was real read as a
repair that had not happened.

THE RULING IS A PROPERTY OF THE FIXTURES, not of one seed: the data the design
host serves at rest holds at least one subject in every state every surface can
draw. The operator's own words for the acquisition surfaces' share: « the
acquisition seeds offer at rest a takeable arrival for a followed medium, a
blocked one, a paused follow and a season with a hole, with a rule that counts
them. » This is that rule, and it counts those four.

THE READING BEFORE THE SEEDS MOVED, which is what the entry lacked: 12 follows,
`up_to_date` ×7 and `pending` ×5 — no `disabled`, nothing `to_grab`, nothing
`acquiring` — and `takeable.json`'s two cards, « The Hawk » and « Backrooms »,
neither of them a followed medium.

IT NEVER CALLS `window.__go`, AND THAT IS THE WHOLE POINT. A hold that drove a
named state first would measure what the harness can reach and report it as what
a hand can reach, which is the confusion the entry exists to end. The walk here
is a boot and two taps on the acquisition tabs — the same two a thumb makes.

AND IT READS BOTH ENDS. The LAYER's answer says the seed holds the subject; the
SCREEN says a finger could find it. Either alone is half the question: a seed
nothing draws is unreachable, and a card drawn from a state nobody seeded is not
at rest.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# THE FOLLOWS THE LAYER HOLDS, with the two fields this rule asks about: what
# the follow is and what state it is in.
FOLLOWS = """()=>(window.__followActions?.all() || []).map(
  (one) => ({t: one.t, k: one.k, st: one.st}))"""

# THE QUEUE THE LAYER HOLDS. `window.__queue` answers the lists the arrivals
# surfaces are drawn from, so this is the same answer the screen was built from
# rather than a second opinion about it.
QUEUE = """()=>{const now = window.__queue?.() || {};
  const titles = (list) => (now[list] || []).map((one) => one && one.t).filter(Boolean);
  return {takeable: titles("takeable"), blocked: titles("blocked"),
          inFlight: titles("inFlight")};}"""

# EVERY SEASON WITH A HOLE, decided from the DATA. `window.SEASONS` is
# `[number, aired, owned]` per season; a hole is `owned < aired` — an episode
# that HAS aired and is not held. An unaired episode is not a hole: it is not
# out yet, and counting it would report a want nobody has.
SEASON_HOLES = """()=>{
  const found = [];
  for (const follow of (window.__followActions?.all() || [])) {
    for (const [number, aired, owned] of (window.SEASONS[follow.t] || [])) {
      if ((owned || 0) < (aired || 0))
        found.push({title: follow.t, season: number, aired, owned});
    }
  }
  return found;}"""

# WHAT IS DRAWN, read as the titles the surface carries. A card's title and a
# row's title are the same part, which is what makes one reader enough.
TITLES_ON_SCREEN = """()=>[...document.querySelectorAll(
  '[data-part="card/title"], [data-part="tile/title"]')].map(
  (one) => (one.textContent || '').trim())"""


async def main():
    journal = Journal("R128 — the seeds offer every state to a hand at rest")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # THE WALK IS A THUMB'S. Two taps, no seam and no named state — the
        # acquisition page, then each of its two tabs in turn.
        #
        # `[data-page]` IS THE FRAME'S BAR AND `[data-go]` IS NOT. The first
        # version of this walk clicked `[data-go="acq"]` and timed out after
        # thirty seconds waiting for it: `data-go` is a CROSS-REFERENCE inside
        # a page — « voir les arrivées » at the foot of a section — so it
        # exists only where an author put one, and none is on the boot page.
        # The bar the thumb actually uses carries `data-page` (`app/tab-bar.tsx`,
        # from `NAVIGATION`'s `inBar` rows).
        await page.click('[data-page="acq"]')
        await page.wait_for_timeout(SETTLED)
        await page.click('[data-acqtab="now"]')
        await page.wait_for_timeout(SETTLED)

        queue = await page.evaluate(QUEUE)
        follows = await page.evaluate(FOLLOWS)
        followed = {one["t"] for one in follows}
        drawn_now = await page.evaluate(TITLES_ON_SCREEN)

        journal.check(
            "the boot alone fills the arrivals — no named state was asked for",
            bool(queue["takeable"] or queue["blocked"] or queue["inFlight"]),
            str(queue))

        # ── 1. A TAKEABLE ARRIVAL FOR A FOLLOWED MEDIUM ────────────────────
        #
        # B-345's own case. « À prendre » held two arrivals and neither was a
        # medium the operator follows, so « Récupérer maintenant » — repaired,
        # measured, green — could not be tried by hand at all.
        takeable_followed = [one for one in queue["takeable"] if one in followed]
        journal.check(
            "« À prendre » offers an arrival for a medium the operator FOLLOWS "
            "(B-345: the state B-309's verb needs to be tried by hand)",
            bool(takeable_followed),
            f"takeable={queue['takeable']} followed∩={takeable_followed}")
        journal.check(
            "and that arrival is DRAWN, so a thumb finds it without a seam",
            any(one in drawn_now for one in takeable_followed),
            f"{takeable_followed} against {drawn_now}")

        # ── 2. A BLOCKED ARRIVAL ───────────────────────────────────────────
        journal.check(
            "a BLOCKED arrival is offered at rest — the decision surfaces have "
            "a subject without one being seeded for them",
            bool(queue["blocked"]), str(queue["blocked"]))
        journal.check(
            "and it is drawn on the same tab",
            any(one in drawn_now for one in queue["blocked"]),
            f"{queue['blocked']} against {drawn_now}")

        # ── 3. A PAUSED FOLLOW, OF EACH KIND ───────────────────────────────
        #
        # BOTH KINDS, and it is not one state asked for twice. A paused SERIES
        # and a paused FILM are drawn from the same status through different
        # code: the series has a fraction and the film has none, which is
        # exactly the difference B-350 turned on. A fixture holding only one of
        # them lets a rule about the pair be green over half of it.
        paused = [one for one in follows if one["st"] == "disabled"]
        paused_shows = [one["t"] for one in paused if one["k"] == "show"]
        paused_movies = [one["t"] for one in paused if one["k"] == "movie"]
        journal.check(
            "a PAUSED follow is offered at rest, and one of each kind — a "
            "series and a film (B-350's difference lives between the two)",
            bool(paused_shows) and bool(paused_movies),
            f"shows={paused_shows} movies={paused_movies}")

        await page.click('[data-acqtab="follows"]')
        await page.wait_for_timeout(SETTLED)
        drawn_follows = await page.evaluate(TITLES_ON_SCREEN)
        journal.check(
            "and the paused ones are DRAWN in « Suivis », where a thumb reaches "
            "them",
            all(one in drawn_follows for one in paused_shows + paused_movies),
            f"{paused_shows + paused_movies} against {drawn_follows}")

        # ── 4. A SEASON WITH A HOLE ────────────────────────────────────────
        #
        # Read on the DATA rather than on a panel: whether the seasons matrix
        # draws the hole is R125's subject, and this rule asks the question one
        # level up — is there anything for it to draw.
        holes = await page.evaluate(SEASON_HOLES)
        journal.check(
            "a followed medium has a SEASON WITH A HOLE at rest — an episode "
            "that aired and is not held, which is what a season grab is for",
            bool(holes), str(holes))
        journal.check(
            "and its medium is drawn in « Suivis » too",
            any(one["title"] in drawn_follows for one in holes),
            f"{[one['title'] for one in holes]} against {drawn_follows}")

        journal.check("and the whole walk raises no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
