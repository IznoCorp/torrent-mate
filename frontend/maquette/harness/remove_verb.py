"""R133 — the removal takes the follow away, and the undo brings it back.

TWO SURFACES OFFER THE SAME ACT, exactly as the pause's do, and they are
reached differently. A follow's panel offers « Retirer de la liste » as a panel
action whose target is a data attribute. A follow's ROW offers « Retirer »
behind a swipe, and that button is dispatched by CLASS inside the engine, with
the subject read off the row's own heading text.

WHAT IT READS, and each fails differently:

  1. THE FIXTURE HOLDS MORE THAN ONE FOLLOW. Held first: a removal read on a
     list of one cannot tell « the follow went » from « the list went », and
     every count below would be comparing one against zero.
  2. THE PANEL'S ACT REMOVES IT — absent from what the layer holds, AND the
     count down by EXACTLY ONE. Absence alone would pass over a removal that
     took the neighbours with it, which is the failure worth catching.
  3. AND THE ROW IS GONE FROM THE SCREEN. A cache the interface does not
     redraw is a follow the operator still sees, which from a finger's side is
     a removal that did not happen.
  4. THE UNDO PUTS IT BACK — present again and the count restored. Read as a
     TRANSITION, never as a state: a hold that merely asks « is it present »
     is answered by a removal that never occurred.
  5. THE ROW'S REVEALED REMOVAL ACTS ON THE FIRST TAP, on a real touch — the
     same finger B-337 is about, on this act's own button.
  6. NO ERROR IS RAISED.

THE REVEALED ACTION IS FOUND BY ITS ATTRIBUTE, `data-action="remove"`, and not
by its label. R132's first version matched « pause » OR « cherch » in the text
and found « Chercher maintenant », a different act entirely; a label is the one
thing on a button that is allowed to change. This surface emits `data-action`
on every swipe action and the markup contract holds those values, so the
attribute is both stabler and already guarded.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE FOLLOWS ARE DRAWN AS ROWS a finger can swipe.
FOLLOWS_STATE = "acq-follows-list"

# WHAT THE LAYER HOLDS — read here and never off the screen, because a row can
# be redrawn from anything and a rule reading its own subject twice reads it
# from one place.
FOLLOWS = """()=>(window.__followActions?.all() || []).map(
  (one) => ({t: one.t, k: one.k, st: one.st}))"""

# THE REMOVAL IN THE PANEL, found by the ATTRIBUTE it carries. Its LABEL
# depends on the kind — « Retirer le film » against « Retirer la série » — so
# no single word finds both, and a rule matching several would find a
# neighbouring act instead.
THE_REMOVAL = """()=>{
  const act = document.querySelector(
    '#sheetin [data-part="sheet/action"][data-remove]');
  if (!act) return {found: false,
    offered: [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
      .map((one) => (one.textContent || '').trim())};
  const box = act.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, label: (act.textContent || '').trim(),
          subject: act.dataset.remove,
          reachable: !!hit && (hit === act || act.contains(hit))};}"""

# WHETHER THE SCREEN STILL CARRIES THE ROW. By the row's own heading — the
# element the engine's dispatch reads the subject from, so a rule asking about
# the same node the act does cannot disagree with it about which row this is.
# ANCHORED ON `data-part`, not on the `.ctitle` class the engine happens to
# select by: a class token in a rule dies the day the style is renamed, and
# nothing could then say whether the anchor or the drawing was at fault.
ROW_ON_SCREEN = """(title)=>[...document.querySelectorAll(
  '[data-part="card/title"]')]
  .some((one) => (one.textContent || '').trim() === title)"""


async def finger_swipe(page, start, end, dwell=120):
    """Drags one finger across the screen, through the browser's input pipeline.

    A REAL TOUCH. `page.touchscreen.tap` sends a touch with no movement and no
    dwell, and the swipe machinery this rule has to open needs a movement to
    respond to at all.

    Args:
        page: The page.
        start: The (x, y) the finger goes down at.
        end: The (x, y) it lifts at.
        dwell: How long the finger rests before lifting, in milliseconds.
    """
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": start[0], "y": start[1]}],
    })
    steps = 8
    for step in range(1, steps + 1):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{
                "x": start[0] + (end[0] - start[0]) * step / steps,
                "y": start[1] + (end[1] - start[1]) * step / steps,
            }],
        })
        await page.wait_for_timeout(16)
    await page.wait_for_timeout(dwell)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await session.detach()


async def finger_tap(page, point, dwell=60):
    """Puts one finger down and lifts it, with a dwell and no movement."""
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": point[0], "y": point[1]}]})
    await page.wait_for_timeout(dwell)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await session.detach()


async def main():
    journal = Journal("R133 — the removal takes the follow away")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)

        before = await page.evaluate(FOLLOWS)
        journal.check(
            "the fixture holds more than one follow — a removal read on a list "
            "of one cannot tell « the follow went » from « the list went »",
            len(before) > 1, f"{len(before)} follow(s)")
        if len(before) < 2:
            await context.close()
            await browser.close()
            journal.summary()
            return
        subject = before[0]

        # ── THE PANEL'S ACT ────────────────────────────────────────────────
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", subject["t"])
        await page.wait_for_timeout(PANEL_IN)
        aim = await page.evaluate(THE_REMOVAL)
        journal.check(
            "the follow's panel offers the removal — found by the ATTRIBUTE "
            "the act carries, because its LABEL depends on the kind",
            aim.get("found"), str(aim))
        journal.check(
            "and it is on a button a finger reaches", aim.get("reachable"),
            str(aim))
        if aim.get("found") and aim.get("reachable"):
            await finger_tap(page, (aim["x"], aim["y"]))
        await page.wait_for_timeout(ACTED)

        after = await page.evaluate(FOLLOWS)
        journal.check(
            "the panel's act REMOVES it — absent from what the layer holds, "
            "AND the count down by EXACTLY ONE, because absence alone passes "
            "over a removal that took the neighbours with it",
            all(one["t"] != subject["t"] for one in after)
            and len(after) == len(before) - 1,
            f"{len(before)} → {len(after)}, « {subject['t']} » "
            f"{'absent' if all(one['t'] != subject['t'] for one in after) else 'STILL THERE'}")

        gone = not await page.evaluate(ROW_ON_SCREEN, subject["t"])
        journal.check(
            "and the ROW is gone from the screen — a cache the interface does "
            "not redraw is a follow the operator still sees",
            gone, f"« {subject['t'] }» {'gone' if gone else 'still drawn'}")

        undo = await page.evaluate("""()=>{
            const one = document.querySelector('#toastundo');
            if (!one) return {found: false};
            const box = one.getBoundingClientRect();
            return {found: true, x: box.left + box.width / 2,
                    y: box.top + box.height / 2};}""")
        if undo.get("found"):
            await finger_tap(page, (undo["x"], undo["y"]))
            await page.wait_for_timeout(ACTED)
        undone = await page.evaluate(FOLLOWS)
        journal.check(
            "and the UNDO puts it back — read as a TRANSITION, never as a "
            "state, because « is it present » is answered by a removal that "
            "never occurred",
            undo.get("found")
            and len(after) == len(before) - 1
            and any(one["t"] == subject["t"] for one in undone)
            and len(undone) == len(before),
            f"{len(before)} → {len(after)} → {len(undone)}")

        # ── B-337's SHAPE ON THIS ACT: THE ROW, ON ONE REAL TAP ────────────
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        errors.clear()
        before_swipe = await page.evaluate(FOLLOWS)
        swiped = before_swipe[0]
        row = await page.evaluate("""(title)=>{
            const cards = [...document.querySelectorAll('[data-part="swipe"]')];
            const one = cards.find((card) => (card.textContent || '').includes(title));
            if (!one) return {found: false};
            const box = one.getBoundingClientRect();
            return {found: true, x: box.left + box.width / 2,
                    y: box.top + box.height / 2};}""", swiped["t"])
        journal.check(
            "a follow is drawn as a row a finger can swipe", row.get("found"),
            str(row))
        if not row.get("found"):
            await context.close()
            await browser.close()
            journal.summary()
            return

        # LEFTWARD: `swipeHTML` puts the removal in the RIGHT drawer, which the
        # card uncovers by travelling left. The other way reveals « Chercher »,
        # which exists only for a follow that is pending.
        await finger_swipe(page, (row["x"] + 100, row["y"]), (row["x"] - 60, row["y"]))
        await page.wait_for_timeout(SETTLED)
        revealed = await page.evaluate("""()=>{
            const one = document.querySelector(
              '[data-part="swipe/action"][data-action="remove"]');
            if (!one) return {found: false};
            const box = one.getBoundingClientRect();
            const x = box.left + box.width / 2;
            const y = box.top + box.height / 2;
            const hit = document.elementFromPoint(x, y);
            return {found: box.width > 0, x, y, width: box.width,
                    label: (one.textContent || '').trim(),
                    reachable: !!hit && (hit === one || one.contains(hit))};}""")
        journal.check(
            "the swipe reveals the removal, found by `data-action` and not by "
            "a word, and a finger reaches it",
            revealed.get("found") and revealed.get("reachable"), str(revealed))
        if not (revealed.get("found") and revealed.get("reachable")):
            journal.check("the row's removal could not be measured — the "
                          "swipe revealed nothing a finger reaches",
                          False, str(revealed))
            await context.close()
            await browser.close()
            journal.summary()
            return

        await finger_tap(page, (revealed["x"], revealed["y"]))
        await page.wait_for_timeout(ACTED)
        after_one = await page.evaluate(FOLLOWS)
        journal.check(
            "ONE tap on the revealed removal acts (B-337: « le premier clic ne "
            "fait rien systématiquement »)",
            all(one["t"] != swiped["t"] for one in after_one)
            and len(after_one) == len(before_swipe) - 1,
            f"{len(before_swipe)} → {len(after_one)} on « {revealed['label']} »")

        journal.check("and the whole gesture raises no error", not errors,
                      str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
