"""R127 — the departing panel's snapshot does not come back, and its scrim does
not stay under the finger.

B-310 and B-338, two readings of one seam: a layer that outlives the crossing it
was supposed to leave on.

WHAT THE READER SEES (B-310). From a bottom panel, « Voir la fiche » opens the
media screen. The navigation captures the OPEN panel under the name
`leaving-panel` and plays `panel-down` on that snapshot. The panel slides down,
the screen stands clean — and then the panel is painted again, open, opaque, at
rest, for ONE frame, before the browser tears the transition down. Not a slide
and not a fade: a still image of the panel, back on top of a screen that had
already arrived.

WHAT MAKES THAT FRAME. `styles/base.css` declared the departure with the
`animation:` SHORTHAND, and a shorthand resets `animation-fill-mode` to `none`.
The user-agent stylesheet gives every `::view-transition-*` pseudo-element
`both` by inheritance; the shorthand throws it away. So when `panel-down` ends
the snapshot returns to its UN-ANIMATED state — which for an OLD snapshot is the
captured image, the panel open — and it is drawn there, above the root, until
the transition ends. The repair is the fill mode, written as a longhand beside
the shorthand.

WHAT THE FINGER FINDS (B-338). The scrim fades over the same step and its
`visibility` flips one step after that — B-249's idiom, which keeps a leaving
layer VISIBLE until it has finished leaving. But `visibility: visible` is also
HIT-TESTABLE: with the crossing over and the media screen fully in,
`elementFromPoint` at the screen's centre still answered `#scrim`, at opacity 0
and above the screen, for the length of that delay. A tap on the fresh screen in
that window closed layers that were already closed, so the tap was simply lost.
The repair keeps the fade — the layer must still be SEEN leaving — and removes
the target: a closed scrim takes no pointer events.

WHY THE SNAPSHOT AND NOT THE DOM. Two rounds of probes read the live tree across
this transition and described the 450 ms before the defect without ever meeting
it. The panel that comes back is not a node: it is the transition's own picture
of one, and its only reading is `getComputedStyle` on the pseudo-element itself.
This rule samples that, once per animation frame, for as long as
`:active-view-transition` holds and well past its end.

AND IT CANNOT SEE THE FLASH, the same way R103 cannot. A flash is a paint and no
assertion here can time one. What it reads is the fact the flash is made of: on
the transition's own last active frames, after `panel-down` has finished, the
snapshot is faded out and still displaced — or it is back at rest, which is the
defect, in the frame that draws it.

FRAMES ARE OBSERVED, NEVER ASSUMED (B-277). If the browser tears the transition
down in the same frame `panel-down` ends, there is no frame to read and the hold
says « not observed » rather than passing over nothing. Every fall prints the
frame it fell on with what it read there, because a rule that samples frames is
exposed to a loaded machine (B-307) and « FAIL » alone would not say which.

UNDER `reduce` THE ANSWER IS A DIFFERENT ONE, and it is drawn one step
earlier than the animation: the transition NAMES are declared under
`no-preference` only, so the panel is never captured, no snapshot exists, and
the frame B-310 is made of cannot occur there. That is held rather than assumed,
because the day a name moves out of that block the reduced path inherits every
animation this rule was written about. The scrim does not follow it — its
delayed `visibility` is an ordinary transition on the closed state, running
whatever the reader asked for — so the finger's half is read under both.

DRIVEN THROUGH THE DELEGATION, NEVER THROUGH THE SEAM — R103's lesson, paid for
in its own file. The panel is raised by a long press on a library tile and left
by a finger on the action carrying `data-mediasheet`; a direct call to the
panel's producer steps over the branch the reader actually walks.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

# Where the walk starts, and what it presses. The library's grid is the one
# surface where a long press raises a panel offering the media screen.
FROM_STATE = "lib-grid"
TILE = '[data-part="tile"]'
DEPARTING = "::view-transition-old(leaving-panel)"

# THE THREE SNAPSHOTS OF ONE SPECIES, each with the animation that OWNS it. All
# three are animated through the `animation:` shorthand, which resets the fill
# mode the user-agent stylesheet gives every `::view-transition-*`
# pseudo-element — so all three snap back to their un-animated state when their
# animation ends. Only the OLD one SHOWS it, because a NEW snapshot's
# un-animated state happens to be its final one, and that is exactly why the
# other two need a hold: a repair whose effect is invisible is a repair a later
# edit removes with nothing said.
#
# THE ANIMATION IS NAMED HERE BECAUSE THE FILL MODE ALONE CANNOT HOLD THEM.
# `both` is what an authored rule declares AND what the user agent gives a
# pseudo-element no author rule matches at all — so a hold reading only
# `animation-fill-mode` passes identically whether the arrival is drawn as
# designed or not drawn by this stylesheet at all. Measured: moving the whole
# `::view-transition-new(screen-banner)` rule to a misspelt pseudo name leaves
# the fill reading `both` on every frame while `banner-in` never runs and the
# browser's own cross-fade plays in its place. So each snapshot is held by BOTH
# facts — its own animation running on its own pseudo, and the fill mode kept —
# and the pair is what makes the reading mean the arrival this file is about.
SNAPSHOTS = {
    "leaving-panel": {"pseudo": DEPARTING, "animation": "panel-down"},
    "screen-banner": {"pseudo": "::view-transition-new(screen-banner)",
                      "animation": "banner-in"},
    "screen-body": {"pseudo": "::view-transition-new(screen-body)",
                    "animation": "body-rise"},
}
FILLED = {name: snapshot["pseudo"] for name, snapshot in SNAPSHOTS.items()}

# HOW LONG THE WALK SAMPLES. The crossing itself is one motion step and the
# scrim's delayed flip is a second one after it, so a window of two steps plus
# the margin below covers both with room for a frame that arrives late on a
# loaded machine. Bounded by TIME and not by a frame count: a machine under load
# draws fewer frames, and a count would then stop the walk before the end it is
# written to read.
WALK_MILLISECONDS = 1600

# The opacity a faded-out snapshot is allowed to read. The last keyframe is
# zero; the tolerance is for the arithmetic and could not hide the defect, which
# reads a full one.
FADED = 0.01

# One reading per animation frame: the snapshot's own computed style, whichever
# animation is running on it, and what a finger would find at the screen's
# centre.
SAMPLE = """([span, departing, filled])=>new Promise((done)=>{
  const started = performance.now();
  const frames = [];
  const asNumber = (value) => (value && typeof value === 'object'
    && 'value' in value) ? value.value : Number(value);
  // The point a finger would land on. The arrived screen's own centre while it
  // is there, the viewport's before it is — the two are the same point on this
  // surface, and reading the screen's box says WHOSE centre was measured.
  const centre = () => {
    const screen = document.querySelector('[data-part="screen"][data-open]');
    const box = screen ? screen.getBoundingClientRect() : null;
    if (box && box.width > 0 && box.height > 0) {
      return {x: box.left + box.width / 2, y: box.top + box.height / 2};
    }
    return {x: window.innerWidth / 2, y: window.innerHeight / 2};
  };
  const read = () => {
    const root = document.documentElement;
    const snapshot = getComputedStyle(root, departing);
    let panelDown = null;
    for (const animation of document.getAnimations()) {
      const pseudo = animation.effect && animation.effect.pseudoElement;
      if (pseudo !== departing) continue;
      if (animation.animationName !== 'panel-down') continue;
      const timing = animation.effect.getComputedTiming();
      panelDown = {
        currentTime: Math.round(asNumber(animation.currentTime) || 0),
        duration: typeof timing.duration === 'number'
          ? Math.round(timing.duration) : null,
        playState: animation.playState,
      };
    }
    const point = centre();
    const under = document.elementFromPoint(point.x, point.y);
    // THE FILL MODE OF EVERY SNAPSHOT OF THE SPECIES, read from the
    // pseudo-element itself rather than from the stylesheet's text: what a rule
    // must hold is the value the browser resolved, and a shorthand written
    // after a longhand resolves to `none` however the source reads.
    const fill = {};
    for (const [name, pseudo] of Object.entries(filled)) {
      fill[name] = getComputedStyle(root, pseudo).animationFillMode;
    }
    frames.push({
      at: Math.round(performance.now() - started),
      active: root.matches(':active-view-transition'),
      opacity: Number(snapshot.opacity),
      transform: snapshot.transform,
      fill,
      // THE DRAWING ITSELF, so that changing it is a rule going red rather than
      // a silent amendment. Read as the browser resolved it, beside the scale's
      // own tokens below — never against a number typed here, which outlives
      // the duration it was set against without saying so (B-276).
      duration: snapshot.animationDuration,
      easing: snapshot.animationTimingFunction,
      panelDown,
      // EVERY view-transition animation running this frame, named. Without it a
      // walk that measured the wrong transition would look like a walk that
      // measured nothing, and the two are answered differently.
      running: document.getAnimations()
        .map((animation) => {
          const pseudo = animation.effect && animation.effect.pseudoElement;
          return pseudo && pseudo.includes('view-transition')
            ? pseudo + ':' + (animation.animationName || '?') : null;
        })
        .filter((name) => name !== null),
      screens: document.querySelectorAll('[data-part="screen"][data-open]').length,
      under: under
        ? (under.id ? '#' + under.id : under.tagName.toLowerCase()) : null,
      onScrim: !!(under && under.closest('#scrim')),
    });
    if (performance.now() - started >= span) return done(frames);
    requestAnimationFrame(read);
  };
  requestAnimationFrame(read);
})"""

# WHAT THE DEPARTURE IS DRAWN WITH, asked of the document. The pair is a drawing
# the operator validated, and the brief that ordered this rule forbids amending
# it — so the hold compares the animation against the SCALE rather than against
# a constant, and a step that moves moves both ends at once.
#
# THROUGH THE BROWSER'S OWN SERIALISER, ON BOTH SIDES, and the first version of
# this was not: it read the tokens as AUTHORED and compared them with a computed
# style. `--duration-4` is written `.45s` and computes to `0.45s`; the curve is
# written with bare `.22` and computes with `0.22`. The values were identical
# and the hold fell on the leading zeros — a rule refusing a change nobody made,
# which is worse than one that misses a change somebody did: it teaches its
# reader to disbelieve it. So the tokens are resolved on a probe element and
# read back the same way the snapshot is read, and what is compared is what the
# engine resolved on both ends rather than two spellings of one number.
SCALE = """()=>{
  const probe = document.createElement('div');
  probe.style.animationName = 'none';
  probe.style.animationDuration = 'var(--duration-4)';
  probe.style.animationTimingFunction = 'var(--ease-standard)';
  document.documentElement.appendChild(probe);
  const resolved = getComputedStyle(probe);
  const scale = {duration: resolved.animationDuration,
                 easing: resolved.animationTimingFunction};
  probe.remove();
  return scale;
}"""


def finished(frame):
    """Whether `panel-down` has run its course on this frame.

    The animation leaves `getAnimations()` when it stops being relevant, which
    is exactly what a fill mode of `none` makes it the moment it ends — so an
    ABSENCE is one of the two shapes an ended animation takes here, and the
    other is a finished animation the fill keeps alive. Both are read, because
    the repair moves the reading from the first to the second and a rule that
    knew only one of them would flip from vacuous to false with it.

    Args:
        frame: One sampled frame.

    Returns:
        True when no `panel-down` is still running on the departing snapshot.
    """
    running = frame["panelDown"]
    if running is None:
        return True
    if running["playState"] == "finished":
        return True
    duration = running["duration"]
    return duration is not None and running["currentTime"] >= duration


def after_the_departure(frames):
    """The active frames that follow the end of `panel-down`.

    A frame is only counted once `panel-down` has been SEEN running: the first
    frames of a crossing are active with no animation on the snapshot yet, and
    reading those as « ended » would refuse the un-animated state the fill mode
    is there to replace — a fall on the repair rather than on the defect.

    Args:
        frames: The sampled frames, in order.

    Returns:
        The frames that are active, after `panel-down` ran, with it over.
    """
    seen = False
    after = []
    for frame in frames:
        if frame["panelDown"] is not None and not finished(frame):
            seen = True
            continue
        if seen and frame["active"] and finished(frame):
            after.append(frame)
    return after


def after_the_crossing(frames):
    """The frames sampled once the view transition is over.

    Args:
        frames: The sampled frames, in order.

    Returns:
        The frames following the last active one, empty if none was seen.
    """
    active = [at for at, frame in enumerate(frames) if frame["active"]]
    if not active:
        return []
    return frames[active[-1] + 1:]


def reading(frame):
    """One frame, printed the way a fall has to be read.

    Args:
        frame: One sampled frame.

    Returns:
        A one-line account of what was measured on that frame.
    """
    return (f"{frame['at']}ms opacity={frame['opacity']} "
            f"transform={frame['transform']} under={frame['under']} "
            f"panel-down={frame['panelDown']}")


async def raise_the_panel(page, journal, motion):
    """Presses a library tile until its panel is up, and reads what it is.

    Args:
        page: The Playwright page.
        journal: The rule's journal.
        motion: The motion preference this walk runs under, named in the holds
            because the panel is a DIFFERENT thing under each: named and
            captured under one, an ordinary layer under the other.

    Returns:
        The reading of the raised panel — its open state, the transition name it
        carries, and whether it offers the media screen — or None when the grid
        has no tile to press.
    """
    await page.evaluate("(state)=>window.__go(state)", FROM_STATE)
    await page.wait_for_timeout(600)
    box = await page.evaluate(
        "(selector)=>{const node = document.querySelector(selector);"
        " if (!node) return null;"
        " const rectangle = node.getBoundingClientRect();"
        " return {x: rectangle.x + rectangle.width / 2,"
        "         y: rectangle.y + rectangle.height / 2};}", TILE)
    if box is None:
        journal.check(f"under `{motion}`, the library grid offers a tile to "
                      "press, so this walk has a panel to raise",
                      False, 'no `[data-part="tile"]` on the grid')
        return None
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
    await page.wait_for_timeout(700)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(600)

    raised = await page.evaluate("""()=>{
      const sheet = document.querySelector('#sheet');
      if (!sheet) return {open: false, name: null, leaves: false};
      return {open: sheet.hasAttribute('data-open'),
              name: getComputedStyle(sheet).viewTransitionName,
              leaves: !!sheet.querySelector('[data-mediasheet]')};}""")
    journal.check(
        f"under `{motion}`, a long press raises the panel and the panel offers "
        "the way onto the media screen, so this walk drives the delegation and "
        "not the seam",
        raised["open"] and raised["leaves"],
        f"read {raised}")
    return raised


async def walk(page, journal, motion):
    """Leaves the panel for the media screen and samples every frame of it.

    Args:
        page: The Playwright page.
        journal: The rule's journal.
        motion: The motion preference this walk runs under.

    Returns:
        The (reading of the raised panel, sampled frames) pair. The frames are
        empty when there was no panel to leave.
    """
    raised = await raise_the_panel(page, journal, motion)
    if not raised or not (raised["open"] and raised["leaves"]):
        return raised, []
    sampling = asyncio.create_task(
        page.evaluate(SAMPLE, [WALK_MILLISECONDS, DEPARTING, FILLED]))
    await asyncio.sleep(0.02)
    # A REAL TOUCH, because this rule's own sentence says « a finger ». A
    # `.click()` reaches the handler and reaches nothing else: the press
    # arbitration that decides whether a gesture is a tap at all never runs, so
    # an instrument driving one is measuring a path no reader walks. The
    # conclusion is the same on this surface, measured — which is the argument
    # for fixing it rather than against, since an instrument that happens to be
    # right is not an instrument that reads what it claims.
    box = await page.evaluate(
        """()=>{const node = document.querySelector('#sheet [data-mediasheet]');
                 const rectangle = node.getBoundingClientRect();
                 return {x: rectangle.x + rectangle.width / 2,
                         y: rectangle.y + rectangle.height / 2};}""")
    await page.touchscreen.tap(box["x"], box["y"])
    return raised, await sampling


def hold_the_scrim_lets_go(journal, frames, motion):
    """Holds what a finger finds on the fresh screen once the crossing is over.

    Read under BOTH preferences, and not as a courtesy: the scrim's delayed
    `visibility` is a transition of its own, declared on the closed state with
    no motion preference attached, so it runs whatever the reader asked for. A
    walk under one preference would have left the other half unmeasured.

    Args:
        journal: The rule's journal.
        frames: The sampled frames, in order.
        motion: The motion preference this walk ran under.
    """
    settled = after_the_crossing(frames)
    journal.check(
        f"under `{motion}`, the transition ENDS inside the window this walk "
        "samples, so what follows it can be read",
        bool(settled),
        f"{len(settled)} frame(s) after the last active one")
    caught = [frame for frame in settled if frame["onScrim"]]
    journal.check(
        f"under `{motion}`, the element under the media screen's centre is "
        "never the scrim once the crossing is over — a tap there reaches the "
        "screen (B-338)",
        not caught,
        (f"{len(caught)} of {len(settled)} frame(s) answered the scrim, "
         f"{caught[0]['at']}ms to {caught[-1]['at']}ms after the tap — first: "
         f"{reading(caught[0])}" if caught
         else f"{len(settled)} frame(s), and what they found: "
              f"{sorted({frame['under'] for frame in settled})}"))


async def hold_the_departure_is_complete(journal, browser, errors):
    """Reads the departing snapshot on the transition's own last frames.

    TWO KINDS OF HOLD LIVE HERE, and the difference is the point rather than an
    accident of grouping.

    The panel's own snapshot is held by its APPEARANCE: what it draws on the
    frames where the transition is still active and `panel-down` is over. That
    is the defect a reader sees, and it is readable because an OLD snapshot's
    un-animated state is the image as it was captured — a picture of something.

    The two arriving snapshots are held by their DECLARATION: the
    `animation-fill-mode` the browser resolved on each pseudo-element. They
    carry the identical defect and it draws NOTHING, because a NEW snapshot's
    un-animated state happens to be its final one — so no reading of the picture
    can find it, on any frame, under any preference. A hold that waited for an
    appearance there would be a hold that can never fail, and a repair whose
    effect is invisible is a repair the next edit removes in silence. Saying
    which of the two a hold does is what keeps the second from being read as a
    weaker version of the first.

    AND EACH IS HELD BY ITS ANIMATION'S NAME TOO, WHICH HAS A COST WORTH
    STATING. A rename carried through consistently — the keyframes and the rule
    moved together, the arrival drawn pixel for pixel as before — falls these
    holds. That is intended, and it is the price of the only reading that can
    tell « this arrival is drawn » from « the browser is cross-fading because no
    rule matches this pseudo-element at all »: the fill mode reads `both` in
    both cases, so the NAME is the only fact separating them. A rename is then
    one deliberate line here, beside the rename that caused it.

    Args:
        journal: The rule's journal.
        browser: A launched Playwright browser.
        errors: The collector this walk's page errors are appended to.
    """
    context, page = await open_page(browser)
    page.on("pageerror", lambda error: errors.append(str(error)))
    raised, frames = await walk(page, journal, "no-preference")
    if not frames:
        await context.close()
        return
    journal.check(
        "the open panel is NAMED, so the stylesheet has something to capture "
        "and something to animate",
        raised["name"] == "leaving-panel",
        f"view-transition-name is {raised['name']!r}")
    crossing = [frame for frame in frames if frame["active"]]
    journal.check(
        "the walk really crosses a view transition, so every hold below has "
        "something to read",
        len(crossing) > 3,
        f"{len(crossing)} active frame(s) of {len(frames)} sampled")
    journal.check(
        "and the media screen really arrives inside the window it samples",
        any(frame["screens"] > 0 for frame in frames),
        "the screen is open from frame "
        f"{next((at for at, frame in enumerate(frames) if frame['screens']), None)}")
    departing = [frame for frame in frames if frame["panelDown"] is not None]
    journal.check(
        "`panel-down` really plays on the departing snapshot — without it the "
        "panel is not drawn leaving at all, and the frame below would be the "
        "whole departure rather than its end",
        len(departing) > 3,
        f"{len(departing)} frame(s) carrying it, of the view-transition "
        "animations "
        f"{sorted({name for frame in frames for name in frame['running']})}")

    after = after_the_departure(frames)
    # B-277's honesty about frame sampling: a window that never crossed the
    # frame in question proves nothing, and « nothing » is not a pass.
    journal.check(
        "the walk crosses at least one frame in which the transition is still "
        "active and `panel-down` is over — the frame B-310 is made of",
        bool(after),
        f"{len(after)} such frame(s)" if after
        else "none observed — the browser tore the transition down in the same "
             "frame `panel-down` ended, so this walk read no state to hold; it "
             "did not read a good one")
    wrong = [frame for frame in after
             if frame["opacity"] > FADED or frame["transform"] == "none"]
    journal.check(
        "and on every one of them the panel's snapshot is FADED OUT and still "
        "displaced — it does not snap back to the panel as it was captured "
        "(B-310)",
        bool(after) and not wrong,
        (f"{len(wrong)} of {len(after)} frame(s) read the snapshot back at "
         f"rest — first: {reading(wrong[0])}" if wrong
         else f"{len(after)} frame(s), last: {reading(after[-1])}"
              if after else "no frame to read"))

    # ── THE OTHER TWO THIRDS OF THE REPAIR, held (the fill mode) ──────────
    #
    # WITHOUT THIS, TWO OF THE THREE DECLARATIONS ARE HELD BY NOTHING. The two
    # NEW snapshots snap back exactly as the old one does; their un-animated
    # state simply happens to be their final one, so the defect draws nothing
    # and no reading of the picture can find it. A repair whose effect is
    # invisible is a repair the next edit removes in silence — so what is held
    # is the DECLARATION, resolved by the browser, on the frames where the
    # pseudo-elements exist at all.
    for name, snapshot in SNAPSHOTS.items():
        owner = f"{snapshot['pseudo']}:{snapshot['animation']}"
        drawn = [frame for frame in crossing if owner in frame["running"]]
        read = sorted({frame["fill"][name] for frame in crossing})
        journal.check(
            f"`{name}` is drawn by `{snapshot['animation']}` and its snapshot "
            "keeps the fill mode the `animation:` shorthand resets — the pair, "
            "because `both` is also what an UNMATCHED pseudo-element reads "
            "(B-310)",
            bool(drawn) and bool(read)
            and all(value in ("both", "forwards") for value in read),
            f"`{snapshot['animation']}` runs on {snapshot['pseudo']} over "
            f"{len(drawn)} of {len(crossing)} active frame(s) and "
            f"animation-fill-mode reads {read} — zero frames means no animation "
            "of THAT NAME on THAT pseudo, which is either the arrival no longer "
            "drawn by this stylesheet or the same arrival drawn under a name "
            "this rule was not told about; what IS running on the pseudo, above, "
            "tells the two apart. `none` is the shorthand having thrown the fill "
            "mode away")

    # ── THE DRAWING IS NOT AMENDED, and that is a rule rather than a promise ──
    #
    # The 450 ms and the standard curve are a drawing the operator validated,
    # and completing the departure was not licence to retune it. Compared
    # against the SCALE's own values, asked of the document: a number typed here
    # would outlive the duration it was set against without saying so (B-276).
    #
    # WHAT THIS IS INVARIANT UNDER, said plainly because the obvious mutation
    # tries it and reports « no rule fell », which reads as a vacuity and is
    # not one. Moving `--duration-4` itself moves BOTH ends of the comparison,
    # so this hold says nothing about it — deliberately: the scale is a decision
    # of its own, with its own guard, and a step that moves moves every surface
    # spending it at once. What this refuses is THIS departure being spent
    # differently from the rest of the scale — `panel-down` given a DIFFERENT
    # token — which is the amendment the brief forbids. The mutation that
    # exercises it is a changed token IN THIS RULE, never a changed token in the
    # scale.
    #
    # A LITERAL OF THE SAME VALUE PASSES HERE, and that is not a gap: `0.45s`
    # written out computes to what the token computes to, so no reading of the
    # animation can tell them apart. What refuses a literal is
    # `check-css-tokens.py`, which reads the SOURCE and holds that every
    # duration in the maquette is a step of the scale. Two guards, two
    # questions — « is it the same step? » here, « is it written as a step? »
    # there — and neither can be asked from the other's position.
    scale = await page.evaluate(SCALE)
    drawn = sorted({(frame["duration"], frame["easing"]) for frame in crossing})
    journal.check(
        "and `panel-down` spends the step and curve the document declares as "
        "`--duration-4` and `--ease-standard` — the departure is not given a "
        "pace of its own",
        len(drawn) == 1 and drawn[0][0] == scale["duration"]
        and drawn[0][1] == scale["easing"],
        f"the snapshot animates {drawn} against the scale's "
        f"({scale['duration']!r}, {scale['easing']!r})")

    hold_the_scrim_lets_go(journal, frames, "no-preference")
    await context.close()


async def hold_the_reduced_path_is_drawn(journal, browser, errors):
    """States what the departure IS for a reader who asked for no motion.

    Invariant 14: the reduced state is drawn, not defaulted to. Here it is drawn
    one step earlier than the animation — the NAMES are declared under
    `no-preference` only, so under `reduce` the panel is never captured, no
    snapshot exists, and the frame B-310 is made of cannot occur. That is a
    reading of the stylesheet's own decision, held rather than assumed, because
    the day a name moves out of that block the reduced path acquires every
    animation this rule was written about.

    The scrim is the other half, and it does NOT follow: its delayed visibility
    is an ordinary transition on the closed state, so it runs here too and is
    held here too.
    """
    context, page = await open_page(browser, reduced_motion="reduce")
    page.on("pageerror", lambda error: errors.append(str(error)))
    raised, frames = await walk(page, journal, "reduce")
    if not frames:
        await context.close()
        return
    journal.check(
        "under `reduce`, the panel is NOT named, so nothing captures it and no "
        "snapshot can come back when an animation ends (invariant 14)",
        raised["name"] == "none",
        f"view-transition-name is {raised['name']!r}")
    journal.check(
        "under `reduce`, the navigation still HAPPENS — a transition that is "
        "silenced must not be a transition that is cancelled",
        any(frame["screens"] > 0 for frame in frames),
        f"{sum(1 for frame in frames if frame['screens'] > 0)} frame(s) with "
        "the screen open")
    animated = sorted({name for frame in frames for name in frame["running"]})
    journal.check(
        "and NO view-transition animation runs there at all, the group's own "
        "included",
        not animated,
        f"animations seen: {animated or 'none'}")
    hold_the_scrim_lets_go(journal, frames, "reduce")
    crossing = [frame for frame in frames if frame["active"]]
    print(f"  note under `reduce` the crossing lasted {len(crossing)} frame(s) "
          f"of the {len(frames)} sampled, and the departing snapshot read "
          f"{sorted({frame['opacity'] for frame in crossing}) or 'nothing'} for "
          "opacity throughout — with no name on the panel that reading is the "
          "pseudo-element's default and not a picture of anything.")
    await context.close()


async def main():
    journal = Journal(
        "R127 — the departing panel does not come back, and its scrim does not "
        "stay under the finger (B-310, B-338)")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        errors: list[str] = []
        await hold_the_departure_is_complete(journal, browser, errors)
        await hold_the_reduced_path_is_drawn(journal, browser, errors)
        await browser.close()
    journal.summary(errors)


asyncio.run(main())
