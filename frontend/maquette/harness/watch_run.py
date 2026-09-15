"""R180 — DOIT-6: the veille says what it found, from either place it is asked.

THE CLAUSE. « Relancer la veille » must give a SEQUENCE — asked, running, then
X detected, Y available, Z taken — and the button that asks for it must actually
ask. The register carried a veille half for a whole wave because the button
answered with a sentence and sent nothing: a verb is proved by what it MOVES,
never by what it says.

WHAT IS READ, and the four holds are four different claims:

  0. THE SEQUENCE IS SEEN BY A PERSON: pressed by a finger, the veille is
     ANSWERED (lancé), is drawn « En cours… » AT REST while the layer's run is
     still going (en cours), and then ends on its own and draws its figures
     (chiffré). A run that ended on its second read skipped the middle state.
  1. THE ACT LANDS FROM BOTH EMITTERS. The « ⋮ » sheet's panel and the levers
     section emit ONE verb, registered once, and each is pressed by a finger and
     read on the NETWORK. A verb that works from one surface and not the other
     is the half-repair this register row is made of.
  2. THE FIGURES DRAWN ARE THE ONES THE LAYER ANSWERED. The run's own detail is
     read through the layer's record, and the three numbers on screen are
     compared against it. A build printing three plausible numbers passes any
     hold that only counts that three numbers are there.
  3. THE ZERO CASE IS SAID, and it is a different drawing from the figures:
     « rien de nouveau » is an answer, and three zeros are not the same sentence.
  4. A DEAD RUN SAYS SO, LOUDLY, AND NOTHING CLAIMS SUCCESS OVER IT.
     NE-DOIT-PAS-1's own example, and the reason this hold reads the whole
     surface for a success word rather than only the block.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# THE STATES OF THE VEILLE, by the id `window.__go` takes.
IDLE = "watch-idle"
RUNNING = "watch-running"
FIGURES = "watch-figures"
NOTHING = "watch-nothing"
ERROR = "watch-error"

# WHERE THE « ⋮ » SHEET IS OPENED FROM: the acquisitions page, whose panel
# carries the veille's own facts and its button.
SHEET = "sheet-more"

# The two emitters, by the `data-part` each carries.
IN_LEVERS = "levers/watch-now"
IN_SHEET = "sheet/action"

# WHAT THE FIGURES BLOCK SAYS.
FIGURES_PART = "levers/figures"

# The words a success wears, for the hold that refuses one over a dead run.
SUCCESS_WORDS = ("terminé", "réussi", "fait", "détectés")

# PRESSED AT ITS OWN CENTRE, after scrolling to it: a finger scrolls first, and
# `elementFromPoint` answers null outside the viewport — which reads as « covered
# by nothing » and is really « not on screen ».
PRESS = """([part, verb])=>{
  const nodes = [...document.querySelectorAll(`[data-part="${part}"]`)];
  const control = verb ? nodes.find((one) => verb in one.dataset) : nodes[0];
  if (!control) return {found: false, pressed: false, covered: ''};
  control.scrollIntoView({block: 'center'});
  const box = control.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
                                        box.top + box.height / 2);
  const mine = Boolean(hit) && (hit === control || control.contains(hit)
                               || hit.contains(control));
  if (mine) control.click();
  return {found: true, pressed: mine,
          covered: mine ? '' : ((hit && (hit.dataset.part || hit.tagName)) || 'nothing')};
}"""

# WHAT THE LAYER ANSWERED, by operation.
ANSWERED = """(name)=>(window.__mocks?.answered?.() || [])
  .filter((call) => call.operationId === name)
  .map((call) => call.status + ' ' + call.method + ' ' + call.path)"""

# WHAT THE RUN THE VEILLE LAUNCHED HOLDS, asked of the layer itself. The figures
# on screen are compared against THIS, never against a seed read by name.
#
# IT IS FOUND BY WHAT LAUNCHED IT, not by « the most recent run »: the history
# holds real passages recorded long after the layer's frozen clock, so the
# newest row is one of THOSE, and a comparison against it would be measuring
# another run's counts — green or red for a reason having nothing to do with
# the veille.
COUNTS = """async ()=>{
  const detect = (window.__mocks?.answered?.() || [])
    .filter((call) => call.operationId === 'runDetection');
  if (detect.length === 0) return null;
  const runs = await (await fetch('/api/pipeline/history')).json();
  const launched = runs.runs.find((one) => one.runUid.startsWith('detection-'));
  if (!launched) return null;
  const detail = await (await fetch('/api/pipeline/history/' + launched.runUid)).json();
  const step = (detail.steps || [])[0];
  return step ? (step.counts || null) : null;
}"""

# THE INTERFACE'S OWN SENTENCES.
RESOURCES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "i18n" / "fr.json")
    .read_text(encoding="utf-8"))
SENTENCES = RESOURCES["screens"]["system"]
VERB_SENTENCES = RESOURCES["verbs"].get("system", {})

# THE MESSAGE THE LAST ACT RAISED.
MESSAGE = """()=>window.__toast?.read()?.message?.message || ''"""

# WHAT THE LAYER SAYS OF THE RUN THE VEILLE LAUNCHED: still going, or how it ended.
LAUNCHED_OUTCOME = """async ()=>{
  const runs = await (await fetch('/api/pipeline/history')).json();
  const launched = runs.runs.find((one) => one.runUid.startsWith('detection-'));
  return launched ? launched.outcome : null;
}"""

# HOW LONG A PERSON MAY WAIT FOR THE FIGURES, polled, in milliseconds.
FIGURES_WAIT = 20000
POLL = 500

# WHAT A PART SAYS.
TEXT = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  return node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# WHAT IS SAID ABOUT THE VEILLE, for the success-word hold: its own block and
# whatever message the act raised. NOT the whole page — the passages list says
# « réussi » about every run it holds, and reading that would make this hold
# fall over a sentence about something else entirely.
SAID = """()=>[...document.querySelectorAll('[data-part="levers/watch"], #toast')]
  .map((node) => node.textContent || '').join(' ')"""


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
    """Walks the veille from both of its buttons, and reads what it says."""
    journal = Journal("R180 — DOIT-6: the veille says what it found, from either "
                      "place it is asked")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # 1a — FROM THE LEVERS SECTION.
        await drive(journal, page, IDLE)
        press = await page.evaluate(PRESS, [IN_LEVERS, None])
        journal.check("the levers' veille button is reachable by a finger",
                      press["pressed"], f"{press}")
        await page.wait_for_timeout(ACTED)
        called = await page.evaluate(ANSWERED, "runDetection")
        journal.check("pressing it CALLS runDetection", bool(called), f"{called}")

        # 0 — EN COURS, AT REST, then CHIFFRÉ on its own.
        for moment in ("right after the press", "and still, a moment later"):
            said = await page.evaluate(TEXT, FIGURES_PART)
            outcome = await page.evaluate(LAUNCHED_OUTCOME)
            journal.check(f"{moment}: the veille is drawn RUNNING, and the layer's run is still going",
                          said == SENTENCES["watchRunning"] and outcome == "running",
                          f"{said!r}, the layer's run is {outcome!r}")
            await page.wait_for_timeout(SETTLED * 2)
        said = ""
        for _ in range(FIGURES_WAIT // POLL):
            said = await page.evaluate(TEXT, FIGURES_PART) or ""
            if said != SENTENCES["watchRunning"]:
                break
            await page.wait_for_timeout(POLL)
        outcome = await page.evaluate(LAUNCHED_OUTCOME)
        journal.check("and it ENDS on its own, drawing its figures, with no state driven",
                      outcome == "success" and "détectés" in said,
                      f"{said!r}, the layer's run is {outcome!r}")

        # 1b — AND FROM THE « ⋮ » SHEET, the emitter that sent nothing.
        await drive(journal, page, SHEET)
        await page.wait_for_timeout(PANEL_IN)
        press = await page.evaluate(PRESS, [IN_SHEET, "watchNow"])
        journal.check("the sheet's veille button is reachable by a finger",
                      press["pressed"], f"{press}")
        await page.wait_for_timeout(ACTED)
        called = await page.evaluate(ANSWERED, "runDetection")
        journal.check("pressing THAT one CALLS runDetection too", bool(called), f"{called}")
        # AND IT ANSWERS WHERE THE FINGER PRESSED (DOIT-4): the sheet draws no
        # run, so the act's own message is the only thing a person there sees.
        message = await page.evaluate(MESSAGE)
        journal.check("and the sheet's press is answered on its surface, in the verb's sentence",
                      bool(VERB_SENTENCES.get("watchLaunched")) and message == VERB_SENTENCES.get("watchLaunched"),
                      f"said {message!r}, expected {VERB_SENTENCES.get('watchLaunched')!r}")

        # 2 — THE FIGURES DRAWN ARE THE LAYER'S.
        await drive(journal, page, FIGURES)
        await page.wait_for_timeout(ACTED)
        counts = await page.evaluate(COUNTS)
        said = await page.evaluate(TEXT, FIGURES_PART)
        journal.check("the run the veille launched carries counts",
                      isinstance(counts, dict) and bool(counts), f"{counts}")
        journal.check("and every one of them is DRAWN, as the layer answered it",
                      bool(said) and isinstance(counts, dict)
                      and all(str(value) in said for value in counts.values()),
                      f"{said!r} against {counts}")

        # 3 — THE ZERO CASE IS SAID, and it is another sentence.
        await drive(journal, page, NOTHING)
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate(TEXT, FIGURES_PART)
        journal.check("a veille that found nothing says so",
                      bool(said) and "rien de nouveau" in said.lower(), f"{said!r}")

        # 4 — A DEAD RUN SAYS SO, AND NOTHING CLAIMS SUCCESS OVER IT.
        await drive(journal, page, ERROR)
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate(TEXT, FIGURES_PART)
        journal.check("a veille that failed says so", bool(said)
                      and any(word in said.lower() for word in ("pas pu", "échou", "erreur")),
                      f"{said!r}")
        whole = await page.evaluate(SAID)
        found = [word for word in SUCCESS_WORDS if word in whole.lower()]
        journal.check("and nothing on the surface claims it succeeded", found == [],
                      f"{found}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
