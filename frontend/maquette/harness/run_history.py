"""R182 — the passages: a row is a path, the line is COMPOSED, and a short list admits it.

TWO HALVES, AND THIS FILE SAYS WHICH IS WHICH. The LIST's holds are here and
they are the ones below. The DETAIL's holds — a run's steps, its reasons, its
remaining steps drawn as unknown — belong to the screen a row leads to, and they
are added to this same file when that screen exists: one subject, one rule.

WHAT THE LIST IS HELD TO:

  1. A ROW LEADS TO ITS OWN ADDRESS. Tapped by a finger, the URL becomes
     `/run/<uid>` — read on the URL, never on a screen appearing. A row that
     looks like a control and goes nowhere is the defect this reads for.
  2. THE LINE IS COMPOSED FROM THE COUNTS, not received as a sentence. The
     narrative is the interface's, built from codes and figures; French off the
     wire is what the demand register exists to stop. So the hold reads the
     layer's own counts and refuses a line they do not produce.
  3. `degraded` IS SAID, above the rows it qualifies. A list that may be short
     drawn as a complete one is NE-DOIT-PAS-5 exactly.
  4. THE EMPTY LIST IS SAID. « Aucun passage enregistré. » — a heading over
     nothing is not an answer, and a fresh install is a real state.
  5. THE TRIGGER IS IN WORDS. `watcher` reads « la veille », `web` reads « depuis
     l'interface ». A legend that teaches the reader a vocabulary is a standing
     refusal: the row says the thing itself.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# THE STATES OF THE LIST, by the id `window.__go` takes.
LIST = "runs-list"
EMPTY = "runs-empty"
DEGRADED = "runs-degraded"

# WHAT THE SECTION AND ITS ROWS CARRY.
SECTION = "runs"
ROW = "runs/row"
DEGRADED_LINE = "runs/degraded"
EMPTY_LINE = "runs/empty"

# PRESSED AT ITS OWN CENTRE, after scrolling to it — a finger scrolls first, and
# `elementFromPoint` answers null outside the viewport.
PRESS_FIRST_ROW = """(part)=>{
  const row = document.querySelector(`[data-part="${part}"]`);
  if (!row) return {found: false, pressed: false, covered: ''};
  row.scrollIntoView({block: 'center'});
  const box = row.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
                                        box.top + box.height / 2);
  const mine = Boolean(hit) && (hit === row || row.contains(hit) || hit.contains(row));
  if (mine) row.click();
  return {found: true, pressed: mine, uid: row.dataset.run || '',
          covered: mine ? '' : ((hit && (hit.dataset.part || hit.tagName)) || 'nothing')};
}"""

# WHAT THE ADDRESS BAR SAYS — the claim D1 makes about a row that leads
# somewhere, and the one a screen appearing cannot make.
ADDRESS = """()=>location.pathname + location.search"""

# WHAT THE LAYER ANSWERED FOR THE LIST, so the line drawn can be compared
# against the figures it claims to be made of.
ANSWERED_RUNS = """async ()=>{
  const answer = await (await fetch('/api/pipeline/history')).json();
  return (answer.runs || []).map((run) => ({
    runUid: run.runUid,
    kind: run.kind,
    trigger: run.trigger,
    outcome: run.outcome,
    durationS: run.durationS,
    steps: (run.steps || []).map((step) => ({name: step.name,
                                             successCount: step.successCount,
                                             errorCount: step.errorCount,
                                             unmatchedCount: step.unmatchedCount})),
  }));
}"""

# WHAT A PART SAYS.
TEXT = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"]`);
  return node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# WHAT ONE PASSAGE'S ROW SAYS, found by the run it stands for.
ROW_TEXT = """(runUid)=>{
  const row = document.querySelector(`[data-run="${runUid}"]`);
  return row ? (row.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# HOW MANY ROWS ARE DRAWN.
ROW_COUNT = """(part)=>document.querySelectorAll(`[data-part="${part}"]`).length"""

# The words the triggers are said with — the interface's own, never a legend.
TRIGGER_WORDS = ("la veille", "depuis l'interface", "un téléchargement", "le planificateur",
                 "en ligne de commande", "le filet de sécurité")


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
    """Reads the passages: their rows, their line, their two bad cases."""
    journal = Journal("R182 — the passages: a row is a path, the line is composed, "
                      "and a short list admits it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # 1 — A ROW LEADS TO ITS OWN ADDRESS.
        await drive(journal, page, LIST)
        drawn = await page.evaluate(ROW_COUNT, ROW)
        journal.check("the passages are drawn as rows", drawn > 0, f"{drawn}")
        press = await page.evaluate(PRESS_FIRST_ROW, ROW)
        journal.check("a row is reachable by a finger", press["pressed"], f"{press}")
        await page.wait_for_timeout(ACTED)
        address = await page.evaluate(ADDRESS)
        journal.check("and it leads to that run's OWN address",
                      bool(press.get("uid")) and address.endswith(press["uid"]),
                      f"{address!r} for {press.get('uid')!r}")

        # 2 — THE LINE IS COMPOSED FROM THE COUNTS.
        await drive(journal, page, LIST)
        runs = await page.evaluate(ANSWERED_RUNS)
        # THE FIRST PIPELINE RUN, not the first row: the history lists
        # maintenance commands beside passages, and a maintenance run has no
        # dispatch step to count. Reading « the newest run » measured a `prime`
        # command and asked it for figures it never had.
        first = next((run for run in runs if run["kind"] == "pipeline"), None)
        dispatched = None
        if first is not None:
            for step in first["steps"]:
                if step["name"] == "dispatch":
                    dispatched = step["successCount"]
        line = None if first is None else await page.evaluate(ROW_TEXT, first["runUid"])
        journal.check("the layer answered runs with their counts",
                      first is not None and dispatched is not None,
                      f"{first['steps'] if first else None}")
        # THE FRAGMENT, NOT THE DIGIT. « the answered count appears somewhere in
        # the line » is satisfied by any other number in it — a mutation putting
        # 9 where the layer said 1 left the hold green, because the duration
        # « 1 min 44 » carried a 1. What the line must contain is the count IN
        # ITS OWN PHRASE, which is what « composed from the counts » means.
        composed = ("rien de nouveau" if dispatched == 0 else f"{dispatched} rangé")
        journal.check("and the row's line is made of THOSE figures",
                      bool(line) and dispatched is not None and composed in line,
                      f"{line!r} must carry {composed!r} (dispatch={dispatched})")

        # 5 — THE TRIGGER IS IN WORDS.
        journal.check("the trigger is said in words, never as a code",
                      bool(line) and any(word in line.lower() for word in TRIGGER_WORDS)
                      and (first is None or first["trigger"] not in line),
                      f"{line!r} for trigger={first['trigger'] if first else None!r}")

        # 3 — A LIST THAT MAY BE SHORT SAYS SO.
        await drive(journal, page, DEGRADED)
        said = await page.evaluate(TEXT, DEGRADED_LINE)
        rows = await page.evaluate(ROW_COUNT, ROW)
        journal.check("an incomplete list admits it", bool(said), f"{said!r}")
        journal.check("and it still draws the rows it did get", rows > 0, f"{rows}")

        # 4 — AND AN EMPTY ONE IS A SENTENCE, not a heading over nothing.
        await drive(journal, page, EMPTY)
        said = await page.evaluate(TEXT, EMPTY_LINE)
        rows = await page.evaluate(ROW_COUNT, ROW)
        journal.check("an empty list says so", bool(said) and "aucun" in said.lower(),
                      f"{said!r}")
        journal.check("and draws no row at all", rows == 0, f"{rows}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
