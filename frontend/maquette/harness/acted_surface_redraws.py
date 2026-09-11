"""R157 — the surface a verb was pressed ON re-reads, not only the one behind it.

THE DEFECT THIS HOLDS, and it is one shape wearing two faces. A panel producer
is a function from the cache to a descriptor and NOT a component: nothing
subscribes to the key it read while the panel is open. So a verb pressed inside
a panel moved the layer, the list BEHIND the panel updated — that one is
observed — and the sheet the operator was actually looking at went on saying
what it said before his act. « Remettre en file » left the stage strip
byte-identical; « Récupérer cette saison » left the season reading « 6/7 · 1
manquant » with no queued mark, while the row behind it had already moved on.

A verb that reports success on a surface that tells the operator nothing
happened is the exact thing this lot exists to end.

HOW IT IS READ, and the discriminator is the point. « Did the text change? » is
a weak hold: a rendering can move for reasons that have nothing to do with the
act, and a rendering that happens not to move is not proof of anything either.
What is held instead is that THE OPEN SURFACE AGREES WITH THE CACHE — the panel
on screen says the same thing a panel produced fresh from the cache says. That
is the operator's own test, and it is what he did to find this: he closed the
sheet and opened it again, and the second one said something different.

Both halves also hold that the surface MOVED across the act, so a build where
the verb does nothing at all cannot pass by agreeing with a cache that never
changed.

⚠ A STRIP WHOSE STATE LIVES IN A DOT IS INVISIBLE TO TEXT, and the next person
to write this probe will write it the same way. A stage says « Scrapé » before
the act and « Scrapé » after it; what moves is the tone of the dot beside it.
The first version of this rule read `textContent` alone and reported the strip
unchanged on a build where it had changed — a rule agreeing with the defect it
was written to catch. The dots are read too, selected by their `data-part` and
their tone taken as a VALUE.

AND THE THIRD HOLD IS THE DOUBLE PRESS. Two presses with no settle between them
sent two identical requests and produced one message: the interface asked twice
and said so once. It is held on what the LAYER answered, never on the screen.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE QUEUE IS DRAWN, so a journey has stages to move.
JOURNEY_STATE = "acq-now-loaded"

# WHERE THE FOLLOWS ARE DRAWN, so a season with a hole can be asked for.
FOLLOWS_STATE = "acq-follows-list"

# WHAT THE LAYER ANSWERED, by operation. The screen is never the witness for a
# call: a build that draws the right thing and sends nothing passes a
# screen-reading hold, which this suite has already paid for once.
ANSWERED = """(name)=>(window.__mocks?.answered?.() || [])
  .filter((call) => call.operationId === name).length"""

# THE OPEN PANEL, AS TEXT, AS TONES AND AS MARKS. Whitespace is collapsed
# because a reflow that rewraps a line is not a change the operator can see.
#
# THE TONES ARE READ BECAUSE THE TEXT DOES NOT MOVE. A stage says « Scrapé »
# before the act and « Scrapé » after it; what changes is the dot beside it,
# and the first version of this rule read `textContent` alone and reported the
# strip unchanged on a build where it had changed. The dots are selected by
# their `data-part` and their tone is read as a VALUE — selecting on the style
# class itself is what the markup guard refuses, and for the same reason: the
# class can be renamed and the anchor would die silently.
ON_SCREEN = """()=>{
  const sheet = document.querySelector('#sheetin');
  if (!sheet) return null;
  return {text: (sheet.textContent || '').replace(/\\s+/g, ' ').trim(),
          dots: [...sheet.querySelectorAll('[data-part="status-dot"]')]
                .map((one) => String(one.className)),
          queued: sheet.querySelectorAll('[data-part="season/queued"]').length};}"""

# EVERY SUBJECT THE QUEUE CARRIES, read from the queue rather than named here:
# a title written into a rule goes stale the day the fixture moves.
QUEUE_SUBJECTS = """()=>{const now = window.__queue?.() || {};
  return [...(now.inFlight || []), ...(now.blocked || []), ...(now.takeable || [])]
    .map((one) => one.t);}"""

# THE STAGES THE LAYER HOLDS for one journey, as the cache has them.
STAGES_HELD = """(title)=>{
  const held = window.__queries.getQueryData(
    ["/api/acquisition/journeys", title]);
  return Array.isArray(held) ? held.map((one) => one.state) : null;}"""

# WHICH SUBJECT CAN MOVE AT ALL. `restart` sets every stage from the first
# unfinished one onward to « upcoming », so a journey already waiting is
# unchanged by a requeue and the strip is RIGHT not to move. Holding « it
# moved » on such a subject would measure the fixture, not the interface — the
# first version of this rule did exactly that and failed on a journey with
# nothing running.
RUNNING_STAGE = "now"

# A FOLLOW WITH A SEASON THAT HAS A HOLE — the only subject the grab applies to.
A_HOLE = """()=>{
  const grab = document.querySelector('[data-grab-season]');
  return grab ? grab.dataset.grabSeason : "";}"""

PRESS_JOURNEY_VERB = """()=>{
  const act = [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
              .find((one) => 'journeyRequeue' in one.dataset);
  if (!act) return {found: false};
  act.click();
  return {found: true, pressed: true};}"""


# WHERE A READER IS IN THE OPEN PANEL, and what a finger at the last season
# act's centre would meet. The LAST act, because it is the one a reader has to
# scroll to — the first one of a long panel is often in view at the top, where
# no place can be lost.
PLACE = """()=>{
  const port = document.querySelector('#sheetin');
  const acts = port
    ? [...port.querySelectorAll('[data-part="season/grab"]')] : [];
  const act = acts[acts.length - 1];
  if (!port || !act) return null;
  const portBox = port.getBoundingClientRect();
  const box = act.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {scrollTop: port.scrollTop,
          room: port.scrollHeight - port.clientHeight,
          offset: box.top - portBox.top + port.scrollTop,
          portHeight: port.clientHeight,
          left: portBox.left, top: portBox.top,
          inView: box.top >= portBox.top && box.bottom <= portBox.bottom,
          x, y, reached: !!hit && (hit === act || act.contains(hit)),
          meets: String(hit && (hit.textContent || '').trim().slice(0, 40)
                        || '')};}"""

# THE LEAST A PANEL MUST SCROLL to have a place worth keeping, in pixels.
SCROLL_ROOM = 80

# WHAT A DRAG TRAVELS BEFORE THE BROWSER CALLS IT A SCROLL, in pixels.
TOUCH_SLOP = 16


async def scroll_by_finger(page, start, distance):
    """Scrolls the panel with a real touch stream, the way a reader moves it.

    Never `scrollTop =`: a written offset is not what a finger does, and the
    defect this holds was measured after a finger's scroll. The finger is held
    still before it lifts, so no fling carries the offset on past the reading.

    Args:
        page: The page under test.
        start: Where the finger lands, as an (x, y) pair.
        distance: How far the content travels upward, in pixels.
    """
    session = await page.context.new_cdp_session(page)
    x, y = start
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    steps = 12
    for step in range(1, steps + 1):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y - distance * step / steps, "id": 1}]})
        await page.wait_for_timeout(24)
    await page.wait_for_timeout(160)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await session.detach()


async def hold_the_place(page, journal):
    """Holds that the redraw a verb causes keeps the reader's place in the panel.

    THE DEFECT, measured by a finger: Silo's follow panel scrolled 171 px, the
    season act pressed, and 100 ms later the panel was back at 0 with the act
    171 px lower; on a panel longer than the screen the act left the view
    entirely (698 → 0, the button from y 764 to y 1462). The redraw is the
    same panel produced again, and a panel produced again is not a panel
    opened: the reset belongs to an open.

    The press is a FINGER at the act's centre, after a hit test says nothing
    covers that point — never `element.click()`, which presses a button a
    finger could not reach and would measure a place nobody was standing at.

    Args:
        page: The page under test.
        journal: Where the holds are recorded.
    """
    await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
    await page.wait_for_timeout(SETTLED)
    followed = await page.evaluate(
        """()=>(window.__followActions?.all?.() || []).map((one) => one.t)""")
    subject = ""
    place = None
    for title in followed:
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
        await page.wait_for_timeout(PANEL_IN)
        place = await page.evaluate(PLACE)
        if place and place["room"] >= SCROLL_ROOM:
            subject = title
            break
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(PANEL_IN)
    journal.check(
        "a followed medium's panel offers a season act and is taller than the "
        "sheet — the only kind of panel whose place a redraw can lose",
        bool(subject),
        subject or f"none of {len(followed)} follow panels scrolls "
                   f"{SCROLL_ROOM} px and offers an act")
    if not subject:
        return

    # SCROLLED SO THE ACT STAYS IN VIEW, near the middle of the port: the offset
    # must be non-zero for the hold to mean anything, and the act must still be
    # under a finger once it is.
    # The browser's touch slop swallows the first pixels of a drag before it
    # becomes a scroll, so the finger travels that much further than the offset
    # it is meant to leave.
    wanted = min(place["room"],
                 max(SCROLL_ROOM / 2, place["offset"] - place["portHeight"] / 2))
    await scroll_by_finger(
        page,
        (place["left"] + 14, place["top"] + place["portHeight"] * 0.8),
        wanted - place["scrollTop"] + TOUCH_SLOP)
    await page.wait_for_timeout(PANEL_IN)
    scrolled = await page.evaluate(PLACE)
    journal.check(
        f"a real touch stream scrolled {subject!r}'s panel, and its last season "
        "act is in view with nothing covering its centre",
        scrolled is not None and scrolled["scrollTop"] > 0
        and scrolled["inView"] and scrolled["reached"],
        str({key: (scrolled or {}).get(key)
             for key in ("scrollTop", "inView", "reached", "meets")}))
    if not (scrolled and scrolled["scrollTop"] > 0 and scrolled["reached"]):
        return

    before = await page.evaluate(ON_SCREEN)
    asked_before = await page.evaluate(ANSWERED, "grabSeasonForFollow")
    await page.touchscreen.tap(scrolled["x"], scrolled["y"])
    await page.wait_for_timeout(ACTED)
    asked = await page.evaluate(ANSWERED, "grabSeasonForFollow")
    journal.check(
        "a finger's tap at the act's centre was taken — one ask",
        asked - asked_before == 1, f"{asked - asked_before} ask(s)")

    after = await page.evaluate(ON_SCREEN)
    journal.check(
        "the panel was redrawn by the act — without it the place below would "
        "be kept by a panel that never moved",
        before is not None and after is not None
        and (before["text"] != after["text"]
             or before["queued"] != after["queued"]),
        f"texts {'differ' if before and after and before['text'] != after['text'] else 'AGREE'}")

    kept = await page.evaluate(PLACE)
    journal.check(
        "the redraw KEPT THE READER'S PLACE — the panel's scroll offset is "
        "where the finger left it, not thrown back to the top with the act "
        "out from under the finger",
        kept is not None and abs(kept["scrollTop"] - scrolled["scrollTop"]) <= 1,
        f"scrollTop {scrolled['scrollTop']} → {(kept or {}).get('scrollTop')}")
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(PANEL_IN)


# HOW LONG THE LAYER HOLDS THE SEASON'S ANSWER BACK, as any real backend does.
# The fixture answers in about fifteen milliseconds, so no rule and no hand met
# the wait this leg is about until the answer was held on purpose.
HELD_BACK_MS = 2500

# ONE SEASON ACT, BY THE SEASON IT ASKS FOR: whether it is drawn as taken, its
# text, and what a finger at its centre would meet.
TAKEN = """(asked)=>{
  const act = [...document.querySelectorAll('#sheetin [data-grab-season]')]
    .find((one) => one.dataset.grabSeason === asked);
  if (!act) return {found: false};
  const box = act.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, busy: act.getAttribute('aria-busy'), x, y,
          reached: !!hit && (hit === act || act.contains(hit)),
          text: (act.textContent || '').trim(),
          taken: document.querySelectorAll(
            '#sheetin [data-grab-season][aria-busy="true"]').length};}"""


async def hold_the_taken_act(page, journal):
    """Holds that a season act whose ask is in flight is drawn as TAKEN.

    THE DEFECT, measured with the answer held back 2.5 s: the pressed act read
    `aria-busy` null, the same text, full opacity, for the whole wait, and three
    further presses did nothing visible. The guard was right — one ask — and the
    operator saw a button that had taken nothing. NE-DOIT-PAS-3 refuses
    « occupé »; it does not refuse a pending state.

    Read on `aria-busy`, the attribute the drawing keys its look on: true after
    the press while the answer is held, the text unchanged, and no act drawn as
    taken once it is answered — so a build that sets the state and never clears
    it falls too. The second press during the wait is a finger's, and it asks
    nothing.

    Args:
        page: The page under test.
        journal: Where the holds are recorded.
    """
    await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
    await page.wait_for_timeout(SETTLED)
    followed = await page.evaluate(
        """()=>(window.__followActions?.all?.() || []).map((one) => one.t)""")
    asked = ""
    for title in followed:
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
        await page.wait_for_timeout(PANEL_IN)
        asked = await page.evaluate(A_HOLE)
        if asked:
            break
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(PANEL_IN)
    journal.check("a follow panel offers a season act whose answer can be held back",
                  bool(asked), asked or f"none of {len(followed)} follows offers one")
    if not asked:
        return

    await page.evaluate(
        """(milliseconds)=>window.__mocks.setOperationOutcome(
             'grabSeasonForFollow', {latencyMilliseconds: milliseconds})""",
        HELD_BACK_MS)
    before = await page.evaluate(TAKEN, asked)
    journal.check(
        "before the press, the act is under a finger and not drawn as taken",
        before.get("found") and before.get("reached") and before.get("busy") != "true",
        str(before))
    if not (before.get("found") and before.get("reached")):
        return

    asked_before = await page.evaluate(ANSWERED, "grabSeasonForFollow")
    await page.touchscreen.tap(before["x"], before["y"])
    await page.wait_for_timeout(PANEL_IN)
    during = await page.evaluate(TAKEN, asked)
    journal.check(
        "WHILE ITS ASK IS IN FLIGHT the pressed act is drawn as TAKEN — "
        "aria-busy true, its text unchanged — where it used to show nothing",
        during.get("busy") == "true" and during.get("text") == before.get("text"),
        f"aria-busy {during.get('busy')!r}, text {during.get('text')!r}")

    await page.touchscreen.tap(before["x"], before["y"])
    await page.wait_for_timeout(HELD_BACK_MS + ACTED)
    asked_after = await page.evaluate(ANSWERED, "grabSeasonForFollow")
    journal.check(
        "a second finger press during the wait asked nothing — one ask",
        asked_after - asked_before == 1, f"{asked_after - asked_before} ask(s)")
    after = await page.evaluate(TAKEN, asked)
    journal.check(
        "once answered, no season act is drawn as taken",
        after.get("taken", 0) == 0, str(after))

    await page.evaluate(
        """()=>window.__mocks.setOperationOutcome(
             'grabSeasonForFollow', {latencyMilliseconds: 0})""")
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(PANEL_IN)


# EVERY SENTENCE A SEASON ASK CAN SPEAK, read from the resource the interface
# reads — a retyped sentence renders correctly in a rule while the reference is
# broken.
SEASON_SENTENCE_KEYS = (
    "seasonAsked", "seasonAskedOne", "seasonAskedNone",
    "seasonAskedNewlyFollowed", "seasonAskedOneNewlyFollowed",
    "seasonAskedNoneNewlyFollowed",
    "seasonQueued", "seasonQueuedNewlyFollowed",
    "seasonHeld", "seasonRefused",
)
MEDIA_SENTENCES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "i18n"
     / "fr.json").read_text(encoding="utf-8"))["verbs"]["media"]

SAID = """()=>{const held = window.__toast?.read?.();
  return held && held.message ? held.message.message || '' : '';}"""

OPEN_PANEL_TITLE = """()=>(window.__store.read().state.panelDescriptor || {}).title || ''"""


async def hold_the_named_answer(page, journal):
    """Holds that a season's answer names the show it is about.

    THE DEFECT: Silo's season 3 asked with the answer held back, the panel
    closed, American Dad!'s opened — and the answer landed over American Dad!'s
    panel as « Saison 3 demandée — 1 épisode à récupérer. », reading as about
    American Dad!. The take's own sentence names its show (« … retenue pour
    « Silo » »); the season's did not.

    TWO READINGS. Every one of the ten sentences a season ask can speak carries
    the show — read in the resource, because most of the ten are reached by no
    walk a fixture allows (offline, a busy pipeline, a follow begun). And on the
    walk B8 was measured on, answered and then refused, the sentence that lands
    over the OTHER show's panel names the show that was asked for.

    Args:
        page: The page under test.
        journal: Where the holds are recorded.
    """
    unnamed = [key for key in SEASON_SENTENCE_KEYS
               if "{{title}}" not in MEDIA_SENTENCES.get(key, "")]
    journal.check(
        "every sentence a season ask can speak names its show — each of the ten "
        "keys carries {{title}}",
        not unnamed, ", ".join(unnamed) or "all ten")

    for status, label in ((200, "answered"), (409, "refused")):
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        followed = await page.evaluate(
            """()=>(window.__followActions?.all?.() || []).map((one) => one.t)""")
        asked = ""
        for title in followed:
            await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
            await page.wait_for_timeout(PANEL_IN)
            asked = await page.evaluate(A_HOLE)
            if asked:
                break
            await page.evaluate("()=>window.__panel.close()")
            await page.wait_for_timeout(PANEL_IN)
        subject = asked.split("|")[0]
        other = next((title for title in followed if title != subject), "")
        journal.check(f"{label}: a follow offers a season act, and another follow exists",
                      bool(asked) and bool(other), f"{asked!r} and {other!r}")
        if not (asked and other):
            continue

        await page.evaluate(
            """(status)=>window.__mocks.setOperationOutcome('grabSeasonForFollow',
                 {status, latencyMilliseconds: %d})""" % HELD_BACK_MS, status)
        act = await page.evaluate(TAKEN, asked)
        if not (act.get("found") and act.get("reached")):
            journal.check(f"{label}: the act is under a finger", False, str(act))
            continue
        await page.touchscreen.tap(act["x"], act["y"])
        await page.wait_for_timeout(ACTED // 4)
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(PANEL_IN)
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", other)
        await page.wait_for_timeout(PANEL_IN)
        opened = await page.evaluate(OPEN_PANEL_TITLE)
        await page.wait_for_timeout(HELD_BACK_MS + ACTED)
        said = await page.evaluate(SAID)
        journal.check(
            f"{label}: the answer that lands over « {other} »'s panel names "
            f"« {subject} », the show that was asked for",
            opened == other and bool(said) and subject in said,
            f"panel {opened!r}, said {said!r}")
        await page.evaluate(
            """()=>window.__mocks.setOperationOutcome('grabSeasonForFollow',
                 {status: 200, latencyMilliseconds: 0})""")
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(PANEL_IN)


async def agrees_with_the_cache(page, journal, produce, half):
    """Holds that what is on screen is what a fresh produce would draw.

    Args:
        page: The page under test.
        journal: Where the holds are recorded.
        produce: An evaluation that produces the same panel again.
        half: Which half of the walk this is, for the hold's own text.
    """
    on_screen = await page.evaluate(ON_SCREEN)
    await page.evaluate("()=>window.__panel.close()")
    await page.wait_for_timeout(PANEL_IN)
    await page.evaluate(produce)
    await page.wait_for_timeout(PANEL_IN)
    reopened = await page.evaluate(ON_SCREEN)
    journal.check(
        f"{half}: the panel ON SCREEN says what a panel produced fresh from "
        "the cache says — the operator's own test, which is how this was "
        "found: he closed the sheet and reopened it and the second one was "
        "different",
        on_screen is not None and reopened is not None
        and on_screen["text"] == reopened["text"]
        and on_screen["dots"] == reopened["dots"]
        and on_screen["queued"] == reopened["queued"],
        f"on screen {(on_screen or {}).get('queued')} mark(s), reopened "
        f"{(reopened or {}).get('queued')}; texts "
        f"{'agree' if on_screen and reopened and on_screen['text'] == reopened['text'] else 'DIFFER'}")
    return on_screen


async def main():
    journal = Journal("R157 — the surface a verb was pressed on re-reads")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # ── THE JOURNEY, AND ITS STAGE STRIP ───────────────────────────────
        await page.evaluate("(id)=>window.__go(id)", JOURNEY_STATE)
        await page.wait_for_timeout(SETTLED)
        subject = ""
        carried = await page.evaluate(QUEUE_SUBJECTS)
        for candidate in carried:
            await page.evaluate(
                "(t)=>window.__panel.produce('journey', t)", candidate)
            await page.wait_for_timeout(PANEL_IN)
            stages = await page.evaluate(STAGES_HELD, candidate)
            if stages and RUNNING_STAGE in stages:
                subject = candidate
                break
            await page.evaluate("()=>window.__panel.close()")
            await page.wait_for_timeout(PANEL_IN)
        journal.check(
            "the queue carries a medium whose tunnel has a stage RUNNING — the "
            "only kind a requeue moves, since it sets everything from the first "
            "unfinished stage onward to « upcoming »",
            bool(subject),
            subject or f"none of {len(carried)} carried medium(s) is running")
        if not subject:
            await context.close()
            await browser.close()
            journal.summary()
            return
        before = await page.evaluate(ON_SCREEN)
        journal.check(
            "its journey sheet is open and has something to say",
            before is not None and len(before["text"]) > 0,
            str((before or {}).get("text", ""))[:60])

        pressed = await page.evaluate(PRESS_JOURNEY_VERB)
        journal.check(
            "« Remettre en file » is on the open sheet and takes a press",
            pressed.get("pressed"), str(pressed))
        await page.wait_for_timeout(ACTED)

        after = await page.evaluate(ON_SCREEN)
        journal.check(
            "the sheet the verb was pressed ON has moved — it used to be "
            "byte-identical after a full settle, while the layer had answered",
            before is not None and after is not None
            and (before["text"] != after["text"]
                 or before["dots"] != after["dots"]),
            f"{(before or {}).get('dots')} → {(after or {}).get('dots')}")

        await agrees_with_the_cache(
            page, journal,
            f"()=>window.__panel.produce('journey', {subject!r})",
            "the journey")

        # ── THE SEASON, AND ITS COUNT AND ITS MARK ─────────────────────────
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        # The panel is produced for each followed title until one offers a grab.
        followed = await page.evaluate(
            """()=>(window.__followActions?.all?.() || []).map((one) => one.t)""")
        holed = ""
        for title in followed:
            await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
            await page.wait_for_timeout(PANEL_IN)
            if await page.evaluate(A_HOLE):
                holed = title
                break
            await page.evaluate("()=>window.__panel.close()")
            await page.wait_for_timeout(PANEL_IN)
        journal.check(
            "a followed medium has a season with a hole, drawn in an open panel",
            bool(holed), holed or f"none of {len(followed)} follows offers a grab")

        if holed:
            season_before = await page.evaluate(ON_SCREEN)
            asked_before = await page.evaluate(ANSWERED, "grabSeasonForFollow")
            # TWICE, WITH NO SETTLE BETWEEN THEM, which is the burst a finger
            # makes when nothing has visibly happened yet. The two presses are
            # in ONE evaluation so nothing can settle between them — awaiting
            # between two Playwright calls is a settle, and it would measure a
            # deliberate second ask rather than the burst.
            press = await page.evaluate(
                """(part)=>{
                  const act = document.querySelector(
                    '#sheetin [data-part="' + part + '"]');
                  if (!act) return {found: false};
                  const box = act.getBoundingClientRect();
                  const hit = document.elementFromPoint(
                    box.left + box.width / 2, box.top + box.height / 2);
                  if (!hit || !(hit === act || act.contains(hit)))
                    return {found: true, pressed: false,
                            covering: String(hit && hit.className || '')};
                  act.click();
                  act.click();
                  return {found: true, pressed: true};}""",
                "season/grab")
            journal.check(
                "« récupérer cette saison » takes a press at its own centre",
                press.get("pressed"), str(press))
            await page.wait_for_timeout(ACTED)

            burst = await page.evaluate(ANSWERED, "grabSeasonForFollow")
            journal.check(
                "and TWO presses with no settle between them asked ONCE — the "
                "same intention made twice because nothing had visibly "
                "happened, not two asks. Read on what the layer answered, "
                "never on the message, which showed one either way",
                burst - asked_before == 1, f"{burst - asked_before} ask(s)")

            season_after = await page.evaluate(ON_SCREEN)
            journal.check(
                "the panel the grab was pressed ON has moved — the row BEHIND "
                "it already did, which is what made this read as « nothing "
                "happened » from the only place the operator was looking",
                season_before is not None and season_after is not None
                and (season_before["text"] != season_after["text"]
                     or season_before["queued"] != season_after["queued"]),
                f"{(season_before or {}).get('queued')} → "
                f"{(season_after or {}).get('queued')} mark(s)")

            await agrees_with_the_cache(
                page, journal,
                f"()=>window.__panel.produce('follow', {holed!r})",
                "the season panel")

        await hold_the_place(page, journal)
        await hold_the_taken_act(page, journal)
        await hold_the_named_answer(page, journal)

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
