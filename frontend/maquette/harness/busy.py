"""R124 — NE-DOIT-PAS-3: a legitimate action under a busy pipeline is ACCEPTED.

THE CLAUSE. « ne jamais répondre 409 ou « occupé » à une action légitime ».
`product-intent-map.md` reads it `partly`: R66 holds the pipeline PASS — asked
for during a run, it is queued and says so — and « every OTHER mutation under a
busy scenario » is **unproved**. This rule is that instrument, written with the
producers that offer those mutations.

WHAT IS READ, and the three questions are not the same one:

  1. THE ACT LANDS. The state moves — a follow is paused, a medium is taken, an
     edit is recorded. Read on the state, never on a message: a toast can be
     right about nothing, and an interface that says « fait » while the list is
     unchanged is NE-DOIT-PAS-1 rather than this clause.
  2. NOTHING ANSWERS 409. Read on the NETWORK, because that is where the
     refusal this clause names would arrive. A rule reading only the screen
     would pass a build that swallowed a 409 and drew the old value.
  3. NOTHING SAYS « occupé ». The word, and its neighbours, anywhere the
     interface put text after the act.

AND THE SCENARIO IS REALLY BUSY, checked before any of it: a walk that ran
against an idle pipeline would prove that the actions work, which nobody
doubts, and nothing about the clause.

WHAT IT DOES NOT READ: the resolve queue's own « En file » pastille, which is
DOIT-4's other half. **It does not exist** — measured, `grep "En file"` finds it
nowhere in `i18n/fr.json` and nowhere in the tree outside the pipeline pass's own
sentence — and drawing it is a behaviour change, which a conversion lot does not
carry. The clause map names its owner, rather than this rule pretending to cover it.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, PANEL_OUT, SETTLED, open_page

from playwright.async_api import async_playwright

# THE BUSY SCENARIO IS COMPOSED, and saying so is the point. `arr-running` has
# the pipeline running and NOTHING waiting to be taken; `acq-now-loaded` has two
# media waiting and an idle pipeline. The clause is about a legitimate action
# ASKED WHILE THE MACHINE IS BUSY, so the walk needs both at once: the state
# that has something to act on, with the pipeline put to work on top of it.
# Driving `arr-running` alone would have measured a page with no subject.
BUSY_STATE = "acq-now-loaded"

# THE WORDS A REFUSAL WEARS. « occupé » is the clause's own; the others are what
# the same refusal reads like when it is dressed differently.
REFUSALS = ("occupé", "occupee", "occupée", "déjà en cours", "réessayez plus tard")

QUEUE = """()=>({
  takeable: (window.__queue?.().takeable || []).map((one) => one.t),
  inFlight: (window.__queue?.().inFlight || []).map((one) => one.t),
  follows: (window.__followActions?.all() || []).map((one) => one.t)})"""

# THE MESSAGE LAYER IS `#toast`, and `[data-part="message"]` is emitted nowhere
# — `check-markup-contracts` said so, which is the three-ends contract caught
# from the markup end. The page itself is read beside it, because a refusal need
# not arrive as a message.
SAID = """()=>[...document.querySelectorAll('#toast, #view')]
  .map((node) => node.textContent || '').join(' ')"""


async def main():
    journal = Journal("R124 — NE-DOIT-PAS-3: a legitimate action is not refused")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        refused: list[str] = []
        page.on("response", lambda answer: refused.append(
            f"{answer.status} {answer.url}") if answer.status == 409 else None)

        await page.evaluate("(id)=>window.__go(id)", BUSY_STATE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("""()=>window.__store.write({pipe: "running"})""")
        await page.wait_for_timeout(SETTLED)
        running = await page.evaluate("()=>window.__store.read().state.pipe")
        journal.check(
            "the scenario really has the pipeline busy, so this walk measures "
            "the clause and not the actions",
            running == "running", str(running))

        before = await page.evaluate(QUEUE)
        journal.check(
            "and it really has something to act on",
            len(before["takeable"]) > 0 and len(before["follows"]) > 0,
            f"{len(before['takeable'])} takeable, {len(before['follows'])} followed")

        # ── TAKING A MEDIUM, from its own panel, while the pipeline runs ────
        title = before["takeable"][0]
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
        await page.wait_for_timeout(PANEL_IN)
        await page.evaluate(
            """()=>{const act = [...document.querySelectorAll(
                     '#sheetin [data-part="sheet/action"]')]
                     .find((one) => 'take' in one.dataset); if (act) act.click();}""")
        await page.wait_for_timeout(ACTED)
        after = await page.evaluate(QUEUE)
        journal.check(
            f"« {title} » is TAKEN while the pipeline runs — the act lands "
            "(NE-DOIT-PAS-3)",
            title in after["inFlight"] and title not in after["takeable"],
            f"{before['takeable']} → {after['takeable']}")

        # ── PAUSING A FOLLOW, from its own panel, while the pipeline runs ───
        watched = before["follows"][0]
        was = await page.evaluate(
            "(t)=>(window.__followActions?.all() || []).find((one) => one.t === t)?.st",
            watched)
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", watched)
        await page.wait_for_timeout(PANEL_IN)
        paused = await page.evaluate(
            """()=>{const act = [...document.querySelectorAll(
                     '#sheetin [data-part="sheet/action"]')]
                     .find((one) => 'pause' in one.dataset);
                    if (!act) return false; act.click(); return true;}""")
        await page.wait_for_timeout(ACTED)
        journal.check(
            f"« {watched} »'s panel offers to pause it while the pipeline runs",
            paused, watched)
        # THE STATE MOVED, whatever it moved TO. « paused » was this rule's
        # first guess and it is the app's `disabled` — the engine's own
        # `actionPause` toggles between `disabled` and the medium's resting
        # state. What the clause is about is that the act LANDED, so the hold
        # reads the CHANGE against what the status was before, and never a word
        # this file chose.
        state = await page.evaluate(
            "(t)=>(window.__followActions?.all() || []).find((one) => one.t === t)?.st",
            watched)
        journal.check(
            "and pausing LANDS — the state moved, not the message "
            "(NE-DOIT-PAS-3)",
            state is not None and state != was,
            f"{watched}: {was} → {state}")

        # ── AND NEITHER REFUSAL EVER ARRIVED ───────────────────────────────
        journal.check(
            "no mutation was answered 409 (NE-DOIT-PAS-3)",
            not refused, str(refused[:3]))
        said = (await page.evaluate(SAID)).lower()
        journal.check(
            "and nothing anywhere said the machine was busy",
            not any(word in said for word in REFUSALS),
            next((word for word in REFUSALS if word in said), ""))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
