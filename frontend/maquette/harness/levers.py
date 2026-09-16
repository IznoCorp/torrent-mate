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

R178 ALSO HOLDS THE SECTION'S WORDS (B-534), because a lever whose words are
wrong acts on a reader who cannot tell what it does:

  4. THE GUIDANCE IS SAID ONCE. The host and the levers printed the same
     sentence one above the other; the screen carries it exactly once.
  5. THE TRIGGER'S CONTROL NAMES THE ACT. Its accessible name begins with the
     verb a press performs; the state it leaves is read BESIDE it, never as the
     control's label.
  6. NOTHING ON THE SECTION SPEAKS BACKEND (NE-DOIT-PAS-4). No text of the
     pipeline section, in any of its states, contains « serveur ».

R181 — §13, NO ANSWER THAT IS NOT HELD. Under the `loading` phase the bound, the
lock and the trigger carry no printed value: not a zero, not a default, not
« Libre » before the read answered. A bound printed as `0` while its read is in
flight is a lie in waiting.
"""
import asyncio
import json
import pathlib
import re
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
WATCHER_STATE = "levers/watcher-state"
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

# WHAT THE WHOLE PIPELINE SECTION SAYS, host and levers together.
PANEL_TEXT = """()=>{
  const node = document.querySelector('[data-part="pipeline-panel"]');
  return node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# A CONTROL'S ACCESSIBLE NAME, as assistive technology computes it for a button
# with no label of its own: its `aria-label`, else its text.
ACCESSIBLE_NAME = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  if (!node) return null;
  return (node.getAttribute('aria-label') || node.textContent || '').replace(/\\s+/g, ' ').trim();
}"""

# THE VERBS A TRIGGER'S PRESS PERFORMS, the first word of its accessible name.
ACT_VERBS = ("Activer", "Désactiver")

# THE WORD A BACKEND SENTENCE WEARS (NE-DOIT-PAS-4).
BACKEND_WORD = "serveur"

# WHAT THE PIPELINE IS DOING, asked of the layer rather than read off the
# screen: « the state moved » is a claim about the machine, and the screen is
# what this rule is trying to prove FOLLOWS it.
PIPELINE_STATE = """async ()=>(await (await fetch('/api/pipeline/status')).json()).state"""

# WHETHER THE AUTOMATIC TRIGGER IS ON, asked of the layer: « setWatcher was
# called » is true of a press that sent the wrong value, so the hold reads the
# state the press left.
WATCHER_ENABLED = """async ()=>(await (await fetch('/api/pipeline/status')).json()).watcherEnabled"""

# THE INTERFACE'S OWN SENTENCES, read from its resources rather than retyped.
DESIGN = pathlib.Path(__file__).resolve().parent.parent / "design" / "src"
SENTENCES = json.loads((DESIGN / "i18n" / "fr.json").read_text(encoding="utf-8"))["screens"]["system"]

# THE BOUND'S OWN SETTING, named by the key the section reads, and what the
# settings seed holds for it. The section draws the seed's value when it holds
# one, and says the setting is owed when it does not — so a figure printed
# there that no seed holds is the §13 lie this reads for.
BOUND_KEY = re.search(r'const BOUND_KEY = "([^"]+)"',
                      (DESIGN / "features" / "system" / "queries.ts").read_text(encoding="utf-8")).group(1)
SEEDED_BOUND = [
    setting.get("raw")
    for topic in json.loads((DESIGN / "mocks" / "seeds" / "settings.json").read_text(encoding="utf-8"))
    for setting in topic.get("settings", [])
    if setting.get("key") == BOUND_KEY
]


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
        enabled = await page.evaluate(WATCHER_ENABLED)
        label = await page.evaluate(TEXT, WATCHER)
        said = await page.evaluate(TEXT, WATCHER_STATE)
        journal.check("and the trigger is OFF afterwards, on the layer, on its state and on the control",
                      enabled is False and said is not None
                      and said.endswith(SENTENCES["triggerOff"])
                      and label == SENTENCES["turnTriggerOn"],
                      f"watcherEnabled={enabled}, state says {said!r}, control says {label!r}")
        await page.evaluate(PRESS, WATCHER)
        await page.wait_for_timeout(ACTED)
        enabled = await page.evaluate(WATCHER_ENABLED)
        label = await page.evaluate(TEXT, WATCHER)
        said = await page.evaluate(TEXT, WATCHER_STATE)
        journal.check("and a second press turns it back ON, on the layer, on its state and on the control",
                      enabled is True and said is not None
                      and said.endswith(SENTENCES["triggerOn"])
                      and label == SENTENCES["turnTriggerOff"],
                      f"watcherEnabled={enabled}, state says {said!r}, control says {label!r}")

        # R178 4 — THE GUIDANCE IS SAID ONCE.
        await drive(journal, page, IDLE)
        panel = await page.evaluate(PANEL_TEXT) or ""
        guidance_line = SENTENCES["pipelineGuidance"]
        journal.check("the pipeline section says its guidance exactly once",
                      panel.count(guidance_line) == 1,
                      f"{panel.count(guidance_line)} time(s) « {guidance_line} »")

        # R178 5 — THE TRIGGER'S CONTROL NAMES THE ACT, in both of its states.
        for state in (IDLE, TRIGGER_OFF):
            await drive(journal, page, state)
            name = await page.evaluate(ACCESSIBLE_NAME, WATCHER)
            journal.check(f"on {state}, the trigger's control is named by the act a press performs",
                          bool(name) and name.split(" ")[0] in ACT_VERBS, f"{name!r}")

        # R178 6 — NOTHING ON THE SECTION SPEAKS BACKEND.
        for state in (IDLE, RUNNING, PAUSED, QUEUED, TRIGGER_OFF):
            await drive(journal, page, state)
            panel = await page.evaluate(PANEL_TEXT) or ""
            journal.check(f"on {state}, no text of the pipeline section says « {BACKEND_WORD} »",
                          bool(panel) and BACKEND_WORD not in panel.lower(),
                          f"…{panel[max(0, panel.lower().find(BACKEND_WORD) - 60):][:120]!r}"
                          if BACKEND_WORD in panel.lower() else f"{len(panel)} characters read")

        # R181 — WHEN READY, THE BOUND SAYS WHAT THE SEED HOLDS, and nothing else.
        await drive(journal, page, IDLE)
        expected = str(SEEDED_BOUND[0]) if SEEDED_BOUND else SENTENCES["boundOwed"]
        bound = await page.evaluate(TEXT, BOUND_VALUE)
        journal.check(f"{BOUND_VALUE} says what the settings seed holds for {BOUND_KEY} "
                      f"({'its value' if SEEDED_BOUND else 'no entry, so the setting is owed'})",
                      bound == expected, f"{bound!r}, expected {expected!r}")

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
        queued = await page.evaluate(TEXT, "levers/queued")
        journal.check("and its queueing is SAID, in the interface's own sentence",
                      bool(queued) and queued == SENTENCES["pipelineQueued"],
                      f"{queued!r}, expected {SENTENCES['pipelineQueued']!r}")

        # R181 — §13: what has not answered is not printed as an answer.
        await drive(journal, page, LOADING)
        # THE SECTION IS THERE AND IT IS WAITING: its place is drawn, and what
        # the read has not answered is not printed as an answer (§13).
        journal.check("the levers' place is drawn while the read is in flight",
                      await page.evaluate(SKELETON, LEVERS) is True,
                      f"{await page.evaluate(SKELETON, LEVERS)}")
        # THE LOCK IS READ HERE TOO, since the clause names it: « Libre » before
        # the locks read answered is the same lie as a bound printed as 0.
        journal.check("the lock's place is drawn while its read is in flight",
                      await page.evaluate(SKELETON, "locks") is True,
                      f"{await page.evaluate(SKELETON, 'locks')}")
        for part in (BOUND_VALUE, PAUSE, RESUME, WATCHER, "locks/pipeline"):
            text = await page.evaluate(TEXT, part)
            journal.check(f"{part} prints no value while the read is in flight",
                          text in (None, ""), f"{text!r}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
