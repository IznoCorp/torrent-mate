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


# THE FILE THAT MOVED, and one setting a thumb can open inside it — read off
# the layer's own answer rather than written down here, so a reseeding that
# renames a file falls on the seed's own guard and not on this walk.
MOVED_FILE_SETTING = """()=>{
  const topics = window.__queries?.getQueryData(['/api/config/schema']) || [];
  for (const topic of topics) {
    for (const setting of topic.r) {
      if (setting.f !== 'notify') continue;
      return {topic: topic.id, identity: setting.f + ':' + setting.c};
    }
  }
  return null;}"""

# A BOOLEAN SETTING IN A FILE THAT DID NOT MOVE — a switch, because it files
# its edit on the tap that changes it and the walk needs no keyboard.
ORDINARY_SETTING = """()=>{
  const topics = window.__queries?.getQueryData(['/api/config/schema']) || [];
  for (const topic of topics) {
    for (const setting of topic.r) {
      if (setting.f === 'notify' || setting.type !== 'boolean') continue;
      return {topic: topic.id, identity: setting.f + ':' + setting.c};
    }
  }
  return null;}"""

# The banners the page is drawing, whichever branch of it is on screen.
BANNERS = """()=>[...document.querySelectorAll('[data-part="load-error"]')]
  .map((one) => one.textContent.replace(/\\s+/g, ' ').trim())"""


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

        # ── 5. THE SETTINGS' SHARE: A CONFLICT, AND A RESTART OWED ─────────
        #
        # B-345's settings half — « a conflict and a restart owed ». Both banners
        # were reachable only from a named state or from a dial — the rule
        # raised `setConfigurationConflict(true)` and read what it had raised,
        # which measures the harness and reports it as what a hand can do.
        #
        # AT REST, one configuration file answers `conflict: true` on its OWN
        # write (`mocks/state.ts`'s `movedFiles`), so a hand reaches B-299's
        # banner by saving a setting that lives in it; and any save at all
        # raises the restart, so B-300's confirmation is one tap further on.
        # The dial STAYS a dial — it is a property of the request — and this is
        # the property of the FILE that a thumb can find.
        # « RÉGLAGES » IS NOT IN THE TAB BAR — `app/navigation.ts` puts five
        # pages there and this is not one of them — so the walk goes the way a
        # thumb goes: Système, then its own row that leads to the settings.
        await page.click('[data-page="sys"]')
        await page.wait_for_timeout(SETTLED)
        await page.click('[data-page="cfg"]')
        await page.wait_for_timeout(SETTLED)
        moved = await page.evaluate(MOVED_FILE_SETTING)
        if journal.check(
                "a configuration file has MOVED under the editor at rest, with a "
                "setting in it a thumb can open (B-345)",
                moved is not None, str(moved)):
            await page.click(f'[data-topic="{moved["topic"]}"]')
            await page.wait_for_timeout(SETTLED)
            await page.click(f'[data-setting="{moved["identity"]}"]')
            await page.wait_for_timeout(SETTLED)
            # A SWITCH FILES ITS EDIT ON THE TAP that changes it — there is
            # nothing held back for a « Valider » to release, which is why the
            # panel offers none for this kind.
            await page.click('#sheetin [data-part="field/toggle"]')
            await page.wait_for_timeout(SETTLED)
            for _ in range(4):
                if "panel=" not in await page.evaluate("()=>location.search"):
                    break
                await page.evaluate("()=>history.back()")
                await page.wait_for_timeout(450)
            saved = await page.query_selector('#savebar [data-save]')
            if saved is not None:
                await saved.click()
                await page.wait_for_timeout(900)
            banners = await page.evaluate(BANNERS)
            journal.check(
                "so SAVING it reaches the version-conflict banner with no dial "
                "and no named state (B-299, B-345)",
                any("conflit" in one.lower() for one in banners), str(banners))
            # AND NOT THE OTHER ONE, in the same breath: the file moved, so
            # nothing was written, so nothing is owed. A build that raised both
            # would be telling the operator a restart is needed for an edit the
            # layer refused.
            journal.check(
                "and that save owes no restart, because it wrote nothing",
                not any("redémarr" in one.lower() for one in banners),
                str(banners))

            # THE RESTART IS THE OTHER SAVE, and reaching it takes the way out
            # the conflict banner offers: the editor's copy is stale, so the
            # edits go with the banner and the settings are asked for again.
            await page.click('[data-reloadsettings]')
            await page.wait_for_timeout(SETTLED)
            ordinary = await page.evaluate(ORDINARY_SETTING)
            if journal.check(
                    "a setting in a file that did NOT move is one tap away too",
                    ordinary is not None, str(ordinary)):
                await page.evaluate("()=>history.back()")
                await page.wait_for_timeout(SETTLED)
                await page.click(f'[data-topic="{ordinary["topic"]}"]')
                await page.wait_for_timeout(SETTLED)
                await page.click(f'[data-setting="{ordinary["identity"]}"]')
                await page.wait_for_timeout(SETTLED)
                await page.click('#sheetin [data-part="field/toggle"]')
                await page.wait_for_timeout(SETTLED)
                for _ in range(4):
                    if "panel=" not in await page.evaluate("()=>location.search"):
                        break
                    await page.evaluate("()=>history.back()")
                    await page.wait_for_timeout(450)
                saved = await page.query_selector('#savebar [data-save]')
                if saved is not None:
                    await saved.click()
                    await page.wait_for_timeout(900)
                banners = await page.evaluate(BANNERS)
                journal.check(
                    "and SAVING it reaches the restart the operator has to "
                    "confirm — B-300's own path, with no named state (B-343, "
                    "B-345)",
                    any("redémarr" in one.lower() for one in banners),
                    str(banners))

        journal.check("and the whole walk raises no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
