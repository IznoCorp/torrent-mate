"""R530 — « Rejeter » writes the rejection from each door Découvrir offers, and « Annuler » takes it back (K3-G7).

FOUR DOORS REJECT A SUGGESTION: the panel's « Pas intéressé » over the list and
over the pile, a row thrown to the right and the pile's top card thrown to the
right. Each is walked by a real finger.

WHAT IS READ IS THE DECK THE LAYER ANSWERS, page after page, never `sugGone`:
a card only spent on the screen leaves the view exactly as a rejected one does,
and is still in the deck the server hands the next read. So for each door:

  1. the card is in the answered deck before the gesture — held first, or the
     holds below pass over a card that was never there;
  2. it is OUT of it once rejected: the write left, and the layer took it;
  3. « Annuler », tapped on the notification, puts it back IN it: the rejection
     is deleted, not merely forgotten by the screen;
  4. and the card is drawn again.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page, browser_channel, chrome_launch_args

from playwright.async_api import async_playwright

ROW = '#view [data-part="suggestion/wrap"]'
TOP_CARD = '[data-part="deck/card"][data-depth="0"]'

# A throw past both gestures' commit distances, in CSS pixels.
THROW = 170

# THE DECK AS THE LAYER ANSWERS IT, every page of it.
ANSWERED = """async () => {
  const ids = [];
  let cursor = null;
  do {
    const query = cursor === null ? '' : '?cursor=' + encodeURIComponent(cursor);
    const page = await (await fetch('/api/v1/acquisition/suggestions' + query)).json();
    ids.push(...page.suggestions.map((one) => one.id));
    cursor = page.nextCursor;
  } while (cursor !== null && ids.length < 1000);
  return ids;
}"""

# THE CARD A DOOR ACTS ON: its position in the reserve, read off what is drawn.
DRAWN_FIRST = {
    "list": f"""()=>Number(document.querySelector('{ROW}')?.dataset.dismissable ?? NaN)""",
    "deck": f"""()=>Number(document.querySelector('{TOP_CARD}')?.dataset.deck ?? NaN)""",
}
ID_AT = "(at)=>(window.__suggestions?.() || [])[at]?.id ?? null"

# WHETHER A CARD IS DRAWN, told by its id through its position in the reserve.
DRAWN = """([shape, id])=>{
  const at = (window.__suggestions?.() || []).findIndex((one) => one.id === id);
  const selector = shape === 'list'
    ? `#view [data-part="suggestion/wrap"][data-dismissable="${at}"]`
    : `[data-part="deck/card"][data-deck="${at}"]`;
  return !!document.querySelector(selector);}"""

# WHERE A FINGER LANDS ON AN ELEMENT, and whether it reaches it there.
AIM = """(selector)=>{
  const one = document.querySelector(selector);
  if (!one) return {found: false};
  const box = one.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, reachable: !!hit && (hit === one || one.contains(hit))};}"""

PANEL_ACTION = """()=>{
  const act = [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
    .find((one) => (one.textContent || '').toLowerCase().includes('intéress'));
  if (!act) return {found: false};
  const box = act.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, reachable: !!hit && (hit === act || act.contains(hit))};}"""


async def tap(page, aim):
    """Taps where an aim says a finger lands, if it reaches the element there."""
    if not (aim.get("found") and aim.get("reachable")):
        return False
    await page.touchscreen.tap(aim["x"], aim["y"])
    return True


async def throw_right(page, cdp, selector):
    """Throws the first element a selector finds to the right, by real touches."""
    box = await page.evaluate("""(selector)=>{
        const b = document.querySelector(selector).getBoundingClientRect();
        return {x: b.left + b.width / 2, y: b.top + b.height / 2};}""", selector)
    point = lambda x: [{"x": x, "y": box["y"], "id": 1}]
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": point(box["x"])})
    for step in range(1, 13):
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchMove", "touchPoints": point(box["x"] + THROW * step / 12)})
        await page.wait_for_timeout(16)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


async def walk(page, cdp, journal, shape, door):
    """Rejects one card through one door, takes it back, and reads the layer's deck at each step."""
    name = f"{shape}, {door}"
    await page.evaluate("""(shape)=>{
        window.__reset();
        applyState({page: "discover", phase: "ready"});
        window.__store.write({sugMode: shape});
        window.__store.touch();
        document.querySelector('#toastx')?.click();}""", shape)
    await page.wait_for_timeout(ACTED)

    position = await page.evaluate(DRAWN_FIRST[shape])
    card = await page.evaluate(ID_AT, position)
    before = await page.evaluate(ANSWERED)
    journal.check(f"[{name}] the card drawn first is in the deck the layer answers",
                  card is not None and card in before, f"position {position}, id {card}")

    if door == "panel":
        await page.evaluate("(at)=>window.__panel.produce('suggestion', String(at))", position)
        await page.wait_for_timeout(PANEL_IN)
        journal.check(f"[{name}] the panel's « Pas intéressé » is reached by a finger",
                      await tap(page, await page.evaluate(PANEL_ACTION)))
    else:
        await throw_right(page, cdp, ROW if shape == "list" else TOP_CARD)
    await page.wait_for_timeout(ACTED)

    rejected = await page.evaluate(ANSWERED)
    journal.check(f"[{name}] rejected, the card is out of the deck the layer answers — the write left",
                  card not in rejected and len(rejected) == len(before) - 1,
                  f"{len(before)} → {len(rejected)}, still held: {card in rejected}")

    journal.check(f"[{name}] the notification's « Annuler » is reached by a finger",
                  await tap(page, await page.evaluate(AIM, "#toastundo")))
    await page.wait_for_timeout(ACTED + SETTLED)

    undone = await page.evaluate(ANSWERED)
    journal.check(f"[{name}] « Annuler » puts it back in the deck the layer answers — the rejection is deleted",
                  card in undone and undone == before, f"{len(rejected)} → {len(undone)}")
    journal.check(f"[{name}] and the card is drawn again",
                  await page.evaluate(DRAWN, [shape, card]))


async def main():
    journal = Journal("R530 — « Rejeter » writes from every door, and « Annuler » deletes what it wrote")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        cdp = await context.new_cdp_session(page)

        for shape in ("list", "deck"):
            for door in ("panel", "swipe"):
                await walk(page, cdp, journal, shape, door)

        journal.check("and no gesture raises an error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
