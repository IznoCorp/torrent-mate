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

# WHERE A FOLLOW IS DRAWN. The acquisitions page lists what is in FLIGHT, so a
# followed medium that is not currently being acquired has no row there at all —
# which is why the pause half of this walk moves here rather than raising a
# panel nobody on that page could reach.
FOLLOWS_STATE = "acq-follows-list"

# THE WORDS A REFUSAL WEARS. « occupé » is the clause's own; the others are what
# the same refusal reads like when it is dressed differently.
REFUSALS = ("occupé", "occupee", "occupée", "déjà en cours", "réessayez plus tard")

QUEUE = """()=>({
  takeable: (window.__queue?.().takeable || []).map((one) => one.t),
  inFlight: (window.__queue?.().inFlight || []).map((one) => one.t),
  follows: (window.__followActions?.all() || []).map((one) => one.t)})"""

# THE THREE OPERATIONS THIS WAVE ADDED, by the operationId the contract names.
# The clause is about ANY legitimate ask arriving while the machine works, and
# these three did not exist when this rule was written — a rule that holds the
# clause for two verbs and not for the three added beside them holds the clause
# for the interface as it used to be.
ADDED_OPERATIONS = ("grabSeasonForFollow", "requeueJourney", "rescrapeJourney")

# WHAT THE LAYER ANSWERED, and to what. Read through the door the mocks publish
# for exactly this, so a rule and the layer cannot disagree about what was asked.
ANSWERED = """(names)=>(window.__mocks?.answered?.() || [])
  .filter((call) => names.includes(call.operationId))
  .map((call) => call.status + " " + call.method + " " + call.operationId)"""

# THE MESSAGE LAYER IS `#toast`, and `[data-part="message"]` is emitted nowhere
# — `check-markup-contracts` said so, which is the three-ends contract caught
# from the markup end. The page itself is read beside it, because a refusal need
# not arrive as a message.
SAID = """()=>[...document.querySelectorAll('#toast, #view')]
  .map((node) => node.textContent || '').join(' ')"""


# AND THE ACTION INSIDE THE PANEL, HIT-TESTED THE WAY THE ROW IS.
#
# THE RESIDUE THE FINGER-DRIVING DID NOT COVER. The row was already raised by a
# hit test — `elementFromPoint` at its own centre — while the action inside the
# panel it raised was still reached with `act.click()`, which is a call and not
# a press: it lands on a node the document has, whether or not anything covers
# it. A button under a message, under a scrim, or under a panel still leaving
# was invisible to this rule, and the clause it holds is precisely about acts
# that must LAND while the machine is busy.
#
# It returns what it found rather than a boolean, so a failure says whether the
# action was absent or covered, and by what.
PRESS_THE_ACTION = """(verb)=>{
  const act = [...document.querySelectorAll(
                '#sheetin [data-part="sheet/action"]')]
              .find((one) => verb in one.dataset);
  if (!act) return {found: false, pressed: false};
  const box = act.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  const mine = !!hit && (hit === act || act.contains(hit));
  if (mine) hit.click();
  return {found: true, pressed: mine,
          covering: hit ? (hit.className || hit.tagName) : null,
          inside: box.top >= 0 && box.bottom <= window.innerHeight};}"""


# A MEDIUM WITH A HOLE whose row is actually drawn — the walk needs both, and
# a subject chosen from the fixture alone can be one no row on this page shows.
THE_MEDIUM_WITH_A_HOLE = """()=>{
  const drawn = [...document.querySelectorAll('[data-panel]')].map(
    (one) => one.dataset.panel);
  const reachable = (title) => drawn.some(
    (seen) => seen === title || seen.endsWith(":" + title));
  for (const follow of (window.__followActions?.all() || [])) {
    if (!reachable(follow.t)) continue;
    for (const [, aired, owned] of (window.SEASONS[follow.t] || [])) {
      if ((owned || 0) < (aired || 0)) return {title: follow.t};
    }
  }
  return null;}"""

# PRESSING A CONTROL NAMED BY ITS `data-part`, hit-tested like everything else
# a finger reaches here. The sibling of `PRESS_THE_ACTION`, which finds a panel
# action by the VERB it carries; this one finds a control by its NAME, because
# the season's grab is named rather than verbed.
PRESS_THE_ACTION_BY_PART = """(part)=>{
  const act = document.querySelector('[data-part="' + part + '"]');
  if (!act) return {found: false, pressed: false};
  const box = act.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  const mine = !!hit && (hit === act || act.contains(hit));
  if (mine) hit.click();
  return {found: true, pressed: mine,
          covering: hit ? (hit.className || hit.tagName) : null};}"""

# WHERE THE ROW IS AND WHETHER A FINGER WOULD REACH IT — read, never assumed.
# `elementFromPoint` at the row's own centre answers what a tap there would
# actually hit, which is a different question from « is the node in the tree ».
AIM_AT_THE_ROW = """(title)=>{
  const row = [...document.querySelectorAll('[data-panel]')].find(
    (one) => one.dataset.panel === title
          || one.dataset.panel.endsWith(":" + title));
  if (!row) return {found: false};
  const box = row.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y,
          reachable: !!hit && (hit === row || row.contains(hit)),
          covering: hit === null ? "nothing" :
            (hit.tagName + (hit.className ? "." + String(hit.className).split(" ")[0] : ""))};}"""

# WHAT COVERS THE ROW IS TAKEN OUT OF THE WAY FIRST, and this is a DOM EDIT
# rather than a gesture — said plainly, because naming a thing for what it is
# not is the defect this same rule was repaired for one commit earlier. The
# prototype greets with a toast that sits over the surface (B-317) and a tap
# under it lands on the toast; no gesture dismisses that toast, so the rule
# empties the element instead. What it costs is stated too: this walk does not
# prove the toast can be dismissed, only that the row underneath is reachable
# once it is gone.
EMPTY_THE_TOAST = """()=>{const one = document.querySelector('#toast');
  if (!one) return false;
  one.textContent = "";
  one.className = "";
  one.removeAttribute("data-open");
  return true;}"""


async def raise_by_finger(page, title):
    """Raises a row's panel with a hit-tested tap, and says what it hit.

    IT USED TO BE `row.click()`, which walks the PATH and not the FINGER: a row
    covered by something else is invisible to a synthetic click, and the commit
    that introduced it claimed a real tap. A tap is a point on a screen, so this
    reads what is at that point before touching it.

    Args:
        page: The page.
        title: The subject the row's `data-panel` names.

    Returns:
        The aim's own reading, with `tapped` saying whether a finger went down.
    """
    await page.evaluate(EMPTY_THE_TOAST)
    aim = await page.evaluate(AIM_AT_THE_ROW, title)
    if aim["found"] and aim["reachable"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        aim["tapped"] = True
    else:
        aim["tapped"] = False
    return aim

async def main():
    journal = Journal("R124 — NE-DOIT-PAS-3: a legitimate action is not refused")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        refused: list[str] = []
        page.on("response", lambda answer: refused.append(
            f"{answer.status} {answer.url}") if answer.status == 409 else None)
        # WHAT THE THREE OPERATIONS THIS WAVE ADDED WERE ANSWERED is read from
        # the LAYER's own record, not from the network. A first version listened
        # for Playwright response events and saw NOTHING: the layer answers in
        # the page, so an ask that really happened produced no response event at
        # all, and the hold reading them was about to be green over an empty
        # list. R125 carries the same note about the same trap. The layer
        # records every call it answered, keyed by the operationId the contract
        # names — which is the thing the clause is about.

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
        # RAISED BY A FINGER, NEVER THROUGH THE SEAM. `window.__panel.produce`
        # opens the panel without walking the path that raises it, so a row
        # that has lost its `data-panel` on a busy page would be invisible here
        # while every hold below stayed green — the shape this suite has
        # already paid for once, in a rule that drove the seam and could not
        # see the wait it existed to refuse. The tap's own answer is held, so a
        # missing path FAILS rather than opening nothing quietly.
        aim = await raise_by_finger(page, title)
        await page.wait_for_timeout(PANEL_IN)
        journal.check(
            f"« {title} » has a row a finger can raise its panel from",
            aim["tapped"],
            f"found={aim['found']} reachable={aim.get('reachable')} "
            f"at ({aim.get('x')}, {aim.get('y')}) hits {aim.get('covering')}")
        press = await page.evaluate(PRESS_THE_ACTION, "take")
        journal.check(
            f"and « {title} »'s own TAKE is reachable by a finger inside that "
            "panel — not merely present in it: a button under a message or "
            "under a panel still leaving takes no press, and a call would land "
            "on it anyway",
            press.get("found") and press.get("pressed"), str(press))
        await page.wait_for_timeout(ACTED)
        after = await page.evaluate(QUEUE)
        journal.check(
            f"« {title} » is TAKEN while the pipeline runs — the act lands "
            "(NE-DOIT-PAS-3)",
            title in after["inFlight"] and title not in after["takeable"],
            f"{before['takeable']} → {after['takeable']}")

        # ── PAUSING A FOLLOW, from its own panel, while the pipeline runs ───
        #
        # ON THE PAGE THAT DRAWS A FOLLOW, and that is a correction. This half
        # used to raise the panel through the seam on the ACQUISITIONS page,
        # where a followed medium not currently in flight has no row at all —
        # so it walked a panel no finger there could open, and said nothing
        # about it. The clause is about an action asked while the machine is
        # busy; where the operator asks it is the follows list, and the
        # pipeline is put back to work on top of that page exactly as it was on
        # the first.
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("""()=>window.__store.write({pipe: "running"})""")
        await page.wait_for_timeout(SETTLED)
        journal.check(
            "the follows list has the pipeline busy too, so this half measures "
            "the clause and not the page",
            await page.evaluate("()=>window.__store.read().state.pipe") == "running")

        drawn = await page.evaluate(
            """()=>[...document.querySelectorAll('[data-panel]')].map(
                 (one) => one.dataset.panel)""")
        watched = next(
            (one for one in before["follows"]
             if one in drawn or any(seen.endswith(":" + one) for seen in drawn)),
            "")
        was = await page.evaluate(
            "(t)=>(window.__followActions?.all() || []).find((one) => one.t === t)?.st",
            watched)
        follow_aim = (await raise_by_finger(page, watched) if watched
                      else {"tapped": False, "found": False})
        await page.wait_for_timeout(PANEL_IN)
        journal.check(
            f"a followed medium has a row a finger can raise its panel from — « {watched} »",
            bool(watched) and follow_aim["tapped"],
            f"{len(drawn)} row(s) drawn, found={follow_aim['found']} "
            f"reachable={follow_aim.get('reachable')} hits {follow_aim.get('covering')}")
        press = await page.evaluate(PRESS_THE_ACTION, "pause")
        await page.wait_for_timeout(ACTED)
        journal.check(
            f"« {watched} »'s panel offers to pause it while the pipeline runs, "
            "and a FINGER reaches that action — hit-tested at its own centre, "
            "like the row that raised the panel",
            press.get("found") and press.get("pressed"), f"{watched}: {press}")
        # THE STATE MOVED, whatever it moved TO. « paused » was this rule's
        # first guess and it is the app's `disabled` — the act toggles between
        # `disabled` and the medium's resting state. What the clause is about is that the act LANDED, so the hold
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

        # ── AND A SEASON IS ASKED FOR, WHILE THE MACHINE IS STILL BUSY ────
        #
        # THE THIRD OF THIS WAVE'S OPERATIONS, asked through its own button
        # rather than through the layer: `grabSeasonForFollow` is the one whose
        # surface this walk can already reach, and the clause is about the ASK
        # landing, so the ask is made the way the operator makes it. The other
        # two are held under a busy pipeline by their own rules — R125 for the
        # season grab's own walk, R126 for the requeue — and what this rule adds
        # is that the SAME refusal sweep covers them: `asked` records every one
        # of the three by address, whatever it was answered.
        with_a_hole = await page.evaluate(THE_MEDIUM_WITH_A_HOLE)
        if with_a_hole is not None:
            grab_aim = await raise_by_finger(page, with_a_hole["title"])
            await page.wait_for_timeout(PANEL_IN)
            journal.check(
                f"« {with_a_hole['title']} » has a season with a hole, and a "
                "row a finger can raise its panel from",
                grab_aim["tapped"], str(grab_aim))
            press = await page.evaluate(PRESS_THE_ACTION_BY_PART,
                                        "season/grab")
            await page.wait_for_timeout(ACTED)
            journal.check(
                "and its « récupérer cette saison » is reachable by a finger "
                "while the pipeline runs — the act the clause is about",
                press.get("found") and press.get("pressed"), str(press))
        asked = await page.evaluate(ANSWERED, list(ADDED_OPERATIONS))
        journal.check(
            "an operation this wave added was really ASKED while the machine "
            "was busy — an empty list would make the hold below it green about "
            "nothing, which is how the first version of it read the network and "
            "saw no ask at all",
            bool(asked), str(asked[:3]))
        journal.check(
            "and every one that was asked was answered WITHOUT a refusal — "
            "queued is an answer, 409 is not (NE-DOIT-PAS-3)",
            bool(asked) and all(not one.startswith("409") for one in asked),
            str(asked[:3]))

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
