"""R182 — the passages: a row is a path, the line is COMPOSED, and a short list admits it.

TWO HALVES, AND THIS FILE SAYS WHICH IS WHICH. The LIST's holds are 1 to 5;
the DETAIL's — the screen a row leads to — are 6 to 8. One subject, one rule:
the list says a run happened, the detail says what happened in it, and both are
read against the same answer.

WHAT THE LIST IS HELD TO:

  1. A ROW LEADS TO ITS OWN ADDRESS. Tapped by a finger, the URL becomes
     `/run/<uid>` — read on the URL, never on a screen appearing. A row that
     looks like a control and goes nowhere is the defect this reads for.
  2. THE LINE IS COMPOSED FROM THE COUNTS, not received as a sentence. The
     narrative is the interface's, built from codes and figures; French off the
     wire is what the demand register exists to stop. So the hold reads the
     layer's own counts and refuses a line they do not produce.
  2b. A DURATION UNDER AN HOUR IS SAID TO THE SECOND. « 1 min 44 », never the
     « 2 min » a rounding to the minute made of 104 s.
  3. `degraded` IS SAID, above the rows it qualifies. A list that may be short
     drawn as a complete one is NE-DOIT-PAS-5 exactly.
  4. THE EMPTY LIST IS SAID. « Aucun passage enregistré. » — a heading over
     nothing is not an answer, and a fresh install is a real state.
  5. THE TRIGGER IS IN WORDS. `watcher` reads « la veille », `web` reads « depuis
     l'interface ». A legend that teaches the reader a vocabulary is a standing
     refusal: the row says the thing itself.

WHAT THE DETAIL IS HELD TO:

  6. ONE ROW PER STEP THE LAYER ANSWERED, in its order, and each row's counts
     are THOSE counts, each in its own phrase (« 3 réussis », « 79 ignorés »).
     A digit found anywhere in the row is not a count: any other number
     satisfies it.
  7. `reasons[]` ARE DRAWN AS LINES, as many as the step recorded, verbatim —
     §8's « chaque rien a sa raison ». A reason is data displayed, not copy.
  8. A RUN STILL GOING DOES NOT ANSWER FOR ITS FUTURE. The live step says it is
     under way, and every step the run has not reached is drawn as unknown
     (« — ») — never « pas faite », never a count. §13: a part not yet known is
     not printed as an answer.
"""
import asyncio
import json
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
# EVERY ROW'S OUTCOME WORD AND LINE, with what the layer answered for it.
ROWS_SAID = """async ()=>{
  const answer = await (await fetch('/api/pipeline/history')).json();
  return (answer.runs || []).map((run) => {
    const row = document.querySelector(`[data-run="${run.runUid}"]`);
    const said = (part) => {
      const node = row && row.querySelector(`[data-part="${part}"]`);
      return node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null;
    };
    return {runUid: run.runUid, command: run.command, outcome: run.outcome,
            detected: ((run.steps || [])[0] || {}).counts?.detected ?? null,
            word: said('runs/outcome'), line: said('runs/line')};
  });
}"""

# THE WORDS THE LIST SAYS, from the interface's own resources.
SENTENCES = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "i18n" / "fr.json")
    .read_text(encoding="utf-8"))["screens"]["system"]
OUTCOME_WORDS = {"success": "runSucceeded", "error": "runFailed", "running": "runRunning",
                 "killed": "runKilled", "paused": "runPaused"}

ROW_TEXT = """(runUid)=>{
  const row = document.querySelector(`[data-run="${runUid}"]`);
  return row ? (row.textContent || '').replace(/\\s+/g, ' ').trim() : null;
}"""

# HOW MANY ROWS ARE DRAWN.
ROW_COUNT = """(part)=>document.querySelectorAll(`[data-part="${part}"]`).length"""

# THE STATES OF A PASSAGE'S SCREEN.
DETAIL = "run-detail"
RUNNING = "run-detail-running"

# WHAT THE LAYER ANSWERED FOR THE RUN ON SCREEN, read by the address the screen
# is at — never by a uid written here, which would read a run the screen is not
# showing and agree with it.
ANSWERED_RUN = """async ()=>{
  const uid = decodeURIComponent(location.pathname.split('/').pop());
  const answer = await fetch('/api/pipeline/history/' + uid);
  if (!answer.ok) return null;
  const run = await answer.json();
  if (!run) return null;
  return {runUid: run.runUid, outcome: run.outcome,
          steps: (run.steps || []).map((step) => ({
            name: step.name, status: step.status,
            successCount: step.successCount ?? 0, skipCount: step.skipCount ?? 0,
            errorCount: step.errorCount ?? 0, unmatchedCount: step.unmatchedCount ?? 0,
            reasons: step.reasons || []}))};
}"""

# WHAT THE SCREEN DREW, step by step.
DRAWN_STEPS = """()=>[...document.querySelectorAll('[data-part="run/step"]')].map((row) => {
  const text = (node) => node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null;
  return {
    name: row.dataset.step || null,
    status: text(row.querySelector('[data-part="run/step-status"]')),
    counts: text(row.querySelector('[data-part="run/step-counts"]')),
    reasons: [...row.querySelectorAll('[data-part="run/reason"]')].map(text),
    whole: text(row),
  };
})"""

# EACH COUNT AND THE PHRASE IT IS SAID IN — the singular stem, so « 1 réussi »
# and « 3 réussis » both carry it and « 3 ignorés » does not.
COUNT_PHRASES = (("successCount", "réussi"), ("skipCount", "ignoré"),
                 ("errorCount", "en erreur"), ("unmatchedCount", "non identifié"))

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
    """Reads the passages: their rows, their line, their bad cases, and a run's detail."""
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

        # 2b — A DURATION UNDER AN HOUR SAYS ITS SECONDS. Rounded to the minute,
        # the seed's 104 s passage read « 2 min » and its 439 s one « 7 min »:
        # each is found by the length the layer answered, and its row must say
        # that length to the second — « 1 min 44 », « 7 min 19 ».
        for length, said in ((104, "1 min 44"), (439, "7 min 19")):
            timed = next((run for run in runs
                          if run["durationS"] is not None and round(run["durationS"]) == length), None)
            row_line = None if timed is None else await page.evaluate(ROW_TEXT, timed["runUid"])
            journal.check(f"the {length} s passage's row says « {said} », to the second",
                          bool(row_line) and said in row_line,
                          f"{row_line!r} for {timed and timed['runUid']!r}")

        # 5 — THE TRIGGER IS IN WORDS.
        journal.check("the trigger is said in words, never as a code",
                      bool(line) and any(word in line.lower() for word in TRIGGER_WORDS)
                      and (first is None or first["trigger"] not in line),
                      f"{line!r} for trigger={first['trigger'] if first else None!r}")

        # 6 — THE OUTCOME WORD IS THE OUTCOME'S (NE-DOIT-PAS-1). A run still
        # going is never « réussi », and a detection's line says what it
        # detected — never « rien de nouveau » over a count.
        await drive(journal, page, "watch-running")
        rows = await page.evaluate(ROWS_SAID)
        going = [row for row in rows if row["outcome"] == "running"]
        journal.check("a run still going is listed, so the non-terminal word has a subject",
                      bool(going), f"{[row['outcome'] for row in rows]}")
        for row in going + [row for row in rows if row["outcome"] != "running"][:1]:
            expected = SENTENCES.get(OUTCOME_WORDS[row["outcome"]])
            journal.check(f"the {row['outcome']} row {row['runUid'][:8]} says its own outcome word",
                          bool(expected) and row["word"] == expected,
                          f"said {row['word']!r}, expected {expected!r}")
        detections = [row for row in rows
                      if row["command"] == "follow-detect" and row["detected"]]
        journal.check("a detection that counted something is listed", bool(detections),
                      f"{[(row['command'], row['detected']) for row in rows]}")
        for row in detections:
            phrase = (SENTENCES.get("detectedCount_other") or "").replace(
                "{{count}}", str(row["detected"]))
            journal.check(f"detection {row['runUid'][:8]}'s line says what it detected, "
                          "never « rien de nouveau »",
                          bool(phrase) and phrase in (row["line"] or "")
                          and SENTENCES["runNothing"] not in (row["line"] or ""),
                          f"line {row['line']!r}, expected {phrase!r}")

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

        # 6 — ONE ROW PER STEP, AND ITS COUNTS ARE THE LAYER'S.
        await drive(journal, page, DETAIL)
        run = await page.evaluate(ANSWERED_RUN)
        drawn = await page.evaluate(DRAWN_STEPS)
        answered_names = [step["name"] for step in (run or {}).get("steps", [])]
        journal.check("the detail draws one row per step the layer answered, in its order",
                      bool(answered_names) and [row["name"] for row in drawn] == answered_names,
                      f"drawn {[row['name'] for row in drawn]} · answered {answered_names}")
        wrong = []
        for step in (run or {}).get("steps", []):
            row = next((one for one in drawn if one["name"] == step["name"]), None)
            for field, phrase in COUNT_PHRASES:
                if step[field] and (row is None or f"{step[field]} {phrase}" not in (row["counts"] or "")):
                    wrong.append(f"{step['name']}: {step[field]} {phrase} not in "
                                 f"{row and row['counts']!r}")
        journal.check("and each step's counts are THOSE counts, each in its own phrase",
                      bool(answered_names) and not wrong, "; ".join(wrong[:4]))

        # 7 — THE REASONS, AS MANY AS RECORDED, VERBATIM.
        missing = []
        for step in (run or {}).get("steps", []):
            row = next((one for one in drawn if one["name"] == step["name"]), None)
            said = (row or {}).get("reasons", [])
            if len(said) != len(step["reasons"]):
                missing.append(f"{step['name']}: {len(said)} drawn, {len(step['reasons'])} recorded")
            elif any(" ".join(reason.split()) not in (line or "") for reason, line in zip(step["reasons"], said)):
                missing.append(f"{step['name']}: a reason is not drawn as recorded")
        journal.check("the reasons are drawn as lines, as many as recorded, verbatim",
                      any(step["reasons"] for step in (run or {}).get("steps", [])) and not missing,
                      "; ".join(missing[:4]))

        # 8 — A RUN STILL GOING DOES NOT ANSWER FOR ITS FUTURE.
        await drive(journal, page, RUNNING)
        run = await page.evaluate(ANSWERED_RUN)
        drawn = await page.evaluate(DRAWN_STEPS)
        steps = (run or {}).get("steps", [])
        journal.check("the layer answers the run as still going",
                      bool(run) and run["outcome"] == "running", f"{run and run['outcome']!r}")
        live = next((step for step in steps if step["status"] == "running"), None)
        live_row = next((row for row in drawn if live and row["name"] == live["name"]), None)
        journal.check("the live step says it is under way",
                      bool(live_row) and "en cours" in (live_row["status"] or "").lower(),
                      f"{live_row and live_row['status']!r}")
        reached = {step["name"] for step in steps}
        ahead = [row for row in drawn if row["name"] not in reached]
        journal.check("the steps not yet reached are drawn",
                      len(ahead) > 0, f"{len(drawn)} drawn, {len(reached)} answered")
        journal.check("and each says « — », never « pas faite » and never a count",
                      bool(ahead) and all((row["status"] or "") == "—"
                                          and "pas faite" not in (row["whole"] or "").lower()
                                          and not any(ch.isdigit() for ch in (row["whole"] or ""))
                                          for row in ahead),
                      f"{[(row['name'], row['status']) for row in ahead]}")

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
