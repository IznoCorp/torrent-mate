"""R115 — the page switch is a DECLARED transition, under both preferences.

P5 and P20. `lib/navigate.ts` decides when a page switch is a transition;
`styles/base.css` decides what it looks like. This drives a real switch and
reads the browser's own animation timeline.

WHY IT MUST BE READ MID-SWITCH, and why the oracle cannot do it. The oracle
measures at rest under `html.measuring`, so a state captured mid-transition is a
FLICKER — named states are measured settled, and that is right. A transition
therefore exists for the oracle only as its two end states, which are identical
whether it animated or teleported. This rule drives the switch and reads it
WHILE it runs, which is the only moment a `::view-transition-*` animation exists
at all.

THE TWO HALVES, and neither alone is a proof (invariant 14):

  - under `no-preference`, a view transition must be RUNNING;
  - under `reduce`, NONE must be — and the switch must still HAPPEN.

The second half's second clause is the one that is easy to lose. `document
.startViewTransition` animates by DEFAULT: a browser given no rule of its own
cross-fades the whole document, so a reader who asked for no motion gets one
anyway unless something says otherwise. A rule that only checked « the page
changed » under `reduce` would be green over exactly that.

HOW A RUNNING TRANSITION IS SEEN. `document.getAnimations()` includes the
animations on the `::view-transition-*` pseudo-elements while the transition is
live, and they are named — `::view-transition-group`, `-old`, `-new`. Reading
the count of those specifically, rather than of all animations, is what keeps
this from passing on an unrelated spinner: the interface has a pulse and a
skeleton shimmer running at all times, so « some animation exists » is true on
every page of this application and proves nothing.

WHAT THIS DOES NOT READ: what the transition LOOKS like — its duration, its
easing, whether the fade is the right fade. Those are drawing decisions the
oracle owns at rest and a person owns in review. This holds that the switch is
declared rather than scripted, that it runs, and that it has a defined
appearance under both preferences.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

# WHICH NAVIGATION THIS DRIVES, AND WHY IT IS NOT THE TAB BAR.
#
# The tab bar's page switch does NOT pass through `lib/navigate.ts`. Measured:
# tapping `#nav button[data-page="lib"]` changes the address from /acquisition to
# /media and calls `document.startViewTransition` ZERO times — the engine handles
# it entirely (`store.write({page})`, `render()`, `switchPage(leaving)`), with no
# seam in between that anything outside the engine owns. Making that one a
# transition would mean ADDING to `legacy.js`, which D5 forbids, and its handler
# is an engine-side caller this lot leaves to L19 by name.
#
# What DOES route through `go()` is every screen and sheet arrival — the media
# sheet, the quality screen, the resolution screen. Those are the transitions
# this lot declares, and the shared element of phase 10 is one of them.
#
# Driven from the gallery, tapping a tile: / -> /media/tmdb/<id>.
FROM_STATE = "lib-grid"
TILE = '[data-part="tile"]'

# The transition's own duration is `--duration-2` = 200ms. The poll must be
# fast enough to land inside it and is run repeatedly rather than once: a single
# read placed by hand either side of a 200ms window is a coin toss, and a rule
# that flakes is a rule nobody believes.
POLL_MILLISECONDS = 16
POLL_ATTEMPTS = 40


WATCH_VIEW_TRANSITIONS = """()=>{
  window.__peak = 0;
  window.__called = 0;
  window.__names = [];
  const native = document.startViewTransition;
  if (native) {
    document.startViewTransition = function (callback) {
      window.__called += 1;
      return native.call(this, callback);
    };
  }
  window.__watch = setInterval(() => {
    const running = document.getAnimations().filter((animation) => {
      const pseudo = animation.effect && animation.effect.pseudoElement;
      return !!pseudo && pseudo.includes('view-transition');
    });
    if (running.length > window.__peak) {
      window.__peak = running.length;
      // EVERY name, never a slice. A truncated list once cut the two
      // `old(carried-poster)` rows off a ten-row reading and produced a defect
      // report about code that was correct.
      window.__names = running.map((a) => a.effect.pseudoElement);
    }
  }, 8);
}"""


async def open_page_with(browser, motion):
    """Opens the prototype under a motion preference.

    Args:
        browser: A launched Playwright browser.
        motion: `"no-preference"` or `"reduce"`.

    Returns:
        The (context, page) pair.
    """
    context = await browser.new_context(
        **{**PHONE, "reduced_motion": "reduce" if motion == "reduce" else "no-preference"})
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    return context, page


async def switch_and_watch(page):
    """Switches page and watches for a view-transition animation.

    The watcher is installed BEFORE the switch and samples on every frame, so a
    transition shorter than one poll interval is still seen.

    Args:
        page: The Playwright page.

    Returns:
        A dict carrying the peak count of view-transition animations seen and
        whether the API was called at all.
    """
    await page.evaluate(WATCH_VIEW_TRANSITIONS)
    await page.click(TILE)
    for _ in range(POLL_ATTEMPTS):
        await page.wait_for_timeout(POLL_MILLISECONDS)
    return await page.evaluate(
        "()=>{clearInterval(window.__watch); "
        "return {peak: window.__peak, called: window.__called, "
        "page: document.documentElement.dataset.page || ''};}")


async def hold_under(journal, browser, motion):
    """Drives a page switch under one motion preference."""
    context, page = await open_page_with(browser, motion)
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(500)
    before = await page.evaluate("()=>location.pathname")
    reading = await switch_and_watch(page)
    after = await page.evaluate("()=>location.pathname")

    # THE SWITCH ITSELF HAPPENS UNDER BOTH PREFERENCES. Without this the
    # `reduce` hold below passes over a navigation that never occurred.
    journal.check(
        f"under `{motion}`, the navigation HAPPENS",
        before != after,
        f"the address stayed at {after} — a transition that prevents the "
        "navigation is worse than no transition")

    journal.check(
        f"under `{motion}`, the switch goes through startViewTransition",
        reading["called"] >= 1,
        f"called {reading['called']}x — the transition must be DECLARED "
        "through the platform's API, not scripted (D9 rule 1)")

    if motion == "reduce":
        journal.check(
            "under `reduce`, NO view transition animates",
            reading["peak"] == 0,
            f"{reading['peak']} view-transition animation(s) ran — "
            "`startViewTransition` cross-fades by DEFAULT, so a reader who "
            "asked for no motion gets one unless the stylesheet says otherwise")
    else:
        journal.check(
            "under `no-preference`, the view transition RUNS",
            reading["peak"] > 0,
            "no `::view-transition-*` animation was ever running — the switch "
            "teleports, and the oracle cannot see the difference")
    await context.close()




# ── P6: the poster travels from the tile into the panel ─────────────────────
# The long press opens the panel, and the panel shows the same poster. A shared
# element makes it ONE picture moving; without it the poster vanishes on the
# card and reappears, a different size, in a layer sliding up.
#
# THE PROOF IS `::view-transition-old(carried-poster)`, and only that. Every
# other reading is satisfied by an element that merely APPEARS: a `group` and a
# `new` exist for any newly named element, so a rule reading those is green over
# a poster that does not travel at all. The OLD snapshot exists only when
# something carried that name in the state before.
#
# WRITTEN AFTER THE PROBE THAT NEARLY COST A RE-ARCHITECTURE. A first reading
# sliced the pseudo-element list to eight entries while ten were running, so
# the two `old(carried-poster)` rows were cut off — and the conclusion drawn
# was that the shared element did not work and that phase 9's ordering was
# wrong. Both were false. A rule that truncates its own evidence reports a
# defect that is not there, which is the mirror of the guard that reports none
# that is.
CARRYING_STATE = "lib-grid"
CARRYING_TILE = '[data-part="tile"]'
PRESS_HOLD_MILLISECONDS = 660


async def hold_the_carried_poster(journal, browser, motion):
    """Long-presses a tile and reads whether the poster travelled."""
    context, page = await open_page_with(browser, motion)
    await page.evaluate("(s)=>window.__go(s)", CARRYING_STATE)
    await page.wait_for_timeout(600)
    await page.evaluate(WATCH_VIEW_TRANSITIONS)

    box = await page.evaluate(
        "(sel)=>{const e=document.querySelector(sel); if(!e) return null;"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height/2};}", CARRYING_TILE)
    journal.check(f"a tile is drawn to press ({motion})", bool(box), str(box))
    if not box:
        await context.close()
        return

    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
    marked = False
    for step in range(int(PRESS_HOLD_MILLISECONDS / 60)):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": box["x"] + 2, "y": box["y"] + 2, "id": 1}]})
        await page.wait_for_timeout(60)
        if step == 3:
            marked = await page.evaluate(
                "()=>!!document.querySelector('[data-carrying]')")
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(600)

    reading = await page.evaluate(
        "()=>{clearInterval(window.__watch);"
        " return {names: window.__names || [], called: window.__called || 0,"
        "  open: !!document.querySelector('#sheet')?.hasAttribute('data-open'),"
        "  left: !!document.querySelector('[data-carrying]')};}")

    journal.check(f"under `{motion}`, the press opens the panel",
                  reading["open"],
                  "no panel — nothing below decides anything")
    journal.check(
        f"under `{motion}`, exactly one tile is marked while the finger is down",
        marked,
        "no `[data-carrying]` mid-press — the poster has no name to travel under")
    # SATISFIED BY THE ENGINE'S RE-RENDER, and saying so is the honest form.
    # The surface is redrawn when the panel opens, so the marked tile is
    # detached whatever `panel-host` does — measured by removing its
    # `releaseCarriedPoster()` call and watching nothing change. This hold is
    # worth keeping (a tile that KEPT the name would break the transition) and
    # it does not isolate that call.
    journal.check(
        f"and under `{motion}` no tile still carries the name once the panel is up",
        not reading["left"],
        "a tile still carries it, so two elements answer to one name and the "
        "browser drops the transition")

    old = [name for name in reading["names"] if "old(carried-poster)" in name]
    if motion == "reduce":
        journal.check(
            "under `reduce`, the poster does NOT travel",
            not old,
            f"{old} — naming the element under this preference makes the "
            "browser animate it, and a reader who asked for no motion gets a "
            "journey anyway")
    else:
        journal.check(
            "under `no-preference`, the poster TRAVELS — an old snapshot exists",
            bool(old),
            f"names seen: {reading['names']} — a `group` and a `new` exist for "
            "any newly named element; only an OLD snapshot proves something "
            "carried the name in the state before")
    await context.close()


async def hold(journal):
    """Drives the page switch under both motion preferences."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_under(journal, browser, "no-preference")
        await hold_under(journal, browser, "reduce")
        await hold_the_carried_poster(journal, browser, "no-preference")
        await hold_the_carried_poster(journal, browser, "reduce")
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R115 — the page switch is a declared transition")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
