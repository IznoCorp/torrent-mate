"""R185 — B-371: the queued mark is reached by the path a HAND takes, and by no other.

THE DEFECT THIS HOLDS. DOIT-4's « En file » pastille was drawn, and R138 passed on
it, while no person could make it appear: the pastille read the layer's pipeline
state, which only the pipeline operations write, and « Lancer le pipeline » wrote
the interface's own store and touched no network. Two pipeline notions, and the
hand could move only the one the pastille did not read.

NO STATE DOOR IS OPENED, and that absence IS the rule's subject. Every other rule
reaching the pastille arranges busy-ness through `window.__pipeline` or drives a
named state through `window.__go`; a walk that does either proves the drawing and
not the path. So this walk counts the calls the state door received, from an
init script installed before the application assigns it, and holds the count at
zero.

RE-AIMED OUT LOUD (OPEN 6, ruled A): « Lancer » and « Arrêter » a pass died with
Arrivées' bar, and no lever took them over. The walk that started a pass by a
finger on that bar now takes the path a hand still has (DESIGN § 6.1): a
maintenance command started from Maintenance holds the lock, then a season is
asked. Where the bar's holds went: « Lancer » drawn inactive while its pass runs,
and a finger on it asking nothing, died with the button; a second pass answered
409 and a pass queued behind a maintenance run were holds on the bar's own
operation, which no surface sends any more — the queued pass is Système's
`levers-queued`, held by levers.py.

WHAT IS READ, in the order a person does it:

  1. AT REST THE PIPELINE IS IDLE, read on the layer: an idle machine is the
     premise, or the walk measures a state it did not cause.
  2. MAINTENANCE IS REACHED BY A FINGER, from the menu's drawer.
  3. A MAINTENANCE COMMAND IS OPENED AND STARTED BY A FINGER, hit-tested.
  4. THE RUN OPERATION IS ANSWERED, and the lock is held after it — read on the
     layer's record of what it was asked, and on its locks read afterwards.
  5. THE FOLLOWS ARE REACHED BY A FINGER, tab bar then the tab.
  6. A SEASON WITH A HOLE IS ASKED FOR, from a row a finger raises.
  7. THE PASTILLE IS PRESENT on that season.
  8. AND THE STATE DOOR WAS NEVER OPENED.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page, chrome_launch_args

from playwright.async_api import async_playwright

# COUNTING THE STATE DOORS, installed before the application assigns them: each
# assignment is wrapped so a call is counted and still made.
COUNT_THE_DOORS = """(() => {
  window.__doorsOpened = [];
  for (const name of ["__go", "__pipeline"]) {
    let held;
    Object.defineProperty(window, name, {
      configurable: true,
      get: () => held,
      set: (value) => {
        held = typeof value === "function"
          ? (...args) => { window.__doorsOpened.push(name); return value(...args); }
          : value;
      },
    });
  }
})();"""

# THE PIPELINE'S STATE, as the layer answers it.
PIPELINE_STATE = """async ()=>(await (await fetch('/api/pipeline/status')).json()).state"""

# WHAT THE LAYER ANSWERED to one operation.
ANSWERED = """(name)=>(window.__mocks?.answered?.() || [])
  .filter((call) => call.operationId === name)
  .map((call) => call.status)"""

# PRESSING A CONTROL THE WAY A FINGER DOES: scrolled into view, hit-tested at its
# centre, clicked only when nothing covers it.
PRESS = """(selector)=>{
  const control = document.querySelector(selector);
  if (!control) return {found: false, pressed: false, covered: ''};
  control.scrollIntoView({block: 'center'});
  const box = control.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
                                        box.top + box.height / 2);
  const mine = Boolean(hit) && (hit === control || control.contains(hit));
  // THE CONTROL IS CLICKED once the finger is proved to land on it: what the
  // point hits may be a drawing inside it (the menu button's SVG has no click).
  if (mine) control.click();
  return {found: true, pressed: mine,
          covered: mine ? '' : ((hit && (hit.dataset.part || hit.tagName)) || 'nothing')};}"""

# WHETHER A FINGER WOULD REACH A CONTROL, without pressing it.
PRESS_PROBE = """(selector)=>{
  const control = document.querySelector(selector);
  if (!control) return {reachable: false};
  const box = control.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
                                        box.top + box.height / 2);
  return {reachable: Boolean(hit) && (hit === control || control.contains(hit))};}"""

# THE MEDIUM WITH A HOLE, among the rows actually drawn. A follow is read in the
# contract's names: its title is `title`.
THE_MEDIUM_WITH_A_HOLE = """()=>{
  const drawn = [...document.querySelectorAll('[data-panel]')].map(
    (one) => one.dataset.panel);
  const reachable = (title) => drawn.some(
    (seen) => seen === title || seen.endsWith(":" + title));
  for (const follow of (window.__followActions?.all() || [])) {
    if (!reachable(follow.title)) continue;
    for (const [number, aired, owned] of (window.__mocks.seasons()[follow.title] || [])) {
      if ((owned || 0) > 0 && (owned || 0) < (aired || 0))
        return {title: follow.title, season: number};
    }
  }
  return null;}"""

# THE ROW OF THAT MEDIUM, as a selector a finger can be aimed at.
ROW_OF = """(title)=>{
  const row = [...document.querySelectorAll('[data-panel]')].find(
    (one) => one.dataset.panel === title || one.dataset.panel.endsWith(":" + title));
  if (!row) return null;
  row.setAttribute('data-aimed', '');
  return '[data-aimed]';}"""

# THE PASTILLE, with the heading of the season row carrying it.
THE_MARK = """()=>[...document.querySelectorAll('[data-part="season/queued"]')].map(
  (one) => (one.closest('[data-part="season"]')
              ?.querySelector('summary')?.textContent || '').trim())"""

GRAB = '[data-part="season/grab"]'

# THE MAINTENANCE COMMAND THE HAND STARTS: a real run of a query, which changes
# no file and holds the lock while it lasts.
COMMAND_TOPIC = "query"
COMMAND = "library-status"

# WHAT THE LAYER SAYS OF THE PIPELINE'S LOCK.
LOCK_HELD = """async ()=>(await (await fetch('/api/maintenance/locks')).json()).pipelineLock.held"""


async def press(journal, page, selector, claim):
    """Presses one control by a finger and holds that it was reachable.

    Args:
        journal: The rule's journal.
        page: The page under test.
        selector: The control's selector.
        claim: What the hold says.

    Returns:
        Whether the control was pressed.
    """
    aim = await page.evaluate(PRESS, selector)
    journal.check(claim, aim["found"] and aim["pressed"], str(aim))
    return aim["found"] and aim["pressed"]


async def walk(journal, page):
    """Takes the hand's path from an idle machine to the queued mark.

    Args:
        journal: The rule's journal.
        page: A freshly opened page, no state driven.
    """
    journal.check(
        "at rest the pipeline is IDLE, on the layer — the walk causes what it reads",
        await page.evaluate(PIPELINE_STATE) == "idle",
        str(await page.evaluate(PIPELINE_STATE)))

    if not await press(journal, page, '[data-drawer]', "the menu is opened by a finger"):
        return
    await page.wait_for_timeout(SETTLED)
    if not await press(journal, page, '#drawer [data-navgo="maint"]',
                       "Maintenance is reached by a finger, from the drawer"):
        return
    await page.wait_for_timeout(SETTLED)
    if not await press(journal, page, f'[data-maintopic="{COMMAND_TOPIC}"]',
                       "its topic is opened by a finger"):
        return
    await page.wait_for_timeout(SETTLED)
    if not await press(journal, page, f'[data-maintact="{COMMAND}"]',
                       "a maintenance command is opened by a finger"):
        return
    await page.wait_for_timeout(PANEL_IN)
    if not await press(journal, page, '[data-maintenance-run]',
                       "and its « Lancer » is pressed by a finger"):
        return
    await page.wait_for_timeout(ACTED)

    answered = await page.evaluate(ANSWERED, "runMaintenanceAction")
    held = await page.evaluate(LOCK_HELD)
    journal.check(
        "the maintenance command is ANSWERED, and it holds the pipeline's lock after it "
        "— a store write answers nothing",
        len(answered) == 1 and answered[0] < 300 and held is True,
        f"runMaintenanceAction answered {answered}, locks read held={held}")

    # THE PANEL THE COMMAND RAISED COVERS THE TAB BAR, so the hand closes it
    # first, the way a phone does: Back, until the bar answers a finger again.
    for _ in range(3):
        if (await page.evaluate(PRESS_PROBE, '[data-page="acq"]'))["reachable"]:
            break
        await page.go_back()
        await page.wait_for_timeout(PANEL_IN)
    if not await press(journal, page, '[data-page="acq"]',
                       "Acquisition is reached by a finger, from the tab bar"):
        return
    await page.wait_for_timeout(SETTLED)
    if not await press(journal, page, '[data-acqtab="follows"]',
                       "and its follows, by a finger"):
        return
    await page.wait_for_timeout(SETTLED)

    subject = await page.evaluate(THE_MEDIUM_WITH_A_HOLE)
    journal.check("a drawn follow holds a season with a hole, so the walk has a subject",
                  subject is not None, str(subject))
    if subject is None:
        return
    row = await page.evaluate(ROW_OF, subject["title"])
    if not await press(journal, page, row,
                       f"« {subject['title']} »'s row raises its panel under a finger"):
        return
    await page.wait_for_timeout(PANEL_IN)
    if not await press(journal, page, GRAB, "a season's grab is pressed by a finger"):
        return
    await page.wait_for_timeout(ACTED)

    marks = await page.evaluate(THE_MARK)
    journal.check(
        "the « En file » pastille is PRESENT on the season asked for — DOIT-4, "
        "reached by a walk a person can repeat",
        len(marks) == 1 and str(subject["season"]) in marks[0],
        f"{len(marks)} mark(s): {marks}, for season {subject['season']}")


async def fresh_page(browser):
    """Opens the prototype with the state doors counted from the first script.

    Args:
        browser: A launched browser.

    Returns:
        The (context, page) pair, past the startup screen.
    """
    context, page = await open_page(browser)
    await context.add_init_script(COUNT_THE_DOORS)
    await page.reload(wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(SETTLED)
    return context, page


async def main():
    journal = Journal("R185 — the queued mark is reached by the path a hand takes")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        errors: list[str] = []
        opened: list[str] = []
        context, page = await fresh_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await walk(journal, page)
        opened += await page.evaluate("()=>window.__doorsOpened")
        await context.close()

        journal.check(
            "and no state door was opened on the way — `__go` and `__pipeline` "
            "called zero times, so what is measured is the path",
            opened == [], str(opened))
        journal.check("and nothing threw", not errors, str(errors))
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
