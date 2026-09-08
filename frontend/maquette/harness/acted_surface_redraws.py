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

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
