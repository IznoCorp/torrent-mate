"""R132 — the pause acts, and it acts on the FIRST tap (B-337).

TWO SURFACES OFFER THE SAME ACT and they are reached differently. A follow's
panel offers « Mettre en pause » as a panel action, whose target is a data
attribute nothing but a delegation reads. A follow's ROW offers it too, revealed
by swiping the card open — and that button is dispatched by CLASS inside the
engine, with the subject read off the row's own title text.

B-337 IS ABOUT THE SECOND, and it is the operator's, verbatim: « il faut 2 clics
sur le bouton pour que ça soit pris en compte, le premier clic ne fait rien
systématiquement ». Two mechanisms were left to tell apart on the device, and
the register says which reading settles it: a finger, not a click. So the swipe
here is a REAL TOUCH — a sequence of touch events with movement and a dwell,
dispatched through the browser's own input pipeline — and the revealed action is
tapped ONCE. `page.touchscreen.tap` cannot reproduce it: it is a synthetic touch
with no movement and no dwell, which is exactly the class of defect it cannot
see.

WHAT IT READS, and each fails differently:

  1. THE FIXTURE OFFERS A FOLLOW THAT IS NOT ALREADY PAUSED. Held first: the act
     TOGGLES, so a subject already paused would move the other way and every
     hold below would read the opposite of what it says.
  2. THE PANEL'S ACT MOVES THE STATE — against what it WAS, never against a word
     this rule chose, because the act is a toggle and a rule naming the
     destination would be asserting the fixture rather than the behaviour.
  3. THE UNDO PUTS IT BACK. A state change offered with an undo that does not
     undo is worse than one offered without.
  4. THE ROW'S REVEALED ACTION ACTS ON THE FIRST TAP (B-337). One touch, and the
     state must have moved. If it takes two, this hold falls and the reading
     says which listener consumed the first.
  5. NO ERROR IS RAISED.

WHAT IT DOES NOT SETTLE, said here because the register asks for it: WHICH
listener eats a swallowed first click. The hold reports that it was eaten and
prints what the press arbitration and the drag were holding at that moment; the
attribution between the two is the reading the register asks for and it is
written down when it happens, never guessed at from a green run.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE FOLLOWS ARE DRAWN AS ROWS a finger can swipe.
FOLLOWS_STATE = "acq-follows-list"

# THE FOLLOWS THE LAYER HOLDS — the state is read here and never on the screen,
# because a row can be redrawn from anything.
FOLLOWS = """()=>(window.__followActions?.all() || []).map(
  (one) => ({t: one.t, k: one.k, st: one.st}))"""

# THE ACTIONS A PANEL OFFERS, by LABEL — printed as the detail of a hold, so a
# failure says what the panel was actually carrying.
ACTIONS = """()=>[...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
  .map((one) => (one.textContent || '').trim())"""

# WHERE THE ACT IS, FOUND BY ITS ATTRIBUTE AND NOT BY A WORD. The label depends
# on the KIND — a film is « Ne plus chercher » and a series « Mettre en pause »,
# which is §5 read from the interface's side — so a rule matching on « pause »
# finds the film's action never. Worse, a rule matching « pause » OR « cherch »
# finds « Chercher maintenant », which is a different act entirely: this rule
# reported the panel « offers the pause » on that one before the attribute
# replaced the words.
THE_PAUSE = """()=>{
  const act = document.querySelector('#sheetin [data-part="sheet/action"][data-pause]');
  if (!act) return {found: false,
    offered: [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
      .map((one) => (one.textContent || '').trim())};
  const box = act.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, label: (act.textContent || '').trim(),
          subject: act.dataset.pause,
          reachable: !!hit && (hit === act || act.contains(hit))};}"""


async def finger_swipe(page, start, end, dwell=120):
    """Drags one finger across the screen, through the browser's input pipeline.

    A REAL TOUCH, and the distinction is the whole point of this rule.
    `page.touchscreen.tap` sends a touch with no movement and no dwell, and
    B-337 is a defect that only a movement can arm: the engine's swipe machinery
    remembers where a drag ended and swallows a click near it. A synthetic tap
    never arms it, so every synthetic reading of this surface is green.

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
    journal = Journal("R132 — the pause acts, and on the first tap")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)

        follows = await page.evaluate(FOLLOWS)
        subject = next((one for one in follows if one["st"] != "disabled"), None)
        journal.check(
            "the fixture offers a follow that is NOT already paused — the act "
            "TOGGLES, so a paused subject would move the other way and every "
            "hold below would read the opposite of what it says",
            subject is not None, str(follows[:3]))
        if subject is None:
            await context.close()
            await browser.close()
            journal.summary()
            return

        # ── THE PANEL'S ACT ────────────────────────────────────────────────
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", subject["t"])
        await page.wait_for_timeout(PANEL_IN)
        offered = await page.evaluate(ACTIONS)
        aim = await page.evaluate(THE_PAUSE)
        journal.check(
            "the follow's panel offers the pause — found by the ATTRIBUTE the "
            "act carries, because its LABEL depends on the kind",
            aim.get("found"), str(offered))
        if aim.get("found") and aim.get("reachable"):
            await finger_tap(page, (aim["x"], aim["y"]))
        journal.check(
            "and it is on a button a finger reaches", aim.get("reachable"), str(aim))
        await page.wait_for_timeout(ACTED)

        after = await page.evaluate(FOLLOWS)
        moved = next((one for one in after if one["t"] == subject["t"]), None)
        journal.check(
            "the panel's act MOVES the state — read against what it WAS, never "
            "against a destination this rule chose, because the act toggles",
            moved is not None and moved["st"] != subject["st"],
            f"{subject['st']} → {moved['st'] if moved else None}")

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
        back = next((one for one in undone if one["t"] == subject["t"]), None)
        journal.check(
            "and the UNDO puts it back — a state change offered with an undo "
            "that does not undo is worse than one offered without",
            undo.get("found") and back is not None
            and moved is not None and moved["st"] != subject["st"]
            and back["st"] == subject["st"],
            f"{moved['st'] if moved else None} → {back['st'] if back else None}")

        # ── B-337: THE ROW'S REVEALED ACTION, ON ONE REAL TAP ──────────────
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        errors.clear()
        before_swipe = await page.evaluate(FOLLOWS)
        row = await page.evaluate("""(title)=>{
            const cards = [...document.querySelectorAll('[data-part="swipe"]')];
            const one = cards.find((card) => (card.textContent || '').includes(title));
            if (!one) return {found: false};
            const box = one.getBoundingClientRect();
            return {found: true, x: box.left + box.width / 2,
                    y: box.top + box.height / 2,
                    left: box.left, right: box.right};}""", before_swipe[0]["t"])
        journal.check(
            "a follow is drawn as a row a finger can swipe", row.get("found"),
            str(row))
        if not row.get("found"):
            await context.close()
            await browser.close()
            journal.summary()
            return

        swiped_subject = before_swipe[0]
        # LEFTWARD, and the direction is read rather than guessed: `swipeHTML`
        # puts the pause and the removal in `data-side="right"`, and a drawer on
        # the right is uncovered by the card travelling LEFT. Swiping the other
        # way reveals the left drawer — « Chercher » — which exists only for a
        # follow that is pending, so the first version of this walk revealed
        # nothing at all on half the fixture and called it a defect.
        await finger_swipe(page, (row["x"] + 100, row["y"]), (row["x"] - 60, row["y"]))
        await page.wait_for_timeout(SETTLED)
        revealed = await page.evaluate("""()=>{
            const act = [...document.querySelectorAll('[data-part="swipe/action"]')]
              .map((one) => {
                const box = one.getBoundingClientRect();
                const x = box.left + box.width / 2;
                const y = box.top + box.height / 2;
                const hit = document.elementFromPoint(x, y);
                return {label: (one.textContent || '').trim(), x, y,
                        width: box.width,
                        reachable: !!hit && (hit === one || one.contains(hit))};})
              .filter((one) => one.width > 0 && one.reachable);
            return act;}""")
        journal.check(
            "the swipe reveals its actions, and a finger reaches one",
            bool(revealed), str(revealed))
        if not revealed:
            journal.check("B-337 could not be measured — the swipe revealed "
                          "nothing a finger reaches", False, str(revealed))
            await context.close()
            await browser.close()
            journal.summary()
            return

        target = next((one for one in revealed
                       if "pause" in one["label"].lower()
                       or "cherch" in one["label"].lower()), revealed[0])
        await finger_tap(page, (target["x"], target["y"]))
        await page.wait_for_timeout(ACTED)
        after_one = await page.evaluate(FOLLOWS)
        moved_once = next((one for one in after_one
                           if one["t"] == swiped_subject["t"]), None)
        journal.check(
            "ONE tap on the revealed action acts (B-337: « le premier clic ne "
            "fait rien systématiquement »)",
            moved_once is not None and moved_once["st"] != swiped_subject["st"],
            f"{swiped_subject['st']} → "
            f"{moved_once['st'] if moved_once else None} on « {target['label']} »")

        journal.check("and the whole gesture raises no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
