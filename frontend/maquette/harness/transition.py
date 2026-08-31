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
        "names: window.__names || [], "
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

    # THE TRANSITION SHOWS THE PREVIOUS STATE, which is a different claim
    # from « a transition is running » and the one this rule used to miss.
    #
    # Phase 9 asked for the capture and then committed synchronously, to
    # keep `go()` synchronous. The browser captures AFTER the current task,
    # so the commit had already run and the « old » snapshot was the new
    # page: the transition animated nothing, and this rule was green because
    # animations were running the whole time.
    #
    # WHAT CATCHES IT IS A NAME THAT EXISTS ON ONE SIDE ONLY. The media
    # screen's hero is `screen-banner`; the library page it leaves carries no
    # `[data-part="hero"]` at all. So `new(screen-banner)` must appear and
    # `old(screen-banner)` must NOT — an old snapshot for a name the old
    # state does not contain can only mean the new page was already mounted
    # when the snapshot was taken.
    names = reading["names"] if isinstance(reading, dict) else []
    if motion != "reduce":
        journal.check(
            "the arriving screen's banner is captured as NEW",
            any("new(screen-banner)" in name for name in names),
            f"names seen: {names}")
        journal.check(
            "and NOT as old — the snapshot is the page being left",
            not any("old(screen-banner)" in name for name in names),
            "an old snapshot exists for a name the previous page does not "
            "carry, so the commit ran before the capture and the transition "
            "animates the new page against itself")

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






# ── ONE ENTRY, ONE OWNER ────────────────────────────────────────────────────
# A CSS animation on a tree mounted under `startViewTransition` does not START
# until the transition ENDS — rendering is frozen for the capture. So any
# element-side entry animation on a surface reached by a transition REPLAYS
# afterwards, over a snapshot that already showed the final state.
#
# Measured by the steward at 25ms intervals: the transition drew the media
# screen's hero full for 315ms; the element went to opacity 0 in ONE FRAME when
# the transition ended; `heroin` then replayed its 450ms entry from zero.
# Appear, flash, reappear — the operator read it as a bug and he was right.
#
# `:active-view-transition` CANNOT GUARD THIS, and that is worth keeping: by the
# moment the animation starts, the transition is over and the selector no longer
# matches. The remedy is not a guard but an ownership rule — an entry has one
# owner, and on a surface reached by transition that owner is the transition.
#
# THE HOLD IS THE SYMPTOM, NOT THE CAUSE, deliberately. It samples the arriving
# element's opacity through the whole arrival and refuses a DIP. A static rule
# grepping for `animate-*` would have to know every spelling of an entry, and
# would have missed this one twice over: `heroin` was declared BOTH as a
# Tailwind utility and as a rule in the dying stylesheet, and removing only the
# utility left it running.
ARRIVING_BACKGROUND = ".herobg"


async def hold_one_entry_one_owner(journal, browser):
    """Samples the arriving hero's opacity and refuses a dip."""
    context, page = await open_page_with(browser, "no-preference")
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)
    await page.evaluate(
        "(sel)=>{window.__samples=[];window.__sampler=setInterval(()=>{"
        " const node=document.querySelector(sel);"
        " if(node) window.__samples.push(Number(getComputedStyle(node).opacity));"
        "},25);}", ARRIVING_BACKGROUND)
    await page.click(TILE)
    await page.wait_for_timeout(1400)
    samples = await page.evaluate(
        "()=>{clearInterval(window.__sampler);return window.__samples;}")

    journal.check(
        "the arriving background is sampled at all",
        len(samples) > 10,
        f"{len(samples)} sample(s) — with too few, the hold below decides "
        "nothing")
    if len(samples) <= 10:
        await context.close()
        return
    journal.check(
        "the arriving background never dips — one entry has one owner",
        min(samples) >= 1.0,
        f"opacity fell to {min(samples)} after the transition had drawn it "
        "full: an element-side entry animation replayed over the transition's "
        "own, which reads as a flash")
    await context.close()


async def hold(journal):
    """Drives the page switch under both motion preferences."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_under(journal, browser, "no-preference")
        await hold_under(journal, browser, "reduce")
        await hold_one_entry_one_owner(journal, browser)
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R115 — the page switch is a declared transition")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
