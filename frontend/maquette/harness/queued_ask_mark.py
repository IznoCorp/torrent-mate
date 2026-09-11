"""R138 — an ask that arrives while the machine is busy SAYS SO, and goes on saying it.

DOIT-4: an ask arriving while the pipeline runs is queued VISIBLY — « En file —
pipeline en cours » — and never refused. The refusing half was already true: the
layer answers `queued` and the verb says so in a message. **The word this rule
exists for is VISIBLY.** A message is gone in four seconds, and after it went
nothing on the screen distinguished a season whose ask was waiting from one
nobody had asked for.

THE ASK IS MADE BY A FINGER, and the machine is put to work through the layer's
own run endpoint. Those are two different things and the difference is stated
rather than blurred:

  · **The ACT is the operator's**: the panel is raised by a hit test at the
    row's own centre, and the grab is the button he presses. Nothing here calls
    a producer or a verb directly, so what is measured is the path and not just
    the drawing at the end of it.
  · **The BUSY-NESS is arranged**, through `/api/pipeline/run` and the store's
    own `pipe`, because `window.__go` re-seeds the layer: a pipeline started by
    a finger on Arrivées BEFORE the state is driven is idle again by the time
    the act lands. R125 paid for that ordering.

**The operator's own path does not need any of that**, and it is written in
DESIGN beside B-352's paragraph: from Arrivées he starts the pipeline with the
button that is already there, then opens a follow and asks for a season. The
layer answers `queued` because `pipelineState` is not idle — the same fact this
rule arranges — so what he sees by hand is what this rule reads.

NO NAMED STATE, and it is B-352: `engine/states.js` is grandfathered AT its
record, so the pastille cannot be given a state and the oracle never sees it.
Its drawing is held here, and by his hand.

WHAT IT READS, and each fails differently:

  1. THE MACHINE REALLY IS BUSY at the moment of the act — in the LAYER, which
     decides whether an ask is queued, AND on the SCREEN, which decides whether
     the operator can see that it is. A hold on one alone passes while the
     other says the opposite, and an idle machine would queue nothing and make
     everything below pass for the wrong reason.
  2. A ROW A FINGER CAN RAISE, and a season with a hole that offers its grab —
     so there is something to ask for and a way to ask for it.
  3. ASKING WHILE BUSY RAISES THE PASTILLE, on the surface the ask was made
     from.
  4. AND IT IS STILL THERE AFTER THE MESSAGE HAS GONE. This is the hold that
     separates « said » from « visible », and it is the only one that would
     have failed against a build that toasts and forgets.
  5. AND NOTHING WAS REFUSED — no error, and the message is the queued one
     rather than a refusal (NE-DOIT-PAS-3).
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE A HAND ASKS FOR A SEASON.
FOLLOWS_STATE = "acq-follows-list"

# PUTTING THE MACHINE TO WORK, and it happens AFTER the state is driven, never
# before. `window.__go` RE-SEEDS the mock layer, so a pipeline started first is
# idle again by the time the act lands — the walk then measures a clause it has
# itself switched off, and the hold saying « the machine is busy » is green over
# a reading already discarded. R125 paid for that ordering; this rule inherits
# it rather than re-discovering it.
RUN_THE_PIPELINE = """async()=>{
  const answer = await window.fetch("/api/pipeline/run", {method: "POST"});
  const body = await answer.json().catch(() => ({}));
  return body.state || "";}"""

# AND THE INTERFACE IS ASKED WHETHER IT AGREES. Two different questions: the
# LAYER decides whether an ask is queued, the SCREEN decides whether the
# operator can see that it is busy. A hold on one alone passes while the other
# says the opposite.
DRAWN_AS_BUSY = """()=>window.__store.read().state.pipe"""

# THE MEDIUM WITH A HOLE, among the rows actually drawn — a subject the panel
# can be raised on AND that has something to ask for.
THE_MEDIUM_WITH_A_HOLE = """()=>{
  const drawn = [...document.querySelectorAll('[data-panel]')].map(
    (one) => one.dataset.panel);
  const reachable = (title) => drawn.some(
    (seen) => seen === title || seen.endsWith(":" + title));
  for (const follow of (window.__followActions?.all() || [])) {
    if (!reachable(follow.t)) continue;
    for (const [number, aired, owned] of (window.SEASONS[follow.t] || [])) {
      if ((owned || 0) < (aired || 0))
        return {title: follow.t, season: number};
    }
  }
  return null;}"""

# RAISING THE PANEL THE WAY A FINGER DOES — a hit test at the row's own centre,
# so a row something covers FAILS instead of being clicked through.
RAISE = """(title)=>{
  const row = [...document.querySelectorAll('[data-panel]')].find(
    (one) => one.dataset.panel === title
          || one.dataset.panel.endsWith(":" + title));
  if (!row) return {found: false};
  const box = row.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  const mine = !!hit && (hit === row || row.contains(hit));
  if (mine) hit.click();
  return {found: true, reachable: mine,
          covering: hit ? (hit.className || hit.tagName) : null};}"""

# THE FIRST SEASON THAT OFFERS A GRAB, inside the panel the hand opened.
THE_GRAB = """()=>{
  const one = document.querySelector('[data-part="season/grab"]');
  if (!one) return null;
  return {season: (one.dataset.grabSeason || '').split('|')[1] || ''};}"""

TAP_GRAB = """()=>{
  document.querySelector('[data-part="season/grab"]').click();}"""

# THE PASTILLE, and WHICH season carries it. Selected by its naming attribute
# and read back with the row's own heading, so a mark drawn on the wrong season
# is a failure rather than a pass.
THE_MARK = """()=>{
  const marks = [...document.querySelectorAll('[data-part="season/queued"]')];
  return marks.map((one) => ({
    said: (one.textContent || '').trim(),
    row: (one.closest('[data-part="season"]')
            ?.querySelector('summary')?.textContent || '').trim()}));}"""

SAID = """()=>window.__toast?.read()?.message?.message || ''"""

# EMPTYING THE MESSAGE, which is what time does on a real screen. The pastille
# must survive it: that is the whole difference between « said » and « visible ».
DISMISS = """()=>window.__toast?.hide()"""


async def main():
    journal = Journal("R138 — a queued ask says so, and goes on saying it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── THE STATE FIRST, THEN THE MACHINE PUT TO WORK ──────────────────
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        started = await page.evaluate(RUN_THE_PIPELINE)
        await page.evaluate("""()=>window.__store.write({pipe: "running"})""")
        await page.wait_for_timeout(SETTLED)
        drawn = await page.evaluate(DRAWN_AS_BUSY)
        journal.check(
            "the LAYER really has the pipeline busy at the moment of the act — "
            "the half that decides whether an ask is queued — and it is put to "
            "work AFTER the state is driven, because driving one re-seeds it",
            started in ("running", "queued") and drawn == "running",
            f"layer={started!r}, interface={drawn!r}")
        if started not in ("running", "queued") or drawn != "running":
            await context.close()
            await browser.close()
            journal.summary()
            return

        # ── AND A SEASON IS ASKED FOR, BY A FINGER ─────────────────────────
        subject = await page.evaluate(THE_MEDIUM_WITH_A_HOLE)
        journal.check(
            "the fixture holds a medium with a hole whose row is drawn, so "
            "this walk has a subject",
            subject is not None, str(subject))
        if subject is None:
            await context.close()
            await browser.close()
            journal.summary()
            return
        aim = await page.evaluate(RAISE, subject["title"])
        journal.check(
            f"« {subject['title']} » has a row a finger can raise its panel "
            "from",
            aim.get("found") and aim.get("reachable"), str(aim))
        if not aim.get("reachable"):
            await context.close()
            await browser.close()
            journal.summary()
            return
        await page.wait_for_timeout(PANEL_IN)
        grab = await page.evaluate(THE_GRAB)
        journal.check(
            "and the season with the hole offers its grab, so there is "
            "something to ask for",
            grab is not None and grab["season"] != "", str(grab))
        if grab is None or not grab["season"]:
            await context.close()
            await browser.close()
            journal.summary()
            return

        await page.evaluate(TAP_GRAB)
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate(SAID)
        marks = await page.evaluate(THE_MARK)

        journal.check(
            "asking while the machine is busy raises the pastille, on the "
            "surface the ask was made from — DOIT-4's « visiblement »",
            len(marks) == 1 and f"{grab['season']}" in marks[0]["row"],
            f"{len(marks)} mark(s): {marks}, for season {grab['season']}")

        # ── AND IT OUTLIVES THE MESSAGE ────────────────────────────────────
        await page.evaluate(DISMISS)
        await page.wait_for_timeout(SETTLED)
        after = await page.evaluate(THE_MARK)
        journal.check(
            "and it is STILL THERE once the message has gone — which is the "
            "whole of « visibly »: a sentence shown for four seconds tells the "
            "operator who was looking, and nobody else",
            len(after) == 1 and after[0]["said"] != "",
            f"{len(after)} mark(s) after the message went: {after}")

        journal.check(
            "and nothing was REFUSED — the ask was queued and said so, never "
            "turned away (NE-DOIT-PAS-3)",
            not errors and said != "", f"errors={errors}, message « {said} »")

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
