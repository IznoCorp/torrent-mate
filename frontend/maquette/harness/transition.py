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
# this lot declares. A carried poster was one of them for two days and is not:
# it was built, the operator watched it and withdrew it, and the name it used
# is in no file now.
#
# Driven from the gallery, tapping a tile: / -> /media/tmdb/<id>.
FROM_STATE = "lib-grid"
TILE = '[data-part="tile"]'

# The transitions run on `--duration-4` = 450ms since the re-tuning. The poll
# must be
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
  window.__commitAwaited = null;
  if (native) {
    document.startViewTransition = function (callback) {
      window.__called += 1;
      // DOES THE COMMIT HAND BACK ITS NAVIGATION? The browser captures the NEW
      // state when the callback's returned promise settles. A callback that
      // returns nothing is captured at the next rendering opportunity whether
      // or not the route has committed — so with a loader or a lazy component
      // on the arriving route, the « new » snapshot is the page being LEFT, and
      // every hold below stays green because they all read the old side.
      return native.call(this, () => {
        const answer = callback();
        window.__commitAwaited =
          !!answer && typeof answer.then === 'function';
        return answer;
      });
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
      // two `old(…)` rows off a ten-row reading and produced a defect
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
        "awaited: window.__commitAwaited, "
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
        f"under `{motion}`, the commit HANDS BACK its navigation",
        reading["awaited"] is True,
        f"the commit returned {reading['awaited']!r} rather than a promise — "
        "the new state is captured at the next rendering opportunity whether "
        "or not the route has committed. It is correct only while no route has "
        "a loader; the day one does, the arrival animates the departing page "
        "and nothing here would say so")
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
# ANCHORED ON `data-part`, NEVER ON THE CLASS (D4). A selector held in a
# variable dies the day the class is removed exactly like one written in a
# call, and `check-markup-contracts` refuses both at a hard zero.
ARRIVING_BACKGROUND_READ = """()=>{
  const hero = document.querySelector('[data-part="hero/background"]');
  return {arrival: hero ? (hero.dataset.arrival || '') : '',
          background: hero ? hero.style.backgroundImage : ''};
}"""

ARRIVING_BACKGROUND = '[data-part="hero/background"]'


async def hold_one_entry_one_owner(journal, browser, warmed):
    """Samples the arriving hero's opacity and refuses the wrong kind of entry.

    Args:
        journal: The rule's journal.
        browser: A launched Playwright browser.
        warmed: Whether to put the fanart in the cache BEFORE arriving, which is
            what makes the `immediate` branch reachable at all.

    BOTH BRANCHES ARE DRIVEN, and until the adversarial review neither was
    chosen: every exercise opened a fresh context, the gallery shows posters and
    not the fanart, so the file was never cached and `data-arrival` read `faded`
    EVERY time. The branch written for the operator's flash — a hero the
    transition already carried, which must not dip — had never executed once,
    and the branch that did execute was green over a second entry animation
    because a second entry also dips.
    """
    context, page = await open_page_with(browser, "no-preference")
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)

    if warmed:
        # THE FANART IS PUT IN THE CACHE BEFORE THE ARRIVAL. Its URL is the one
        # the media screen will paint, read from the fixture the same way the
        # screen reads it, and fetched in THIS context so the browser holds it.
        warmed_source = await page.evaluate("""async ()=>{
          const reference = window.__referentiel;
          const title = reference.titleForProviderId('tmdb', '1284465');
          const sheet = title ? reference.sheetFor(title) : null;
          const source = (window.HERO_IMAGES || {})[title]
            || (sheet && sheet.hero) || null;
          if (!source) return null;
          const image = new Image();
          image.src = source;
          try { await image.decode(); } catch (error) { return null; }
          return source;
        }""")
        journal.check(
            "the fanart can be warmed, so the `immediate` branch is reachable",
            bool(warmed_source),
            "no hero source found to pre-load — without it every run takes the "
            "`faded` branch and the hold written for the operator's flash never "
            "executes")
        if not warmed_source:
            await context.close()
            return

    # TWO SAMPLES PER FRAME, and they answer two different questions. The
    # ELEMENT's opacity must never move: it carries the placeholder colour and
    # the melt gradient, so anything fading IT blinks both. The COVER's opacity
    # is the picture's entry — a `::before` the placeholder's colour, fading
    # out, revealing the file underneath.
    await page.evaluate(
        "(sel)=>{window.__samples=[];window.__cover=[];window.__coverFrom=null;"
        "window.__sampler=setInterval(()=>{"
        " const node=document.querySelector(sel);"
        " if(!node) return;"
        " window.__samples.push(Number(getComputedStyle(node).opacity));"
        " const cover=getComputedStyle(node, '::before');"
        " window.__cover.push(cover.content === 'none'"
        "   ? null : Number(cover.opacity));"
        " for (const animation of node.getAnimations({subtree:true})) {"
        "   const frames = animation.effect && animation.effect.getKeyframes"
        "     ? animation.effect.getKeyframes() : [];"
        "   if (frames.length && frames[0].opacity !== undefined)"
        "     window.__coverFrom = String(frames[0].opacity);"
        " }"
        "},16);}", ARRIVING_BACKGROUND)
    await page.click(TILE)
    await page.wait_for_timeout(1600)
    samples = await page.evaluate(
        "()=>{clearInterval(window.__sampler);return window.__samples;}")
    cover = [value for value in await page.evaluate("()=>window.__cover")
             if value is not None]
    cover_from = await page.evaluate("()=>window.__coverFrom")

    journal.check(
        f"the arriving background is sampled at all ({'warm' if warmed else 'cold'})",
        len(samples) > 10,
        f"{len(samples)} sample(s) — with too few, the holds below decide "
        "nothing")
    if len(samples) <= 10:
        await context.close()
        return

    arrival = await page.evaluate(
        "(sel)=>{const node=document.querySelector(sel);"
        " return node ? (node.dataset.arrival || '') : '';}",
        ARRIVING_BACKGROUND)
    journal.check(
        f"the arrival is the one this exercise drove ({'warm' if warmed else 'cold'})",
        arrival == ("immediate" if warmed else "faded"),
        f"data-arrival is {arrival!r} where {'immediate' if warmed else 'faded'} "
        "was driven — the branch below is not the branch this exercise exists "
        "to reach")

    # HOW MANY TIMES THE PICTURE GOES AWAY, not merely whether it ever does.
    # « min < 1 » is true of one fade and of two, so it was green over a second
    # entry animation replaying after the transition — the hero's flash exactly.
    #
    # COUNTED ON THE COVER, WHICH IS WHERE THE ENTRY LIVES. It was counted on the
    # ELEMENT, and the day the fade moved to a `::before` that made it a
    # tautology: the hold above establishes the element never leaves 1.0, and no
    # index can then satisfy `samples[i-1] >= 1.0 > samples[i]`, so `descents`
    # was 0 whenever the hold above passed and could only fall after it already
    # had. A second entry replaying now replays on the COVER, and nothing was
    # watching it.
    def rises_in(series):
        """How many upward STEPS a retreating cover takes back over the picture.

        It counts steps of 0.15 rather than whole rises — a single 0 → 1 return
        is several of them — so the number is a magnitude and not a count of
        replays. What the hold reads is whether it is ZERO, and for that the
        distinction does not matter; the name says so rather than implying a
        precision the arithmetic does not have.

        A COVER ONLY EVER RETREATS. « How many times does it fall from full »
        cannot say that: an entry replayed a second time passes through full
        opacity for one instant between the two falls, and a 16ms sampler reads
        exactly 1.0 there only by luck — measured, a cover keyframed 1 → 0 → 1
        → 0 was counted as ONE descent, because the peak fell between two
        samples. What a second entry always leaves behind is a RISE.

        Args:
            series: The cover's opacity samples, in order.

        Returns:
            How many times the series rose materially above its running low.
        """
        recoveries = 0
        lowest = series[0] if series else 1.0
        for value in series:
            if value > lowest + 0.15:
                recoveries += 1
                lowest = value
            lowest = min(lowest, value)
        return recoveries

    descents = rises_in(cover)
    if arrival == "immediate":
        journal.check(
            "a hero the transition already carried does NOT dip — one owner",
            min(samples) >= 1.0,
            f"opacity fell to {min(samples)} on a picture that was already "
            "there: a second entry replayed over the transition's own, which is "
            "the flash the operator saw")
        # AND THERE IS NO COVER AT ALL, which is the half the element cannot
        # say. The entry lives on a `::before` keyed on `faded`; widen that key
        # to any arrival and the cover replays over a picture the transition
        # already drew — appear, flash, reappear — while the element sits at 1.0
        # throughout and the hold above stays green. A CSS animation on a tree
        # mounted under `startViewTransition` starts when the transition ENDS,
        # which is exactly when that flash would be seen.
        journal.check(
            "and it has no entry of its own — nothing covers a carried hero",
            not cover,
            f"a cover was drawn on it, running {max(cover) if cover else None} "
            f"to {min(cover) if cover else None}: the transition already showed "
            "this picture, so anything revealing it a second time is the flash")
    else:
        # IT PASSES THROUGH THE MIDDLE, which is what separates a fade from a
        # snap — and « first high, last low » does not: a `steps(1, end)` on the
        # same animation gives [1, 1, 1, 1, 0, 0, 0, 0], first high, last low,
        # no rise and no descent, and the picture appears in ONE FRAME. That is
        # the sentence in this hold's own failure message, and the hold was
        # green over it. A 450ms fade sampled at 16ms lands in the middle band
        # about twenty times; a snap never does.
        #
        # AND THE START IS READ FROM THE DECLARED KEYFRAME rather than from the
        # first sample. `cover[0] > 0.9` demanded that the first read land
        # within about 90ms of the start on this curve — a loaded runner that
        # reaches the mark later reads 0.896 and the hold falls for the
        # machine's reasons. What A1 actually repaired is the `from` being
        # DECLARED, so that is what is asserted.
        middle = [value for value in cover if 0.15 < value < 0.85]
        journal.check(
            "a hero whose file arrived LATE fades in rather than snapping",
            len(cover) > 4 and len(middle) >= 3 and cover[-1] < 0.5,
            f"the cover ran {cover[0] if cover else None} to "
            f"{cover[-1] if cover else None} over {len(cover)} sample(s), "
            f"{len(middle)} of them between 0.15 and 0.85 — a picture that "
            "arrived after the transition appeared in one frame, or the cover "
            "ran the wrong way")
        journal.check(
            "and its entry DECLARES where it starts",
            cover_from == "1",
            f"the cover's first keyframe declares opacity {cover_from!r} — left "
            "implicit, the browser takes the pseudo-element's underlying value "
            "and re-evaluates it mid-flight: measured, the cover ran 1 → 0.002 "
            "→ 0.996 → 0 inside ONE run, which is the flash this rule exists "
            "to refuse")
        journal.check(
            "and the ELEMENT itself never dips — the placeholder and the melt "
            "stay",
            min(samples) >= 1.0,
            f"opacity fell to {min(samples)} on the element that CARRIES the "
            "placeholder colour and the melt gradient: fading it takes both "
            "away for a frame and brings them back with the image, which is "
            "the flash this rule exists to refuse, in miniature")
        journal.check(
            "and it fades ONCE — one entry, one owner",
            descents == 0,
            f"the cover came back over the picture {descents} time(s) after "
            "retreating: it is revealed more than once, which is a second entry "
            "animation replaying over the first")
    await context.close()





# ── OPTIMISTIC PRIMING — a dead tap is impossible by construction ────────────
# « A généralisée + amorçage optimiste » (operator, 2026-08-31): the optimistic-answer property's
# discipline applied to an ARRIVAL. The media screen opens with what the tap
# already knows — title, year, type, poster — in real content, on the first
# frame. The wait is only ever for what is genuinely unknown.
#
# THE HOLD MUST SEPARATE PRIMED FROM SERVED, and the operator named that trap
# before it was built: a rule that only asks « was there content on the first
# frame? » is GREEN ON A SCREEN THAT NEVER ENRICHES — priming alone would
# satisfy it forever. So this reads both ends: the content is there while the
# query is still `isPlaceholderData`, AND the query later stops being
# placeholder. Either half alone proves the wrong thing.
#
# `placeholderData` rather than `initialData` is what makes that observable at
# all: initial data is written INTO the cache and is indistinguishable from a
# served answer afterwards.
#
# DRIVEN AGAINST A DELIBERATELY SLOW READ, because priming has no subject when
# the answer is instant — a fixture that resolves at once produces content on
# the first frame whether or not anything primed it.
PRIMING_DELAY_MILLISECONDS = 1200
MEDIA_TITLE = '[data-part="hero/title"]'

READ_PRIMING = """()=>{
  // THE SHEET'S OWN QUERY, not the seasons one beside it: both keys begin
  // '/api/media', and `find` took whichever came first.
  const sheet = window.__queries.getQueryCache().getAll()
    .find((query) => query.queryKey[0] === '/api/media'
                     && query.queryKey.length === 3);
  // THE META LINE, NOT THE TITLE. The title is derived from the ROUTE
  // (`titleForProviderId`) and is drawn whether or not anything primed the
  // query — reading it left this hold green with `placeholderData` DELETED,
  // which is the trap its own comment says it refuses. The year and the type
  // come from the sheet payload, and only priming puts them on screen before
  // the read lands.
  const meta = document.querySelector('[data-part="hero/content"] p');
  return {
    meta: ((meta && meta.textContent) || '').trim(),
    // THE CACHE IS EMPTY UNTIL THE READ LANDS. `state.status === 'pending'`
    // said only that a read was outstanding, which is true with or without
    // priming; placeholder data lives on the observer and never in
    // `query.state`. What separates them is that the cache holds NOTHING while
    // the screen already shows the facts.
    cacheEmpty: !!sheet && sheet.state.data === undefined,
    served: !!sheet && sheet.state.data !== undefined,
  };
}"""


async def hold_the_priming(journal, browser):
    """Opens a media screen against a slow read and reads both ends."""
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)
    # THE READ IS SLOWED THROUGH THE MOCK LAYER'S OWN KNOB, not through
    # `page.route`. The mocks answer IN THE PAGE, so no request leaves it and a
    # network interception matches NOTHING — measured, zero routes intercepted,
    # which means an earlier version of this hold ran against a read that was
    # never slow and proved nothing about priming at all.
    await page.evaluate("(ms)=>window.__mocks.setDefaultLatency(ms)",
                        PRIMING_DELAY_MILLISECONDS)
    await page.click(TILE)
    await page.wait_for_timeout(140)

    early = await page.evaluate(READ_PRIMING)
    journal.check(
        "the media screen opens with PRIMED facts while its read is in flight",
        early["cacheEmpty"] and len(early["meta"]) > 2
        and "inconnu" not in early["meta"].lower(),
        f"read {early} — the screen must show the facts the tap already knew. "
        "« Métadonnées inconnues » is the screen's OWN empty case and is what a "
        "screen with no priming draws, so a length check alone passes over "
        "exactly the defect this hold exists for. The cache being empty is what "
        "makes this the PRIMED reading rather than a served one.")

    await page.wait_for_timeout(PRIMING_DELAY_MILLISECONDS + 900)
    late = await page.evaluate(READ_PRIMING)
    await page.evaluate("()=>window.__mocks.setDefaultLatency(0)")
    # THE OTHER END. Without this the hold above is satisfied forever by a
    # screen that primes and never enriches.
    journal.check(
        "and the read LANDS afterwards — primed is not the end state",
        late["served"],
        f"read {late} — the screen shows primed content and never replaces it, "
        "which this hold would otherwise call success")
    await context.close()




# ── THE PERSISTENT CHROME STAYS IN FRONT ────────────────────────────────────
# The operator saw it and the steward reproduced it in frames: « la bottom barre
# passe par une phase transparente » — the entering screen's cast row showed
# THROUGH the bar for the whole crossing, ghost icons over faces.
#
# NOTHING WAS TRANSPARENT. Un-named, the bar is baked into the ROOT group's
# snapshots; `screen-body` is a NAMED group extracted from that same snapshot,
# and named groups paint ABOVE the root group in the `::view-transition` tree.
# The body rose over the bar. The tab change was healthy because it runs the root
# pair ALONE, with no named group to paint over anything — which is the
# observation that identified the mechanism, and the reason this defect could not
# exist before transition A introduced a named group.
#
# WHAT THIS HOLDS, and why it is the group rather than a pixel. A screenshot
# comparison is not an oracle here (D8's own reason), and the pseudo-element tree
# is not hit-testable, so `elementFromPoint` answers about the real DOM and would
# be green either way. What IS observable and decisive is that the bar has a
# group of its own during the crossing: un-name it and the group disappears,
# which is exactly the state that produced the defect.
#
# The second half refuses a fix that trades one defect for another: the bar
# exists at both ends with the same content, so its pairing must be STABLE — a
# group of its own that cross-fades would be a bar that blinks instead of a bar
# that is covered.
BAR = "#nav"


async def hold_the_chrome_stays_in_front(journal, browser):
    """Drives a page arrival and reads the bar's own group."""
    context, page = await open_page_with(browser, "no-preference")
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)

    named = await page.evaluate(
        "(sel)=>getComputedStyle(document.querySelector(sel)).viewTransitionName",
        BAR)
    journal.check(
        "the persistent bar carries a transition name of its own",
        named not in ("none", "", None),
        f"view-transition-name is {named!r} — un-named, the bar is baked into "
        "the ROOT snapshot and every NAMED group paints above it")

    await page.evaluate("""()=>{
      window.__groups = [];
      window.__fades = [];
      window.__watch = setInterval(() => {
        for (const animation of document.getAnimations()) {
          const pseudo = animation.effect && animation.effect.pseudoElement;
          if (!pseudo || !pseudo.includes('view-transition')) continue;
          window.__groups.push(pseudo);
          if (pseudo.includes('shell-tab-bar')
              && (pseudo.includes('old(') || pseudo.includes('new('))) {
            window.__fades.push(pseudo);
          }
        }
      }, 8);
    }""")
    await page.click(TILE)
    await page.wait_for_timeout(1200)
    reading = await page.evaluate(
        "()=>{clearInterval(window.__watch);"
        " return {groups:[...new Set(window.__groups)], fades:[...new Set(window.__fades)]};}")

    journal.check(
        "and it is its OWN group while the arrival crosses",
        any("group(shell-tab-bar)" in name for name in reading["groups"]),
        f"groups seen: {reading['groups']} — with no group of its own the bar "
        "is inside the root snapshot, underneath every named group, and the "
        "arriving content rises over it")
    journal.check(
        "and its pairing is STABLE — the bar does not fade of its own accord",
        not reading["fades"],
        f"{reading['fades']} — a bar with its own cross-fade blinks instead of "
        "being covered, which trades one defect for another")
    await context.close()


async def hold_the_panel_departs(journal, browser):
    """Arrives at the media screen FROM AN OPEN PANEL and reads the departure.

    THE ANIMATION THIS READS PAINTED NOTHING FOR A DAY, under a green rule set.
    « Voir la fiche » is reached from an open panel, and the engine closed the
    panel and waited 260ms before opening the screen — so by the time the
    transition captured the old state there was no open panel to capture,
    `#sheet[data-open]` matched nothing, and `::view-transition-old(leaving-panel)`
    never existed. Every hold in this file passed: they all read the ROOT
    transition, which happens either way.

    A view transition captures the old state at the next rendering update, not
    at the call, so no ordering of two statements in one task fixes this — the
    dismissal belongs INSIDE the commit, and that is what `go()`'s `during`
    exists for.

    Args:
        journal: The rule's journal.
        browser: A launched Playwright browser.
    """
    context, page = await open_page_with(browser, "no-preference")
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)

    # The panel is opened the way a reader opens it — a long press on a tile.
    box = await page.evaluate(
        "(sel)=>{const node=document.querySelector(sel);"
        " const r=node.getBoundingClientRect();"
        " return {x:r.x + r.width/2, y:r.y + r.height/2};}", TILE)
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
    await page.wait_for_timeout(700)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(600)

    opened = await page.evaluate(
        "()=>{const node=document.querySelector('#sheet');"
        " return {open: !!node && node.hasAttribute('data-open'),"
        "         name: node ? getComputedStyle(node).viewTransitionName : null};}")
    journal.check(
        "a long press opens the panel, and the open panel is NAMED",
        opened["open"] and opened["name"] == "leaving-panel",
        f"read {opened} — with no open panel there is no departure to drive, "
        "and with no name on it there is nothing for the stylesheet to animate")
    leave = await page.query_selector('#sheet [data-mediasheet]')
    journal.check(
        "and the panel offers the way onto the media screen",
        leave is not None,
        "no `[data-mediasheet]` control inside the open panel — the arrival "
        "this hold measures cannot be driven")
    if not (opened["open"] and leave):
        await context.close()
        return

    await page.evaluate("""()=>{
      window.__seen = new Set();
      window.__watch = setInterval(() => {
        for (const animation of document.getAnimations()) {
          const pseudo = animation.effect && animation.effect.pseudoElement;
          if (pseudo && pseudo.includes('view-transition')) {
            // THE NAME OF WHAT IS RUNNING, beside the pseudo-element it runs
            // on. The pseudo-element alone says only that the browser is
            // cross-fading, which it does by default.
            window.__seen.add(
              pseudo + ':' + (animation.animationName || '?'));
          }
        }
      }, 8);
    }""")
    await leave.click()
    # MID-CROSSING, the LIVE sheet must not be sliding: the transition owns the
    # departure. The seam's close removes `data-open`, and the sheet's own
    # stylesheet slide would then run on the element captured inside
    # `::view-transition-new(root)` — a second panel going down, on a second
    # curve, fading IN under the one fading out.
    await page.wait_for_timeout(150)
    live_panel = await page.evaluate("""()=>{
      const node = document.querySelector('#sheet');
      if (!node) return null;
      const style = getComputedStyle(node);
      // MOVEMENT ONLY. `visibility` still transitions on purpose — B-249's
      // idiom keeps the layer hit-testable until it has finished leaving — and
      // it moves nothing, so counting it here would make this hold refuse the
      // very thing the layer must keep doing.
      const moving = node.getAnimations().filter((animation) => {
        const property = animation.transitionProperty || animation.animationName;
        return property && property !== 'visibility';
      });
      return {transition: style.transitionProperty,
              duration: style.transitionDuration,
              running: moving.length,
              movingProperties: moving.map(
                (animation) => animation.transitionProperty
                  || animation.animationName),
              crossing: document.documentElement.matches(
                ':active-view-transition')};
    }""")
    await page.wait_for_timeout(1050)
    seen = await page.evaluate(
        "()=>{clearInterval(window.__watch); return [...window.__seen];}")

    # READ BY THE ANIMATION'S NAME, for the reason the body's hold pays two
    # hundred lines below: every `::view-transition-old(x)` carries the
    # browser's OWN cross-fade by default, so « the pseudo-element is animating »
    # is true with `animation: panel-down …` deleted outright — and `panel-down`
    # would then be a drawing decided with no rule, which is the sentence this
    # wave wrote about `body-rise` one commit earlier.
    journal.check(
        "the panel is captured LEAVING, so its departure has something to draw",
        any("old(leaving-panel):panel-down" in name for name in seen),
        f"pseudo-elements seen: {sorted(seen)} — no "
        "`::view-transition-old(leaving-panel)`. The panel was already shut "
        "when the old state was captured, so the departure animates nothing "
        "and the reader sees the panel vanish under an arriving screen")
    journal.check(
        "and the screen it arrives at is drawn in the same transition",
        any("screen-banner" in name or "screen-body" in name for name in seen),
        f"pseudo-elements seen: {sorted(seen)} — the arrival's own parts are "
        "absent, so the departure above is being read across some other "
        "transition than the one this hold drives")

    # THE DEPARTING PANEL OUTRANKS THE BAR, as it does at rest. The sheet is
    # `z-[52]` against the bar's `z-50` and its action row sits over the bar's
    # own footprint (P31, the operator's ruling). Ordering the bar's group and
    # leaving the panel's at `auto` inverts that for the crossing: the first
    # frame surfaces the bar over the leaving panel. Read on the pseudo-elements
    # themselves, which is where the order is declared.
    ranks = await page.evaluate("""()=>{
      const read = (name) => getComputedStyle(
        document.documentElement, '::view-transition-group(' + name + ')').zIndex;
      return {bar: read('shell-tab-bar'), panel: read('leaving-panel')};
    }""")
    journal.check(
        "the live panel does NOT slide while the transition draws its departure",
        bool(live_panel) and live_panel["crossing"]
        and live_panel["running"] == 0,
        f"read {live_panel} — the panel is animating on its own while "
        "`old(leaving-panel)` plays `panel-down` above it: two panels going "
        "down on two curves, which is « one entry, one owner » broken in the "
        "gesture that rule was written for")
    journal.check(
        "and the departing panel is ordered ABOVE the bar, as it is at rest",
        (ranks["panel"] not in ("auto", "", None)
         and ranks["bar"] not in ("auto", "", None)
         and int(ranks["panel"]) > int(ranks["bar"])),
        f"read {ranks} — at rest the sheet paints over the bar; ordered this "
        "way the bar surfaces over the leaving panel for the length of the "
        "crossing and the panel slides out from under it")
    await context.close()


async def hold_a_hero_that_changes_picture(journal, browser):
    """Navigates media to media and reads whether the hero is followed again.

    THE MEDIA SCREEN LEADS TO OTHER MEDIA — a suggestion, a related title — and
    the route's params change while the SAME element stays mounted with a new
    `background-image`. The first version of `artwork-arrival` returned early on
    `data-arrival` being set at all, and its observer watched added nodes only,
    so nothing followed the second picture: the stale mark stayed, no entry
    played, and the new fanart snapped in. On the one navigation most likely to
    happen twice in a row.

    Args:
        journal: The rule's journal.
        browser: A launched Playwright browser.
    """
    context, page = await open_page_with(browser, "no-preference")
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)
    await page.click(TILE)
    await page.wait_for_timeout(1500)

    first = await page.evaluate(ARRIVING_BACKGROUND_READ)
    journal.check(
        "the media screen is reached with a hero that carries a picture",
        bool(first["background"]) and bool(first["arrival"]),
        f"read {first} — without a first arrival there is no second one to "
        "compare against")
    if not (first["background"] and first["arrival"]):
        await context.close()
        return

    # EVERY WRITE OF THE MARK, counted across the second navigation. Its VALUE
    # cannot decide this: two faded arrivals in a row read `faded` both times,
    # so a stale mark and a fresh one are the same string. What separates them
    # is whether anything wrote it.
    await page.evaluate("""()=>{
      window.__hero = document.querySelector('[data-part="hero/background"]');
      window.__arrivalWrites = 0;
      new MutationObserver((records) => {
        window.__arrivalWrites += records.length;
      }).observe(window.__hero, {attributes: true,
                                 attributeFilter: ['data-arrival']});
    }""")
    clicked = await page.evaluate("""()=>{
      const all = [...document.querySelectorAll('[data-mediasheet]')];
      const node = all[all.length - 1];
      if (!node) return null;
      node.click();
      return node.getAttribute('data-mediasheet');
    }""")
    journal.check(
        "and it offers a way to ANOTHER medium",
        bool(clicked),
        "no `[data-mediasheet]` on the media screen — the navigation this hold "
        "measures cannot be driven")
    if not clicked:
        await context.close()
        return
    await page.wait_for_timeout(1600)

    second = await page.evaluate(ARRIVING_BACKGROUND_READ)
    same_node = await page.evaluate(
        """()=>window.__hero === document.querySelector(
             '[data-part="hero/background"]')""")
    writes = await page.evaluate("()=>window.__arrivalWrites")

    journal.check(
        "the second medium reuses the SAME hero element with a NEW picture",
        same_node and second["background"] != first["background"],
        f"same node {same_node}, {first['background']} then "
        f"{second['background']} — this hold exists for a picture that changes "
        "UNDER a mounted element, and that is not what was driven")
    journal.check(
        "and the mark is WRITTEN AGAIN, so the new picture gets an entry",
        writes >= 1,
        f"{writes} write(s) of `data-arrival` across the navigation — the mark "
        "left over from the previous medium was kept, so the arriving fanart "
        "plays no entry and snaps in")
    await context.close()


async def hold_one_owner_on_the_body(journal, browser):
    """Reads how many things animate the media body's blocks on one arrival.

    THE DRAWING SAID « one entry, one owner » AND HAD TWO. The blocks carry an
    element-side entry — `opacity` and `translate` from a `@starting-style` — on
    the argument that an element already present when the screen mounted never
    has a starting style, so the two cases could not overlap. The whole screen is
    inserted INSIDE the view transition's callback, so every block has one on the
    arrival itself: measured at 16ms, `opacity` and `translate` ran from 0 and
    16px in the very frames `body-rise` was lifting the same snapshot 24px.
    Forty pixels and a double fade.

    Nothing read it. `body-rise` was one of three drawings this lot decided with
    no rule at all, which is why a second owner could sit in it unseen.

    Args:
        journal: The rule's journal.
        browser: A launched Playwright browser.
    """
    context, page = await open_page_with(browser, "no-preference")
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)
    await page.evaluate("""()=>{
      window.__owners = new Set();
      window.__bodyOpacity = [];
      window.__watchBody = setInterval(() => {
        const body = document.querySelector('[data-region="screen-media/body"]');
        const block = body && body.firstElementChild;
        if (!block) return;
        window.__bodyOpacity.push(Number(getComputedStyle(block).opacity));
        for (const animation of document.getAnimations()) {
          const effect = animation.effect;
          if (!effect) continue;
          // The view transition's own half, by pseudo-element…
          const pseudo = effect.pseudoElement;
          if (pseudo && pseudo.includes('screen-body')) {
            // THE ANIMATION'S NAME, not merely that the pseudo-element
            // animates. Every view-transition pseudo-element gets the browser's
            // OWN cross-fade by default, so « something is animating here » is
            // true with the declared animation deleted — measured: the hold
            // below passed with `animation: body-rise …` removed outright.
            window.__owners.add(
              'transition:' + pseudo + ':' + (animation.animationName || '?'));
          }
          // …and the element-side half, by target.
          if (effect.target === block) {
            window.__owners.add(
              'element:' + (animation.transitionProperty
                            || animation.animationName || '?'));
          }
        }
      }, 16);
    }""")
    await page.click(TILE)
    await page.wait_for_timeout(1600)
    reading = await page.evaluate(
        "()=>{clearInterval(window.__watchBody);"
        " return {owners: [...window.__owners],"
        "         lowest: Math.min(...window.__bodyOpacity),"
        "         samples: window.__bodyOpacity.length};}")

    journal.check(
        "the media body's arrival IS drawn — the view transition lifts it",
        any("body-rise" in name for name in reading["owners"]),
        f"owners seen: {reading['owners']} — `body-rise` is the arrival's own "
        "drawing and this lot decided it with no rule. Read by NAME, because "
        "every view-transition pseudo-element gets the browser's own cross-fade "
        "by default: « something animates here » is true with the declared "
        "animation deleted, and was")
    journal.check(
        "and it has ONE owner — nothing animates the blocks BESIDE it",
        not any(name.startswith("element:") for name in reading["owners"]),
        f"owners seen: {reading['owners']} — a second entry runs on the blocks "
        "in the same frames the transition is lifting the snapshot that "
        "contains them: the content moves twice and fades twice")
    journal.check(
        "and the blocks never go transparent inside the arrival",
        reading["samples"] > 10 and reading["lowest"] >= 1.0,
        f"opacity fell to {reading['lowest']} over {reading['samples']} "
        "sample(s) — the snapshot already carries the blocks, so anything "
        "fading them is fading a picture of them")

    # THE OTHER HALF OF THE SAME DRAWING, and the one that keeps it alive: a
    # block arriving AFTER the transition — a slow read landing — must still
    # enter rather than snap in. Driven by inserting one, because the fixture
    # serves the whole sheet at once and no block ever arrives late in it.
    entered = await page.evaluate("""async ()=>{
      const body = document.querySelector('[data-region="screen-media/body"]');
      if (!body) return null;
      const block = document.createElement('div');
      block.textContent = '.';
      body.appendChild(block);
      const first = getComputedStyle(block).opacity;
      await new Promise((settle) => setTimeout(settle, 120));
      return {atInsertion: Number(first),
              afterwards: Number(getComputedStyle(block).opacity)};
    }""")
    journal.check(
        "a block that arrives LATER still enters rather than snapping in",
        bool(entered) and entered["atInsertion"] < 0.5
        and entered["afterwards"] > entered["atInsertion"],
        f"read {entered} — the entry above is scoped away from the page's own "
        "transition, and this is what it is scoped away FOR: with the rule "
        "removed rather than scoped, a read that lands after the arrival puts "
        "its blocks on screen in one frame")
    await context.close()


async def hold(journal):
    """Drives the page switch under both motion preferences."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_under(journal, browser, "no-preference")
        await hold_under(journal, browser, "reduce")
        await hold_one_entry_one_owner(journal, browser, warmed=False)
        await hold_one_entry_one_owner(journal, browser, warmed=True)
        await hold_the_priming(journal, browser)
        await hold_the_chrome_stays_in_front(journal, browser)
        await hold_the_panel_departs(journal, browser)
        await hold_a_hero_that_changes_picture(journal, browser)
        await hold_one_owner_on_the_body(journal, browser)
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R115 — the page switch is a declared transition")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
