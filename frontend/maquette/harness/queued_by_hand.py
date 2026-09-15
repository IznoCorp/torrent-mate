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

RED AGAINST MAIN DOES NOT EXIST: main has the path. The red is a MUTATION — the
verb's network call made a no-op — under which holds 4 and 7 fall by name.

WHAT IS READ, in the order a person does it:

  1. AT REST THE PIPELINE IS IDLE, read on the layer: an idle machine is the
     premise, or the walk measures a state it did not cause.
  2. ARRIVÉES IS REACHED BY A FINGER, from the tab bar, hit-tested.
  3. « LANCER LE PIPELINE » IS PRESSED BY A FINGER, hit-tested.
  4. THE RUN OPERATION IS ANSWERED — read on the layer's record of what it was
     asked, and on its status read afterwards. A store write answers nothing,
     which is exactly the defect.
  5. THE FOLLOWS ARE REACHED BY A FINGER, tab bar then the tab.
  6. A SEASON WITH A HOLE IS ASKED FOR, from a row a finger raises.
  7. THE PASTILLE IS PRESENT on that season.
  8. AND THE STATE DOOR WAS NEVER OPENED.

A SECOND PASS IS REFUSED, AND THE QUEUE IS THE MAINTENANCE LOCK'S — the backend's
own answer (DESIGN § 3.2): a second PIPELINE pass is the strict duplicate §6
permits refusing, and a pass waits only behind a MAINTENANCE run.

  9. PRESSED AGAIN WHILE ITS PASS RUNS, the run operation answers 409 and the
     pipeline goes on running — it is not demoted to a queue.
 10. AND THE REFUSAL IS SAID IN ITS OWN SENTENCE — never « arrêté », which is what a
     verb reading every answer other than running or queued as a stop said.
 11. WITH A MAINTENANCE RUN IN FLIGHT, « Lancer le pipeline » is answered and the
     pass is QUEUED, and the queued sentence says so.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

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
  if (mine) hit.click();
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

# THE MEDIUM WITH A HOLE, among the rows actually drawn.
THE_MEDIUM_WITH_A_HOLE = """()=>{
  const drawn = [...document.querySelectorAll('[data-panel]')].map(
    (one) => one.dataset.panel);
  const reachable = (title) => drawn.some(
    (seen) => seen === title || seen.endsWith(":" + title));
  for (const follow of (window.__followActions?.all() || [])) {
    if (!reachable(follow.t)) continue;
    for (const [number, aired, owned] of (window.__mocks.seasons()[follow.t] || [])) {
      if ((owned || 0) > 0 && (owned || 0) < (aired || 0))
        return {title: follow.t, season: number};
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
START = '[data-part="pipeline"] [data-pipe="start"]'

# THE STATUS EVERY RUN REQUEST WAS ANSWERED WITH, in order.
RUN_STATUSES = """()=>(window.__mocks?.answered?.() || [])
  .filter((call) => call.operationId === "runPipeline").map((call) => call.status)"""

# A MAINTENANCE RUN PUT IN FLIGHT the way the veille's lever does — its own
# operation, not a state door.
LAUNCH_MAINTENANCE = """async ()=>(await fetch('/api/acquisition/detect', {method: 'POST'})).status"""

SAID = """()=>window.__toast?.read()?.message?.message || ''"""

# THE SENTENCES THE VERB MAY SAY, read from the interface's own resources.
VERB_SENTENCES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "i18n" / "fr.json")
    .read_text(encoding="utf-8"))["verbs"]["arrivals"]


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

    if not await press(journal, page, '[data-page="arr"]',
                       "Arrivées is reached by a finger, from the tab bar"):
        return
    await page.wait_for_timeout(SETTLED)
    if not await press(journal, page, '[data-part="pipeline"] [data-pipe="start"]',
                       "« Lancer le pipeline » is pressed by a finger"):
        return
    await page.wait_for_timeout(ACTED)

    answered = await page.evaluate(ANSWERED, "runPipeline")
    state = await page.evaluate(PIPELINE_STATE)
    journal.check(
        "the RUN OPERATION is answered, and the layer's pipeline is running after "
        "it — a store write answers nothing",
        answered == [200] and state == "running",
        f"runPipeline answered {answered}, status read says {state!r}")

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


async def refused_while_running(journal, page):
    """Presses « Lancer » again while the pass the walk started runs.

    Args:
        journal: The rule's journal.
        page: The page the walk left, its pipeline running.
    """
    # THE PANEL THE WALK RAISED COVERS THE TAB BAR, so the hand closes it first,
    # the way a phone does: Back, until the bar answers a finger again.
    for _ in range(3):
        if (await page.evaluate(PRESS_PROBE, '[data-page="arr"]'))["reachable"]:
            break
        await page.go_back()
        await page.wait_for_timeout(PANEL_IN)
    if not await press(journal, page, '[data-page="arr"]',
                       "Arrivées is reached again by a finger, once Back closed the panel"):
        return
    await page.wait_for_timeout(SETTLED)
    if not await press(journal, page, START,
                       "and its « Lancer » is pressed again while the pass runs"):
        return
    await page.wait_for_timeout(ACTED)
    statuses = await page.evaluate(RUN_STATUSES)
    state = await page.evaluate(PIPELINE_STATE)
    journal.check(
        "a second PIPELINE pass is answered 409, and the pipeline goes on RUNNING "
        "— not demoted to a queue",
        statuses[-1:] == [409] and state == "running",
        f"runPipeline answered {statuses}, status read says {state!r}")
    said = await page.evaluate(SAID)
    refusal = VERB_SENTENCES.get("pipelineAlreadyRunning")
    journal.check(
        "and the refusal is said in its own sentence, never « arrêté »",
        refusal is not None and said == refusal and said != VERB_SENTENCES["pipelineStopped"],
        f"said « {said} », the refusal sentence is {refusal!r}")


async def queued_behind_maintenance(journal, page):
    """Starts a pass while a maintenance run holds the lock.

    Args:
        journal: The rule's journal.
        page: A freshly opened page, its pipeline idle.
    """
    launched = await page.evaluate(LAUNCH_MAINTENANCE)
    if not await press(journal, page, '[data-page="arr"]',
                       "with a maintenance run in flight, Arrivées is reached by a finger"):
        return
    await page.wait_for_timeout(SETTLED)
    if not await press(journal, page, START, "and « Lancer le pipeline » is pressed"):
        return
    await page.wait_for_timeout(ACTED)
    statuses = await page.evaluate(RUN_STATUSES)
    state = await page.evaluate(PIPELINE_STATE)
    said = await page.evaluate(SAID)
    journal.check(
        "a pass asked while a MAINTENANCE run holds the lock is answered and QUEUED, "
        "and the queued sentence says so",
        launched == 202 and statuses == [200] and state == "queued"
        and said == VERB_SENTENCES["pipelineQueued"],
        f"maintenance launch {launched}, runPipeline answered {statuses}, "
        f"status {state!r}, said « {said} »")


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
        browser = await playwright.chromium.launch(channel="chrome")
        errors: list[str] = []
        opened: list[str] = []
        for steps in ((walk, refused_while_running), (queued_behind_maintenance,)):
            context, page = await fresh_page(browser)
            page.on("pageerror", lambda error: errors.append(str(error)))
            for step in steps:
                await step(journal, page)
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
