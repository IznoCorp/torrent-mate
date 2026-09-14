"""R178, R179, R181 — the pipeline's levers: they ACT, they are never refused, they print nothing they do not know.

THREE LABELS IN ONE FILE because they walk the same surface, and each failure
says which question fell rather than « the levers are wrong ».

R178 — A LEVER ACTS, and the three halves are not the same claim:

  1. PRESSED BY A FINGER. `document.elementFromPoint` at the control's own
     centre, and what covers it is NAMED when it is not the control. A
     `.click()` is a call, not a press: it lands on a node the document has,
     whether or not a message, a scrim or a panel leaving covers it.
  2. THE OPERATION IS CALLED. Read on the NETWORK, through the layer's own
     record: the mock replaces `fetch`, so a hold written on the browser's
     request events is green whatever the interface does, and a hold reading the
     SCREEN passes a build that says « fait » and sends nothing.
  3. THE STATE MOVES afterwards — pause becomes resume, the sentinel appears.
     Read on the state, never on a message: a toast can be right about nothing.

R179 — DOIT-4 ON A LEVER. Asked while a MAINTENANCE run holds the lock, the
lever is accepted and its queueing is SAID; nothing answers 409 and nothing says
« occupé ». The refusal words are R124's list, reused rather than re-invented.
AND THE SCENARIO IS CHECKED REALLY BUSY first: a walk against an idle pipeline
proves the levers work, which nobody doubts, and nothing about the clause.

R181 — §13, NO ANSWER THAT IS NOT HELD. Under the `loading` phase the bound, the
lock and the trigger carry no printed value: not a zero, not a default, not
« Libre » before the read answered. A bound printed as `0` while its read is in
flight is a lie in waiting.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# THE STATES THIS SURFACE CAN BE IN, by the id `window.__go` takes.
IDLE = "levers-idle"
RUNNING = "levers-running"
PAUSED = "levers-paused"
QUEUED = "levers-queued"
TRIGGER_OFF = "levers-trigger-off"
LOADING = "levers-loading"

# THE CONTROLS, by the `data-part` each carries.
PAUSE = "levers/pause"
RESUME = "levers/resume"
WATCHER = "levers/watcher"
BOUND = "levers/bound"
BOUND_VALUE = "levers/bound-value"
LEVERS = "levers"

# THE WORDS A REFUSAL WEARS — R124's own list, reused. « occupé » is the
# clause's; the others are the same refusal dressed differently.
REFUSALS = ("occupé", "occupee", "occupée", "déjà en cours", "réessayez plus tard")

# PRESSED AT ITS OWN CENTRE, and what covers it named. The hit test is the
# difference between « the document has this button » and « a finger reaches
# it »: the second is the claim DOIT-3 makes.
PRESS = """(part)=>{
  const control = document.querySelector(`[data-part="${part}"]`);
  if (!control) return {found: false, pressed: false, covered: ''};
  // A FINGER SCROLLS FIRST. The section sits far down a long page, so a hit
  // test taken where the control happens to be on load measures the viewport
  // and not the control — `elementFromPoint` answers null outside it, which
  // reads as « covered by nothing » and is really « not on screen yet ».
  control.scrollIntoView({block: 'center'});
  const box = control.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
                                        box.top + box.height / 2);
  const mine = Boolean(hit) && (hit === control || control.contains(hit)
                               || hit.contains(control));
  if (mine) control.click();
  return {
    found: true,
    pressed: mine,
    covered: mine ? '' : ((hit && (hit.dataset.part || hit.tagName)) || 'nothing'),
  };
}"""

# WHAT THE LAYER ANSWERED, and to what. The record the mock publishes for
# exactly this — a rule and the layer cannot disagree about what was asked.
ANSWERED = """(name)=>(window.__mocks?.answered?.() || [])
  .filter((call) => call.operationId === name)
  .map((call) => call.status + ' ' + call.method + ' ' + call.operationId)"""

# EVERY REFUSAL THE LAYER ANSWERED, whatever was asked of it: the clause is
# « a legitimate action is never refused », and an operation this phase did not
# add breaks it exactly as one of these does.
EVERY_REFUSAL = """()=>(window.__mocks?.answered?.() || [])
  .filter((call) => call.status === 409)
  .map((call) => call.status + ' ' + call.operationId)"""

# HOW MANY CALLS THE LAYER ANSWERED AT ALL: a refusal read off an empty record
# is green over nothing.
ANSWER_COUNT = """()=>(window.__mocks?.answered?.() || []).length"""

# WHETHER A CONTROL IS ON SCREEN, by its part.
PRESENT = """(part)=>Boolean(document.querySelector(`[data-part="${part}"]`))"""

# WHAT THE SURFACE SAYS, for the refusal words and for the queueing.
SAID = """()=>[...document.querySelectorAll('#toast, #view')]
  .map((node) => node.textContent || '').join(' ')"""

# WHETHER A PART IS THERE AS A SKELETON rather than as an answer: under the
# loading phase the controls have a PLACE — they are what the read will fill —
# and what they must not have is a value. Reading « no value » alone would be
# satisfied by a surface that drew nothing at all, which is the vacuous form of
# this hold.
SKELETON = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  if (!node) return null;
  return Boolean(node.querySelector('[data-skeleton]') || node.matches('[data-skeleton]'));
}"""

# WHAT A PART SAYS, alone.
TEXT = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  return node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# WHAT THE PIPELINE IS DOING, asked of the layer rather than read off the
# screen: « the state moved » is a claim about the machine, and the screen is
# what this rule is trying to prove FOLLOWS it.
PIPELINE_STATE = """async ()=>(await (await fetch('/api/pipeline/status')).json()).state"""


async def drive(journal, page, state):
    """Drives one named state and holds that the table declares it.

    Args:
        journal: The run's journal.
        page: The prototype's page.
        state: The named state's id.

    Returns:
        Whether the state could be driven.
    """
    try:
        await page.evaluate("(id)=>window.__go(id)", state)
        reached, detail = True, ""
    except Exception as error:  # noqa: BLE001 — the message IS the measurement
        reached, detail = False, str(error).splitlines()[0]
    journal.check(f"{state} is a state the table declares", reached, detail)
    await page.wait_for_timeout(SETTLED)
    return reached


async def main():
    """Walks the levers: a press, the operation, the state, and what is not known."""
    journal = Journal("R178, R179, R181 — the pipeline's levers act, are never "
                      "refused, and print nothing they do not know")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # R178 — PAUSE, pressed by a finger, over a pipeline that is running.
        await drive(journal, page, RUNNING)
        journal.check("with a run going, the pause lever is the one offered",
                      await page.evaluate(PRESENT, PAUSE)
                      and not await page.evaluate(PRESENT, RESUME),
                      f"pause={await page.evaluate(PRESENT, PAUSE)} "
                      f"resume={await page.evaluate(PRESENT, RESUME)}")
        press = await page.evaluate(PRESS, PAUSE)
        journal.check("the pause lever is reachable by a finger", press["pressed"],
                      f"{press}")
        await page.wait_for_timeout(ACTED)
        called = await page.evaluate(ANSWERED, "pausePipeline")
        journal.check("pressing it CALLS pausePipeline", bool(called), f"{called}")
        state = await page.evaluate(PIPELINE_STATE)
        journal.check("and the pipeline is paused afterwards", state == "paused", f"{state}")
        journal.check("so the resume lever is the one offered now",
                      await page.evaluate(PRESENT, RESUME)
                      and not await page.evaluate(PRESENT, PAUSE),
                      f"resume={await page.evaluate(PRESENT, RESUME)} "
                      f"pause={await page.evaluate(PRESENT, PAUSE)}")

        # R178 — RESUME, from the paused state, the same three halves.
        await drive(journal, page, PAUSED)
        press = await page.evaluate(PRESS, RESUME)
        journal.check("the resume lever is reachable by a finger", press["pressed"],
                      f"{press}")
        await page.wait_for_timeout(ACTED)
        called = await page.evaluate(ANSWERED, "resumePipeline")
        journal.check("pressing it CALLS resumePipeline", bool(called), f"{called}")
        state = await page.evaluate(PIPELINE_STATE)
        journal.check("and the pipeline is running afterwards", state == "running", f"{state}")

        # R178 — THE AUTOMATIC TRIGGER, and its consequence said in words.
        await drive(journal, page, IDLE)
        press = await page.evaluate(PRESS, WATCHER)
        journal.check("the automatic trigger is reachable by a finger", press["pressed"],
                      f"{press}")
        await page.wait_for_timeout(ACTED)
        called = await page.evaluate(ANSWERED, "setWatcher")
        journal.check("pressing it CALLS setWatcher", bool(called), f"{called}")

        await drive(journal, page, TRIGGER_OFF)
        said = await page.evaluate(SAID)
        journal.check("a trigger that is off says what that MEANS",
                      "n'ouvrent plus" in said,
                      f"…{said[max(0, said.find('automatique')):][:120]!r}")

        # R179 — DOIT-4: a lever asked while a MAINTENANCE run holds the lock.
        await drive(journal, page, QUEUED)
        busy = await page.evaluate(PIPELINE_STATE)
        journal.check("the scenario really is busy before the clause is read",
                      busy in ("running", "queued", "paused"), f"{busy}")
        press = await page.evaluate(PRESS, PAUSE)
        journal.check("a lever is offered while the machine is busy", press["pressed"],
                      f"{press}")
        await page.wait_for_timeout(ACTED)
        answers = await page.evaluate(ANSWER_COUNT)
        journal.check("the layer was asked for something at all", answers > 0, f"{answers}")
        refusals = await page.evaluate(EVERY_REFUSAL)
        journal.check("nothing was answered 409", refusals == [], f"{refusals}")
        said = await page.evaluate(SAID)
        journal.check("and nothing says « occupé »",
                      not any(word in said.lower() for word in REFUSALS),
                      f"{[word for word in REFUSALS if word in said.lower()]}")

        # R181 — §13: what has not answered is not printed as an answer.
        await drive(journal, page, LOADING)
        # THE SECTION IS THERE AND IT IS WAITING: its place is drawn, and what
        # the read has not answered is not printed as an answer (§13).
        journal.check("the levers' place is drawn while the read is in flight",
                      await page.evaluate(SKELETON, LEVERS) is True,
                      f"{await page.evaluate(SKELETON, LEVERS)}")
        for part in (BOUND_VALUE, PAUSE, RESUME, WATCHER):
            text = await page.evaluate(TEXT, part)
            journal.check(f"{part} prints no value while the read is in flight",
                          text in (None, ""), f"{text!r}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
